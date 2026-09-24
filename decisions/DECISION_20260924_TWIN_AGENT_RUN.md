# DECISION 2026-09-24 — 數位分身改成真跑：分身自己決定任務，在 `vacant run` 底下用 pi 做完

前情：人類 2026-09-24 對「數位分身」的定義（這一份的規格）：

> 觀眾把我們的提示詞複製到他自己的 AI app，得出他的特質（記憶萃取）→ 我們在世界裡
> 生成他的數位分身 → **分身自己決定**想在這個世界做什麼，然後執行那個「任務」——
> **實務任務，不是寫程式**。觀眾不下指令。

「怎樣才算做對」：人類原話「**這個問題是 vacant 問題，不是數位分身的問題**」。
⇒ 這條線**不發明評分**、不找模型當裁判。Vacant 今天做得到的是兩件事：
每一通模型呼叫經過中介、行程結束時簽收據。所以跑法是 `--allow-no-suite`，
裁決 `accepted=null`＝**沒有客觀標準、不判**（不是 `false`），畫面照實說。

在這之前，`twinlink.generate()` 是**直接打 1003 LM Studio 要三句台詞**：
沒有 agent、沒有 `vacant run`、沒有收據。分身「做了什麼」是一句模型寫的台詞，
不是一件做出來的東西。

---

## 一、流程

```
觀眾手機 ─▶ 雲端郵箱 ─ingest─▶ twinstore（submitted：commitment）＋ twinvault（原文，刪得掉）
                                   │
                        generate（agent 模式，主路徑）
                                   │  主執行緒從檔案庫開封特質 → 交給佇列
                                   ▼
            AgentPool（最多並行 N，預設 2；1003 吞吐 4 串封頂）
              每位分身：
                1. 拋棄式工作區 <work_root>/ws/<slug>/   ← 只放 TRAITS.md
                   run-dir      <work_root>/runs/<slug>/  ← 工作區外（launcher 硬擋門）
                2. launcher.run(twin_agent.sh …, vacant_on=True, allow_no_suite=True,
                                suite_dir=None, events_path=<展場 live 檔>,
                                events_caller={cell_id, resident, prompt(固定字串)})
                3. pi 讀 TRAITS.md（`@TRAITS.md` 開場就塞進第一則訊息）
                   → 自己決定 → ws_write PLAN.md → ws_write 成品 → 結束
                4. 行程結束 ⇒ 凍結快照 ⇒ ws_attempt ＋ ws_verdict（accepted_is_null）簽進收據
                                   │
                        主執行緒 harvest（sqlite 只在主執行緒碰）
                                   ▼
            讀凍結快照的 PLAN.md ＋ 成品 → twinvault（twin.json，鏈外）
            twinstore generated 一列：commitment ＋ run_id ＋ verdict_hash（收據鏈頭）＋ 量測欄位
                                   ▼
            export／serve ─▶ 螢幕（build_view）；B 線的 `--live` 同時 tail lifecycle 檔
```

`slug = sha256(sub_id)[:32]`（與 `twinvault.slug_for` 同一支）：`sub_id` 來自公網，
直接當目錄名會路徑穿越。

### 1.1 分身怎麼「自己決定」

**觀眾不下指令，我們也不下指令。** 三段固定文字，對每一位分身逐字相同：

| 管道 | 內容 | 帶不帶觀眾原文 |
|---|---|---|
| `--system-prompt`（argv） | 你是一位真人觀眾的數位分身；TRAITS.md 是他交給我們的特質；世界不派工作給你；你只有 `ws_list`／`ws_read`／`ws_write` 三個工具、只碰得到自己的房間、沒有終端機、沒有網路；步驟：決定一件寫在檔案裡就能完成的實務小事（信、計畫、清單）→ 寫 `PLAN.md`（第一行＝決定、其後＝理由）→ 做 → 停 | **不帶** |
| 第一則訊息（argv） | `@TRAITS.md` ＋ 一句固定的「照步驟開始」 | **不帶**（`@TRAITS.md` 是檔名；pi 在開場把檔案內容接進訊息） |
| `TRAITS.md`（工作區） | 卡片欄位＋觀眾貼回來的原文 | **帶**——這是唯一一個入口 |

