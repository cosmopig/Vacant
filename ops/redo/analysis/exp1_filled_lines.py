#!/usr/bin/env python3
"""實驗一（重評敏感度，事後）：有填行版比值與被標比例。

讀取 cA 重評後的逐行標記與 cB 原樣逐行標記，照 ops/d2/exp1_combine.py 的合併方式
（組以 A_/B_ 前綴區分；軟體＋公司＝domain 不以 football 開頭）與 summarize 判準，
對預註冊定義（repro）與 B24 兩版，各算「合併」與「軟體＋公司」兩塊、兩種分母：
  (a) 排除 status == "missing"（與 exp1_combine.py 的 combined_excl_missing、sc_excl_missing 相同）；
  (b) 只排除值為空的行（None / "" / "None"；由於 flags 檔的 rows 不帶 value 欄，
      依 (set, arm, eval==cycle, claim) 對齊對應的 score_strict 檔取 value 並驗證 status 一致）。

每塊報旗標內錯誤率、旗標外錯誤率、比值、召回、被標比例，並以組為群集做 bootstrap
（2,000 次、種子 20261128）計算比值與召回的 95% 區間。輸出只含計數與比例，不含任何值。
另從重評版 exp1_combine.py 輸出原樣抽出 combined_excl_missing 與 sc_excl_missing。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import random
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "ops" / "d2"))
import exp1_combine as COMB  # noqa: E402

CRITERION_VERBATIM = (
    "有填行上比值仍 ≥3 且被標比例 ≤30% ⇒「人工複查引導」列為候選；"
    "比值 <2 ⇒ 7.63 主要來自抓空白。"
)

DEFAULT_INPUTS = {
    "flags_a_repro": "~/dev/ops/ctl/regrade_20261128/exp1cA_flags_regrade_repro.json",
    "flags_a_b24": "~/dev/ops/ctl/regrade_20261128/exp1cA_flags_regrade_b24.json",
    "flags_b_repro": "~/dev/ops/d2_results/exp1_recompute_20261128/exp1cB_flags_repro.json",
    "flags_b_b24": "~/dev/ops/d2_results/exp1_recompute_20261128/exp1cB_flags_b24.json",
    "score_a": "~/dev/ops/ctl/regrade_20261128/exp1cA_score_strict_regrade.json",
    "score_b": "~/dev/ops/d2_results/exp1cB/score_strict.json",
    "combined_repro": "~/dev/ops/ctl/regrade_20261128/exp1_combined_regrade_repro.json",
    "combined_b24": "~/dev/ops/ctl/regrade_20261128/exp1_combined_regrade_b24.json",
}


def is_empty_value(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() in ("", "None"):
        return True
    return False


def load_score_map(path: pathlib.Path) -> dict[tuple[str, str, int, str], dict]:
    rows = json.loads(path.expanduser().read_text())["rows"]
    out: dict[tuple[str, str, int, str], dict] = {}
    for r in rows:
        k = (r["set"], r["arm"], int(r["cycle"]), r["claim"])
        if k in out:
            raise ValueError(f"duplicate score key: {k}")
        out[k] = r
    return out


def merge_with_empty_flag(
    fa_path: pathlib.Path,
    fb_path: pathlib.Path,
    sa_map: dict[tuple[str, str, int, str], dict],
    sb_map: dict[tuple[str, str, int, str], dict],
) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    audit: dict[str, dict[str, int]] = {}
    for tag, fp, smap in (("A", fa_path, sa_map), ("B", fb_path, sb_map)):
        frows = json.loads(fp.expanduser().read_text())["rows"]
        c_total = len(frows)
        c_status_missing = 0
        c_empty_val = 0
        c_missing_nonempty = 0
        c_nonmissing_empty = 0
        for r in frows:
            k = (r["set"], r["arm"], int(r["eval"]), r["claim"])
            if "value" in r:
                v = r["value"]
            else:
                sr = smap.get(k)
                if sr is None:
                    raise KeyError(f"score key missing for {tag}: {k}")
                if sr["status"] != r["status"]:
                    raise ValueError(f"status mismatch for {tag} {k}: {sr['status']} != {r['status']}")
                v = sr.get("value")
            empty = is_empty_value(v)
            st_miss = r["status"] == "missing"
            if st_miss:
                c_status_missing += 1
            if empty:
                c_empty_val += 1
            if st_miss and not empty:
                c_missing_nonempty += 1
            if not st_miss and empty:
                c_nonmissing_empty += 1
            rows.append({**r, "set": f"{tag}_{r['set']}", "_empty_value": empty})
        audit[tag] = {
            "total_rows": c_total,
            "status_missing_rows": c_status_missing,
            "empty_value_rows": c_empty_val,
            "status_missing_with_nonempty_value_rows": c_missing_nonempty,
            "nonmissing_with_empty_value_rows": c_nonmissing_empty,
            "excl_status_missing_rows": c_total - c_status_missing,
            "excl_empty_value_rows": c_total - c_empty_val,
        }
    audit["combined"] = {
        k: audit["A"][k] + audit["B"][k] for k in audit["A"]
    }
    return rows, audit


def eval_criterion(ratio: float | None, fs: float | None) -> dict:
    r_ge_3 = ratio is not None and ratio >= 3.0
    fs_le_30 = fs is not None and fs <= 0.30
    r_lt_2 = ratio is not None and ratio < 2.0
    if r_ge_3 and fs_le_30:
        outcome = "candidate_human_review_guidance"
        desc = "落入「有填行上比值仍 ≥3 且被標比例 ≤30% ⇒『人工複查引導』列為候選」"
    elif r_lt_2:
        outcome = "mainly_from_blanks"
        desc = "落入「比值 <2 ⇒ 7.63 主要來自抓空白」"
    elif r_ge_3 and not fs_le_30:
        outcome = "neither_branch_ratio_ge3_but_flagged_gt30pct"
        desc = (
            "兩條事前判準皆未落入：比值仍 ≥3（不落入「比值 <2 ⇒ 7.63 主要來自抓空白」），"
            "但被標比例 >30%（未達「人工複查引導」候選條件）"
        )
    else:
        outcome = "neither_branch_ratio_between_2_and_3"
        desc = "兩條事前判準皆未落入：比值介於 2 與 3 之間"
    return {
        "ratio_ge_3": r_ge_3,
        "flagged_share_le_30pct": fs_le_30,
        "ratio_lt_2": r_lt_2,
        "outcome": outcome,
        "description": desc,
    }


def summarize_block(rs: list[dict], *, boot: int = 2000, seed: int = 20261128) -> dict:
    base = COMB.summarize(rs, boot=boot)
    n = len(rs)
    fl = sum(r["flagged"] for r in rs)
    er = sum(r["error"] for r in rs)
    tp = sum(r["flagged"] and r["error"] for r in rs)
    in_rate = tp / fl if fl else None
    out_rate = (er - tp) / (n - fl) if n - fl else None
    ratio = (in_rate / out_rate) if (in_rate is not None and out_rate) else None
    rc = tp / er if er else None
    fs = fl / n if n else None
    erate = er / n if n else None

    assert base["units"] == n
    assert base["errors"] == er
    assert base["flagged_share"] == fs
    assert base["recall"] == rc
    assert base["error_rate_flagged"] == in_rate
    assert base["error_rate_unflagged"] == out_rate
    assert base["rate_ratio"] == ratio

    sets = sorted({r["set"] for r in rs})
    by_set = {s: [r for r in rs if r["set"] == s] for s in sets}
    rng = random.Random(seed)
    recs: list[float] = []
    rats: list[float] = []
    inf_draws = 0
    undef_ratio_draws = 0
    for _ in range(boot if sets else 0):
        pick = [rng.choice(sets) for _ in sets]
        n2 = fl2 = e2 = t2 = 0
        for s in pick:
            for r in by_set[s]:
                n2 += 1
                if r["flagged"]:
                    fl2 += 1
                    if r["error"]:
                        e2 += 1
                        t2 += 1
                elif r["error"]:
                    e2 += 1
        if e2:
            recs.append(t2 / e2)
        if fl2 > 0 and n2 - fl2 > 0:
            ir2 = t2 / fl2
            or2 = (e2 - t2) / (n2 - fl2)
            if or2 > 0:
                rats.append(ir2 / or2)
            elif ir2 > 0:
                rats.append(math.inf)
                inf_draws += 1
            else:
                undef_ratio_draws += 1
        else:
            undef_ratio_draws += 1

    recs.sort()
    rats.sort()
    rc_ci = [recs[int(0.025 * len(recs))], recs[int(0.975 * len(recs)) - 1]] if recs else None
    rc_lo95 = recs[int(0.05 * len(recs))] if recs else None
    if rats:
        r_lo = rats[int(0.025 * len(rats))]
        r_hi = rats[int(0.975 * len(rats)) - 1]
        ratio_ci = [None if math.isinf(r_lo) else r_lo, None if math.isinf(r_hi) else r_hi]
    else:
        ratio_ci = None

    et = collections.Counter((r.get("etype", r["status"]), r["flagged"]) for r in rs if r["error"])
    return {
        "units": n,
        "sets": len(sets),
        "flagged": fl,
        "flagged_share": fs,
        "errors": er,
        "error_rate": erate,
        "error_rate_flagged": in_rate,
        "error_rate_unflagged": out_rate,
        "rate_ratio": ratio,
        "rate_ratio_ci95": ratio_ci,
        "recall": rc,
        "recall_ci95": rc_ci,
        "recall_lower95_boot20261128": rc_lo95,
        "exp1_combine_recall_lower95": base["recall_lower95"],
        "exp1_combine_verdict": base["verdict"],
        "criterion_eval": eval_criterion(ratio, fs),
        "bootstrap_diag": {
            "n_boot": boot,
            "seed": seed,
            "recall_valid_draws": len(recs),
            "ratio_valid_draws": len(rats),
            "ratio_inf_draws": inf_draws,
            "ratio_undef_draws": undef_ratio_draws,
        },
        "errors_by_type": {f"{k}|{'flagged' if f else 'missed'}": c for (k, f), c in sorted(et.items())},
        "recall_by_type": {
            t: (et[(t, True)] / (et[(t, True)] + et[(t, False)])) if (et[(t, True)] + et[(t, False)]) else None
            for t in sorted({k for k, _ in et})
        },
        "plain": base["plain"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default=str(REPO / "ops/redo/audit/judge_v2v3_20261128/regrade/exp1_filled_lines.json"),
    )
    ap.add_argument(
        "--out-excl-missing",
        default=str(REPO / "ops/redo/audit/judge_v2v3_20261128/regrade/exp1_combined_regrade_excl_missing.json"),
    )
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261128)
    a = ap.parse_args()

    sa_map = load_score_map(pathlib.Path(DEFAULT_INPUTS["score_a"]))
    sb_map = load_score_map(pathlib.Path(DEFAULT_INPUTS["score_b"]))

    comb_repro = json.loads(pathlib.Path(DEFAULT_INPUTS["combined_repro"]).expanduser().read_text())
    comb_b24 = json.loads(pathlib.Path(DEFAULT_INPUTS["combined_b24"]).expanduser().read_text())

    results: dict[str, dict] = {}
    row_audit_by_ver: dict[str, dict] = {}
    check_keys = (
        "units",
        "sets",
        "flagged_share",
        "errors",
        "error_rate",
        "recall",
        "error_rate_flagged",
        "error_rate_unflagged",
        "rate_ratio",
    )

    for ver, fa_key, fb_key, comb_ref in (
        ("repro", "flags_a_repro", "flags_b_repro", comb_repro),
        ("b24", "flags_a_b24", "flags_b_b24", comb_b24),
    ):
        rows, audit = merge_with_empty_flag(
            pathlib.Path(DEFAULT_INPUTS[fa_key]),
            pathlib.Path(DEFAULT_INPUTS[fb_key]),
            sa_map,
            sb_map,
        )
        row_audit_by_ver[ver] = audit
        sc = [r for r in rows if not r["domain"].startswith("football")]
        blocks = {}
        for scope, sub, ref_key in (
            ("combined", rows, "combined_excl_missing"),
            ("software_plus_companies", sc, "sc_excl_missing"),
        ):
            excl_miss = summarize_block(
                [r for r in sub if r["status"] != "missing"], boot=a.boot, seed=a.seed
            )
            excl_empty = summarize_block(
                [r for r in sub if not r["_empty_value"]], boot=a.boot, seed=a.seed
            )
            ref = comb_ref[ref_key]
            for ck in check_keys:
                if excl_miss[ck] != ref[ck]:
                    raise AssertionError(
                        f"mismatch on {ver}.{scope}.excl_status_missing.{ck}: {excl_miss[ck]} != {ref[ck]}"
                    )
            if excl_miss["exp1_combine_verdict"] != ref["verdict"]:
                raise AssertionError(f"verdict mismatch on {ver}.{scope}")
            if excl_miss["exp1_combine_recall_lower95"] != ref["recall_lower95"]:
                raise AssertionError(f"recall_lower95 mismatch on {ver}.{scope}")
            blocks[scope] = {
                "excl_status_missing": excl_miss,
                "excl_empty_value": excl_empty,
            }
        results[ver] = blocks

    assert row_audit_by_ver["repro"] == row_audit_by_ver["b24"]

    out_doc = {
        "note": (
            "事後敏感度（2026-11-28）：實驗一重評後「有填行版」比值與被標比例。"
            "合併方式與判準照 ops/d2/exp1_combine.py（組以 A_/B_ 前綴區分）。"
            "分母 (a) excl_status_missing 排除 status=='missing'（與 exp1_combine.py 的 "
            "combined_excl_missing / sc_excl_missing 逐位一致）；"
            "分母 (b) excl_empty_value 只排除值為空（None / '' / 'None'）的行，值欄由對應 "
            "score_strict 檔依 (set, arm, eval==cycle, claim) 對齊並驗證 status 一致。"
            "本檔只含計數與比例，不含任何值。"
        ),
        "prereg_criterion_verbatim": CRITERION_VERBATIM,
        "bootstrap": {
            "method": "cluster_by_set",
            "n_boot": a.boot,
            "seed": a.seed,
            "ci_level": 0.95,
            "quantile_rule": "[sorted[int(0.025*len)], sorted[int(0.975*len)-1]]",
        },
        "inputs": {
            k: DEFAULT_INPUTS[k]
            for k in (
                "flags_a_repro",
                "flags_a_b24",
                "flags_b_repro",
                "flags_b_b24",
                "score_a",
                "score_b",
            )
        },
        "row_counts_audit": row_audit_by_ver["repro"],
        "matches_exp1_combine_excl_missing": True,
        "results": results,
    }
    pathlib.Path(a.out).write_text(json.dumps(out_doc, ensure_ascii=False, indent=1) + "\n")

    excl_doc = {
        "note": (
            "從重評敏感度 exp1_combine.py 輸出"
            "（~/dev/ops/ctl/regrade_20261128/exp1_combined_regrade_repro.json 與 _b24.json）"
            "原樣抽出之 combined_excl_missing、sc_excl_missing 兩塊。"
        ),
        "sources": {
            "repro": DEFAULT_INPUTS["combined_repro"],
            "b24": DEFAULT_INPUTS["combined_b24"],
        },
        "repro": {
            "combined_excl_missing": comb_repro["combined_excl_missing"],
            "sc_excl_missing": comb_repro["sc_excl_missing"],
        },
        "b24": {
            "combined_excl_missing": comb_b24["combined_excl_missing"],
            "sc_excl_missing": comb_b24["sc_excl_missing"],
        },
    }
    pathlib.Path(a.out_excl_missing).write_text(json.dumps(excl_doc, ensure_ascii=False, indent=1) + "\n")

    for ver in ("repro", "b24"):
        for scope in ("combined", "software_plus_companies"):
            for denom in ("excl_status_missing", "excl_empty_value"):
                b = results[ver][scope][denom]
                print(
                    f"{ver:5s} | {scope:23s} | {denom:19s} | "
                    f"n={b['units']:4d} sets={b['sets']:2d} | "
                    f"flag={b['flagged_share']:.4f} | "
                    f"in={b['error_rate_flagged']:.4f} out={b['error_rate_unflagged']:.4f} | "
                    f"ratio={b['rate_ratio']:.4f} CI95=[{b['rate_ratio_ci95'][0]:.4f}, {b['rate_ratio_ci95'][1]:.4f}] | "
                    f"recall={b['recall']:.4f} CI95=[{b['recall_ci95'][0]:.4f}, {b['recall_ci95'][1]:.4f}] | "
                    f"crit={b['criterion_eval']['outcome']}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
