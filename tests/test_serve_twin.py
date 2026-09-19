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
    # ⚠ **一格現在有兩串事件**（ON／OFF），所以要指名 ON 那一臂。
    #   不指名的話後發的 OFF 會蓋掉 ON——而 OFF 的 `accepted` 恆為 null
    #   （那一臂沒有閘門、沒有裁決）。這個坑電視那一端也踩過同一次。
    def on_verdict(tid):
        return next(e for e in evs if e["type"] == "verdict"
                    and e["task_id"] == tid and e.get("arm", "ON") == "ON")
    assert on_verdict(held)["accepted"] is False
    assert on_verdict(pc)["accepted"] is True
    # 而 OFF 那一臂**不准**有裁決
    for e in evs:
        if e["type"] == "verdict" and e.get("arm") == "OFF":
            assert e["accepted"] is None


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


def test_phone_node_check_is_runnable_offline():
    """手機頁那一段判準有自己的 node check，而且離線也跑得過。

    ⚠ 這一條只保證「那一支存在而且跑得動」。它說的每一句話在
    `ops/exhibit/twin/phone_node_check.mjs` 裡，不在這裡重寫一份——
    兩份判準遲早會分岔，而分岔的時候沒有人會發現。
    """
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("沒有 node")
    r = subprocess.run(
        ["node", str(ROOT / "ops" / "exhibit" / "twin" / "phone_node_check.mjs")],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "全部通過" in r.stdout


# ── 翻位元的狀態會自己過期 ──────────────────────────────────────
def test_tamper_clears_when_the_tv_moves_on(pack, tmp_path):
    """實測抓到的謊：**舊狀態不會清**。

    `tamper` 舊版只能靠明確呼叫 `untamper` 清掉，而無人值守的展場沒有人會按。
    第一個觀眾按完走掉，導播列那一行留在螢幕上 4 分半，對後面每一位觀眾
    指著一格他們沒看到的東西。它不是捏造，是沒有人來收。
    """
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    stage.advance()
    first = stage.now["cell_id"]
    assert stage.press("tamper")["ok"]
    assert stage.tamper["cell_id"] == first
    # 同一格還在演 ⇒ 留著
    assert stage.state()["tamper"]["cell_id"] == first
    # 電視換格 ⇒ 當場清掉（那句話沒有指涉對象了）
    stage.advance()
    assert stage.now["cell_id"] != first
    assert stage.tamper is None
    assert stage.state()["tamper"] is None


def test_tamper_expires_on_its_own(pack, tmp_path, monkeypatch):
    """就算電視沒換格，翻位元也會過期：那是瞬間動作，不是狀態。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    stage.advance()
    stage.press("tamper")
    assert stage.state()["tamper"] is not None
    # 把時鐘往前撥超過 TTL（不真的等 45 秒）
    stage.tamper_mono -= S.TAMPER_TTL_S + 1
    assert stage.state()["tamper"] is None


def test_tamper_state_always_matches_the_cell_on_screen(pack, tmp_path):
    """`/state` 給出去的 tamper，`cell_id` 必定等於 `now.cell_id`（或為 None）。

    這一條是那個謊的**通用形式**：電視與手機都從 `/state` 讀，
    只要這個不變量成立，兩端都不可能指著一格沒人在看的東西。
    """
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    for k in range(len(stage.flat)):
        stage.advance()
        if k % 3 == 0:
            stage.press("tamper")
        st = stage.state()
        if st["tamper"]:
            assert st["tamper"]["cell_id"] == st["now"]["cell_id"], k


def test_now_carries_why_so_the_tv_can_tell_a_press_from_autoplay(pack, tmp_path):
    """電視要分得出「人按的」與「機器自己播的」：人按的要插隊，輪播不插隊。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                                dwell=10_000, quiet=True)
    assert stage.advance()["now"]["why"] == "autoplay"
    assert stage.press("held")["now"]["why"] == "phone"
    assert stage.press("next")["now"]["why"] == "autoplay"   # next ⇒ 走排程
    assert stage.state()["now"]["why"] in ("autoplay", "phone")


