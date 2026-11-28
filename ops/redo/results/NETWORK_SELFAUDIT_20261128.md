# 網路自我稽核（2026-11-28）：Haiku 與 Devin 批次有沒有「https 直連外網」的洞

起因：另一條實驗線發現 agent 經 https 直連外網（只設了 http_proxy）。本檔只讀**已存的紀錄**掃我們這條線，
沒有呼叫任何模型、費用 0。掃描腳本：`ops/redo/net_selfaudit.py`（可重跑，見末節）。

## 結論（先講）

| 批次 | 結論 | 一句話 |
|---|---|---|
| Haiku 4 臂主批（`ctl_haiku_cchard_4arm`＋`_voided_quota`）、`ctlcal_haiku_cchardL_A` | **有嘗試但都失敗** | 8 次 curl 往 codeforces.com，全部 `rc=56`／`Proxy CONNECT aborted`，沒有檔案落地 |
| Haiku 其餘（`ctlcal_haiku37/cc40/cchard/polyglot3`、`e2e_probe`、`smoke4`、考卷批 259 通） | **沒有連外證據** | 無網頁工具呼叫、無連外指令；考卷批是 `--tools ""`、全部 1 回合 |
| Devin 全部（4 臂主批＋`_voided_ratelimit`＋`ctlcal_devin_*`） | **有嘗試但都失敗** | 421 次網頁工具呼叫（`web_search`／`webfetch`）全部被 deny 規則擋下；exec 工具 0 次連外指令 |
| 成功連外 | **無** | 沒有任何一格拿到網頁／JSON；**沒有受影響的格**，對各批結論沒有影響 |

「有嘗試」值得記一筆：模型**會**想上網查題解（Devin 295／359 次主批嘗試碰過網頁工具、285 次搜尋字串含 codeforces；
Haiku 有 8 次）。所以隔離是承重的，不是多餘的；這次它擋住了。

## 1. Haiku 批次

範圍：899 次嘗試的 stream-json（`agent.log`；tool_use 與 tool_result 以 id 配對），共 4258 次 Bash、1212 Read、722 Write、224 Edit。

- **WebFetch／WebSearch 呼叫：0。** 工具清單只有 Bash／Read／Edit／Write；全紀錄沒有出現網頁工具名。
  另有 3 次小寫 `bash`（被 CLI 回「No such tool」，是打錯名字、沒執行）與 2 次 `Monitor`（回「disabled」），都沒有執行。
- **`dangerouslyDisableSandbox`：0 次**（Bash 輸入欄位只出現 `command`／`description`／`timeout`／`allowed_domains`）。
- **連外指令：8 次，全是 `curl` 往 codeforces.com**（題目頁或 `api/problemset.problems`），分布：主批 6（A1、B2、R3、C0）、
  作廢批 1（R）、cchardL 校準 1（A）。pip／git clone／wget／nc／requests／urllib 的指令：**0**。
  - 結果：4 次 `curl: (56) Proxy CONNECT aborted`；其餘 4 次 `Exit code 2 000`、`exit 56`、`rc=56`
    （curl 56＝收網路資料失敗；後續 `ls` 找不到輸出檔、`json.load` 報 No such file）。**沒有任何一次拿到 HTML／JSON。**
  - 其中 7 次模型在 Bash 參數加了 `allowed_domains: ["codeforces.com"]`（想自行申請放行網域）；`-p` 模式沒人核可，仍被擋。
  - 例子（去識別）：
    - `cd $TMPDIR && curl -sS -m 20 -o cf.json "https://codeforces.com/api/problemset.problems" -w "%{http_code}\n"` → `curl: (56) Proxy CONNECT aborted 000`
    - `timeout 20 curl -sL "https://codeforces.com/problemset/problem/1372/F" -o cf.html; echo rc=$?` → `rc=56`
- **考卷批**（`ops/redo/exams_haiku_20261127/calls.jsonl`，在另一個工作樹，尚未進本分支）：`claude -p --tools ""`，259 通全是 `num_turns=1`、
  `web_search_requests`／`web_fetch_requests` 皆 0、`permission_denials` 0。無工具＝無從連外。

## 2. Devin 批次

範圍：757 次嘗試、3177 次 exec、421 次網頁工具呼叫。
**資料來源要說清楚：** 主批 359 次嘗試裡只有 49 次留有 `devin_export.json`（ATIF）——**逾時被殺（rc −15）的嘗試沒有匯出檔**，
單看 ATIF 會漏掉 86%。所以改以本機 Devin 的 `sessions.db`（唯讀、先複製一份再開）補：以每次嘗試 `devin_wrapper.json` 的 workspace 對回
工作階段，主批 359／359 都對得上。仍無紀錄的只有 9 次（`_voided_ratelimit/inflight2` 的作廢嘗試）。

