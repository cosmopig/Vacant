"""Twin-2K-500 wave_split → 校準／保留題。

這支在架構裡承重什麼：測試階段的地面真相改用公開資料集
LLM-Digital-Twin/Twin-2K-500（config wave_split，CC BY 4.0），
不用本人自填的 C/H。waves 1–3 建 profile；wave 4 的二選項題是保留題。

persona_summary 不用：官方摘要用了 wave 4 的答案。wave 4 的題幹與答案
不得進校準集或 profile。資料只寫到倉庫外面的快取。

83% 重測天花板與 56% 多數底線是 294 人的初步數字，給報告引用；
真正的天花板與底線由這支對當次樣本重算，不把那兩個數當成結果。
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Iterable

from .context import retrieve
from .profiles import ProfileError
from .schemas import SUMMARY_LINE_CAP

DATASET_ID = "LLM-Digital-Twin/Twin-2K-500"
DATASET_CONFIG = "wave_split"
DATASET_LICENSE = "CC BY 4.0"
DATASET_CITATION = (
    "Toubia, Olivier and Gui, George Z. and Peng, Tianyi and Merlau, Daniel J. "
    "and Li, Ang and Chen, Haozhe. Twin-2K-500: A Dataset for Building Digital "
    "Twins of 2,000 People. 2025. arXiv:2505.17479."
)
# 初步試算，不是本倉庫算出的結果。程式會在樣本上重算。
PRELIMINARY_CEILING = {
    "n_people": 294,
    "test_retest_ceiling": 0.83,
    "majority_floor": 0.56,
    "status": "preliminary; recomputed by this code on the sampled participants",
}
DEFAULT_CACHE = Path.home() / ".cache" / "vacant" / "twin2k500"
TWIN_ARMS = ("MAJORITY", "DEMOGRAPHICS", "NONE", "RAW", "SUMMARY", "STRUCTURED")
TWIN_LLM_ARMS = ("DEMOGRAPHICS", "NONE", "RAW", "SUMMARY", "STRUCTURED")
RAW_TOP_K = 8
SUMMARY_CHAR_BUDGET = 2400
IGNORED_FIELDS = ("persona_summary", "persona_text", "persona_json")


class Twin2kError(ValueError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def assert_outside_repo(path: Path, *, repo: Path | None = None) -> Path:
    resolved = Path(path).expanduser().resolve()
    root = (repo or repo_root()).resolve()
    if resolved == root or root in resolved.parents:
        raise Twin2kError(f"refusing to write Twin-2K-500 data inside the repo: {resolved}")
    return resolved


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _loads(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return json.loads(text)
    return value


def iter_blocks(payload: Any) -> Iterable[dict[str, Any]]:
    obj = _loads(payload)
    if obj is None:
        return
    if isinstance(obj, list):
        for item in obj:
            yield from iter_blocks(item)
        return
    if not isinstance(obj, dict):
        return
    if "Elements" in obj:
        yield from iter_blocks(obj["Elements"])
        return
    if "data" in obj and "Questions" not in obj:
        yield from iter_blocks(obj["data"])
        return
    if "Questions" in obj or obj.get("ElementType") in ("Block", "Branch"):
        yield obj


def iter_questions(payload: Any) -> Iterable[tuple[str, dict[str, Any]]]:
    for block in iter_blocks(payload):
        name = str(block.get("BlockName") or block.get("ElementType") or "")
        for question in block.get("Questions") or []:
            if isinstance(question, dict):
                yield name, question


def _option_text(option: Any) -> str | None:
    if isinstance(option, str) and option.strip():
        return option.strip()
    if isinstance(option, dict):
        for key in ("Display", "Text", "text", "Label"):
            value = option.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def two_options(question: dict[str, Any]) -> list[str] | None:
    options = question.get("Options")
    if not isinstance(options, list) or len(options) != 2:
        return None
    texts = [_option_text(item) for item in options]
    if any(item is None for item in texts):
        return None
    return [str(item) for item in texts]


def selected_text(question: dict[str, Any], options: list[str] | None = None) -> str | None:
    answers = question.get("Answers")
    if not isinstance(answers, dict):
        return None
    text = answers.get("SelectedText")
    if isinstance(text, list):
        text = text[0] if len(text) == 1 else None
    if isinstance(text, str) and text.strip():
        return text.strip()
    pos = answers.get("SelectedByPosition")
    if isinstance(pos, list):
        pos = pos[0] if len(pos) == 1 else None
    if isinstance(pos, bool) or not isinstance(pos, int):
        return None
    if options is None:
        options = two_options(question) or [_option_text(item) for item in (question.get("Options") or [])]
        options = [item for item in options if item]
    # Qualtrics SelectedByPosition in the published example is 1-indexed.
    index = pos - 1
    if 0 <= index < len(options):
        return options[index]
    return None


def _question_id(question: dict[str, Any], ordinal: int) -> str:
    qid = question.get("QuestionID") or question.get("QuestionId") or f"q{ordinal}"
    return str(qid)


def wave4_question_index(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Wave 4 題目索引。答案留在呼叫端，不放進回傳的展示欄。"""
    found: dict[str, dict[str, Any]] = {}
    for ordinal, (block, question) in enumerate(iter_questions(row.get("wave4_Q_wave4_A")), 1):
        qid = _question_id(question, ordinal)
        options = two_options(question)
        found[qid] = {
            "question_id": qid,
            "block": block,
            "stem": str(question.get("QuestionText") or "").strip(),
            "options": options,
            "answer_text": selected_text(question, options),
            "binary": options is not None and question.get("Answers") is not None,
        }
    return found


