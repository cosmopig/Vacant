# Worker harness 研究：pi／OpenCode 原始碼讀後的規格與實驗設計

**這份文件是什麼**：把兩個公開 coding agent harness（`badlogic/pi-mono`、`sst/opencode`）
**原始碼裡真的有的東西**，跟 Vacant 這邊**真的量到的東西**接在一起，產出三條可實作的
worker harness 臂（H-PI／H-OC／H-MIX）與一份可預註冊的實驗設計。

**紀律**（沿用 `docs/VACANT_ARCHITECTURE_AND_RESULTS_2026-09-07.md`）：
每一個數字後面帶來源（檔案路徑＋行號／commit／json 路徑）。
**沒有落盤來源的數字一律寫「未量測」**。外部專案的宣稱一律標「作者自報」或「無法一手驗證」。

**版本**：branch `feat/v2-four-stages`、HEAD `1bcb31a`（撰寫時 `git status` 乾淨）。

**本輪做了什麼**：讀原始碼、讀已歸檔的 `runs/g_r447_conform_lcb2/`、在本機沙箱做了
**零模型呼叫**的機制驗證（§3.1、§3.3 的四種失敗類別是實跑出來的）。
**沒有做**：沒有改任何 Vacant 程式碼、沒有對 `100.119.113.56:8765` 或
`100.86.226.21:1234` 發出任何請求、沒有跑任何 arm。

**這份文件的地位**：規格與預註冊草案，**不是結果**。任何「harness 有效」的說法在
`g_r460_*` 跑完並經稽核之前都是待驗證的宣稱（SPEC_GAIN §7）。

---

## 一、pi 與 OpenCode：有出處的事實，與傳說

### 1.1 讀了什麼（版本釘死）

| 專案 | commit | 讀了什麼 |
|---|---|---|
| `badlogic/pi-mono`（pi.dev 上已改指向 `earendil-works/pi`，npm `@earendil-works/pi-coding-agent`） | `9767ba275f3e9a5ee0f5c5342249b629ab1b2282`（2026-09-06，`packages/coding-agent/package.json` = 0.85.1） | `packages/agent/src/agent-loop.ts`、`packages/coding-agent/src/core/system-prompt.ts`、`core/tools/{bash,read,edit,write,truncate,edit-diff,index}.ts`、`core/compaction/compaction.ts`、`packages/agent/src/harness/config.ts`、`AGENTS.md` |
| `badlogic/pi-terminal-bench` | `0074c915dc7d8ceeba5f61b19e7b9aa078564fa3` | `src/pi_terminal_bench/pi_agent.py`、`run.sh` |
| `sst/opencode`（原始碼內部自稱已遷至 `anomalyco/opencode`） | `53fec37d8d2b9e0d92a1b4184e8df8f8480a2d26`（2026-09-07） | `packages/opencode/src/{session,tool,agent,lsp}/`、`packages/core/src/session/`、`session/prompt/*.txt`、`tool/*.txt` |

⚠ **版本落差是引用時的第一個陷阱**：pi 的 Terminal-Bench 跑分是 **2025-12-02**、
約 v0.12.x；當時**沒有 compaction**（CHANGELOG `[0.12.7] - 2025-12-04` 才加入）、
**沒有 skills／extensions／grep／find／ls**、system prompt 是更短的版本。
所以「架構描述引用 HEAD」沒問題，但**任何把 49.8% 歸功於 HEAD 某個機制的說法都是錯的**。

### 1.2 有出處、而且對我們有用的十件事

以下每一條都在上表的 commit 裡讀得到。**這一節是本文件唯一可以拿來當設計依據的外部材料。**

**F1（pi，`agent-loop.ts:148-271` `runLoop`）迴圈只有一個停止條件：這一輪 assistant
沒有發出任何 tool call。** 沒有 done 工具、沒有 finish 訊號、沒有回合上限。
在 `packages/` 全域 grep `maxTurns|maxSteps|maxIterations|turnLimit`，產品程式碼裡
一個都沒有（只有 `packages/ai/test/stream.test.ts` 一個測試常數）。

**F2（OpenCode，`session/prompt.ts:1110-1128`）停止判斷不看 `finish_reason`，看
「這一輪有沒有 tool part」。** 註解逐字：

> `// Some providers return "stop" even when the assistant message contains`
> `// tool calls. Keep the loop running so tool results can be sent back to`
> `// the model, but ignore cleanup-marked interrupted orphans.`

**F3（兩邊都是）工具失敗不是例外，是一則正常的 toolResult，迴圈照跑。**
pi：`executePreparedToolCall` 把 throw 接住轉成 `createErrorToolResult(...)`、`isError: true`
（`agent-loop.ts:660` 附近）。OpenCode：壞掉的 tool call 經
`experimental_repairToolCall`（`session/llm.ts:296`）改寫成 `invalid` 工具，模型收到
`The arguments provided to the tool are invalid: ${params.error}`，可以看著錯誤自己修。

**F4（pi，`tools/bash.ts`）stdout 與 stderr 合流，非零退出碼直接附在輸出尾巴：**
`throw new Error(appendStatus(outputText, "Command exited with code " + exitCode))`。
模型看到的是「完整輸出 ＋ 空行 ＋ `Command exited with code 1`」。
⚠ 對照組：**OpenCode 的 exit code 只進 metadata，不進模型可見文字**
（`tool/shell.ts:586-593`）——模型得從輸出內容猜成敗。這是兩者的直接分歧，
我們站 pi 這邊（理由見 §4.0.4）。

**F5（兩邊都是）截斷是契約，方向要分，而且截斷訊息本身是下一步指令。**
pi `tools/truncate.ts`：`DEFAULT_MAX_LINES = 2000`、`DEFAULT_MAX_BYTES = 50 * 1024`；
bash 走 **tail**（錯誤摘要在尾巴）、read 走 **head**。訊息逐字：
`[Showing lines 312-2311 of 5000. Full output: /tmp/pi-bash-xxxx]`、
`[Showing lines 1-2000 of 8123. Use offset=2001 to continue.]`。
OpenCode `tool/truncate.ts` 同樣是 `MAX_LINES = 2000` / `MAX_BYTES = 50 * 1024`，
並把全文寫到磁碟：`The tool call succeeded but the output was truncated. Full output saved to: ${file}`。

**F6（pi，`agent-loop.ts:228-233` ＋ `failToolCallsFromTruncatedMessage`）輸出被 token
limit 砍斷時，該訊息裡所有 tool call 一律不執行，每個都回一則錯誤：**

> `Tool call "{name}" was not executed: the response hit the output token limit, so its arguments may be truncated. Re-issue the tool call with complete arguments.`

理由（註解）：streaming 的 JSON 有 best-effort salvage parser，所以截斷的參數可能
「parse 得過、validate 得過，但內容是靜默不完整的」。

**F7（OpenCode，`session/processor.ts:29,352-378`）doom-loop 偵測門檻是 3：**
`const DOOM_LOOP_THRESHOLD = 3`；最後 3 個 part 全是 tool part、工具名相同、
`JSON.stringify(input)` 完全相同 ⇒ 觸發。預設處置（`agent/agent.ts:121`）是
`doom_loop: "ask"`——**問人類**。⚠ 無人值守時等於沒有守門員。

**F8（OpenCode，`packages/core/src/session/runner/max-steps.ts`）撞到步數上限不硬砍，
改成關掉工具、強迫一則純文字收尾。** `MAX_STEPS_PROMPT` 開頭逐字：

> `CRITICAL - MAXIMUM STEPS REACHED`
> `The maximum number of steps allowed for this task has been reached. Tools are disabled until next user input. Respond with text only.`

**F9（OpenCode，`tool/edit.ts:196-201`、`tool/write.ts:74-90`）唯一真正自動的
verification 是 LSP 診斷注入，不是 prompt。** 寫檔後自動跑 LSP 並把錯誤附在工具結果後：

> `LSP errors detected in this file, please fix:` ＋ `<diagnostics file="...">\nERROR [12:5] ...\n</diagnostics>`

`lsp/diagnostic.ts`：只取 `severity === 1`（ERROR，warning/info/hint 全丟）、
`MAX_PER_FILE = 20`、格式 `${severity} [${line}:${col}] ${message}`。
`touchFile(path, "document")` 會 `waitForDiagnostics()` 等 LSP 真的回報完才讀，不是 fire-and-forget。

**F10（pi）harness 層完全不叫模型驗證自己。** 在 `packages/agent/src` 與
`packages/coding-agent/src` 全域 grep `verify|Verify|run the tests|make sure|double-check`，
system prompt 與工具描述裡**一個字都沒有**。真正的驗證紀律寫在 `AGENTS.md`（專案檔）：

> `- After code changes (not docs): `npm run check` (full output, no tail). Fix all errors, warnings, and infos before committing.`
> `- If you create or modify a test file, run it and iterate on test or implementation until it passes.`

⚠ `full output, no tail` 是刻意的：作者知道模型會為了省 context 自我截斷，於是禁掉。
OpenCode 走反方向，把驗證寫進 provider prompt（`session/prompt/default.txt:70-76`）：

> `- Verify the solution if possible with tests. NEVER assume specific test framework or test script.`
> `- VERY IMPORTANT: When you have completed a task, you MUST run the lint and typecheck commands ... with Bash if they were provided to you to ensure your code is correct.`

最乾淨的一句在 `prompt/meta.txt:17`：

> `- IMPORTANT: Verify the correctness of your solution through execution whenever possible and reasonable: run code to confirm expected outputs, write and execute tests, and/or perform sanity checks.`

### 1.3 傳說清單：以下九條**不准**寫進任何 Vacant 文件或展場文案

| # | 傳說 | 為什麼不成立 |
|---|---|---|
| T1 | 「pi 的 harness 比 Claude Code 好 9.7pp」 | leaderboard 是 harness×model 的混合。pi 那一列用 **Opus 4.5**，Claude Code 那一列用 **Sonnet 4.5**。那是模型差，不是 harness 差。 |
| T2 | 「harness 是大差異的來源」 | 表上唯一乾淨的同模型對照（Claude Sonnet 4.5）：Terminus 2 **42.8%**、OpenHands **42.6%**、Mini-SWE-Agent **42.5%**、Claude Code **40.1%**——**四個 harness 全距 2.7pp，全部落在彼此誤差棒內**。openbench（2026-07-02，gpt-5.5-medium）更直接：5 個 harness 在 trivial／中等任務上正確率**全部打平 100%**，差異只在牆鐘與 token。 |
| T3 | 「pi 證明了 loop 比 single-shot 好」 | **Terminal-Bench 2.0 leaderboard （快照口徑逐字 `as of Dec 1, 2025`，`show-results.js:20-24`）上 60 個 entry 沒有任何一個是 single-shot baseline。** loop vs single-shot 在這份證據裡**完全沒有被測量**。 |
| T4 | 「極簡 system prompt 就夠了」 | 作者自己的論證是 `all the frontier models have been RL-trained up the wazoo, so they inherently understand what a coding agent is`。**gemma-4-12b-it-qat 沒有這個先驗**，前提不成立。 |
| T5 | 「pi 拿第 7／第 8 名」 | X 貼文說 8th、截圖顯示 rank 7，無法釐清（貼文回 HTTP 402）。引用數字 **49.8% ± 2.4**，不引用名次。 |
| T6 | 「pi 拿 51.2%」 | 那是 **CET-only 的第二次跑、只跑到 297/445 trials 的未完成 run**，作者說會更新但文中沒有更新版數字。 |
| T7 | 「2026-05 pi 在四個模型上贏 Cline 兩個」 | 一手來源查不到（mariozechner.at 文章索引 2024-07→2026-05-30 共 19 篇無對應文、pi.dev 無 benchmark 頁）。當未驗證傳聞處理。 |
| T8 | 「compaction 是 pi 拿高分的原因」 | compaction 在 **2025-12-04 的 v0.12.7** 才進版，跑分是 **12-02**。 |
| T9 | 「OpenCode 的 edit 工具強制 read-before-edit」 | `tool/edit.txt` 這樣寫，但這個 commit 的 `tool/edit.ts` **沒有這個檢查**（grep `FileTime`／`hasRead`／`lastRead` 全無命中）。描述與實作對不上。 |

**⚠ 稽核更正（Fable，2026-09-07）——引用時以本表為準，初稿的數字作廢**：

| 原文 | 更正 | 出處 |
|---|---|---|
| T3「61 個 entry」 | **60 個 entry** | `show-results.js:20-24` |
| T1／T2 引 leaderboard 沒有標快照日期 | 三條傳說引的是**同一份快照**，它自報的口徑逐字是 `as of Dec 1, 2025`。引用 T1 的 Opus 4.5／Sonnet 4.5 分列、T2 的 42.8／42.6／42.5／40.1% 時**必須連這個日期一起講**，否則會被讀成「現在的排行榜」 | `show-results.js:20-24` |
| F7「`agent/agent.ts:120`」 | **`agent/agent.ts:121`** | 同檔 |

⚠ **這三條由稽核者在外部原始碼上核對；本 checkout 沒有 `badlogic/pi-mono` 與
`sst/opencode` 兩個倉庫，本輪無法一手重驗**——照本文件開頭的紀律，這是
「無法一手驗證」等級的引用。要升級成一手驗證，必須先按 §1.1 的 commit 取回兩個倉庫、
依 `examples/archive_citations.py` 的三級規則落盤（含 sha256），再回來改這一行。

