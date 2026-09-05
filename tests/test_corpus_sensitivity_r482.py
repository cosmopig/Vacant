"""R482 接線測試：語料增長擾動 census 的判準與目標發現。

植入缺陷（`R482_MUTANT`）：
  M1_IGNORE_NONDET        不決定性被當成 DECAY_PRONE
  M2_ANY_CHANGE_IS_FINE   任何 rc 變化都判 INSENSITIVE（＝沒牙齒）
  M3_STRING_HEURISTIC     退回 `"--selftest" in src` 的舊發現法
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ops" / "gain"))

import r482_corpus_sensitivity_census as C  # noqa: E402

MUT = os.environ.get("R482_MUTANT", "")


def test_classification_rules_match_prereg():
    """判準 §三 逐條。"""
    assert C.classify(0, 0, {"P_MD": 0})[0] == "INSENSITIVE"
    assert C.classify(0, 0, {"P_MD": 1})[0] == "DECAY_PRONE"
    assert C.classify(1, 1, {"P_MD": 0})[0] == "MASKING"
    assert C.classify(1, 1, {"P_MD": 2})[0] == "SENSITIVE_OTHER"
    assert C.classify(0, 0, {"P_MD": -9})[0] == "BROKEN"


def test_nondeterminism_beats_decay():
    """判準 §六-4：clean 兩次不同 ⇒ 不准記成 DECAY_PRONE。"""
    assert C.classify(0, 1, {"P_MD": 1})[0] == "NONDETERMINISTIC"


def test_passer_is_not_a_target():
    """只把 --selftest 傳給別人的工具不是受測目標，而且要具名列出。"""
    src = 'import subprocess\nsubprocess.run(["t.py", "--selftest"])\n'
    assert not C.provides_selftest(src)
    assert C.provides_selftest('if "--selftest" in sys.argv:\n    pass\n')
    assert C.provides_selftest('ap.add_argument("--selftest", action="store_true")')


def test_real_repo_split_is_named_not_silent():
    """真 repo 上：受測數 + 只提及數 = 字面出現數（沒有人被安靜丟掉）。"""
    gain = ROOT / "ops" / "gain"
    tools, mentions = C.discover_tools(gain)
    literal = [p.name for p in sorted(gain.glob("*.py"))
               if p.name not in C.EXCLUDED
               and "--selftest" in p.read_text(encoding="utf-8", errors="replace")]
    assert sorted(tools + mentions) == sorted(literal)
    assert len(mentions) > 0, "R482 §九 的 8 支若歸零，代表發現法又退回字面比對"


def test_perturbations_are_cleaned_up():
    """擾動檔絕不能留在工作區（會被別的 session commit 進去）。"""
    for rel, _ in C.PERTURBATIONS.values():
        assert not (ROOT / rel).exists(), f"殘留擾動檔 {rel}"
