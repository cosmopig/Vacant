"""`--bank-filter` 分層選擇與 builtin 無限池護欄（R529 跨題庫，2026-09-11）。

這支在架構裡承重什麼：R529 要回答「H-MIX 的單一效果在**不同題目集**上穩不穩」，
而手上真正不同來源的題庫只有兩個（LCB、MBPP+）。要把「題目集」數量誠實地加上去，
唯一不作弊的做法是**同來源的平台原生分層**（LCB 的 difficulty／platform）——
那是 LeetCode 出題時就掛在題目上的標籤，不是我們自己貼的。

所以這支測試守的是三件事，每一件都對應一種「看起來有跑、其實沒跑」：

1. **切層不准安靜地選錯集合**：切層在 `offset`／`n` 之前做，`--offset` 數的是
   **該層之內**的第幾題；切出來的每一題都真的屬於那一層，塊與塊零交集。
2. **對不上一律停**：不認得的 key、題庫裡沒有的 value、沒有分層標籤的 bank、
   語法壞掉的 spec——四種都 `SystemExit`。**量不到不是通過**（鐵律 3 的同一條）。
   特別是 key 白名單：開放任意欄位 ⇒ 有一天會有人用 `n_hidden_total=24` 切層，
   那等於讓**隱藏測資的形狀**決定哪些題進 run（V/GT 分離的旁路）。
3. **不切層的 run 逐位元不變**：沒有 `--bank-filter` 時 `load_tasks` 的回傳與
   rows／summary 的 key 集合一個字都沒動——R460／R460R 的資料還在跑，
   這支改動不准動到它們的形狀。

外加一條與 R529 無關但同一次抓到的：`--bank builtin` 在 `--bank` 的 choices 裡
列著，而 `BuiltinSampleLoader` 是**無限**產生器 ⇒ 原本那句
`list(loader.iter_tasks(seed))` 對它永遠不回來。掛死與「跑很久」在終端機上
長得一模一樣，所以要有一條會在秒級內失敗的測試釘住它。
"""
from __future__ import annotations

import collections
import inspect

import pytest

from ops.gain.gain_run import (
    LCB_BANK_VERSION,
    bank_strata,
    load_tasks,
    parse_bank_filter,
)
from vacant.codebench import LCB_STRATUM_KEYS, lcb_strata


# ── 一、分層選的是對的集合 ────────────────────────────────────────
def test_lcb3_difficulty_strata_partition_the_bank_exactly():
    """hard ＋ medium ＝ 全部 189 題，且兩層零交集——分層不准漏題也不准重複。"""
    hard = {t["task_id"] for t in load_tasks("lcb3", "s", 0, bank_filter="difficulty=hard")}
    med = {t["task_id"] for t in load_tasks("lcb3", "s", 0, bank_filter="difficulty=medium")}
    whole = {t["task_id"] for t in load_tasks("lcb3", "s", 0)}
    assert len(hard) == 54 and len(med) == 135
    assert hard & med == set()
    assert hard | med == whole


def test_every_selected_task_really_carries_that_label():
    strata = lcb_strata("v3")
    for t in load_tasks("lcb3", "s", 0, bank_filter="difficulty=hard"):
        assert strata[t["task_id"]]["difficulty"] == "hard"


def test_multi_value_filter_is_the_union():
    both = {t["task_id"] for t in
            load_tasks("lcb3", "s", 0, bank_filter="difficulty=medium,hard")}
    whole = {t["task_id"] for t in load_tasks("lcb3", "s", 0)}
    assert both == whole


def test_offset_counts_inside_the_stratum_and_blocks_stay_disjoint():
    """切層在 offset 之前 ⇒ 54 題的 hard 層切成兩塊 27 恰好用完，且兩塊零交集。

    ⚠ 這一條就是切塊語意：若切層跑在 offset **之後**，`--offset 27` 會落在
      整個題庫的第 27 題（medium 居多）再過濾 ⇒ 塊的大小會隨層的分布飄，
      而終端機上只會看到「只載到 N 題」這種看起來很正常的警告。
    """
    a = [t["task_id"] for t in
         load_tasks("lcb3", "s", 27, offset=0, bank_filter="difficulty=hard")]
    b = [t["task_id"] for t in
         load_tasks("lcb3", "s", 27, offset=27, bank_filter="difficulty=hard")]
    assert len(a) == 27 and len(b) == 27
    assert set(a) & set(b) == set()
    assert len(set(a) | set(b)) == 54


def test_seed_still_orders_the_stratum_deterministically():
    one = [t["task_id"] for t in load_tasks("lcb3", "seed-A", 10, bank_filter="difficulty=hard")]
    again = [t["task_id"] for t in load_tasks("lcb3", "seed-A", 10, bank_filter="difficulty=hard")]
    other = [t["task_id"] for t in load_tasks("lcb3", "seed-B", 10, bank_filter="difficulty=hard")]
    assert one == again
    assert one != other


