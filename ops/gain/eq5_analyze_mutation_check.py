#!/usr/bin/env python3
"""`analyze_eq5.py` 的植入缺陷測試（round691）。

記憶鐵律：**判準不能只寫 rc≠0**（突變體害 import 失敗也是 rc≠0＝infra 壞掉被誤判成
偵測器有牙齒）。所以每個突變體都要指名「哪一條自檢該叫」，並要求 **乾淨版那條不叫**。
每個突變體也都要有**看得見它的夾具**（單一夾具會讓「顛倒 b/c」在對稱夾具上是 MISSED）。
"""
import os, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "analyze_eq5.py"

# 突變體 -> 該叫的自檢條（selftest 輸出裡必須出現 "SELFTEST FAIL: <前綴>"）
MUTANTS = {
    "M1": ("A", "b/c 顛倒：只有閘門對 vs 只有多數決對 抽反邊"),
    "M2": ("F", "預算擋門從 ==5 放寬成 <=5：早停回來也放行"),
    "M3": ("E", "deliv 口徑漏掉 accepted：拒交但 meets_demand=True 被算成交付"),
    "M4": ("D", "缺欄位靜靜當 False（安靜量不到 型一）"),
    "M5": ("C", "rows 行數與 processed 對不上時不擋（安靜量不到 型二）"),
    "M6": ("J", "run 還沒跑完（terminal=False）也放行 ⇒ 半截 run 被當收官資料"),
    # round692 AMEND-1（same_choice 在拒交格量錯東西）
    "M7": ("K", "退回 AMEND-1 之前：拒交格的 fallback 相同也算「選到同一份」"),
    "M8": ("L", "少了 gate/vote sha 也照跑、退回 raw（AMEND-1 的重算輸入安靜消失）"),
    "M9": ("M", "落盤的 same_choice_effective 與離線重算打架時不擋（安靜取其一）"),
}


def run(mutant: str) -> tuple[int, str]:
    env = dict(os.environ, EQ5_ANALYZE_MUTANT=mutant)
    p = subprocess.run([sys.executable, str(TOOL), "--selftest"],
                       capture_output=True, text=True, env=env,
                       cwd=str(HERE.parents[1]))
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    rc0, out0 = run("")
    fails = []
    if rc0 != 0 or "SELFTEST PASS" not in out0:
        fails.append(f"乾淨版沒 PASS：rc={rc0}\n{out0}")
    caught = {}
    for m, (cond, why) in MUTANTS.items():
        rc, out = run(m)
        hit = f"SELFTEST FAIL: {cond}:" in out
        caught[m] = hit
        if not hit:
            fails.append(f"{m}（{why}）MISSED：自檢條 {cond} 沒有叫。輸出：\n{out.strip()}")
        elif rc == 0:
            fails.append(f"{m}: 條 {cond} 叫了但 rc=0")
    for f in fails:
        print("MUTATION FAIL:", f)
    print("MUTATION", "FAIL" if fails else "PASS",
          "caught=" + ",".join(f"{m}:{'Y' if v else 'N'}" for m, v in caught.items()))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
