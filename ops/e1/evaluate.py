"""ops.e1.evaluate — 獨立評分器、B2 可見檢查與文件 S 臂範圍推導。

這支在架構裡承重什麼
====================
1. **程式碼評分與可見測試（無網路沙箱）**：
   - `evaluate_code_source` 在獨立的 `bwrap --unshare-net` 沙箱內（含記憶體與逾時限制）載入候選
     `solution.py`，逐函式執行測資並以 `signal.SIGALRM` 隔離單一函式的無窮迴圈；結果由宿主端接收與落盤。
   - `compute_expected_outputs_in_sandbox` 供 `build_code_chains.py` 在無網路沙箱裡由 canonical solution
     計算 `base_input`／`plus_input` 預期輸出。
   - 依 Vacant 不變量 I-4：`n_total == 0` 一律判 `passed = False`（「沒測到」不是「通過」）。
2. **文件評分、B2 結構檢查與 S 臂範圍計算**：
   - `check_doc_structural`：B2 宿主可用檢查——只看每個範本行前綴是否皆存在且有非空、非佔位符的值
     （絕不讀真值）。
   - `evaluate_doc_report`：獨立評分——將每條宣稱正規化後與 `truth[k]` 精確比對。
   - `compute_doc_scope_s`：S 臂宿主端範圍推導——直接呼叫產品函式
     `vacant_network.trace.sources.value_status(prev_page_text, cur_page_text, value, by_field=True)`，
     對上一狀態曾出現該值的頁面逐一檢查，標出 `changed` 或 `no_source` 的範本行；零模型呼叫、不碰真值。

誠實邊界（改碼請保留）
----------------------
- 程式碼評分的型別編解碼（`_encode_val`/`_decode_val`）涵蓋 Python 常見值型別（tuple／set／float／
  complex／bytes／list／dict／基本型別）；自訂類別實例或不可序列化物件會被拒收，不猜測相等。
- 文件 S 臂範圍計算依賴「上一狀態哪些頁面含這個值」的純文字匹配（`plain_contains`）與 `value_status`；
  若同一個值巧合出現在另一張有變動的頁面，可能多放行（保守偏向不漏，符合產品 `sources.py` 語意）；
  反過來說若值在改動後仍巧合留於同列，亦可能漏標（由事後 `false_rejects` 量測）。
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys
import tempfile
from typing import Any

# 確保可匯入本 repo 的 vacant_network.trace.sources
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vacant_network.trace.sources import plain_contains, value_status  # noqa: E402

from .sandbox import build_eval_bwrap_argv, run_sandboxed  # noqa: E402
from .units import doc_line_prefix, doc_line_value, extract_doc_units  # noqa: E402

_PLACEHOLDER_RE = re.compile(r"_{3,}|\bTODO\b|\bTBD\b", re.I)

# ── 沙箱內共用的型別編解碼與比對程式段 ──────────────────────────────────────

_CODEC_AND_CMP_SRC = r"""
import copy, json, math, signal, sys, traceback

