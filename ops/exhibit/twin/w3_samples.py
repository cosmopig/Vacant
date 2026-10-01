"""twin/w3_samples — W3（2026-10-01）世界＋複雜需求指令的真跑樣本。

這支在架構裡承重什麼：和 divination_samples 同一批 6 組合成特質，改跑 W3 指令
（SYSTEM_PROMPT 帶 WORLD.md 前提與複雜度條件），把每一跑的決定句、「如果你在這裡」全文、
成品、說的話、秒數、回合數、工具呼叫數原樣收起來，並自查：有沒有照抄 WORLD.md 連續 ≥12 字、
工作區裡是否真的有 WORLD.md（sha256 對得上）。

⚠ 不經過任何審查閘門（`allow_no_suite`，`accepted=null`）；特質是合成的；6 筆不是統計。
⚠ 不改 timeout：沿用 `--timeout`（預設 300）只為量測；超過就如實記「被切斷」。
"""
from __future__ import annotations

import argparse
import contextlib
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

PERSONAS: tuple[dict[str, Any], ...] = (
    {"name": "d1", "card": {"shape": "厚實", "color": "暖土", "texture": "斑駁",
                            "vibe": "話少、慢慢說、嘴上總說「沒關係啦」",
                            "first_line": "吃飽沒。"},
     "text": "（合成的特質，不是真人）開了三十年公車，上個月剛退休。每天還是四點半自然醒，"
             "去市場繞一圈什麼也沒買。女兒在國外，視訊講不到五分鐘就說「你忙你的」。"
             "不想麻煩任何人。"},
    {"name": "d2", "card": {"shape": "修長", "color": "灰藍", "texture": "光滑",
                            "vibe": "禮貌、怕冷場、被問到喜歡什麼就會愣一下",
                            "first_line": "我都可以。"},
     "text": "（合成的特質，不是真人）高三。成績中上，爸媽希望念醫學系。晚上寫完考卷之後"
             "會偷偷畫幾格漫畫，畫完又撕掉。從來沒給任何人看過。"},
    {"name": "d3", "card": {"shape": "小巧", "color": "珊瑚", "texture": "指紋",
                            "vibe": "語速快、愛開玩笑、笑完會突然安靜",
                            "first_line": "歡迎光臨——欸你先坐！"},
     "text": "（合成的特質，不是真人）咖啡店開了三個月，帳面剛好打平，只請了一個大學生"
             "週末幫忙。常常凌晨三點醒來重算一次帳。不太跟家人說店裡的狀況。"},
    {"name": "d4", "card": {"shape": "粗獷", "color": "深藍", "texture": "光滑",
                            "vibe": "冷靜、動作很快、很討厭被問「累不累」",
                            "first_line": "說重點。"},
     "text": "（合成的特質，不是真人）醫院夜班護理師，作息顛倒，朋友約不到人。養了一隻"
             "十六歲的老貓，貓最近吃得比較少。下班回家第一件事是看貓有沒有動。"},
    {"name": "d5", "card": {"shape": "圓潤", "color": "苔綠", "texture": "斑駁",
                            "vibe": "自嘲、拖延、講話常常講到一半放棄",
                            "first_line": "呃，算了，沒事。"},
     "text": "（合成的特質，不是真人）碩二，論文卡在第三章。指導教授三個月沒回信。"
             "最近開始整理房間，整理到凌晨，書桌卻一直沒碰。"},
    {"name": "d6", "card": {"shape": "方正", "color": "奶油", "texture": "指紋",
                            "vibe": "客氣、字斟句酌、說話像在寫報告",
                            "first_line": "您好，不好意思打擾。"},
     "text": "（合成的特質，不是真人）外派到異國城市半年的工程師，語言不太通。每天中午吃"
             "同一家便當，會對店員說謝謝，但沒有再多講過一句話。手機裡存著很多還沒回的訊息。"},
)


def longest_shared(a: str, b: str, floor: int = 12) -> list[str]:
    """b 裡與 a 連續相同 ≥ floor 字的片段（去重、取每處最長）。"""
    hits: list[str] = []
    i = 0
    while i + floor <= len(b):
        seg = b[i:i + floor]
        if "\n" not in seg and seg in a:
            j = i + floor
            while j < len(b) and b[i:j + 1] in a:
                j += 1
            hits.append(b[i:j])
            i = j
        else:
            i += 1
    return hits