另有一條**紅線級**的：OpenCode `prompt/beast.txt:47` 第 10 點寫
`remember there are hidden tests that must also pass before the solution is truly complete`。
**這句直接違反 V/GT 分離（SPEC_GAIN §2）**，抄 beast.txt 的工作流時必須刪掉；
任何「多寫些測試以防萬一」的措辭都要檢查是不是在誘導模型猜 hidden case。

### 1.4 對「大差別來自 harness」這個判斷的誠實結論

人類的判斷是「harness（iterative test-run-fix loop、tool feedback、context discipline）
才是大差異的來源」。**外部證據既不能證實也不能證偽它**：

- 能證實的只有 **T2 的反面**：一旦你有 loop，**loop 的裝潢不重要**（同模型四個 harness 全距 2.7pp）。
- **loop vs 沒有 loop** 這個對比——也就是 Vacant 的 OFF／CONFORM／OFF5 現在在量的東西——
  外部一份資料都沒有。

所以本實驗的正當性**不能**建立在「業界公認 harness 才是關鍵」上（那是鐵律 5 的展場版問題）。
它建立在 §2 那個**我們自己量到的**東西上。

---

## 二、為什麼在 Vacant 這裡迴圈仍然值得一試（本地證據）

### 2.1 綁定約束是候選池，而選擇機制永遠打不破天花板

`docs/VACANT_ARCHITECTURE_AND_RESULTS_2026-09-07.md` §3.1 逐字：

> 綁定約束不是選擇器，是候選池。17–19% 的題目五個候選全錯，任何選擇機制都救不了。
> 這是任何「選得更聰明」路線的天花板，也解釋了為什麼加預算沒用：worker 的錯誤高度相關。

| 重放批次 | 池子上限（≥1 個候選正確） | 五個候選全錯 |
|---|---|---|
| `g_r441_gemma_only_mbpp_b`（gemma-12b、179 題） | **82.68%** | 31 題 |
| `g_r356_3arm_20260830`（qwen35b＋gemma12b、147 題） | **85.03%** | 22 題 |

**這是整個 harness 路線唯一站得住的動機**，而且它是一句可以寫下來的機制陳述：

> CONFORM／OFF5／EQ5 都是**選擇規則**——它們從 k 份既有候選裡挑一份，交付率的上限
> 就是「至少一份對」的比例。**修訂迴圈不是選擇規則**：第 t 輪的候選是用第 t−1 輪的
> 執行結果生出來的新東西，不在原本那 k 份裡面。所以迴圈是目前唯一**在原理上**
> 可以越過池子天花板的做法。

⚠ 誠實邊界：「原理上可以」不等於「實際上會」。12B 模型看著 stderr 也可能改不動；
而且修訂出來的候選是**朝著可見測資**改的，過擬合風險比隨機抽樣更高（§6 R4）。

### 2.2 r447 逐題重算：四個本輪新算出來的數字（零模型呼叫）

以下全部由 `runs/g_r447_conform_lcb2/{rows,calls}.jsonl` 離線重算，重算指令見附錄 A。
r447 ＝ LCB v2 120 題、seed `g-r440-lcb2`、單一模型池 `gemma-4-12b-it-qat`
（`calls.jsonl` 的 `server_model` 926/926 皆為此值）、`infra_void=0`、`run_complete=true`、
跑於 2026-09-04 14:22 → 2026-09-05 01:05。

**N1 修理的機會有多大：OFF 的 120 份草稿裡 41 份（34.2%）沒過可見驗收，而這 41 份
hidden 也全錯。** 交叉表（`rows.jsonl`）：

| 臂 | 可見通過 | hidden 通過 | 可見過但 hidden 錯（假交付素材） | hidden 過但可見沒過 |
|---|---|---|---|---|
| OFF | 79/120 | 61/120 | **18** | **0** |
| CONFORM | 113/120 | 84/120 | **29** | **0** |
| OFF5 | 97/120 | 76/120 | **21** | **0** |

「hidden 過但可見沒過」＝0 重現了 §3.1-D 的無損性 0/120。
**迴圈臂的作用面就是那 41 題**；其餘 79 題第一輪就會停，H 臂在那些題上與 OFF 完全一樣。

**N2 上限的算術：即使把 41 題全部修到可見通過，也不會全部變成正確交付。**
CONFORM 把可見通過從 79 推到 113（＋34），hidden 通過只從 61 推到 84（＋23）——
**轉換率 67.6%**，而且假交付從 18 漲到 29。若 H 臂把 41 題全修成可見通過而轉換率
維持 67.6%，交付率上限約 61 + 41×0.676 ≈ **88.7/120 ＝ 73.9%**；要打到
§5.6 的 EFFECTIVE 門檻（≥80%），轉換率必須顯著高於 CONFORM 的 67.6%——
也就是說**修訂出來的解必須比重抽出來的解更「真的對」，而不只是更「通過可見測資」**。
這正是本實驗要問的問題，而且它有機會失敗。

**N3 有 25/925（2.7%）的草稿在跑任何一條驗收之前就被沙箱載入器擋掉，其中 16 份是
`list.remove()`。** 用 `_candidate_functions` 的規則逐份重跑 r447 的 925 份成功回應
（我另寫的 `static_precheck` 與它在 925/925 上判定一致，0 分歧）：

| 臂 | 草稿數 | 載入器拒收 | `.remove` 屬性 | SyntaxError | `locals()` |
|---|---|---|---|---|---|
| OFF | 120 | **7（5.8%）** | 3 | 3 | 1 |
| CONFORM | 205 | 5 | 3 | 2 | 0 |
| OFF5 | 600 | 13 | 10 | 3 | 0 |
| 合計 | 925 | **25（2.7%）** | **16** | 8 | 1 |

**OFF 的 7 題全部被計成 hidden 錯**（`meets_demand=False`），佔 OFF 全部 59 個失敗的 11.9%。

`.remove` 那 16 份是量具偏誤，不是模型能力：`vacant/checks.py:191` 的 `_FORBIDDEN_ATTRS`
含 `remove`（防的是 `os.remove`），但 AST 層看不出 `x.remove(v)` 的 `x` 是 list 還是 `os`
⇒ **一個完全正常的 `list.remove()` 會讓候選連載都載不進去**。這與 round393 的
`typing` 漏洞是同一型（`DECISION_20260831_R393_TYPING_IMPORT_WHITELIST_BUG.md`）。

⚠ **這件事對本實驗有直接後果，寫在 §5.7-G3**：有靜態診斷的 H 臂會**免費**修掉這 7 題
（12B 把 `lst.remove(x)` 換成切片、把 SyntaxError 改對，都不難），那最多是 **+5.8pp**、
超過 §5.6 門檻的一半，而它買到的是「我們自己的禁用屬性表太嚴」的修補，不是能力提升。
**必須分層並報。**

⚠ 本輪**不改** `_FORBIDDEN_ATTRS`（改它會動到 `vacant/checks.py` 這個承重件、
需要重跑 B 層與一批測試）。建議另開一份 DECISION 處理，不要夾帶在本實驗裡。

**N4 成本與延遲的實測分佈（本實驗預算的依據）**，取自 `calls.jsonl` 的 `usage` 與 `latency_ms`：

| 臂 | 呼叫數 | prompt tokens | completion tokens | 總 tokens | tokens／題 | **tokens／正確交付** | 牆鐘 |
|---|---|---|---|---|---|---|---|
| OFF | 120 | 61,543 | 261,420 | 322,963 | 2,691 | **5,294** | 4,165 s |
| CONFORM | 205 | 108,460 | 623,626 | 732,086 | 6,101 | **8,715** | 11,654 s |
| OFF5 | 600 | 307,415 | 1,384,804 | 1,692,219 | 14,102 | **22,266** | 22,726 s |

單次呼叫的 completion tokens（n=926）：min 2、**p50 1,443**、p90 5,681、p99 13,242、
**max 33,974**。單次呼叫延遲：**p50 20.7 s**、p90 90.5 s、**max 504.9 s**。

⚠ **沒有任何 `max_tokens` 上限**——`brain_cline.make_body` 不送這個欄位（`brain_cline.py:110-118`）。
一次呼叫可以吐 34k tokens。這是 §4.0.6 預算設計的直接理由。

**N5 協定遵循度（12B 的實際表現）**：925 份回應**全部**至少有一個 markdown 圍欄（三個反引號）（0 例外），
但 **179 份（19.4%）有兩個以上的圍欄區塊**（分佈：1 塊 746、2 塊 112、3 塊 31、
≥4 塊 36，最多一份有 56 塊）。`extract_code` 取的是**第一個非空區塊**。
⇒ 在單輪臂上這 19.4% 大致無害，但在迴圈臂裡「解釋＋程式碼＋用法範例」的機率會上升，
**必須逐輪記錄區塊數**（§4.0.8），事後才查得出「第一塊規則」有沒有咬到人。
**不准為了 H 臂改 `gain_run.extract_code` 本身**——改它會同時動到 OFF／CONFORM／OFF5（§5.2 不變量 4）。D4 的做法是**另寫**一個只作用在修訂輪的 harness 取碼器，初稿輪仍走原件，兩個選擇都落盤。

---

## 三、實作前必須先同意的六條承重決策

### 3.1 不改 `vacant/checks.py`；回饋走 `run_python_capture` 包一層 try/except

**問題**：`run_python_check` 只回 bool（`checks.py:630-655`），`_run_sandboxed` 的
`out, _ = proc.communicate(...)` 把 **stderr 丟掉了**（`checks.py:606`）。
`meets_demand` 的失敗訊息對每個候選都是同一個常數字串 `"sandbox_check_failed"`。
⇒ **現況拿不到任何可以餵回模型的東西。**

**選項 A（否決）**：在 `checks.py` 加一個回傳 stderr 的函式。
否決理由：`checks.py` 是承重件（RECORD_SPEC、B 層、`tests/test_gain_*.py`、
`peerexec` 都吃它），動它就要重跑一整批；而且沒有必要——

**選項 B（採用）**：用**既有的** `run_python_capture`（`checks.py:656-678`），
把 `visible_check['code']` **原封不動**縮排進一個 try/except，只多印一行帶 nonce 的 JSON。
候選碼仍然只活在 worker、仍走 literal-only proxy、仍受 `python -I`／RLIMIT／
import 白名單約束——**與 OFF5 的 `behavior_signature` 是同一條路徑**（2026-08-20 修正後）。

**已在本機實跑驗證**（零模型呼叫，LCB v2 `lcb_3634`，重跑指令見附錄 A）：

```python
def visible_report(code, task, timeout_s=10):
    nonce = "FB_" + secrets.token_hex(8)
    var = "__vacant_fb_" + secrets.token_hex(4)
    indented = "\n".join("    " + l for l in task["visible_check"]["code"].splitlines())
    probe = (
        f"{var} = ['pass', '', '']\n"
        "try:\n" + indented + "\n"
        "except BaseException as __vacant_e:\n"
        f"    {var} = ['fail', type(__vacant_e).__name__, str(__vacant_e)]\n"
        f"print({nonce!r} + __import__('json').dumps({var}))\n"
    )
    out = run_python_capture(code, probe, timeout=timeout_s,
                             allowed_imports=_GAIN_ALLOWED_IMPORTS,
                             allowed_entry_points=(task["entry_point"],))
    ...
```

**變數名要帶 nonce**：候選可以定義任意頂層函式名，而 `_test_runner_source` 先貼 proxy
再貼 test_code；用固定名字有被候選的同名 proxy 佔走的理論風險。

### 3.2 實跑出來的四種失敗類別（＋一種「拿不到」）

| 候選 | `visible_report` 回傳 | `run_python_check` |
|---|---|---|
| 邏輯錯（`return len(s)`） | `['fail', 'AssertionError', "args=['abcdef'] got=6 want=0"]` | False |
| 執行期例外（`return s[999]`） | `['fail', 'IndexError', 'string index out of range']` | False |
| 死迴圈 | `['fail', 'TimeoutError', 'candidate solve timed out']` | False |
| `import os` | **`None`** | False |
| 語法錯 | **`None`** | False |

**`None` 代表「沙箱連載入都不肯」**，`_run_sandboxed` 在 `_candidate_functions` 回 None 時
直接回 `(None, "")`。它有兩個完全不同的成因（語法錯／禁用 import 或屬性），
**回饋必須說出是哪一個**，否則模型收到的是「你的程式壞了」這種零資訊訊息。
⇒ 這就是 §3.4 靜態預檢存在的理由，也是 OpenCode F9（LSP 診斷注入）在我們這邊的對應物。

### 3.3 MBPP+ 的 assert 訊息是**空的**；LCB v2 才是主場

- **LCB**（`codebench.py:_lcb_check_code`）的 assert 帶訊息：
  `f"args={__t['args']!r} got={__got!r} want={__t['expected']!r}"`。
  三個欄位**全部來自 `visible_tests`**，是客戶自己的驗收測資 ⇒ 給模型看**合法**。
- **MBPP+**（`codebench.py:_check_code`）產生的是
  `assert __aeq({entry}(*inp), __canon(*inp), atol)`——**沒有訊息**。
  本機實跑：`mbppplus_Mbpp/7` 的錯誤候選回 `['fail', 'AssertionError', '']`。

⚠ **而且不准去補**：MBPP+ 的期望值是 `visible_check` 裡內嵌的 canonical **當場算出來的**
（`exec({canonical!r}, __ns)`）。要在回饋裡寫出 `want=` 就必須執行 `__canon`，
而 canonical 是 GT（SPEC_GAIN §2 逐字：「canonical solution、expected outputs 與 plus cases
才是不能進 prompt 的 GT」）⇒ **那是 V/GT 破功**。

**後果，寫死進規格**：

