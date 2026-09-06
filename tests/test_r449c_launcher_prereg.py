"""發射器與預註冊文件不准漂開（R449C：EQ5 的第三個題庫，LCB v3 189 題）。

這支在架構裡承重什麼：R440G 閘門（`gain_run.py`）只檢查
「DECISION 檔存在，且內文含 `--out` 的目錄名」。它**檢查不到** seed、n、offset、
arms、bank、模型、timeout——那些打錯了，run 會照跑，而且跑出來的東西看起來
完全正常：`runs/g_r449c_eq5_lcb3` 裡會有 189 列漂亮的資料，只是它答的
不是 `DECISION_20260906_R449C_EQ5_LCB3_PREREG.md` 註冊的那個問題。

本 run 最貴的三格：
  **`--bank lcb3`**——整個 run 的意義就是「第三批題目」。掉回 lcb2 的話跑出來的是
  r449b 的重複，而 rows 裡的 `bank` 欄位事後看得出來，但那時機時已經燒掉了。
  **`--n 189`**——lcb3 只有 189 題；沿用 r449b 的 120 會安靜跑一個別的實驗
  （`load_tasks` 會乖乖切前 120 題，一個警告都不印）。
  **seed**——抄到一顆用過的 seed，跑出來的是「同抽樣再跑一次」；r446 那顆
  `g-r212-route-20260828` 在 repo 裡被 21 個 run 用過，靠人眼看不出來。
  所以發射器掃過**所有** `runs/*/summary.json`，本檔釘住它真的在掃而不是比字串。

外加本檔比 `tests/test_r449b_launcher_prereg.py` 多的一組：
  **九條預測指名的仲裁欄位，必須真的存在於 `analyze_eq5.py` 的輸出 dict 裡**
  ——既 grep 原始碼（工具改名時會紅），也真的呼叫 `analyze()` 走一次
  dotted path（欄位被搬到別層時會紅）。判準指名了一個不存在的 key，
  收官時會安靜地拿到 `None` 然後被讀成「量到 0」。

本檔零 API、零 ssh、不寫 `runs/`（只讀 `runs/*/summary.json` 做新鮮度證明），
只讀三個檔（DECISION、發射器、analyzer）外加 `bash -n`。
**本檔刻意不寫任何「`runs/<run>` 目錄不存在」的斷言**：
`tests/test_r448_launcher_prereg.py` 那樣寫過，那個 run 真的跑完之後它就永遠是紅的，
把「這支測試弄髒了 runs/」與「那個 run 已經跑過了」混成同一個訊號。
"""
from __future__ import annotations

import glob
import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SH = ROOT / "ops" / "gain" / "launch_eq5_lcb3.sh"
DEC = ROOT / "DECISION_20260906_R449C_EQ5_LCB3_PREREG.md"
ANALYZER = ROOT / "ops" / "gain" / "analyze_eq5.py"

RUN_NAME = "g_r449c_eq5_lcb3"
SEED = "g-r449c-eq5-lcb3"
MODEL = "gemma-4-12b-it-qat"
PRIOR_DEFAULT = "runs/g_r449_eq5_lcb2"
BANK_FILE = "ops/gain/data/lcb_bank_v3.jsonl"
N_TASKS = 189

# §三 的九條預測 + §三 末「無條件一併印」的次要量，逐字就是本檔要釘的東西。
ARBITER_FIELDS = (
    "paired.delta_pp",                    # P-1
    "paired.ci95_lo_pp",                  # P-2（主判準）
    "paired.n_discordant",                # P-3
    "calls_per_task",                     # P-4
    "budget_all_exactly_5",               # P-4
    "void_rate_pp",                       # P-5
    "gate.deliv_pp_denom_measured",       # P-6
    "vote.deliv_pp_denom_measured",       # P-7
    "gate.coverage_pp",                   # P-8
    "same_choice_effective_rate_pp",      # P-9
    # 次要量（無條件一併印）
    "gate.deliv_pp_denom_accepted",
    "same_choice_rate_pp",
    "false_same_choice_n",
    "paired.b_gate_only",
    "paired.c_vote_only",
    "paired.p_mcnemar_exact",
    "paired.ci95_hi_pp",
    "power.mde_at_n_pp",
    "power.n80_if_true_effect_is_observed",
    "power.n_needed_halfwidth_5pp",
    "verdict_four_cell",
)


