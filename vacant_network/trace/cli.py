"""trace/cli — `vacant trace …` 與 `vacant flag …`：人看病歷、人指出錯的地方。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.1-2、§4.5「撤銷」）：

    vacant trace show [--json]              每一步：行動者、工具、寫了什麼；缺口
    vacant trace verify                     病歷的簽章鏈驗不驗得過
    vacant trace report [--check]           未解問題清單（`--check` 先重驗一次契約再追緝）
    vacant trace blame <檔>[:<行>] [--value V]   這個位置的值是哪一步、從哪裡來的
    vacant flag <檔>[:<行>] "<哪裡錯>" [--value V]   人指出錯處：簽章、追緝、進病歷
    vacant flag --dismiss <finding_id> "<理由>"      人撤銷一個追緝結論（信譽效果反轉，兩筆都留）

開放任務沒有免費的裁判（論文 7.1 test oracle）：契約寫不出來的錯，**人指出來**就是最誠實的
判準。標記用 owner 金鑰簽（K13：鏈的終點是人），綁繳付物目前的內容雜湊與位置。

## 誠實邊界（改碼請保留）

1. 標記**不擋**收件（v1）：它進病歷、進給人的報告、進下一次回合邊界給 agent 的回饋；
   要讓人的判斷擋收件，用契約裡的 `review` 主張（`vacant review`）。
2. owner 金鑰和 agent 在同一台機器、同一個帳號 ⇒ agent 的 shell 也叫得到 `vacant flag`；
   報告照實寫出簽章者，不宣稱那一定是人按的。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import time
from typing import Any

from ..intake import contract as C
from ..intake import keys as _keys
from . import blame as B
from . import feedback as F
from .locate import Location
from .recorder import Recorder


def _workspace(args: argparse.Namespace) -> tuple[pathlib.Path, Any]:
    cpath = pathlib.Path(args.contract) if getattr(args, "contract", None) \
        else C.find(pathlib.Path.cwd())
    if cpath is not None:
        c = C.load(cpath)
        return c.base_dir, c
    return pathlib.Path.cwd().resolve(), None


def _parse_where(where: str) -> tuple[str, int | None]:
    path, _, line = where.partition(":")
    if line:
        first = line.split("-", 1)[0]
        if first.isdigit():
            return path, int(first)
    return where, None


def _rel(ws: pathlib.Path, path: str) -> str:
    p = pathlib.Path(path)
    p = p if p.is_absolute() else pathlib.Path.cwd() / p
    try:
        return p.resolve().relative_to(ws).as_posix()
    except ValueError:
        raise SystemExit(f"vacant: {path} is not inside the project {ws}") from None


def cmd_show(args: argparse.Namespace) -> int:
    ws, _c = _workspace(args)
    rec = Recorder(ws)
    evs = rec.events()
    if args.json:
        print(json.dumps(evs, ensure_ascii=False, indent=1, default=str))
        return 0
    if not evs:
        print(f"no trace for {ws} (tracing starts when the project has a contract, or "
              f"with VACANT_TRACE=1)")
        return 0
    for e in evs:
        t = e["type"]
        if t == "step":
            a = e.get("actor") or {}
            who = f"{a.get('platform')}:{a.get('agent_type') or 'main'}" + \
                (f"#{str(a['agent'])[:8]}" if a.get("agent") else "")
            w = ", ".join(f"{x['kind'][0]}:{x['path']}" for x in (e.get("writes") or [])[:6])
            flags = [k for k in ("denied", "post_missing", "pre_missing") if e.get(k)]
            if e.get("concurrent_with"):
                flags.append("concurrent")
            print(f"{e.get('n', '?'):>4}  {who:<28} {e.get('tool', '?'):<14} {w}"
                  + (f"  [{', '.join(flags)}]" if flags else "")
                  + (f"  error: {str(e['error'])[:60]}" if e.get("error") else ""))
        elif t == "unrecorded_change":
            print(f"   ·  GAP ({e.get('observed_at')}): "
                  + ", ".join(c["path"] for c in (e.get("changes") or [])[:6]))
        elif t in ("finding", "flag"):
            loc = e.get("location") or {}
            print(f"   !  {t} {e.get('finding_id') or e.get('flag_id')} "
                  f"{e.get('status', '')} {loc.get('path', '')}:{loc.get('line', '')} "
                  f"{e.get('confidence', '')}")
        elif t in ("session_closed", "transcript"):
            print(f"   ·  {t} {(e.get('actor') or {}).get('session', '')}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    ws, _c = _workspace(args)
    ok, why = Recorder(ws).verify()
    print(("OK " if ok else "BROKEN ") + why)
    return 0 if ok else 1


def cmd_report(args: argparse.Namespace) -> int:
    ws, c = _workspace(args)
    rec = Recorder(ws)
    if args.check:
        if c is None:
            raise SystemExit("vacant trace report --check needs a task contract")
        from ..intake import flow
        from .stopcheck import localize
        res = flow.check(c, c.base_dir)
        localize(c, res, cwd=str(ws), why_open="on request")
    rp = rec.dir / "report.md"
    if not rp.is_file():
        print("no report yet (it is written at the end of each turn; or run with --check)")
        return 0
    print(rp.read_text(encoding="utf-8"), end="")
    return 0


def _blame_where(ws: pathlib.Path, c: Any, where: str, value: str | None) -> dict[str, Any]:
    path, line = _parse_where(where)
    rel = _rel(ws, path)
    return B.blame_location(B.Trace(Recorder(ws)), Location(rel, line, value=value), contract=c)


def cmd_blame(args: argparse.Namespace) -> int:
    ws, c = _workspace(args)
    Recorder(ws).checkpoint("blame")          # 行號要對得上現在的檔
    b = _blame_where(ws, c, args.where, args.value)
    if args.json:
        print(json.dumps(b, ensure_ascii=False, indent=1, default=str))
    else:
        print(F.render_report([b], [], outcome=None, coverage={}), end="")
    return 0


def cmd_flag(args: argparse.Namespace) -> int:
    ws, c = _workspace(args)
    rec = Recorder(ws)
    owner = _keys.load_or_create("owner")
    if args.dismiss:
        known = {str(e.get("finding_id") or e.get("flag_id")) for e in rec.events()
                 if e["type"] in ("finding", "flag")}
        if args.dismiss not in known:
            # 不存在的 id 不收：否則會預先撤銷一個之後才出現的結論（審查 consequences#5）
            print(f"vacant flag: no finding or flag {args.dismiss!r} in this project's trace "
                  f"(see `vacant trace show`)", file=sys.stderr)
            return 2
        doc = _keys.sign_doc(owner, {"kind": "dismiss", "finding_id": args.dismiss,
                                     "reason": args.note or "", "ts": time.time()})
        ref = rec.append("flag", {"flag_id": "d_" + args.dismiss, "dismisses": args.dismiss,
                                  "signed": doc})
        from . import actors as A
        if A.dismiss(A.ActorBook(), args.dismiss, args.note or ""):
            rec.append("consequence", {"kind": "dismiss", "finding_id": args.dismiss})
        print(f"dismissed {args.dismiss} (trace entry {ref['seq']})")
        return 0
    if not args.where:
        raise SystemExit("vacant flag: give <file>[:<line>] and what is wrong")
    path, line = _parse_where(args.where)
    rel = _rel(ws, path)
    fp = ws / rel
    content_sha = hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else None
    value = args.value
    if value is None and line is not None and fp.is_file():
        lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        value = lines[line - 1].strip() if 0 < line <= len(lines) else None
    loc = Location(rel, line, value=value, note=args.note or "")
    fid = "h_" + hashlib.sha256(json.dumps([rel, line, value, args.note]).encode()).hexdigest()[:10]
    doc = _keys.sign_doc(owner, {"kind": "flag", "flag_id": fid, "location": loc.to_json(),
                                 "note": args.note or "", "file_sha256": content_sha,
                                 "ts": time.time()})
    rec.append("flag", {"flag_id": fid, "location": loc.to_json(), "note": args.note or "",
                        "file_sha256": content_sha, "signed": doc, "status": "open"})
    rec.checkpoint("flag")
    b = B.blame_location(B.Trace(rec), loc, contract=c)
    b["claim"] = f"flag:{fid}"
    rec.append("finding", {"finding_id": fid, "status": "open", "from_flag": True, **{
        k: b.get(k) for k in ("claim", "location", "value", "state", "fault_class",
                              "confidence", "layer", "step", "source", "candidates", "note")}})
    if args.json:
        print(json.dumps({"flag_id": fid, "blame": b}, ensure_ascii=False, indent=1, default=str))
    else:
        print(f"flag {fid} recorded (signed with the owner key {_keys.pub_hex(owner)[:12]}…)")
        print(F.render_report([b], [], outcome=None, coverage={}), end="")
    return 0


def _owner_signed(e: dict[str, Any], trust: Any) -> bool:
    """這個標記／撤銷真的是委託者（owner 金鑰）簽的，而且簽的就是事件裡寫的內容。
    病歷的鏈是 verifier 金鑰簽的，任何能寫檔的步驟都可以往裡面加一筆「flag」——沒有 owner 簽章的
    不可以被當成委託者的話回饋給 agent（2026-09-24 審查 credit#8：子 agent 偽造一個標記＝提示注入）。"""
    doc = e.get("signed")
    who, why = _keys.verify_doc(doc, trust=trust, role="owner")
    if who is None or why or not isinstance(doc, dict):
        return False
    p = doc.get("payload") or {}
    if e.get("dismisses"):
        return p.get("kind") == "dismiss" and p.get("finding_id") == e.get("dismisses")
    return (p.get("kind") == "flag" and p.get("flag_id") == e.get("flag_id")
            and p.get("note", "") == e.get("note", "") and p.get("location") == e.get("location"))


