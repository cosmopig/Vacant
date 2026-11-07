# 現在（第 1214 輪後，2026-11-07）

## r1214：PHASE3 第二批 STALE 重驗完成（工單 P20261107_2028-2 → done）
- `run_eval.py --phase3`（online）：7 格 RESUMED（0 呼叫）；dab_426-pi-C **fixed**（12c/468665t、stalled）、dab_427-pi-A **fixed**（10c/432313t、gap_closed）；本批 2 sessions/22 calls/900978 tok（1004 gemma-4-12b-it-qat、raw usage、無硬 token 上限）。
- 驗收＝**🏆 G2.5 全三項門禁整合驗收：PASS、rc=0**（commit dd6e49c4）：G1 PASS（39/39、0 冤枉、41c/328550t）＋REAL14 PASS（9/9、1/5 冤枉、74c/732826t）＋PHASE3 PASS（fixed 7／unresolved 2／0 error、15s/275c/15087278t）；vibe_calls 130→130（0 新外部呼叫）。

## PHASE3 現況（口徑）
- 9 格：fixed 7（039、378、426 新、427 新、507、dabstep-10、23）＋unresolved 2（055 stalled、1273 max_rounds）；progress.json complete=True、0 STALE、0 ERROR。
- 所有裁決＝開發選樣單 rep（gemma 12b 本機）；426/427 fixed 為本批單格結果，不宣稱管線普遍較好。

## 下一步
1. 等審查新派工／G2.5 後續（vq-el4 工單面已清空：open/doing 皆空）。
2. 巡 CI：auto/qwen27b dd6e49c4、auto/argon 2db8afa5（輪首時未跑完）；GitHub Actions 仍停擺。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照／官方鎖檔 eval_phase3_glm53.json；成本缺值＝UNKNOWN 不填 0。