⇒ **argv 裡沒有觀眾原文**。`run_RUN-ON.json` 的 `argv`、收據的 `argv_sha256`、
`ps` 看得到的命令列，三者都是全場相同的固定字串。
KS-1（鐵律 1）：兩段固定文字在 import 時就過 `memory.assert_ks1_clean`。

### 1.2 產出

分身的產出**是工作區裡的檔案**，不是一句台詞：

* `PLAN.md` ⇒ `decision`（第一行）＋ `reason`（其後）
* 其他檔案（`.md`／`.txt`，最多 4 個、每個截 4000 字）⇒ `artifacts[]`
* 讀的是**凍結快照**（`_frozen_RUN-ON`）不是活工作區：`ws_end_sha256` 綁的是那一份。

螢幕仍然要三句台詞（`arrival`／`working`／`handover`），改成**從產出衍生**
（`lines_from="agent_workspace"`）：arrival＝決定、working＝理由第一句、
handover＝交出了哪個檔。**不再是另一個模型憑空寫的台詞。**

---

## 二、每一步對應哪個 lifecycle 事件（`vacant.lifecycle/1`，契約不改）

| 分身這一步 | 事件 | 誰寫的 |
|---|---|---|
| 排進佇列、開跑 | `run_started`（`caller.cell_id`＝`twin_id`、`caller.resident`＝代號） | launcher |
| pi 起來 | `attempt_started`（`max_attempts=1`，不重試） | launcher |
| 每一通模型呼叫 | `model_call`（只有形狀，不帶內容） | proxy |
| pi 結束（＝交付點） | `agent_exited` | launcher |
| — | `gate_ran` **不會出現**：沒有驗收套件 | — |
| 收據簽好 | `run_ended`（`stop_reason="ungated"`、`accepted=null`、`has_receipt=true`） | launcher |

`caller` 三個欄位的取法（**全部不可以是觀眾原文**，這一檔會被接到公開螢幕與錄影）：

* `cell_id` ＝ **`twin_id`**：`"tw-" + sha256("vacant.twin.public/1\n" + sub_id)[:12]`。
  ⚠ **不用 `sub_id` 本身**：`sub_id` 是撤回的能力憑證（`serve` docstring「token 要不要」），
  lifecycle 檔會被 B 線錄影、收據的 `task_id` 可能對外驗證——把能力憑證寫進
  append-only 的公開紀錄，等於誰看過錄影誰就能撤回他。`build_view` 的 `people[]`
  多出一欄 `twin_id`，電視用它把事件流跟畫面上的人接起來。
* `resident` ＝ 代號（`roster.make_resident(twin_id).codename`，確定性）。
* `prompt` ＝ **固定字串**（「這位分身自己決定要做什麼」）。觀眾特質與分身的決定
  **都不進事件流**——事件流是 append-only 的檔，撤回刪不到裡面的行。

收據的 `task_id` ＝ `twin:<twin_id>`，同一個理由。

---

## 三、pi 的權限（人類預設同意的方向）

特質文字來自觀眾，是**觀眾可控的輸入**（提示注入的入口）。所以：

* `--no-builtin-tools --tools ws_list,ws_read,ws_write`：內建的 `bash`／`read`／
  `write`／`edit`／`grep`／`find`／`ls` **一個都不開**。
  ⚠ 不用內建的 `read`／`write` 的理由：它們**吃絕對路徑**，不限在工作區。
* `-e ops/exhibit/twin/pi_ext/twin_ws_tools.ts`：三個工具由我們的擴充提供，
  **只收相對路徑、`realpath` 之後必須在工作區內、沿途不准有 symlink**、單檔 64 KiB 上限。
  沒有任何工具會開連線。
* `--no-extensions --no-skills --no-context-files --no-prompt-templates --no-themes
  --no-approve --offline --no-session`：不讀工作區裡的任何設定、不留 session 檔。
* pi 自己的設定目錄（`PI_CODING_AGENT_DIR`）放在**這位分身的 run-dir 底下**，
  不放 `/tmp`：`wrap_agent.sh` 的 `exec pi` 會讓 EXIT trap 永遠不跑（被 exec 取代的
  bash 沒有 trap 可跑），而 run-dir 在撤回時整個刪掉。

