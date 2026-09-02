# R523（fable 稽核輪）：對 R522「A 曲線第二點」的獨立重算——判準寫在任何數字算出來之前

（2026-09-02 UTC 22:15 起，Fable 5.1。round522 交棒的稽核重點：R522 **刻意沿用** R519 的
parser 與參考解執行器（`exec` 逐字取用），所以它的 G1 只證明「同一把尺套到別的模型上沒套歪」，
**沒有**證明尺本身對 qwen 的輸出格式是對的。本輪用**第三條程式路徑**重算 A_qwen。）

## 一、稽核輪的限制（照模型政策）

- **不改任何實驗程式碼**（`ops/gain/`、`vacant/`）。只新增 `runs/analysis_round523_audit/` 下的稽核腳本與輸出。
- 不起 run、零 API 呼叫、不動 1004／8765、不刪任何 run 目錄。
- 每個數字附 rows/votes 檔的行數與 sha256 前 8 碼。

## 二、開場對帳（DECISION 寫之前已看過的東西，照實列）

- `acurve_r522.json` sha8 `b1132799`（與 GAIN_STATE 一致）、`votes_r522.jsonl` 3388 行 sha8 `bbccb6d9`、
  題庫 `MbppPlus-v0.2.0.jsonl.gz` sha8 `af43697e`。
- 全部 44 個 run 的 ok review 呼叫：**每個 (run, arm, task, agent, model) 剛好 1 票，沒有重複計票**（3388/3388）。
- `model` 欄有 `qwen_qwen3.6-35b-a3b` 62 張，其 `model_configured` 全是 `qwen/qwen3.6-35b-a3b` ⇒ R522 的
  `norm_model` 合併有據。cline-pass 三顆 `model_configured=None`，n≤1，事前就不進曲線。
- **無法核的**：所有 run 都早於 round520 的 `server_model` 落盤，`model` 是**請求的**模型名，不是伺服器回報的。
  這是 R520 已記錄的缺口，本輪不能補、也不當作推翻理由（8765 依名載模型，沒有證據顯示替換）。

## 三、第三條路徑的定義（與 R518 §十一 同義，實作零共用）

- **parser**：逐行找 `TEST_ARGS:` 與 `EXPECTED:`（大小寫不敏感、允許前導空白），值 `NONE` ⇒ 不可解析；
  `ast.literal_eval`；args 必須是 list/tuple。**不 `exec` R519 的程式碼，不 import R522 的模組。**
- **harness 相等**：數值 `math.isclose(rel=abs=1e-9)`；list/tuple 互通、逐元；dict 鍵集相同、遞迴；其餘 `==`。
- **參考解執行**：`canonical_solution` 在**同一個直譯器**內 `exec` ＋ `signal.alarm(10)`（R519/R522 用子行程；
  路徑刻意不同）。任何例外 ⇒ harness=False。
- **vote_pass**：第一個非空行去空白後大小寫不敏感等於 `VERDICT: PASS`（R522 用「第一行」不是「第一個非空行」；
  qwen 的回應常以 `\n\n` 開頭，這個差異**必須**量出來，見 C4）。

## 四、判準（先寫）

| 檢查 | PASS 條件 | 不過的後果 |
|---|---|---|
| C1 A_qwen 第三路徑 | harness 計數 = **20/108**，逐位 | 列出每一張不一致的票並判定哪條路徑對；以**本輪路徑**重算 Wilson 上界 |
| C1' A_gemma 第三路徑 | = **162/305** | 同上 |
| C2 逐票對帳 | 3388 張的 (parseable, harness) 與 `votes_r522.jsonl` 不一致數 = 0 | 每一張列出、歸類（parser／相等判定／執行器） |
| C3 R522 裁決是否站得住 | 以本輪路徑算出的 A_qwen **Wilson95 上界 < 0.80** | 上界 ≥ 0.80 ⇒ R522 §九-4 裁決降級為「懸而未決」，CONCLUSION 追補段要改 |
| C4 PASS 率 | qwen 投 PASS 的比例以「第一個非空行」重算；與 R522 的 95.5% 差 < 1pp | 差 ≥ 1pp ⇒ R522 「95.5%」要改成本輪數字（不影響 A） |
| C5 分母補報 | A_qwen 限制在 `in_rows=True`（非 void 題）的版本；以及分 vote_pass 兩群（R518 §十一 要求報的） | 只報，不當閘門 |

**C3 是唯一會動裁決的閘門。** C1/C2 的不一致若能歸因且不改變 C3，裁決維持；若不能歸因，
本輪只寫「無法重現」，不寫「推翻」也不寫「確認」。

## 五、推翻本輪的條件

- 若本輪 parser 在 qwen 的**不可解析**票裡多解析出 ≥ 3 張具體反例（R522 §七 的門檻），A_qwen 要用擴大的分母重算；
  若擴大後 Wilson 上界 ≥ 0.80，C3 失敗。
- 若 in-process 執行器與子行程執行器在同一張票上給出不同 harness 值，以**人眼核參考解實際輸出**為準，不是以票數多者為準。

## 六、量測結果

（量完補。）
