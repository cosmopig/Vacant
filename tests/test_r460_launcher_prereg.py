"""發射器、預註冊文件、分析尺三邊不准漂開（R460：harness 六臂，LCB v2 120 題）。

這支在架構裡承重什麼：R440G 閘門（`gain_run.py`）只檢查
「DECISION 檔存在，且內文含 `--out` 的目錄名」。它**檢查不到** seed、n、offset、
arms、bank、模型、timeout——那些打錯了，run 會照跑，而且跑出來的東西看起來完全正常：
`runs/g_r460_harness_lcb2_a1` 裡會有漂亮的六臂資料，只是它答的不是
`DECISION_20260907_R460_HARNESS_PREREG.md` 註冊的那個問題。

本 run 最貴的五格：
  **`--arms` 的六條**——少一條 OFF5 就等於把 D3 的 (iii) token 門檻抽掉（D2 明文禁止省它）。
  **`--bank lcb2` / 六塊各 `--n 20`**——掉成 lcb3/189 會安靜跑一個別的實驗。
  **D9／A1 的六塊、兩個端點、每顆端點三塊**——某顆端點被塞成四塊、
    或任何一塊走回 8765 那顆 hub，會把「兩顆卡各三個 runner」安靜地變成
    「一顆卡塞四個 run」（掉進實測 6 併發才有的退化區），而那**看起來只是比較慢**。
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

# round460e：舊名字（不帶塊名、以及兩塊時代的 `_a`／`_b`）都**不在授權內**。
STALE_NAMES = ("g_r460_harness_lcb2", "g_r460_harness_lcb2_a", "g_r460_harness_lcb2_b")
BLOCKS = ("a1", "a2", "a3", "b1", "b2", "b3")
RUNS = tuple(f"runs/g_r460_harness_lcb2_{b}" for b in BLOCKS)
OFFSETS = (0, 20, 40, 60, 80, 100)
API_A = "http://100.119.113.56:1234/v1/chat/completions"
API_B = "http://100.86.226.21:1234/v1/chat/completions"
API_OF = {"a1": API_A, "a2": API_A, "a3": API_A,
          "b1": API_B, "b2": API_B, "b3": API_B}
# round460f：a* 在 round460e 已以 slice 模式通過並開跑（3/3、3/3、4/4）；
# b* 用 bank（12/12）——理由是 b 組逐片量具結構性地必有一塊 0/0（§四 E-3 補述）。
GAUGE_SCOPE_OF = {"a1": "slice", "a2": "slice", "a3": "slice",
                  "b1": "bank", "b2": "bank", "b3": "bank"}
BANK_REF_TASKS = 12          # lcb2 全 120 題裡有官方參考解的題數（實測）
HUB_MARK = "8765"
ENDPOINT_ENV = "VACANT_GAIN_API"
REQUEST_TIMEOUT_S = 1200
SEED = "g-r440-lcb2"
SEED_PRIOR_RUN = "runs/g_r447_conform_lcb2"
MODEL = "gemma-4-12b-it-qat"
PRIOR_DEFAULT = "runs/g_r449c_eq5_lcb3"
BANK_FILE = "ops/gain/data/lcb_bank_v2.jsonl"
ARMS = "OFF,CONFORM,OFF5,HPI,HOC,HMIX"
N_TASKS = 120                              # 合併後；每一塊是 20
N_PER_BLOCK = 20
N_BLOCKS = 6
BLOCKS_PER_ENDPOINT = 3

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
    """D9／A1：授權的是**六個**塊名；不帶塊名與兩塊時代的舊名字都不在授權內。"""
    assert _var(sh, "DEC") == DEC.name
    for tag, run in zip(BLOCKS, RUNS):
        assert _var(sh, f"OUT_{tag.upper()}") == run
        assert run in dec, f"DECISION 沒有授權塊名 {run}"
    # R440G 是子字串比對 ⇒ 舊名字會照樣通過它（`…_a1` 甚至整個含著 `…_a`）；
    # DECISION 與發射器都要自己再擋一次。
    assert "不在授權內" in dec, "DECISION 沒有明說舊名字不在授權內"
    assert "abort_stale_run_name" in sh, "發射器沒擋舊 run 名字"
    stale = _var(sh, "STALE_NAMES").split()
    assert sorted(stale) == sorted(STALE_NAMES), stale


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

    D9／A1 之後多驗四件事：六塊各 20、塊間**兩兩零交集**、六塊接起來逐題逐序等於
    r447 的 120、而且 **a1+a2+a3 就是 r447 的前 60 題**（P-H0 的錨）。
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
    blks = [[x["task_id"] for x in load_tasks("lcb2", SEED, N_PER_BLOCK, offset=o)]
            for o in OFFSETS]
    assert all(len(b) == N_PER_BLOCK for b in blks)
    for i, x in enumerate(blks):
        for y in blks[i + 1:]:
            assert set(x) & set(y) == set(), "塊間有交集——不准合併（Q1 MISS）"
    flat = [t for b in blks for t in b]
    assert flat == a, "六塊接起來不等於原本那 120 題、那個順序"
    assert len(set(flat)) == N_TASKS, "六塊的聯集不是 120 題"
    assert flat[:60] == off[:60], "a1+a2+a3 不是 r447 的前 60 題 ⇒ P-H0 的錨要重算"


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
    '--request-timeout-s "$REQUEST_TIMEOUT_S"', "--review-timeout-s 380", "--retries 4",
    '--models "$MODEL"', '--seed "$SEED"', '--decision "$DEC"', '--out "$OUT"',
    '--arms "$ARMS"',
])
def test_launch_command_carries_the_registered_flag(sh: str, flag: str) -> None:
    assert flag in sh, f"發射指令少了 {flag}"


def test_request_timeout_is_the_registered_1200(sh: str, dec: str) -> None:
    """A1：逾時是實驗條件，發射器與 DECISION 必須是同一個數字。

    600 在三併發之下會把正常的長生成誤判成逾時 ⇒ **假的 infra_void**，
    而假 void 同時污染 complete-case 分母與 token 帳。
    """
    m = re.search(r"^REQUEST_TIMEOUT_S=(\d+)", sh, re.M)
    assert m and int(m.group(1)) == REQUEST_TIMEOUT_S, "發射器的逾時不是 1200"
    assert f"--request-timeout-s {REQUEST_TIMEOUT_S}" in dec
    assert 'grep -q -- "--request-timeout-s $REQUEST_TIMEOUT_S" "$DEC"' in sh, \
        "發射器沒有對 DECISION 驗這一格"
    assert "abort_timeout_not_prereg" in sh
    # 牆鐘護欄＝逾時 + WALL_CLOCK_SLACK_S；DECISION 要寫出那個和。
    from ops.gain.brain_cline import WALL_CLOCK_SLACK_S
    assert str(REQUEST_TIMEOUT_S + WALL_CLOCK_SLACK_S) in dec, \
        "DECISION 沒寫出牆鐘護欄的實際上限"


def test_decision_registers_the_same_flags(dec: str) -> None:
    for flag in ("--n 20", "--offset 0", "--bank lcb2", "--probe-sample 0",
                 "--request-timeout-s 1200", "--review-timeout-s 380", "--retries 4"):
        assert flag in dec, f"DECISION 沒寫到 {flag}"
    for off in OFFSETS:
        assert f"--offset {off}" in dec, f"DECISION 沒寫到 --offset {off}"


def test_launcher_never_carries_another_runs_task_count(sh: str) -> None:
    for line in _code_lines(sh):
        for stale in ("--n 189", "--n 371", "--n 60", "--n 40", "--n 120"):
            assert stale not in line, f"題數抄成別的 run: {line!r}"
    m = re.search(r"^N_BLOCK=(\d+)", sh, re.M)
    assert m and int(m.group(1)) == N_PER_BLOCK, "每塊題數不是 20"


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

    D9／A1 之後「別人」的定義是：本支自己的**六塊**不算別人（它們是設計要的併發），
    其餘任何 gain_run 都算。所以判準是 (a) 錨行首的 grep 還在、
    (b) 過濾掉的**只有** `$ALL_OUTS` 那六個、而且是 `--out <dir> ` 的**逐塊**比對
    （前綴比對會把兩塊時代的 `…_a` 也算成自己人）、(c) 每一塊之間再查一次。
    """
    assert 'grep "^python3 ops/gain/gain_run\\.py"' in sh, "pattern 沒有錨在行首"
    assert 'index($0, "--out " o[i] " ")' in sh, \
        "過濾自己人的規則不見了（或退回成會誤中舊塊名的前綴比對）"
    assert 'awk -v outs="$ALL_OUTS"' in sh, "自己人的名單不是來自 ALL_OUTS"
    # ALL_OUTS 是六個 `$OUT_xx` 的引用（DRY）；展開之後必須逐字等於註冊的六個名字。
    expanded = [_var(sh, tok.lstrip("$")) for tok in _var(sh, "ALL_OUTS").split()]
    assert expanded == list(RUNS), expanded
    assert "abort_other_run" in sh
    # 每一塊之間要再查一次：前一塊起來之後才冒出來的第三方 run 也要擋。
    assert sh.count("count_other_runs") >= 3, "只在發射前查一次；塊與塊之間沒有再查"


