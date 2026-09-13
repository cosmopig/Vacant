"""等預算選擇規則的單元測試（R446 / Task A）。

這支在架構裡承重什麼：`ops/gain/replay/equal_budget_rules.py` 的結論
（「同樣 5 通呼叫下，篩選 vs 投票」）完全建立在 `_pick` 這幾行的語意上。
規則寫錯的話，數字會照樣印出來、而且看起來很合理——所以每條規則的定義
都要有一個手算得出答案的最小例子釘住。

**最重要的一條**：`test_pick_never_sees_hidden` 用一個沒有 `hid` 欄位的 view
跑完全部規則。V/GT 分離（SPEC §5.3）在這裡是可執行的防呆，不是註解。
"""
from __future__ import annotations

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
)

ebr = pytest.importorskip("ops.gain.replay.equal_budget_rules")


def V(vis, sig, depth, hid=None):
    return {"vis": vis, "sig": sig, "depth": depth, "hid": hid}


def test_filter_first_takes_earliest_visible_passer():
    view = [V(False, "a", 1), V(True, "b", 3), V(True, "c", 3),
            V(False, "a", 0), V(False, "a", 2)]
    assert ebr._pick(view, "FILTER_FIRST") == (1, False)


def test_filter_first_refuses_when_none_pass_visible():
    view = [V(False, "a", 1)] * 5
    assert ebr._pick(view, "FILTER_FIRST") == (None, True)
    # 拒交＝沒交出去＝不算通過，即使該候選其實 hidden 過。
    assert ebr._score([V(False, "a", 1, hid=True)] * 5, None, True) is False


def test_filter_vote_prefers_the_majority_behaviour_among_passers():
    # 通過可見的是 1、2、4；行為簽名 b 佔 2 票、c 佔 1 票 ⇒ 選 b 的最前者＝1
    view = [V(False, "a", 1), V(True, "b", 3), V(True, "c", 3),
            V(False, "a", 0), V(True, "b", 3)]
    assert ebr._pick(view, "FILTER_VOTE") == (1, False)
    # 反過來：c 佔 2 票 ⇒ 選 index 2（＝與 FILTER_FIRST 不同）
    view2 = [V(True, "b", 3), V(False, "a", 1), V(True, "c", 3),
             V(True, "c", 3), V(False, "a", 0)]
    assert ebr._pick(view2, "FILTER_VOTE") == (2, False)
    assert ebr._pick(view2, "FILTER_FIRST") == (0, False)


def test_filter_vote_fallback_never_refuses():
    view = [V(False, "x", 1), V(False, "y", 0), V(False, "x", 1),
            V(False, "z", 2), V(False, "x", 1)]
    idx, refused = ebr._pick(view, "FILTER_VOTE_FB")
    assert refused is False and idx == 0          # 全不過 ⇒ 退化成 OFF5 多數決（x 三票）
    assert ebr._pick(view, "FILTER_VOTE") == (None, True)


def test_depth_best_picks_deepest_prefix_and_never_refuses():
    view = [V(False, "a", 0), V(False, "b", 2), V(False, "c", 1),
            V(False, "d", -1), V(False, "e", 2)]
    assert ebr._pick(view, "DEPTH_BEST") == (1, False)   # 平手取最前者
    # 有人全過時，滿分深度必然最大 ⇒ 退回 FILTER_FIRST
    view2 = [V(False, "a", 2), V(True, "b", 3), V(False, "c", 2),
             V(True, "d", 3), V(False, "e", 0)]
    assert ebr._pick(view2, "DEPTH_BEST") == ebr._pick(view2, "FILTER_FIRST")


def test_off5_replay_is_plain_majority_ignoring_visible():
    view = [V(False, "wrong", 0), V(False, "wrong", 0), V(True, "right", 3),
            V(False, "wrong", 0), V(True, "right", 3)]
    assert ebr._pick(view, "OFF5_REPLAY") == (0, False)   # 錯的那個佔 3 票
    assert ebr._pick(view, "FILTER_FIRST") == (2, False)


