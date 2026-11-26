#!/usr/bin/env python3
"""ops.e1.build_code_chains — 從公開 EvalPlus（HumanEval+ v0.1.10／MBPP+ v0.2.0）建構 E1′ 程式碼多回合鏈。

這支在架構裡承重什麼
====================
將公開的單題程式評測題庫（HumanEval+ v0.1.10 與 MBPP+ v0.2.0，均驗證釘死 sha256）確定性地組裝為
E1′ 的 5 回合演進鏈（**本實驗延伸，our extension**）：
- 初始狀態 `solution.py`：8–10 支不同題目的 canonical solution（函式名互異、無頂層名稱碰撞），
  合併後的單一檔案必須在無網路 bwrap 沙箱中通過每一支函式的全部 plus 測試。
- 5 個回合：
  - r1–r3（`add`）：各新增 1 支不在檔內的新函式（任務文字＝該題簽章＋docstring／說明）。
  - r4（`rename`）：將檔內既有的一支函式改名為新名稱（行為不變；測資改呼叫新名；若有檔內呼叫端一併更新）。
  - r5（`confirm`）：確認回合（不需改動任何函式）。
- 每回合落盤：任務文字、當下要求的函式集合、可見測資（EvalPlus `base_input`）、隱藏測資
  （`plus_input`，獨立存於 `hidden_tests.json` 以確保隔離）與 oracle 受影響單元。
- 所有預期輸出皆於無網路 `bwrap` 沙箱中由 canonical solution 實跑計算並加逾時保護。

誠實邊界（改碼請保留）
----------------------
- **EvalPlus 無法構造「行為變更（behavior-change）」回合**：EvalPlus 只對單一規格提供測資，沒有
  「規格改變後的變體測資」，本建構器在每條鏈的 metadata 與總索引明確標記 `behavior_change_round_possible: false`。
- 多回合鏈的組裝方式屬於本實驗延伸（our extension），不可直接當成 EvalPlus 原生基準分數解讀。
- 為確保每個單元乾淨對應一支頂層函式，篩選器排除含多支頂層 `def`、非頂層純函式副作用、逾時或無法
  序列化的題目，並在索引記下篩選統計。
"""
from __future__ import annotations

import argparse
import ast
import gzip
import json
import pathlib
import random
import re
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1 import (
    CODE_CHAIN_SCHEMA,
    DEFAULT_EVALPLUS_DIR,
    EVALPLUS_SHA256,
    assert_ks1_clean,
    atomic_write_json,
    sha256_file,
    utc_now_iso,
)
from ops.e1.evaluate import compute_expected_outputs_in_sandbox, evaluate_code_source
from ops.e1.units import _bound_names_of_stmt, _node_span, _slice_lines


def _load_evalplus(evalplus_dir: pathlib.Path, *, verify_sha256: bool = True) -> tuple[list[dict], dict[str, str]]:
    """載入 HumanEval+ 與 MBPP+ gzip JSONL，並驗證釘死 sha256（預設 fail-closed）。"""
    rows: list[dict] = []
    hashes: dict[str, str] = {}
    for fname, expected_sha in EVALPLUS_SHA256.items():
        path = evalplus_dir / fname
        if not path.is_file():
            raise FileNotFoundError(f"找不到 EvalPlus 檔案：{path}")
        actual_sha = sha256_file(path)
        hashes[fname] = actual_sha
        if verify_sha256 and actual_sha != expected_sha:
            raise ValueError(f"{fname} sha256 不符：實際 {actual_sha} != 預期 {expected_sha}")
        source_tag = "humanevalplus" if "HumanEval" in fname else "mbppplus"
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                obj["_source"] = source_tag
                rows.append(obj)
    rows.sort(key=lambda r: (r["_source"], str(r["task_id"])))
    return rows, hashes


def _detect_cmp_mode(row: dict) -> str:
    """從 EvalPlus 的 test/assertion 偵測是否需要 set_equivalent 比對（例如 Mbpp/2）。"""
    ep = re.escape(str(row["entry_point"]))
    text = str(row.get("assertion") or row.get("test") or "")
    if re.search(rf"\bset\s*\(\s*{ep}\s*\(", text):
        return "set_equivalent"
    return "exact"


