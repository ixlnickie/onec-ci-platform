# Сервис автодонастройки GitLab-проектов 1С

Принимает **system hook** GitLab `project_create` и через API доводит новый
репозиторий до рабочего состояния:

- включает «merge только при зелёном pipeline» и resolved-обсуждения;
- защищает `main`, `release/*` и теги `v*`;
- проставляет переменные проекта: `APP_NAME`, `SONAR_PROJECT_KEY`,
  `ONEC_ENABLED`, `ONEC_CONFIG_PATH`.

## Запуск

В составе стенда (профиль `provisioning`):

```bash
cd docker
docker compose --profile provisioning up -d hook-service
```

Переменные (в `docker/.env`):

| Переменная           | Назначение                                           |
| -------------------- | ---------------------------------------------------- |
| `GITLAB_ADMIN_TOKEN` | PAT администратора GitLab, scope `api`               |
| `HOOK_SECRET`        | общий секрет system hook                             |
| `ONEC_ENABLED`       | стартовое значение `ONEC_ENABLED` для новых проектов |

GitLab должен достучаться до сервиса по имени `http://hook-service:8099/hooks/gitlab`
(оба контейнера в одной сети compose). Адрес system hook задаёт
`provision/gitlab_provision.py`.

## Проверка вручную

```bash
curl -s http://localhost:8099/health
curl -s -X POST http://localhost:8099/hooks/gitlab \
  -H "X-Gitlab-Token: $HOOK_SECRET" -H "Content-Type: application/json" \
  -d '{"event_name":"project_create","project_id":1,"project_path_with_namespace":"demo/x","project_name":"x"}'
```

## Безопасность

- Запросы без верного `X-Gitlab-Token` отклоняются.
- Сервис не публикует порт наружу (`expose`, не `ports`) — доступен только из сети compose.
- Токен и секрет приходят из окружения, в git не коммитятся.
