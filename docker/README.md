# Docker-стенд CI/CD для 1С

Развёртывание GitLab CE, GitLab Runner, SonarQube (с плагином BSL) и PostgreSQL
через Docker Compose. Доступ по IP и портам (без домена и nginx).

## Состав и порты

| Сервис     | Порт хоста | Назначение                       |
| ---------- | ---------- | -------------------------------- |
| GitLab     | 8929       | веб-интерфейс `http://<IP>:8929` |
| GitLab SSH | 2224       | git по SSH                       |
| SonarQube  | 9000       | веб-интерфейс `http://<IP>:9000` |
| PostgreSQL | —          | только внутри сети compose       |

## Требования к хосту

- Docker Engine + Compose v2.
- Минимум: 2 vCPU, 4 ГБ RAM, 40 ГБ диска.
  Стек урезан под 4 ГБ: heap SonarQube по 512 МБ, GitLab в single-puma, без Prometheus.
- `vm.max_map_count >= 262144` (для Elasticsearch в SonarQube):
  ```
  sysctl -w vm.max_map_count=262144
  echo 'vm.max_map_count=262144' > /etc/sysctl.d/99-sonar.conf
  ```

## Первый запуск

1. Скопировать `.env.example` в `.env` и заполнить пароли и адрес:
   ```
   cp .env.example .env
   ```
2. Поднять стек:
   ```
   docker compose up -d
   ```
3. Проверить:
   ```
   docker compose ps
   curl -s http://localhost:9000/api/system/status
   ```
4. Каталоги `sonar/*` должны принадлежать uid 1000 (иначе SonarQube не стартует):
   ```
   chown -R 1000:1000 sonar
   ```

## Плагин BSL и quality gate

- Плагин кладётся в `sonar/extensions/plugins/` (см. `../ci/scripts/fetch-bsl-plugin.sh`).
- Quality gate `onec-gate` создаётся через `../ci/scripts/sonar-setup.sh`.

## Бэкапы

`backup.sh` сохраняет архив GitLab, `gitlab.rb`, `gitlab-secrets.json` и дамп БД SonarQube
в `/opt/onec-ci/backups/<timestamp>`, хранит 7 дней. Cron:

```
0 3 * * * /opt/onec-ci/docker/backup.sh >> /var/log/onec-ci-backup.log 2>&1
```

## Автодонастройка проектов (опционально)

Сервис `hook-service` живёт в профиле `provisioning` и не стартует при обычном
`docker compose up -d`. Ему нужен каталог `../provision` рядом с `docker/`
(то есть разворачивается весь репозиторий, а не только `docker/`):

```bash
cp ../provision/.env.example ../provision/.env   # заполнить
docker compose --profile provisioning up -d --build hook-service
```

System hook в GitLab создаётся скриптом `../provision/gitlab_provision.py`.
Подробности — [`../provision/README.md`](../provision/README.md).

## Ограничение прототипа

Стенд рассчитан на небольшой VPS. При 4 ГБ RAM активно используется swap;
для стабильной работы под нагрузкой рекомендуется 8 ГБ RAM.
