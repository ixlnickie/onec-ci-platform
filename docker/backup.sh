#!/usr/bin/env bash
# Резервное копирование GitLab и SonarQube (БД) в /opt/onec-ci/backups/<timestamp>.
# Запуск вручную: bash /opt/onec-ci/docker/backup.sh
# В cron (root):  0 3 * * * /opt/onec-ci/docker/backup.sh >> /var/log/onec-ci-backup.log 2>&1
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
set -a; . ./.env; set +a

BACKUP_ROOT="${BACKUP_ROOT:-/opt/onec-ci/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
TS="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT/$TS"
mkdir -p "$DEST"

echo "[gitlab] backup"
docker exec -t gitlab gitlab-backup create CRON=1
docker cp gitlab:/etc/gitlab/gitlab.rb "$DEST/gitlab.rb" 2>/dev/null || true
docker cp gitlab:/etc/gitlab/gitlab-secrets.json "$DEST/gitlab-secrets.json" 2>/dev/null || true
# перенести свежий архив из тома в каталог бэкапа, чтобы не держать копию дважды
cp -a gitlab/data/backups/*.tar "$DEST/" 2>/dev/null || true
find gitlab/data/backups -maxdepth 1 -name '*.tar' -delete 2>/dev/null || true

echo "[sonar] db dump"
docker exec -t sonar-postgres pg_dump -U "${SONAR_DB_USER:-sonar}" "${SONAR_DB_NAME:-sonar}" > "$DEST/sonar.sql"

echo "[prune] older than ${KEEP_DAYS} days"
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} + 2>/dev/null || true

echo "done: $DEST"
du -sh "$DEST"
