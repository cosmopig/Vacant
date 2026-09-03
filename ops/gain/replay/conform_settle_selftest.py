"""conform_settle.py 的植入缺陷自檢：乾淨要 OK，五種缺陷要 BROKEN。"""
import json, pathlib, subprocess, sys, copy

ROOT = pathlib.Path("/home/user1/vacant/Vacant")
TOOL = ROOT / "ops/gain/replay/conform_settle.py"
BASE = pathlib.Path("/dev/shm/r667/fix")

def mkrows(n=20):
    rows = []
    for i in range(n):
        t = f"t{i}"
        # OFF/OFF5：accepted 恆 True。CONFORM：後 4 題拒交，其中 2 題的離線碼其實是對的
        rows.append({"arm": "OFF", "task_id": t, "accepted": True,
                     "meets_demand": i % 3 != 0, "calls_used": 1})
        rows.append({"arm": "OFF5", "task_id": t, "accepted": True,
                     "meets_demand": i % 4 != 0, "calls_used": 5})
        refused = i >= n - 4
        rows.append({"arm": "CONFORM", "task_id": t, "accepted": not refused,
                     "meets_demand": (i % 5 != 0) if not refused else (i % 2 == 0),
                     "calls_used": 2, "receipt_head": "ab" * 32})
    return rows

def write(d, rows):
    d.mkdir(parents=True, exist_ok=True)
    (d / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "notes.jsonl").write_text("")
    arms = {}
    for a in ("OFF", "CONFORM", "OFF5"):
        rs = [r for r in rows if r["arm"] == a]
        acc = [r for r in rs if r["accepted"]]
        arms[a] = {"terminal": True,
                   "calls_per_task": sum(r["calls_used"] for r in rs) / len(rs) if rs else None,
                   "leaked": sum(1 for r in acc if not r["meets_demand"])}
    (d / "summary.json").write_text(json.dumps({"n": 20, "arms": arms}))

def run(d):
    p = subprocess.run([sys.executable, str(TOOL), "--run", str(d)],
                       capture_output=True, text=True, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr

clean = mkrows()
write(BASE / "clean", clean)
rc, out = run(BASE / "clean")
print(f"CLEAN            rc={rc}  {'OK' if rc == 0 else 'FAIL(應該要 OK)'}")
clean_out = out
ok_all = rc == 0

MUT = {}
m = copy.deepcopy(clean); del m[2]["accepted"]; MUT["M1 抽掉一列 accepted"] = m
m = copy.deepcopy(clean); MUT["M2 CONFORM 零列"] = [r for r in m if r["arm"] != "CONFORM"]
m = copy.deepcopy(clean); m.append(copy.deepcopy(m[2])); MUT["M3 CONFORM task_id 重複"] = m
m = copy.deepcopy(clean); m[2]["meets_demand"] = "False"; MUT["M4 meets_demand 是字串"] = m
m = copy.deepcopy(clean); m[2]["calls_used"] = 99; MUT["M5 summary 與逐列對不起來"] = m

for name, rows in MUT.items():
    d = BASE / name.split()[0]
    write(d, clean)                      # summary/notes 一律照乾淨資料寫
    (d / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    rc, out = run(d)
    good = rc == 2 and out.startswith("BROKEN")
    ok_all &= good
    print(f"{name:28s} rc={rc}  {'BROKEN OK' if good else 'FAIL(沒抓到)'}  {out.splitlines()[0][:100]}")

# M6：同樣的不一致，但 terminal=False ⇒ 不准 BROKEN，要照實報 skew
d = BASE / "M6"; write(d, clean)
s6 = json.loads((d / "summary.json").read_text())
s6["arms"]["CONFORM"]["calls_per_task"] = 99.0
for a in s6["arms"]: s6["arms"][a]["terminal"] = False
(d / "summary.json").write_text(json.dumps(s6))
rc, out = run(d)
good6 = rc == 0 and "live_snapshot_skew" in out and "calls_per_task summary=99.0" in out
ok_all &= good6
print(f"{'M6 未收官的 skew 要照實報':28s} rc={rc}  {'OK' if good6 else 'FAIL'}")

print("\n=== 乾淨輸出 ===\n" + clean_out)
print("SELFTEST:", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)
