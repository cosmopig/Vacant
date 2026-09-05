"""發射器與預註冊文件不准漂開（R449B：EQ5 第一次跑在難題上）。

這支在架構裡承重什麼：R440G 閘門（`gain_run.py:1259-1267`）只檢查
「DECISION 檔存在，且內文含 `--out` 的目錄名」。它**檢查不到** seed、n、offset、
arms、bank、模型、timeout——那些打錯了，run 會照跑，而且跑出來的東西看起來
完全正常：`runs/g_r449_eq5_lcb2` 裡會有 120 列漂亮的資料，只是它答的
不是 `DECISION_20260906_R449B_EQ5_LCB2_PREREG.md` 註冊的那個問題。

本 run 最貴的兩格：
  **`--bank lcb2`**——整個 run 的意義就是「換到難題」。掉回 evalplus 的話跑出來的是
  r446/r448 的第三次重複，而 rows 裡的 `bank` 欄位事後看得出來，但那時機時已經燒掉了。
  **seed**——抄到一顆用過的 seed，跑出來的是「同抽樣再跑一次」；r446 那顆
  `g-r212-route-20260828` 在 repo 裡被 21 個 run 用過，靠人眼看不出來。
  所以發射器掃過**所有** `runs/*/summary.json`，本檔釘住它真的在掃而不是比字串。

本檔零 API、零 ssh、不寫 `runs/`（只讀 `runs/*/summary.json` 做新鮮度證明），
只讀兩個文字檔（外加 `bash -n`）。
"""
from __future__ import annotations

import glob
import json
import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SH = ROOT / "ops" / "gain" / "launch_eq5_lcb2.sh"
DEC = ROOT / "DECISION_20260906_R449B_EQ5_LCB2_PREREG.md"

RUN_NAME = "g_r449_eq5_lcb2"
SEED = "g-r449-eq5-lcb2"
MODEL = "gemma-4-12b-it-qat"
PRIOR_DEFAULT = "runs/g_r448_eq5_mbpp_seed2"


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


def _code_lines(text: str) -> list[str]:
    """把每一行的 `#` 之後砍掉——歷史敘述留在註解裡沒關係，邏輯不准寫死。"""
    return [line.split("#", 1)[0] for line in text.splitlines()]


