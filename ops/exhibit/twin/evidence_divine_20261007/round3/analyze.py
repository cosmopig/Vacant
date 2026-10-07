#!/usr/bin/env python3
"""P13 第三輪：把真跑的 JSON 收成 REPORT.txt（全文）與確定性檢查表（checks.json）。

用法：
    python3 analyze.py --a <out_a> --v <out_v> --old ../round2_final12 --out REPORT.txt --checks checks.json

* `--a`：12 份「像真 AI 回答」的觀眾（a1..a12）新版跑的結果。
* `--v`：第二輪那 12 位合成觀眾（v1..v12）用新版再跑的結果（同一位觀眾，才有新舊 A/B 可比）。
* `--old`：第二輪原始結果（v1..v12.json）。
只用標準函式庫。「代理評審」不在這裡（見 judge_*.py）；這裡全是確定性的字面檢查。
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))
from ops.exhibit.twin import fortune as fz  # noqa: E402

ABS = ("渴望", "靜默", "虛無", "細碎", "共振", "壓抑", "沉默", "溫潤", "圓潤")
#: 材料（相對路徑 → 它在句子裡會被怎麼稱呼的關鍵名詞）。只用來數「物件分布」與「第 2 行含世界物件名」，不進任何提示。
OBJECTS: dict[str, tuple[str, ...]] = {
    "帳本鏈/出生片_420到440.txt": ("出生片",), "帳本鏈/尾段_418到447片.txt": ("尾段", "鏈尾"),
    "帳本鏈/放大鏡的鏡片.txt": ("放大鏡", "鏡片"), "帳本鏈/鏈尾那片空白的陶片.txt": ("空白的陶片", "空白陶片"),
    "帳本鏈/鏈的彎處.txt": ("鏈的彎處", "彎處"), "投遞口/收據卡_蕨葉.txt": ("收據卡",),
    "投遞口/朝外的小口.txt": ("朝外的小口", "小口"), "投遞口/沒人認領的信.txt": ("沒人認領", "托盤"),
    "投遞口/缺角的信.txt": ("缺角的信",), "投遞口/郵筒下的細線.txt": ("郵筒下的細線", "郵筒下"),
    "捏土處/手印牆.txt": ("手印牆",), "捏土處/最後那團灰藍的土.txt": ("灰藍的土", "灰藍土"),
    "捏土處/沒捏完的小東西.txt": ("沒捏完",), "捏土處/陶杯裡的種子.txt": ("種子", "陶杯"),
    "畫架與長椅/兩道光交界的地.txt": ("兩道光", "交界"), "畫架與長椅/畫架上的去向.txt": ("貼紙", "畫架上"),
    "畫架與長椅/長椅上的紙筒.txt": ("紙筒",), "畫架與長椅/長椅下的抽屜.txt": ("抽屜",),
    "畫架與長椅/長椅底下縮著的灰藍小東西.txt": ("灰藍小東西", "小東西"),
    "石頭閘門/第七格窗.txt": ("第七格", "第 7 格"), "石頭閘門/背面的小門.txt": ("小門",),
    "石頭閘門/閘門旁的陶碗.txt": ("陶碗",), "石頭閘門/退回紙_另一張.txt": ("退回紙",),
    "石頭閘門/退回紙_第四列.txt": ("退回紙",), "紙卡地/卡面上的圓.txt": ("卡面",),
    "紙卡地/格狀圖.txt": ("格狀圖",), "紙卡地/沒有被撿起來過的那張.txt": ("沒有被撿起來",),
    "紙卡地/頭頂那根線.txt": ("頭頂那根線", "頭頂的線"), "草稿角/一個沒打開的紙團.txt": ("紙團",),
    "草稿角/擦過三次的那個字.txt": ("擦過三次", "那個字"), "草稿角/沒有點過的小燈.txt": ("小燈", "燈"),
    "草稿角/石壁上的高低線.txt": ("高低線", "石壁"), "長桌廣場/一張畫到邊緣的圖.txt": ("畫到邊緣的圖",),
    "長桌廣場/土堆上的紙船.txt": ("紙船",), "長桌廣場/土堆裡的洞.txt": ("土堆裡的洞", "洞"),
    "長桌廣場/筆筒裡的藍鉛筆.txt": ("藍鉛筆", "筆筒"), "長桌廣場/陶哨子.txt": ("陶哨子", "哨子"),
    "長桌廣場/土堆/小陶印.txt": ("小陶印", "陶罐"), "長桌廣場/桌五_音樂盒.txt": ("音樂盒",),
    "長桌廣場/桌五_壓著筆的紙.txt": ("壓著筆的紙",),
    # 第三輪新增
    "長桌廣場/桌六的砂鍋.txt": ("砂鍋", "鍋"), "投遞口/借走的細頸陶瓶.txt": ("陶瓶", "細頸"),
    "畫架與長椅/冷藍光邊的紙喇叭.txt": ("紙喇叭", "喇叭"), "畫架與長椅/板角那個炭條的圓.txt": ("炭條",),
    "長桌廣場/桌四邊的紙鞋.txt": ("紙鞋",), "石頭閘門/石墩背面的凹印.txt": ("凹印", "石墩背面"),
    "草稿角/石壁前那張半張紙.txt": ("半張紙",), "紙卡地/轉到一半的小人.txt": ("小黏土人", "轉到一半", "小人"),
    "長桌廣場/桌二的空位.txt": ("桌二", "空位", "陶碗排"), "投遞口/綁好線的小方塊.txt": ("小方塊", "黏土方塊"),
    "草稿角/信紙與那根線.txt": ("信紙",), "紙卡地/圍成一圈的碎石.txt": ("圍成一圈的碎石", "碎石"),
    "帳本鏈/彎處旁那塊黏土板.txt": ("黏土板",), "捏土處/量了三次的土團.txt": ("土團",),
    "帳本鏈/多出的小印.txt": ("多出的小印", "小印"), "石頭閘門/束在一起的陶管.txt": ("陶管",),
    "捏土處/碗口缺了三角.txt": ("粗陶碗", "缺了三角", "碗口"),
}
#: 一個像樣的「做了什麼／留下什麼改變」句子會有的動詞字（確定性字面檢查，不是語意判斷）。
VERBS = set("放變成多少填蓋掛立斷接亮響擺貼留拆摺捏種推拉裂補綁埋圍搭刻畫寫挖移擠壓抱捲揉串排插抬翻點釘縫裝敲吹拿帶遞送做建修")
ROUTE = re.compile(r"先去了|再到|做出《|中途被退回")
MOLD = ("瞳孔", "指尖", "摩擦", "摩挲", "微微收縮", "微微皺起")


def load(d: pathlib.Path, prefix: str) -> dict[str, dict]:
    out = {}
    for p in sorted(d.glob(f"{prefix}[0-9]*.json"), key=lambda p: int(re.sub(r"\D", "", p.stem))):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def card_of(r: dict) -> dict:
    """最終版組合器重算的卡（有就用，見 recompute_cards.py）；沒有就用真跑當下的。"""
    return r.get("card_final") or r.get("card") or {}


def card_lines(r: dict) -> list[str]:
    return list(card_of(r).get("lines") or [])


def objects_in(text: str) -> set[str]:
    return {rel for rel, ns in OBJECTS.items() if any(n in text for n in ns)}


def stem(rel: str) -> str:
    return pathlib.PurePath(rel).stem


def bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def jaccard(a: str, b: str) -> float:
    x, y = bigrams(a), bigrams(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def gate_x(r: dict) -> list[dict]:
    out = []
    for a in r.get("attempts", []):
        for w in a.get("windows", []):
            if not w.get("ok"):
                out.append({"attempt": a.get("attempt"), "window": w.get("id"), "label": w.get("label"),
                            "message": w.get("message")})
    return out


def block(name: str, r: dict) -> str:
    L = []
    L.append("=" * 40 + f" {name} 想試:{r.get('want_given')}")
    var = r.get("variation") or {}
    L.append(f"秒數 {r.get('wall_s')} / 步數 {r.get('steps_total')} / 閘門嘗試 {r.get('attempts_used')} / 卡死重開 "
             f"{r.get('stall_restarts')} / 時限失敗 {r.get('time_limit_failure')} / accepted {r.get('accepted')} / 撤回後殘留 "
             f"{r.get('erased_left')}")
    L.append(f"變化：醒來 {var.get('wake')} / 感官 {var.get('sense')} / 身體部位 {var.get('body')} / ws_list 地點順序 "
             f"{'>'.join(var.get('places') or [])}")
    L.append(f"外形：{r.get('look')}")
    L.append("--信\n" + (r.get("letter_full") or "(無)"))
    L.append("--PLAN\n" + (r.get("plan_full") or "(無)"))
    L.append("--試的紀錄\n" + (r.get("record_full") or "(無)"))
    for k, v in (r.get("made_things") or {}).items():
        L.append(f"--成品 {k}\n{v}")
    L.append("--命盤卡（最終版組合器重算）\n" + ((r.get("card_md_final") or r.get("card_md")) or "(無)").rstrip())
    if r.get("card_md_final") and r.get("card_md_final") != r.get("card_md"):
        L.append("--（真跑當下 VM 上組出來的卡，與上面不同）\n" + (r.get("card_md") or "(無)").rstrip())
    xs = gate_x(r)
    L.append("--閘門 ✗：" + ("無" if not xs else json.dumps(xs, ensure_ascii=False)))
    L.append("--讀過的地上檔：" + "、".join(sorted(stem(x) for x in (r.get("ground_read") or []))))
    return "\n".join(L)


def checks(runs: dict[str, dict], label: str) -> dict:
    rows = []
    l2s = []
    obj_runs: Counter = Counter()
    card_obj_runs: Counter = Counter()
    for n, r in runs.items():
        ls = card_lines(r)
        c = card_of(r)
        l2, l3 = c.get("want_line"), c.get("tried_line")
        plan = r.get("plan_full") or ""
        l2_ok = bool(l2) and l2.startswith(fz.WANT_PREFIX)
        l2_obj = sorted(stem(x) for x in objects_in(l2 or ""))
        body3 = (l3 or "")[len(fz.TRIED_PREFIX):]
        l3_ok = bool(l3) and not ROUTE.search(l3) and any(ch in VERBS for ch in body3) and len(body3) <= fz.MAX_TRIED_CARD
        plan_first = next((x for x in plan.splitlines() if x.strip()), "")
        plan_wish_label = bool(re.match(r"^[\s#>*\-_]*\**我想\**\s*[：:]", plan_first))
        po = objects_in(plan)
        for x in po:
            obj_runs[x] += 1
        for x in objects_in((l2 or "") + (l3 or "")):
            card_obj_runs[x] += 1
        ls_ok = len(ls) <= 4 and all(0 < len(x) <= 60 for x in ls)
        tv = c.get("tv_lines") or []
        tv_ok = len(tv) <= 3 and all(0 < len(x) <= 60 for x in tv)
        xs = gate_x(r)
        rows.append({"name": n, "plan_wish_label": plan_wish_label, "l1_ok": bool(ls) and ls[0].startswith(fz.VERDICT_PREFIX)
                     and "居民" in ls[0] and "（" in ls[0], "l2": l2, "l2_starts_with_prefix": l2_ok, "l2_world_object": l2_obj,
                     "l3": l3, "l3_verb_not_route": l3_ok, "cloud_lines_ok": ls_ok, "tv_lines_ok": tv_ok,
                     "n_lines": len(ls), "gate_x_n": len(xs), "gate_runs_accepted_first": r.get("attempts_used") == 1,
                     "time_limit_failure": bool(r.get("time_limit_failure")), "stall_restarts": r.get("stall_restarts"),
                     "wall_s": r.get("wall_s"), "steps": r.get("steps_total"), "plan_objects": sorted(stem(x) for x in po),
                     "wake": (r.get("variation") or {}).get("wake")})
        l2s.append((n, l2 or ""))
    pair = [(a, b, jaccard(x, y)) for (a, x), (b, y) in itertools.combinations(l2s, 2) if x and y]
    dup = [(a, b) for (a, x), (b, y) in itertools.combinations(l2s, 2) if x and x == y]
    present = [x for _, x in l2s if x]
    top_plan = obj_runs.most_common(6)
    top_card = card_obj_runs.most_common(6)
    return {"label": label, "runs": rows,
            "l2_present": len(present), "l2_pairwise_distinct": not dup, "l2_dups": dup,
            "l2_max_bigram_jaccard": max((j for *_, j in pair), default=0.0),
            "object_runs_plan_top": [(stem(k), v) for k, v in top_plan], "object_runs_plan_max": max(obj_runs.values(), default=0),
            "object_runs_card_top": [(stem(k), v) for k, v in top_card], "object_runs_card_max": max(card_obj_runs.values(), default=0),
            "distinct_plan_objects": len(obj_runs),
            "wake_distinct": len({r["wake"] for r in rows if r["wake"]}),
            "all_ok": {"l2": sum(r["l2_starts_with_prefix"] for r in rows), "l3": sum(r["l3_verb_not_route"] for r in rows),
                       "plan_label": sum(r["plan_wish_label"] for r in rows), "cloud": sum(r["cloud_lines_ok"] for r in rows),
                       "tv": sum(r["tv_lines_ok"] for r in rows), "l1": sum(r["l1_ok"] for r in rows),
                       "gate_x_runs": sum(1 for r in rows if r["gate_x_n"]),
                       "time_limit": sum(r["time_limit_failure"] for r in rows)}}


def letter_stats(runs: dict[str, dict]) -> dict:
    txt = "\n".join((r.get("letter_full") or "") for r in runs.values())
    per = {n: {w: (r.get("letter_full") or "").count(w) for w in MOLD} for n, r in runs.items()}
    runs_with_mold = {w: sum(1 for p in per.values() if p[w]) for w in MOLD}
    allt = "\n".join("\n".join([r.get("letter_full") or "", r.get("plan_full") or "", r.get("record_full") or ""]
                               + list((r.get("made_things") or {}).values())) for r in runs.values())
    abs_ = {w: allt.count(w) for w in ABS}
    follow = {}
    for n, r in runs.items():
        v = r.get("variation") or {}
        lt = r.get("letter_full") or ""
        body = lt.split("命盤")[0]
        follow[n] = {"body_part_in_letter": bool(v.get("body")) and v["body"] in body,
                     "sense_word_in_letter": bool(v.get("sense")) and any(w in body for w in SENSE_WORDS.get(v.get("sense"), ())),
                     "mold_words": sum(per[n].values())}
    return {"runs_with_mold_word": runs_with_mold, "abstract_total": sum(abs_.values()), "abstract_words": abs_,
            "follow": follow, "n_runs": len(runs)}


SENSE_WORDS = {"聲音": ("聲", "響", "音", "吵", "靜"), "氣味": ("味", "香", "臭", "氣息"), "溫度": ("熱", "冷", "涼", "暖", "溫"),
               "重量": ("重", "沉", "輕", "壓"), "觸感": ("摸", "觸", "粗", "滑", "軟", "硬", "紋")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--v", required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--checks", required=True)
    a = ap.parse_args()
    ra, rv = load(pathlib.Path(a.a), "a"), load(pathlib.Path(a.v), "v")
    ro = load(pathlib.Path(a.old), "v")
    ck = {"a_set_new": checks(ra, "a1..a12 新版"), "v_set_new": checks(rv, "v1..v12 新版"), "v_set_round2": checks(ro, "v1..v12 第二輪"),
          "letters": {"a_set_new": letter_stats(ra), "v_set_new": letter_stats(rv), "v_set_round2": letter_stats(ro)}}
    pathlib.Path(a.checks).write_text(json.dumps(ck, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    parts = ["P13 第三輪真跑全文（舊 VM，enclose=on，gemma-4-12b-it-qat；合成人格，不是真人）\n",
             "## A. 12 份像真 AI 回答的觀眾（a1..a12，新版）\n"]
    parts += [block(n, r) for n, r in ra.items()]
    parts.append("\n## B. 第二輪那 12 位合成觀眾（v1..v12，用新版再跑；第二輪的原卡見 round2_final12/REPORT12.txt）\n")
    parts += [block(n, r) for n, r in rv.items()]
    pathlib.Path(a.out).write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print("ok", len(ra), len(rv), len(ro))
    return 0


if __name__ == "__main__":
    sys.exit(main())
