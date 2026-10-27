"""trace/cli — `vacant trace …` 與 `vacant flag …`：人看病歷、人指出錯的地方。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §4.1-2、§4.5「撤銷」）：

    vacant trace show [--json] [--tail N]   每一步：行動者、工具、寫了什麼（沒有歸屬寫入時：
                                            工具輸入的一行預覽，blob 被 gc 就空白）；缺口；觀察停用狀態
    vacant trace verify                     病歷的簽章鏈驗不驗得過（有任務帳本就對它簽過的鏈頭）
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
3. `vacant trace verify` 對任務帳本的錨點只看到最後一次錨點（回合邊界寫的）；在那之後的尾巴只有
   沒簽章的 `head.json` 在看。沒有契約或帳本時輸出寫「not checked」，退出碼仍是 0。
4. 病歷不存在不是 BROKEN（BROKEN＝鏈在、但驗不過）：沒有病歷時 `verify` 照實說「沒有東西可驗」、
   退出碼 0（與 `show`／`report` 一致）；唯一例外是任務帳本已簽過這個專案的鏈頭——那代表病歷
   被整條刪掉，照舊 BROKEN、退出碼 1。
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


def _fmt_clock(ts_ms: Any) -> str:
    """`ts_ms`（epoch ms）→ 本地 `HH:MM:SS`；缺或壞 → 空字串（舊條目照樣印，round 122）。"""
    try:
        return time.strftime("%H:%M:%S", time.localtime(ts_ms / 1000))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _fmt_dur(ms: Any) -> str:
    """步的耗時 ms → `737ms`／`12s`／`12.4s`／`2m03s`；缺或壞 → 空字串（舊條目沒有
    `wall_ms`，本專案 41/6816 步）。"""
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return ""
    if ms < 0:
        return ""
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s".replace(".0s", "s")
    return f"{ms // 60_000}m{ms % 60_000 // 1000:02d}s"


def _input_preview(rec: Recorder, e: dict, limit: int = 64) -> str:
    """一步的工具輸入，取一行預覽（從物件庫）。沒有就回空字串。

    病歷 4062 個 bash 步、4055 個沒有歸屬寫入，read 也一樣——`show` 以前對這些步
    印出的是空行，看不出那步做了什麼。輸入（實際做了什麼）存在物件庫，預覽它就是
    這行誠實的內容。fail-open：blob 被 gc 掉或損壞就回空、`show` 退回舊的空行——
    本專案 5094 個輸入 blob 已有 4930 個被 gc，這是常態而不是例外，`show` 不能
    因為它失敗。"""
    sha = e.get("input_blob")
    if not sha:
        return ""
    try:
        if not rec.blobs.has(sha):
            return ""
        data = rec.blobs.get(sha)
    except Exception:
        return ""
    text = data.decode("utf-8", "replace").strip()
    try:
        obj: Any = json.loads(text)
    except (ValueError, TypeError):
        obj = None
    if isinstance(obj, dict):
        for key in ("command", "path"):            # 最常用的兩個工具輸入
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                text = v.strip()
                break
        else:
            for v in obj.values():
                if isinstance(v, str) and v.strip():
                    text = v.strip()
                    break
    elif isinstance(obj, str):
        text = obj.strip()
    first = text.splitlines()[0].strip() if text else ""
    if len(first) > limit:
        first = first[:limit] + "…"
    return first


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
    # round 107 dogfood：步驟視圖不說自己是哪個專案的病歷——在錯的 cwd 跑會靜默看到別專案
    # 的步（no-trace 訊息、verify、dashboard 都帶專案名，show 主視圖沒有）：首行帶專案路徑。
    # 只加在人的視圖；--json 的結構不變（機器消費方不該被格式變化打破）。
    print(f"workspace: {ws}")
    # 觀察狀態是**現在時**的事實，不是流水裡的一行（round 27 dogfood：病歷主視圖看不出來
    # 就等于沒有——blame 頁的小字不能替 show 背書）。`last_scan_disabled` 只看最後一個
    # 改變狀態的 coverage 事件：成功的 rescan（自動／手動，round 47 起）之後，之前的停用
    # 事件不代表現況——round 49 現場案例：gc 後增量掃描超時被停用、自動 rescan 救回
    # （state 已無 scan_disabled），banner 卻還印「revive it with `vacant trace rescan`」，
    # 指著一個已經健康的狀態。
    disabled = F.last_scan_disabled(evs)
    if disabled is not None:
        print(f"   ·  coverage: file-change observation is disabled — {disabled} "
              f"(steps are still recorded, but file changes are no longer attributed "
              f"step by step; `trace blame` will show unattributable — revive it with "
              f"`vacant trace rescan`)")
    tail = getattr(args, "tail", None)
    if tail is not None:
        if tail < 1:
            raise SystemExit("vacant: --tail must be >= 1")
        step_pos = [i for i, e in enumerate(evs) if e["type"] == "step"]
        if step_pos:                             # 最近 N 步，連同它們之間的缺口/標記一起看
            start = step_pos[-tail] if len(step_pos) > tail else step_pos[0]
            # 窗口前一筆若是缺口/標記：它是「這裡有沒記錄到的改動」的證據，留給看的人
            while start > 0 and evs[start - 1]["type"] in ("unrecorded_change", "finding", "flag"):
                start -= 1
            evs = evs[start:]
    for e in evs:
        t = e["type"]
        if t == "step":
            a = e.get("actor") or {}
            who = f"{a.get('platform')}:{a.get('agent_type') or 'main'}" + \
                (f"#{str(a['agent'])[:8]}" if a.get("agent") else "")
            w = ", ".join(f"{x['kind'][0]}:{x['path']}" for x in (e.get("writes") or [])[:6])
            if not w:
                # 沒有歸屬寫入的步（bash 99.8%）：行印工具輸入的一行預覽，blob 被 gc 就空白
                w = _input_preview(rec, e)
            flags = [k for k in ("denied", "post_missing", "pre_missing") if e.get(k)]
            if e.get("concurrent_with"):
                flags.append("concurrent")
            # round 122 dogfood：行以前只有「誰、用什麼工具、對哪個檔」——沒有「什麼時候」
            # 也沒有「花了多久」，兩者在記錄裡都有（ts_ms/wall_ms），要看只能轉 --json 自己換算。
            # 舊條目缺欄位就省掉該段（_fmt_* 回空），不崩潰、不印 None。
            clock = _fmt_clock(e.get("ts_ms"))
            dur = _fmt_dur(e.get("wall_ms"))
            print(f"{e.get('n', '?'):>4}  " + (f"{clock}  " if clock else "")
                  + f"{who:<28} {e.get('tool', '?'):<14} {w}"
                  + (f"  ({dur})" if dur else "")
                  + (f"  [{', '.join(flags)}]" if flags else "")
                  + (f"  error: {str(e['error'])[:60]}" if e.get("error") else "")
                  # round 117 dogfood：`error` 常只有一句 `tool reported an error`，真正的文字
                  # 在 blob（會 gc）；入口留了短預覽（`error_preview`），印出來才看得懂為什麼。
                  # 舊條目沒有這個欄位：不印，不報錯。
                  + (f"  [out: {str(e['error_preview'])[:80]}]" if e.get("error_preview") else ""))
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
    """簽章鏈＋`head.json`＋任務帳本裡簽過的鏈頭錨點（`stopcheck.verify_anchored`）。
    沒有契約或帳本 ⇒ 照樣驗前兩項，輸出寫明「沒有對帳本」；退出碼只有 0／1。
    沒有病歷 ⇒ 沒有東西可驗，退出碼 0（與 `show`／`report` 一致；不說「OK」，因為沒有鏈被驗過）——
    除非任務帳本已簽過這個專案的鏈頭，那代表病歷被整條刪掉，照舊 BROKEN。"""
    ws, c = _workspace(args)
    rec = Recorder(ws)
    if not rec.chain_path.is_file():
        from .stopcheck import ledger_anchor
        anchor, broken, _note = ledger_anchor(rec, c)
        if broken:
            print("BROKEN " + broken)
            return 1
        if anchor is not None:
            print(f"BROKEN no trace for {ws}, but the task ledger anchored entry "
                  f"{anchor.get('seq')} for this project (the record was deleted or moved)")
            return 1
        print(f"no trace for {ws} (nothing to verify; tracing starts when the project has a "
              f"contract, or with VACANT_TRACE=1)")
        return 0
    from .stopcheck import verify_anchored
    ok, why = verify_anchored(rec, c)
    print(("OK " if ok else "BROKEN ") + why)
    return 0 if ok else 1


def cmd_report(args: argparse.Namespace) -> int:
    ws, c = _workspace(args)
    rec = Recorder(ws)
    if args.check:
        if c is None:
            # 跟 `vacant check` 同因同語（intake/cli.py 的 no-contract 訊息）：說清找過哪、
            # 怎麼建——否則照著 `vacant trace report` 的「or run with --check」提示跑會撞這句
            # 卻不知下一步（round 17 dogfood 的同一類摩擦）。
            raise SystemExit("vacant trace report --check needs a task contract "
                             "(looked for .vacant/contract.json up to the git root). "
                             "Create one with `vacant contract init --task <id>`.")
        from ..intake import flow
        from .stopcheck import localize
        res = flow.check(c, c.base_dir)
        localize(c, res, cwd=str(ws), why_open="on request")
    rp = rec.dir / "report.md"
    if not rp.is_file():
        if c is None:
            # round 17 dogfood：無契約的工作區照原提示跑 --check 會撞 rc=1；
            # 提示要帶得起來的前提，不帶不成立的前提。
            print("no report yet (it is written at the end of each turn; "
                  "or run with --check — it re-verifies the task contract first, "
                  "which this workspace does not have yet)")
        else:
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
    rec = Recorder(ws)
    rec.checkpoint("blame")          # 行號要對得上現在的檔
    b = _blame_where(ws, c, args.where, args.value)
    if args.json:
        print(json.dumps(b, ensure_ascii=False, indent=1, default=str))
    else:
        # 覆蓋率行照實際病歷算（round 27 摩擦 3）：這裡傳空 dict 會永遠寫
        # `recorded steps: 0`，和 `trace show` 的步數字面矛盾
        # workspace 行：人的視圖要帶專案名（round 107）；JSON 結構不變
        print(F.render_report([b], [], outcome=None, coverage=F.coverage_summary(rec),
                              workspace=str(ws)), end="")
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
        print(F.render_report([b], [], outcome=None, coverage=F.coverage_summary(rec),
                              workspace=str(ws)), end="")
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
    print(f"{'actor':<60} {'runs':>5} {'accepted':>8} {'undecided':>9} {'provable':>8}  family")
    for c in st["cells"]:
        print(f"{c['label'][:60]:<60} {c['runs']:>5} {c['accepted']:>8} "
              f"{c.get('undecided', 0):>9} {c['provable_faults']:>8}  {c['key'][3]}")
    for src, v in sorted(st["sources"].items()):
        print(f"input  {src}: {v['count']} finding(s) traced to it")
    for plat, n in sorted(st["coverage_gaps"].items()):
        print(f"gaps   {plat}: {n} unrecorded change(s) behind findings (integration coverage)")
    print(f"(counts, not scores; nothing is acted on below n={A.MIN_N}; 'undecided' runs ended "
          f"on hold/escalate — waiting on review or evidence — and are not in 'runs')")
    return 0


def cmd_rescan(args: argparse.Namespace) -> int:
    ws, _c = _workspace(args)
    out = Recorder(ws).rescan()
    if getattr(args, "json", False):
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    if out.get("rescanned"):
        if not getattr(args, "json", False):
            revived = " (this revives step-by-step observation)" if out.get("was_disabled") else ""
            print(f"re-observed {out.get('files', '?')} files in {out.get('seconds', '?')}s{revived}")
            print("file-change observation is on again: subsequent steps are attributed step by step")
        return 0
    if not getattr(args, "json", False):
        print(f"rescan failed: {out.get('error', out)}", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vacant trace")
    ap.add_argument("--contract")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("show")
    p.add_argument("--json", action="store_true")
    p.add_argument("--tail", type=int, metavar="N",
                   help="show only the last N steps (with the surrounding gaps/flags); "
                        "--json is always the full record")
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
    p = sp.add_parser("rescan",
                      help="re-observe the workspace: revive step-by-step observation that was "
                           "turned off (e.g. after `vacant gc`) — long-running, user-invoked")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_rescan)
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
