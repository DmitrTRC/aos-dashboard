# AOS Project Dashboard — design spec

> **Версия:** 1.0 · **Дата:** 2026-06-19 · **Автор сессии:** Claude + Димас
> **Статус:** утверждён, переход к planning
> Локальный control plane поверх workflow `kitty + zellij + nvim + claude + alternative agent`.

---

## 1. Цель и границы

### 1.1 Цель

Локальный дашборд `aos`, который автоматически обнаруживает проекты в рабочей директории,
хранит для каждого `.aos/project.yaml`, показывает состояние (git/diff, прогресс, сроки,
Graphify, тесты, процессы, агентные сессии, security-сигналы) и по клику открывает живую
рабочую сессию проекта через существующую команду `project`. Первичный интерфейс — локальный
web; вспомогательный — лёгкий TUI. Полноценная CLI для работы из терминала — first-class.

### 1.2 В scope (v1)

Обнаружение проектов, чтение состояния (git, graphify, прогресс, дедлайны, тесты, процессы,
сессии, security-lite), health-модель, web `/wall` + детальная страница, TUI-борд, полная CLI,
безопасные действия из whitelist (open session, run tests, git fetch, graphify update/hook-install/init),
авто-скаффолд `.aos/project.yaml`, инициализация Graphify и установка её commit-хука.

### 1.3 Вне scope (v1, NON-goals)

NAS/QNAP, домашняя сеть, погода, новости, медиа/IoT, общесистемная безопасность дома;
SQLite и event-timeline; ingest-API и Claude statusline/lifecycle-хуки; web-терминал;
редактирование `.aos/project.yaml` из браузера и add-project wizard (правим в nvim / `aos init`);
автоматический git commit/push/pull/reset/checkout/rebase; убийство процессов; отправка
промптов агентам; любые изменения в файлах проекта вне каталога `.aos/`.

### 1.4 Жёсткие принципы

Terminal workflow = место работы; дашборд = обзор, сигналы и переходы. `project` остаётся
главным входом в работу и не заменяется. Дашборд — единственный слой, выполняющий команды,
и делает это только через структурный whitelist. Всё локально (`127.0.0.1`), офлайн; сеть —
только в явных действиях `git fetch` и `graphify --init`.

---

## 2. Контекст и интеграции

### 2.1 `project` (zsh-функция)

`project` — функция в `~/.config/zsh/project.zsh` (не бинарь на PATH). Запуск из Python — через
логин-shell: `zsh -ic 'project <name>'`. `project` поднимает `zellij attach`/create **в текущем
терминале и требует TTY** — окно сам не создаёт. Поэтому из web дашборд **сам открывает окно kitty**,
внутри которого запускается `project <name>`.

### 2.2 Реестр `~/.config/projects.conf`

Формат: `имя | путь | layout` (pipe-separated, строки `#…` и пустые игнорируются). Это канонический
реестр, который использует `project`. **Имя в реестре ≠ имя директории** (`pvil → project village`,
папка `village-emrg`; `pjit → project junior-it`, папка `Junior_IT`). Ключ связи — **путь**; третье
поле — zellij-layout (`dev`/`research`/`teaching`/`scratch`). Идентичность для запуска — имя из реестра.

### 2.3 zellij

Живость сессии детектируется как:
`zellij list-sessions -n | grep -v EXITED | awk '{print $1}'` → набор имён живых сессий.
Проект считается «session active», если его имя из реестра в этом наборе. EXITED-зомби игнорируются.

### 2.4 Graphify

CLI (подтверждено установленными хуками и `GRAPH_REPORT.md`):

| Команда | Назначение | Сеть/затраты |
|---|---|---|
| `graphify .` | Полная инициализация графа | **LLM-экстракция → сеть + токены** |
| `graphify update .` | Ребилд по коду после изменений | нет (code-only) |
| `graphify hook install` | Ставит `post-commit` + `post-checkout` авто-ребилд | нет |

Артефакты в `graphify-out/`: `manifest.json` (file → mtime/ast_hash/semantic_hash), `cost.json`
(прогоны токенов), `graph.html`, `graph.json`, `GRAPH_REPORT.md` (содержит `Built from commit: <hash>`),
служебные `.graphify_root`, `.graphify_python`. Хуки помечены маркерами `# graphify-hook-start` /
`# graphify-checkout-hook-start`.

### 2.5 superpowers-планы

