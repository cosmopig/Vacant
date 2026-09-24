# 早上的報告：可究責追緝（2026-09-24 晚上做的）

> 分支 `claude/vacant-verification-redesign-jv7eou`。證據等級：**L-fake**（四個真 agent＋照劇本回答的假模型，
> 沒碰任何真模型 API、也沒連外網）。沒有開 PR。

## 一句話

昨晚你說收件口只是「本機多個驗證器」，不是咎責、不是抓錯誤點。現在有了：**每一步誰做了什麼都簽進一條鏈；
驗收不過時，追到是哪一步、哪個行動者（主 agent、子 agent）、那個錯的值是從哪裡來的；回合結束時告訴 agent
「哪個檔哪一行、應該是多少、第一次出現在第幾步」；agent 不再被要求繼續時，沒解決的問題直接交到你手上。**
四個 agent（pi、Claude Code、OpenCode、Codex）都接上了，而且都用真的程式跑過。

## 好消息

1. **歸因 33/33**：四個 agent × 八種埋錯，另加 Claude 的背景子 agent——`ops/accountability/evidence_20260924/README.md`。

   | 錯從哪裡來 | Vacant 的結論 |
   |---|---|
   | agent 憑空寫了錯的數字 | 指到寫下它的那一步；在重建的前後狀態上重跑同一條驗收，翻轉成立 ⇒ **可證明**（只有這一級會影響信譽） |
   | 給定的輸入本身就錯 | 指到那個輸入檔的那一行；**agent 不背** |
   | agent 寫的腳本算錯 | 指到**寫腳本**的那一步，不是寫報告的那一步 |
   | agent 走了之後有人在外面改檔（負控制） | 記成「沒被記錄的改動」，**不怪任何人** |
   | 抓回來的**網頁**本身就錯（`curl`） | 指到那個網址，agent 不背。反過來，agent 不能靠「順便 curl 一下」把自己算的值洗成網頁說的 |
   | **子 agent** 算錯、主 agent 照抄 | 指到子 agent 寫錯的那一步（帶子 agent 的 id 與類型），四個 agent 都對 |
   | Claude 的**背景**子 agent（它的預設） | 同上；而且子 agent 還在做時，回合結束的驗收先不跑（原本會催主 agent 把子 agent 的工作重做一遍） |
   | **平行**委派兩個子 agent，其中一個錯 | 指到錯的那一個子 agent 的那一步，不怪另一個（跑的時候發現、修了：先收尾的委派會把兄弟的寫入掃進自己的差異） |
   | **你**指出一個契約檢查不到的錯（`vacant flag`） | 指到寫下那一行的那一步；下一次工作階段的回合結束告訴 agent（契約過了也照樣）；改掉之後自己解決 |

2. **回饋真的到了模型手上**：Claude Code、Codex、pi 的下一次模型請求裡（22/22 格），看得到這樣一段（實錄）：

   ```
   - total: FAIL — report.md:3 says "96"
     expected 69 (column 'amount', 3 rows)
     it was copied from step 2 (Bash); step 5 wrote it into report.md
   ```

   改好之後收件 accept（22/22）。裡面沒有「是誰」（0/33）——那只寫在給你的報告裡（KS-1：後果不走文字通道）。

3. **問題不會被淹沒**：輪數用完、或只剩 agent 改不動的（等審查、等證據），Claude Code 直接在畫面上顯示給你
   （`systemMessage`）；任何 agent 都可以 `vacant trace report` 看完整清單；OpenCode `run` 沒有回合邊界可以回饋，
   但工作階段結束時會在背景把報告寫好。

4. **後果**：只有「可證明」的錯進 agent 的信譽（不用 slash，你撤銷一個結論會逐位元反轉）；輸入錯、網頁錯記在來源上；
   沒被記錄的改動記在那個平台的整合覆蓋率上。路由＝報告尾端給你的建議，或 `vacant do --agent auto`
   （每個 agent 在這類任務上不到 5 次就先輪流，不拿小樣本做決定）。

5. **四輪對抗審查，75 條，全部重現、成立的全部修掉，每條一個會紅的回歸測試**：
   - 核心（47 條，`ops/accountability/review_m8/FINDINGS.md`）：同一個值出現在好幾行時曾經錯怪人；`python3 -u x.py`、
     `cd dir &&` 曾經讓「跑腳本的人」背了「寫腳本的人」的錯；Claude 背景子 agent 的結果曾經被當成**你**說的話。
   - 大專案（8 條，`ops/accountability/review_scale/FINDINGS.md`）：背景還在看第一眼時就開始的步驟，曾經讓**後來只改了
     一行的人**背「可證明」。
   - 子 agent 與網頁（12 條，`ops/accountability/review_subagent_curl/FINDINGS.md`）：pi 的子 agent 標記第一版在平行、
     重載、巢狀、tmux、別的專案下都會認錯主／子；`curl` 第一版可以被拿來洗掉 agent 自己算的值。兩個都重新設計了。
   - 延後驗收與委派的寫入（8 條，`ops/accountability/review_defer_credit/FINDINGS.md`）：沒回報的子 agent 會讓
     `--resume` 之後一小時不驗；「同一個版本」只比後版本時，無辜的後來者會背「可證明」；子 agent 能偽造一個「你的」標記
     （提示注入）——都修了（標記現在要有你的 owner 簽章）。

