# Центральная CI-библиотека 1С

Каталог `ci/` — источник истины для GitLab-проекта `onec-platform/ci-templates`.
Его содержимое раскатывается в GitLab скриптом `provision/gitlab_provision.py`,
после чего любой проект конфигурации 1С подключает пайплайн одной строкой:

```yaml
include:
  - project: "onec-platform/ci-templates"
    ref: main
    file: "/onec-pipeline.yml"
```

## Файлы

| Файл                                | Назначение                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| `onec-pipeline.yml`                 | Переиспользуемый pipeline: lint → build → test → artifact → deploy-test → deploy-prod |
| `.gitlab-ci.yml`                    | Заглушка: в самом проекте-библиотеке pipeline не запускаются                          |
| `scripts/build.sh`                  | Сборка `.cf`/`.cfe` из исходников EDT (раннер `onec`)                                 |
| `scripts/test.sh`                   | Автотесты на отдельной тестовой ИБ (vanessa-runner/xUnit)                             |
| `scripts/deploy-test.sh`            | Обновление тестового контура после merge в `release/*`                                |
| `scripts/deploy-prod.sh`            | Обновление прода по тегу: бэкап → обновление                                          |
| `scripts/rollback.sh`               | Откат прода из бэкапа вручную                                                         |
| `scripts/sonar-setup.sh`            | Создание quality gate `onec-gate`                                                     |
| `scripts/fetch-bsl-plugin.sh`       | Загрузка плагина BSL для SonarQube                                                    |
| `scripts/register-runner-docker.sh` | Регистрация docker-раннера                                                            |

## Стадии и требования

| Стадия        | Раннер   | Платформа 1С | Когда запускается                           |
| ------------- | -------- | ------------ | ------------------------------------------- |
| `lint`        | `docker` | нет          | MR, main, release/*, теги, ручной запуск    |
| `build`       | `onec`   | да           | MR, release/*, теги при `ONEC_ENABLED=true` |
| `test`        | `onec`   | да           | как `build`                                 |
| `artifact`    | `onec`   | да           | release/* и теги                            |
| `deploy-test` | `onec`   | да           | release/*                                   |
| `deploy-prod` | `onec`   | да           | теги `vX.Y.Z`, только вручную               |

## Переменные

Задаются на уровне группы `onec-platform` и наследуются проектами
(см. `provision/gitlab_provision.py`):

| Переменная         | Значение                | Примечание                                     |
| ------------------ | ----------------------- | ---------------------------------------------- |
| `SONAR_HOST_URL`   | `http://sonarqube:9000` | адрес из сети docker compose                   |
| `SONAR_TOKEN`      | токен SonarQube         | masked                                         |
| `ONEC_ENABLED`     | `false` / `true`        | `true`, когда на раннере `onec` есть платформа |
| `ONEC_CONFIG_PATH` | `src`                   | путь к исходникам EDT                          |

## SonarQube: ключ и quality gate

- Ключ проекта — `CI_PROJECT_PATH` с заменой `/` на `:` (Sonar не допускает `/`);
  hook-service кладёт его в `SONAR_PROJECT_KEY`.
- Сканер запускается с `sonar.qualitygate.wait=true`: красный quality gate
  `onec-gate` валит job `lint`, и merge блокируется.

## Ограничение прототипа

Стадии `build`, `test`, `artifact`, `deploy-test`, `deploy-prod` описаны и готовы к
запуску, но не запускались: на стенде пока нет платформы 1С и раннера с тегом `onec`.
До её появления они выключены (`ONEC_ENABLED=false`) и не ломают pipeline.
