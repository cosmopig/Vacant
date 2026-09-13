"""`--bank humanevalplus` 接進 runner 的那幾條線（R529 第三個真來源）。

`tests/test_humanevalplus_loader.py` 驗的是 loader 本身（sha256／schema／V/GT）；
這支驗的是**接線**——loader 對了但線接錯，長得跟「這個題庫效果比較差」一模一樣：

  1. `load_tasks("humanevalplus", …)` 吐得出 156 題（164 − 8 排除），
     切塊語意（offset／n）與別的 bank 逐字相同；
  2. `_canonical_solutions("humanevalplus")` 回的是**完整**參考解
     （`prompt + canonical_solution`），不是縮排的函式體；
  3. `probe_instrument` 在這個 bank 上兩個方向都答得對（離線、零模型呼叫）；
  4. 八題排除逐題有名字、有成因，而且**沒有動到 MBPP+ 那七題**；
  5. `--bank` 的 choices 有它、`--bank-filter` 對它**不成立**（它沒有平台原生標籤）。

⚠ 官方包不在場時，需要真資料的那幾條 skip——不假裝驗過。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.gain_run import (  # noqa: E402
    GAIN_EVALPLUS_RESOURCE_EXCLUSIONS,
    GAIN_HUMANEVAL_EXCLUSIONS,
    _canonical_solutions,
    bank_strata,
    load_tasks,
    probe_instrument,
)
from vacant.codebench import (  # noqa: E402
    EVALPLUS_HUMANEVAL_DEFAULT_PATH,
    EvalPlusHumanEvalLoader,
)

_HAVE_PACK = (ROOT / EVALPLUS_HUMANEVAL_DEFAULT_PATH).exists()
needs_pack = pytest.mark.skipif(not _HAVE_PACK, reason="官方 HumanEval+ 包不在場")


# ── 1. load_tasks ─────────────────────────────────────────────────────────
@needs_pack
def test_bank_yields_164_minus_8_tasks():
    ts = load_tasks("humanevalplus", "g-r529-he", 0)
    assert len(ts) == 156
    assert len({t["task_id"] for t in ts}) == 156
    assert all(t["task_id"].startswith("humanevalplus_") for t in ts)
    assert not ({t["task_id"] for t in ts} & set(GAIN_HUMANEVAL_EXCLUSIONS))


@needs_pack
def test_offset_slicing_is_disjoint_and_deterministic():
    a = [t["task_id"] for t in load_tasks("humanevalplus", "g-r529-he", 20, offset=0)]
    b = [t["task_id"] for t in load_tasks("humanevalplus", "g-r529-he", 20, offset=20)]
    again = [t["task_id"] for t in load_tasks("humanevalplus", "g-r529-he", 20, offset=0)]
    assert a == again
    assert len(a) == len(b) == 20 and set(a) & set(b) == set()
    tail = load_tasks("humanevalplus", "g-r529-he", 16, offset=140)
    assert len(tail) == 16          # 尾塊取餘數，不湊不補


@needs_pack
def test_zero_intersection_with_the_other_three_sets():
    he = {t["task_id"] for t in load_tasks("humanevalplus", "g-r529-he", 0)}
    mb = {t["task_id"] for t in load_tasks("evalplus", "g-r529-mbpp", 0)}
    lcb = {t["task_id"] for t in load_tasks("lcb3", "g-r529-lcb3", 0)}
    assert he & mb == set() and he & lcb == set()
    assert len(he | mb | lcb) == 156 + 371 + 189


# ── 2. 參考解是完整的，不是函式體 ──────────────────────────────────────────
@needs_pack
def test_canonical_solutions_are_complete_and_compile():
    refs = _canonical_solutions("humanevalplus")
    assert len(refs) == 164            # 排除是 runner 層的事，參考解表是整個題庫
    ts = load_tasks("humanevalplus", "g-r529-he", 0)
    assert all(refs.get(t["task_id"]) for t in ts)      # 156/156 覆蓋
    for t in ts[:20]:
        compile(refs[t["task_id"]], "<ref>", "exec")


@needs_pack
def test_canonical_table_is_not_the_mbpp_one():
    """漏接分支的話會掉進 EvalPlus 那條路，拿 `mbppplus_*` 的解去配 HumanEval 的 id
    ⇒ covered 恆為 0 ⇒ 錯誤訊息變成「讀不到參考解」，把接線錯誤講成資料不在。"""
    refs = _canonical_solutions("humanevalplus")
    assert all(k.startswith("humanevalplus_") for k in refs)


# ── 3. 量具（離線、零模型呼叫）──────────────────────────────────────────────
@needs_pack
def test_probe_instrument_answers_both_directions_on_a_sample():
    """抽 6 題跑完整的量具：參考解要過、壞樁要被擋，hidden 與 visible 各一次。

    ⚠ 全 156 題的版本在 vacant-dev 上跑過（預註冊 §五-1，約 114 秒）；
      這裡只抽 6 題是為了讓測試在秒級結束，不是判準放寬。
    """
    ts = load_tasks("humanevalplus", "g-r529-he", 6)
    pr = probe_instrument(ts, lambda _obj: None, sample=6, bank="humanevalplus",
                          coverage_tasks=ts)
    assert pr["n"] == 6
    assert pr["ref_pass"] == 6 and pr["broken_rejected"] == 6
    assert pr["visible_n"] == 6
    assert pr["visible_ref_pass"] == 6 and pr["visible_stub_rejected"] == 6
    # 出貨閘門覆蓋：CONFORM／HMIX 要用的 `visible_check` 每一題都在
    assert pr["coverage_n"] == pr["coverage_visible_n"] == 6


# ── 4. 排除清單：逐題有名字、有成因，且不動 MBPP+ ─────────────────────────
def test_exclusions_are_pinned_with_reasons():
    assert len(GAIN_HUMANEVAL_EXCLUSIONS) == 8
    assert set(GAIN_HUMANEVAL_EXCLUSIONS) == {
        f"humanevalplus_HumanEval/{k}"
        for k in (39, 160, 162, 83, 100, 130, 139, 15)}
    for tid, why in GAIN_HUMANEVAL_EXCLUSIONS.items():
        assert isinstance(why, str) and len(why) > 15, tid


def test_mbpp_exclusions_are_untouched():
    """2× 餘裕那條門檻對 evalplus 是 no-op（那 371 題最慢 2.98 s）——
    本輪**不准**順手改動 MBPP+ 的七題，那會改掉一個被引用過的題庫定義。"""
    assert len(GAIN_EVALPLUS_RESOURCE_EXCLUSIONS) == 7
    assert set(GAIN_EVALPLUS_RESOURCE_EXCLUSIONS) == {
        f"mbppplus_Mbpp/{k}" for k in (255, 271, 392, 599, 603, 630, 644)}


def test_exclusion_reasons_name_the_three_causes():
    """三種成因不准全掛在「資源」名下：允許清單／記憶體／時間餘裕各有其題。"""
    blob = " ".join(GAIN_HUMANEVAL_EXCLUSIONS.values())
    assert "allowlist" in blob and "eval()" in blob
    assert blob.count("128 MiB") == 4
    assert "margin" in blob


# ── 5. CLI 接線 ───────────────────────────────────────────────────────────
def test_bank_is_in_the_cli_choices():
    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    assert '"evalplus", "humanevalplus", "builtin"' in src


def test_bank_filter_does_not_apply_to_humanevalplus():
    """它沒有平台原生標籤——`family` 是我們自己貼的啟發式，不准拿來切層。"""
    assert bank_strata("humanevalplus") == {}
    with pytest.raises(SystemExit, match="不成立"):
        load_tasks("humanevalplus", "s", 5, bank_filter="difficulty=hard")


def test_record_bank_field_flag_exists_and_defaults_off():
    out = subprocess.run(
        [sys.executable, str(ROOT / "ops" / "gain" / "gain_run.py"), "--help"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert "--record-bank-field" in out.stdout
    assert "humanevalplus" in out.stdout


@needs_pack
def test_prompt_carries_no_ground_truth_through_the_runner_path():
    """最後一道：從 runner 真正拿到的 task 上掃一次 GT。"""
    ld = EvalPlusHumanEvalLoader()
    bodies = {r["task_id"]: r["canonical_solution"].strip() for r in ld._records}
    for t in load_tasks("humanevalplus", "g-r529-he", 30):
        raw_id = t["task_id"].removeprefix("humanevalplus_")
        assert bodies[raw_id] not in t["prompt"]
        assert "plus_input" not in t["prompt"]