# ── QR 一定要指到手機連得到的地方 ───────────────────────────────
def test_qr_encodes_the_runtime_phone_url(pack, tmp_path):
    """**展場當天最會壞的一格。**

    舊的 `world3/qr.png` 是 2026-08-30 的靜態佔位圖（比 `phone.html` 早三個星期），
    而 `--bind 0.0.0.0` 之後手機要連的是展場那台機器的區網 IP、每次開機可能不同。
    ⇒ QR 的內容必須是**執行期** `base_url` 算出來的那一個網址。
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from ops.exhibit.twin import qr as qrlib
    out = tmp_path / "ev.jsonl"
    srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out, dwell=10_000,
                               quiet=True, base_url="http://192.168.1.23:8899")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        c = Client(f"http://127.0.0.1:{srv.server_address[1]}")
        st = c.get_json("/state")
        assert st["phone_url"] == "http://192.168.1.23:8899/phone.html"
        assert "127.0.0.1" not in st["phone_url"]
        code, headers, body = c.get("/qr.png")
        assert code == 200 and headers["Content-Type"] == "image/png"
        assert body[:8] == b"\x89PNG\r\n\x1a\n"
        # 那張圖真的是那個網址畫出來的（逐 byte 相同）
        assert body == qrlib.to_png(st["phone_url"], scale=8)
        code, headers, body = c.get("/qr.svg")
        assert code == 200 and "image/svg+xml" in headers["Content-Type"]
        assert b"<svg" in body
    finally:
        srv.shutdown()
        srv.server_close()


def test_receipt_urls_use_the_same_base_as_the_qr(pack, tmp_path):
    """收據網址與 QR 要指到同一台。兩邊各自組字串遲早會分岔。"""
    out = tmp_path / "ev.jsonl"
    _srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out, dwell=10_000,
                                quiet=True, base_url="http://10.0.0.7:8899")
    res = stage.advance()
    assert res["now"]["receipt_url"].startswith("http://10.0.0.7:8899/r/")
    assert stage.phone_url().startswith("http://10.0.0.7:8899/")


# ── `--token` 預設開啟（DECISION_20260919_EXHIBIT_UNATTENDED.md §一）──────────
#
# 展場的 `exhibit_boot.sh --lan` 把 serve_twin 綁到 0.0.0.0。舊的預設是
# 「`--token` 可選、預設空＝不驗」⇒ 同一個區網（展場 hotspot）上任何人都按得動
# 那台電視。這一組把新的預設釘死。
#
# ⚠ 口徑：token **不是身分驗證**。看得到電視的人都拿得到它（它就印在 QR 裡）。
#   它擋的是「連上同一個 hotspot、但沒站在展件前面」的人。測試只測這件事。

def test_lan_bind_gets_a_token_without_anybody_asking():
    """展場的那一種綁法，沒給 token 也**一定**會有一把。"""
    tok, why = S.resolve_token("0.0.0.0", "", False)
    assert why == "auto"
    assert len(tok) >= 10          # secrets.token_urlsafe(9)
    # 每一次都不一樣（不是寫死的一把）
    assert tok != S.resolve_token("0.0.0.0", "", False)[0]


def test_loopback_bind_stays_tokenless_so_local_dev_is_not_annoying():
    for bind in ("127.0.0.1", "::1", "localhost"):
        assert S.resolve_token(bind, "", False) == ("", "off-loopback")


def test_an_explicit_token_wins_and_no_token_must_be_explicit():
    assert S.resolve_token("0.0.0.0", "abc", False) == ("abc", "given")
    assert S.resolve_token("0.0.0.0", "", True) == ("", "off-explicit")
    # `--token` 與 `--no-token` 同時給：明確給的那把贏（不要靜靜關掉門檻）
    assert S.resolve_token("0.0.0.0", "abc", True) == ("abc", "given")


def _tokened(pack, tmp_path, token="s3cr3t", base="http://192.168.1.23:8899"):
    out = tmp_path / "ev.jsonl"
    srv, stage = S.make_server(pack, bind="127.0.0.1", port=0, out=out,
                               dwell=10_000, quiet=True, token=token,
                               base_url=base)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, stage, Client(f"http://127.0.0.1:{srv.server_address[1]}")


def test_control_is_403_without_the_token_and_200_with_it(pack, tmp_path):
    srv, _stage, c = _tokened(pack, tmp_path)
    try:
        code, res = c.post({"action": "next"})
        assert code == 403 and res["ok"] is False
        code, res = c.post({"action": "next", "token": "wrong"})
        assert code == 403
        code, res = c.post({"action": "next", "token": "s3cr3t"})
        assert code == 200 and res["ok"] is True
    finally:
        srv.shutdown(); srv.server_close()


def test_the_qr_carries_the_token_or_the_phone_cannot_press_anything(pack, tmp_path):
    """QR 是觀眾唯一的入口。token 沒編進去＝掃了進來一顆鍵都按不動。"""
    srv, stage, c = _tokened(pack, tmp_path)
    try:
        assert stage.phone_url() == "http://192.168.1.23:8899/phone.html?t=s3cr3t"
        st = c.get_json("/state")                     # 從 loopback 打（＝電視）
        assert st["phone_url"].endswith("?t=s3cr3t")
        assert st["control_token_required"] is True
    finally:
        srv.shutdown(); srv.server_close()


def test_state_does_not_hand_the_token_to_the_rest_of_the_lan(pack, tmp_path):
    """否則 token 只是**一個 GET 的距離**，等於沒有。

    這裡直接測那個純函數的分流（`with_token=False`）：整合層的判準是
    `venue_check.sh` 第七節，它從這台機器的區網位址真的打一次 `/state`。
    """
    _srv, stage, _c = _tokened(pack, tmp_path)
    try:
        assert "t=" not in stage.phone_url(with_token=False)
        assert "t=" not in stage.state(with_token=False)["phone_url"]
        # 但「有沒有門檻」這件事可以講（不講手機不知道要帶什麼）
        assert stage.state(with_token=False)["control_token_required"] is True
    finally:
        _srv.shutdown(); _srv.server_close()


def test_token_also_accepted_from_query_and_header(pack, tmp_path):
    """少一條，展場當天就是「怎麼按都沒反應」。"""
    srv, _stage, c = _tokened(pack, tmp_path)
    try:
        req = urllib.request.Request(
            c.base + "/control?t=s3cr3t",
            data=json.dumps({"action": "next"}).encode(),
            headers={"content-type": "application/json"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 200
        req = urllib.request.Request(
            c.base + "/control", data=json.dumps({"action": "next"}).encode(),
            headers={"content-type": "application/json",
                     "X-Twin-Token": "s3cr3t"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 200
    finally:
        srv.shutdown(); srv.server_close()


def test_read_only_endpoints_stay_open_because_the_tv_has_no_token(pack, tmp_path):
    """電視、收據頁、事件流都不帶 token。把讀也擋住＝電視自己黑掉。"""
    srv, _stage, c = _tokened(pack, tmp_path)
    try:
        for p in ("/state", "/live/events.jsonl", "/phone.html", "/viewer.html",
                  "/qr.png"):
            assert c.get(p)[0] == 200, p
    finally:
        srv.shutdown(); srv.server_close()


def test_phone_page_sends_the_token_it_was_scanned_with():
    """`phone.html` 一定要從自己的網址讀 `t=` 並帶進 POST。

    漏掉這一行＝伺服器有門檻、手機沒有鑰匙，展場現象是「三顆鍵全部按不動」，
    而畫面上不會說是為什麼。
    """
    html = (ROOT / "ops" / "exhibit" / "twin" / "phone.html").read_text("utf-8")
    assert 'URLSearchParams(location.search).get("t")' in html
    assert "JSON.stringify({ action, token: TOKEN })" in html
    # 403 要講人話（那一定是「上一次開機留下來的分頁」）
    assert "重新掃電視上的 QR" in html


# ── 區網 IP 偵測（DECISION_20260919_EXHIBIT_UNATTENDED.md §五-1）────────────
#
# 這一組守的是一個**真的發生過**的事故形狀：`exhibit_boot.sh` 裡算區網 IP 的
# 那一段在 2026-09-19 之前**從來沒有被執行過**（它只有加 `--lan` 才會跑），
# 只被「讀碼讀出來」寫進紀錄。真的跑下去是 `set -euo pipefail` 底下當場斷掉
# ——**exit 1、一個字都不印**，在 systemd 底下就是無限重啟而 journal 什麼都沒有。
#
# 所以這裡釘的不是「它抓到哪個位址」（那跟跑測試的機器有關，釘不得），
# 而是**離開碼的契約**：0＝抓到並印出來、2＝抓不到但說了為什麼。
# **1 永遠是 bug**：那代表又有一條路徑安靜地斷掉了。

BOOT_SH = ROOT / "ops" / "exhibit" / "twin" / "exhibit_boot.sh"


def _print_host(*args):
    import subprocess
    return subprocess.run(
        ["bash", str(BOOT_SH), "--print-host", *args],
        capture_output=True, text=True, timeout=60)


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_lan_detection_never_dies_silently():
    """**這一條就是那個 bug 的形狀。**

    `exit 1` ＋ 空輸出 ＝ 腳本在某處被 `set -e` 砍掉而沒有人知道。
    fail-closed 的意思是「拒絕啟動**並說明**」，不是「安靜地不見」。
    """
    r = _print_host("--lan")
    assert r.returncode in (0, 2), (
        f"--lan --print-host 回 {r.returncode}（只准 0 或 2）\n"
        f"stdout={r.stdout!r} stderr={r.stderr!r}")
    if r.returncode == 2:
        assert r.stderr.strip(), "抓不到區網 IP 的時候**一定要說為什麼**"
    else:
        assert r.stdout.strip(), "回 0 就一定要把位址印在 stdout"


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_loopback_mode_prints_loopback():
    """不帶 `--lan` 就不該去碰那一整段（那是展場才用的路徑）。"""
    r = _print_host()
    assert r.returncode == 0
    assert r.stdout.strip() == "127.0.0.1"


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_unusable_address_is_refused_with_a_reason_not_a_silent_death():
    """指定一個**不能用**的位址 ⇒ 2 ＋ 講理由，不是 1 ＋ 沉默。

    169.254.0.0/16 ＝ link-local。展場手機連不到 ⇒ QR 掃不開 ⇒ 寧可不啟動。
    """
    import os
    env = dict(os.environ, VACANT_LAN_IP="169.254.7.7")
    import subprocess
    r = subprocess.run(["bash", str(BOOT_SH), "--lan", "--print-host"],
                       capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 2, f"回了 {r.returncode}"
    assert "抓不到可用的區網 IP" in r.stderr


@pytest.mark.skipif(not BOOT_SH.exists(), reason="沒有 exhibit_boot.sh")
def test_interface_names_are_not_hardcoded_on_linux():
    """不准再靠猜介面名字。

    舊版寫死 `en0 en1 eth0 wlan0`，而 vacant-dev 的介面叫 `ens33`
    ——名單全部落空。展場機的網卡叫什麼**沒有人保證得了**。
    """
    src = BOOT_SH.read_text(encoding="utf-8")
    assert "addr show scope global" in src, "Linux 那一段要列真的存在的位址"
    # ⚠ 只看**程式碼**，不看註解：解釋那個 bug 的註解裡本來就會寫 `eth0 wlan0`，
    #   那段字**應該留著**（它是為什麼要這樣寫的理由）。把註解一起掃進來，
    #   這一條就會逼人把歷史刪掉才會綠——那是拿判準去換紀錄。
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "eth0" not in code and "wlan0" not in code, "不要再寫死介面名字"
    # 而且那條管線一定要有退路（沒有 `|| true` ＝ pipefail 之下當場斷掉）
    assert "| cut -d/ -f1 | head -1 || true)" in src, (
        "`ip …` 那條管線少了 `|| true`：`ip` 對不存在的介面回 1，"
        "在 `set -o pipefail` 底下會讓整支腳本 exit 1 而且一個字都不印")
