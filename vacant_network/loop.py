"""loop — **迴圈在父行程，不在掛鉤裡**。

這支在架構裡承重什麼（`decisions/DECISION_20260929_LOOP_WITHOUT_POSSESSION.md`）
---------------------------------------------------------------------------

量到的三個缺口裡，兩個是「把裁決點放進 agent 行程」造成的：

* `vrun/envmap.py` 只對 `OPENAI_API_KEY`／`ANTHROPIC_API_KEY` 給 sentinel，
  `OPENROUTER_API_KEY` 整個刪掉 ⇒ 只讀那個變數的 agent（opencode 的 openrouter
  provider）在本機就失敗，一次 wire 都沒發。
* opencode 的 plugin 沒有 stop 等價事件 ⇒ `trace/zerostop.py` 的回合結束檢查不可達。

兩者的共同後果是**靜默無效**：病歷與簽章鏈都正常，零個裁決。

`ops/eval/native_acceptance_bridge.py` 證明了裁決點可以在 agent 行程之外。缺的是迴圈。
本模組就是那個迴圈，而且**不依賴 wire 中介、不依賴任何掛鉤**：

    vacant loop --suite <dir> --attempts N --feedback prompt -- <agent cmd>
      attempt 1: spawn agent（原生、完整行為）→ 凍結候選 → 在釘住的套件上重驗
      非 accept：把**可見套件自己的失敗原文**送進下一次嘗試的提示詞
      accept：簽裁決 → 收件端重驗 → 寫入 → 讀回 → 放行
      用完預算仍非 accept：拒交（不交付），並把失敗原文留給人

掛鉤從**必要條件**降級成**加速器**（回合內中途回饋）。沒有掛鉤也不掉級。

為什麼迴圈必須是父行程的：任何「是一個可 spawn 的 CLI」的 agent 平台都自動獲得
完整能力，而回合結束事件不是每個平台都有（opencode 沒有）。父行程只需要退出碼。

## 誠實邊界（改碼請保留）

1. **只證明「agent 有跑」。** 迴圈靠子行程退出碼知道回合結束。agent 若自己殺掉自己
   卻留下通過的檔案，這裡當通過——那個檔案是通過可見套件的，而通過可見套件不等於
   滿足需求（`suitegauge.py` 的單邊保證，見 policy.py 的同名引文）。
2. **回饋一定出現在模型的輸入裡，不是「不可忽略」。** R535 量過寫檔式回饋被讀到的比例
   是 1/46；`--feedback prompt` 把同一段文字接在下一個提示詞的尾端，命中率較高，但
   仍然是「送得到」不是「照做」。
3. **隱藏資料永不進提示詞。** 回饋只來自 `--suite` 那一個目錄（客戶自己的驗收套件）。
4. **同 OS 帳號時隔離靠路徑，不是靠權限。** 收件端 home 與工作區分離，並在放行前
   重算每個物件的雜湊；對不上就拒絕。要不可竄改，收件端要跑在另一個帳號／另一台機器。
5. **不中介模型通道。** 這一點是刻意的：中介要求金鑰變數白名單（缺口 W1）。放棄
   `requests_seen` 這種證據，換取「對任何 CLI 都成立」。要通道中介的形状仍在
   `vrun/launcher.py`，兩者不共用程式路徑。
"""
from __future__ import annotations

import dataclasses
import os
import pathlib
import shlex
import subprocess
import time
from typing import Any, Sequence

DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT_S = 1800.0

#: 走 prompt 還是走工作區檔。預設 prompt：R535 量過寫檔式回饋被 agent 讀到的比例是
#: 1/46；接在提示詞尾端命中率較高。兩者都可指定 `--feedback both`。
FEEDBACK_MODES = ("prompt", "file", "both", "none")

EXIT_ACCEPT = 0
EXIT_REFUSE = 20
EXIT_EXHAUSTED = 21
EXIT_INFRA = 22