def test_probe_checks_body_not_only_http_200(sh: str) -> None:
    assert "body_ok=" in sh
    assert '[ "$code" = "200" ] && [ "$body" = "yes" ]' in sh
    assert '[ "$ok" -eq 3 ]' in sh, "探針要 3/3 才准發射"
    assert "for i in 1 2 3; do" in sh, "探針次數不是 3"


# ── round460f：量具範圍（--gauge-scope）─────────────────────────────
#
# 發射當天量到的結構性衝突：lcb2 的 120 題只有 12 題有官方參考解，
# 六塊之間是 3/3/4/**0**/1/1 ⇒ offset=60 那塊量到 0/0，runner 照
# 「量不到不是通過」拒跑（正確）。而後 60 題總共只有 2 題有參考解
# ⇒ **b 組不論怎麼三等分，一定至少一塊是 0**，在 b 組內部重切救不了。
# 裁決是換一條**更強**的規則：對整個題庫驗 12/12。下面這一組釘住
# 「更強」而不是「更鬆」——slice 逐字不變、bank 更嚴、擋門一條都沒少。
def test_gauge_scope_flag_exists_and_defaults_to_slice() -> None:
    """預設必須是 slice：既有五臂與 E-5 的釘死不准因為這個旗標而變。"""
    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    assert '"--gauge-scope", default="slice", choices=["slice", "bank"]' in src, \
        "旗標不存在，或預設不是 slice"


