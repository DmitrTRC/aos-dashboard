# Отчёт по реализации: AOS Actions + Safety + Web `/wall` (План 2)

**План:** `docs/superpowers/plans/2026-06-19-aos-actions-web.md`
**Спека:** `docs/superpowers/specs/2026-06-19-project-dashboard-design.md` (§7 actions+safety, §9 web)
**Базис:** ядро Плана 1 уже в `main`.
**Метод:** subagent-driven-development в main-сессии, строгий TDD (red → green → commit), ревью после каждой задачи.
**Статус:** завершено полностью — Task 1…10, 10/10.
**Дата:** 2026-06-19

## Покрытие задач плана

| # | Задача | Артефакт | Тестов | Коммит |
|---|--------|----------|:--:|--------|
| 1 | Валидация команд + типы результата | `aos/actions.py` | 5 | `528c9ab` |
| 2 | Shell-free runner + jsonl action log | `aos/actions.py` | 3 | `b088483` |
| 3 | `run_tests` (resolve + exec + state) | `aos/actions.py` | 4 | `67e4733` |
| 4 | `git_fetch`, `graphify`, `open_report` | `aos/actions.py` | 5 | `ee3f695` |
| 5 | `open_session` + диспетчер `run_action` | `aos/actions.py` | 4 | `5ba82e1` |
| 6 | CLI: open/test/fetch/graphify | `aos/cli.py` | 2 | `78aabff` |
| 7 | Server auth helpers + token | `aos/server.py` | 3 | `649304a` |
| 8 | HTTP read endpoints + token-guarded POST | `aos/server.py`, `aos/web/index.html` | 4 | `7968106` |
| 9 | Offline web `/wall` | `aos/web/index.html` | 1 | `83a5750` |
| 10 | `aos serve` + README + верификация | `aos/cli.py`, `README.md` | 1 | `2e6e8ef` |

## Метрики

- **Коммиты:** 10 (`528c9ab..2e6e8ef`)
- **Изменения:** 15 файлов, +968 (новый код, без удалений)
- **Тесты:** 64 passed суммарно (32 План 1 + 32 План 2), 0 failed; 2 безобидных warning
  (pytest принимает датакласс `TestState` за тест-класс)
- **Зависимости:** новых нет — stdlib (`subprocess`, `shlex`, `http.server`, `http.client`,
  `secrets`, `hmac`) + существующий PyYAML; фронтенд — vanilla JS, без CDN

## Модель безопасности (реализовано)

- Закрытый набор `ACTION_KINDS` (7 видов), единая точка входа `run_action`.
- Команды per-project проходят `validate_command` против `exec_allowlist`; запуск
  `shell=False`, список-argv, санированный env, timeout, cwd привязан к проекту.
- `graphify init` (сеть + токены LLM) требует явного подтверждения.
- `open_report` блокирует пути вне проекта; `open_session` валидирует имя проекта.
- Сервер слушает только `127.0.0.1`, проверяет Host; POST-действия требуют per-run
  токен (`~/.config/aos/token`, режим 600), сравнение через `hmac.compare_digest`.

## Смоук

`aos serve --no-browser` + `curl -s 127.0.0.1:7777/api/projects` → корректный JSON-массив
проектов (git/graphify/progress/deadlines). Сервер заглушён после проверки.

## Сохранение публичного API

Интеграция в существующий `cli.py` через `_find`/`_snapshot`/`_conf_path`/`expand`/`sub_common`;
`build_parser` (пара `top_common`/`sub_common`) расширен подкомандами без изменения
сигнатур; `Project.path/.name`, `build_all(cfg, conf_path=)`, `make_server(cfg, port, token, conf_path=)`
использованы дословно. Все тесты плана — дословны.

## Расхождения

Расхождений тест↔реализация в Плане 2 не было. Единственная правка окружения (Task 2):
тесты дословно вызывают `python`, которого на macOS нет (только `python3`) →
создан симлинк `~/.local/bin/python → python3` (каталог на PATH, вне репозитория,
обратимо `rm ~/.local/bin/python`). Код и тесты не менялись.

## Scope

Реализованы spec §7 (actions+safety) и §9 (web). Отложено в План 3: коллекторы
processes/sessions/security, TUI `aos dash`, auto-scaffold-on-discover, патч `new-project.sh`.

## Состояние дерева

Всё закоммичено. Неотслеживаемым остаётся только `graphify-out/`. Ветка `main`
впереди `origin/main` на 11 коммитов (Плана 2 + отчёт Плана 1) — не запушено.
