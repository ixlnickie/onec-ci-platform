#!/usr/bin/env python3
"""Сервис автодонастройки GitLab-проектов 1С.

Принимает GitLab system hook `project_create` и через GitLab API:

  * включает merge только при зелёном pipeline и resolved-обсуждениях;
  * защищает ветки `main` и `release/*`, теги `v*`;
  * проставляет переменные проекта (APP_NAME, SONAR_PROJECT_KEY, ONEC_*).

Запускается в docker compose вместе со стендом (профиль `provisioning`).
Зависимостей нет — только стандартная библиотека Python.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GITLAB_URL = os.environ.get("GITLAB_URL", "http://gitlab:8929").rstrip("/")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", os.environ.get("HOOK_SECRET", ""))
PORT = int(os.environ.get("PORT", "8099"))
# Служебные проекты, которые hook-service не трогает (префикс с "/" — целая группа).
SKIP_PATHS = [
    p.strip()
    for p in os.environ.get(
        "SKIP_PATHS", "onec-platform/ci-templates,onec-templates/"
    ).split(",")
    if p.strip()
]


def log(msg: str) -> None:
    print(msg, flush=True)


def is_skipped(full_path: str) -> bool:
    full_path = full_path or ""
    for item in SKIP_PATHS:
        if item.endswith("/"):
            if full_path.startswith(item):
                return True
        elif full_path == item:
            return True
    return False


def api(method: str, path: str, data: dict | None = None) -> tuple[int, str]:
    url = f"{GITLAB_URL}/api/v4{path}"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, str(exc)


def ensure_variable(pid: int, key: str, value: str, masked: bool = False) -> None:
    payload = {
        "value": value,
        "masked": masked,
        "protected": False,
        "environment_scope": "*",
    }
    encoded = urllib.parse.quote(key, safe="")
    status, _ = api("GET", f"/projects/{pid}/variables/{encoded}")
    if status == 200:
        status, body = api("PUT", f"/projects/{pid}/variables/{encoded}", payload)
    else:
        status, body = api(
            "POST", f"/projects/{pid}/variables", {"key": key, **payload}
        )
    if status not in (200, 201):
        log(f"  ! переменная {key}: {status} {body}")
    else:
        log(f"  = {key}")


def ensure_protected_branch(pid: int, name: str) -> None:
    payload = {"name": name, "push_access_level": 0, "merge_access_level": 40}
    status, body = api("POST", f"/projects/{pid}/protected_branches", payload)
    if status in (200, 201):
        log(f"  + protected branch {name}")
    elif status in (400, 409):
        log(f"  = protected branch {name} уже есть")
    else:
        log(f"  ! protected branch {name}: {status} {body}")


def ensure_protected_tag(pid: int, name: str) -> None:
    payload = {"name": name, "create_access_level": 40}
    status, body = api("POST", f"/projects/{pid}/protected_tags", payload)
    if status in (200, 201):
        log(f"  + protected tag {name}")
    elif status in (400, 409):
        log(f"  = protected tag {name} уже есть")
    else:
        log(f"  ! protected tag {name}: {status} {body}")


def configure_project(pid: int) -> None:
    # Включаем «merge только при зелёном pipeline» и прочие правила MR.
    # Если в проекте нет .gitlab-ci.yml, правило заблокировало бы все merge.
    status, body = api("GET", f"/projects/{pid}")
    branch = "main"
    if status == 200:
        branch = json.loads(body).get("default_branch") or "main"
    encoded = urllib.parse.quote(".gitlab-ci.yml", safe="")
    ci_status, _ = api(
        "GET", f"/projects/{pid}/repository/files/{encoded}?ref={branch}"
    )

    payload = {
        "only_allow_merge_if_pipeline_succeeds": ci_status == 200,
        "only_allow_merge_if_all_discussions_are_resolved": True,
        "remove_source_branch_after_merge": True,
    }
    status, body = api("PUT", f"/projects/{pid}", payload)
    if status == 200:
        log("  = настройки MR включены")
    else:
        log(f"  ! настройки MR: {status} {body}")


def on_project_create(payload: dict) -> None:
    pid = payload.get("project_id")
    full = payload.get("project_path_with_namespace") or payload.get(
        "path_with_namespace"
    )
    name = (
        payload.get("project_name")
        or payload.get("name")
        or (full or "").rsplit("/", 1)[-1]
    )
    if not pid:
        raise ValueError("project_create без project_id")
    if is_skipped(full):
        log(f"пропуск служебного проекта {full}")
        return
    log(f"Автодонастройка {full} (id={pid})")

    configure_project(pid)
    # ONEC_ENABLED и ONEC_CONFIG_PATH не задаём на уровне проекта:
    # иначе проектные значения перекроют групповые, и платформу нельзя будет
    # включить централизованно.
    ensure_variable(pid, "APP_NAME", name)
    # Sonar не допускает '/' в ключе проекта
    ensure_variable(pid, "SONAR_PROJECT_KEY", (full or name).replace("/", ":"))
    for branch in ("main", "release/*"):
        ensure_protected_branch(pid, branch)
    ensure_protected_tag(pid, "v*")


class Handler(BaseHTTPRequestHandler):
    server_version = "onec-hook/1.0"

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/hooks/gitlab":
            self._json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        token = self.headers.get("X-Gitlab-Token", "")
        if not WEBHOOK_SECRET or not hmac.compare_digest(token, WEBHOOK_SECRET):
            log("отклонено: неверный X-Gitlab-Token")
            self._json(401, {"error": "invalid token"})
            return

        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return

        event = payload.get("event_name", "")
        log(f"event={event} project={payload.get('project_path_with_namespace')}")
        try:
            if event == "project_create":
                on_project_create(payload)
        except Exception as exc:  # noqa: BLE001 — сервис не должен падать от одного события
            log(f"ОШИБКА обработки {event}: {exc}")
            self._json(500, {"error": str(exc)})
            return

        self._json(200, {"status": "ok", "event": event})

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        log(f"{self.address_string()} {fmt % args}")


def main() -> None:
    if not GITLAB_TOKEN:
        log("ОШИБКА: GITLAB_TOKEN не задан")
        sys.exit(1)
    if not WEBHOOK_SECRET:
        log("ОШИБКА: WEBHOOK_SECRET/HOOK_SECRET не задан")
        sys.exit(1)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"hook-service слушает :{PORT}, GitLab {GITLAB_URL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