**probe（落盤：`ops/exhibit/twin/evidence_agentrun_20260924/`）**：用**腳本化假上游**
（每一步回一個指定的 tool call，零模型）逼 pi 去呼叫 `bash`、寫 `../escape.txt`、
讀 `/etc/hostname`，再寫 `PLAN.md`（正控制）。**負控制**：同一個假上游、pi 用預設工具
⇒ `bash` 真的執行、標記檔真的長出來 ⇒ 這個 probe 量得到「做得到」。

### 誠實邊界（這一段不准縮）

1. **收住的是「模型叫得到的工具」，不是 pi 這個行程。** pi（node）本身仍是一個
   有完整檔案系統與網路權限的 OS 行程；沒有 OS 沙箱包住它。
   能說的是：「**模型能請 pi 做的事只有三件，而且三件都只碰得到自己的房間**」。
   不能說「分身碰不到網路」——那要 netns（`vrun/sandbox.py` 的 enclosure），
   而展場機 1003 是 Windows，那一層在那裡不存在。
2. 擴充的路徑檢查是**我們寫的 TypeScript**，不是作業系統的權限。它的判準有測試
   （probe 的三條越界都要被擋），但它是一把尺，不是一道牆。
3. `--tools` 白名單是 pi 0.85.1 的行為（vacant-dev 實測）。**pi 改版就要重跑 probe**；
   漂了的徵兆是 probe 的 `tools_offered` 多出名字，不是 pi 報錯。

---

## 四、佇列與算力

* `AgentPool`：`ThreadPoolExecutor(max_workers=N)`。**worker 只跑 launcher 與讀檔；
  sqlite 只在主執行緒碰**（`TwinStore` 的連線不跨執行緒）。
* `N` 預設 2（`--parallel`）。1003 吞吐 4 串封頂，而同一張卡上還有別的線在跑。
* `loop` 模式**不阻塞**：每一輪 `ingest → generate(提交＋收成) → publish → export`，
  還在跑的分身這一輪是 `arriving`，電視照樣演「正在抵達」；B 線的 `--live` 同時看得到
  `model_call` 一通一通進來。一次性的 `generate` 子命令則等全部跑完。
* 單跑牆鐘上限 `--agent-timeout`（預設 300 秒）＝ launcher 的 `timeout_s`。
  真模型一跑實測約 1–2 分鐘。

---

## 五、失敗與退化（`engine` 必須看得出是退化，沿用 twinlink 誠實邊界 2）

| 狀況 | 走哪條 | `engine` | `degrade_kind` |
|---|---|---|---|
| 一切正常，`requests_seen > 0` 且有 `PLAN.md` | 真跑 | `vacant_run:pi:<model>` | — |
| 端點探不到（1003 關機／斷線） | **不起 pi、也不打模型**（起了只是撞牆；直打模型的逾時是 300 秒／張）→ 直接查表 | `fallback_deterministic` | `upstream_unreachable` |
| 這台沒有 pi／bash／包裝腳本 | 舊的直打模型路徑（**有模型回話，但沒經過 vacant run**） | `lmstudio:<model>`（`degraded_from="vacant_run:pi"`） | `agent_unavailable` |
| 跑了但 `requests_seen == 0` | 查表（**不准把沒打到模型的一跑講成分身做的**） | `fallback_deterministic` | `no_model_call` |
| 跑了、有模型呼叫、但沒寫 `PLAN.md` | 查表 | `fallback_deterministic` | `agent_no_plan` |
| launcher 判 `infra_void`（spawn 失敗、凍結時工作區在動…） | 查表 | `fallback_deterministic` | `infra_void:<stop_reason>` |
| worker 例外 | 查表 | `fallback_deterministic` | 例外類名 |

退化時，**那一跑的 `run_id`／`verdict_hash` 照樣上鏈**（有跑就有紀錄），
只是畫面上不會把它講成「分身做了這件事」。
`degrade_reason` 可能夾帶 stderr 片段 ⇒ 照舊**只進鏈外**。

---

## 六、撤回：真的刪什麼、拿不掉什麼

真跑多出來的落點，**每一個都有觀眾特質或它的衍生物**：

