import json, pathlib, collections
H = pathlib.Path(__file__).resolve().parent
key = {k["id"]: k for k in json.loads((H / "key.json").read_text(encoding="utf-8"))}
votes = collections.defaultdict(dict)
for k in (1, 2, 3):
    for ln in (H / f"rater{k}.txt").read_text(encoding="utf-8").splitlines():
        p = ln.split("\t")
        if len(p) >= 2 and p[0] in key:
            votes[p[0]][k] = (p[1].strip(), p[2].strip() if len(p) > 2 else "")
out = []
def tally(kind):
    ids = [i for i, v in key.items() if v["kind"] == kind]
    no = {i: sum(1 for r in votes[i].values() if r[0].startswith("否")) for i in ids}
    return ids, no
for kind, name in (("neg", "負控制（已知殘句）"), ("pos", "正控制（完整句）"), ("card", "新卡第2–4行")):
    ids, no = tally(kind)
    n_votes = sum(len(votes[i]) for i in ids)
    n_no = sum(no.values())
    maj_no = sum(1 for i in ids if no[i] >= 2)
    any_no = sum(1 for i in ids if no[i] >= 1)
    out.append(f"{name}: {len(ids)} 行 × 3 評審 = {n_votes} 票；判『否』{n_no} 票；多數（≥2/3）判否 {maj_no} 行；至少 1 人判否 {any_no} 行")
    if kind in ("neg", "card"):
        for i in ids:
            if kind == "card" and no[i] == 0:
                continue
            out.append(f"   {i} {no[i]}/3 否  {key[i]['text']}  | " + " / ".join(f"R{k}:{votes[i][k][1]}" for k in votes[i] if votes[i][k][0].startswith("否")))
missing = [i for i in key if len(votes[i]) < 3]
out.append(f"缺票的行：{missing}")
(H / "JUDGE_RESULT.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