def _parse_problem_source(row: dict) -> dict | None:
    """解析單題的 canonical solution，拆出頂層 imports 與唯一頂層目標函式。"""
    source_tag = row["_source"]
    ep = str(row["entry_point"])
    if source_tag == "humanevalplus":
        full_src = str(row["prompt"]) + str(row["canonical_solution"])
    else:
        full_src = str(row["canonical_solution"])

    try:
        tree = ast.parse(full_src)
    except SyntaxError:
        return None

    lines = full_src.splitlines(keepends=True)
    imports: list[str] = []
    import_bindings: set[str] = set()
    func_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_nodes.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            b = _bound_names_of_stmt(node)
            if "*" in b:
                return None
            st, en = _node_span(node)
            seg = _slice_lines(lines, st, en).strip()
            imports.append(seg)
            import_bindings |= b
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        else:
            # 含額外頂層常數／類別／執行敘述的題目跳過，避免多題合併時產生隱藏頂層衝突
            return None

    if len(func_nodes) != 1 or func_nodes[0].name != ep:
        return None

    fnode = func_nodes[0]
    st, en = _node_span(fnode)
    func_src = _slice_lines(lines, st, en)
    if not func_src.endswith("\n"):
        func_src += "\n"

    # 組合不洩漏解答本體的題目文字（含簽章＋說明）
    if source_tag == "humanevalplus":
        prompt_text = str(row["prompt"]).strip()
    else:
        sig_args = ast.unparse(fnode.args)
        ret = f" -> {ast.unparse(fnode.returns)}" if fnode.returns is not None else ""
        desc = str(row.get("prompt") or "").strip().strip('"""').strip("'''").strip()
        indented_desc = "\n".join("    " + ln if ln.strip() else "" for ln in desc.splitlines())
        prompt_text = f'def {ep}({sig_args}){ret}:\n    """\n{indented_desc}\n    """\n'

    return {
        "task_id": str(row["task_id"]),
        "source": source_tag,
        "entry_point": ep,
        "imports": imports,
        "import_bindings": sorted(import_bindings),
        "func_src": func_src,
        "canonical_full_src": ("\n".join(imports) + "\n\n" + func_src) if imports else func_src,
        "prompt_text": prompt_text,
        "base_input": list(row.get("base_input") or []),
        "plus_input": list(row.get("plus_input") or []),
        "atol": float(row.get("atol") or 0.0),
        "cmp_mode": _detect_cmp_mode(row),
    }


def _combine_solution(problems: list[dict]) -> str:
    """將多道相容題目的 imports（去重）與函式定義合併為單一 `solution.py`。"""
    seen_imp: list[str] = []
    for p in problems:
        for imp in p["imports"]:
            if imp not in seen_imp:
                seen_imp.append(imp)
    parts: list[str] = []
    if seen_imp:
        parts.append("\n".join(seen_imp) + "\n")
    for p in problems:
        parts.append(p["func_src"].rstrip() + "\n")
    return "\n\n".join(parts)


def _find_in_file_callers(solution_src: str, target_fn: str) -> list[str]:
    """檢查 `solution_src` 裡有哪些「其他頂層函式」呼叫了 `target_fn`。"""
    tree = ast.parse(solution_src)
    callers: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != target_fn:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id == target_fn:
                    callers.append(node.name)
                    break
    return callers


def _bindings_compatible(selected: list[dict], cand: dict) -> bool:
    """確認加入 `cand` 不會與既有題目發生函式名或頂層綁定名稱碰撞。"""
    used_eps = {p["entry_point"] for p in selected}
    used_imps: dict[str, set[str]] = {}
    for p in selected:
        for imp in p["imports"]:
            for b in p["import_bindings"]:
                used_imps.setdefault(b, set()).add(imp)

    ep = cand["entry_point"]
    if ep in used_eps or ep in used_imps:
        return False
    # 若 cand 的 import 綁定與既有函式名撞名則排除
    for b in cand["import_bindings"]:
        if b in used_eps:
            return False
    return True