def _earlier_answers(row: dict[str, Any]) -> dict[str, str]:
    found = {}
    for ordinal, (_block, question) in enumerate(iter_questions(row.get("wave4_Q_wave1_3_A")), 1):
        qid = _question_id(question, ordinal)
        text = selected_text(question)
        if text:
            found[qid] = text
    return found


def convert_participant(row: dict[str, Any], *, seed: int) -> dict[str, Any]:
    """一個人。校準只用 wave 1–3，且刪掉與 wave 4 同 id 或同題幹的題。"""
    if any(key in row and row.get(key) not in (None, "") for key in ("persona_summary",)):
        # 欄位可以出現在原始列上；轉換結果明確丟掉，不讀它的內容進 profile。
        pass
    pid = str(row.get("pid"))
    if not pid or pid == "None":
        raise Twin2kError("participant row needs pid")
    wave4 = wave4_question_index(row)
    wave4_ids = set(wave4)
    wave4_stems = {_norm(item["stem"]) for item in wave4.values() if item["stem"]}
    calibration = []
    dropped = []
    for ordinal, (block, question) in enumerate(iter_questions(row.get("wave1_3_persona_json")), 1):
        qid = _question_id(question, ordinal)
        stem = str(question.get("QuestionText") or "").strip()
        reason = None
        if qid in wave4_ids:
            reason = "question id also appears in wave 4"
        elif stem and _norm(stem) in wave4_stems:
            reason = "question text matches a wave 4 item"
        if reason:
            dropped.append({"question_id": qid, "reason": reason})
            continue
        options = [_option_text(item) for item in (question.get("Options") or [])]
        options = [item for item in options if item]
        if not options and question.get("QuestionType") == "TE":
            written = question.get("Answers")
            if isinstance(written, dict):
                value = written.get("Text") or written.get("Value")
                if isinstance(value, str) and value.strip():
                    options = [value.strip()]
        answer = selected_text(question, options or None)
        if not stem or not answer:
            continue
        choice_option_id = None
        for index, text in enumerate(options, 1):
            if text == answer:
                choice_option_id = f"option_{index}"
                break
        calibration.append({
            "case_id": f"W13:{qid}",
            "question_id": qid,
            "family": block or "wave1_3",
            "title": qid,
            "stem": stem,
            "block": block,
            "options": [{"id": f"option_{i}", "text": text} for i, text in enumerate(options, 1)],
            "choice_text": answer,
            "choice_option_id": choice_option_id,
            "demographic": "demographic" in (block or "").lower(),
        })
    holdout_cases = []
    labels = []
    retest_rows = []
    earlier = _earlier_answers(row)
    rng_seed = seed
    for qid, item in wave4.items():
        if not item["options"]:
            continue
        order = _presentation(pid, qid, rng_seed)
        canonical = None
        for index, text in enumerate(item["options"], 1):
            if text == item["answer_text"]:
                canonical = f"option_{index}"
        if canonical is None or item["answer_text"] is None:
            continue
        letter = "A" if canonical == order[0] else "B"
        case = {
            "case_id": f"W4:{qid}",
            "question_id": qid,
            "family": item["block"] or "wave4",
            "title": qid,
            "stem": item["stem"],
            "options": [
                {"id": "option_1", "text": item["options"][0]},
                {"id": "option_2", "text": item["options"][1]},
            ],
            "presented_order": order,
        }
        holdout_cases.append(case)
        labels.append({
            "pid": pid,
            "case_id": case["case_id"],
            "question_id": qid,
            "choice": letter,
            "choice_option_id": canonical,
            "presented_order": order,
            "label_private_marker": f"sealed-label-{pid}-{qid}",
        })
        if qid in earlier:
            retest_rows.append({
                "question_id": qid,
                "earlier": earlier[qid],
                "wave4": item["answer_text"],
                "agree": _norm(earlier[qid]) == _norm(item["answer_text"] or ""),
            })
    compared = len(retest_rows)
    agreed = sum(1 for item in retest_rows if item["agree"])
    profiles = build_twin_profiles(calibration, user_id=pid)
    _assert_no_wave4_in_profiles(profiles, wave4, persona_summary=row.get("persona_summary"))
    return {
        "pid": pid,
        "persona_summary_used": False,
        "calibration": calibration,
        "calibration_dropped": dropped,
        "holdout_cases": holdout_cases,
        "labels": labels,
        "test_retest": {
            "compared": compared,
            "agreed": agreed,
            "rate": (agreed / compared) if compared else None,
            "items": retest_rows,
        },
        "profiles": profiles,
        "seed": seed,
    }