def encode_val(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if math.isnan(v):
            return {"__e1_t__": "float", "v": "nan"}
        if math.isinf(v):
            return {"__e1_t__": "float", "v": "inf" if v > 0 else "-inf"}
        return v
    if isinstance(v, tuple):
        return {"__e1_t__": "tuple", "v": [encode_val(x) for x in v]}
    if isinstance(v, set):
        items = [encode_val(x) for x in v]
        items.sort(key=lambda z: json.dumps(z, sort_keys=True))
        return {"__e1_t__": "set", "v": items}
    if isinstance(v, complex):
        return {"__e1_t__": "complex", "v": [v.real, v.imag]}
    if isinstance(v, bytes):
        return {"__e1_t__": "bytes", "v": list(v)}
    if isinstance(v, list):
        return [encode_val(x) for x in v]
    if isinstance(v, dict):
        if all(isinstance(k, str) for k in v.keys()):
            if "__e1_t__" in v:
                return {"__e1_t__": "dict", "v": [[encode_val(k), encode_val(val)] for k, val in v.items()]}
            return {k: encode_val(val) for k, val in v.items()}
        return {"__e1_t__": "dict", "v": [[encode_val(k), encode_val(val)] for k, val in v.items()]}
    raise TypeError(f"unsupported value type: {type(v).__name__}")

def decode_val(v):
    if isinstance(v, dict) and "__e1_t__" in v:
        t = v["__e1_t__"]
        val = v["v"]
        if t == "float":
            return float(val)
        if t == "tuple":
            return tuple(decode_val(x) for x in val)
        if t == "set":
            return set(decode_val(x) for x in val)
        if t == "complex":
            return complex(val[0], val[1])
        if t == "bytes":
            return bytes(val)
        if t == "dict":
            return {decode_val(k): decode_val(vv) for k, vv in val}
    if isinstance(v, list):
        return [decode_val(x) for x in v]
    if isinstance(v, dict):
        return {k: decode_val(val) for k, val in v.items()}
    return v

def _eq_num(a, b, atol):
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    if atol and atol > 0:
        return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=atol)
    return a == b

def values_equal(got, exp, atol=0.0, cmp_mode="exact"):
    if cmp_mode == "set_equivalent":
        try:
            return set(got) == set(exp)
        except TypeError:
            return False
    if isinstance(got, bool) or isinstance(exp, bool):
        return isinstance(got, bool) and isinstance(exp, bool) and got == exp
    if isinstance(got, (int, float)) and isinstance(exp, (int, float)):
        return _eq_num(got, exp, atol)
    if isinstance(got, complex) or isinstance(exp, complex):
        if isinstance(got, (int, float, complex)) and isinstance(exp, (int, float, complex)):
            gc, ec = complex(got), complex(exp)
            return _eq_num(gc.real, ec.real, atol) and _eq_num(gc.imag, ec.imag, atol)
        return False
    if isinstance(got, tuple) and isinstance(exp, tuple):
        return len(got) == len(exp) and all(values_equal(x, y, atol, "exact") for x, y in zip(got, exp))
    if isinstance(got, list) and isinstance(exp, list):
        return len(got) == len(exp) and all(values_equal(x, y, atol, "exact") for x, y in zip(got, exp))
    if isinstance(got, set) and isinstance(exp, set):
        return got == exp
    if isinstance(got, dict) and isinstance(exp, dict):
        if set(got.keys()) != set(exp.keys()):
            return False
        return all(values_equal(got[k], exp[k], atol, "exact") for k in got)
    return type(got) is type(exp) and got == exp
"""

_EVAL_DRIVER_PY = _CODEC_AND_CMP_SRC + r"""
class _FnTimeout(Exception):
    pass

def _alarm_handler(signum, frame):
    raise _FnTimeout("per-function timeout")

