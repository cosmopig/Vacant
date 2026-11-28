#!/usr/bin/env python3
"""只查教材答案鍵（cycle 0 的 truth[0]）有沒有確認批次那兩種附帶文字：『; N years ago』與指數成分（"... component"）。
不重算任何批次；輸出各批次受影響的欄位與行數（無值）。事後；規則同 judge_v2v3_20261128/PLAN.md 步驟 0。"""
import collections, json, pathlib, re, sys
REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402
AGE = re.compile(r";?\s*\d+\s+years?\s+ago", re.I)
IDX = re.compile(r"\bcomponent\b", re.I)
PLANS = {"confirm_expTc": "expTc_drafts_qwen9b.json", "exploratory_expT": "expT_qwen9b.json",
         "exp1_cA_1003": "exp1cA_d2_qwen9b_1003.json", "exp1_cA_1004": "exp1cA_d2_qwen9b_1004.json",
         "exp1_cB_1003": "exp1cB_d2_qwen9b_1003.json", "exp1_cB_1004": "exp1cB_d2_qwen9b_1004.json",
         "d2prime_r5real_1003": "r5real_d2_qwen9b_1003.json", "d2prime_r5real_1004": "r5real_d2_qwen9b_1004.json"}
out = {}
for name, f in PLANS.items():
    plan = json.loads((REPO / "ops/d2/plans" / f).read_text())
    try:
        truth = M.load_manifests_with_truth(plan)
    except Exception as e:  # noqa: BLE001
        out[name] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}; continue
    per = collections.defaultdict(lambda: collections.Counter()); tot = collections.Counter()
    for sid, st in truth.items():
        grp = re.sub(r"-s\d+$", "", sid)
        for c in st["claims"]:
            a = st["truth"][0].get(c["id"]) or ""
            tot[grp] += 1
            lab = re.sub(r"\s+", " ", c.get("label", "")).strip()
            if AGE.search(a):
                per[grp][f"age|{lab}"] += 1
            if IDX.search(a):
                per[grp][f"index_component|{lab}"] += 1
    out[name] = {"sets": len(truth), "lines_by_group": dict(tot),
                 "affected_by_group": {g: {"lines": sum(c.values()), "fields": dict(c)} for g, c in per.items()}}
p = REPO / "ops/redo/audit/judge_v2v3_20261128/answer_key_artifacts_other_batches.json"
p.write_text(json.dumps({"note": "只查答案鍵 truth[0]；行數＝答案鍵的行（每組每欄一行），不是初稿行；不重算批次。", "batches": out}, ensure_ascii=False, indent=1))
for k, v in out.items():
    print(k, v.get("error") or {g: x["lines"] for g, x in v["affected_by_group"].items()}, v.get("lines_by_group"))