def test_unknown_signature_does_not_merge_buckets():
    """未知簽名（`sig is None`）每個各自成桶，不併成同一桶。

    ⚠ 下面第一個例子**分辨不出兩種語意**（R738 實測：把 `_buckets` 改成併桶，
    這一條照樣綠）——併桶後未知桶只有 2 票，本來就贏不了 `s` 的 3 票。
    留著它是因為它仍是一個正確的回歸釘子，但**承重的是後面三個 witness**：
    要看得見併桶，必須讓合併後的未知桶**自己變成多數**，而且它的最小 index **不是 0**
    （否則跟「平手取抽樣序最前者」同一個答案，一樣分辨不出來）。
    """
    view = [V(True, None, 3), V(True, None, 3), V(True, "s", 3),
            V(True, "s", 3), V(True, "s", 3)]
    assert ebr._pick(view, "FILTER_VOTE") == (2, False)

    # W1：五個各自成桶 ⇒ 全平手 ⇒ 取最前者 0。若併桶，未知桶 {1,3} 兩票獨大 ⇒ 會變成 1。
    w1 = [V(True, "a", 3), V(True, None, 3), V(True, "b", 3),
          V(True, None, 3), V(True, "c", 3)]
    assert ebr._pick(w1, "FILTER_VOTE") == (0, False)
    assert ebr._pick(w1, "OFF5_REPLAY") == (0, False)

    # W2：`a` 桶 2 票是多數 ⇒ 0。若併桶，未知桶 {2,3,4} 三票反超 ⇒ 會變成 2。
    w2 = [V(True, "a", 3), V(True, "a", 3), V(True, None, 3),
          V(True, None, 3), V(True, None, 3)]
    assert ebr._pick(w2, "FILTER_VOTE") == (0, False)

    # W3：換一個出口函式再看一次同一件事——分佈而不是單一贏家。
    # 不併桶＝五桶全平手，每人 1/5；併桶＝只有未知桶贏，index 1、3 各 1/2。
    d = dict(ebr._vote_dist(w1, list(range(5))))
    assert set(d) == {0, 1, 2, 3, 4}
    assert all(pytest.approx(p) == 0.2 for p in d.values())


def test_vote_dist_matches_arm_off5_two_stage_uniform():
    # 兩個平手桶（各 1 票）與一個 2 票桶 ⇒ 只有 2 票桶會贏，桶內兩人各 1/2
    view = [V(True, "a", 3), V(True, "b", 3), V(True, "c", 3),
            V(True, "a", 3), V(True, "d", 3)]
    d = dict(ebr._vote_dist(view, list(range(5))))
    assert pytest.approx(d[0]) == 0.5 and pytest.approx(d[3]) == 0.5
    assert set(d) == {0, 3}
    # 全部平手（5 個不同簽名）⇒ 每人 1/5
    view2 = [V(True, s, 3) for s in "abcde"]
    d2 = dict(ebr._vote_dist(view2, list(range(5))))
    assert all(pytest.approx(p) == 0.2 for p in d2.values()) and len(d2) == 5
    assert sum(d2.values()) == pytest.approx(1.0)


def test_pick_never_sees_hidden():
    """規則函式拿不到 hidden 標籤——V/GT 分離的可執行防呆（SPEC §5.3）。"""
    view = [{"vis": i % 2 == 0, "sig": f"s{i % 3}", "depth": i} for i in range(5)]
    for rule in ebr.RULES:
        idx, refused = ebr._pick(view, rule)          # 沒有 "hid" key，KeyError 就代表洩漏
        assert refused in (True, False)
        assert idx is None or 0 <= idx < 5


def test_mcnemar_exact_two_sided():
    n, b, c, p = ebr.mcnemar([(True, False)] * 5 + [(False, True)] * 0
                             + [(True, True)] * 10)
    assert (n, b, c) == (15, 5, 0)
    assert p == pytest.approx(2 * 1 / 2 ** 5)
    assert ebr.mcnemar([(True, True)] * 7)[3] == 1.0


def test_boot_ci_is_deterministic_and_brackets_the_point_estimate():
    pairs = [(True, False)] * 20 + [(False, True)] * 10 + [(True, True)] * 70
    lo, hi = ebr.boot_ci(pairs, b=2000, seed=1)
    assert (lo, hi) == ebr.boot_ci(pairs, b=2000, seed=1)
    assert lo < 10.0 < hi          # 點估計 (20-10)/100 = +10pp


def test_score_counts_refusal_as_failure():
    view = [V(False, "a", 0, hid=True)] * 5
    assert ebr._score(view, None, True) is False
    assert ebr._score(view, 0, False) is True
