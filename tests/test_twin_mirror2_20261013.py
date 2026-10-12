"""mirror2（2026-10-13）：給觀眾的習慣句更分散、更有個人味，且每一句尾端的「（第 N 步）」對得上收據的步驟清單。

守的是：
* 每句 ≤ 60 字（含「（第 N 步）」）；每句都有步數，步數指得到步驟紀錄裡真的有的那一步，而且那一步的動作與句子相符；
* 步數＝步驟紀錄檔的順位（`_n`），不是排序後的位置——收據頁／手機過程清單用同一個編號；
* 收據的逐步清單只有 n／t／k／ok，沒有檔名與內容；雜湊與雲端瀏覽器端重算的是同一份（固定樣本）；
* 稀有度表覆蓋所有習慣鍵；
* 口徑禁詞掃描（看穿／預測／讓 AI 更好／你是／命盤字樣／世界地名）；
* divine 那 30 張真跑離線重算：沒有任何一句超過 1/3、每張至少一句不是「開頭方式」或「最後做出來的是」。
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import fortune as fz            # noqa: E402

EV = ROOT / "ops" / "exhibit" / "twin" / "evidence_mirror2_20261012"
TAG = re.compile(r"（第 (\d+) 步）$")


def R(tool, path, ok=True, seq=0, ts=0):
    return {"tool": tool, "path": path, "ok": ok, "seq": seq, "ts_ms": ts}


# 讀信 → 列房間 → 翻三個地方 → 寫計畫 → 寫成品 → 回頭翻最早去的那一類 ⇒ 全部步驟 8 步，每一步位置固定
ROWS = [R("ws_read", "信.md", seq=1, ts=0), R("ws_list", ".", seq=2, ts=1000),
        R("ws_read", "地上/草稿角/a.txt", seq=3, ts=2000), R("ws_read", "地上/帳本鏈/b.txt", seq=4, ts=3000),
        R("ws_write", "PLAN.md", seq=5, ts=90000), R("ws_write", "成品.md", seq=6, ts=91000),
        R("ws_read", "地上/草稿角/a.txt", seq=7, ts=92000), R("ws_list", ".", seq=8, ts=93000)]
FILES = {"成品.md": "# 鬆環對照冊\n內文，也許可能是這樣吧？"}


def _picks(rows=ROWS, **kw):
    return fz.mirror_picks(rows, FILES, kw.pop("retries", 0), kw.pop("title", "鬆環對照冊"), **kw)


def test_every_line_has_a_step_tag_within_60_chars_and_pointing_at_a_real_step() -> None:
    lines = fz.mirror_lines(ROWS, FILES, 0, "鬆環對照冊")
    assert 1 <= len(lines) <= fz.MAX_MIRROR_LINES
    for ln in lines:
        m = TAG.search(ln)
        assert m, ln
        assert len(ln) <= fz.MAX_CARD_LINE_CHARS, ln
        assert 1 <= int(m.group(1)) <= len(ROWS), ln


def test_step_points_at_the_step_that_proves_the_sentence() -> None:
    ev = fz.Evidence(ROWS, None)
    ev.files = dict(FILES)
    cands = {c["key"]: c for c in fz.mirror_candidates(ev, 0, "鬆環對照冊")}
    assert cands["start_browse"]["step"] == 3                       # 第一次翻地上的東西
    assert ROWS[cands["start_browse"]["step"] - 1]["path"].startswith("地上/")
    assert cands["recheck_first"]["step"] == 7                      # 做完之後回頭讀最早去的那一類
    assert cands["made"]["step"] == 6                               # 最後一次寫成品
    assert ROWS[cands["made"]["step"] - 1]["path"] == "成品.md"
    assert not any(k in cands for k in ("pace_slow", "pace_fast", "steps_few", "steps_many")), "節奏／步數不進候選（反映模型延遲，不是人的習慣）"
    assert cands["q_mark"]["step"] == 6


def test_step_number_is_the_position_in_the_step_file_not_the_sorted_position(tmp_path) -> None:
    """被退回重做時 seq 從頭再來；排序（ts_ms,seq）後的位置不一定等於檔案順位。編號用檔案順位（`_n`）。"""
    rows = [dict(r) for r in ROWS]
    # 把第 6、7 步的時間對調：排序後第 6 位變成原本的第 7 步
    rows[5]["ts_ms"], rows[6]["ts_ms"] = 92000, 91000
    (tmp_path / fz.STEP_LOG_NAME).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    got = fz.read_steps(tmp_path)
    assert [r["_n"] for r in got][5:7] == [7, 6], "排序後的順序與檔案順序不同，但 _n 仍是檔案順位"
    pub = fz.public_steps(got)
    assert [s["n"] for s in pub] == list(range(1, 9)), "公開清單依 n 排好"
    assert pub[5] == {"n": 6, "t": "w", "k": "成品", "ok": True}


def test_public_steps_have_no_filenames_and_digest_matches_the_browser_fixture() -> None:
    pub = fz.public_steps(ROWS)
    blob = json.dumps(pub, ensure_ascii=False)
    for secret in ("a.txt", "b.txt", "成品.md", "PLAN.md", "信.md", "草稿角", "帳本鏈"):
        assert secret not in blob, secret
    assert all(set(s) == {"n", "t", "k", "ok"} for s in pub)
    # 固定樣本：雲端 test/fixtures/steps_fixture.json 在瀏覽器端重算的是同一個值（跨語言規範化一致）
    sample = fz.public_steps([R("ws_read", "信.md"), R("ws_list", "."), R("ws_read", "地上/帳本鏈/出生片.txt"),
                              R("ws_read", "地上/草稿角/x.txt", ok=False), R("ws_write", "PLAN.md"), R("ws_write", "秘密檔名.md")])
    assert fz.steps_digest(sample) == "778c466e68e9d2aee8de6bfc952f0f0158ea6f1a6587adeb46b08fc3ec41c969"


def test_steps_beyond_the_500_step_cap_are_not_cited() -> None:
    big = [R("ws_read", "信.md", seq=1)] + [R("ws_list", ".", seq=i + 2) for i in range(600)]
    big[3] = R("ws_read", "地上/帳本鏈/x.txt", seq=4)
    big.append(R("ws_write", "成品.md", seq=999))
    for ln in fz.mirror_lines(big, FILES, 0, "甲"):
        assert int(TAG.search(ln).group(1)) <= 500


def test_strip_step_and_polaroid_and_tv_lines_carry_no_step() -> None:
    ln = "先去看了一眼，才決定要做什麼（第 12 步）"
    assert fz.strip_step(ln) == "先去看了一眼，才決定要做什麼" and fz.step_of(ln) == 12
    assert fz.polaroid_sentence(ln) == "先去看了一眼，才決定要做什麼"
    assert fz.strip_step("沒有步數") == "沒有步數" and fz.step_of("沒有步數") is None


def test_tables_cover_every_habit_and_selection_is_deterministic_and_spread() -> None:
    assert set(fz.RARITY) == set(fz.MIRROR_GROUP)
    assert fz.RARITY["made"] == min(fz.RARITY.values()), "「最後做出來的是」最不稀有（沒別的才用）"
    a = fz.mirror_lines(ROWS, FILES, 0, "鬆環對照冊", seed="x1")
    assert a == fz.mirror_lines(ROWS, FILES, 0, "鬆環對照冊", seed="x1"), "同一份輸入同一份輸出（不經模型、不隨機）"


def test_banned_words_and_no_world_place_names_in_any_habit_sentence() -> None:
    texts = [c["text"] for c in fz.mirror_candidates(_ev_all(), 2, "甲", plan_text="我想：x", retry_ids=("G1",))]
    texts += [v for v in fz.PLACE_KIND.values()]
    assert len(texts) >= 10
    banned = ("看穿", "預測", "讓 AI 更好", "讓AI更好", "你是", "MBTI", "星座", "血型", "命盤", "不會被繞過", "信任")
    for t in texts:
        for b in banned:
            assert b not in t, (t, b)
        for place in fz.PLACES:
            assert place not in t, (t, place)


def _ev_all():
    rows = [R("ws_read", "信.md", seq=1, ts=0)] + [R("ws_read", f"地上/{p}/x.txt", seq=i + 2, ts=1000 * (i + 1))
                                                    for i, p in enumerate(("草稿角", "帳本鏈", "捏土處", "草稿角", "草稿角", "紙卡地"))]
    rows += [R("ws_read", "地上/草稿角/q.txt", ok=False, seq=9, ts=9000), R("ws_read", "地上/紙卡地/y.txt", seq=10, ts=9500),
             R("ws_write", "PLAN.md", seq=11, ts=70000), R("ws_read", "PLAN.md", seq=12, ts=71000),
             R("ws_write", "PLAN.md", seq=13, ts=72000), R("ws_write", "甲.md", seq=14, ts=73000), R("ws_write", "甲.md", seq=15, ts=74000),
             R("ws_read", "信.md", seq=1, ts=80000), R("ws_write", "PLAN.md", seq=2, ts=81000), R("ws_write", "乙.md", seq=3, ts=82000),
             R("ws_read", "地上/草稿角/x.txt", seq=4, ts=83000)]
    ev = fz.Evidence(rows, None)
    ev.files = {"甲.md": "好吧？" + "字" * 250, "乙.md": "也許可能 3 個"}
    return ev


def test_every_candidate_fits_with_a_three_digit_step_tag() -> None:
    for c in fz.mirror_candidates(_ev_all(), 2, "甲" * 20, plan_text="我想：x", retry_ids=("G1",)):
        if c["key"] != "made":
            assert len(c["text"]) + len("（第 500 步）") <= fz.MAX_CARD_LINE_CHARS, c


def test_retry_reason_comes_from_gate_cell_ids_not_guessed() -> None:
    ev = _ev_all()
    keys = lambda ids: {c["key"] for c in fz.mirror_candidates(ev, 1, "甲", retry_ids=ids)}   # noqa: E731
    assert "retried_open" in keys(("G1",)) and "retried_source" in keys(("G2",))
    k0 = keys(())
    assert "retried" in k0 and "retried_open" not in k0 and "retried_source" not in k0, "讀不到原因就用通用說法，不編"


def test_retried_open_says_passed_only_when_accepted_true() -> None:
    ev = _ev_all()
    txt = lambda acc: next(c["text"] for c in fz.mirror_candidates(ev, 1, "甲", retry_ids=("G1",), accepted=acc)   # noqa: E731
                           if c["key"] == "retried_open")
    assert "才過" in txt(True)                                   # 正控制：通過了才能說「才過」
    for acc in (False, None):                                    # 負控制：沒通過／不知道，不說「過」
        assert "過" not in txt(acc).replace("被退回過", ""), txt(acc)
        assert "回去補開了" in txt(acc)


def test_thirty_real_runs_no_sentence_over_a_third_and_every_card_has_a_real_habit() -> None:
    cards = json.loads((EV / "cards_r7.json").read_text(encoding="utf-8"))
    assert len(cards) == 30
    start = ("還沒決定要做什麼", "先去看了一眼", "先把要做的事寫下來", "沒寫計畫，直接", "第一個動手翻的")
    norm = lambda l: re.sub(r"\d+( 分 \d+)?", "N", TAG.sub("", l))      # noqa: E731
    cnt = collections.Counter()
    for c in cards:
        ls = [norm(x) for x in c["lines"]]
        cnt.update(set(ls))
        assert all(TAG.search(x) and len(x) <= fz.MAX_CARD_LINE_CHARS for x in c["lines"]), c["lines"]
        assert any(not l.startswith(start) and not l.startswith("最後做出來的是") for l in ls), (c["id"], ls)
    assert cnt.most_common(1)[0][1] <= 30 / 3, cnt.most_common(3)
    assert len(cnt) >= 25, "句子夠分散：至少 25 種不同的句型"


def test_before_table_is_kept_for_comparison() -> None:
    before = json.loads((EV / "cards_before.json").read_text(encoding="utf-8"))
    cnt = collections.Counter(x if not x.startswith("最後做出來的是") else "最後做出來的是" for c in before for x in set(c["lines"]))
    assert cnt.most_common(1)[0][1] / len(before) > 1 / 3, "舊版確實有一句超過 1/3（這是要修的問題，不是編的）"


def test_pace_and_step_count_habits_are_off_everywhere_even_in_the_30_real_runs() -> None:
    assert fz.PACE_HABITS is False
    cards = json.loads((EV / "cards_r7.json").read_text(encoding="utf-8"))
    for c in cards:
        for x in c["lines"]:
            assert "才開始寫計畫" not in x and "很快就開始寫計畫" not in x and "步才交" not in x and "步就交了" not in x, x


def test_no_recognized_artifact_still_gives_evidenced_lines() -> None:
    """2026-10-13 展前線上驗收：交了件、成品寫入卻沒被認出 ⇒ 卡上 0 句。
    現在：跟成品無關的習慣（怎麼開始、翻了什麼、被退回）照樣出，每句仍有自己的那一步；跟成品有關的不出。"""
    rows = [r for r in ROWS if not (r["tool"] == "ws_write" and r["path"] not in fz.SYSTEM_FILES)]
    picks = fz.mirror_picks(rows, {}, 1, None, retry_ids=("G1",), accepted=False)
    assert picks, "有翻東西、有寫計畫、有被退回，卻一句都沒有"
    keys = {c["key"] for c in picks}
    assert not keys & {"made", "short_made", "long_made", "two_versions", "several_made", "recheck", "recheck_first"}
    for c in picks:
        assert 1 <= c["step"] <= len(rows)


def test_nothing_done_still_gives_nothing() -> None:
    """負控制：完全沒翻、沒寫計畫、沒做東西 ⇒ 仍然 0 句（不補、不編）。"""
    assert fz.mirror_picks([R("ws_list", ".", seq=1)], {}, 0, None) == []
