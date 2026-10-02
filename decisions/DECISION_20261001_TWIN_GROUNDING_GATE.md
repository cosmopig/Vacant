# DECISION 2026-10-01 — 分身交件過「有沒有根據」的閘門（Vacant 側，P7）

分支 `feat/twin-world`。程式：`ops/exhibit/twin/grounding_gate.py`（四格窗）、`world/build_facts.py`＋`world/materials/_facts.json`
（窗 3 的事實表）、`twin_agent.sh`／`twinagent.py`（接 `launcher.run` 的閘門與重改）、`live_events.py`／`tv_contract.py`／`sidecar.py`
（電視事件）、`gate_samples.py`（真跑覆蓋）。證據：`ops/exhibit/twin/evidence_gate_20261001/`。測試：`tests/test_twin_grounding_gate_20261001.py`。

## 一、人類原話，與為什麼四格窗不是「審查規則」

> 「確保他可以正確的被觸發」「在正確的 vacant 邏輯上」「如果後續有用到那個內容，他就可以有正確觸發」「vacant 不應該有審查規則」

分身那一條路在這之前走 `allow_no_suite=True`：整條路上沒有任何會退回、會重來的邏輯，所以「被退回／發現錯誤／重來」一個都不會發生。
要讓它們**真的**發生，又不違反「Vacant 不審查」，做法是讓每一位分身交件時都過**同一道**閘門，而且那道閘門只問一件事：
**成品裡的每一句話、每一個數字，在這一跑的紀錄裡找不找得到根據**。

為什麼這不是審查規則：

1. **所有分身同一套**：四格窗不看是誰、不看他的特質、不看他決定做什麼；窗的內容由世界（地上的東西、帳本鏈）決定，不由某個人的口味決定。
2. **只查根據的有無，不查好壞**：沒有一格問「做得好不好」「有沒有趣」「合不合那個人」。全部有根據 ≠ 做對。
3. **對齊產品原則 2**（「咎責只要確認每一步是否都是合理」）與零設定的 `unread`（點名的檔沒打開）／`unsourced`（沒出處的值）／
   `test_claim`（說測過但紀錄對不上）——同一個精神，用 main 現成的 `launcher.run(suite_dir=…, retry_arm="revise", feedback_into="both")`
   執行，**不是另寫一個裁判**，`vacant_network/vrun/*` 一個字沒動。
4. 失敗訊息只寫**位置與缺的根據**，不寫對錯、不寫行動者、不寫應該改成什麼（`memory.assert_ks1_clean` 逐條測）。

## 二、取代 09-24 哪一條

取代 `DECISION_20260924_TWIN_AGENT_RUN.md` 開頭的「跑法是 `--allow-no-suite`，裁決 `accepted=null`＝沒有客觀標準、不判」與 §八 第 1 條
「`accepted=null`……不准寫成 `false`」——**只對分身的預設路徑**。具體：

* `AgentConfig.gate=True`（預設）：`allow_no_suite=False`、`retry_arm="revise"`、`max_attempts=3`、`feedback_into="both"`；
  `accepted` 是 `True`／`False`，說的**只是**「有沒有根據」。
* `AgentConfig.gate=False`：舊行為逐字不變（只給不跑世界的 fixture agent 的舊測試用，三處）。
* 沒變的：`accepted=null` 在這一格**仍然**代表「沒有閘門量到」（舊錄影、`gate=False`、`infra_void`）；Vacant 不判對錯的口徑不動。
* `tv_contract` 規則 11 換成第 2 版（`RULE11_VERSION = 2`）：practical 格允許 `gate_ran`／`revised`；`verdict.accepted` 與 `stop_reason`
  對得上（`visible_pass`⇒true、`attempts_exhausted`⇒false、`ungated`／`infra_void`⇒null）；`gate_ran.checks[]` 每條只准
  `id`／`ok`／`label`／`file`／`line`（`file`＝artifact｜plan、`line`＝正整數，**沒過才帶、通過不帶**，不含檔名與內容），
  `passed`＝所有 `ok` 的 AND。電視端文件 `LIVE_INTERFACE.md` §十、§十一（v8／v9，另一個 repo）已是這個形狀；
  欄位名已與電視端 commit 9485f45 對齊（`line`／`file` 直接在每條 check 上，不是 `where`）。
  practical 格的 `verdict.blocked_by` 恆 `null`（沒過照常交件，沒有東西被擋下）；計數器 `Tally` 不把它算進 blocked／delivered。

