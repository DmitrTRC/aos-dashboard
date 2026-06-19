# Отчёт по реализации: AOS Sensors + TUI + Auto-scaffold (План 3, финальный)

**План:** `docs/superpowers/plans/2026-06-19-aos-sensors-tui.md`
**Спека:** `docs/superpowers/specs/2026-06-19-project-dashboard-design.md` (§5, §6, §10, §4.1)
**Базис:** Планы 1–2 в `main`.
**Метод:** subagent-driven-development в main-сессии, строгий TDD, ревью после каждой задачи.
**Статус:** завершено полностью — Task 1…12, 12/12.
**Дата:** 2026-06-19

## Покрытие задач плана

| # | Задача | Артефакт | Тестов | Коммит |
|---|--------|----------|:--:|--------|
| 1 | Model: Process/Session/Security + active | `aos/model.py` | 2 | `f27bc73` |
| 2 | Config: ps, python3, auto_scaffold | `aos/config.py` | 1 | `ec24b3e` |
| 3 | Sessions collector (zellij + agents) | `aos/collectors/sessions.py` | 4 | `20c39d5` |
| 4 | Processes collector (project-bound) | `aos/collectors/processes.py` | 2 | `b80732c` |
| 5 | Security-lite secret scan | `aos/collectors/security.py` | 2 | `e0e2f37` |
| 6 | Health: red на tracked-secret | `aos/health.py` | 2 | `a5d4007` |
| 7 | Aggregator: sensors + active + live once | `aos/aggregator.py` | 1 | `f408c6c` |
| 8 | Auto-scaffold on scan/serve | `aos/scaffold.py`, `aos/cli.py` | 1 | `b47e88b` |
| 9 | TUI board `render_dash` + watch | `aos/tui.py` | 1 | `f84aa34` |
| 10 | CLI dash/wall (+ --watch) | `aos/cli.py` | 2 | `e2bf054` |
| 11 | Web: session/agents + secret warning | `aos/web/index.html` | 1 | `ca09bb8` |
| 12 | new-project.sh doc + README + verify | `docs/integration-new-project.md`, `README.md` | — | `775a2f8` |

## Метрики

- **Коммиты:** 12 (`f27bc73..775a2f8`)
- **Изменения:** 24 файла, +573 / −9
- **Тесты на момент завершения Плана 3:** 83 passed, 2 безобидных warning (`TestState`)
- **Зависимости:** новых нет — stdlib + PyYAML

## Backward-compatible расширения (как требовалось)

- `Project` получил поля `processes/session/security/active` с дефолтами; `to_dict`
  добавляет `security.has_tracked_secret`. Старые вызовы и сериализация не сломаны.
- `build_project(ref, cfg, live=None)` — двухаргументные вызовы Планов 1–2 работают
  (при `live=None` live-набор считается внутри); `build_all` вычисляет live-сессии
  один раз и пробрасывает в каждый `build_project`.
- Все старые тесты (model/aggregator/health/scaffold/cli/web) остались зелёными.

## Смоук

`aos dash` — доска с колонкой `SES`; `aos scan` — discovery (+ авто-скаффолд при
`auto_scaffold`); `aos show` / web `/wall` — session/processes/security. На реальном
workspace всплыли два дефекта (см. План 4): false-positive secret на `.env.example`
и `/wall` 404.

## Scope

Реализованы spec §5 (processes/sessions/security), §6 (security red + active),
§10 (TUI), §4.1 (auto-scaffold). Definition of Done v1 закрыт Планами 1–3
(дефекты добиты Планом 4).