@pytest.fixture(scope="module")
def sh() -> str:
    return SH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dec() -> str:
    return DEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def analyzer_src() -> str:
    return ANALYZER.read_text(encoding="utf-8")


def _var(text: str, name: str) -> str:
    """取發射器頂端 `NAME="value"` 的值（只認雙引號的字面值）。"""
    m = re.search(rf'^{name}="([^"]*)"$', text, re.M)
    assert m, f"發射器裡找不到 {name}= 的字面定義"
    return m.group(1)


def _code_lines(text: str) -> list[str]:
    """把每一行的 `#` 之後砍掉——歷史敘述留在註解裡沒關係，邏輯不准寫死。"""
    return [line.split("#", 1)[0] for line in text.splitlines()]


# ── 語法 ───────────────────────────────────────────────────────────────
def test_launcher_is_valid_bash() -> None:
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
    # 量具指令用 `--out /tmp/eq5lcb3_probe`，R440G 檢查的是 basename ⇒ 這個字串
    # 也必須寫在 DECISION 裡，否則預註冊的自我驗證指令自己跑不起來。
    assert "eq5lcb3_probe" in dec


def test_decision_names_the_seed_and_launcher_greps_for_it(sh: str, dec: str) -> None:
    # 閘門檢查不到 seed，所以發射器自己 grep DECISION；這裡釘住兩邊寫著同一顆。
    assert _var(sh, "SEED") == SEED
    assert SEED in dec
    assert 'grep -q -- "$SEED" "$DEC"' in sh
    assert "abort_seed_not_prereg" in sh


# ── 這個 run 的意義：第三個題庫（189 題）＋沒用過的 seed ────────────────
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
    # 舊寫法（跟單一顆舊 seed 比字串）不准回來。
    for line in _code_lines(sh):
        for stale in ("g-r212-route", "g-r448-eq5-seed2", "g-r449-eq5-lcb2", "g-r461-lcb3"):
            assert stale not in line, f"又退回單顆 seed 比字串: {line!r}"


def test_bank_is_lcb3_everywhere(sh: str, dec: str) -> None:
    assert "--bank lcb3" in sh
    assert "--bank lcb3" in dec
    for line in _code_lines(sh):
        for stale in ("--bank evalplus", "--bank lcb2", "--bank lcb "):
            assert stale not in line, f"題庫掉回舊的: {line!r}"


def test_bank_file_presence_is_checked(sh: str) -> None:
    assert _var(sh, "BANK_FILE") == BANK_FILE
    assert (ROOT / BANK_FILE).exists()
    assert "abort_no_bank" in sh


def test_bank_file_really_has_189_tasks() -> None:
    """`--n 189` 不是隨手寫的數字：它就是 lcb3 題庫的全部題數。"""
    with (ROOT / BANK_FILE).open(encoding="utf-8") as fh:
        n = sum(1 for line in fh if line.strip())
    assert n == N_TASKS, f"lcb3 題庫是 {n} 題，但預註冊寫 {N_TASKS}"


# ── 註冊過的旗標必須逐字出現在發射指令裡 ────────────────────────────────
@pytest.mark.parametrize("flag", [
    "--n 189", "--offset 0", "--arms EQ5", "--bank lcb3",
    "--probe-sample 0", "--request-timeout-s 600", "--review-timeout-s 380",
    '--models "$MODEL"', '--seed "$SEED"', '--decision "$DEC"', '--out "$OUT"',
])
def test_launch_command_carries_the_registered_flag(sh: str, flag: str) -> None:
    assert flag in sh, f"發射指令少了 {flag}"


