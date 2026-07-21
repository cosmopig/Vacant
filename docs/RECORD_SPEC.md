# RECORD_SPEC — 一次 run 的最小證據包

> 承重點：17 號 P0-2「紀錄基建」。這份規格定義一次實驗 run 落盤後，**別人不必信任你、
> 只憑磁碟上的檔案就能複核**所需的最小證據集合。任何進入統計的 run 都必須先通過本規格
> （`vacant record check`）；缺任一必要項＝該 run 記錄層 `infra_void`，**不得進統計**。

## 1. 目錄結構

```
runs/<experiment>/<run_id>/
├── manifest.json      # 執行環境與參數的單一真相（必要）
├── wire.jsonl         # MCP 全訊息側錄（可缺，須在 manifest.missing 註明理由）
├── model_io.jsonl     # 每次模型呼叫的完整 I/O（可缺，須在 manifest.missing 註明理由）
├── ledger_events.jsonl# 生態事件流（ROUTE/REVIEW/AUDIT/SLASH/DELIVERED…）（必要）
├── chain_verify.txt   # 離線重驗簽章鏈的「實際執行輸出」（必要）
├── trust_cards/*.json # 交付信任狀（可缺；若有，card_verify.txt 必存在）
├── card_verify.txt    # 對 trust_cards 逐張獨立驗簽的實際輸出（有卡即必要）
├── anomalies.md       # 非乾淨事件逐筆；無異常也要寫「無」（必要）
└── SHA256SUMS         # 對以上全部檔案的 sha256（不含自身）（必要）
```

## 2. 必要項 vs 可缺項

| 檔案 | 分類 | 規則 |
|------|------|------|
| `manifest.json` | 必要 | 缺＝`infra_void` |
| `ledger_events.jsonl` | 必要 | 缺＝`infra_void` |
| `chain_verify.txt` | 必要 | 恆存在；無居民鏈可驗時寫 `SKIPPED` 與理由 |
| `anomalies.md` | 必要 | 恆存在；無異常寫「無」 |
| `SHA256SUMS` | 必要 | 對其餘全部檔案逐檔 sha256（排除自身） |
| `wire.jsonl` | 可缺 | 缺則 `manifest.missing` 須列出並附理由 |
| `model_io.jsonl` | 可缺 | 缺則 `manifest.missing` 須列出並附理由 |
| `trust_cards/*.json` | 可缺 | run 可能無交付；**若有卡則 `card_verify.txt` 必存在** |
| `card_verify.txt` | 條件必要 | 有 `trust_cards/*.json` 時必存在、非空、不含 `FAIL` |

**可缺不等於可靜默省略**：wire.jsonl / model_io.jsonl 每一項缺席都必須在
`manifest.missing`（`{檔名: 理由}`）留下明確理由，否則 `check` 判為 problem。
「沒有理由的缺席」與「竄改」在記錄紀律上同罪。

## 3. manifest.json 必要欄位

| 欄位 | 型別 | 說明 |
|------|------|------|
| `repo_commit` | str | `git rev-parse HEAD`；抓不到寫 `"unknown"` 並記入 `missing` |
| `pip_freeze` | list[str] | `python -m pip freeze` 逐行 |
| `os` | str | `platform.platform()` |
| `python` | str | 直譯器版本 |
| `model_id` | str\|null | 受測模型 id（由 run harness 經 `extra_meta` 提供） |
| `endpoint` | str\|null | 模型端點（base URL / in-process） |
| `no_think` | bool\|null | 是否關閉 reasoning（reasoning 模型的關鍵開關） |
| `seeds` | list\|null | 本 run 使用的所有種子 |
| `machine` | str | 主機識別（node + arch） |
| `utc_start` | str | run 起始 UTC ISO-8601 |
| `utc_end` | str | run 結束 UTC ISO-8601（pack 時刻） |
| `trust_arm` | str\|null | `on` / `off` / 其他臂別（CLAUDE.md 鐵律 4：記憶不跨臂共享） |
| `scripts` | dict[str,str] | 產生本 run 的腳本路徑 → sha256 |
| `missing` | dict[str,str] | 缺席的可缺項 → 理由（`pack` 自動補齊） |

凡 `pack` 無法自動偵測、`extra_meta` 又未提供的欄位（`model_id` / `endpoint` /
`no_think` / `seeds` / `trust_arm` / `scripts`），一律填 null/空並登記進 `missing`，
讓「這件事沒記錄」是被斷言的、而非讀者從空白腦補的。

## 4. 誠實邊界（規格的一部分，不可刪）

- `pack` 只能保證「**這個包是完整且自洽的**」（必要項齊、雜湊自洽、驗證輸出落盤）；
  **不能保證「內容是真的」**。內容真實性由簽章鏈（`chain_verify.txt`）與稽核
  （`auditor` / `card_verify.txt`）承擔——那是密碼學與重跑檢查的責任，不是打包器的。
- 宣稱「可驗證」者**必附驗證的實際執行輸出**：`chain_verify.txt` 是離線重驗簽章鏈的
  真輸出、`card_verify.txt` 是逐張獨立驗簽的真輸出。沒有輸出的「已驗證」＝形同無驗證。
- `SHA256SUMS` 偵測（detects）落盤後的竄改，不預防（not prevents）；它證明的是
  「check 當下這些檔與 pack 當下一致」，不證明 pack 當下的內容未被作者本人捏造——
  後者由簽章鏈的不可偽造性承擔。

## 5. infra_void / retry×4 / parse_void 規律（引 09 §3.5；CLAUDE.md 鐵律 3）

- **全 I/O JSONL 落盤**：wire / model_io / ledger 全部逐行 JSON，可離線重放。
- **retry×4**：單次模型/端點呼叫內建重試（見 `substrate.py`）；N 次全失敗才升級。
- **infra_void**：基建層失敗（端點瞬斷、retry 全滅）的試次**永不計為一票**，
  且不寫入統計 ledger（下次 resume 自動重試，瞬斷不留永久洞）。
- **parse_void**：模型輸出無法解析出可檢查答案者，同樣不計為一票、需登記於 `anomalies.md`。
- **記錄層 infra_void**：本規格新增的一層——**證據包本身**缺必要項或雜湊對不上時，
  整個 run 的記錄層作廢，不得進統計。`vacant record check` 是它的可執行判準。

## 6. 使用

```bash
vacant record pack  runs/x1/run_0007      # 就地整理成本規格佈局、產出 manifest 與 SHA256SUMS
vacant record check runs/x1/run_0007      # 逐項核對；有問題逐條印出、exit code 非 0
```

## 7. 私鑰排除（07-09 實錄教訓 §4.4；prevents 級紀律）

證據包**不得攜帶居民私鑰**（`residents/*/trust/identity.key`）。證據包的用途是
離線複核——驗簽章鏈用同目錄的 `identity.pub`＋`vacant_id` 即足夠；私鑰入包＝
任何拿到包的人都能偽造該居民未來的簽章，把「可複核」擴大成「可冒名」，問責
根基即毀。規則：

- `pack`：私鑰**不進** `SHA256SUMS`，且把包內存在的私鑰路徑逐一寫進
  `manifest.excluded_private_keys`——「知道它在、刻意不打包」是明白斷言，
  不是靜默省略（與 §2「缺席須有理由」同紀律，私鑰尤甚）。
- `check`：①`SHA256SUMS` 出現私鑰路徑 → FAIL；②磁碟上存在私鑰但
  `manifest.excluded_private_keys` 未聲明 → FAIL。
- 複核者需要驗鏈時使用 `identity.pub`（公鑰本就設計為可公開）。