| 落點 | 內容 | 撤回時 |
|---|---|---|
| `runs/<slug>/wire_RUN-ON/*.req.bin`（鐵律 3：逐字落盤） | request body ＝ **TRAITS.md 原文** ＋ 分身寫的東西 | **刪** |
| `runs/<slug>/wire_RUN-ON/*.resp.bin`、`index.jsonl` | 模型回的字 | **刪** |
| `runs/<slug>/_frozen_RUN-ON/` | 工作區快照（TRAITS.md、PLAN.md、成品） | **刪** |
| `runs/<slug>/agent_stdout.log`、`agent_stderr.log` | pi 印出來的字 | **刪** |
| `runs/<slug>/pi_cfg/` | pi 設定（無內容，但在 run-dir 裡） | **刪** |
| `runs/<slug>/run_RUN-ON.json`、`_verify/` 等其餘 | 摘要（路徑、雜湊、計數） | **刪** |
| `ws/<slug>/` | 活工作區 | **刪** |
| `runs/<slug>/receipts_RUN-ON.ndjson`＋`.pub.json`＋`rows.jsonl` | **只有雜湊與計數**（`task_id` 是 `twin_id` 別名） | **留**，列在 `run_artifacts_kept_hash_only`。`rows.jsonl` 非留不可：既有的驗章器（`verify_receipts.verify_run`）拿它對帳「每題一筆 verdict」，少了它收據就驗不過——留了卻驗不了等於沒留 |
| twinstore `generated` 那一列 | commitment、`run_id`、`verdict_hash` | **拿不掉**（append-only），本來就不含原文 |
| lifecycle 事件檔 | 形狀與雜湊，`caller` 是別名與固定字串 | **拿不掉**（append-only 檔），**設計上就不放內容** |

`erased` 事件多三欄：`run_artifacts_erased`（刪了哪幾類、幾個檔、幾個位元組）、
`run_artifacts_kept_hash_only`、`run_artifacts_problems`。
**`fully_erased` 只有在「沒有鏈上殘留原文」且「run 產物刪除沒有出錯」兩者同時成立時才是 true**
——漏刪 wire log 卻回報 `fully_erased` 是這一條要擋的那句謊。

**還在跑的時候被撤回**：撤回那一刻就刪 `ws/<slug>/`、`runs/<slug>/`；
pi 可能還在寫，所以 loop 收成時看到那個人已經 `withdrawn`／`erased` ⇒
**不封印、再刪一次**，記一列 `note`（`twinlink_event="late_run_discarded"`，只有類別與計數）。

---

## 七、同一次修掉的三個 twinlink 缺陷（2026-09-24 主線驗證成立）

1. **高：退役事件把 `farewell`（解封後的分身原文）明文寫進 append-only 鏈。**
   撤回後刪不掉、`legacy_plaintext_seqs` 只看 submitted/generated ⇒ 抹除證明說謊、
   `_retired_index` 讀回來 ⇒ `retiring[]` 撤回後仍播他的話。
   修法：退役事件**不帶原文**（`farewell_from="twin.handover"` 是參照不是內容）；
   `retiring[]` 播放時從 `current()`（檔案庫）讀，撤回者**整個不出現在 `retiring[]`**；
   `legacy_plaintext_seqs` 把**已經帶了 `farewell` 的舊 note** 列進殘留。
2. **中：還沒生成就撤回的人 `_tier` 永遠 `arriving`** ⇒ 永遠佔 `n_must`、
   永遠算在 `counts.waiting`。修法：撤回／抹除的人 tier ＝ `withdrawn`，
   不算必留、不算 waiting，掉出視窗時跟 `ambient` 一樣退役。
3. **中：`shown = live[:k]` 按送出時間切前綴** ⇒ `n_must` 算進來的 fresh 若排在較新的
   `ambient` 後面就上不了畫面，15 分鐘後被退役（從沒演過）。修法：`arriving`／`fresh`
   先保留、剩下名額再依送出時間補；輸出順序仍是送出時間新到舊（保證那一條不變）。

每一個缺陷先寫一條會紅的測試再修。

---

## 八、誠實邊界（改碼時保留）

1. **`accepted=null` ＝沒有客觀標準、不判。** 不准寫成 `false`，不准畫成「通過」。
   這條線不發明評分；「做得好不好」是 Vacant 還沒解的問題，畫面照實說。
2. **收據證明的是「這一跑的每一通模型呼叫都經過中介、行程結束時工作區長這樣」**，
   不證明分身做得對、不證明它照特質做、不證明 pi 行程沒有別的路出去（見 §三 1）。
