"""展場機那一支伺服器的可執行判準（`ops/exhibit/twin/serve_twin.py`）。

守的是 `decisions/DECISION_20260919_TWIN_LIVE.md` 的接口契約與四條展場鐵律：

- 秒級：一次 POST /control ⇒ 事件檔就長出那一格（零模型呼叫）。
- 離線：只有 stdlib、只綁 loopback、頁面零外部資源。
- 無人值守：沒人按就自己輪播；一圈播完截檔（去重集合不會無限長）。
- 一格沒收尾不准卡死整批（D2）：過不了契約自檢的格子跳過並記下原因。

以及一條口徑紅線：**這一支不得宣告任何驗證結果**（面板不是信任來源）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import serve_twin as S  # noqa: E402
from ops.exhibit.twin import to_events as tolib  # noqa: E402

PACK = ROOT / "ops" / "exhibit" / "twin" / "twin_pack.json"
pytestmark = pytest.mark.skipif(not PACK.exists(), reason="沒有 twin_pack.json")


@pytest.fixture(scope="module")
def pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


class Client:
    def __init__(self, base: str):
        self.base = base

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, dict(r.headers), r.read()

    def get_json(self, path: str):
        return json.loads(self.get(path)[2])

    def post(self, obj: dict):
        req = urllib.request.Request(
            self.base + "/control", data=json.dumps(obj).encode("utf-8"),
            headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def location(self, path: str):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NoRedirect)
        try:
            with op.open(self.base + path) as r:
                return r.status, r.headers.get("Location")
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location")


@pytest.fixture
def server(pack, tmp_path):
    out = tmp_path / "events.jsonl"
    # dwell 很大 ⇒ 測試期間不會有輪播插進來把斷言弄亂。輪播本身另外測。
    srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                               dwell=10_000, quiet=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield Client(f"http://127.0.0.1:{srv.server_address[1]}"), stage, out
    srv.shutdown()
    srv.server_close()


# ── 接口契約 ────────────────────────────────────────────────────
def test_state_has_the_three_buttons(server):
    c, _stage, _out = server
    st = c.get_json("/state")
    actions = [b["action"] for b in st["buttons"]]
    assert actions == ["held", "pc", "tamper"]
    # 前兩顆一定指到**同一題、同一位居民**的兩邊——那才是反事實對照。
    held, pc = st["buttons"][0]["cell_id"], st["buttons"][1]["cell_id"]
    assert held.endswith("__held") and pc.endswith("__pc")
    assert held[:-len("__held")] == pc[:-len("__pc")]


def test_control_appends_exactly_that_cell(server):
    c, _stage, out = server
    st = c.get_json("/state")
    held = st["buttons"][0]["cell_id"]
    code, res = c.post({"action": "held"})
    assert code == 200 and res["ok"] and res["now"]["cell_id"] == held
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").split("\n") if x.strip()]
    assert {e["task_id"] for e in evs} == {held}
    assert [e["type"] for e in evs][0] == "task_opened"
    assert any(e["type"] == "verdict" for e in evs)


def test_both_sides_of_one_pair_are_playable(server):
    c, _stage, out = server
    st = c.get_json("/state")
    held, pc = st["buttons"][0]["cell_id"], st["buttons"][1]["cell_id"]
    c.post({"action": "held"})
    c.post({"action": "pc"})
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").split("\n") if x.strip()]
    ids = [e["task_id"] for e in evs if e["type"] == "task_opened"]
    assert ids == [held, pc]
    # 反事實的兩邊在資料上真的不一樣：一邊擋下、一邊交付。
    verdicts = {e["task_id"]: e for e in evs if e["type"] == "verdict"}
    assert verdicts[held]["accepted"] is False
    assert verdicts[pc]["accepted"] is True


def test_events_are_deduplicable_by_the_tv_key(server):
    """電視的去重鍵是 `ts|type|task_id|arm|reviewer`。撞鍵＝那一格被靜靜吃掉。"""
    c, _stage, out = server
    for _ in range(4):
        c.post({"action": "held"})
        c.post({"action": "pc"})
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").split("\n") if x.strip()]
    keys = [f'{e["ts"]}|{e["type"]}|{e["task_id"]}|{e.get("arm","")}|{e.get("reviewer","")}'
            for e in evs]
    assert len(set(keys)) == len(keys)


def test_per_cell_receipt_redirect(server):
    """C4：每一格指到自己那一頁，不是全批共用一個字串。"""
    c, stage, _out = server
    cid = sorted(stage.pl.cells)[0]
    code, loc = c.location(f"/r/{cid}")
    assert code == 302 and loc == f"/viewer.html#cell={cid}"
    code, loc = c.location(f"/r/{cid}?tamper=1")
    assert loc == f"/viewer.html#cell={cid}&tamper=1"
    from urllib.parse import quote
    assert c.location("/r/" + quote("沒有這一格"))[0] == 404


def test_receipt_url_in_events_is_per_cell(server):
    c, _stage, out = server
    c.post({"action": "held"})
    c.post({"action": "pc"})
    evs = [json.loads(x) for x in out.read_text(encoding="utf-8").split("\n") if x.strip()]
    rec = [e for e in evs if e["type"] == "receipt"]
    assert len(rec) == 2
    assert len({e["verify_url"] for e in rec}) == 2
    for e in rec:
        assert e["verify_url"].endswith("/r/" + e["task_id"])


def test_cors_header_is_present(server):
    """電視在另一個埠（run.sh 的 8420）；沒有這個標頭就一個字都拿不到。"""
    c, _stage, _out = server
    for path in ("/state", "/live/events.jsonl"):
        _code, headers, _body = c.get(path)
        assert headers.get("Access-Control-Allow-Origin") == "*"


def test_viewer_and_phone_are_served(server):
    c, _stage, _out = server
    for path, needle in (("/viewer.html", b"twin-pack"),
                         ("/phone.html", b"charset=\"utf-8\"")):
        code, headers, body = c.get(path)
        assert code == 200
        assert "text/html" in headers["Content-Type"]
        assert needle in body


# ── 無人值守 ────────────────────────────────────────────────────
def test_autoplay_walks_pairs_and_truncates_each_lap(pack, tmp_path):
    """沒人按就自己播；一圈播完截檔（D3：檔案不會一整天無限長）。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    seen = []
    for _ in range(len(stage.flat)):
        res = stage.advance()
        seen.append(res["now"]["cell_id"])
    assert len(set(seen)) == len(stage.pl.cells)      # 一圈把每一格都播到
    assert stage.laps == 0                            # 還沒跨圈
    n_before = len([x for x in out.read_text(encoding="utf-8").split("\n") if x.strip()])
    assert n_before > 0
    # 跨圈：**截檔發生在新的一圈開頭**，剛播完那一格要留著（電視不能抓到空檔案）
    before_ts = stage.ts_ms
    first_of_lap2 = stage.advance()["now"]["cell_id"]
    assert stage.laps == 1
    evs = [x for x in out.read_text(encoding="utf-8").split("\n") if x.strip()]
    assert 0 < len(evs) < n_before
    assert {__import__("json").loads(x)["task_id"] for x in evs} == {first_of_lap2}
    # 下一圈的 ts 還是往前走 ⇒ 截檔不會讓電視重播舊的
    assert stage.ts_ms > before_ts


