"""twin/divine_samples — P13 通靈版的真跑樣本（2026-10-07，舊 VM，不是展場）。

這支在架構裡承重什麼：計畫 `PLAN_P13_DIVINE_20261007.md` 第五節——8 組**彼此很不同的「他心裡一直想試、卻還沒試的事」**
（想唱歌、想種東西、想逃跑、想被聽見、想蓋個小房子、想修好某個壞掉的東西、想找人說話、想什麼都不做），
每組真跑 1 次（真 pi＋真模型＋真 launcher 閘門，enclose=on），把每一跑的：信全文、PLAN、試的紀錄、成品、命盤卡四行、
四格窗每一個 ✗ 的原文與出處、每跑秒數、工具呼叫數、重開次數、有沒有任何一跑因為「時限」失敗，原樣收起來。

用法（VM 上）：
    PYTHONPATH=<repo> python3 ops/exhibit/twin/divine_samples.py run --out-dir <dir> \\
        --endpoint http://100.119.113.56:5500/v1 --enclose on
    python3 ops/exhibit/twin/divine_samples.py report --out-dir <dir>

⚠ 合成人格（不是真人）；每跑跑完就撤回（抹除暫存）。同一個 sub_id 重跑不保證同一個結果；8 筆不是統計。
⚠ 「這是占卜遊戲」：這裡量的是「看了會不會想：我進去也想試這個」與「命盤卡每一句有沒有根據」，不是占卜準不準。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: 8 組合成人格。形狀／質感／色系／氣質／MBTI／星座／血型／想試的事／第一句話 就是新提示詞要觀眾貼回來的欄位
#: （「想試」用抽象說法、不寫具體人事物）。八個「想試」彼此很不同；MBTI 涵蓋 E/I S/N T/F J/P 兩邊。
DIVINERS: tuple[dict[str, Any], ...] = (
    {"name": "v1", "want_kind": "唱歌",
     "card": {"shape": "圓潤", "texture": "絨面", "color": "奶油", "vibe": "害羞、溫柔、愛哼歌",
              "want": "想把一直憋在喉嚨裡、從來沒有出過聲的東西，唱出來", "first_line": "那個……我可以小聲一點嗎？",
              "mbti": "ISFP", "zodiac": "天秤", "blood": "O"}},
    {"name": "v2", "want_kind": "種東西",
     "card": {"shape": "厚實", "texture": "指紋", "color": "苔綠", "vibe": "耐心、固執、手很穩",
              "want": "想親手讓一個很小的東西，從什麼都沒有開始，慢慢長大", "first_line": "慢慢來，不急。",
              "mbti": "ISTJ", "zodiac": "金牛", "blood": "A"}},
    {"name": "v3", "want_kind": "逃跑",
     "card": {"shape": "修長", "texture": "光滑", "color": "灰藍", "vibe": "不安分、機靈、愛繞路",
              "want": "想不告訴任何人，一個人走到很遠、沒有人認得自己的地方", "first_line": "我只是路過。",
              "mbti": "ENTP", "zodiac": "射手", "blood": "B"}},
    {"name": "v4", "want_kind": "想被聽見",
     "card": {"shape": "小巧", "texture": "斑駁", "color": "赭紅", "vibe": "急切、敏感、話很多",
              "want": "想讓自己的聲音，被某個真的在聽的人接住", "first_line": "你有在聽嗎？我是說真的在聽。",
              "mbti": "ENFP", "zodiac": "雙子", "blood": "AB"}},
    {"name": "v5", "want_kind": "蓋個小房子",
     "card": {"shape": "方正", "texture": "光滑", "color": "沙金", "vibe": "務實、害怕被打擾、愛整理",
              "want": "想為自己搭一個誰也拿不走的、剛好容得下自己的小角落", "first_line": "先量一量。",
              "mbti": "INTJ", "zodiac": "摩羯", "blood": "A"}},
    {"name": "v6", "want_kind": "修好壞掉的東西",
     "card": {"shape": "粗獷", "texture": "斑駁", "color": "暖土", "vibe": "念舊、沉默、手巧",
              "want": "想把一樣壞掉很久、一直捨不得丟的東西修好", "first_line": "給我一點時間。",
              "mbti": "ISFJ", "zodiac": "處女", "blood": "O"}},
    {"name": "v7", "want_kind": "找人說話",
     "card": {"shape": "圓潤", "texture": "指紋", "color": "沙金", "vibe": "孤單、溫暖、很會傾聽別人",
              "want": "想找到一個願意聽完整件事、不急著給答案的人", "first_line": "你今天好嗎？真的好嗎？",
              "mbti": "INFJ", "zodiac": "巨蟹", "blood": "B"}},
    {"name": "v8", "want_kind": "什麼都不做",
     "card": {"shape": "厚實", "texture": "絨面", "color": "灰藍", "vibe": "疲倦、倔強、其實很想休息",
              "want": "想什麼都不做，只是待著，而且不覺得愧疚", "first_line": "讓我坐一下就好。",
              "mbti": "ESTP", "zodiac": "獅子", "blood": "AB"}},
    {"name": "v9", "want_kind": "想吃一頓很慢的飯",
     "card": {"shape": "圓潤", "texture": "指紋", "color": "暖土", "vibe": "老是趕、嘴上說不餓、其實很饞",
              "want": "想坐下來吃一頓很慢很慢、沒有人催的飯", "first_line": "我吃很快的，真的。",
              "mbti": "ESFJ", "zodiac": "牡羊", "blood": "A"}},
    {"name": "v10", "want_kind": "把舊東西還給某個人",
     "card": {"shape": "方正", "texture": "斑駁", "color": "灰藍", "vibe": "欠著事、記性太好、不太會道歉",
              "want": "想把一件留了太久的舊東西，親手還給它原來的主人", "first_line": "這個……是你的吧。",
              "mbti": "ISTP", "zodiac": "天蠍", "blood": "O"}},
    {"name": "v11", "want_kind": "想大聲罵人但不會",
     "card": {"shape": "粗獷", "texture": "光滑", "color": "赭紅", "vibe": "老好人、笑著吞下去、肚子裡有火",
              "want": "想對一個一直欺負自己的人大聲吼出來，哪怕只有一次", "first_line": "沒關係啦，我沒事。",
              "mbti": "ENFJ", "zodiac": "水瓶", "blood": "B"}},
    {"name": "v12", "want_kind": "畫一張沒人看過的圖",
     "card": {"shape": "修長", "texture": "絨面", "color": "苔綠", "vibe": "愛塗鴉、藏得很深、怕被評價",
              "want": "想畫一張完全只為自己畫、永遠不給任何人看的圖", "first_line": "我隨便畫畫的。",
              "mbti": "INTP", "zodiac": "雙魚", "blood": "AB"}},
)


R3_INPUTS = HERE.parent / "evidence_divine_20261007" / "round3" / "inputs12_parsed.json"


def _load_r3() -> tuple[dict[str, Any], ...]:
    """第三輪：12 份「像真 AI 回答」（原文＋雲端 parseCard 解析後的 card；見 evidence_divine_20261007/round3/parse_inputs.mjs）。"""
    rows = json.loads(R3_INPUTS.read_text(encoding="utf-8"))
    return tuple({"name": r["name"], "want_kind": (r["card"].get("want") or "")[:14], "card": r["card"], "text": r["text"],
                  "voice": r["voice"]} for r in rows)


def _active(set_name: str | None = None) -> tuple[dict[str, Any], ...]:
    return _load_r3() if (set_name or _SET[0]) == "r3" else DIVINERS


_SET: list[str] = ["r2"]


def _text_of(card: dict[str, Any]) -> str:
    """觀眾貼回來的原文（新提示詞的固定格式；合成）。"""
    return ("（合成的特質，不是真人）\n"
            f"形狀：{card['shape']}\n質感：{card['texture']}\n色系：{card['color']}\n氣質：{card['vibe']}\n"
            f"MBTI：{card['mbti']}\n星座：{card['zodiac']}\n血型：{card['blood']}\n"
            f"他心裡一直想試、卻還沒試的事：{card['want']}\n他來到新世界會說的第一句話：{card['first_line']}\n")


def _spec_list(seed: str) -> list[dict[str, Any]]:
    return [{"name": d["name"], "persona": "dv_" + d["name"], "sub_id": f"p13-{seed}-{d['name']}",
             "note": d["want_kind"]} for d in _active()]


def _install_personas() -> None:
    from ops.exhibit.twin import w3b_samples
    extra = [{"name": "dv_" + d["name"], "card": {**d["card"], "mbti_source": "ai"}, "text": d.get("text") or _text_of(d["card"])}
             for d in _active()]
    w3b_samples.PERSONAS = tuple(w3b_samples.PERSONAS) + tuple(extra)


def _collect(rd: pathlib.Path, ws: pathlib.Path, rec: dict[str, Any]) -> None:
    """撤回之前多收：信全文、PLAN、試的紀錄、成品、命盤卡四行、卡死／步數／時限的紀錄。"""
    from ops.exhibit.twin import fortune as fz
    from ops.exhibit.twin import grounding_gate as gg
    p = rd / "letter_final.md"
    rec["letter_full"] = p.read_text(encoding="utf-8") if p.is_file() else ""
    last = (rec.get("attempts") or [{}])[-1]
    rec["plan_full"] = last.get("plan")
    arts = {a["name"]: a["text"] for a in last.get("artifacts", [])}
    rec["record_full"] = arts.get(fz.RECORD_FILE)
    rec["made_things"] = {k: v for k, v in arts.items() if k != fz.RECORD_FILE}
    card = {}
    cp = rd / fz.CARD_JSON_NAME
    if cp.is_file():
        card = json.loads(cp.read_text(encoding="utf-8"))
    rec["card"] = card
    rec["card_md"] = fz.card_md(card) if card.get("first_line") else ""
    rec["fortune_final"] = fz.load_final(rd)
    rec["want_given"] = next(d["card"]["want"] for d in _active() if d["name"] == rec["name"].replace("dv_", ""))
    lo = rd / "list_order.json"
    rec["variation"] = json.loads(lo.read_text(encoding="utf-8")) if lo.is_file() else None
    lk = rd / "look_in.json"
    rec["look"] = json.loads(lk.read_text(encoding="utf-8")) if lk.is_file() else None
    rec["stall_restarts"] = gg.stall_restarts(rd)
    sp = rd / gg.STEP_CAP_NAME
    rec["step_cap"] = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else {"attempts": 0, "hit": 0}
    rows = fz.read_steps(rd)
    rec["steps_total"] = len(rows)
    rec["steps_per_attempt_cap"] = gg.STEP_CAP
    rec["time_limit_failure"] = bool(rec.get("cut_attempts")) or any(
        a.get("timed_out") for a in rec.get("attempts", []))
    gj = rd / "letter_guard.json"
    rec["letter_guard"] = json.loads(gj.read_text(encoding="utf-8")) if gj.is_file() else None


def cmd_run(a: argparse.Namespace) -> int:
    _SET[0] = a.set
    from ops.exhibit.twin import gate_samples
    _install_personas()
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for s in _spec_list(a.seed):
        if a.only and s["name"] not in a.only.split(","):
            continue
        f = out / f"{s['name']}.json"
        if f.exists() and not a.redo:
            continue
        rec = gate_samples.run_one(s, a.endpoint, a.model, a.timeout, out, a.enclose, None, collect=_collect)
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"name": s["name"], "want": s["note"], "wall_s": rec.get("wall_s"),
                          "accepted": rec.get("accepted"), "attempts": rec.get("attempts_used"),
                          "steps": rec.get("steps_total"), "stalls": rec.get("stall_restarts"),
                          "gates": [("".join("✓" if w["ok"] else "✗" for w in x["windows"]))
                                    for x in rec.get("attempts", [])],
                          "card_lines": len((rec.get("card") or {}).get("lines") or []),
                          "error": rec.get("error")}, ensure_ascii=False), flush=True)
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    out = pathlib.Path(a.out_dir)
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(list(out.glob("v[0-9]*.json")) + list(out.glob("a[0-9]*.json")))]
    walls = [r["wall_s"] for r in runs if isinstance(r.get("wall_s"), (int, float))]
    agent = [x["agent_wall_s"] for r in runs for x in r.get("attempts", [])
             if isinstance(x.get("agent_wall_s"), (int, float))]
    summ = {"runs": len(runs), "errors": [r["name"] for r in runs if r.get("error")],
            "wall_s": {"median": statistics.median(walls) if walls else None, "max": max(walls) if walls else None,
                       "all": walls},
            "per_attempt_pi_s": {"median": statistics.median(agent) if agent else None,
                                 "max": max(agent) if agent else None},
            "steps_total": [r.get("steps_total") for r in runs],
            "stall_restarts": [r.get("stall_restarts") for r in runs],
            "step_cap_hits": [(r.get("step_cap") or {}).get("hit") for r in runs],
            "time_limit_failures": [r["name"] for r in runs if r.get("time_limit_failure")],
            "accepted": [r.get("accepted") for r in runs],
            "attempts_used": [r.get("attempts_used") for r in runs],
            "card_lines": [len((r.get("card") or {}).get("lines") or []) for r in runs],
            "erased_left": [r.get("erased_left") for r in runs]}
    (out / "SUMMARY.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P13 通靈版真跑樣本（舊 VM）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out-dir", required=True)
    r.add_argument("--endpoint", default="http://100.119.113.56:5500/v1")
    r.add_argument("--model", default="gemma-4-12b-it-qat")
    r.add_argument("--timeout", type=float, default=3600.0, help="最後保險，不是時限")
    r.add_argument("--seed", default="a")
    r.add_argument("--only", default=None)
    r.add_argument("--redo", action="store_true")
    r.add_argument("--set", default="r2", choices=["r2", "r3"], help="r2＝第二輪的 12 組合成人格；r3＝12 份像真 AI 回答")
    r.add_argument("--enclose", default="on", choices=["off", "auto", "on"])
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
