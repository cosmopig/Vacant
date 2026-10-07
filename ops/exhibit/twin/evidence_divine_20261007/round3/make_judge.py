#!/usr/bin/env python3
"""P13 第三輪：代理評審（Haiku 子 agent）的題目產生器與計分器。**評審是代理，不是真人**。

用法：
    python3 make_judge.py build --a <out_a> --v <out_v> --old ../round2_final12 --out-dir <rater檔目錄> --key <key.json> [--raters 4]
    python3 make_judge.py calib --old ../round2_final12 --out-dir <dir> --key <key.json>      # 量具自證：只有控制卡＋2 張第二輪的卡
    python3 make_judge.py score --raw-dir <rater輸出目錄> --key <key.json> --out judge_scores.json

設計：
* 每位評審拿到同一批題目（順序、左右各自隨機），題目不標哪張是新版、哪張是第二輪。
  題目 = 12 組「同一位觀眾：兩張卡左右隨機」（v1..v12：新版 vs 第二輪）＋12 張單卡（a1..a12，新版）＋ 4 張控制卡。
* 控制卡（量具自證）：c_bad_route（路線句＋抽象詞＋殘句）、c_bad_generic（空泛、殘句）、c_mismatch（寫得好但是別人的卡）、c_good（手寫的好卡）。
  合格標準（寫死）：兩張爛卡在三題上平均都比好卡低至少 1.5 分；mismatch 在「像不像這個人」比好卡低至少 1.5 分。
* 每題三問 1–5 分：Q1 像不像這個人／Q2 讀了會不會想進去試／Q3 第 3 行看得出它真的做了什麼（沒有第 3 行＝1）。附一句理由。
* 評審看得到的資訊只有「這位觀眾的 AI 判決原文」與卡；看不到版本、不看到鍵。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO))

INTRO = """你是一位剛走進展覽的觀眾，不是專家。這個展覽有個遊戲：你把自己的 AI 對你的「占卜判決」貼進去，一個數位分身會替你走進一個黏土世界，試一件你心裡想試的事，最後印出一張「命盤卡」給你。

下面有很多個項目。每個項目有「這位觀眾的 AI 判決原文」，和他拿到的命盤卡（有的項目是左右兩張卡，有的只有一張）。請你站在那位觀眾的位置看卡，對**每一張卡**回答三個問題，各打 1–5 分（整數；1＝很差，3＝普通，5＝非常好）：

Q1 像不像這個人：卡上的外形、氣質、願望，和判決原文對得起來嗎？讀起來像不像是在說他、讓他覺得「啊，這就是我」？
Q2 讀了會不會想進去試：看完這張卡，你會不會想：「我進去這個世界也想試這個」？
Q3 第 3 行看得出它真的做了什麼：卡的第 3 行讓你看得到一個具體的動作與世界裡的改變嗎？（卡上沒有第 3 行就給 1）

評分錨點（請照這個尺打，不要憑感覺都打高分）：
Q1：1＝完全是別人的卡／和原文矛盾；2＝只有命盤代號對得上，其他空泛；3＝大致對得上但沒有「就是他」的感覺；4＝外形、氣質、願望都對得上；5＝連原文沒直說的細節都像他、會讓他說「這就是我」。
Q2：1＝無聊、不想看；2＝看得懂但沒興趣；3＝有點好奇；4＝想進去看看；5＝讀完立刻想自己進去試那件事。空泛、抽象、堆砌文藝詞的卡最多 2 分。
Q3：1＝沒有第 3 行，或只是一個標題／名詞；2＝只說去了哪些地方、走了什麼路線，或只有成品的名字；3＝有具體動作，但看不出世界因此有什麼不同；4＝有具體動作，也大致看得出留下了什麼；5＝清楚的「對某樣東西做了什麼」＋世界裡看得見的改變。
每個分數後面各附一句理由（20 字內）。誠實打分，不要全給中間分；不好的就給低分，好的才給高分。有左右兩張卡的項目，最後再回答 prefer：left、right 或 tie（你更想進去試的那一張）。

