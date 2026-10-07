"""W3b（2026-10-01）：先寫信、再進世界；地上有真東西。

守的是：材料池是世界裡的實物（不是任務、不是分身台詞）、抽樣確定性、TRAITS.md 在段 2 不在工作區、
信的防呆（LEAK 8 字、300 字上限）、信屬於觀眾資料（撤回會刪、列進抹除清單）。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from ops.exhibit.twin import twin_letter_guard as guard  # noqa: E402
from ops.exhibit.twin import twinagent, twinground, twinlink  # noqa: E402
from test_twin_agent_run import (  # noqa: E402,F401
    NEED, TRAITS_TEXT, _all_bytes_under, _ingest, env, upstream,
)

#: 世界外的詞、時段詞、任務／菜單句式、分身台詞句式
_OUTSIDE = ("AI", "模型", "agent", "Agent", "驗證", "信任", "系統", "任務", "用戶", "專案", "使用者", "提示詞")
_TIME = ("白天", "晚上", "夜", "早上", "黃昏", "日落", "日出", "凌晨")
_MENU = ("可以做", "需要", "請", "應該", "必須", "建議", "不妨", "待辦", "任務清單", "小事清單",
         "要有人", "幫忙", "誰來", "有人要", "希望", "想要", "你可以", "不妨")
_VOICE = ("我想", "我要", "我決定", "我打算", "我會", "我來")
_ALL = sorted(twinground.pool())


def _text(rel: str) -> str:
    return (twinground.MATERIALS / rel).read_text(encoding="utf-8")


def test_pool_size_places_and_links() -> None:
    """P13：≥ 30 件新的「想動手但還沒人試過」的東西＋少數可核對的事實檔；八個地點各 3–7 件；關聯組彼此呼應。"""
    assert len(_ALL) >= 38
    places: dict[str, int] = {}
    for rel in _ALL:
        places[twinground.place_of(rel)] = places.get(twinground.place_of(rel), 0) + 1
    assert set(places) == {"投遞口", "捏土處", "長桌廣場", "石頭閘門", "帳本鏈", "草稿角", "紙卡地", "畫架與長椅"}
    assert all(3 <= n <= 8 for n in places.values()), places
    gs = twinground.groups()
    assert 8 <= len(gs) <= 16
    for g, ms in gs.items():
        assert len(ms) >= 2 and all(m in _ALL for m in ms), g


def test_pool_has_no_outside_words_no_menu_no_task_voice() -> None:
    from vacant_network.memory import assert_ks1_clean
    for rel in _ALL:
        t = _text(rel)
        assert t.strip(), rel
        assert [w for w in _OUTSIDE if w in t] == [], (rel, [w for w in _OUTSIDE if w in t])
        assert [w for w in _TIME if w in t] == [], (rel, [w for w in _TIME if w in t])
        assert [w for w in _MENU if w in t] == [], (rel, [w for w in _MENU if w in t])
        assert [w for w in _VOICE if w in t] == [], (rel, [w for w in _VOICE if w in t])
        assert not re.search(r"(可以|能夠|得|要).{0,3}(補|改|對|找|查|整理|做完|處理|重做)", t), rel
        assert_ks1_clean(t)
    # 負控制：這把尺量得到
    bad = "這裡請有人把鏈量一量，我想要把它補完，可以做"
    assert [w for w in _MENU if w in bad] and [w for w in _VOICE if w in bad]


def test_pool_links_are_checkable_facts() -> None:
    """留下來的幾組可核對事實（G3 的權威與對不上）＋新世界裡彼此呼應的數字／物件。"""
    tail = _text("帳本鏈/尾段_418到447片.txt")
    assert re.search(r"^431 .*印紋：蕨葉.*鐵環：鬆", tail, re.M)
    assert re.search(r"^438 .*印紋：半月", tail, re.M) and "片 438" in _text("畫架與長椅/畫架上的去向.txt")
    # 刻意的「對不上」：土堆小罐裡只有兩枚（沒有第三枚），閘門退回紙上的土堆清單卻寫 3 枚
    assert "沒有第三枚" in _text("長桌廣場/土堆/小陶印.txt")
    assert re.search(r"小陶印\s*3 枚", _text("石頭閘門/退回紙_另一張.txt"))
    # 紙卡地格狀圖：第四列 5 張；退回紙第四列寫 6 張
    assert "在位 24 張" in _text("紙卡地/格狀圖.txt") and "24 張卡" in _text("紙卡地/卡面上的圓.txt")
    assert "第四列：6 張" in _text("石頭閘門/退回紙_第四列.txt")
    # 新世界的呼應：音樂盒停在第 11 個音、斷的是第 12 根；哨子刻 12 道；第 7 格窗與 6 格窗；冷藍光與藍鉛筆、小門
    assert "第 11 個音" in _text("長桌廣場/桌五_音樂盒.txt") and "第 12" in _text("長桌廣場/桌五_音樂盒.txt")
    assert "12 道短線" in _text("長桌廣場/陶哨子.txt")
    assert "第 7 格" in _text("石頭閘門/第七格窗.txt") and "6 格" in _text("石頭閘門/第七格窗.txt")
    assert "冷藍" in _text("石頭閘門/背面的小門.txt") and "冷藍" in _text("長桌廣場/筆筒裡的藍鉛筆.txt")
    assert "橘" in _text("畫架與長椅/長椅上的紙筒.txt") and "橘" in _text("帳本鏈/放大鏡的鏡片.txt")
    # 水只有兩處
    assert "兩處水" in _text("捏土處/陶杯裡的種子.txt") and "兩處水" in _text("石頭閘門/閘門旁的陶碗.txt")


def test_the_world_invites_trying_and_never_assigns_it() -> None:
    """人類（2026-10-07）：世界要讓人看了想進去試——材料是事實與懸念，不是任務句、不是清單。
    每個地點至少有一件「還沒有人動過」的東西（沒人點過、沒人澆過、沒人推開、沒人撿起、沒人封好…），
    且每件都有感官（光／聲音／溫度／觸感／氣味之一）。"""
    untouched = ("沒有人", "沒有被", "從來沒有", "沒被", "沒有點過", "沒有撿起", "沒有扣上", "沒有壓", "沒有說過", "沒有走回來",
                 "沒有把握", "沒有裂穿", "沒有掉", "沒有按穿", "沒有被誰", "沒有第三枚", "沒有燒黑", "沒有一點磨損", "沒有任何",
                 "沒有蓋", "沒有開頭", "沒有印紋", "還沒", "沒有用過", "沒有去碰", "放了很久", "少了一撮", "沒有字", "沒有說")
    sense = ("光", "亮", "響", "聲", "暖", "涼", "冷", "軟", "潮", "味", "橘", "藍", "灰", "指紋", "摸", "咚", "重", "抖", "滾", "一起一伏")
    facts_only = {"帳本鏈/尾段_418到447片.txt", "紙卡地/格狀圖.txt", "石頭閘門/退回紙_第四列.txt",
                  "石頭閘門/退回紙_另一張.txt", "長桌廣場/桌五_壓著筆的紙.txt", "投遞口/收據卡_蕨葉.txt",
                  "帳本鏈/出生片_420到440.txt"}        # 留給「有沒有根據」那道閘門核對的幾份事實，不要求感官
    by_place: dict[str, list[str]] = {}
    for rel in _ALL:
        t = _text(rel)
        assert rel in facts_only or any(s in t for s in sense), rel
        if any(u in t for u in untouched):
            by_place.setdefault(twinground.place_of(rel), []).append(rel)
    for place in ("投遞口", "捏土處", "長桌廣場", "石頭閘門", "帳本鏈", "草稿角", "紙卡地", "畫架與長椅"):
        assert len(by_place.get(place, [])) >= 1, (place, by_place.get(place))
    # 不准有「去做 X」的句式
    for rel in _ALL:
        assert not re.search(r"(去|來|把|替|幫).{0,4}(試試|試一下|試看看|做完|補完|完成它)", _text(rel)), rel


def test_everyone_gets_the_same_ground_all_files() -> None:
    """P10：命盤決定走法、不決定地上有什麼——每位觀眾的地上都是同一整片與全部關聯組。"""
    a1, a2 = twinground.sample("sub-A"), twinground.sample("sub-A")
    assert a1 == a2
    assert {tuple(twinground.sample(f"sub-{i}")["files"]) for i in range(30)} == {tuple(_ALL)}
    assert twinground.sample("sub-A")["groups"] == sorted(twinground.groups())


def test_every_item_lures_some_temperament_and_all_eight_letters_are_covered() -> None:
    """每件地上的東西至少對一種性情有吸引力；E I S N T F J P 各至少三件（`world/materials/_lure.json`）。"""
    lure = json.loads((twinground.MATERIALS / "_lure.json").read_text(encoding="utf-8"))["lure"]
    assert sorted(lure) == _ALL
    assert all(v and set(v) <= set("EISNTFJP") for v in lure.values())
    for letter in "EISNTFJP":
        assert sum(letter in v for v in lure.values()) >= 3, letter


def test_lay_copies_read_only_and_records_sha(tmp_path) -> None:
    import hashlib
    m = twinground.lay(tmp_path, "sub-X")
    assert m["n_files"] == len(m["files"]) == len(_ALL)
    for f in m["files"]:
        p = tmp_path / f["path"]
        assert p.is_file() and not (p.stat().st_mode & 0o222), "要唯讀"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"]
        assert f["path"].startswith("地上/")
    assert not list((tmp_path / "地上").rglob("_links.json"))


def test_provenance_counts_found_and_missing() -> None:
    ground = [_text("帳本鏈/尾段_418到447片.txt")]
    r = twinground.provenance(["片 431 的印紋是蕨葉，鐵環鬆；片 999 印紋星"], ground)
    assert "431" in r["found_tokens"] and "蕨葉" in r["found_tokens"] and "星" in r["found_tokens"]
    assert r["missing_tokens"] == ["999"]
    # 整個數字才算：423 在地上，不代表 23 在地上；兩份清單相加出來的 23 找不到
    r2 = twinground.provenance(["共 23 個鐵環，片 423"], ["片 423 星"])
    assert r2["found_tokens"] == ["423"] and r2["missing_tokens"] == ["23"]
    # 條列序號不算
    assert twinground.tokens("12. 看一下\n3、再看") == []


# ───────── 信的關卡 ─────────

def _mk_room(tmp_path, letter: str | None, traits: str = "T" * 5):
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(); rd.mkdir()
    (ws / "TRAITS.md").write_text(traits, encoding="utf-8")
    if letter is not None:
        (ws / "信.md").write_text(letter, encoding="utf-8")
    (ws / "雜.md").write_text(traits, encoding="utf-8")
    s2 = rd / "stage2_in"
    (s2 / "地上" / "帳本鏈").mkdir(parents=True)
    (s2 / "WORLD.md").write_text("世界", encoding="utf-8")
    (s2 / "地上" / "帳本鏈" / "a.txt").write_text("x", encoding="utf-8")
    return ws, rd


def test_guard_removes_traits_leaves_only_letter_then_world(tmp_path) -> None:
    ws, rd = _mk_room(tmp_path, "這個人愛安靜。在意東西有沒有放回原處。")
    assert guard.run(ws, rd) == 0
    assert not (ws / "TRAITS.md").exists() and not (ws / "雜.md").exists()
    assert (ws / "信.md").is_file() and (ws / "WORLD.md").is_file() and (ws / "地上/帳本鏈/a.txt").is_file()
    info = json.loads((rd / "letter_guard.json").read_text(encoding="utf-8"))
    assert info["traits_removed"] is True and info["ok"] is True
    assert "愛安靜" not in json.dumps(info, ensure_ascii=False), "紀錄只有計數，沒有信的內容"


def test_guard_drops_8_char_leak_and_caps_300(tmp_path) -> None:
    traits = "我每天四點半自然醒然後去市場繞一圈"
    letter = "這個人手慢。他每天四點半自然醒，很早。在意東西的位置。" + "。".join("句子%d" % i + "字" * 30 for i in range(20)) + "。"
    ws, rd = _mk_room(tmp_path, letter, traits)
    assert guard.run(ws, rd) == 0
    out = (ws / "信.md").read_text(encoding="utf-8")
    assert "每天四點半自然醒" not in out and "手慢" in out
    assert len(out.strip()) <= 300
    info = json.loads((rd / "letter_guard.json").read_text(encoding="utf-8"))
    assert info["dropped_leak"] == 1 and info["truncated"] is True
    # 負控制：7 字相同不算
    assert guard.shares_window("每天四點半自然醒", "每天四點半自然", 8) is False
    assert guard.shares_window("每天四點半自然醒", "每天四點半自然醒", 8) is True


def test_guard_no_letter_still_removes_traits_and_fails(tmp_path) -> None:
    ws, rd = _mk_room(tmp_path, None)
    assert guard.run(ws, rd) == 4
    assert not (ws / "TRAITS.md").exists()
    assert not (ws / "WORLD.md").exists(), "信沒寫出來就不進世界"


def test_guard_letter_all_leak_fails(tmp_path) -> None:
    traits = "他每天四點半自然醒去市場繞一圈"
    ws, rd = _mk_room(tmp_path, "每天四點半自然醒去市場繞一圈", traits)
    assert guard.run(ws, rd) == 4 and not (ws / "TRAITS.md").exists()


def test_letter_prompt_has_no_examples_and_forbids_reality() -> None:
    p = twinagent.LETTER_SYSTEM_PROMPT
    for bad in ("例如", "比如", "譬如", "像是", "每當"):
        assert bad not in p
    for must in ("手慢還是手快", "愛一個人還是愛湊熱鬧", "拉扯", "習慣的手勢", "職業", "學校",
                 "家人", "寵物", "作品", "地名", "品牌", "三百字", "不要自稱 AI", "占卜", "你沒有任何工具"):
        assert must in p, must
    assert "WORLD.md" not in p and "地上" not in p, "段 1 看不到世界"


def test_wrapper_stage1_is_one_model_call_then_guard_then_the_only_pi_session() -> None:
    """P13：段 1 不再開 pi——`twin_letter.py` 一通模型呼叫 → 關卡 → 段 2 才是 pi（`runwatch` 看著）。"""
    sh = "\n".join(ln for ln in (ROOT / "ops/exhibit/twin/twin_agent.sh").read_text(encoding="utf-8").splitlines()
                   if not ln.lstrip().startswith("#"))
    assert "@TRAITS.md" not in sh and sh.count("@信.md") == 1 and sh.count('"$PI_BIN"') == 1
    assert sh.index("twin_letter.py") < sh.index("twin_letter_guard.py") < sh.index("runwatch") < sh.index("@信.md")
    assert "runlimited" not in sh and "limit " not in sh.replace("runwatch", ""), "沒有牆鐘時限了"


# ───────── 端到端（假 agent 走兩段流程）＋撤回 ─────────

_TWO_STAGE = r'''
import json, os, pathlib, sys, urllib.request
sys.path.insert(0, os.environ["REPO"])
from ops.exhibit.twin import twin_letter_guard as g
run_dir = sys.argv[-3]
ws = pathlib.Path.cwd()
traits = (ws / "TRAITS.md").read_text(encoding="utf-8")
(ws / "信.md").write_text("這個人手慢，在意東西有沒有放回原處。\n", encoding="utf-8")
rc = g.run(ws, pathlib.Path(run_dir))
assert rc == 0, rc
assert not (ws / "TRAITS.md").exists()
base = os.environ["OPENAI_BASE_URL"].rstrip("/")
req = urllib.request.Request(base + "/chat/completions", method="POST",
    data=json.dumps({"model": "m", "messages": [{"role": "user", "content": "好"}]}).encode())
req.add_header("Content-Type", "application/json")
urllib.request.urlopen(req, timeout=30).read()
ground = sorted(p.relative_to(ws).as_posix() for p in (ws / "地上").rglob("*") if p.is_file())
(ws / "PLAN.md").write_text("去對鏈尾\n三個想要\n", encoding="utf-8")
(ws / "成品.md").write_text("片 431\n", encoding="utf-8")
(ws / "過程.md").write_text("ground=" + str(len(ground)) + "\n", encoding="utf-8")
print("交出了成品")
'''


def test_two_stage_run_end_to_end_and_withdraw_erases_letter(env, monkeypatch, tmp_path) -> None:
    st, cfg = env["store"], env["cfg"]
    fx = tmp_path / "two_stage.py"
    fx.write_text(_TWO_STAGE, encoding="utf-8")
    monkeypatch.setenv("REPO", str(ROOT))
    cfg.argv_prefix = [sys.executable, str(fx)]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1 and r["degraded"] == 0, r
    tw = st.current(sid)["twin"]
    names = [a["name"] for a in tw["artifacts"]]
    assert "信.md" not in names and not [n for n in names if n.startswith("地上/")], names
    assert {"成品.md", "過程.md"} <= set(names)
    ws, rd = twinagent.paths_for(cfg.work_root, sid)
    assert not (ws / "TRAITS.md").exists() and (ws / "信.md").is_file() and (ws / "WORLD.md").is_file()
    man = json.loads((rd / "ground_manifest.json").read_text(encoding="utf-8"))
    assert man["n_files"] >= 16
    # 信是觀眾資料：公開鏈上沒有
    chain = "\n".join(json.dumps(e["payload"], ensure_ascii=False) for e in st.events())
    assert "手慢" not in chain
    assert b"\xe6\x89\x8b\xe6\x85\xa2" in _all_bytes_under(cfg.work_root), "負控制：撤回前找得到信"

    out = twinlink.withdraw(st, sid)
    assert out["ok"] is True and out["fully_erased"] is True
    what = [e["what"] for e in out["run_artifacts_erased"]]
    assert "letter" in what, what
    assert "手慢".encode("utf-8") not in _all_bytes_under(cfg.work_root)
    assert not list(cfg.work_root.rglob("信.md"))


def test_ws_write_extension_refuses_ground_dir() -> None:
    ts = (ROOT / "ops/exhibit/twin/pi_ext/twin_ws_tools.ts").read_text(encoding="utf-8")
    assert '"地上" + sep' in ts and "唯讀" in ts
    # 擋門在 confine 之後、寫檔之前
    assert ts.index('"地上" + sep') < ts.index("writeFileSync(abs, text")


def test_guard_drops_time_of_day_sentences(tmp_path) -> None:
    ws, rd = _mk_room(tmp_path, "這個人手慢。他總在深夜才安靜下來。在意東西的位置。", "毫不相干的特質文字")
    assert guard.run(ws, rd) == 0
    out = (ws / "信.md").read_text(encoding="utf-8")
    assert "深夜" not in out and "手慢" in out and "位置" in out
    assert json.loads((rd / "letter_guard.json").read_text(encoding="utf-8"))["dropped_time"] == 1
    # 負控制：沒有時段詞的句子不會被誤刪
    assert guard.clean_letter("這個人愛安靜。", "別的")[1]["dropped_time"] == 0


def test_system_prompt_says_where_to_write_and_third_person_letter() -> None:
    assert "最上層" in twinagent.SYSTEM_PROMPT and "唯讀" in twinagent.SYSTEM_PROMPT
    assert "第三人稱" in twinagent.LETTER_SYSTEM_PROMPT and "只有傾向，沒有場景" in twinagent.LETTER_SYSTEM_PROMPT
