# 可究責追緝——2026-09-24 的證據（L-fake）

> **證據等級：L-fake。** 模型是照劇本回答的假上游（`ops/intake/mock_model.py`），沒有真模型、
> 沒有 API 金鑰。這裡證明的是**機制**在四個真 agent 的真掛鉤、真工具迴圈上接得起來，且歸因規則在
> 乾淨的埋錯下給出期望的答案。**不證明**真模型下產出會更接近需求——那是
> `decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md` 的事（草稿，待人類簽字）。

## 1. 四個真 agent × 八個埋錯情境＋Claude 的背景子 agent（`e2e_trace_SUMMARY.md`、`e2e_trace_results.json`）

> 第 1–3 節的三張表都在 `b23046a5`（最後一輪對抗審查——重置輪數與 TUI 量測——修正之後）上重跑，2026-09-25 01:40–02:09 UTC、依序跑、中間沒有改碼。假模型收到帶著非假金鑰的請求：三張表合計 0。
> 之後的 `contract quick`、HTTP 定位與它們的審查修正改到了定位器與回饋措辭；三張表在 `93308330` 上又確認重跑一次（03:37–04:05 UTC）：33/33、25/25、16/16，回饋到模型、改好後收下、鏈、行動者識別、非假金鑰請求的數字都和上面一樣。存的結果檔仍是 `b23046a5` 那一跑。

重跑：

    python ops/accountability/e2e_trace.py --bin <pi/opencode/codex 所在目錄> --out <dir>

| 量什麼 | 結果 |
|---|---|
| 歸因正確（狀態／類別／等級／指到的步驟／來源都對） | **33/33** |
| B（agent 憑空寫錯）⇒ `provable`，指到寫報告那一步；重跑前那個位置沒有這個值、之後不過且有 | 4/4 |
| A（輸入本來就錯）⇒ `input`／`lineage_exact`，來源＝`inputs/summary.txt`；agent 沒被記過錯 | 4/4 |
| C（腳本錯）⇒ `lineage_internal`，指到**寫腳本**的那一步（不是寫報告那一步） | 4/4 |
| D（agent 走了之後有人在外面改檔；負控制）⇒ `UNOBSERVED`／`gap`；沒有任何行動者被記 | 4/4 |
| F（網頁本身就錯：`curl http://portal.vacant-lab.test/…` 抓回來的頁面寫著 58、照抄；實驗環境用 `http_proxy` 把這個名字接到假模型）⇒ `input`／`lineage_exact`，來源是那個網址；agent 不背；網址記進來源帳 | 4/4 |
| I（**平行委派**兩個子 agent：A 把列數寫進 `count.txt`、B 把 96 寫進 `figure.txt`；主 agent 兩個都讀、照抄）⇒ 指到 **B** 寫 `figure.txt` 的那一步（不怪 A）。跑的時候發現：先收尾的委派呼叫會把兄弟子 agent 還沒收尾的寫入掃進自己的差異——修了（委派呼叫自己不寫檔；同一個版本歸真正寫它的那一步） | 4/4 |
| H（**人標記**了契約檢查不到的錯：第一跑總數對、「Region: South」錯 ⇒ 收件 accept；人下 `vacant flag report.md:4 "the region is North, not South"`；第二跑是新的工作階段）⇒ 回合結束時把標記回饋給 agent（契約過了也照樣）、追緝指到第一跑寫下那一行的那一步、改好之後標記解決 | 4/4 |
| G（只有 Claude Code：子 agent 在**背景**跑——Claude 的預設；主 agent 從 `<task-notification>` 照抄）⇒ 同 E，指到子 agent；子 agent 還在做時回合結束的驗收**先不跑**（不催主 agent 重做） | 1/1 |
| E（子 agent 算錯寫進 `figure.txt`、主 agent 照抄）⇒ `agent`／`lineage_internal`，指到**子 agent** 寫 `figure.txt` 的那一步，行動者帶子 agent 的 id（Claude `general-purpose`、Codex `default`、pi `worker`、OpenCode `subagent`） | 4/4 |
| 有位置的回饋出現在下一次模型請求裡 | Claude Code、Codex、pi：**是**（A／B／C／E／F／H／I＋Claude 的 G，22 格）；OpenCode `run`：**否**（既有邊界：`run` 在第一個 idle 就結束；OpenCode 的互動 TUI 與 `vacant do` **有**，見第 3、2 節） |
| 給 agent 的回饋裡有行動者識別 | 0/33 |
| 改好之後，病歷記「已解決」、收件 accept | Claude／Codex／pi 的 A／B／C／E／F／H／I＋Claude 的 G：22/22 |
| 病歷簽章鏈驗得過 | 33/33 |
| 每次掛鉤的額外時間 p95 | 6.3–13.3 ms（小工作區；大專案見第 5 節）。之前的一跑裡 Codex 的 H 那一格有一次 59 ms（那一格只有 13 次掛鉤，p95 就是最慢那一次） |
| 行動者帳本 | 每個 agent 一格（6 跑）；B 記 1 筆可證明的錯；A 記在來源 `inputs/summary.txt`、F 記在那個網址；D 記在該平台的整合覆蓋率；E 是推論層（`lineage_internal`），照規則不進信譽 |