1. 主實驗跑 **LCB v2**。這不只是因為 §3.1 說那裡效應最大，也是因為**只有那裡的回饋有內容**。
2. 任何 MBPP+ 的複製跑，回饋只能是 `AssertionError`（無訊息）＋
   `conform_failure_detail` 算出的**條號**（那是零模型呼叫、只用可見測資的既有機制）。
   複製跑的效果**天生就會比 LCB 小**，不准把這個差異讀成「MBPP+ 上 harness 沒用」。
3. 回饋渲染器**只准轉發 `str(exc)`**，永遠不准自己計算期望值、不准呼叫 `__canon`。
   稽核鉤子見 §5.8。

### 3.4 靜態預檢：**絕對不准執行模型寫的測試碼**

H-OC 要「模型自己寫額外測資」。**不可以讓模型交出 test code 讓我們跑。**
理由在 `checks.py:386-545`：`_test_runner_source` 把 test_code **原樣貼進 runner 的
module scope**，而 runner 裡有 `os`、`subprocess`、`sys`、`_worker.stdin`。
runner 是**受信任側**，只有 worker 裡的候選碼是不受信任的。
把模型產生的碼貼進 runner ＝ 自己開一個逃逸通道。

**採用的替代做法（repo 內已有先例）**：要模型交 **literal 對**，由 harness 用
**自己的**模板渲染成檢查碼。`brain_cline.REVIEWER_SYSTEM` 早就是這個協定
（`TEST_ARGS:` ＋ `EXPECTED:`，「反例會由系統實際執行」）。H-OC 沿用同一形狀：

```
SELFTEST: [<positional args as a python list literal>] -> <expected value as a python literal>
```

harness 端 `ast.literal_eval` 兩邊，用 `_lcb_check_code` 同款的 `__aeq` 模板渲染。
解析不了就丟掉並計數，**不回問模型**（省呼叫）。

⚠ **自測永遠不是出貨閘門**：R518 量到反例精確度上界 <0.80、R438/R516 量到評審票近乎
常數函數 ⇒ 模型自己寫的期望值有相當比例是錯的。規則寫死：
**只有 `visible_check` 決定出貨；自測失敗只在可見測資也失敗時才顯示**（可見一過就停，
所以這條自動成立），而且訊息裡必須標明 `(your own test — it may itself be wrong)`。

### 3.5 prompt 用**英文**

**決定：H 臂新增的所有 user-turn 文字用英文；`POOL` 的六個中文 system prompt 一字不動。**

理由不是偏好，是**對齊**：

1. OFF／CONFORM／OFF5 現在送的就是「中文 system prompt ＋ **英文** user turn」
   （`arm_off` 送 `task["prompt"]`，LCB 的題目是英文競賽題）。H 臂用英文寫 user turn，
   **語言組成與既有臂完全相同**；改用中文反而是引入一個 OFF 沒有的變因。
2. 回饋內容本身是英文／Python（`args=['abcdef'] got=6 want=0`、`SyntaxError: ...`）。
   在英文內容外面包一層中文指示，對 12B 是多一次語碼切換。
3. §1.2 借用的措辭（F4、F6、F10）都是英文原文；翻成中文就變成沒有出處的改寫。

**文件本身用繁體中文；prompt 一律引英文原文**（`~/.claude/.../report-in-traditional-chinese.md`）。

### 3.6 KS-1 與「prompt 就是處理本身」

鐵律 1（KS-1）要求「三臂模板逐字相同，唯一差異＝MemoryManager 注入的記憶區塊」。
**那條規則管的是記憶臂（X1 的 M0/M1/M2）**：那裡要量的是記憶的效果，所以 prompt 必須是常數。

**這裡不一樣：harness 臂要量的就是 harness，而 prompt 是 harness 的一部分。**
所以 H-PI／H-OC／H-MIX 的 prompt **本來就不同，而且必須不同**。
把它們統一成同一份 prompt 會讓整個實驗變成沒有處理的實驗。

**但 KS-1 的實質禁令照樣適用**，逐字寫死：

> 三條 H 臂的任何 prompt、任何回饋訊息，**禁止出現「你有責任／會被懲罰／會被扣分／
> 有人在看／這關係到你的評價」類措辭**。允許的只有「做什麼」與「執行結果是什麼」。

理由與 KS-1 相同：那類措辭量到的是提示詞效果不是機制效果。
`vacant/memory.py::assert_ks1_clean` 是既有的可執行防呆——
**H 臂的所有 prompt 常數必須過這一關**（測試見 §4.6-T7）。

**維持可比性的九條不變量**見 §5.2。

---

## 四、三條臂的完整規格

### 4.0 共同骨架（三條臂逐字相同的部分）

差異只在 §4.1–4.3 明列的地方；**其餘一律相同**。

#### 4.0.1 檔案與函式

新檔 `ops/gain/harness_arms.py`。**不動 `arm_off`／`arm_off5`／`arm_conform`／`arm_eq5`／`arm_on` 一個字。**

```
ops/gain/harness_arms.py
  ├─ HARNESS_BUDGET          # 預算常數（不是 CLI 旋鈕，見 4.0.6）
  ├─ static_precheck(code, allowed_imports, entry_point) -> (ok, reason)
  ├─ visible_report(code, task, timeout_s) -> ["pass"|"fail", exc_type, message] | None
  ├─ render_feedback(kind, payload, variant) -> str
  ├─ parse_selftests(text) -> list[(args, expected)]        # H-OC 用
  ├─ render_selftest_check(entry_point, cases) -> str       # H-OC 用
  ├─ PROMPT_* 常數（英文，逐字如 §4.1–4.3）
  └─ run_harness_arm(task, agents, rng, calls, book, ident, *, variant)
        -> (code, worker, involved, extra)                   # 與其他 arm_* 同簽章
```

#### 4.0.2 後端：新增 `ClineBrain.chat()`，**不動 `generate()`**

`generate()` 只送 `[system, user]` 兩則訊息（`brain_cline.py:110-118`），沒有多輪。
新增一個**並存**的方法（`generate` 逐位元不變，所有既有臂的落盤逐字不變）：

```python
def chat(self, messages, *, role="gen", meta=None, timeout_s=None, retries=None) -> tuple[str, dict]:
    """messages = [{"role": "user"|"assistant", "content": ...}]；system 用 self.system。
    回傳 (text, info)；info 至少含 finish_reason / usage / model / server_model。"""
```

與 `generate` 的**唯一**差別：
- body 的 `messages` ＝ `[{"role":"system",...}] + messages`（其餘欄位、temperature、
  retry／backoff／404 型號輪替、`RelayError`／`EmptyResponse`／`InfraVoid` 語意逐字沿用）；
- 落盤紀錄多三個鍵：`"messages"`（全文陣列，取代 `"prompt"` 的角色）、
  `"finish_reason"`、`"turn"`；同時**保留** `"prompt"` ＝ 最後一則 user 訊息全文，
  讓 `latency_summary`、`calls_audit.py` 這些既有工具不必改就讀得到。

⚠ **`finish_reason` 現在沒有被落盤**（`brain_cline.py` 只在 `EmptyResponse` 的錯誤字串裡
提到它）。F6 那條保護**必須**有它。這是 `chat()` 存在的第二個理由。

⚠ **未驗證的假設**：本階段零呼叫，所以**沒有驗證中轉接不接受 3 則以上的 messages**。
規格要求：run 一開始、模型池預檢之後，先發一次**四則訊息**的探針
（system／user／assistant／user，內容 `Reply with exactly: OK`）。
- 通過 ⇒ 走多輪模式，`summary.json` 記 `harness_wire_mode: "multiturn"`。
- 400／格式錯 ⇒ 退回**單則攤平模式**：把整個對話序列化成一則 user 訊息
  （格式刻意不像對話，抄 pi `docs/compaction.md` 的理由
  `This prevents the model from treating it as a conversation to continue.`），
  記 `harness_wire_mode: "flattened"`。
- **兩種模式的結果不得混算**（SPEC_GAIN §7 的 timeout／retry 同理）。

#### 4.0.3 文字協定（三臂相同）

- **出碼**：一個 markdown 圍欄區塊（三個反引號）。

**取碼器（D4，逐條寫死）**：

- **初稿輪（turn 1）走 `gain_run.extract_code`，一個字不改。** 這是 D4 的核心：
  turn 1 與 OFF 用**同一個**取碼器 ⇒ 「H 臂的 turn 1 對 OFF」是乾淨的比較，
  §5.3.1 的 prompt 效果才有意義。
- **修訂輪改用 harness 端取碼器**：取**第一個既 `ast.parse` 得過、又定義了 entry point**
  的圍欄塊；一個都找不到就 **fallback 回 `gain_run.extract_code`**。
  理由是 N5 量到的形狀：19.4% 的回應有兩塊以上，而迴圈會放大它
  （模型常先貼一段錯誤重述或修改說明、再貼修好的函式）。
- **兩個取碼器的選擇都逐輪落盤**（`extractor`、`code_sha256`、`baseline_code_sha256`、
  `extractor_divergent`），**分歧逐臂計數**（`extractor_divergences`）。
  分歧率是一級指標：接近 0 代表 D4 這個改動沒買到東西；很高則代表
  「H 臂比 OFF 好」有一部分來自取碼器，**裁決書必須把這一塊單獨講**。
- **`nocode` ＝ 整則回應一個圍欄塊都沒有**——判定用 harness 自己的偵測器
  （`_fenced_blocks`），**不是**「`extract_code` 回空字串」。
  ⇒ `fail_kind="nocode"`，回一則協定提醒（§4.0.4），**計入呼叫預算**，並計數。
- **有圍欄但第一塊不是 Python**（`blocks[0]` compile 不過）**單獨計數**
  （`first_block_non_python`），與 `nocode` 分開記——那是兩種不同的協定失敗，
  混在一起會讓 P-H8 的 MISS 讀不出原因。
- **多個圍欄** ⇒ 區塊數逐輪落盤（`n_code_blocks`，N5）。
- H-OC 的計畫輪另有 `PLAN:／EDGE CASES:／SELFTEST:` 三個前綴（§4.2）。

#### 4.0.4 回饋渲染（三臂**逐字相同**——這是刻意的）

三條臂的回饋文字完全一樣。**差異只在 prompt、迴圈與 context 政策**，
否則就分不清增益來自「有回饋」還是「回饋寫得比較好」。

```
The function was run against the acceptance tests. It did not pass.

{BLOCK}

Reply with exactly one Python code block containing the complete corrected
function. Do not explain.
```

`{BLOCK}` 依 `fail_kind` 取六種之一（全部英文、原文轉發、不做摘要、不加建議）：

| `fail_kind` | 來源 | `{BLOCK}` |
|---|---|---|
| `assert` | `visible_report` ＝ `['fail','AssertionError',msg]` | `AssertionError: {msg}` |
| `exception` | 其他 exc_type | `{exc_type}: {msg}` |
| `timeout` | `TimeoutError: candidate solve timed out` | `TimeoutError: the function did not return within the 10 second limit.` |
| `loader` | `visible_report` 回 `None` ＋ `static_precheck` 的 reason | `The code could not be loaded: {reason}` |
| `nocode` | 回應裡沒有圍欄 | `No Python code block was found in the reply.` |
| `selftest`（僅 H-OC，附加在上面任一段之後） | 模型自己的 SELFTEST | `Your own test also failed (this test is yours and may itself be wrong): args={args!r} got={got!r} you expected={expected!r}` |

**`static_precheck` 的 reason 是一個封閉集**（D4），逐字五個值：
`{syntax_error, forbidden_import, forbidden_attr, entry_point_missing, empty}`
——`PRECHECK_REASONS` 是模組常數，不准臨時多長一個字串出來（測試 T4／T5 釘住它）。
理由：reason 直接進**模型看得到的文字**，一個沒登記過的值同時代表
「模型收到一則沒見過的訊息」與「離線分析的分母裂開」兩件壞事。

其中 **`entry_point_missing` 必須與其餘四個分開計數**（`extra["entry_point_missing"]`）：
它的意思和另外四個不同——那不是「碼壞了」，是**碼沒壞、只是函式名不對**，
在 12B 上是一種光靠一句提醒就修得掉的協定失敗。
把它混進 `loader_refusals` 會讓 §5.7-G3 的分層讀數把「模型沒照協定命名」
算成「我們的禁用屬性表太嚴」，那是兩個相反的結論。

**截斷規則**（F5 的改寫）：`{msg}` 超過 2000 字元時保留**前 1000 ＋ 後 1000**，
中間插 `…[{n} characters omitted]…`。
不用 pi 的純 tail，因為我們的訊息形狀是 `args=…（前） got=… want=…（後）`，
砍頭會丟掉 args、砍尾會丟掉 want。整個 `{BLOCK}` 再硬上限 30 行。
**完整原文照樣落盤**（`extra.harness_turns[i].fail_message_full`），對應 pi 的
「全文寫進 temp 檔並把路徑告訴模型」——我們不告訴模型路徑（它沒有 shell），但保證事後查得到。

**`exit code` 這件事我們站 pi（F4）不站 OpenCode（F4 的⚠）**：狀態要明寫在模型看得到的
文字裡。上表每一行的第一個 token 就是狀態（`AssertionError:` / `TimeoutError:` /
`The code could not be loaded:`），不留給模型猜。

#### 4.0.5 一題一個 worker

`worker = rng.choice(agents)` **只抽一次**，整題的所有輪次都用同一個 persona。

