# 讓依賴有根據：離線歸檔分析

這是**實際模型跑數的事後分析**，不是產品功能，也不是人類使用者實驗。
合成資料只用於 `tests/test_reliance_claims.py` 的回歸案例。

從 repo 根目錄執行（不呼叫模型、不執行歸檔內的指令）：

```sh
.venv/bin/python ops/reliance/analyze_receipts.py
.venv/bin/python ops/reliance/validate_receipts.py
.venv/bin/python ops/reliance/claims.py
```

- 預設快取：`~/.cache/vacant/reliance`；可用環境變數 `VACANT_RELIANCE_CACHE` 指定 **repo 外**的目錄。
- `cache.py` 用 Python tarfile 讀取已追蹤的 repo 歸檔，排除金鑰與非普通檔案；不 checkout 其他分支。
  歸檔內容 SHA256 改變才重新解壓。不把原始逐列輸出寫入 repo。
- Discovery：`ops/eval/evidence_20260925/formal/formal_jobs.tar.xz`。
- Held-out／重跑：`ops/eval/evidence_20260927_nocap/{u274,s36nc}/raw/chunk_*.tar.xz`；
  `ops/eval/evidence_20260926_local/{formal,s36}/` 的 jobs 歸檔。
- 前兩支保留探索／重跑分析分界；`answer_overlap()` 函式原文 SHA256 為
  `06d1a91dc7e121a5b9f606d2da8cf7920757b57d7f612b03ca7a8cc429efab2d`，驗證器啟動時斷言。
  搬移後改釘函式原文，而非包含舊絕對路徑的整支檔案。規則內容未改。

快取輸出：`receipt_rows.jsonl`、`receipt_analysis.md`、`heldout_receipt_rows.jsonl`、
`heldout_receipt_analysis.md`、`process_claim_rows.jsonl`、`process_claim_summary.md`、
`manual_review_candidates.jsonl`。完整資料只在快取；repo 僅保留摘要與短摘錄。

流程稽核先以全部 1,476 筆已納入且有 GT 的跑數重建最後一個非工具 agent 訊息；
只用該訊息**之前**的步驟。無最後訊息的跑數仍寫入逐列檔，但不算有主張，也不放進交件條件機率分母。
這個「交件」定義是最後訊息存在，**不同於**凍結規則使用的 answer.txt 存在／答案可恢復。
部分 ATIF 把 thought channel 留在最後訊息；本分析沒有另造未歸檔的使用者可見訊息。

## 規則邊界

| 類型 | SUPPORTED 的操作定義 | CONTRADICTED 的操作定義／保留 |
|---|---|---|
| read/open/use 檔案 | 成功 read 或讀取型 shell 指令具名提及同一路徑；裸檔名容許 basename 對應 | 找不到直接讀取；間接腳本／工作目錄仍可能誤判 |
| compute/filter | 成功 Python/awk/grep/cut/sort 等指令代理 | 沒有符合的成功指令；不查演算法是否真的實作該句 |
| verify/confirm | 答案先出現在特定計算指令輸出，之後不同指令再輸出同一答案；批次呼叫只看該指令的輸出 | ≤1 個不同計算指令；多個但無法定位核對則 UNCHECKABLE |
| run/test | 成功 shell／測試 runner；若具名引用命令則需匹配 | 無符合紀錄；不推論測試覆蓋率 |
| 數量／引號中的數字 | 各數值以 float 精確匹配輸出；比例／算式句也擷取其餘數字，包含所述結果 | 有數值缺席；若缺值出現在命令參數，或跑數有 exception，降為 UNCHECKABLE |
| consistently／一貫 | 不自動支持 | 一律 UNCHECKABLE；需要領域語意 |

英文與中文規則只做簡單句子比對；否定／未來式略過。不同指令只是**獨立核對的代理**，不是語意獨立性。
SUPPORTED 不表示數值正確或主張整句成立；CONTRADICTED 也只是待人工核對的候選。
精確數值匹配會把正常四捨五入／隱含加總列紅，這是本版刻意揭露的主要限制。

人工審查的候選依資料集、arm、trial 排序後，以 `random.Random(20261001)` 從全部紅標主張抽 20 筆。
人工結果不回寫模型，也不以 GT 決定標籤；見 [REVIEW.md](REVIEW.md)；整體摘要見 [FINDINGS.md](FINDINGS.md)。
