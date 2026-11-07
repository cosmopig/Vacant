# 現在（第 1207 輪後，2026-11-07）

## r1207：工單 P20261107_1827-1 完成（ebe4344c，工單已入 done/）
- json_preview：頂層 list→5 列（列內 list 完整）；頂層 dict→全部鍵、陣列值取前 5 項；
  無深層遞迴（_cap_lists 遞迴 r1206 已還原，本輪補回工單要求的 dict 分支＋2 測試）。
- 驗收：run_eval.py --all＝🏆 G2.5 全三項門禁整合驗收 PASS、RC=0
  （G1 39/39・REAL14 9/9 冤枉1/5・PHASE3 6fixed/3unres 全 RESUMED）；
  0 新 API 呼叫（vibe_calls 130→130）；14/14 prompt_sha 快取命中；
  out 凍結檔已還原 HEAD；reqloop 12 檔 347 passed。
- 帳本事實：r1205（_cap_lists 時代）18:19–18:35 有 3 次 real14 真實擷取呼叫
  （71→74 次／701,696→732,826 tok）——快取失效風險曾實際發生，現已修復。

## 下一步
1. 巡 auto/qwen27b（ebe4344c 之後的 HEAD）本地 CI 綠燈。
2. GitHub Actions 13:22 UTC 後仍無新 run＝人類/基建問題，等指示。
3. 等 G2.5 後續或審查新派工。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden／scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
