# round680 碼版本背書：`g_r444_conform_mbpp` 與 `g_r445_conform_mbpp_ext` 的處置定義相同

兩個 run 的 `summary.json` **都沒有記錄自己跑在哪個 commit**（round680 發現的設計缺口）。
`pool_precheck.py` 因此把 C2 判成 `UNVERIFIABLE_NO_CODE_VERSION`，要併庫必須附這份逐函式比對。

## 一、兩個 run 各自跑在哪個碼版本

**這一段是量測，不是 mtime 推論**（判準 T4 禁止拿 mtime 猜還當量測）：

- `r445` 的命令列有 `--offset 179` 且沒有報錯。`--offset` 這個 CLI 參數
  **只存在於 `17215c1`（round673）之後** ⇒ r445 跑的碼 ≥ `17215c1`。
- `r444` 的 `summary.json` **沒有 `offset` 與 `n_tasks_loaded` 兩個鍵**，
  而 r445 的有。這兩個鍵由 `write_summary()` 無條件寫出，也是 `17215c1` 加的
  ⇒ r444 跑的碼 < `17215c1`。

輔助（**標為推論**）：r444 的 run 目錄檔案 mtime 為 18:53–22:13 UTC，
`gain_run.py` 在那之前最後一次改動是 `7330f74`（15:31）⇒ r444 載入的是 `7330f74` 版。
r445 起跑 22:27:56，`17215c1` 於 22:27 commit ⇒ r445 載入的是 `17215c1` 版。

## 二、`7330f74` → `17215c1` 的 `gain_run.py` 逐函式比對

以 AST 取出每個 function 的原始碼片段做 sha256（`ops/gain/replay/pool_precheck.py`
的姊妹檢查，指令記於 GAIN_STATE round680）：**39 個函式中 35 個逐位元相同**。
不同的 4 個：

| 函式 | 改了什麼 | 是否影響臂的處置 |
|---|---|---|
| `probe_instrument` | 加 `visible_check` 雙向驗證（round671） | 否——**開跑前**的量具驗證，不碰 rng、不多一次模型呼叫；只會讓 run 提早中止，不會改變任一題的處置 |
| `save_receipts` | 新增；把收據鏈與公鑰落盤（round666） | 否——**所有臂跑完之後**才呼叫，純寫檔 |
| `write_summary` | 多寫 `offset`／`n_tasks_loaded` 兩個鍵 | 否——純落盤 |
| `main` | `--offset` CLI、負值擋門、載不到題就停、可見閘門硬擋、呼叫 `save_receipts` | 否——改的是**取哪些題**與前置擋門，不是取到之後怎麼處置 |

**四個臂的碼逐位元相同**：`arm_off`／`arm_on`／`arm_off5`／`arm_conform` 全部 sha 相同。
`load_tasks`、`meets_demand`、`conform_failure_detail` 亦相同。
⇒ 判準 **T2 未觸發**（diff 沒有碰到 `arm_conform`／`arm_off5`／評審 prompt）。

`load_tasks` 逐位元相同這一條另有獨立的實測佐證：兩個 run 的 task_id
**交集＝0、聯集＝371＝179+192**——若題序在兩次載入之間變過，
`ts[0:179]` 與 `ts[179:371]` 幾乎必然重疊。

## 三、`brain_cline.py`：`c1e6653` → `dec41c2`（round662，19:09，落在 r444 跑的中間）

r444 於 18:53 起跑 ⇒ 載入 `c1e6653` 版；r445 ⇒ `dec41c2` 版。
diff 全部落在既有 `except` 區塊內：把 `HTTPError` 的回應本體接到 `last_err` 字串後面。
**控制流、重試判定、void 定義都沒有改**（diff 只有 `last_err = f"...{body}"` 與 body 的取得）。
`REVIEWER_SYSTEM`／`REVIEW_LENSES`／`POOL` 均未變動。

觸發次數（實測，不是宣稱）：r444 的 `calls.jsonl` 1327 筆裡有 **3 筆 HTTPError（HTTP 500）
＋1 筆 TimeoutError**，全部重試成功、`infra_void` 三臂皆 0；
r445 至本文寫成時 495 筆呼叫 **0 筆 err**。
⇒ 這段碼在 r444 走過 3 次、在 r445 尚未走過，但它改的只有錯誤訊息字串。

## 四、結論與界線

**可以併庫**：處置定義（四個臂的碼、模型池、seed、題庫、評審 prompt）相同。

**不准由此推出**：兩批題目難度相同。McNemar 是**題內配對**，跨題難度異質不是併庫的
障礙，但也不代表兩批等價（判準 T3 事前寫死的防線）。
