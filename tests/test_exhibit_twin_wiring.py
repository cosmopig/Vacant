"""數位分身那條線**真的在開機路徑上**（2026-09-21）。

## 這支在架構裡承重什麼

`twinlink`／`twinstore` 那一整條鏈（觀眾手機 → 公網 → append-only 庫 → 1003 →
現場螢幕）寫好了、演練過了、有 e2e 腳本——**但它沒有接在開機路徑上**。
批判者對六支營運檔跑同一個 grep（正控制是同一個 grep 打在 `twinlink.py` 上）：

    exhibit_boot.sh 0 · exhibit_preflight.sh 0 · venue_check.sh 0
    systemd/install.sh 0 · vacant-exhibit.service 0 · vacant-exhibit-kiosk.service 0
    twinlink.py 16   ← 正控制，grep 量得動

⇒ 布展當天 `venue_check.sh` 會印綠，而整條數位分身線一個字都沒被量。

這一支就是那個 grep 的可執行版本。它守的**不是**「函式寫對了」，是
「**產品路徑上真的有人呼叫它**」——2026-09-21 剛抓到一個同形的病：
`resolve_endpoint()` 六條測試全綠而產品路徑零呼叫點。測試綠 ≠ 接上去了。

⚠ 這支的界線：它證明的是「字串在檔案裡／端點敲得到／快照新鮮度這把尺量得動」。
  它**沒有**證明電視那顆瀏覽器真的去讀了 `&twin=`（那要開瀏覽器，
  在 `vacant_hm/tools/livecheck.mjs` 那一邊）。兩件事不要混講。
"""
from __future__ import annotations

import json
import pathlib
import re
import socket
import subprocess
import time
from datetime import datetime, timedelta, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TWIN = ROOT / "ops" / "exhibit" / "twin"

#: 批判者用的那一個 regex，一個字都沒改。
WIRE_RE = re.compile(r"twinlink|twinstore|twinanchor|visitors\.json|&twin=")

#: 六支營運檔＋一支新的 unit。命中數必須 ≥1。
OPS_FILES = [
    TWIN / "exhibit_boot.sh",
    TWIN / "exhibit_preflight.sh",
    TWIN / "venue_check.sh",
    TWIN / "systemd" / "install.sh",
    TWIN / "systemd" / "vacant-exhibit.service",
    TWIN / "systemd" / "vacant-exhibit-kiosk.service",
    TWIN / "systemd" / "vacant-twin-loop.service",
]


def _hits(p: pathlib.Path) -> int:
    return sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if WIRE_RE.search(ln))


def test_positive_control_the_grep_actually_matches():
    """🔴 **先證明量得動。** 沒有這一條，下面全綠跟「regex 寫錯了」同形。"""
    n = _hits(TWIN / "twinlink.py")
    assert n >= 10, f"正控制掛了：twinlink.py 只有 {n} 命中 ⇒ 下面那些 0 不算數"


@pytest.mark.parametrize("p", OPS_FILES, ids=lambda p: p.name)
def test_twin_line_is_on_the_boot_path(p: pathlib.Path):
    """六支營運檔每一支都要提到分身那條線。2026-09-21 之前全部是 0。"""
    assert p.exists(), p
    assert _hits(p) >= 1, (
        f"{p.name} 對 twinlink|twinstore|visitors.json|&twin= 零命中"
        "——分身那條線又從開機路徑上掉了")


