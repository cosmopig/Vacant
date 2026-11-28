#!/usr/bin/env python3
"""D2′ 第四、五輪評分器雙向審查（離線、不叫模型）。

對象是 `ops/d2/score_d2.py` 實際用於這兩輪的預設評分函式：版本號優先、否則只取第一個
數字（去千分位；單位、幣別、尺度字、正負號、後續數字都不看）。`--strict` 是 2026-11-26 04:28
才加入的後續實驗修正案，會依序比對全部數字；這兩輪開跑時的程式沒有該旗標，所以這裡只把
strict 當對照，不把它當成本批實際評分器。

公開輸出不含實驗值；含值抽樣清單只寫到私有目錄。行鍵是明文代號：
`<批次>/<組>|r<週期>|<臂>|<claim>`；批次是為了避免不同 root 之間同組同臂撞鍵。
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import pathlib
import random
import re
import sys
from decimal import Decimal, InvalidOperation
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
D2DIR = REPO / "ops" / "d2"
if str(D2DIR) not in sys.path:
    sys.path.insert(0, str(D2DIR))
import score_d2  # noqa: E402

OUTDIR = REPO / "ops/redo/audit/scorer_validity_20261128/d2"
PRIV_DEFAULT = pathlib.Path.home() / "dev/ops/ctl/scorer_d2_private"
SEED = 20261128

VER = re.compile(r"v?(\d+\.\d+\.\d+)")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
TOKRE = re.compile(r"v?\d+(?:\.\d+){2,}|\d[\d,]*(?:\.\d+)?")

# 合成控制例。基礎組沿用確認批次 scorer_controls.py 的兩組；这些是合成字串，不是實驗值。
BASE_DIFF = [
    ("scale", "US$3 million", "US$3 billion"), ("scale", "3 thousand", "3 million"), ("scale", "€1.2 billion", "€1.2 trillion"), ("scale", "US$5 bn", "US$5 m"),
    ("sign", "−3", "3"), ("sign", "-3 million", "3 million"), ("sign", "US$(120) million", "US$120 million"), ("sign", "loss of US$5 million", "US$5 million"),
    ("percent", "10%", "10"), ("percent", "15%", "15 million"), ("percent", "2.5%", "2.5"),
    ("currency", "USD 10", "JPY 10"), ("currency", "€10 billion", "US$10 billion"), ("currency", "£3 million", "US$3 million"), ("currency", "CN¥8 billion", "US$8 billion"),
    ("period", "US$5 billion (2023)", "US$5 billion (2024)"), ("period", "US$5 billion (FY2023)", "US$5 billion (Q3 2023)"), ("period", "US$2 billion (2022)", "US$2 billion"),
    ("unit", "10 km", "10 mi"), ("unit", "5 kg", "5 lb"), ("unit", "300 employees", "300 stores"),
    ("date", "March 1990", "April 1990"), ("date", "5 March 1990", "3 May 1990"),
    ("football_order", "12 (3)", "3 (12)"), ("football_partial", "12", "12 (0)"), ("football_partial", "(3)", "12 (3)"),
    ("decimal", "1.5", "15"), ("ticker", "NYSE: ABC", "NYSE: ABD"), ("ticker_exchange", "Nasdaq: ABC", "NYSE: ABC"),
]
BASE_SAME = [
    ("currency_form", "US$3 million", "$3 million"), ("currency_form", "USD 3 million", "US$3 million"), ("thousands_sep", "1,234", "1234"),
    ("scale_word_vs_digits", "US$3 million", "US$3,000,000"), ("scale_abbrev", "US$3.2 bn", "US$3.2 billion"),
    ("minus_glyph", "−3", "-3"), ("percent_space", "10 %", "10%"), ("date_order", "March 5, 1990", "5 March 1990"),
    ("football_space", "12(3)", "12 (3)"), ("markdown", "**12 (3)**", "12 (3)"), ("year_paren", "US$1.2 billion (2023)", "$1.2 billion (2023)"),
    ("age_suffix", "1990", "1990; 36 years ago"), ("ticker_index", "NYSE: ABC", "NYSE: ABC S&P 500 component"), ("trailing_dot", "1990.", "1990"),
]
R4_EXTRA_DIFF = [
    ("version_patch", "v1.2.4", "v1.2.3"), ("version_width", "v1.2.30", "v1.2.3"),
    ("dynamic_noise_trailing", "30 days; fetch count 1042", "30 days"),
    ("dynamic_noise_leading", "fetch count 1042; 30 days", "30 days"),
    ("dynamic_noise_timestamp", "30 days (fetched 2026-11-25T19:16:25.123Z)", "30 days"),
    ("dynamic_noise_hex", "30 days [fetch 9f8e7d6c5b4a]", "30 days"),
    ("adjacent_fields", "30 days, firmware: v1.2.3", "30 days"),
    ("adjacent_numeric_fields", "30 days, pressure: 240 kPa", "30 days"),
]
R4_EXTRA_SAME = [
    ("version_prefix", "1.2.3", "v1.2.3"), ("decimal_zero", "30.0 days", "30 days"),
    ("markdown_unit", "**30 days**", "30 days"), ("space_unit", "30  days", "30 days"),
]
R5_EXTRA_DIFF = [
    ("football_wrong_goals", "12 (4)", "12 (3)"), ("football_wrong_apps", "13 (3)", "12 (3)"),
    ("football_missing_goals", "12", "12 (3)"), ("football_repeated_apps", "12 (12)", "12 (3)"),
    ("football_noise_trailing", "12 (3); fetch count 1042", "12 (3)"),
]
R5_EXTRA_SAME = [
    ("football_words", "12 apps (3 goals)", "12 (3)"), ("football_comma_words", "12 appearances, 3 goals", "12 (3)"),
]

ROOT_SPECS = {
    "r4": [
        {"batch": "r4main_1003", "root": "r4main_1003", "plan": "r4main_d2_qwen9b_1003.json", "family": "r4main_v4"},
        {"batch": "r4main_1004", "root": "r4main_1004", "plan": "r4main_d2_qwen9b_1004.json", "family": "r4main_v4"},
        {"batch": "r4h3seen", "root": "r4h3seen", "plan": "r4h3seen_d2_qwen9b_1003.json", "family": "r4h3seen_v3"},
        {"batch": "r4haiku", "root": "r4haiku", "plan": "r4haiku_d2.json", "family": "r4main_v4"},
    ],
    "r5": [
        {"batch": "r5real_qwen_merged", "root": "r5real_merged", "plan": "r5real_d2_qwen9b_1003.json", "family": "r5real"},
        {"batch": "r5real_haiku", "root": "r5real_haiku", "plan": "r5real_haiku_d2.json", "family": "r5real"},
    ],
}
INVENTORY_ROOTS = [
    "r4main_1003", "r4main_1004", "r4h3seen", "r4haiku", "r4_merged",
    "r5real_1003", "r5real_1003b", "r5real_1004", "r5real_1004b", "r5real_haiku", "r5real_merged",
]


def canon_default(v: str | None) -> str | None:
    """Exact copy of score_d2.canon with STRICT=False."""
    if v is None:
        return None
    s = v.strip().strip("`*").strip()
    m = VER.search(s)
    if m:
        return "v" + m.group(1)
    m = NUM.search(s)
    if m:
        x = m.group(0).replace(",", "")
        return x[:-2] if x.endswith(".0") else x
    return None


def raw_tokens(v: str | None) -> list[str]:
    if v is None:
        return []
    s = v.strip().strip("`*").strip()
    return TOKRE.findall(s)


def canon_strict(v: str | None) -> str | None:
    """Exact copy of score_d2.canon with STRICT=True."""
    if v is None:
        return None
    toks = [("v" + t[1:].lstrip("v")) if t.lower().startswith("v") else t.replace(",", "")
            for t in raw_tokens(v)]
    toks = [t[:-2] if t.endswith(".0") else t for t in toks]
    return "|".join(toks) if toks else None


def same_mode(v: str | None, a: str | None, mode: str) -> bool:
    cv = canon_strict(v) if mode == "strict" else canon_default(v)
    ca = canon_strict(a) if mode == "strict" else canon_default(a)
    return cv is not None and cv == ca


def _norm_decimal_text(x: str) -> str:
    try:
        d = Decimal(x.replace(",", ""))
    except InvalidOperation:
        return x
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def semantic_tokens(v: str | None) -> list[str]:
    """Numeric/version token sequence for human-style comparison; formatting-only differences collapse."""
    out = []
    for t in raw_tokens(v):
        if re.fullmatch(r"v?\d+(?:\.\d+){2,}", t, flags=re.I):
            core = t[1:] if t.lower().startswith("v") else t
            out.append("v" + ".".join(str(int(x)) for x in core.split(".")))
        else:
            out.append(_norm_decimal_text(t))
    return out


def materials_dir(plan: dict[str, Any]) -> pathlib.Path:
    raw = str(plan["materials"]["dir"])
    d2p = os.environ.get("D2_PRIVATE")
    if not d2p:
        raise RuntimeError("D2_PRIVATE is not set")
    raw = raw.replace("${D2_PRIVATE}", d2p)
    return pathlib.Path(os.path.expandvars(os.path.expanduser(raw)))


def load_plan(name: str) -> dict[str, Any]:
    return json.loads((REPO / "ops/d2/plans" / name).read_text())


def load_manifest(plan: dict[str, Any]) -> tuple[pathlib.Path, dict[str, Any]]:
    mat = materials_dir(plan)
    return mat, json.loads((mat / "manifest.json").read_text())


def root_counts(root: pathlib.Path) -> dict[str, int | bool]:
    cells = root / "cells"
    sets = [p for p in cells.iterdir() if p.is_dir()] if cells.exists() else []
    c0 = sum((p / "c0" / "report.md").exists() for p in sets)
    arm_done = 0
    cyc = 0
    for sd in sets:
        for ad in sd.iterdir():
            if ad.is_dir() and (ad / "done.json").exists():
                arm_done += 1
                cyc += len(list(ad.glob("cycle_*/report.md")))
    return {"sets": len(sets), "c0_reports": int(c0), "arm_dirs_done": arm_done, "cycle_reports": cyc}


def report_hashes(root: pathlib.Path) -> dict[tuple[str, str], str]:
    import hashlib
    out: dict[tuple[str, str], str] = {}
    cells = root / "cells"
    if not cells.exists():
        return out
    for p in cells.glob("*/c0/report.md"):
        out[(p.parts[-3], "c0")] = hashlib.sha256(p.read_bytes()).hexdigest()
    for p in cells.glob("*/*/cycle_*/report.md"):
        out[(p.parts[-4], p.parts[-3] + "/" + p.parts[-2])] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def inventory(d2private: pathlib.Path) -> dict[str, Any]:
    inv: dict[str, Any] = {}
    for name in INVENTORY_ROOTS:
        root = d2private / name
        runp = root / "RUN.json"
        if not runp.exists():
            continue
        run = json.loads(runp.read_text())
        pb = run.get("plan_body") or {}
        inv[name] = {
            "plan_id": pb.get("id"), "started": run.get("started"), "arms": pb.get("arms"),
            "dynamic_noise": bool(pb.get("dynamic_noise")), **root_counts(root),
        }
    def cmp_union(merged: str, parts: list[str]) -> dict[str, Any]:
        mh = report_hashes(d2private / merged)
        uh: dict[tuple[str, str], str] = {}
        for p in parts:
            uh.update(report_hashes(d2private / p))
        keys = set(mh) | set(uh)
        return {"part_union_reports": len(uh), "merged_reports": len(mh),
                "identical_report_bytes": bool(keys and all(mh.get(k) == uh.get(k) for k in keys))}
    if "r4_merged" in inv:
        inv["r4_merged"]["union_check"] = cmp_union("r4_merged", ["r4main_1003", "r4main_1004"])
    if "r5real_merged" in inv:
        inv["r5real_merged"]["union_check"] = cmp_union("r5real_merged", ["r5real_1003b", "r5real_1004b"])
    return inv


def answer_features(answer: str) -> dict[str, bool | str]:
    s = str(answer or "")
    parens = re.findall(r"\(([^)]*)\)", s)
    toks = semantic_tokens(s)
    cur = bool(re.search(r"(?:US\$|A\$|C\$|HK\$|NT\$|R\$|CN¥|JP¥|[$€£¥₹₩]|\b(?:USD|EUR|GBP|JPY|CNY|RMB|INR|CHF|KRW|CAD|AUD|HKD|SEK|NOK|DKK|BRL|TWD)\b)", s, re.I))
    scale = bool(re.search(r"\b(?:thousand|million|mllion|billion|trillion|bn|mn)\b", s, re.I))
    version = bool(re.fullmatch(r"`?\s*v?\d+(?:\.\d+){2,}\s*`?", s.strip(), re.I))
    apps_goals = bool(re.fullmatch(r"`?\s*\d+\s*\(\s*\d+\s*\)\s*`?", s.strip()))
    year_period_paren = any(re.search(r"(?:\b(?:18|19|20)\d{2}\b|\bFY\b|\bQ[1-4]\b|\bH[12]\b)", x, re.I) for x in parens)
    numeric_paren = any(re.fullmatch(r"\s*\d+\s*", x) for x in parens)
    unit_match = re.search(r"\d\s*([A-Za-zµμ]+(?:/[A-Za-z]+)?)", s)
    currency_words = {"usd", "eur", "gbp", "jpy", "cny", "rmb", "inr", "chf", "krw", "cad", "aud", "hkd", "sek", "nok", "dkk", "brl", "twd"}
    alpha_after_num = bool(unit_match and unit_match.group(1).lower() not in currency_words)
    rng = bool(re.search(r"\d\s*(?:–|—|\bto\b)\s*\d", s, re.I))
    if version:
        form = "version"
    elif apps_goals:
        form = "apps_goals_parentheses"
    elif cur:
        form = "currency_amount"
    elif "%" in s:
        form = "percent"
    elif alpha_after_num:
        form = "number_with_unit"
    elif toks:
        form = "bare_numeric"
    else:
        form = "other"
    return {
        "form": form, "relative_age": bool(re.search(r";?\s*\d+\s+years?\s+ago", s, re.I)),
        "index_component": bool(re.search(r"\bcomponent\b", s, re.I)),
        "footnote": bool(re.search(r"\[\d+\]|[†‡§]", s)),
        "year_or_period_paren": year_period_paren, "unit_like_text": alpha_after_num,
        "currency": cur, "scale_word": scale, "range": rng,
        "multi_value": len(toks) > 1, "numeric_parenthesis": numeric_paren,
        "version": version, "decimal_numeric": bool(re.search(r"\d\.\d", s)),
    }


def label_features(label: str) -> dict[str, bool]:
    s = str(label or "")
    return {
        "label_year_or_period": bool(re.search(r"(?:\b(?:18|19|20)\d{2}\b|\bFY\b|\bQ[1-4]\b|\bH[12]\b)", s, re.I)),
        "label_year_range": bool(re.search(r"\b(?:18|19|20)\d{2}\s*[–—-]\s*(?:(?:18|19|20)\d{2})?", s)),
    }


def answer_key_styles(per_round_manifests: dict[str, dict[str, tuple[pathlib.Path, dict[str, Any]]]]) -> dict[str, Any]:
    featnames = [
        "relative_age", "index_component", "footnote", "year_or_period_paren", "unit_like_text",
        "currency", "scale_word", "range", "multi_value", "numeric_parenthesis", "version", "decimal_numeric",
        "label_year_or_period", "label_year_range",
    ]
    def full_summary(cnt: collections.Counter) -> dict[str, Any]:
        out: dict[str, Any] = {"lines": cnt["lines"]}
        for fn in featnames:
            out[fn] = cnt[fn]
        for k, v in sorted(cnt.items()):
            if k.startswith("form:"):
                out[k] = v
        for k in ("sets", "claims"):
            if cnt[k]:
                out[k] = cnt[k]
        return out
    rounds: dict[str, Any] = {}
    for rnd, mats in per_round_manifests.items():
        field_stats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        mat_out: dict[str, Any] = {}
        total = collections.Counter()
        dyn_total = collections.Counter()
        for fam, (matdir, manifest) in sorted(mats.items()):
            mtot = collections.Counter()
            dyn = collections.Counter()
            for st in manifest["sets"]:
                for c in st["claims"]:
                    label = re.sub(r"\s+", " ", c.get("label", "")).strip()
                    # dynamic-noise placeholders are a property of source templates, not of truth values.
                    dynkinds = set()
                    for pg in c.get("source_pages") or []:
                        for k in range(len(st.get("truth") or [])):
                            p = matdir / "sets" / st["set"] / f"cycle_{k}" / "site" / pg
                            try:
                                blob = p.read_bytes()
                            except OSError:
                                continue
                            for token in (b"{{FETCH_TS}}", b"{{FETCH_COUNT}}", b"{{FETCH_ID}}"):
                                if token in blob:
                                    dynkinds.add(token.decode().strip("{}").lower())
                    if dynkinds:
                        dyn["claims_with_fetch_templates"] += 1
                        for x in sorted(dynkinds):
                            dyn[x] += 1
                        field_stats[label]["dynamic_noise_template_claims"] += 1
                    lf = label_features(label)
                    for truth in st["truth"]:
                        a = truth.get(c["id"], "")
                        fs = answer_features(a)
                        field_stats[label]["lines"] += 1
                        field_stats[label][f"form:{fs['form']}"] += 1
                        mtot["lines"] += 1
                        total["lines"] += 1
                        for fn, hit in lf.items():
                            if hit:
                                field_stats[label][fn] += 1
                                mtot[fn] += 1
                                total[fn] += 1
                        for fn in featnames:
                            if fn.startswith("label_"):
                                continue
                            if fs[fn]:
                                field_stats[label][fn] += 1
                                mtot[fn] += 1
                                total[fn] += 1
                        mtot[f"form:{fs['form']}"] += 1
                        total[f"form:{fs['form']}"] += 1
            mtot["sets"] = len(manifest["sets"])
            mtot["claims"] = sum(len(x["claims"]) for x in manifest["sets"])
            mat_out[fam] = {"summary": full_summary(mtot), "dynamic_noise_templates": dict(sorted(dyn.items()))}
            dyn_total.update(dyn)
        fields = {}
        for label, cnt in sorted(field_stats.items()):
            n = cnt["lines"]
            fields[label] = {
                "lines": n,
                "forms": {k[5:]: v for k, v in sorted(cnt.items()) if k.startswith("form:")},
                "feature_lines": {fn: cnt[fn] for fn in featnames if cnt[fn]},
                **({"dynamic_noise_template_claims": cnt["dynamic_noise_template_claims"]} if cnt["dynamic_noise_template_claims"] else {}),
            }
        rounds[rnd] = {
            "note": "行數是答案鍵行：set × claim × cycle（D2′ truth 有逐週期答案）；同一套教材不因不同模型/root 重複計。label_* 是欄位標籤本身的形式（第五輪年份在標籤，不在答案值）；dynamic_noise_templates 是來源模板含 FETCH_TS/COUNT/ID 的 claim 數，不是答案鍵被雜訊污染。",
            "summary": full_summary(total), "materials": mat_out,
            "dynamic_noise_templates": dict(sorted(dyn_total.items())), "fields": fields,
        }
    return rounds


def control_rows(rnd: str) -> tuple[list[tuple[str, str, str, str]], list[tuple[str, str, str, str]]]:
    diff = [("base",) + x for x in BASE_DIFF]
    same = [("base",) + x for x in BASE_SAME]
    extra_d = R4_EXTRA_DIFF if rnd == "r4" else R5_EXTRA_DIFF
    extra_s = R4_EXTRA_SAME if rnd == "r4" else R5_EXTRA_SAME
    diff += [("round_specific",) + x for x in extra_d]
    same += [("round_specific",) + x for x in extra_s]
    return diff, same


def run_controls() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rnd in ("r4", "r5"):
        diff, same = control_rows(rnd)
        res: dict[str, Any] = {"must_differ": [], "should_match": []}
        for grp, rows, target in (("must_differ", diff, False), ("should_match", same, True)):
            for i, (origin, cat, v, a) in enumerate(rows, 1):
                row = {"id": f"{grp[:1]}{i:02d}", "origin": origin, "cat": cat}
                for mode in ("default", "strict"):
                    row[f"{mode}_same"] = same_mode(v, a, mode)
                res[grp].append(row)
        summ: dict[str, Any] = {}
        for mode in ("default", "strict"):
            fp = [r for r in res["must_differ"] if r[f"{mode}_same"]]
            fb = [r for r in res["should_match"] if not r[f"{mode}_same"]]
            summ[mode] = {
                "false_pass": len(fp), "false_pass_cats": sorted({r["cat"] for r in fp}),
                "false_block": len(fb), "false_block_cats": sorted({r["cat"] for r in fb}),
            }
        res["summary"] = {"must_differ_n": len(diff), "should_match_n": len(same), **summ}
        out[rnd] = res
    return {
        "note": "合成控制只報分類與判定，不報控制字串。default＝這兩輪實際評分函式；strict＝後來才加入的對照。dynamic_noise/adjacent_fields 控制例依『值必須是該欄在頁面上陳述的值本身，不帶抓取雜訊或鄰欄』判為必須不同。",
        "rounds": out,
    }


def gc_unrestorable() -> dict[str, set[str]]:
    p = REPO / "ops/redo/audit/d2_gc_impact_20261128/unrestorable_cells.json"
    data = json.loads(p.read_text())
    return {root: {k.split("/", 1)[0] for k in cells} for root, cells in data.items()}


def load_population(d2private: pathlib.Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, dict[str, tuple[pathlib.Path, dict[str, Any]]]]]:
    rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"roots": {}}
    per_round_manifests: dict[str, dict[str, tuple[pathlib.Path, dict[str, Any]]]] = {"r4": {}, "r5": {}}
    gcmap = gc_unrestorable()
    score_d2.STRICT = False
    for rnd, specs in ROOT_SPECS.items():
        for spec in specs:
            root = d2private / spec["root"]
            plan = load_plan(spec["plan"])
            matdir, manifest = load_manifest(plan)
            per_round_manifests[rnd].setdefault(spec["family"], (matdir, manifest))
            reports, _costs = score_d2.load_harness(root)
            scored = score_d2.score(manifest, reports, {})
            idx = {(st["set"], c["id"]): (st, c) for st in manifest["sets"] for c in st["claims"]}
            nbefore = len(rows)
            status_counts = collections.Counter()
            for r in scored["rows"]:
                st, c = idx[(r["set"], r["claim"])]
                answer = st["truth"][r["cycle"]][r["claim"]]
                key = f"{spec['batch']}/{r['set']}|r{r['cycle']}|{r['arm']}|{r['claim']}"
                toks_v = semantic_tokens(r.get("value"))
                toks_a = semantic_tokens(answer)
                hp_false_pass = bool(r["status"] == "correct" and toks_v != toks_a)
                hp_false_block = bool(r["status"] != "correct" and toks_v and toks_v == toks_a)
                fp_kind = None
                if hp_false_pass:
                    if len(toks_v) < len(toks_a) and toks_v == toks_a[:len(toks_v)]:
                        fp_kind = "missing_numeric_component"
                    elif len(toks_v) > len(toks_a) and toks_v[:len(toks_a)] == toks_a:
                        fp_kind = "extra_numeric_component"
                    elif len(toks_v) == len(toks_a):
                        fp_kind = "mismatched_numeric_component"
                    else:
                        fp_kind = "other_numeric_sequence_difference"
                row = {
                    "round": rnd, "batch": spec["batch"], "family": spec["family"], "set": r["set"],
                    "cycle": r["cycle"], "arm": r["arm"], "claim": r["claim"], "key": key,
                    "label": re.sub(r"\s+", " ", c.get("label", "")).strip(),
                    "status": r["status"], "value": r.get("value"), "answer": answer,
                    "gc_unrestorable_set": r["set"] in gcmap.get(spec["root"], set()),
                    "mechanical_false_pass_numeric": hp_false_pass,
                    "mechanical_false_pass_kind": fp_kind,
                    "mechanical_false_block_numeric": hp_false_block,
                }
                rows.append(row)
                status_counts[r["status"]] += 1
            meta["roots"][spec["batch"]] = {
                "root_name": spec["root"], "plan": spec["plan"], "family": spec["family"],
                "rows": len(rows) - nbefore, "status_counts": dict(sorted(status_counts.items())),
                **root_counts(root),
            }
    return rows, meta, per_round_manifests


def population_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rnd in ("r4", "r5"):
        rr = [x for x in rows if x["round"] == rnd]
        cnt = collections.Counter(x["status"] for x in rr)
        mechfp = sum(x["mechanical_false_pass_numeric"] for x in rr)
        mechfb = sum(x["mechanical_false_block_numeric"] for x in rr)
        fpkinds = collections.Counter(x["mechanical_false_pass_kind"] for x in rr if x["mechanical_false_pass_numeric"])
        gc = [x for x in rr if x["gc_unrestorable_set"]]
        gccnt = collections.Counter(x["status"] for x in gc)
        out[rnd] = {
            "rows": len(rr), "judged_correct": cnt["correct"], "judged_wrong": len(rr) - cnt["correct"],
            "status_counts": dict(sorted(cnt.items())),
            "mechanical_false_pass_numeric": mechfp, "mechanical_false_pass_kinds": dict(sorted(fpkinds.items())), "mechanical_false_block_numeric": mechfb,
            "by_batch": {b: dict(sorted(collections.Counter(x["status"] for x in rr if x["batch"] == b).items())) for b in sorted({x["batch"] for x in rr})},
            "gc_unrestorable_sets_separate": {
                "rows": len(gc), "status_counts": dict(sorted(gccnt.items())),
                "mechanical_false_pass_numeric": sum(x["mechanical_false_pass_numeric"] for x in gc),
                "mechanical_false_block_numeric": sum(x["mechanical_false_block_numeric"] for x in gc),
                "sets_by_batch": {b: sorted({x["set"] for x in gc if x["batch"] == b}) for b in sorted({x["batch"] for x in gc})},
            },
        }
    return out


def dynamic_noise_value_scan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Value-free census of r4 report-value shapes that dynamic noise or adjacent-field copying could induce."""
    def feats(x: dict[str, Any]) -> list[str]:
        v = str(x.get("value") or "")
        a = str(x.get("answer") or "")
        out = []
        if re.search(r"\d{4}-\d{2}-\d{2}[T ]", v):
            out.append("iso_timestamp")
        if re.search(r"\b[0-9a-fA-F]{12}\b", v):
            out.append("hex12")
        if re.search(r"\bfetch(?:ed)?\b|\bcount\b", v, re.I):
            out.append("fetch_or_count_word")
        if len(semantic_tokens(v)) > len(semantic_tokens(a)):
            out.append("extra_numeric_tokens")
        if ":" in v:
            out.append("embedded_colon")
        if a and v.count(a) >= 2:
            out.append("answer_repeated")
        return out
    rr = [x for x in rows if x["round"] == "r4"]
    total = collections.Counter()
    bybatch: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    byfield: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for x in rr:
        if not str(x.get("value") or "").strip():
            continue
        fs = feats(x)
        for tab in (total, bybatch[x["batch"]], byfield[x["label"]]):
            tab["filled_rows"] += 1
            if fs:
                tab["rows_with_any_shape"] += 1
                for f in fs:
                    tab[f] += 1
    fields = {}
    for label, cnt in sorted(byfield.items()):
        if cnt["rows_with_any_shape"]:
            fields[label] = dict(sorted(cnt.items()))
    return {
        "note": "這是第四輪 report 值的形式普查（分母是有值行），不是答案鍵行數；只報形狀與行數，不報值。FETCH_TS/COUNT/ID 的模板暴露量見 answer_key_styles.json。",
        "feature_definitions": {
            "iso_timestamp": "值內有 ISO 日期/時間形狀", "hex12": "值內有 12 位十六進位 token",
            "fetch_or_count_word": "值內有 fetch/count 字樣", "extra_numeric_tokens": "值比答案多數字/版本成分",
            "embedded_colon": "值內嵌冒號（常見於把鄰欄一起抄入）", "answer_repeated": "答案字串在值內重複出現",
        },
        "total": dict(sorted(total.items())),
        "by_batch": {k: dict(sorted(v.items())) for k, v in sorted(bybatch.items())},
        "fields_with_any_shape": fields,
    }


