#!/usr/bin/env python3
"""R468：`tests/` 全量掃描的分類器。

判準逐字照 `DECISION_20260904_R468_TESTS_SWEEP_PREREG.md` §三。
**分類靠證據不靠印象**：判 STALE 一定要貼 commit sha；貼不出來就是 REAL 或 UNCLASSIFIED。

## 兩個「安靜量不到」的坑（本輪實際踩過，記在這裡免得重犯）

1. **traceback 走 stderr、不是 stdout。** 第一版分類器只讀 stdout ⇒ 41 條失敗只看見 26 條
   （15 條 FAIL 全部安靜消失），而且**它不會報錯**，只會少數幾條。
   ⇒ 收尾一定要斷言 `len(分類到的) == fail + error`，對不上就 BROKEN。
2. **`AssertionError` 不一定是測試或產品的錯。** 替身的 `parametrize` 對
   list 值的參數綁錯（綁成 `'up'` 而不是 `["up","--help"]`）⇒ 測試裡拋 AssertionError、
   最深 frame 在測試檔，**照 §三 的字面會被判成 REAL**。這是判準沒有的一類，
   照 §三 的事前聲明記為 UNCLASSIFIED，**不當場補分類法去吸收它**。
"""
import json, re, collections, sys, pathlib

RAW = sys.argv[1] if len(sys.argv) > 1 else "/dev/shm/r468_sweep_raw.json"
OUT = pathlib.Path("ops/gain/data/r468_tests_map.json")

# ── 人工裁定（每一筆都要有證據；沒有證據不准進這張表）─────────────────
MANUAL = {
    ("tests/test_archive_index.py", "test_refuted_verdicts_carry_the_correction"): {
        "cls": "STALE",
        "evidence": "cfe882b",
        "why": "測試斷言 verdict ∈ (refuted, overstated)；commit cfe882b 標題明說"
               "『held/no_effect 兩個新裁決值』＝產品契約在測試最後一次修改（8344805）"
               "之後被有意擴充，測試沒跟上。gain.signal_exists 的 verdict 是 held。",
    },
}
# 量具偽紅：§三 沒有這一類，照事前聲明記 UNCLASSIFIED（附最小重現）
GAUGE_FALSE_RED = {
    ("tests/test_cli_eco.py", "test_help_does_not_crash"): {
        "cls": "UNCLASSIFIED",
        "why": "替身 parametrize 對 list 值參數綁錯：綁 'up' 而非 ['up','--help']，"
               "argparse 逐字元走字串 ⇒ 測試內拋 AssertionError。最小重現："
               "parametrize('argv', [['up','--help']]) ⇒ 綁到的是 'up'。"
               "照 §三 字面會判成 REAL；這是判準缺的一類，不當場補判準。",
    },
}


def classify(module, name, tb):
    base = re.sub(r"\[\d+\]$", "", name)
    for tbl in (MANUAL, GAUGE_FALSE_RED):
        if (module, base) in tbl:
            return dict(tbl[(module, base)])
    if tb.startswith("__SHIM_MISSING__"):
        return {"cls": "SHIM", "why": "替身缺 fixture " + tb.split("__SHIM_MISSING__", 1)[1].strip()}
    if "ModuleNotFoundError" in tb:
        m = re.search(r"No module named '([^']+)'", tb)
        return {"cls": "SHIM", "why": f"§三：缺第三方套件 {m.group(1) if m else '?'}"}
    if "has no attribute 'importorskip'" in tb:
        return {"cls": "SHIM", "why": "§三：替身未支援 pytest.importorskip"}
    exc = (re.findall(r"^(\w+Error|\w*Exception):", tb, re.M) or [""])[-1]
    deepest = (re.findall(r'^  File "([^"]+)", line', tb, re.M) or [""])[-1]
    in_shim = deepest.endswith("run_tests_nopytest.py")
    if exc in ("AttributeError", "TypeError", "NameError") and in_shim:
        return {"cls": "SHIM", "why": f"§三：{exc} 且最深 frame 在替身內（{exc == 'TypeError' and 'fixture 吃 fixture' or ''}）"}
    if exc == "FileNotFoundError":
        p = (re.findall(r"No such file or directory: '([^']+)'", tb) or [""])[-1]
        if "/Library/Mobile Documents/" in p or "CloudDocs" in p:
            return {"cls": "ENV", "why": f"§三 ENV：需要 Mac iCloud 路徑 {p[:60]}…（這台是 Linux）"}
        return {"cls": "ENV", "why": f"§三 ENV：缺檔 {p[:70]}"}
    if exc == "AssertionError":
        return {"cls": "UNCLASSIFIED", "why": "AssertionError 但無人工裁定的 commit 證據 ⇒ 不准自動判 STALE/REAL"}
    return {"cls": "UNCLASSIFIED", "why": f"無法辨識：{exc or '未知例外'}"}