def build_code_chains(
    *,
    seed: int,
    n: int,
    out_dir: pathlib.Path,
    evalplus_dir: pathlib.Path = DEFAULT_EVALPLUS_DIR,
    min_init: int = 8,
    max_init: int = 10,
    max_plus_cases: int | None = None,
    compute_timeout_s: float = 8.0,
    verify_sha256: bool = True,
) -> dict:
    """建構 `n` 條 E1′ 程式碼鏈，每條具 8–10 支初始函式與 5 回合演進任務。"""
    if min_init < 1 or max_init < min_init:
        raise ValueError("min_init/max_init 不合法")
    rows, hashes = _load_evalplus(evalplus_dir, verify_sha256=verify_sha256)
    parsed_pool: list[dict] = []
    for r in rows:
        p = _parse_problem_source(r)
        if p is not None and len(p["base_input"]) > 0 and len(p["plus_input"]) > 0:
            parsed_pool.append(p)

    rng = random.Random(seed)
    order = list(range(len(parsed_pool)))
    rng.shuffle(order)

    # 快取單題在無網路沙箱裡算好的 expected outputs（同一題可跨鏈重用計算結果）
    computed_cache: dict[str, dict | None] = {}

    def get_computed(prob: dict) -> dict | None:
        tid = prob["task_id"]
        if tid in computed_cache:
            return computed_cache[tid]
        plus_in = prob["plus_input"] if max_plus_cases is None else prob["plus_input"][:max_plus_cases]
        res = compute_expected_outputs_in_sandbox(
            prob["canonical_full_src"],
            prob["entry_point"],
            prob["base_input"],
            plus_in,
            timeout_s=compute_timeout_s,
        )
        if not res.get("ok"):
            computed_cache[tid] = None
            return None
        computed_cache[tid] = {
            "base_cases": res["base_cases"],
            "plus_cases": res["plus_cases"],
            "atol": prob["atol"],
            "cmp_mode": prob["cmp_mode"],
        }
        return computed_cache[tid]

    out_dir.mkdir(parents=True, exist_ok=True)
    chains_summary: list[dict] = []
    cursor = 0

    for ci in range(1, n + 1):
        chain_id = f"code_{ci:03d}"
        init_count = rng.randint(min_init, max_init)
        needed = init_count + 3  # initial + r1 + r2 + r3
        selected: list[dict] = []
        selected_tests: dict[str, dict] = {}
        attempts = 0

        # 若一輪掃完池子仍需更多鏈，重新用確定性次序洗牌（允許不同鏈重用不同組合）
        while len(selected) < needed:
            if attempts > len(parsed_pool) * 3:
                raise RuntimeError(f"無法湊足 {needed} 支有效題目建構鏈 {chain_id}（僅湊到 {len(selected)}）")
            if cursor >= len(order):
                order = list(range(len(parsed_pool)))
                rng.shuffle(order)
                cursor = 0
            cand = parsed_pool[order[cursor]]
            cursor += 1
            attempts += 1
            if any(p["task_id"] == cand["task_id"] for p in selected):
                continue
            if not _bindings_compatible(selected, cand):
                continue
            comp = get_computed(cand)
            if comp is None:
                continue
            selected.append(cand)
            selected_tests[cand["entry_point"]] = comp

        init_probs = selected[:init_count]
        add_probs = selected[init_count:]  # 3 支：r1, r2, r3
        initial_solution = _combine_solution(init_probs)

        # 強制驗證：合併後的初始 solution.py 必須通過每一支初始函式的全部 plus 測試（在無網路 bwrap 沙箱中）
        init_full_specs = {
            p["entry_point"]: {
                "cases": selected_tests[p["entry_point"]]["base_cases"] + selected_tests[p["entry_point"]]["plus_cases"],
                "atol": selected_tests[p["entry_point"]]["atol"],
                "cmp_mode": selected_tests[p["entry_point"]]["cmp_mode"],
            }
            for p in init_probs
        }
        init_eval = evaluate_code_source(initial_solution, init_full_specs, per_fn_timeout_s=compute_timeout_s)
        if not init_eval["all_pass"]:
            raise RuntimeError(
                f"鏈 {chain_id} 合併後初始解未全數通過 plus 測試：{init_eval}"
            )

        # 挑選 r4 要改名的既有函式（從初始集合確定性挑選），並避免新名字碰撞
        all_names = {p["entry_point"] for p in selected}
        rename_target = init_probs[rng.randrange(len(init_probs))]
        old_name = rename_target["entry_point"]
        new_name = f"{old_name}_v2"
        suffix_idx = 2
        while new_name in all_names:
            suffix_idx += 1
            new_name = f"{old_name}_v{suffix_idx}"

        # 組裝 5 個回合
        rounds_public: list[dict] = []
        hidden_by_fn: dict[str, dict] = {}
        visible_by_fn: dict[str, dict] = {}

        for p in selected:
            ep = p["entry_point"]
            comp = selected_tests[ep]
            visible_by_fn[ep] = {
                "cases": comp["base_cases"],
                "atol": comp["atol"],
                "cmp_mode": comp["cmp_mode"],
            }
            hidden_by_fn[ep] = {
                "cases": comp["plus_cases"],
                "atol": comp["atol"],
                "cmp_mode": comp["cmp_mode"],
            }
        # r4 改名後的新函式沿用同一組 base/plus 測資
        visible_by_fn[new_name] = visible_by_fn[old_name]
        hidden_by_fn[new_name] = hidden_by_fn[old_name]

        req_fns = [p["entry_point"] for p in init_probs]

        # r1, r2, r3: 各新增一支函式
        for r_idx, add_p in enumerate(add_probs, start=1):
            ep = add_p["entry_point"]
            req_fns = [*req_fns, ep]
            task_text = (
                f"Add the following Python function to `solution.py`. "
                f"Keep all existing functions in `solution.py` working without breaking them.\n\n"
                f"```python\n{add_p['prompt_text']}\n```"
            )
            assert_ks1_clean(task_text)
            rounds_public.append({
                "round": r_idx,
                "kind": "add",
                "task_text": task_text,
                "added_function": ep,
                "added_task_id": add_p["task_id"],
                "required_functions": list(req_fns),
                "new_requirements": [ep],
                "oracle_affected_units": [ep],
                "visible_tests": {fn: visible_by_fn[fn] for fn in req_fns},
            })

        # r4: 改名既有函式
        in_file_callers = _find_in_file_callers(initial_solution, old_name)
        req_fns_r4 = [new_name if fn == old_name else fn for fn in req_fns]
        task_text_r4 = (
            f"Rename the existing function `{old_name}` in `solution.py` to `{new_name}`. "
            f"Keep its behavior completely unchanged, update any in-file callers of `{old_name}` if any exist, "
            f"and keep all other functions in `solution.py` working."
        )
        assert_ks1_clean(task_text_r4)
        oracle_r4 = list(dict.fromkeys([old_name, new_name, *in_file_callers]))
        rounds_public.append({
            "round": 4,
            "kind": "rename",
            "task_text": task_text_r4,
            "rename_from": old_name,
            "rename_to": new_name,
            "in_file_callers": in_file_callers,
            "required_functions": list(req_fns_r4),
            "new_requirements": [new_name],
            "oracle_affected_units": oracle_r4,
            "visible_tests": {fn: visible_by_fn[fn] for fn in req_fns_r4},
        })

        # r5: 確認回合（無需修改）
        task_text_r5 = (
            "Review `solution.py` and confirm that all functions currently required are present and correct. "
            "Make changes only if needed; do not alter functions that are already correct."
        )
        assert_ks1_clean(task_text_r5)
        rounds_public.append({
            "round": 5,
            "kind": "confirm",
            "task_text": task_text_r5,
            "required_functions": list(req_fns_r4),
            "new_requirements": [],
            "oracle_affected_units": [],
            "visible_tests": {fn: visible_by_fn[fn] for fn in req_fns_r4},
        })

        cdir = out_dir / chain_id
        cdir.mkdir(parents=True, exist_ok=True)
        chain_obj = {
            "schema": CODE_CHAIN_SCHEMA,
            "chain_id": chain_id,
            "kind": "code",
            "created_utc": utc_now_iso(),
            "seed": seed,
            "extension_note": (
                "Derived from public EvalPlus (HumanEval+ v0.1.10 and MBPP+ v0.2.0); "
                "multi-round chain composition is our extension."
            ),
            "evalplus_sha256": hashes,
            "behavior_change_round_possible": False,
            "behavior_change_limitation": (
                "A behavior-change round is NOT possible from EvalPlus because EvalPlus does not "
                "provide variant test suites for modified specifications."
            ),
            "initial_functions": [p["entry_point"] for p in init_probs],
            "initial_task_ids": [p["task_id"] for p in init_probs],
            "initial_solution": initial_solution,
            "initial_eval_verified": True,
            "rounds": rounds_public,
        }
        hidden_obj = {
            "schema": "vacant.e1.code_hidden_tests/1",
            "chain_id": chain_id,
            "hidden_tests_by_function": hidden_by_fn,
            "visible_tests_by_function": visible_by_fn,
        }
        atomic_write_json(cdir / "chain.json", chain_obj)
        atomic_write_json(cdir / "hidden_tests.json", hidden_obj)
        chains_summary.append({
            "chain_id": chain_id,
            "path": str(cdir.resolve()),
            "n_initial": len(init_probs),
            "n_rounds": len(rounds_public),
            "initial_functions": [p["entry_point"] for p in init_probs],
            "added_functions": [p["entry_point"] for p in add_probs],
            "rename": [old_name, new_name],
        })

    index_obj = {
        "schema": "vacant.e1.code_chain_index/1",
        "kind": "code",
        "created_utc": utc_now_iso(),
        "seed": seed,
        "n_chains": len(chains_summary),
        "pool_parsed": len(parsed_pool),
        "evalplus_sha256": hashes,
        "extension_note": (
            "Derived from public EvalPlus (HumanEval+ v0.1.10 and MBPP+ v0.2.0); "
            "multi-round chain composition is our extension."
        ),
        "behavior_change_round_possible": False,
        "chains": chains_summary,
    }
    atomic_write_json(out_dir / "index.json", index_obj)
    return index_obj


