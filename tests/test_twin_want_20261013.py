"""「它想做的是…」（2026-10-13）：卡上 `want`＝PLAN「我想：」之後那一句（同一套 `wish_of` 防呆），`want_step`＝PLAN 寫入那一步。

守的是：取得到（句子＋步數對得上步驟紀錄）、取不到就 None（不編）、不像檔名、≤60 字、
twin_view／twinlink 帶得出去、旁註與電視契約收 `want` 並擋壞形狀（正負控制）、離線 30 張真跑重算有 want。
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import fortune as fz            # noqa: E402
from ops.exhibit.twin import sidecar as sc            # noqa: E402
from ops.exhibit.twin import tv_contract as tv        # noqa: E402

EV = ROOT / "ops" / "exhibit" / "twin" / "evidence_mirror2_20261012"


def R(tool, path, seq=0, ts=0, ok=True, n=None):
    r = {"tool": tool, "path": path, "ok": ok, "seq": seq, "ts_ms": ts}
    if n is not None:
        r["_n"] = n
    return r


ROWS = [R("ws_read", "信.md", 1, 0), R("ws_list", ".", 2, 1000), R("ws_write", "PLAN.md", 3, 2000),
        R("ws_write", "成品.md", 4, 3000), R("ws_write", "PLAN.md", 5, 4000), R("ws_write", "PLAN.md", 6, 5000, ok=False)]
PLAN = "我想：讓那艘紙船在暗處找到一個完整的終點\n\n先去看看。"


def _card(plan=PLAN, rows=ROWS):
    return fz.compose_card({}, letter_text="", rows=rows, files={"成品.md": "內文"}, retries=0, plan_text=plan)


def test_want_is_the_wish_sentence_and_step_is_last_ok_plan_write() -> None:
    c = _card()
    assert c["want"] == "讓那艘紙船在暗處找到一個完整的終點"
    assert c["want_step"] == 5                      # 最後一次「成功」寫 PLAN；失敗的第 6 步不算
    assert len(c["want"]) <= fz.MAX_WANT_PUBLIC and not fz._FILENAME_LIKE.search(c["want"])


def test_want_none_when_no_label_or_filtered_or_empty_never_invented() -> None:
    for plan in ("", "先去看看。\n再做成品。", "我想：把 PLAN.md 改一改", "我想：一張填滿了圓圈的紙卡", "我想：讓那"):
        c = _card(plan)
        assert c["want"] is None and c["want_step"] is None, plan


def test_want_without_recorded_plan_write_keeps_sentence_but_no_step() -> None:
    c = _card(rows=[R("ws_read", "信.md", 1, 0)])
    assert c["want"] and c["want_step"] is None


def test_step_uses_file_position_n_and_is_capped_at_500() -> None:
    assert _card(rows=[R("ws_write", "PLAN.md", 1, 0, n=7)])["want_step"] == 7
    assert _card(rows=[R("ws_write", "PLAN.md", 1, 0, n=501)])["want_step"] is None


def test_lines_unchanged_by_want() -> None:
    c = _card()
    assert len(c["lines"]) <= 3 and all("它想做的是" not in x for x in c["lines"])


def test_twin_view_carries_want() -> None:
    v = fz.twin_view({}, _card())
    assert v["want"] and v["want_step"] == 5


def test_sidecar_and_tv_contract_accept_good_want_reject_bad() -> None:
    base = {"schema": "twin.sidecar/1", "type": "twin_fortune", "ts_ms": 1, "cell_id": "c", "run_id": "r", "phase": "card",
            "attempt": 1, "mbti": None, "mbti_source": None, "zodiac": None, "element": None, "blood": None, "lines": []}
    assert not sc._fortune_problems({**base, "want": "讓紙船找到終點"}, 0)
    assert not tv.fortune_event_problems({**base, "want": "讓紙船找到終點"}, 0)
    for bad in ("", "x" * 61, "讓 成品.md 動起來", 5):
        assert sc._fortune_problems({**base, "want": bad}, 0), bad
        assert tv.fortune_event_problems({**base, "want": bad}, 0), bad
    way = {**base, "phase": "way", "want": "讓紙船找到終點"}
    assert sc._fortune_problems(way, 0) and tv.fortune_event_problems(way, 0)
    assert "want" not in sc.FIELDS["twin_fortune"]          # 選填：舊旁註沒有也合格
    assert not sc._fortune_problems(base, 0)


def test_offline_30_real_runs_have_want_for_most_and_none_is_unfit() -> None:
    p = EV / "want_r7.json"
    cards = json.loads(p.read_text(encoding="utf-8"))
    got = [x for x in cards if x["want"]]
    assert len(cards) == 30 and len(got) >= 25
    for x in got:
        assert len(x["want"]) <= fz.MAX_WANT_PUBLIC and not fz._FILENAME_LIKE.search(x["want"])
        assert isinstance(x["want_step"], int) and 1 <= x["want_step"] <= 500


def test_adjective_lines_30_real_runs_distribution_and_bans() -> None:
    """形容語句版：30 跑離線重算，沒有任何一句超過 1/3、不寫「你是」、不帶世界地名／禁詞、最後手段的 made 只在沒別句時出現。"""
    import collections
    cards = json.loads((EV / "want_r7.json").read_text(encoding="utf-8"))
    cnt = collections.Counter(fz.strip_step(l) for x in cards for l in x["lines"])
    assert cards and max(cnt.values()) <= len(cards) / 3, cnt.most_common(3)
    banned = ("你是", "看穿", "預測", "讓 AI 更好", "命盤", "前前後後", "一共")
    for x in cards:
        assert x["lines"], x["id"]
        for l in x["lines"]:
            assert not any(b in l for b in banned), l
            assert len(l) <= 40
        if any(not l.startswith("最後做出來的是") for l in x["lines"]):
            assert not any(l.startswith("最後做出來的是") for l in x["lines"])


def test_adjective_table_covers_every_habit_but_made_and_off_pace_keys() -> None:
    keys = set(fz.RARITY) - {"made", "pace_slow", "pace_fast", "steps_few", "steps_many"}
    assert keys <= set(fz.ADJ_TEXT), keys - set(fz.ADJ_TEXT)
    assert all("你是" not in v for v in fz.ADJ_TEXT.values())


def test_made_is_last_resort_only() -> None:
    rows = [R("ws_write", "成品.md", 1, 0)]
    cands = [{"key": "made", "text": "最後做出來的是《甲》", "step": 1}]
    assert [c["key"] for c in fz.mirror_pick(cands + [{"key": "recheck", "text": "細心", "step": 2}], "s")] == ["recheck"]
    assert [c["key"] for c in fz.mirror_pick(cands, "s")] == ["made"]