def test_bank_scope_has_reference_solutions_where_the_slice_has_none() -> None:
    """本輪的事實基礎：offset=60 那塊逐片是 0，整個題庫是 12。"""
    from ops.gain.gain_run import _canonical_solutions, load_tasks
    refs = _canonical_solutions("lcb2")
    per_block = []
    for off in OFFSETS:
        ts = load_tasks("lcb2", SEED, N_PER_BLOCK, offset=off)
        per_block.append(sum(1 for t in ts if refs.get(t["task_id"])))
    assert per_block == [3, 3, 4, 0, 1, 1], per_block
    assert sum(per_block) == BANK_REF_TASKS
    # 結構性論證：後 60 題只有 2 題有參考解 ⇒ 任何三等分都至少一塊是 0。
    assert sum(per_block[3:]) == 2, "b 組的參考解題數變了 ⇒ E-3 補述的論證要重寫"


def test_bank_scope_gauges_the_whole_bank_and_slice_mode_is_unchanged() -> None:
    """bank 在 offset=60 的塊上得到 12/12；slice 在同一塊上仍然是 0/0。

    這是零 API 的（參考解與壞樁都不經模型），但會跑沙箱。
    """
    from ops.gain.gain_run import load_tasks, probe_instrument
    blk = load_tasks("lcb2", SEED, N_PER_BLOCK, offset=60)
    # slice：逐字現行行為——n=0，而且**不算**任何覆蓋鍵。
    sl = probe_instrument(blk, lambda _r: None, sample=len(blk), bank="lcb2")
    assert sl["n"] == 0, sl["n"]
    assert "coverage_n" not in sl, "slice 模式多算了東西 ⇒ 現行行為被改到了"
    # bank：整個題庫的 12 題、兩個方向全過，外加本塊 20 題的出貨閘門覆蓋。
    full = load_tasks("lcb2", SEED, 0)
    assert len(full) == N_TASKS
    bk = probe_instrument(full, lambda _r: None, sample=len(full), bank="lcb2",
                          coverage_tasks=blk)
    assert bk["n"] == BANK_REF_TASKS, bk["n"]
    assert bk["ref_pass"] == BANK_REF_TASKS, "參考解方向沒有全過"
    assert bk["broken_rejected"] == BANK_REF_TASKS, "壞樁方向沒有全擋"
    assert bk["visible_n"] == BANK_REF_TASKS
    assert bk["visible_ref_pass"] == bk["visible_stub_rejected"] == BANK_REF_TASKS
    # 擴大量具不准把「本塊每題都有出貨閘門」這條擋門弄不見。
    assert bk["coverage_n"] == N_PER_BLOCK
    assert bk["coverage_visible_n"] == N_PER_BLOCK, bk.get("coverage_missing_visible")


