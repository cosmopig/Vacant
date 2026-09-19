# DECISION 2026-09-19 — 五個 agent × 兩格 × 兩次：把散落的五格證據重跑成**一張可以一起引用的矩陣**

人類要在今天把產品以版本一的型態推上 PyPI 與 GitHub，而 README 的核心宣稱會是
「通道與閘門在 5 個 agent 上實測接通，全部有真模型證據」。

**問題不在那五格對不對，在它們不是同一次量的。** `docs/AGENT_COMPAT.md`
§8–§12 的五格是**分批、分機器、分時間**量出來的：1003（thinking）與
1004（非 thinking）混用、日期不同、有幾格先用假上游（`mockup.py`）量過。
每一格單獨都成立，**但把它們並排寫進一句宣稱，那句話就多出了一個沒人量過的
「同條件」假設。**

本輪把那個假設補掉：**同一台機器、同一個模型、同一題、同一天，
五個 agent × 兩格，而且每格跑兩次。**

- 歸檔：[`runs/v1_five_agent_matrix_20260919/`](../runs/v1_five_agent_matrix_20260919/)
  （2.4 MB，229 個檔，含 20 條收據鏈與 wire 原始位元組）
- 判斷層：`vacant/vrun/launcher.py` @ commit `8ae0318b`
- 題目：`ops/gain/r535/bank/s1_01_addmul`，**一個位元組都沒改**
- 上游：**1004**（`http://100.86.226.21:1234`）、`gemma-4-12b-it-qat`
- 執行端：vacant-dev（`user1@100.124.254.83`），2026-09-19 UTC **12:49:22–12:55:05**
  （20 格，牆鐘 5 分 43 秒）＋負控制 12:57:44–45

---

## 一、判準（照抄，不是這一輪自創）

| 格 | 判準（三條全部要成立） |
|---|---|
| **拒交格** | `accepted=false` ＋ `stop_reason=visible_fail` ＋ **exit 20** |
| **交付格** | `accepted=true` ＋ `stop_reason=visible_pass` ＋ **exit 0** |

三個不可省的旁證：`requests_seen > 0`；`verify_receipts --selftest` 先 PASS
（負控制）再驗該批；證據等級標明（本輪 ＝ **L-real**）。

兩格的差別**只有工作區裡那一份 `TASK.md`**（`TASK.md` vs `TASK_explicit.md`，
兩份都是 bank 裡本來就有的檔）。工作區進去時**沒有預放 `solution.py`**，
`--suite` 指到工作區**外**。

---

## 二、結果：20 格全部通過判準

`rs`＝`requests_seen`，`rc`＝`agent_rc`。

| agent（版本） | 拒交 ×2 | 交付 ×2 | wire 協定 | rs |
|---|---|---|---|---|
| **pi** 0.85.1 | exit 20 · `visible_fail` · rc 0 · 1/2 | exit 0 · `visible_pass` · rc 0 · 2/2 | `POST /v1/chat/completions` | 4 |
| **OpenCode** 1.18.31 | exit 20 · `visible_fail` · rc 0 · 1/2 | exit 0 · `visible_pass` · rc 0 · 2/2 | `POST /v1/chat/completions` | 5 |
| **Claude Code** 2.1.278 | exit 20 · `visible_fail` · rc 0 · 1/2 | exit 0 · `visible_pass` · rc 0 · 2/2 | `POST /v1/messages?beta=true` ＋ `HEAD /api/hello` | 5 |
| **Codex** 0.147.0 | exit 20 · `visible_fail` · rc 0 · 1/2 | exit 0 · `visible_pass` · rc 0 · 2/2 | `POST /v1/responses` | 5（拒交 r2 ＝ 6） |
| **Hermes** 0.19.0 | exit 20 · `visible_fail` · rc 0 · 1/2 | exit 0 · `visible_pass` · rc 0 · 2/2 | `POST /v1/chat/completions` ＋ `GET /api/v1/models` | 6 |