## 三、四格窗的定義與閾值（常數都在 `grounding_gate.py`，測試釘住）

| 窗 | id | 查什麼 | 失敗訊息（只寫位置與缺的根據） | 短句 label（電視／手機；不含觀眾內容） |
|---|---|---|---|---|
| 1 讀過了嗎 | G1 | PLAN.md「它牽動到」一節點名的 `地上/…`（也認省略「地上/」「.txt」）必須在步驟紀錄的**成功讀取**集合裡；點名資料夾＝裡面至少讀過一件；點名了地上沒有的檔＝沒打開過。沒有該節標題 ⇒ 整份 PLAN 都算。PLAN 不存在 ⇒ 不亮 | 「計畫第 N 行點名的『地上/…』，這一跑沒有成功打開過」 | 讀過了／點名的東西沒打開（計畫第 N 行） |
| 2 找得到出處嗎 | G2 | 成品（工作區裡 PLAN 與信等之外的 `.md`／`.txt`）每行的阿拉伯數字（≥2 位，或接在 第／桌／列行位格窗封片 或 張枚截撮指掌 前後的個位數）、小數、印紋名（限「印紋X」「片號 X」「X 印紋／卡」脈絡）在這一跑讀過的內容（讀過的地上檔、信、**讀過的** WORLD.md）裡找得到。允許：千分位寫法差異、**同一份**內容裡兩個數的和或差、比某個讀過的數大 1 的下一號。不查：列表編號、第 N 步／次、共 N 項／字／分鐘、檔名裡的數字、中文數字 | 「成品第 N 行的『23』，這一跑讀過的東西裡找不到」 | 找得到出處／找不到出處（成品第 N 行） |
| 3 兩個出處對得上嗎 | G3 | `_facts.json` 登記的 32 個實體（帳本鏈 418–447 每片的印紋；第四列張數；土堆小陶印枚數；權威＝帳本鏈尾段／格狀圖／小陶印.txt）。成品對某實體說的值與權威不同，**而且它讀過權威檔**、同一行（或同實體的相鄰行）沒有指出（對不上、不一致、抄錯、修正、原本…，或同行寫出權威的值）⇒ 標出成品那一行與兩個出處的路徑（第二個出處＝它讀過、說的值與成品相同的那一件；沒有就只標權威） | 「成品第 N 行的『片 426 的印紋』，這一跑讀過的『地上/帳本鏈/…』與『地上/長桌廣場/…』說法不同，成品沒有指出」 | 兩個出處對得上／兩個出處對不上（成品第 N 行） |
| 4 收據只有閘門給 | G4 | 成品的**陳述句**同時有閘門詞（`GATE_WORDS`）與結果詞（`RESULT_WORDS`）、或鍵值形的自編收據（「閘門：過」「窗：6 格全亮」）。排除（`EXCLUDE_WORDS`）：未來／計畫／假設／否定／預留空白；豁免：逐字或轉述自它讀過的地上檔、而句子沒有指向自己的成品（`SELF_WORDS`），或句子在說地上某一片（含印紋名或 418–449 片號） | 「成品第 N 行寫了閘門通過或收據，這一跑的紀錄裡閘門沒有給過這個結果」 | 收據是閘門給的／收據不是閘門給的（成品第 N 行） |

* 沒有紀錄可對照（`_ledger.py` 沒備好，例如那一次 pi 被牆鐘砍掉）：四格一律不亮（量不到不是通過），訊息「這一跑的步驟紀錄沒有備好，這一格沒辦法對照」，label「沒有紀錄可對照」。
* 資料來源在工作區外：`<run>/twin_steps.ndjson`（pi 擴充寫）、`<run>/stage2_in/`（地上與 WORLD.md 的備份）、`<run>/letter_final.md`（段 1 結束時的信）。
  `tests_visible/` 由 `write_suite` 生成（`test_grounding.py`＋`_gg.py`＝本檔逐字複本＋`_ledger.py`）；`_ledger.py` 由 `twin_agent.sh` 在**每次 pi 結束後、凍結前**
  呼叫 `prepare` 重寫，並預先把四格結果寫成旁註 `twin_gate`（先於 `gate_ran`）。
