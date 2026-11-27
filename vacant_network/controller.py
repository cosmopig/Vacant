"""Vacant-first 產品控制器：先取得可驗證交付，再啟動任意外部 agent。

這支不是提醒 agent「最好呼叫 Vacant」，而是把選擇權移出模型：controller 本身直接
delegate、重驗 check、驗 receipt/trust card，通過後才到唯一的 subprocess 出口。
Hermes、Claude Code 或任何 CLI agent 都只是 gate 後的消費者，無法在此流程內先跑。

誠實邊界：保證只涵蓋透過本 controller 啟動的子行程；無法阻止同一 OS 使用者繞過
本命令直接執行 agent。需要強制全機唯一出口時，仍須容器、ACL 或 egress policy。
"""

from __future__ import annotations

import json
import os
import signal
import string
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .atomic import atomic_write_text, file_lock
from .checks import compile_check
from .receipt import ReceiptError, VerifiedReceipt, verify_delegation_receipt

_ALLOWED_FIELDS = {"task", "answer", "task_id", "receipt_path", "context_path"}
_STRONG_LAUNCH_CHECKS = {"equals", "json_schema", "run_python"}
_SHELL_EXECUTABLES = {
    "bash", "busybox", "cmd", "cmd.exe", "cscript", "cscript.exe", "csh", "dash",
    "env", "fish", "ksh", "lua", "node", "nodejs", "osascript", "perl", "php",
    "powershell", "powershell.exe", "pwsh", "pwsh.exe", "ruby", "sh", "tcsh",
    "wscript", "wscript.exe", "xonsh", "zsh",
}


class GateRejected(RuntimeError):
    """委派、驗章、客觀重驗或 policy 未過；外部 agent 尚未啟動。"""


class AgentRunFailed(RuntimeError):
    """gate 已通過，但下游 agent 執行失敗。"""

    def __init__(self, result: "ControllerResult", reason: str | None = None) -> None:
        super().__init__(reason or f"downstream agent exited with code {result.returncode}")
        self.result = result


class AgentEvidenceError(RuntimeError):
    """下游 agent 已執行，但結果證據落盤失敗；不得誤報為「未啟動」。"""

    def __init__(self, result: "ControllerResult", cause: Exception) -> None:
        super().__init__(f"agent ran, but result evidence could not be persisted: {cause}")
        self.result = result


@dataclass(frozen=True)
class GatePolicy:
    """產品預設是 fail-closed：trust、驗證、稽核與至少一名 reviewer 全部必須成立。"""

    require_trust_on: bool = True
    require_verified: bool = True
    require_audit_pass: bool = True
    min_reviews: int = 1
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.min_reviews < 0:
            raise ValueError("min_reviews must be >= 0")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")

    def admit(self, receipt: VerifiedReceipt) -> None:
        if self.require_trust_on and not receipt.trust_on:
            raise GateRejected("trust is off")
        if self.require_verified and not receipt.verified:
            raise GateRejected("Vacant delivery did not pass the objective check")
        if self.require_audit_pass and not (
            receipt.audit_performed and receipt.audit_passed is True
        ):
            raise GateRejected("delivery was not audited successfully")
        if receipt.review_passed < self.min_reviews:
            raise GateRejected(
                f"only {receipt.review_passed} passing reviews; policy requires "
                f"{self.min_reviews}")


@dataclass(frozen=True)
class ArgvTemplate:
    """shell-free argv 模板；只允許白名單 placeholder，且 argv[0] 必須是固定程式。"""

    argv: tuple[str, ...]

    def __init__(self, argv: Sequence[str]) -> None:
        if isinstance(argv, (str, bytes)):
            raise ValueError("argv must be a sequence of arguments, not a command string")
        object.__setattr__(self, "argv", tuple(argv))
        self._validate()

    def _validate(self) -> None:
        if not self.argv or any(not isinstance(arg, str) or "\x00" in arg for arg in self.argv):
            raise ValueError("argv must contain non-NUL strings")
        executable = Path(self.argv[0]).name.lower()
        if executable in _SHELL_EXECUTABLES:
            raise ValueError("shell and env launchers are not allowed as agent executables")
        formatter = string.Formatter()
        used: set[str] = set()
        for index, arg in enumerate(self.argv):
            try:
                parts = list(formatter.parse(arg))
            except ValueError as exc:
                raise ValueError(f"invalid argv template: {exc}") from exc
            for _, field, spec, conversion in parts:
                if field is None:
                    continue
                if field not in _ALLOWED_FIELDS or spec or conversion:
                    raise ValueError(f"unsupported placeholder: {field!r}")
                if index == 0:
                    raise ValueError("argv[0] must be a fixed executable")
                if field in ("task", "answer") and arg == "{" + field + "}" \
                        and (index == 0 or self.argv[index - 1] != "--"):
                    raise ValueError(
                        f"standalone {{{field}}} requires a preceding '--' option terminator")
                used.add(field)
        if executable.startswith(("python", "pypy")) and "-c" in self.argv and used:
            raise ValueError("dynamic Python -c launchers are not allowed")
        if not ({"answer", "context_path"} & used):
            raise ValueError("agent command must receive {answer} or {context_path}")

    def render(self, **values: str) -> list[str]:
        missing = _ALLOWED_FIELDS - values.keys()
        if missing:
            raise ValueError(f"missing template values: {sorted(missing)}")
        return [arg.format_map(values) for arg in self.argv]