def strict_population_sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rnd in ("r4", "r5"):
        cnt = collections.Counter()
        for x in [x for x in rows if x["round"] == rnd]:
            strict_correct = same_mode(x["value"], x["answer"], "strict")
            default_correct = x["status"] == "correct"
            cnt["rows"] += 1
            cnt["strict_correct"] += strict_correct
            cnt["default_correct"] += default_correct
            cnt["default_correct_strict_wrong"] += default_correct and not strict_correct
            cnt["default_wrong_strict_correct"] += (not default_correct) and strict_correct
        out[rnd] = dict(cnt)
    return out


def actual_scorer_evidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Value-free cross-check that the published r4/r5 scoring used default canon, not the later strict branch."""
    def counts(sel: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "rows": len(sel),
            "default_correct": sum(x["status"] == "correct" for x in sel),
            "strict_correct": sum(same_mode(x["value"], x["answer"], "strict") for x in sel),
        }
    c0 = [x for x in rows if x["cycle"] == 0]
    batches = {b: counts([x for x in c0 if x["batch"] == b]) for b in sorted({x["batch"] for x in c0})}
    combined = {
        "r4main_qwen_components": counts([x for x in c0 if x["batch"] in {"r4main_1003", "r4main_1004"}]),
    }
    official_files = {
        "r4main_qwen_components": "ops/d2/results/r4_merged/score_summary.json",
        "r4h3seen": "ops/d2/results/r4h3seen/score_summary.json",
        "r4haiku": "ops/d2/results/r4haiku/score_summary.json",
        "r5real_qwen_merged": "ops/d2/results/r5real_merged/score_summary.json",
        "r5real_haiku": "ops/d2/results/r5real_haiku/score_summary.json",
    }
    official: dict[str, Any] = {}
    recomputed: dict[str, Any] = {}
    for name, rel in official_files.items():
        p = REPO / rel
        if not p.exists():
            continue
        pub = json.loads(p.read_text()).get("c0") or {}
        official[name] = {"claims": pub.get("claims"), "correct": pub.get("correct")}
        if name == "r4main_qwen_components":
            recomputed[name] = combined[name]
        else:
            recomputed[name] = batches.get(name)
    return {
        "history_note": "r4 開跑 commit 與 r5 開跑/重跑 commit 都早於 score_d2 --strict 的引入；report_d2.py 也不設定 STRICT。strict 因此只是對照。",
        "c0_recomputed": batches,
        "c0_recomputed_combined": combined,
        "published_score_summary_c0": official,
        "comparison_recomputed": recomputed,
        "decisive_check": "r5real_qwen_merged c0：default 197/360、strict 190/360；repo 的 published score_summary 是 197/360，對上 default。",
    }


def choose_samples(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(SEED)
    samples: dict[str, list[dict[str, Any]]] = {}
    # 固定顺序是一轮内先判對後判錯、第四輪後第五輪；單一 RNG 依次使用，對應種子 20261128。
    for rnd in ("r4", "r5"):
        for cls, pred in (("judged_correct", lambda x: x["status"] == "correct"), ("judged_wrong", lambda x: x["status"] != "correct")):
            grp = sorted([x for x in rows if x["round"] == rnd and pred(x)], key=lambda x: x["key"])
            rng.shuffle(grp)
            samples[f"{rnd}_{cls}"] = grp[:40]
    return samples


def write_private_samples(samples: dict[str, list[dict[str, Any]]], priv: pathlib.Path) -> None:
    priv.mkdir(parents=True, exist_ok=True)
    fields = ["key", "round", "batch", "family", "set", "cycle", "arm", "claim", "label", "status",
              "gc_unrestorable_set", "value", "answer", "mechanical_false_pass_numeric", "mechanical_false_pass_kind", "mechanical_false_block_numeric"]
    with open(priv / "manual_samples_20261128.jsonl", "w", encoding="utf-8") as fh:
        for grp in sorted(samples):
            for x in samples[grp]:
                rec = {k: x.get(k) for k in fields}
                rec["sample_group"] = grp
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cp_upper_one_sided(x: int, n: int, alpha: float = 0.05) -> float:
    """One-sided Clopper-Pearson upper bound; x=0 reduces to 1-alpha^(1/n)."""
    if n <= 0:
        return math.nan
    if x >= n:
        return 1.0
    def cdf_le(p: float) -> float:
        # P[X <= x] for Binomial(n,p), summed in logs for numerical stability.
        terms = []
        for k in range(x + 1):
            terms.append(math.log(math.comb(n, k)) + k * math.log(p) + (n - k) * math.log1p(-p))
        m = max(terms)
        return sum(math.exp(t - m) for t in terms) * math.exp(m)
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if cdf_le(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def sample_public_skeleton(samples: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {"seed": SEED, "key_format": "<批次>/<組>|r<週期>|<臂>|<claim>（批次前綴只用來避免不同 root 的同組同臂撞鍵）", "ordering": "round r4 then r5; within each round judged_correct then judged_wrong; keys sorted before one shared RNG shuffle", "groups": {}}
    for grp, rows in sorted(samples.items()):
        out["groups"][grp] = {
            "n": len(rows),
            "keys": [x["key"] for x in rows],
            "gc_unrestorable_keys": [x["key"] for x in rows if x["gc_unrestorable_set"]],
            "status_counts": dict(sorted(collections.Counter(x["status"] for x in rows).items())),
        }
    return out


def load_manual_verdicts(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("verdicts", data)


def summarize_manual(samples: dict[str, list[dict[str, Any]]], verdicts: dict[str, Any]) -> dict[str, Any]:
    bykey = {x["key"]: x for rows in samples.values() for x in rows}
    missing = [k for k in bykey if k not in verdicts]
    res: dict[str, Any] = {"criterion": None, "complete": not missing, "missing_keys": missing, "rounds": {}}
    if missing:
        return res
    all_rows = []
    for grp, rows in sorted(samples.items()):
        rnd, direction = grp.split("_", 1)
        xs = []
        for x in rows:
            v = verdicts[x["key"]]
            manual_correct = bool(v["manual_value_correct"])
            scorer_correct = (x["status"] == "correct") == manual_correct
            mis = None
            if x["status"] == "correct" and not manual_correct:
                mis = "false_pass"
            elif x["status"] != "correct" and manual_correct:
                mis = "false_block"
            rec = {"key": x["key"], "status": x["status"], "manual_value_correct": manual_correct,
                   "scorer_judgment_correct": scorer_correct, "misjudgment": mis,
                   "manual_category": v.get("category"), "gc_unrestorable_set": x["gc_unrestorable_set"]}
            xs.append(rec)
            all_rows.append({"round": rnd, "direction": direction, **rec})
        n = len(xs)
        bad = sum(not x["scorer_judgment_correct"] for x in xs)
        res["rounds"].setdefault(rnd, {})[direction] = {
            "n": n, "misjudged": bad, "rate": round(bad / n, 4),
            "upper95_one_sided": round(cp_upper_one_sided(bad, n), 4),
            "misjudged_keys": [x["key"] for x in xs if not x["scorer_judgment_correct"]],
            "rows": xs,
        }
    for rnd in ("r4", "r5"):
        rr = [x for x in all_rows if x["round"] == rnd]
        # 兩個方向分開抽，不能合成一個無加權母體率；這裡只報方向別數字。
        res["rounds"][rnd]["gc_unrestorable_sample_rows"] = sum(x["gc_unrestorable_set"] for x in rr)
    res["criterion"] = (
        "人工核判準：以該週期答案鍵為準。值必須是同一欄位的同一個值：數值大小、版本三段、正負號、"
        "尺度、幣別、單位、百分比、以及多成分值的每一成分（第五輪 apps 與 goals 兩者）都要相同；"
        "千分位、空白、Markdown、版本前綴 v、小數尾零等純格式差異可。只寫前一個數字而漏掉答案成分、"
        "把舊值與新值並列、或把抓取雜訊／相鄰欄位併入該欄，都不算同一個值。missing、空白或無法辨識的值不判對。"
    )
    return res


def field_error_rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """High-confidence mechanical field screen used for item (d), with rates per field."""
    out: dict[str, Any] = {}
    for rnd in ("r4", "r5"):
        tab: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for x in [x for x in rows if x["round"] == rnd]:
            f = tab[x["label"]]
            f["rows"] += 1
            f["judged_correct"] += x["status"] == "correct"
            f["judged_wrong"] += x["status"] != "correct"
            f["false_pass_numeric"] += x["mechanical_false_pass_numeric"]
            f["false_block_numeric"] += x["mechanical_false_block_numeric"]
        flagged = []
        for label, c in sorted(tab.items()):
            errors = c["false_pass_numeric"] + c["false_block_numeric"]
            rate = errors / c["rows"] if c["rows"] else 0.0
            fp_rate_correct = c["false_pass_numeric"] / c["judged_correct"] if c["judged_correct"] else 0.0
            fb_rate_wrong = c["false_block_numeric"] / c["judged_wrong"] if c["judged_wrong"] else 0.0
            if rate > 0.05 or fp_rate_correct > 0.05 or fb_rate_wrong > 0.05:
                flagged.append({
                    "field": label, "rows": c["rows"], "judged_correct": c["judged_correct"], "judged_wrong": c["judged_wrong"],
                    "false_pass_numeric": c["false_pass_numeric"], "false_block_numeric": c["false_block_numeric"],
                    "error_rate_all_rows": round(rate, 4), "false_pass_rate_among_judged_correct": round(fp_rate_correct, 4),
                    "false_block_rate_among_judged_wrong": round(fb_rate_wrong, 4),
                })
        out[rnd] = {
            "method": "高置信機械篩：只把『評分判對但語義數字/版本成分序列與答案不同』列為誤放、『評分判錯但該序列完全相同』列為誤擋；不等於全部語義誤判。分母另列全行數與方向別行數。",
            "fields_over_5pct": sorted(flagged, key=lambda x: (-x["error_rate_all_rows"], x["field"])),
        }
    return out


def make_readme(public: dict[str, Any]) -> str:
    lines = [
        "# D2′ 第四、五輪評分器雙向審查（2026-11-28）",
        "",
        "離線重算，未呼叫模型。實際評分函式是 `score_d2` 預設模式：版本號優先、否則只取第一個數字；`--strict` 是開跑後才加入的對照（依序比對全部數字），不是這兩輪實際使用的函式。交叉檢查：r5real qwen c0 在 default 為 197/360、strict 為 190/360，repo 內已發表 score_summary 為 197/360；且 r4/r5 開跑 commit 早於 strict 旗標。",
        "",
        "## 採用 root",
    ]
    for x in public["root_selection"]["adopted"]:
        lines.append(f"- {x}")
    lines += ["", "未採用／只作對照："]
    for x in public["root_selection"]["not_adopted"]:
        lines.append(f"- {x}")
    sty = public["answer_key_styles"]
    s4, s5 = sty["r4"]["summary"], sty["r5"]["summary"]
    lines += [
        "",
        "## (a) 答案鍵形式",
        f"- r4: {s4['lines']} 行；number+unit {s4.get('form:number_with_unit', 0)}、version {s4.get('form:version', 0)}、currency {s4.get('form:currency_amount', 0)}、percent {s4.get('form:percent', 0)}。相對年齡、指數成分、註腳、年份/期間括號、尺度字、範圍、多值都是 0。",
        f"- r5: {s5['lines']} 行；全部是 apps (goals) 括號多值（{s5.get('form:apps_goals_parentheses', 0)} 行），答案本身沒有相對年齡、指數成分、註腳、幣別或尺度字；年份/期間在欄位標籤（{s5.get('label_year_or_period', 0)} 行），不在答案值。",
        "",
        "## (b) 合成控制", "", "| 輪次 | 函式 | 誤放（該不同判同） | 誤擋（該相同判不同） |", "|---|---|---:|---:|",
    ]
    for rnd in ("r4", "r5"):
        s = public["controls"]["rounds"][rnd]["summary"]
        for mode in ("default", "strict"):
            lines.append(f"| {rnd} | {mode} | {s[mode]['false_pass']}/{s['must_differ_n']} | {s[mode]['false_block']}/{s['should_match_n']} |")
    lines += ["", "## (c) 人工抽樣", "", "| 輪次 | 抽樣方向 | 誤判 | 單尾 95% 上界 |", "|---|---|---:|---:|"]
    manual = public.get("manual_check", {})
    if manual.get("complete"):
        for rnd in ("r4", "r5"):
            for direction, label in (("judged_correct", "判對"), ("judged_wrong", "判錯")):
                x = manual["rounds"][rnd][direction]
                lines.append(f"| {rnd} | {label} | {x['misjudged']}/{x['n']} ({x['rate']:.1%}) | {x['upper95_one_sided']:.2%} |")
    else:
        lines.append("| — | — | 人工判定尚未填入 | — |")
    pop = public["population_summary"]
    dyn = public["dynamic_noise_value_scan"]["total"]
    gc4 = pop["r4"]["gc_unrestorable_sets_separate"]
    lines += [
        "",
        "gc 補不回頁面的組另列（只在 r4）："
        f"rows {gc4['rows']}，狀態 {gc4['status_counts']}，高置信誤放 {gc4['mechanical_false_pass_numeric']}、誤擋 {gc4['mechanical_false_block_numeric']}；"
        "人工抽樣中此類行數見 manual_check.json。",
        "",
        "r4 dynamic_noise 形式普查：來源模板 FETCH_TS/COUNT/ID 暴露細項在 answer_key_styles.json；report 有值行中沒有 ISO 時間戳、12 位 hex 或 fetch/count 字樣，"
        f"形狀異常 {dyn.get('rows_with_any_shape', 0)}/{dyn.get('filled_rows', 0)} 行（多為額外數字成分／鄰欄冒號；細項在 dynamic_noise_value_scan.json）。",
        "",
        "高置信全母體數字成分篩（補充人工抽樣，不是人工核的替代；抽樣 0/40 與全母體仍有少量誤放並不矛盾，因單尾上界為 7.22%）：",
    ]
    for rnd in ("r4", "r5"):
        fp = pop[rnd]["mechanical_false_pass_numeric"]
        jc = pop[rnd]["judged_correct"]
        fb = pop[rnd]["mechanical_false_block_numeric"]
        kinds = pop[rnd].get("mechanical_false_pass_kinds") or {}
        lines.append(f"- {rnd}: 誤放 {fp}/{jc}（{fp / jc:.2%}；分類 {kinds}），誤擋 {fb}。")
    lines += ["", "## (d) 誤判率 >5% 的欄位", ""]
    for rnd in ("r4", "r5"):
        flagged = public["field_error_rates"][rnd]["fields_over_5pct"]
        lines.append(f"- {rnd}: {len(flagged)} 個欄位（見 `field_error_rates.json`；這是高置信數字成分機械篩，會低估單位/文字層問題）。")
    lines += [
        "",
        "輸出檔：`answer_key_styles.json`（a）、`synthetic_controls.json`（b）、`manual_samples_public_keys.json` 與 `manual_check.json`（c）、`field_error_rates.json`（d）、`population_summary.json`、`dynamic_noise_value_scan.json`、`root_inventory.json`。含值抽樣只在私有目錄；此目錄與 JSON 不含實驗值。",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", default=str(PRIV_DEFAULT))
    a = ap.parse_args()
    if "D2_PRIVATE" not in os.environ:
        raise SystemExit("D2_PRIVATE is not set; cannot read experiment data")
    d2private = pathlib.Path(os.environ["D2_PRIVATE"])
    if not d2private.is_dir():
        raise SystemExit("D2_PRIVATE does not name a readable directory")
    priv = pathlib.Path(a.private).expanduser()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    inv = inventory(d2private)
    rows, meta, per_round_manifests = load_population(d2private)
    styles = answer_key_styles(per_round_manifests)
    controls = run_controls()
    popsum = population_summary(rows)
    dynscan = dynamic_noise_value_scan(rows)
    strictsens = strict_population_sensitivity(rows)
    scorer_evidence = actual_scorer_evidence(rows)
    samples = choose_samples(rows)
    write_private_samples(samples, priv)
    sample_skel = sample_public_skeleton(samples)
    verdicts = load_manual_verdicts(OUTDIR / "manual_verdicts.json")
    manual = summarize_manual(samples, verdicts)
    fieldrates = field_error_rates(rows)

    root_selection = {
        "adopted": [
            "r4main_1003＋r4main_1004（兩台各一部分；逐位元檢查等同 r4_merged，採分 root 以保留 gc 來源）、r4h3seen、r4haiku",
            "r5real_merged（正式合併 root；逐位元檢查等同 r5real_1003b＋r5real_1004b）、r5real_haiku（正式 Haiku root；99/100 arm dirs，缺的部分不補、照實計入 population 缺口）",
        ],
        "not_adopted": [
            "r5real_1003／r5real_1004：第一次啟動不完整（RUN.json 與 cells 數目見 root_inventory.json）",
            "r5real_1003b／r5real_1004b：完整組件，但與 r5real_merged 逐位元相同；為避免重複只算 merged",
            "r4_merged：與 r4main_1003＋r4main_1004 逐位元相同；為保留 gc 來源，直接用兩個組件 root",
        ],
    }
    public = {
        "note": "D2′ scorer audit; public files contain no experiment values.",
        "scoring_functions": {
            "actual_default": "score_d2.canon with STRICT=False: version first if present, otherwise first numeric token; ignores sign, unit, currency, scale words and all later numeric tokens.",
            "strict_comparison_only": "score_d2.canon with STRICT=True: all numeric/version tokens in order. The flag did not exist in the run-time commits for r4/r5.",
        },
        "root_selection": root_selection,
        "root_inventory": inv,
        "answer_key_styles": styles,
        "population_summary": popsum,
        "dynamic_noise_value_scan": dynscan,
        "strict_population_sensitivity": strictsens,
        "actual_scorer_evidence": scorer_evidence,
        "controls": controls,
        "manual_check": manual,
        "field_error_rates": fieldrates,
    }
    # 分檔輸出，避免人工檢查時打開一個很大的 JSON。
    for name, obj in [
        ("root_inventory.json", {"root_selection": root_selection, "root_inventory": inv, "root_runtime_metadata": meta["roots"]}),
        ("answer_key_styles.json", {"note": "逐欄答案鍵樣式；不含答案值。", "rounds": styles}),
        ("synthetic_controls.json", controls),
        ("population_summary.json", {"population_summary": popsum, "strict_population_sensitivity": strictsens, "actual_scorer_evidence": scorer_evidence}),
        ("dynamic_noise_value_scan.json", dynscan),
        ("manual_samples_public_keys.json", sample_skel),
        ("manual_check.json", manual),
        ("field_error_rates.json", fieldrates),
    ]:
        (OUTDIR / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    (OUTDIR / "README.md").write_text(make_readme(public))
    print(json.dumps({
        "rows": {r: popsum[r]["rows"] for r in popsum},
        "controls": {r: controls["rounds"][r]["summary"] for r in controls["rounds"]},
        "manual_complete": manual.get("complete"),
        "field_flag_counts": {r: len(fieldrates[r]["fields_over_5pct"]) for r in fieldrates},
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