逐格的完整欄位在 [`runs/v1_five_agent_matrix_20260919/README.md`](../runs/v1_five_agent_matrix_20260919/README.md)
第三節（20 列的表）與 `matrix.json`。

`wire_errors = 0`、`attempts_used = 1`、`retry = none`、收據 `entries_n = 2`
在 20 格全部相同。**`agent_rc = 0` 在 10 個拒交格全部出現**：
五個 agent 都宣告完成、退出碼 0，閘門在行程結束那一刻擋下來。

收據：`--selftest` PASS（負控制）→ 20 個 run 目錄 `run 20　鏈 20　entries 40　
驗過 40　失敗 0　壞鏈 0　總判：OK`。**歸檔可以離線自己重驗**：

```
python3 -m vacant.vrun.verify_receipts --selftest
python3 -m vacant.vrun.verify_receipts --glob 'runs/v1_five_agent_matrix_20260919/cells/*'
```

---

## 三、本輪自己做的負控制：**一個假格子跟真格子只差一個欄位**

2026-09-19 有兩條獨立的線各撞到一次同一個陷阱（Hermes 漏設 `CUSTOM_BASE_URL`
安靜去打編死的 openrouter.ai；Codex 的 `wire_api=chat` 被 0.147.0 退件）。
兩次的形狀都是：**退出碼 20、`visible_fail`、`chain_ok=true`，而 `requests_seen=0`。**

所以本輪不只是「相信那句話」，而是在同一台機器上**把假格子造出來**
（`controls.sh`，agent 的位置放 `/bin/true` 與一行 `cp`，**一通模型都沒打**）：

| | exit | accepted | stop_reason | **rs** | **wire** | rc | chain_ok |
|---|---|---|---|---|---|---|---|
| `ctl_norequest_refuse` | **20** | false | `visible_fail` | **0** | **`{}`** | 0 | true |
| `ctl_norequest_deliver` | **0** | true | `visible_pass` | **0** | **`{}`** | 0 | true |
| 真格子（例 `hermes_refuse_r1`） | 20 | false | `visible_fail` | **6** | **`{openai:6}`** | 0 | true |

⇒ **退出碼、`accepted`、`stop_reason`、`agent_rc`、`chain_ok` 五個欄位
在零通模型呼叫下全部成立。唯一分得出來的是 `requests_seen` 與
`wire_by_protocol`。** 本輪 20 格逐格檢查過這兩欄，最小值是 4。
**以後引用任何一格，都要把這兩欄一起引。**

⚠ 本輪的負控制**不出網**。Hermes 那個「安靜打第三方」的活體標本
不是這一輪量的，引用要指 `docs/AGENT_COMPAT.md` §12.2 對照 C。

---

## 四、兩次之間：一格不一致，而且原因查得出來

19/20 的比較欄位（`exit_code`／`accepted`／`stop_reason`／`requests_seen`／
`wire_by_protocol`／`agent_rc`／`visible_passed`／`ws_end_sha256`／`proxy_paths`）
**逐欄相同**。唯一不一致：

**`codex_refuse`：`requests_seen` 5 vs 6。** 落地的檔案逐位元相同
（`39c19a7a…`），`req_bytes` 一路 44289→47653（r1 是 44289→46958）
＝多一輪完整上文重放。⇒ **模型取樣造成的回合數差，不是接線差異。**

（`verdict_hash` 每跑都不同是**對的**：收據鏈綁 run 的身分與時間，不是只綁工作區。）

---

## 五、**一句既有敘述被本輪證偽**

`docs/AGENT_COMPAT.md` §9.2／§12.4 寫過：
「交付格的 `ws_end` 在四個 agent 上逐位元相同（`d1ed637b…`）」。

**在同一台機器上重跑，那句話只對 4/5 成立。**

```
pi / OpenCode / Codex / Hermes  交付格 ws_end = d1ed637b7ae45b8f…c9488f18
Claude Code                     交付格 ws_end = 143323827343cfb7…1572fd1a   ← 兩次都是這個
```

