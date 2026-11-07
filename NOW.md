# NOW — R-loop (auto/qwen27b)

## 第 1151 輪 (2026-11-07 08:22 +0800)
**KV 鍵級保留審計接線（r1148 audit_kv_preservation → repair_slice/g2 報告）＋ r1150 A/B raw 補算審計證據**

- 工單 R20261107_0022-1（六要素齊、done/）：KV 單一交付物「保留其餘成果」原本無機械落點（檔案級 satisfied_* 對單一交付物 by design 不適用；manifest independent_acceptance(2)「9 條已滿足行位元組相同（審計端計算）」無產品欄位）→ repair_slice 報告新增 kv_preserved/kv_mutated（初始驗已滿足 key 中值位元組相同＝preserved；值改/缺失/重複/檔案缺＝mutated，保守分類；零輪 no_gap⇒兩欄空＝審計未執行）＋ g2 每格/總計/人讀輸出。純資訊審計、不改變退出碼（argon 20261106_1121：不得誤拒正確候選）。
- TDD 紅→綠：test_kv_preservation_audit_single_deliverable（4 情境：C 修復 8 鍵保留＋exit 0；C 篡改 pre_mean⇒kv_mutated＋regressed；A 重驗 10 鍵保留；A no_gap 兩欄空）。
- 驗收：5 檔 checks/g2/repair/real_slice/g1_gate＝**221 passed**。
- r1150 A/B raw 補算（審計端、離線、同一產品函式）：C 兩格 **8/8 保留、0 mutated**；A generic **10/10 保留、0 mutated**；A localized no_gap＝審計未執行（by design）——「保留其餘 9 個通過 key」（資深審查 #3）自此有機械證據；~/dev/ops/audits/realab_kv_preservation_20261107.json。
- 紅線：0 模型呼叫、0 發射、未加 regex/靜態 prompt/重試、未動 main、未自 push（loop 自動推）、未讀 hidden/scorer、缺值 UNKNOWN 不填 0、未改凍結 manifest。

## 第 1150 輪 (2026-11-07 08:05 +0800)
**redo 審查點名 6 檔（實讀＋現樹重跑）＋發射 4 格 A/B（已完成、raw 在案）**

- 實讀 6 檔＋重跑：5 檔 checks/g2/repair/real_slice/g1_gate＝**220 passed**；g2＋real_slice＝46 passed；針守衛 -1.13 重算 1 passed；baseline C 9/11（pre/post_kurtosis FAIL、-1.17 vs 重算、expected_in_evidence=false）＋A 11/11。
- **4 格 A/B 已完成**（unit `vacant-realab-20261107.service`、raw `~/dev/ops/realab_20261107/g2_result.json`、4 格 exit 0、00:06–00:10Z）：
  - C(bad) 兩臂 9/11→**11/11**（fixed=[pre,post_kurtosis]、regressed=0、source_tampered=false）。
  - A(good) 兩臂 11/11→**11/11**（fixed=0、regressed=0、**right_to_wrong=0**；localized no_gap 0 呼叫）。
  - 總 65 calls/979,588 tok/255,833ms；C generic 29 calls vs localized 14、A generic 22 vs localized 0（本 rep localized 省，r1145 反之＝單 rep 噪音）。
  - hidden_after=**UNKNOWN**（本地無權重跑、缺值不填 0）；單 rep 開發選樣、**不宣稱 localized 較好**。
- 需求端三問（11-05）：①內容錯誤可修回＝**是**（2 rep）；②已正確產出被保留＝**是**；③成本＝總量小但臂間優勢單 rep 翻轉、不宣稱。
- 紅線：未動 main、未自 push、未讀 hidden/scorer、未加 regex/靜態 prompt/重試、未改凍結 manifest；repo 零代碼改動。

## 待辦
- [x] （r1151 完成）鍵級保留審計接線＋ raw 補算證據（~/dev/ops/audits/realab_kv_preservation_20261107.json）。
- [ ] vq-6rp（dabstep-1753）／vq-5nz.6 仍候需求端點名。
- [ ] 是否擴量＝新決策、需另行授權（11-06#4「證明可修回後再擴量」；本 4 格已證明可修回＋保留）。