def test_tv_url_carries_twin_and_the_port_never_drifts():
    """`&twin=` 的埠在四個地方寫著，它們**必須是同一個**。

    ⚠ 這不是潔癖：`bridge.js` 的來源鏈第一層（store）只能從網址進來，
      `index.html` 刻意不給預設值。埠一旦漂掉，畫面不會報錯，只會安靜地
      少一層來源，然後說「分身讀本機快照」——而那個快照可能沒人在寫。
    """
    boot = (TWIN / "exhibit_boot.sh").read_text(encoding="utf-8")
    kiosk = (TWIN / "systemd" / "vacant-exhibit-kiosk.service").read_text(encoding="utf-8")
    venue = (TWIN / "venue_check.sh").read_text(encoding="utf-8")
    unit = (TWIN / "systemd" / "vacant-exhibit.service").read_text(encoding="utf-8")

    m = re.search(r"^STORE_PORT=(\d+)", boot, re.M)
    assert m, "exhibit_boot.sh 沒有 STORE_PORT 預設值"
    port = m.group(1)

    assert re.search(r"^STORE_PORT=" + port + r"$", venue, re.M), \
        f"venue_check.sh 的 STORE_PORT 跟 exhibit_boot.sh（{port}）對不上"
    assert f"&twin=http://127.0.0.1:{port}/visitors.json" in kiosk, \
        f"kiosk unit 的網址沒有帶 &twin=…:{port}/visitors.json"
    assert f"--store-port {port}" in unit, \
        f"vacant-exhibit.service 沒有把 --store-port {port} 寫出來"
    # 開機腳本自己要把 `&twin=` 接到電視網址上（不是只有變數宣告）
    assert '&twin=$STORE_URL' in boot, "exhibit_boot.sh 沒有把 &twin= 接進 TV_URL"


def test_loop_unit_restarts_always_and_fails_loud_without_a_token():
    """loop 死掉時畫面完全正常 ⇒ 它要有自己的 unit、自己的 Restart=always。"""
    u = (TWIN / "systemd" / "vacant-twin-loop.service").read_text(encoding="utf-8")
    assert "Restart=always" in u
    assert "StartLimitIntervalSec=0" in u, "沒關速率限制＝失敗幾次就永久放棄，展期一整天不會再起來"
    assert "ExecStart=@@REPO@@/ops/exhibit/twin/twin_loop.sh" in u
    assert "EnvironmentFile=-/etc/vacant/twin.env" in u, "token 要從檔案進來，不進版控"


def test_twin_loop_script_exits_78_and_says_why_without_a_token():
    """**負控制**：沒有 token 不可以安靜地不做事。

    安靜空轉一整天＝觀眾投的卡永遠不變成分身，而畫面一切正常。
    """
    r = subprocess.run([str(TWIN / "twin_loop.sh")], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp"})
    assert r.returncode == 78, (r.returncode, r.stdout, r.stderr)
    assert "VACANT_TWIN_CLOUD_TOKEN" in r.stderr
    # 「不是 0 個觀眾，是這條線沒接」——這句話是規格的一部分
    assert "不是「0 個觀眾」" in r.stderr


def test_twin_loop_print_cmd_masks_the_token():
    """`--print-cmd` 會被貼進紀錄與 journal，token 不准跟著出去。"""
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp",
           "VACANT_TWIN_CLOUD_TOKEN": "s3cr3t-do-not-log"}
    r = subprocess.run([str(TWIN / "twin_loop.sh"), "--print-cmd"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "s3cr3t-do-not-log" not in r.stdout
    assert "***" in r.stdout
    assert "loop" in r.stdout and "--out" in r.stdout


# ---------------------------------------------------------------------------
# 活體：venue_check 第八節真的敲得到一個真的 twinlink serve 嗎
# ---------------------------------------------------------------------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _write_snapshot(path: pathlib.Path, when: datetime | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    g = None if when is None else when.isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps(
        {"generated_at": g, "counts": {"visitors": 0}, "people": []}), encoding="utf-8")


