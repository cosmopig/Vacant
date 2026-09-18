# R519 稽核：round518 的 P-CEIL（A=0.609）獨立重算、敏感度、與是否寫進 CONCLUSION

（2026-09-02 UTC 21:37–22:05，**Fable 5.1 稽核輪**。依模型政策：稽核輪只重算、裁決、
開提案，**不改實驗碼**。本輪零 API 呼叫、零 run。）

## 一、稽核對象與資料指紋

| 檔 | 行數 | sha256 前 8 碼 |
|---|---|---|
| `runs/g_r441_gemma_only_mbpp_b/rows.jsonl` | 525 | `440d973c` |
| `runs/g_r441_gemma_only_mbpp_b/calls.jsonl` | 1986 | `3d24b73d` |

與 round518 用的是同一份資料（round518 未記指紋；本輪起記）。

## 二、獨立重算的路徑（跟 round518 的 `ceiling_r518.py` 沒有共用程式碼）

腳本：`runs/g_r441_gemma_only_mbpp_b/analysis_round519/ceiling_audit_r519.py`（輸出 `.json` 同目錄）。

- **不 import `ops.gain.gain_run`**。直接讀 `MbppPlus-v0.2.0.jsonl.gz` 取 `canonical_solution`／`entry_point`。
- 自己寫的 claim parser（regex + `literal_eval`），自己的 `VERDICT: PASS` 判定。
- 參考解在獨立 subprocess（`python3 -I`）執行，不經 vacant sandbox；args/expected 以 `repr` 傳遞再 `literal_eval`（與 harness 的 `{args!r}` 同語意）。
- 逐票對到 `rows.review_evidence` 的 status：用 call 的頂層 `agent_id` ↔ evidence 的 `agent_id`（逐題唯一，歧義 0）。
- 三種相等判定並列：`strict`（`==`）、`harness`（重寫 `__vacant_equal`：isclose 1e-9、list~tuple、dict 遞迴）、
  `loose`（harness ＋ 順序不敏感、set~list、bool~int、`str()` 化相等）。**loose 是 A 的上界**，用來回答
  §十四「相等判定有沒有系統性誤判」。

## 三、結果：round518 的每一個數字逐位重現

```
ON 評審票（對齊 rows）501；逐題票數 vs review_evidence 筆數不一致 0
  PASS 312 ／ FAIL 不可解析 33 ／ FAIL 可解析 156     （= round518）

A（harness 判定）           95/156 = 0.6090   Wilson95 [0.5307, 0.6821]   ← 與 round518 逐位相同
A（strict ==）              94/156 = 0.6026
A（loose 上界）             98/156 = 0.6282   Wilson95 [0.5501, 0.7001]

分群（harness）  candidate_passed_claim   62/64 = 0.9688   ← = round518
                 counterexample_confirmed 21/61 = 0.3443   ← = round518（loose 24/61 = 0.3934）
                 outside_input_contract   12/31 = 0.3871   ← = round518（strict 11/31）
```

**harness-A 為 False 的 61 票拆成三類**：

| 類 | 票數 | 說明 |
|---|---|---|
| 值真的不同 | 42 | 參考解跑出的值與評審宣稱的 EXPECTED 不同，loose 判定也不同 |
| 參考解本身拋例外 | 16 | TypeError 11、ZeroDivisionError 2、ValueError／IndexError／AttributeError 各 1；**其中 11 票在 `outside_input_contract`、5 票在 `counterexample_confirmed`** |
| 只有 loose 才相等 | 3 | 全是 `Mbpp/7`：評審給 set、參考解回 list，元素相同 |

**敏感度（全部在判準觸發之後做，不是換判準）**：

| 口徑 | A | Wilson95 上界 |
|---|---|---|
| harness，全部 156 | 0.6090 | 0.6821 |
| loose，全部 156 | 0.6282 | 0.7001 |
| harness，排除參考解拋例外的 16 票 | 95/140 = 0.6786 | 0.7503 |
| loose，排除 16 票 | 98/140 = 0.7000 | 0.7697 |
| harness，再排除 outside_input_contract | 83/120 = 0.6917 | 0.7673 |
| **loose，排除例外＋契約外（對評審最寬容）** | 86/120 = 0.7167 | **0.7896** |

**最寬容的口徑上界仍 < 0.80。** §十一 預註冊的分支（A < 0.80 ⇒ 瓶頸在原始能力、梯子不再往上疊）
在稽核後**維持**。§十四 要求的「另一個系統性誤判來源」本輪找過：loose-only 只有 3 票（1.9%），
參考解例外 16 票（10.3%）——兩者加起來把 A 從 0.61 推到最多 0.72，推不過 0.80。

## 四、機制敘事的稽核（§十二「逆向選擇器」）