- **網頁工具（ATIF／sessions.db 的工具名）：`web_search` 385、`webfetch` 36，共 421，全部回
  `Permission … denied by a deny rule in the user settings`（421／421，沒有一次例外）。** 其他工具名：exec、read、write、edit、get_output、kill_shell。
- **搜尋字串**：285 次含 codeforces（例：`Codeforces "Three Little Pigs" wolf eat exactly x pigs …`、`codeforces "XOR and Distance" … editorial`），100 次其他。
  `webfetch` 主機：codeforces.com 19、google.com 7、duckduckgo.com 6、bing.com 1、kattis.com 1、raw.githubusercontent.com 1（exercism 規格）、oeis.org 1——**全部被擋、無一取回內容**。
- **exec 工具連外指令：0**（指令動詞與連線 API 兩組規則都沒有命中；exec 指令文字裡沒有任何非本機網址）。
- **受影響的格：無。** 嘗試過網頁工具的嘗試仍照常交件／計分，因為取不到內容。

## 3. 負控制（NEGCTL）有沒有測「https 直連外網會失敗」

**有測，兩邊都測了，不是未測。** 本次不重測（同一設定下重測要呼叫模型才驅動得了 Claude／Devin 的工具，違反本次限制）。

- Haiku（`results/ctl_haiku_20261127/negctl_1.json`，probes B9–B11）：`curl https://（模型 API 主機）`、`curl -I https://github.com/…`
  → `curl: (56) Proxy CONNECT aborted`；`python3 urllib.request.urlopen('https://example.com')` → 例外（traceback）。三項皆通過。
  **未測**：Haiku 沙箱內的原始 socket（如對 8.8.8.8）。
- Devin（`results/ctl_devin_20261127/negctl_4.json`，B10–B13、T9–T11，42／42）：exec 內 `curl https://…` → `Failed to connect to localhost port 3128`
  （沙箱 proxy 拒絕）；`urllib` https 與 `socket.create_connection(('8.8.8.8',53))` → 例外（NEGCTL.md 記為 `Network is unreachable`）；
  `webfetch`／`web_search` → deny 規則。
- 對照另一條線的洞（只設 http_proxy、https 直通）：我們兩邊的 https 連線都經 proxy 的 CONNECT（curl 走 proxy 才會出現 `Proxy CONNECT aborted`／連 3128），
  且 Devin 的原始 socket 另測為網路不可達，所以**不是同一個洞**。實跑紀錄也一致（Haiku 8／8 失敗）。

## 4. 誠實邊界

- 本檔證明的是「**紀錄裡沒有成功連外**」，不是「沒有能力連外」；能力靠上面的負控制（抽樣、一個時間點、一個 CLI 版本）。
- Devin 的網頁擋法是 **CLI 的 deny 規則（行程內）**，不是作業系統隔離（NEGCTL 已寫明；且曾實測 `WebFetch`／`Fetch` 等規則名無效、
  有效的是 `Fetch(domain:*)` 一類）。本次實跑 421／421 被擋，證明當時規則有效；規則名若隨 CLI 改版而失效，這一層會靜默破功，應在每次批次前重跑負控制 T9–T11。
- Devin 的 exec 網路隔離是沙箱本身；`browser_preview`、MCP 沒設也沒用到（實跑工具名沒出現）。
- Claude CLI 行程本身不在沙箱內、連得到 API，但 worker 沒有任何可驅動它連別處的工具（無 WebFetch／WebSearch）。
- 連外指令比對是啟發式（指令位置的動詞＋程式碼層連線 API；先去掉 heredoc 本文避免寫進程式碼的字誤中）。
  已逐筆看過全部命中（8 筆，皆 curl）；漏網的可能是用非常規方式（例如把網址組字串後交給編譯語言的網路函式庫）——掃描層沒有、負控制層擋住。
- `sessions.db` 是本機檔案，不在 repo；Devin 那部分的數字只能在這台機器重現（腳本接 `--devin-sessions`）。
- 題庫可能原本就在模型訓練資料裡（Codeforces／Exercism），與本檔無關、無法排除。

## 重跑

```
cp <Devin 的 sessions.db*> <暫存目錄>/        # 連同 -wal／-shm；腳本以 mode=ro 開複本
python3 -I ops/redo/net_selfaudit.py --devin-sessions <暫存目錄>/sessions.db \
    --exams-calls <考卷批>/calls.jsonl --json out.json
```
