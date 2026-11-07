# 現在（第 1189 輪，2026-11-07）

## r1189：real14 門禁 PASS（vq-el4.4 收）
- 審查指示：review auto/argon 後 merge → 續 vq-el4.4。已 merge（含 WIP ae6448a1：
  extract.py `deliverable_not_in_request` 守衛、run_eval `load_cell_request_text` 附
  contract.md、cache 記 prompt_sha256＋raw_output 可離線重建、rebuild_from_logs.py）。
- 根因（r1188 冤枉 4/5）：prompt 漏了公開 contract.md，擷取模型只能猜交付檔名
  （answer、@x[y]、/app/answer.txt）→ 草稿明明有 answer.txt 也全判 missing_file。
- 修法＝argon WIP 設計路徑：新 prompt（request.md＋contract.md）重擷取 14 cell
  （14 次/~190k tok，日預算內；舊 cache 是舊 prompt 結果，沿用則數字不變——
  run_eval.py docstring 明示「不靜默沿用舊 prompt 的需求」）。
- **結果：抓錯 9/9（>=5）、冤枉 1/5（<=1）→ 門禁 PASS（RC=0）**。
  r1188 的 4 份冤枉（dab_035/057/105/dabstep-13）3 份轉 CLEAN；dab_039 改以
  contract 點名的 answer.txt 判「答案檔不存在」＝真抓錯。
- 重跑驗證 cache：0 新呼叫（ledger 85→85 行）、14 格結果逐字相同、門禁同 PASS。
- 證據：`ops/reqloop/extract/out/eval_real14_glm53_r2.json`；r1188 FAIL 快照
  `ops/reqloop/extract/out/real14_round1/`（14 檔）。
- 殘留冤枉 dab_057-pi-A（1/5 在門限內）3 因：req-3/req-5 對原始字串欄
  （"630308[495000-801000]"）取可解析子集重算 r=0.52 vs 0.97（擷取解釋錯）；
  req-6 deliverable 誤綁資料檔 data/estimated_numbers.csv；req-4 round 參數在
  item 層而 checker 讀 recompute 層（0.96966 vs 0.97、atol 1e-6 → 假 FAIL；
  已 note 進 vq-el4.5 待修，修了該 cell 仍 FALSE）。
- vq-el4.4 已 close（bd reason 帶證據路徑）；測試 test_reqloop_extract/
  run_eval/checks 148 passed。

## 下一步（vq-el4.5）
- 擷取需求＋localized 修復跑 9 份錯、獨立 scorer 評分（印出修好幾份、呼叫數、
  token，跟手寫 9/9 對照）。先修 dab_057 型 round 參數層級錯配（vq-el4.5 note）。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
