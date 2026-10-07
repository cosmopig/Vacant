#!/usr/bin/env python3
"""把 checks.json 收成回報用的確定性檢查表（REPORT_CHECKS.txt）。"""
import json, pathlib, statistics
H = pathlib.Path(__file__).resolve().parent
c = json.loads((H / "checks.json").read_text(encoding="utf-8"))
#: 寬鬆版「世界裡的東西」：地名＋地上東西的通稱（比 analyze.OBJECTS 的專名寬）。報告兩個數字，不挑好看的。
BROAD = ("投遞口", "捏土處", "長桌廣場", "石頭閘門", "帳本鏈", "草稿角", "紙卡地", "畫架", "長椅", "土堆", "紙船", "音樂盒", "哨子", "種子", "小燈", "燈",
         "信", "細線", "線", "紙卡", "紙", "筆", "鉛筆", "碗", "陶", "土", "石壁", "石頭", "印紋", "鏈", "鞋", "喇叭", "小人", "碎石", "洞", "閘門", "窗",
         "門", "光", "圖", "貼紙", "抽屜", "紙筒", "鍋", "瓶", "管", "板", "印", "圈", "卡")
out = []
for k, label in (("a_set_new", "A組 a1..a12（12 份像真 AI 回答；新版）"), ("v_set_new", "B組 v1..v12（第二輪同一批觀眾；新版）"),
                 ("v_set_round2", "對照 v1..v12（第二輪原版）")):
    x = c[k]; rows = x["runs"]
    l2 = [r for r in rows if r["l2"]]
    l2_obj = sum(1 for r in l2 if r["l2_world_object"])
    out.append(f"## {label}")
    out.append(f"- PLAN 第一行以「我想：」開頭：{x['all_ok']['plan_label']}/12")
    out.append(f"- 卡第 1 行是『你的數位分身其實是：…居民…（…）』：{x['all_ok']['l1']}/12")
    l2_broad = sum(1 for r in l2 if any(w in r["l2"] for w in BROAD))
    out.append(f"- 卡第 2 行存在且以『它心裡想：』開頭：{x['all_ok']['l2']}/12；其中含世界物件名：專名 {l2_obj}/{len(l2)}、寬鬆（含地名與通稱）{l2_broad}/{len(l2)}")
    out.append(f"- 卡第 3 行含動詞且不是路線句：{x['all_ok']['l3']}/12")
    out.append(f"- 12 跑兩兩第 2 行不同：{x['l2_pairwise_distinct']}（現有 {x['l2_present']} 句；兩兩字二元組最大重疊 {x['l2_max_bigram_jaccard']:.2f}）")
    out.append(f"- 物件分布：PLAN 提到的不同物件 {x['distinct_plan_objects']} 種；同一件物件最多出現在 {x['object_runs_plan_max']} 跑（{x['object_runs_plan_top'][:3]}）；"
               f"上卡（第 2＋3 行）最多 {x['object_runs_card_max']} 跑（{x['object_runs_card_top'][:3]}）")
    out.append(f"- 雲端單行上限（≤4 行、每行 ≤60 字）：{x['all_ok']['cloud']}/12；電視 twin_fortune lines（≤3 句、每句 ≤60 字）：{x['all_ok']['tv']}/12")
    out.append(f"- 第一次嘗試就過閘門：{sum(1 for r in rows if r['gate_runs_accepted_first'])}/12；任一嘗試有 ✗ 的跑：{x['all_ok']['gate_x_runs']}/12")
    out.append(f"- 時限失敗：{x['all_ok']['time_limit']}；醒來地點種數：{x['wake_distinct']}")
    ws = [r["wall_s"] for r in rows if r["wall_s"] is not None]
    out.append(f"- 每跑秒數 中位 {statistics.median(ws):.1f} / 最慢 {max(ws):.1f}；步數 中位 {statistics.median([r['steps'] for r in rows if r['steps'] is not None])}")
    out.append("")
out.append("## 信（感官／小動作的模子）")
for k, v in c["letters"].items():
    out.append(f"- {k}：含『瞳孔／指尖／摩擦／摩挲／微微收縮／微微皺起』的信 {v['runs_with_mold_word']}；抽象詞合計 {v['abstract_total']}；"
               f"信裡有指定身體部位 {sum(1 for f in v['follow'].values() if f['body_part_in_letter'])}/12、有指定感官的字 {sum(1 for f in v['follow'].values() if f['sense_word_in_letter'])}/12")
(H / "REPORT_CHECKS.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
