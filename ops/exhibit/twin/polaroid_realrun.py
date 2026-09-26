"""twin/polaroid_realrun — 拍立得範例上那一句，**要是分身真跑一次自己寫出來的**。

## 這支在架構裡承重什麼

人類 2026-09-26（看了範例拍立得「寫一封謝卡給國小導師」）：
「那個字是不是應該要讓他是 AI agent 生成的，不要隨便刻板」。
2026-09-26 以前的範例是 `polaroid.SAMPLES` 裡**人寫死的決定**——那是我們替分身想的句子，
放在給觀眾看的範例上等於示範一個不存在的東西。這一支把範例改成**真跑**：

1. `run`（在有 pi 的機器上，例如 vacant-dev）：每一位**合成**特質各起一個拋棄式 store，
   走**產品路徑** `twinlink generate --engine agent`（`launcher.run` → `twin_agent.sh` → pi，
   在 `vacant run` 底下、同一支 `twinagent.SYSTEM_PROMPT`），讀回它自己寫的 PLAN.md 第一行、
   run_id、收據鏈頭（`verdict_hash`）、engine，驗收據，然後撤回、刪掉暫存庫；
2. `compose`（在有 Pillow 的機器上）：拿 `run` 的紀錄，用**與 `twinlink.make_polaroid`
   相同的輸入**（`pick_cast_for(card)`、`verdict_hash[:8]`、`originals_of`）做拍立得。
   **沒有真跑成功的那一位不產範例**（`skipped` 照實列出理由）。

兩步分開是因為 vacant-dev 的系統 python 沒有 Pillow（裁決檔 §三），而 pi 只在 vacant-dev。

⚠ 特質是**合成的**（`PERSONAS`），不是任何真人——所以它們的產出可以進版控當證據。
  特質刻意多樣、**不寫 need**（需求那一格最容易替它預設要做什麼）；分身做什麼由它自己決定。
⚠ 誠實邊界：這是「這個模型、這一次」的產出，不代表分身一般會寫什麼；同一張卡再跑一次
  可能完全不同。範例 json 記下 engine／model／run_id／收據鏈頭，查得到每一句是哪一跑生的。

用法：
    # vacant-dev（pi 在 node 目錄裡；1004 LM Studio）
    PATH=$HOME/.local/opt/node-v22.23.2-linux-x64/bin:$PATH \\
    python3 ops/exhibit/twin/polaroid_realrun.py run \\
        --endpoint http://100.86.226.21:1234/v1 --out runs.json
    # 開發機（有 Pillow）
    python3 ops/exhibit/twin/polaroid_realrun.py compose --runs runs.json --out <dir>
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: 合成特質（**不是真人**）。卡上的形狀／色系／質感只決定那張黏土臉（`pick_cast_for`），
#: 刻意涵蓋「有姿勢圖」與「沒有姿勢圖」的 cast。沒有 need：不替分身預設它要做什麼。
PERSONAS: tuple[dict[str, Any], ...] = (
    {"name": "p1", "card": {"shape": "修長", "color": "灰藍", "texture": "光滑",
                            "vibe": "說話很直、不太會客套、週末會一個人去爬郊山",
                            "first_line": "先講結論。"},
     "text": "（合成的特質，不是真人）在物流倉庫排班，數字記得很牢，常常忘記吃午餐。"
             "朋友說我看起來很兇，其實只是在想事情。"},
    {"name": "p2", "card": {"shape": "粗獷", "color": "暖土", "texture": "指紋",
                            "vibe": "安靜、喜歡觀察人、對聲音很敏感",
                            "first_line": "嗯……讓我想一下。"},
     "text": "（合成的特質，不是真人）大學念化學，後來轉去做木工，手上常有小傷口。"
             "晚上會聽廣播，不太看手機。"},
    {"name": "p3", "card": {"shape": "小巧", "color": "苔綠", "texture": "斑駁",
                            "vibe": "急性子、笑點很低、很會跟陌生人聊天",
                            "first_line": "欸你知道嗎！"},
     "text": "（合成的特質，不是真人）在夜市幫家裡顧攤十幾年，最近開始自學日文，"
             "背單字背得很痛苦。"},
    {"name": "p4", "card": {"shape": "厚實", "color": "奶油", "texture": "光滑",
                            "vibe": "慢條斯理、有點固執、記性很好",
                            "first_line": "坐，不急。"},
     "text": "（合成的特質，不是真人）退休的公車司機，每天早上去公園走一圈，"
             "還記得跑過的每一條路線上每一站的名字。"},
    {"name": "p5", "card": {"shape": "圓潤", "color": "暖土", "texture": "絨面",
                            "vibe": "容易緊張但很認真、半夜才有精神",
                            "first_line": "我可以問一個可能很笨的問題嗎？"},
     "text": "（合成的特質，不是真人）剛出社會的護理師，輪三班。想養貓，但宿舍不能養。"},
    {"name": "p6", "card": {"shape": "粗獷", "color": "奶油", "texture": "絨面",
                            "vibe": "好奇、想法跳來跳去、什麼都想拆開看看",
                            "first_line": "這個可以拆開嗎？"},
     "text": "（合成的特質，不是真人）國中生，喜歡恐龍和天文，最近在學做模型，數學不太好。"},
    # 卡上什麼都沒選（形狀／色系／質感全空 ⇒ cast c01），只有貼回來的原文
    {"name": "p7", "card": {},
     "text": "（合成的特質，不是真人）我在南部長大，現在在台北做會計，每年只回家兩次。"
             "不太會表達，但很會記帳，也記得每個人借過我什麼。"},
    {"name": "p8", "card": {"shape": "方正", "color": "灰藍", "texture": "絨面",
                            "vibe": "話很多、一講就停不下來、喜歡把事情講得很完整",
                            "first_line": "好我跟你說喔，這件事要從頭講起。"},
     "text": "（合成的特質，不是真人）做了二十年的婚禮主持，現在轉行當導遊，"
             "對每個地方都有一段故事可以講。"},
)


def _wire_stats(wire: pathlib.Path) -> dict[str, int]:
    req = sorted(wire.glob("*.req.bin")) if wire.exists() else []
    resp = sorted(wire.glob("*.resp.bin")) if wire.exists() else []
    rc = sum(1 for p in resp if b'"reasoning_content":"' in (b := p.read_bytes())
             and b'"reasoning_content":""' not in b)
    return {"requests": len(req), "responses": len(resp),
            "responses_with_reasoning_content": rc}


def run_one(persona: dict[str, Any], endpoint: str, model: str, timeout: float,
            enclose: str) -> dict[str, Any]:
    """一位合成分身，產品路徑真跑一次；記下它自己寫的東西與收據；撤回；刪暫存。"""
    from ops.exhibit.twin import twinagent, twinlink, twinvault
    from ops.exhibit.twin.twinstore import KIND_SUBMITTED, TwinStore
    from vacant_network.vrun import lifecycle
    from vacant_network.vrun import verify_receipts as vrr

    sid = f"SYN-polaroid-20260926-{persona['name']}"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="twin_polaroid_"))
    rec: dict[str, Any] = {"name": persona["name"], "synthetic": True,
                           "card": persona["card"], "card_text": persona["text"],
                           "endpoint": endpoint, "model_requested": model,
                           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        db, events = tmp / "twinstore.sqlite3", tmp / "lifecycle.jsonl"
        st = TwinStore(db)
        payload, secs = st.vault.seal_card(sid, persona["card"], persona["text"],
                                           ts=int(time.time() * 1000))
        twinvault.append_sealed(st, KIND_SUBMITTED, sid, payload, secs,
                                source="polaroid_realrun:synthetic", what="card")
        st.close()
        t0 = time.time()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = twinlink.main(["--db", str(db), "generate", "--endpoint", endpoint,
                                "--model", model, "--engine", "agent", "--parallel", "1",
                                "--agent-timeout", str(timeout), "--events", str(events),
                                "--enclose", enclose])
        rec["generate_rc"], rec["wall_s"] = rc, round(time.time() - t0, 1)
        try:
            rec["generate"] = json.loads(buf.getvalue())
        except ValueError:
            rec["generate"] = buf.getvalue()[-2000:]
        st = TwinStore(db)
        tw = (st.current(sid) or {}).get("twin") or {}
        rec["twin"] = {k: tw.get(k) for k in (
            "engine", "degrade_kind", "decision", "reason", "run_id", "verdict_hash",
            "accepted", "requests_seen", "agent_rc", "agent_timed_out", "latency_ms",
            "tier", "enclosed", "twin_id")}
        rec["artifacts"] = [a.get("name") if isinstance(a, dict) else a
                            for a in (tw.get("artifacts") or [])]
        ws, rd = twinagent.paths_for(twinagent.default_work_root(db), sid)
        plan = ws / "PLAN.md"
        rec["plan_md"] = plan.read_text(encoding="utf-8", errors="replace")[:4000] \
            if plan.is_file() else None
        rec["receipts"] = [{k: r.get(k) for k in ("verdict", "chain_ok", "mediated", "tier",
                                                   "type_counts", "failures")}
                           for r in vrr.verify_run(rd)]
        rec["wire"] = _wire_stats(rd / "wire_RUN-ON")
        evs = lifecycle.read(events) if events.exists() else []
        rec["lifecycle"] = {"n": len(evs), "validate_stream": lifecycle.validate_stream(evs)}
        rec["outcome"] = twinlink.run_outcome(tw)
        rec["local_date"] = twinlink._local_date(None)      # 展場本機時區（make_polaroid 同一支）
        w = twinlink.withdraw(st, sid, reason="polaroid_realrun:cleanup")
        rec["withdrawn"] = bool(w.get("ok"))
        st.close()
    except Exception as exc:                                  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rec


def made(rec: dict[str, Any]) -> tuple[bool, str]:
    """這一跑算不算「做成了」（與 `twinlink.run_outcome == "made"` 同一個判準）。"""
    tw = rec.get("twin") or {}
    if rec.get("error"):
        return False, "error"
    if not str(tw.get("engine") or "").startswith("vacant_run:pi:"):
        return False, f"engine={tw.get('engine')}"
    if not tw.get("decision"):
        return False, "no_decision"
    if not tw.get("verdict_hash"):
        return False, "no_verdict_hash"
    if rec.get("outcome") != "made":
        return False, f"outcome={rec.get('outcome')}"
    return True, "made"


def _cmd_run(a: argparse.Namespace) -> int:
    names = set(a.only.split(",")) if a.only else None
    out = pathlib.Path(a.out)
    recs: list[dict[str, Any]] = []
    if out.exists():
        recs = json.loads(out.read_text(encoding="utf-8")).get("runs", [])
    for p in PERSONAS:
        if names and p["name"] not in names:
            continue
        rec = run_one(p, a.endpoint, a.model, a.timeout, a.enclose)
        ok, why = made(rec)
        rec["made"], rec["made_why"] = ok, why
        recs = [r for r in recs if r.get("name") != p["name"]] + [rec]
        out.write_text(json.dumps({"note": "合成特質；分身真跑（產品路徑）；每一句都是它自己寫的",
                                   "runs": recs}, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(json.dumps({"name": p["name"], "made": ok, "why": why,
                          "decision": (rec.get("twin") or {}).get("decision"),
                          "wall_s": rec.get("wall_s")}, ensure_ascii=False), flush=True)
    return 0


def _cmd_compose(a: argparse.Namespace) -> int:
    from ops.exhibit.twin import polaroid
    runs = json.loads(pathlib.Path(a.runs).read_text(encoding="utf-8"))["runs"]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    samples, skipped = [], []
    for rec in sorted(runs, key=lambda r: r["name"]):
        ok, why = made(rec)
        if not ok:
            skipped.append({"name": rec["name"], "why": why})
            continue
        tw = rec["twin"]
        cid = polaroid.pick_cast_for(rec["card"])
        date = rec["local_date"]
        png, meta = polaroid.compose(
            decision=tw["decision"], cast_id=cid, date_str=date,
            receipt_short=str(tw["verdict_hash"])[:8],
            originals=polaroid.originals_of(rec["card"], rec["card_text"]))
        name = f"polaroid_{rec['name']}_{cid}_{meta['figure']}.png"
        (out / name).write_bytes(png)
        samples.append({
            "file": name, "synthetic": True, "persona": rec["name"], "card": rec["card"],
            "decision_by_agent": tw["decision"], "engine": tw["engine"],
            "model": str(tw["engine"]).split("vacant_run:pi:", 1)[-1],
            "run_id": tw["run_id"], "verdict_hash": tw["verdict_hash"],
            "receipt_short": str(tw["verdict_hash"])[:8],
            "receipts": rec.get("receipts"), "endpoint": rec.get("endpoint"),
            "run_at": rec["at"], "cast_id": cid,
            "sha256": hashlib.sha256(png).hexdigest(), "meta": meta})
    (out / "samples.json").write_text(json.dumps({
        "note": ("合成特質（不是真人）；那一句＝分身真跑一次自己寫的 PLAN.md 第一行"
                 "（decision_by_agent），不是人寫的。沒有真跑成功的不產範例，列在 skipped。"),
        "composed_with": "polaroid.compose（與 twinlink.make_polaroid 同一組輸入）",
        "samples": samples, "skipped": skipped}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"ok": True, "n": len(samples), "skipped": skipped}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    from ops.exhibit.twin import twinagent
    ap = argparse.ArgumentParser(description="拍立得範例：分身真跑")
    s = ap.add_subparsers(dest="cmd", required=True)
    r = s.add_parser("run")
    r.add_argument("--endpoint", required=True)
    r.add_argument("--model", default="gemma-4-12b-it-qat")
    r.add_argument("--out", required=True)
    r.add_argument("--timeout", type=float, default=twinagent.DEFAULT_AGENT_TIMEOUT)
    r.add_argument("--enclose", choices=("off", "auto", "on"), default="off")
    r.add_argument("--only", default=None, help="逗號分隔的 persona 名（重跑其中幾位）")
    c = s.add_parser("compose")
    c.add_argument("--runs", required=True)
    c.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return _cmd_run(a) if a.cmd == "run" else _cmd_compose(a)


if __name__ == "__main__":
    sys.exit(main())
