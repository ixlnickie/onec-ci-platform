# Декларативный CI/CD для 1С

Цель: сотрудник создаёт репозиторий в GitLab — и сразу получает структуру
проекта 1С (EDT), pipeline, статический анализ, защиту веток и переменные.
Ничего не настраивается вручную.

## Из чего состоит

```
GitHub (этот репозиторий)                GitLab (self-managed)
┌───────────────────────────┐            ┌──────────────────────────────┐
│ ci/                       │  provision │ onec-platform/ci-templates   │
│ templates/edt-config……    │ ─────────► │ onec-templates/edt-config…   │
│ provision/gitlab_provis…  │            │ system hook → hook-service   │
└───────────────────────────┘            └──────────────────────────────┘
                                                       │ project_create
                                                       ▼
                                          ┌──────────────────────────────┐
                                          │ hook-service (docker)        │
                                          │ переменные / ветки / теги    │
                                          └──────────────────────────────┘
```

### 1. Центральная библиотека (`ci/`)

Раскатывается в `onec-platform/ci-templates`. Содержит единственный
переиспользуемый pipeline `onec-pipeline.yml` и скрипты стадий.

### 2. Шаблон проекта (`templates/edt-configuration/`)

Раскатывается в `onec-templates/edt-configuration` и назначается источником
instance-level шаблонов. Внутри: структура `src/`, тонкий `.gitlab-ci.yml`
(только `include`), `.bsl-language-server.json`, `sonar-project.properties`,
`.editorconfig`, `.gitignore`. Скрипты `ci/scripts/` подкладываются при
провижининге, чтобы в проекте был один источник истины.

### 3. Автодонастройка (`provision/`)

`gitlab_provision.py` создаёт группы/проекты, заливает файлы, задаёт переменные
группы и system hook. `hook-service` принимает `project_create` и через API
включает правила MR, защищает ветки/теги, проставляет переменные проекта.

## Поток «новый репозиторий»

1. `project_create` → system hook → `hook-service`.
2. Сервис ставит `APP_NAME`, `SONAR_PROJECT_KEY` (путь с `/` → `:`); защищает
   `main`, `release/*`, `v*`; включает «merge только при зелёном pipeline»
   (если есть `.gitlab-ci.yml`).
3. Проект наследует переменные группы `onec-platform`:
   `SONAR_HOST_URL`, `SONAR_TOKEN`, `CI_TEMPLATES_PROJECT`.
4. На MR запускается `lint` (SonarQube + BSL). Сканер ждёт quality gate
   (`sonar.qualitygate.wait=true`), поэтому красный `onec-gate` валит pipeline
   и блокирует merge. Стадии 1С выключены до `ONEC_ENABLED=true`.

## Стадии

| Стадия        | Раннер   | Платформа 1С | Триггер                   |
| ------------- | -------- | ------------ | ------------------------- |
| `lint`        | `docker` | нет          | MR, main, release/*, теги |
| `build`       | `onec`   | да           | MR, release/*, теги       |
| `test`        | `onec`   | да           | как `build`               |
| `artifact`    | `onec`   | да           | release/*, теги           |
| `deploy-test` | `onec`   | да           | release/*                 |
| `deploy-prod` | `onec`   | да           | тег `vX.Y.Z` вручную      |

Подробности по переменным — в [`ci/README.md`](../ci/README.md).

## Что нужно от платформы 1С

Сейчас работает только `lint`. Для `build/test/deploy` нужны:

- раннер с тегом `onec` и установленной платформой 1С (учебная — для демо);
- переменная `ONEC_ENABLED=true` (уровень группы);
- строки подключения ИБ (`TEST_STAND_IB`, `PROD_IB`) на раннере.

После подключения учебной платформы стадии включаются без изменения pipeline.

## Ограничения

- Доступ по IP и портам, без домена и HTTPS (осознанное решение для стенда).
- Нет CI/CD components и pipeline execution policies (это Ultimate) —
  используется `include: project:` + system hook.
- 4 ГБ RAM: сервер 1С и Windows-агент на этом VPS не поднимаются; платформа
  ставится на отдельную машину-раннер.
