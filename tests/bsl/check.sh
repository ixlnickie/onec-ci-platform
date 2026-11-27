#!/usr/bin/env bash
# Проверка линтера BSL на фикстурах:
#   good.bsl — не должно быть диагностик уровня Error;
#   bad.bsl  — должна быть ошибка разбора (Error).
#
# Требуется Java 17+ и bsl-language-server exec jar:
#   BSL_LS_JAR=/path/to/bsl-language-server-1.0.7-exec.jar bash tests/bsl/check.sh
set -euo pipefail

: "${BSL_LS_JAR:?укажите BSL_LS_JAR — путь к bsl-language-server-*-exec.jar}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
cd "$OUT"

set +e
java -jar "$BSL_LS_JAR" analyze \
  --srcDir "$ROOT/fixtures" \
  --workspaceDir "$OUT" \
  --outputDir "$OUT" \
  --reporter json \
  --silent
RC=$?
set -e

REPORT="$OUT/bsl-json.json"
if [ ! -f "$REPORT" ]; then
  REPORT="$(find "$OUT" -name bsl-json.json | head -1)"
fi
if [ -z "$REPORT" ] || [ ! -f "$REPORT" ]; then
  echo "FAIL: отчёт bsl-json.json не создан (код bsl-language-server: $RC)"
  exit 1
fi

python3 - "$REPORT" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))


def errors(name):
    for fileinfo in report.get("fileinfos", []):
        if fileinfo.get("path", "").endswith("/" + name):
            return [
                d for d in fileinfo.get("diagnostics", [])
                if d.get("severity") == "Error"
            ]
    return None


good = errors("good.bsl")
bad = errors("bad.bsl")
if good is None or bad is None:
    print("FAIL: в отчёте нет good.bsl/bad.bsl")
    sys.exit(1)
if good:
    messages = "; ".join(d.get("message", "") for d in good)
    print(f"FAIL: good.bsl содержит Error: {messages}")
    sys.exit(1)
if not bad:
    print("FAIL: bad.bsl не дал ошибку разбора")
    sys.exit(1)
print("OK: good.bsl без Error; bad.bsl с Error ->", bad[0].get("message", ""))
PY
