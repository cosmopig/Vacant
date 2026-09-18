"""逾時收尾：**送得出訊號不等於殺得掉**（2026-09-19 vacant-dev 實測而來）。

這支在架構裡承重什麼
────────────────────
`UnshareSandbox` 走 `sudo -n unshare -- setpriv --reuid=<nobody>`，於是
`Popen` 記到的 pid 是 `sudo`（root 的）。舊版 `_kill_group` 用無特權身分
`killpg` 會拿到 `PermissionError: [Errno 1]`，被 `except Exception: pass`
吞掉 ⇒ **逾時什麼都沒殺**。實地後果：vacant-dev 上累積 72 個
`python3 -m solution tests_visible/test_visible.py` 孤兒（ppid=1、2–4 天、
每個 13% CPU、load 71），而 load 又讓後面每一格的逾時虛發，再生更多孤兒。

這裡釘死三件事：整組真的死、收尾結果**落盤**、送不到訊號要誠實說洩漏。
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

import pytest

from vacant.vrun import sandbox as sb

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX 才有行程組")


@posix_only
def test_timeout_kills_the_whole_group_and_records_it(tmp_path):
    """孫行程也要死，而且 `kill_status` 要記成 `reaped`。"""
    marker = tmp_path / "grandchild.pid"
    # 孫行程：把自己的 pid 寫出來然後睡很久。寫成檔避免多層引號。
    script = tmp_path / "gc.py"
    script.write_text(
        "import os, time\n"
        f"open({str(marker)!r}, 'w').write(str(os.getpid()))\n"
        "time.sleep(600)\n", encoding="utf-8")
    # `&` ⇒ 孫行程與 bash 平行；bash 自己也睡著，逼出逾時。
    cmd = f"{sys.executable} {script} & sleep 600"
    r = sb.Sandbox().run(cmd, workspace=tmp_path, timeout_s=3)

    assert r.timed_out is True
    assert r.rc is None, "逾時不是「跑出某個 rc」"
    assert r.kill_status == "reaped", f"收尾沒成功：{r.kill_status}"

    for _ in range(40):
        if marker.exists():
            break
        time.sleep(0.05)
    assert marker.exists(), "孫行程根本沒起來，這個測試就沒測到東西"
    gpid = int(marker.read_text())
    for _ in range(40):                       # 收割是非同步的，給一點時間
        try:
            os.kill(gpid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        os.kill(gpid, signal.SIGKILL)         # 別把孤兒留給下一個測試
        pytest.fail(f"孫行程 {gpid} 還活著——killpg 沒吃到整組")


@posix_only
def test_no_timeout_leaves_kill_status_empty(tmp_path):
    """沒逾時就沒收尾；`""` 代表「沒發生」，不是「成功」。"""
    r = sb.Sandbox().run("true", workspace=tmp_path, timeout_s=30)
    assert r.timed_out is False
    assert r.kill_status == ""
    assert "kill_status" in r.to_json()


@posix_only
def test_group_alive_reports_true_when_we_lack_permission(monkeypatch):
    """⚠ 方向性：訊號送不到 ⇒ **還在**，不可以樂觀讀成「已經沒了」。

    這正是 vacant-dev 那 72 個孤兒的處境：`killpg(0)` 回 `PermissionError`。
    """
    def deny(_pgid, _sig):
        raise PermissionError(1, "Operation not permitted")
    monkeypatch.setattr(sb.os, "killpg", deny)
    assert sb._group_alive(424242) is True

    def gone(_pgid, _sig):
        raise ProcessLookupError()
    monkeypatch.setattr(sb.os, "killpg", gone)
    assert sb._group_alive(424242) is False


@posix_only
def test_unkillable_group_is_reported_as_leaked(monkeypatch):
    """殺不掉要回 `leaked:`，而且**不准丟例外**（收尾在錯誤路徑上）。"""
    monkeypatch.setattr(
        sb.os, "killpg",
        lambda _p, _s: (_ for _ in ()).throw(
            PermissionError(1, "Operation not permitted")))
    t0 = time.time()
    status = sb._kill_and_verify(424242, sudo=False, grace_s=0.2)
    assert status.startswith("leaked:"), status
    assert "PermissionError" in status
    assert time.time() - t0 < 5, "grace 沒有被遵守"


@posix_only
def test_sudo_path_is_attempted_for_unshare_backend(monkeypatch):
    """`unshare` 後端的收尾必須**走 sudo**，否則對 nobody 的行程組無效。"""
    seen: list[list[str]] = []

    def fake_run(argv, **_kw):
        seen.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(sb.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sb.os, "killpg",
        lambda _p, _s: (_ for _ in ()).throw(ProcessLookupError()))

    assert sb._kill_and_verify(4242, sudo=True) == "reaped"
    assert seen, "根本沒呼叫 sudo"
    assert seen[0][:4] == ["sudo", "-n", "kill", "-9"], seen[0]
    assert seen[0][-1] == "-4242", "要殺的是**行程組**（負號），不是單一 pid"


def test_unshare_backend_overrides_the_kill_path():
    """擋門：有人把覆寫拿掉，這條就紅。"""
    assert sb.UnshareSandbox._kill_group is not sb.Sandbox._kill_group
