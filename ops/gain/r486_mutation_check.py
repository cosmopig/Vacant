#!/usr/bin/env python3
"""R486 量具的植入缺陷測試。

規則（歷輪教訓）：
- 判準不是 `rc != 0`，是「**哪一條具名檢查**變紅」——每個突變體都要有看得見它的夾具。
- crash 收場不算偵測到（T-5）。
- 雙向校準：`M0_NOOP` 是不改變任何行為的對照，**必須 caught=N**；
  只有正對照時「什麼都判成抓到」也會全綠。
"""
import os, re, subprocess, sys

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "r486_longreq_attrib.py")

MUTANTS = [
    ("M0_NOOP",                    False, "不改任何行為的負對照"),
    ("M1_TS_ALWAYS_START",         True,  "跳過 ts 語意解析、硬用 start"),
    ("M2_OVERLAP_INCLUDES_SELF",   True,  "重疊把自己也算進去 ⇒ 人人 1.0"),
    ("M3_OVERLAP_THRESHOLD_ZERO",  True,  "重疊門檻 0.50→0.0（單調：只會更容易判 QUEUE_LIVE）"),
    ("M4_DROP_FOREIGN_BASERATE",   True,  "拿掉基準率 ⇒ 空綠燈不再被標成 FORCED_GREEN"),
    ("M5_RELOAD_IGNORE_UNLOADED",  True,  "只算 loaded、漏掉 unloaded"),
    ("M6_TARGET_THRESHOLD_LOW",    True,  "長請求門檻 600s→0 ⇒ 母體被稀釋"),
    ("M7_REF_BAND_USE_MEAN_OF_ALL",True,  "參考帶納入長請求本身 ⇒ 循環論證"),
    ("M8_UNSCANNED_TO_VERDICT",    True,  "樣本不足仍下判決（把 UNSCANNED 吞掉）"),
    ("M9_EVENTS_WINDOW_GUARD_OFF", True,  "事件窗口沒蓋到也敢判 RELOAD_RULED_OUT"),
]


def run(mut):
    env = dict(os.environ)
    env["R486_MUTANT"] = mut
    p = subprocess.run([sys.executable, TOOL, "--selftest"], env=env,
                       capture_output=True, text=True)
    crash = "Traceback" in p.stderr
    m = re.search(r"FAILED=\[(.*)\]", p.stdout)
    failed = [x.strip().strip("'") for x in m.group(1).split(",")] if m else []
    return p.returncode, crash, failed


def main():
    base_rc, base_crash, base_failed = run("")
    ok = (base_rc == 0 and not base_crash and not base_failed)
    print(f"baseline: rc={base_rc} crash={int(base_crash)} failed={base_failed} -> "
          f"{'CLEAN' if ok else 'BASELINE_BROKEN'}")
    if not ok:
        sys.exit(2)
    bad = []
    for mut, should_catch, desc in MUTANTS:
        rc, crash, failed = run(mut)
        caught = bool(failed) and not crash
        verdict = "OK" if caught == should_catch else ("MISSED" if should_catch else "FALSE_ALARM")
        if crash:
            verdict = "BROKEN_CRASH"     # T-5：crash 收場不算偵測到
        if verdict != "OK":
            bad.append(mut)
        print(f"{mut:30s} expect_catch={'Y' if should_catch else 'N'} caught="
              f"{'Y' if caught else 'N'} crash={int(crash)} {verdict:12s} by={failed[:4]}")
    print(f"\n{len(MUTANTS) - len(bad)}/{len(MUTANTS)} mutants behaved as prereg'd"
          + (f"  PROBLEM={bad}" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
