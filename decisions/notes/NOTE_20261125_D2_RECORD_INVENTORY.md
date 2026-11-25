# NOTE 2026-11-25 — 現有的紀錄／稽核功能，在「來源變了只重查受影響的宣稱」（D2′）裡哪些能直接用

範圍：auto/redo `6cdaad556` 之前的產品碼（rc6-final 之後的 auto/redo；病歷格式與 rc6-final 相同），
情境是 pi＋本機模型依幾張網頁填一份 20 條事實的報告，之後來源改了要維護。
依據：讀碼，加上兩次真模型實跑（gemma-4-12b，1003，掛 `vacant install --agents pi` 真的寫出的擴充；
`probe1`／`probe2` 在 scratchpad，未入庫）。只記事實。

## 直接可用

| 功能 | 在這個情境做到什麼 | 實測 |
|---|---|---|
| 病歷（`trace/recorder.py`＋`capture.py`） | 零設定（`install.json` 的 `mode: evidence`，不用契約、不用 `VACANT_TRACE`）就記下每一次工具呼叫：工具、輸入、輸出（內容定址）、前後的工作區索引、寫了哪個檔 | 工具呼叫數＝鏈上 step 數：8／8（probe2）、112／112（probe1，模型陷入迴圈的那一跑）。`curl` 的輸出逐字存進 `objects/` |
| 簽章鏈 | 一個專案一條鏈，`seq` 連續、`prev_hash` 串接、每筆 Ed25519 簽章；`vacant trace verify` 可驗 | — |
| 追緝（`trace/blame.py`） | 給「檔案：行：值」，追到：寫下這一行的那一步 → 值出現在哪一步的輸出 → 那一步抓了哪個網址（`source.kind = url`、`ref`、`step`、`observed`） | probe2 `report.md:6 $32` → step 8 edit ← step 3 `curl …/p1.html` |
| 數字抽取（`trace/evidence.numbers_in`） | 交件裡的具體數字（千分位、幣別都認） | `$32`、`1,800`、`100` 都抽得到 |
| 內容定址庫的格式 | 索引是 JSON、內容是 `objects/<前兩碼>/<sha256>`，**不用 Vacant 的程式也讀得出來** | 稽核腳本 `ops/d2/audit_d2.py` 只用標準函式庫重建每個週期的 report.md |

## 不能直接用、或有前提

- **追緝只在「某條主張不過」時才被叫**：沒有入口能對一份交件一次列出「每一條各自來自哪裡」，也沒有入口能事後問「那些來源現在還一樣嗎」。→ 補在產品路徑上，見下節。
- **本機網址不算來源**：`blame` 把 `127.0.0.1` 這類網址判成「可能是 agent 自己開的伺服器」⇒ `unresolved`、沒有 `source`（刻意的防偽規則）。實驗的來源因此改成保留網域 `*.d2-sources.example`，經 `http_proxy` 送到本機的來源伺服器（`ops/d2/source_server.py`）。真實網頁不受影響。
- **版本號抽不到**：`numbers_in` 不認 `v5.7.9`。→ `sources.py` 另加版本號的規則。
- **出處是推論層**：`blame` 用值比對往回追，同一個值出現在兩頁時可能指錯。材料裡本來就有這種撞值（例如兩個產品同價），覆蓋率照實分成「指到正確頁」和「指到某一頁」。
- **`docs/AUDIT_RECORD_V1.md`／`vacant audit export`**：正規化的是「一跑」層級（哪個 agent、哪個任務、幾次嘗試、驗收結果、退回什麼、缺口），**沒有宣稱層級的出處**，這個情境用不上。
- **收件帳本、重開收據**（`intake/ledger.py`、`restart_receipt`）：只在契約路徑／`vacant do` 才有，這個情境沒有經過它們。
- **`stopcheck.localize`、契約回饋**：給契約主張用的，不相關（見 `NOTE_20261125_CONTRACT_FEEDBACK_MODES.md`）。

## 補在產品路徑上的（auto/redo `6cdaad556`）

- `vacant_network/trace/sources.py`＋`vacant trace sources <檔> [--check] [--json]`：
  - 不帶 `--check`：每條具體值 → `blame_location` → 外部網址、那一步、當時讀到的內容 sha256。
  - `--check`：Vacant 自己重讀每個網址（0 token），當時讀到的每一個非空行現在還在 ⇒ `unchanged`，否則 `changed`；讀不到 ⇒ `unknown`；沒有外部來源 ⇒ `no_source`。整份結果（不含內文）簽進同一條鏈，事件類型 `source_check`（`recorder.EVENT_TYPES` 加了這一個）。
- 沒有另外寫一套紀錄：實驗的出處、來源檢查、agent 的每一步都在產品的病歷裡；執行器只多記每個週期結束時鏈的最後 `seq`（稽核切週期用）。

## 一句話

「以前的東西大致都做了」**對一半**：記錄本身（每一步、讀到的內容、寫了什麼、簽章）完整可用，追到來源的邏輯也在；
缺的是把它**當成出處來用**的入口（列出每條宣稱的來源、事後重讀來源），以及本機來源被刻意排除。補了一支約 170 行的模組。
