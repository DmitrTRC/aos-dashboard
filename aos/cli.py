from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aos import __version__
from aos.actions import ActionError, graphify_action, run_action
from aos.aggregator import build_all, build_project
from aos.config import expand, load_config
from aos.model import Health, Project
from aos.registry import ProjectRef, discover
from aos.scaffold import init_project
from aos.tablefmt import colorize, render_table


def _apply_root_override(cfg: dict, root: str | None) -> dict:
    if root:
        cfg = dict(cfg, roots=[root])
    return cfg


def _conf_path() -> Path:
    return expand("~/.config/projects.conf")


def _snapshot(cfg: dict) -> list[Project]:
    return build_all(cfg, conf_path=_conf_path())


def _cmd_status(args, cfg) -> int:
    projects = _snapshot(cfg)
    if args.json:
        print(json.dumps([p.to_dict() for p in projects], ensure_ascii=False, indent=2))
    else:
        rows = []
        for p in projects:
            diff = f"+{p.git.insertions}/-{p.git.deletions}" if p.git.is_repo else "-"
            pct = f"{p.progress.percent}%" if p.progress.percent is not None else "-"
            rows.append([
                colorize(p.name, p.health.value, args.color),
                p.health.value, p.stage, p.git.branch or "-",
                "dirty" if p.git.dirty else "clean", p.graphify.status, pct,
            ])
        print(render_table(
            ["NAME", "HEALTH", "STAGE", "BRANCH", "GIT", "GRAPH", "PROG"], rows, color=args.color))
    if getattr(args, "exit_code", False) and any(p.health == Health.RED for p in projects):
        return 2
    return 0


def _cmd_ls(args, cfg) -> int:
    refs = discover(roots=cfg["roots"], conf_path=_conf_path(), exclude_dirs=cfg["exclude_dirs"])
    if args.json:
        print(json.dumps([r.__dict__ for r in refs], ensure_ascii=False, indent=2))
    else:
        rows = [[r.name, "reg" if r.registered else "new", r.layout or "-", r.path] for r in refs]
        print(render_table(["NAME", "REG", "LAYOUT", "PATH"], rows, color=False))
    return 0


def _find(cfg: dict, name: str) -> Project | None:
    for p in _snapshot(cfg):
        if p.name == name:
            return p
    return None


