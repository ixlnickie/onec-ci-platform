# Тест линтера BSL

Фикстуры и скрипт, которые проверяют сам линтер: он должен ловить критичную
ошибку и не валить корректный код.

| Файл                | Ожидание                              |
| ------------------- | ------------------------------------- |
| `fixtures/good.bsl` | 0 диагностик уровня **Error**         |
| `fixtures/bad.bsl`  | есть **Error** — пропущен `КонецЕсли` |

## Локально

```bash
BSL_LS_JAR=/path/to/bsl-language-server-1.0.7-exec.jar bash tests/bsl/check.sh
```

Скрипт запускает `bsl-language-server analyze` в режиме JSON-отчёта и проверяет,
что у `good.bsl` нет `Error`, а у `bad.bsl` он есть.

## В CI

- **GitHub Actions** job `bsl` скачивает BSL Language Server v1.0.7 и запускает
  `tests/bsl/check.sh`.
- **GitLab** это же проверяется на реальном SonarQube в проекте
  `onec-platform/bsl-test`:
  - зелёный pipeline #11 (`main`);
  - красный pipeline #12 (`test/bad`, quality gate failed).
    Доказательства: [`docs/evidence/bsl-test.txt`](../../docs/evidence/bsl-test.txt).
