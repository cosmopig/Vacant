import json, collections
A="/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/analysis_formal"
cells = json.load(open(A+"/cells.json"))
rows = {(r["task"], r["arm"], r["sample"]): r for r in json.load(open("/tmp/claude-0/verify_formal/rows.json"))}
print("cells", len(cells))
ck = {(c["task"], c["arm"], c["sample"]): c for c in cells}
print("key sets equal:", set(ck)==set(rows))
mm = [(k, c["reward"], float(rows[k]["reward_txt"])) for k,c in ck.items() if float(c["reward"]) != float(rows[k]["reward_txt"])]
print("cells.json reward vs reward.txt mismatches:", mm)
print("job/trial mismatch:", [k for k,c in ck.items() if c["job"]!=rows[k]["job"] or c["trial"]!=rows[k]["trial"]])
print("upstream mismatch:", [k for k,c in ck.items() if c["upstream"]!=rows[k]["up"]])
print("infra_void true:", [k for k,c in ck.items() if c["infra_void"]])
print("answer_file None:", collections.Counter((c["arm"], c["answer_file"]) for c in cells))
# reward 1 but answer_file False?
print("reward1 & answer_file False:", [k for k,c in ck.items() if c["reward"] and c["answer_file"] is False])
# recompute per-arm-sample on 77
EX={"5","70"}
for a in ("A","C1","C2"):
    for s in (1,2,3):
        rs=[c for c in cells if c["arm"]==a and c["sample"]==s and c["task"] not in EX]
        print(a,s,len(rs),"correct",sum(1 for c in rs if c["reward"]), "noans", sum(1 for c in rs if c["answer_file"] is False), "wrong", sum(1 for c in rs if not c["reward"] and c["answer_file"] is True), "other", sum(1 for c in rs if not c["reward"] and c["answer_file"] is None))
# check the three void cells picked the rerun
for k in [("1273","A",3),("1273","C2",3),("69","C2",3)]:
    print(k, ck[k]["job"], ck[k]["trial"], ck[k]["started"], ck[k]["reward"], ck[k]["requests"])