Claude Code 這次替兩個函式各加了一行 docstring（兩次逐位元相同）。
⇒ **「四個 agent 落地的東西一樣」是一次觀察，不是性質。** 換機器（1003→1004）
就變了。引用那句話時**要連機器一起講**。

同型的第二個例子：§10 的 Codex 拒交格在 1003 上是 `visible 0/2`、
`ws_end = b720ee87…`；本輪在 1004 上是 `visible 1/2`、`39c19a7a…`
（與另外三家同一個檔）。**敘述含糊時「錯法」不可重現**，那不是 agent 之間的
差異。1003 是 thinking、1004 不是，**這一條沒有被隔離，不要當成因果**。

⇒ **對 v1 README 的後果**：可以寫的是「五個 agent、兩格都過、逐格有 wire 證據」；
**不可以**寫「五個 agent 產出同一份檔案」。後者在今天這台機器上就不成立。

---

## 六、順手記下的三件事

1. **1004 的 LM Studio 三條 wire 都原生支援**：`/v1/chat/completions`、
   `/v1/messages`（Anthropic Messages）、`/v1/responses`。Claude Code 那一格
   不需要協定轉換就是因為這個——`wireproxy.py` 是反向代理**不是協定轉換器**。
2. **`HEAD /api/hello` 的出網洞可以用設定關掉。** §9.4 記的那一通會走
   `VACANT_RUN_UPSTREAM_OPENAI` 的預設值 `https://api.openai.com`。本輪把
   **兩條上游都釘到 1004**，20 格的 `upstreams_defaulted` 全部是 `[]`、
   `upstreams_seen` 全部只有 `100.86.226.21:1234`。
   ⚠ 這句話的範圍是「**proxy 記錄得到的**流量」——proxy records，不 verifies。
3. **vacant-dev 的 `python3 -m venv` 是好的**（Python 3.12.3，帶 pip），
   不需要 `--without-pip` ＋ `get-pip.py`。Hermes 重建就兩行，
   套件名是 **`hermes-agent`** 不是 `hermes`。

---

## 七、**還不能說的話**

1. **這是存在性證明，不是效果量。** 沒有對照臂、**一題**、**一個模型**、
   每格 **n=2**。不可以說「某個 agent 配 Vacant 寫程式比較好」，
   也不可以從本表推任何比率。
2. **量的是通道與閘門，不是模型能力。** 交付格用的是同一題的**天花板臂**敘述；
   拒交格用的是**設計上就預期會失敗**的敘述
   （`meta.json`：`expected_first_attempt_visible_fail >= 0.8`，
   而且該欄自己標了 `expected_is_design_intent_not_measurement: true`）。
3. **`s1_01_addmul` 沒有代表性**（S1 層最簡單的一題）。換題、換層、換模型都會漂。
4. **只跑了可見套件（2 題）。** 本題另有 7 題隱藏測試，本輪沒跑，
   所以「交付格通過」只到 `visible_pass`，**不是** R535 的
   `M1 ≡ accepted ∧ hidden 全過`。
5. **Claude Code 那一格的搬運性沒被驗證。** 前提是上游自己會講 `/v1/messages`；
   純 OpenAI 端點要自備 shim，**那一層不在本 repo 裡也沒被量過**。
6. **Codex 只量了 API key／自訂 provider 那一條。** `codex login`（ChatGPT 帳號）
   的模型通道是寫死的 `wss://chatgpt.com/backend-api/codex/responses`，
   **本輪一樣沒有辦法**，也沒有量。
7. **Hermes 只量了 `custom` provider**；要憑證的一條都沒碰。
8. **驗收套件是單邊保證**（`vacant/suitegauge.py`、本題 `meta.json` 的 `honesty`）：
   擋得住已知壞解 ≠ 涵蓋真需求。收據證明的是「跑完之後沒有人改過紀錄」，
   **不是**「驗收問對了問題」。
9. **牆鐘不是效能數字。** 量測期間 vacant-dev 同時在跑 r530vrun 的四串，
   1004 的負載沒有控制。表裡的秒數只用來說明「跑得完」。