def hermes_argv(binary: str = "hermes") -> ArgvTemplate:
    """Hermes one-shot adapter；完整 Vacant 交付在 agent 啟動時已成為輸入。"""
    prompt = (
        "This task has already passed through the mandatory Vacant-first gate. "
        "Use the verified delivery below as your baseline, apply it to the user's workspace "
        "when appropriate, run any final integration checks, and report what changed.\n\n"
        "ORIGINAL TASK:\n{task}\n\n"
        "VACANT VERIFIED DELIVERY:\n{answer}\n\n"
        "TASK ID: {task_id}\n"
        "SIGNED RECEIPT: {receipt_path}\n"
        "PUBLIC CONTEXT: {context_path}"
    )
    return ArgvTemplate((binary, "-z", prompt))


@dataclass(frozen=True)
class ControllerResult:
    request_id: str
    task_id: str
    answer: str
    receipt: dict[str, Any]
    trust_card: dict[str, Any]
    receipt_path: Path
    context_path: Path
    agent_argv: tuple[str, ...] | None = None
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    evidence_error: str = ""


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _run_agent_process(
    argv: Sequence[str],
    *,
    cwd: str | None,
    env: Mapping[str, str] | None,
    capture_output: bool,
    text: bool,
    timeout: float,
    shell: bool,
) -> subprocess.CompletedProcess[str]:
    """等主 agent 行程，不等後代持有的 stdout pipe EOF；子孫不繼承 controller stdio。"""
    if shell or not capture_output or not text:
        raise ValueError("agent runner requires shell=False, capture_output=True, text=True")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file, \
            tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=(dict(env) if env is not None else None),
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            shell=False,
            start_new_session=(os.name == "posix"),
        )
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # ⚠ 收尾不准把逾時判定弄丟：`killpg` 除了 `ProcessLookupError`
            #   還會丟 `PermissionError`（子行程在 `wait` 逾時與這一行之間結束，
            #   `process.pid` 那個 pgid 就可能已經不屬於我們了）。例外從這裡逃出去，
            #   呼叫端收到的就不是 `TimeoutExpired` 而是一個爆炸。
            #   `process.wait()` 也不給逾時：殺不掉的話它會永遠等下去。
            #   2026-09-19 在 macOS CI 上從 `vacant_network/checks.py` 的同一形狀實際炸過。
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                except Exception:                            # noqa: BLE001
                    pass
            try:
                process.kill()          # killpg 沒吃到就退回單一行程
            except Exception:                                # noqa: BLE001
                pass
            try:
                process.wait(timeout=5)
            except Exception:                                # noqa: BLE001
                pass
            stdout_file.seek(0)
            stderr_file.seek(0)
            raise subprocess.TimeoutExpired(
                list(argv), timeout,
                output=stdout_file.read(), stderr=stderr_file.read()) from exc
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            list(argv), returncode,
            stdout=stdout_file.read(), stderr=stderr_file.read())


def verify_delivery(
    ecosystem,
    result: dict[str, Any],
    *,
    task: str,
    tests: dict,
    risk: str,
    request_id: str,
    policy: GatePolicy,
) -> VerifiedReceipt:
    """controller/MCP 共用的嚴格產品 gate；只回已綁定且當下鏈有效的 receipt。"""
    try:
        answer = result["answer"]
        receipt = result["receipt"]
        card = result["trust_card"]
    except (KeyError, TypeError) as exc:
        raise GateRejected("delegate returned an incomplete product delivery") from exc
    if not isinstance(answer, str) or not isinstance(receipt, dict) or not isinstance(card, dict):
        raise GateRejected("delegate returned malformed product delivery")
    try:
        verifier = compile_check(tests)
    except Exception as exc:
        raise GateRejected(f"invalid check spec: {type(exc).__name__}: {exc}") from exc
    signer_id = receipt.get("signer", {}).get("vacant_id", "")
    anchor = ecosystem.registry.card(signer_id)
    if anchor is None:
        raise GateRejected("receipt signer is absent from the current registry")
    try:
        verified = verify_delegation_receipt(
            receipt,
            task=task,
            tests=tests,
            risk=risk,
            answer=answer,
            trust_card=card,
            anchor_pub_hex=anchor.pub_hex,
            request_id=request_id,
        )
    except ReceiptError as exc:
        raise GateRejected(f"receipt verification failed: {exc}") from exc

    resident = ecosystem.resident_by_id(signer_id)
    if resident is None:
        raise GateRejected("receipt signer is not an active resident")
    logbook = resident.body.logbook
    if not logbook.verify_chain(resident.body.public_identity()):
        raise GateRejected("deliverer logbook chain verification failed")
    actual_stream = logbook.stream_id() or signer_id
    signer_claim = receipt["signer"]
    if receipt["substrate"] != ecosystem.substrate_id \
            or signer_claim["stream_id"] != actual_stream \
            or signer_claim["branch_id"] != logbook.branch_id() \
            or signer_claim["chain_head"] != logbook.head():
        raise GateRejected("receipt does not match the current resident chain head")

    for review in card.get("reviews", []):
        envelope = review.get("envelope", {})
        reviewer_id = envelope.get("reviewer_id", "")
        reviewer_anchor = ecosystem.registry.card(reviewer_id)
        if reviewer_anchor is None or reviewer_anchor.pub_hex != review.get("reviewer_pub_hex"):
            raise GateRejected("reviewer is not anchored in the current registry")
        matching = [
            (index, entry) for index, entry in enumerate(logbook.entries)
            if entry.hash() == envelope.get("target_head")
        ]
        if len(matching) != 1:
            raise GateRejected("review target head is absent from the deliverer chain")
        index, delivery = matching[0]
        payload = delivery.payload if isinstance(delivery.payload, dict) else {}
        if index != len(logbook.entries) - 2 \
                or delivery.type != "DELIVER" \
                or delivery.branch_id != envelope.get("branch_id") \
                or payload.get("task_id") != verified.task_id \
                or payload.get("answer_sha256") != receipt["answer_sha256"]:
            raise GateRejected("review is not bound to this exact delivery and answer")

    policy.admit(verified)
    if not verifier(answer):
        raise GateRejected("local objective re-check rejected the delivered answer")
    return verified


