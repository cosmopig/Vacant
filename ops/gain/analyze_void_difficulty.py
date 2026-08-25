"""round83 §8 預先寫死的檢查（DECISION_20260825_ROUND83_POWER_DECOMPOSITION.md）：

    把 void 題與已量到題的難度代理量（prompt 長度、hidden test 數、
    canonical solution 行數）做比較。若 void 題顯著更難 ⇒ 分母被審查，
    failure_rate 是低估，P4 的輸入本身不可信。若沒差 ⇒ 假說作廢，照實寫作廢。

只有一種 void 型態被假說指向：`finish_reason=length` 的 EmptyResponse
（模型自己在 reasoning 裡跑掉）。HTTPError（400 等）是網路/探測事故，
不屬於「模型覺得這題太難所以吐不出答案」的機制，混進去會稀釋真訊號，
所以本工具把兩種 void 分開報，只對 length 型態做難度比較。

本工具只做讀出（read-only），不對 relay 發任何呼叫。

用法：
    python3 ops/gain/analyze_void_difficulty.py runs/g_off371_20260825 \
        [--evalplus-path PATH] [--json OUT]
    python3 ops/gain/analyze_void_difficulty.py --self-test
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

MIN_LENGTH_VOIDS_FOR_VERDICT = 5


def load_notes(d: Path) -> list[dict]:
    p = d / "notes.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.open() if l.strip()]


def load_rows(d: Path) -> list[dict]:
    return [json.loads(l) for l in (d / "rows.jsonl").open() if l.strip()]


def classify_void_reason(reason: str) -> str:
    if "finish_reason=length" in reason or "EmptyResponse" in reason:
        return "length"
    if "HTTPError" in reason:
        return "http_error"
    return "other"


def collect_voids(notes: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"length": [], "http_error": [], "other": []}
    for nt in notes:
        reason = nt.get("infra_void")
        if not reason:
            continue
        out[classify_void_reason(reason)].append(nt["task_id"])
    return out


def difficulty_proxies(records_by_task_id: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for task_id, rec in records_by_task_id.items():
        base = rec.get("base_input") or []
        plus = rec.get("plus_input") or []
        canon = rec.get("canonical_solution") or ""
        out[task_id] = {
            "prompt_len": len(rec.get("prompt") or ""),
            "hidden_test_count": len(base) + len(plus),
            "canonical_lines": len([l for l in canon.splitlines() if l.strip()]),
        }
    return out


def percentile_rank(value: float, population: list[float]) -> float:
    if not population:
        return float("nan")
    below = sum(1 for p in population if p < value)
    return below / len(population)


def compare(void_task_ids: list[str], measured_task_ids: list[str],
            proxies: dict[str, dict]) -> dict:
    measured_present = [t for t in measured_task_ids if t in proxies]
    void_present = [t for t in void_task_ids if t in proxies]
    missing_void = [t for t in void_task_ids if t not in proxies]
    metrics = ["prompt_len", "hidden_test_count", "canonical_lines"]
    result: dict = {
        "n_void": len(void_task_ids), "n_void_matched": len(void_present),
        "n_measured_matched": len(measured_present),
        "missing_from_dataset": missing_void,
        "per_metric": {},
    }
    for m in metrics:
        pop = [proxies[t][m] for t in measured_present]
        pop_median = statistics.median(pop) if pop else float("nan")
        void_vals = [proxies[t][m] for t in void_present]
        ranks = [percentile_rank(v, pop) for v in void_vals]
        result["per_metric"][m] = {
            "measured_median": pop_median,
            "void_values": void_vals,
            "void_percentile_ranks": ranks,
            "void_mean_percentile_rank": (statistics.mean(ranks) if ranks else None),
        }
    n_above_75 = 0
    for m in metrics:
        ranks = result["per_metric"][m]["void_percentile_ranks"]
        n_above_75 += sum(1 for r in ranks if r >= 0.75)
    total_checks = len(metrics) * len(void_present)
    result["n_above_p75_checks"] = n_above_75
    result["total_checks"] = total_checks
    if len(void_present) < MIN_LENGTH_VOIDS_FOR_VERDICT:
        result["verdict"] = "insufficient_data"
        result["verdict_reason"] = (
            f"length 型 void 只有 {len(void_present)} 題（含資料集比對成功者），"
            f"< 門檻 {MIN_LENGTH_VOIDS_FOR_VERDICT}，不做「顯著更難／沒差」判斷，"
            "照實寫證據不足，等 run 跑更多之後再檢查一次。"
        )
    elif total_checks and (n_above_75 / total_checks) >= 0.5:
        result["verdict"] = "systematically_harder"
        result["verdict_reason"] = (
            f"{n_above_75}/{total_checks} 次代理量檢查落在已量到題目分布的 p75 以上"
            "⇒ length 型 void 系統性偏難，分母被審查，failure_rate 是低估，"
            "P4 的輸入不可信。"
        )
    else:
        result["verdict"] = "no_difference_hypothesis_refuted"
        result["verdict_reason"] = (
            f"{n_above_75}/{total_checks} 次代理量檢查落在 p75 以上，未過半"
            "⇒ round83 §8 的假說作廢，failure_rate 沒有被系統性審查偏低的證據。"
        )
    return result


def load_dataset_records(path: str | None) -> dict[str, dict]:
    """讀官方 EvalPlus 包算難度代理量。

    ⚠ 刻意繞過 `EvalPlusMBPPLoader`：那個 loader 的 public projection 不含
    `canonical_solution`（V/GT 分離紀律，見 gain_run.py `_canonical_solutions`
    docstring），而且它的 fail-closed 建構子在傳入非預設 `path` 時要求呼叫端
    顯式帶 sha256（測試 fixture 才該這樣做）。本工具跟 `_canonical_solutions`
    走同一條路：量具/分析側直接讀原始檔，不進任何 prompt，不算作弊。
    """
    import gzip
    import os
    from vacant.codebench import EVALPLUS_DEFAULT_PATH
    p = Path(path or os.environ.get("VACANT_EVALPLUS_PATH", EVALPLUS_DEFAULT_PATH))
    out: dict[str, dict] = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[f"mbppplus_{r['task_id']}"] = r
    return out


def analyze(run_dir: Path, evalplus_path: str | None) -> dict:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    notes = load_notes(run_dir)
    rows = load_rows(run_dir)
    voids = collect_voids(notes)
    off_rows = [r for r in rows if r.get("arm") == "OFF"]
    measured_task_ids = [r["task_id"] for r in off_rows]

    records_by_task_id = load_dataset_records(evalplus_path)
    proxies = difficulty_proxies(records_by_task_id)

    out = {
        "run_dir": str(run_dir),
        "void_counts_by_reason": {k: len(v) for k, v in voids.items()},
        "n_measured": len(measured_task_ids),
        "length_type_comparison": compare(voids["length"], measured_task_ids, proxies),
    }
    if voids["http_error"]:
        out["http_error_note"] = (
            f"{len(voids['http_error'])} 題是 HTTPError（探測事故，非模型難度行為），"
            "已排除在難度比較之外，見本檔 docstring。"
        )
    return out


def _run_self_tests() -> int:
    cases = []

    def check(name, cond):
        cases.append((name, bool(cond)))

    check("classify_length", classify_void_reason(
        "plain-2 重試 4 次仍失敗：EmptyResponse: content 為空（finish_reason=length，reasoning 25307 字）"
    ) == "length")
    check("classify_http", classify_void_reason(
        "plain-2 重試 4 次仍失敗：HTTPError: HTTP Error 400: Bad Request"
    ) == "http_error")
    check("classify_other", classify_void_reason("something else entirely") == "other")

    notes = [
        {"task_id": "t1", "infra_void": "... finish_reason=length ..."},
        {"task_id": "t2", "infra_void": "... HTTPError: HTTP Error 400 ..."},
        {"task_id": "t3", "infra_void": None},
        {"task_id": "t4"},
    ]
    voids = collect_voids(notes)
    check("collect_length", voids["length"] == ["t1"])
    check("collect_http", voids["http_error"] == ["t2"])
    check("collect_ignores_non_void", "t3" not in voids["length"] + voids["http_error"] + voids["other"])

    proxies = {f"m{i}": {"prompt_len": i, "hidden_test_count": i, "canonical_lines": i}
               for i in range(1, 21)}
    hard_void_ids = ["m18", "m19", "m20"]
    r_hard = compare(hard_void_ids, list(proxies.keys())[:17], proxies)
    check("insufficient_data_below_min", r_hard["verdict"] == "insufficient_data")

    many_hard = [f"h{i}" for i in range(6)]
    proxies2 = dict(proxies)
    for i, tid in enumerate(many_hard):
        proxies2[tid] = {"prompt_len": 100 + i, "hidden_test_count": 100 + i, "canonical_lines": 100 + i}
    r_many_hard = compare(many_hard, list(proxies.keys()), proxies2)
    check("systematically_harder_detected", r_many_hard["verdict"] == "systematically_harder")

    many_random = [f"r{i}" for i in range(6)]
    proxies3 = dict(proxies)
    typical = [10, 10, 10, 10, 10, 10]
    for tid, v in zip(many_random, typical):
        proxies3[tid] = {"prompt_len": v, "hidden_test_count": v, "canonical_lines": v}
    r_no_diff = compare(many_random, list(proxies.keys()), proxies3)
    check("no_difference_when_typical", r_no_diff["verdict"] == "no_difference_hypothesis_refuted")

    r_missing = compare(["ghost1"], list(proxies.keys())[:5], proxies)
    check("missing_from_dataset_tracked", r_missing["missing_from_dataset"] == ["ghost1"])
    check("missing_excluded_from_n_matched", r_missing["n_void_matched"] == 0)

    ok = True
    for name, passed in cases:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        ok = ok and passed
    print(f"self-test: {sum(p for _, p in cases)}/{len(cases)} passed")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--evalplus-path")
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _run_self_tests()

    if not a.run_dir:
        ap.error("run_dir is required unless --self-test")

    out = analyze(Path(a.run_dir), a.evalplus_path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
