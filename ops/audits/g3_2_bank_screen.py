#!/usr/bin/env python3
"""G3.2 題庫相容性篩選（離線、0 model calls、只讀；工單 P20261111_1918-2）。
對 dabench 每道未見題（排除集＝g3_1 manifest tasks ∪ seen_set），以 goal.md 需求
詞彙靜態比對 checks.py 凍結能力集，輸出 COMPATIBLE/PARTIAL/INCOMPATIBLE/INCOMPLETE
排序＋top4（JSON）。能力事實來源＝凍結四檔（只讀）：checks.SUPPORTED_VERIFIERS／
KV_RECOMPUTE_TYPES／PLAIN_RECOMPUTE_TYPES；本檔不造第二份能力清單，只定義
「詞彙→(verifier, recompute type)」映射且 --selftest 逐項核對落在凍結集內（G3.1 §3
預檢查 3：verifier 不在表＝期望 unverified；I-4：未測量不是通過；假 PARTIAL 可接受、
假 COMPATIBLE 不允許）。最終裁決是 extract 預跑門（G3.2-H0），不是本排序；不讀 hidden/scorer。
用法：python3 ops/audits/g3_2_bank_screen.py [--selftest]
"""
import argparse
import json
import pathlib
import re, tempfile

BANK = pathlib.Path("/home/user1/dev/ops/ref/bm_tasks/dabench")
G31 = pathlib.Path(__file__).resolve().parents[2] / "ops/reqloop/g3_1/manifest.json"
TAG_RE = re.compile(r"@[A-Za-z_][A-Za-z0-9_]*\[")
CLASSES = ("COMPATIBLE", "PARTIAL", "INCOMPATIBLE", "INCOMPLETE")

# (詞彙, verifier, recompute type 或 None)：verifier/rtype 須在凍結集內（selftest C1 核對）
SUPPORTED: tuple[tuple[str, str, str | None], ...] = (
    (r"correlation|pearson", "kv_recomputed", "pearson2"), (r"\bmean\b|\baverage\b", "kv_recomputed", "col_stats"),
    (r"median", "kv_recomputed", "col_stats"), (r"standard deviation|std[_ ]dev", "kv_recomputed", "col_stats"),
    (r"skewness", "kv_recomputed", "col_stats"), (r"kurtosis", "kv_recomputed", "col_stats"),
    (r"missing (values?|null)", "kv_recomputed", "null_count"), (r"\btop\b", "kv_recomputed", "max_row_first"),
    (r"\bmax(?:imum)?\b", "plain_recomputed", "col_max"), (r"\bratio\b|percent", "plain_recomputed", "group_ratio_stat"),
    (r"\bunique\b|\bdistinct\b", "plain_recomputed", "unique_count"), (r"filter|keep only|retain", "rowset_filter", None),
)
# 凍結重算集無對應規則的需求家族 → 期望 unverified→UNKNOWN（誠實預記，非裁決）
UNSUPPORTED: tuple[tuple[str, str], ...] = (
    (r"p-?value|significan|two-?tailed", "hypothesis_test"), (r"imput|fill(ing)? (the )?missing", "imputation"),
    (r"normality|shapiro", "normality_test"), (r"t-?test|regress", "statistical_test"),
    (r"cluster", "clustering"), (r"forecast|predict", "ml_model"),
    (r"new feature|feature engineering|derived column", "derived_feature"), (r"outlier|z-?score", "outlier_detection"),
)

def screen(task_dir: pathlib.Path) -> dict:
    goal = task_dir / "workspace/goal.md"
    data = task_dir / "workspace/data"
    text = goal.read_text(encoding="utf-8", errors="replace") if goal.is_file() else ""
    tags = TAG_RE.findall(text)
    data_files = sorted(p.name for p in data.glob("*") if p.is_file()) if data.is_dir() else []
    sup = sorted({f"{v}:{t or '-'}" for pat, v, t in SUPPORTED if re.search(pat, text, re.I)})
    uns = sorted({label for pat, label in UNSUPPORTED if re.search(pat, text, re.I)})
    if not (tags and data_files):
        cls = "INCOMPLETE"  # 無答案項或資料檔缺失→期望全 claims UNKNOWN（G3 c-fire 教訓）
    else:
        cls = "INCOMPATIBLE" if not sup else ("PARTIAL" if uns else "COMPATIBLE")
    return {"task": task_dir.name, "class": cls, "n_tags": len(tags),
            "data_files": data_files, "supported": sup, "unsupported": uns}

