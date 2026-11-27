#!/usr/bin/env bash
# Ручной откат продуктивной ИБ из бэкапа.
# Использование: rollback.sh <путь к .dt>
# Требует платформу 1С / vrunner на раннере `onec`. Не запускалось.
set -euo pipefail

BACKUP="${1:?укажите путь к бэкапу .dt}"
: "${PROD_IB:?строка подключения продуктивной ИБ}"

test -f "$BACKUP" || { echo "бэкап не найден: $BACKUP"; exit 1; }

echo "Откат продуктивной ИБ из $BACKUP"
vrunner restore --ibconnection "$PROD_IB" --src "$BACKUP"

echo "Откат выполнен"