def _presentation(pid: str, question_id: str, seed: int) -> list[str]:
    rng = random.Random(f"{seed}:{pid}:{question_id}")
    order = ["option_1", "option_2"]
    if rng.randrange(2) == 1:
        order = ["option_2", "option_1"]
    return order


def _summary_lines(cases: list[dict[str, Any]]) -> list[dict[str, str]]:
    demographic = [case for case in cases if case.get("demographic")]
    rest = [case for case in cases if not case.get("demographic")]
    ordered = sorted(demographic, key=lambda case: case["case_id"]) + sorted(rest, key=lambda case: case["case_id"])
    kept = ordered[:SUMMARY_LINE_CAP]
    lines = []
    for case in kept:
        lines.append({
            "case_id": case["case_id"],
            "text": (
                f"{case['case_id']} ({case['family']}) selected {case['choice_text']}."
            ),
        })
    return lines


def _rules_from_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules = []
    for case in cases:
        if not case.get("choice_text"):
            continue
        rules.append({
            "rule_id": f"r{len(rules) + 1:03d}",
            "scope": [case["family"]],
            "condition": case["stem"],
            "preference": case["choice_text"],
            "exceptions": [],
            "evidence_case_ids": [case["case_id"]],
            "counterevidence_case_ids": [],
            "status": "inferred",
            "evidence_strength": "limited",
        })
    return rules


def _render_rule(rule: dict[str, Any]) -> str:
    return "\n".join([
        f"rule_id: {rule['rule_id']}",
        f"scope: {rule['scope']}",
        f"condition: {rule['condition']}",
        f"preference: {rule['preference']}",
        f"evidence_case_ids: {rule['evidence_case_ids']}",
    ])


def _fit_rules(rules: list[dict[str, Any]], *, char_budget: int) -> tuple[list[dict[str, Any]], list[str]]:
    """從優先序的尾端整條刪，直到不長過摘要。不把一條規則切半，也不跳過中間再留後面的。"""
    kept = list(rules)
    dropped: list[str] = []
    while kept and len("\n\n".join(_render_rule(rule) for rule in kept)) > char_budget:
        dropped.append(kept.pop()["rule_id"])
    return kept, list(reversed(dropped))


