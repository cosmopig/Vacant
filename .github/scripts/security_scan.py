"""bandit 的高嚴重度掃描＋**逐項具名**的已知例外（CI 的 security scan job）。

這支在架構裡承重什麼
────────────────────
「安全掃描」很容易長成兩種沒有用的東西：

  * **全開**——repo 裡 1,498 個 Low（`subprocess` 呼叫、`assert`、
    `/tmp` 字串……）會讓門永遠紅，於是被關掉或加 `|| true`，等於沒有；
  * **全關**——只跑不判（`continue-on-error`），紅的東西沒有人會看。

所以判準是：**HIGH 嚴重度的發現一個都不准新增**，而現存的那幾個逐項寫在
下面的 `KNOWN` 裡，每一個都要有「為什麼它在這裡是可接受的」。名單比對用
`(test_id, 檔案)` 不用行號——行號會隨無關的編輯漂掉，那種假紅會訓練人
去忽略這道門。

⚠ **為什麼有些發現進名單而不是改碼**：`ops/vacantrun/*_2026091x／2026092x/` 底下
是**已經產出歸檔證據的 harness**，被量到的那條路（例如「路徑型 unix socket 讓
被封鎖的 uid 連得上」）本身就是實驗條件；`ops/eval/codesuite/make_lcb_suite.py` 的
sha256 被釘進已歸檔的建置 manifest，`check` 會拿現在的檔去比。改這幾支＝讓歸檔證據
和產生它的程式碼對不起來，所以逐項寫理由、不改碼。**新寫的程式碼沒有這個藉口**——
`vacant_network/` 底下目前沒有任何例外，要加就得先說服自己為什麼修不了。

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
    ("B602", "ops/eval/evidence_20261008_091_container/drivers/cc_drv/timing.py"):
        "`shell=True` 跑的是 `vacant install` 自己寫進 Claude 設定裡的 hook 指令列——量的就是"
        "Claude Code 用 shell 執行那一行的成本（0.9.0 對 0.9.1），拆成 argv 就不是在量同一件事。"
        "只在一次性、`--network none` 的測試容器裡跑，指令來自容器內的設定檔、不吃外部輸入；"
        "歸檔證據（`runs/claude/`）就是這支量的，不改碼、不進 wheel。",
    ("B602", "ops/eval/evidence_20261008_091_container/drivers/oc1drv/drive.py"):
        "容器 e2e 的 OpenCode 1.x 驅動程式：`shell=True` 只用在寫死的 tmux／檔案指令（指令字串由"
        "本檔組出，沒有外部輸入），只在一次性、`--network none` 的測試容器裡跑。"
        "歸檔證據（`runs/opencode1/`）就是這支跑的，不改碼、不進 wheel。",
    ("B103", "ops/gain/r530/run_r530.py"):
        "0o777 開在**沙箱探針目錄**上：R530 的 unshare 沙箱降權成 uid 65534，"
        "探針要寫得進去才驗得到「寫入真的被關在 cwd 裡」。那個目錄是每塊 run "
        "自己建的暫存工作區，不是資料或金鑰（SANDBOX.md／預註冊 §三-3 S2）。",
    ("B103", "ops/vacantrun/bypass_stress_20260919/harness/unixrelay.py"):
        "0o777 開在**盲點示範用的 unix socket**（`/var/tmp/vbypass/work/relay.sock`，"
        "`setup.sh` 已把 `work/` 開成 777）：這支 harness 量的就是「`iptables --uid-owner` "
        "封鎖看不到路徑型 unix socket」——user1 聽、被封鎖的 uid 1001 要 `connect()` 得上，"
        "而 unix socket 的 connect 需要對該檔有寫入權，所以放寬權限是**被量的那個條件**"
        "不是疏漏（`data/unix_probe.json`：封鎖下 0.034 秒 200 OK、計數器 0）。"
        "改成 0o600 ⇒ uid 1001 得到 EACCES，示範的那一格就量不到盲點。它只做 bytes 轉送、"
        "不讀不存內容；是一次性的 L-sim 替身，不進 wheel。不改碼：證據已歸檔。",
    ("B103", "ops/vacantrun/egress_v3_20260919/harness/unixrelay.py"):
        "與 `bypass_stress_20260919/harness/unixrelay.py` **逐位元組相同**（sha256 "
        "be3121f1…），理由相同：0o777 開在盲點示範的 unix socket（`/var/tmp/v3egress/or.sock`），"
        "被封鎖的 uid 1001 要連得上才量得到「封鎖之後 unix socket 照樣 200 OK」"
        "（`unix_relay_after.json`）。放寬權限是被量的條件；不讀不存內容、不進 wheel、"
        "歸檔證據已錄所以不改碼。",
    ("B103", "ops/vacantrun/enclosure_20260920/bin/door_host_bytepipe.py"):
        "0o666 開在**已被取代的舊門**的 socket（`$BASE/door/echo_pipe.sock`，`run_probes.sh` "
        "自己建的目錄），它存在的唯一理由是 `/admin` 那一格的**負控制**（檔頭 docstring）："
        "要照舊把 bytes 原樣隧道到對面那台自己起的 echo 上游（127.0.0.1，只記 path），"
        "才證明「門不終結 HTTP 的話 /admin 到得了上游」，所以不改它的行為。"
        "⚠ 同機任何 uid 都連得上、而且不看內容——**它不能當正式的門**；正式的門"
        "（`wireproxy.py`，bind 之後 `chmod 0o600`、`proxyd` 的 `sentinel=\"\"` 不持有金鑰）"
        "沒有這個放寬，`vacant_network/` 也沒有任何 HIGH。不進 wheel。",
    ("B103", "ops/vacantrun/enclosure_20260920/bin/targets_up.py"):
        "0o666 開在 enclosure 圍牆探針的**目標** socket（`unix_path` 模式：`/tmp/vacant_enc_target_$$.sock`，"
        "只回固定的 `ALIVE`、不讀不存任何資料，`run_probes.sh` 的 cleanup 會刪掉它）。"
        "它是「不套圍牆時要連得到」的負控制：連得到才有資格說圍牆那一側的 ENOENT 是圍牆造成的"
        "（README §1 `unix_path_tmp`）；放寬權限是讓負控制那一側不會被檔案權限擋下而誤判。"
        "歸檔證據（`evidence/probe_*.json`）就是用這支量的，不進 wheel。",
    ("B324", "ops/eval/codesuite/make_lcb_suite.py"):
        "sha1 在這裡是 **git blob 物件 id**（`sha1(\"blob <n>\\0\" + 內容)`），唯一用途是跟 "
        "`git ls-tree -r` 的清單對（`pin-export --ls-tree`），驗證匯出目錄就是釘死 commit 的那一份"
        "——git 的物件 id 只能是 sha1，換不掉也不該換。完整性的承重釘是 sha256"
        "（`sha256_file`／`dir_hash`、EXPORT_MANIFEST 的 `task_dir_sha256`、官方檔的 `OFFICIAL_*_SHA256`），"
        "沒有任何信任判斷只靠 sha1。**為什麼不改成 `usedforsecurity=False`**（雜湊值不變）："
        "這支自己的 sha256 被釘進已歸檔的 `LCB_VISIBLE_MANIFEST_v2.json` 的 `converter_sha256`，"
        "`check` 會拿現在的檔去比——改一個字元就讓那份歸檔建置出現「converter changed since build」"
        "（2026-10-01 在 scratch 複本上實測：原檔 problems 無此項、加了 `usedforsecurity=False` 後出現）。",
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
