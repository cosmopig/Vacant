# 現在（第 1190 輪，2026-11-07）

## r1190：argon merge 後 real14 重跑（門禁 PASS）
- 資深審查指示：審過＋merge auto/argon 7899602d（checks.py
  resolve_deliverable_path：/app/、./、絕對路徑前綴剝除並錨定
  deliverable_dir，防 docker 路徑穿透；附回歸測試）→ 本地 137 tests
  passed。⚠ 該 SHA CI pending（排在 qwen27b 之後）；DECISION：依資深
  明確指示＋審過＋本地測試綠而合；下一輪先查 CI 結果。
- 清 out/real14/*.glm53.json（r1189 cache 快照 real14_round2/，16 檔）
  → 14 cell 重擷取（glm53，14 次）→ **門禁 PASS：抓錯 8/9（≥5）、
  冤枉 1/5（≤1）、RC=0**。
- 與 r1189（9/9、1/5）差：dab_039 本輪漏（0 FAIL/4 UNKNOWN；擷取
  非確定，仍達門限）；dab_057 仍冤枉（門限內）。
- 重跑驗證：0 新呼叫（ledger 113→113）、結果逐字相同。
- 成本累計 71 次/701696 tokens（vibe_calls.jsonl；日 ≤2M 預算內）。
- vq-el4.4 r1189 已 close；r1190 復核記入 bd note。vq-el4.5 已 claim。

## 下一步（vq-el4.5，in_progress）
- 9 份錯草稿＋自動擷取需求（real14 cache）＋localized 修復：修復
  控制器 `python -m vacant_network.reqloop.repair`（--task/--draft/
  --out/--rounds/--timeout；內部 reuse adapters/run.py run_agent；
  repair.py 凍結、不加單案例規則）。
- 獨立 scorer：~/dev/ops/effects_20261105/independent_score.py
  （依 ops/audits/effects_20261105_summary.json 的 source_root 重算；
  sudo -n 跑 lab scorer，只 pass/status 等欄位出評分端、評分永不回
  饋修復；嚴禁讀 hidden/scorer 源）。
- 印出：修好（錯→對）、對→錯、未解決＋停因；成本依 repair.py 口徑：
  calls＝修復 session 數、model_calls＝實際 API 呼叫數（兩量嚴分）、
  token 缺＝UNKNOWN（絕不填 0）、任一輪 usage 缺⇒總成本 UNKNOWN；
  對照手寫 9/9（g2-truth：localized 9/9、generic 7/9）與
  effects_20261105 參考（policy30 generic 7/10、localized 6/10；
  once20 generic 7/10、localized 4/10；開發選樣單 rep、不宣稱較好）。
- 長實驗：先寫 phase3（run_eval.py 第三項）＋凍結清單/hash/預算，
  再發射；發射後不等，看 progress。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連
vibe；不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝
UNKNOWN 不填 0。