* 兩段式在重改時：**第 2、3 次只跑段 2**（`TRAITS.md` 早被關卡移走、信已寫好，`twin_agent.sh` 的 `RETRY` 判斷）；回饋接在第 5 個參數尾端。
  第 1 次渲染後的 argv 與沒有閘門時**逐位元相同**（`argv_sha256`／`feedback_in_prompt_bytes=0`，e2e 測試逐元素比對）。
* 撤回：`tests_visible/`、步驟紀錄、`visible_*.json`（失敗訊息含成品片段）、預檢、`letter_final.md` 都在 run-dir，`erase_run_artifacts` 整個刪（e2e 測試逐項確認；真跑 `erased_left` 全部 false）。

## 四、真跑覆蓋表（舊 VM，真 pi＋gemma-4-12b-it-qat；合成特質 6 組輪流；`evidence_gate_20261001/`）

batch1＝g01–g30（30 跑）、batch2＝h01–h12＋b7＋b8、batch3＝rg02／rg06／rg08／rh07（旁註編號修正後的 4 跑重跑）。
覆蓋表算 batch1＋batch2 的 43 個有起 pi 的跑（42 個真跑＋b7；B2 不含「沒有紀錄可對照」的 ✗，那是 B7；batch3 的 4 跑另列：B2a 2、B2b 1、B2c 1、B2d 3、B3 4、B4 2、B5 2、B6 4、B7 1）。**每一條都真的發生過**（30 跑以內就齊了；B7 用 `--timeout 12` 另造一次）。

| 分支 | 發生在幾跑 | 哪幾跑（例） |
|---|---|---|
| B1 一次就過 | 16 | g09 g10 g11 g12 g13 g15 g16 g18 g19 g21 g27；h03 h08 h12 … |
| B2a 沒打開就說用了（G1 ✗） | 23 | g01 g02 g03 … h01 h02 h04 h05 h06 h07 h09 h10 h11 |
| B2b 數字沒出處（G2 ✗） | 10 | g06 g08 g14 g20 g23 g26 g28 g29；h04 h11 |
| B2c 兩個出處對不上（G3 ✗） | 8 | g02 g04 g14 g17 g23；h01 h05 h07 |
| B2d 自己寫的收據（G4 ✗） | 9 | g01 g04 g08 g14 g17 g23 g28 g29；h11 |
| B3 重來（`feedback_ready`→第 2 次 `attempt_started`） | 27（含 b7） | 任一 B2 或 B7 之後 |
| B4 改好了（第 2／3 次全亮） | 7 | g05 g20 g24；h02 h06 h09 h10 |
| B5 改了還是沒過（`attempts_exhausted`，拍立得照發、收據照簽） | 20 | g01 g02 g03 g04 …；h01 h04 h05 h07 h11 |
| B6 想把東西放進地上被擋（`twin_step ok:false` 寫 `地上/`） | 20 | g01 g02 g04 …；h02 h03 h04 h06 h08 h10 |
| B7 時間到、沒說做完（`agent_exited.timed_out`） | 5 跑／7 次嘗試被砍（batch3 的 rg02 又一次） | g02 g06 g08 h07；b7（`--timeout 12`，三次都砍＝stage 1 沒寫完信 ⇒ 退化 `agent_no_plan`） |
| B8 這一跑不算 | **沒有演到 `infra_void`**：b8（`VACANT_TWIN_PI` 指到不存在的檔）在起 pi 之前就被 `agent_available` 擋下，走 `agent_unavailable` 退化（沒有 lifecycle 事件） | b8 |
| B9 撤回 | 48／48（含 batch3、b8）跑完以 `twinlink.withdraw` 撤回，`run_artifacts_present`＝false | 全部 |

* 時間：42 個真跑（含重改）牆鐘**中位 91.8 秒、最慢 494.8 秒**（g06：一次 300 秒被砍）；單次嘗試多在 25–130 秒。
* 結果：accepted=true 23／false 19；**第 1 次就有 ✗ 的 26 跑，其中 7 跑在第 2／3 次改好（27%）**；16 跑第 1 次就全亮。
  ⚠ 這是 gemma-12B 在這一組提示下的比例，不是「閘門讓分身做得更好」；多數沒改好的是模型把同一個沒根據的東西原樣再交（例：g01 三次都寫「閘門亮燈：綠光」）。
