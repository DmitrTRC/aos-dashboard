# Отчёт по реализации: AOS Core + CLI (read-only)

**План:** `docs/superpowers/plans/2026-06-19-aos-core-cli.md`
**Спека:** `docs/superpowers/specs/2026-06-19-project-dashboard-design.md`
**Метод:** subagent-driven-development в main-сессии, строгий TDD (red → green → commit), ревью после каждой задачи.
**Статус:** завершено полностью — Task 0…14, 15/15.
**Дата:** 2026-06-19

## Покрытие задач плана

| # | Задача | Артефакт | Тестов | Коммит |
|---|--------|----------|:--:|--------|
| 0 | Скелет пакета + pytest | `pyproject.toml`, `aos/__init__`, `__main__`, `tests/conftest` | — | `e245cc2` |
| 1 | Загрузка конфига (deep-merge) | `aos/config.py` | 2 | `dd8dcde` |
| 2 | Модель данных | `aos/model.py` | 2 | `b31408b` |
| 3 | Registry + discovery | `aos/registry.py` | 2 | `e986a44` |
| 4 | Git-коллектор | `aos/collectors/git.py` | 3 | `96b9cf7` |
| 5 | Progress-коллектор | `aos/collectors/progress.py` | 3 | `2bf7dc5` |
| 6 | Deadlines | `aos/collectors/deadlines.py` | 1 | `f50569a` |
| 7 | Graphify freshness + hook | `aos/collectors/graphify.py` | 4 | `0097b10` |
| 8 | Tests-state | `aos/collectors/tests.py` | 2 | `612ce95` |
| 9 | Health-эвалуатор | `aos/health.py` | 5 | `f374e3c` |
| 10 | Агрегатор (concurrent) | `aos/aggregator.py` | 2 | `4f9ff28` |
| 11 | Scaffold `aos init` | `aos/scaffold.py` | 2 | `e1e379f` |
| 12 | Табличный рендер | `aos/tablefmt.py` | 1 | `bd5c18d` |
| 13 | CLI (status/ls/show/scan/init/doctor) | `aos/cli.py` | 3 | `b306c88` |
| 14 | Примеры конфигов + README | `configs/*.yaml`, `README.md` | — | `c35ddd3` |

## Метрики

- **Коммиты:** 15 (диапазон `e245cc2..c35ddd3`, базовая точка `59667b8`)
- **Изменения:** 35 файлов, +1219 / −3
- **Тесты:** 32 passed, 0 failed; 2 безобидных warning (pytest принимает датакласс `TestState` за тест-класс — имя согласовано планом, на работу не влияет)
- **Зависимости:** только PyYAML (рантайм) + pytest (dev), остальное — stdlib (спека §3)

## Смоук на реальном workspace

`aos --root ~/Projects status` → exit 0, 5 проектов (aos-dashboard, brainme, junior-it,
research, village-emrg) с колонками health/stage/branch/git/graph/prog. `ls` и `doctor`
отработали, `doctor` — все инструменты `ok`.

## Отклонения от плана (1)

**Task 13, согласовано с заказчиком.** Тест-код и реализация из плана были взаимно
несовместимы: `argparse` не принимает глобальные флаги после подкоманды
(`aos status --json --root …`). Починен `build_parser()` — два common-парсера
(корневой с дефолтами, сабпарсеры с `argparse.SUPPRESS`, обход CPython bpo-9351).
Публичные имена/сигнатуры/флаги (`main`, `_cmd_*`, `--root/--json/--no-color/--exit-code`)
не менялись; тесты плана остались дословными. Обе позиции флагов работают.

## Зафиксированный scope

Реализованы Milestones 1–2 (read-only). Намеренно отложено в следующие планы:
- **Plan 2:** actions + safety + `serve` + web `/wall`
- **Plan 3:** сенсоры processes/sessions/security + TUI + polish

## Состояние дерева

Всё закоммичено. Неотслеживаемым остаётся только `graphify-out/`. Ветка `main`,
не запушено.