Прогресс выводится из чеклистов `docs/superpowers/plans/*.md` (`- [ ]` / `- [x]`). Спеки —
`docs/superpowers/specs/`. Это существующие артефакты; новый `.aos/tasks.md` не вводим (опциональный фолбэк).

---

## 3. Архитектура

`aos` — Python-пакет, единственная внешняя зависимость **PyYAML**. Frontend — vanilla JS, инлайн CSS,
без CDN (офлайн). CLI и web используют одну core-библиотеку; CLI работает standalone (читает ФС напрямую,
сервер не требуется). `aos serve` дополнительно поднимает web + фоновый цикл обновления.

### 3.1 Модули (каждый — изолированный, тестируемый)

```
aos/
  __main__.py        точка входа `python -m aos`
  cli.py             argparse subparsers; рендер таблиц/JSON; exit-коды
  config.py          ~/.config/aos/config.yaml + дефолты
  registry.py        discovery: parse projects.conf + скан roots; reconcile name/path/layout
  model.py           dataclasses + сериализация в JSON
  health.py          сведение сигналов → green/yellow/red/unknown + причины
  aggregator.py      параллельный опрос коллекторов (ThreadPoolExecutor), кэш с TTL, фоновый refresh
  actions.py         ЕДИНСТВЕННЫЙ исполнитель; whitelist видов + exec-allowlist
  server.py          stdlib ThreadingHTTPServer, bind 127.0.0.1, API + статика
  tui.py             `aos dash`/`wall`: ANSI-таблица, --watch
  collectors/
    git.py  progress.py  deadlines.py  graphify.py
    tests.py  processes.py  sessions.py  security.py
  web/
    index.html       одна самодостаточная страница (/wall + детальная)
```

### 3.2 Поток данных

```
discovery (registry) ──► для каждого проекта: collectors параллельно (с таймаутами)
   └─► aggregator собирает snapshot ──► health ──► кэш (TTL)
          ├─► CLI рендерит (table | --json)
          ├─► server отдаёт /api/projects(/{name})
          └─► web/TUI рисуют
actions (open/test/fetch/graphify) ──► subprocess (shell=False) ──► пишут .aos/state/ ──► refresh
```

Ни один коллектор не роняет агрегатор: при таймауте/ошибке возвращает частичный результат со
статусом поля `unknown`. Снапшот всегда собирается.

---

## 4. Модель данных

### 4.1 `.aos/project.yaml` (коммитим; авто-скаффолд стаба при первом обнаружении)

```yaml
name: village            # имя из реестра (= `project <name>`), НЕ обязательно имя папки
title: "Village EMRG"    # человекочитаемое
type: app                # app|monorepo|research|content|education|devops|unknown (авто-детект, override тут)
stage: build             # idea|research|build|test|ship|maintenance|paused
priority: high           # low|medium|high
tags: []
deadlines:
  - { title: "MVP deploy", due: 2026-07-01 }
progress:
  mode: auto             # auto (по docs/superpowers/plans/*) | manual
  percent: null          # учитывается только при manual
  plan: null             # явный путь к плану; иначе берётся свежий
graphify:
  required: false        # true → отсутствие graphify-out даёт red; иначе missing = optional (как research)
  disabled: false        # true → коллектор не считает graphify (статус disabled)
commands:                # валидируются по exec-allowlist; запуск shell=False (test/lint/build)
  test: pnpm test
session:
  launch: null           # override команды запуска; по умолчанию `project <name>`
dashboard:
  show_on_wall: true
```

Сознательно убрано: `root` (выводится из расположения файла — переносимость), отдельный `id`
(имя = ключ реестра — нет рассинхрона с `project <name>`).

### 4.2 Состояние и кэш (gitignored)

```
.aos/
  project.yaml         коммитим
  state/               в .gitignore
    tests.json         результат последнего прогона тестов (exit code, длительность, время, лог-путь)
    actions.log        журнал выполненных действий
    snapshot.json      последний снапшот (кэш, опционально)
```

При `aos init` в `.gitignore` проекта добавляется строка `.aos/state/`.

### 4.3 Дискавери и reconcile

1. Парсим `projects.conf` → записи `(name, path, layout)`; `eval`-разворот `$HOME`/`~` без env-зависимости.
2. Скан `roots` (деф. `~/Projects`) на директории-проекты (git-репо ИЛИ есть `.aos/project.yaml`
   ИЛИ в реестре), с исключениями (`node_modules`, dotdirs, и т.п.).