理由：(a) pi／OpenCode 的迴圈就是一個 agent 一個 conversation；
(b) 更重要的是**把處理效果切乾淨**——CONFORM 的增益來自「換人重抽」，
H 臂的增益（若有）必須來自「同一個人看著執行結果改」。
中途換 persona 會把兩件事混在一起。
⇒ H 臂**不繼承** CONFORM 的換人紅利，這是設計要的，不是遺漏。

#### 4.0.6 預算（三臂相同，寫死成模組常數，**不做成 CLI 旋鈕**）

```python
HARNESS_BUDGET = {
    "max_calls": 5,        # 每題模型呼叫上限
    "max_tokens": 32_000,  # 每題 prompt+completion 累計上限（呼叫「之間」檢查）
    "max_wall_s": 900,     # 每題牆鐘上限（呼叫「之間」檢查）
    "sandbox_timeout_s": 10,
    "truncation_retries": 1,
    "doom_threshold": 2,   # 只有 H-MIX 用
}
```

**`max_calls = 5` 的理由**：等於 OFF5／EQ5。SPEC_GAIN §3 逐字「**OFF-5x 是這個實驗誠實
與否的分水嶺**……真正要回答的是：等預算之下，Vacant 打不打得贏 self-consistency」。
用 6 會讓 H 臂比 OFF5 多花一通，那正是 SPEC 罵的「拿成本冒充機制」。
⇒ H-PI ＝ 1 初稿 ＋ 最多 4 次修訂；**H-OC ＝ 1 計畫 ＋ 1 初稿 ＋ 最多 3 次修訂**
（計畫輪要跟一次修訂機會競爭——這正是要問的問題，不是設計缺陷）。

**`max_tokens = 32_000` 的理由（N4）**：OFF5 每題平均 14,102；單次 completion 的
p99 是 13,242、max 33,974。上限訂在 32k ≈ OFF5 的 2.3 倍，
低於這個數會變成常常在「模型話太多」而不是「迴圈跑太久」上收工。

**`max_wall_s = 900` 的理由（N4；D6 裁定：外部數字已刪，改綁我們自己的實測）**：
本專案自己量到的單次呼叫延遲 p50 **20.7 s**、p90 **90.5 s**、max **504.9 s**
（`runs/g_r447_conform_lcb2/calls.jsonl`，n=926，重算指令見附錄 A）。
**900 s ＝ 504.9 × 1.78**——「一次歷史最壞延遲再加約八成」的安全係數。

⚠ **初稿在這裡引的那組「pi 的逾時比例」數字（試驗次數／逾時件數／百分比）已整條刪除，
本檔各處都不再出現。** D6：那組數字來自
`https://mariozechner.at/posts/2025-11-30-pi-coding-agent/` 這篇部落格文章裡的一張圖，
本 repo 沒有依 `examples/archive_citations.py` 的三級規則落盤
（URL ＋圖名＋抓取日期＋sha256 快照），所以**不留「作者自報」版本、直接刪**
——**連「原本寫的是多少」都不複述**，複述等於用一份沒有落盤的來源當事實。
要復活它只有一條路：照那三級規則抓一次、落盤、再引。
刪掉它之後 `max_wall_s` 的正當性**完全建立在我們自己落盤的延遲分佈上**
（`runs/g_r447_conform_lcb2/calls.jsonl` 的 max 504.9 s × 1.78），
與任何外部宣稱無關——這正是 D6 要的效果，不是把數字藏起來。

所以 (a) 要有這條線，(b)**撞線要單獨記成一個 outcome**，
不可以混進失敗率（`stop_reason="budget_wall"`）。

⚠ **不送 `max_tokens` 給端點**。H 臂的 request body 除了 `messages` 之外與 OFF 完全相同。
若只有 H 臂設了輸出上限，長答案會被砍而 OFF 不會 ⇒ 那是憑空造出來的劣勢。
預算只在**呼叫之間**當停止條件。

#### 4.0.7 停止規則（依序檢查）

```
每輪：
  1. 呼叫模型 → (text, info)
  2. info.finish_reason == "length" 且 truncation_retries 還有額度
        → 不使用這份輸出，回一則
          "The previous reply was cut off before it was complete. Reply again with
           exactly one Python code block containing the complete function."
          （抄 F6 的語意：截斷的輸出可能語法上 parse 得過卻是靜默不完整的）
          truncation_retries -= 1；計入呼叫預算；記 kind="truncated_retry"；回到 1
  3. code = extract_code(text)；沒有圍欄 → fail_kind="nocode"
  4. ok, reason = static_precheck(code, ...)         # 零沙箱、零呼叫
     不 ok → fail_kind="loader"
  5. ok → rep = visible_report(code, task)
     rep is None       → fail_kind="loader"（reason 由步驟 4 補；理論上不該到這裡，
                          到了就記 detail_reason="precheck_disagrees" 並照實落盤）
     rep[0] == "pass"  → **接受**，stop_reason="visible_pass"，跳出
     否則              → fail_kind ∈ {assert, exception, timeout}
  6. （僅 H-MIX）doom 判定，見 §4.3
  7. 預算檢查（呼叫數 / tokens / 牆鐘任一超過）→ 跳出，stop_reason ∈
        {"budget_calls","budget_tokens","budget_wall"}
  8. 組回饋訊息 → 回到 1
```

**`InfraVoid` 一律往外拋**，與 `arm_conform` 完全相同 ⇒ dispatch 端把該格記成
`infra_void`（`gain_run.py:1590` 附近的 try/except）。已經花掉的呼叫仍在 `calls.jsonl`，
該格不進分母。**不新增 void 語意。**

#### 4.0.8 拒交語意（**必須與 CONFORM 逐字相同**，否則結果不可比）

```python
accepted = (chosen is not None)          # 有沒有任何一輪通過 visible
code = chosen if accepted else last_draft
return code, worker, involved, {"accepted": accepted, "visible_ok": accepted, ...}
```

拒交時**仍然回傳最後一份草稿**——dispatch 端無條件用 `hidden_check` 離線計分，
那是評分不是出貨；`accepted=False` 才是「沒有交出去」。
這段語意逐字抄 `arm_conform` 的註解（`gain_run.py:603-606`），
目的就是讓 `leaked = accepted and not truth` 在六條臂之間同義。

#### 4.0.9 逐輪落盤（離線分析的全部依據）

`extra["harness_turns"]` ＝ list，每輪一個 dict：

```
turn, kind ∈ {plan, build, revise, truncated_retry, doom_nudge},
agent_id, model, server_model, finish_reason, latency_ms,
prompt_tokens, completion_tokens,
n_code_blocks,                      # N5：第一塊規則有沒有咬到人
code_sha256, code_chars,
precheck_ok, precheck_reason,
fail_kind, fail_exc_type, fail_message (≤2000), fail_message_full_sha256,
n_visible_tests,                    # 來自 _visible_test_slicer，零成本
selftests_parsed, selftests_failed, # H-OC
feedback_chars, feedback_sha256,
context_messages, context_prompt_tokens,
entry_hash                          # 這一輪的收據鏈 entry
```

`extra` 頂層（進 `rows.jsonl`）：

```
accepted, visible_ok, harness_variant, harness_calls, harness_tokens_total,
harness_wall_s, stop_reason, first_pass_turn, n_turns,
loader_refusals, nocode_turns, truncated_retries, doom_triggered,
receipt_head, harness_turns
```

**收據**：每一輪 `book.append("harness_attempt", rec, ident, ...)`、收官
`book.append("harness_verdict", ...)`，與 CONFORM／EQ5 同一條 hash-chain。
`save_receipts` 已經會把任何非空的鏈寫出來（`gain_run.py:517-540`），**不用改**。
成本：簽章＋上鏈 1.0 ms／筆（R449 §三-3 實測），可忽略。

---

### 4.1 H-PI — 極簡迴圈

**設計主張**：只做 F1（迴圈到模型不再需要動作）＋ F3（失敗是一則正常輸入）＋
F4（狀態明寫）＋ F10（**harness 不叫模型驗證自己**）。
沒有計畫、沒有診斷、沒有 verify 指示、沒有 doom 偵測、**完整對話全留**。
它是 baseline：如果連它都贏，後面的裝潢就不必談；如果只有它輸，就知道裝潢在買什麼。

**system prompt**：`POOL` 的六個之一，**一字不動**（§5.2 不變量 2）。

**turn 1（build）**——`PROMPT_HPI_BUILD.format(entry_point=..., task=task["prompt"])`：

````
Write a complete Python solution.

Reply with exactly one Python code block and nothing else:

```python
def {entry_point}(...):
    ...
```

Rules:
- Define a top-level function named `{entry_point}`. Do not rename it.
- Only these modules can be imported: bisect, cmath, collections, functools,
  heapq, itertools, math, operator, re, sys, typing.
- Do not call input(), open(), eval(), exec(), locals(), globals() or getattr().
- Return the value. Do not print it.

Task:
{task}
````

**turn 2..5（revise）**：§4.0.4 的回饋訊息，原文照送。

**context 政策**：**全留**。第 n 輪送出的 messages ＝
`[u1, a1, u2, a2, …, u_n]`，一則都不丟（pi 的 `runLoop` 就是一路 append，
而 compaction 在跑分當時還不存在——T8）。

**停止**：§4.0.7。**沒有** doom 偵測（pi 沒有這個機制）。

**為什麼沒有 verify 指示**：F10。pi 的 system prompt 與工具描述裡
`verify|run the tests|make sure|double-check` **一個字都沒有**，
它靠的是「唯一的資訊來源就是真實執行結果」。這條臂就是在測那個主張。

---

### 4.2 H-OC — 先計畫後動手，加靜態診斷

**設計主張**：把 OpenCode 真正**自動**的那一件事（F9 的 LSP 診斷注入）搬過來，
加上它 prompt 層唯一有結構的東西（`prompt/gemini.txt:21-24` 的 self-verification loop、
`prompt/default.txt:70-76` 的 Doing tasks 步驟）。**代價是一通呼叫**。

**turn 1（plan）**——`PROMPT_HOC_PLAN`：

```
Before writing code, plan.

Reply in exactly this format and nothing else:

PLAN:
<2 to 4 short lines: the algorithm you will use>
EDGE CASES:
<2 to 4 short lines: inputs that could break it>
SELFTEST: [<positional arguments as a Python list literal>] -> <expected value as a Python literal>
SELFTEST: ...

At most 3 SELFTEST lines. Each one must be a case you worked out yourself from
the statement and the examples above. Write "SELFTEST: NONE" if you cannot work
one out. Do not write the solution yet.

Task:
{task}
```

**turn 2（build）**——`PROMPT_HOC_BUILD`（前一輪的計畫由對話歷史帶著，不重貼）：

````
Now write the solution.

Reply with exactly one Python code block and nothing else:

```python
def {entry_point}(...):
    ...
```

Rules:
- Define a top-level function named `{entry_point}`. Do not rename it.
- Only these modules can be imported: bisect, cmath, collections, functools,
  heapq, itertools, math, operator, re, sys, typing.
- Do not call input(), open(), eval(), exec(), locals(), globals() or getattr().
- Return the value. Do not print it.
````

**turn 3..5（revise）**：§4.0.4 的回饋，**外加**：

1. **靜態診斷優先**（F9 的移植）：`static_precheck` 不過就**不跑沙箱**，
   直接回 `The code could not be loaded: {reason}`。
   格式抄 OpenCode 只報 severity-1、上限 20 條的節制；我們一次只有一個 reason，天然滿足。
   ⚠ **不用 LSP**：OpenCode 的 Python LSP 需要專案 marker
   （`NearestRoot(["pyproject.toml","setup.py","setup.cfg","requirements.txt","Pipfile","pyrightconfig.json"])`），
   我們是暫存目錄裡的一份 .py，server 根本不會起來。用 `ast.parse` ＋ 白名單直接判，務實得多。
   ⚠ **不用 pyflakes**：`CLAUDE.md` 慣例「runtime 依賴只有 `cryptography`」。
2. **自測回報**：可見測資失敗時，把模型自己的 SELFTEST 也跑一遍
   （harness 渲染，§3.4），失敗的第一個附在回饋後面，**標明是它自己的測試、可能是錯的**。

**context 政策**：**全留**（與 H-PI 相同 ⇒ H-OC vs H-PI 的差異不含 context 政策）。

**停止**：§4.0.7。**沒有** doom 偵測。

---

### 4.3 H-MIX — 我判斷最好的組合

**每個元件都指名出處，沒有出處的不放。**

| 元件 | 出處 | 為什麼放 |
|---|---|---|
| 原文執行回饋、狀態明寫 | F3、F4 | 兩個專案唯一共識；也是本設計最便宜的一課 |
| 靜態診斷先於跑測試 | F9（改用 `ast`＋白名單，理由見 §4.2） | N3：25/925 的草稿連載都載不進去，其中 OFF 有 7 題（5.8%）就這樣輸掉 |
| 一句 verify 指示 | `prompt/meta.txt:17` 逐字 | 成本一行；OpenCode 選擇把它寫進 prompt，pi 選擇不寫（F10）——H-PI 已經測了「不寫」，這裡測「寫」 |
| doom-loop 偵測 | F7（門檻 3 → **2**；`ask` → **自動介入**） | 預算只有 5 通，等到第 3 次重複就沒機會了；無人值守（`CLAUDE.md`「離線可跑、可無人值守循環」）不能問人類 |
| context 紀律：只留最後一次失敗 | OpenCode `session/compaction.ts:273-315` 的 prune（把舊 tool output 換成 `"[Old tool result content cleared]"` 而**不刪訊息**） | §5.6 的 token 門檻直接獎勵它；而且 12B 的 context 比前沿模型脆弱得多 |
| **不放**計畫輪 | — | 5 通預算下計畫輪要吃掉一次修訂機會；而且 H-OC 已經在測它。放進來會讓三條臂互相不可歸因 |