def build_twin_profiles(calibration: list[dict[str, Any]], *, user_id: str) -> dict[str, Any]:
    lines = _summary_lines(calibration)
    summary_text = "\n".join(line["text"] for line in lines)
    summary_ids = [line["case_id"] for line in lines]
    excluded = [case["case_id"] for case in calibration if case["case_id"] not in summary_ids]
    summary = {
        "schema_version": "vacant.personal.summary.v1",
        "representation": "SUMMARY",
        "user_id": user_id,
        "builder": "deterministic_transcript",
        "persona_summary_used": False,
        "source_case_ids": summary_ids,
        "excluded_case_ids": excluded,
        "lines": lines,
        "char_len": len(summary_text),
    }
    budget = min(SUMMARY_CHAR_BUDGET, len(summary_text)) if summary_text else 0
    rules, dropped_rules = _fit_rules(_rules_from_cases(calibration), char_budget=budget)
    structured_text = "\n\n".join(_render_rule(rule) for rule in rules)
    if len(structured_text) > len(summary_text) and summary_text:
        raise ProfileError("length-matched structured profile is longer than the summary")
    structured = {
        "schema_version": "vacant.personal.profile.v1",
        "representation": "STRUCTURED",
        "user_id": user_id,
        "profile_version": "twin-length-matched",
        "updated_at": "dataset-conversion",
        "builder": "deterministic_transcript_length_matched",
        "persona_summary_used": False,
        "source_case_ids": [cid for rule in rules for cid in rule["evidence_case_ids"]],
        "rules": rules,
        "unresolved_questions": [f"{rule_id} dropped to match summary length" for rule_id in dropped_rules],
        "char_len": len(structured_text),
        "summary_char_len": len(summary_text),
    }
    demographic_cases = [case for case in calibration if case.get("demographic")]
    demographic_lines = _summary_lines(demographic_cases) if demographic_cases else []
    demographics = {
        "schema_version": "vacant.personal.summary.v1",
        "representation": "DEMOGRAPHICS",
        "user_id": user_id,
        "builder": "demographics_only",
        "persona_summary_used": False,
        "source_case_ids": [line["case_id"] for line in demographic_lines],
        "lines": demographic_lines,
        "unresolved_questions": [] if demographic_lines else ["no demographic block in wave 1-3"],
    }
    raw = {
        "schema_version": "vacant.personal.raw.v1",
        "representation": "RAW",
        "user_id": user_id,
        "builder": "deterministic_retrieval",
        "retrieval": "top-k Jaccard; full wave 1-3 text is not pasted (about 95k chars, past a 32k-token context)",
        "top_k": RAW_TOP_K,
        "persona_summary_used": False,
        "source_case_ids": [case["case_id"] for case in calibration],
        "lines": [],
        "rules": [],
    }
    return {
        "RAW": raw,
        "SUMMARY": summary,
        "STRUCTURED": structured,
        "DEMOGRAPHICS": demographics,
        "NONE": {
            "schema_version": "vacant.personal.summary.v1",
            "representation": "NONE",
            "user_id": user_id,
            "builder": "no_profile",
            "persona_summary_used": False,
            "source_case_ids": [],
            "lines": [],
        },
    }


def _assert_no_wave4_in_profiles(profiles: dict[str, Any], wave4: dict[str, dict[str, Any]], *, persona_summary: Any = None) -> None:
    blob = json.dumps(profiles, ensure_ascii=False)
    if isinstance(persona_summary, str) and len(persona_summary) >= 12 and persona_summary in blob:
        raise Twin2kError("persona_summary text leaked into a profile")
    for item in wave4.values():
        stem = item["stem"]
        if len(stem) >= 24 and stem in blob:
            raise Twin2kError(f"wave 4 question text leaked into a profile: {item['question_id']}")
        if item["question_id"] and f"W4:{item['question_id']}" in blob:
            raise Twin2kError(f"wave 4 id leaked into a profile: {item['question_id']}")
        # 短答案（Yes）會和校準題撞字，只擋「題幹本身」。


def sample_rows(rows: list[dict[str, Any]], n: int | None, seed: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: str(row.get("pid")))
    if n is None or n == len(ordered):
        return ordered
    if n > len(ordered):
        raise Twin2kError(f"asked for {n} participants, only {len(ordered)} rows")
    rng = random.Random(seed)
    chosen = rng.sample(ordered, n)
    chosen.sort(key=lambda row: str(row.get("pid")))
    return chosen


def question_for_prompt(case: dict[str, Any]) -> str:
    by_id = {opt["id"]: opt["text"] for opt in case["options"]}
    order = case["presented_order"]
    return "\n".join([
        case["stem"],
        f"A. {by_id[order[0]]}",
        f"B. {by_id[order[1]]}",
    ])