輸出規則：只輸出一個 JSON 陣列，不要加說明文字、不要加程式碼框。每個元素：
{"item":"項目編號","cards":{"left":{"q1":整數,"q2":整數,"q3":整數,"why":["Q1理由","Q2理由","Q3理由"]},"right":{...}},"prefer":"left|right|tie"}
只有一張卡的項目，cards 裡只放 "single" 這一個鍵，不要 prefer。把輸出寫進指定的檔案，並在回覆裡也貼出同一份 JSON。
"""

#: 控制卡用的假觀眾（合成）。
C_VIEWERS = {
    "c_bad_route": "形狀：圓潤／質感：絨面／色系：灰藍／氣質：安靜、固執、愛收集／MBTI：INFJ／星座：巨蟹／血型：O／"
                   "他心裡一直想試、卻還沒試的事：把一直沒湊齊的一整套東西湊齊／他來到新世界會說的第一句話：還差一個。",
    "c_bad_generic": "形狀：小巧／質感：光滑／色系：奶油／氣質：活潑、愛笑、坐不住／MBTI：ESFP／星座：獅子／血型：A／"
                     "他心裡一直想試、卻還沒試的事：在很多人面前唱一首完整的歌／他來到新世界會說的第一句話：大家好！",
    "c_mismatch": "形狀：修長／質感：斑駁／色系：赭紅／氣質：暴躁、嘴硬、講義氣／MBTI：ESTP／星座：牡羊／血型：B／"
                  "他心裡一直想試、卻還沒試的事：對一個一直讓著的人把話吼出來／他來到新世界會說的第一句話：廢話少說。",
    "c_good": "形狀：厚實／質感：絨面／色系：苔綠／氣質：慢熱、嘴硬、藏零食／MBTI：ISFJ／星座：金牛／血型：A／"
              "他心裡一直想試、卻還沒試的事：坐下來吃一頓慢慢吃、沒有人催的飯／他來到新世界會說的第一句話：我不餓，真的。",
}
C_CARDS = {
    "c_bad_route": ("你的數位分身其實是：INFJ · 巨蟹（水）· O 型\n它心裡一直想試的是：渴望共振與靜默的虛無\n"
                    "它試了：先去了投遞口，再到長桌廣場，再到石頭閘門，在石頭閘門做出《紙條》\n試完它說：感覺很"),
    "c_bad_generic": ("你的數位分身其實是：ESFP · 獅子（火）· A 型\n它心裡一直想試的是：把一件事做好\n"
                      "它試了：在紙卡地做出《成品》\n試完它說：還不錯"),
    "c_mismatch": ("你的數位分身其實是：厚實絨面的苔綠色居民，慢熱、嘴硬（ISFJ · 金牛 · A）\n"
                   "它心裡想：讓桌六那鍋還溫著的穀子飯，有人坐下吃完\n"
                   "它試了：搬了張矮石凳到砂鍋邊，吃到鍋底，鍋緣的霧散了\n試完它說：原來沒有人催的時候，連湯都是甜的"),
    "c_good": ("你的數位分身其實是：厚實絨面的苔綠色居民，慢熱、嘴硬（ISFJ · 金牛 · A）\n"
               "它心裡想：讓桌六那鍋還溫著的穀子飯，有人坐下吃完\n"
               "它試了：搬了張矮石凳到砂鍋邊，吃到鍋底，鍋緣的霧散了\n試完它說：原來沒有人催的時候，連湯都是甜的"),
}


def _load(d: pathlib.Path, prefix: str) -> dict[str, dict]:
    import re
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(d.glob(f"{prefix}[0-9]*.json"), key=lambda p: int(re.sub(r"\D", "", p.stem)))}


def _viewer_v(name: str) -> str:
    from ops.exhibit.twin import divine_samples as ds
    d = next(x for x in ds.DIVINERS if x["name"] == name)
    return ds._text_of(d["card"]).split("\n", 1)[1].strip().replace("\n", "／")


def _card_text(r: dict) -> str:
    return ((r.get("card_md_final") or r.get("card_md")) or "").strip()


def build_items(a: pathlib.Path, v: pathlib.Path, old: pathlib.Path) -> list[dict]:
    ra, rv, ro = _load(a, "a"), _load(v, "v"), _load(old, "v")
    inp = {x["name"]: x for x in json.loads((HERE / "inputs12_parsed.json").read_text(encoding="utf-8"))}
    items = []
    for n, r in rv.items():
        items.append({"id": f"pair_{n}", "kind": "pair", "viewer": _viewer_v(n),
                      "new": _card_text(r), "old": _card_text(ro[n]), "src": n})
    for n, r in ra.items():
        items.append({"id": f"single_{n}", "kind": "single", "viewer": inp[n]["text"].strip(), "card": _card_text(r), "src": n})
    for c in ("c_bad_route", "c_bad_generic", "c_mismatch", "c_good"):
        items.append({"id": c, "kind": "control", "viewer": C_VIEWERS[c], "card": C_CARDS[c], "src": c})
    return items


def render(items: list[dict], seed: int) -> tuple[str, dict]:
    rnd = random.Random(seed)
    order = items[:]
    rnd.shuffle(order)
    key: dict = {}
    parts = [INTRO, "\n=====題目開始=====\n"]
    for i, it in enumerate(order, 1):
        label = f"項目{i:02d}"
        parts.append(f"【{label}】\n這位觀眾的 AI 判決原文：\n{it['viewer']}\n")
        if it["kind"] == "pair":
            new_left = rnd.random() < 0.5
            l, rr = (it["new"], it["old"]) if new_left else (it["old"], it["new"])
            parts.append(f"左邊的卡：\n{l}\n\n右邊的卡：\n{rr}\n")
            key[label] = {"id": it["id"], "kind": "pair", "left": "new" if new_left else "old", "right": "old" if new_left else "new"}
        else:
            parts.append(f"他拿到的卡：\n{it['card']}\n")
            key[label] = {"id": it["id"], "kind": it["kind"]}
        parts.append("")
    parts.append("=====題目結束=====\n請現在輸出 JSON 陣列（每個項目一個元素，item 欄位寫「項目01」這種編號）。")
    return "\n".join(parts), key


def cmd_build(a: argparse.Namespace) -> int:
    items = build_items(pathlib.Path(a.a), pathlib.Path(a.v), pathlib.Path(a.old))
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    keys = {}
    for k in range(1, a.raters + 1):
        txt, key = render(items, seed=1000 + k)
        (out / f"rater{k}.txt").write_text(txt, encoding="utf-8")
        keys[f"rater{k}"] = key
    pathlib.Path(a.key).write_text(json.dumps(keys, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", a.raters, "rater files;", len(items), "items each")
    return 0


def cmd_calib(a: argparse.Namespace) -> int:
    old = _load(pathlib.Path(a.old), "v")
    items = [{"id": f"old_{n}", "kind": "single", "viewer": _viewer_v(n), "card": _card_text(old[n]), "src": n} for n in ("v2", "v5")]
    for c in ("c_bad_route", "c_bad_generic", "c_mismatch", "c_good"):
        items.append({"id": c, "kind": "control", "viewer": C_VIEWERS[c], "card": C_CARDS[c], "src": c})
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    txt, key = render(items, seed=77)
    (out / "calib.txt").write_text(txt, encoding="utf-8")
    pathlib.Path(a.key).write_text(json.dumps({"calib": key}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


def _parse(raw: str) -> list[dict]:
    """先照 JSON 讀；Haiku 常把 prefer 寫進 cards 裡、少一個右括號 ⇒ JSON 壞掉時改用正則逐項撈（只撈寫在紙上的數字，不補值）。"""
    import re
    s = raw.strip()
    i, j = s.find("["), s.rfind("]")
    try:
        return json.loads(s[i:j + 1])
    except ValueError:
        pass
    out = []
    chunks = re.split(r'(?=\{\s*"item"\s*:)', s)
    for ch in chunks:
        m = re.match(r'\{\s*"item"\s*:\s*"([^"]+)"', ch)
        if not m:
            continue
        cards = {}
        for side, q1, q2, q3 in re.findall(r'"(left|right|single)"\s*:\s*\{\s*"q1"\s*:\s*(\d)\s*,\s*"q2"\s*:\s*(\d)\s*,\s*"q3"\s*:\s*(\d)', ch):
            cards[side] = {"q1": int(q1), "q2": int(q2), "q3": int(q3)}
        pf = re.search(r'"prefer"\s*:\s*"(left|right|tie)"', ch)
        el = {"item": m.group(1), "cards": cards}
        if pf:
            el["prefer"] = pf.group(1)
        out.append(el)
    return out


def avg(xs: list[float]) -> float | None:
    return round(statistics.mean(xs), 2) if xs else None


def cmd_score(a: argparse.Namespace) -> int:
    key = json.loads(pathlib.Path(a.key).read_text(encoding="utf-8"))
    rawdir = pathlib.Path(a.raw_dir)
    per_rater: dict[str, list[dict]] = {}
    for rk in key:
        p = rawdir / f"{rk}.json"
        if p.is_file():
            per_rater[rk] = _parse(p.read_text(encoding="utf-8"))
    rows = []     # (rater, id, which, q1,q2,q3)
    prefs = []
    for rk, arr in per_rater.items():
        for el in arr:
            k = key[rk].get(el.get("item"))
            if not k:
                continue
            cards = el.get("cards") or {}
            if k["kind"] == "pair":
                for side in ("left", "right"):
                    c = cards.get(side) or {}
                    rows.append({"rater": rk, "id": k["id"], "which": k[side], **{q: c.get(q) for q in ("q1", "q2", "q3")}})
                pf = el.get("prefer")
                prefs.append({"rater": rk, "id": k["id"], "prefer": (k[pf] if pf in ("left", "right") else "tie")})
            else:
                c = cards.get("single") or next(iter(cards.values()), {})
                rows.append({"rater": rk, "id": k["id"], "which": k["kind"], **{q: c.get(q) for q in ("q1", "q2", "q3")}})
    def pick(pred, q):
        return [r[q] for r in rows if pred(r) and isinstance(r.get(q), (int, float))]
    summary = {}
    for label, pred in (("pair_new", lambda r: r["id"].startswith("pair_") and r["which"] == "new"),
                        ("pair_old(第二輪)", lambda r: r["id"].startswith("pair_") and r["which"] == "old"),
                        ("single_a_new", lambda r: r["id"].startswith("single_")),
                        ("c_bad_route", lambda r: r["id"] == "c_bad_route"), ("c_bad_generic", lambda r: r["id"] == "c_bad_generic"),
                        ("c_mismatch", lambda r: r["id"] == "c_mismatch"), ("c_good", lambda r: r["id"] == "c_good")):
        summary[label] = {q: avg(pick(pred, q)) for q in ("q1", "q2", "q3")} | {"n": len(pick(pred, "q1"))}
    good = summary["c_good"]
    proof = {
        "bad_route_lower_by>=1.5_all": all(summary["c_bad_route"][q] is not None and good[q] is not None and good[q] - summary["c_bad_route"][q] >= 1.5 for q in ("q1", "q2", "q3")),
        "bad_generic_lower_by>=1.5_all": all(summary["c_bad_generic"][q] is not None and good[q] is not None and good[q] - summary["c_bad_generic"][q] >= 1.5 for q in ("q1", "q2", "q3")),
        "mismatch_q1_lower_by>=1.5": (summary["c_mismatch"]["q1"] is not None and good["q1"] is not None and good["q1"] - summary["c_mismatch"]["q1"] >= 1.5),
    }
    pc = {"new": sum(1 for p in prefs if p["prefer"] == "new"), "old": sum(1 for p in prefs if p["prefer"] == "old"),
          "tie": sum(1 for p in prefs if p["prefer"] == "tie"), "n": len(prefs)}
    per_pair = {}
    for r in rows:
        if r["id"].startswith("pair_"):
            per_pair.setdefault(r["id"], {}).setdefault(r["which"], []).append([r["q1"], r["q2"], r["q3"]])
    out = {"raters": sorted(per_rater), "summary": summary, "instrument_self_proof": proof, "prefer_counts": pc,
           "prefers": prefs, "rows": rows}
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("raters", "summary", "instrument_self_proof", "prefer_counts")}, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--a", required=True); b.add_argument("--v", required=True); b.add_argument("--old", required=True)
    b.add_argument("--out-dir", required=True); b.add_argument("--key", required=True); b.add_argument("--raters", type=int, default=4)
    b.set_defaults(fn=cmd_build)
    c = sub.add_parser("calib")
    c.add_argument("--old", required=True); c.add_argument("--out-dir", required=True); c.add_argument("--key", required=True)
    c.set_defaults(fn=cmd_calib)
    s = sub.add_parser("score")
    s.add_argument("--raw-dir", required=True); s.add_argument("--key", required=True); s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