def test_family_field_already_carries_the_stratum_label():
    """rows 的 `family` 欄位（`lcb_<platform>_<difficulty>`）就是那一層的標籤。

    收官分層讀的是這一欄，不是 run 目錄名——目錄名可以打錯，`family` 是從
    釘死的題庫算出來的。
    """
    fams = collections.Counter(
        t["family"] for t in load_tasks("lcb3", "s", 0, bank_filter="difficulty=hard"))
    assert fams == {"lcb_leetcode_hard": 54}


# ── 二、對不上一律停（量不到不是通過） ────────────────────────────
@pytest.mark.parametrize("bank,spec,needle", [
    ("lcb3", "difficulty=easy", "實際有的是"),
    ("lcb3", "platform=codeforces", "實際有的是"),
    ("lcb3", "n_hidden_total=24", "不認得 key"),
    ("lcb3", "prompt=x", "不認得 key"),
    ("evalplus", "difficulty=hard", "不成立"),
    ("builtin", "difficulty=hard", "不成立"),
    ("lcb3", "difficultyhard", "格式是 key=value"),
    ("lcb3", "difficulty=hard=medium", "格式是 key=value"),
    ("lcb3", "difficulty=", "是空的"),
    ("lcb3", "=hard", "是空的"),
])
def test_bad_filters_stop_instead_of_quietly_selecting_something(bank, spec, needle):
    with pytest.raises(SystemExit) as e:
        load_tasks(bank, "s", 5, bank_filter=spec)
    assert needle in str(e.value)


def test_hidden_shaped_keys_are_not_selectable():
    """白名單只有兩個 key——這是 V/GT 分離的旁路防線，不是打字方便。"""
    assert LCB_STRATUM_KEYS == ("difficulty", "platform")
    for key in ("hidden_tests", "n_hidden_total", "visible_tests", "entry_point"):
        with pytest.raises(SystemExit, match="不認得 key"):
            load_tasks("lcb3", "s", 5, bank_filter=f"{key}=1")


def test_strata_map_covers_every_task_in_every_lcb_bank():
    """分層表不准是半殘的：每一題都要有兩個標籤，缺一個就不是「那一層是空的」。"""
    for bank, version in LCB_BANK_VERSION.items():
        tasks = load_tasks(bank, "s", 0)
        strata = bank_strata(bank)
        assert len(strata) == len(tasks)
        for t in tasks:
            m = strata[t["task_id"]]
            assert set(m) == set(LCB_STRATUM_KEYS)
            assert all(isinstance(v, str) and v for v in m.values())


def test_parse_bank_filter_is_syntax_only():
    assert parse_bank_filter("difficulty=hard") == ("difficulty", ("hard",))
    assert parse_bank_filter(" difficulty = hard , medium ") == (
        "difficulty", ("hard", "medium"))


# ── 三、不切層的 run 逐位元不變 ───────────────────────────────────
def test_unfiltered_load_is_unchanged():
    """`bank_filter=None` 與完全不傳這個引數的結果必須逐項相同。"""
    a = [t["task_id"] for t in load_tasks("lcb2", "g-r440-lcb2", 20, offset=20)]
    b = [t["task_id"] for t in
         load_tasks("lcb2", "g-r440-lcb2", 20, offset=20, bank_filter=None)]
    assert a == b
    assert len(a) == 20


def test_bank_filter_is_keyword_only_with_a_none_default():
    """既有呼叫端（analyze_r460r、r475_oracle_sweep、測試）一個字都不必改。"""
    sig = inspect.signature(load_tasks)
    p = sig.parameters["bank_filter"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is None


def test_row_and_summary_keys_only_appear_when_a_filter_is_given():
    """rows／summary 的新欄位是**條件的**——沒切層就完全不出現。

    這一條是對著還在跑的 R460R 寫的：它的 30 塊用的是同一支 runner，
    多一個 `"bank_filter": null` 就是多一個下游 parser 要處理的形狀。
    """
    import pathlib
    src = pathlib.Path("ops/gain/gain_run.py").read_text(encoding="utf-8")
    for anchor in ('if args.bank_filter else {}',):
        assert src.count(anchor) >= 2, "rows 與 summary 兩處都要是條件式"


# ── 四、builtin 的無限池護欄 ──────────────────────────────────────
def test_builtin_bank_does_not_hang_forever():
    """`--bank builtin` 是 `--bank` 的合法值，而它的 loader 是無限產生器。

    改動之前這一行會掛死（`list()` 吃一個 `while True`）。測試的價值不在於
    builtin 好不好用（它是合成題庫，結論不可外推），而在於**掛死不准長得
    像在跑**。
    """
    ts = load_tasks("builtin", "g1", 6)
    assert len(ts) == 6
    assert len({t["task_id"] for t in ts}) == 6


def test_builtin_offset_slices_without_overlap():
    a = {t["task_id"] for t in load_tasks("builtin", "g1", 6, offset=0)}
    b = {t["task_id"] for t in load_tasks("builtin", "g1", 6, offset=6)}
    assert len(a) == len(b) == 6 and a & b == set()


def test_builtin_with_n_zero_stops_instead_of_hanging():
    """n=0 的意思是「整個題庫」，對無限池沒有定義 ⇒ 明講，不默默取一個上限。"""
    with pytest.raises(SystemExit, match="無限產生器"):
        load_tasks("builtin", "g1", 0)
