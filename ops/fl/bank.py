"""ops.fl.bank — Bank verification (LCB v3 function & APPS stdio), AST-literal parsing, and 50/50 split.

Verifies bank sha256 against either a plan-pinned `expected_sha256` or `runs/INDEX.json`
(`banks.lcb.v3.sha256`) and refuses to proceed on mismatch. Parses test literal strings safely
with `ast.literal_eval` (never `eval`/`exec`) and performs deterministic per-task 50/50
splitting of `hidden_tests` into `gate_hidden` and `eval_hidden`.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import pathlib
import random
from typing import Any

from ops.fl import DEFAULT_BANK_PATH, DEFAULT_INDEX_PATH, sha256_file

TASK_FORMATS: tuple[str, ...] = ("function", "stdio")


def verify_bank_sha256(
    bank_path: pathlib.Path = DEFAULT_BANK_PATH,
    index_path: pathlib.Path | None = DEFAULT_INDEX_PATH,
    *,
    expected_sha256: str | None = None,
) -> str:
    """Verify `bank_path` sha256 against `expected_sha256` (from plan) or `runs/INDEX.json`.

    Raises ValueError on missing/invalid pin or sha256 mismatch.
    """
    bank_p = pathlib.Path(bank_path).expanduser().resolve()
    if not bank_p.is_file():
        raise FileNotFoundError(f"Bank file not found: {bank_p}")

    if expected_sha256 is not None:
        expected_sha = str(expected_sha256).strip().lower()
        pin_source = "plan bank_sha256"
        if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
            raise ValueError(f"Invalid expected_sha256 in {pin_source}: {expected_sha!r}")
    else:
        if index_path is None:
            raise ValueError("Either expected_sha256 or index_path must be provided to verify bank sha256")
        idx_p = pathlib.Path(index_path).expanduser().resolve()
        if not idx_p.is_file():
            raise FileNotFoundError(f"Index file not found: {idx_p}")
        idx = json.loads(idx_p.read_text(encoding="utf-8"))
        try:
            expected_sha = str(idx["banks"]["lcb"]["v3"]["sha256"]).strip().lower()
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Missing banks.lcb.v3.sha256 in {idx_p}") from exc
        if len(expected_sha) != 64:
            raise ValueError(f"Invalid banks.lcb.v3.sha256 in {idx_p}: {expected_sha!r}")
        pin_source = str(idx_p)

    actual_sha = sha256_file(bank_p).lower()
    if actual_sha != expected_sha:
        raise ValueError(
            f"Bank sha256 mismatch for {bank_p}: expected {expected_sha} (from {pin_source}), got {actual_sha}"
        )
    return actual_sha


def _is_codec_literal(val: Any, _depth: int = 0) -> bool:
    """Check that `val` is a pure Python literal supported by `ops.e1.evaluate` codec."""
    if _depth > 64:
        return False
    if val is None or isinstance(val, (bool, int, str, bytes, complex)):
        return True
    if isinstance(val, float):
        return not (math.isnan(val) or math.isinf(val))
    if isinstance(val, (list, tuple, set)):
        return all(_is_codec_literal(x, _depth + 1) for x in val)
    if isinstance(val, dict):
        return all(
            _is_codec_literal(k, _depth + 1) and _is_codec_literal(v, _depth + 1)
            for k, v in val.items()
        )
    return False


def parse_test_case(raw_case: Any) -> dict[str, Any]:
    """Parse a single `{args, expected}` test case using `ast.literal_eval` when string-encoded.

    Supports both:
    - string-encoded cases (e.g. `{"args": "[1, 2]", "expected": "3"}` or `{"args": "('abc',)", "expected": "'cba'"}`)
    - native literal cases (e.g. `{"args": [1, 2], "expected": 3}`, preserving string return values like `"11001"`)
    """
    if not isinstance(raw_case, dict):
        raise ValueError(f"Test case must be a dict, got {type(raw_case).__name__}")
    if "args" not in raw_case or "expected" not in raw_case:
        raise ValueError("Test case must contain 'args' and 'expected'")

    raw_args = raw_case["args"]
    raw_exp = raw_case["expected"]

    args_was_str = isinstance(raw_args, str)
    if args_was_str:
        try:
            args_val = ast.literal_eval(raw_args)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"Failed ast.literal_eval on args={raw_args!r}: {exc}") from exc
    else:
        args_val = raw_args

    if isinstance(args_val, tuple):
        args_list = list(args_val)
    elif isinstance(args_val, list):
        args_list = list(args_val)
    else:
        raise ValueError(f"Test case 'args' must be a list or tuple, got {type(args_val).__name__}")

    if args_was_str and isinstance(raw_exp, str):
        try:
            exp_val = ast.literal_eval(raw_exp)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"Failed ast.literal_eval on expected={raw_exp!r}: {exc}") from exc
    else:
        exp_val = raw_exp

    if not _is_codec_literal(args_list):
        raise ValueError("Test case 'args' contains unsupported non-literal value")
    if not _is_codec_literal(exp_val):
        raise ValueError("Test case 'expected' contains unsupported non-literal value")

    return {"args": args_list, "expected": exp_val}


def parse_test_cases(raw_cases: Any) -> list[dict[str, Any]]:
    """Parse a sequence (or string literal of a sequence) of `{args, expected}` test cases."""
    if isinstance(raw_cases, str):
        try:
            raw_cases = ast.literal_eval(raw_cases)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"Failed ast.literal_eval on test cases string: {exc}") from exc
    if not isinstance(raw_cases, (list, tuple)):
        raise ValueError(f"Test cases must be a list or tuple, got {type(raw_cases).__name__}")
    return [parse_test_case(c) for c in raw_cases]


def parse_stdio_case(raw_case: Any) -> dict[str, str]:
    """Validate a single `{"input": str, "output": str}` stdio test case."""
    if not isinstance(raw_case, dict):
        raise ValueError(f"Stdio test case must be a dict, got {type(raw_case).__name__}")
    if "input" not in raw_case or "output" not in raw_case:
        raise ValueError("Stdio test case must contain 'input' and 'output'")
    inp = raw_case["input"]
    out = raw_case["output"]
    if not isinstance(inp, str):
        raise ValueError(f"Stdio test case 'input' must be str, got {type(inp).__name__}")
    if not isinstance(out, str):
        raise ValueError(f"Stdio test case 'output' must be str, got {type(out).__name__}")
    return {"input": inp, "output": out}


def parse_stdio_cases(raw_cases: Any) -> list[dict[str, str]]:
    """Parse a sequence (or string literal of a sequence) of `{"input": str, "output": str}` cases."""
    if isinstance(raw_cases, str):
        try:
            raw_cases = ast.literal_eval(raw_cases)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f"Failed ast.literal_eval on stdio test cases string: {exc}") from exc
    if not isinstance(raw_cases, (list, tuple)):
        raise ValueError(f"Stdio test cases must be a list or tuple, got {type(raw_cases).__name__}")
    return [parse_stdio_case(c) for c in raw_cases]


def parse_tests_spec_text(
    text: str,
    *,
    task_format: str = "function",
) -> tuple[list[dict[str, Any]], str | None]:
    """Safely parse a `tests_spec.py` file using ONLY `ast.parse` + `ast.literal_eval`.

    Accepts either:
    - a bare Python literal list/tuple of case dicts, or
    - a single top-level assignment `TESTS = [...]` / `tests_spec = [...]` (optionally
      preceded by a module docstring).

    For `task_format == "function"`, each dict has `{"args": [...], "expected": ...}`.
    For `task_format == "stdio"`, each dict has `{"input": str, "output": str}`.

    Rejects any imports, function definitions, calls, or other executable statements.
    Returns `(cases, error_message)`. On failure or 0 cases, returns `([], reason)`.
    """
    if task_format not in TASK_FORMATS:
        return [], f"unknown_task_format: {task_format!r}"

    src = (text or "").strip()
    if not src:
        return [], "empty_tests_spec"

    try:
        tree = ast.parse(src, mode="exec")
    except SyntaxError as exc:
        return [], f"syntax_error: {exc}"

    stmts = list(tree.body)
    # Allow a single leading module docstring
    if (
        stmts
        and isinstance(stmts[0], ast.Expr)
        and isinstance(stmts[0].value, ast.Constant)
        and isinstance(stmts[0].value.value, str)
    ):
        stmts = stmts[1:]

    if len(stmts) != 1:
        return [], f"expected_single_literal_statement_got_{len(stmts)}"

    stmt = stmts[0]
    if isinstance(stmt, ast.Expr):
        value_node = stmt.value
    elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        value_node = stmt.value
    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        value_node = stmt.value
    else:
        return [], f"disallowed_statement: {type(stmt).__name__}"

    try:
        literal_obj = ast.literal_eval(value_node)
    except (ValueError, SyntaxError) as exc:
        return [], f"not_a_python_literal: {exc}"

    try:
        cases = parse_stdio_cases(literal_obj) if task_format == "stdio" else parse_test_cases(literal_obj)
    except ValueError as exc:
        return [], f"invalid_case_format: {exc}"

    if not cases:
        return [], "zero_cases"
    return cases, None


def _stable_seed_int(seed: int, tag: str) -> int:
    digest = hashlib.sha256(f"{seed}:{tag}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def split_hidden_tests(
    hidden_tests: list[dict[str, Any]],
    *,
    task_id: str,
    seed: int,
) -> dict[str, Any] | None:
    """Deterministically split `hidden_tests` 50/50 into `gate_hidden` and `eval_hidden`.

    Returns `None` if `len(hidden_tests) < 4` (caller must skip and log the task).
    """
    n = len(hidden_tests)
    if n < 4:
        return None
    indices = list(range(n))
    rng = random.Random(_stable_seed_int(seed, task_id))
    rng.shuffle(indices)
    mid = n // 2
    gate_idx = indices[:mid]
    eval_idx = indices[mid:]
    return {
        "gate_hidden": [hidden_tests[i] for i in gate_idx],
        "eval_hidden": [hidden_tests[i] for i in eval_idx],
        "gate_indices": gate_idx,
        "eval_indices": eval_idx,
    }


def _build_task_obj(row: dict[str, Any], *, task_format: str, seed: int) -> dict[str, Any]:
    tid = str(row["task_id"])
    diff = str(row.get("difficulty") or "unknown").strip().lower()
    if task_format == "stdio":
        raw_ex = row.get("examples") if "examples" in row else row.get("visible_tests")
        vis = parse_stdio_cases(raw_ex or [])
        hid = parse_stdio_cases(row.get("hidden_tests") or [])
        split = split_hidden_tests(hid, task_id=tid, seed=seed)
        assert split is not None
        return {
            "task_id": tid,
            "task_format": "stdio",
            "difficulty": diff,
            "entry_point": None,
            "prompt": str(row["prompt"]),
            "examples": vis,
            "visible_tests": vis,
            "gate_hidden": split["gate_hidden"],
            "eval_hidden": split["eval_hidden"],
            "gate_indices": split["gate_indices"],
            "eval_indices": split["eval_indices"],
            "n_hidden_total": len(hid),
        }

    vis = parse_test_cases(row.get("visible_tests") or [])
    hid = parse_test_cases(row.get("hidden_tests") or [])
    split = split_hidden_tests(hid, task_id=tid, seed=seed)
    assert split is not None
    return {
        "task_id": tid,
        "task_format": "function",
        "difficulty": diff,
        "entry_point": str(row["entry_point"]),
        "prompt": str(row["prompt"]),
        "visible_tests": vis,
        "gate_hidden": split["gate_hidden"],
        "eval_hidden": split["eval_hidden"],
        "gate_indices": split["gate_indices"],
        "eval_indices": split["eval_indices"],
        "n_hidden_total": len(hid),
    }


def load_bank_tasks(
    bank_path: pathlib.Path = DEFAULT_BANK_PATH,
    *,
    index_path: pathlib.Path | None = DEFAULT_INDEX_PATH,
    expected_sha256: str | None = None,
    task_format: str = "function",
    seed: int,
    task_ids: list[str] | None = None,
    difficulties: list[str] | None = None,
    n_tasks: int | None = None,
    verify_sha256: bool = True,
) -> dict[str, Any]:
    """Stream, verify, parse, filter, and deterministically split tasks from a bank JSONL.

    Supports both `task_format="function"` (LCB v3) and `task_format="stdio"` (APPS).
    Uses byte-offset indexing so large banks (e.g. 900 MB APPS) load only selected tasks into memory.
    """
    if task_format not in TASK_FORMATS:
        raise ValueError(f"Unsupported task_format={task_format!r}; expected one of {TASK_FORMATS}")

    bank_p = pathlib.Path(bank_path).expanduser().resolve()
    bank_sha = (
        verify_bank_sha256(bank_p, index_path, expected_sha256=expected_sha256)
        if verify_sha256
        else sha256_file(bank_p)
    )

    diff_set = {d.strip().lower() for d in difficulties} if difficulties else None

    eligible_refs: list[tuple[str, int]] = []
    skipped: list[dict[str, Any]] = []
    offset_by_id: dict[str, int] = {}

    # Pass 1: stream line-by-line recording byte offsets so huge banks stay low-memory
    with open(bank_p, "rb") as fh:
        line_no = 0
        while True:
            offset = fh.tell()
            raw_b = fh.readline()
            if not raw_b:
                break
            line_no += 1
            s = raw_b.decode("utf-8").strip()
            if not s:
                continue
            try:
                row = json.loads(s)
            except ValueError as exc:
                raise ValueError(f"Invalid JSON at {bank_p}:{line_no}: {exc}") from exc

            tid = str(row["task_id"])
            diff = str(row.get("difficulty") or "unknown").strip().lower()
            raw_hid = row.get("hidden_tests") or []
            n_hid = len(raw_hid) if isinstance(raw_hid, list) else len(parse_test_cases(raw_hid))
            if n_hid < 4:
                skipped.append({"task_id": tid, "difficulty": diff, "reason": f"hidden_tests<4 (n={n_hid})"})
                continue

            offset_by_id[tid] = offset
            if diff_set is None or diff in diff_set:
                eligible_refs.append((tid, offset))

    if task_ids is not None:
        wanted_refs: list[tuple[str, int]] = []
        skipped_by_id = {s["task_id"]: s for s in skipped}
        for tid in task_ids:
            if tid in offset_by_id:
                wanted_refs.append((tid, offset_by_id[tid]))
            elif tid in skipped_by_id:
                continue
            else:
                raise ValueError(f"Requested task_id not found in bank: {tid!r}")
    elif n_tasks is not None:
        if n_tasks <= 0:
            raise ValueError(f"n_tasks must be > 0, got {n_tasks}")
        pool = list(eligible_refs)
        rng = random.Random(_stable_seed_int(seed, "__sample_tasks__"))
        rng.shuffle(pool)
        wanted_refs = pool[: min(n_tasks, len(pool))]
    else:
        wanted_refs = eligible_refs

    # Pass 2: seek directly to selected lines and construct full task objects
    selected: list[dict[str, Any]] = []
    with open(bank_p, "rb") as fh:
        for _tid, offset in wanted_refs:
            fh.seek(offset)
            row = json.loads(fh.readline().decode("utf-8"))
            selected.append(_build_task_obj(row, task_format=task_format, seed=seed))

    return {
        "bank_path": str(bank_p),
        "bank_sha256": bank_sha,
        "task_format": task_format,
        "seed": seed,
        "tasks": selected,
        "skipped": skipped,
    }