def _cmd_show(args, cfg) -> int:
    p = _find(cfg, args.project)
    if not p:
        print(f"проект не найден: {args.project}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(p.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"{p.name}  [{p.health.value}]  {p.type}/{p.stage}")
    print(f"  path:     {p.path}")
    print(f"  git:      {p.git.branch or '-'}  "
          f"{'dirty' if p.git.dirty else 'clean'}  +{p.git.insertions}/-{p.git.deletions}")
    print(f"  graphify: {p.graphify.status}  hook={'yes' if p.graphify.hook_installed else 'no'}")
    if p.progress.percent is not None:
        print(f"  progress: {p.progress.percent}% ({p.progress.done}/{p.progress.total})")
    for d in p.deadlines:
        print(f"  deadline: {d.title} {d.due} ({d.days_left} дн)")
    for r in p.health_reasons:
        print(f"  · {r}")
    return 0


def _cmd_scan(args, cfg) -> int:
    if cfg.get("auto_scaffold", False):
        from aos.scaffold import scaffold_missing
        created = scaffold_missing(cfg, conf_path=_conf_path())
        if created:
            print(f"скаффолд .aos/project.yaml: {', '.join(created)}")
    n = len(_snapshot(cfg))
    print(f"обнаружено проектов: {n}")
    return 0


def _cmd_init(args, cfg) -> int:
    if args.all:
        refs = discover(roots=cfg["roots"], conf_path=_conf_path(), exclude_dirs=cfg["exclude_dirs"])
        for r in refs:
            created = init_project(Path(r.path), name=r.name)
            print(f"{'создан' if created else 'есть'}: {r.name}")
        return 0
    if not args.project:
        print("укажите <project> или --all", file=sys.stderr)
        return 1
    ref = next((r for r in discover(roots=cfg["roots"], conf_path=_conf_path(),
                                    exclude_dirs=cfg["exclude_dirs"]) if r.name == args.project), None)
    target = Path(ref.path) if ref else (expand(cfg["roots"][0]) / args.project)
    created = init_project(target, name=args.project)
    print(f"{'создан' if created else 'уже есть'}: {target}/.aos/project.yaml")
    return 0


def _cmd_doctor(args, cfg) -> int:
    import shutil

    ok = True
    for label, tool in cfg["tools"].items():
        found = Path(tool).exists() or shutil.which(tool) is not None
        ok = ok and found
        print(f"  [{'ok' if found else 'MISS'}] {label}: {tool}")
    conf = _conf_path()
    print(f"  [{'ok' if conf.exists() else 'MISS'}] projects.conf: {conf}")
    for root in cfg["roots"]:
        rp = expand(root)
        print(f"  [{'ok' if rp.is_dir() else 'MISS'}] root: {rp}")
    return 0 if ok else 1


def _require(cfg, name):
    p = _find(cfg, name)
    if not p:
        print(f"проект не найден: {name}", file=sys.stderr)
    return p


def _cmd_open(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    try:
        r = run_action("open_session", p, cfg)
    except ActionError as exc:
        print(f"отказано: {exc}", file=sys.stderr)
        return 1
    print(r.message or "открыто")
    return 0


def _cmd_test(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    try:
        r = run_action("run_tests", p, cfg)
    except ActionError as exc:
        print(f"отказано: {exc}", file=sys.stderr)
        return 1
    print(f"tests: {'pass' if r.ok else 'fail'} (exit {r.exit_code}) — {' '.join(r.command)}")
    if not r.ok and r.message:
        print(f"  {r.message}")
    return 0 if r.ok else 1


def _cmd_fetch(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    r = run_action("git_fetch", p, cfg)
    print(f"git fetch: {'ok' if r.ok else 'fail'} (exit {r.exit_code})")
    return 0 if r.ok else 1


def _cmd_graphify(args, cfg) -> int:
    p = _require(cfg, args.project)
    if not p:
        return 1
    if args.init:
        mode, confirm = "init", args.yes
        if not confirm:
            reply = input("graphify init ходит в LLM (сеть + токены). Продолжить? [y/N] ").strip().lower()
            confirm = reply in ("y", "yes", "д", "да")
        if not confirm:
            print("отменено")
            return 1
        try:
            r = graphify_action(p, cfg, mode="init", confirm=True)
        except ActionError as exc:
            print(f"отказано: {exc}", file=sys.stderr)
            return 1
    else:
        mode = "hook_install" if args.hook_install else "update"
        r = run_action(f"graphify_{mode}", p, cfg)
    print(f"graphify {mode}: {'ok' if r.ok else 'fail'} (exit {r.exit_code})")
    return 0 if r.ok else 1


def _cmd_serve(args, cfg) -> int:
    import webbrowser

    from aos.server import load_or_create_token, make_server

    port = args.port or cfg["port"]
    if cfg.get("auto_scaffold", False):
        from aos.scaffold import scaffold_missing
        scaffold_missing(cfg, conf_path=_conf_path())
    token = load_or_create_token(expand("~/.config/aos/token"))
    srv = make_server(cfg, port=port, token=token, conf_path=_conf_path())
    url = f"http://127.0.0.1:{port}/"
    print(f"aos serve → {url}  (Ctrl+C для выхода)")
    if not args.no_browser and cfg.get("open_browser", True):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")
    finally:
        srv.shutdown()
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Two parsers for the shared global flags: the top-level copy carries the
    # real defaults; the per-subcommand copy uses SUPPRESS so a flag given
    # before the subcommand is not clobbered by the subparser (bpo-9351).
    top_common = argparse.ArgumentParser(add_help=False)
    top_common.add_argument("--root", default=None, help="override roots with a single path")
    top_common.add_argument("--json", action="store_true", help="machine-readable output")
    top_common.add_argument("--no-color", dest="color", action="store_false", default=True, help="disable ANSI color")

    sub_common = argparse.ArgumentParser(add_help=False)
    sub_common.add_argument("--root", default=argparse.SUPPRESS, help="override roots with a single path")
    sub_common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="machine-readable output")
    sub_common.add_argument("--no-color", dest="color", action="store_false", default=argparse.SUPPRESS, help="disable ANSI color")

    parser = argparse.ArgumentParser(prog="aos", description="Local project dashboard", parents=[top_common])
    parser.add_argument("--version", action="version", version=__version__)
    parser.set_defaults(func=_cmd_status, exit_code=False)

    sub = parser.add_subparsers(dest="command")

    s = sub.add_parser("status", parents=[sub_common])
    s.add_argument("--exit-code", action="store_true")
    s.set_defaults(func=_cmd_status)

    sub.add_parser("ls", parents=[sub_common]).set_defaults(func=_cmd_ls)
    sub.add_parser("list", parents=[sub_common]).set_defaults(func=_cmd_ls)

    sh = sub.add_parser("show", parents=[sub_common])
    sh.add_argument("project")
    sh.set_defaults(func=_cmd_show)

    sub.add_parser("scan", parents=[sub_common]).set_defaults(func=_cmd_scan)

    it = sub.add_parser("init", parents=[sub_common])
    it.add_argument("project", nargs="?")
    it.add_argument("--all", action="store_true")
    it.set_defaults(func=_cmd_init)

    sub.add_parser("doctor", parents=[sub_common]).set_defaults(func=_cmd_doctor)

    op = sub.add_parser("open", parents=[sub_common])
    op.add_argument("project")
    op.set_defaults(func=_cmd_open)

    te = sub.add_parser("test", parents=[sub_common])
    te.add_argument("project")
    te.set_defaults(func=_cmd_test)

    fe = sub.add_parser("fetch", parents=[sub_common])
    fe.add_argument("project")
    fe.set_defaults(func=_cmd_fetch)

    gf = sub.add_parser("graphify", parents=[sub_common])
    gf.add_argument("project")
    gf.add_argument("--init", action="store_true")
    gf.add_argument("--update", action="store_true")
    gf.add_argument("--hook-install", dest="hook_install", action="store_true")
    gf.add_argument("--yes", action="store_true", help="skip confirmation for --init")
    gf.set_defaults(func=_cmd_graphify)

    sv = sub.add_parser("serve", parents=[sub_common])
    sv.add_argument("--port", type=int, default=None)
    sv.add_argument("--no-browser", action="store_true")
    sv.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = _apply_root_override(load_config(), args.root)
    return args.func(args, cfg)
