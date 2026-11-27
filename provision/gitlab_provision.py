#!/usr/bin/env python3
"""Декларативный провижининг GitLab для 1С-платформы.

Идемпотентно приводит self-managed GitLab к нужному состоянию:

  1. группа `onec-platform` и проект-библиотека `ci-templates` (содержимое `ci/`);
  2. группа шаблонов `onec-templates` и проект-шаблон `edt-configuration`
     (содержимое `templates/edt-configuration/` + скрипты из `ci/scripts/`);
  3. группа шаблонов назначается источником instance-level project templates;
  4. переменные CI/CD на уровне группы (SONAR_HOST_URL, SONAR_TOKEN, ONEC_ENABLED, ...);
  5. system hook на сервис автодонастройки (project_create).

Требуется только Python 3 (stdlib) и токен GitLab с правами admin (api scope).
Запуск:
    cp provision/.env.example provision/.env   # заполнить
    python3 provision/gitlab_provision.py --dry-run
    python3 provision/gitlab_provision.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Конфигурация из окружения / provision/.env
# ---------------------------------------------------------------------------


def load_env(path: Path) -> None:
    """Простой парсер KEY=VALUE без зависимостей."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env(ROOT / "provision" / ".env")

GITLAB_URL = os.environ.get("GITLAB_URL", "http://localhost:8929").rstrip("/")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
CI_GROUP = os.environ.get("CI_GROUP", "onec-platform")
CI_TEMPLATES_PROJECT = os.environ.get("CI_TEMPLATES_PROJECT", "ci-templates")
TEMPLATE_GROUP = os.environ.get("TEMPLATE_GROUP", "onec-templates")
TEMPLATE_PROJECT = os.environ.get("TEMPLATE_PROJECT", "edt-configuration")

SONAR_URL = os.environ.get("SONAR_URL", "http://localhost:9000").rstrip("/")
SONAR_CI_URL = os.environ.get("SONAR_CI_URL", "http://sonarqube:9000").rstrip("/")
SONAR_ADMIN_USER = os.environ.get("SONAR_ADMIN_USER", "admin")
SONAR_ADMIN_PASSWORD = os.environ.get("SONAR_ADMIN_PASSWORD", "")
SONAR_TOKEN_ENV = os.environ.get("SONAR_TOKEN", "")

HOOK_URL = os.environ.get("HOOK_URL", "http://hook-service:8099/hooks/gitlab")
HOOK_SECRET = os.environ.get("HOOK_SECRET", "")

ONEC_ENABLED = os.environ.get("ONEC_ENABLED", "false").lower()
ONEC_CONFIG_PATH = os.environ.get("ONEC_CONFIG_PATH", "src")