* 窗別（嘗試層級、不含沒紀錄那 7 次）：G1 35、G2 16、G3 16、G4 19。
* 事件流（43 條 lifecycle＋旁註）全部過 `lifecycle.validate_stream`、`sidecar.validate`、`Folder`→`tv_contract.validate`；93 筆 `gate_ran` 裡有 82 筆帶 `checks`，
  沒帶的 11 筆是 7 次被砍＋（修正前）4 筆編號錯位，見下。
* 事件流原封不動存檔，可直接餵電視：`evidence_gate_20261001/batch*/<name>.lifecycle.jsonl`＋`.sidecar.jsonl`。

## 五、誤擋清單（每一個 ✗ 原文與出處在各跑的 `<name>.json` 的 `attempts[].windows[].evidence`；以下是**判成誤擋**並已修的）

| # | 跑 | 窗 | 被擋的那一行 | 為什麼是誤擋 | 修法 |
|---|---|---|---|---|---|
| 1 | g23 a1 | G2 | `印紋：[與出生片_420到440.txt 中的印紋一致]` | 420 在檔名裡，不是宣稱 | 先去掉檔名樣式（`_FILENAME`）再抓數字 |
| 2 | g14 a1／a2 | G3 | `在第四列的第二個位置放了一張卡片。` | 「一張」被當成第四列的張數 | 張數必須緊接在主詞後（「第四列：6 張」「第四列共有 6 張」） |
| 3 | g23 a3 | G3 | `…修正了原本第四列僅有6張的錯誤。` | 成品自己指出了舊值是錯的 | 指出詞加：錯誤、更正、修正、原本 |
| 4 | g29 a2／a3 | G4 | `窗格亮燈數：6 格全亮`、`「蕨葉」…最終成功通過了所有 6 格窗格。` | 在說地上蕨葉那張收據，不是自己這件成品 | 轉述地上檔（句子沒有指向自己）與在說地上某一片（印紋名／片號）的句子豁免；上下文窗縮到 ±3 字 |
| 5 | h04 a3；h11 a2／a3 | G2 | `編號：448（接續於 447 片之後）`、`片：448` | 自己編的下一號 | 比讀過的某個數大 1 的下一號算找得到 |
| 6 | rg08 a1 | G4 | `（此處預留閘門生成的綠光收據編號）` | 預留空白，不是宣稱 | 排除詞加：預留、留空、保留、待填、填入、等待、空白 |

另有一個**不是誤擋、是 bug**：旁註 `twin_gate.attempt` 原本取「`prepare` 被呼叫的次數」，被牆鐘砍掉的那一次沒有 prepare ⇒ 後面的編號錯位（g02／g06／g08／h07 的第 1 筆被借給被砍掉的那一次）。
修成取 launcher 的真實嘗試編號（事件檔裡這一跑的 `attempt_started` 數；`_learn_run`），回歸測試 `test_e2e_sidecar_attempt_numbers_are_the_launchers_…`；
batch1／batch2 那 4 條旁註在存檔時依規則改正（見 `evidence_gate_20261001/README.md`），batch3 是用修好的程式重跑的 4 跑，編號全對。

**修好之後的驗證**：每一條誤擋都有回歸測試＋負控制（同一類的真實原句照擋，來自真跑）；把 batch1／batch2 存下的每一次嘗試（成品、PLAN、抽到的地上）離線重算，
被修掉的只有上表那些行（其餘被拿掉的多是「後面幾次才讀」的累計讀取近似造成），沒有新增的 ✗；batch3（最終版再加第 6 條前的程式）剩下的 ✗ 全部人工讀過、都是真的沒根據
（自編收據、編造的鏈上號碼與印紋、抄錯的 426／第四列張數、沒打開就點名）。⚠ **沒有用最終版把 42 跑整批重跑**——第 5、6 條是在 batch2／batch3 才看到的，靠離線重算與測試確認，不是靠新一輪真跑。

主線逐條判斷用：每個 ✗ 都附被擋那一行原文（`blocked_line`）與地上出處（`ground_origin`：G2 是該數字在哪些地上檔出現、讀過沒；G3 是主詞所在行；G1 是點名的檔地上有沒有；G4 是地上有閘門字樣的行）。

## 六、誠實邊界（改碼時保留）