def test_bank_scope_still_gates_block_level_visible_coverage() -> None:
    """負控：本塊有一題沒有 visible_check 時，覆蓋數必須掉下來（＝擋得住）。"""
    from ops.gain.gain_run import load_tasks, probe_instrument
    blk = [dict(t) for t in load_tasks("lcb2", SEED, N_PER_BLOCK, offset=60)]
    blk[0]["visible_check"] = {"code": ""}
    full = load_tasks("lcb2", SEED, 0)
    bk = probe_instrument(full[:1], lambda _r: None, sample=1, bank="lcb2",
                          coverage_tasks=blk)
    assert bk["coverage_visible_n"] == N_PER_BLOCK - 1, bk["coverage_visible_n"]
    assert bk["coverage_missing_visible"] == [blk[0]["task_id"]]
    # 而且 runner 真的把它當停止條件（不是只印出來）。
    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    assert 'if pr["coverage_visible_n"] < pr["coverage_n"]:' in src
    assert "沒有 visible_check" in src


def test_launcher_assigns_the_registered_gauge_scope_per_block(sh: str, dec: str) -> None:
    """哪一塊配哪一種模式：發射器的表與 DECISION §二 的指令表必須一致。"""
    for tag, scope in GAUGE_SCOPE_OF.items():
        assert f"--gauge-scope {scope}" in dec, f"DECISION 沒註冊 --gauge-scope {scope}"
    assert '--gauge-scope "$scope"' in sh, "發射指令沒有把量具範圍傳下去"
    assert 'grep -q -- "--gauge-scope $scope" "$DEC"' in sh, \
        "發射器沒有對 DECISION 驗量具範圍"
    # DECISION 的指令表要逐塊寫出來（a* slice、b* bank）。
    for tag, scope in GAUGE_SCOPE_OF.items():
        row = f"`runs/g_r460_harness_lcb2_{tag}`"
        line = next((ln for ln in dec.splitlines() if ln.startswith(f"| {tag} |")), None)
        assert line and row in line, f"DECISION 指令表沒有 {tag} 那一列"
        assert f"--gauge-scope {scope}" in line, \
            f"DECISION 指令表的 {tag} 沒有寫 --gauge-scope {scope}"