def test_launcher_never_carries_the_previous_run_task_count(sh: str) -> None:
    """r449b 是 120 題、r446/r448 是 371 題——抄過來會安靜跑一個別的實驗。"""
    for line in _code_lines(sh):
        for stale in ("--n 120", "--n 371"):
            assert stale not in line, f"題數抄成舊 run 的: {line!r}"


def test_model_is_the_registered_one(sh: str, dec: str) -> None:
    assert _var(sh, "MODEL") == MODEL
    assert MODEL in dec


def test_decision_registers_the_same_flags(dec: str) -> None:
    for flag in ("--n 189", "--offset 0", "--arms EQ5", "--bank lcb3",
                 "--probe-sample 0", "--request-timeout-s 600",
                 "--review-timeout-s 380"):
        assert flag in dec, f"DECISION 沒寫到 {flag}"


# ── 從 launch_lcb2.sh／launch_eq5_lcb2.sh 繼承的守則，一條都不准掉 ───────
def test_wait_pattern_is_anchored_and_uses_prior_run(sh: str) -> None:
    pat = _var(sh, "WAIT_PAT")
    # 未錨行首會匹配到 grep 自己 ⇒ 等待條件恆為真 ⇒ 永遠不發射（R440E）。
    assert pat.startswith("^python3 ops/gain/gain_run"), pat
    # 等待目標是環境變數，不是再寫死一個 run 名字。
    assert "$PRIOR_RUN" in pat


def test_prior_run_is_configurable_env_var_with_r449b_default(sh: str) -> None:
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
    """除了 PRIOR_RUN 的預設值那一行，可執行碼裡不准出現任何舊 run 名字字面值。"""
    for line in _code_lines(sh):
        if "PRIOR_RUN:-" in line:            # 預設值那一行是唯一合法的字面值
            continue
        for stale in ("g_r447", "g_r461", "g_r448", "g_r446", "g_r449_eq5"):
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
    assert "EQ5_LCB3_LAUNCH_RESULT=" in sh
    # finish() 是唯一的出口，最後一行必須是它 ⇒ 每條路徑都留下結果行。
    assert sh.strip().splitlines()[-1].startswith("finish ")


# ── 突變檢查：把守則拿掉，指名的測試必須變紅 ────────────────────────────
#
# 記憶鐵律：偵測條要有牙齒。下面五個突變體逐一改動發射器的**字串複本**，
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
    """M1：seed 抄成 r449b 用過的那一顆。

    **這條突變是本檔最重要的一條，因為它證明另一道擋門擋不住它。**
    發射器有兩道與 seed 有關的擋門：
      (i)  `abort_seed_not_prereg`＝`grep -q -- "$SEED" "$DEC"`；
      (ii) `abort_seed_not_fresh`＝掃過所有 `runs/*/summary.json`。
    本檔的 DECISION **正當地**在錨值表裡引用了 r449b 的 seed（§一 的四 run 對照），
    所以 (i) 對這個突變**會放行**。擋得住它的只有 (ii)。
    這就是為什麼新鮮度檢查必須是真的掃描。
    """
    stale = "g-r449-eq5-lcb2"
    mutant = sh.replace(f'SEED="{SEED}"', f'SEED="{stale}"')
    assert mutant != sh and _var(mutant, "SEED") == stale

    # (i) 擋不住：那顆 seed 確實寫在本檔的 DECISION 內文裡（錨值表）。
    assert stale in dec, "前提變了：r449b 的 seed 已不在本檔內文，本條的論證要重寫"

    # (ii) 擋得住：它在 runs/*/summary.json 裡被用過。
    assert _seed_used_by_some_run(stale), f"{stale} 竟然沒被任何 run 用過"
    assert not _seed_used_by_some_run(SEED), f"{SEED} 已經被用過"

    # 而且發射器真的把 (ii) 接成了會 abort 的路徑，不只是算了個數字。
    assert "finish abort_seed_not_fresh" in mutant


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


