"""展場螢幕的視窗與退役程序的判準（2026-09-21）。

## 這一份在守什麼

「第七天任何一次重整，電視會從第一天的第一個人開始重演。」

真因是兩邊各一半：`twinlink.build_view()` 回**整個 roster 沒有上限**，
而 `vacant_hm/world3/bridge.js` 的 `seenIds` 在**記憶體裡**（每次載入都是空的）。
看門狗 reload／kiosk `Restart=always`／斷電／有人按 F5，任一觸發就整批重排。
`spawnQueue.shift()` 一次一個、每人約 30 秒 ⇒ 300 人時剛投完卡的觀眾等 **2.5 小時**。

這一份只守 `twinlink.py` 那一側，判準一律是**觀眾體驗**不是資料結構：

| 測試 | 守的那句話 |
|---|---|
| `test_the_person_who_just_submitted_is_first` | 他投完卡走到螢幕前**一定看得到自己** |
| `test_peak_hour_cannot_squeeze_him_out` | 尖峰時段（一秒內湧入 300 人）也擠不掉他 |
| `test_arriving_is_never_dropped` | 分身還在生成中的那一位也在畫面上（「正在抵達」） |
| `test_retirement_is_visible_and_on_chain` | 退役**有交代**：告別詞上鏈、畫面拿得到 |
| `test_retirement_is_not_erasure` | 退役 ≠ 刪除（鏈還是綠的、事件一列沒少） |
| `test_export_cli_*` / `test_loop_cli_*` | **產品路徑真的在呼叫它**，不是旗標存在而已 |

⚠ **每個綠燈都配一個負控制**：能證明「這個量法有鑑別力」的，才算量到東西。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_GENERATED, KIND_NOTE, KIND_SUBMITTED, TwinStore,
)

DAY = 86_400_000


@pytest.fixture()
def store(tmp_path: pathlib.Path) -> TwinStore:
    st = TwinStore(tmp_path / "t.sqlite3")
    yield st
    st.close()


def _person(st: TwinStore, sid: str, *, ms: int | None = None,
            generated: bool = True) -> None:
    st.append(KIND_SUBMITTED, sid, {"card": {"need": f"事:{sid}"}},
              source="test", ts_unix_ms=ms)
    if generated:
        st.append(KIND_GENERATED, sid,
                  {"arrival": f"{sid} 到了", "working": "做", "handover": f"{sid} 交件",
                   "engine": "fallback_deterministic"},
                  source="test", ts_unix_ms=None if ms is None else ms + 1)


def _crowd(st: TwinStore, n: int, *, now_ms: int, days_ago: int = 6) -> None:
    """造一批「前幾天來的」人。時間戳往前推，所以他們是 `ambient`。"""
    base = now_ms - days_ago * DAY
    for i in range(n):
        _person(st, f"old{i:04d}", ms=base + i * 1000)


# ---------------------------------------------------------------------------
# 一、核心體驗：投完卡走到螢幕前要看到自己
# ---------------------------------------------------------------------------

def test_the_person_who_just_submitted_is_first(store: TwinStore) -> None:
    """🔴 展件的核心體驗。**`--recent` 再小都擠不掉他。**"""
    now = 1_800_000_000_000
    _crowd(store, 300, now_ms=now)
    _person(store, "剛剛那位", ms=now - 5_000)

    for recent in (1, 5, 60, 300):
        view = twinlink.build_view(store, recent=recent, now_ms=now)
        assert view["people"][0]["id"] == "剛剛那位", f"recent={recent} 把他排到後面了"
        assert view["people"][0]["tier"] == "fresh"
        assert len(view["people"]) <= max(recent, 1) * twinlink.FRESH_OVERFLOW_FACTOR


def test_negctl_the_old_ordering_really_did_bury_him(store: TwinStore) -> None:
    """負控制：**沒有這個修改的話他真的被埋掉**。

    量法要有鑑別力——如果「舊排序」下他也在前面，那上面那條綠燈什麼都沒證明。
    舊行為＝`store.roster()`（`sub_ids()` 依 `MIN(seq)` **遞增**）。
    """
    now = 1_800_000_000_000
    _crowd(store, 300, now_ms=now)
    _person(store, "剛剛那位", ms=now - 5_000)

    old_order = [c["sub_id"] for c in store.roster()]
    assert old_order.index("剛剛那位") == 300, "負控制失效：舊排序沒有把他埋掉"
    # 每人 30 秒（**估計值**，電視那端沒有這個常數可引——見 twinlink.DEFAULT_RECENT
    # 的註解 1）⇒ 他在舊行為下要等多久。這裡只用它撐出「兩小時以上」這個量級。
    assert old_order.index("剛剛那位") * 30 / 3600 > 2.0, "負控制失效：舊行為沒有 2 小時以上"


def test_peak_hour_cannot_squeeze_him_out(store: TwinStore) -> None:
    """尖峰：模型掛掉 ⇒ 300 張卡在一秒內全部 `fallback` 生完、全部 `fresh`。

    這是唯一會讓「最近 N 位」爆掉的情境。判準仍然是觀眾體驗：
    **最新的那一位在 `people[0]`**，而塞不下的人記成 `waiting` 讓畫面講得出來，
    不是靜靜消失也不是假裝塞得下。
    """
    now = 1_800_000_000_000
    for i in range(300):
        _person(store, f"flood{i:04d}", ms=now - 60_000 - i)   # 一分鐘內全部湧入
    _person(store, "剛剛那位", ms=now - 2_000)

    view = twinlink.build_view(store, recent=20, now_ms=now)
    assert view["people"][0]["id"] == "剛剛那位"
    assert len(view["people"]) == 20 * twinlink.FRESH_OVERFLOW_FACTOR
    assert view["counts"]["waiting"] == 301 - 60
    # 被硬上限切掉的人**還沒輪到**，不可以當成「演完了」而退役
    assert view["counts"]["retired"] == 0


def test_arriving_is_never_dropped(store: TwinStore) -> None:
    """分身還在生成中的那一位也要在畫面上——他正站在螢幕前面等。"""
    now = 1_800_000_000_000
    _crowd(store, 100, now_ms=now)
    _person(store, "還在生成", ms=now - 3_000, generated=False)

    view = twinlink.build_view(store, recent=3, now_ms=now)
    assert view["people"][0]["id"] == "還在生成"
    assert view["people"][0]["tier"] == "arriving"
    assert view["people"][0]["status"] == "submitted"
    assert view["counts"]["arriving"] == 1


def test_fresh_window_is_wide_enough_for_a_slow_generation(store: TwinStore) -> None:
    """正控制：卡在生成裡十分鐘的那一位，一生出來仍然算 `fresh`。

    最壞情況是同一個檔案裡的常數推出來的：`DEFAULT_GEN_TIMEOUT` 兩發 ＋ 一輪 loop。
    """
    worst_s = twinlink.DEFAULT_GEN_TIMEOUT * 2 + 10.0
    assert twinlink.DEFAULT_FRESH_WINDOW_S > worst_s, (
        f"fresh 視窗 {twinlink.DEFAULT_FRESH_WINDOW_S}s 蓋不住最壞生成路徑 {worst_s}s")

    now = 1_800_000_000_000
    store.append(KIND_SUBMITTED, "慢的", {"card": {"need": "x"}},
                 source="test", ts_unix_ms=now - int(worst_s * 1000))
    store.append(KIND_GENERATED, "慢的",
                 {"arrival": "a", "working": "b", "handover": "c", "engine": "x"},
                 source="test", ts_unix_ms=now - 1_000)
    assert twinlink.build_view(store, now_ms=now)["people"][0]["tier"] == "fresh"


def test_negctl_stale_person_is_not_fresh(store: TwinStore) -> None:
    """負控制：三小時前生成的人**不可以**被標成 `fresh`，否則分級毫無意義。"""
    now = 1_800_000_000_000
    _person(store, "三小時前", ms=now - 3 * 3600_000)
    view = twinlink.build_view(store, now_ms=now)
    assert view["people"][0]["tier"] == "ambient"
    assert view["counts"]["fresh"] == 0


# ---------------------------------------------------------------------------
# 二、`total`／`today`：畫面要講得出「今天來過 N 位」
# ---------------------------------------------------------------------------

def test_total_counts_everyone_even_after_retirement(store: TwinStore) -> None:
    now = 1_800_000_000_000
    _crowd(store, 80, now_ms=now)
    view = twinlink.build_view(store, recent=10, record_retire=True, now_ms=now)
    assert view["counts"]["total"] == 80, "total 必須是整場來過幾位，不是畫面上幾位"
    assert view["counts"]["shown"] == 10
    assert view["counts"]["retired"] == 70
    # 退役之後再算一次，total 不會縮水
    assert twinlink.build_view(store, recent=10, now_ms=now)["counts"]["total"] == 80


def test_today_uses_local_midnight_not_utc(store: TwinStore) -> None:
    """「今天」用展場本機時區切。

    負控制：三天前來的人**不可以**算進今天——不然這個數字沒有資訊。
    """
    import datetime as _dt
    now_dt = _dt.datetime.now().astimezone()
    now = int(now_dt.timestamp() * 1000)
    _person(store, "今天來的", ms=now - 60_000)
    _person(store, "三天前來的", ms=now - 3 * DAY)

    view = twinlink.build_view(store, now_ms=now)
    assert view["counts"]["total"] == 2
    assert view["counts"]["today"] == 1, "把三天前的人算進今天了"
    assert view["day"]["start_utc_ms"] <= now
    # 本機時區真的有被用到（UTC 會讓偏移永遠是 0，那就看不出差別）
    off = int(now_dt.utcoffset().total_seconds() // 60) if now_dt.utcoffset() else 0
    assert view["day"]["tz_offset_minutes"] == off


# ---------------------------------------------------------------------------
# 三、退役（展覽設計 §5.1-7「要給結束一個形狀」）
# ---------------------------------------------------------------------------

def test_retirement_is_visible_and_on_chain(store: TwinStore) -> None:
    """退役要**看得見**：告別詞上鏈、畫面拿得到，不是靜靜消失。"""
    now = 1_800_000_000_000
    _crowd(store, 30, now_ms=now)
    view = twinlink.build_view(store, recent=5, record_retire=True, now_ms=now)

    ret = view["retirement"]
    assert ret["retired_total"] == 25
    # 25 個一起退 ⇒ 電視演不下 25 次個別退場（180 秒寬限只有 6 格）。
    # 掛得出去的是 RETIRE_SHOW_MAX 個，其餘用 `retiring_pending` 交代。
    assert len(ret["retiring"]) == twinlink.RETIRE_SHOW_MAX
    assert ret["retiring_pending"] == 25 - twinlink.RETIRE_SHOW_MAX
    assert ret["bulk"] is True
    assert all(r["farewell"] for r in ret["retiring"]), "沒有告別詞＝靜靜消失"
    assert all(r["reason"] for r in ret["retiring"])
    # 「螢幕演過他了」**我們量不到** ⇒ null，不准寫 false
    assert all(r["screen_confirmed"] is None for r in ret["retiring"])

    # 帳本上真的有那一列，而且看得出是誰退的
    notes = [e for e in store.events(kind=KIND_NOTE)
             if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK]
    assert len(notes) == 25
    assert notes[0]["payload"]["farewell"] == f"{notes[0]['sub_id']} 交件"
    assert notes[0]["source"] == "local:twinlink.retire"


def test_retirement_is_not_erasure(store: TwinStore) -> None:
    """🔴 **退役 ≠ 刪除。** 混講就是對觀眾說錯話。"""
    now = 1_800_000_000_000
    _crowd(store, 30, now_ms=now)
    before = store.count()
    twinlink.build_view(store, recent=5, record_retire=True, now_ms=now)

    assert store.count() > before, "退役竟然讓事件變少了——那是刪除不是退役"
    assert store.verify()["ok"] is True, "退役把鏈弄壞了"
    assert len(list(store.events(sub_id="old0000"))) >= 2, "退役的人事件被拿掉了"
    assert store.current("old0000")["status"] == "generated"
    # 他只是不上螢幕，不是不存在：roster 照樣有他，卡照樣讀得出來。
    # ⚠ `recent=0`（關窗）**不會**把已退役的人撈回畫面——退役是單向的，
    #    那是刻意的（演完退場又出現＝那個儀式沒有意義）。
    assert any(c["sub_id"] == "old0000" for c in store.roster())
    assert store.current("old0000")["card"] == {"need": "事:old0000"}
    assert all(p["id"] != "old0000"
               for p in twinlink.build_view(store, recent=0, now_ms=now)["people"])


def test_retiring_falls_out_of_the_list_after_the_grace(store: TwinStore) -> None:
    """告別掛 `RETIRE_GRACE_S` 秒就下架——不然第七天的 `retiring[]` 會有 300 個人。

    正控制（寬限內看得到）＋負控制（寬限外看不到）成對。
    """
    now = 1_800_000_000_000
    _crowd(store, 12, now_ms=now)
    twinlink.build_view(store, recent=2, record_retire=True, now_ms=now)

    inside = twinlink.build_view(store, recent=2, now_ms=now + 10_000)
    assert len(inside["retirement"]["retiring"]) == 10
    assert inside["retirement"]["bulk"] is False   # 10 < RETIRE_SHOW_MAX

    later = now + int(twinlink.RETIRE_GRACE_S * 1000) + 60_000
    outside = twinlink.build_view(store, recent=2, now_ms=later)
    assert outside["retirement"]["retiring"] == []
    assert outside["retirement"]["retiring_pending"] == 0
    assert outside["retirement"]["retired_total"] == 10, "下架 ≠ 沒退役過"


def test_bulk_retirement_stays_screen_playable(store: TwinStore) -> None:
    """🔴 **第一次上線一定會發生的那一輪**：庫裡已經有幾百人，一口氣退掉。

    判準仍然是觀眾體驗：電視演不下 500 次個別退場（180 秒寬限只有 6 格），
    所以掛得出去的有上限、其餘用一個數字**集體交代**——不是靜靜消失。
    落盤的 JSON 也不可以因此膨脹（實測未設限時 600 人那一輪是 182 KB）。
    """
    now = 1_800_000_000_000
    _crowd(store, 500, now_ms=now)
    view = twinlink.build_view(store, recent=60, record_retire=True, now_ms=now)

    ret = view["retirement"]
    assert ret["retired_total"] == 440
    assert len(ret["retiring"]) == twinlink.RETIRE_SHOW_MAX
    assert ret["retiring_pending"] == 440 - twinlink.RETIRE_SHOW_MAX
    assert ret["bulk"] is True
    # 帳本上每一位都有自己那一列，**一個都沒有被省略**
    notes = [e for e in store.events(kind=KIND_NOTE)
             if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK]
    assert len(notes) == 440
    # 畫面那份 JSON 不因為大批退役而爆掉
    payload = json.dumps(view, ensure_ascii=False)
    assert len(payload.encode()) < 200_000, f"JSON {len(payload.encode())} bytes 太大"


def test_read_only_paths_never_write(store: TwinStore) -> None:
    """負控制：`record_retire=False` 的那一條路**一列都不可以寫**。

    `serve` 用 `mode=ro` 開庫，這裡多寫一列＝現場的唯讀端點直接 500。
    """
    now = 1_800_000_000_000
    _crowd(store, 40, now_ms=now)
    before = store.count()
    view = twinlink.build_view(store, recent=5, record_retire=False, now_ms=now)
    assert store.count() == before, "唯讀路徑寫了東西"
    assert view["retirement"]["recorded_here"] is False
    assert view["retirement"]["retired_total"] == 0
    # 但視窗照樣有效：唯讀不等於沒有視窗
    assert len(view["people"]) == 5


def test_retirement_is_one_way(store: TwinStore) -> None:
    """退役是單向的：重新生成不會把人撈回螢幕（不然退場演完又出現）。"""
    now = 1_800_000_000_000
    _crowd(store, 20, now_ms=now)
    twinlink.build_view(store, recent=3, record_retire=True, now_ms=now)

    store.append(KIND_GENERATED, "old0000",
                 {"arrival": "我又來了", "working": "做", "handover": "交",
                  "engine": "x"}, source="test", ts_unix_ms=now)
    view = twinlink.build_view(store, recent=3, now_ms=now)
    assert all(p["id"] != "old0000" for p in view["people"])


def test_recent_zero_is_the_explicit_escape_hatch(store: TwinStore) -> None:
    """`--recent 0` ＝ 明示關窗：全部都在，而且**一個人都不退役**。"""
    now = 1_800_000_000_000
    _crowd(store, 50, now_ms=now)
    before = store.count()
    view = twinlink.build_view(store, recent=0, record_retire=True, now_ms=now)
    assert len(view["people"]) == 50
    assert view["counts"]["retired"] == 0
    assert store.count() == before, "關窗竟然還退役了人"


# ---------------------------------------------------------------------------
# 三之二、🔴 視窗**不可以**弄壞電視那端的對帳
# ---------------------------------------------------------------------------

def test_window_must_not_break_the_tv_reconciliation(store: TwinStore) -> None:
    """🔴 **這是這個改動自己製造出來的回歸，不是本來就有的坑。**

    電視那端（`vacant_hm/world3/bridge.js`）有一本「公網來的卡待對帳帳本」，
    核銷條件寫死是「本機視圖裡真的看得到那個 id」，而它的 `localIds` **只從
    `people[]` 來**（`reconcile(localIds)` ← `subsFromView(data)`）。

    加視窗之前 `people` ＝ 全部的人 ⇒ 一定核銷得掉。加了之後就不一定了，
    而核銷不掉的帳本**只增不減、每 15 秒重送一次**。所以視圖要另外給一份
    不受視窗影響的 id 集合：`roster_ids`。

    這裡用最惡劣的那一位當樣本：**生成卡住的人**（`arriving`，永遠不退役，
    但前面壓了一堆更新的人 ⇒ 進不了畫面）。
    """
    now = 1_800_000_000_000
    # 他很早就投了卡，分身一直沒生出來
    _person(store, "卡住的那位", ms=now - 5 * DAY, generated=False)
    _crowd(store, 200, now_ms=now, days_ago=1)

    view = twinlink.build_view(store, recent=60, record_retire=True, now_ms=now)
    people_ids = {p["id"] for p in view["people"]}

    # 負控制：證明這個量法有鑑別力——他**真的**不在畫面上，
    # 所以「對 people 核銷」這條路對他確實是死的。
    assert "卡住的那位" not in people_ids, "負控制失效：他還在畫面上，這個測試沒在測東西"
    # 而且他也**沒有**被退役（他還沒輪到，不是演完了）
    assert all(r["id"] != "卡住的那位" for r in view["retirement"]["retiring"])

    # 正題：對帳要對得到他
    assert "卡住的那位" in view["roster_ids"], "電視那端永遠核銷不掉他"
    assert len(view["roster_ids"]) == view["counts"]["total"] == 201
    # 已退役的人也要在裡面（退役 ≠ 不存在，帳一樣要銷得掉）
    retired_ids = {e["sub_id"] for e in store.events(kind=KIND_NOTE)
                   if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK}
    assert retired_ids, "這一輪根本沒人退役，下面那條就沒在測東西"
    assert retired_ids <= set(view["roster_ids"])
    # 契約要講出來，不然對面只能用猜的
    assert view["screen_contract"]["reconcile_against"] == "roster_ids"


def test_roster_ids_is_not_a_way_to_bypass_the_window(store: TwinStore) -> None:
    """負控制：`roster_ids` **只是 id**，拿不到卡也拿不到分身。

    如果它帶著 `card`／`arrival`，對面就能直接拿它生分身 ⇒ 視窗被繞掉、
    第七天又從第一個人重演。所以它必須是**純字串陣列**。
    """
    now = 1_800_000_000_000
    _crowd(store, 30, now_ms=now)
    view = twinlink.build_view(store, recent=5, now_ms=now)
    assert all(isinstance(i, str) for i in view["roster_ids"])
    assert len(view["people"]) == 5 < len(view["roster_ids"]) == 30


# ---------------------------------------------------------------------------
# 四、🔴 產品路徑：不是「旗標存在」，是「展場真的會呼叫到」
# ---------------------------------------------------------------------------

#: ⚠ **`no_proxy=*` 在這裡不是裝飾，是量具的修正。**
#:
#: 這批 CLI 測試第一次跑的時候 `test_loop_cli_passes_the_window` **逾時 180 秒**，
#: 而它連的是 `http://127.0.0.1:1`——一個必定連不上的位址。直覺的結論是
#: 「死位址不會快速拒絕，把 timeout 調大」，那是**錯的**：量出來連線本身
#: （connection refused）是 **0.00 秒**，付錢的是 `urllib.request.getproxies()`
#: ——macOS 上那是一次 SystemConfiguration 查詢，本機實測單次 **1.4～206 秒**
#: （間歇，reps=6 那一輪最大 119.83），而且**每個新行程的第一通 HTTP 都要付一次**。
#:
#: CPython 的 `getproxies()` ＝ `getproxies_environment() or getproxies_macosx_sysconf()`。
#: 環境裡只要有任何 `*_proxy` 變數（`no_proxy` 也算），前者就回非空字典，
#: **整段跳過** OS 那次查詢；`proxy_bypass()` 同樣改走 env 分支。
#: 設成 `*` ⇒ 不經任何 proxy，直連、快速拒絕。
#:
#: 證據＋負控制（換一個不以 `_proxy` 結尾的變數名，改善必須消失）：
#: `ops/exhibit/twin/probe_proxy_stall.py`、`evidence_window_20260921/proxy_stall_mac_*.json`。
#: ⚠ 展場那台是 1003（Windows，走 `getproxies_registry`），**沒量過** ⇒ 見報告。
_CLI_ENV = {**os.environ, "no_proxy": "*"}


def _run(args: list[str], db: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "ops/exhibit/twin/twinlink.py", "--db", str(db), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=180, env=_CLI_ENV)


def _seed_yesterday(db: pathlib.Path, n: int) -> None:
    """造 n 個「昨天來的」人（CLI 用真時鐘，所以要把時間戳往前推）。

    ⚠ 不能用「現在」：那樣全部都是 `fresh`，視窗依設計會為了他們撐開
    ——那是**正確行為**，但就量不到 `--recent` 有沒有接上去了。
    """
    import time as _t
    st = TwinStore(db)
    base = int(_t.time() * 1000) - DAY
    for i in range(n):
        _person(st, f"p{i:04d}", ms=base + i * 1000)
    st.close()


def test_export_cli_passes_the_window(tmp_path: pathlib.Path) -> None:
    """`export --recent N` 要真的傳到 `build_view`，落盤的檔案也要只有 N 位。"""
    db = tmp_path / "t.sqlite3"
    _seed_yesterday(db, 12)

    out = tmp_path / "live" / "visitors.json"
    r = _run(["export", "--out", str(out), "--recent", "4"], db)
    assert r.returncode == 0, f"stderr={r.stderr[:400]}"
    res = json.loads(r.stdout)
    assert res["window"]["recent"] == 4
    assert res["visitors"] == 4 and res["total"] == 12
    view = json.loads(out.read_text(encoding="utf-8"))
    assert len(view["people"]) == 4, "旗標印出來了但落盤的檔案沒跟著變"
    assert view["people"][0]["id"] == "p0011", "落盤的不是新到舊"


def test_negctl_export_default_is_already_bounded(tmp_path: pathlib.Path) -> None:
    """負控制：**不給旗標**也要有上限。

    預設值若是「全部」，這個修改在展場就等於不存在——沒有人會記得加旗標。
    """
    db = tmp_path / "t.sqlite3"
    n = twinlink.DEFAULT_RECENT + 25
    _seed_yesterday(db, n)

    out = tmp_path / "visitors.json"
    r = _run(["export", "--out", str(out)], db)
    assert r.returncode == 0, f"stderr={r.stderr[:400]}"
    view = json.loads(out.read_text(encoding="utf-8"))
    assert len(view["people"]) == twinlink.DEFAULT_RECENT, "預設沒有上限"
    assert view["counts"]["total"] == n


def test_loop_cli_passes_the_window(tmp_path: pathlib.Path) -> None:
    """🔴 **展場跑的是 `loop`**（`vacant-exhibit.service`），不是 `export`。

    `loop` 裡漏傳視窗＝旗標存在、產品路徑沒接上去——本 repo 一直在抓的那個病
    （對照 `test_twin_endpoint_resolution.py` 的同型測試）。
    雲端與模型都指到死位址：這條路要在**完全離線**之下也走得完。
    """
    db = tmp_path / "t.sqlite3"
    _seed_yesterday(db, 9)

    out = tmp_path / "visitors.json"
    r = _run(["loop", "--cloud", "http://127.0.0.1:1", "--token", "t",
              "--endpoint", "http://127.0.0.1:1/v1", "--rounds", "1",
              "--interval", "0", "--out", str(out), "--recent", "3"], db)
    assert r.returncode == 0, f"stderr={r.stderr[:400]}"
    line = json.loads(r.stdout.strip().splitlines()[-1])
    assert line["export"]["window"]["recent"] == 3, "loop 沒有把視窗傳給 export"
    view = json.loads(out.read_text(encoding="utf-8"))
    assert len(view["people"]) == 3
    assert view["counts"]["total"] == 9
    # loop 是會寫退役的那一條（展場靠它，§5.1-7 才成立）
    assert view["counts"]["retired"] == 6


def test_loop_no_retire_flag_actually_stops_the_writing(tmp_path: pathlib.Path) -> None:
    """負控制：`--no-retire` 要真的關掉寫入，不然那個旗標是裝飾。"""
    db = tmp_path / "t.sqlite3"
    _seed_yesterday(db, 9)

    out = tmp_path / "visitors.json"
    r = _run(["loop", "--cloud", "http://127.0.0.1:1", "--token", "t",
              "--endpoint", "http://127.0.0.1:1/v1", "--rounds", "1",
              "--interval", "0", "--out", str(out), "--recent", "3",
              "--no-retire"], db)
    assert r.returncode == 0, f"stderr={r.stderr[:400]}"
    view = json.loads(out.read_text(encoding="utf-8"))
    assert len(view["people"]) == 3, "--no-retire 不該關掉視窗，只關掉寫入"
    assert view["counts"]["retired"] == 0
    # ⚠ 只數**退役那一種**事件：同一輪 loop 的 ingest／publish 會因為
    #    雲端是死位址而各寫下 gap／error，那是**應該寫的**，不是這裡要抓的。
    #    數總事件數會抓到它們，那個綠燈就沒有指向性。
    st2 = TwinStore(db)
    try:
        notes = [e for e in st2.events(kind=KIND_NOTE)
                 if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK]
        assert notes == [], "--no-retire 還是把退役寫上鏈了"
        # 正控制（同一個量法，去掉旗標就要量得到）
        r2 = _run(["loop", "--cloud", "http://127.0.0.1:1", "--token", "t",
                   "--endpoint", "http://127.0.0.1:1/v1", "--rounds", "1",
                   "--interval", "0", "--out", str(out), "--recent", "3"], db)
        assert r2.returncode == 0, f"stderr={r2.stderr[:400]}"
    finally:
        st2.close()
    st3 = TwinStore(db)
    try:
        notes = [e for e in st3.events(kind=KIND_NOTE)
                 if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK]
        assert len(notes) == 6, "正控制失效：這個量法根本量不到退役"
    finally:
        st3.close()


def test_serve_cli_accepts_and_forwards_the_window() -> None:
    """`serve` 那條唯讀路也要吃得到視窗，而且**永遠不寫**。

    用 AST 查呼叫點（起 HTTP server 在測試裡太吵），但查的是**產品碼**不是測試碼：
    `serve` 內對 `build_view` 的呼叫必須同時帶 `recent` 與 `record_retire=False`。
    """
    import ast
    src = (ROOT / "ops/exhibit/twin/twinlink.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "serve")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "build_view"]
    assert calls, "serve 沒有呼叫 build_view？"
    for c in calls:
        kw = {k.arg: k.value for k in c.keywords}
        assert "recent" in kw, "serve 沒把 --recent 傳下去"
        assert isinstance(kw.get("record_retire"), ast.Constant) \
            and kw["record_retire"].value is False, "serve 竟然可能寫退役（庫是 mode=ro）"


def test_selftest_still_green() -> None:
    """正控制：這一支自己的離線自檢（含視窗與退役那兩節）要全綠。"""
    # 同樣帶 `_CLI_ENV`：selftest 第 5／6 節故意連死位址，會付上面那筆 proxy 查詢
    r = subprocess.run([sys.executable, "ops/exhibit/twin/twinlink.py", "selftest"],
                       cwd=ROOT, capture_output=True, text=True, timeout=180,
                       env=_CLI_ENV)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-800:]
    assert "全綠" in r.stdout