1. **查的是根據的有無，不是好不好**；全部有根據 ≠ 做對。`accepted=true` 只說「每一步有根據」，不說「Vacant 讓分身做得更好」。
2. **G2 是字面比對，會被巧合騙**：一份讀過的內容裡數字很多時（帳本鏈尾段 418–447）小於 30 的數都「算得出來」、「下一號」放行，所以編造的 448 這類延伸不一定被抓；
   只認阿拉伯數字；三個以上相加的總數會被標出。G3 只對 32 個登記的實體、而且要它**讀過權威檔**才判；G4 是詞表，會誤放（未收錄的說法）也可能誤擋（未收錄的轉述）。
3. 被牆鐘砍掉的那一次沒有 prepare ⇒ 四格全不亮、訊息是「步驟紀錄沒有備好」（量不到不是通過）；電視看到的是 4 個 ✗ 但沒有位置。B7 的畫面應該看 `agent_exited.timed_out`，不是看 checks。
4. 模型常常**不照回饋改**（G4 的自編收據三次都原樣再交）；回饋「一定出現在模型輸入裡」是機制性質，不是效果量測。
5. 圍牆模式（`enclose=on`）有把閘門參數傳進圍牆裡的 launcher，**但圍牆裡再開驗收沙箱的巢狀 bwrap 沒有真跑驗證過**。真跑都是 `enclose=off`。
6. 步驟紀錄由 pi 擴充寫、pi 結束後才讀；沒有 OS 隔離（`twinagent` 誠實邊界 2）。
7. 手機端：`/api/result` 帶 `review:[{id,ok,label,attempt}]`——雲端 server.js（vacant-world-cloud P4-A）的 `reviewProblem` 形狀相容（id≤24 字元、label≤120、attempt≤9），**只讀了程式沒有對雲端真送**。
   電視端 `LIVE_INTERFACE.md` 在另一個 repo，本次沒改；它已是 `checks[].line`／`file` 的形狀。
8. 沒演到的：B8 的 `infra_void`（見上）、`requests_seen=0`（不可歸因）。


## 七、P8 線 V（2026-10-02）：逾時＝未判、整跑預算、B8、最終版再驗誤擋

1. **被時限切掉的那一次不是「四個錯」**：`agent_exited.timed_out`（launcher 牆鐘）或整跑預算切掉（`gate_cut.json`／旁註 `twin_gate.cut=true`）的嘗試，
   `gate_ran.checks` 四格 `ok:null`、label「時間到，這一次沒有交件」（`tv_contract.GATE_CHECK_TIMEOUT_LABEL`，`ok:null` 只准配這句、不帶位置，`passed` 必為 false）；
   手機 `review` 同樣 `ok:null`。電視看 `draft_done.timed_out` 演 B7。沒逾時的照常判（負控制測試）。
   ⚠ 這一條只涵蓋「被時限切掉」；`pi` 自己崩潰／沒寫出信（`twin_agent.sh` exit 3／4，沒有 prepare）不算，那種嘗試在 visible 結果裡仍是四個「沒有紀錄可對照」，
   Folder 不帶 `checks`（電視不會演成四個錯，但手機 review 的 label 是「沒有紀錄可對照」）。
2. **整跑預算**：`twinagent.RUN_BUDGET_S=420`、`MIN_ATTEMPT_S=60`（`AgentConfig.run_budget_s／min_attempt_s`）。`twin_agent.sh` 用 `grounding_gate.py limit` 算這一次 pi 的時限
   ＝min(單次上限 300, 剩下的預算)，用 `runlimited` 殺整個行程群組；重改時剩不到 60 秒就不開 pi（SKIP）。⚠ 沒動 `vrun/*`：launcher 的嘗試數固定 3，
   所以被 SKIP 的嘗試仍會有 `attempt_started`／`gate_ran`（四格 `ok:null`）事件，只是沒有 pi；整跑照 `attempts_exhausted` 收尾（拍立得照發）。
   最終版 12 跑牆鐘中位 179 秒、最慢 363.6 秒（f08：第 1 次 300 秒被牆鐘砍、第 2 次 33 秒過）；**沒有任何一跑真的撞到 420 秒預算**，預算切斷只有測試證明（假 pi：預算 12 秒、下限 6 秒 ⇒ 只開 1 次 pi）。
