"""發射器與預註冊文件不准漂開（R448）。

這支在架構裡承重什麼：R440G 閘門（`gain_run.py:1228-1233`）只檢查
「DECISION 檔存在，且內文含 `--out` 的目錄名」。它**檢查不到** seed、n、offset、
arms、bank、模型、timeout——那些打錯了，run 會照跑，而且跑出來的東西看起來
完全正常：`runs/g_r448_eq5_mbpp_seed2` 裡會有 371 列漂亮的資料，只是它答的
不是 `DECISION_20260904_R448_EQ5_REPLICATION_PREREG.md` 註冊的那個問題。

最貴的一格是 **seed**：R448 的整個價值就在於「換一顆 seed」（R446 §五 的推翻
條件）。抄回 r446 那一顆的話，跑出來的是「同條件再跑一次」，而 rows 裡沒有任何
欄位事後分得出這兩件事的差別——只有發射時擋得住。

本檔零 API、零 ssh、不碰 `runs/`，只讀兩個文字檔（外加 `bash -n`）。
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SH = ROOT / "ops" / "gain" / "launch_eq5_seed2.sh"
DEC = ROOT / "DECISION_20260904_R448_EQ5_REPLICATION_PREREG.md"

RUN_NAME = "g_r448_eq5_mbpp_seed2"
SEED = "g-r448-eq5-seed2"
R446_SEED = "g-r212-route-20260828"
MODEL = "gemma-4-12b-it-qat"


@pytest.fixture(scope="module")
def sh() -> str:
    return SH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dec() -> str:
    return DEC.read_text(encoding="utf-8")


def _var(text: str, name: str) -> str:
    """取發射器頂端 `NAME="value"` 的值（只認雙引號的字面值）。"""
    m = re.search(rf'^{name}="([^"]*)"$', text, re.M)
    assert m, f"發射器裡找不到 {name}= 的字面定義"
    return m.group(1)


# ── 語法 ───────────────────────────────────────────────────────────────
def test_launcher_is_valid_bash(sh: str) -> None:
    bash = shutil.which("bash")
    assert bash, "沒有 bash 可用"
    r = subprocess.run([bash, "-n", str(SH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── R440G 閘門：DECISION 必須真的授權這個 run 名字 ──────────────────────
def test_decision_file_exists_and_authorizes_the_run_name(sh: str, dec: str) -> None:
    assert _var(sh, "DEC") == DEC.name
    # gain_run.py 的閘門條件逐字：run 名字要出現在 DECISION 內文裡。
    assert RUN_NAME in dec
    assert _var(sh, "OUT") == f"runs/{RUN_NAME}"


def test_decision_names_the_fresh_seed(sh: str, dec: str) -> None:
    # 閘門檢查不到 seed，所以發射器自己 grep DECISION；這裡釘住兩邊都寫著同一顆。
    assert _var(sh, "SEED") == SEED
    assert SEED in dec
    assert f'grep -q -- "$SEED" "$DEC"' in sh


# ── 這個 run 的意義就在 seed 不同 ──────────────────────────────────────
def test_seed_differs_from_r446_and_the_launcher_checks_it(sh: str) -> None:
    assert _var(sh, "SEED") != _var(sh, "R446_SEED")
    assert _var(sh, "R446_SEED") == R446_SEED
    assert '[ "$SEED" != "$R446_SEED" ]' in sh, "發射器沒有擋『抄回舊 seed』"


# ── 其餘參數必須與 r446 逐字相同（唯一的差別是 seed）────────────────────
@pytest.mark.parametrize("flag", [
    "--n 371", "--offset 0", "--arms EQ5", "--bank evalplus",
    "--probe-sample 0", "--request-timeout-s 600", "--review-timeout-s 380",
    '--models "$MODEL"', '--seed "$SEED"', '--decision "$DEC"', '--out "$OUT"',
])
def test_launch_command_carries_the_registered_flag(sh: str, flag: str) -> None:
    assert flag in sh, f"發射指令少了 {flag}"


def test_model_is_the_registered_one(sh: str, dec: str) -> None:
    assert _var(sh, "MODEL") == MODEL
    assert MODEL in dec


def test_decision_registers_the_same_flags(dec: str) -> None:
    for flag in ("--n 371", "--offset 0", "--arms EQ5", "--bank evalplus",
                 "--probe-sample 0"):
        assert flag in dec, f"DECISION 沒寫到 {flag}"


# ── 從 launch_lcb2.sh 繼承的守則，一條都不准掉 ─────────────────────────
def test_wait_pattern_is_anchored_and_names_r447(sh: str) -> None:
    pat = _var(sh, "WAIT_PAT")
    # 未錨行首會匹配到 grep 自己 ⇒ 等待條件恆為真 ⇒ 永遠不發射（R440E）。
    assert pat.startswith("^python3 ops/gain/gain_run"), pat
    assert "runs/g_r447_conform_lcb2" in pat


def test_single_run_recheck_before_launch_is_anchored(sh: str) -> None:
    assert 'grep -c "^python3 ops/gain/gain_run\\.py"' in sh
    assert "abort_other_run" in sh


def test_probe_checks_body_not_only_http_200(sh: str) -> None:
    assert 'body_ok=' in sh
    assert '[ "$code" = "200" ] && [ "$body" = "yes" ]' in sh
    assert '[ "$ok" -eq 3 ]' in sh, "探針要 3/3 才准發射"


def test_existing_evidence_is_never_overwritten(sh: str) -> None:
    assert 'abort_dir_exists' in sh and 'abort_launchlog_exists' in sh
    # launch.log 一律 append：舊證據不准被蓋掉。
    assert '>>"$OUT.launch.log"' in sh
    assert '>"$OUT.launch.log"' not in sh.replace('>>"$OUT.launch.log"', "")


def test_flock_guards_against_duplicate_launchers(sh: str) -> None:
    assert "flock -n 9" in sh
    assert "9>&-" in sh, "發射的子行程要關掉鎖的 fd，否則鎖跟著 run 活著"


def test_waits_for_prior_run_or_refuses_to_start(sh: str) -> None:
    # 比 launch_lcb2.sh 多的一道：r447 既沒在跑也還沒 terminal ⇒ 停，不搶端點。
    assert "abort_prior_not_terminal" in sh
    assert "run_terminal" in sh


def test_evalplus_pack_presence_is_checked(sh: str) -> None:
    assert _var(sh, "BANK_FILE").endswith("MbppPlus-v0.2.0.jsonl.gz")
    assert "abort_no_bank" in sh


def test_machine_readable_result_line(sh: str) -> None:
    assert "EQ5_SEED2_LAUNCH_RESULT=" in sh


# ── 展場口徑紅線（CLAUDE.md）─────────────────────────────────────────
@pytest.mark.parametrize("word", ["信任", "防止", "保證"])
def test_forbidden_exhibition_words_appear_only_as_prohibitions(
        word: str, sh: str, dec: str) -> None:
    assert word not in sh
    for line in dec.splitlines():
        if word in line:
            assert "不准出現" in line, f"DECISION 用了「{word}」：{line.strip()}"


# ── 決策規則必須在資料之前寫死（本檔存在的理由）──────────────────────
def test_decision_rule_is_written_before_any_data(dec: str) -> None:
    for state in ("REPLICATED", "NOT_REPLICATED", "UNRESOLVED", "INVALID"):
        assert state in dec, f"決策規則缺 {state}"
    for pred in ("P-1", "P-2", "P-3", "P-4", "P-5", "P-6"):
        assert pred in dec
    # 併庫不准當獨立樣本（R680 Q1 在這裡是 MISS）。
    assert "n=742" in dec


def test_r448_run_dir_is_not_created_by_this_test() -> None:
    assert not (ROOT / "runs" / RUN_NAME).exists()