def main() -> int:
    ap = argparse.ArgumentParser(description="建構 E1′ 程式碼多回合任務鏈（衍生自 EvalPlus，屬本實驗延伸）")
    ap.add_argument("--seed", type=int, required=True, help="確定性隨機種子")
    ap.add_argument("--n", type=int, required=True, help="欲建構的鏈數")
    ap.add_argument("--out", type=pathlib.Path, required=True, help="輸出目錄")
    ap.add_argument("--evalplus-dir", type=pathlib.Path, default=DEFAULT_EVALPLUS_DIR, help="EvalPlus jsonl.gz 目錄")
    ap.add_argument("--min-init", type=int, default=8, help="每條鏈最少初始函式數（預設 8）")
    ap.add_argument("--max-init", type=int, default=10, help="每條鏈最多初始函式數（預設 10）")
    ap.add_argument("--max-plus", type=int, default=None, help="選用：每題最多取幾筆 plus_input（預設全部）")
    ap.add_argument("--timeout", type=float, default=8.0, help="單題無網路沙箱計算逾時秒數")
    ap.add_argument("--allow-custom-evalplus", action="store_true", help="僅供單元測試假題庫略過 sha256 驗證")
    args = ap.parse_args()

    idx = build_code_chains(
        seed=args.seed,
        n=args.n,
        out_dir=args.out,
        evalplus_dir=args.evalplus_dir,
        min_init=args.min_init,
        max_init=args.max_init,
        max_plus_cases=args.max_plus,
        compute_timeout_s=args.timeout,
        verify_sha256=not args.allow_custom_evalplus,
    )
    print(f"built {idx['n_chains']} code chains in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