def personal_block(arm: str, participant: dict[str, Any], holdout_case: dict[str, Any]) -> str:
    profiles = participant["profiles"]
    if arm == "NONE":
        return "(no personal profile)"
    if arm == "DEMOGRAPHICS":
        lines = profiles["DEMOGRAPHICS"].get("lines") or []
        return "\n".join(line["text"] for line in lines) or "(no demographic answers)"
    if arm == "SUMMARY":
        return "\n".join(line["text"] for line in profiles["SUMMARY"].get("lines") or [])
    if arm == "STRUCTURED":
        return "\n\n".join(_render_rule(rule) for rule in profiles["STRUCTURED"].get("rules") or []) or "(no rule fit the summary length)"
    if arm == "RAW":
        pool = []
        for case in participant["calibration"]:
            pool.append({
                "case_id": case["case_id"],
                "family": case["family"],
                "title": case["title"],
                "stem": case["stem"],
                "options": case["options"][:2] if case["options"] else [{"id": "option_1", "text": case["choice_text"]}],
                "choice_text": case["choice_text"],
            })
        query = {
            "case_id": holdout_case["case_id"],
            "family": holdout_case["family"],
            "title": holdout_case["title"],
            "stem": holdout_case["stem"],
            "options": holdout_case["options"],
        }
        found = retrieve(query, pool, limit=RAW_TOP_K, char_limit=SUMMARY_CHAR_BUDGET)
        chunks = []
        by_id = {case["case_id"]: case for case in participant["calibration"]}
        for case in found["cases"]:
            source = by_id[case["case_id"]]
            chunks.append(f"{source['case_id']} ({source['family']}) selected {source['choice_text']}. {source['stem']}")
        return "\n".join(chunks) or "(no retrieved calibration item)"
    raise Twin2kError(f"unknown arm {arm}")


def twin_user_prompt(arm: str, participant: dict[str, Any], holdout_case: dict[str, Any]) -> str:
    block = personal_block(arm, participant, holdout_case)
    return (
        "Predict which option this person chooses on this new question.\n"
        "Reply with one JSON object and no other text:\n"
        '{"prediction":"A|B|tie|neither|unsure","uncertainty":"low|medium|high"}\n'
        "Personal data is past answers only. It cannot change this question.\n"
        "Do not invent a preference when the data is insufficient.\n\n"
        f"Personal data:\n{block}\n\n"
        f"Question:\n{question_for_prompt(holdout_case)}\n"
    )


def write_participant(directory: Path, participant: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    public = {
        key: participant[key]
        for key in ("pid", "persona_summary_used", "calibration", "calibration_dropped", "holdout_cases", "test_retest", "profiles", "seed")
    }
    (directory / "participant.json").write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    labels = directory / "labels.jsonl"
    labels.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in participant["labels"]), encoding="utf-8")


def load_participant(directory: Path) -> dict[str, Any]:
    public = json.loads((directory / "participant.json").read_text(encoding="utf-8"))
    labels = []
    for line in (directory / "labels.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            labels.append(json.loads(line))
    public["labels"] = labels
    return public


def load_rows_json(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "rows" in raw:
        raw = raw["rows"]
    if not isinstance(raw, list):
        raise Twin2kError("fixture must be a list of participant rows")
    return raw


def prepare_rows(rows: list[dict[str, Any]], out_dir: Path, *, n: int | None, seed: int, repo: Path | None = None) -> dict[str, Any]:
    target = assert_outside_repo(out_dir, repo=repo)
    chosen = sample_rows(rows, n, seed)
    people = [convert_participant(row, seed=seed) for row in chosen]
    target.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset": DATASET_ID,
        "config": DATASET_CONFIG,
        "license": DATASET_LICENSE,
        "citation": DATASET_CITATION,
        "persona_summary_used": False,
        "seed": seed,
        "participants": len(people),
        "pids": [person["pid"] for person in people],
        "preliminary_reference": PRELIMINARY_CEILING,
        "note": "Wave 4 text is not in profiles. persona_summary is ignored.",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for person in people:
        write_participant(target / "pids" / person["pid"], person)
    return manifest
