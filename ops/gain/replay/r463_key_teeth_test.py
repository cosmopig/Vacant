#!/usr/bin/env python3
"""R463 §三：證明 `paired_ci.py --key` 有牙齒。純標準庫、零模型呼叫。

事前判準寫在 DECISION_20260904_R463_PAIRED_CI_KEY_GAP.md §三，**先 commit 才寫這支**。

為什麼不能拿 runs/g_r447_conform_lcb2 當牙齒證明（§3.1）：
實測該 run 的分歧格（accepted=False ∧ meets_demand=True）是**空的**
（120 題 CONFORM：113 accepted、7 refused，7 個全部 meets_demand=False）
⇒ 兩個 key 必然同值 ⇒ 拿它「驗證」等於「乾淨 PASS、植入缺陷仍 PASS」的假測試。
所以牙齒要靠 T1 的合成夾具，r447 只當回歸對照。

夾具**不共用被測檔的任何 helper**（§3.3；r699 的教訓：夾具由被測模組自己的 helper 造
⇒ 驗不到真資料 schema）。代價：驗得到「口徑選擇」，驗不到「欄位名對不對」，後者由 r447 對照補。
"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys, tempfile

TOOL = pathlib.Path(__file__).resolve().parent / "paired_ci.py"

# 夾具：70 題、兩臂。手寫，逐格意圖見下表。
#   A 40 格：兩臂都對                        → 兩個 key 都 concordant
#   B 10 格：只有 CONFORM 對（有交付）        → 兩個 key 都 b+=1
#   C  5 格：只有 OFF 對                     → 兩個 key 都 c+=1
#   D  5 格：CONFORM 拒交但回退碼碰巧對       → **分歧格**：meets_demand 記 b+=1；deliv 記 concordant
#   E 10 格：兩臂都錯                        → 兩個 key 都 concordant
GROUPS = [("A", 40, dict(off_md=True,  con_md=True,  con_acc=True)),
          ("B", 10, dict(off_md=False, con_md=True,  con_acc=True)),
          ("C",  5, dict(off_md=True,  con_md=False, con_acc=True)),
          ("D",  5, dict(off_md=False, con_md=True,  con_acc=False)),
          ("E", 10, dict(off_md=False, con_md=False, con_acc=True))]

EXPECT_MD    = {"b": 15, "c": 5}   # B(10) + D(5)
EXPECT_DELIV = {"b": 10, "c": 5}   # B(10) only


def build(d: pathlib.Path) -> None:
    rows, i = [], 0
    for _g, cnt, spec in GROUPS:
        for _ in range(cnt):
            tid = f"t{i:03d}"; i += 1
            rows.append({"task_id": tid, "arm": "OFF", "i": i,
                         "accepted": True, "meets_demand": spec["off_md"]})
            rows.append({"task_id": tid, "arm": "CONFORM", "i": i,
                         "accepted": spec["con_acc"], "meets_demand": spec["con_md"]})
    (d / "rows.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (d / "summary.json").write_text(json.dumps(
        {"pool": "fixture", "instrument": {"n": 12, "ref_pass": 12, "broken_rejected": 12},
         "calibration": None, "request_policy": "fixture"}), encoding="utf-8")


def run(d: pathlib.Path, key: str, mutant: str = "") -> dict:
    env = dict(os.environ)
    env.pop("MUTANT", None)
    if mutant:
        env["MUTANT"] = mutant
    out = d / f"o_{key}_{mutant or 'clean'}.json"
    r = subprocess.run([sys.executable, str(TOOL), "--run", str(d), "--a-arm", "CONFORM",
                        "--b-arm", "OFF", "--key", key, "--json", str(out)],
                       env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"工具 rc={r.returncode}（infra 壞掉，不是偵測到缺陷）\n{r.stderr}")
    return json.load(out.open(encoding="utf-8"))


def main() -> int:
    fails = []
    with tempfile.TemporaryDirectory(dir="/dev/shm") as td:
        d = pathlib.Path(td); build(d)

        md, dv = run(d, "meets_demand"), run(d, "deliv")
        got_md, got_dv = {"b": md["b_discordant_a_only"], "c": md["c_discordant_b_only"]}, \
                         {"b": dv["b_discordant_a_only"], "c": dv["c_discordant_b_only"]}

        # T1：兩個 key 必須吐出不同的 b/c，且各自等於手算值
        if got_md != EXPECT_MD:
            fails.append(f"T1 meets_demand b/c={got_md} != 手算 {EXPECT_MD}")
        if got_dv != EXPECT_DELIV:
            fails.append(f"T1 deliv b/c={got_dv} != 手算 {EXPECT_DELIV}")
        if got_md == got_dv:
            fails.append(f"T1 兩個 key 給出相同的 b/c={got_md} ⇒ --key 是裝飾品")
        # 產物要記得自己量的是哪一個 key
        if md.get("key") != "meets_demand" or dv.get("key") != "deliv":
            fails.append(f"T1 產物沒記對 key：{md.get('key')} / {dv.get('key')}")

        # T2：具名突變體 M_KEY（--key 做成裝飾品）。判準指名「b/c 這個量沒有變」，
        #     不是 rc≠0——rc≠0 也可能只是 infra 壞掉（memory 記過）。
        m_md, m_dv = run(d, "meets_demand", "M_KEY"), run(d, "deliv", "M_KEY")
        m_got_md = {"b": m_md["b_discordant_a_only"], "c": m_md["c_discordant_b_only"]}
        m_got_dv = {"b": m_dv["b_discordant_a_only"], "c": m_dv["c_discordant_b_only"]}
        if m_got_dv != m_got_md:
            fails.append(f"T2 M_KEY 底下 deliv={m_got_dv} 仍 != meets_demand={m_got_md}"
                         f" ⇒ 突變點沒生效，T1 的綠燈不算數")
        if m_got_dv != EXPECT_MD:
            fails.append(f"T2 M_KEY 底下 deliv b/c={m_got_dv}，應退化成舊語意 {EXPECT_MD}")
        # T2b：突變體底下 T1 的核心斷言必須真的翻紅（證明 T1 看得見這個突變）
        if m_got_dv == EXPECT_DELIV:
            fails.append("T2b M_KEY 底下 deliv 仍等於正確值 ⇒ T1 看不見這個突變體")

    if fails:
        print("R463 TEETH FAIL:"); [print("  -", f) for f in fails]; return 1
    print(f"R463 TEETH PASS: T1 meets_demand b/c={EXPECT_MD} vs deliv b/c={EXPECT_DELIV}"
          f"（分歧 5 格）  T2 M_KEY 底下 deliv 退化成 {EXPECT_MD} 且 T1 翻紅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
