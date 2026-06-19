# Отчёт по реализации: AOS v1 Hardening (План 4)

**План:** `docs/superpowers/plans/2026-06-19-aos-v1-hardening.md`
**Базис:** Планы 1–3 в `main`.
**Метод:** subagent-driven-development в main-сессии, строгий TDD, ревью после каждой задачи.
**Статус:** завершено полностью — Task 1…4, 4/4.
**Дата:** 2026-06-19

## Покрытие задач плана

| # | Задача | Артефакт | Тестов | Коммит |
|---|--------|----------|:--:|--------|
| 1 | Не флагать `.env.example`/шаблоны как секрет | `aos/collectors/security.py` | 2 | `39ba355` |
| 2 | Отдавать стену на `/wall` и `/wall/` | `aos/server.py` | 1 | `bcfa93c` |
| 3 | `auto_scaffold` off by default (opt-in) | `aos/config.py` + доки | 2 | `dd87554` |
| 4 | Housekeeping `*.egg-info/` + verify | `.gitignore` | — | `fd58cad` |

## Метрики

- **Коммиты:** 4 (`39ba355..fd58cad`)
- **Изменения:** 10 файлов, +104 / −9
- **Тесты:** 88 passed (Планы 1–4), 0 failed, 2 безобидных warning (`TestState`)

## Закрытые дефекты (найдены на смоуке Плана 3)

1. **False-positive secret на `.env.example`/шаблонах** — добавлен guard `_is_example`
   (`.example/.sample/.template/.dist/.tmpl`). village-emrg перестал быть ложно RED.
2. **`/wall` 404** — рассинхрон док↔код из Плана 2; добавлен роут `/wall` и `/wall/`
   к индексной странице.
3. **Сюрприз авто-скаффолда** — `auto_scaffold` теперь `False` по умолчанию;
   read-команды (`scan`/`serve`) больше не пишут `.aos/` в чужие репозитории без
   явного opt-in. Доки (README, integration-new-project) обновлены.
4. **Гигиена** — `*.egg-info/` в `.gitignore`.

## Смоук (ре-верификация)

- `aos show village-emrg` → **YELLOW** (был RED): причина «в git закоммичен секрет» ушла.
- `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7777/wall` → **200**.

## Расхождение (отмечено, Task 3)

Старый тест Плана 3 `test_config_v3.py` кодировал прежний дефолт `auto_scaffold is True`.
План 4 намеренно меняет дефолт на `False` — минимально обновлён тот assert на `is False`
(новый dedicated-тест `test_config_autoscaffold_default.py` покрывает оба случая).
Публичный API не затронут.

## Прим. (вне кода)

village-emrg's `.env.example` — закоммиченный шаблон по соглашению; `git rm --cached`
не требуется, Task 1 просто прекращает его ложно флагать.