# ── 語法 ───────────────────────────────────────────────────────────────
def test_launcher_is_valid_bash(sh: str) -> None:
    bash = shutil.which("bash")
    assert bash, "沒有 bash 可用"
    r = subprocess.run([bash, "-n", str(SH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_launcher_is_executable() -> None:
    assert SH.stat().st_mode & 0o111, "發射器沒有執行位元"


# ── R440G 閘門：DECISION 必須真的授權這個 run 名字 ──────────────────────
def test_decision_file_exists_and_authorizes_the_run_name(sh: str, dec: str) -> None:
    assert _var(sh, "DEC") == DEC.name
    # gain_run.py 的閘門條件逐字：run 名字要出現在 DECISION 內文裡。
    assert RUN_NAME in dec
    assert _var(sh, "OUT") == f"runs/{RUN_NAME}"


def test_decision_authorizes_the_zero_api_probe_out_name(dec: str) -> None:
    # 量具指令用 `--out /tmp/eq5lcb2_probe`，R440G 檢查的是 basename ⇒ 這個字串
    # 也必須寫在 DECISION 裡，否則預註冊的自我驗證指令自己跑不起來。
    assert "eq5lcb2_probe" in dec


def test_decision_names_the_seed_and_launcher_greps_for_it(sh: str, dec: str) -> None:
    # 閘門檢查不到 seed，所以發射器自己 grep DECISION；這裡釘住兩邊寫著同一顆。
    assert _var(sh, "SEED") == SEED
    assert SEED in dec
    assert 'grep -q -- "$SEED" "$DEC"' in sh
    assert "abort_seed_not_prereg" in sh


# ── 這個 run 的意義：新題庫（難題）＋沒用過的 seed ──────────────────────
def test_seed_is_absent_from_every_run_summary() -> None:
    """事前證明：這顆 seed 沒有在任何一個既有 run 裡被用過。"""
    files = sorted(glob.glob(str(ROOT / "runs" / "*" / "summary.json")))
    assert files, "一個 runs/*/summary.json 都沒掃到——量不到不是通過"
    used = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                if json.load(fh).get("seed") == SEED:
                    used.append(f)
        except Exception:                                    # noqa: BLE001
            pass
    assert not used, f"seed {SEED} 已經被用過：{used}"


def test_launcher_scans_all_summaries_not_a_single_string_compare(sh: str) -> None:
    """abort_seed_not_fresh 必須是真的掃描，不是跟某一顆舊 seed 比字串。"""
    assert "abort_seed_not_fresh" in sh
    assert 'glob.glob("runs/*/summary.json")' in sh, "seed 新鮮度沒有掃 runs/*/summary.json"
    assert '.get("seed")' in sh, "掃描沒有真的讀 summary.json 的 seed 欄位"
    # 掃到 0 個檔案要停（「都很新鮮」與「線沒接上」不准長得一樣）。
    assert '[ "$n_files" -gt 0 ]' in sh
    assert '[ "$n_hits" -eq 0 ]' in sh
    # 舊寫法（跟單一顆 r446 seed 比字串）不准回來。
    for line in _code_lines(sh):
        assert "g-r212-route" not in line, f"又退回單顆 seed 比字串: {line!r}"


def test_bank_is_lcb2_everywhere(sh: str, dec: str) -> None:
    assert "--bank lcb2" in sh
    assert "--bank lcb2" in dec
    for line in _code_lines(sh):
        assert "--bank evalplus" not in line, f"掉回 MBPP+ 題庫: {line!r}"


def test_bank_file_presence_is_checked(sh: str) -> None:
    assert _var(sh, "BANK_FILE") == "ops/gain/data/lcb_bank_v2.jsonl"
    assert (ROOT / "ops" / "gain" / "data" / "lcb_bank_v2.jsonl").exists()
    assert "abort_no_bank" in sh


# ── 註冊過的旗標必須逐字出現在發射指令裡 ────────────────────────────────
@pytest.mark.parametrize("flag", [
    "--n 120", "--offset 0", "--arms EQ5", "--bank lcb2",
    "--probe-sample 0", "--request-timeout-s 600", "--review-timeout-s 380",
    '--models "$MODEL"', '--seed "$SEED"', '--decision "$DEC"', '--out "$OUT"',
])
def test_launch_command_carries_the_registered_flag(sh: str, flag: str) -> None:
    assert flag in sh, f"發射指令少了 {flag}"


def test_model_is_the_registered_one(sh: str, dec: str) -> None:
    assert _var(sh, "MODEL") == MODEL
    assert MODEL in dec


def test_decision_registers_the_same_flags(dec: str) -> None:
    for flag in ("--n 120", "--offset 0", "--arms EQ5", "--bank lcb2",
                 "--probe-sample 0", "--request-timeout-s 600",
                 "--review-timeout-s 380"):
        assert flag in dec, f"DECISION 沒寫到 {flag}"


# ── 從 launch_lcb2.sh／launch_eq5_seed2.sh 繼承的守則，一條都不准掉 ─────
def test_wait_pattern_is_anchored_and_uses_prior_run(sh: str) -> None:
    pat = _var(sh, "WAIT_PAT")
    # 未錨行首會匹配到 grep 自己 ⇒ 等待條件恆為真 ⇒ 永遠不發射（R440E）。
    assert pat.startswith("^python3 ops/gain/gain_run"), pat
    # 等待目標是環境變數，不是再寫死一個 run 名字。
    assert "$PRIOR_RUN" in pat


def test_prior_run_is_configurable_env_var_with_r448_default(sh: str) -> None:
    assert f'PRIOR_RUN="${{PRIOR_RUN:-{PRIOR_DEFAULT}}}"' in sh


def test_prior_run_default_is_already_terminal() -> None:
    """預設等待目標必須是真的已收官的 run，否則發射器預設就會 abort。"""
    p = ROOT / PRIOR_DEFAULT / "summary.json"
    assert p.exists(), f"{PRIOR_DEFAULT}/summary.json 不存在"
    with p.open(encoding="utf-8") as fh:
        assert json.load(fh).get("run_terminal") is True


def test_terminal_check_reads_prior_run_summary(sh: str) -> None:
    # abort_prior_not_terminal 的 terminal 檢查跟 WAIT_PAT 必須讀同一個變數，
    # 否則等待迴圈跟中止檢查會看兩個不同的 run。
    assert '"$PRIOR_RUN/summary.json"' in sh
    assert "abort_prior_not_terminal" in sh
    assert "run_terminal" in sh


def test_no_hardcoded_prior_run_literal_outside_comments_and_default(sh: str) -> None:
    """除了 PRIOR_RUN 的預設值那一行，可執行碼裡不准出現任何 run 名字字面值。"""
    for line in _code_lines(sh):
        if "PRIOR_RUN:-" in line:            # 預設值那一行是唯一合法的字面值
            continue
        for stale in ("g_r447", "g_r461", "g_r448", "g_r446"):
            assert stale not in line, f"{stale} 字面值漏在可執行碼: {line!r}"


def test_single_run_recheck_before_launch_is_anchored(sh: str) -> None:
    assert 'grep -c "^python3 ops/gain/gain_run\\.py"' in sh
    assert "abort_other_run" in sh


def test_probe_checks_body_not_only_http_200(sh: str) -> None:
    assert "body_ok=" in sh
    assert '[ "$code" = "200" ] && [ "$body" = "yes" ]' in sh
    assert '[ "$ok" -eq 3 ]' in sh, "探針要 3/3 才准發射"
    assert "for i in 1 2 3; do" in sh, "探針次數不是 3"


def test_existing_evidence_is_never_overwritten(sh: str) -> None:
    assert "abort_dir_exists" in sh and "abort_launchlog_exists" in sh
    # launch.log 一律 append：舊證據不准被蓋掉。
    assert '>>"$OUT.launch.log"' in sh
    assert '>"$OUT.launch.log"' not in sh.replace('>>"$OUT.launch.log"', "")


def test_flock_guards_against_duplicate_launchers(sh: str) -> None:
    assert "flock -n 9" in sh
    assert "9>&-" in sh, "發射的子行程要關掉鎖的 fd，否則鎖跟著 run 活著"


def test_machine_readable_result_line(sh: str) -> None:
    assert "EQ5_LCB2_LAUNCH_RESULT=" in sh
    # finish() 是唯一的出口，最後一行必須是它 ⇒ 每條路徑都留下結果行。
    assert sh.strip().splitlines()[-1].startswith("finish ")


# ── 突變檢查：把守則拿掉，指名的測試必須變紅 ────────────────────────────
#
# 記憶鐵律：偵測條要有牙齒。下面三個突變體逐一改動發射器的**字串複本**，
# 然後直接呼叫那條測試——沒叫的話它就是裝飾品。判準不是 rc≠0。
def _expect_fail(fn, text: str, why: str) -> None:
    try:
        fn(text)
    except AssertionError:
        return
    raise AssertionError(f"突變體沒有被抓到：{why}")


def _seed_used_by_some_run(seed: str) -> bool:
    """把發射器 abort_seed_not_fresh 的判準在測試側重算一次（同一個定義）。"""
    for f in sorted(glob.glob(str(ROOT / "runs" / "*" / "summary.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                if json.load(fh).get("seed") == seed:
                    return True
        except Exception:                                    # noqa: BLE001
            pass
    return False


def test_mutation_stale_seed_is_caught_only_by_the_summary_scan(sh: str, dec: str) -> None:
    """M1：seed 抄成 r448 用過的那一顆。

    **這條突變是本檔最重要的一條，因為它證明另一道擋門擋不住它。**
    發射器有兩道與 seed 有關的擋門：
      (i)  `abort_seed_not_prereg`＝`grep -q -- "$SEED" "$DEC"`；
      (ii) `abort_seed_not_fresh`＝掃過所有 `runs/*/summary.json`。
    本檔的 DECISION **正當地**在錨值表裡引用了 r448 的 seed（§一 的三 run 對照），
    所以 (i) 對這個突變**會放行**——撰寫本檔的過程中實測到這一點。
    擋得住它的只有 (ii)。這就是為什麼新鮮度檢查必須是真的掃描。
    """
    stale = "g-r448-eq5-seed2"
    mutant = sh.replace(f'SEED="{SEED}"', f'SEED="{stale}"')
    assert mutant != sh and _var(mutant, "SEED") == stale

    # (i) 擋不住：那顆 seed 確實寫在本檔的 DECISION 內文裡（錨值表）。
    assert stale in dec, "前提變了：r448 的 seed 已不在本檔內文，本條的論證要重寫"

    # (ii) 擋得住：它在 runs/*/summary.json 裡被用過。
    assert _seed_used_by_some_run(stale), f"{stale} 竟然沒被任何 run 用過"
    assert not _seed_used_by_some_run(SEED), f"{SEED} 已經被用過"

    # 而且發射器真的把 (ii) 接成了會 abort 的路徑，不只是算了個數字。
    assert 'finish abort_seed_not_fresh' in mutant


def test_mutation_unanchored_wait_pattern_is_caught(sh: str) -> None:
    """M2：等待字串少了 `^` ⇒ grep 會匹配到自己，條件恆為真，永遠不發射。"""
    mutant = sh.replace('WAIT_PAT="^python3', 'WAIT_PAT="python3')
    assert mutant != sh
    _expect_fail(test_wait_pattern_is_anchored_and_uses_prior_run, mutant, "錨消失了")


def test_mutation_probe_count_reduced_is_caught(sh: str) -> None:
    """M3：探針從 3 次改成 1 次 ⇒ 單次 200 就發射，端點抖動會被當成健康。"""
    mutant = sh.replace("for i in 1 2 3; do", "for i in 1; do").replace(
        '[ "$ok" -eq 3 ]', '[ "$ok" -eq 1 ]')
    assert mutant != sh
    _expect_fail(test_probe_checks_body_not_only_http_200, mutant, "探針只剩 1 次")


def test_mutation_bank_flipped_to_evalplus_is_caught(sh: str) -> None:
    """M4：題庫掉回 evalplus ⇒ 這個 run 就不是「難題上的第一次」了。"""
    mutant = sh.replace("--bank lcb2", "--bank evalplus")
    assert mutant != sh
    _expect_fail(lambda t: test_bank_is_lcb2_everywhere(t, DEC.read_text(encoding="utf-8")),
                 mutant, "bank 被換成 evalplus")


def test_mutation_seed_scan_replaced_by_string_compare_is_caught(sh: str) -> None:
    """M5：新鮮度檢查退回「跟一顆舊 seed 比字串」⇒ 掃描擋門必須變紅。"""
    mutant = sh.replace('glob.glob("runs/*/summary.json")', '["runs/g_r446_eq5_mbpp/summary.json"]')
    assert mutant != sh
    _expect_fail(test_launcher_scans_all_summaries_not_a_single_string_compare,
                 mutant, "掃描被換成單一檔案")


# ── 展場口徑紅線（CLAUDE.md）─────────────────────────────────────────
@pytest.mark.parametrize("word", ["信任", "防止", "保證"])
def test_forbidden_exhibition_words_appear_only_as_prohibitions(
        word: str, sh: str, dec: str) -> None:
    assert word not in sh
    for line in dec.splitlines():
        if word in line:
            assert "不准出現" in line, f"DECISION 用了「{word}」：{line.strip()}"


# ── 決策規則與檢定力必須在資料之前寫死（本檔存在的理由）──────────────
def test_decision_rule_is_written_before_any_data(dec: str) -> None:
    for state in ("REPLICATED_ON_HARD", "NOT_REPLICATED_ON_HARD",
                  "UNRESOLVED", "INVALID"):
        assert state in dec, f"決策規則缺 {state}"
    for pred in ("P-1", "P-2", "P-3", "P-4", "P-5", "P-6", "P-7", "P-8", "P-9"):
        assert pred in dec


def test_decision_names_the_arbiter_fields_from_the_analyzer(dec: str) -> None:
    """判準要指名它讀 analyze_eq5.py 輸出的哪個 key，不准靠工具印的字串。"""
    for field in ("paired.delta_pp", "paired.ci95_lo_pp", "paired.n_discordant",
                  "calls_per_task", "budget_all_exactly_5", "void_rate_pp",
                  "gate.deliv_pp_denom_measured", "vote.deliv_pp_denom_measured",
                  "gate.coverage_pp", "same_choice_effective_rate_pp",
                  "paired.b_gate_only", "paired.c_vote_only",
                  "power.mde_at_n_pp", "power.n80_if_true_effect_is_observed"):
        assert field in dec, f"DECISION 沒指名仲裁欄位 {field}"


def test_decision_states_underpowered_before_the_data(dec: str) -> None:
    """n=120 檢定力不足這件事必須寫在資料之前，不是收官時拿來解釋結果。"""
    assert "UNDERPOWERED" in dec
    assert "18.1%" in dec, "事前檢定力（MBPP+ 效果原樣搬過來）沒寫上去"
    assert "MDE" in dec and "N₈₀" in dec


def test_decision_forbids_editing_the_r446_prereg_constant(dec: str) -> None:
    assert "analyze_eq5.py" in dec
    assert "PREREG" in dec
    # 那支常數是 r446 的事前註冊，改它等於改別人的事前註冊。
    assert any("不准" in line and "PREREG" in line for line in dec.splitlines()), \
        "DECISION 沒有寫死「不准改 analyze_eq5.py 的 PREREG」"


def test_decision_carries_the_lcb_honesty_boundaries(dec: str) -> None:
    """R440Z §五 的誠實邊界不准在換臂的時候掉。"""
    assert "12/120" in dec, "量具只覆蓋 12/120 沒寫"
    assert "lcb_3026" in dec and "2023-08-26" in dec, "污染定界對 lcb_3026 無效沒寫"
    assert "lcb_3763" in dec and "lcb_3613" in dec, "兩題已知量具問題沒寫"
    assert "g_r447_conform_lcb2" in dec, "與 r447 同題不同設計的關係沒寫"
    assert "不是獨立樣本" in dec


def test_this_test_never_creates_an_empty_run_dir() -> None:
    """本檔零 API、不寫 `runs/`——唯一會出錯的方式是留下一個空目錄。

    刻意**不**寫成 `assert not dir.exists()`：`tests/test_r448_launcher_prereg.py`
    就是那樣寫的，而 r448 真的跑完之後那條就永遠是紅的（實測），
    把「這支測試弄髒了 runs/」與「那個 run 已經跑過了」混成同一個訊號。
    真正要守的是前者：目錄若存在，裡面必須有真的 run 產物。
    （空目錄還會撞上發射器的 `abort_dir_exists`，那才是它真正的代價。）
    """
    d = ROOT / "runs" / RUN_NAME
    if not d.exists():
        return
    assert any((d / f).exists() for f in ("rows.jsonl", "summary.json",
                                          "notes.jsonl", "calls.jsonl")), \
        f"{d} 存在但沒有任何 run 產物——像是被測試或誤操作建出來的空目錄"