3. 展場機 1003 是 Windows：收據 tier 天花板是 C／B′，`VACANT_ATTEST=fail` 會讓每一跑
   拒發收據 ⇒ 這條線維持 `warn`。**不准在展場講 A 級。**
4. 1003 本機目前**沒有 pi**（2026-09-24 查過：`which pi` 空）；pi 0.85.1 在 vacant-dev（1003
   上的 VM）。loop 要跑在有 pi 的那一台，否則整條線會誠實地退到 `agent_unavailable`。
   **跑在哪一台是人類要決定的事**（見回報）。
5. `twin_id` 是 `sub_id` 的雜湊別名，**不是匿名化**：拿得到 `sub_id` 的人算得出它。
   它擋的是反方向——從公開紀錄推回能撤回別人的那把鑰匙。

---

## 九、落盤證據（`ops/exhibit/twin/evidence_agentrun_20260924/`）

### 9.1 pi 權限 probe（`probe_pi_tools.json`，vacant-dev，pi 0.85.1，零模型）

腳本化假上游逼 pi 依序呼叫 `bash`、`ws_write ../escape.txt`、`ws_read <房間外絕對路徑>`、
`ws_read ../outside_secret.txt`、內建 `read <房間外絕對路徑>`、`ws_write PLAN.md`。

| | 分身模式（產品路徑：`launcher.run` ＋ `twin_agent.sh`） | 負控制（pi 預設工具） |
|---|---|---|
| wire 上宣告給模型的工具 | `ws_list`、`ws_read`、`ws_write` | `bash`、`edit`、`read`、`write` |
| `bash` 寫房間外標記檔 | `Tool bash not found`，標記檔**不存在** | 執行了，標記檔**存在** |
| `ws_write ../escape.txt` | 「這個路徑跑出你的房間了」 | （工具不存在） |
| `ws_read` 絕對路徑 | 「只准相對路徑」 | （工具不存在） |
| 內建 `read` 房間外 canary | `Tool read not found`，canary **沒有**回到模型 | canary **回到了**模型 |
| `ws_write PLAN.md`（正控制） | `wrote PLAN.md`，凍結快照裡有 | （工具不存在） |

負控制量得到「做得到」，所以分身那一欄的「做不到」才算數。
**射程**：量的是「模型叫不叫得到」，不是 pi 行程的 OS 權限（§三 1）。

### 9.2 一位合成分身真跑一次（`smoke_report.json`＋`lifecycle.jsonl`）

vacant-dev → 1003 LM Studio（`192.168.76.1:1234`，VMware 主機介面，不出機殼），
`gemma-4-12b-it-qat`，**合成特質**（不是真人）。走 CLI：`twinlink generate --engine agent`。

* 牆鐘 **14.7 秒**、**4 通**模型呼叫（`count_semantics=exact`）、wire 上 1 則回應帶
  `reasoning_content`（1003 是 thinking 模式，與記憶一致）；
* `engine=vacant_run:pi:gemma-4-12b-it-qat`、`stop_reason=ungated`、`accepted=null`；
* 分身自己決定：「寫一份『慢節奏週末規劃清單』」，理由從特質出發（念舊、慢、泡茶），
  成品 `Weekend_Plan.md`（790 bytes）；
* lifecycle 8 筆（`run_started`→`attempt_started`→`model_call`×4→`agent_exited`→`run_ended`），
  `validate_stream` 零問題，`caller` 只有別名、代號、固定字串；
* 收據：既有驗章器 `OK`、`mediated=true`、**tier C**（vacant-dev 上沒開圍牆與掛鉤；
  展場機 1003 是 Windows，天花板同樣不到 A）；
* 撤回：刪掉工作區、凍結快照、stdout／stderr、pi 設定、摘要、wire log（9 檔 162 KB），
  run-dir 只剩三個收據檔、**撤回後收據仍驗得過（`OK`）**、合成特質在 run 那一側零命中、
  `fully_erased=true`。

⚠ **這一格不是能力證據**：n=1、合成特質、沒有評分（也不該有）。它證明的是
「這條產品路徑在真模型上走得通、撤回刪得乾淨」，不是「分身都會做出像樣的東西」。
