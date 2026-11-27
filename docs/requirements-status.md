# Статус 15 требований приёмки

Статусы: **выполнено** (есть реальное доказательство), **описано, не запущено**, **ожидает людей**. На момент создания черновика ничего не запускалось на стенде — все статусы обновляются людьми по факту.

| № | Требование | Статус | Доказательство |
| --- | --- | --- | --- |
| 1 | GitLab и Runner в локальной инфраструктуре | выполнено | стенд поднят: `docker/docker-compose.yml`, `docker compose ps`; GitLab `:8929`, instance-runner `docker-runner` online |
| 2 | Конфигурация в Git в формате EDT | описано, не запущено | `demo-config/README.md`; `evidence/edt-project-open.png` — [добавить] |
| 3 | Ветки main / release / feature | описано, не запущено | `regulation.md`; скрин защиты — [добавить] |
| 4 | Роли | описано, не запущено | `roles.md`; `evidence/gitlab-protected-branches.png` — [добавить] |
| 5 | Pipeline на MR | выполнено | `ci/onec-pipeline.yml`, `provision/gitlab_provision.py`; green: http://185.20.225.253:8929/onec-platform/demo-1c/-/pipelines/7 |
| 6 | Статический анализ BSL, отчёт в Sonar | выполнено | Sonar нашёл CRITICAL BUG в `src/bad.bsl`: http://185.20.225.253:9000/dashboard?id=onec-platform%3Ademo-1c |
| 7 | Анализ виден в MR, критичное блокирует merge | выполнено | pipeline 10 failed по quality gate, MR !2 `ci_must_pass`: http://185.20.225.253:8929/onec-platform/demo-1c/-/merge_requests/2; отчёт Sonar — по ссылке (виджет интеграции в этой сборке недоступен) |
| 8 | Автосборка | описано, не запущено (нужна платформа 1С) | `ci/scripts/build.sh` |
| 9 | Автотесты на тестовой ИБ | описано, не запущено (нужна платформа 1С) | `ci/scripts/test.sh` |
| 10 | Версионируемый артефакт | описано, не запущено (нужна платформа 1С) | стадия `artifact` |
| 11 | Merge в release обновляет тест | описано, не запущено (нужна платформа 1С) | `ci/scripts/deploy-test.sh` |
| 12 | Прод: подтверждение, бэкап, откат | описано, не запущено | `prod-scenario.md`, `deploy-prod.sh`, `rollback.sh` |
| 13 | Документы переданы куратору | ожидает людей | подтверждение — [добавить] |
| 14 | Схема СППР согласована | подготовлено | `docs/sppr-integration.md`; согласование концептуальной схемы зафиксировано в документе |
| 15 | Демо: зелёный и заблокированный pipeline | выполнено | green #7 http://185.20.225.253:8929/onec-platform/demo-1c/-/pipelines/7; red #10 http://185.20.225.253:8929/onec-platform/demo-1c/-/pipelines/10; `docs/evidence/ci-demo-green-red.txt` |
