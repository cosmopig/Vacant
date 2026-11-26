"""ops.fl.bank — LCB v3 bank verification, AST-literal test parsing, and deterministic 50/50 split.

Verifies `ops/gain/data/lcb_bank_v3.jsonl` against `runs/INDEX.json` (`banks.lcb.v3.sha256`)
and refuses to proceed on mismatch. Parses test literal strings safely with `ast.literal_eval`
(never `eval`/`exec`) and performs deterministic per-task 50/50 splitting of `hidden_tests`
into `gate_hidden` and `eval_hidden`.
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


def verify_bank_sha256(
    bank_path: pathlib.Path = DEFAULT_BANK_PATH,
    index_path: pathlib.Path = DEFAULT_INDEX_PATH,
) -> str:
    """Verify `bank_path` sha256 against `runs/INDEX.json` `banks.lcb.v3.sha256`.

    Raises ValueError on missing index/pin or sha256 mismatch.
    """
    bank_p = pathlib.Path(bank_path).expanduser().resolve()
    idx_p = pathlib.Path(index_path).expanduser().resolve()
    if not bank_p.is_file():
        raise FileNotFoundError(f"Bank file not found: {bank_p}")
    if not idx_p.is_file():
        raise FileNotFoundError(f"Index file not found: {idx_p}")

    idx = json.loads(idx_p.read_text(encoding="utf-8"))
    try:
        expected_sha = str(idx["banks"]["lcb"]["v3"]["sha256"]).strip().lower()
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Missing banks.lcb.v3.sha256 in {idx_p}") from exc
    if len(expected_sha) != 64:
        raise ValueError(f"Invalid banks.lcb.v3.sha256 in {idx_p}: {expected_sha!r}")

    actual_sha = sha256_file(bank_p).lower()
    if actual_sha != expected_sha:
        raise ValueError(
            f"Bank sha256 mismatch for {bank_p}: expected {expected_sha} (from {idx_p}), got {actual_sha}"
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


def parse_tests_spec_text(text: str) -> tuple[list[dict[str, Any]], str | None]:
    """Safely parse a `tests_spec.py` file using ONLY `ast.parse` + `ast.literal_eval`.

    Accepts either:
    - a bare Python literal list/tuple of `{"args": ..., "expected": ...}` dicts, or
    - a single top-level assignment `TESTS = [...]` / `tests_spec = [...]` (optionally
      preceded by a module docstring).

    Rejects any imports, function definitions, calls, or other executable statements.
    Returns `(cases, error_message)`. On failure or 0 cases, returns `([], reason)`.
    """
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
        cases = parse_test_cases(literal_obj)
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


def load_bank_tasks(
    bank_path: pathlib.Path = DEFAULT_BANK_PATH,
    *,
    index_path: pathlib.Path = DEFAULT_INDEX_PATH,
    seed: int,
    task_ids: list[str] | None = None,
    difficulties: list[str] | None = None,
    n_tasks: int | None = None,
    verify_sha256: bool = True,
) -> dict[str, Any]:
    """Load, verify, parse, filter, and deterministically split tasks from the LCB bank."""
    bank_p = pathlib.Path(bank_path).expanduser().resolve()
    bank_sha = verify_bank_sha256(bank_p, index_path) if verify_sha256 else sha256_file(bank_p)

    raw_rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(bank_p.read_text(encoding="utf-8").splitlines(), start=1):
        s = raw_line.strip()
        if not s:
            continue
        try:
            raw_rows.append(json.loads(s))
        except ValueError as exc:
            raise ValueError(f"Invalid JSON at {bank_p}:{line_no}: {exc}") from exc

    diff_set = {d.strip().lower() for d in difficulties} if difficulties else None

    eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    for row in raw_rows:
        tid = str(row["task_id"])
        diff = str(row.get("difficulty") or "unknown").strip().lower()
        vis = parse_test_cases(row.get("visible_tests") or [])
        hid = parse_test_cases(row.get("hidden_tests") or [])
        split = split_hidden_tests(hid, task_id=tid, seed=seed)
        if split is None:
            skipped.append({"task_id": tid, "difficulty": diff, "reason": f"hidden_tests<4 (n={len(hid)})"})
            continue

        task_obj = {
            "task_id": tid,
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
        by_id[tid] = task_obj
        if diff_set is None or diff in diff_set:
            eligible.append(task_obj)

    if task_ids is not None:
        selected: list[dict[str, Any]] = []
        skipped_by_id = {s["task_id"]: s for s in skipped}
        for tid in task_ids:
            if tid in by_id:
                selected.append(by_id[tid])
            elif tid in skipped_by_id:
                continue
            else:
                raise ValueError(f"Requested task_id not found in bank: {tid!r}")
    elif n_tasks is not None:
        if n_tasks <= 0:
            raise ValueError(f"n_tasks must be > 0, got {n_tasks}")
        pool = list(eligible)
        rng = random.Random(_stable_seed_int(seed, "__sample_tasks__"))
        rng.shuffle(pool)
        selected = pool[: min(n_tasks, len(pool))]
    else:
        selected = eligible

    return {
        "bank_path": str(bank_p),
        "bank_sha256": bank_sha,
        "seed": seed,
        "tasks": selected,
        "skipped": skipped,
    }
