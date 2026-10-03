"""把錄好的 C 組病歷，在每一次交件前檢查的那一刻重算一次（2026-09-28；v3.7 的離線驗證）。

這支在架構裡承重什麼：Colab 程式題 920 題（`decisions/conclusions/CONCLUSION_20260928_COLAB_C5_PI_VACANT361.md`）與 u274
（`decisions/conclusions/CONCLUSION_20260928_NOCAP_UNSEEN_U274.md`）找到三個缺陷；改之前先在**真的 C 組紀錄**上量：
1. **保真**：用當時的版本（v3.6.1，另一個 checkout）重算，發現的類別與動作要和紀錄裡的 `review` 事件相同——對不上就不能拿來比新版。
2. **新版**：同一個時刻、同一段紀錄，新版會發現什麼、退不退回。

做法（每一跑、每一個 `review` 事件）：
- 把病歷（`vacant_home/trace`）複製到暫存；`chain.ndjson` 截到那個 `review` 之前（`Trace` 只讀事件、不驗簽章）。
- 那一刻 agent 說的最後一段話：pi 自己的工作階段檔（`…/pi/sessions/*.jsonl`，比 `pi.txt` 完整——被切斷時 `pi.txt` 會掉尾巴），
  依 `review` 的工作階段與時間對齊，照 `vacant.ts` 的 `finalText`：那一刻之前最後一則有文字的助理訊息、截到 20000 字
  （審查之前的版本用「第 k 個沒有工具呼叫的訊息」，遇到 pi 自動重試與帶了半個工具呼叫的解碼錯誤會錯位，u274 81 次裡 19 次）。
  對齊的檢查：那一刻之前最後一則助理訊息是不是錯誤結束，要和紀錄的 `last_turn_error` 一致（`aligned`）；有引文（`quote`）的也對。
- `Evidence(...).run()` 用 `--code` 指到的那一份 `vacant_network`；退不退回用那一份的 `zerostop.pushable_for`（有的話；v3.6.1 沒有 ⇒ 用當時 `_decide` 的規則）。

**只看第一次檢查的差別才是乾淨的**：新版在第一次就放行的話，後面錄到的回合在新版裡不會發生；之後的檢查只在兩版都退回時才比。

    python3 ops/eval/colab_replay/replay_reviews.py --code <vacant 原始碼根> --cells '<glob：每一跑的目錄>' \
        --layout colab|harbor --out <jsonl>

不讀評分、不讀 `auth.json`、不讀 `intake/keys`。原始紀錄可能含不能公開散布的題目（MBPP+／HumanEval+）——輸出只寫類別與動作、引文截短，不寫題目內容。
"""
from __future__ import annotations

import argparse
import glob
import importlib
import json
import pathlib
import shutil
import sys
import tempfile
from typing import Any