def test_mutation_bank_flipped_to_lcb2_is_caught(sh: str) -> None:
    """M4：題庫掉回 lcb2 ⇒ 這個 run 就變成 r449b 的重複了。"""
    mutant = sh.replace("--bank lcb3", "--bank lcb2")
    assert mutant != sh
    _expect_fail(lambda t: test_bank_is_lcb3_everywhere(t, DEC.read_text(encoding="utf-8")),
                 mutant, "bank 被換成 lcb2")


def test_mutation_n_copied_from_r449b_is_caught(sh: str) -> None:
    """M5：`--n` 抄成 r449b 的 120 ⇒ 只跑前 120 題，一個警告都不印。"""
    mutant = sh.replace("--n 189", "--n 120")
    assert mutant != sh
    _expect_fail(test_launcher_never_carries_the_previous_run_task_count,
                 mutant, "題數被抄成 120")


def test_mutation_seed_scan_replaced_by_string_compare_is_caught(sh: str) -> None:
    """M6：新鮮度檢查退回「跟一顆舊 seed 比字串」⇒ 掃描擋門必須變紅。"""
    mutant = sh.replace('glob.glob("runs/*/summary.json")',
                        '["runs/g_r449_eq5_lcb2/summary.json"]')
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
    for state in ("REPLICATED_ON_LCB3", "NOT_REPLICATED_ON_LCB3",
                  "UNRESOLVED", "INVALID"):
        assert state in dec, f"決策規則缺 {state}"
    for pred in ("P-1", "P-2", "P-3", "P-4", "P-5", "P-6", "P-7", "P-8", "P-9"):
        assert pred in dec


def test_decision_states_are_not_the_hard_bank_ones(dec: str) -> None:
    """lcb3 不是難題題庫——狀態名不准沿用 r449b 的 `*_ON_HARD`。

    R461 稽核 §二-2：lcb3 的 OFF 失敗率 27.5%，回到 MBPP+ 量級（31.8%），
    lcb2 是 49.2%。把本 run 判成「難題複製」會讓難題那一格從 1 個 run
    看起來變成 2 個。狀態名是最後一道防線：它會被抄進標題。
    """
    for banned in ("REPLICATED_ON_HARD", "NOT_REPLICATED_ON_HARD"):
        for line in dec.splitlines():
            if banned in line:
                # 只准出現在「引用 r449b 那個 run 的既有判決」的脈絡裡。
                assert "r449b" in line or "R449B" in line, \
                    f"DECISION 用了難題狀態名而沒有標明那是 r449b 的：{line.strip()}"


def test_decision_says_explicitly_it_is_not_a_hard_bank_replication(dec: str) -> None:
    assert "27.5%" in dec, "lcb3 的 OFF 失敗率沒寫進來（不是難題的證據）"
    assert "不是難題" in dec or "不是「難題複製」" in dec or "不是難題複製" in dec, \
        "DECISION 沒有明講這不是難題複製"
    assert "第三個題庫" in dec


def test_decision_states_underpowered_before_the_data(dec: str) -> None:
    """n=189 檢定力不足這件事必須寫在資料之前，不是收官時拿來解釋結果。"""
    assert "UNDERPOWERED" in dec
    assert "34.9%" in dec, "事前檢定力（MBPP+ 效果原樣搬過來）沒寫上去"
    assert "MDE" in dec and "N₈₀" in dec
    assert "5.29" in dec and "5.82" in dec, "n=189 的 MDE 沒寫上去"


def test_decision_forbids_editing_the_r446_prereg_constant(dec: str) -> None:
    assert "analyze_eq5.py" in dec
    assert "PREREG" in dec
    # 那支常數是 r446 的事前註冊，改它等於改別人的事前註冊。
    assert any("不准" in line and "PREREG" in line for line in dec.splitlines()), \
        "DECISION 沒有寫死「不准改 analyze_eq5.py 的 PREREG」"