3. Reconcile по **абсолютному пути**: запись реестра ⨝ директория. Проекты вне реестра → флаг
   `unregistered` (подсказка: зарегистрировать через `project --edit`). Имя для запуска берётся
   из реестра; если проект не в реестре — фолбэк на имя директории.

---

## 5. Коллекторы (read-only, у каждого таймаут)

| Коллектор | Читает | Сигналы |
|---|---|---|
| `git` | `/usr/bin/git -C <p> --no-optional-locks`: branch, ahead/behind vs upstream, `status --porcelain` (staged/unstaged/untracked), `diff --stat`, last commit, recent commits | dirty/clean, ahead/behind, diff +/− |
| `progress` | `docs/superpowers/plans/*.md` чеклисты (свежий план или `progress.plan`); либо `progress.percent` при `manual` | % выполнения, открытые пункты |
| `deadlines` | `.aos/project.yaml: deadlines[]` | дней до / просрочено |
| `graphify` | `graphify-out/`: наличие, `GRAPH_REPORT.md` (`Built from commit`), mtime манифеста vs исходников, маркер хука в `.git/hooks/post-commit` | fresh/stale/missing/disabled/error; hook installed да/нет; built_commit vs HEAD |
| `tests` | `.aos/state/tests.json`; тест-команда из yaml→CLAUDE.md `### Команды`→`package.json` | last pass/fail/unknown, длительность |
| `processes` | `ps` (read-only) по cmdline/cwd, привязанным к пути проекта; `lsof -nP -iTCP -sTCP:LISTEN` (best-effort) | dev-сервер/воркеры, порты, pid |
| `sessions` | `zellij list-sessions -n \| grep -v EXITED`; процессы `claude`/`opencode` с cwd проекта; наличие `.claude/` | session active/idle, какой агент |
| `security` | shallow-скан: `.env`, `env.bak`, `*.pem`, `*.key`, secret-like; наличие `SECURITY.md`; tracked `node_modules` | список потенциально чувствительных файлов |

Все subprocess-вызовы — абсолютными путями к утилитам (как в `project.zsh`), список аргументов,
`shell=False`, таймаут, `cwd` = путь проекта.

---

## 6. Health-модель

Состояние проекта: `green` / `yellow` / `red` / `unknown`, с перечнем причин.

- **red:** тесты упали; дедлайн просрочен; Graphify `missing` там, где `graphify.required: true`;
  упавший проектный процесс; рискованное git-состояние; критичный security-сигнал.
- **yellow:** незакоммиченный diff; Graphify `stale`; тесты давно не гонялись; дедлайн ближе
  `health.deadline_warn_days`; нет активности дольше `health.inactive_warn_days`.
- **green:** нет критичных проблем; git чистый/ожидаемый; тесты pass или осознанно unknown;
  Graphify fresh/disabled; дедлайн не горит.
- **unknown:** не git-репо; нет `.aos/project.yaml`; не удалось прочитать состояние/выполнить коллектор.

Проект «active», если есть живая zellij-сессия / свежая git-активность / активный процесс /
открыт из дашборда; иначе «inactive».

---

## 7. Действия и безопасность

### 7.1 Виды действий (закрытый список — других в коде нет)

`open_session` · `run_tests` · `git_fetch` · `graphify_update` · `graphify_hook_install` ·
`graphify_init` · `open_report` (открыть файл через `open`). Опасные git-операции
(commit/push/pull/reset/checkout/rebase/delete-branch) **отсутствуют как виды** — невозможны структурно.

### 7.2 Безопасность исполнения

- Сервер bind только `127.0.0.1`; POST-действия требуют per-run токен (`~/.config/aos/token`, mode 600)
  и проверку заголовков `Origin`/`Host` (анти-DNS-rebinding). Read-эндпоинты открыты на localhost.
- Команды из `project.yaml` валидируются по **глобальному exec-allowlist**: `shlex`-парсинг, `argv[0]`
  обязан быть в списке (`git, pnpm, npm, yarn, pytest, python, node, make, just, bats, graphify, cargo, go`),
  `shell=False`, аргументы списком, таймаут (тесты 120 c, graphify 300 c), `cwd` = путь проекта,
  очищенный env. Shell-метасимволы → отказ.
- В проект пишем только в `.aos/`; `.aos/state/` gitignored. CLAUDE.md/package.json/код не трогаем.
- Сеть только в `git_fetch` и `graphify_init`. Никаких NAS/домашней сети/погоды/новостей. Фронт офлайн.