FEEDBACK_HEADER = (
    "A previous attempt at this task was checked against the task's acceptance "
    "suite and it did not pass. The suite reported:")
FEEDBACK_FOOTER = (
    "Fix the file so the suite passes. Do not change the interface away from "
    "what the suite imports. The suite is the only thing that decides; there is "
    "no partial credit and no way to see the suite's own cases.")


@dataclasses.dataclass
class Attempt:
    n: int
    agent_rc: int
    timed_out: bool
    wall_s: float
    accepted: bool
    detail: str
    outcome: str


@dataclasses.dataclass
class LoopResult:
    attempts: list[Attempt]
    accepted: bool | None
    exit_code: int
    artifact_sha256: str | None
    wall_s: float
    total_attempts_used: int
    events: list[dict[str, Any]]


def _feedback_text(detail: str, limit: int = 1800) -> str:
    return (detail or "").strip()[:limit]


def _compose_prompt(base: str, detail: str) -> str:
    fb = _feedback_text(detail)
    if not fb:
        return base
    return base + "\n\n" + FEEDBACK_HEADER + "\n\n" + fb + "\n\n" + FEEDBACK_FOOTER


def run_loop(*, workspace: pathlib.Path, suite: pathlib.Path,
             cmd: Sequence[str], attempts: int = DEFAULT_ATTEMPTS,
             feedback: str = "prompt", timeout_s: float = DEFAULT_TIMEOUT_S,
             env: dict[str, str] | None = None,
             check=None, on_attempt=None) -> LoopResult:
    """跑 agent、驗收、不合格就把可見套件的失敗原文送回下一次嘗試。

    `check(workspace, attempt) -> (accepted, detail, artifact_sha256)` 是裁決點。
    預設走 `intake.flow`（prepare/submit/release），所以簽章、內容定址凍結與讀回
    都不是這支另寫的一份——注入別的裁決點是為了測試，不是為了取代。
    """
    if feedback not in FEEDBACK_MODES:
        raise ValueError(f"feedback must be one of {FEEDBACK_MODES}")
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    workspace = pathlib.Path(workspace).resolve()
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist: {workspace}")
    suite = pathlib.Path(suite).resolve()
    if not suite.is_dir():
        raise ValueError(f"suite does not exist: {suite}")
    # 權威套件在工作區外：「agent 改得到的驗收不是驗收」（vrun/launcher.py 的形狀）。
    if suite == workspace or workspace in suite.parents:
        raise ValueError("suite must live outside the workspace")

    e = dict(os.environ if env is None else env)
    recs: list[Attempt] = []
    events: list[dict[str, Any]] = []
    t_all = time.time()
    prompt_file = workspace / "VACANT_FEEDBACK.md"

    for n in range(1, attempts + 1):
        argv = list(cmd)
        if n > 1 and feedback in ("prompt", "both"):
            detail = recs[-1].detail if recs else ""
            inject = _compose_prompt("", detail)
            if inject:
                argv = argv + [inject]
        t0 = time.time()
        timed_out = False
        try:
            p = subprocess.run(argv, cwd=workspace, env=e,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout_s)
            rc, out, err = p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as ex:
            timed_out, rc = True, 124
            out, err = ex.stdout or b"", ex.stderr or b""
        wall = round(time.time() - t0, 3)
        (workspace.parent / f"loop_attempt{n}.out").write_bytes(out)
        (workspace.parent / f"loop_attempt{n}.err").write_bytes(err)

        detail = ""
        accepted: bool | None = None
        sha = None
        infra = False
        try:
            if check is None:
                accepted, detail, sha, infra = _default_check(
                    workspace, suite, n, attempts, e)
            else:
                accepted, detail, sha = check(workspace, n)[:3]
        except Exception as ex:                      # 裁決點壞掉 ⇒ 不交付
            infra = True
            detail = f"{type(ex).__name__}: {ex}"

        if feedback in ("file", "both") and detail and not accepted:
            prompt_file.write_text(
                FEEDBACK_HEADER + "\n\n" + _feedback_text(detail)
                + "\n\n" + FEEDBACK_FOOTER, encoding="utf-8")

        outcome = "infra_void" if infra else ("accept" if accepted else "reject")
        rec = Attempt(n=n, agent_rc=rc, timed_out=timed_out, wall_s=wall,
                      accepted=bool(accepted), detail=detail, outcome=outcome)
        recs.append(rec)
        events.append({"type": "attempt", "attempt": n, "agent_rc": rc,
                       "timed_out": timed_out, "outcome": outcome,
                       "wall_s": wall, "detail_head": detail[:200]})
        if on_attempt:
            on_attempt(rec)
        if infra or accepted:
            break

    used = len(recs)
    last = recs[-1]
    if last.outcome == "infra_void":
        code, accepted_final = EXIT_INFRA, None
    elif last.accepted:
        code, accepted_final = EXIT_ACCEPT, True
    elif used >= attempts:
        code, accepted_final = EXIT_EXHAUSTED, False
    else:
        code, accepted_final = EXIT_REFUSE, False
    return LoopResult(attempts=recs, accepted=accepted_final, exit_code=code,
                      artifact_sha256=sha, wall_s=round(time.time() - t_all, 3),
                      total_attempts_used=used, events=events)