def test_launcher_can_launch_a_subset_without_aborting_on_running_blocks(sh: str) -> None:
    """`BLOCKS=b1,b2,b3` 要發得出去——a* 的目錄**本來就該存在**（它們正在跑）。

    目錄檢查若還是掃全部六塊，補發永遠會撞 `abort_dir_exists`。
    但「別人在跑」的判準仍然要涵蓋全部六塊（a* 是自己人，不是別人）。
    """
    assert 'BLOCKS="${BLOCKS:-a1 a2 a3 b1 b2 b3}"' in sh, "沒有 BLOCKS 子集旗標"
    # 「目錄／launch.log 已存在」那一圈要走子集；
    # 「舊名字」那一圈**仍然**該掃全部六塊（那是設計檢查，與這次發射範圍無關）。
    dir_loop = sh.split("for OUT in $SEL_OUTS; do", 1)
    assert len(dir_loop) == 2, "目錄檢查沒有改成只看要發的那幾塊"
    guard = dir_loop[1].split("done", 1)[0]
    assert "abort_dir_exists" in guard and "abort_launchlog_exists" in guard, \
        "已存在檢查不在子集那一圈裡"
    assert "for OUT in $ALL_OUTS; do" in sh, "舊名字檢查不該縮成子集"
    assert "abort_stale_run_name" in sh
    # 認不得的塊名要停，不是安靜地少發。
    assert "abort_unknown_block" in sh and "abort_no_block_selected" in sh
    # 自己人的名單仍然是全部六塊。
    assert 'awk -v outs="$ALL_OUTS"' in sh
    # 拓撲不變量仍然對**整張表**檢查（子集只改發射範圍，不改註冊的設計）。
    assert 'printf \'%s\\n\' "$BLOCK_TABLE" | awk -v x="$API_A"' in sh, \
        "每端點三塊的檢查被改成只看子集了"


def test_launcher_probes_only_the_endpoints_it_will_use(sh: str) -> None:
    """補發 b 組時不要去打正在跑 a 組的那顆卡。"""
    assert 'grep -qx -- "$API_A"' in sh and 'grep -qx -- "$API_B"' in sh
    assert 'probe_backend a "$API_A"' in sh and 'probe_backend b "$API_B"' in sh


def test_launcher_probe_max_tokens_matches_the_runner_constant(sh: str) -> None:
    """round460e-2：發射器的 curl 探針不准比 runner 的線路探針小。

    第一次發射就死在這一格：`max_tokens:16` 之下 gemma-4-12b-it-qat 回
    HTTP 200／`finish_reason=length`／`content=""`（13 個 reasoning token 把 16 的預算
    吃光）⇒ 探針 0/3、`abort_probe_a_rc10`，而後端其實是好的。
    round460c 已經在 runner 那邊修過同一件事，**發射器被漏掉**——所以這裡把兩邊釘在一起。
    """
    from ops.gain.harness_arms import WIRE_PROBE_MAX_TOKENS
    m = re.search(r"^PROBE_MAX_TOKENS=(\d+)", sh, re.M)
    assert m, "發射器沒有寫出探針的 max_tokens"
    assert int(m.group(1)) == WIRE_PROBE_MAX_TOKENS, (
        f"發射器探針 {m.group(1)} 與 runner 的 {WIRE_PROBE_MAX_TOKENS} 不一致"
        "——兩邊分開改就會再出現一次「後端好的但發射器說壞」")
    assert int(m.group(1)) >= 256, "實測 16／64 回空 content，256 才回 OK"
    # 兩個探針（3× 存活 ＋ 多輪線路）都要用它，不准留任何硬編的小值。
    assert sh.count('\\"max_tokens\\":$PROBE_MAX_TOKENS') == 2
    for line in _code_lines(sh):
        assert "max_tokens\\\":16" not in line, f"還有硬編的 max_tokens 16: {line!r}"


def test_launcher_probe_still_requires_nonempty_content(sh: str) -> None:
    """放大 max_tokens **不准**順手把 body 檢查放寬——那等於把探針關掉。"""
    assert 'print("yes" if ("error" not in d and c.strip()) else "no")' in sh, \
        "探針的 body 判準被改了：content 非空這一條是它唯一的牙齒"
    assert '[ "$code" = "200" ] && [ "$body" = "yes" ]' in sh
    assert '[ "$ok" -eq 3 ]' in sh


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
    assert "1200" in dec and "呼叫之間" in dec
    # 逾時加倍 ⇒ 最壞燒掉的時間也加倍，這件事要跟著更正，不能留舊算式。
    assert "~6000 s" in dec, "逾時改成 1200 之後，最壞燒掉的時間沒有跟著更正"


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
    assert len(A.MUTANTS) == 11, sorted(A.MUTANTS)
    for m in ("M8_topology_not_enforced", "M9_stage2_any_arm",
              "M10_block_broken_not_propagated",
              "M11_endpoint_balance_not_checked"):
        assert m in A.MUTANTS, f"D9／A1 的突變體 {m} 不見了"
    assert A.mutation_check() == 0