**turn 1（build）**——`PROMPT_HMIX_BUILD`＝ `PROMPT_HPI_BUILD` **加一行**（插在 Rules 之後、Task 之前）：

```
Before you answer, check your function against the examples in the task by
hand and fix anything that does not match.
```

（逐字取自 `prompt/meta.txt:17` 的核心子句 `Verify the correctness of your solution
through execution whenever possible and reasonable` 的**改寫版**——因為模型在這裡
沒有 execution 可用，只能 by hand；改寫過所以不標「逐字引用」。
KS-1 檢查：沒有責任／懲罰／監督語意。）

**turn 2..5（revise）**：§4.0.4 的回饋 ＋ §4.2 的靜態診斷優先。

**context 政策（與另外兩條臂的關鍵差異）**：第 n 輪送出的 messages ＝

```
[ u1(build prompt) ,
  a_{n-1}(上一輪的完整回應，原文) ,
  u_n(這一輪的回饋) ]
```

也就是**只保留初始題目、最近一份草稿、最近一次失敗**。中間輪次全部丟掉。
⚠ 抄 OpenCode 的 prune 而不是它的 compaction：prune **零模型呼叫**，
compaction 要多花一次呼叫（我們只有 5 通，不划算），而且單函式任務也逼不到 context 上限。
⚠ 這是**有代價**的設計：模型看不到「我前兩輪試過什麼」，可能繞回去。
doom 偵測就是這個代價的對沖。

**doom-loop 規則（只有這條臂有）**：

```
signature = (fail_kind, fail_exc_type, sha256(fail_message_full))
若本輪 signature 與上一輪相同：
    doom_hits += 1
    若 doom_hits == 1  → 這一輪的回饋**後面追加** DOOM_NUDGE，記 kind="doom_nudge"
    若 doom_hits >= 2  → 停止，stop_reason="doom"，走拒交路徑
```

`DOOM_NUDGE`（逐字）：

```
The same failure happened twice with the same input. Do not adjust the same
line again. State in one sentence what the function currently computes for
that input and why that is not what the task asks for, then write a different
approach.
```

⚠ 用 `fail_message_full` 的 sha 而不是 `code_sha256`：模型常常改了幾行但行為不變
（OpenCode 比對的是 `JSON.stringify(input)` ＝ **動作**，不是原始碼）。
`stop_reason="doom"` 要**單獨計數**，它與 `budget_calls` 是不同的失敗故事。

---

### 4.4 三條臂的差異一覽（其餘一律相同）

| | H-PI | H-OC | H-MIX |
|---|---|---|---|
| 計畫輪 | ✗ | ✓（吃掉 1 通） | ✗ |
| 模型自寫測資（不執行其碼，只吃 literal） | ✗ | ✓ | ✗ |
| 靜態診斷先行 | ✗ | ✓ | ✓ |
| verify 指示（1 行） | ✗ | ✗（計畫輪本身就是前置驗證） | ✓ |
| doom-loop 偵測 | ✗ | ✗ | ✓（門檻 2） |
| context | 全留 | 全留 | 只留最後一次失敗 |
| 可用的**寫碼**輪數（max_calls=5） | 5 | 4 | 5 |

**這是三點比較，不是因子拆解。** 各配對能講什麼、不能講什麼：

- `H-PI vs OFF`：**有沒有迴圈**有差嗎（同一個 worker、同一份題目）。
- `H-PI vs CONFORM`：**修訂**打不打得贏**換人重抽**。
- `H-OC vs H-PI`：前置（計畫＋自測）＋診斷 vs 空迴圈。
- `H-MIX vs H-PI`：診斷＋verify＋doom＋context 紀律 vs 空迴圈。
- `H-MIX vs H-OC`：同樣 5 通預算，前置 vs 迴圈衛生。

⚠ **靜態診斷同時出現在 H-OC 與 H-MIX ⇒ 計畫輪的獨立效果在這個設計裡不可辨識。**
若 H-OC 與 H-MIX 都贏 H-PI，要歸因就得再跑第四條臂（H-PI ＋ 只加診斷）。
**現在就寫進預註冊當後續條件**（§5.10 的 P-H9），不要事後補。

---

### 4.5 接進 `gain_run.py`（不動既有臂的最小改動集）

**改動 1／4 — import**（檔頭既有 import 區塊之後）：

```python
from ops.gain.harness_arms import HARNESS_BUDGET, run_harness_arm  # noqa: E402
```

**改動 2／4 — `KNOWN_ARMS`**（`gain_run.py:1271`）：

```python
KNOWN_ARMS = {"OFF", "OFF5", "ON", "ONR", "CONFORM", "EQ5", "HPI", "HOC", "HMIX"}
```

**改動 3／4 — 決策量具的硬擋**（`gain_run.py:1339` 附近，round689 那一段）：

```python
_gate_arms = {"CONFORM", "EQ5", "HPI", "HOC", "HMIX"} & {a.strip() for a in args.arms.split(",")}
```

理由與 round689 逐字相同：H 臂也用 `visible_check` 當**出貨閘門**，
量具沒驗過的話「閘門根本沒有閘」會長得跟「機制很便宜」一模一樣。
⚠ 這一行是本次唯一動到**共用路徑**的改動；它只**增加**停止條件，
不含 H 臂的 run 行為逐位元不變。

**改動 4／4 — dispatch**（`gain_run.py:1580` 附近，`elif arm == "EQ5":` 之後、
`elif arm == "ON":` 之前）：

```python
elif arm in ("HPI", "HOC", "HMIX"):
    code, worker, involved, extra = run_harness_arm(
        t, agents, rng, calls, s["book"], s["ident"], variant=arm)
    accepted = extra["accepted"]
```

**不動的東西（明列，稽核時逐條核）**：
- `finalize()` 一行不改。H 臂用的是通用欄位（`accepted`、`n_acc_ok`、`calls`、
  `wall_s`、`cost`），`revision_transitions`／`eq5_*` 對 H 臂自然是 `None`。
  harness 專屬的聚合在離線分析腳本算，不塞進 `summary.json`。
- `st` 的初始化不改（`book`／`ident` 本來就每臂各一份）。
- `save_receipts` 不改。
- `write_summary` 的 `equal_budget_comparison_valid` 不改（它只問 ON／OFF5）。
- `rows.jsonl` 的寫入不改；`extra` 的鍵不在排除集 `{"votes","raw_reviews",
  "initial_code","vote_code"}` 裡，會自動全部寫出去。
- **`arm_off`／`arm_off5`／`arm_conform`／`arm_eq5`／`arm_on` 一個字都不動。**
- `extract_code`、`meets_demand`、`behavior_signature`、`conform_failure_detail`、
  `_visible_test_slicer` 一個字都不動（H 臂只**呼叫**它們）。

**啟動指令**（D9：**兩塊、兩顆直連後端、併發**；`--decision` 閘門要求 DECISION 檔內文含 run 名字）：

```
# block a —— VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions
python3 ops/gain/gain_run.py \
  --out runs/g_r460_harness_lcb2_a \
  --decision DECISION_20260907_R460_HARNESS_PREREG.md \
  --bank lcb2 --n 60 --offset 0 --seed g-r440-lcb2 \
  --arms OFF,CONFORM,OFF5,HPI,HOC,HMIX \
  --models gemma-4-12b-it-qat \
  --probe-sample 0 \
  --request-timeout-s 600 --retries 4

# block b —— VACANT_GAIN_API=http://100.86.226.21:1234/v1/chat/completions
python3 ops/gain/gain_run.py \
  --out runs/g_r460_harness_lcb2_b \
  --decision DECISION_20260907_R460_HARNESS_PREREG.md \
  --bank lcb2 --n 60 --offset 60 --seed g-r440-lcb2 \
  --arms OFF,CONFORM,OFF5,HPI,HOC,HMIX \
  --models gemma-4-12b-it-qat \
  --probe-sample 0 \
  --request-timeout-s 600 --retries 4
```

發射器 `ops/gain/launch_harness_lcb2.sh` 一支發兩塊，各自 `flock`、各自 `launch.log`，
各自探**自己的**後端 `/v1/models`（**不探 hub**）。收官一律兩塊一起餵給 analyzer：
`python3 ops/gain/analyze_r460.py --run runs/g_r460_harness_lcb2_a runs/g_r460_harness_lcb2_b --bank lcb2 --rescore-turn1`。

`--seed g-r440-lcb2` **必須與 r447 相同**：`LiveCodeBenchLoader.iter_tasks` 用
`sha256(f"{seed}:{task_id}")` 排序 ⇒ 同 seed ＝ 同題序；而每臂的 rng 是
`random.Random(f"{seed}:{arm}")` ⇒ 新的 OFF 臂會把**同一個 persona 指派給同一題**，
與 r447 的 OFF 逐格對齊。這讓「新 OFF vs r447 OFF」變成一個乾淨的**後端漂移探針**（§5.1）。

⚠ **D9 的代價，寫在指令旁邊**：那顆 rng **在每一塊各自從頭抽**
⇒ **只有 block a（offset 0）的 persona 指派與 r447 對齊**。
block b 的第 1 題拿到的是 r447 第 1 題的 persona，不是第 61 題的
⇒ **P-H0 這個漂移探針只在 block a 上成立**，錨換成 r447 前 60 題的 32/60 ＝ 53.33%、
窗從 ±10pp 放寬成 ±15pp（n 從 120 掉到 60）。詳見
`DECISION_20260907_R460_HARNESS_PREREG.md` §二-5 與 §三 P-H0。

### 4.6 必須有的測試（全部零 API 呼叫，`tests/test_gain_harness_arms.py`）

| # | 測什麼 | 判準 |
|---|---|---|
| T1 | 早停 | 第一輪就通過 visible ⇒ `harness_calls == 1`、`accepted is True`、`stop_reason == "visible_pass"` |
| T2 | 修訂會發生 | 假 agent 第 1 輪給壞碼、第 2 輪給好碼 ⇒ `accepted is True`、`first_pass_turn == 2`、第 1 輪的 `fail_kind == "assert"` |
| T3 | 拒交語意 | 五輪都壞 ⇒ `accepted is False`、`stop_reason == "budget_calls"`、**仍回傳最後一份草稿**（與 `arm_conform` 同型） |
| T4 | 四種 fail_kind | 用 §3.2 那五份候選（邏輯錯／例外／死迴圈／`import os`／語法錯）⇒ 四種 `fail_kind` 各命中一次，且 `loader` 那兩份的 `precheck_reason` 不同 |
| T5 | `static_precheck` 不漂移 | 對一組候選語料，`static_precheck(...)[0]` 與 `checks._candidate_functions(...) is not None` 逐份一致。**本輪已在 r447 的 925 份真候選上跑過：0 分歧**；測試用小語料 + 這個判準防未來漂移 |
| T6 | 回饋不含 GT | 對每一則送出的 user 訊息斷言：不含 `__canon`、不含 `exec(`、不含任何 `hidden_check` 專屬案例的 `repr(args)`（見 §5.8） |
| T7 | KS-1 | `harness_arms` 模組裡所有 `PROMPT_*`／`DOOM_NUDGE`／回饋模板全部過 `vacant.memory.assert_ks1_clean` |
| T8 | 收據可驗 | 跑完後 `Logbook.verify_chain` 為真；改掉任一 entry 的一個欄位 ⇒ 驗不過 |
| T9 | doom | H-MIX 連續兩輪同 signature ⇒ 第一次追加 `DOOM_NUDGE`、第二次 `stop_reason == "doom"`；H-PI／H-OC 同樣輸入下**不會**觸發 |
| T10 | context 政策 | H-MIX 第 4 輪送出的 messages 長度 == 3；H-PI 第 4 輪 == 7 |
| T11 | 截斷保護 | `finish_reason == "length"` ⇒ 該輪輸出不被採用、重發一次、`truncated_retries == 1`；第二次再截斷就不再重發 |
| T12 | 不動既有臂 | `arm_off`/`arm_off5`/`arm_conform`/`arm_eq5`/`arm_on` 的原始碼 sha256 與 HEAD `1bcb31a` 相同（防止「順手改一下」） |

---

## 五、實驗設計

### 5.1 題庫、以及為什麼**要**重跑 OFF／CONFORM／OFF5

**題庫：LCB v2（120 題，72 medium／48 hard）**，seed `g-r440-lcb2`。理由三條：

1. 效應最大（`docs/…RESULTS…`§3.1：CONFORM−OFF 在 LCB v2 是 **+19.17pp**、
   MBPP+ 只有 +4.58pp；OFF5−OFF 在 LCB v2 是 **+12.50pp**、MBPP+ 是 +0.81pp 且被判 `RULED_OUT`）。
2. **只有這裡的回饋有內容**（§3.3：MBPP+ 的 assert 訊息是空字串）。
3. 有一份逐格可比的既有 run（r447）當後端探針。

⚠ **汙染**：LCB v2 的日期視窗是 2023-08-26 → 2025-04-05，其中 **`lcb_3026` 是 2023-08-26**，
比其餘題目早一年多（`codebench.py:LiveCodeBenchLoader` docstring 逐字）。
主張「晚於訓練截止」時必須把它單獨列出。⇒ §5.7-G4 要求逐題附難度與日期。

**要不要重用 r447 的 OFF／CONFORM／OFF5 數字？答案是不要，要在同一個 run 裡重跑。**

支持重用的（都成立）：同一批 120 題、同一 seed、`infra_void=0`、`run_complete=true`、
`server_model` 926/926 都是 `gemma-4-12b-it-qat`、tokens 有落盤、
McNemar 的配對是逐題的，跨 run 配對在算術上沒問題。

