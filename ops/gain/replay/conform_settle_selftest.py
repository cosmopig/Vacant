"""conform_settle.py 的植入缺陷自檢：乾淨要 OK，缺陷要 BROKEN。

round669 起 summary 樁改成**與真 run 同形**（gain_run.py:1260-1280 無條件寫出
`calls/processed/infra_void/accepted/accepted_and_meets_demand/leaked`）——
舊樁只有三個欄位，於是「calls 對不對」這條在樁上根本沒被驗到。
同時補 M7-M10：缺欄位、健康的 void（**不准**誤報）、超過上界的竄改、列不見了。"""
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
    (d / "summary.json").write_text(json.dumps({"n": 20, "arms": mkarms(rows)}))

def mkarms(rows, void=None):
    """照 gain_run.py:1256-1280 的算式造 summary（void: {arm: (n_void, 額外calls)}）。"""
    void = void or {}
    arms = {}
    for a in ("OFF", "CONFORM", "OFF5"):
        rs = [r for r in rows if r["arm"] == a]
        acc = [r for r in rs if r["accepted"]]
        ok = [r for r in acc if r["meets_demand"]]
        n_void, extra = void.get(a, (0, 0))
        calls = sum(r["calls_used"] for r in rs) + extra
        measured = len(rs)
        arms[a] = {"terminal": True, "tasks": 20,
                   "calls": calls, "infra_void": n_void,
                   "processed": measured + n_void,
                   "accepted": len(acc), "accepted_and_meets_demand": len(ok),
                   "leaked": len(acc) - len(ok),
                   "calls_per_task": calls / measured if measured else None}
    return arms

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
s6["arms"]["CONFORM"]["calls"] += 99
for a in s6["arms"]: s6["arms"][a]["terminal"] = False
(d / "summary.json").write_text(json.dumps(s6))
rc, out = run(d)
good6 = rc == 0 and "live_snapshot_skew" in out and "CONFORM.calls" in out
ok_all &= good6
print(f"{'M6 未收官的 skew 要照實報':28s} rc={rc}  {'OK' if good6 else 'FAIL'}")

# ── round669 新增 ────────────────────────────────────────────────
def variant(name, rows, arms_mut):
    d = BASE / name.split()[0]
    write(d, rows)
    s_ = json.loads((d / "summary.json").read_text())
    arms_mut(s_["arms"])
    (d / "summary.json").write_text(json.dumps(s_))
    return run(d)

# M7：summary 少一個欄位 ⇒ 安靜量不到，必須 BROKEN
rc, out = variant("M7", clean, lambda A: A["CONFORM"].pop("calls"))
g = rc == 2 and out.startswith("BROKEN")
ok_all &= g
print(f"{'M7 summary 缺 calls 欄位':28s} rc={rc}  {'BROKEN OK' if g else 'FAIL(沒抓到)'}  {out.splitlines()[0][:90]}")

# M8（反向）：健康的 run 但有一個吃掉呼叫的 void ⇒ **不准**誤報
#   碼上的樣子：該格不寫列、processed 照加、n_void+1、calls[0] 不回捲。
m8 = [r for r in clean if not (r["arm"] == "CONFORM" and r["task_id"] == "t3")]
victim = next(r for r in clean if r["arm"] == "CONFORM" and r["task_id"] == "t3")
d = BASE / "M8"; write(d, m8)
s8 = {"n": 20, "arms": mkarms(m8, void={"CONFORM": (1, victim["calls_used"])})}
(d / "summary.json").write_text(json.dumps(s8))
rc, out = run(d)
g8 = rc == 0 and "bounded(n_void=1" in out
ok_all &= g8
print(f"{'M8 健康的 void 不准誤報':28s} rc={rc}  {'OK(不誤報)' if g8 else 'FAIL(誤報了)'}")

# M9：同樣有 void，但 calls 灌到超過 n_void×單格上限 ⇒ 牙齒必須還在
d = BASE / "M9"; write(d, m8)
s9 = {"n": 20, "arms": mkarms(m8, void={"CONFORM": (1, victim["calls_used"] + 50)})}
(d / "summary.json").write_text(json.dumps(s9))
rc, out = run(d)
g9 = rc == 2 and "超過" in out
ok_all &= g9
print(f"{'M9 void 掩護下灌大 calls':28s} rc={rc}  {'BROKEN OK' if g9 else 'FAIL(牙齒掉了)'}  {out.splitlines()[0][:90]}")

# M10：列不見了、summary 一個字都不動 ⇒ processed 不變性要抓到
d = BASE / "M10"; write(d, clean)
(d / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in m8))
rc, out = run(d)
g10 = rc == 2 and out.startswith("BROKEN")
ok_all &= g10
print(f"{'M10 列不見了、summary 不動':28s} rc={rc}  {'BROKEN OK' if g10 else 'FAIL(沒抓到)'}  {out.splitlines()[0][:90]}")

print("\n=== 乾淨輸出 ===\n" + clean_out)
print("SELFTEST:", "PASS" if ok_all else "FAIL")
sys.exit(0 if ok_all else 1)