@pytest.fixture()
def twin_stack(tmp_path):
    """起一個真的 `twinlink serve` ＋ 一個假的電視靜態站。

    ⚠ 埠一律動態挑。展場那三個埠（8420/8899/8901）在這台機器上**可能有人在跑**
      （2026-09-21 實測：另一個 session 在 18901 上留了一支「什麼都回
      `{"ok":true}`」的行程，venue_check 的負控制當場抓到它）。
    """
    db = tmp_path / "t.sqlite3"
    tv_root = tmp_path / "tv"
    (tv_root / "world3" / "live").mkdir(parents=True)
    subprocess.run(["python3", str(TWIN / "twinlink.py"), "--db", str(db), "view"],
                   check=True, capture_output=True)
    sp, tp = _free_port(), _free_port()
    serve = subprocess.Popen(
        ["python3", str(TWIN / "twinlink.py"), "--db", str(db), "serve", "--port", str(sp)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tv = subprocess.Popen(
        ["python3", "-m", "http.server", str(tp), "--bind", "127.0.0.1"],
        cwd=str(tv_root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ⚠ **不要用固定的 sleep。** 2026-09-21 實測：這台機器上同時有別的工作在
    #   跑整套測試，兩支 python 兩秒之內起不來 ⇒ 正控制那條假紅。
    #   （同一個坑也在 `exhibit_boot.sh` 裡，那邊改成 `wait_for` 輪詢。）
    #   起不來就 `pytest.fail`，**不是 skip**——「沒量到」要看得見。
    import urllib.error
    import urllib.request

    def _up(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    deadline = time.time() + 30
    while time.time() < deadline:
        if (_up(f"http://127.0.0.1:{sp}/visitors.json")
                and _up(f"http://127.0.0.1:{tp}/")):
            break
        time.sleep(0.5)
    else:
        serve.terminate(); tv.terminate()
        pytest.fail(f"30 秒內 twinlink serve（{sp}）或靜態站（{tp}）沒起來")

    try:
        yield {"store_port": sp, "tv_port": tp, "serve": serve,
               "snap": tv_root / "world3" / "live" / "visitors.json"}
    finally:
        for p in (serve, tv):
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


def _venue(stack, *extra) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(TWIN / "venue_check.sh"), "--only-twin",
         "--store-port", str(stack["store_port"]),
         "--tv-port", str(stack["tv_port"]), *extra],
        capture_output=True, text=True)


def test_venue_check_greenlights_a_live_twin_line(twin_stack):
    """正控制：serve 活著、快照是新的 ⇒ exit 0。"""
    _write_snapshot(twin_stack["snap"], datetime.now(timezone.utc))
    r = _venue(twin_stack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "/visitors.json → 200" in r.stdout
    assert "counts.visitors 讀得到" in r.stdout
    # 量具自己的負控制也要在畫面上講
    assert "404" in r.stdout


def test_venue_check_catches_a_stale_snapshot(twin_stack):
    """🔴 靜默降級：loop 死了，畫面完全正常，只有快照的時間停住。"""
    _write_snapshot(twin_stack["snap"], datetime.now(timezone.utc) - timedelta(hours=3))
    r = _venue(twin_stack)
    assert r.returncode == 1, r.stdout
    assert "分鐘前就停了" in r.stdout


def test_venue_check_calls_placeholder_snapshot_null_not_zero(twin_stack):
    """`generated_at: null` ＝ 沒有東西寫過它，**不是「0 分鐘前」也不是 0 個觀眾**。

    commit 進 `vacant_hm` 的那一份佔位檔就長這樣。
    """
    _write_snapshot(twin_stack["snap"], None)
    r = _venue(twin_stack)
    assert r.returncode == 1, r.stdout
    assert "null" in r.stdout
    assert "不是「0 個觀眾」" in r.stdout


def test_venue_check_notices_the_readonly_endpoint_is_dead(twin_stack):
    """負控制：把 serve 殺掉 ⇒ 必須判硬傷（電視的 &twin= 是死的）。"""
    _write_snapshot(twin_stack["snap"], datetime.now(timezone.utc))
    twin_stack["serve"].terminate()
    twin_stack["serve"].wait(timeout=5)
    time.sleep(0.5)
    r = _venue(twin_stack)
    assert r.returncode == 1, r.stdout
    assert "twinlink serve 沒起來" in r.stdout


def test_venue_check_skip_twin_says_not_measured_not_ok(twin_stack):
    """`--skip-twin` 要講「沒量到」，不可以長得像「量到沒問題」。"""
    _write_snapshot(twin_stack["snap"], None)      # 故意是壞的
    r = _venue(twin_stack, "--skip-twin")
    assert r.returncode == 0
    assert "沒量到" in r.stdout
