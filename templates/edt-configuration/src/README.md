# Исходники конфигурации (EDT)

Сюда кладётся проект 1C:EDT. Ожидаемая структура (создаётся самим EDT при
экспорте/импорте конфигурации):

```
src/
└── <ИмяКонфигурации>/
    ├── .project
    ├── .settings/
    └── src/
        └── Configuration/
            ├── Configuration.mdo
            ├── Languages/
            ├── CommonModules/
            └── ...
```

`.project` и `.settings/` **коммитятся** — без них проект не открывается в EDT.
Каталог `/.metadata/` (рабочая область Eclipse) в git не попадает.

Если конфигурация ещё не выгружена в EDT: в 1C:EDT → File → Export →
Configuration to XML/EDT, затем скопировать результат в `src/`.

Проверка, что всё на месте:

```bash
ls src/*/src/Configuration/Configuration.mdo
```
