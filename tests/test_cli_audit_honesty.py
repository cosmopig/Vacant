"""`vacant audit` 是**外人跑的那個究責入口**，它的措辭就是規格。

這支在架構裡承重什麼
────────────────────
三條原則的第二條是「能讓外部驗證」。外人手上只有 wheel，他跑的是
`vacant audit <name>`。那一行輸出說了什麼，就是我們對外宣稱了什麼。

兩個舊問題（2026-09-19 修）：

1. **空鏈印「✓ PASS（…每筆簽章過）」**。零筆的時候那句話是**恆真**的——
   沒有東西可以驗，不是「驗過了」。那是「沒量到」被寫成「量到 0」的
   同一種混淆（09 §3.5 `infra_void`）。
2. **沒講驗不到什麼**。`verify_chain` 沒有長度承諾也沒有外部錨點 ⇒
   從**鏈尾**砍掉幾筆之後它照樣 PASS（截斷／省略攻擊，Ma & Tsudik 2009，
   DOI 10.1145/1502777.1502779：完整性 ≠ 完備性）。不講的話，
   外人會以為 PASS 涵蓋了「紀錄是完整的」。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from vacant.body import VacantBody


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "vacant.cli", *args],
                          capture_output=True, text=True, timeout=120)


@pytest.fixture()
def body(tmp_path):
    r = _cli("--root", str(tmp_path), "init", "alice")
    assert r.returncode == 0, r.stderr
    return tmp_path


def test_empty_chain_does_not_claim_it_passed(body):
    """空鏈不准印 PASS——但也不是錯誤（剛 init 出來本來就是空的）。"""
    r = _cli("--root", str(body), "audit", "alice")
    assert r.returncode == 0, "空鏈不是錯誤"
    assert "0 筆" in r.stdout
    assert "PASS" not in r.stdout, f"空鏈仍在宣稱通過：\n{r.stdout}"
    assert "沒有東西可驗" in r.stdout
    assert "這不是通過，是沒發生" in r.stdout


def _sign(root: pathlib.Path, n: int) -> None:
    b = VacantBody.load("alice", root)
    for i in range(n):
        b.logbook.append("demo", {"i": i}, b.identity, ts_ms=1000 + i)
    b.logbook.save(b.trust_dir / "logbook.ndjson")


def test_non_empty_chain_passes_and_states_what_it_misses(body):
    _sign(body, 4)
    r = _cli("--root", str(body), "audit", "alice")
    assert r.returncode == 0
    assert "4 筆" in r.stdout
    assert "PASS" in r.stdout
    # ⚠ 誠實邊界要**印出來**，不是只寫在 docstring 裡
    assert "抓不到從鏈尾截斷" in r.stdout, f"沒講盲點：\n{r.stdout}"


def test_truncation_still_passes_which_is_why_the_warning_must_be_there(body):
    """⚠ 這條**刻意斷言一個弱點**：砍掉鏈尾照樣 PASS。

    它不是在說那樣可以接受，是在釘住「既然抓不到，畫面就必須講」。
    哪天真的加了長度承諾／外部錨點，這條會紅——**那時候該改的是這條測試
    與那行警語，不是把警語拿掉了事**。
    """
    _sign(body, 4)
    log = VacantBody.load("alice", body).trust_dir / "logbook.ndjson"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    log.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")

    r = _cli("--root", str(body), "audit", "alice")
    assert r.returncode == 0
    assert "2 筆" in r.stdout
    assert "PASS" in r.stdout, "截斷被抓到了——那就要改警語與這條測試"
    assert "抓不到從鏈尾截斷" in r.stdout


def test_tampering_is_caught(body):
    """抓得到的那一半也要釘住，否則上一條會退化成「反正都 PASS」。"""
    _sign(body, 4)
    log = VacantBody.load("alice", body).trust_dir / "logbook.ndjson"
    lines = log.read_text(encoding="utf-8").splitlines()
    # 序列化是緊湊的（`{"i":1}`，冒號後沒有空白）——照抄格式不要猜
    assert '"payload":{"i":1}' in lines[1], lines[1][:120]
    lines[1] = lines[1].replace('"payload":{"i":1}', '"payload":{"i":99}')
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    r = _cli("--root", str(body), "audit", "alice")
    assert r.returncode == 1
    assert "FAIL" in r.stdout