DRY = False


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str) -> NoReturn:
    log(f"ОШИБКА: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# GitLab API
# ---------------------------------------------------------------------------


def api(method: str, path: str, data: dict | None = None) -> tuple[int, str]:
    if DRY and method != "GET":
        log(f"  [dry-run] {method} {path}")
        return 200, "{}"

    url = f"{GITLAB_URL}/api/v4{path}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        fail(f"GitLab недоступен: {url}: {exc}")


def get_json(path: str) -> dict | None:
    status, body = api("GET", path)
    if status == 200:
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return None


def ensure_group(path: str) -> dict:
    if DRY:
        log(f"  [dry-run] группа {path}")
        return {"id": 0, "full_path": path}
    existing = get_json(f"/groups/{urllib.parse.quote(path, safe='')}")
    if existing:
        return existing
    parent_path, _, name = path.rpartition("/")
    parent = ensure_group(parent_path) if parent_path else None
    payload = {"name": name, "path": name, "visibility": "internal"}
    if parent:
        payload["parent_id"] = parent["id"]
    status, body = api("POST", "/groups", payload)
    if status not in (200, 201):
        fail(f"не удалось создать группу {path}: {status} {body}")
    log(f"  + группа {path}")
    return json.loads(body)


def ensure_project(full_path: str) -> dict:
    if DRY:
        log(f"  [dry-run] проект {full_path}")
        return {"id": 0, "path_with_namespace": full_path, "default_branch": "main"}
    existing = get_json(f"/projects/{urllib.parse.quote(full_path, safe='')}")
    if existing:
        return existing
    group_path, _, name = full_path.rpartition("/")
    group = ensure_group(group_path) if group_path else None
    payload = {
        "name": name,
        "path": name,
        "visibility": "internal",
        "initialize_with_readme": True,
    }
    if group:
        payload["namespace_id"] = group["id"]
    status, body = api("POST", "/projects", payload)
    if status not in (200, 201):
        # гонка: проект мог быть создан параллельно
        existing = get_json(f"/projects/{urllib.parse.quote(full_path, safe='')}")
        if existing:
            return existing
        fail(f"не удалось создать проект {full_path}: {status} {body}")
    log(f"  + проект {full_path}")
    return json.loads(body)


# ---------------------------------------------------------------------------
# Раскатка файлов
# ---------------------------------------------------------------------------


def read_file(path: Path, replacements: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def push_tree(
    project: dict, sources: dict[Path, str], replacements: dict[str, str], message: str
) -> None:
    """sources: {локальный_каталог: префикс_в_репозитории}."""
    if DRY:
        for src, prefix in sources.items():
            log(
                f"  [dry-run] залить {src.relative_to(ROOT)} → {project['path_with_namespace']}/{prefix or '.'}"
            )
        return

    pid = project["id"]
    branch = project.get("default_branch") or "main"
    actions: list[dict] = []

    for src, prefix in sources.items():
        for path in sorted(src.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            rel = path.relative_to(src).as_posix()
            dest = f"{prefix.rstrip('/')}/{rel}" if prefix else rel
            content = read_file(path, replacements)
            encoded = urllib.parse.quote(dest, safe="")
            status, current = api(
                "GET", f"/projects/{pid}/repository/files/{encoded}/raw?ref={branch}"
            )
            if status == 200 and current == content:
                continue
            action = "update" if status == 200 else "create"
            actions.append(
                {
                    "action": action,
                    "file_path": dest,
                    "encoding": "base64",
                    "content": base64.b64encode(content.encode("utf-8")).decode(
                        "ascii"
                    ),
                    "execute_filemode": dest.endswith(".sh"),
                }
            )

    if not actions:
        log(f"  = {project['path_with_namespace']}: без изменений")
        return

    status, body = api(
        "POST",
        f"/projects/{pid}/repository/commits",
        {"branch": branch, "commit_message": message, "actions": actions},
    )
    if status not in (200, 201):
        fail(
            f"не удалось закоммитить в {project['path_with_namespace']}: {status} {body}"
        )
    log(f"  ↑ {project['path_with_namespace']}: {len(actions)} файл(ов)")


# ---------------------------------------------------------------------------
# Переменные, шаблоны, hook
# ---------------------------------------------------------------------------


def ensure_group_variable(
    group_id: int, key: str, value: str, masked: bool = False
) -> None:
    payload = {
        "value": value,
        "masked": masked,
        "protected": False,  # важно: иначе MR из feature/* не увидит переменную
        "environment_scope": "*",
    }
    if DRY:
        log(f"  [dry-run] переменная группы {key}={'***' if masked else value}")
        return
    encoded = urllib.parse.quote(key, safe="")
    existing = get_json(f"/groups/{group_id}/variables/{encoded}")

    def write(data: dict) -> tuple[int, str]:
        if existing:
            return api("PUT", f"/groups/{group_id}/variables/{encoded}", data)
        return api("POST", f"/groups/{group_id}/variables", {"key": key, **data})

    status, body = write(payload)
    if status not in (200, 201) and masked:
        # значение не проходит правила маскировки — сохраняем без неё
        log(f"  ! {key}: не удалось замаскировать ({status}), сохраняю без masked")
        status, body = write({**payload, "masked": False})
    if status not in (200, 201):
        fail(f"не удалось задать переменную {key}: {status} {body}")
    log(f"  = переменная {key}")


def set_custom_templates_group(group_id: int) -> None:
    if DRY:
        log(f"  [dry-run] custom_project_templates_group_id={group_id}")
        return
    status, body = api(
        "PUT", "/application/settings", {"custom_project_templates_group_id": group_id}
    )
    if status == 200:
        log("  = группа шаблонов назначена источником instance-шаблонов")
        return
    # В GitLab 19.6 параметр не входит в permitted params API (настройка живёт
    # в ApplicationSetting, но наружу не отдаётся). Задаём вручную один раз.
    log("  ! API не принимает custom_project_templates_group_id (GitLab 19.6).")
    log(
        "    Задайте один раз в Admin → Settings → Templates → Custom project templates,"
    )
    log(
        f"    либо на сервере: docker exec gitlab gitlab-rails runner "
        + f'"s=ApplicationSetting.current; s.custom_project_templates_group_id={group_id}; s.save!"'
    )
    log("    (на 4 ГБ RAM Rails-runner может вызвать OOM — лучше через веб-интерфейс)")


def ensure_system_hook() -> None:
    if not HOOK_SECRET:
        log("  ! HOOK_SECRET не задан — system hook пропущен")
        return
    payload = {"url": HOOK_URL, "token": HOOK_SECRET, "enable_ssl_verification": False}
    if DRY:
        log(f"  [dry-run] system hook → {HOOK_URL}")
        return
    hooks = get_json("/hooks") or []
    for hook in hooks:
        if hook.get("url") == HOOK_URL:
            status, _ = api("PUT", f"/hooks/{hook['id']}", payload)
            if status not in (200, 201):
                status, _ = api("POST", "/hooks", payload)
            log("  = system hook обновлён")
            return
    status, body = api("POST", "/hooks", payload)
    if status not in (200, 201):
        fail(f"не удалось создать system hook: {status} {body}")
    log(f"  + system hook → {HOOK_URL}")


# ---------------------------------------------------------------------------
# SonarQube: токен для CI
# ---------------------------------------------------------------------------


def sonar_request(
    method: str, path: str, auth: str, data: bytes | None = None
) -> tuple[int, str]:
    url = f"{SONAR_URL}{path}"
    headers = {"Authorization": f"Basic {auth}"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, str(exc)


def ensure_sonar_token() -> str:
    if SONAR_TOKEN_ENV:
        return SONAR_TOKEN_ENV
    if not SONAR_ADMIN_PASSWORD:
        log("  ! SONAR_TOKEN и SONAR_ADMIN_PASSWORD не заданы — Sonar-токен пропущен")
        return ""
    if DRY:
        log("  [dry-run] сгенерировать SonarQube-токен gitlab-ci")
        return "dry-run-token"

    auth = base64.b64encode(
        f"{SONAR_ADMIN_USER}:{SONAR_ADMIN_PASSWORD}".encode()
    ).decode()
    # Перевыпускаем стабильный токен, чтобы не копить мусор.
    sonar_request("POST", "/api/user_tokens/revoke?name=gitlab-ci", auth)
    status, body = sonar_request(
        "POST", "/api/user_tokens/generate?name=gitlab-ci", auth
    )
    if status != 200:
        log(f"  ! не удалось создать Sonar-токен: {status} {body}")
        return ""
    token = json.loads(body).get("token", "")
    log("  + SonarQube-токен gitlab-ci")
    return token


# ---------------------------------------------------------------------------
# Основной сценарий
# ---------------------------------------------------------------------------


def main() -> None:
    global DRY
    parser = argparse.ArgumentParser(
        description="Идемпотентный провижининг GitLab для 1С"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="только показать действия"
    )
    parser.add_argument(
        "--skip-hook", action="store_true", help="не создавать system hook"
    )
    parser.add_argument(
        "--skip-sonar", action="store_true", help="не трогать SonarQube"
    )
    args = parser.parse_args()
    DRY = args.dry_run

    if not GITLAB_TOKEN:
        fail("GITLAB_TOKEN не задан (нужен admin PAT со scope api)")

    template_path = f"{CI_GROUP}/{CI_TEMPLATES_PROJECT}"
    template_full = f"{TEMPLATE_GROUP}/{TEMPLATE_PROJECT}"
    log(f"GitLab: {GITLAB_URL}")
    log(f"Библиотека CI: {template_path}")
    log(f"Шаблон проекта: {template_full}")

    log("\n[1/5] Группа и проект-библиотека CI")
    ci_project = ensure_project(template_path)
    push_tree(
        ci_project,
        {ROOT / "ci": ""},
        {},
        "chore: синхронизировать центральную CI-библиотеку 1С",
    )

    log("\n[2/5] Группа шаблонов и проект-шаблон")
    template_group = ensure_group(TEMPLATE_GROUP)
    project_template = ensure_project(template_full)
    push_tree(
        project_template,
        {
            ROOT / "templates" / "edt-configuration": "",
            # один источник истины для скриптов: подкладываем их в шаблон
            ROOT / "ci" / "scripts": "ci/scripts",
        },
        {"__CI_TEMPLATES_PROJECT__": template_path},
        "chore: синхронизировать шаблон проекта 1С (EDT)",
    )

    log("\n[3/5] Instance-level project templates")
    set_custom_templates_group(template_group["id"])

    log("\n[4/5] Переменные CI/CD группы")
    sonar_token = "" if args.skip_sonar else ensure_sonar_token()
    group = ensure_group(CI_GROUP)
    ensure_group_variable(group["id"], "SONAR_HOST_URL", SONAR_CI_URL)
    if sonar_token:
        ensure_group_variable(group["id"], "SONAR_TOKEN", sonar_token, masked=True)
    ensure_group_variable(group["id"], "ONEC_ENABLED", ONEC_ENABLED)
    ensure_group_variable(group["id"], "ONEC_CONFIG_PATH", ONEC_CONFIG_PATH)
    ensure_group_variable(group["id"], "CI_TEMPLATES_PROJECT", template_path)

    log("\n[5/5] System hook автодонастройки")
    if args.skip_hook:
        log("  - пропущено (--skip-hook)")
    else:
        ensure_system_hook()

    log("\nГотово." if not DRY else "\nDry-run завершён, изменений не внесено.")


if __name__ == "__main__":
    main()
