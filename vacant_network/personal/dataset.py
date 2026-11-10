"""題庫載入與硬條件枚舉。

這支在架構裡承重什麼：校準、保留題與端到端任務是三份資料。保留標籤
不在題庫裡，模型輸入組裝器也不接受那個路徑。合法子集只證明硬限制下
不只有一個方案，不代表哪個方案符合本人偏好。

事實欄位放在 task 頂層，與附錄 C.2 一致，不另包 constraints。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .schemas import (
    SchemaError,
    map_choice,
    validate_formal_answer,
)

OPTION_IDS = ("option_1", "option_2")
LABEL_FILE_NAMES = frozenset({"holdout_labels.jsonl", "holdout_labels.json"})


class DataError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def refuse_label_path(path: Path) -> None:
    """模型上下文與 profile 建構不准打開保留標籤檔。評分程序用自己的讀取函式。"""
    name = Path(path).name
    if name in LABEL_FILE_NAMES or "holdout_label" in name:
        raise DataError([f"refusing to read holdout labels from {path}"])


def load_bank(path: Path, *, kind: str) -> dict[str, Any]:
    refuse_label_path(path)
    raw = load_json(path)
    problems = validate_bank(raw, kind=kind)
    if problems:
        raise DataError(problems)
    return raw


def _ids(items: Iterable[dict], key: str) -> list[str]:
    return [str(item[key]) for item in items]


def validate_bank(raw: Any, *, kind: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(raw, dict):
        return ["bank must be an object"]
    if raw.get("schema_version") != "vacant.personal.bank.v1":
        problems.append("schema_version must be vacant.personal.bank.v1")
    if raw.get("kind") != kind:
        problems.append(f"kind must be {kind!r}")
    if raw.get("synthetic") is not True:
        problems.append("synthetic must be true; this bank is not a company record")
    if kind in ("calibration", "holdout"):
        cases = raw.get("cases")
        if not isinstance(cases, list) or not cases:
            return problems + ["cases must be a non-empty list"]
        seen: set[str] = set()
        for i, case in enumerate(cases):
            problems += _validate_case(case, i, seen, prefix="C" if kind == "calibration" else "H")
        if kind == "calibration":
            ids = {c["case_id"] for c in cases if isinstance(c, dict)}
            for case in cases:
                if isinstance(case, dict) and case.get("role") == "condition_reversal":
                    target = case.get("reverses")
                    if target not in ids:
                        problems.append(f"{case.get('case_id')} reverses {target!r}, which is not in this bank")
        expected = 16 if kind == "calibration" else 24
        if isinstance(cases, list) and len(cases) != expected:
            problems.append(f"{kind} bank must contain {expected} cases, found {len(cases)}")
    elif kind == "tasks":
        tasks = raw.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return problems + ["tasks must be a non-empty list"]
        seen = set()
        for i, task in enumerate(tasks):
            problems += _validate_task(task, i, seen)
        if len(tasks) != 12:
            problems.append(f"task bank must contain 12 tasks, found {len(tasks)}")
        documented = raw.get("documented_legal_subset_counts") or {}
        for task in tasks:
            if not isinstance(task, dict) or "task_id" not in task:
                continue
            try:
                got = len(legal_subsets(task))
            except DataError as exc:
                problems.append(f"{task.get('task_id')}: {exc}")
                continue
            want = documented.get(task["task_id"])
            if want is not None and got != want:
                problems.append(
                    f"{task['task_id']}: legal subsets {got} != documented {want}"
                )
            if got < 2:
                problems.append(f"{task['task_id']}: fewer than 2 legal subsets ({got})")
    else:
        problems.append(f"unknown bank kind {kind!r}")
    return problems


def _validate_case(case: Any, index: int, seen: set[str], *, prefix: str) -> list[str]:
    problems: list[str] = []
    where = f"cases[{index}]"
    if not isinstance(case, dict):
        return [f"{where} must be an object"]
    for banned in ("choice", "reason", "label", "human_acceptance", "prediction"):
        if banned in case:
            problems.append(f"{where} must not carry {banned}; labels live outside the repo")
    for key in ("case_id", "family", "title", "stem"):
        if not isinstance(case.get(key), str) or not case[key].strip():
            problems.append(f"{where}.{key} must be a non-empty string")
    cid = case.get("case_id")
    if isinstance(cid, str):
        if not cid.startswith(prefix):
            problems.append(f"{where}.case_id must start with {prefix!r}")
        if cid in seen:
            problems.append(f"duplicate case_id {cid}")
        seen.add(cid)
    if case.get("family") not in ("F1", "F2", "F3"):
        problems.append(f"{where}.family must be F1, F2, or F3")
    options = case.get("options")
    if not isinstance(options, list) or len(options) != 2:
        problems.append(f"{where}.options must be exactly two options")
    else:
        ids = [o.get("id") if isinstance(o, dict) else None for o in options]
        if ids != list(OPTION_IDS):
            problems.append(f"{where}.options must be option_1 then option_2")
        for j, opt in enumerate(options):
            if not isinstance(opt, dict) or not isinstance(opt.get("text"), str) or not opt["text"].strip():
                problems.append(f"{where}.options[{j}].text must be a non-empty string")
    return problems


def _int_field(task: dict, key: str, where: str, problems: list[str]) -> None:
    value = task.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        problems.append(f"{where}.{key} must be a non-negative integer")


def _validate_task(task: Any, index: int, seen: set[str]) -> list[str]:
    problems: list[str] = []
    where = f"tasks[{index}]"
    if not isinstance(task, dict):
        return [f"{where} must be an object"]
    required = {
        "task_id", "family", "title", "synthetic", "facts", "task_instruction",
        "max_person_hours", "max_cost_units", "min_options", "max_options",
        "required_outputs", "required_option_ids", "choice_groups", "options",
    }
    extra = sorted(set(task) - required)
    if extra:
        problems.append(f"{where}: unknown key(s) {extra}")
    tid = task.get("task_id")
    if not isinstance(tid, str) or not tid.startswith("T"):
        problems.append(f"{where}.task_id must start with T")
    elif tid in seen:
        problems.append(f"duplicate task_id {tid}")
    else:
        seen.add(tid)
    if task.get("family") not in ("F1", "F2", "F3"):
        problems.append(f"{where}.family must be F1, F2, or F3")
    if task.get("synthetic") is not True:
        problems.append(f"{where}.synthetic must be true")
    for key in ("title", "facts", "task_instruction"):
        if not isinstance(task.get(key), str) or not task[key].strip():
            problems.append(f"{where}.{key} must be a non-empty string")
    for key in ("max_person_hours", "max_cost_units", "min_options", "max_options"):
        _int_field(task, key, where, problems)
    if isinstance(task.get("min_options"), int) and isinstance(task.get("max_options"), int):
        if task["min_options"] > task["max_options"]:
            problems.append(f"{where}.min_options exceeds max_options")
    if task.get("required_outputs") != ["memo.md", "plan.json"]:
        problems.append(f"{where}.required_outputs must be ['memo.md', 'plan.json']")
    options = task.get("options")
    if not isinstance(options, list) or not options:
        return problems + [f"{where}.options must be a non-empty list"]
    option_ids: list[str] = []
    by_id: dict[str, dict] = {}
    for j, opt in enumerate(options):
        owhere = f"{where}.options[{j}]"
        if not isinstance(opt, dict):
            problems.append(f"{owhere} must be an object")
            continue
        keys = {"id", "description", "person_hours", "cost_units", "depends_on"}
        extra_o = sorted(set(opt) - keys)
        if extra_o:
            problems.append(f"{owhere}: unknown key(s) {extra_o}")
        oid = opt.get("id")
        if not isinstance(oid, str) or not oid:
            problems.append(f"{owhere}.id must be a non-empty string")
        elif oid in by_id:
            problems.append(f"{where} duplicate option id {oid}")
        else:
            option_ids.append(oid)
            by_id[oid] = opt
        if not isinstance(opt.get("description"), str) or not opt.get("description", "").strip():
            problems.append(f"{owhere}.description must be a non-empty string")
        for key in ("person_hours", "cost_units"):
            value = opt.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                problems.append(f"{owhere}.{key} must be a non-negative integer, not a boolean")
        deps = opt.get("depends_on")
        if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
            problems.append(f"{owhere}.depends_on must be a list of option ids")
    known = set(option_ids)
    for oid, opt in by_id.items():
        for dep in opt.get("depends_on") or []:
            if dep not in known:
                problems.append(f"{where} option {oid} depends_on unknown id {dep}")
    if _has_cycle(by_id):
        problems.append(f"{where} dependency graph has a cycle")
    required_ids = task.get("required_option_ids")
    if not isinstance(required_ids, list) or not all(isinstance(x, str) for x in required_ids):
        problems.append(f"{where}.required_option_ids must be a list of strings")
    else:
        for rid in required_ids:
            if rid not in known:
                problems.append(f"{where} required option {rid} does not exist")
    groups = task.get("choice_groups")
    if not isinstance(groups, list) or not groups:
        problems.append(f"{where}.choice_groups must be a non-empty list")
    else:
        for g, group in enumerate(groups):
            gwhere = f"{where}.choice_groups[{g}]"
            if not isinstance(group, dict):
                problems.append(f"{gwhere} must be an object")
                continue
            if sorted(group) != ["min_count", "option_ids"]:
                problems.append(f"{gwhere} keys must be option_ids and min_count")
            ids = group.get("option_ids")
            if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x in known for x in ids):
                problems.append(f"{gwhere}.option_ids must be existing option ids")
            count = group.get("min_count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                problems.append(f"{gwhere}.min_count must be an integer >= 1")
            elif isinstance(ids, list) and count > len(set(ids)):
                problems.append(f"{gwhere}.min_count exceeds the group size")
    return problems


def _has_cycle(by_id: dict[str, dict]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        mark = state.get(node, 0)
        if mark == 1:
            return True
        if mark == 2:
            return False
        state[node] = 1
        for dep in by_id[node].get("depends_on") or []:
            if dep in by_id and visit(dep):
                return True
        state[node] = 2
        return False

    return any(visit(node) for node in by_id if state.get(node, 0) == 0)


def legal_subsets(task: dict[str, Any]) -> list[list[str]]:
    """硬限制下的選項子集。順序不在這裡枚舉；sequence 由 checker 另驗拓撲。

    不指定哪個子集才是本人要的。依賴未閉合、超額、缺必選或缺群組都不算合法。
    """
    options = task["options"]
    ids = [opt["id"] for opt in options]
    by_id = {opt["id"]: opt for opt in options}
    required = set(task["required_option_ids"])
    groups = task["choice_groups"]
    found: list[list[str]] = []
    n = len(ids)
    for mask in range(1 << n):
        selected = [ids[i] for i in range(n) if mask & (1 << i)]
        if not (task["min_options"] <= len(selected) <= task["max_options"]):
            continue
        chosen = set(selected)
        if not required <= chosen:
            continue
        if any(
            len(chosen & set(group["option_ids"])) < group["min_count"]
            for group in groups
        ):
            continue
        if any(dep not in chosen for oid in selected for dep in by_id[oid]["depends_on"]):
            continue
        cost = sum(by_id[oid]["cost_units"] for oid in selected)
        hours = sum(by_id[oid]["person_hours"] for oid in selected)
        if cost > task["max_cost_units"] or hours > task["max_person_hours"]:
            continue
        found.append(selected)
    return found


def topo_sequence(task: dict[str, Any], selected: list[str]) -> list[str]:
    """依 depends_on 排一個合法 sequence。同層以題目表上的 id 順序打破平手。"""
    by_id = {opt["id"]: opt for opt in task["options"]}
    order = {opt["id"]: i for i, opt in enumerate(task["options"])}
    remaining = set(selected)
    seq: list[str] = []
    while remaining:
        ready = [
            oid for oid in remaining
            if all(dep not in remaining for dep in by_id[oid]["depends_on"])
        ]
        if not ready:
            raise DataError([f"{task['task_id']}: cycle while ordering {sorted(remaining)}"])
        ready.sort(key=lambda oid: order[oid])
        pick = ready[0]
        seq.append(pick)
        remaining.remove(pick)
    return seq


def structural_plan(task: dict[str, Any]) -> dict[str, Any]:
    """字典序最小的合法子集。這是管線見證，不是本人偏好，也不是模型答案。"""
    subsets = legal_subsets(task)
    if not subsets:
        raise DataError([f"{task['task_id']}: no legal subset"])
    chosen = min(subsets, key=lambda row: tuple(row))
    by_id = {opt["id"]: opt for opt in task["options"]}
    return {
        "task_id": task["task_id"],
        "selected_option_ids": list(chosen),
        "sequence": topo_sequence(task, chosen),
        "total_cost_units": sum(by_id[oid]["cost_units"] for oid in chosen),
        "total_person_hours": sum(by_id[oid]["person_hours"] for oid in chosen),
        "validation": [{
            "metric": "管線 fixture：所選項目的成本與人時可重算",
            "method": "由選項表加總，不讀模型",
            "decision_rule": "合計不符或超出上限即 FAIL；這不判斷方案好不好",
        }],
        "stop_condition": "這是管線 fixture 的停止條件欄位，不是本人決定的停止條件。",
        "assumptions": ["合成題目的數字就是事實；不外推到真實費用。"],
        "tradeoff": "採用字典序最小的合法子集只為了讓檢查器有一份可重算的結構，犧牲的是任何實質取捨。",
    }


def structural_memo(task: dict[str, Any], plan: dict[str, Any]) -> str:
    selected = "、".join(plan["selected_option_ids"])
    return (
        f"這是管線 fixture，不是本人偏好，也不是模型試驗結果。"
        f"任務 {task['task_id']} 的結構見證選了 {selected}。"
        f"硬條件見題目；此備忘錄不宣稱這些工作值得採用。"
    )


def case_by_id(bank: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case["case_id"]: case for case in bank["cases"]}


def task_by_id(bank: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {task["task_id"]: task for task in bank["tasks"]}


def load_answers(path: Path) -> list[dict[str, Any]]:
    """正式答案，一行一筆。空白模板（含 _blank_form 或 null choice）整檔拒絕。"""
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        raise DataError([f"{path} is empty"])
    seen: set[str] = set()
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {lineno}: {exc.msg}")
            continue
        if isinstance(obj, dict) and obj.get("_blank_form") is True:
            problems.append(f"line {lineno}: blank form cannot be imported as answers")
            continue
        row_problems = validate_formal_answer(obj)
        if row_problems:
            problems.append(f"line {lineno}: " + "; ".join(row_problems))
            continue
        if obj["case_id"] in seen:
            problems.append(f"line {lineno}: duplicate case_id {obj['case_id']}")
        seen.add(obj["case_id"])
        rows.append(obj)
    if problems:
        raise DataError(problems)
    return rows


def join_answers(cases: dict[str, dict[str, Any]], answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用 case_id 把題幹、兩個選項、展示順序與映回的穩定 ID 接在一起。

    不能只把「C01 選 A」交給模型。缺題或題庫沒有該 id 都拒絕，不補造。
    """
    joined: list[dict[str, Any]] = []
    problems: list[str] = []
    for answer in answers:
        case = cases.get(answer["case_id"])
        if case is None:
            problems.append(f"answer {answer['case_id']} has no case in the calibration bank")
            continue
        try:
            stable = map_choice(answer["choice"], answer["presented_order"])
        except SchemaError as exc:
            problems.append(str(exc))
            continue
        option_text = {opt["id"]: opt["text"] for opt in case["options"]}
        joined.append({
            "case_id": case["case_id"],
            "family": case["family"],
            "title": case["title"],
            "stem": case["stem"],
            "options": [
                {"id": opt["id"], "text": opt["text"]}
                for opt in case["options"]
            ],
            "presented_order": list(answer["presented_order"]),
            "choice": answer["choice"],
            "choice_option_id": stable,
            "choice_text": option_text.get(stable) if stable else None,
            "reason": answer.get("reason") or "",
            "switch_condition": answer.get("switch_condition") or "",
            "seconds_spent": answer.get("seconds_spent"),
            "answered_at": answer["answered_at"],
            "role": case.get("role"),
            "reverses": case.get("reverses"),
        })
    if problems:
        raise DataError(problems)
    return joined


def assert_banks_separated(calibration: dict[str, Any], holdout: dict[str, Any], tasks: dict[str, Any]) -> list[str]:
    c_ids = {case["case_id"] for case in calibration["cases"]}
    h_ids = {case["case_id"] for case in holdout["cases"]}
    t_ids = {task["task_id"] for task in tasks["tasks"]}
    problems = []
    overlap = c_ids & h_ids
    if overlap:
        problems.append(f"calibration and holdout share ids {sorted(overlap)}")
    if c_ids & t_ids or h_ids & t_ids:
        problems.append("task ids overlap comparison cases")
    return problems
