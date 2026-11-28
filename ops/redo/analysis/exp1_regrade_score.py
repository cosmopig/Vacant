#!/usr/bin/env python3
"""實驗一敏感度（事後）：把 score_strict 的逐行狀態用第二正規化器放寬（原判對照舊；否則值合規則——答案去掉『; N years ago』後 canon_strict 等值，
或答案的（交易所, 代號）對包含值的全部對——改判 correct），寫出新的 score 檔，交給原程式 exp1_flags.py 重算。用法：exp1_regrade_score.py PLAN1,PLAN2 IN OUT（PLAN 的 materials dir 要先展開 ${D2_PRIVATE}）"""
import collections, json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from regrade_sensitivity import key_equiv_nolabel, M  # noqa: E402
truth = {}
for pf in sys.argv[1].split(","):
    truth.update(M.load_manifests_with_truth(json.loads(pathlib.Path(pf).read_text())))
d = json.loads(pathlib.Path(sys.argv[2]).read_text()); flips = collections.Counter()
for r in d["rows"]:
    v = r.get("value")
    if r["status"] == "correct" or v in (None, "None", ""):
        continue
    t = truth[r["set"]]["truth"][int(r["cycle"])].get(r["claim"])
    e = key_equiv_nolabel(v, t)
    if e:
        flips[(r["status"], e, r["arm"])] += 1; r["status"] = "correct"
d["regrade_note"] = "事後敏感度：第二正規化器放寬；見 ops/redo/analysis/exp1_regrade_score.py"
pathlib.Path(sys.argv[3]).write_text(json.dumps(d, ensure_ascii=False))
print(json.dumps({"|".join(k): v for k, v in flips.items()}))