```
confirmed 61 票：初稿 hidden 真的失敗 41（0.672，= round518 的精度數字）
  評審 EXPECTED 對 ⇒ 初稿 hidden 失敗   21/21（EXPECTED 對且初稿 hidden 過 = 0）
  評審 EXPECTED 錯 ＆ 初稿 hidden 過      20      ← 純粹評審算錯，初稿無辜
  評審 EXPECTED 錯 ＆ 初稿 hidden 失敗    20      ← 指對了有 bug、給錯了答案
```

round518 寫「約 20 題是指對了有 bug 但給錯答案」——精確數是 **20 票**（票不是題）。
「逆向選擇器」的推論與資料一致。**稽核加一條限制**：`candidate_passed_claim` 的 0.97 是
**在「評審答案＝初稿輸出」這個條件下**量的，而初稿大多正確，所以那個 0.97 接近套套邏輯，
**不能引用成「碼對的時候評審就準」**；能對外說的只有合併的 A=0.61 與 confirmed 的 0.34。

**眼睛確認**（seed 519 從 32 票「confirmed 且值真的不同」隨機抽 8）：7 票評審明顯算錯
（例：`Mbpp/296` 逆序數 [2,1,1] 評審說 3 實為 2；`Mbpp/259` tuple 逐位 max 給錯；`Mbpp/739` 16 位數
三角數索引給 18／14142136，實為 44721360）；1 票（`Mbpp/563`，跳脫引號）是題目規格歧義、
參考解定義真值——這種算在 A 的分母裡對評審略不利，但只 1/8，改不了結論。

## 五、順帶稽核：無聲替換／半殘資料／對帳

- `calls.jsonl` 1986 筆，`model == model_configured == gemma-4-12b-it-qat` **全部 1986 筆**，api 全為 8765 中轉。
  **沒有無聲替換的痕跡**（但這只是「客戶端設定值」，伺服端實際載入哪顆仍無逐筆紀錄——R516 §8 缺口未修）。
- 55 筆 `ok=false` 且 response 為空（＝重試／void 的原始紀錄），`notes.jsonl` 12 筆 ON void ＋ 1 筆 preflight，與 R516 一致。
- 三臂對帳（rows 重算 vs R516）：OFF 122/179=68.16%、ON 122/167=73.05%、OFF5 132/179=73.74%；
  ON vs OFF5 **b=11 c=12 p=1.0000（−0.60pp）**；ON vs OFF b=17 c=7 p=0.0639；OFF5 vs OFF b=12 c=2 p=0.0129。
  **全部與 R516 相同。**
- `summary.json`：ON `complete=false`（有 void 就永遠 false，R516 §8 的邏輯瑕疵**仍在**）。

## 六、裁決

1. **round518 的 A=0.609 成立**，獨立路徑逐位重現；六種敏感度口徑的 Wilson 上界最高 0.7896，全部 < 0.80。
   §十三「梯子在 L0 之後停住」**維持**。
2. **寫進 CONCLUSION**：round518 把「A 要不要進 CONCLUSION」交給稽核輪。本輪裁決：**寫**——但只寫成
   「機制解釋」的補節，並且 (a) 註明是同一 run 上的探索性分析、(b) 附資料指紋、(c) 不動 R516 §3d
   「評審準確率分不出 0、不寫附註」的裁決（那條管的是家族歸因，不是 A）。理由：CONCLUSION 的
   「邊界」節目前寫著「換更強的評審模型都可能翻盤」，A 曲線是唯一能把這句話變成可量的東西，不寫的話
   下一個讀結論的人不知道該量什麼。同時補上 E1 的等預算複製結果——CONCLUSION 至今**一個字都沒提 E1**
   （R516 只裁「不寫評審準確率附註」，沒裁「不寫 E1」；第二個乾淨 run 複製同一個答案是結論的直接證據）。
3. **不改實驗碼**（稽核輪規則）。

## 七、給下一輪（sonnet，碼工）的提案

1. R516 §8 兩項落盤缺口（伺服端 `model` 逐筆；`complete` 區分「void 但已處理完」）。改碼要附測試，
   植入缺陷測試要能證明「舊版會把有 void 的 run 永遠標成未完成」。
2. 新增觀察（本輪）：`counterexample_confirmed` 裡有 5/61 票的 args 連**參考解**都會拋例外
   （`Mbpp/620` 全零 ZeroDivision、`Mbpp/567` 混型 list、`Mbpp/573` 空 list、`Mbpp/724` 負數）——契約檢查
   放行了不在題意內的輸入。**不要**為此把參考解接進 verify 路徑（V/GT 分離）；可考慮的是把
   「初稿在宣稱的 args 上拋例外」與「初稿回傳不同的值」分成兩種 status 落盤，先量再說。這是提案，不是判準。

## 八、推翻條件

- 若有人指出本輪 `loose` 判定漏掉某類等價（例如浮點容忍度該放到 1e-6、或字串大小寫），要**量出**那一類
  的票數；要翻轉結論得把 A 的上界推過 0.80，也就是至少再多 **≈13 票**（156 票口徑）從錯變對。
- 若換更強的評審模型（需人類動 1004）量到 A ≥ 0.80，R518 §十四 已寫：L3 復活，判準不重訂。