# ══════════════════════════════════════════════════════════════════════
# D9：兩個後端、兩塊、併發
# ──────────────────────────────────────────────────────────────────────
# 這一組守的是一個**看不出來**的失敗：兩塊都跑完、六臂資料漂亮、
# 但其實兩塊打的是同一顆 GPU（或都被 hub 路由回同一顆）。那個世界裡
# 「併發」只買到排隊，牆鐘不會減半，而且沒有任何一個既有欄位會變紅。
# 所以判準必須落在**端點身分**上，而端點身分唯一的落盤處是 calls.jsonl 的 `api`。
# ══════════════════════════════════════════════════════════════════════
def test_launcher_launches_all_six_blocks(sh: str) -> None:
    """一支發射器發六塊，各自 offset／端點；不是發一塊也不是發兩塊。"""
    for tag, off in zip(BLOCKS, OFFSETS):
        assert f"OFFSET_{tag.upper()}={off}" in sh, f"{tag} 的 offset 不是 {off}"
    # 發射走的是同一張表，不准另外抄一份。
    for tag, run, off in zip(BLOCKS, RUNS, OFFSETS):
        api = "$API_A" if tag.startswith("a") else "$API_B"
        assert (f"{tag} $OUT_{tag.upper()} $OFFSET_{tag.upper()} {api} "
                f"{GAUGE_SCOPE_OF[tag]}") in sh, f"BLOCK_TABLE 少了 {tag} 那一列（或量具範圍不對）"
    assert 'launch_block "$tag" "$OUT" "$off" "$api" "$scope"' in sh, \
        "發射不是走 BLOCK_TABLE"
    # 六塊加起來要等於註冊的題數；少一塊就是另一個實驗。
    assert N_BLOCKS * N_PER_BLOCK == N_TASKS
    assert len(RUNS) == N_BLOCKS


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


def test_launcher_refuses_the_hub_and_endpoint_oversubscription(sh: str) -> None:
    """D9／A1 的硬禁令：不准走 hub、兩顆端點不准同位址、每顆端點恰好三塊。

    「同端點」在六塊之下**不再是違規、是設計**；要擋的變成**超賣**
    （某台四塊 ⇒ 掉進實測 6 併發才有的退化區，而那看起來只是比較慢）。
    """
    assert _var(sh, "HUB_MARK") == HUB_MARK
    assert "abort_hub_endpoint" in sh
    assert "abort_same_endpoint" in sh
    assert "abort_endpoint_imbalance" in sh, "沒有擋端點超賣"
    assert "abort_block_count" in sh, "沒有擋塊數不是 6"
    assert '[ "$API_A" != "$API_B" ]' in sh, "沒有比較兩顆端點"
    m = re.search(r"^BLOCKS_PER_ENDPOINT=(\d+)", sh, re.M)
    assert m and int(m.group(1)) == BLOCKS_PER_ENDPOINT
    for api in (API_A, API_B):
        assert HUB_MARK not in api, f"註冊的端點 {api} 指向 hub"
    # 表裡每顆端點真的是三塊（發射器自己數一次，本檔在此再數一次）。
    assert sum(1 for t in BLOCKS if API_OF[t] == API_A) == BLOCKS_PER_ENDPOINT
    assert sum(1 for t in BLOCKS if API_OF[t] == API_B) == BLOCKS_PER_ENDPOINT


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
    """六塊各自 flock、各自 launch.log——共用會讓後面幾塊安靜地不跑。"""
    assert 'lock="$ROOT/.launch_harness_lcb2_${tag}.lock"' in sh
    assert 'flock -n "$lock" python3 ops/gain/gain_run.py' in sh
    assert '>>"$OUT.launch.log"' in sh
    # 發射器自己那把鎖仍在（防重複發射整支）。
    assert "flock -n 9" in sh