**否決重用的三條，任何一條單獨就足夠：**

1. **後端漂移不可觀測。** r447 跑於 2026-09-04，本 run 至少晚三天；
   期間 ops 側已經動過（`54bfcde ops(loop): localagent 預設模型改 qwen3.6-35b-a3b`），
   而記憶檔 `vacant-gain-backend-topology.md` 記著 8765 的卡數已經變過。
   若 H 臂輸了，我們**分不出**是「harness 沒用」還是「後端變差了」。
2. **`gain_run` 的交錯設計就是為了這件事。** round278 的註解逐字：
   `for task: for arm` 讓「中斷在任何時刻都會留下**兩臂格數相等**的可分析資料」。
   把六條臂放進同一個交錯 run，後端漂移對每一條臂的影響在時間上是對齊的
   ——這是**設計上**消掉混淆，不是統計上假設它不存在。
3. **r447 的 `runner_git.dirty == True`。** 那一輪的碼版本無法逐位重建
   （`pool_precheck` 的紀律：`sha=None` 當「沒記錄」不當「相同」；`dirty=True` 同理）。

**那 r447 拿來做什麼**（這是它真正的價值）：**當後端的量具驗證**——
沿用「量具要先答已知答案」那條紀律，只是這次驗的是端點不是判定邏輯。
預註冊：

> **P-H0（後端漂移探針；D9 之後只在 block a 上判）**：
> `runs/g_r460_harness_lcb2_a`（offset 0 的 60 題）的 OFF 臂交付率落在
> **53.33% ± 15pp**（＝[38.3, 68.3]）之內。落在區間外 ⇒ 後端已漂移，
> **本 run 與 r447 的任何橫向比較作廢**，而本 run 內部的六臂比較仍然有效
> （同一題的六臂共享同一顆後端）。
>
> 兩個數字都因 D9 換過，**換在資料之前**：錨從 61/120 ＝ 50.83% 換成 r447
> **前 60 題**的 32/60 ＝ 53.33%（block a 就是那 60 題、同序）；
> 窗從 ±10pp 放寬成 ±15pp（n 從 120 掉到 60，二項 SE 從 4.56 漲到 6.44pp，
> ±10×√2 ≈ ±14.1 ⇒ 取 ±15）。**放寬的理由是 n 減半，不是為了讓它容易 HIT。**
> **block b 不判**：它的 persona 指派與 r447 不對齊（每臂的 rng 在每一塊各自從頭抽）。
> ⇒ **block b 那顆後端（`100.86.226.21:1234`）沒有事前錨**，本 run 對它一句話都不能說。

**⚠ D2 裁定：OFF5 不准省跑。** 初稿在這裡寫「機時不夠時唯一可接受的省法是砍掉 OFF5，
把 token 門檻改綁 r447 的 22,266」——**那條已作廢**，理由是它與 P-H0 互相拆台：

- P-H0 存在的前提是「後端可能已經漂了」。**若 P-H0 MISS（後端真的漂了），
  那顆歸檔常數 22,266 同時失效**——它是 r447 那個後端上量到的 token 數。
  也就是說：省跑 OFF5 的那個備案，剛好在**最需要它的時候**（後端漂了）不能用。
- 反過來若 P-H0 HIT，省跑省下的 6.3 h 也不再值得——後端沒漂，六臂交錯照跑就好。
- ⇒ 省跑 OFF5 在兩種世界裡都不划算。**OFF、CONFORM、OFF5 三條對照一條都不准省。**

**P-H0 的效力範圍也要一起寫死**（免得收官時被放大）：
P-H0 MISS **只作廢本 run 與 r447 的橫向比較**（含「r447 的 22,266 當事前錨」這種引用），
**不作廢本 run 內部的六臂比較**——六條臂共享同一個後端、在同一個交錯 run 裡逐題輪流跑，
後端漂移對它們的影響在時間上是對齊的。
⇒ §5.6 的四條門檻裡，只有 (iii) 需要 `TPC_OFF5`，而那個值**一律取本 run 的 OFF5**，
所以 **P-H0 MISS 不會讓 §5.6 的任何一格失效**。這一句是事前寫的，不是收官時的解釋。

### 5.2 對齊不變量（九條，稽核時逐條核）

| # | 不變量 | 怎麼保證 |
|---|---|---|
| 1 | 同一批 120 題、同一題序 | 同 bank 同 seed；`n_tasks_loaded=120` |
| 2 | 同一個 agent 池、六個 persona、system prompt 逐字不變 | `brain_cline.POOL` 不動 |
| 3 | 同一個 model id、同一 temperature（0.7）、同一端點、同一 request policy | 同一個 run 的同一組 `ClineBrain` |
| 4 | 取碼器：**turn 1 六臂完全相同**，修訂輪的差異是註冊過的處置（D4） | 初稿輪一律走 `gain_run.extract_code`（一個字不改）⇒ 「H 臂 turn 1 vs OFF」乾淨；修訂輪走 harness 取碼器（第一個 ast-parse 且定義 entry point 的塊，否則 fallback），**兩個選擇逐輪落盤、分歧逐臂計數**。**仍然禁止**「無條件取最後一塊」這類規則，也禁止改 `gain_run.extract_code` 本身（那會動到既有臂） |
| 5 | 同一個沙箱、同一份 import 白名單、同一個 10 s timeout | 全部走 `meets_demand` → `run_python_check` |
| 6 | 同一個接受語意 | `accepted ⟺ 出貨的那份通過 visible`；拒交仍回傳草稿（§4.0.8） |
| 7 | 同一個計分路徑 | dispatch 端的 `meets_demand(hidden)`；**臂內永遠看不到 hidden** |
| 8 | 六條臂交錯在同一個 run | `--arms OFF,CONFORM,OFF5,HPI,HOC,HMIX` |
| 9 | **唯一的差異是 H 臂的 user-turn 文字、迴圈與 context 政策——那就是處理本身** | §3.6 |

### 5.3 指標

**主指標**：**正確交付率** ＝ `accepted ∧ hidden_pass` ／ `measured`
（`measured = processed − infra_void`，`gain_run.finalize` 的 `correct_delivery_rate`）。
SPEC_GAIN §4-2 就是這個。

**必須並報的次指標**（缺一不可，§5.7 說為什麼）：

| 指標 | 定義 | r447 基準（LCB v2） |
|---|---|---|
| 假交付率 | `accepted ∧ ¬hidden` ／ `measured` | OFF 49.2%、CONFORM 24.2%、OFF5 36.7% |
| 接受精度 | `accepted ∧ hidden` ／ `accepted` | OFF 50.8%、CONFORM 74.3%、OFF5 63.3% |
| 拒交率 | `¬accepted` ／ `measured` | OFF 0、CONFORM 5.8%、OFF5 0 |
| 呼叫／題 | `calls / measured` | 1.00 / 1.71 / 5.00 |
| tokens／題 | `Σusage.total_tokens / measured` | 2,691 / 6,101 / 14,102 |
| **tokens／正確交付** | `Σusage.total_tokens / n_acc_ok` | 5,294 / 8,715 / **22,266** |
| 牆鐘／題 | `wall_s / measured` | 34.7 s / 97.1 s / 189.4 s |
| 撞上限率 | `stop_reason ∈ {budget_*, doom}` 的比例 | — |
| 協定失敗率 | `nocode_turns / n_turns`、`loader_refusals / n_turns` | 載入器拒收 25/925 ＝ 2.7% |

#### 5.3.1 歸因分解（D5）：prompt 效果與迴圈效果必須分開報

逐題落盤 `first_pass_turn`（第一次通過可見驗收的輪號；從未通過就是 `null`），
裁決書上**同時**報下面兩個差，缺一不可：

| 量 | 定義 | 它答的問題 | 仲裁欄位 |
|---|---|---|---|
| **Δ(turn1 − OFF)** | 只取 H 臂**第一輪**產出的那份碼，離線走同一條 `meets_demand(hidden)` 重評，與同 run OFF 逐題配對 | **prompt 效果**：光是換一份 user-turn 文字（§4.1–4.3 的差異）值多少 | `attribution.<ARM>.delta_turn1_minus_off_pp` |
| **Δ(final − turn1)** | 同一條 H 臂：最終出貨的那份 vs 它自己第一輪那份，逐題配對 | **迴圈效果**：把執行結果貼回去、讓它改，值多少 | `attribution.<ARM>.delta_final_minus_turn1_pp` |

⚠ **兩者相加不等於 Δ_O**，裁決書只准寫「Δ_O ≈ prompt 效果 ＋ 迴圈效果」，**不准寫成恆等式**：
turn-1 那一份沒有「拒交」概念（無條件計分，形狀與 OFF 相同），最終那一份有 `accepted`，
兩者的分母語意不同。
⚠ turn-1 的碼要靠 `calls.jsonl` 的全文回應離線重取（`--rescore-turn1`），
**用的是與 dispatch 端逐字相同的 `meets_demand(hidden)`**——是事後評分，
臂內仍然看不到 hidden（§5.2 不變量 7）。**零模型呼叫，但要跑沙箱**。
⚠ `first_pass_turn == 1` 的比例事前預期很高（N1：79/120 第一輪就停），
所以 `Δ(final − turn1)` 的**有效樣本**只有其餘約 41 題。
兩個分母都要印：全 120 題一次（`delta_final_minus_turn1_pp`）、
只算 `first_pass_turn != 1` 的題一次（`delta_final_minus_turn1_looponly_pp`）。
只報前者會把迴圈效果稀釋成「看起來很小」，只報後者會把它放大成「看起來很大」。

### 5.4 檢定（D3：顯著性、區間、分母三件事分開定義，各自可執行）

**(1) 配對單位與分母＝complete case。**
配對單位是 `task_id`；成功的定義是 `deliv = accepted ∧ meets_demand`
（R667 凍結口徑，`ops/gain/replay/paired_ci.py:25` 逐字）。
兩臂比較的分母是 **complete-case n**：**兩臂都非 void 的題**，
即 `n_common = |{task_id ∈ rows[A]} ∩ {task_id ∈ rows[B]}|`
（`gain_run` 只在非 void 的格子寫 rows ⇒ 交集就是「兩臂都量到」）。
仲裁欄位 `paired.<A>_vs_<B>.n_common`。
⚠ **不准**用聯集、不准用 `processed`、不准用各臂自己的 `measured`：
H 臂的 void 曝險比 OFF 高 3–5 倍（R7），三個分母在這個 run 上會給出不同答案。
⚠ 每一對比較各自有自己的 `n_common`（H 臂彼此 void 的題不一樣），
所以 `n_common` **必須逐對印出來**，不准只印一個「n=120」。

**(2) 顯著性＝Holm 調整後的精確 McNemar p 值。**
每一對算 `p = mcnemar_exact(b, c)`（`vacant/research.py:141`），
家族是 **3 條 H 臂 × 2 個對照（OFF、CONFORM）＝ 6 個檢定**，
一次性丟進 `vacant/research.py::holm_bonferroni`（α=0.05）。
仲裁欄位：`paired.<A>_vs_<B>.p_mcnemar_exact`（未調整）、
`holm.<A>_vs_<B>.p_adj`（調整後）、`holm.family_size`（必須 == 6）。
⚠ 家族固定是 6，**不准**因為某一臂 void 太多就把它抽掉再重算 Holm
（抽掉會讓剩下的 p 變小 ⇒ 那是看到數字之後改家族）。

**(3) 區間＝未調整的 95% Clopper–Pearson 條件區間。**
用 `ops/gain/replay/paired_ci.py::diff_ci`（`analyze_r447.py` 用的同一支，
n_d 固定、b~Bin(n_d, π)、Clopper–Pearson 取 π 的精確區間、映射
Δ=(2π−1)·n_d/n）。仲裁欄位 `paired.<A>_vs_<B>.ci95_lo_pp` / `ci95_hi_pp`。

> **「Holm 後的 CI」不存在，本文件不准再出現這個詞。**
> 印出來的區間**沒有**做多重比較調整。任何引用它的地方都要逐字附上這一句：
> **「區間未做多重比較調整；仲裁以 analyzer 為準」**。
> 顯著性一律由 (2) 的 `holm.<pair>.p_adj` 決定，區間只用來說「資料還容得下多大的差異」。
> ⚠ 於是會出現一種**事前就知道可能發生**的情形：某一對的
> `ci95_lo_pp > 0`（未調整區間排除 0）但 `p_adj ≥ 0.05`（Holm 後不顯著）。
> 那不是矛盾，是多重比較的代價。**此時以 `p_adj` 為準**，
> 而 §5.6 的 RULED_OUT 判定仍然讀未調整的 `ci95_hi_pp`（D3 逐字）。

**(4) 主要假設指定為 H-MIX vs CONFORM**（H-MIX 是照證據組出來的成品，
H-PI／H-OC 是拆解它的消融）。三條 H 臂各自判自己的裁決，但
**展場口徑只跟著 H-MIX 走**。

**(5) 禁令**：不准把三條 H 臂合併成一個「harness 臂」再檢定；
不准跨 run 合併 n（沿用 R449c §三「不准併成 n=1051 做檢定」的預註冊禁令）；
不准在看到數字之後改分母、改家族、改仲裁欄位。
差異的**方向**、`b`／`c` 逐題清單一律落盤（`ops/gain/analyze_*` 的既有慣例）。

### 5.5 檢定力（`vacant.research.mcnemar_power` 實算，不是估計）

