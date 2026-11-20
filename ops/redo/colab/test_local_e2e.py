#!/usr/bin/env python3
"""Local offline end-to-end test for ops/redo/colab/ scaffolding (stdlib only).

Proves without touching Google Colab or any external network:
1. Dry-run mode for every script (render_models.py, vm_setup.sh, vm_run_batch.sh,
   launch_batch.sh, poll_batch.sh, fetch_batch.sh) prints the expected commands and
   NEVER invokes `colab` (enforced by a failing trap `colab` binary on PATH).
2. A tiny stdlib http.server OpenAI-compatible fake endpoint works with the rendered
   models.json and real `pi -p` (gets a reply, sends `reasoning_effort: "none"`).
3. VM-side `vm_run_batch.sh` + `vm_setup.sh` runs a 1-pair `redo.py` smoke plan
   (arms A and R3) end-to-end against the fake endpoint with real `pi`, archives
   results to results.tar.gz + .sha256, and the tarball verifies & extracts cleanly.

Usage:
    python3 ops/redo/colab/test_local_e2e.py
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
REDO_PY = REPO_ROOT / "ops" / "redo" / "redo.py"


class FakeOpenAIState:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.lock = threading.Lock()
        self.requests: list[dict[str, Any]] = []
        self.models_hits = 0


def make_handler(state: FakeOpenAIState):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:
            if self.path.rstrip("/") in ("/v1/models", "/models"):
                with state.lock:
                    state.models_hits += 1
                payload = {
                    "object": "list",
                    "data": [{"id": state.model_id, "object": "model", "owned_by": "fake-vllm"}],
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.rstrip("/") == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            if not self.path.endswith("/chat/completions"):
                self.send_response(404)
                self.end_headers()
                return
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            with state.lock:
                state.requests.append(req)

            tools = req.get("tools") or []
            messages = req.get("messages") or []
            saw_tool_result = any(m.get("role") == "tool" for m in messages)
            stream = bool(req.get("stream"))
            model = req.get("model") or state.model_id

            # Decide reply:
            # - No tools -> simple text probe reply for `pi -p` smoke check.
            # - Tools present and first turn -> emit a tool call that writes sol.py.
            # - Tools present and after tool result -> finish with text reply.
            tool_call = None
            text_reply = "FAKE_SERVER_REPLY_OK"
            if tools and not saw_tool_result:
                tool_call = self._build_write_tool_call(tools)
            elif tools and saw_tool_result:
                text_reply = "Implemented f(x) = x + 1 in sol.py."

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                if tool_call is not None:
                    chunks = [
                        {
                            "id": "chatcmpl-fake-1",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [
                                            {
                                                "index": 0,
                                                "id": "call_fake_1",
                                                "type": "function",
                                                "function": {
                                                    "name": tool_call["name"],
                                                    "arguments": json.dumps(tool_call["arguments"]),
                                                },
                                            }
                                        ],
                                    },
                                    "finish_reason": None,
                                }
                            ],
                        },
                        {
                            "id": "chatcmpl-fake-1",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
                        },
                    ]
                else:
                    chunks = [
                        {
                            "id": "chatcmpl-fake-2",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": text_reply},
                                    "finish_reason": None,
                                }
                            ],
                        },
                        {
                            "id": "chatcmpl-fake-2",
                            "object": "chat.completion.chunk",
                            "created": 1,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                            "usage": {"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 48},
                        },
                    ]
                for c in chunks:
                    self.wfile.write(("data: " + json.dumps(c) + "\n\n").encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                msg: dict[str, Any] = {"role": "assistant", "content": text_reply}
                finish = "stop"
                if tool_call is not None:
                    msg = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_fake_1",
                                "type": "function",
                                "function": {
                                    "name": tool_call["name"],
                                    "arguments": json.dumps(tool_call["arguments"]),
                                },
                            }
                        ],
                    }
                    finish = "tool_calls"
                resp = {
                    "id": "chatcmpl-fake",
                    "object": "chat.completion",
                    "created": 1,
                    "model": model,
                    "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52},
                }
                body = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        @staticmethod
        def _build_write_tool_call(tools: list[dict[str, Any]]) -> dict[str, Any]:
            by_name = {t["function"]["name"]: t["function"] for t in tools if isinstance(t.get("function"), dict)}
            if "write" in by_name:
                props = by_name["write"].get("parameters", {}).get("properties", {})
                path_key = "path" if "path" in props else next(iter(props), "path")
                return {
                    "name": "write",
                    "arguments": {path_key: "sol.py", "content": "def f(x):\n    return x + 1\n"},
                }
            if "bash" in by_name:
                return {
                    "name": "bash",
                    "arguments": {"command": "printf 'def f(x):\\n    return x + 1\\n' > sol.py"},
                }
            first = next(iter(by_name))
            return {"name": first, "arguments": {}}

    return Handler


def run_cmd(argv: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, env=env, timeout=timeout)


def main() -> int:
    checks: list[tuple[bool, str]] = []

    def chk(cond: bool, msg: str) -> None:
        checks.append((bool(cond), msg))
        print(("OK    " if cond else "FAIL  ") + msg)

    pi_bin = shutil.which("pi")
    chk(pi_bin is not None, f"local `pi` binary available ({pi_bin})")
    if pi_bin is None:
        print("VERDICT: COLAB_LOCAL_E2E_FAIL")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="redo-colab-e2e-"))
    srv: http.server.ThreadingHTTPServer | None = None
    try:
        # 0) Create a trap `colab` binary on PATH to prove dry-run NEVER executes colab.
        trap_bin = tmp / "trap_bin"
        trap_bin.mkdir()
        trap_colab = trap_bin / "colab"
        trap_colab.write_text("#!/usr/bin/env bash\necho 'TRAP: colab must never be executed!' >&2\nexit 99\n", encoding="utf-8")
        os.chmod(trap_colab, stat.S_IRWXU)
        trap_env = {**os.environ, "PATH": f"{trap_bin}:{os.environ.get('PATH', '')}"}

        # 1) Create tiny 1-task bank + bank tarball.
        bank = tmp / "bank"
        tdir = bank / "toy_inc"
        (tdir / "workspace").mkdir(parents=True)
        (tdir / "workspace" / "goal.md").write_text("Write sol.py implementing f(x) = x + 1.\n", encoding="utf-8")
        (tdir / "workspace" / "contract.md").write_text("sol_test.py must pass.\n", encoding="utf-8")
        (tdir / "workspace" / "sol.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
        (tdir / "workspace" / "sol_test.py").write_text(
            "import unittest\nfrom sol import f\n\nclass T(unittest.TestCase):\n"
            "    def test_one(self):\n        self.assertEqual(f(1), 2)\n"
            "    def test_two(self):\n        self.assertEqual(f(41), 42)\n",
            encoding="utf-8",
        )
        bank_tar = tmp / "bank.tar.gz"
        with tarfile.open(bank_tar, "w:gz") as tf:
            for child in sorted(bank.iterdir()):
                tf.add(child, arcname=child.name)

        # 2) Start local fake OpenAI-compatible server on an ephemeral 127.0.0.1 port.
        model_id = "fake-gemma-4-12b"
        state = FakeOpenAIState(model_id)
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()

        # 3) Write vLLM config pointing at the fake server port (contextWindow = 32768).
        vllm_cfg_path = tmp / "vllm_cfg.json"
        vllm_cfg = {
            "vllm_version": "0.30.0",
            "node_version": "v22.23.2",
            "pi_version": "0.87.1",
            "model_family": "gemma4",
            "model_id": "google/gemma-4-12B-it-qat-w4a16-ct",
            "served_model_name": model_id,
            "provider_name": "colab-vllm-nothink",
            "reasoning": "off",
            "host": "127.0.0.1",
            "port": port,
            "max_model_len": 32768,
            "max_tokens": 4096,
            "max_num_seqs": 4,
            "gpu_memory_utilization": 0.90,
            "enable_prefix_caching": True,
            "enable_prompt_tokens_details": True,
            "async_scheduling": True,
            "flashinfer_sampler": 0,
            "tool_call_parser": "gemma4",
            "reasoning_parser": "gemma4",
            "chat_template_url": "https://raw.githubusercontent.com/vllm-project/vllm/v0.30.0/examples/tool_chat_template_gemma4.jinja",
            "limit_mm_per_prompt": "{\"image\": 0, \"audio\": 0}",
            "ready_timeout_s": 30,
        }
        vllm_cfg_path.write_text(json.dumps(vllm_cfg, indent=2) + "\n", encoding="utf-8")

        # 4) Write 1-pair smoke plan using real `pi` + rendered models.json dir.
        pi_dir = tmp / "pi_agent"
        plan_path = tmp / "smoke_plan.json"
        plan = {
            "schema": "vacant.redo.plan/1",
            "id": "colab_local_e2e_smoke",
            "seed": 42,
            "tasks": ["toy_inc"],
            "reps": 1,
            "arms": {
                "A": {"policy": "single", "attempt_timeout_s": 60},
                "R3": {"policy": "restart", "max_attempts": 3, "attempt_timeout_s": 30, "budget_s": 60, "hint": "none"},
            },
            "pair": ["A", "R3"],
            "attempt_timeout_s": 60,
            "backoff_scale": 0.0,
            "agent": {
                "argv": [
                    "pi", "-p", "--mode", "json", "--offline",
                    "--session-dir", "{logs}/sessions",
                    "--provider", "{provider}", "--model", "{model}",
                    "{prompt}",
                ],
                "env": {"PI_SKIP_VERSION_CHECK": "1", "PI_OFFLINE": "1"},
                "config_dir": {"env": "PI_CODING_AGENT_DIR", "from": str(pi_dir), "copy": ["models.json"]},
                "log_drop_re": "\"type\":\"message_update\"",
                "usage": "pi_json",
            },
            "providers": [
                {
                    "name": "fake-colab-vllm",
                    "provider": "colab-vllm-nothink",
                    "model": model_id,
                    "health_url": f"http://127.0.0.1:{port}/v1/models",
                    "health_contains": model_id,
                    "jobs": 1,
                }
            ],
            "acceptance": {"kind": "workspace_tests", "patterns": ["*_test.py"], "timeout_s": 30},
            "grader": {"timeout_s": 30, "visible_equals_grader": True},
            "analysis": {"alpha": 0.05},
        }
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

        # 5) Dry-run checks for EVERY script (with trap `colab` on PATH).
        r = run_cmd([sys.executable, str(HERE / "render_models.py"), "--config", str(vllm_cfg_path), "--dry-run"], env=trap_env)
        chk(r.returncode == 0 and f"http://127.0.0.1:{port}/v1" in r.stdout and '"contextWindow": 32768' in r.stdout,
            "dry-run: render_models.py outputs valid models.json with contextWindow=max_model_len")

        r = run_cmd(["bash", str(HERE / "vm_setup.sh"), "--config", str(vllm_cfg_path), "--dry-run"], env=trap_env)
        chk(
            r.returncode == 0
            and "VLLM_USE_FLASHINFER_SAMPLER=0" in r.stdout
            and "--enable-prompt-tokens-details" in r.stdout
            and "--host 127.0.0.1" in r.stdout
            and "vllm==0.30.0" in r.stdout,
            "dry-run: vm_setup.sh prints pinned vLLM, FlashInfer=0, prompt-tokens-details, 127.0.0.1",
        )

        r = run_cmd(["bash", str(HERE / "vm_setup.sh"), "--config", str(HERE / "vllm_qwen3_27b.json"), "--dry-run"], env=trap_env)
        chk(
            r.returncode == 0
            and "--tool-call-parser hermes" in r.stdout
            and "--reasoning-parser qwen3" in r.stdout,
            "dry-run: vm_setup.sh with vllm_qwen3_27b.json selects Qwen tool-call & reasoning parsers",
        )

        r = run_cmd([
            "bash", str(HERE / "launch_batch.sh"), str(plan_path), str(bank),
            "--gpu", "G4", "--vllm-config", str(vllm_cfg_path), "--dry-run",
        ], env=trap_env)
        chk(r.returncode == 2, "launch_batch.sh refuses uncommitted plan unless --allow-uncommitted-plan is passed")

        r = run_cmd(["bash", str(HERE / "vm_run_batch.sh"), "--plan", str(plan_path),
                     "--vllm-config", str(vllm_cfg_path), "--dry-run"], env=trap_env)
        chk(r.returncode == 0 and "redo.py run" in r.stdout and "BATCH_DONE.json" in r.stdout,
            "dry-run: vm_run_batch.sh prints setup, redo.py run, and tarball steps")

        for tr in ("ssh", "exec"):
            r = run_cmd([
                "bash", str(HERE / "launch_batch.sh"), str(plan_path), str(bank),
                "--gpu", "G4", "--vllm-config", str(vllm_cfg_path),
                "--out-dir", str(tmp / f"out_{tr}"), "--transport", tr,
                "--allow-uncommitted-plan", "--dry-run",
            ], env=trap_env)
            chk(
                r.returncode == 0
                and "colab new -s" in r.stdout
                and "--gpu G4" in r.stdout
                and "colab upload -s" in r.stdout
                and (f"colab {tr} -s" in r.stdout or f"colab {tr}" in r.stdout)
                and "colab pay" not in r.stdout,
                f"dry-run: launch_batch.sh (--transport {tr}) prints colab new/upload/{tr}, never runs colab",
            )

        # Create dummy state.json for poll_batch.sh & fetch_batch.sh dry-runs.
        dummy_state = tmp / "state.json"
        dummy_state.write_text(json.dumps({
            "session": "redo-drytest",
            "batch_name": "drytest",
            "gpu": "G4",
            "plan_id": "colab_local_e2e_smoke",
            "local_out_dir": str(tmp / "out_ssh"),
            "remote_work_dir": "/srv/redo",
            "remote_run_root": "/srv/redo/run",
            "remote_results_tar": "/content/redo_results_drytest.tar.gz",
            "transport": "ssh",
            "colab_bin": "colab",
        }, indent=2), encoding="utf-8")

        r = run_cmd(["bash", str(HERE / "poll_batch.sh"), str(dummy_state), "--live-status", "--dry-run"], env=trap_env)
        chk(
            r.returncode == 0
            and "colab download -s redo-drytest /srv/redo/run/STATUS.txt" in r.stdout
            and "colab download -s redo-drytest /srv/redo/run/runner.log" in r.stdout
            and "redo.py status" in r.stdout,
            "dry-run: poll_batch.sh prints colab download + live status commands, never runs colab",
        )

        r = run_cmd(["bash", str(HERE / "fetch_batch.sh"), str(dummy_state), "--dry-run"], env=trap_env)
        chk(
            r.returncode == 0
            and "colab download -s redo-drytest /content/redo_results_drytest.tar.gz" in r.stdout
            and "colab stop -s redo-drytest" in r.stdout
            and "colab pay" not in r.stdout,
            "dry-run: fetch_batch.sh prints colab download + verify + colab stop, never runs colab",
        )

        # 6) Run vm_setup.sh against the fake server (--skip-install --skip-vllm).
        work_dir = tmp / "vm_work"
        ready_file = work_dir / "VM_READY.json"
        r = run_cmd([
            "bash", str(HERE / "vm_setup.sh"),
            "--config", str(vllm_cfg_path),
            "--work-dir", str(work_dir),
            "--pi-dir", str(pi_dir),
            "--ready-file", str(ready_file),
            "--skip-install", "--skip-vllm",
        ], env=trap_env)
        chk(r.returncode == 0 and ready_file.is_file(), f"vm_setup.sh waited for /v1/models and wrote VM_READY.json (rc={r.returncode})")
        models_json = pi_dir / "models.json"
        chk(models_json.is_file() and (os.stat(models_json).st_mode & 0o777) == 0o600,
            "vm_setup.sh rendered models.json with mode 0600")
        mj = json.loads(models_json.read_text(encoding="utf-8"))
        chk(
            mj["providers"]["colab-vllm-nothink"]["baseUrl"] == f"http://127.0.0.1:{port}/v1"
            and mj["providers"]["colab-vllm-nothink"]["models"][0]["contextWindow"] == 32768
            and mj["providers"]["colab-vllm-nothink"]["models"][0]["samplingParams"]["reasoning_effort"] == "none",
            "models.json has exact baseUrl, contextWindow=32768, reasoning_effort=none",
        )

        # 7) Prove rendered models.json works with real `pi -p` against fake server.
        pi_env = {**trap_env, "PI_CODING_AGENT_DIR": str(pi_dir), "PI_SKIP_VERSION_CHECK": "1", "PI_OFFLINE": "1"}
        r = run_cmd([
            "pi", "-p", "--mode", "json", "--no-session", "--no-tools", "--offline",
            "--provider", "colab-vllm-nothink", "--model", model_id,
            "Reply with OK",
        ], env=pi_env, timeout=60)
        chk(
            r.returncode == 0 and "FAKE_SERVER_REPLY_OK" in r.stdout,
            f"pi -p got reply from local fake OpenAI server via models.json (rc={r.returncode})",
        )
        with state.lock:
            probe_req = state.requests[-1] if state.requests else {}
        chk(probe_req.get("reasoning_effort") == "none",
            f"fake server received reasoning_effort='none' from pi (got {probe_req.get('reasoning_effort')!r})")

        # 8) Run vm_run_batch.sh end-to-end (unpack bank tar -> vm_setup -> redo.py 1 pair -> tar results).
        run_root = work_dir / "run"
        tar_out = work_dir / "results.tar.gz"
        r = run_cmd([
            "bash", str(HERE / "vm_run_batch.sh"),
            "--repo-dir", str(REPO_ROOT),
            "--bank-tar", str(bank_tar),
            "--plan", str(plan_path),
            "--vllm-config", str(vllm_cfg_path),
            "--work-dir", str(work_dir),
            "--pi-dir", str(pi_dir),
            "--root", str(run_root),
            "--tar-out", str(tar_out),
            "--status-interval", "2",
            "--skip-install", "--skip-vllm",
        ], env=trap_env, timeout=180)
        if r.returncode != 0:
            print("vm_run_batch stderr:", r.stderr[-1500:], file=sys.stderr)
            print("vm_run_batch stdout:", r.stdout[-1500:], file=sys.stderr)
        chk(r.returncode == 0, f"vm_run_batch.sh completed 1-pair redo.py smoke plan (rc={r.returncode})")

        report_p = run_root / "REPORT.json"
        done_p = run_root / "BATCH_DONE.json"
        status_p = run_root / "STATUS.txt"
        chk(report_p.is_file() and done_p.is_file() and status_p.is_file(),
            "run root contains REPORT.json, BATCH_DONE.json, and STATUS.txt")
        if report_p.is_file():
            rep = json.loads(report_p.read_text(encoding="utf-8"))
            chk(
                rep["pairs_complete"] == 1
                and rep["pairs_scored"] == 1
                and len(rep["pairs_infra_void"]) == 0
                and rep["per_arm"]["A"]["pass"] == 1
                and rep["per_arm"]["R3"]["pass"] == 1
                and (rep["per_arm"]["A"]["mean_model_calls"] or 0) >= 2
                and (rep["per_arm"]["R3"]["mean_model_calls"] or 0) >= 2,
                f"REPORT.json: 1/1 pair complete, A=1/1, R3=1/1, 0 infra_void, calls>=2 "
                f"(A_calls={rep['per_arm']['A']['mean_model_calls']}, R3_calls={rep['per_arm']['R3']['mean_model_calls']})",
            )

        # 9) Verify results tarball SHA-256 and extract cleanly.
        sha_file = pathlib.Path(str(tar_out) + ".sha256")
        chk(tar_out.is_file() and sha_file.is_file(), "results.tar.gz and results.tar.gz.sha256 created")
        got_sha = hashlib.sha256(tar_out.read_bytes()).hexdigest()
        want_sha = sha_file.read_text(encoding="utf-8").split()[0]
        done_doc = json.loads(done_p.read_text(encoding="utf-8"))
        chk(got_sha == want_sha == done_doc["tarball_sha256"],
            "results.tar.gz SHA-256 matches .sha256 and BATCH_DONE.json")

        extracted = tmp / "extracted_run"
        extracted.mkdir()
        with tarfile.open(tar_out, "r:gz") as tf:
            names = tf.getnames()
            tf.extractall(extracted)
        chk(
            any(n.endswith("RUN.json") for n in names)
            and any(n.endswith("REPORT.json") for n in names)
            and any(n.endswith("VM_READY.json") for n in names)
            and any(n.endswith("runner.log") for n in names),
            "tarball contains RUN.json, REPORT.json, VM_READY.json, and runner.log",
        )
        r = run_cmd([sys.executable, str(REDO_PY), "status", "--root", str(extracted)], env=trap_env)
        chk(r.returncode == 0 and "1/1" in r.stdout,
            f"redo.py status works on extracted tarball ({r.stdout.strip()})")
    finally:
        if srv is not None:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [m for ok, m in checks if not ok]
    print(f"\nVERDICT: {'COLAB_LOCAL_E2E_OK' if not failed else 'COLAB_LOCAL_E2E_FAIL'} ({len(checks) - len(failed)}/{len(checks)})")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
