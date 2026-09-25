"""adapters 的命令列——`vacant do|hook|install|uninstall|adapters`。

這支在架構裡承重什麼：把 `agents.py` 的四份翻譯表與 `run.py` 的行程層接成使用者打得到的指令。

    vacant do pi "寫一份比較報告"            # 隔離工作區裡跑 pi -p，結束後交進收件口
    vacant do claude --prompt-file task.md
    vacant do --cmd 'mytool --task {prompt}' --prompt "…"   # 任何 CLI
    vacant install                           # 找得到的 agent 各裝一份掛鉤（可逆；技能要 --skill）
    vacant uninstall                         # 只移除我們那幾條，使用者自己的改動保留
    vacant adapters                          # 哪些 agent 在、裝了什麼、現在還在不在

⚠ `vacant install` 在 2026-09-24 之前是 `possess`（把模型通道接到常駐 proxy）。
那條路仍然在：`vacant possess install`，或 `vacant install --observe-model`（兩者都裝）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from ..intake import contract as C
from ..intake import flow
from . import agents as A
from . import install as INS
from .hookpolicy import feedback_text

EXIT = {"accept": 0, "reject": 40, "hold": 41, "escalate": 42, "void": 43}


def _home() -> pathlib.Path:
    return pathlib.Path.home()


def cmd_do(args) -> int:
    cpath = pathlib.Path(args.contract) if args.contract else C.find(pathlib.Path.cwd())
    if cpath is None:
        print("vacant do: no task contract found (create one with `vacant contract quick "
              "--deliverable FILE --lock`, or `vacant contract init`)",
              file=sys.stderr)
        return 2
    task = flow.open_task(cpath)
    if args.prompt_file:
        prompt = pathlib.Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        prompt = args.prompt or ""
    if not prompt:
        print("vacant do: give the task with --prompt or --prompt-file", file=sys.stderr)
        return 2
    if args.cmd:
        import shlex
        build = A.generic_build(shlex.split(args.cmd))
        agent = "generic"
    else:
        if args.agent == "auto":
            # 非文字的機會通道（DECISION_20260924_ACCOUNTABLE_TRACE §4.7）：依這類任務的紀錄挑；
            # 次數不夠就輪流探索，不拿小樣本做決定
            from ..trace import actors as TA
            have = [n for n, b in A.detect().items() if b]
            if not have:
                print("vacant do: --agent auto found none of the four agents on PATH",
                      file=sys.stderr)
                return 2
            pick = TA.pick_agent(TA.ActorBook(), TA.family_of(task.contract), have)
            print(f"[vacant do] auto → {pick['agent']} ({pick['why']})", file=sys.stderr)
            args.agent = pick["agent"]
        if args.agent not in A.AGENTS:
            print(f"vacant do: unknown agent {args.agent!r} (known: {', '.join(A.AGENTS)}; "
                  f"or use --cmd)", file=sys.stderr)
            return 2
        spec = A.AGENTS[args.agent]
        agent = spec.name

        def build(p, ws, _spec=spec):
            return _spec.build(p, ws, hooks=not args.no_hooks, extra=args.extra)
    res = __import__("vacant_network.adapters.run", fromlist=["do"]).do(
        task, agent=agent, build=build, prompt=prompt, in_place=args.in_place,
        timeout_s=args.timeout, attempts=args.attempts, sandbox=args.sandbox,
        feedback=lambda r: feedback_text(r, task.contract), feedback_mode=args.feedback_mode)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    else:
        oc = res.get("outcome") or ("void" if res.get("void") else "?")
        print(f"[vacant do] {agent}: {oc.upper()} after {len(res.get('attempts', []))} "
              f"attempt(s); workspace {res.get('workspace')}")
        for a in res.get("attempts", []):
            esc = a.get("workspace_escape")
            print(f"  a{a['attempt']}: agent rc={a.get('rc')} timed_out={a.get('timed_out')} "
                  f"→ {a.get('outcome')}" + ("  ⚠ wrote outside the workspace" if esc else ""))
        for r in res.get("results", []):
            if r["status"] != "PASS":
                print(f"  {r['claim_id']}: {r['status']} — {r['detail'][:200]}")
        tr = res.get("trace") or {}
        if tr.get("summary"):
            print("  " + str(tr["summary"]).replace("\n", "\n  "))
        elif tr.get("report") and oc != "accept":
            print(f"  open issues: {tr['report']}")
        if oc == "accept":
            print("  next: `vacant release` (nothing has been published yet)")
    if res.get("void"):
        return EXIT["void"]
    return EXIT.get(str(res.get("outcome")), 2)


def cmd_install(args) -> int:
    names = args.agents.split(",") if args.agents else list(A.AGENTS)
    m = INS.Manifest()
    home = _home()
    found = A.detect()
    rc = 0
    for n in names:
        if n not in A.AGENTS:
            print(f"  {n}: unknown agent", file=sys.stderr)
            rc = 2
            continue
        if not found.get(n) and not args.force:
            print(f"  {n}: not installed on this machine — skipped (use --force to write its "
                  f"config anyway)")
            continue
        try:
            ops = A.AGENTS[n].install(m, home, skill=bool(getattr(args, "skill", False)))
        except (OSError, ValueError) as e:
            print(f"  {n}: FAILED — {e}", file=sys.stderr)
            rc = 1
            continue
        print(f"  {n}: {A.AGENTS[n].hook_install_note} — {', '.join(op['path'] for op in ops)}")
    # 零設定（產品原則）：裝了就有作用；人自己改過 mode 就不動它
    m.data.setdefault("mode", "evidence")
    m.data["schema"] = 2
    m.save()
    if args.observe_model:
        from ..vrun import possess
        print("  + observe-model: running `vacant possess install` (model-traffic proxy)")
        rc = rc or possess.main(["install"])
    print(f"[vacant install] done. Open your agent as usual; each task is checked against its own "
          f"recorded steps before it is handed back. Data: {INS.state_root().parent} "
          f"(remove everything with `vacant uninstall`).")
    hint = _path_hint()
    if hint:
        print(hint)
    return rc


def _path_hint() -> str | None:
    """`vacant` 這支指令所在的目錄不在 PATH 上（pip --user、pipx 還沒 ensurepath）⇒ 印出補救那一行。"""
    import os
    import shutil
    here = pathlib.Path(sys.argv[0]).resolve().parent if sys.argv and sys.argv[0] else None
    if here is None or not (here / "vacant").exists() or shutil.which("vacant"):
        return None
    if str(here) in os.environ.get("PATH", "").split(os.pathsep):
        return None
    return (f"[vacant] note: {here} is not on your PATH, so the `vacant` command may not be found "
            f"in a new terminal. Add it with: export PATH=\"{here}:$PATH\"")


def cmd_uninstall(args) -> int:
    m = INS.Manifest()
    names = args.agents.split(",") if args.agents else list(m.data["agents"])
    errors = 0
    for n in names:
        for r in INS.uninstall(m, n):
            errors += r["result"].startswith("error:")
            print(f"  {n}: {r['op']:<10} {r['path']}: {r['result']}")
    m.save()
    rc = 0
    # 0.8.0 的 `vacant install`（以及 `--observe-model`）裝的是模型通道常駐代理；
    # 那個安裝有自己的狀態檔。整體解除安裝時一起拆——否則舊使用者照 0.8.0 的文件打
    # `vacant uninstall`，什麼都沒發生、退出碼 0，代理端點還寫在五個 agent 的設定裡。
    from ..vrun import possess
    if (possess.state_home(pathlib.Path.home()) / "state.json").is_file():
        if args.agents:
            print("[vacant] the model-channel install (`vacant possess`) is still present; "
                  "remove it with `vacant possess uninstall`", file=sys.stderr)
        else:
            print("  + model-channel install found: running `vacant possess uninstall`")
            rc = possess.main(["uninstall"])
    if errors:
        print(f"[vacant] {errors} step(s) could not be undone; they are still recorded — fix "
              f"the file and run `vacant uninstall` again", file=sys.stderr)
        return 1
    return rc


def status() -> dict[str, dict]:
    m = INS.Manifest()
    out = {}
    found = A.detect()
    for n in A.AGENTS:
        ops = m.ops(n)
        checks = []
        for op in ops:
            p = pathlib.Path(op["path"])
            if op["op"] == "file":
                if not p.exists():
                    state = "missing"
                else:
                    import hashlib
                    state = ("present" if hashlib.sha256(p.read_bytes()).hexdigest() == op["sha256"]
                             else "modified")
            elif op["op"] == "json_hooks":
                try:
                    txt = p.read_text(encoding="utf-8") if p.exists() else ""
                    state = "present" if INS.MARKER in txt else "missing"
                except OSError:
                    state = "unreadable"
            else:
                state = ("present" if p.exists() and INS.BLOCK_END in p.read_text(encoding="utf-8")
                         else "missing")
            checks.append({"op": op["op"], "path": str(p), "state": state})
        out[n] = {"binary": found.get(n), "installed": bool(ops), "config": checks}
    return out


def cmd_adapters(args) -> int:
    st = status()
    if args.json:
        print(json.dumps(st, indent=2))
        return 0
    for n, s in st.items():
        states = [c["state"] for c in s["config"]]
        summary = ("not installed" if not s["installed"] else
                   "configured" if all(x == "present" for x in states) else
                   "DRIFTED: " + ", ".join(f"{c['path']} {c['state']}" for c in s["config"]
                                           if c["state"] != "present"))
        print(f"  {n:<9} binary={s['binary'] or '-':<40} {summary}")
    print("  ('configured' means the files are in place; whether a hook fires is only known "
          "from its events in ~/.vacant/intake/hooks/events.jsonl)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vacant")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("do", help="run an agent headless in an isolated workspace, then submit "
                                 "its work to the intake")
    p.add_argument("agent", nargs="?", default="",
                   help=f"one of {', '.join(A.AGENTS)}, or `auto` (pick by this task family's "
                        f"record; explores until each has enough runs)")
    p.add_argument("--cmd", help="any CLI instead: a template with {prompt} / {workspace}")
    p.add_argument("--prompt")
    p.add_argument("--prompt-file")
    p.add_argument("--contract")
    p.add_argument("--in-place", action="store_true",
                   help="work in the project itself instead of an isolated copy")
    p.add_argument("--attempts", type=int, help="override contract.attempts.max")
    p.add_argument("--timeout", type=float, default=1800.0)
    p.add_argument("--no-hooks", action="store_true",
                   help="do not add Vacant's per-run hooks (process + workspace only)")
    p.add_argument("--sandbox", default="auto")
    p.add_argument("--feedback-mode", choices=("localized", "generic", "none"),
                   default="localized",
                   help="what the next attempt is told: the traced findings (default), the "
                        "generic check summary, or nothing (a fresh re-draw)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_do, extra=[])

    p = sp.add_parser("install", help="add Vacant's hooks to each agent's own config")
    p.add_argument("--agents", help="comma list (default: all four)")
    p.add_argument("--force", action="store_true", help="write config even if the binary is "
                                                         "not found")
    p.add_argument("--observe-model", action="store_true",
                   help="also install the optional model-traffic proxy (`vacant possess`)")
    p.add_argument("--skill", action="store_true",
                   help="also add Vacant's skill file (it becomes part of the agent's prompt)")
    p.set_defaults(func=cmd_install)

    p = sp.add_parser("uninstall", help="remove only what `vacant install` added")
    p.add_argument("--agents")
    p.set_defaults(func=cmd_uninstall)

    p = sp.add_parser("adapters", help="which agents exist and whether Vacant's config is still "
                                       "in place")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_adapters)
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == ["hook"]:
        from .hook import main as hook_main
        return hook_main(raw[1:])
    extra: list[str] = []
    if "--" in raw:  # `vacant do pi --prompt … -- --model x`：`--` 之後原樣交給 agent
        i = raw.index("--")
        raw, extra = raw[:i], raw[i + 1:]
    args = build_parser().parse_args(raw)
    args.extra = extra
    try:
        return int(args.func(args))
    except C.ContractError as e:
        print("vacant: contract problems:\n" + "\n".join(f"  - {p}" for p in e.problems),
              file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"vacant: {e}", file=sys.stderr)
        return 2
