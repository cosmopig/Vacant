"""ops.fl.eval_fl — Sandboxed evaluator, Solution-class normalization, MV clustering, and CT scoring.

Reuses `ops.e1.evaluate` (`evaluate_code_source`, `_CODEC_AND_CMP_SRC`, `_extract_marker_json`)
and `ops.e1.sandbox` (`build_eval_bwrap_argv`, `run_sandboxed`) directly by import.
"""
from __future__ import annotations

import ast
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import pathlib
import tempfile
from typing import Any

from ops.e1.evaluate import (
    _CODEC_AND_CMP_SRC,
    _extract_marker_json,
    evaluate_code_source,
)
from ops.e1.sandbox import build_eval_bwrap_argv, run_sandboxed

ERR_SENTINEL = "ERR"
ERR_TAG = "__FL_ERR__"


def encode_val_host(v: Any) -> Any:
    """Host-side mirror of `ops.e1.evaluate._CODEC_AND_CMP_SRC.encode_val`."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if math.isnan(v):
            return {"__e1_t__": "float", "v": "nan"}
        if math.isinf(v):
            return {"__e1_t__": "float", "v": "inf" if v > 0 else "-inf"}
        return v
    if isinstance(v, tuple):
        return {"__e1_t__": "tuple", "v": [encode_val_host(x) for x in v]}
    if isinstance(v, set):
        items = [encode_val_host(x) for x in v]
        items.sort(key=lambda z: json.dumps(z, sort_keys=True))
        return {"__e1_t__": "set", "v": items}
    if isinstance(v, complex):
        return {"__e1_t__": "complex", "v": [v.real, v.imag]}
    if isinstance(v, bytes):
        return {"__e1_t__": "bytes", "v": list(v)}
    if isinstance(v, list):
        return [encode_val_host(x) for x in v]
    if isinstance(v, dict):
        if all(isinstance(k, str) for k in v.keys()) and "__e1_t__" not in v:
            return {k: encode_val_host(val) for k, val in v.items()}
        return {"__e1_t__": "dict", "v": [[encode_val_host(k), encode_val_host(val)] for k, val in v.items()]}
    raise TypeError(f"unsupported value type: {type(v).__name__}")


def _defines_top_level_name(tree: ast.Module, name: str) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


def _has_solution_class(tree: ast.Module) -> bool:
    return any(isinstance(node, ast.ClassDef) and node.name == "Solution" for node in tree.body)


def normalize_solution_source(solution_src: str, entry_point: str) -> str:
    """Normalize LeetCode `class Solution` solutions to expose a top-level `entry_point`.

    If `solution_src` defines a top-level `entry_point` function (or has a syntax error),
    returns `solution_src` unchanged. If no top-level `entry_point` exists and `class Solution`
    is defined, appends a thin wrapper calling `Solution().<entry_point>(*args, **kwargs)`.
    """
    if not entry_point or not entry_point.isidentifier():
        return solution_src
    try:
        tree = ast.parse(solution_src)
    except SyntaxError:
        return solution_src

    if _defines_top_level_name(tree, entry_point):
        return solution_src
    if not _has_solution_class(tree):
        return solution_src

    wrapper = (
        "\n\n# [ops.fl] LeetCode Solution class normalization\n"
        f"if {entry_point!r} not in globals() and 'Solution' in globals() and hasattr(Solution, {entry_point!r}):\n"
        f"    def {entry_point}(*__fl_args, **__fl_kwargs):\n"
        f"        return Solution().{entry_point}(*__fl_args, **__fl_kwargs)\n"
    )
    return solution_src.rstrip() + wrapper


def evaluate_solution_on_cases(
    solution_src: str,
    entry_point: str,
    cases: list[dict[str, Any]],
    *,
    per_fn_timeout_s: float = 20.0,
    total_timeout_s: float = 45.0,
    mem_limit_mb: int = 1024,
) -> dict[str, Any]:
    """Evaluate `solution_src` on `cases` inside E1's `--unshare-net` bwrap sandbox.

    Normalizes `class Solution` methods automatically and delegates execution to
    `ops.e1.evaluate.evaluate_code_source`.
    """
    if not cases:
        return {
            "passed": False,
            "n_passed": 0,
            "n_total": 0,
            "error": "no_cases",
            "load_error": None,
            "wall_s": 0.0,
        }

    norm_src = normalize_solution_source(solution_src, entry_point)
    encoded_cases = [
        {"args": encode_val_host(c["args"]), "expected": encode_val_host(c["expected"])}
        for c in cases
    ]
    specs = {
        entry_point: {
            "cases": encoded_cases,
            "atol": 0.0,
            "cmp_mode": "exact",
        }
    }
    raw = evaluate_code_source(
        norm_src,
        specs,
        per_fn_timeout_s=min(per_fn_timeout_s, max(2.0, total_timeout_s - 2.0)),
        total_timeout_s=total_timeout_s,
        mem_limit_mb=mem_limit_mb,
    )
    fn_info = (raw.get("functions") or {}).get(entry_point) or {}
    return {
        "passed": bool(raw.get("all_pass") and fn_info.get("passed")),
        "n_passed": int(fn_info.get("n_passed") or 0),
        "n_total": int(fn_info.get("n_total") or len(cases)),
        "error": fn_info.get("error"),
        "load_error": raw.get("load_error"),
        "wall_s": float(raw.get("wall_s") or 0.0),
    }


_GEN_INPUTS_DRIVER_PY = _CODEC_AND_CMP_SRC + r"""
class _GenTimeout(Exception):
    pass