def main():
    req = json.loads(sys.stdin.read())
    sol_path = req["solution_path"]
    tests = req["tests"]
    per_fn_s = max(1, int(math.ceil(float(req.get("per_fn_timeout_s", 5.0)))))
    out = {"load_error": None, "functions": {}}
    ns = {"__name__": "e1_candidate_solution"}
    try:
        with open(sol_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        compiled = compile(code, sol_path, "exec")
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(per_fn_s)
        try:
            exec(compiled, ns)
        finally:
            signal.alarm(0)
    except BaseException as exc:
        out["load_error"] = f"{type(exc).__name__}: {exc}"
        for fn, spec in tests.items():
            cases = spec.get("cases") or []
            out["functions"][fn] = {
                "passed": False,
                "n_passed": 0,
                "n_total": len(cases),
                "error": out["load_error"],
            }
        print("@@E1_EVAL@@" + json.dumps(out))
        return

    for fn, spec in tests.items():
        cases = spec.get("cases") or []
        atol = float(spec.get("atol") or 0.0)
        cmp_mode = str(spec.get("cmp_mode") or "exact")
        n_total = len(cases)
        n_passed = 0
        first_err = None
        target = ns.get(fn)
        if not callable(target):
            out["functions"][fn] = {
                "passed": False,
                "n_passed": 0,
                "n_total": n_total,
                "error": f"missing or non-callable function: {fn}",
            }
            continue
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(per_fn_s)
        try:
            for idx, c in enumerate(cases):
                args = decode_val(copy.deepcopy(c["args"]))
                exp = decode_val(c["expected"])
                try:
                    got = target(*args)
                except _FnTimeout:
                    raise
                except BaseException as exc:
                    if first_err is None:
                        first_err = f"case {idx}: {type(exc).__name__}: {exc}"
                    continue
                if values_equal(got, exp, atol=atol, cmp_mode=cmp_mode):
                    n_passed += 1
                elif first_err is None:
                    first_err = f"case {idx}: mismatch got={repr(got)[:80]} expected={repr(exp)[:80]}"
        except _FnTimeout as exc:
            first_err = str(exc)
        finally:
            signal.alarm(0)
        # I-4: n_total == 0 絕不算過
        out["functions"][fn] = {
            "passed": bool(n_total > 0 and n_passed == n_total),
            "n_passed": n_passed,
            "n_total": n_total,
            "error": first_err,
        }

    print("@@E1_EVAL@@" + json.dumps(out))

main()
"""

_COMPUTE_DRIVER_PY = _CODEC_AND_CMP_SRC + r"""
class _FnTimeout(Exception):
    pass

def _alarm_handler(signum, frame):
    raise _FnTimeout("compute timeout")

def main():
    req = json.loads(sys.stdin.read())
    src_path = req["solution_path"]
    entry_point = req["entry_point"]
    base_inputs = req["base_inputs"]
    plus_inputs = req["plus_inputs"]
    timeout_s = max(1, int(math.ceil(float(req.get("timeout_s", 5.0)))))
    ns = {"__name__": "e1_canonical"}
    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout_s)
    try:
        with open(src_path, "r", encoding="utf-8") as fh:
            code = fh.read()
        exec(compile(code, src_path, "exec"), ns)
        fn = ns.get(entry_point)
        if not callable(fn):
            print("@@E1_COMP@@" + json.dumps({"ok": False, "error": f"entry_point {entry_point} missing"}))
            return
        base_cases = []
        for args in base_inputs:
            got = fn(*copy.deepcopy(args))
            base_cases.append({"args": args, "expected": encode_val(got)})
        plus_cases = []
        for args in plus_inputs:
            got = fn(*copy.deepcopy(args))
            plus_cases.append({"args": args, "expected": encode_val(got)})
        print("@@E1_COMP@@" + json.dumps({"ok": True, "base_cases": base_cases, "plus_cases": plus_cases}))
    except BaseException as exc:
        print("@@E1_COMP@@" + json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
    finally:
        signal.alarm(0)

main()
"""


def _extract_marker_json(stdout: str, marker: str) -> dict | None:
    idx = stdout.rfind(marker)
    if idx < 0:
        return None
    tail = stdout[idx + len(marker) :].strip()
    line = tail.splitlines()[0] if tail else ""
    try:
        return json.loads(line)
    except ValueError:
        return None


def compute_expected_outputs_in_sandbox(
    canonical_src: str,
    entry_point: str,
    base_inputs: list[list[Any]],
    plus_inputs: list[list[Any]],
    *,
    timeout_s: float = 8.0,
    mem_limit_mb: int = 1024,
) -> dict:
    """在無網路 bwrap 沙箱內以 canonical solution 計算 base/plus 預期輸出。"""
    with tempfile.TemporaryDirectory(prefix="e1_comp_") as tmp:
        sol_file = pathlib.Path(tmp) / "canonical.py"
        sol_file.write_text(canonical_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _COMPUTE_DRIVER_PY],
            ro_binds=[(sol_file, "/work/canonical.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(2, int(math.ceil(timeout_s)) + 1),
        )
        req = {
            "solution_path": "/work/canonical.py",
            "entry_point": entry_point,
            "base_inputs": base_inputs,
            "plus_inputs": plus_inputs,
            "timeout_s": max(1.0, timeout_s - 1.0),
        }
        res = run_sandboxed(argv, timeout_s=timeout_s + 2.0, stdin_bytes=json.dumps(req).encode("utf-8"))
        if res["timed_out"]:
            return {"ok": False, "error": "sandbox_timeout"}
        parsed = _extract_marker_json(res["stdout"], "@@E1_COMP@@")
        if parsed is None:
            return {"ok": False, "error": f"sandbox_rc={res['rc']}: {res['stderr'][:200]}"}
        return parsed


def evaluate_code_source(
    solution_src: str,
    test_specs: dict[str, dict],
    *,
    per_fn_timeout_s: float = 6.0,
    total_timeout_s: float = 45.0,
    mem_limit_mb: int = 1024,
) -> dict:
    """在無網路 bwrap 沙箱中評測 `solution_src` 對每個要求函式的通過情形。"""
    if not test_specs:
        return {"all_pass": False, "load_error": "no_test_specs", "functions": {}, "wall_s": 0.0}
    with tempfile.TemporaryDirectory(prefix="e1_eval_") as tmp:
        sol_file = pathlib.Path(tmp) / "solution.py"
        sol_file.write_text(solution_src, encoding="utf-8")
        argv = build_eval_bwrap_argv(
            ["python3", "-c", _EVAL_DRIVER_PY],
            ro_binds=[(sol_file, "/work/solution.py")],
            chdir="/tmp",
            mem_limit_mb=mem_limit_mb,
            cpu_limit_s=max(5, int(math.ceil(total_timeout_s)) + 2),
        )
        req = {
            "solution_path": "/work/solution.py",
            "tests": test_specs,
            "per_fn_timeout_s": per_fn_timeout_s,
        }
        res = run_sandboxed(argv, timeout_s=total_timeout_s + 2.0, stdin_bytes=json.dumps(req).encode("utf-8"))
        parsed = _extract_marker_json(res["stdout"], "@@E1_EVAL@@")
        if parsed is None:
            err = "sandbox_timeout" if res["timed_out"] else f"sandbox_rc={res['rc']}: {res['stderr'][:240]}"
            funcs = {
                fn: {"passed": False, "n_passed": 0, "n_total": len(spec.get("cases") or []), "error": err}
                for fn, spec in test_specs.items()
            }
            return {"all_pass": False, "load_error": err, "functions": funcs, "wall_s": res["wall_s"]}
        funcs = parsed.get("functions") or {}
        all_pass = bool(test_specs) and all(bool((funcs.get(fn) or {}).get("passed")) for fn in test_specs)
        return {
            "all_pass": all_pass,
            "load_error": parsed.get("load_error"),
            "functions": funcs,
            "wall_s": res["wall_s"],
        }


# ── 文件檢查、評分與 S 臂來源範圍計算 ───────────────────────────────────────

def normalize_doc_value(val: str | None) -> str | None:
    """正規化文件宣稱值：去頭尾空白與 markdown 強調字元、壓縮內部空白；空值或佔位符回 None。"""
    if val is None:
        return None
    s = val.strip().strip("`*_").strip()
    if not s or _PLACEHOLDER_RE.search(s):
        return None
    return " ".join(s.split())


def check_doc_structural(report_text: str, required_prefixes: list[str]) -> dict:
    """B2 文件宿主檢查：每個範本行前綴皆須存在且含非空、非佔位符的值（絕不看真值）。"""
    units = extract_doc_units(report_text)
    missing: list[str] = []
    empty_or_placeholder: list[str] = []
    for pref in required_prefixes:
        if pref not in units:
            missing.append(pref)
        elif normalize_doc_value(units[pref]) is None:
            empty_or_placeholder.append(pref)
    passed = bool(required_prefixes) and not missing and not empty_or_placeholder
    return {
        "all_pass": passed,
        "missing": missing,
        "empty_or_placeholder": empty_or_placeholder,
        "checked": len(required_prefixes),
    }


def evaluate_doc_report(
    report_text: str,
    claims: list[dict],
    truth_k: dict[str, str],
) -> dict:
    """文件獨立評分：逐條比對 `report.md` 裡每條宣稱的值是否等於 `truth_k[claim_id]`。"""
    units = extract_doc_units(report_text)
    per_claim: dict[str, dict] = {}
    per_unit: dict[str, dict] = {}
    for c in claims:
        cid = c["id"]
        pref = doc_line_prefix(c["template_line"]) or c["template_line"].rstrip(": ").strip()
        raw_val = units.get(pref)
        got = normalize_doc_value(raw_val)
        exp = normalize_doc_value(truth_k[cid])
        ok = (got is not None) and (exp is not None) and (got == exp)
        entry = {
            "claim_id": cid,
            "prefix": pref,
            "passed": ok,
            "got": got,
            "expected": exp,
            "missing": pref not in units,
        }
        per_claim[cid] = entry
        per_unit[pref] = entry
    all_pass = bool(claims) and all(v["passed"] for v in per_claim.values())
    return {
        "all_pass": all_pass,
        "n_passed": sum(1 for v in per_claim.values() if v["passed"]),
        "n_total": len(claims),
        "claims": per_claim,
        "units": per_unit,
    }


def compute_doc_scope_s(
    baseline_text: str,
    prev_pages: dict[str, str],
    cur_pages: dict[str, str],
) -> dict:
    """文件 S 臂宿主端範圍計算：對每個範本行呼叫產品函式 `value_status(..., by_field=True)`。

    作法（零模型呼叫、不碰答案）：
    - 取出基線 `report.md` 每個範本行的標籤前綴與上一狀態的值 `val`。
    - 找出上一狀態（`prev_pages`）中實際包含 `val` 的所有頁面（`plain_contains(prev_txt, val)`）。
    - 對每個候選頁呼叫 `vacant_network.trace.sources.value_status(prev_txt, cur_txt, val, by_field=True)`：
      - 若無候選頁（或所有候選頁回 `None`）⇒ `no_source` ⇒ 列入允許範圍。
      - 若任一候選頁回 `"changed"`（或非 `"unchanged"`）⇒ `changed` ⇒ 列入允許範圍。
      - 否則全為 `"unchanged"` ⇒ 不列入允許範圍。
    """
    allowed: list[str] = []
    per_unit: dict[str, dict] = {}
    for line in baseline_text.splitlines():
        pref = doc_line_prefix(line)
        if pref is None:
            continue
        val = doc_line_value(line)
        norm_val = normalize_doc_value(val)
        if norm_val is None:
            per_unit[pref] = {
                "value": val,
                "candidate_pages": [],
                "per_page": {},
                "status": "no_source",
            }
            allowed.append(pref)
            continue

        cand_pages = [pg for pg, txt in sorted(prev_pages.items()) if plain_contains(txt, norm_val)]
        per_page: dict[str, str | None] = {}
        non_none: list[str] = []
        for pg in cand_pages:
            prev_txt = prev_pages[pg]
            cur_txt = cur_pages.get(pg, "")
            st = value_status(prev_txt, cur_txt, norm_val, by_field=True)
            per_page[pg] = st
            if st is not None:
                non_none.append(st)

        if not non_none:
            status = "no_source"
        elif any(st != "unchanged" for st in non_none):
            status = "changed"
        else:
            status = "unchanged"

        per_unit[pref] = {
            "value": norm_val,
            "candidate_pages": cand_pages,
            "per_page": per_page,
            "status": status,
        }
        if status != "unchanged":
            allowed.append(pref)

    return {
        "allowed_units": allowed,
        "per_unit": per_unit,
    }