def test_worker_concurrency_and_block_parallelism_are_distinct(sh: str) -> None:
    """平行度來自六個行程，不是來自 runner 的旋鈕——兩個數字要分開寫。"""
    assert "WORKER_CONCURRENCY=1" in sh
    assert f"BLOCK_PARALLELISM={N_BLOCKS}" in sh
    assert "abort_concurrency_knob_appeared" in sh
    src = (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")
    assert "ThreadPoolExecutor(" not in src, \
        "runner 長出併發旋鈕了 ⇒ WORKER_CONCURRENCY=1 這格要重新裁決"


def test_decision_registers_the_six_block_topology(dec: str) -> None:
    """預註冊要寫死：六個名字、兩個端點、每顆三塊、合併分析、不准走 hub。"""
    assert "D9" in dec
    for run in RUNS:
        assert run in dec
    assert API_A in dec and API_B in dec
    for off in OFFSETS:
        assert f"--offset {off}" in dec
    assert ENDPOINT_ENV in dec, "DECISION 沒寫端點是靠哪個環境變數傳的"
    assert "hub" in dec and "禁止" in dec
    assert "endpoint_block_count_not_3" in dec, "DECISION 沒指名超賣的擋門欄位"
    assert "pooled_task_count_not_120" in dec, "DECISION 沒指名聯集擋門"
    assert "block_count_not_6" in dec
    # 後端是 task 層級干擾項、不是 arm 層級混淆——D9 成立的全部理由。
    assert "task 層級" in dec and "arm 層級" in dec


def test_decision_records_the_ph0_degradation(dec: str) -> None:
    """A1 要求寫明：六塊之下 persona 只剩 a1 的前 20 題對齊 ⇒ P-H0 變成非配對探針。"""
    assert "只在 a1+a2+a3" in dec, "DECISION 沒寫 P-H0 讀的是哪三塊"
    assert "不對齊" in dec or "錯開" in dec
    assert "38.3" in dec and "68.3" in dec, "P-H0 的窗沒寫進 DECISION"
    assert "53.33" in dec, "P-H0 的錨（r447 前 60 題）沒寫進 DECISION"
    assert "±15pp" in dec
    # 窗**不准**因為 A1 再放寬——放寬只會讓它更容易 HIT。
    assert "窗不因此再放寬" in dec, "沒有寫死「不再放寬」"
    assert "非配對" in dec, "沒有寫明 P-H0 退化成非配對比較"
    # 原本 ±15 的理由（n 減半）仍然要在。
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

    用 r447 的真 rows 切成**六塊**再合併：交付數與 token 總量都必須逐字重現，
    否則「合併」就是一條會安靜改數字的路徑。
    """
    run = ROOT / SEED_PRIOR_RUN
    if not (run / "rows.jsonl").exists():
        pytest.skip(f"{SEED_PRIOR_RUN} 不在本 checkout")
    from ops.gain import analyze_r460 as A
    from ops.gain.gain_run import load_tasks
    rows, _, calls = A.load_run(run)
    blocks = []
    for tag, name, off in zip(BLOCKS, A.AUTHORIZED_BLOCKS, OFFSETS):
        ids = {t["task_id"] for t in load_tasks("lcb2", SEED, N_PER_BLOCK, offset=off)}
        api = API_OF[tag]
        rs = [r for r in rows if r["task_id"] in ids]
        cs = [dict(c, api=api) for c in calls
              if (c.get("meta") or {}).get("task_id", "") in ids]
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
    assert out["block_order"] == list(A.AUTHORIZED_BLOCKS), "塊沒有依 offset 排序"
    for sub in out["blocks"].values():
        assert sub["per_arm"]["OFF"]["measured"] == N_PER_BLOCK
    # P-H0 讀的是 a1+a2+a3 的聯集，不是合併值、也不是任何單一塊。
    assert out["prereg"]["P-H0"]["source_field"] == \
        "ph0_pool.per_arm.OFF.deliv_pp_denom_measured"
    assert out["ph0_pool_blocks"] == list(A.PH0_BLOCKS)
    assert out["ph0_pool"]["per_arm"]["OFF"]["measured"] == 60
    assert round(out["prereg"]["P-H0"]["value"], 2) == 53.33
    assert out["prereg"]["P-H0"]["value"] != \
        out["prereg"]["P-H0"]["pooled_off_deliv_pp_NOT_ARBITER"]
    # 六塊的端點都記下來了：恰好兩個不同的直連端點、每個三塊。
    assert out["topology"]["endpoints_all"] == sorted([API_A, API_B])
    assert out["topology"]["blocks_n"] == N_BLOCKS
    assert out["topology"]["task_ids_union"] == N_TASKS
    assert {k: len(v) for k, v in out["topology"]["blocks_per_endpoint"].items()} == \
        {API_A: BLOCKS_PER_ENDPOINT, API_B: BLOCKS_PER_ENDPOINT}


@pytest.mark.parametrize("kw,marker", [
    ({"hub": True}, "block_used_hub"),
    ({"overlap": True}, "block_task_overlap"),
    ({"overlap": True}, "pooled_task_count_not_120"),
    ({"same_endpoint": True}, "endpoints_n_not_2"),
    ({"imbalance": True}, "endpoint_block_count_not_3"),
])
def test_analyzer_topology_violations_are_broken_reasons(kw, marker) -> None:
    """每一種拓撲違規各自要進 `broken_reasons`（E-7）。

    `imbalance` 是 round460e 新增的那一格：端點還是兩顆、塊數還是六，
    但被塞成 4／2。那個世界裡**沒有任何既有欄位會變紅**，只會比較慢。
    """
    from ops.gain import analyze_r460 as A
    out = A._pooled(A._fixture_blocks(**kw))
    assert any(s.startswith(marker) for s in out["broken_reasons"]), \
        f"{marker} 沒有被算成 BROKEN：{out['broken_reasons']}"


def test_analyzer_refuses_to_score_a_partial_block_set() -> None:
    """少給塊就結算＝安靜地把 n 砍掉換一個實驗；必須紅。"""
    from ops.gain import analyze_r460 as A
    out = A._pooled(A._fixture_blocks()[:1])
    assert any(s.startswith("block_count_not_6") for s in out["broken_reasons"]), \
        out["broken_reasons"]
    # 少一塊（五塊）也要紅——不是只擋「只有一塊」那個極端。
    out5 = A._pooled(A._fixture_blocks()[:5])
    assert any(s.startswith("block_count_not_6") for s in out5["broken_reasons"])
    assert any(s.startswith("pooled_task_count_not_120")
               for s in out5["broken_reasons"]), out5["broken_reasons"]


def test_analyzer_refuses_to_judge_ph0_without_all_three_anchor_blocks() -> None:
    """錨塊不齊 ⇒ P-H0 不判（缺一塊就換了一個錨，而錨換了窗沒有意義）。"""
    from ops.gain import analyze_r460 as A
    blocks = [b for b in A._fixture_blocks() if b["name"] != A.PH0_BLOCKS[1]]
    out = A._pooled(blocks)
    assert out["ph0_pool"] is None
    assert out["prereg"]["P-H0"]["value"] is None
    assert out["prereg"]["P-H0"]["hit"] == "UNEVALUABLE"


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
    assert "--run " + " ".join(RUNS) in dec, "收官指令沒有寫成六塊一起餵"
    assert "合併後的量" in dec
    assert "塊間點估計不得互相比較" in dec or "點估計不得互相比較" in dec
    assert "topology.violations" in dec


def test_decision_freezes_stage_two_as_two_blocks(dec: str) -> None:
    """階段二也凍結成兩塊，而且不准沿用階段一的 P-H0 窗。"""
    assert "runs/g_r461h_harness_lcb3_a" in dec and "runs/g_r461h_harness_lcb3_b" in dec
    assert "--offset 0 --n 95" in dec and "--offset 95 --n 94" in dec
    assert "不准沿用本檔的 [38.3, 68.3]" in dec


def test_study_and_decision_agree_on_d9(study: str, dec: str) -> None:
    """研究文件與預註冊不准對 D9／A1 各說各話。"""
    for text, name in ((study, "HARNESS_STUDY"), (dec, "DECISION")):
        for run in RUNS:
            assert run in text, f"{name} 沒寫到 {run}"
        assert API_A in text and API_B in text, name
        assert "只在 a1+a2+a3" in text, f"{name} 沒寫 P-H0 讀的是哪三塊"
        assert "每顆端點" in text or "每台三塊" in text, f"{name} 沒寫每顆端點三塊"
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
    end = body.index("\n# rc 9 ＝", start)
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