模型實際收到的回饋（Claude Code，情境 B，第 2 次請求）：

```
The task contract's checks do not pass yet (this is feedback from `vacant check`, not a final decision):
- total: FAIL — report.md:3 says "999"
  expected 69 (column 'amount', 3 rows)
  this value first appeared at step 2 (Bash)
Run `vacant check` to re-check before finishing.
```

## 2. 同樣的情境走 `vacant do`（R536 的路；`e2e_trace_via_do_SUMMARY.md`、`e2e_trace_via_do_results.json`）

重跑：

    python ops/accountability/e2e_trace.py --bin <pi/opencode/codex 所在目錄> --out <dir> --via-do

`vacant do <agent> --attempts 2 --feedback-mode localized`：隔離的工作區、行程結束後驗收與追緝、回饋接在**下一次嘗試**
的提示後面（預註冊 R536 的 RL 臂就是這條）。D、H 不跑（要在 agent 跑完之後去動原本的專案，`vacant do` 不在那裡跑）。

| 量什麼 | 結果 |
|---|---|
| 歸因正確 | **25/25**（四個 agent × A／B／C／E／F／I＋Claude 的 G） |
| 有位置的回饋出現在下一次嘗試的模型請求裡 | **25/25——OpenCode 也是**（`vacant do` 自己在行程結束後驗收、重開一次，不靠 `opencode run` 沒有的回合邊界） |
| 改好之後病歷記「已解決」、收件 accept | 25/25 |
| 給 agent 的回饋裡有行動者識別 | 0/25 |
| 病歷簽章鏈驗得過 | 25/25 |

第一跑（00:26 UTC，`6d5184a6`）是 22/25：三格是 harness 沒把原生那條的 agent 參數帶進 `vacant do`（pi 的 subagent 擴充、
Codex 的網路），修了之後整張重跑 25/25；這一份是在 `b23046a5` 上再重跑的。

## 3. 人直接開 agent 的互動介面（`e2e_tui_SUMMARY.md`、`e2e_tui_results.json`、`tui_screens/`）

重跑（要 tmux）：

    python ops/accountability/e2e_tui.py --bin <pi/opencode/codex 所在目錄> --out <dir>

人類定的場景是「人直接用一個 agent」——多半就是開它的互動介面打字。這一節把埋錯放進四個 agent 的**真 TUI**
（tmux 的偽終端機：等畫面出現就緒的字樣、打提示、按 Enter、做完之後下離開的指令 `/exit`／`/quit`／Ctrl-D）。
`tui_screens/` 是每一格結束時畫面上的文字（tmux 抓的，不是截圖；OpenCode 是全螢幕介面，只抓得到最後一屏）。