6. **大專案也在掛鉤的 30 秒上限內**：4 萬檔的專案第一次 5.7–8.2 秒、之後每次掛鉤 p95 0.6 秒、回合結束的追緝 1.9 秒，
   每一步多存 0.9 KB（修之前第一次要 33.8 秒、每一步 4.9 MB）——`ops/accountability/evidence_20260924/perf/`。

7. **真模型實驗準備好了（草稿）**：`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md`＋
   `ops/accountability/r536/`（題庫、執行器、收官計算，假模型冒煙過）。三臂只差下一次嘗試的提示：
   不回饋（重抽）／今天的泛用回饋／追緝過的回饋。

每一次推上去的程式碼，全套測試的失敗集合都等於基線（`test_cert_*` 5 條＋`test_exhibit_twin_wiring.py` 5 條，環境造成）。

## 壞消息與還不能說的

1. **「產出更接近需求」還沒有被證明。** 今晚的一切都是機制證據（假模型看到回饋就照劇本改對）。真的答案要等 R536
   在團隊的本機模型上跑。而且 n=50 對 +10 pp 的檢定力只有 0.14–0.18——**最可能的結果是 INCONCLUSIVE**，
   預註冊裡事先寫好了，不會事後加題。如果追緝過的回饋和泛用回饋一樣好，那也是結論：追緝的價值在給人的報告，
   不在讓 agent 改得更好。
2. **OpenCode `run` 沒有交件前的回饋通道**（它在第一個 idle 就結束）。報告照樣有、你的標記也留著，但 agent 沒機會改。
3. **沒跑的**：Codex 的 multi-agent v2 的端到端。兩步（或兩個子 agent）同時寫**同一個**檔時，只能說「是其中之一」
   （候選集合），不會硬選一個。
4. **pi 的子 agent**（pi 本身沒有，靠擴充另開 pi 行程）：從這個 pi 開出來、在同一個專案裡的任何 pi 都算它的子 agent
   （包括你在 pi 裡用 `!` 開的）；叫它的是哪一個呼叫靠任務文字對，兩個平行的子 agent 拿到一模一樣的任務時說不出是哪一個。
5. **網頁來源**：Vacant 只看得到指令字串——代理、DNS、hosts 檔把一個正常的名字指到本機，它看不出來。
   端到端的情境 F 就是用代理把 `portal.vacant-lab.test` 接到假模型的（實驗設定）。
6. **超過 5 萬檔就不逐步掃描**：agent 仍然收得到「哪個檔哪一行」（驗證器自己給的），但沒有「第一次出現在第幾步」，
   也不會怪任何人。第一次掃描超過 8 秒會改到背景做，那段時間的步驟記成「沒觀察到」。
7. **簽章金鑰和 agent 在同一台機器、同一個帳號**：竄改看得出來（讀不回來的狀態 ⇒ 追緝一律「沒觀察到」），
   但不是不可能。要更強要把簽章者放到另一個帳號。
8. **SessionEnd 不保證觸發**（Claude `-p` 有背景指令還在跑、pi 被 Ctrl-C）：那一次沒有工作階段結束的報告。
   `vacant do` 不受影響（它自己在行程結束後追緝）。
9. **Claude Code 的掛鉤不帶模型 id**，信譽格的模型欄是 `unknown`（逐字稿裡有自稱的模型，封存了，但沒當鍵）。

## 需要你決定的

1. **R536 要不要簽？** 簽之前要填：模型（含量化）、後端、推論模式、agent 與版本、`vacant` commit、題庫雜湊
   （預註冊 §二-4）。簽了就交給團隊跑：
   ```
   python ops/accountability/r536/bank.py --out bank --n 50 --seed 536
   python ops/accountability/r536/run.py --bank bank --agent pi --out rows.jsonl
   python ops/accountability/r536/analyze.py rows.jsonl
   ```
2. **人的標記（`vacant flag`）要不要能擋收件？** 現在不擋（進病歷、進報告、下一次回合結束告訴 agent）；要擋的話走契約裡的
   `review` 主張。
3. **產品路徑不用 slash**（可證明的錯只記一筆 weight 1.0 的負評、可撤銷）。論文裡 λ=1 的永久排除是 8/17 你們的裁決；
   這裡沒有推翻它，只是單一使用者的產品路徑不接它。同意嗎？
4. **要不要開 PR？** 還沒開。

## 五分鐘看懂（建議順序）

1. `decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §一、§三、§四-5（等級與後果）、§七（審查改了什麼）
2. `ops/accountability/evidence_20260924/README.md`（33/33 那張表、模型真的收到的回饋、大專案的時間）
3. 四份審查：`ops/accountability/review_m8/`、`review_scale/`、`review_subagent_curl/`、`review_defer_credit/` 的 `FINDINGS.md`
4. 在任何有契約的專案裡：`vacant trace show`、`vacant trace report --check`、`vacant trace blame <檔>:<行>`、
   `vacant flag <檔>:<行> "哪裡錯"`

## 過程紀錄

每一輪做了什麼、證據、偏移檢查：`ops/accountability/PROGRESS.md`。`/loop` 的錨與里程碑：`LOOP.md`。