def _default_check(workspace, suite, n, attempts, env):
    """收件口的裁決：凍結 → 在釘住的副本上驗 → 簽裁決 → 放行 → 讀回。"""
    # `intake` lives on the 3.7 branch (fix/native-acceptance-bridge-audit-20260928),
    # not on main. `run_loop` itself does not need it -- the check is injectable --
    # so a main-only install still gets the loop with any check. This import is
    # therefore lazy AND guarded, and its absence is a stated condition rather
    # than an ImportError from module load.
    try:
        from .intake import flow
    except ImportError as ex:            # pragma: no cover - branch-dependent
        raise RuntimeError(
            "the intake-backed check needs vacant_network.intake, which ships on the "
            "3.7 branch (fix/native-acceptance-bridge-audit-20260928). On this build, "
            "pass a check= to run_loop instead.") from ex
    root_s = env.get("VACANT_INTAKE_ROOT")
    if not root_s:
        raise ValueError("VACANT_INTAKE_ROOT is required for the intake check")
    # open_task does `r / "trust.json"`, so root must be a Path, not the raw env
    # string. (Getting this wrong surfaced as infra_void with
    # "unsupported operand type(s) for /: 'str' and 'str'" -- measured, not guessed.)
    root = pathlib.Path(root_s)
    # The native acceptance bridge keeps the signed contract one level ABOVE the
    # intake root (<receiver_home>/contract.json vs <receiver_home>/intake/), so the
    # contract path is separate rather than derived.
    contract = env.get("VACANT_CONTRACT_PATH") or str(root / "contract.json")
    task = flow.open_task(pathlib.Path(contract), root=root)
    result = flow.submit(task, workspace, source="vacant-loop", attempt=n)
    outcome = result.get("outcome")
    detail = "; ".join(
        "{}={} {}".format(r.get("claim_id"), r.get("status"), str(r.get("detail"))[:200])
        for r in result.get("results", []))
    sha = result.get("artifact_sha256")
    accepted = outcome == "accept"
    if accepted and sha:
        rel = flow.release(task, artifact_sha256=sha)
        if not rel.get("released"):
            accepted = False
            detail += " | release refused: " + str(rel.get("reasons"))
    return accepted, detail, sha, bool(result.get("void"))


def argv_for(cli_cmd: Sequence[str]) -> list[str]:
    if not cli_cmd:
        raise ValueError("empty command")
    return list(cli_cmd)


def shell_split(s: str) -> list[str]:
    return shlex.split(s)
