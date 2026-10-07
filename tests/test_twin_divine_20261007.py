"""P13 通靈版（2026-10-07）：`card.want`、寫信不開 pi、自創的東西不算編造、命盤卡標題、世界的「想試」。

裁決：`decisions/DECISION_20261007_TWIN_DIVINE.md`。守的是：
* `want`（他心裡一直想試、卻還沒試的事）選填；沒有就當沒有；進 TRAITS.md、進原文防呆、進封存的類別、撤回一起刪；
* 段 1 寫信是一通模型呼叫（`twin_letter.py`）：串流／整份 JSON 都收、空回重打、stdout 不印東西、沒有牆鐘逾時；
* G2 對「這是我自己做的」那一行的數字放行，但不放行別行的編造、也不放行印紋名；
* 命盤卡標題在第一行不能當標題時用檔名（過同一把尺）；
* 世界的材料與指令都不替分身列清單（KS-1 逐條）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from ops.exhibit.twin import fortune as fz  # noqa: E402
from ops.exhibit.twin import grounding_gate as gg  # noqa: E402
from ops.exhibit.twin import polaroid, twin_letter, twinagent, twinlink, twinvault  # noqa: E402
from test_twin_agent_run import (  # noqa: E402,F401
    TRAITS_TEXT, _all_bytes_under, _chain_blob, env, upstream,
)
from vacant_network.memory import assert_ks1_clean  # noqa: E402

WANT = "想把一直憋在喉嚨裡的東西唱出來"


# ───────── want ─────────

def test_want_is_an_optional_card_field_in_traits_and_in_the_original_guard() -> None:
    t = twinagent.render_traits({"want": WANT, "shape": "圓潤"}, "")
    assert f"- 他心裡一直想試、卻還沒試的事：{WANT}" in t
    assert "他心裡一直想試" not in twinagent.render_traits({"shape": "圓潤"}, ""), "沒有就當沒有"
    # 拍立得／字幕的原文防呆（≥8 字逐字抄就丟）要把 want 算進去
    assert WANT in polaroid.originals_of({"want": WANT}, None)
    assert polaroid.caption_leaks_original("他想把一直憋在喉嚨裡的東西唱出來", polaroid.originals_of({"want": WANT}, None))
    # 封存類別：want 與 need 同一類（needs）
    assert twinvault.CARD_FIELD_CATEGORY["want"] == "needs"
    # 模型直打的舊退路也讀得到 want（不是只有 agent 那條）
    assert WANT in twinlink.build_prompt({"want": WANT}, None)
    assert WANT[:8] in twinlink.fallback_twin({"want": WANT})["working"]
    assert twinlink.fallback_twin({"want": 123})["engine"] == "fallback_deterministic", "卡的形狀不對不准炸"


def test_withdraw_erases_want_everywhere(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = "sub-通靈-001"
    secret = "想把一件只有自己知道的事交給風"

    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        return 200, {"items": [{"id": sid, "card": {"want": secret, "vibe": "念舊"}, "card_text": TRAITS_TEXT,
                                "ts": 1_900_000_000_000}]}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    twinlink.ingest(st, "http://cloud.invalid", "t")
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1, r
    assert secret.encode("utf-8") in _all_bytes_under(cfg.work_root), "負控制：撤回前，run 目錄裡找得到（TRAITS.md）"
    assert secret not in _chain_blob(st), "鏈上沒有觀眾原文"
    out = twinlink.withdraw(st, sid)
    assert out["ok"] is True and out["fully_erased"] is True
    assert secret.encode("utf-8") not in _all_bytes_under(cfg.work_root)
    assert secret not in _chain_blob(st)
    vault = pathlib.Path(st.vault.plain_dir) if hasattr(st.vault, "plain_dir") else None
    if vault is not None and vault.exists():
        assert secret.encode("utf-8") not in _all_bytes_under(vault.parent)


# ───────── 段 1：寫信是一通模型呼叫 ─────────

class _LetterUp(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    mode = "sse"
    seen: list = []

    def log_message(self, *a):
        return

    def do_POST(self):                                    # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8"))
        type(self).seen.append(body)
        mode = type(self).mode
        if mode == "empty-then-ok" and len(type(self).seen) == 1:
            data = json.dumps({"choices": [{"message": {"content": ""}}]}).encode()
            self._send(data, "application/json")
        elif mode in ("json", "empty-then-ok"):
            data = json.dumps({"choices": [{"message": {"content": "信本文。\n命盤\nMBTI：INFP\n"}}]}).encode()
            self._send(data, "application/json")
        else:
            chunks = [{"choices": [{"delta": {"reasoning_content": "（思考不算）"}}]},
                      {"choices": [{"delta": {"content": "信本文。"}}]},
                      {"choices": [{"delta": {"content": "\n命盤\nMBTI：INFP\n"}}]}]
            payload = "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            self._send(payload.encode("utf-8"), "text/event-stream")

    def _send(self, data: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def letter_server():
    _LetterUp.seen = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _LetterUp)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


@pytest.mark.parametrize("mode", ["sse", "json", "empty-then-ok"])
def test_twin_letter_writes_the_letter_from_one_model_call(letter_server, tmp_path, capsys, mode) -> None:
    _LetterUp.mode = mode
    (tmp_path / "TRAITS.md").write_text(f"- 他心裡一直想試、卻還沒試的事：{WANT}\n", encoding="utf-8")
    rc = twin_letter.write_letter(tmp_path, twinagent.LETTER_SYSTEM_PROMPT, twinagent.LETTER_FIRST_MESSAGE,
                                  letter_server, "m", "k", stall_s=5, attempts=3)
    assert rc == 0
    assert (tmp_path / "信.md").read_text(encoding="utf-8").startswith("信本文。")
    assert "思考不算" not in (tmp_path / "信.md").read_text(encoding="utf-8")
    first = _LetterUp.seen[0]
    assert first["stream"] is True and first["messages"][0]["content"] == twinagent.LETTER_SYSTEM_PROMPT
    assert WANT in first["messages"][1]["content"] and "tools" not in first, "沒有工具"
    assert len(_LetterUp.seen) == (2 if mode == "empty-then-ok" else 1)
    assert capsys.readouterr().out == "", "stdout 不准印東西（pi 的 agent_stdout.log 是 JSON 事件流）"


def test_twin_letter_without_traits_or_with_a_dead_endpoint_fails_cleanly(tmp_path) -> None:
    assert twin_letter.write_letter(tmp_path, "s", "m", "http://127.0.0.1:9", "m", "k", stall_s=1, attempts=1) == 3
    (tmp_path / "TRAITS.md").write_text("x\n", encoding="utf-8")
    assert twin_letter.write_letter(tmp_path, "s", "m", "http://127.0.0.1:9", "m", "k", stall_s=1, attempts=2) == 3
    assert not (tmp_path / "信.md").exists()


def test_twin_letter_has_no_wall_clock_and_goes_through_the_vacant_proxy() -> None:
    src = (ROOT / "ops/exhibit/twin/twin_letter.py").read_text(encoding="utf-8")
    sh = (ROOT / "ops/exhibit/twin/twin_agent.sh").read_text(encoding="utf-8")
    assert '"stream": True' in src and "stall_s" in src
    assert '"$BASE" "$MODEL"' in sh and 'BASE="${VACANT_RUN_PROXY%/}"' in sh, "打的是 vacant run 的中介，不是旁路"


# ───────── G2：自創的東西 ─────────

def test_g2_self_made_line_exempts_its_numbers_but_nothing_else() -> None:
    hay = ["石頭上刻著 63 撮"]
    ok = [("成品.md", "我捏了一個哨子，這是我自己做的，長 12 指，刻了 9 道。\n後來哨子的 12 指那一頭裂了。\n")]
    assert gg.check_source(ok, hay) == []
    bad = [("成品.md", "我捏了一個哨子，長 12 指。\n")]                       # 沒明講是自己做的 ⇒ 照擋
    assert [i["line"] for i in gg.check_source(bad, hay)] == [1]
    other = [("成品.md", "這是我自己做的，長 12 指。\n石頭上刻著 77 撮。\n")]      # 免的是那個數字，不是整份
    assert [i["line"] for i in gg.check_source(other, hay)] == [2]
    mark = [("成品.md", "這是我自己做的，印紋：魚骨。\n")]                     # 不免印紋名
    assert gg.check_source(mark, hay) != []
    # 地上有的數字照舊要對得上；自己做的那一行不會讓別的東西「被讀過」
    assert gg.check_source([("成品.md", "石頭上刻著 63 撮。\n")], hay) == []


def test_g3_and_g4_still_bite_on_a_self_made_line() -> None:
    facts = gg.load_facts()
    read = {"地上/紙卡地/格狀圖.txt"}
    arts = [("成品.md", "這是我自己做的小卡，第四列：6 張。\n")]
    assert gg.check_agree(arts, read, facts), "對登記實體說了和權威不同的值：照擋"
    assert gg.check_receipt([("成品.md", "這是我自己做的，閘門通過了，我拿到收據。\n")], []), "自編收據照擋"


# ───────── 命盤卡標題 ─────────

def test_title_falls_back_to_the_file_name_when_the_first_line_is_a_sentence() -> None:
    f = fz.resolve({"mbti": "ISFP", "mbti_source": "ai", "zodiac": "天秤", "blood": "O"}, {})
    sentence = "這是我自己做的陶哨子。它很小，只有指節長度，顏色是奶油色的黏土捏的。"
    assert fz.title_of({"奶油色微型陶哨子.md": sentence}, f) == "奶油色微型陶哨子"
    assert fz.title_of({"成品.md": sentence}, f) is None, "泛稱的檔名不是這樣東西的名字"
    assert fz.title_of({"試的紀錄.md": sentence}, f) is None
    assert fz.title_of({"給伴侶的小卡.md": sentence}, f) is None, "檔名也過現實詞"
    assert fz.title_of({"雙子座的燈.md": sentence}, f) is None, "沒給的星座不准出現（天秤不是雙子）"
    assert fz.title_of({"哨子.md": "# 一盞點亮的燈\n內文"}, f) == "一盞點亮的燈", "第一行能當標題就用第一行"
    assert fz.title_of({"共鳴音符.md": "這是我自己做的。\n它是一個音符"}, f) == "共鳴音符", "「這是我自己做的」是標記句不是名字"


# ───────── 世界的「想試」 ─────────

def test_the_world_prompt_gives_no_list_and_the_card_says_what_it_is() -> None:
    for text in (twinagent.SYSTEM_PROMPT, twinagent.FIRST_MESSAGE, twinagent.LETTER_SYSTEM_PROMPT,
                 twinagent.LETTER_FIRST_MESSAGE):
        assert_ks1_clean(text)
    world = (ROOT / "ops/exhibit/twin/world/WORLD.md").read_text(encoding="utf-8")
    for must in ("一小點橘色", "水很少", "手邊沒有的東西，就用土、紙和線捏一個出來", "心裡都有一件一直擱著的事",
                 "試過的事，試完寫在一張紙上", "先讓他自己選一件事去試", "沒有太陽", "閘門的背面，沒有人細看過"):
        assert must in world, must
    # 指令不替分身列「可以試的事」：沒有任何地上物件的名字
    from ops.exhibit.twin import twinground
    names = [pathlib.PurePath(rel).stem for rel in twinground.pool()]
    assert [n for n in names if len(n) >= 3 and n in twinagent.SYSTEM_PROMPT] == []


def test_twin_letter_stall_watchdog_cuts_a_server_that_keeps_the_line_open_but_sends_nothing(tmp_path) -> None:
    """P13 真跑：寫信那一通在中介後面掛了 2500–3600 秒。守衛：連續 stall_s 秒沒有 data: 行就關連線重打。"""
    import time

    class Hang(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        n = 0

        def log_message(self, *a):
            return

        def do_POST(self):                                # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            type(self).n += 1
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if type(self).n == 1:                          # 第一次：吐標頭與保活註解行，之後什麼都不給
                try:
                    for _ in range(30):
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        time.sleep(0.5)
                except OSError:
                    pass
                return
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": "好的信。"}}]}) + "\n\ndata: [DONE]\n\n").encode())
            self.wfile.flush()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Hang)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
    try:
        (tmp_path / "TRAITS.md").write_text("x\n", encoding="utf-8")
        t0 = time.time()
        rc = twin_letter.write_letter(tmp_path, "s", "m", f"http://127.0.0.1:{srv.server_address[1]}", "m", "k",
                                      stall_s=2, attempts=2)
        assert rc == 0 and (tmp_path / "信.md").read_text(encoding="utf-8").startswith("好的信")
        assert Hang.n == 2 and time.time() - t0 < 12, "保活註解行不算動靜；2 秒沒有 data: 就重打"
    finally:
        srv.shutdown()
        srv.server_close()


def test_g1_path_followed_by_prose_is_cut_at_the_folder_or_the_file_extension() -> None:
    """真跑 v6：『地上/長桌廣場/土堆/裡那些被遺棄卻沒人捨得丟的東西』被整串當成路徑 ⇒ 「地上沒有這個檔」誤擋。"""
    gf = ["地上/長桌廣場/土堆/小陶印.txt", "地上/投遞口/缺角的信.txt"]
    plan = "試\n\n為什麼是他：我看到地上/長桌廣場/土堆/裡那些被遺棄卻沒人捨得丟的東西，還有地上/投遞口/缺角的信.txt這封信。\n"
    named = gg.named_paths(plan, gf)
    assert [(n["path"], n["kind"]) for n in named] == [("地上/長桌廣場/土堆", "folder"), ("地上/投遞口/缺角的信.txt", "file")]
    assert gg.check_read(plan, {"地上/長桌廣場/土堆/小陶印.txt", "地上/投遞口/缺角的信.txt"}, gf) == []
    # 負控制：點名了卻沒打開，照擋（v6 第 1 次的真陽性）
    bad = gg.check_read(plan, {"地上/長桌廣場/土堆/小陶印.txt"}, gf)
    assert len(bad) == 1 and "缺角的信" in bad[0]["msg"]
    # 負控制：地上真的沒有的檔，仍是「地上沒有這個檔」
    assert "地上沒有這個檔" in gg.check_read("x\n地上/帳本鏈/不存在的檔.txt\n", set(), gf)[0]["msg"]
