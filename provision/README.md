# Декларативный провижининг GitLab

Скрипты в этом каталоге приводят self-managed GitLab к состоянию «готов к работе
с 1С». Всё, что создаётся, — идемпотентно: повторный запуск обновляет, а не дублирует.

```
provision/
├── gitlab_provision.py   # группы, проекты, шаблоны, переменные, system hook
├── .env.example          # конфигурация (скопировать в .env)
└── hook-service/         # сервис автодонастройки новых проектов
    ├── app.py
    ├── Dockerfile
    └── README.md
```

## Что создаётся

| Объект                                    | Назначение                                                          |
| ----------------------------------------- | ------------------------------------------------------------------- |
| группа `onec-platform`                    | все рабочие проекты 1С; переменные CI/CD наследуются                |
| проект `onec-platform/ci-templates`       | центральный pipeline (`ci/` из этого репо)                          |
| группа `onec-templates`                   | источник instance-level шаблонов                                    |
| проект `onec-templates/edt-configuration` | шаблон проекта EDT (`templates/edt-configuration/` + `ci/scripts/`) |
| system hook                               | `project_create` → `hook-service`                                   |
| сервис `hook-service`                     | переменные, защита веток и тегов, правила MR нового проекта         |

После этого сотрудник: **New project → Create from template → Instance →
«Конфигурация 1С (EDT)»** — и получает репозиторий с готовым pipeline,
настройками анализа и защитой веток.

## Порядок раскатки

### 1. Токен администратора GitLab

Создать Personal Access Token у пользователя с ролью **Administrator**
(обычно `root`): _User settings → Access tokens_, scope **`api`**.
Токен — секрет, в git не коммитить.

### 2. Конфигурация

```bash
cd provision
cp .env.example .env
$EDITOR .env      # GITLAB_URL, GITLAB_TOKEN, SONAR_ADMIN_PASSWORD, HOOK_SECRET
```

`SONAR_ADMIN_PASSWORD` нужен, чтобы скрипт перевыпустил токен `gitlab-ci`
в SonarQube. Если токен уже есть — заполнить `SONAR_TOKEN` и оставить пароль пустым.
`HOOK_SECRET` — любая случайная строка (например, `openssl rand -hex 24`), та же,
что в `docker/.env`.

### 3. Предпросмотр и применение

```bash
python3 provision/gitlab_provision.py --dry-run
python3 provision/gitlab_provision.py
```

Скрипт использует только стандартную библиотеку Python 3.

### 4. Сервис автодонастройки

```bash
cd docker
# в docker/.env: GITLAB_ADMIN_TOKEN (тот же PAT), HOOK_SECRET
docker compose --profile provisioning up -d --build hook-service
curl -s http://localhost:8099/health   # изнутри сети; с хоста порт не опубликован
```

### 5. Проверка

1. Создать проект из шаблона (Instance → «Конфигурация 1С (EDT)»).
2. В проекте: **Settings → CI/CD → Variables** — должны появиться `APP_NAME`,
   `SONAR_PROJECT_KEY`. Переменные `ONEC_ENABLED`, `ONEC_CONFIG_PATH`,
   `SONAR_HOST_URL`, `SONAR_TOKEN` наследуются от группы `onec-platform`.
3. **Settings → Repository → Protected branches** — `main`, `release/*`; теги `v*`.
4. **Build → Pipelines** — pipeline `lint` должен стартовать на MR.
5. Проверить, что стадии `build/test/...` отсутствуют при `ONEC_ENABLED=false`.

## Ограничения

- `include: project:` требует, чтобы `ci-templates` был доступен создателю
  pipeline; проекты создаются с видимостью **Internal**.
- В GitLab 19.6 настройка «источник instance-шаблонов»
  (`custom_project_templates_group_id`) **не входит в permitted params API** —
  скрипт пишет предупреждение. Задайте её один раз в
  **Admin → Settings → Templates → Custom project templates** (группа
  `onec-templates`) или через `gitlab-rails runner`. На хосте с 4 ГБ RAM
  Rails-runner может вызвать OOM, поэтому предпочтителен веб-интерфейс.
- `SONAR_TOKEN` намеренно **не protected** — иначе MR из `feature/*` не увидит
  переменную и `lint` упадёт.
- `hook-service` не трогает служебные проекты `onec-platform/ci-templates` и
  группу `onec-templates` (`SKIP_PATHS`): иначе их `main` станет push-0 и
  провижининг не сможет обновлять библиотеку и шаблон.
- System hook ходит по внутреннему имени `hook-service`; снаружи оно не резолвится.