def open_flags(rec: Recorder) -> list[dict[str, Any]]:
    """還沒撤銷的人標記（`stopcheck` 會把它們帶進下一次回合邊界的回饋）。只收 owner 簽過的。"""
    trust = _keys.Trust.load()
    flags: dict[str, dict[str, Any]] = {}
    dismissed: set[str] = set()
    for e in rec.events():
        if e["type"] != "flag" or not _owner_signed(e, trust):
            continue
        if e.get("dismisses"):
            dismissed.add(str(e["dismisses"]))
        elif e.get("flag_id"):
            flags[str(e["flag_id"])] = e
    return [f for k, f in flags.items() if k not in dismissed]


def cmd_actors(args: argparse.Namespace) -> int:
    from . import actors as A
    st = A.ActorBook().state()
    st.pop("reputation", None)
    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=1))
        return 0
    if not st["cells"] and not st["sources"]:
        print("no consequences recorded yet")
        return 0
    print(f"{'actor':<60} {'runs':>5} {'accepted':>8} {'provable':>8}  family")
    for c in st["cells"]:
        print(f"{c['label'][:60]:<60} {c['runs']:>5} {c['accepted']:>8} "
              f"{c['provable_faults']:>8}  {c['key'][3]}")
    for src, v in sorted(st["sources"].items()):
        print(f"input  {src}: {v['count']} finding(s) traced to it")
    for plat, n in sorted(st["coverage_gaps"].items()):
        print(f"gaps   {plat}: {n} unrecorded change(s) behind findings (integration coverage)")
    print(f"(counts, not scores; nothing is acted on below n={A.MIN_N})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vacant trace")
    ap.add_argument("--contract")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("show")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)
    p = sp.add_parser("verify")
    p.set_defaults(func=cmd_verify)
    p = sp.add_parser("report")
    p.add_argument("--check", action="store_true")
    p.set_defaults(func=cmd_report)
    p = sp.add_parser("actors", help="consequences per actor: runs, accepted, provable faults")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_actors)
    p = sp.add_parser("blame")
    p.add_argument("where")
    p.add_argument("--value")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_blame)
    return ap


def flag_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vacant flag")
    ap.add_argument("where", nargs="?")
    ap.add_argument("note", nargs="?")
    ap.add_argument("--value")
    ap.add_argument("--dismiss", metavar="FINDING_ID")
    ap.add_argument("--contract")
    ap.add_argument("--json", action="store_true")
    ap.set_defaults(func=cmd_flag)
    return ap


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        if raw[:1] == ["flag"]:
            args = flag_parser().parse_args(raw[1:])
            if args.dismiss and args.where and not args.note:
                args.note = args.where
            return int(args.func(args))
        args = build_parser().parse_args(raw[1:] if raw[:1] == ["trace"] else raw)
        return int(args.func(args))
    except C.ContractError as e:
        print("vacant: contract problems:\n" + "\n".join(f"  - {p}" for p in e.problems),
              file=sys.stderr)
        return 2
    except OSError as e:
        print(f"vacant: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    raise SystemExit(main())
