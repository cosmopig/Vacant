#!/usr/bin/env python3
"""整合（2026-10-12）：用 divine 的真跑紀錄（round3 的 24 跑＋round4/live 的 6 跑，共 30 張）離線重算 mirror 的「像不像你？」習慣句。
走的是**真的 `fortune.build_card`**：把旁註 `twin_step` 還原成 `twin_steps.ndjson`（路徑由位元組數對回 attempts 的成品／試的紀錄／信），
工作區放最後的成品＋PLAN.md＋試的紀錄.md＋信.md，再呼叫 build_card——所以「系統檔不算做出來的東西」那條也在被測。
⚠ 誠實：旁註不帶檔名，只能由位元組數還原；對不上的寫入當成品（保守＝可能多算成品寫入）。觀眾原文已撤回，traits 用 round3 存的人設重建。
用法：python3 recompute_r6.py [--before-fix]   輸出 cards_r6.json / habits_r6.txt
"""
from __future__ import annotations
import collections, json, pathlib, sys, tempfile
HERE = pathlib.Path(__file__).resolve().parent
EV = HERE.parent
R3 = EV / "round3"; R4 = EV / "round4"
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(R3))
from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import twinagent  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402
import recompute_cards as rc  # noqa: E402

INV = {code: place for place, code in sc.GROUND_PLACES.items()}


def b(t: str) -> int:
    return len((t or "").encode("utf-8"))


def steps_of(r: dict, side: pathlib.Path) -> tuple[list[dict], int]:
    letter_b = b(r.get("letter_full"))
    by_attempt = []
    for a in r.get("attempts") or []:
        by_attempt.append({b(x["text"]): x["name"] for x in a.get("artifacts") or []})
    glob = {}
    for m in by_attempt:
        glob.update(m)
    glob[b(r.get("record_full"))] = fz.RECORD_FILE
    rows, ai, last_seq, unmapped = [], 0, 0, 0
    raw = sorted((x for x in sc.read(side) if x.get("type") == "twin_step"), key=lambda x: (x["ts_ms"], x["seq"]))
    for x in raw:
        if x["seq"] <= last_seq:
            ai += 1                                    # seq 回到 1 ＝ 下一次嘗試
        last_seq = x["seq"]
        kind, step = x.get("path_kind"), x["step"]
        tool = {"read": "ws_read", "write": "ws_write", "list": "ws_list"}[step]
        if kind and kind.startswith("ground:"):
            path = f"地上/{INV[kind.split(':', 1)[1]]}/x"
        elif kind == "plan":
            path = fz.PLAN_FILE
        elif kind == "traits":
            path = "TRAITS.md"
        elif kind == "artifact":
            m = by_attempt[ai] if ai < len(by_attempt) else {}
            if step == "read" and x.get("bytes") == letter_b:
                path = fz.LETTER_FILE
            elif x.get("bytes") in m:
                path = m[x["bytes"]]
            elif x.get("bytes") in glob:
                path = glob[x["bytes"]]
            else:
                path, unmapped = "成品.md", unmapped + 1
        elif kind == "other" and step == "read":
            path = fz.LETTER_FILE if x.get("bytes") == letter_b else "WORLD.md"
        else:
            path = "."
        rows.append({"ts_ms": x["ts_ms"], "seq": x["seq"], "tool": tool, "path": path, "ok": x.get("ok")})
    return rows, unmapped


def main() -> int:
    srcs = []
    for which, d in (("a", R3 / "out_a"), ("v", R3 / "out_v")):
        for p in sorted(d.glob(f"{which}[0-9]*.json"), key=lambda x: int(x.stem[1:])):
            srcs.append((f"r3_{p.stem}", which, p))
    for p in sorted((R4 / "live").glob("a[0-9]*.json"), key=lambda x: int(x.stem[1:])):
        if ".lifecycle" not in p.name:
            srcs.append((f"r4live_{p.stem}", "a", p))
    out, cnt, per_sentence = [], collections.Counter(), collections.Counter()
    for rid, which, p in srcs:
        r = json.loads(p.read_text(encoding="utf-8"))
        side = p.with_name(p.stem + ".lifecycle.sidecar.jsonl")
        rows, unm = steps_of(r, side)
        name = r["name"].replace("dv_", "")
        pcard, ptext = rc.persona(name, which)
        traits = twinagent.render_traits(pcard, ptext)
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td); rd = td / "rd"; ws = td / "ws"; rd.mkdir(); ws.mkdir()
            (rd / fz.STEP_LOG_NAME).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
            (rd / "letter_final.md").write_text(r.get("letter_full") or "", encoding="utf-8")
            (rd / "run_RUN-ON.json").write_text(json.dumps({"attempts": [{}] * max(1, int(r.get("attempts_used") or 1))}), encoding="utf-8")
            (rd / fz.LOOK_NAME).write_text(json.dumps(r.get("look") or {}, ensure_ascii=False), encoding="utf-8")
            (ws / fz.PLAN_FILE).write_text(r.get("plan_full") or "", encoding="utf-8")
            (ws / fz.RECORD_FILE).write_text(r.get("record_full") or "", encoding="utf-8")
            (ws / fz.LETTER_FILE).write_text(r.get("letter_full") or "", encoding="utf-8")
            for n, t in (r.get("made_things") or {}).items():
                (ws / n).write_text(t, encoding="utf-8")
            card = fz.build_card(rd, ws, r.get("fortune_final") or {}, traits)
        lines = card["lines"]
        for ln in lines:
            per_sentence[ln if not ln.startswith("最後做出來的是") else "最後做出來的是《標題》"] += 1
        cnt[len(lines)] += 1
        out.append({"id": rid, "n_steps": len(rows), "unmapped_writes": unm, "attempts_used": r.get("attempts_used"),
                    "title": card.get("title"), "head": card["head"], "lines": lines,
                    "plan_writes": sum(1 for x in rows if x["tool"] == "ws_write" and x["path"] == fz.PLAN_FILE)})
    (HERE / "cards_r6.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    txt = [f"共 {len(out)} 張；句數分布 {dict(sorted(cnt.items()))}；空卡 {cnt.get(0, 0)} 張", "", "## 每種句子的出現次數"]
    txt += [f"{n:3d}  {s}" for s, n in per_sentence.most_common()]
    txt += ["", "## 逐張"]
    for x in out:
        txt += [f"{x['id']}  步{x['n_steps']} 嘗試{x['attempts_used']} PLAN寫{x['plan_writes']}次 未對回檔名的寫入{x['unmapped_writes']}  《{x['title']}》"] + [f"    {l}" for l in x["lines"]]
    (HERE / "habits_r6.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print("\n".join(txt))
    return 0


sys.exit(main())
