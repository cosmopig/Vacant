# 重評敏感度的完整命令列（2026-11-28；事後）

環境：`. ~/dev/ops/d2_private.env`（設 `$D2_PRIVATE`）、`export PYTHONPATH=.`；工作目錄＝repo 根。輸出先寫 `~/dev/ops/ctl/regrade_20261128/`，再原樣複製到本目錄。

```bash
# 確認批次主分析（v4 同參數）
python3 ops/redo/analysis/regrade_sensitivity.py ops/d2/expTc_confirm_analysis.py -- \
  --drafts $D2_PRIVATE/expTc_drafts_q9_1003 $D2_PRIVATE/expTc_drafts_q9_1004 \
  --fb $D2_PRIVATE/expTc_fb_q9_1003 $D2_PRIVATE/expTc_fb_q9_1004 \
  --known-file ~/dev/ops/ctl/expTc_known_names_B56_20261128.json \
  --negctl-after ops/redo/audit/expTc_negctl_after_v2_expTc_fb_q9_1003.json ops/redo/audit/expTc_negctl_after_v2_expTc_fb_q9_1004.json \
  --infra-rule b61 --out ~/dev/ops/ctl/regrade_20261128/expTc_confirm_analysis_regrade_b61.json \
  --md ~/dev/ops/ctl/regrade_20261128/expTc_confirm_analysis_regrade_b61.md
# E 家族分析（原同參數）
python3 ops/redo/analysis/regrade_sensitivity.py ops/d2/expTc_escalation_analysis.py -- \
  --drafts $D2_PRIVATE/expTc_drafts_q9_1003 $D2_PRIVATE/expTc_drafts_q9_1004 --k 5 \
  --b27 ~/dev/ops/ctl/b27_suspicious.json --out ~/dev/ops/ctl/regrade_20261128/expTc_escalation_regrade.json
# E 家族逐份匯出
python3 ops/redo/analysis/regrade_sensitivity.py ops/d2/export_expTc_efamily.py -- \
  $D2_PRIVATE/expTc_drafts_q9_1003 $D2_PRIVATE/expTc_drafts_q9_1004 --out ~/dev/ops/ctl/regrade_20261128/efamily_regrade
# 彙整
python3 ops/redo/analysis/regrade_summary.py
# 不看欄名版對看欄名版的一致性（初稿；全部產出）
python3 ops/redo/analysis/regrade_sensitivity.py --selfcheck $D2_PRIVATE/expTc_drafts_q9_1003 $D2_PRIVATE/expTc_drafts_q9_1004
python3 ops/redo/analysis/regrade_selfcheck_all.py $D2_PRIVATE/expTc_drafts_q9_1003 $D2_PRIVATE/expTc_drafts_q9_1004 $D2_PRIVATE/expTc_fb_q9_1003 $D2_PRIVATE/expTc_fb_q9_1004
# 公司組旗標（改標籤）
python3 ops/redo/analysis/flags_regrade.py $D2_PRIVATE/expTc_drafts_q9_1003 $D2_PRIVATE/expTc_drafts_q9_1004
# 實驗一 cA（plan 的 materials dir 先把 ${D2_PRIVATE} 展開成兩個暫存 plan 檔）
python3 ops/redo/analysis/exp1_regrade_score.py <plan_cA_1003>,<plan_cA_1004> ~/dev/ops/d2_results/exp1cA/score_strict.json ~/dev/ops/ctl/regrade_20261128/exp1cA_score_strict_regrade.json
python3 ops/d2/exp1_flags.py --root $D2_PRIVATE/exp1cA_merged --materials $D2_PRIVATE/realrev2_sc --score ~/dev/ops/ctl/regrade_20261128/exp1cA_score_strict_regrade.json --arms a --out ~/dev/ops/ctl/regrade_20261128/exp1cA_flags_regrade_repro.json
python3 ops/d2/exp1_flags.py --root $D2_PRIVATE/exp1cA_merged --materials $D2_PRIVATE/realrev2_sc --score ~/dev/ops/ctl/regrade_20261128/exp1cA_score_strict_regrade.json --arms a --b24 --out ~/dev/ops/ctl/regrade_20261128/exp1cA_flags_regrade_b24.json
python3 ops/d2/exp1_combine.py --a ~/dev/ops/ctl/regrade_20261128/exp1cA_flags_regrade_repro.json --b ~/dev/ops/d2_results/exp1_recompute_20261128/exp1cB_flags_repro.json --out ~/dev/ops/ctl/regrade_20261128/exp1_combined_regrade_repro.json
python3 ops/d2/exp1_combine.py --a ~/dev/ops/ctl/regrade_20261128/exp1cA_flags_regrade_b24.json --b ~/dev/ops/d2_results/exp1_recompute_20261128/exp1cB_flags_b24.json --out ~/dev/ops/ctl/regrade_20261128/exp1_combined_regrade_b24.json
# 探索批次
python3 ops/redo/analysis/regrade_sensitivity.py ops/d2/expT_metrics.py -- $D2_PRIVATE/expT_q9 --json-out ~/dev/ops/ctl/regrade_20261128/expT_metrics_regrade.json
python3 ops/redo/analysis/regrade_sensitivity.py ops/d2/expT_escape.py -- $D2_PRIVATE/expT_q9 --out-dir ~/dev/ops/ctl/regrade_20261128/escape_regrade
python3 ops/redo/analysis/expT_regrade_b48.py $D2_PRIVATE/expT_q9 ~/dev/ops/ctl/regrade_20261128/expT_b48_regrade.json
# 其他批次答案鍵
python3 ops/redo/analysis/answer_key_artifacts.py
```
注意：`regrade_sensitivity.py` 對目標是 `expT_metrics.py` 本身時改呼叫已換過的模組的 `main()`（runpy 會另起命名空間、換不到；第一次跑因此 0 次換判，已修正後重跑）。