def _alarm_handler(signum, frame):
    raise _GenTimeout("gen_inputs timeout")

def main():
    req = json.loads(sys.stdin.read())
    gen_path = req["gen_path"]
    max_inputs = int(req.get("max_inputs", 20))
    timeout_s = max(1, int(math.ceil(float(req.get("timeout_s", 8.0)))))
    ns = {"__name__": "fl_gen_inputs"}
    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout_s)
    try:
        with open(gen_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        exec(compile(code, gen_path, "exec"), ns)
        raw_inputs = None
        for fn_name in ("gen_inputs", "generate_inputs"):
            fn = ns.get(fn_name)
            if callable(fn):
                raw_inputs = fn()
                break
        if raw_inputs is None:
            for var_name in ("INPUTS", "inputs"):
                if isinstance(ns.get(var_name), (list, tuple)):
                    raw_inputs = ns[var_name]
                    break
        if raw_inputs is None:
            print("@@FL_GEN@@" + json.dumps({"ok": False, "inputs": [], "error": "missing gen_inputs() or INPUTS"}))
            return
        if not isinstance(raw_inputs, (list, tuple)):
            print("@@FL_GEN@@" + json.dumps({"ok": False, "inputs": [], "error": f"expected list/tuple, got {type(raw_inputs).__name__}"}))
            return
        encoded = []
        skipped = 0
        for item in raw_inputs:
            if len(encoded) >= max_inputs:
                break
            if isinstance(item, tuple):
                args_list = list(item)
            elif isinstance(item, list):
                args_list = list(item)
            else:
                skipped += 1
                continue
            try:
                encoded.append(encode_val(args_list))
            except Exception:
                skipped += 1
        print("@@FL_GEN@@" + json.dumps({"ok": len(encoded) > 0, "inputs": encoded, "skipped": skipped, "error": None if encoded else "no_valid_inputs"}))
    except BaseException as exc:
        print("@@FL_GEN@@" + json.dumps({"ok": False, "inputs": [], "error": f"{type(exc).__name__}: {exc}"}))
    finally:
        signal.alarm(0)

main()
"""


def run_input_generator_in_sandbox(
    gen_src: str,
    *,
    max_inputs: int = 20,
    timeout_s: float = 10.0,
    mem_limit_mb: int = 1024,
) -> dict[str, Any]:
    """Execute `gen_inputs.py` in `--unshare-net` bwrap sandbox and return encoded arg-lists."""
    with tempfile.TemporaryDirectory(prefix="fl_gen_") as tmp:
        gen_file = pathlib.Path(tmp) / "gen_inputs.py"
        gen_file.write_text(gen_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _GEN_INPUTS_DRIVER_PY],
            ro_binds=[(gen_file, "/work/gen_inputs.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(3, int(math.ceil(timeout_s)) + 2),
        )
        req = {
            "gen_path": "/work/gen_inputs.py",
            "max_inputs": max_inputs,
            "timeout_s": max(1.0, timeout_s - 1.0),
        }
        res = run_sandboxed(argv, timeout_s=timeout_s + 2.0, stdin_bytes=json.dumps(req).encode("utf-8"))
        parsed = _extract_marker_json(res["stdout"], "@@FL_GEN@@")
        if parsed is None:
            err = "sandbox_timeout" if res["timed_out"] else f"sandbox_rc={res['rc']}: {res['stderr'][:240]}"
            return {"ok": False, "inputs": [], "error": err, "wall_s": res["wall_s"]}
        parsed["wall_s"] = res["wall_s"]
        return parsed


_COLLECT_OUTPUTS_DRIVER_PY = _CODEC_AND_CMP_SRC + r"""
class _CallTimeout(Exception):
    pass

def _alarm_handler(signum, frame):
    raise _CallTimeout("call timeout")

def main():
    req = json.loads(sys.stdin.read())
    sol_path = req["solution_path"]
    entry_point = req["entry_point"]
    inputs = req["inputs"]
    per_call_s = max(1, int(math.ceil(float(req.get("per_call_timeout_s", 2.0)))))
    load_s = max(1, int(math.ceil(float(req.get("load_timeout_s", 5.0)))))
    ns = {"__name__": "fl_candidate_solution"}
    try:
        with open(sol_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        compiled = compile(code, sol_path, "exec")
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(load_s)
        try:
            exec(compiled, ns)
        finally:
            signal.alarm(0)
    except BaseException as exc:
        err = f"{type(exc).__name__}: {exc}"
        outs = [{"ok": False, "val": "ERR", "err": err} for _ in inputs]
        print("@@FL_OUTS@@" + json.dumps({"load_error": err, "outputs": outs}))
        return

    target = ns.get(entry_point)
    if not callable(target):
        err = f"missing or non-callable function: {entry_point}"
        outs = [{"ok": False, "val": "ERR", "err": err} for _ in inputs]
        print("@@FL_OUTS@@" + json.dumps({"load_error": err, "outputs": outs}))
        return

    outs = []
    for raw_args in inputs:
        args = decode_val(copy.deepcopy(raw_args))
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(per_call_s)
        try:
            got = target(*args)
            enc = encode_val(got)
            outs.append({"ok": True, "val": enc})
        except BaseException as exc:
            outs.append({"ok": False, "val": "ERR", "err": f"{type(exc).__name__}: {exc}"})
        finally:
            signal.alarm(0)
    print("@@FL_OUTS@@" + json.dumps({"load_error": None, "outputs": outs}))

main()
"""


def canonicalize_output_entry(entry: Any) -> str:
    """Map an output record (or raw value / ERR_SENTINEL) to a collision-free canonical tag.

    - Exceptions / timeouts (`{"ok": False, ...}` or `ERR_TAG`) -> `ERR_TAG`.
    - Normal values (`{"ok": True, "val": v}` or raw literal `v`) -> `"__FL_OK__:" + canonical_json`.
      Note: if a caller passes the literal `ERR_TAG`, it is treated as an error; if a candidate
      returns the Python string `"ERR"`, `{"ok": True, "val": "ERR"}` maps to `'__FL_OK__:"ERR"'`,
      distinct from `ERR_TAG`.
    """
    if entry == ERR_TAG:
        return ERR_TAG
    if isinstance(entry, dict) and "ok" in entry and "val" in entry:
        if not entry["ok"]:
            return ERR_TAG
        return "__FL_OK__:" + json.dumps(entry["val"], sort_keys=True, separators=(",", ":"))
    return "__FL_OK__:" + json.dumps(encode_val_host(entry), sort_keys=True, separators=(",", ":"))


def collect_outputs_in_sandbox(
    solution_src: str,
    entry_point: str,
    encoded_inputs: list[Any],
    *,
    per_call_timeout_s: float = 2.0,
    total_timeout_s: float = 30.0,
    mem_limit_mb: int = 1024,
) -> dict[str, Any]:
    """Run normalized `solution_src` on `encoded_inputs` in `--unshare-net` bwrap sandbox."""
    if not encoded_inputs:
        return {"load_error": None, "outputs": [], "tags": [], "wall_s": 0.0}

    norm_src = normalize_solution_source(solution_src, entry_point)
    with tempfile.TemporaryDirectory(prefix="fl_outs_") as tmp:
        sol_file = pathlib.Path(tmp) / "solution.py"
        sol_file.write_text(norm_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _COLLECT_OUTPUTS_DRIVER_PY],
            ro_binds=[(sol_file, "/work/solution.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(5, int(math.ceil(total_timeout_s)) + 2),
        )
        req = {
            "solution_path": "/work/solution.py",
            "entry_point": entry_point,
            "inputs": encoded_inputs,
            "per_call_timeout_s": per_call_timeout_s,
            "load_timeout_s": min(5.0, total_timeout_s),
        }
        res = run_sandboxed(argv, timeout_s=total_timeout_s + 2.0, stdin_bytes=json.dumps(req).encode("utf-8"))
        parsed = _extract_marker_json(res["stdout"], "@@FL_OUTS@@")
        if parsed is None:
            err = "sandbox_timeout" if res["timed_out"] else f"sandbox_rc={res['rc']}: {res['stderr'][:240]}"
            outs = [{"ok": False, "val": ERR_SENTINEL, "err": err} for _ in encoded_inputs]
            tags = [ERR_TAG for _ in encoded_inputs]
            return {"load_error": err, "outputs": outs, "tags": tags, "wall_s": res["wall_s"]}
        outs = parsed.get("outputs") or []
        tags = [canonicalize_output_entry(o) for o in outs]
        return {
            "load_error": parsed.get("load_error"),
            "outputs": outs,
            "tags": tags,
            "wall_s": res["wall_s"],
        }


def cluster_mv_outputs(output_vectors: list[list[Any]]) -> dict[str, Any]:
    """Cluster solutions by identical output vectors (with exceptions/timeouts as distinct output `ERR`).

    Each element of `output_vectors[i]` can be a pre-tagged string (`ERR_TAG` / `"__FL_OK__:..."`),
    an output dict `{"ok": bool, "val": ...}`, or a raw value (where `ERR_TAG` denotes error).

    Rule:
    - Group solutions with identical canonical output tuples across all inputs.
    - Deliver the earliest solution in the largest cluster iff its size >= 2 (and >= 1 input).
    - Otherwise `undetermined = True` and deliver attempt 1 (index 0).
    """
    n_sols = len(output_vectors)
    if n_sols == 0:
        return {
            "undetermined": True,
            "delivered_idx": 0,
            "clusters": [],
            "largest_cluster_size": 0,
            "winning_cluster": [],
            "agree_counts": [],
        }

    n_inputs = len(output_vectors[0]) if output_vectors else 0
    if n_inputs == 0:
        return {
            "undetermined": True,
            "delivered_idx": 0,
            "clusters": [[i] for i in range(n_sols)],
            "largest_cluster_size": 1,
            "winning_cluster": [],
            "agree_counts": [1] * n_sols,
        }

    groups: dict[tuple[str, ...], list[int]] = {}
    for idx, vec in enumerate(output_vectors):
        sig = tuple(
            v if (isinstance(v, str) and (v == ERR_TAG or v.startswith("__FL_OK__:"))) else canonicalize_output_entry(v)
            for v in vec
        )
        groups.setdefault(sig, []).append(idx)

    clusters = sorted(groups.values(), key=lambda members: (-len(members), members[0]))
    agree_counts = [0] * n_sols
    for members in clusters:
        sz = len(members)
        for m in members:
            agree_counts[m] = sz

    largest = clusters[0]
    if len(largest) >= 2:
        return {
            "undetermined": False,
            "delivered_idx": largest[0],
            "clusters": clusters,
            "largest_cluster_size": len(largest),
            "winning_cluster": largest,
            "agree_counts": agree_counts,
        }
    return {
        "undetermined": True,
        "delivered_idx": 0,
        "clusters": clusters,
        "largest_cluster_size": len(largest),
        "winning_cluster": [],
        "agree_counts": agree_counts,
    }


def score_ct_solutions(
    output_vectors: list[list[Any]],
    tests_passed: list[int],
    n_generated_tests: int,
) -> dict[str, Any]:
    """CodeT-style dual agreement scoring.

    For each solution `i`:
        score[i] = (#solutions agreeing with i on generated inputs, incl. i) * (#generated tests i passes)

    Selection:
    - If `n_generated_tests <= 0` or `max(scores) <= 0`: `undetermined = True`, deliver attempt 1 (idx 0).
    - Otherwise deliver the top-scoring solution. If all top-scoring solutions tie across
      distinct clusters or include attempt 1, wait:
      - If attempt 1 is among the tied top scorers, attempt 1 (idx 0) is delivered.
      - If a single winning cluster of size >= 2 beats attempt 1 (e.g. scores `[0, 20, 20]`
        where attempts 2 & 3 agree), deliver the earliest solution in that winning cluster (`min(top_indices)`).
      - If two distinct clusters tie for the top score without attempt 1 (e.g. `[5, 10, 10]`
        with distinct outputs), tie breaks to attempt 1 (idx 0) per spec ("ties => attempt 1").
    """
    n_sols = len(output_vectors)
    if n_sols != len(tests_passed):
        raise ValueError(f"Mismatched lengths: {n_sols} solutions vs {len(tests_passed)} test scores")

    mv_info = cluster_mv_outputs(output_vectors)
    agree_counts = mv_info["agree_counts"] if n_sols > 0 else []
    scores = [int(agree_counts[i]) * int(tests_passed[i]) for i in range(n_sols)]

    if n_sols == 0 or n_generated_tests <= 0 or max(scores) <= 0:
        return {
            "undetermined": True,
            "delivered_idx": 0,
            "scores": scores,
            "agree_counts": agree_counts,
            "tests_passed": list(tests_passed),
            "n_generated_tests": n_generated_tests,
            "clusters": mv_info["clusters"],
            "tie": True,
        }

    max_score = max(scores)
    top_indices = [i for i, s in enumerate(scores) if s == max_score]
    # Check whether all top_indices belong to the same equivalence cluster
    top_clusters = [c for c in mv_info["clusters"] if any(i in c for i in top_indices)]
    if len(top_indices) == 1:
        delivered_idx = top_indices[0]
        tie = False
    elif len(top_clusters) == 1:
        # All top-scoring solutions are identical on all generated inputs (same winning cluster)
        delivered_idx = top_indices[0]
        tie = False
    else:
        # True tie between distinct solutions/clusters -> deliver attempt 1 (idx 0)
        delivered_idx = 0
        tie = True

    return {
        "undetermined": False,
        "delivered_idx": delivered_idx,
        "scores": scores,
        "agree_counts": agree_counts,
        "tests_passed": list(tests_passed),
        "n_generated_tests": n_generated_tests,
        "clusters": mv_info["clusters"],
        "tie": tie,
    }


def deduplicate_encoded_inputs(encoded_inputs: list[Any]) -> list[Any]:
    """Deduplicate encoded argument lists while preserving first-seen order."""
    seen: set[str] = set()
    out: list[Any] = []
    for item in encoded_inputs:
        key = json.dumps(item, sort_keys=True, separators=(",", ":"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ── Stdio (APPS) normalization, float-tolerant comparison, and sandboxed evaluator ──


def normalize_stdio_output(text: str) -> str:
    """Normalise stdout/expected text: strip trailing whitespace per line and trailing blank lines."""
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _try_parse_finite_decimal(tok: str) -> Decimal | None:
    if not tok or "_" in tok:
        return None
    try:
        fv = float(tok)
    except ValueError:
        return None
    if not math.isfinite(fv):
        return None
    try:
        return Decimal(tok)
    except (InvalidOperation, ValueError):
        return Decimal(str(fv))


def stdio_outputs_equal(got: str, expected: str, *, float_tol: float = 1e-6) -> bool:
    """Compare stdout and expected after normalising, with float token tolerance `float_tol`."""
    g = normalize_stdio_output(got)
    e = normalize_stdio_output(expected)
    if g == e:
        return True
    g_lines = g.split("\n")
    e_lines = e.split("\n")
    if len(g_lines) != len(e_lines):
        return False
    tol_dec = Decimal(str(float_tol))
    for gl, el in zip(g_lines, e_lines):
        if gl == el:
            continue
        gt = gl.split()
        et = el.split()
        if len(gt) != len(et):
            return False
        for a, b in zip(gt, et):
            if a == b:
                continue
            da = _try_parse_finite_decimal(a)
            db = _try_parse_finite_decimal(b)
            if da is None or db is None:
                return False
            if abs(da - db) > tol_dec:
                return False
    return True


def deduplicate_stdio_inputs(stdin_inputs: list[str]) -> list[str]:
    """Deduplicate stdin strings while preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in stdin_inputs:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


_STDIO_HELPER_SRC = r"""
from decimal import Decimal, InvalidOperation
import hashlib, json, math, os, signal, subprocess, sys, threading, time

MAX_STDOUT_BYTES = 16 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024

def normalize_stdio_output(text):
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)

def _try_parse_finite_decimal(tok):
    if not tok or "_" in tok:
        return None
    try:
        fv = float(tok)
    except ValueError:
        return None
    if not math.isfinite(fv):
        return None
    try:
        return Decimal(tok)
    except (InvalidOperation, ValueError):
        return Decimal(str(fv))

def stdio_outputs_equal(got, expected, float_tol=1e-6):
    g = normalize_stdio_output(got)
    e = normalize_stdio_output(expected)
    if g == e:
        return True
    g_lines = g.split("\n")
    e_lines = e.split("\n")
    if len(g_lines) != len(e_lines):
        return False
    tol_dec = Decimal(str(float_tol))
    for gl, el in zip(g_lines, e_lines):
        if gl == el:
            continue
        gt = gl.split()
        et = el.split()
        if len(gt) != len(et):
            return False
        for a, b in zip(gt, et):
            if a == b:
                continue
            da = _try_parse_finite_decimal(a)
            db = _try_parse_finite_decimal(b)
            if da is None or db is None:
                return False
            if abs(da - db) > tol_dec:
                return False
    return True

def run_one_stdio(sol_path, inp_str, timeout_s, cwd):
    proc = subprocess.Popen(
        [sys.executable, sol_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        start_new_session=True,
        close_fds=True,
    )
    inp_bytes = inp_str.encode("utf-8", errors="replace")

    def _feed():
        try:
            proc.stdin.write(inp_bytes)
            proc.stdin.flush()
        except OSError:
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    out_buf = bytearray()
    out_truncated = [False]
    def _read_out():
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            rem = MAX_STDOUT_BYTES - len(out_buf)
            if rem > 0:
                out_buf.extend(chunk[:rem])
            if len(chunk) > rem:
                out_truncated[0] = True

    err_buf = bytearray()
    def _read_err():
        while True:
            chunk = proc.stderr.read(16384)
            if not chunk:
                break
            rem = MAX_STDERR_BYTES - len(err_buf)
            if rem > 0:
                err_buf.extend(chunk[:rem])

    t_in = threading.Thread(target=_feed, daemon=True)
    t_out = threading.Thread(target=_read_out, daemon=True)
    t_err = threading.Thread(target=_read_err, daemon=True)
    t_in.start()
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        t_in.join(timeout=1.0)
        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)
        for s in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if s is not None:
                    s.close()
            except OSError:
                pass

    if timed_out:
        return {"ok": False, "stdout": "", "err": "timeout"}
    if out_truncated[0]:
        return {"ok": False, "stdout": "", "err": "stdout_limit_exceeded"}
    if proc.returncode != 0:
        err_lines = err_buf.decode("utf-8", errors="replace").strip().splitlines()
        tail = err_lines[-1] if err_lines else f"rc={proc.returncode}"
        return {"ok": False, "stdout": "", "err": f"rc={proc.returncode}: {tail[:160]}"}
    return {"ok": True, "stdout": out_buf.decode("utf-8", errors="replace"), "err": None}
"""


_STDIO_EVAL_DRIVER_PY = _STDIO_HELPER_SRC + r"""
def main():
    req = json.loads(sys.stdin.read())
    sol_path = req["solution_path"]
    cases = req["cases"]
    per_case_s = float(req.get("per_case_timeout_s", 2.0))
    total_s = float(req.get("total_timeout_s", 45.0))
    float_tol = float(req.get("float_tol", 1e-6))
    n_total = len(cases)

    try:
        with open(sol_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        if not code.strip():
            print("@@FL_STDIO_EVAL@@" + json.dumps({
                "passed": False, "n_passed": 0, "n_total": n_total,
                "error": "empty_solution", "load_error": "empty_solution",
            }))
            return
        compile(code, sol_path, "exec")
    except BaseException as exc:
        err = f"{type(exc).__name__}: {exc}"
        print("@@FL_STDIO_EVAL@@" + json.dumps({
            "passed": False, "n_passed": 0, "n_total": n_total,
            "error": err, "load_error": err,
        }))
        return

    deadline = time.monotonic() + total_s
    n_passed = 0
    first_err = None

    for idx, case in enumerate(cases):
        rem = deadline - time.monotonic()
        if rem <= 0.05:
            if first_err is None:
                first_err = f"case {idx}: total_timeout"
            break
        case_dir = f"/tmp/c_{idx}"
        os.makedirs(case_dir, exist_ok=True)
        res = run_one_stdio(sol_path, case["input"], min(per_case_s, rem), case_dir)
        if not res["ok"]:
            if first_err is None:
                first_err = f"case {idx}: {res['err']}"
            continue
        if stdio_outputs_equal(res["stdout"], case["output"], float_tol=float_tol):
            n_passed += 1
        elif first_err is None:
            got_n = normalize_stdio_output(res["stdout"])
            exp_n = normalize_stdio_output(case["output"])
            first_err = f"case {idx}: mismatch got={repr(got_n)[:80]} expected={repr(exp_n)[:80]}"

    passed = bool(n_total > 0 and n_passed == n_total)
    print("@@FL_STDIO_EVAL@@" + json.dumps({
        "passed": passed,
        "n_passed": n_passed,
        "n_total": n_total,
        "error": first_err,
        "load_error": None,
    }))

main()
"""


def evaluate_stdio_on_cases(
    solution_src: str,
    cases: list[dict[str, str]],
    *,
    per_case_timeout_s: float = 2.0,
    total_timeout_s: float = 45.0,
    mem_limit_mb: int = 1024,
    float_tol: float = 1e-6,
) -> dict[str, Any]:
    """Evaluate a stdin/stdout Python program on `cases` inside `--unshare-net` bwrap sandbox."""
    if not cases:
        return {
            "passed": False,
            "n_passed": 0,
            "n_total": 0,
            "error": "no_cases",
            "load_error": None,
            "wall_s": 0.0,
        }
    if not (solution_src or "").strip():
        return {
            "passed": False,
            "n_passed": 0,
            "n_total": len(cases),
            "error": "empty_solution",
            "load_error": "empty_solution",
            "wall_s": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix="fl_stdio_eval_") as tmp:
        sol_file = pathlib.Path(tmp) / "solution.py"
        sol_file.write_text(solution_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _STDIO_EVAL_DRIVER_PY],
            ro_binds=[(sol_file, "/work/solution.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(5, int(math.ceil(total_timeout_s)) + 5),
        )
        req = {
            "solution_path": "/work/solution.py",
            "cases": [{"input": str(c["input"]), "output": str(c["output"])} for c in cases],
            "per_case_timeout_s": float(per_case_timeout_s),
            "total_timeout_s": float(total_timeout_s),
            "float_tol": float(float_tol),
        }
        res = run_sandboxed(
            argv,
            timeout_s=total_timeout_s + 5.0,
            stdin_bytes=json.dumps(req).encode("utf-8"),
        )
        parsed = _extract_marker_json(res["stdout"], "@@FL_STDIO_EVAL@@")
        if parsed is None:
            err = "sandbox_timeout" if res["timed_out"] else f"sandbox_rc={res['rc']}: {res['stderr'][:240]}"
            return {
                "passed": False,
                "n_passed": 0,
                "n_total": len(cases),
                "error": err,
                "load_error": err,
                "wall_s": float(res["wall_s"]),
            }
        return {
            "passed": bool(parsed.get("passed")),
            "n_passed": int(parsed.get("n_passed") or 0),
            "n_total": int(parsed.get("n_total") or len(cases)),
            "error": parsed.get("error"),
            "load_error": parsed.get("load_error"),
            "wall_s": float(res["wall_s"]),
        }


_STDIO_GEN_INPUTS_DRIVER_PY = r"""
import json, math, signal, sys

class _GenTimeout(Exception):
    pass

def _alarm_handler(signum, frame):
    raise _GenTimeout("gen_inputs timeout")

def main():
    req = json.loads(sys.stdin.read())
    gen_path = req["gen_path"]
    max_inputs = int(req.get("max_inputs", 20))
    timeout_s = max(1, int(math.ceil(float(req.get("timeout_s", 8.0)))))
    ns = {"__name__": "fl_gen_stdio_inputs"}
    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout_s)
    try:
        with open(gen_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        exec(compile(code, gen_path, "exec"), ns)
        raw_inputs = None
        for fn_name in ("gen_inputs", "generate_inputs"):
            fn = ns.get(fn_name)
            if callable(fn):
                raw_inputs = fn()
                break
        if raw_inputs is None:
            for var_name in ("INPUTS", "inputs"):
                if isinstance(ns.get(var_name), (list, tuple)):
                    raw_inputs = ns[var_name]
                    break
        if raw_inputs is None:
            print("@@FL_STDIO_GEN@@" + json.dumps({"ok": False, "inputs": [], "error": "missing gen_inputs() or INPUTS"}))
            return
        if not isinstance(raw_inputs, (list, tuple)):
            print("@@FL_STDIO_GEN@@" + json.dumps({"ok": False, "inputs": [], "error": f"expected list/tuple, got {type(raw_inputs).__name__}"}))
            return
        out = []
        skipped = 0
        for item in raw_inputs:
            if len(out) >= max_inputs:
                break
            if isinstance(item, str):
                out.append(item)
            else:
                skipped += 1
        print("@@FL_STDIO_GEN@@" + json.dumps({
            "ok": len(out) > 0,
            "inputs": out,
            "skipped": skipped,
            "error": None if out else "no_valid_inputs",
        }))
    except BaseException as exc:
        print("@@FL_STDIO_GEN@@" + json.dumps({"ok": False, "inputs": [], "error": f"{type(exc).__name__}: {exc}"}))
    finally:
        signal.alarm(0)

main()
"""


def run_stdio_input_generator_in_sandbox(
    gen_src: str,
    *,
    max_inputs: int = 20,
    timeout_s: float = 10.0,
    mem_limit_mb: int = 1024,
) -> dict[str, Any]:
    """Execute stdio `gen_inputs.py` in `--unshare-net` bwrap sandbox and return list of stdin strings."""
    with tempfile.TemporaryDirectory(prefix="fl_sgen_") as tmp:
        gen_file = pathlib.Path(tmp) / "gen_inputs.py"
        gen_file.write_text(gen_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _STDIO_GEN_INPUTS_DRIVER_PY],
            ro_binds=[(gen_file, "/work/gen_inputs.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(3, int(math.ceil(timeout_s)) + 2),
        )
        req = {
            "gen_path": "/work/gen_inputs.py",
            "max_inputs": max_inputs,
            "timeout_s": max(1.0, timeout_s - 1.0),
        }
        res = run_sandboxed(argv, timeout_s=timeout_s + 2.0, stdin_bytes=json.dumps(req).encode("utf-8"))
        parsed = _extract_marker_json(res["stdout"], "@@FL_STDIO_GEN@@")
        if parsed is None:
            err = "sandbox_timeout" if res["timed_out"] else f"sandbox_rc={res['rc']}: {res['stderr'][:240]}"
            return {"ok": False, "inputs": [], "error": err, "wall_s": res["wall_s"]}
        parsed["wall_s"] = res["wall_s"]
        return parsed


_STDIO_COLLECT_DRIVER_PY = _STDIO_HELPER_SRC + r"""
def main():
    req = json.loads(sys.stdin.read())
    sol_path = req["solution_path"]
    inputs = req["inputs"]
    per_case_s = float(req.get("per_case_timeout_s", 2.0))
    total_s = float(req.get("total_timeout_s", 45.0))

    try:
        with open(sol_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        if not code.strip():
            outs = [{"ok": False, "val": "ERR", "err": "empty_solution"} for _ in inputs]
            print("@@FL_STDIO_OUTS@@" + json.dumps({"load_error": "empty_solution", "outputs": outs}))
            return
        compile(code, sol_path, "exec")
    except BaseException as exc:
        err = f"{type(exc).__name__}: {exc}"
        outs = [{"ok": False, "val": "ERR", "err": err} for _ in inputs]
        print("@@FL_STDIO_OUTS@@" + json.dumps({"load_error": err, "outputs": outs}))
        return

    deadline = time.monotonic() + total_s
    outs = []
    for idx, inp_str in enumerate(inputs):
        rem = deadline - time.monotonic()
        if rem <= 0.05:
            outs.append({"ok": False, "val": "ERR", "err": "total_timeout"})
            continue
        case_dir = f"/tmp/mv_{idx}"
        os.makedirs(case_dir, exist_ok=True)
        res = run_one_stdio(sol_path, inp_str, min(per_case_s, rem), case_dir)
        if not res["ok"]:
            outs.append({"ok": False, "val": "ERR", "err": res["err"]})
        else:
            norm = normalize_stdio_output(res["stdout"])
            if len(norm) <= 4096:
                outs.append({"ok": True, "val": norm})
            else:
                digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
                outs.append({"ok": True, "val": f"__SHA256__:{digest}", "sha256": digest})

    print("@@FL_STDIO_OUTS@@" + json.dumps({"load_error": None, "outputs": outs}))

main()
"""


def collect_stdio_outputs_in_sandbox(
    solution_src: str,
    stdin_inputs: list[str],
    *,
    per_case_timeout_s: float = 2.0,
    total_timeout_s: float = 45.0,
    mem_limit_mb: int = 1024,
) -> dict[str, Any]:
    """Run stdin/stdout `solution_src` on `stdin_inputs` in `--unshare-net` bwrap sandbox for MV/CT."""
    if not stdin_inputs:
        return {"load_error": None, "outputs": [], "tags": [], "wall_s": 0.0}
    if not (solution_src or "").strip():
        outs = [{"ok": False, "val": ERR_SENTINEL, "err": "empty_solution"} for _ in stdin_inputs]
        return {"load_error": "empty_solution", "outputs": outs, "tags": [ERR_TAG for _ in stdin_inputs], "wall_s": 0.0}

    with tempfile.TemporaryDirectory(prefix="fl_souts_") as tmp:
        sol_file = pathlib.Path(tmp) / "solution.py"
        sol_file.write_text(solution_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _STDIO_COLLECT_DRIVER_PY],
            ro_binds=[(sol_file, "/work/solution.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(5, int(math.ceil(total_timeout_s)) + 5),
        )
        req = {
            "solution_path": "/work/solution.py",
            "inputs": [str(x) for x in stdin_inputs],
            "per_case_timeout_s": float(per_case_timeout_s),
            "total_timeout_s": float(total_timeout_s),
        }
        res = run_sandboxed(
            argv,
            timeout_s=total_timeout_s + 5.0,
            stdin_bytes=json.dumps(req).encode("utf-8"),
        )
        parsed = _extract_marker_json(res["stdout"], "@@FL_STDIO_OUTS@@")
        if parsed is None:
            err = "sandbox_timeout" if res["timed_out"] else f"sandbox_rc={res['rc']}: {res['stderr'][:240]}"
            outs = [{"ok": False, "val": ERR_SENTINEL, "err": err} for _ in stdin_inputs]
            tags = [ERR_TAG for _ in stdin_inputs]
            return {"load_error": err, "outputs": outs, "tags": tags, "wall_s": float(res["wall_s"])}
        outs = parsed.get("outputs") or []
        tags = [canonicalize_output_entry(o) for o in outs]
        return {
            "load_error": parsed.get("load_error"),
            "outputs": outs,
            "tags": tags,
            "wall_s": float(res["wall_s"]),
        }
