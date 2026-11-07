# NOW — R-loop (auto/qwen27b)

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
- [ ] （可選）以 raw 結果彙整 audits summary 檔（fixed/regressed/cost/UNKNOWN 如實、供下輪引用）。
- [ ] vq-6rp（dabstep-1753）／vq-5nz.6 仍候點名（不阻本 A/B）。
- [ ] 是否擴量＝新決策、需另行授權（11-06#4「證明可修回後再擴量」；本 4 格已證明可修回＋保留）。