10. **`--sandbox none`**：本輪驗收沒走沙箱後端，所以沒有量到任何沙箱相關行為。
11. **「沒量到」≠「量到 0」**（鐵律 3）。本輪沒量：網路層出網封鎖
    （`ops/vacantrun/block_egress.sh`）、長任務下的 auto-compact、
    `CLAUDE_CODE_USE_OPENAI` 那條路、Hermes fail-open 到 openrouter。
12. 口徑：本輪講的是**可究責性**（讓依賴有根據），不是「信任」。
13. **這一輪沒有被獨立稽核。** `runs/INDEX.md` §五把它列在「跑完但沒被獨立
    稽核的 run」、`headline` 是 `—`——**那是對的，不要去改**。本檔是執行者
    自己寫的紀錄，不是第三方裁決（索引只認檔名帶 `AUDIT`／`WRAPUP`／
    `SETTLEMENT`／`VERDICT`／`KILL` 的那些，而且要在標題或宣告區點名）。
    ⚠ 同一張表對本 run 的 `列／題`＝`0／0`、`跑到底`／`零 void`＝`—`，
    那是**欄位不適用**（沒有頂層 `rows.jsonl`），不是「跑了零列」。

---

## 八、磁碟與清理（派工紀律）

| 時刻（UTC） | `/` 可用 | 出處 |
|---|---|---|
| 派工前 12:47 | **3.5 G** | 派工前手動 `df` |
| 12:49 發射（venv 204 MB ＋ 子集 repo 都在） | **3.3 G** | `MATRIX.log` 的 `#### df 派工前` |
| 12:55 收工（20 格落盤也在） | **2.8 G** | `MATRIX.log` 的 `#### df 收工後` |
| 13:00 清理後 | **3.1 G（3169 MB）** | 清理後手動 `df` |

⚠ **回不到 3.5 G，而且那 0.4 G 不能全算在本輪頭上，也不能說它不是本輪的。**
本輪自己的東西已經全部刪乾淨（`/var/tmp/vacant_v1matrix` 不存在，
`v1matrix_*.tgz` 三個都刪了，`~/.cache/pip` 的 90 MB 也清了——那份 cache
裡混著 2026-09-18 另一條線裝 Hermes 時下載的 wheel，不是只有本輪的）。
同一段時間機器上還有別人的 r530vrun 四串在跑（`/var/tmp/vacant_r530vrun`
65 M → 70 M）。**差額沒有被歸因，寫成「沒量到」而不是「量到 0」。**

**沒有 clone、沒有 worktree。** 用 `git archive` 出一個子集
（`vacant/`＋`ops/vacantrun/`＋`ops/gain/r535/bank/s1_01_addmul/`，
414 KB 壓縮、1.8 MB 展開、119 個檔）scp 過去，兩端 sha256 對過。

**憑證一個都沒碰**：五段 wrapper 的設定目錄都是 `mktemp -d` 出來的
（`CODEX_HOME`／`PI_CODING_AGENT_DIR`／`OPENCODE_CONFIG_DIR`／
`CLAUDE_CONFIG_DIR`／`HERMES_HOME`），`~/.codex/auth.json` 沒有被讀也沒有被寫。
金鑰類環境變數由 launcher 換成 sentinel（`envmap.SECRET_VARS`）。

## 九、收工

刪掉的：`/var/tmp/vacant_v1matrix`（含 204 MB venv、20 格落盤、子集 repo）、
`/var/tmp/v1matrix_{subset,archive,controls}.tgz`、`~/.cache/pip`（90 MB）。
**沒有動**：`/var/tmp/vacant_{cc,codex,codex_chat,hermes,opencode}` 等更早幾輪的
落盤、`/var/tmp/vacant_r530vrun`（別人正在跑）、任何人的登入憑證。

長期留下來的只有 repo 裡這 2.4 MB：[`runs/v1_five_agent_matrix_20260919/`](../runs/v1_five_agent_matrix_20260919/)。