def run_one(persona: dict[str, Any], endpoint: str, model: str, timeout: float) -> dict[str, Any]:
    from ops.exhibit.twin import twinagent, twinlink, twinvault
    from ops.exhibit.twin.twinstore import KIND_SUBMITTED, TwinStore

    sid = f"SYN-w3world-20261001-{persona['name']}"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="twin_divine_"))
    rec: dict[str, Any] = {"name": persona["name"], "synthetic": True,
                           "card": persona["card"], "card_text": persona["text"],
                           "endpoint": endpoint, "model_requested": model,
                           "prompt_sha256": __import__("hashlib").sha256(
                               twinagent.SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
                           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        db, events = tmp / "twinstore.sqlite3", tmp / "lifecycle.jsonl"
        st = TwinStore(db)
        payload, secs = st.vault.seal_card(sid, persona["card"], persona["text"],
                                           ts=int(time.time() * 1000))
        twinvault.append_sealed(st, KIND_SUBMITTED, sid, payload, secs,
                                source="divination_samples:synthetic", what="card")
        st.close()
        t0 = time.time()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = twinlink.main(["--db", str(db), "generate", "--endpoint", endpoint,
                                "--model", model, "--engine", "agent", "--parallel", "1",
                                "--agent-timeout", str(timeout), "--events", str(events),
                                "--enclose", "off"])
        rec["generate_rc"], rec["wall_s"] = rc, round(time.time() - t0, 1)
        st = TwinStore(db)
        tw = (st.current(sid) or {}).get("twin") or {}
        rec["twin"] = {k: tw.get(k) for k in (
            "engine", "degrade_kind", "decision", "reason", "run_id", "verdict_hash",
            "accepted", "stop_reason", "requests_seen", "agent_rc", "agent_timed_out",
            "latency_ms", "tier", "twin_id")}
        ws, rd = twinagent.paths_for(twinagent.default_work_root(db), sid)
        plan = ws / "PLAN.md"
        rec["plan_md"] = plan.read_text(encoding="utf-8", errors="replace") if plan.is_file() else None
        files = []
        for p in sorted(ws.rglob("*")):
            if p.is_file() and p.name not in ("TRAITS.md", "PLAN.md", "WORLD.md"):
                t = p.read_text(encoding="utf-8", errors="replace")
                files.append({"name": p.relative_to(ws).as_posix(),
                              "chars": len(t), "text": t})
        rec["artifacts_full"] = files
        wmd = ws / "WORLD.md"
        world = twinagent.WORLD_PATH.read_text(encoding="utf-8")
        rec["world_in_workspace"] = wmd.is_file()
        rec["world_sha256_expected"] = twinagent.world_sha256()
        rec["world_sha256_in_ws"] = (__import__("hashlib").sha256(wmd.read_bytes()).hexdigest()
                                     if wmd.is_file() else None)
        rec["world_files_changed_by_twin"] = bool(
            wmd.is_file() and wmd.read_bytes() != twinagent.WORLD_PATH.read_bytes())
        # 回合數／工具呼叫數：agent_stdout.log 的 turn_start；步驟紀錄長度
        out_log = rd / twinagent.AGENT_STDOUT_NAME
        turns = 0
        if out_log.is_file():
            for ln in out_log.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    if json.loads(ln).get("type") == "turn_start":
                        turns += 1
                except Exception:                                  # noqa: BLE001
                    pass
        rec["turns"] = turns
        texts = [(rec["plan_md"] or "")] + [f["text"] for f in files]
        rec["copy_from_world_ge12"] = longest_shared(world, "\n".join(texts))
        rec["says"] = [s.get("text") if isinstance(s, dict) else s
                       for s in twinagent.read_says(rd, [persona["text"]])]
        rec["steps"] = twinagent.read_step_log(rd)
        w = twinlink.withdraw(st, sid, reason="divination_samples:cleanup")
        rec["withdrawn"] = bool(w.get("ok"))
        st.close()
    except Exception as exc:                                  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="占卜指令真跑樣本（合成特質）")
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", default="gemma-4-12b-it-qat")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--only", default=None)
    a = ap.parse_args(argv)
    names = set(a.only.split(",")) if a.only else None
    out = pathlib.Path(a.out)
    recs: list[dict[str, Any]] = []
    if out.exists():
        recs = json.loads(out.read_text(encoding="utf-8")).get("runs", [])
    for p in PERSONAS:
        if names and p["name"] not in names:
            continue
        rec = run_one(p, a.endpoint, a.model, a.timeout)
        recs = [r for r in recs if r.get("name") != p["name"]] + [rec]
        out.write_text(json.dumps({"note": "W3：世界＋複雜需求指令；合成特質；分身真跑（無審查閘門）",
                                   "runs": recs}, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(json.dumps({"name": p["name"], "engine": (rec.get("twin") or {}).get("engine"),
                          "decision": (rec.get("twin") or {}).get("decision"),
                          "wall_s": rec.get("wall_s"), "error": rec.get("error")},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
