import json, pathlib
H = pathlib.Path(__file__).resolve().parent
key = json.loads((H / "key.json").read_text(encoding="utf-8"))
items = {i["id"]: i for i in key["items"]}
out = []; tally = {"real": [0, 0], "ctl": [0, 0]}
for k in (1, 2, 3):
    flips = key["flips"][str(k)]
    for ln in (H / f"rater{k}.txt").read_text(encoding="utf-8").splitlines():
        qid, pick = ln.split("\t")[:2]
        good_is = "A" if flips[qid] == 0 else "B"      # flip=0：A＝good（第五輪新選的／控制的對的那條）
        ok = pick == good_is
        t = tally[items[qid]["kind"]]; t[0] += ok; t[1] += 1
        out.append(f"R{k} {qid} {items[qid]['kind']} {items[qid]['src']}: {'選到對的' if ok else '選到另一個'}")
for kind, name in (("ctl", "對照（對的 vs 無關的）"), ("real", "第3行有改變的卡（第五輪 vs 第四輪）")):
    out.append(f"{name}: {tally[kind][0]}/{tally[kind][1]} 票選第五輪／對的那條")
(H / "JUDGE_RESULT.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