def main():
    raw = json.load(open(RAW))
    mods, entries = [], []
    for r in raw:
        so, se, mod = r["stdout"], r["stderr"], r["module"]
        if r["timeout"]:
            mods.append({"module": mod, "verdict": "TIMEOUT", "n": 0, "pass": 0, "fail": 0, "error": 0, "skip": 0})
            entries.append({"module": mod, "test": "<module>", **{"cls": "ENV", "why": "B4：120s 逾時"}})
            continue
        mm = re.search(r"^tests/\S+: (\d+)/(\d+) pass, (\d+) fail, (\d+) error, (\d+) skip => (\S+)", so, re.M)
        if not mm:
            v = "IMPORT_ERROR" if "IMPORT_ERROR" in so else "NO_SUMMARY"
            mods.append({"module": mod, "verdict": v, "n": 0, "pass": 0, "fail": 0, "error": 0, "skip": 0})
            entries.append({"module": mod, "test": "<import>", **classify(mod, "<import>", se), "module_level": True})
            continue
        p, n, f, e, s = (int(mm[i]) for i in range(1, 6))
        v = mm[6]
        mods.append({"module": mod, "verdict": v, "n": n, "pass": p, "fail": f, "error": e, "skip": s})
        for em in re.finditer(r"^ERROR (\S+): 需要這支撐不住的 (.*)$", so, re.M):
            entries.append({"module": mod, "test": em[1], **classify(mod, em[1], "__SHIM_MISSING__" + em[2])})
        fails = re.findall(r"^FAIL  (\S+)$", so, re.M)
        tbs = re.split(r"(?=^Traceback \(most recent call last\):)", se, flags=re.M)
        tbs = [t for t in tbs if t.startswith("Traceback")]
        # 替身對每個 FAIL 依序印一段 traceback；ERROR 不印 ⇒ 兩者數量必須相等
        if len(tbs) != len(fails):
            entries.append({"module": mod, "test": "<parse>", "cls": "BROKEN",
                            "why": f"traceback 段數 {len(tbs)} != FAIL 數 {len(fails)}"})
            tbs = tbs + [""] * len(fails)
        for nm, tb in zip(fails, tbs):
            entries.append({"module": mod, "test": nm, **classify(mod, nm, tb)})

    tot_f = sum(m["fail"] for m in mods)
    tot_e = sum(m["error"] for m in mods)
    mlvl = sum(1 for x in entries if x.get("module_level"))
    # ── 坑 1 的擋門：分類到的條數必須等於 fail+error（＋module 級）──────
    covered = len(entries) - mlvl
    consistent = covered == tot_f + tot_e
    cc = collections.Counter(x["cls"] for x in entries)
    vc = collections.Counter(m["verdict"] for m in mods)
    rep = {
        "modules": len(mods), "module_verdicts": dict(vc),
        "green_modules": vc["PASS"] + vc["PASS_WITH_SKIP"],
        "collected": sum(m["n"] for m in mods), "passed": sum(m["pass"] for m in mods),
        "failed": tot_f, "errored": tot_e, "skipped": sum(m["skip"] for m in mods),
        "zero_collected_modules": sum(1 for m in mods if m["n"] == 0),
        "class_counts": dict(cc),
        "coverage_check": {"classified": covered, "expected": tot_f + tot_e, "ok": consistent},
        "per_module": mods, "entries": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rep, open(OUT, "w"), ensure_ascii=False, indent=1)
    for k in ("modules", "green_modules", "collected", "passed", "failed", "errored",
              "zero_collected_modules", "module_verdicts", "class_counts", "coverage_check"):
        print(f"{k:24s} {rep[k]}")
    if not consistent:
        print("BROKEN：分類覆蓋率對不上 fail+error"); return 1
    if cc.get("BROKEN"):
        print("BROKEN：traceback 配對失敗"); return 1
    print("\n== 非全綠模組 ==")
    for m in mods:
        if m["verdict"] in ("PASS", "PASS_WITH_SKIP"): continue
        print(f"  {m['verdict']:13s} {m['pass']:3d}/{m['n']:<3d} f={m['fail']} e={m['error']}  {m['module']}")
    print("\n== STALE / REAL / UNCLASSIFIED 逐條（SHIM/ENV 只計數）==")
    for x in entries:
        if x["cls"] in ("SHIM", "ENV"): continue
        print(f"  [{x['cls']}] {x['module']}::{x['test']}")
        print(f"        {x.get('evidence','')} {x['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