def test_a_cell_that_never_settles_is_skipped_not_stuck(pack, tmp_path, monkeypatch):
    """D2：`infra_void` 不簽收據也不發裁決。一格收不了尾不准卡死整個佇列。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    bad = sorted(stage.pl.cells)[0]
    real = tolib.events_for_cell

    def broken(cell, **kw):
        evs = real(cell, **kw)
        if cell["cell_id"] == bad:
            return [e for e in evs if e["type"] != "verdict"]   # 模擬 infra_void
        return evs

    monkeypatch.setattr(tolib, "events_for_cell", broken)
    played = []
    for _ in range(len(stage.pl.cells)):
        res = stage.advance()
        if res.get("ok"):
            played.append(res["now"]["cell_id"])
    assert bad not in played
    assert len(played) == len(stage.pl.cells) - 1           # 其餘照播
    assert [s["cell_id"] for s in stage.skipped] == [bad]   # 而且說得出是哪一格
    assert stage.skipped[0]["reason"]                       # 原因不是空的


def test_skipped_cells_show_up_in_state(pack, tmp_path, monkeypatch):
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    real = tolib.events_for_cell
    monkeypatch.setattr(
        tolib, "events_for_cell",
        lambda cell, **kw: [e for e in real(cell, **kw) if e["type"] != "verdict"])
    stage.advance()
    st = stage.state()
    assert st["skipped"] and st["skipped"][0]["reason"]
    assert st["now"] is None                      # 沒收尾的格子不准變成「正在演」


# ── 口徑紅線 ────────────────────────────────────────────────────
def test_tamper_does_not_claim_any_verification_result(server):
    """「翻一個位元」只交出網址。翻、重算、看簽章紅，都在觀眾自己的瀏覽器裡。"""
    c, _stage, _out = server
    c.post({"action": "held"})
    _code, res = c.post({"action": "tamper"})
    tam = res["tamper"]
    assert tam["url"].endswith("?tamper=1")
    joined = json.dumps(res, ensure_ascii=False)
    for banned in ("簽章對不上", "驗證通過", "驗過了", "已驗證"):
        assert banned not in joined
    assert "沒有驗" in tam["note"]


def test_state_never_says_trust(server):
    """展場口徑：用「可究責性 / 讓依賴有根據」，不要用「信任」。"""
    c, _stage, _out = server
    text = json.dumps(c.get_json("/state"), ensure_ascii=False)
    assert "信任" not in text
    phone = (ROOT / "ops" / "exhibit" / "twin" / "phone.html").read_text(encoding="utf-8")
    assert "信任" not in phone


def test_no_model_call_anywhere_in_this_path(server):
    """展場鐵律：現場零模型呼叫。這一支連出網的能力都不該有。"""
    src = (ROOT / "ops" / "exhibit" / "twin" / "serve_twin.py").read_text(encoding="utf-8")
    for banned in ("import requests", "urllib.request", "httpx", "socket.create_connection",
                   "openai", "anthropic"):
        assert banned not in src, banned


def test_phone_page_has_no_external_resource():
    """離線：手機頁不准連任何外部資源（展場沒有網路）。"""
    import re
    html = (ROOT / "ops" / "exhibit" / "twin" / "phone.html").read_text(encoding="utf-8")
    assert '<meta charset="utf-8">' in html
    for m in re.finditer(r'(?:src|href)\s*=\s*"([^"]+)"', html):
        u = m.group(1)
        assert not u.startswith(("http://", "https://", "//")), u
    assert "fonts.googleapis" not in html


# ── to_events 的逐格吐出模式 ─────────────────────────────────────
def test_follow_emits_one_cell_at_a_time(pack, tmp_path):
    out = tmp_path / "follow.jsonl"
    sizes: list[int] = []
    tolib.follow(pack, out, verify_url="/r/{cell}", interval=0,
                 sleep=lambda _s: sizes.append(
                     len([x for x in out.read_text(encoding="utf-8").split("\n") if x.strip()])))
    assert len(sizes) == len(pack["cells"])
    assert sizes == sorted(sizes)                 # 逐格追加，不是一次吐完
    assert sizes[0] < sizes[-1]


def test_verify_url_template_is_per_cell(pack):
    evs = tolib.build(pack, verify_url="/r/{cell}", t0_ms=1_789_000_000_000)
    rec = [e for e in evs if e["type"] == "receipt"]
    assert len({e["verify_url"] for e in rec}) == len(rec)
    # 沒有佔位符就維持舊行為（`file://` 直開整頁那種用法仍然成立）
    evs2 = tolib.build(pack, verify_url="twin_viewer.html", t0_ms=1_789_000_000_000)
    rec2 = [e for e in evs2 if e["type"] == "receipt"]
    assert {e["verify_url"] for e in rec2} == {"twin_viewer.html"}


def test_phone_press_moves_the_autoplay_cursor(pack, tmp_path):
    """人放手之後接下去播的是下一格，不是又回到他剛剛看過的那一格。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    stage.press("pc")                       # 手機把第 0 對的「寫明」那邊叫上來
    nxt = stage.advance()["now"]["cell_id"]  # 放手之後輪播接下去
    assert nxt == stage.pl.pair(1)["held"]