def excluded_set() -> set[str]:
    m = json.loads(G31.read_text(encoding="utf-8"))
    return {t["task_id"] for t in m["tasks"]} | set(m["seen_set"])

def screen_all() -> list[dict]:
    ex = excluded_set()
    dirs = [d for d in BANK.iterdir() if d.is_dir() and d.name not in ex]
    order = {c: i for i, c in enumerate(CLASSES)}
    return sorted((screen(BANK / d.name) for d in dirs),
                  key=lambda r: (order[r["class"]], -len(r["supported"]), r["task"]))

def selftest() -> int:
    from vacant_network.reqloop import checks as C
    n = 0
    def ctl(name: str, cond: bool) -> None:
        nonlocal n
        if not cond:
            raise AssertionError(f"selftest control failed: {name}")
        n += 1
        print(f"PASS {name}")
    sets = {"kv_recomputed": set(C.KV_RECOMPUTE_TYPES), "plain_recomputed": set(C.PLAIN_RECOMPUTE_TYPES)}
    ctl("C1_mapping_in_frozen", all(v in C.SUPPORTED_VERIFIERS for _, v, _ in SUPPORTED)
        and all(t is None or t in sets.get(v, set()) for _, v, t in SUPPORTED))
    def mk(base: pathlib.Path, name: str, goal: str, with_data: bool) -> pathlib.Path:
        d = base / name / "workspace"
        d.mkdir(parents=True)
        (d / "goal.md").write_text(goal, encoding="utf-8")
        if with_data:
            (d / "data").mkdir()
            (d / "data" / "x.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        return base / name
    cases = (
        ("C2_positive_compatible", "# Task\nmean and standard deviation of col.\n## Answer format\n@mean[v]\n", True, "COMPATIBLE"),
        ("C3_negative_incompatible", "# Task\nRun a Shapiro normality test.\n## Answer format\n@p[v]\n", True, "INCOMPATIBLE"),
        ("C4_mixed_partial", "# Task\nmean of col; report the p-value.\n## Answer format\n@mean[v] @p[v]\n", True, "PARTIAL"),
        ("C5_no_data_incomplete", "# Task\nmean of col.\n## Answer format\n@mean[v]\n", False, "INCOMPLETE"),
    )
    with tempfile.TemporaryDirectory() as td:
        b = pathlib.Path(td)
        for i, (name, g, wd, want) in enumerate(cases):
            ctl(name, screen(mk(b, f"c{i}", g, wd))["class"] == want)
    rank = screen_all()
    n_bank = len([d for d in BANK.iterdir() if d.is_dir()])
    ex_in_bank = [e for e in excluded_set() if (BANK / e).is_dir()]
    ctl("C6_seen_excluded", not ({r["task"] for r in rank} & set(ex_in_bank)))
    ctl("C6_arithmetic", len(rank) == n_bank - len(ex_in_bank))
    ctl("C7_candidates_enough_for_top4", len(rank) >= 4)
    ctl("C8_deterministic", rank == screen_all())
    print(f"VERDICT: G3_2_SCREEN_SELFTEST_OK ({n} controls)")
    return 0
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        return selftest()
    rank = screen_all()
    ex = sorted(excluded_set())
    ex_in_bank = [e for e in ex if (BANK / e).is_dir()]
    out = {"schema": "vacant.g3_2_bank_screen/1", "bank": str(BANK),
           "n_bank": len([d for d in BANK.iterdir() if d.is_dir()]),
           "n_excluded_total": len(ex), "n_excluded_in_bank": len(ex_in_bank),
           "excluded_in_bank": ex_in_bank, "n_candidates": len(rank),
           "top4": [r["task"] for r in rank[:4]], "ranking": rank}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