模型：n 對配對、不一致率 `p_disc`、不一致對落在 b 方向的機率 ψ；Δ = p_disc·(2ψ−1)。

| p_disc | Δ | ψ | power @ n=120 | power @ n=189 |
|---|---|---|---|---|
| 0.20 | +5pp | 0.625 | 0.169 | 0.280 |
| 0.20 | **+10pp** | 0.750 | **0.633** | 0.853 |
| 0.20 | +15pp | 0.875 | 0.970 | 0.998 |
| 0.25 | +5pp | 0.600 | 0.143 | 0.236 |
| 0.25 | **+10pp** | 0.700 | **0.525** | 0.761 |
| 0.25 | +15pp | 0.800 | 0.904 | 0.989 |
| 0.325 | +10pp | 0.654 | 0.428 | 0.639 |
| 0.325 | +15pp | 0.731 | 0.801 | 0.951 |

r447 的 CONFORM vs OFF 實測 `b=31, c=8` ⇒ `p_disc = 39/120 = 0.325`。

**誠實結論：n=120 對 +10pp 的檢定力只有 0.43–0.63，剛好在門檻的刀口上。**
所以預註冊**兩階段**：

> **階段一**：LCB v2 120 題（本 run）。裁決落在 **INCONCLUSIVE** ⇒ 觸發**階段二**。
> **INCONCLUSIVE 的定義只有一個地方**，就是 §5.6 的表：
> 「不是 EFFECTIVE、不是 COSTLY_BUT_REAL、也不是 RULED_OUT」的其餘情形
> （典型：未調整的 95% CI 同時跨過 0 與 +10pp）。
> **階段二**：LCB v3 189 題（與 v2 **零交集**，`codebench.py` 逐字；
> run 名 `runs/g_r461h_harness_lcb3`、seed `g-r461-lcb3`）
> 以**相同規格、相同門檻、相同六臂**做確認跑。
> 階段二是**預註冊的確認**不是探索，門檻不得在看到階段一之後修改。

⚠ **初稿在這裡寫的「點估計 ≥ +10pp 但 Holm 後的 CI 下界 ≤ 0」已刪除**，兩個理由：
(a)「Holm 後的 CI」不存在（§5.4-(3)）；
(b) 它與 §5.6 的表不一致——照初稿的寫法，「點估計 < +10pp 而 CI 上界 > +10pp」
這一格會兩邊都沒接住。現在**只有 §5.6 的表定義狀態**，本節只說階段二接在哪一格後面。

### 5.6 預註冊門檻（人類的規則：「可以接受高 token，但差距也要大」）

**符號**（全部是 complete-case 配對量，§5.4-(1)）：
Δ_C ＝ H 臂 − CONFORM 的配對差（pp）；Δ_O ＝ H 臂 − OFF；
`TPC` ＝ tokens per correct delivery；`TPC_OFF5` ＝ **同一個 run 的 OFF5**
（D2：OFF5 不准省跑 ⇒ 這個常數只能來自本 run，見 §5.1）。

| 裁決 | 條件 | 意義 |
|---|---|---|
| **EFFECTIVE** | (i) Δ_O ≥ **+25.0pp** **且** Δ_C ≥ **+10.0pp**（**點估計**）　(ii) 對 OFF 與對 CONFORM **兩個** Holm 調整後 p 值**都** < 0.05　(iii) `TPC ≤ TPC_OFF5`（同 run）　(iv) 假交付率 ≤ CONFORM ＋ 5pp　——**四條全部成立** | 值得裝。可以進展場的候選句 |
| **COSTLY_BUT_REAL** | (ii) 的 **CONFORM 那一半**成立（`holm.<ARM>_vs_CONFORM.p_adj < 0.05`），但 (i)(iii)(iv) 任一條不成立 | 真的有效但不划算／或用假交付換來的。**展場不得宣稱**，只能寫進誠實邊界 |
| **RULED_OUT** | Δ_C 的 **95% CI 上界 < +10.0pp**（未調整區間，§5.4-(3)） | 排除了 ≥10pp 的實務增益。這是**結論**不是失敗（沿用 R445 對 OFF5 的 `RULED_OUT` 用法） |
| **INCONCLUSIVE** | 其餘 | 走 §5.5 的階段二（LCB v3 189 題，規則凍結不變） |

**判定順序（照這個順序判，先命中者為準，事前寫死）**：
EFFECTIVE → COSTLY_BUT_REAL → RULED_OUT → INCONCLUSIVE。
仲裁欄位 `decision.<ARM>.verdict`（analyzer 直接印字串）。

⚠ **winner's curse 免責聲明是強制的**（不寫＝裁決不得結算）：
n=120 對 +10pp 的檢定力只有 0.43–0.63（§5.5），
能被判顯著的點估計本來就會被截斷在 MDE 以上 ⇒
**任何被判 EFFECTIVE 的臂，其點估計是效果量的上偏估計**；
跨 run／跨臂比幅度一律報區間重疊，不報點估計誰大。
逐字句子見 §5.6 末的「必寫句」。

⚠ **Δ_O 門檻為什麼是 +25pp**：CONFORM 對 OFF 在同題庫已經量到 +19.17pp。
一條連 +25pp 都達不到的 H 臂，對 OFF 的優勢還落在「換人重抽」這條便宜路線的量級裡，
那不足以支撐展場那句「把預算花在迴圈上」。這是**事前**訂的，不是看到數字才訂的。

**(iii) 的算術要先攤開來，讓工程師知道靶在哪**（用 r447 的 `TPC_OFF5 = 22,266`
當**事前錨**；實際仲裁用本 run 的同 run 值）：
若某條 H 臂交付 96/120（80.0%，＝Δ_C +10pp），它整條臂的 token 預算上限是
`96 × 22,266 = 2,137,536`，即**每題平均 17,813 tokens**。
H-PI（全留 context、5 輪）在 §4.0.6 的 32k 上限下很可能逼近它；
H-MIX 的 context 紀律就是為這一條設計的。
⇒ 預測 `tokens/task(H-MIX) < tokens/task(H-PI)`，寫進 §5.10 P-H6。

**(iii) 旁邊必須同時印一張 token 倍數表**（D3 逐字要求；缺表＝裁決不得結算）。
analyzer 逐臂印下面五格，**倍數對照 OFF 與 CONFORM 兩個基準都要有**：

| 欄 | 仲裁欄位 | r447 的事前錨（OFF / CONFORM / OFF5） |
|---|---|---|
| tokens／題 | `tokens.<ARM>.tokens_per_task` | 2,691 / 6,101 / 14,102 |
| 對 OFF 的倍數 | `tokens.<ARM>.multiple_vs_off` | 1.00× / 2.27× / 5.24× |
| 對 CONFORM 的倍數 | `tokens.<ARM>.multiple_vs_conform` | 0.44× / 1.00× / 2.31× |
| tokens／正確交付（**含** void 呼叫） | `tokens.<ARM>.tpc_incl_void` | 5,294 / 8,715 / 22,266（r447 void=0 ⇒ 兩版相同） |
| tokens／正確交付（**排除** void 格的呼叫） | `tokens.<ARM>.tpc_excl_void` | 同上 |

⚠ 兩個 TPC 都要印的理由是 R7 的不對稱：void 格的呼叫已經燒掉 token 但不進分母
⇒ 只報 `tpc_excl_void` 會**低估** H 臂的成本。**(iii) 的仲裁用 `tpc_incl_void`**
（較嚴的那個），另一個並列印出。

**推翻條件（寫進 DECISION，事後不得補）**：

> 若三條 H 臂全部落 `RULED_OUT`，則本 repo 對外的說法要改成：
> **「在 12B worker ＋ 可執行驗收測資的設定下，把 5 通呼叫花在修訂迴圈，
> 不比花在換人重抽（CONFORM，1.71 通）更好。」**
> 這句話要進 `examples/verdicts.py` 當一條 refuted 裁決，與
> `gain.equal_budget_on_beats_off5` 並列。

### 5.7 必須並報的守門指標（缺任何一項，裁決不得結算）

**G1 假交付。** 迴圈是**朝著可見測資**改的，過擬合風險結構性地高於隨機抽樣。
N1／N2 已經顯示 CONFORM 把可見通過 +34 換成 hidden 通過 +23、假交付從 18 漲到 29。
⇒ 門檻 ④ 就是這條的硬約束。並報「可見通過但 hidden 錯」的**絕對件數**（SPEC_GAIN §4-5）。

**G2 拒交與無損性。** 逐題重放拒交的題目，檢查「最後那份草稿是不是真的錯」
（r447／r449b／r449c／r461 都做過，全部 N/N 全錯）。H 臂多了一個新的拒交理由
（`doom`／`budget_*`），要分開列。

**G3 載入器拒收的分層讀數（N3 的直接後果）。** 必須同時報兩個版本的主指標：

- **ITT（主）**：全部 120 題。
- **artifact-excluded（必報次要）**：排除「**OFF 臂的那一份草稿被載入器拒收**」的題目
  （r447 上是 7 題；本 run 重算）。

若 H 臂的優勢在排除後掉超過一半，裁決書必須逐字寫：
**「這條臂買到的主要是我們自己的禁用屬性表太嚴（`_FORBIDDEN_ATTRS` 含 `remove`），
不是產出變好。」**

**G4 難度與日期分層。** 72 medium / 48 hard 分開報；`lcb_3026`（2023-08-26）單獨列。

**G5 每題呼叫數逐題落盤，不只報平均。** SPEC_GAIN §3 逐字：
「呼叫數要逐題記錄並報出來，不能只報平均」（E19 的 whitewash 29/30 vs patient 1/30 前例）。
H 臂的呼叫分佈預期是雙峰（79 題 1 通、41 題 2–5 通），只報平均會完全看不出來。

**G6 `harness_wire_mode`**（§4.0.2）。多輪與攤平兩種模式的結果不得混算。

### 5.8 V/GT 洩漏的稽核鉤子

**⚠ D7（本 repo 第一次）：可見測資的內容會進 worker prompt。**
H 臂的回饋訊息裡有 `args=[…] got=… want=…`——那三個欄位全部來自
`visible_tests`，是**客戶自己交出來的驗收測資**（§3.3）。
既有的 OFF／CONFORM／OFF5 只把題目敘述送進 prompt，
**從來沒有把可見測資的 args／expected 逐字送進去過；H 臂是第一次。**

這件事**是設計要的、不是漏洞**：整條 harness 路線的機制就是「把執行結果貼回去」，
而執行結果的內容就是可見測資的內容。V/GT 分離（SPEC_GAIN §2）分的是
`visible` 與 `hidden`，**可見的部分本來就允許給模型看**。

但它有三個必須同時做到的後果，缺一不可：

1. **稽核對象因此是 `hidden_tests \ visible_tests`，不是「所有測資」。**
   下面的動態稽核只斷言「hidden 扣掉 visible 的那些 case 沒有出現在送出的文字裡」——
   斷言「visible 沒出現」會**必然失敗**，因為它按設計就在裡面。
   `ops/gain/harness_vgt_audit.py` 的 docstring 必須逐字寫明這一點。
2. **展場文案必須講。** 口徑：「這條臂會把**客戶自己寫的驗收測資**的失敗訊息原文貼回去給模型改」
   ——不准只說「把錯誤貼回去」讓人以為模型是憑空修對的。
   §6-R9 的必講清單加這一條。
3. **這件事本身是 R4（過擬合可見測資）的機制來源。** 模型看得到 2–4 條可見測資的
   args 與期望值 ⇒ 「改到通過」與「寫對」的距離比 OFF 更大，
   所以 §5.6 的 (iv) 假交付門檻與 §5.7-G1 是**這條設計的配套**，不是附加的保險。

**靜態（跑在 CI 與 pre-commit）**：

1. `ops/gain/harness_arms.py` 全文**不得出現** `hidden_check`、`canonical`、`__canon`、`plus`。
   一行 grep 斷言，放進 `tests/test_gain_harness_arms.py::T6`。
2. `harness_arms` 不得 import `_canonical_solutions`、不得 import `vacant.suitegauge`。

**動態（`ops/gain/harness_vgt_audit.py`，run 之後跑，零模型呼叫）**：

對 `calls.jsonl` 裡每一筆 `meta.arm ∈ {HPI,HOC,HMIX}` 的紀錄，取它送出的**全部** messages 文字，斷言：

1. 不含子字串 `__canon`、`exec(`、`__aeq`、`__tests`
   （⇒ `visible_check` 的**原始碼**從來沒有被送給模型；只有 `str(exc)` 被轉發）。
2. 對該題的 `hidden_tests \ visible_tests`（LCB 直接有這兩個 list），
   每一個 case 的 `repr(args)` 與 `repr(expected)` 都**不出現**在任何送出的文字裡。
3. 對 MBPP+ 的複製跑：另外斷言不含 `plus_input` 的任何 `repr`。

任何一條命中 ⇒ **整個 run 作廢**，照 SPEC_GAIN §7 落盤並公開，不得只修不報。

⚠ 這個稽核**必須跑在 rows/calls 上，不能只讀原始碼**——
「程式碼裡沒有 import hidden_check」不能證明「沒有 GT 進 prompt」
（例如未來有人把 `conform_failure_detail` 的輸出擴充成帶期望值）。

### 5.9 機時預算與分塊

用 r447 的實測外推（N4；H 臂假設平均 3.3 通／題、每通與 OFF 同量級的 34.7 s）：

| 臂 | 預估牆鐘 |
|---|---|
| OFF | 1.2 h（實測 4,165 s） |
| CONFORM | 3.2 h（實測 11,654 s） |
| OFF5 | 6.3 h（實測 22,726 s） |
| H-PI／H-OC／H-MIX | 各約 3.8 h |
| **合計（六臂交錯）** | **≈ 22 h** |