| 量什麼 | 結果 |
|---|---|
| 歸因正確（B／A／C＋多回合 M） | **16/16** |
| 寫錯的那一回合，指到**這一格結論那個值**的回饋（`… says "999"`）出現在模型的下一次請求裡 | **16/16**——**OpenCode 的互動 TUI 也有**（外掛在 idle 時用 SDK 送回；之前寫了但沒量過）。`opencode run` 仍然沒有 |
| 同一段回饋出現在人的畫面上 | 16/16（Claude Code 標成「Stop hook error」——它自己的字樣，模型收到的是「Stop hook feedback」；Codex「Blocked by hook」；pi `[vacant-check]`；OpenCode 是一則使用者訊息） |
| **這一個**結論（`finding_id`）被解決、收件 accept | 16/16 |
| 給 agent 的回饋裡有行動者識別（任何一則） | 0/16 |
| 病歷裡的「人說的」提示 | 單回合 1 則、多回合 2 則，四個 agent 都是（OpenCode 從這一輪起也記得到：外掛聽 `chat.message`）；不是人打的被記成人說的：0 |
| 多回合那幾格，前面的回合**真的用完了**輪數（否則最後一回合的回饋證明不了重置） | 4/4（harness 讀掛鉤紀錄確認；沒用完那一格判不過） |
| 假模型收到帶著非假金鑰的請求 | 0——只說得出送到假模型的模型請求；Claude Code 在隔離的 HOME 裡仍提示它看得到主機的另一種憑證，它拿那個做什麼這裡量不到 |
| 病歷簽章鏈驗得過 | 16/16 |
| 每次掛鉤的額外時間 p95 | 6.7–12.6 ms；OpenCode 的 A 那一格有一次 59 ms（12 次掛鉤，p95 就是最慢那一次；p50 4.7 ms） |

**多回合（M）與它抓到的問題。** 人先問「帳本有幾列？先不要寫檔」——agent 回答了，回合結束時契約還沒過（報告還沒有）
⇒ 回饋；agent 回「好，等你說」⇒ 輪數（這個情境的上限是 1 輪）用完，人看到「輪數用完」。之後人才說「現在寫報告」，
agent 寫了 999。原本的規則是**輪數只在過了才歸零** ⇒ 這一回合 agent 收不到位置。
負控制（把重置拿掉）：Claude Code（`f90da052`、上限 2 輪；`tui_screens/claude_M_multi_turn_NEGATIVE_CONTROL.txt`、
`e2e_tui_negative_control_claude_results.json`）與 OpenCode（`b23046a5` 的工作樹、上限 1 輪；
`tui_screens/opencode_M_multi_turn_NEGATIVE_CONTROL.txt`、`e2e_tui_negative_control_opencode_results.json`）都是：
最後一回合沒有回饋、只有人看到「輪數用完…report.md:3 = 999」、最後 **reject**。
修（`hookpolicy.new_request`）：**人打的新要求重新算輪數**。不是人打的不算，也不當成值的來源——背景子 agent 的結果、
父 agent 給子 agent 的任務、Vacant 自己的回饋被送回來（只認開頭）、agent 自己排的提示（Claude Code 的 CronCreate／
ScheduleWakeup）、別的工作階段的信封（`capture.classify_prompt`；審查 `ops/accountability/review_rounds_tui/FINDINGS.md`）。
第一次存的這份證據（`9ceeb052`）有一格說了它沒證明的事：OpenCode 的 M 過了，但前面的回合沒用完輪數、根本沒測到重置——
審查抓到，現在上限 1 輪並由 harness 檢查。

## 4. R536 的管線冒煙（`r536_mock_smoke_*.json*`）