3. **B8**：把端點指到關閉的埠後，production 的探測（`upstream_reachable`）直接退化成 `upstream_unreachable`、不起 pi（`b8_probe_blocked.json`）。略過探測讓 pi 起得來：
   pi 打了 4 通到中介，**每一通 `model_call.error=true`、`requests_seen=4`（中介把失敗的呼叫也算進去）**，沒有信 ⇒ stage 1 失敗、`agent_no_plan` 退化；
   所以 **`requests_seen=0`／`infra_void` 這條在這條路上造不出來**。能從事件流辨認「模型打不到」的訊號是：該跑所有 `model_call.error=true`、沒有 `gate_ran.checks`、twin 退化 `agent_no_plan`。
4. **最終版 12 跑**（`evidence_gate_20261002/`）：accepted true 8／false 4；B1 4、B2a 7、B2b 3、B2c 1、B2d 4、B3 8、B4 4、B5 4、B6 5、B7 1。逐條 ✗ 的原文與出處見回報與各跑 json。
   判斷：沒有確定的誤擋；兩處待主線判——f03 的「第三列：16-19 號在位」等自訂卡片編號（G2，三次嘗試都擋，是分身自訂的編號、地上沒有這些數字），
   f06 a1 的 `地上/捏土處/出生片 433 的資訊`（G1，路徑後面接了說明，地上沒有「出生片」這個檔）。

## 八、P9 線 V（2026-10-02）：圍牆（`enclose=on`、`require_tier=B`）裡的閘門

舊 VM 真跑 6 跑＋1 個預算探針（`evidence_gate_20261002/enclose/`）：驗收沙箱在 bwrap 圍牆裡起得來、四格窗照跑、收據級別 **B**（`enclosure_applied=true`，6 跑全是 B）、
門的呼叫數＝收據的 `requests_seen`。踩到並修掉兩件事：
1. 第一次跑 `gate_ran` 沒有 `checks`：圍牆裡的 `prepare` 寫不到圍牆外的旁註檔與事件檔。修：`gate_meta` 在圍牆模式指向 run-dir 的 `lifecycle_part.jsonl`／`gate_sidecar_part.jsonl`，
   主機側 `twinenclose.EventForwarder` 先轉旁註、再轉 lifecycle（旁註先於 `gate_ran`）。修後 6 跑的每一筆 `gate_ran` 都帶 `checks`。
2. 被時限切掉但閘門仍全過的嘗試（e7）：Folder／手機 review 照實用逐格結果，不標 `ok:null`（`passed` 必須等於逐條 AND）。
- 預算在圍牆裡生效：e7 以 `VACANT_TWIN_RUN_BUDGET_S=40` 跑，牆鐘 40.6 秒、第 1 次嘗試被預算切斷、閘門仍判過。
- 環境坑：門的 `AF_UNIX` 路徑超過 108 字元會 `OSError`（`<TMPDIR>/…agentruns/doors/<32 字>/relay.sock`）；展場的資料庫路徑要夠短。
- 圍牆內 e1 有一次 300 秒牆鐘逾時（四格 `ok:null`）。

## 九、工具必填參數 `thought`（2026-10-02）：讓「它在想」看得到

gemma 在段 2 幾乎只呼叫工具、不說話（提示裡「動手前先說一句」它不照做），電視上 `twin_say` 只有 0–3 句。三個工具（`ws_list`／`ws_read`／`ws_write`）各加**必填**參數
`thought`（一句繁體中文、不寫檔名、40 字內，說明過 KS-1）。擴充只把它追加到 `$VACANT_TWIN_THOUGHT_LOG`（`twin_thoughts.ndjson`，run-dir）；**主機側** `twinagent.SayForwarder`
讀它，過既有的 LEAK 防呆、檔名過濾、≤80 字後才轉成 `twin_say`（違規就丟那一句、工具照執行）；`thought` **不進** `twin_step`。空的或缺的 thought：不記、不失敗。
真跑 6 跑（enclose=on、級別 B）每跑段 2 有 14–38 句 `twin_say`（原本 0–3）；被防呆丟掉的 thought：0／0／0／0／2／3 句。四格結果沒有可歸因的變化（單次抽樣，見證據 README）。
⚠ 段 1（寫信）的 thought 也會進 `twin_say`，防呆同一套（抄觀眾原文 ≥8 字就丟）。⚠ 手機 `read_says` 目前只讀 stdout 的 say，沒有併入 thought。
