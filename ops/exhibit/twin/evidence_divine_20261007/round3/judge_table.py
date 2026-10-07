#!/usr/bin/env python3
"""把 judge/judge_scores.json 收成回報用的表（judge/JUDGE_TABLE.txt）。代理評審（Haiku），不是真人。"""
import json, pathlib, statistics as st, collections
H = pathlib.Path(__file__).resolve().parent / "judge"
d = json.loads((H / "judge_scores.json").read_text(encoding="utf-8"))
rows = d["rows"]
L = []
S = d["summary"]
L.append("## 量具自證（4 位評審 × 4 張控制卡；1–5 分；越低越爛）")
L.append("| 控制卡 | 像不像 | 想試 | 第3行 |")
L.append("|---|---|---|---|")
for k, lab in (("c_good", "手寫好卡"), ("c_bad_route", "爛卡一（路線句＋抽象詞＋殘句）"), ("c_bad_generic", "爛卡二（空泛、殘句）"), ("c_mismatch", "寫得好但是別人的卡")):
    L.append(f"| {lab} | {S[k]['q1']} | {S[k]['q2']} | {S[k]['q3']} |")
L.append(f"自證判準：{d['instrument_self_proof']}")
L.append("⚠ 量具的限度：第二輪的卡（有路線句）被打了 3.0–3.6 分，離好卡 5 分很遠、離爛卡 1–2 分也很遠——它分得出『爛／別人的』與『好』，分不太出『中等』之間的細差，所以下面的 A/B 看的是『偏好票』與『逐對分差』，不是絕對分。")
L.append("")
L.append("## 新版 vs 第二輪（同一批觀眾 v1..v12；每張卡 4 位評審平均；左右隨機、評審不知道哪張是新版）")
L.append("| 觀眾 | 新 像/想試/第3行 | 第二輪 像/想試/第3行 | 4 票偏好（新/舊/平） |")
L.append("|---|---|---|---|")
per = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    if r["id"].startswith("pair_"):
        per[r["id"]][r["which"]].append((r["q1"], r["q2"], r["q3"]))
pf = collections.defaultdict(list)
for p in d["prefers"]:
    pf[p["id"]].append(p["prefer"])
key = lambda x: int(x[0].split("v")[-1])
for pid, v in sorted(per.items(), key=key):
    nm = [round(st.mean(x[i] for x in v["new"]), 2) for i in range(3)]
    om = [round(st.mean(x[i] for x in v["old"]) , 2) for i in range(3)]
    c = collections.Counter(pf[pid])
    L.append(f"| {pid[5:]} | {nm[0]}/{nm[1]}/{nm[2]} | {om[0]}/{om[1]}/{om[2]} | {c['new']}/{c['old']}/{c['tie']} |")
L.append(f"| 全部（48 張卡對） | {S['pair_new']['q1']}/{S['pair_new']['q2']}/{S['pair_new']['q3']} | {S['pair_old(第二輪)']['q1']}/{S['pair_old(第二輪)']['q2']}/{S['pair_old(第二輪)']['q3']} | {d['prefer_counts']['new']}/{d['prefer_counts']['old']}/{d['prefer_counts']['tie']} |")
# 逐對符號：新版平均三題總分 > 舊版？
wins = sum(1 for v in per.values() if st.mean(sum(x) for x in v["new"]) > st.mean(sum(x) for x in v["old"]))
ties = sum(1 for v in per.values() if st.mean(sum(x) for x in v["new"]) == st.mean(sum(x) for x in v["old"]))
L.append(f"逐對（12 對，三題總分的 4 位平均）：新版較高 {wins}、較低 {12 - wins - ties}、相同 {ties}。")
L.append("")
L.append("## 12 份像真 AI 回答的觀眾（a1..a12；新版；4 位評審平均）")
L.append("| 觀眾 | 像不像 | 想試 | 第3行 |")
L.append("|---|---|---|---|")
sg = collections.defaultdict(list)
for r in rows:
    if r["id"].startswith("single_"):
        sg[r["id"]].append((r["q1"], r["q2"], r["q3"]))
for k, v in sorted(sg.items(), key=lambda x: int(x[0].split("a")[-1])):
    m = [round(st.mean(x[i] for x in v), 2) for i in range(3)]
    L.append(f"| {k[7:]} | {m[0]} | {m[1]} | {m[2]} |")
L.append(f"| 平均 | {S['single_a_new']['q1']} | {S['single_a_new']['q2']} | {S['single_a_new']['q3']} |")
(H / "JUDGE_TABLE.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