### 7.3 Открытие сессии

По умолчанию дашборд открывает новое окно kitty, в нём запускается `project <name>`:

```
/Applications/kitty.app/Contents/MacOS/kitty -1 -e /bin/zsh -ic 'project <name>'
```

detached через `Popen(start_new_session=True)`. Команда задаётся одной строкой в конфиге
(`session.launch_cmd_template`); альтернативы — `kitty @ launch` (нужен `allow_remote_control`),
helper `kw`, либо fallback «скопировать команду в буфер».

### 7.4 Graphify-действия

- `graphify_hook_install` → `graphify hook install` (бесплатно, code-only). Делегируем graphify;
  сами в `.git/hooks/` не пишем.
- `graphify_update` → `graphify update .` (бесплатно).
- `graphify_init` → `graphify .` — **LLM-экстракция: сеть + расход токенов**. Только явное действие,
  с подтверждением в UI/CLI и пометкой стоимости; **никогда не выполняется автоматически и не входит
  в фоновый refresh**.

---

## 8. CLI (terminal-first, stdlib `argparse`)

```
aos                                  краткий status-борд (alias на status)
aos status [<proj>] [--exit-code]    health-таблица / детально; --exit-code≠0 если есть red
aos ls | list                        список проектов (реестр + unregistered)
aos show <proj>                      полный снапшот проекта
aos open <proj>                      открыть рабочую сессию (kitty → project <name>)
aos serve [--port N] [--no-browser]  web + фоновый цикл
aos wall | dash [--watch]            живой TUI-борд
aos scan                             принудительное переобнаружение/refresh
aos init [<proj>|--all]              скаффолд .aos/project.yaml + .aos/state/ + .gitignore
aos graphify <proj> [--init|--update|--hook-install]   --update по умолчанию
aos test <proj>                      прогнать whitelisted test-команду, сохранить результат
aos fetch <proj>                     git fetch (единственное сетевое git-действие)
aos doctor                           проверка окружения (пути, конфиг, порт, права токена)
aos config [--edit|--path]
aos version | --version
глобально: --json  --root <path>  --no-color  -q/-v
```

`--json` у всех read-команд (под `jq`/statusline). Exit-коды осмысленные (`status --exit-code` ≠ 0
при наличии red). CLI не зависит от запущенного сервера. `aos graphify --init` запрашивает
подтверждение (сеть + токены).

---

## 9. Web

Stdlib `ThreadingHTTPServer`, bind `127.0.0.1`. Эндпоинты:

```
GET  /                              одна самодостаточная HTML-страница (инлайн CSS+JS, без CDN)
GET  /api/projects                  список снапшотов
GET  /api/projects/{name}           детальный снапшот
POST /api/projects/{name}/actions/{kind}   токен + Origin/Host; kind из закрытого списка
GET  /api/events                    (опц.) SSE для live-обновления; иначе клиентский polling
```

`/wall`: header со сводкой (green/yellow/red), карточки проектов (имя, health-точка, тип/stage,
branch+diff, graphify, progress/tests, session, дедлайн, действия Open/Details/Test/Rebuild graph),
панель «Сегодня в фокусе» (tests failing / graph stale / uncommitted / active session / due soon).
Детальная страница — вкладки Overview / Diff / Graphify / Tests / Processes / Sessions / Security / Git.

---

## 10. TUI

`aos dash` / `aos wall`: ANSI-таблица проектов (health, branch, diff, progress, deadline, session),
`--watch N` для авто-refresh. Та же core-библиотека, без внешних зависимостей.

---

## 11. Конфиг `~/.config/aos/config.yaml`

```yaml
roots: ["~/Projects"]
port: 7777
refresh_interval_sec: 10
open_browser: true
tools:                       # абсолютные пути (как в project.zsh)
  git: /usr/bin/git
  zellij: /opt/homebrew/bin/zellij
  kitty: /Applications/kitty.app/Contents/MacOS/kitty
  graphify: graphify         # через PATH; путь-override допустим
session:
  launch_cmd_template: '{kitty} -1 -e /bin/zsh -ic ''project {name}'''
exec_allowlist: [git, pnpm, npm, yarn, pytest, python, node, make, just, bats, graphify, cargo, go]
exclude_dirs: [node_modules, .git, dist, build, target, .venv, venv, __pycache__]
timeouts_sec: { collector: 5, tests: 120, graphify: 300 }
health:
  deadline_warn_days: 7      # дедлайн ближе этого → yellow
  inactive_warn_days: 14     # нет активности дольше → yellow
```