2 題 × 3 臂，Claude Code 對假模型：RS（重抽、無回饋）3 次都錯；RF、RL 第 2 次改對。2026-09-25 在最後的程式碼上重跑
（同樣的結果）時抓到一個回歸：`vacant do` 的工作區都在工作區根底下，而審查修正（recorder#11）把整個根當成狀態目錄不追
⇒ `vacant do` 一步都沒記、追緝只剩「缺口」。修了（根本身不追、根底下的工作區照追），重跑後三臂都追到「第 2 步」。
四個 agent 的端到端走掛鉤，沒有經過 `vacant do`，所以沒抓到——這一份冒煙是 `vacant do` 那條路的檢查。
**只證明管線接得起來**（假模型看到回饋開頭就照劇本改對），任何效果數字都不能從這裡來。

## 5. 大專案的掛鉤時間（`perf/`）

重跑：

    python ops/accountability/perf_scan.py --out <dir> --sizes 100,1000,10000,40000,60000 --steps 10

真的掛鉤進入點（`python -m vacant_network hook claude …`，含行程啟動，約 130 ms）。每個大小：第一次 Pre（冷）→
10 對 Pre／Post（每一步改一個檔）→ Stop（驗收＋追緝＋在重建的前後狀態上重跑；第 1 步埋了 `999`）。
`perf.md` 是表，`perf.json` 是原始數字，`stop_40000.json`／`stop_60000.json` 是 agent 收到的回饋原文，
`machine.txt` 是機器。

| 量什麼 | 結果 |
|---|---|
| 4 萬檔：第一次 Pre／之後每次 p95／Stop | 5.7 s／597 ms／1.9 s（都在 30 秒上限內；改之前第一次 Pre 是 33.8 s；同一支腳本三次量測的第一次 Pre 是 5.7–8.2 s） |
| 1 萬檔：同上 | 3.1 s／325 ms／0.56 s |
| 每一步多存多少（1000 檔以上） | 0.9 KB（差異索引；改之前 4 萬檔每一步 4.9 MB） |
| 6 萬檔（超過 5 萬檔上限） | 第一次看改到背景、背景看不完 ⇒ 關掉逐步掃描；之後每次掛鉤 p95 227 ms；Stop 的回饋仍有 `report.md:2 says "999"`，但沒有「第一次出現在第幾步」 |
| 一個 12 GiB 的檔（審查 #5 的重現） | 第一次 Pre 8.2 秒改到背景，之後每次 0.14 秒（改之前每一次都被 30 秒上限砍掉、什麼都沒記） |

這一節的表是**對抗審查修正之後**重跑的（`ops/accountability/review_scale/FINDINGS.md`：8 條全部成立、全部修掉）。

誠實邊界：檔案都很小（大檔的雜湊另計）；本機磁碟、快取是熱的，網路檔案系統會更慢；4 萬檔的第一次掃描貼著
8 秒的時限，換一台慢一點的機器就會改到背景（那段時間的步驟記成「沒觀察到」）。只量 Claude Code 格式的掛鉤
（四個平台走同一個 `hook.handle`）。

## 6. 沒有做到的（照實寫）

- 子 agent：Codex 的 multi-agent v2 沒有端到端跑（有 `ops/accountability/capture/` 的可觀測面實測）。
  平行委派（情境 I）是兩個子 agent 寫**不同**的檔；兩個子 agent 同時寫**同一個**檔時只能說「是其中之一」。
- pi 的子 agent 靠 Vacant 的 pi 擴充在工具呼叫期間放進環境的標記認出來：平行的工具呼叫下，標記可能指到兄弟呼叫
  （工作階段仍然對）；不是 pi 擴充啟動的 pi 行程（例如使用者自己在另一個終端機開的）不會被當成子 agent。
- Claude Code 的掛鉤不帶模型 id ⇒ 信譽格的 substrate 是 `unknown`（逐字稿裡有自稱的模型，封存了，
  但沒拿來當鍵）。
