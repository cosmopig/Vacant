"""twin/fortune_samples — P10 命盤的真跑樣本（2026-10-02，舊 VM，不是展場）。

這支在架構裡承重什麼：計畫 P10 線 F §F2-7——8 組合成人格（E/I、S/N、T/F、J/P 各兩邊、四種元素、四種血型；
其中 2 組不給 MBTI 讓分身猜、2 組不給星座與血型），每組真跑 1 次（真 pi＋真模型＋真 launcher 閘門），
把每一跑的：信的命盤段全文、命盤卡全文與被拿掉的句子、去過的地點順序、「先逛還是先寫計畫」、
閘門結果序列、秒數，原樣收起來，供「劇本多樣性」與「這就是我」兩個判讀。

用法（VM 上）：
    PYTHONPATH=<repo> python3 ops/exhibit/twin/fortune_samples.py run --out-dir <dir> \\
        --endpoint http://100.119.113.56:5500/v1 --timeout 300
    python3 ops/exhibit/twin/fortune_samples.py report --out-dir <dir>

⚠ 合成人格（不是真人）；每跑跑完就撤回（抹除暫存）。同一個 sub_id 重跑不保證同一個結果；8 筆不是統計。
⚠ 「這是占卜遊戲」：這裡量的是「劇本有沒有因命盤而不同」與「命盤卡的每一句有沒有步驟根據」，不是命盤準不準。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: 8 組合成人格：特質沿用 W3b 的 6 組（d1–d6）加兩組新的，命盤另給。
#: 覆蓋：E（f1 f3 f7）I（f2 f4 f8）／S（f1 f4 f8）N（f2 f3 f7）／T（f1 f4 f7）F（f2 f3 f8）／J（f1 f4 f8）P（f2 f3 f7）；
#: 元素 火 f1／水 f2／風 f3 f6／土 f4 f5；血型 A f1 f6／B f3 f5／O f2／AB f4；
#: 不給 MBTI：f5 f6（分身要猜）；不給星座血型：f7 f8。
FORTUNES: tuple[dict[str, Any], ...] = (
    {"name": "f1", "persona": "d1", "fortune": {"mbti": "ESTJ", "mbti_source": "ai", "zodiac": "牡羊", "blood": "A"}},
    {"name": "f2", "persona": "d2", "fortune": {"mbti": "INFP", "mbti_source": "self", "zodiac": "雙魚", "blood": "O"}},
    {"name": "f3", "persona": "d3", "fortune": {"mbti": "ENFP", "mbti_source": "ai", "zodiac": "雙子", "blood": "B"}},
    {"name": "f4", "persona": "d4", "fortune": {"mbti": "ISTJ", "mbti_source": "ai", "zodiac": "處女", "blood": "AB"}},
    {"name": "f5", "persona": "d5", "fortune": {"mbti": None, "mbti_source": None, "zodiac": "摩羯", "blood": "B"}},
    {"name": "f6", "persona": "d6", "fortune": {"mbti": None, "mbti_source": None, "zodiac": "水瓶", "blood": "A"}},
    {"name": "f7", "persona": "d3", "fortune": {"mbti": "ENTP", "mbti_source": "self", "zodiac": None, "blood": None}},
    {"name": "f8", "persona": "d4", "fortune": {"mbti": "ISFJ", "mbti_source": "ai", "zodiac": None, "blood": None}},
)


def _spec_list(seed: str) -> list[dict[str, Any]]:
    out = []
    for f in FORTUNES:
        out.append({"name": f["name"], "persona": "fz_" + f["name"], "sub_id": f"p10-{seed}-{f['name']}",
                    "note": json.dumps(f["fortune"], ensure_ascii=False)})
    return out


def _install_personas() -> None:
    """把 8 組人格塞進 `w3b_samples.PERSONAS`（`gate_samples.run_one` 從那裡找 persona）。"""
    from ops.exhibit.twin import w3b_samples
    base = {p["name"]: p for p in w3b_samples.PERSONAS}
    extra = []
    for f in FORTUNES:
        p = base[f["persona"]]
        extra.append({"name": "fz_" + f["name"], "card": {**p["card"], **f["fortune"]}, "text": p["text"]})
    w3b_samples.PERSONAS = tuple(w3b_samples.PERSONAS) + tuple(extra)


def _collect(rd: pathlib.Path, ws: pathlib.Path, rec: dict[str, Any]) -> None:
    """撤回之前多收：信的命盤段、命盤卡（含被拿掉的句子）、地點順序、先逛還是先寫計畫、閘門結果序列。"""
    from ops.exhibit.twin import fortune as fz
    letter = (rd / "letter_final.md")
    txt = letter.read_text(encoding="utf-8") if letter.is_file() else ""
    body, sec = fz.parse_letter(txt)
    rec["letter_full"] = txt
    rec["letter_fortune_section"] = txt[txt.index("命盤"):] if "命盤" in txt else ""
    rec["fortune_final"] = fz.load_final(rd)
    card = {}
    cp = rd / fz.CARD_JSON_NAME
    if cp.is_file():
        card = json.loads(cp.read_text(encoding="utf-8"))
    rec["card"] = card
    rec["card_md_final"] = fz.card_md(card) if card.get("first_line") else ""
    raw = ""
    # 凍結快照裡分身寫的原始命盤卡（被拿掉之前）
    fr = None
    runj = rd / "run_RUN-ON.json"
    if runj.is_file():
        atts = json.loads(runj.read_text(encoding="utf-8")).get("attempts", [])
        fr = atts[-1].get("frozen_path") if atts else None
    if fr and (pathlib.Path(fr) / fz.CARD_FILE).is_file():
        raw = (pathlib.Path(fr) / fz.CARD_FILE).read_text(encoding="utf-8")
    rec["card_md_raw_by_twin"] = raw
    rows = fz.read_steps(rd)
    ev = fz.Evidence(rows, pathlib.Path(fr) if fr else None)
    rec["place_order"] = fz.visited_places(rows)
    rec["plan_first"] = ev.a_plan_first()
    rec["browse_first"] = ev.a_browse_first()
    rec["plan_writes"] = len(ev.plan_writes)
    rec["way_text"] = fz.way_text(rec["fortune_final"] or {}) if rec["fortune_final"] else ""
    seq = []
    for a in rec.get("attempts", []):
        seq.append("".join(("✓" if w["ok"] else "✗") if w["ok"] is not None else "?" for w in a["windows"]))
    rec["gate_sequence"] = seq
    # 命盤的做事方式有沒有真的發生（字面的步驟證據；與命盤卡檢查同一套判準）
    rec["flags"] = {"plan_first": ev.a_plan_first(), "browse_first": ev.a_browse_first(),
                    "recheck": ev.a_recheck(), "changed_mind": ev.a_changed_mind(),
                    "two_versions": ev.a_two_versions(), "left_for": ev.a_left_for(), "kept": ev.a_kept(),
                    "n_artifacts": len(ev.files), "artifact_names": sorted(ev.files)}
    gj = rd / "letter_guard.json"
    rec["letter_guard"] = json.loads(gj.read_text(encoding="utf-8")) if gj.is_file() else None


def cmd_run(a: argparse.Namespace) -> int:
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
        rec["fortune_given"] = next(x["fortune"] for x in FORTUNES if x["name"] == s["name"])
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"name": s["name"], "wall_s": rec.get("wall_s"), "accepted": rec.get("accepted"),
                          "attempts": rec.get("attempts_used"), "places": rec.get("place_order"),
                          "gates": rec.get("gate_sequence"), "card_lines": len((rec.get("card") or {}).get("lines") or []),
                          "error": rec.get("error")}, ensure_ascii=False), flush=True)
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    out = pathlib.Path(a.out_dir)
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("f[0-9]*.json"))]
    orders = [tuple(r.get("place_order") or []) for r in runs]
    gates = [tuple(r.get("gate_sequence") or []) for r in runs]
    walls = sorted(r["wall_s"] for r in runs if isinstance(r.get("wall_s"), (int, float)))
    summ = {"runs": len(runs), "errors": [r["name"] for r in runs if r.get("error")],
            "distinct_place_orders": len(set(orders)), "distinct_gate_sequences": len(set(gates)),
            "distinct_first_places": len({o[0] for o in orders if o}),
            "first_fail_then_pass_n": sum(1 for g in gates if len(g) == 2 and g[0] != "✓✓✓✓" and g[1] == "✓✓✓✓"),
            "wall_median_s": walls[len(walls) // 2] if walls else None, "wall_max_s": walls[-1] if walls else None,
            "per_run": [{"name": r["name"], "given": r.get("fortune_given"),
                         "final": {k: (r.get("fortune_final") or {}).get(k) for k in ("mbti", "mbti_source", "zodiac", "blood")},
                         "places": r.get("place_order"), "plan_first": r.get("plan_first"),
                         "browse_first": r.get("browse_first"), "gates": r.get("gate_sequence"),
                         "accepted": r.get("accepted"), "wall_s": r.get("wall_s"),
                         "card_kept": len((r.get("card") or {}).get("lines") or []),
                         "card_dropped": len((r.get("card") or {}).get("dropped") or [])} for r in runs]}
    (out / "SUMMARY.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P10 命盤真跑樣本（舊 VM）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out-dir", required=True)
    r.add_argument("--endpoint", default="http://100.119.113.56:5500/v1")
    r.add_argument("--model", default="gemma-4-12b-it-qat")
    r.add_argument("--timeout", type=float, default=300.0)
    r.add_argument("--seed", default="a")
    r.add_argument("--only", default=None)
    r.add_argument("--redo", action="store_true")
    r.add_argument("--enclose", default="off", choices=["off", "auto", "on"])
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