---

## 12. Тестирование

`pytest` + `tmp_path`. Фикстуры: временные git-репозитории (через subprocess), фейковые планы с
чеклистами, фейковый `graphify-out/manifest.json` + `GRAPH_REPORT.md`, фейковый `projects.conf`,
фейковые `.git/hooks/post-commit` с маркером.

Покрываем: reconcile имя-реестра vs имя-папки; коллекторы при таймауте → partial и не роняют агрегатор;
переходы health; свежесть graphify по `Built from commit` vs HEAD и по mtime; детект установленного хука;
`actions` отклоняет не-allowlist `argv[0]` и shell-метасимволы и никогда не использует `shell=True`;
`graphify_init` требует явного флага/подтверждения; server-эндпоинты через `http.client`; проверка
токена и Origin/Host; скан не выходит за `roots`. Финальный шаг плана — прогон всех тестов и `aos doctor`.

---

## 13. Структура репозитория

```
aos-dashboard/                 (создан через new-project.sh → git init + регистрация в реестре)
  aos/                         (см. §3.1)
  tests/
  configs/ config.example.yaml  project.example.yaml
  docs/superpowers/specs/      (этот документ)
  pyproject.toml  README.md
```

---

## 14. Майлстоуны (CLI-first)

1. **Ядро + CLI:** `config` + `registry` (parse `projects.conf` + скан `~/Projects`) + `model` +
   `aos status`/`ls`/`show` (table + `--json`) + `aos doctor`.
2. **Коллекторы:** git + graphify (incl. freshness/hook-sensor) + progress + deadlines + health → снапшот.
3. **Действия + безопасность:** `open_session` (kitty-лаунчер), `run_tests`, `git_fetch`,
   `graphify_update`/`hook_install`/`init` + harness безопасности + тесты.
4. **Web:** `serve` + `/wall` + детальная страница (read) + действия из UI.
5. **Сенсоры + TUI:** processes + sessions + security + `aos dash`.
6. **Polish:** авто-скаффолд yaml + `aos init` + README + (опц.) патч `new-project.sh` для дропа
   `.aos/project.yaml` в новых проектах.

---

## 15. Definition of Done (v1)

1. `aos status`/`ls`/`show` и `aos serve` работают локально; `/wall` показывает `Junior_IT`, `research`,
   `village-emrg`.
2. Для каждого проекта видны health, stage, branch, diff, Graphify-статус, progress, last activity,
   session-статус.
3. Клик/`aos open` запускает существующую `project <name>` (новое окно kitty).
4. Graphify-статус корректно различает fresh/stale/missing/disabled/error; для `research` показывается
   `missing` с действием инициализации.
5. `aos graphify --hook-install` ставит commit-хук; `--update` ребилдит бесплатно; `--init` спрашивает
   подтверждение (сеть+токены).
6. Прогресс считается из `docs/superpowers/plans/*`; дедлайны — из `project.yaml`.
7. Дашборд не выполняет опасных команд; все действия проходят exec-allowlist и `shell=False`;
   bind `127.0.0.1`; в проект пишется только `.aos/`.
8. `aos doctor` зелёный; все тесты проходят.

---

## 16. Принятые решения

1. Стек: Python + единственная зависимость PyYAML; фронт vanilla-JS, офлайн, без CDN.
2. Форм-фактор: web-первичный + лёгкий TUI; CLI — first-class.
3. Открытие сессии: новое окно kitty → `project <name>` (по умолчанию; настраивается в конфиге).
4. `project` и terminal workflow не меняем; `project` остаётся главным входом.
5. Идентичность проекта = имя из `projects.conf`; ключ связи с папкой = путь; layout — 3-е поле.
6. Хранилище — только файлы; без SQLite и event-timeline. `.aos/state/` gitignored.
7. Graphify: `init` (LLM/сеть) только явно; `update`/`hook install` бесплатны и безопасны;
   свежесть по `Built from commit` vs HEAD.
8. Безопасность: closed-list видов действий + exec-allowlist + `shell=False` + per-run токен +
   localhost-only; сеть только в `git_fetch`/`graphify_init`.
9. Местоположение: `~/Projects/aos-dashboard`, бутстрап через `new-project.sh`.
