#!/usr/bin/env bash
# Обновление продуктивного контура по тегу vX.Y.Z.
# Запускается вручную (when: manual). Перед обновлением делает бэкап ИБ.
# Требует платформу 1С и утилиты vrunner/ibcmd на раннере `onec`. Не запускалось.
set -euo pipefail

: "${PROD_IB:?строка подключения продуктивной ИБ, например /F/var/onec/prod}"
: "${APP_VERSION:?версия артефакта}"

CF="$(ls build/*.cf | head -1)"
: "${CF:?нет собранного .cf}"

BACKUP_DIR="${PROD_BACKUP_DIR:-/var/onec/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_DIR/prod-$STAMP.dt"
mkdir -p "$BACKUP_DIR"

echo "Бэкап продуктивной ИБ → $BACKUP"
vrunner backup --ibconnection "$PROD_IB" --path "$BACKUP"

echo "Обновление конфигурации $APP_VERSION из $CF"
vrunner load --src "$CF" --ibconnection "$PROD_IB"
vrunner updatedb --ibconnection "$PROD_IB"

echo "Прод обновлён: $CF (бэкап $BACKUP)"
