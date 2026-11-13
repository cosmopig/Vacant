# G4 預註冊實驗包（status: preregistered；未經人類點頭禁止真發射）

工單：P20261113_0708-2-g4-preregistration。依據：2026-11-13 人類定案第 4 條——成效門達標
（現況 66/76 可確定性檢查、0 假 PASS）後由規劃者開 G4 預註冊工單；**發射前要人類點頭**。

## 設計（12 格）
- 4 題：dab_725 / dab_587 / dab_657 / dab_517（有凍結規格、可確定性檢查的題）。
- 3 臂：`native_pi`（無需求清單）／`reqlist_only`（需求清單、無修復迴圈）／`full_rloop`（需求清單＋需求驅動修復迴圈）。
- 每格直接重用 `ops/reqloop/g4/specs/` 的凍結需求規格（D4 定案：正式發射直接重用、不重新擷取——G3.3 已證明重新擷取不穩定）。
- 預註冊假設（發射前不下方向性結論）：full_rloop 較 native_pi 與 reqlist_only 更能減少原始需求的缺口；實際成效以發射後 REPORT＋成本為準。model／budget 於人類簽核時定案並寫回 manifest（現為 null）。

## 凍結規格 sha256 清單
自 hash＝整份規格（除 spec_sha256 欄）canonical JSON 的 sha256（`freeze_specs.py` 同口徑；改任何一字必紅）：

| task | 檔 | spec_sha256 | n_items |
|---|---|---|---|
| dab_725 | ops/reqloop/g4/specs/dab_725.json | 5b63ebbde4210b35aa17ee476c0f1f8975b6013c9527c9ec64ed243e892def10 | 6 |
| dab_587 | ops/reqloop/g4/specs/dab_587.json | ec5f83fa63eb5442e5aeb877f1552c3a1f5c8d90ca7fae907017374636cf8857 | 5 |
| dab_657 | ops/reqloop/g4/specs/dab_657.json | 0284bfe8cb713a081355b5427bb2e08b4d13dfec4281a700acb6aaee7875adbb | 8 |
| dab_517 | ops/reqloop/g4/specs/dab_517.json | 046111f8a2cff72cca35323b99a6774ab55f94b1f9349258f7dbca294c05fb77 | 6 |

## 對照設計
- 三臂同起始草稿、同上下文、同模型、同預算（簽核時定案）；成本自原始 usage 讀、缺值 UNKNOWN。
- 交付物全為非輸入檔 `answer.txt`；輸入檔永遠不可當交付物（D2 口徑）。
- tamper／UNKNOWN 不算成功；FAIL→UNKNOWN 不算修好；任何原有 PASS 退步都要記錄。

## 核准門禁（fail-closed）
1. `manifest.json` 的 `human_signoff == null` 時，任何發射啟動器必須拒絕執行——參考門
   `decide_launch()` 與負控制測試在 `tests/test_g4_preregistration.py`。
2. 人類簽核＝把 `manifest.json` 的 `human_signoff` 填為 `{by, ts, sha256}`，其中 sha256 為簽核時
   整檔（`human_signoff` 仍為 null）UTF-8 字節的 sha256；簽核後先重跑測試確認 0 model calls。
3. 本包不含任何真模型呼叫；dry-run（`test_dry_run_zero_model_calls`）即 0 model calls 驗收。

## 驗收
`python3 -m pytest tests/test_g4_preregistration.py` → 3 passed。