class VacantFirstController:
    """直接委派並以簽章 gate 控制下游 agent 啟動順序。"""

    def __init__(
        self,
        ecosystem,
        *,
        policy: GatePolicy | None = None,
        runner: Runner = _run_agent_process,
        refresh_before_delegate: bool = True,
    ) -> None:
        self.ecosystem = ecosystem
        self.policy = policy or GatePolicy()
        self._runner = runner
        self.refresh_before_delegate = refresh_before_delegate
        self.root = Path(ecosystem.root) / "controller"

    @classmethod
    def from_endpoint(
        cls,
        base_url: str,
        model: str,
        *,
        root: str | Path | None = None,
        api: str = "responses",
        api_key: str | None = None,
        model_timeout: int = 900,
        policy: GatePolicy | None = None,
        runner: Runner = _run_agent_process,
    ) -> "VacantFirstController":
        """以 OpenAI-compatible／LM Studio 端點建立全良性的產品 controller。"""
        if api not in ("responses", "openai"):
            raise ValueError("api must be 'responses' or 'openai'")
        if not model:
            raise ValueError("model must be non-empty")
        if model_timeout <= 0:
            raise ValueError("model_timeout must be > 0")
        from .brains import LMStudioBrain
        from .ecosystem import Ecosystem, PRODUCT_ROSTER, assert_product_root

        brain = LMStudioBrain(
            base_url, model, api=api, api_key=api_key,
            timeout=model_timeout, max_tokens=None,
        )
        eco_root = Path(root) if root is not None else Path.home() / ".vacant-mcp"
        with file_lock(eco_root / "controller" / "bootstrap.lock", timeout=30):
            assert_product_root(eco_root)
            ecosystem = Ecosystem(
                eco_root, brain, roster=PRODUCT_ROSTER,
                k_reviewers=2, audit_rate=1.0, persist_artifacts=False,
                root_mode="product",
            )
        return cls(ecosystem, policy=policy, runner=runner)

    def _emit(self, event: str, **payload: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts_ms": time.time_ns() // 1_000_000,
                "event": event,
                **payload,
            }, ensure_ascii=False) + "\n")
            f.flush()

    @staticmethod
    def _claim_launch(path: Path, request_id: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise GateRejected("receipt has already been consumed for launch") from exc
        try:
            os.write(fd, (request_id + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def delegate_then_run(
        self,
        *,
        task: str,
        tests: dict,
        risk: str = "normal",
        launch: ArgvTemplate | None = None,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 900,
        require_agent_success: bool = True,
    ) -> ControllerResult:
        """完成強制委派；有 launch 時，gate 通過後才以 shell=False 啟動外部 agent。"""
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        if risk not in ("normal", "high"):
            raise ValueError("risk must be 'normal' or 'high'")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        try:
            verifier = compile_check(tests)
        except Exception as exc:
            raise ValueError(f"invalid check spec: {type(exc).__name__}: {exc}") from exc
        if launch is not None and not isinstance(launch, ArgvTemplate):
            raise ValueError("launch must be an ArgvTemplate")
        if launch is not None and tests.get("type") not in _STRONG_LAUNCH_CHECKS:
            raise ValueError(
                "launching an agent requires equals, json_schema, or run_python; "
                "contains/regex checks are advisory only")
        request_id = uuid.uuid4().hex
        run_dir = self.root / "runs" / request_id
        receipt_path = run_dir / "receipt.json"
        context_path = run_dir / "context.json"
        trust_card_path = run_dir / "trust_card.json"

        try:
            with file_lock(self.root / "controller.lock", timeout=30):
                if self.refresh_before_delegate:
                    try:
                        self.ecosystem = self.ecosystem.fresh()
                    except Exception as exc:
                        raise GateRejected(
                            f"root refresh failed: {type(exc).__name__}: {exc}") from exc
                if self.policy.require_trust_on and not self.ecosystem.trust_on:
                    raise GateRejected("trust is off; enable it before running a guarded agent")
                self._emit("DELEGATE_START", request_id=request_id)
                try:
                    result = self.ecosystem.delegate(
                        task,
                        tests,
                        risk=risk,
                        max_attempts=self.policy.max_attempts,
                        issue_receipt=True,
                        request_id=request_id,
                        output_mode="auto",
                    )
                except Exception as exc:
                    raise GateRejected(
                        f"delegation failed: {type(exc).__name__}: {exc}") from exc
                answer = result["answer"]
                receipt = result.get("receipt")
                card = result["trust_card"]
                verified = verify_delivery(
                    self.ecosystem,
                    result,
                    task=task,
                    tests=tests,
                    risk=risk,
                    request_id=request_id,
                    policy=self.policy,
                )

                public_context = {
                    "kind": "vacant.delegation.context",
                    "request_id": request_id,
                    "task_id": result["task_id"],
                    "task": task,
                    "verified_delivery": answer,
                    "receipt_path": str(receipt_path),
                    "trust_card_path": str(trust_card_path),
                    "note": "Hidden checks are intentionally omitted from agent context.",
                }
                atomic_write_text(
                    receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
                atomic_write_text(
                    trust_card_path, json.dumps(card, ensure_ascii=False, indent=2) + "\n")
                atomic_write_text(
                    context_path, json.dumps(public_context, ensure_ascii=False, indent=2) + "\n")
                self._emit(
                    "GATE_PASS",
                    request_id=request_id,
                    task_id=result["task_id"],
                    attempts=verified.attempts,
                )
                if launch is not None:
                    self._claim_launch(run_dir / "launch.claim", request_id)
        except OSError as exc:
            raise GateRejected(f"failed to persist gate evidence: {exc}") from exc

        base = ControllerResult(
            request_id=request_id,
            task_id=result["task_id"],
            answer=answer,
            receipt=receipt,
            trust_card=card,
            receipt_path=receipt_path,
            context_path=context_path,
        )
        if launch is None:
            return base

        rendered = launch.render(
            task=task,
            answer=answer,
            task_id=result["task_id"],
            receipt_path=str(receipt_path),
            context_path=str(context_path),
        )
        self._emit("AGENT_START", request_id=request_id, executable=rendered[0])
        child_env = dict(os.environ) if env is None else dict(env)
        child_env.pop("VACANT_API_KEY", None)
        child_env.pop("VACANT_MCP_API_KEY", None)
        try:
            completed = self._runner(
                rendered,
                cwd=(str(cwd) if cwd is not None else None),
                env=child_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            timed_out = ControllerResult(
                request_id=base.request_id,
                task_id=base.task_id,
                answer=base.answer,
                receipt=base.receipt,
                trust_card=base.trust_card,
                receipt_path=base.receipt_path,
                context_path=base.context_path,
                agent_argv=tuple(rendered),
                stdout=stdout,
                stderr=stderr,
                returncode=None,
                evidence_error="agent timed out after launch; workspace side effects are possible",
            )
            try:
                atomic_write_text(
                    run_dir / "agent_result.json",
                    json.dumps({
                        "returncode": None,
                        "timed_out": True,
                        "stdout": stdout,
                        "stderr": stderr,
                    }, ensure_ascii=False, indent=2) + "\n",
                )
                self._emit("AGENT_TIMEOUT", request_id=request_id)
            except OSError as evidence_exc:
                timed_out = ControllerResult(
                    **{**timed_out.__dict__,
                       "evidence_error": timed_out.evidence_error + f"; evidence error: {evidence_exc}"})
            raise AgentEvidenceError(timed_out, exc) from exc
        except Exception as exc:
            try:
                self._emit("AGENT_ERROR", request_id=request_id, error=type(exc).__name__)
            except OSError:
                pass
            raise AgentRunFailed(
                base, f"downstream agent did not complete: {type(exc).__name__}: {exc}") from exc

        final = ControllerResult(
            request_id=base.request_id,
            task_id=base.task_id,
            answer=base.answer,
            receipt=base.receipt,
            trust_card=base.trust_card,
            receipt_path=base.receipt_path,
            context_path=base.context_path,
            agent_argv=tuple(rendered),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            returncode=completed.returncode,
        )
        try:
            atomic_write_text(
                run_dir / "agent_result.json",
                json.dumps({
                    "returncode": final.returncode,
                    "stdout": final.stdout,
                    "stderr": final.stderr,
                }, ensure_ascii=False, indent=2) + "\n",
            )
            self._emit(
                "AGENT_DONE", request_id=request_id, returncode=completed.returncode)
        except OSError as exc:
            final = ControllerResult(
                **{**final.__dict__, "evidence_error": str(exc)})
            raise AgentEvidenceError(final, exc) from exc
        if require_agent_success and completed.returncode != 0:
            raise AgentRunFailed(final)
        return final


# =============================================================================
# Evidence Controller (DECISION_20261127_EVIDENCE_CONTROLLER.md — frozen)
# Pure deterministic decision module (stdlib only for decision & feedback),
# shared feedback generator for arms B and C, signed Logbook events & replay.
# =============================================================================

import re as _re  # noqa: E402
import sys as _sys  # noqa: E402

#: Frozen thresholds (DECISION_20261127_EVIDENCE_CONTROLLER.md — do not modify).
REPAIR_PASS_RATIO: float = 0.70
STUCK_CONSECUTIVE_SIGNATURE: int = 2
FEEDBACK_MAX_BYTES: int = 400

#: Controller actions (exact string identifiers).
ACTION_STOP_SUCCESS = "stop_success"
ACTION_DELIVER_BEST_BUDGET = "deliver_best_budget"
ACTION_RESTORE_BEST = "restore_best"
ACTION_RESTART_FRESH = "restart_fresh"
ACTION_REPAIR = "repair"
ACTION_CONTINUE = "continue"

CONTROLLER_ACTIONS: frozenset[str] = frozenset({
    ACTION_STOP_SUCCESS,
    ACTION_DELIVER_BEST_BUDGET,
    ACTION_RESTORE_BEST,
    ACTION_RESTART_FRESH,
    ACTION_REPAIR,
    ACTION_CONTINUE,
})

CONTROLLER_EVENT_TYPE = "CONTROLLER_DECISION"

#: Exact single-line action instructions appended by arm C (KS-1 clean).
ACTION_LINE_RESTORE_BEST = (
    "Action: workspace restored to the best prior snapshot; "
    "continue from this state and fix the remaining failing tests."
)
ACTION_LINE_RESTART_FRESH = (
    "Action: fresh workspace from the original files; "
    "the prior approach stalled on these failing tests."
)
ACTION_LINE_REPAIR = (
    "Action: workspace kept (most tests pass); "
    "repair only the remaining failing tests."
)
ACTION_LINE_CONTINUE = (
    "Action: workspace kept; "
    "continue from the current files to address the failing tests."
)

CONTROLLER_ACTION_LINES: dict[str, str] = {
    ACTION_RESTORE_BEST: ACTION_LINE_RESTORE_BEST,
    ACTION_RESTART_FRESH: ACTION_LINE_RESTART_FRESH,
    ACTION_REPAIR: ACTION_LINE_REPAIR,
    ACTION_CONTINUE: ACTION_LINE_CONTINUE,
}

#: KS-1 guard covering both vacant_network.memory.KS1_FORBIDDEN and ops/e1 KS1_BANNED_RE.
_CONTROLLER_KS1_BANNED_RE = _re.compile(
    r"你有責任|你會被懲罰|你將被懲罰|你要負責|後果自負|會被懲罰|負責任|"
    r"you are responsible|you will be punished|you will be held accountable|"
    r"responsib|punish|penal|blame|fault of",
    _re.I,
)


def _assert_ks1_static_strings() -> None:
    """Verify all controller static feedback/action strings are KS-1 clean."""
    static_strings = (
        "Failing tests: ",
        "Acceptance status: ",
        "First failure:",
        *CONTROLLER_ACTION_LINES.values(),
    )
    for text in static_strings:
        m = _CONTROLLER_KS1_BANNED_RE.search(text)
        if m:
            raise ValueError(f"KS-1 violation in controller string: {m.group(0)!r}")


_assert_ks1_static_strings()


@dataclass(frozen=True)
class Decision:
    """Output of one deterministic evidence-controller step."""

    action: str
    rule: int
    evidence: dict[str, Any]
    reason: str
    feedback_source: str = "none"  # "none" | "current" | "best"
    delivered_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "rule": self.rule,
            "evidence": self.evidence,
            "reason": self.reason,
            "feedback_source": self.feedback_source,
            "delivered_index": self.delivered_index,
        }


def compute_failure_signature(
    tests: Mapping[str, bool] | None = None,
    *,
    accepted: bool = False,
    status: str | None = None,
) -> list[str]:
    """Canonical sorted list of failing test names (or status sentinel when no tests ran)."""
    if tests:
        failing = sorted(str(k) for k, ok in tests.items() if not ok)
        if failing:
            return failing
    if not accepted:
        return [f"__status__:{status or 'error'}"]
    return []


def normalize_attempt(rec: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an attempt acceptance record into canonical stdlib primitives."""
    raw_tests = rec.get("tests")
    if raw_tests is None:
        raw_tests = rec.get("test_results")
    tests: dict[str, bool] = (
        {str(k): bool(v) for k, v in raw_tests.items()}
        if isinstance(raw_tests, Mapping)
        else {}
    )
    raw_total = rec.get("total")
    if raw_total is None:
        raw_total = rec.get("run")
    total = int(raw_total) if raw_total is not None else len(tests)

    raw_passed = rec.get("passed")
    if raw_passed is not None:
        passed = int(raw_passed)
    else:
        passed = sum(1 for v in tests.values() if v)

    raw_acc = rec.get("accepted")
    if raw_acc is None:
        raw_acc = rec.get("accept")
    status = str(rec["status"]) if rec.get("status") is not None else None
    if raw_acc is not None:
        accepted = bool(raw_acc)
    else:
        accepted = bool(total > 0 and passed == total and all(tests.values()))

    raw_sig = rec.get("failure_signature")
    if raw_sig is None and rec.get("failing_tests") is not None:
        raw_sig = rec.get("failing_tests")
    if raw_sig is not None:
        sig = sorted({str(x) for x in raw_sig if str(x)})
        if not sig and not accepted:
            sig = compute_failure_signature(tests, accepted=False, status=status)
    else:
        sig = compute_failure_signature(tests, accepted=accepted, status=status)

    first_problem = rec.get("first_problem")
    return {
        "tests": tests,
        "passed": passed,
        "total": total,
        "accepted": accepted,
        "status": status,
        "failure_signature": sig,
        "first_problem": str(first_problem) if first_problem is not None else None,
    }


def select_best_index(attempts: Sequence[Mapping[str, Any]]) -> int:
    """Choose best attempt index: first accepted, else highest passed count (ties -> latest)."""
    if not attempts:
        raise ValueError("attempts must be non-empty")
    normed = [normalize_attempt(a) for a in attempts]
    for i, a in enumerate(normed):
        if a["accepted"]:
            return i
    return max(range(len(normed)), key=lambda i: (normed[i]["passed"], i))


def decide(
    current: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    best: Mapping[str, Any] | None = None,
    *,
    remaining_attempts: int,
    remaining_budget_s: float,
    min_attempt_s: float = 0.0,
) -> Decision:
    """Pure, deterministic evidence-controller rule evaluator (rules 1..6 in frozen order).

    Rule order (first match wins):
      1. All acceptance tests pass -> stop_success
      2. Budget exhausted (attempts or wall time) -> deliver_best_budget
      3. Current worse than known best (passed < best.passed) -> restore_best
      4. No progress: identical failure signature 2 consecutive times with no
         increase in passed count -> restart_fresh
      5. Mostly passing (passed >= 70% of total, total > 0) -> repair
      6. Otherwise -> continue
    """
    cur = normalize_attempt(current)
    hist = [normalize_attempt(h) for h in history]
    all_attempts = [*hist, cur]

    prior_best: dict[str, Any] | None
    if best is not None:
        prior_best = normalize_attempt(best)
    elif hist:
        prior_best = hist[select_best_index(hist)]
    else:
        prior_best = None

    overall_best_idx = select_best_index(all_attempts)
    overall_best = all_attempts[overall_best_idx]

    cur_sig = cur["failure_signature"]
    cur_passed = cur["passed"]
    cur_total = cur["total"]
    cur_accepted = cur["accepted"]

    prev = hist[-1] if hist else None
    consecutive_same_sig = 0
    if cur_sig:
        consecutive_same_sig = 1
        for prev_item in reversed(hist):
            if prev_item["failure_signature"] == cur_sig:
                consecutive_same_sig += 1
            else:
                break

    worse_than_best = prior_best is not None and cur_passed < prior_best["passed"]
    no_progress_stuck = (
        prev is not None
        and bool(cur_sig)
        and prev["failure_signature"] == cur_sig
        and cur_passed <= prev["passed"]
        and consecutive_same_sig >= STUCK_CONSECUTIVE_SIGNATURE
    )
    mostly_passing = cur_total > 0 and (cur_passed * 10 >= cur_total * 7)
    pass_ratio = (cur_passed / cur_total) if cur_total > 0 else 0.0

    rem_attempts = int(remaining_attempts)
    rem_budget_s = float(remaining_budget_s)
    min_att_s = float(min_attempt_s)
    budget_exhausted = rem_attempts <= 0 or rem_budget_s <= 0.0 or rem_budget_s < min_att_s

    evidence: dict[str, Any] = {
        "tests": dict(cur["tests"]),
        "failure_signature": list(cur_sig),
        "passed": cur_passed,
        "total": cur_total,
        "accepted": cur_accepted,
        "status": cur["status"],
        "pass_ratio": round(pass_ratio, 6),
        "prior_best_passed": prior_best["passed"] if prior_best is not None else None,
        "prior_best_total": prior_best["total"] if prior_best is not None else None,
        "worse_than_best": worse_than_best,
        "consecutive_same_signature": consecutive_same_sig,
        "no_progress_stuck": no_progress_stuck,
        "mostly_passing": mostly_passing,
        "remaining_attempts": rem_attempts,
        "remaining_budget_s": round(rem_budget_s, 3),
        "min_attempt_s": round(min_att_s, 3),
        "history_len": len(hist),
    }

    # Rule 1: All acceptance tests pass -> stop early and deliver current version.
    if cur_accepted:
        evidence["delivered_attempt"] = len(hist) + 1
        evidence["delivered_passed"] = cur_passed
        evidence["unsatisfied"] = []
        return Decision(
            action=ACTION_STOP_SUCCESS,
            rule=1,
            evidence=evidence,
            reason=f"all acceptance tests passed ({cur_passed}/{cur_total})",
            feedback_source="none",
            delivered_index=len(hist),
        )

    # Rule 2: Budget exhausted -> deliver best version and list unsatisfied items.
    if budget_exhausted:
        evidence["delivered_attempt"] = overall_best_idx + 1
        evidence["delivered_passed"] = overall_best["passed"]
        evidence["unsatisfied"] = list(overall_best["failure_signature"])
        return Decision(
            action=ACTION_DELIVER_BEST_BUDGET,
            rule=2,
            evidence=evidence,
            reason=(
                f"budget exhausted (remaining_attempts={rem_attempts}, "
                f"remaining_budget_s={round(rem_budget_s, 1)}); "
                f"delivering attempt {overall_best_idx + 1} "
                f"({overall_best['passed']}/{overall_best['total']})"
            ),
            feedback_source="none",
            delivered_index=overall_best_idx,
        )

    # Rule 3: Worse than known best -> restore best snapshot, feedback from best.
    if worse_than_best:
        assert prior_best is not None
        return Decision(
            action=ACTION_RESTORE_BEST,
            rule=3,
            evidence=evidence,
            reason=(
                f"regression below best ({cur_passed} < {prior_best['passed']}); "
                f"restoring best snapshot"
            ),
            feedback_source="best",
            delivered_index=None,
        )

    # Rule 4: Stuck (same failure signature 2 consecutive times, no increase) -> restart fresh.
    if no_progress_stuck:
        return Decision(
            action=ACTION_RESTART_FRESH,
            rule=4,
            evidence=evidence,
            reason=(
                f"no progress: identical failure signature {consecutive_same_sig} "
                f"consecutive times with passed={cur_passed}"
            ),
            feedback_source="current",
            delivered_index=None,
        )

    # Rule 5: Mostly passing (>= 70%) -> keep workspace and repair failing items.
    if mostly_passing:
        return Decision(
            action=ACTION_REPAIR,
            rule=5,
            evidence=evidence,
            reason=f"mostly passing ({cur_passed}/{cur_total} = {pass_ratio:.1%} >= 70%)",
            feedback_source="current",
            delivered_index=None,
        )

    # Rule 6: Otherwise -> keep workspace and continue.
    return Decision(
        action=ACTION_CONTINUE,
        rule=6,
        evidence=evidence,
        reason=f"continuing from current workspace ({cur_passed}/{cur_total})",
        feedback_source="current",
        delivered_index=None,
    )


def _truncate_utf8(text: str, max_bytes: int) -> str:
    """Truncate text so its UTF-8 encoding is at most max_bytes without splitting code points."""
    if max_bytes <= 0:
        return ""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    return raw[:max_bytes].decode("utf-8", errors="ignore")


def _fit_first_problem(problem: str, max_bytes: int) -> str:
    """Fit first failure message within max_bytes, preserving assertion/error lines when truncated."""
    cleaned = problem.strip()
    if not cleaned or max_bytes <= 0:
        return ""
    if len(cleaned.encode("utf-8")) <= max_bytes:
        return cleaned
    lines = [ln.rstrip() for ln in cleaned.splitlines() if ln.strip()]
    if not lines:
        return ""
    # Prefer keeping the final error/assertion line (often at the end of a unittest traceback).
    exc_line = ""
    for ln in reversed(lines):
        tok = ln.strip().split(":", 1)[0]
        if tok and " " not in tok and tok.endswith(("Error", "Exception", "Failure")):
            exc_line = ln.strip()
            break
    if exc_line and len(exc_line.encode("utf-8")) <= max_bytes:
        head = lines[0].strip()
        if head != exc_line:
            combo = f"{head}\n{exc_line}"
            if len(combo.encode("utf-8")) <= max_bytes:
                return combo
        return exc_line
    # Otherwise keep the tail (where unittest prints the assertion diff/error).
    raw = cleaned.encode("utf-8")
    tail = raw[-max_bytes:].decode("utf-8", errors="ignore")
    return tail


def build_feedback(
    failing_tests: Sequence[str],
    first_problem: str | None = None,
    *,
    status: str | None = None,
    max_bytes: int = FEEDBACK_MAX_BYTES,
) -> str:
    """Shared feedback generator used by BOTH arm B and arm C.

    Includes failing test names and the first failure message, strictly <= max_bytes (400B)
    in UTF-8. Pure stdlib, KS-1 clean.
    """
    names = sorted({
        str(t).strip()
        for t in failing_tests
        if str(t).strip() and not str(t).startswith("__status__:")
    })
    prob = (first_problem or "").strip()

    if names:
        prefix = "Failing tests: "
        # Reserve room for first failure message when present.
        name_budget = min(180, max_bytes // 2) if prob else max_bytes
        name_budget = max(name_budget, min(max_bytes, len(prefix) + 24))
        kept: list[str] = []
        for idx, name in enumerate(names):
            rem = len(names) - (idx + 1)
            suffix = f" (+{rem} more)" if rem > 0 else ""
            cand = prefix + ", ".join([*kept, name]) + suffix
            if len(cand.encode("utf-8")) <= name_budget:
                kept.append(name)
            else:
                break
        if kept:
            rem = len(names) - len(kept)
            header = prefix + ", ".join(kept) + (f" (+{rem} more)" if rem > 0 else "")
        else:
            header = _truncate_utf8(prefix + names[0], name_budget)
    else:
        header = _truncate_utf8(f"Acceptance status: {status or 'failed'}", max_bytes)

    if not prob:
        return _truncate_utf8(header, max_bytes)

    sep = "\nFirst failure:\n"
    rem_bytes = max_bytes - len(header.encode("utf-8")) - len(sep.encode("utf-8"))
    if rem_bytes <= 8:
        return _truncate_utf8(header, max_bytes)

    fitted = _fit_first_problem(prob, rem_bytes)
    out = f"{header}{sep}{fitted}" if fitted else header
    return _truncate_utf8(out, max_bytes)


def build_controller_feedback(
    action: str,
    failing_tests: Sequence[str],
    first_problem: str | None = None,
    *,
    status: str | None = None,
    max_bytes: int = FEEDBACK_MAX_BYTES,
) -> str:
    """Arm C feedback: shared base feedback (<=400B) plus one exact KS-1-clean action line."""
    if action not in CONTROLLER_ACTION_LINES:
        raise ValueError(f"no feedback action line for action {action!r}")
    base = build_feedback(
        failing_tests, first_problem, status=status, max_bytes=max_bytes
    )
    return f"{base}\n{CONTROLLER_ACTION_LINES[action]}"


def controller_event(
    logbook: Any,
    identity: Any,
    *,
    attempt: int,
    decision: Decision,
    ts_ms: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Any:
    """Append a signed CONTROLLER_DECISION event to a vacant_network.logbook.Logbook."""
    from . import crypto

    ts = int(ts_ms) if ts_ms is not None else (time.time_ns() // 1_000_000)
    payload: dict[str, Any] = {
        "attempt": int(attempt),
        "action": decision.action,
        "rule": int(decision.rule),
        "reason": decision.reason,
        "feedback_source": decision.feedback_source,
        "delivered_index": decision.delivered_index,
        "evidence": decision.evidence,
        "signer": {
            "vacant_id": identity.vacant_id,
            "pub_hex": crypto.pub_to_hex(identity.pub),
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return logbook.append(CONTROLLER_EVENT_TYPE, payload, identity, ts_ms=ts)


def save_controller_chain(logbook: Any, identity: Any, chain_path: str | Path) -> Path:
    """Atomically persist a controller Logbook chain and its sidecar public key JSON."""
    from . import crypto

    path = Path(chain_path)
    logbook.save(path)
    pub_path = path.with_suffix(".pub.json")
    pub_doc = {
        "vacant_id": identity.vacant_id,
        "pub_hex": crypto.pub_to_hex(identity.pub),
    }
    atomic_write_text(pub_path, json.dumps(pub_doc, ensure_ascii=False, indent=2) + "\n")
    return path


def reconstruct(
    chain_path: str | Path,
    *,
    pub: Any = None,
    stream: Any = None,
    emit: bool = True,
) -> list[dict[str, Any]]:
    """Verify a signed controller chain and print/return its reconstructed decision history.

    Raises vacant_network.logbook.ChainError if the chain is missing, empty, or fails
    cryptographic hash-chain / signature verification.
    """
    from .identity import PublicIdentity
    from .logbook import ChainError, Logbook

    path = Path(chain_path)
    if not path.is_file():
        raise ChainError(f"controller chain not found: {path}")
    try:
        book = Logbook.load(path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ChainError(f"failed to load controller chain {path}: {exc}") from exc
    if not book.entries:
        raise ChainError(f"controller chain is empty: {path}")

    who = pub
    if who is None:
        pub_path = path.with_suffix(".pub.json")
        if pub_path.is_file():
            try:
                pub_doc = json.loads(pub_path.read_text(encoding="utf-8"))
                who = PublicIdentity.from_hex(pub_doc["vacant_id"], pub_doc["pub_hex"])
            except Exception as exc:
                raise ChainError(f"invalid sidecar public key {pub_path}: {exc}") from exc
        else:
            genesis_signer = (
                book.entries[0].payload.get("signer")
                if isinstance(book.entries[0].payload, dict)
                else None
            )
            if not isinstance(genesis_signer, dict) or "vacant_id" not in genesis_signer or "pub_hex" not in genesis_signer:
                raise ChainError("no PublicIdentity provided and no signer metadata in chain")
            who = PublicIdentity.from_hex(genesis_signer["vacant_id"], genesis_signer["pub_hex"])

    if not book.verify_chain(who):
        raise ChainError(f"controller chain verification failed (tampered or bad signature): {path}")

    history: list[dict[str, Any]] = []
    out_stream = stream if stream is not None else _sys.stdout
    for entry in book.entries:
        if entry.type != CONTROLLER_EVENT_TYPE or not isinstance(entry.payload, dict):
            continue
        p = entry.payload
        ev = p.get("evidence") or {}
        rec = {
            "seq": entry.seq,
            "ts_ms": entry.ts_ms,
            "attempt": p.get("attempt"),
            "rule": p.get("rule"),
            "action": p.get("action"),
            "reason": p.get("reason"),
            "feedback_source": p.get("feedback_source"),
            "delivered_index": p.get("delivered_index"),
            "evidence": ev,
            "extra": p.get("extra"),
        }
        history.append(rec)
        if emit:
            passed = ev.get("passed")
            total = ev.get("total")
            sig = ev.get("failure_signature") or []
            rem_b = ev.get("remaining_budget_s")
            print(
                f"seq={entry.seq} attempt={rec['attempt']} rule={rec['rule']} "
                f"action={rec['action']} passed={passed}/{total} "
                f"sig={sig} rem_budget={rem_b}s — {rec['reason']}",
                file=out_stream,
            )
    return history