def session_messages(sess_file: pathlib.Path) -> list[dict[str, Any]]:
    """pi 工作階段檔裡每一則助理訊息：時間（ms）、文字（文字段落以換行接起來）、stopReason。"""
    import datetime as dt
    out = []
    for ln in sess_file.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        m = e.get("message") or {}
        if e.get("type") != "message" or m.get("role") != "assistant":
            continue
        try:
            ts = dt.datetime.fromisoformat(str(e.get("timestamp")).replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            continue
        c = m.get("content")
        parts = c if isinstance(c, list) else [{"type": "text", "text": c or ""}]
        text = "\n".join(str(x.get("text") or "") for x in parts if isinstance(x, dict) and x.get("type") == "text")
        out.append({"ts": ts, "text": text, "stop": m.get("stopReason")})
    return out


def final_at(msgs: list[dict[str, Any]], ts_ms: float) -> dict[str, Any]:
    """交件前檢查那一刻 pi 擴充送給 Vacant 的 `final_text`：和 `vacant.ts` 的 `finalText` 同一個規則——
    那一刻之前最後一則**有文字**的助理訊息，截到 20000 字；`stop`＝那一刻之前最後一則助理訊息的 stopReason。"""
    before = [m for m in msgs if m["ts"] <= ts_ms]
    text = next((m["text"] for m in reversed(before) if m["text"].strip()), "")
    return {"text": text[:20000], "stop": before[-1]["stop"] if before else None}


def paths(cell: pathlib.Path, layout: str) -> tuple[pathlib.Path, list[pathlib.Path]]:
    if layout == "colab":
        return cell / "vacant_home" / "trace", sorted(cell.glob("agentlog/pi/sessions/*.jsonl"))
    return cell / "agent" / "vacant_home" / "trace", sorted(cell.glob("agent/pi/sessions/*.jsonl"))


def replay_cell(cell: pathlib.Path, layout: str, mods: dict[str, Any]) -> list[dict[str, Any]]:
    trace_root, sess_files = paths(cell, layout)
    projs = sorted(trace_root.glob("projects/*/chain.ndjson"))
    if not projs or not sess_files:
        return [{"cell": cell.name, "skip": "no trace or no session log"}]
    chain = projs[0]
    lines = chain.read_text(encoding="utf-8").splitlines()
    events = [json.loads(x) for x in lines if x.strip()]
    by_session = {f.stem.rsplit("_", 1)[-1]: session_messages(f) for f in sess_files}
    rows: list[dict[str, Any]] = []
    k = 0
    used = 0
    prev_request = None
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td) / "trace"
        shutil.copytree(trace_root, root, ignore=shutil.ignore_patterns("lock"))
        pdir = root / "projects" / chain.parent.name
        state = json.loads((trace_root / "projects" / chain.parent.name / "state.json").read_text())
        ws = state.get("workspace") or "/app"
        for i, ev in enumerate(events):
            if ev.get("type") != "review":
                continue
            p = ev.get("payload") or {}
            session = str(p.get("session") or "").split(":", 1)[-1]
            (pdir / "chain.ndjson").write_text("\n".join(lines[:i]) + "\n", encoding="utf-8")
            final = final_at(by_session.get(session) or [], float(ev.get("ts_ms") or 0))
            k += 1
            quotes = [f.get("quote") for f in p.get("findings") or [] if f.get("quote")]
            quote_ok = all(q.replace("…", "")[:40] in final["text"] for q in quotes) if quotes else None
            rec = mods["Recorder"](ws, root=root)
            try:
                res = mods["Evidence"](rec, platform="pi", session=session, final_text=final["text"]).run()
                err = None
            except Exception as e:  # noqa: BLE001
                res, err = {"findings": []}, f"{type(e).__name__}: {e}"[:300]
            if p.get("window_start") != prev_request:
                used, prev_request = 0, p.get("window_start")
            error_stop = bool(p.get("last_turn_error"))
            aligned = (final["stop"] == "error") == error_stop
            push = mods["pushable"](res.get("findings") or [], used, error_stop)
            action = "continue" if push and used < mods["max_rounds"] else "allow"
            rows.append({
                "cell": cell.name, "review": k, "window_start": p.get("window_start"), "error_stop": error_stop,
                "final_stop": final["stop"], "aligned": aligned, "quote_match": quote_ok, "error": err,
                "rec_action": p.get("action"), "rec_kinds": sorted({f.get("kind") + ("/" + f["sub"] if f.get("sub") else "")
                                                                    for f in p.get("findings") or []}),
                "rec_sent": len(p.get("sent") or []),
                "new_action": action, "new_kinds": sorted({f["kind"] + ("/" + f["sub"] if f.get("sub") else "")
                                                           for f in res.get("findings") or []}),
                "new_sent_kinds": sorted({f["kind"] + ("/" + f["sub"] if f.get("sub") else "") for f in push}),
                "requested_outputs": res.get("requested_outputs"), "deliverables": res.get("deliverables")})
            if p.get("action") == "continue":
                used += 1
    return rows


def load(code: pathlib.Path) -> dict[str, Any]:
    sys.path.insert(0, str(code))
    ev = importlib.import_module("vacant_network.trace.evidence")
    zs = importlib.import_module("vacant_network.trace.zerostop")
    recm = importlib.import_module("vacant_network.trace.recorder")
    assert pathlib.Path(ev.__file__).resolve().is_relative_to(code.resolve()), ev.__file__
    if hasattr(zs, "pushable_for"):
        pushable = zs.pushable_for
    else:                                               # v3.6.1 的 `_decide`：沒打開的檔只退一回合
        def pushable(findings, used, error_stop):  # noqa: ARG001 — v3.6.1 不看 error_stop
            return [f for f in findings if f["kind"] != "unread" or used < zs.UNREAD_MAX_ROUNDS]
    return {"Evidence": ev.Evidence, "Recorder": recm.Recorder, "pushable": pushable,
            "max_rounds": zs.ZERO_MAX_ROUNDS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--code", required=True, type=pathlib.Path, help="含 vacant_network/ 的原始碼根")
    ap.add_argument("--cells", required=True, help="每一跑目錄的 glob")
    ap.add_argument("--layout", choices=["colab", "harbor"], required=True)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    mods = load(a.code)
    rows: list[dict[str, Any]] = []
    for c in sorted(glob.glob(a.cells)):
        rows += replay_cell(pathlib.Path(c), a.layout, mods)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    rv = [r for r in rows if "review" in r]
    same = sum(1 for r in rv if r["rec_action"] == r["new_action"] and
               sorted(k.split("/")[0] for k in r["rec_kinds"]) == sorted(k.split("/")[0] for k in r["new_kinds"]))
    print(json.dumps({"cells": len({r["cell"] for r in rows}), "reviews": len(rv), "same_action_and_kinds": same,
                      "not_aligned": sum(1 for r in rv if not r["aligned"]),
                      "quote_mismatch": sum(1 for r in rv if r["quote_match"] is False),
                      "errors": sum(1 for r in rv if r["error"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
