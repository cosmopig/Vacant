# 現在（第 1196 輪，2026-11-07）

## r1196：工單 P20261107_1426-2 收（vq-el4.6 啟動）
- run_eval.py 新增 `--models m1,m2,...` 多模型對照：每模型 evaluate_task＋read_extract_costs（離線、0 模型呼叫）；
  對照表 Model/Bad Caught/Caught %/Good FP/Total Good/Calls/Tokens；`--json` 寫 models 字典（metrics＋成本）。
  門禁同口徑（≥70% 且 0 冤枉）；缺擷取→MISSING/rc2；任一 FAIL→rc20；成本缺值→None（不填 0）。
- 驗收 RC=0：glm53 39/39 (100.0%)、FP 0、41 calls/328550 tok、eval_g1_compare.json 已寫。
  ⚠ 票面「29/39 (74.4%)」與現盤不符（top out/=39/39；round1 11/39、round2 31/39、round3 28/39）——
  表顯示真實盤上數字，已註明於工單尾。
- 82 tests passed（含新 test_run_eval_multi_model_comparison）；commit dff8f918；工單 mv done/；
  vq-el4.6 in_progress＋bd note（下一步＝其他模型擷取＋同表對照）。

## 下一步（vq-el4.6 本體）
1. glm53flash、deepseek41 各跑 G1 7 題擷取（走 `glm` 指令、查 ledger 日 ≤2M token 餘額再發射）。
2. `--models glm53,glm53flash,deepseek41 --json ...` 同表對照（抓錯/冤枉/成本）。
3. gemma 非 vibe 別名（1004 provider），進同表需另定對接口——先報規劃者。
4. 復核 7de75257 CI（auto/qwen27b）。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden／scorer；不繞 glm 直連 vibe；不改
repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
