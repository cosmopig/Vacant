"""bandit 的高嚴重度掃描＋**逐項具名**的已知例外（CI 的 security scan job）。

這支在架構裡承重什麼
────────────────────
「安全掃描」很容易長成兩種沒有用的東西：

  * **全開**——repo 裡 1,498 個 Low（`subprocess` 呼叫、`assert`、
    `/tmp` 字串……）會讓門永遠紅，於是被關掉或加 `|| true`，等於沒有；
  * **全關**——只跑不判（`continue-on-error`），紅的東西沒有人會看。

所以判準是：**HIGH 嚴重度的發現一個都不准新增**，而現存的三個逐項寫在
下面的 `KNOWN` 裡，每一個都要有「為什麼它在這裡是可接受的」。名單比對用
`(test_id, 檔案)` 不用行號——行號會隨無關的編輯漂掉，那種假紅會訓練人
去忽略這道門。

⚠ **這是單邊保證**：擋得住已知壞法 ≠ 涵蓋真需求（`vacant_network/suitegauge.py`
的同一句話）。bandit 是語法層樣式比對，它看不出邏輯上的權限錯誤。

用法（CI 與本機同一支）：
    python .github/scripts/security_scan.py
    python .github/scripts/security_scan.py --selftest   # 判準自己的牙齒
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: 掃描範圍。`tests/` 不掃：測試本來就在故意造壞輸入。
TARGETS = ("vacant_network", "ops", "examples")

#: 已知且**有理由**的 HIGH 發現。key＝(bandit test_id, 相對路徑)。
#: 新增一筆就是一次明示決定——要寫得出理由才加得進來。
KNOWN: dict[tuple[str, str], str] = {
    ("B103", "ops/gain/r530/run_r530.py"):
        "0o777 開在**沙箱探針目錄**上：R530 的 unshare 沙箱降權成 uid 65534，"
        "探針要寫得進去才驗得到「寫入真的被關在 cwd 裡」。那個目錄是每塊 run "
        "自己建的暫存工作區，不是資料或金鑰（SANDBOX.md／預註冊 §三-3 S2）。",
    ("B324", "ops/gain/replay/seq_shortstop.py"):
        "sha1 在這裡是**分組用的短鍵**不是安全雜湊：它把同一個 prompt 的呼叫"
        "併成一格好做重放比對。鏈上的簽章與 RECORD_SPEC 的逐檔雜湊一律 sha256"
        "（`vacant_network/logbook.py`、`vacant_network/record.py`），沒有用到 sha1。",
    ("B602", "ops/progress.py"):
        "shell=True 的輸入是本檔自己寫死的字串常數（進度顯示用的 git 指令），"
        "不吃外部輸入。這支是開發期的終端機小工具，不進 wheel"
        "（`pyproject.toml` 只打包 `vacant_network`）。",
}


def run_bandit(targets: tuple[str, ...]) -> list[dict]:
    """只要 HIGH 嚴重度（`-lll`），輸出 JSON。"""
    proc = subprocess.run(
        [sys.executable, "-m", "bandit", "-q", "-r", *targets, "-lll", "-f", "json"],
        cwd=ROOT, capture_output=True, text=True, timeout=1800)
    # bandit 有發現時 exit code 是 1；真正的失敗看 stdout 是不是合法 JSON。
    try:
        return json.loads(proc.stdout)["results"]
    except (ValueError, KeyError):
        raise SystemExit(
            f"bandit 沒有吐出可讀的 JSON（rc={proc.returncode}）：\n{proc.stderr[-2000:]}")


def classify(results: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """回 (未授權的新發現, 名單裡沒有被命中的項目)。"""
    seen: set[tuple[str, str]] = set()
    unknown: list[dict] = []
    for r in results:
        key = (r["test_id"], str(pathlib.Path(r["filename"]).resolve()
                                 .relative_to(ROOT).as_posix()))
        if key in KNOWN:
            seen.add(key)
        else:
            unknown.append(r)
    return unknown, sorted(set(KNOWN) - seen)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="不跑 bandit，改驗判準自己擋不擋得住")
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    results = run_bandit(TARGETS)
    print(f"bandit -lll 掃 {'／'.join(TARGETS)}：{len(results)} 個 HIGH 發現")
    unknown, stale = classify(results)

    for key, why in sorted(KNOWN.items()):
        print(f"  已知例外 {key[0]} {key[1]}\n      {why}")
    for key in stale:
        print(f"  ⚠ 名單裡的 {key[0]} {key[1]} 這次沒被命中——"
              "程式碼可能已經改掉了，把它從 KNOWN 刪掉（留著就是在放行不存在的東西）")
    for r in unknown:
        print(f"  × 未授權的 HIGH：{r['test_id']} {r['filename']}:{r['line_number']}"
              f"\n      {r['issue_text']}")

    if unknown:
        print(f"FAIL：{len(unknown)} 個新的 HIGH 發現。"
              "要嘛修掉，要嘛在 .github/scripts/security_scan.py 的 KNOWN 裡"
              "寫下理由——不准直接關掉這道門。")
        return 1
    if stale:
        print("FAIL：KNOWN 裡有過期的例外（見上）。")
        return 1
    print("OK：沒有新的 HIGH 發現。")
    return 0


def _selftest() -> int:
    """判準的牙齒：多一個 HIGH 要紅、名單過期要紅、剛好相等才綠。"""
    known_key = next(iter(KNOWN))
    hit = {"test_id": known_key[0],
           "filename": str(ROOT / known_key[1]), "line_number": 1,
           "issue_text": "x"}
    all_hits = [{"test_id": k[0], "filename": str(ROOT / k[1]),
                 "line_number": 1, "issue_text": "x"} for k in KNOWN]
    stranger = {"test_id": "B602", "filename": str(ROOT / "vacant_network/agent.py"),
                "line_number": 1, "issue_text": "x"}

    unknown, stale = classify(all_hits)
    assert unknown == [] and stale == [], (unknown, stale)
    unknown, stale = classify(all_hits + [stranger])
    assert len(unknown) == 1 and stale == [], (unknown, stale)
    unknown, stale = classify([hit])
    assert unknown == [] and len(stale) == len(KNOWN) - 1, (unknown, stale)
    print(f"selftest OK（KNOWN {len(KNOWN)} 筆：新發現會紅、名單過期會紅）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
