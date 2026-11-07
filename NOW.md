# 現在（第 1197 輪，2026-11-07）

## r1197：vq-el4.6 對照表完成（3 模型）＋擷取失敗點名
- glm53flash/deepseek41 各跑 G1 7 題擷取（走 glm 指令、ledger 先查：今日 1.04M/2M 內發射）。
  結果：glm53flash 3/7 成功（inventory_alerts/orders_monthly/support_tickets/web_traffic
  ＝deadline×3、token_limit×1）；deepseek41 5/7（inventory_alerts/web_traffic＝turn_limit×2）。
  依 glm 規則「撞額度就停，不要重試」→ 不重試，失敗入盤為 fail-closed 0 條目。
- 產品修（93b8d6d1，TDD）：run_eval 對照表點名擷取失敗題——Extract OK 欄＋extract_failed
  原因＋擷取不完整→FAIL（不得 PASS）；單模型路徑同標 ⚠️。83 tests passed。
- 對照表（out/eval_g1_compare_3m.json）：
  - glm53：抓錯 39/39 (100%)、FP 0、Extract 7/7、41 calls/328550 tok → PASS
  - glm53flash：16/39 (41%)、FP 0、Extract 3/7、成本 UNKNOWN → FAIL
  - deepseek41：23/39 (59%)、FP 1、Extract 5/7、成本 UNKNOWN → FAIL（RC=20，非全過）
  - 只可讀作「固定 harness（150s deadline、單回合、無工具）下 G1 開發樣本」，單 rep、
    非未見任務效力；不宣稱某模型較好。
- CI：dd4566e2 仍排隊（LATEST 綠＝87ca83d3 5014 passed；f5347a0a 跑中）→ 下輪復核。

## 下一步
1. 待規劃者：gemma（1004 provider，非 vibe 別名）進同表需定對接口——先報後做。
2. 待規劃者：r1195 兩跑差異（phase3 6/3 vs 8/1）裁決。
3. vq-el4.6 結案條件＝gemma 入表或規劃者改口徑；複核 dd4566e2 CI。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden／scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
