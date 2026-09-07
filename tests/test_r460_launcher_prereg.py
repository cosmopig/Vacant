"""發射器、預註冊文件、分析尺三邊不准漂開（R460：harness 六臂，LCB v2 120 題）。

這支在架構裡承重什麼：R440G 閘門（`gain_run.py`）只檢查
「DECISION 檔存在，且內文含 `--out` 的目錄名」。它**檢查不到** seed、n、offset、
arms、bank、模型、timeout——那些打錯了，run 會照跑，而且跑出來的東西看起來完全正常：
`runs/g_r460_harness_lcb2_a` 裡會有漂亮的六臂資料，只是它答的不是
`DECISION_20260907_R460_HARNESS_PREREG.md` 註冊的那個問題。

本 run 最貴的五格：
  **`--arms` 的六條**——少一條 OFF5 就等於把 D3 的 (iii) token 門檻抽掉（D2 明文禁止省它）。
  **`--bank lcb2` / 兩塊各 `--n 60`**——掉成 lcb3/189 會安靜跑一個別的實驗。
  **D9 的兩塊與兩個端點**——兩塊同端點、或任何一塊走回 8765 那顆 hub，
    會把「兩顆卡併發」安靜地變回「一顆卡塞兩個 run」，而那看起來只是比較慢。
  **seed `g-r440-lcb2`**——本 run **刻意重用** r447 的 seed（DECISION §二-4）。
    既有發射器的「新鮮度檢查」在這裡會擋下一個我們要的設定，所以換成
    「授權集合相等」檢查。本檔釘住那個替代品**更嚴不是更鬆**：
    它同時擋得住「抄到別的用過的 seed」與「r447 從 runs/ 消失」。
  **併發**——`gain_run.py` 沒有併發旋鈕（round22/23/262 的裁決），
    發射器把「runner 支援的最大值＝1」寫在明處，並在旋鈕出現時中止。

外加本檔比 `tests/test_r449c_launcher_prereg.py` 多的兩組：
  **十條預測指名的仲裁欄位必須真的存在於 `analyze_r460.py` 的輸出裡**
  （既 grep 原始碼，也真的呼叫 `analyze()` 走一次 dotted path）。
  **Fable 的 D3–D7 逐條落在文件裡**（可執行的 CI 定義、complete-case 分母、
  階段二一致性、D6 的引用刪除、D4 的取碼協定、D5 的歸因、D7 的措辭）。

本檔零 API、零 ssh、不寫 `runs/`（只讀 `runs/*/summary.json` 與 r447 的 rows 做證明）。
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

SH = ROOT / "ops" / "gain" / "launch_harness_lcb2.sh"
DEC = ROOT / "DECISION_20260907_R460_HARNESS_PREREG.md"
ANALYZER = ROOT / "ops" / "gain" / "analyze_r460.py"
STUDY = ROOT / "docs" / "HARNESS_STUDY_2026-09-07.md"
VGT = ROOT / "ops" / "gain" / "harness_vgt_audit.py"

RUN_NAME = "g_r460_harness_lcb2"          # 不帶塊名的舊名字：**不在授權內**
RUN_A = "runs/g_r460_harness_lcb2_a"
RUN_B = "runs/g_r460_harness_lcb2_b"
API_A = "http://100.119.113.56:1234/v1/chat/completions"
API_B = "http://100.86.226.21:1234/v1/chat/completions"
HUB_MARK = "8765"
ENDPOINT_ENV = "VACANT_GAIN_API"
SEED = "g-r440-lcb2"
SEED_PRIOR_RUN = "runs/g_r447_conform_lcb2"
MODEL = "gemma-4-12b-it-qat"
PRIOR_DEFAULT = "runs/g_r449c_eq5_lcb3"
BANK_FILE = "ops/gain/data/lcb_bank_v2.jsonl"
ARMS = "OFF,CONFORM,OFF5,HPI,HOC,HMIX"
N_TASKS = 120                              # 合併後；每一塊是 60
N_PER_BLOCK = 60

CI_DISCLAIMER = "區間未做多重比較調整；仲裁以 analyzer 為準"

# §三 的十條預測 ＋ §三-B 的歸因 ＋ §三-C「無條件一併印」的次要量。
ARBITER_FIELDS = (
    # P-H0..P-H8
    "per_arm.OFF.deliv_pp_denom_measured",
    "paired.HPI_vs_OFF.delta_pp",
    "paired.HOC_vs_OFF.delta_pp",
    "paired.HMIX_vs_OFF.delta_pp",
    "paired.HPI_vs_CONFORM.delta_pp",
    "paired.HMIX_vs_CONFORM.delta_pp",
    "per_arm.HPI.calls_per_task",
    "per_arm.HMIX.false_delivery_pp",
    "per_arm.HOC.loader_turn_rate_pp",
    "per_arm.HMIX.loader_turn_rate_pp",
    "tokens.HMIX.tokens_per_task",
    "tokens.HPI.tokens_per_task",
    "per_arm.HMIX.stop_reason_pp",
    "per_arm.HPI.nocode_turn_rate_pp",
    "prereg.P-H9.followup_h4_required",
    # D5 歸因
    "attribution.HMIX.delta_turn1_minus_off_pp",
    "attribution.HMIX.delta_final_minus_turn1_pp",
    "attribution.HMIX.delta_final_minus_turn1_looponly_pp",
    "attribution.HMIX.turn1_visible_pass_pp",
    "attribution.HMIX.loop_gain_n",
    "attribution.HMIX.first_pass_turn_hist",
    # D3 裁決
    "decision.HMIX.delta_o_pp",
    "decision.HMIX.delta_c_pp",
    "decision.HMIX.p_adj_vs_off",
    "decision.HMIX.p_adj_vs_conform",
    "decision.HMIX.tpc_incl_void",
    "decision.HMIX.tpc_off5",
    "decision.HMIX.false_delivery_pp",
    "decision.HMIX.verdict",
    "holm.family_size",
    "holm.HMIX_vs_CONFORM.p_adj",
    "paired.HMIX_vs_CONFORM.ci95_lo_pp",
    "paired.HMIX_vs_CONFORM.ci95_hi_pp",
    "paired.HMIX_vs_CONFORM.n_common",
    "paired.HMIX_vs_CONFORM.p_mcnemar_exact",
    # token 倍數表（D3 要求貼在 (iii) 旁邊）
    "tokens.HMIX.multiple_vs_off",
    "tokens.HMIX.multiple_vs_conform",
    "tokens.HMIX.tpc_excl_void",
    "tokens.HMIX.tpc_ratio_vs_off5",
    # 守門指標與檢定力
    "gates.G1_false_delivery",
    "gates.G2_refusal_losslessness",
    "gates.G3_loader_artifact",
    "gates.G4_difficulty_date",
    "gates.G5_calls_per_task",
    "gates.G6_wire_mode",
    "power.HMIX_vs_CONFORM.mde_at_n_pp",
    "per_arm.HMIX.extractor_divergences",
    "per_arm.HMIX.entry_point_missing",
    "per_arm.HMIX.first_block_non_python",
    "per_arm.HMIX.wire_modes",
    "stage2_triggered",
    "winners_curse_disclaimer",
)


@pytest.fixture(scope="module")
def sh() -> str:
    return SH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dec() -> str:
    return DEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def study() -> str:
    return STUDY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def analyzer_src() -> str:
    return ANALYZER.read_text(encoding="utf-8")


def _var(text: str, name: str) -> str:
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


# ── R440G 閘門 ─────────────────────────────────────────────────────────
def test_decision_authorizes_the_run_name(sh: str, dec: str) -> None:
    """D9：授權的是**兩個**塊名，不帶塊名的舊名字不在授權內。"""
    assert _var(sh, "DEC") == DEC.name
    assert _var(sh, "OUT_A") == RUN_A
    assert _var(sh, "OUT_B") == RUN_B
    assert RUN_A in dec and RUN_B in dec, "DECISION 沒有授權兩個塊名"
    # R440G 是子字串比對 ⇒ 舊名字會照樣通過它；DECISION 與發射器都要自己再擋一次。
    assert "不在授權內" in dec, "DECISION 沒有明說不帶塊名的舊名字不在授權內"
    assert "abort_unsuffixed_run_name" in sh, "發射器沒擋不帶塊名的舊 run 名字"
    assert _var(sh, "UNSUFFIXED") == RUN_NAME


def test_decision_authorizes_the_zero_api_probe_out_name(dec: str) -> None:
    # 量具指令用 `--out /tmp/r460_probe`，R440G 檢查 basename ⇒ 這個字串也要在 DECISION 裡。
    assert "r460_probe" in dec


def test_decision_names_the_seed_and_launcher_greps_for_it(sh: str, dec: str) -> None:
    assert _var(sh, "SEED") == SEED
    assert SEED in dec
    assert 'grep -q -- "$SEED" "$DEC"' in sh
    assert "abort_seed_not_prereg" in sh


# ── seed 重用：本 run 與所有前例最大的程序差異 ──────────────────────────
def test_decision_carries_the_literal_seed_reuse_authorization(dec: str) -> None:
    """授權句必須在**行首**、逐字，發射器才 grep 得到。"""
    m = re.search(rf"^SEED_REUSE_AUTHORIZED: {re.escape(SEED)} <- (.+)$", dec, re.M)
    assert m, "DECISION 沒有行首的 SEED_REUSE_AUTHORIZED 授權句"
    allowed = sorted(x.strip() for x in m.group(1).split(",") if x.strip())
    assert allowed == [SEED_PRIOR_RUN], allowed


def test_decision_explains_why_seed_reuse_costs_nothing(dec: str) -> None:
    """重用 seed 要有理由，而且理由要是可驗的（bank 全取 ⇒ seed 不抽樣）。"""
    assert "只打亂順序" in dec and "不做抽樣" in dec
    assert "逐格對齊" in dec
    assert "P-H0" in dec


def test_launcher_replaced_freshness_with_authorized_set_equality(sh: str) -> None:
    """新鮮度檢查換成「命中集合 == 授權集合」，而且不是換成「不檢查」。"""
    assert "abort_seed_reuse_unauthorized" in sh
    assert "abort_seed_reuse_set_mismatch" in sh
    assert 'glob.glob("runs/*/summary.json")' in sh, "沒有真的掃 runs/*/summary.json"
    assert '.get("seed")' in sh, "掃描沒有讀 summary.json 的 seed 欄位"
    assert "SEED_REUSE_AUTHORIZED" in sh, "發射器沒有 grep 授權句"
    assert 'hits == allowed' in sh, "沒有做集合相等比較"
    # 掃到 0 個檔案要停（「量不到」不是「通過」）。
    assert '[ "$n_files" -gt 0 ]' in sh
    # 舊語意（掃到任何命中就停）不准回來——那會擋掉本 run 刻意要的設定。
    # 註解裡講「我們換掉了 abort_seed_not_fresh」是**該留的歷史敘述**，
    # 所以只看程式碼行：`_code_lines` 把每行 `#` 之後砍掉再比。
    assert "abort_seed_not_fresh" not in "\n".join(_code_lines(sh)), \
        "abort_seed_not_fresh 回到邏輯裡了（註解裡出現沒關係）"
    for line in _code_lines(sh):
        assert '"$n_hits" -eq 0' not in line, f"退回「命中必須為 0」的舊語意: {line!r}"


def test_seed_is_used_by_exactly_the_authorized_run() -> None:
    """事前證明（在測試時重算）：這顆 seed 恰好被授權的那一個 run 用過。"""
    files = sorted(glob.glob(str(ROOT / "runs" / "*" / "summary.json")))
    assert files, "一個 runs/*/summary.json 都沒掃到——量不到不是通過"
    used = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                if json.load(fh).get("seed") == SEED:
                    used.append(pathlib.Path(f).parent.relative_to(ROOT).as_posix())
        except Exception:                                    # noqa: BLE001
            pass
    assert sorted(used) == [SEED_PRIOR_RUN], used


def test_same_seed_selects_the_same_120_tasks_as_r447() -> None:
    """§九-1 的證明：同 seed ＝ 同題、同序（bank 只有 120 題 ⇒ seed 不抽樣）。

    D9 之後多驗三件事：兩塊各 60、塊間**零交集**、`a + b` 逐題逐序等於 r447 的 120。
    塊間零交集是 `CRITERION_20260903_R680_POOL_PRECONDITIONS.md` 的 Q1，
    也是 analyzer 敢按 `task_id` 合併的前提。
    """
    rows_p = ROOT / SEED_PRIOR_RUN / "rows.jsonl"
    if not rows_p.exists():
        pytest.skip(f"{SEED_PRIOR_RUN}/rows.jsonl 不在本 checkout")
    from ops.gain.gain_run import load_tasks
    a = [t["task_id"] for t in load_tasks("lcb2", SEED, N_TASKS, offset=0)]
    rows = [json.loads(l) for l in rows_p.open(encoding="utf-8") if l.strip()]
    off = [r["task_id"] for r in rows if r["arm"] == "OFF"]
    assert len(a) == N_TASKS and len(set(a)) == N_TASKS
    assert set(a) == {r["task_id"] for r in rows}
    assert a == off, "同 seed 沒有給出同一個題序——§二-4 的論證要重寫"
    blk_a = [x["task_id"] for x in load_tasks("lcb2", SEED, N_PER_BLOCK, offset=0)]
    blk_b = [x["task_id"] for x in load_tasks("lcb2", SEED, N_PER_BLOCK, offset=N_PER_BLOCK)]
    assert len(blk_a) == len(blk_b) == N_PER_BLOCK
    assert set(blk_a) & set(blk_b) == set(), "兩塊有交集——不准合併（Q1 MISS）"
    assert blk_a + blk_b == a, "兩塊接起來不等於原本那 120 題、那個順序"
    assert blk_a == off[:N_PER_BLOCK], "block a 不是 r447 的前 60 題 ⇒ P-H0 的錨要重算"


# ── 題庫、題數、臂 ─────────────────────────────────────────────────────
def test_bank_is_lcb2_everywhere(sh: str, dec: str) -> None:
    assert "--bank lcb2" in sh
    assert "--bank lcb2" in dec
    for line in _code_lines(sh):
        for stale in ("--bank evalplus", "--bank lcb3", "--bank lcb "):
            assert stale not in line, f"題庫掉回別的: {line!r}"


def test_bank_file_presence_is_checked(sh: str) -> None:
    assert _var(sh, "BANK_FILE") == BANK_FILE
    assert (ROOT / BANK_FILE).exists()
    assert "abort_no_bank" in sh


def test_bank_file_really_has_120_tasks() -> None:
    with (ROOT / BANK_FILE).open(encoding="utf-8") as fh:
        n = sum(1 for line in fh if line.strip())
    assert n == N_TASKS, f"lcb2 題庫是 {n} 題，但預註冊寫 {N_TASKS}"


def test_all_six_arms_are_registered_everywhere(sh: str, dec: str) -> None:
    assert _var(sh, "ARMS") == ARMS
    assert ARMS in dec
    for arm in ARMS.split(","):
        assert arm in dec


def test_off5_is_not_dropped(dec: str) -> None:
    """D2：OFF5 不准省。省了就等於把 (iii) 的 token 門檻抽掉。"""
    assert "OFF5" in _var(sh_text := SH.read_text(encoding="utf-8"), "ARMS")
    assert "OFF5 不准省" in dec
    assert "22,266" in dec or "tpc_off5" in dec
    del sh_text


@pytest.mark.parametrize("flag", [
    '--n "$nn"', '--offset "$off"', "--bank lcb2", "--probe-sample 0",
    "--request-timeout-s 600", "--review-timeout-s 380", "--retries 4",
    '--models "$MODEL"', '--seed "$SEED"', '--decision "$DEC"', '--out "$OUT"',
    '--arms "$ARMS"',
])
def test_launch_command_carries_the_registered_flag(sh: str, flag: str) -> None:
    assert flag in sh, f"發射指令少了 {flag}"


def test_decision_registers_the_same_flags(dec: str) -> None:
    for flag in ("--n 120", "--offset 0", "--bank lcb2", "--probe-sample 0",
                 "--request-timeout-s 600", "--review-timeout-s 380", "--retries 4"):
        assert flag in dec, f"DECISION 沒寫到 {flag}"


def test_launcher_never_carries_another_runs_task_count(sh: str) -> None:
    for line in _code_lines(sh):
        for stale in ("--n 189", "--n 371", "--n 60", "--n 40"):
            assert stale not in line, f"題數抄成別的 run: {line!r}"


def test_model_is_the_registered_one(sh: str, dec: str) -> None:
    assert _var(sh, "MODEL") == MODEL
    assert MODEL in dec


# ── 併發：runner 沒有旋鈕，最大值就是 1 ────────────────────────────────
def test_worker_concurrency_is_documented_as_one(sh: str) -> None:
    m = re.search(r"^WORKER_CONCURRENCY=(\d+)", sh, re.M)
    assert m, "發射器沒有寫出 worker 併發度"
    assert m.group(1) == "1", "runner 是依序送出，最大支援值就是 1"
    assert "SERIALIZE_CONCURRENT_CALLS" in sh, "沒有指到那份裁決"


def test_runner_really_has_no_concurrency_knob() -> None:
    """「最大值＝1」不是猜的：runner 裡沒有任何 ThreadPoolExecutor 實例化。"""
    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    assert "ThreadPoolExecutor(" not in src, \
        "gain_run.py 出現併發旋鈕了——WORKER_CONCURRENCY 這一格要重新裁決"
    # 而且沒有任何 CLI 旗標在調它。
    assert "--jobs" not in src and "--workers" not in src


def test_launcher_aborts_if_a_concurrency_knob_appears(sh: str) -> None:
    assert 'grep -q "ThreadPoolExecutor(" ops/gain/gain_run.py' in sh
    assert "abort_concurrency_knob_appeared" in sh


# ── 從既有發射器繼承的守則，一條都不准掉 ────────────────────────────────
def test_wait_pattern_is_anchored_and_uses_prior_run(sh: str) -> None:
    pat = _var(sh, "WAIT_PAT")
    assert pat.startswith("^python3 ops/gain/gain_run"), pat
    assert "$PRIOR_RUN" in pat


def test_prior_run_is_configurable_env_var(sh: str) -> None:
    assert f'PRIOR_RUN="${{PRIOR_RUN:-{PRIOR_DEFAULT}}}"' in sh


def test_prior_run_default_is_already_terminal() -> None:
    p = ROOT / PRIOR_DEFAULT / "summary.json"
    if not p.exists():
        pytest.skip(f"{PRIOR_DEFAULT}/summary.json 不在本 checkout")
    with p.open(encoding="utf-8") as fh:
        assert json.load(fh).get("run_terminal") is True


def test_terminal_check_reads_prior_run_summary(sh: str) -> None:
    assert '"$PRIOR_RUN/summary.json"' in sh
    assert "abort_prior_not_terminal" in sh
    assert "run_terminal" in sh


def test_no_hardcoded_prior_run_literal_outside_comments_and_default(sh: str) -> None:
    for line in _code_lines(sh):
        if "PRIOR_RUN:-" in line:
            continue
        for stale in ("g_r461_lcb3_three_arm", "g_r448", "g_r446", "g_r449_eq5"):
            assert stale not in line, f"{stale} 字面值漏在可執行碼: {line!r}"


def test_single_run_recheck_before_launch_is_anchored(sh: str) -> None:
    """發射前重做「沒有別人在跑」檢查，pattern 錨在行首。

    D9 之後「別人」的定義變了：本支自己的兩塊**不算**別人（它們是設計要的併發），
    其餘任何 gain_run 都算。所以判準是 (a) 錨行首的 grep 還在、
    (b) 過濾掉的**只有** OUT_A／OUT_B 這兩個、(c) 兩塊之間再查一次。
    """
    assert 'grep "^python3 ops/gain/gain_run\\.py"' in sh, "pattern 沒有錨在行首"
    assert 'grep -v -- "--out $OUT_A "' in sh and 'grep -v -- "--out $OUT_B "' in sh, \
        "過濾自己人的規則不見了（或過濾了不該過濾的東西）"
    assert "abort_other_run" in sh
    # 兩塊之間要再查一次：block a 起來之後才冒出來的第三個 run 也要擋。
    assert sh.count("count_other_runs") >= 3, "只在發射前查一次；兩塊之間沒有再查"


def test_probe_checks_body_not_only_http_200(sh: str) -> None:
    assert "body_ok=" in sh
    assert '[ "$code" = "200" ] && [ "$body" = "yes" ]' in sh
    assert '[ "$ok" -eq 3 ]' in sh, "探針要 3/3 才准發射"
    assert "for i in 1 2 3; do" in sh, "探針次數不是 3"


def test_wire_mode_is_decided_by_the_runner_not_the_launcher(sh: str) -> None:
    """發射器可以記錄多輪探針，但**不准**自己決定 wire mode。

    兩個地方各自判，會出現「發射器說 multiturn、rows 說 flattened」這種對不上的狀態，
    而 G6 的「兩種模式不得混算」就靠 rows 裡那個欄位。
    """
    assert "harness_wire_mode" in sh, "發射器沒有指出模式由 runner 落盤"
    for line in _code_lines(sh):
        assert "HARNESS_WIRE_MODE=" not in line, f"發射器自己決定了 wire mode: {line!r}"


def test_existing_evidence_is_never_overwritten(sh: str) -> None:
    assert "abort_dir_exists" in sh and "abort_launchlog_exists" in sh
    assert '>>"$OUT.launch.log"' in sh
    assert '>"$OUT.launch.log"' not in sh.replace('>>"$OUT.launch.log"', "")


def test_flock_guards_against_duplicate_launchers(sh: str) -> None:
    assert "flock -n 9" in sh
    assert "9>&-" in sh, "發射的子行程要關掉鎖的 fd，否則鎖跟著 run 活著"


def test_machine_readable_result_line(sh: str) -> None:
    assert "HARNESS_LCB2_LAUNCH_RESULT=" in sh
    assert sh.strip().splitlines()[-1].startswith("finish ")


# ── 突變檢查：把守則拿掉，指名的測試必須變紅 ────────────────────────────
def _expect_fail(fn, text: str, why: str) -> None:
    try:
        fn(text)
    except AssertionError:
        return
    raise AssertionError(f"突變體沒有被抓到：{why}")


def test_mutation_freshness_semantics_restored_is_caught(sh: str) -> None:
    """M1：把授權集合檢查換回「命中必須為 0」⇒ 本 run 永遠發射不出去。"""
    mutant = sh.replace('[ "$verdict" = "OK" ]', '[ "$n_hits" -eq 0 ]')
    assert mutant != sh
    _expect_fail(test_launcher_replaced_freshness_with_authorized_set_equality,
                 mutant, "退回新鮮度語意")


def test_mutation_authorization_grep_removed_is_caught(sh: str) -> None:
    """M2：拿掉授權句 grep ⇒ 任何用過的 seed 都能通過。"""
    mutant = sh.replace("SEED_REUSE_AUTHORIZED", "SEED_ANYTHING_GOES")
    assert mutant != sh
    _expect_fail(test_launcher_replaced_freshness_with_authorized_set_equality,
                 mutant, "授權句 grep 被拿掉")


def test_mutation_unanchored_wait_pattern_is_caught(sh: str) -> None:
    mutant = sh.replace('WAIT_PAT="^python3', 'WAIT_PAT="python3')
    assert mutant != sh
    _expect_fail(test_wait_pattern_is_anchored_and_uses_prior_run, mutant, "錨消失了")


def test_mutation_probe_count_reduced_is_caught(sh: str) -> None:
    mutant = sh.replace("for i in 1 2 3; do", "for i in 1; do").replace(
        '[ "$ok" -eq 3 ]', '[ "$ok" -eq 1 ]')
    assert mutant != sh
    _expect_fail(test_probe_checks_body_not_only_http_200, mutant, "探針只剩 1 次")


def test_mutation_off5_dropped_from_arms_is_caught(sh: str) -> None:
    """M5：`--arms` 少了 OFF5 ⇒ D3 的 (iii) 沒有同 run 的對照。"""
    mutant = sh.replace(f'ARMS="{ARMS}"', 'ARMS="OFF,CONFORM,HPI,HOC,HMIX"')
    assert mutant != sh
    _expect_fail(lambda t: test_all_six_arms_are_registered_everywhere(
        t, DEC.read_text(encoding="utf-8")), mutant, "OFF5 被拿掉")


def test_mutation_bank_flipped_to_lcb3_is_caught(sh: str) -> None:
    mutant = sh.replace("--bank lcb2", "--bank lcb3")
    assert mutant != sh
    _expect_fail(lambda t: test_bank_is_lcb2_everywhere(
        t, DEC.read_text(encoding="utf-8")), mutant, "bank 被換成 lcb3")


def test_mutation_concurrency_bumped_is_caught(sh: str) -> None:
    mutant = sh.replace("WORKER_CONCURRENCY=1", "WORKER_CONCURRENCY=3")
    assert mutant != sh
    _expect_fail(test_worker_concurrency_is_documented_as_one, mutant, "併發度被調高")


# ── 展場口徑紅線（CLAUDE.md）─────────────────────────────────────────
@pytest.mark.parametrize("word", ["信任", "防止", "保證"])
def test_forbidden_exhibition_words_appear_only_as_prohibitions(
        word: str, sh: str, dec: str) -> None:
    assert word not in sh
    for line in dec.splitlines():
        if word in line:
            assert "不准" in line or "不得" in line, \
                f"DECISION 用了「{word}」：{line.strip()}"


# ── 決策規則必須在資料之前寫死（本檔存在的理由）──────────────────────
def test_decision_rule_is_written_before_any_data(dec: str) -> None:
    for state in ("EFFECTIVE", "COSTLY_BUT_REAL", "RULED_OUT", "INCONCLUSIVE", "INVALID"):
        assert state in dec, f"決策規則缺 {state}"
    for pred in [f"P-H{i}" for i in range(10)]:
        assert pred in dec, f"預測缺 {pred}"


def test_decision_thresholds_are_the_frozen_d3_numbers(dec: str) -> None:
    assert "+25.0pp" in dec, "Δ_O 門檻沒寫死"
    assert "+10.0pp" in dec, "Δ_C 門檻沒寫死"
    assert "α=0.05" in dec
    assert "6 個檢定" in dec, "Holm 家族大小沒寫死"
    assert "holm.family_size" in dec


def test_decision_ci_is_unadjusted_with_the_verbatim_disclaimer(dec: str) -> None:
    """D3：區間是**未調整**的 Clopper–Pearson 條件區間，而且免責句要逐字。"""
    assert CI_DISCLAIMER in dec
    assert "Clopper" in dec and "未調整" in dec
    assert "Holm 後的 CI" in dec and "不存在" in dec, \
        "沒有明文把「Holm 後的 CI」這個錯詞釘死"


def test_decision_uses_complete_case_denominator(dec: str) -> None:
    assert "complete case" in dec or "complete-case" in dec
    assert "n_common" in dec
    assert "不准" in dec and "聯集" in dec, "沒有禁止用聯集當分母"


def test_decision_has_mandatory_winners_curse_disclaimer(dec: str) -> None:
    assert "winner's curse" in dec
    assert "上偏" in dec, "沒講清楚點估計偏在哪一邊"
    assert "不寫＝裁決不得結算" in dec


def test_decision_token_multiple_table_is_required(dec: str) -> None:
    """D3：token 倍數（對 OFF 與 CONFORM）要印在 (iii) 旁邊。"""
    assert "multiple_vs_off" in dec and "multiple_vs_conform" in dec
    assert "tpc_incl_void" in dec and "tpc_excl_void" in dec


def test_decision_records_the_underpowered_fact_before_the_data(dec: str) -> None:
    assert "MDE" in dec
    assert "11.67" in dec and "15.83" in dec, "Holm 下的 MDE 沒寫進來"
    assert "0.428" in dec or "0.43" in dec, "n=120 的檢定力沒寫進來"
    assert "INCONCLUSIVE" in dec and "最可能" in dec, \
        "沒有事前寫下「最可能的落點是 INCONCLUSIVE」"


def test_decision_freezes_stage_two_now(dec: str) -> None:
    assert "g_r461h_harness_lcb3" in dec
    assert "lcb3" in dec and "189" in dec
    assert "g-r461-lcb3" in dec
    assert "不得修改" in dec or "不准修改" in dec
    # 階段二的 seed 也要有行首授權句（它同樣是重用的）。
    assert re.search(r"^SEED_REUSE_AUTHORIZED: g-r461-lcb3 <- ", dec, re.M), \
        "階段二的 seed 授權句不在行首"
    # lcb3 不是難題題庫——狀態名不准帶 HARD。
    assert "不是難題" in dec or "不是**難題" in dec


def test_decision_carries_the_honest_boundaries(dec: str) -> None:
    for probe, why in [
        ("可見測資", "D7：可見測資內容進 prompt"),
        ("19.4%", "12B 的多圍欄協定風險"),
        ("2–4 條", "只有 2–4 條可見測資 ⇒ 過擬合"),
        ("budget_wall", "牆鐘不對稱"),
        ("void", "void 不對稱"),
        ("2023-08-26", "汙染定界"),
        ("_FORBIDDEN_ATTRS", "載入器拒收的量具偏誤"),
    ]:
        assert probe in dec, f"誠實邊界缺：{why}"


def test_decision_states_max_wall_is_not_a_hard_bound(dec: str) -> None:
    """`max_wall_s` 在呼叫之間檢查 ⇒ 它不是每題牆鐘的上界。"""
    assert "不是每題牆鐘的上界" in dec
    assert "600" in dec and "呼叫之間" in dec


# ── D6：外部引用刪掉了沒有 ─────────────────────────────────────────────
def test_uncited_pi_numbers_are_gone_everywhere(study: str, dec: str) -> None:
    """D6：沒有合規引用的那組 pi 逾時數字要**整條消失**，連刪除紀錄都不准複述。

    複述「原本寫的是 N 次裡 M 次逾時」＝用一份沒落盤的來源當事實，
    只是換了個位置；所以判準是那幾個字面數字在兩份文件裡都不出現。
    """
    for text, name in ((study, "HARNESS_STUDY"), (dec, "DECISION")):
        for needle in ("428 trials", "AgentTimeoutError", "13.3%"):
            assert needle not in text, f"{name} 還留著沒有合規引用的數字：{needle}"
    # 刪除本身要留下紀錄（含唯一合規復活路徑：那篇文章的 URL ＋三級規則）。
    assert "已整條刪除" in study and "archive_citations.py" in study
    assert "mariozechner.at/posts/2025-11-30-pi-coding-agent" in study, \
        "刪除紀錄沒有留下來源 URL——復活它的唯一一條路要寫在明處"
    # 牆鐘改綁自己的實測。
    assert "504.9" in study and "1.78" in study
    assert "504.9" in dec and "1.783" in dec


def _wrong_value_only_in_correction_rows(text: str, wrong: str, right: str) -> None:
    """舊值只准出現在**同時寫著新值**的那一行（＝更正表那一列）。

    更正表必須說出原本錯在哪，否則讀者無從判斷更正了什麼；
    但除了那一列以外，舊值一次都不准再出現。
    """
    stray = [ln for ln in text.splitlines() if wrong in ln and right not in ln]
    assert not stray, f"舊值 {wrong} 出現在更正表以外的行：{stray[:3]}"


def test_study_citation_corrections_are_applied(study: str) -> None:
    assert "60 個 entry" in study
    _wrong_value_only_in_correction_rows(study, "61 個 entry", "60 個 entry")
    assert "as of Dec 1, 2025" in study
    assert "show-results.js:20-24" in study
    assert "agent/agent.ts:121" in study
    _wrong_value_only_in_correction_rows(study, "agent/agent.ts:120", "agent/agent.ts:121")
    assert "無法一手重驗" in study, "外部更正沒有標明本輪沒有一手驗證"


# ── D4／D5／D7 的措辭落在文件裡 ────────────────────────────────────────
def test_study_records_the_d4_extractor_protocol(study: str) -> None:
    assert "初稿輪" in study and "gain_run.extract_code" in study
    assert "extractor_divergences" in study, "分歧計數沒寫進規格"
    assert "first_block_non_python" in study, "第一塊非 Python 沒有單獨計數"
    assert "_fenced_blocks" in study, "nocode 的偵測器沒有指名"


def test_precheck_reason_vocabulary_is_closed_and_matches_the_code(study: str) -> None:
    from ops.gain.harness_arms import PRECHECK_REASONS
    want = {"syntax_error", "forbidden_import", "forbidden_attr",
            "entry_point_missing", "empty"}
    assert set(PRECHECK_REASONS) == want, PRECHECK_REASONS
    for r in sorted(want):
        assert r in study, f"reason 封閉集少了 {r}"
    assert "entry_point_missing` 必須與其餘四個分開計數" in study \
        or "entry_point_missing" in study and "單獨計數" in study


def test_study_and_decision_carry_the_d5_attribution(study: str, dec: str) -> None:
    for text, name in ((study, "HARNESS_STUDY"), (dec, "DECISION")):
        assert "first_pass_turn" in text, name
        assert "prompt 效果" in text and "迴圈效果" in text, name
        assert "不准寫成恆等式" in text, f"{name} 沒寫「相加不等於 Δ_O」"


def test_d7_wording_is_in_all_three_places(study: str, dec: str) -> None:
    """D7：預註冊、展場文案、稽核腳本 docstring 三處都要寫明。"""
    assert "第一次" in study and "可見測資" in study
    assert "hidden" in study and "visible" in study
    assert "D7" in dec and "第一次" in dec
    vgt = VGT.read_text(encoding="utf-8")
    head = vgt.split('"""')[1] if '"""' in vgt else vgt[:4000]
    assert "visible" in head and "hidden" in head, "稽核腳本 docstring 沒寫 D7"


# ── 仲裁欄位必須真的存在於 analyze_r460.py 的輸出裡 ────────────────────
def test_decision_names_the_arbiter_fields_from_the_analyzer(dec: str) -> None:
    for field in ARBITER_FIELDS:
        leaf = field.split(".")[-1]
        assert leaf in dec or field in dec, f"DECISION 沒指名仲裁欄位 {field}"


def test_arbiter_fields_appear_as_json_keys_in_analyzer_source(analyzer_src: str) -> None:
    """(a) grep 原始碼：每個 dotted path 的葉子都要是真的 key 字面值。"""
    for field in ARBITER_FIELDS:
        leaf = field.split(".")[-1]
        if leaf.startswith("P-H"):
            leaf = "P-H9"
        assert re.search(rf'"{re.escape(leaf)}"', analyzer_src), \
            f"analyze_r460.py 的輸出裡沒有 key `{leaf}`（DECISION 指名了 {field}）"


def test_arbiter_fields_resolve_on_a_real_analyzer_output() -> None:
    """(b) 真的呼叫 `analyze()` 走一次 dotted path——欄位被搬層時 grep 抓不到。

    用 analyzer 自己的合成夾具（零 I/O、零 API），不碰任何 run。
    """
    from ops.gain.analyze_r460 import _fixture, analyze
    rows, summ, calls = _fixture()
    out = analyze(rows, summ, calls)
    assert out["broken_reasons"] == [], out["broken_reasons"]
    for field in ARBITER_FIELDS:
        node = out
        for seg in field.split("."):
            assert isinstance(node, dict) and seg in node, \
                f"`{field}` 在 analyze() 的輸出裡走不到（卡在 `{seg}`）"
            node = node[seg]
    assert out["holm"]["family_size"] == 6


def test_analyzer_reproduces_the_r447_known_answers() -> None:
    """量具要先答已知答案：r447 三條既有臂的交付數是 61／84／76。"""
    run = ROOT / SEED_PRIOR_RUN
    if not (run / "rows.jsonl").exists():
        pytest.skip(f"{SEED_PRIOR_RUN} 不在本 checkout")
    from ops.gain.analyze_r460 import analyze, load_run
    rows, summ, calls = load_run(run)
    out = analyze(rows, summ, calls)
    assert out["broken_reasons"] == [], out["broken_reasons"]
    assert {a: out["per_arm"][a]["deliv_n"] for a in ("OFF", "CONFORM", "OFF5")} == \
        {"OFF": 61, "CONFORM": 84, "OFF5": 76}
    # N4 的 token 總量與 N3 的載入器拒收也一併釘（歸戶沒漂）。
    assert out["tokens"]["OFF5"]["tokens_total_incl_void"] == 1692219
    assert out["gates"]["G3_loader_artifact"]["off_loader_refused_n"] == 7


def test_analyzer_detection_strip_has_teeth() -> None:
    """突變檢查：每一個突變體各自要讓**指名的那一條** selftest 變紅。

    D9 加了三個（M8 拓撲不判、M9 階段二觸發鍵放鬆、M10 逐塊 BROKEN 不往上帶），
    所以這裡也釘住數量——少一個突變體＝少一道牙齒，而那不會讓任何測試變紅。
    """
    from ops.gain import analyze_r460 as A
    assert len(A.MUTANTS) == 10, sorted(A.MUTANTS)
    for m in ("M8_topology_not_enforced", "M9_stage2_any_arm",
              "M10_block_broken_not_propagated"):
        assert m in A.MUTANTS, f"D9 的突變體 {m} 不見了"
    assert A.mutation_check() == 0


# ══════════════════════════════════════════════════════════════════════
# D9：兩個後端、兩塊、併發
# ──────────────────────────────────────────────────────────────────────
# 這一組守的是一個**看不出來**的失敗：兩塊都跑完、六臂資料漂亮、
# 但其實兩塊打的是同一顆 GPU（或都被 hub 路由回同一顆）。那個世界裡
# 「併發」只買到排隊，牆鐘不會減半，而且沒有任何一個既有欄位會變紅。
# 所以判準必須落在**端點身分**上，而端點身分唯一的落盤處是 calls.jsonl 的 `api`。
# ══════════════════════════════════════════════════════════════════════
def test_launcher_launches_both_blocks(sh: str) -> None:
    """一支發射器發兩塊，各自 offset／n／端點；不是發一塊。"""
    assert "OFFSET_A=0" in sh and "OFFSET_B=60" in sh, "兩塊的 offset 不對"
    assert f"N_A={N_PER_BLOCK}" in sh and f"N_B={N_PER_BLOCK}" in sh
    assert 'launch_block a "$OUT_A" "$OFFSET_A" "$N_A" "$API_A"' in sh
    assert 'launch_block b "$OUT_B" "$OFFSET_B" "$N_B" "$API_B"' in sh
    # 兩塊加起來要等於註冊的題數；少一塊就是另一個實驗。
    assert 2 * N_PER_BLOCK == N_TASKS


def test_launcher_exports_the_endpoint_env_var_per_block(sh: str) -> None:
    """端點靠環境變數傳給 runner；漏 export 會安靜地退回模組預設（＝hub）。"""
    assert _var(sh, "API_A") == API_A
    assert _var(sh, "API_B") == API_B
    assert f'{ENDPOINT_ENV}="$api"' in sh, f"發射時沒有逐塊 export {ENDPOINT_ENV}"
    # 名字必須真的是 brain_cline.endpoint() 讀的那一個，不是長得像的。
    import inspect

    from ops.gain import brain_cline
    assert ENDPOINT_ENV in inspect.getsource(brain_cline.endpoint), \
        f"{ENDPOINT_ENV} 不是 brain_cline.endpoint() 讀的環境變數名"


def test_launcher_refuses_the_hub_and_duplicate_endpoints(sh: str) -> None:
    """D9 的兩條硬禁令：不准走 hub、兩塊不准同端點。"""
    assert _var(sh, "HUB_MARK") == HUB_MARK
    assert "abort_hub_endpoint" in sh
    assert "abort_same_endpoint" in sh
    assert '[ "$API_A" != "$API_B" ]' in sh, "沒有比較兩塊的端點"
    for api in (API_A, API_B):
        assert HUB_MARK not in api, f"註冊的端點 {api} 指向 hub"


def test_launcher_probes_each_backend_not_the_hub(sh: str) -> None:
    """每一塊探**自己的**後端 /v1/models 與 /v1/chat/completions。"""
    assert 'probe_backend a "$API_A"' in sh and 'probe_backend b "$API_B"' in sh
    assert 'base="${api%/chat/completions}"' in sh, "探針沒有從該塊的端點推導 /v1/models"
    assert '"$base/models"' in sh
    # hub 的位址不准出現在任何一行程式碼裡（註解裡講歷史沒關係）。
    # 唯一的例外是 `HUB_MARK=` 那一行——它是**用來擋 hub 的**那個字面值。
    for line in _code_lines(sh):
        if line.strip().startswith("HUB_MARK="):
            continue
        assert HUB_MARK not in line, f"發射器的程式碼裡還有 hub 位址：{line.strip()!r}"


def test_each_block_has_its_own_flock_and_log(sh: str) -> None:
    """兩塊各自 flock、各自 launch.log——共用會讓第二塊安靜地不跑。"""
    assert 'lock="$ROOT/.launch_harness_lcb2_${tag}.lock"' in sh
    assert 'flock -n "$lock" python3 ops/gain/gain_run.py' in sh
    assert '>>"$OUT.launch.log"' in sh
    # 發射器自己那把鎖仍在（防重複發射整支）。
    assert "flock -n 9" in sh


def test_worker_concurrency_and_block_parallelism_are_distinct(sh: str) -> None:
    """平行度來自兩個行程，不是來自 runner 的旋鈕——兩個數字要分開寫。"""
    assert "WORKER_CONCURRENCY=1" in sh
    assert "BLOCK_PARALLELISM=2" in sh
    assert "abort_concurrency_knob_appeared" in sh
    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    assert "ThreadPoolExecutor(" not in src, \
        "runner 長出併發旋鈕了 ⇒ WORKER_CONCURRENCY=1 這格要重新裁決"


def test_decision_registers_the_two_block_topology(dec: str) -> None:
    """預註冊要寫死：兩個名字、兩個端點、合併分析、不准走 hub。"""
    assert "D9" in dec
    assert RUN_A in dec and RUN_B in dec
    assert API_A in dec and API_B in dec
    assert "--offset 0" in dec and "--offset 60" in dec
    assert ENDPOINT_ENV in dec, "DECISION 沒寫端點是靠哪個環境變數傳的"
    assert "hub" in dec and "禁止" in dec
    # 後端是 task 層級干擾項、不是 arm 層級混淆——D9 成立的全部理由。
    assert "task 層級" in dec and "arm 層級" in dec


def test_decision_records_block_b_is_not_aligned_with_r447(dec: str) -> None:
    """D9 要求寫明：block b 的 persona 指派與 r447 不對齊 ⇒ P-H0 只在 block a。"""
    assert "只在 block a" in dec
    assert "不對齊" in dec
    assert "38.3" in dec and "68.3" in dec, "P-H0 放寬後的窗沒寫進 DECISION"
    assert "53.33" in dec, "P-H0 的新錨（r447 前 60 題）沒寫進 DECISION"
    assert "±15pp" in dec
    # 放寬要說理由，而且理由不准是「比較容易 HIT」。
    assert "n 減半" in dec


def test_prereg_and_analyzer_agree_on_the_ph0_window() -> None:
    """窗只准有一份真相：DECISION 寫的與 analyzer 編碼的必須逐位相同。"""
    from ops.gain.analyze_r460 import PREREG
    _, lo, hi = PREREG["P-H0"]
    assert (lo, hi) == (38.3, 68.3), (lo, hi)
    dec = DEC.read_text(encoding="utf-8")
    assert f"[{lo}, {hi}]" in dec, "DECISION 的窗與 analyzer 的常數對不上"


def test_analyzer_pools_several_run_dirs() -> None:
    """`--run` 收多個目錄，依 task_id 合併；合併必須是**無損的**。

    用 r447 的真 rows 切成兩塊再合併：交付數與 token 總量都必須逐字重現，
    否則「合併」就是一條會安靜改數字的路徑。
    """
    run = ROOT / SEED_PRIOR_RUN
    if not (run / "rows.jsonl").exists():
        pytest.skip(f"{SEED_PRIOR_RUN} 不在本 checkout")
    from ops.gain import analyze_r460 as A
    from ops.gain.gain_run import load_tasks
    rows, _, calls = A.load_run(run)
    a_ids = {t["task_id"] for t in load_tasks("lcb2", SEED, N_PER_BLOCK, offset=0)}
    blocks = []
    for name, off, api, in_a in ((A.AUTHORIZED_BLOCKS[0], 0, API_A, True),
                                 (A.AUTHORIZED_BLOCKS[1], N_PER_BLOCK, API_B, False)):
        rs = [r for r in rows if (r["task_id"] in a_ids) == in_a]
        cs = [dict(c, api=api) for c in calls
              if ((c.get("meta") or {}).get("task_id", "") in a_ids) == in_a]
        n = len({r["task_id"] for r in rs})
        summ = {"run_terminal": True, "seed": SEED, "n": n, "offset": off,
                "arms": {x: {"processed": n, "infra_void": 0, "wall_s": 1.0,
                             "complete": True, "terminal": True}
                         for x in ("OFF", "CONFORM", "OFF5")}}
        blocks.append({"name": name, "path": f"runs/{name}", "rows": rs,
                       "summary": summ, "calls": cs, "endpoints": A.endpoints_of(cs),
                       "offset": off, "n": n, "seed": SEED,
                       "arms": sorted(("OFF", "CONFORM", "OFF5")),
                       "task_ids": {r["task_id"] for r in rs}})
    out = A.analyze([r for b in blocks for r in b["rows"]],
                    A.merge_summaries([b["summary"] for b in blocks]),
                    [c for b in blocks for c in b["calls"]], blocks=blocks)
    assert out["broken_reasons"] == [], out["broken_reasons"]
    assert {a: out["per_arm"][a]["deliv_n"] for a in ("OFF", "CONFORM", "OFF5")} == \
        {"OFF": 61, "CONFORM": 84, "OFF5": 76}, "合併改了交付數"
    assert out["tokens"]["OFF5"]["tokens_total_incl_void"] == 1692219, "合併改了 token 總量"
    # 逐塊報表在，而且結構與合併版相同（收官要能一眼看出哪一塊壞了）。
    assert sorted(out["blocks"]) == sorted(A.AUTHORIZED_BLOCKS)
    assert out["block_order"][0] == A.AUTHORIZED_BLOCKS[0], "block a 不是排在前面"
    for sub in out["blocks"].values():
        assert sub["per_arm"]["OFF"]["measured"] == N_PER_BLOCK
    # P-H0 讀的是 block a 那一格，不是合併值。
    assert out["prereg"]["P-H0"]["source_field"] == \
        f"blocks.{A.AUTHORIZED_BLOCKS[0]}.per_arm.OFF.deliv_pp_denom_measured"
    assert round(out["prereg"]["P-H0"]["value"], 2) == 53.33
    assert out["prereg"]["P-H0"]["value"] != \
        out["prereg"]["P-H0"]["pooled_off_deliv_pp_NOT_ARBITER"]
    # 兩塊的端點都記下來了，而且是兩個不同的直連端點。
    assert out["topology"]["endpoints_all"] == sorted([API_A, API_B])
    assert out["topology"]["blocks_n"] == 2


@pytest.mark.parametrize("kw,marker", [
    ({"hub": True}, "block_used_hub"),
    ({"overlap": True}, "block_task_overlap"),
    ({"same_endpoint": True}, "blocks_share_endpoint"),
])
def test_analyzer_topology_violations_are_broken_reasons(kw, marker) -> None:
    """三種拓撲違規各自要進 `broken_reasons`（E-7）。"""
    from ops.gain import analyze_r460 as A
    out = A._pooled(A._fixture_blocks(**kw))
    assert any(s.startswith(marker) for s in out["broken_reasons"]), \
        f"{marker} 沒有被算成 BROKEN：{out['broken_reasons']}"


def test_analyzer_refuses_to_score_a_single_block() -> None:
    """只給一塊就結算＝安靜地把 n 砍半換一個實驗；必須紅。"""
    from ops.gain import analyze_r460 as A
    out = A._pooled(A._fixture_blocks()[:1])
    assert any(s.startswith("block_count_not_2") for s in out["broken_reasons"]), \
        out["broken_reasons"]


def test_calls_log_really_carries_the_endpoint() -> None:
    """端點身分的落盤處是 calls.jsonl 的 `api`——D8 不准為它改 runner。"""
    import inspect

    from ops.gain import brain_cline
    src = inspect.getsource(brain_cline.ClineBrain)
    assert src.count('"api": self.api') >= 2, \
        "generate()/chat() 沒有逐次落盤端點身分"
    run = ROOT / SEED_PRIOR_RUN / "calls.jsonl"
    if not run.exists():
        pytest.skip("r447 calls.jsonl 不在本 checkout")
    with run.open(encoding="utf-8") as fh:
        first = json.loads(fh.readline())
    assert "api" in first, "既有 run 的 calls.jsonl 沒有 api 欄位 ⇒ D9 的判準沒有來源"


def test_decision_pre_registers_the_pooled_analysis(dec: str) -> None:
    """合併分析要在資料之前註冊：指令、仲裁層級、塊間不可比都要寫。"""
    assert f"--run {RUN_A} {RUN_B}" in dec, "收官指令沒有寫成兩塊一起餵"
    assert "合併後的量" in dec
    assert "塊間點估計不得互相比較" in dec or "點估計不得互相比較" in dec
    assert "topology.violations" in dec


def test_decision_freezes_stage_two_as_two_blocks(dec: str) -> None:
    """階段二也凍結成兩塊，而且不准沿用階段一的 P-H0 窗。"""
    assert "runs/g_r461h_harness_lcb3_a" in dec and "runs/g_r461h_harness_lcb3_b" in dec
    assert "--offset 0 --n 95" in dec and "--offset 95 --n 94" in dec
    assert "不准沿用本檔的 [38.3, 68.3]" in dec


def test_study_and_decision_agree_on_d9(study: str, dec: str) -> None:
    """研究文件與預註冊不准對 D9 各說各話。"""
    for text, name in ((study, "HARNESS_STUDY"), (dec, "DECISION")):
        assert RUN_A in text and RUN_B in text, name
        assert API_A in text and API_B in text, name
        assert "只在 block a" in text, f"{name} 沒寫 P-H0 只在 block a"
    assert "[38.3, 68.3]" in study and "[38.3, 68.3]" in dec


def test_probe_failure_never_returns_success(sh: str) -> None:
    """探針全掛時的回傳碼不准是 0。

    `return $ok` 在 ok=0（三次全掛）時是 0＝成功 ⇒ 後端整個死掉會被讀成通過，
    而且是**最需要擋的那一格**。所以回傳碼一律偏移成 ≥ 1。
    """
    assert 'return "$ok"' not in sh, "探針全掛會回 0（＝成功）"
    assert "return $((10 + ok))" in sh
    assert "abort_probe_a_rc" in sh and "abort_probe_b_rc" in sh


def test_probe_failure_return_code_is_nonzero_when_run() -> None:
    """把 `probe_backend` 抽出來實跑一次：curl 全失敗時 rc 必須 ≥ 1。"""
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("沒有 bash")
    body = SH.read_text(encoding="utf-8")
    start = body.index("probe_backend() {")
    end = body.index("\nprobe_backend a ", start)
    harness = (
        "set -u\n"
        'ROOT=$(mktemp -d); mkdir -p "$ROOT/logs"\n'
        'MODEL=x\n'
        'say() { :; }\n'
        + body[start:end] + "\n"
        # 指到一個關著的埠：/v1/models 拿不到東西 ⇒ 必須非 0。
        'probe_backend t "http://127.0.0.1:1/v1/chat/completions"; echo "rc=$?"\n'
    )
    r = subprocess.run([bash, "-c", harness], capture_output=True, text=True, timeout=120)
    assert "rc=0" not in r.stdout, f"後端連不上卻回 rc=0：{r.stdout!r} {r.stderr[-300:]!r}"


def test_pid_detection_ignores_the_flock_wrapper(sh: str) -> None:
    """`flock` 那一行也含 `python3 ops/gain/gain_run.py --out …` ⇒ 會誤中。

    誤中的後果不是崩潰而是**沉默**：抓到 flock 的 pid，`kill -0` 照樣為真，
    於是「runner 死了但 flock 還在」會被讀成「還活著」。所以 pid 必須指定
    第二欄是 python3。
    """
    assert 'awk \'$2 == "python3" {print $1}\'' in sh, "pid 偵測沒有排除 flock 包裝行"
    # `$!` 是 setsid 的 pid（fork 完就結束）⇒ 不准拿它當 runner 的存活訊號。
    # 註解裡解釋這件事沒關係，邏輯裡用到才是問題。
    assert "$!" not in "\n".join(_code_lines(sh)), \
        "`$!` 是 setsid 的 pid，不能拿來當 runner 的存活訊號"
