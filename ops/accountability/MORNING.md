# 早上的報告：可究責追緝（2026-09-24 晚上做的）

> 分支 `claude/vacant-verification-redesign-jv7eou`。證據等級：**L-fake**（四個真 agent＋照劇本回答的假模型，
> 沒碰任何真模型 API）。沒有開 PR。

## 一句話

昨晚你說收件口只是「本機多個驗證器」，不是咎責、不是抓錯誤點。現在有了：**每一步誰做了什麼都簽進一條鏈；
驗收不過時，追到是哪一步、哪個行動者、那個錯的值是從哪裡讀來的；回合結束時告訴 agent「哪個檔哪一行、應該是
多少、第一次出現在第幾步」；agent 不再被要求繼續時，沒解決的問題直接交到你手上，不會被上下文淹沒。**
四個 agent（pi、Claude Code、OpenCode、Codex）都接上了。

## 好消息

1. **歸因 16/16**（四個 agent × 四種埋錯；對抗審查修正之後重跑仍是 16/16）——`ops/accountability/evidence_20260924/README.md`：

   | 錯從哪裡來 | Vacant 的結論 |
   |---|---|
   | agent 憑空寫了錯的數字 | 指到寫下它的那一步；在重建的前後狀態上重跑同一條驗收，翻轉成立 ⇒ **可證明**（只有這一級會影響信譽） |
   | 給定的輸入本身就錯 | 指到那個輸入檔的那一行；**agent 不背** |
   | agent 寫的腳本算錯 | 指到**寫腳本**的那一步，不是寫報告的那一步 |
   | agent 走了之後有人在外面改檔（負控制） | 記成「沒被記錄的改動」，**不怪任何人** |

2. **回饋真的到了模型手上**：Claude Code、Codex、pi 的下一次模型請求裡，看得到這樣一段（實錄）：

   ```
   - total: FAIL — report.md:3 says "999"
     expected 69 (column 'amount', 3 rows)
     this value first appeared at step 2 (Bash)
   ```

   裡面沒有「是誰」（0/16）——那只寫在給你的報告裡（KS-1：後果不走文字通道）。

3. **問題不會被淹沒**：輪數用完、或只剩 agent 改不動的（等審查、等證據），Claude Code 直接在畫面上顯示給你
   （`systemMessage`）；任何 agent 都可以 `vacant trace report` 看完整清單；OpenCode `run` 沒有回合邊界可以回饋，
   但工作階段結束時會在背景把報告寫好。你也可以自己指出錯處：`vacant flag report.md:2 "市長是 Alice"`——
   簽章、追緝、下一回合告訴 agent。

4. **後果**：只有「可證明」的錯進 agent 的信譽（不用 slash，你撤銷一個結論會逐位元反轉）；輸入錯記在來源上；
   沒被記錄的改動記在那個平台的整合覆蓋率上。路由＝報告尾端給你的建議，或 `vacant do --agent auto`
   （每個 agent 在這類任務上不到 5 次就先輪流，不拿小樣本做決定）。

5. **對抗審查 47 條，全部重現、全部處理，每條一個會紅的回歸測試**——`ops/accountability/review_m8/FINDINGS.md`。
   其中幾條很重要：同一個值出現在好幾行時曾經會錯怪人（現在逐行追）；`python3 -u x.py`、`cd dir &&` 曾經讓
   「跑腳本的人」背了「寫腳本的人」的錯；Claude 背景子 agent 的結果曾經被當成**你**說的話；隱藏驗收的位置曾經
   從「還沒解決」的標記漏出去。另外一份完備性批判抓到：四個平台的主 agent 共用同一個信譽衰減時鐘
   （Codex 跑 400 次會讓 Claude 那一格變舊）——也修了。

6. **真模型實驗準備好了（草稿）**：`decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md`＋
   `ops/accountability/r536/`（題庫、執行器、收官計算，假模型冒煙過）。三臂只差下一次嘗試的提示：
   不回饋（重抽）／今天的泛用回饋／追緝過的回饋。

## 壞消息與還不能說的

1. **「產出更接近需求」還沒有被證明。** 今晚的一切都是機制證據（假模型看到回饋就照劇本改對）。真的答案要等 R536
   在團隊的本機模型上跑。而且 n=50 對 +10 pp 的檢定力只有 0.14–0.18——**最可能的結果是 INCONCLUSIVE**，
   預註冊裡事先寫好了，不會事後加題。如果追緝過的回饋和泛用回饋一樣好，那也是結論：追緝的價值在給人的報告，
   不在讓 agent 改得更好。
2. **OpenCode `run` 沒有交件前的回饋通道**（它在第一個 idle 就結束）。報告照樣有，但 agent 沒機會改。
3. **子 agent 的端到端沒跑**（假模型不會演子 agent），只有單元測試＋四份可觀測面實測底稿。
4. **大專案沒量**：每次掛鉤多花 7–16 ms（p95）是在小工作區量的。超過 5 萬檔或一次掃描超過 10 秒，Vacant 就不再逐步掃描，
   追緝一律回「沒觀察到」。
5. **簽章金鑰和 agent 在同一台機器、同一個帳號**：竄改看得出來，但不是不可能。鏈頭另外寫進收件端的帳本，
   截短對得出來；要更強要把簽章者放到另一個帳號。
6. **SessionEnd 不保證觸發**（Claude `-p` 有背景指令還在跑、pi 被 Ctrl-C）：那一次沒有工作階段結束的報告。
   `vacant do` 不受影響（它自己在行程結束後追緝）。
7. **Claude Code 的掛鉤不帶模型 id**，信譽格的模型欄是 `unknown`（逐字稿裡有自稱的模型，封存了，但沒當鍵）。
8. 平行執行的平台（Codex、pi 預設平行）上，兩步同時寫檔時只能說「是其中之一」（候選集合），不會硬選一個。

## 需要你決定的

1. **R536 要不要簽？** 簽之前要填：模型（含量化）、後端、推論模式、agent 與版本、`vacant` commit、題庫雜湊
   （預註冊 §二-4）。簽了就交給團隊跑：
   ```
   python ops/accountability/r536/bank.py --out bank --n 50 --seed 536
   python ops/accountability/r536/run.py --bank bank --agent pi --out rows.jsonl
   python ops/accountability/r536/analyze.py rows.jsonl
   ```
2. **人的標記（`vacant flag`）要不要能擋收件？** 現在不擋（進病歷、進報告、下一回合告訴 agent）；要擋的話走契約裡的
   `review` 主張。
3. **產品路徑不用 slash**（可證明的錯只記一筆 weight 1.0 的負評、可撤銷）。論文裡 λ=1 的永久排除是 8/17 你們的裁決；
   這裡沒有推翻它，只是單一使用者的產品路徑不接它。同意嗎？
4. **要不要開 PR？** 還沒開。

## 五分鐘看懂（建議順序）

1. `decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §一、§三、§四-5（等級與後果）、§七（審查改了什麼）
2. `ops/accountability/evidence_20260924/README.md`（16/16 那張表＋模型真的收到的回饋）
3. `ops/accountability/review_m8/FINDINGS.md`（47 條）
4. 在任何有契約的專案裡：`vacant trace show`、`vacant trace report --check`、`vacant trace blame <檔>:<行>`

## 過程紀錄

每一輪做了什麼、證據、偏移檢查：`ops/accountability/PROGRESS.md`。`/loop` 的錨與里程碑：`LOOP.md`。
