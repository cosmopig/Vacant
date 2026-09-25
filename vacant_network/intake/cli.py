"""intake 的命令列——`vacant contract|check|submit|review|reverify|approve|release|withdraw|task|keys|intake`。

這支在架構裡承重什麼：把 `flow.py` 的每一步變成一個**任何 agent 都呼叫得到**的指令。
pi、Claude Code、OpenCode、Codex 四個都有 shell 工具 ⇒ `vacant check` 是它們唯一
百分之百共通的呼叫面（MCP 不是：pi 沒有；hook 格式也各不相同）。

## 退出碼（與 `vacant run`／gateshim 的 20–26 分開，那一套的語意不動）

| 碼 | 意思 |
|---|---|
| 0 | accept（check／submit）、released（release） |
| 40 | reject |
| 41 | hold（有必要主張判不了——等證據或人工審查） |
| 42 | escalate（證據矛盾） |
| 43 | void（基礎設施失敗：不是成果的錯，也不是成功） |
| 44 | release refused（收件端拒絕放行） |
| 45 | release unconfirmed（做了，但目的端讀回不成立——先查，不要重做） |
| 2 | 用法／契約錯誤 |

⚠ `0` 只表示「在這份契約、這些驗證器觀測得到的範圍內沒有發現不合格」，不是「做得好」。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from . import contract as C
from . import flow, keys
from . import home as _home
from .ledger import LedgerError, report as ledger_report

EXIT = {"accept": 0, "reject": 40, "hold": 41, "escalate": 42, "void": 43,
        "release_refused": 44, "release_unconfirmed": 45}

TOP = ("contract", "check", "submit", "review", "reverify", "approve", "release",
       "withdraw", "task", "keys", "intake")


def _emit(obj: Any, as_json: bool, human: str) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    else:
        print(human)


def _contract_path(args) -> pathlib.Path:
    if getattr(args, "contract", None):
        return pathlib.Path(args.contract)
    found = C.find(pathlib.Path.cwd())
    if found is None:
        raise SystemExit("vacant: no contract found (looked for .vacant/contract.json up to the "
                         "git root). Create one with `vacant contract init --task <id>`.")
    return found


def _summary(res: dict[str, Any]) -> str:
    lines = []
    oc = res.get("outcome") or ("void" if res.get("void") else "?")
    art = (res.get("artifact_sha256") or "")[:12]
    cov = res.get("coverage") or {}
    lines.append(f"[vacant] {oc.upper()}  artifact {art or '-'}  "
                 f"required {cov.get('pass', '?')}/{cov.get('required', '?')} PASS")
    for r in res.get("results", []):
        mark = {"PASS": "✓", "FAIL": "✗", "UNKNOWN": "?", "CONFLICT": "!"}[r["status"]]
        req = "" if r.get("required") else " (optional)"
        lines.append(f"  {mark} {r['claim_id']}{req}: {r['status']} — {r['detail'][:200]}")
    if not res.get("results"):
        for x in res.get("reasons", []):
            lines.append(f"  - {x}")
    if oc == "accept" and not res.get("dry_run"):
        lines.append("  next: `vacant release` (the recipient re-checks everything before "
                     "publishing)")
    return "\n".join(lines)


def _outcome_exit(res: dict[str, Any]) -> int:
    if res.get("void"):
        return EXIT["void"]
    return EXIT.get(str(res.get("outcome")), 2)


# ── commands ─────────────────────────────────────────────────────────

def cmd_contract(args) -> int:
    if args.action == "init":
        target = pathlib.Path(args.path or ".vacant/contract.json")
        if target.exists():
            raise SystemExit(f"vacant: {target} already exists (refusing to overwrite)")
        raw = C.scaffold(args.task, objective=args.objective or "",
                         deliverable=args.deliverable or None,
                         destination=args.to or "dir:.vacant/published")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[vacant] wrote {target}. Edit its claims, then `vacant contract lock`.")
        return 0
    if args.action == "quick":
        return _contract_quick(args)
    path = _contract_path(args)
    if args.action == "lock":
        res = flow.lock(path)
        _emit(res, args.json, f"[vacant] pinned {len(res['pins'])} input(s) and locked "
                              f"contract {res['contract_sha256'][:12]}… for task "
                              f"{res['lock']['payload']['task_id']} (owner-signed; edit the "
                              f"contract ⇒ lock again)")
        return 0
    c = C.load(path)
    if args.action == "validate":
        print(f"[vacant] {path}: valid (task {c.task_id}, {len(c.claims)} claims, "
              f"sha256 {c.sha256[:12]}…)")
        return 0
    info = {"path": str(path), "task_id": c.task_id, "version": c.version,
            "contract_sha256": c.sha256, "base_dir": str(c.base_dir),
            "claims": [{"id": x.id, "verifier": x.verifier, "required": x.required,
                        "authority": x.authority} for x in c.claims],
            "release": c.release}
    _emit(info, True, "")
    return 0


def _contract_quick(args) -> int:
    """`vacant contract quick`：一行寫出一份會驗人在意的事的契約（`contract.quick`）；`--lock` 順便釘住輸入、簽名。"""
    target = pathlib.Path(args.path or ".vacant/contract.json")
    if target.exists():
        raise SystemExit(f"vacant: {target} already exists (refusing to overwrite)")
    base = (target.parent.parent if target.parent.name == ".vacant" else target.parent)
    try:
        raw, summary = C.quick(base, deliverable=args.deliverable or [], inputs=args.input,
                               must=args.must, must_not=args.must_not, headings=args.heading,
                               totals=args.total, report=args.report, task_id=args.task,
                               objective=args.objective or "",
                               destination=args.to or "dir:.vacant/published")
    except C.ContractError as e:
        raise SystemExit("vacant: " + "; ".join(e.problems)) from None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["path"] = str(target)
    if args.lock:
        res = flow.lock(target)
        summary["locked"] = {"contract_sha256": res["contract_sha256"], "pins": res["pins"]}
    req = [c for c in summary["checks"] if c["required"]]
    lines = [f"[vacant] wrote {target} (task {summary['task_id']}): {len(req)} required "
             f"check(s), {len(summary['checks']) - len(req)} advisory, 0 human review"]
    lines += [f"  - {c['what']}" + ("" if c["required"] else " (advisory)")
              for c in summary["checks"]]
    lines.append(f"  not checked: {summary['not_checked']}")
    lines += [f"  hint: {h}" for h in summary["hints"]]
    lines.append("  locked: inputs pinned and the contract signed with your owner key" if args.lock
                 else "  next: `vacant contract lock` (pins the inputs and signs the contract)")
    _emit(summary, args.json, "\n".join(lines))
    return 0


def cmd_check(args) -> int:
    c = C.load(_contract_path(args))
    res = flow.check(c, pathlib.Path(args.dir or c.base_dir), sandbox=args.sandbox,
                     reveal_hidden=args.reveal_hidden)
    _emit(res, args.json, _summary(res))
    return _outcome_exit(res)


def cmd_submit(args) -> int:
    task = flow.open_task(_contract_path(args))
    res = flow.submit(task, pathlib.Path(args.dir or task.contract.base_dir),
                      source=args.source, sandbox=args.sandbox)
    _emit(res, args.json, _summary(res))
    return _outcome_exit(res)


def cmd_review(args) -> int:
    task = flow.open_task(_contract_path(args))
    flow.review(task, claim_id=args.claim, verdict=args.verdict, reason=args.reason,
                artifact_sha256=args.artifact)
    res = flow.reverify(task, args.artifact, sandbox=args.sandbox)
    _emit(res, args.json, _summary(res))
    return _outcome_exit(res)


def cmd_reverify(args) -> int:
    task = flow.open_task(_contract_path(args))
    res = flow.reverify(task, args.artifact, sandbox=args.sandbox)
    _emit(res, args.json, _summary(res))
    return _outcome_exit(res)


def cmd_approve(args) -> int:
    task = flow.open_task(_contract_path(args))
    doc = flow.approve(task, artifact_sha256=args.artifact, destination=args.to,
                       ttl_s=args.ttl)
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    p = doc["payload"]
    _emit(doc, args.json, f"[vacant] approved {p['artifact_sha256'][:12]}… → "
                          f"{p['destination']} (expires in {args.ttl:.0f}s, single use)")
    return 0


def cmd_release(args) -> int:
    task = flow.open_task(_contract_path(args))
    appr = json.loads(pathlib.Path(args.approval).read_text()) if args.approval else None
    res = flow.release(task, artifact_sha256=args.artifact, destination=args.to,
                       approval_doc=appr)
    if res.get("released"):
        human = (f"[vacant] RELEASED {res.get('effect')} → {res.get('location')} "
                 f"(read back: {'ok' if res.get('readback_ok') else 'FAILED'})")
        code = 0
    elif res.get("void"):
        human = "[vacant] RELEASE VOID (infrastructure failure; recorded)\n" + "\n".join(
            f"  - {r}" for r in res.get("reasons", []))
        code = EXIT["void"]
    elif res.get("effect"):
        human = (f"[vacant] RELEASE UNCONFIRMED ({res.get('effect')}): "
                 + "; ".join(res.get("readback_problems") or res.get("reasons") or []))
        code = EXIT["release_unconfirmed"]
    else:
        human = "[vacant] RELEASE REFUSED\n" + "\n".join(f"  - {r}" for r in res["reasons"])
        code = EXIT["release_refused"]
    _emit(res, args.json, human)
    return code


def cmd_withdraw(args) -> int:
    task = flow.open_task(_contract_path(args))
    res = flow.withdraw(task, reason=args.reason, destination=args.to)
    if res.get("void"):
        _emit(res, args.json, "[vacant] WITHDRAW VOID: " + "; ".join(res.get("reasons", [])))
        return EXIT["void"]
    _emit(res, args.json, f"[vacant] withdrawn from {res['destination']} "
                          f"(read back: {'gone' if res['readback_ok'] else 'STILL PRESENT'}); "
                          f"{res['note']}")
    return 0 if res["readback_ok"] else EXIT["release_unconfirmed"]


def cmd_task(args) -> int:
    if args.action == "report":
        rep = ledger_report(trust=keys.Trust.load())
        if args.json:
            _emit(rep, True, "")
        else:
            print(f"[vacant] {rep['n_tasks']} task(s); by state: "
                  + ", ".join(f"{k}={v}" for k, v in rep["by_state"].items() if v))
            for t in rep["tasks"]:
                print(f"  {t['task_id']:<32} {t['state']:<20} attempts={t['attempts']} "
                      f"decisions={t['decisions']} void={t['void']} "
                      f"ledger={'ok' if t.get('ledger_ok') else 'BROKEN'}")
            print(f"  ({rep['note']})")
        return 0
    task = flow.open_task(_contract_path(args))
    if args.action == "verify":
        ok, why = task.ledger.verify(task.trust)
        print(f"[vacant] ledger {task.ledger.path}: {'OK' if ok else 'BROKEN'} — {why}")
        return 0 if ok else 1
    st = flow.status(task)
    human = (f"[vacant] {st['task_id']}: {st['state']}  (attempts {st['attempts']}, "
             f"decisions {st['decisions']}, void {st['void']})")
    for x in st.get("latest_reasons") or []:
        human += f"\n  - {x}"
    _emit(st, args.json, human)
    return 0


def cmd_keys(args) -> int:
    if args.action == "init":
        out = keys.init_local(name=args.name)
        _emit(out, args.json, "[vacant] local keys ready:\n" + "\n".join(
            f"  {role:<9} {pub}" for role, pub in out.items()))
        return 0
    if args.action == "add":
        t = keys.Trust.load()
        t.add(args.role, args.name, args.pub)
        t.save()
        print(f"[vacant] {args.name} is now an accepted {args.role} in {t.path}")
        return 0
    t = keys.Trust.load()
    _emit(t.data, True, "")
    return 0


def cmd_intake(args) -> int:
    from .server import serve
    return serve(contracts=[pathlib.Path(c) for c in args.contract], host=args.host,
                 port=args.port, token_file=args.token_file,
                 insecure_no_token=args.insecure_no_token, sandbox=args.sandbox)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vacant",
        description="Vacant intake: contract → quarantine → evidence → decision → release. "
                    "Works the same for pi, Claude Code, OpenCode, Codex, any other agent, "
                    "or a human upload; it never needs to see model traffic.")
    sp = ap.add_subparsers(dest="cmd", required=True)

    def common(p, *, sandbox=False):
        p.add_argument("--contract", help="contract file (default: nearest .vacant/contract.json)")
        p.add_argument("--json", action="store_true", help="print JSON")
        if sandbox:
            p.add_argument("--sandbox", default="auto",
                           help="sandbox for executable checks (auto|bwrap|unshare|none)")

    p = sp.add_parser("contract", help="create / lock / validate / show the task contract")
    p.add_argument("action", choices=["init", "quick", "lock", "validate", "show"])
    p.add_argument("--task", help="task id (init/quick)")
    p.add_argument("--objective", help="objective text (init/quick)")
    p.add_argument("--deliverable", action="append",
                   help="deliverable file or glob (init/quick, repeatable)")
    p.add_argument("--input", action="append",
                   help="quick: a file the task is given; pinned by sha256 on lock (repeatable)")
    p.add_argument("--must", action="append",
                   help="quick: plain text the deliverable must contain (repeatable)")
    p.add_argument("--must-not", action="append", dest="must_not",
                   help="quick: plain text the deliverable must not contain (repeatable)")
    p.add_argument("--heading", action="append",
                   help="quick: a heading the deliverable must have (repeatable)")
    p.add_argument("--total", action="append",
                   help="quick: [INPUT:]COLUMN — the total the deliverable states equals the sum "
                        "of that column of a CSV input (repeatable)")
    p.add_argument("--report", help="quick: the file --must/--total read (default: the "
                                    "deliverable, when it is one file)")
    p.add_argument("--lock", action="store_true", help="quick: lock right away")
    p.add_argument("--to", help="release destination, e.g. dir:published or git:repo#branch")
    p.add_argument("--path", help="where to write the new contract (init)")
    common(p)
    p.set_defaults(func=cmd_contract)

    p = sp.add_parser("check", help="verify a directory against the contract (dry run: "
                                    "nothing is recorded or released)")
    p.add_argument("--dir", help="directory to check (default: the project root)")
    p.add_argument("--reveal-hidden", action="store_true",
                   help="show the details of hidden claims (for the contract owner)")
    common(p, sandbox=True)
    p.set_defaults(func=cmd_check)

    p = sp.add_parser("submit", help="freeze a directory into the quarantine, verify, decide, "
                                     "record")
    p.add_argument("--dir", help="directory to submit (default: the project root)")
    p.add_argument("--source", default="cli", help="free-text label of who produced it")
    common(p, sandbox=True)
    p.set_defaults(func=cmd_submit)

    p = sp.add_parser("review", help="record a signed human review of the latest candidate")
    p.add_argument("claim")
    p.add_argument("verdict", choices=["pass", "fail"])
    p.add_argument("--reason", required=True)
    p.add_argument("--artifact")
    common(p, sandbox=True)
    p.set_defaults(func=cmd_review)

    p = sp.add_parser("reverify", help="re-run the verifiers on a quarantined candidate")
    p.add_argument("--artifact")
    common(p, sandbox=True)
    p.set_defaults(func=cmd_reverify)

    p = sp.add_parser("approve", help="sign a single-use approval bound to one artifact and "
                                      "one destination")
    p.add_argument("--artifact")
    p.add_argument("--to")
    p.add_argument("--ttl", type=float, default=24 * 3600.0)
    p.add_argument("--out", help="also write the approval document to this file")
    common(p)
    p.set_defaults(func=cmd_approve)

    p = sp.add_parser("release", help="publish an accepted candidate through the recipient "
                                      "gate and read it back")
    p.add_argument("--artifact")
    p.add_argument("--to")
    p.add_argument("--approval", help="approval document file (default: the latest recorded)")
    common(p)
    p.set_defaults(func=cmd_release)

    p = sp.add_parser("withdraw", help="withdraw a released deliverable from the destination")
    p.add_argument("--reason", required=True)
    p.add_argument("--to")
    common(p)
    p.set_defaults(func=cmd_withdraw)

    p = sp.add_parser("task", help="task state, ledger verification, report over all tasks")
    p.add_argument("action", choices=["status", "verify", "report"])
    common(p)
    p.set_defaults(func=cmd_task)

    p = sp.add_parser("keys", help="local signing keys and the accepted-signer list")
    p.add_argument("action", choices=["init", "show", "add"])
    p.add_argument("role", nargs="?", choices=list(keys.ROLES))
    p.add_argument("name", nargs="?")
    p.add_argument("pub", nargs="?")
    p.add_argument("--name", dest="name_opt")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_keys)

    p = sp.add_parser("intake", help="run the HTTP intake (submitters can only submit)")
    p.add_argument("action", choices=["serve"])
    p.add_argument("--contract", action="append", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8740)
    p.add_argument("--token-file", help="file holding the submitter bearer token")
    p.add_argument("--insecure-no-token", action="store_true",
                   help="development only: accept submissions without a token")
    p.add_argument("--sandbox", default="auto")
    p.set_defaults(func=cmd_intake)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "keys":
        args.name = args.name_opt or args.name
    try:
        return int(args.func(args))
    except C.ContractError as e:
        print("vacant: contract problems:\n" + "\n".join(f"  - {p}" for p in e.problems),
              file=sys.stderr)
        return 2
    except LedgerError as e:
        # 帳本本身壞了：這不是用法錯誤，也不是成果的錯——基礎設施失敗
        print(f"vacant: {e}", file=sys.stderr)
        return EXIT["void"]
    except ValueError as e:
        print(f"vacant: {e}", file=sys.stderr)
        return 2


def vacant_home() -> pathlib.Path:
    return _home()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
