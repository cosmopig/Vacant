#!/usr/bin/env python3
"""R491 植入缺陷測試：每個突變體都要有「看得見它的那個量」。

規則（本迴圈已成立的通則）：
  - 突變體在**被測函式內部**生效（不是模組層讀 env）
  - 判準寫「該變的是哪個量」，**不是只寫 rc≠0**
  - crash 收場算 `BROKEN`，不算「偵測到」
  - 在乾淨輸入下看不見的突變體，**照實記成 `INVISIBLE_ON_CLEAN`**，
    並另外用一個**專門的**夾具證明那條防線本身有牙齒（不准假裝它被測到了）
"""
import importlib, json, os, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CALLS = sys.argv[1] if len(sys.argv) > 1 else "/dev/shm/r491/calls_snapshot.jsonl"


def run(mutant=""):
    os.environ.pop("R491_MUTANT", None)
    if mutant:
        os.environ["R491_MUTANT"] = mutant
    import ops.gain.r491_falsifiability_census as C
    importlib.reload(C)
    try:
        calls = C.load_calls(CALLS)
        return C.census(calls), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        os.environ.pop("R491_MUTANT", None)


clean, err = run()
assert err is None, f"clean run BROKEN: {err}"
rows = []


def check(name, mutant, quantity, expect_fn, detail_fn):
    res, e = run(mutant)
    if res is None:
        rows.append((name, "BROKEN", quantity, e)); return
    ok = expect_fn(res)
    rows.append((name, "DETECTED" if ok else "MISSED", quantity, detail_fn(res)))


check("M0_noop", "", "所有格不變",
      lambda r: r["cells"] == clean["cells"] and r["verdict"] == clean["verdict"],
      lambda r: r["verdict"])
check("M2_SINGLE_WINDOW", "M2_SINGLE_WINDOW", "n_windows 與各格 -> UNSCANNED",
      lambda r: r["n_windows"] == 1 and all(
          v["cell"] in ("UNSCANNED", "WITHHELD") for v in r["cells"].values()),
      lambda r: f"n_windows={r['n_windows']} cells={sorted({v['cell'] for v in r['cells'].values()})}")
check("M4_ALWAYS_FORCED", "M4_ALWAYS_FORCED", "負對照崩掉 -> CENSUS_BROKEN",
      lambda r: r["verdict"] == "CENSUS_BROKEN" and "CENSUS_BROKEN" in r["blockers"],
      lambda r: f"{r['verdict']} calib={r['calibration']}")
check("M5_ALWAYS_EVALUABLE", "M5_ALWAYS_EVALUABLE", "正對照崩掉 -> CENSUS_BROKEN",
      lambda r: r["verdict"] == "CENSUS_BROKEN" and "CENSUS_BROKEN" in r["blockers"],
      lambda r: f"{r['verdict']} calib={r['calibration']}")
check("M7_NO_ADVERSARIAL", "M7_NO_ADVERSARIAL", "R485_P3 由 EMPIRICAL 誤升成 IDENTITY",
      lambda r: (clean["cells"]["R485_P3"]["cell"] == "FORCED_GREEN_EMPIRICAL"
                 and r["cells"]["R485_P3"]["cell"] == "FORCED_GREEN_IDENTITY"),
      lambda r: r["cells"]["R485_P3"]["cell"])

# --- 在乾淨輸入下看不見的兩個，照實記，並各自用專門夾具證明防線有牙齒 -------
import ops.gain.r491_falsifiability_census as C          # noqa: E402
importlib.reload(C)

res, _ = run("M1_SOURCE_CHECK_TOOTHLESS")
invisible_1 = (res is not None and res["cells"] == clean["cells"])
# 專門夾具：把釘死的字面換成原始碼裡沒有的字串，乾淨版必須判 False、突變版仍 True
saved = dict(C.SOURCE_CLAIMS)
C.SOURCE_CLAIMS["bogus"] = ("ops/gain/r484_time_attribution.py", "analyse",
                            "this_literal_is_not_in_the_source_xyzzy")
clean_sees = not all(C.check_source_claims().values())
os.environ["R491_MUTANT"] = "M1_SOURCE_CHECK_TOOTHLESS"
mut_sees = not all(C.check_source_claims().values())
os.environ.pop("R491_MUTANT", None)
C.SOURCE_CLAIMS.clear(); C.SOURCE_CLAIMS.update(saved)
rows.append(("M1_SOURCE_CHECK_TOOTHLESS",
             "INVISIBLE_ON_CLEAN+GUARD_HAS_TEETH" if invisible_1 and clean_sees and not mut_sees
             else "MISSED", "source_claims（乾淨原始碼下無差異）",
             f"invisible={invisible_1} clean_detects_drift={clean_sees} mutant_blind={not mut_sees}"))

res, _ = run("M6_SCHEMA_GAUGE_TOOTHLESS")
invisible_6 = (res is not None and res["cells"] == clean["cells"])
bad = [{"ts_ms": 1, "latency_ms": 2, "attempt": 1, "role": "gen",
        "meta": {"task_id": "t1", "arm": "OFF"}}]          # agent_id 整欄缺席
clean_sees6 = "agent_id" in C.schema_gauge(bad)["missing"]
os.environ["R491_MUTANT"] = "M6_SCHEMA_GAUGE_TOOTHLESS"
mut_sees6 = "agent_id" in C.schema_gauge(bad)["missing"]
os.environ.pop("R491_MUTANT", None)
rows.append(("M6_SCHEMA_GAUGE_TOOTHLESS",
             "INVISIBLE_ON_CLEAN+GUARD_HAS_TEETH" if invisible_6 and clean_sees6 and not mut_sees6
             else "MISSED", "schema.missing（乾淨資料下本來就是空的）",
             f"invisible={invisible_6} clean_detects={clean_sees6} mutant_blind={not mut_sees6}"))

# M3 是單元層（真資料視窗數遠大於 MIN_WINDOWS ⇒ 全量跑看不見）
c3 = C.classify({"X"}, {"X"}, {"X"}, 1)
os.environ["R491_MUTANT"] = "M3_SKIP_MIN_WINDOWS"
c3m = C.classify({"X"}, {"X"}, {"X"}, 1)
os.environ.pop("R491_MUTANT", None)
rows.append(("M3_SKIP_MIN_WINDOWS",
             "DETECTED" if c3 == "UNSCANNED" and c3m != "UNSCANNED" else "MISSED",
             "classify 在 n_windows<MIN 時的回傳", f"clean={c3} mutant={c3m}"))

for n, st, q, d in rows:
    print(f"  {n:34s} {st:34s} {q}\n      {d}")
bad_rows = [r for r in rows if r[1] not in ("DETECTED", "INVISIBLE_ON_CLEAN+GUARD_HAS_TEETH")]
print(f"\n{len(rows) - len(bad_rows)}/{len(rows)} behaved as prereg'd")
sys.exit(1 if bad_rows else 0)