⚠ `gain_run` **沒有續跑**（輸出目錄有產物就 `SystemExit` 拒絕 append，
`gain_run.py:1292-1301`）。中斷一次那一塊就得從頭。

**D9 已經裁定用切塊，而且理由不是「機時不穩」而是「機時拓撲」**：
2026-09-07 15:40 量到 8765 那顆 hub 把 **100% 的請求路由到後端 1003**
（6 次探針：1003 +6、1004 +0），而且併發打 hub 吞吐**退化**
（n=8→12：206→175→144 tok/s）；兩顆直連後端各自在 n=4 熱身後約 **110–120 tok/s**。
⇒ 走 hub 只用得到一張卡。所以照 R445 的先例切成
`--offset 0 --n 60`（→ `100.119.113.56:1234`）與 `--offset 60 --n 60`
（→ `100.86.226.21:1234`）兩個 run、**同時跑**、收官按 `task_id` 併庫。
牆鐘從 ≈22 h 降到 ≈11 h，而**每一顆卡上仍然是一次一個請求**
（`DECISION_20260824_SERIALIZE_CONCURRENT_CALLS.md` 擋的是同端點併發，這裡沒有做）。

⚠ **代價逐條登記**（全部在 `DECISION_20260907_R460_HARNESS_PREREG.md` §二-5）：
第二塊的 `random.Random(f"{seed}:{arm}")` 從頭開始 ⇒
**persona 指派不再與 r447 對齊** ⇒ §5.1 的 P-H0 後端探針**只在 block a 有效**；
兩塊的難度組成不同（block a medium 40／hard 20、block b 32／28）⇒
**塊間點估計不得互相比較**；多一組合併擋門（塊間 task_id 交集、走 hub、
兩塊同端點、只跑完一塊）全部進 `analyze_r460.topology_report()` 的 `broken_reasons`。

### 5.10 預註冊預測（DECISION 檔要逐條寫上，跑完逐條記 HIT／MISS）

| # | 預測 | 窗 | 為什麼這樣猜 |
|---|---|---|---|
| P-H0 | 新 OFF 的交付率（**只在 block a 上判**） | [38.3, 68.3]% | 錨＝r447 前 60 題的 32/60 ＝ 53.33%；窗 ±15pp（n=60）；後端漂移探針（§5.1）。block b 的 persona 指派與 r447 不對齊 ⇒ 不判 |
| P-H1 | 三條 H 臂都 > OFF | Δ_O > 0 | N1：41 題有修理空間，且那 41 題 hidden 全錯 ⇒ 只會往上 |
| P-H2 | 至少一條 H 臂 > CONFORM | Δ_C > 0 | §2.1：修訂可越過池子天花板，選擇不行 |
| P-H3 | H 臂的實際呼叫／題 | [1.8, 3.2] | N1：79/120 題第一輪就停（＝1.0 通），41 題會用到 2–5 通 |
| P-H4 | H 臂的假交付率 | 高於 CONFORM 的 24.2%，但 ≤ 35% | 迴圈朝可見測資修 ⇒ 過擬合升高；CONFORM 已示範 +34 可見換 +23 hidden |
| P-H5 | 載入器拒收在 H 臂**降到接近 0** | ≤ 0.5% 的輪次以 `loader` 收工 | 靜態診斷會把 reason 直接告訴模型（僅 H-OC／H-MIX；H-PI 沒有診斷 ⇒ 預期仍在 2% 上下） |
| P-H6 | `tokens/task(H-MIX) < tokens/task(H-PI)` | 差距 ≥ 20% | §4.3 的 context 紀律就是為這條設計的 |
| P-H7 | `stop_reason` 分佈 | `visible_pass` 為主；`budget_wall` ≤ 5% | 900 s ＝ 我們自己實測的單次 max 504.9 s 的 **1.78 倍**，而一題只有一個函式（不是無上限的 shell 任務）⇒ 要撞線得比歷史最壞再慢 78%。**外部的 timeout 比例已依 D6 刪除，不再當錨** |
| P-H8 | 協定：`nocode` 輪次比例 | ≤ 3% | N5：925/925 都有圍欄 |
| P-H9 | **條件性後續**：若 H-OC 與 H-MIX 都顯著贏 H-PI | ⇒ 追加第四條臂 H-PI＋診斷，否則計畫輪的效果不可辨識（§4.4） | — |

---

## 六、風險

**R1 12B 的協定遵循。** 已量到的好消息：925/925 都有圍欄（N5）。壞消息：19.4% 有多塊、
`extract_code` 取第一塊。迴圈會**放大**這個風險（「先解釋、再貼碼、再貼用法」）。
處置：逐輪記 `n_code_blocks`（§4.0.9）、`nocode`（＝零圍欄）走跟工具錯誤同一條路（F3）
並計數、`first_block_non_python` 單獨計數，
**不改 `gain_run.extract_code`**（不變量 4；修訂輪的 harness 取碼器是註冊過的處置，
見 §4.0.3 的 D4，其分歧數逐臂落盤，事後扣得掉）。若 P-H8 大幅 MISS，那本身就是一個結論
（「12B 撐不住多輪協定」），不是要偷偷修掉的 bug。

**R2 prompt 格式脆弱（H-OC 尤其）。** `PLAN:／EDGE CASES:／SELFTEST:` 三段式對 12B 是
考驗；`SELFTEST` 還要吐兩個 Python literal。既有證據不樂觀：R518 量到反例精確度上界 <0.80、
R438/R516 量到評審票近乎常數函數，而那個協定（`REVIEWER_SYSTEM` 的 `TEST_ARGS`／`EXPECTED`）
比這個還簡單。處置：解析失敗**不重問**（省呼叫）、只計數；
`selftests_parsed` 是 H-OC 的一個一級指標——**若它接近 0，H-OC 就退化成「多花一通講廢話」**，
裁決書要照這樣寫，不准把它讀成「計畫沒用」。

**R3 逾時與長尾。** 單次呼叫 max 504.9 s（N4）。5 通最壞 ≈ 42 分鐘／題。
`max_wall_s=900` 會擋住，但擋住的那些題會變成拒交 ⇒ 拉低交付率。
⚠ **這是一個真實的不公平風險**：OFF 只有 1 通，永遠不會撞牆鐘。
處置：`budget_wall` 單獨計數並在裁決書單獨一行；
若 `budget_wall` > 5%（P-H7 MISS），必須做敏感度分析
（把撞牆鐘的題當 missing 重算一次，兩個數字都報）。

**R4 過擬合可見測資（最重要的一條）。** LCB v2 每題只有 **2–4 條**可見測資
（分佈：2 條 59 題、3 條 52 題、4 條 9 題）。
「反覆改到 2 條測資通過」與「寫對」的距離比 MBPP+ 大。
N2 已經給了 CONFORM 的轉換率 67.6% 當對照。處置：§5.6 門檻 ④ ＋ §5.7-G1。
⚠ 若 H 臂交付率上升而**假交付絕對件數也上升**，展場一個字都不准講。

**R5 迴圈失控。** doom 只有 H-MIX 有；H-PI／H-OC 靠 `max_calls=5` 硬擋。
5 通不算長，失控的空間有限——但**成本失控**是另一回事：
全留 context 的 H-PI 在第 5 輪的 prompt 會含前 4 輪的全部回應（p90 completion 5,681 tokens
⇒ 第 5 輪 prompt 可能 20k+）。`max_tokens=32_000` 就是這條線。

**R6 汙染（LCB 日期）。** LCB v2 視窗 2023-08-26 → 2025-04-05，`lcb_3026` 是離群值
（§5.1）。迴圈臂**不會**改變汙染的性質（同一批題目、同一個模型），
但**會**改變它的表現方式：若模型「記得」某題的解，多給幾輪只會讓它更快收斂到記得的答案。
⇒ 分層報（§5.7-G4），而且對外一律用 `docs/…RESULTS…`§5.2 的口徑，不宣稱「未汙染」。

**R7 `infra_void`。** 現行規則不變：`InfraVoid` 往外拋、該格不進分母（§4.0.7）。
⚠ **H 臂的 void 曝險比 OFF 高 3–5 倍**（每題最多 5 次呼叫，任何一次重試用盡都會 void 掉整格，
包含前面已經成功的幾輪）。r447 的 void 是 0，但 `g_off60_relay_20260824` 曾經 30%。
處置：(a) `--retries 4` 不變；(b) 若某臂 void 率 > 10%（SPEC 的既有擋門），
**該臂的比例不得拿去比較**；(c) 逐格 void 的 `turn` 位置要落盤
（第 1 輪就 void vs 第 5 輪才 void 是不同的故事）。
⚠ 已知的不對稱：H 臂在第 4 輪 void 時，前 3 通呼叫已經進了 `calls.jsonl` 的成本，
但該格不進分母 ⇒ **tokens／題會被低估**。裁決書要同時報「含 void 呼叫的總 token」與
「除以 measured 的 token」，不可只報後者。

**R8 什麼會讓比較不公平（總表）**：

| 來源 | 方向 | 處置 |
|---|---|---|
| 載入器拒收（N3） | **利 H**（診斷免費修掉 5.8%） | §5.7-G3 分層並報；不改 `_FORBIDDEN_ATTRS` |
| 牆鐘上限（R3） | **不利 H**（OFF 永遠不撞） | `budget_wall` 單獨報＋敏感度分析 |
| 後端漂移（§5.1） | 未知 | 六臂交錯同 run ＋ P-H0 探針 |
| `max_tokens` 只設給 H | **不利 H** | **不設**（§4.0.6 ⚠） |
| 為 H 改**共用**取碼器 | 利 H | 禁止（不變量 4）。D4 的 harness 取碼器只作用在修訂輪、turn 1 與 OFF 同一件，且分歧逐輪落盤 ⇒ 事後扣得掉 |
| H 用不同 persona 策略 | 利 H | 一題一 worker，只抽一次（§4.0.5） |
| void 不進分母（R7） | 利 H（token 低估） | 兩個 token 數字都報 |
| 多輪 vs 攤平 wire mode | 未知 | §5.7-G6，不得混算 |

**R9 展場口徑。** 就算 EFFECTIVE，能講的也只有：
「在 120 題 LeetCode 中高難度題上、用一顆 12B 本地模型、把五通呼叫花在
『跑客戶的驗收測資、把失敗原文貼回去、讓它改』，比花在換人重抽多交付 N 個百分點。」
**必須**同時講：「回饋的內容是**客戶自己交出來的驗收測資**的失敗原文
（`args=… got=… want=…`），模型看得到那幾條測資的輸入與期望值」（D7）。
**不准**講「業界證明 harness 才是關鍵」（T2）、
**不准**講「我們的 agent 會自我驗證」（我們量的是 harness 強迫它看執行結果，不是它自覺）、
**不准**省略「需求可以被編譯成可執行驗收測資」那句強制前提（§1.1 的口徑紅線）。

---

## 附錄 A：本文所有新數字的重算指令（零模型呼叫）

N1／N4 的交叉表與 token 分佈：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant
.venv/bin/python - <<'PY'
import json, collections
rows = [json.loads(l) for l in open('runs/g_r447_conform_lcb2/rows.jsonl')]
by = collections.defaultdict(list)
for r in rows: by[r['arm']].append(r)
for arm, rs in by.items():
    print(arm, 'n', len(rs),
          'visible_ok', sum(1 for r in rs if r.get('visible_ok')),
          'hidden_ok', sum(1 for r in rs if r['meets_demand']),
          'vis&~hid', sum(1 for r in rs if r.get('visible_ok') and not r['meets_demand']),
          'hid&~vis', sum(1 for r in rs if r['meets_demand'] and not r.get('visible_ok')))
agg = collections.defaultdict(lambda: [0, 0])
for line in open('runs/g_r447_conform_lcb2/calls.jsonl'):
    r = json.loads(line)
    if not r.get('ok'): continue
    a = (r.get('meta') or {}).get('arm') or r.get('role')
    u = r.get('usage') or {}
    agg[a][0] += 1; agg[a][1] += u.get('total_tokens') or 0
for k, v in agg.items(): print(k, 'calls', v[0], 'tokens', v[1])
PY
```

N3（載入器拒收）需要 §3.1 的 `static_precheck` 與 `vacant.checks._candidate_functions`
逐份比對；N5（圍欄區塊數）只要數 `response` 裡三個反引號的出現次數除以 2。
兩者的完整腳本在本輪的 scratchpad
（`/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/{precheck,fences}.py`），
**那是暫存目錄，會消失**——實作 `ops/gain/harness_arms.py` 時把 `static_precheck`
落進 repo，這兩個數字就永久可重算。

## 附錄 B：待人類／Fable 裁決的四件事

1. **`max_calls = 5` 還是 6。** 本文選 5（等預算，SPEC_GAIN §3 的分水嶺）。
   選 6 的話 H 臂會比 OFF5 多一通，等預算的宣稱就沒了。
2. **要不要省掉 OFF5 的重跑**（省 6.3 h，代價是 token 門檻改綁歸檔常數，§5.1）。
3. **`_FORBIDDEN_ATTRS` 含 `remove` 這個量具偏誤要不要另開修**（N3）。
   本文的立場：**本實驗內不修**，另開 DECISION；但修不修會改變 §5.7-G3 的讀法。
4. **階段二（LCB v3 189 題）的機時要不要先預留**（§5.5）。
   n=120 對 +10pp 的檢定力只有 0.43–0.63，不預留的話 INCONCLUSIVE 會卡住。
