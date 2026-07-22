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
import string
import subprocess
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
        runner: Runner = subprocess.run,
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
        runner: Runner = subprocess.run,
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
            f.write(json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n")
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