def test_decision_carries_the_lcb3_honesty_boundaries(dec: str) -> None:
    """R461 附錄 A.2／F.3 與 R440Z §五 的誠實邊界不准在換臂的時候掉。"""
    assert "12/189" in dec, "量具只覆蓋 12/189 沒寫"
    assert "lcb_v3_probe_solutions.json" in dec, "手寫參考解的來源檔沒寫"
    assert "verify_lcb_bank" in dec and "0/189" in dec, \
        "verify_lcb_bank 會印 0/189 是工具路徑寫死——這條沒寫"
    assert "2023-05-07" in dec and "2024-08-10" in dec, "v3 的日期視窗沒寫"
    assert "KNOWN_BAD" in dec, "本題庫沒有登記在案的量具問題題——這條沒寫"
    assert "g_r461_lcb3_three_arm" in dec, "與 r461 同題不同設計的關係沒寫"
    assert "不是獨立樣本" in dec


def test_decision_names_the_arbiter_fields_from_the_analyzer(dec: str) -> None:
    """判準要指名它讀 analyze_eq5.py 輸出的哪個 key，不准靠工具印的字串。"""
    for field in ARBITER_FIELDS:
        assert field in dec, f"DECISION 沒指名仲裁欄位 {field}"


# ── 仲裁欄位必須真的存在於 analyze_eq5.py 的輸出裡 ──────────────────────
def test_arbiter_fields_appear_as_json_keys_in_analyzer_source(analyzer_src: str) -> None:
    """(a) grep 原始碼：每個 dotted path 的每一段都要是真的 JSON key 字面值。

    工具把欄位改名（例如 `deliv_pp_denom_measured` → `deliv_pp`）而 DECISION
    沒跟著改，收官時 `.get()` 會安靜地回 None，然後被讀成「量到 0」。
    """
    for field in ARBITER_FIELDS:
        parts = field.split(".")
        if len(parts) == 2:
            parent, leaf = parts
            assert re.search(rf'"{re.escape(parent)}"\s*:\s*\{{', analyzer_src), \
                f"analyze_eq5.py 裡沒有 {parent} 這一層 dict"
        else:
            leaf = parts[0]
        assert re.search(rf'"{re.escape(leaf)}"\s*:', analyzer_src), \
            f"analyze_eq5.py 的輸出裡沒有 key `{leaf}`（DECISION 指名了 {field}）"


def test_arbiter_fields_resolve_on_a_real_analyzer_output() -> None:
    """(b) 真的呼叫 `analyze()` 走一次 dotted path——欄位被搬層時 grep 抓不到。

    用 analyzer 自己的合成夾具 `_fx`（零 I/O、零 API），不碰任何 run。
    """
    from ops.gain.analyze_eq5 import _fx, analyze

    rows, summ = _fx(60, 15, 5, 20)          # 100 題：b=15、c=5，形狀近似 r449b
    out = analyze(rows, summ)
    assert out["broken_reasons"] == [], out["broken_reasons"]
    for field in ARBITER_FIELDS:
        node = out
        for seg in field.split("."):
            assert isinstance(node, dict) and seg in node, \
                f"`{field}` 在 analyze() 的輸出裡走不到（卡在 `{seg}`）"
            node = node[seg]


def test_analyzer_prereg_constant_is_still_r446s_not_this_runs(analyzer_src: str) -> None:
    """§三 末那張「工具會印錯」的表，前提是工具的 PREREG 仍然是 R446 的窗。

    若有人把 `PREREG` 改成本 run 的窗，那張表就變成假的敘述——
    而且那個動作本身被 DECISION 明文禁止（改別人的事前註冊）。
    """
    assert '"P-R446-3": ("閘門 deliv%（分母 measured）", 68.0, 84.0)' in analyzer_src
    assert '"P-R446-4": ("多數決 deliv%（分母 measured）", 64.0, 80.0)' in analyzer_src
    assert '"P-R446-7"' in analyzer_src and "15.0" in analyzer_src
