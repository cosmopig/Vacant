# rfh4 ADDENDA（計畫 `rfh4_polyglot34_pi_gemma12b_local.json`，prereg 一字不改）

## 2026-11-26 15:07Z — 冒煙閘門判 GATE_FAIL，依 prereg 放行主批（vacant-hope 決定）

> 更正（第九次稽核，11-27）：標頭原寫 15:40Z，實際提交與推送是 15:07Z（5a09670ce）。

- **冒煙**：`smoke_rfh4_polyglot_pi_gemma12b_1003`，2 對（pg_wordy、pg_transpose）×四臂，10:55Z–14:57Z。
  - 8 格**全部沒過**、全部跑滿時間；判定是 UNRESOLVED（閘門不看通過率）。
- **閘門腳本 `ops/redo/gates/smoke_gate_rfh4.py` 判 GATE_FAIL，唯一的失敗項**：`pg_wordy/r1/R` 第 2 次嘗試，驗收（題目原本的測試，上限 120 秒）回 `acc_status=timeout`。
  - 那一次 agent 也跑滿 600 秒。同格第 1、3 次驗收正常（21/25、7/25）。
  - 閘門的其他檢查全過：2/2 對；四臂各 2 格；每格都有模型呼叫；infra_void 0；評分器種類正確；H 有 evidence 模式的 review；RF 第 2、3 次都有模板 hint；R 沒有 hint；沒有 harness 例外。
- **閘門腳本比 prereg 嚴**：
  - prereg `stop_rules` 第 3 條的冒煙條件是四臂各至少 1 格有成功的模型呼叫、H 至少 1 格有掛鉤事件、RF 至少 1 次 hint_bytes>0、0 個 harness 例外。這四條都成立。
  - 腳本另外要求「每次驗收 status 都是 ok」，這條不在 prereg 裡。
- **放行理由**（vacant-hope 11-26）：預註冊的文字是準據，腳本是它的實作，而且比它嚴。失敗的那一項是 agent 留下的程式讓驗收逾時，屬於受測行為，不是 harness 故障。閘門腳本不改。

### 放行前的兩個檢查（唯讀）

1. **驗收逾時在主批怎麼計**：`redo.py` 的 `acceptance()` 用 `_run_quiet`。逾時時：
   - 會殺掉整個行程群組（`start_new_session` 加 `os.killpg`），回傳 `status="timeout"`、`accept=False`。
   - R／RF 照政策（只讀 acc）繼續下一次嘗試。
   - 交件時，評分器是 `visible_tests_pristine`，`pass=bool(acc.accept)`，所以這一次記成**未過**；它不是 None，因此**不會**變成 `grader_failed` 的 infra_void。
   - infra_void 只由嘗試層的基礎設施失敗判定（工作區沒動，加上 0 次模型呼叫或連線錯誤），和驗收無關。
   - 冒煙結束後，機器上沒有殘留的測試行程。
2. **冒煙 0/8 是不是異常**：拿這兩題在先前同模型（gemma-4-12b-it-qat、pi）批次的歷史來對照：
   - **pg_wordy**：A 臂 confirm1／1c／2_1004／redo1 合計 **2/20**；R3（redo1）**2/5**；`vacant do` P 臂 0/5、0/5、3/5。
   - **pg_transpose**：A 臂合計 **1/20**；R3（redo1）**2/4**；P 臂 1/5、0/5、2/5。
   - 照歷史，A／H 幾乎一定不過；R／RF 每格約 0.4，四格全滅的機率約 0.6⁴≈0.13。**不算異常。**
   - 模型呼叫速率（A 臂，每分鐘）：冒煙 pg_wordy 6.6、pg_transpose 0.8；歷史 pg_wordy 4.1–5.8、pg_transpose 2.1–4.1。pg_transpose 在最後一次長生成時逾時，所以速率較低。整體在歷史範圍內，**看不出環境變了**。
   - 差別：冒煙的 A／H 在 pg_wordy 上一直工作到 1800 秒（197 次呼叫）；歷史上 A 常在 400–800 秒就自己停下。這是 agent 行為的變異，不是速度問題。
- **結論**：照發主批。閘門 `next` 的兩行由執行方手動附加到 queue_rfh4_1003.txt／queue_rfh4_1004.txt，兩台各自的佇列都可以個別暫停、續跑。

### 補記（第九次稽核，11-27）：兩份預註冊文件並存
- 同一個提交裡的冒煙計畫 `smoke_rfh4_polyglot_pi_gemma12b_1003.json`，`prereg.purpose` 寫的是：「只檢查基礎設施與操作：……驗收都正常、0 個 infra_void。**條件寫在 ops/redo/gates/smoke_gate_rfh4.py**，與通過率無關。」
- 所以有兩份預註冊文件並存：
  - 主計畫 `stop_rules` 的文字比較寬。
  - 冒煙計畫把腳本當作條件所在，而且明列「驗收都正常」。
- 放行是 vacant-hope 在**看到 GATE_FAIL 與冒煙 0/8 之後**決定的，採用的是主計畫文字這一種讀法。**另一種讀法（照腳本判不過、重跑冒煙）同樣站得住。**

## 2026-11-27 — 暫停 1004 的佇列（偏離計畫；vacant-hope 決定）
- **偏離什麼**：計畫的 `stop_rules` 只允許在 bad allocation、C 槽空間、崩潰這幾種情況停批；`schedule` 還寫了「兩批照跑、照結案，不搶 GPU」。這次暫停不在允許的情況裡，所以是偏離。
- **原因**：把 1004 讓給探索性先導（快車道：9B 幹活、Haiku 出考卷），這是 vacant-hope 11-27 的決定。rfh4 在 1003 照跑不動。
- **做法**：先寫這份附錄並推上遠端，再停。
  - 等 1004 正在跑的那一格完成、寫出 cell.json，立刻對 1004 的 runner 送 SIGTERM。
  - 如果送出時下一格已經開始，那一格依計畫的續跑規則丟掉，續跑時重做。
- **寫這段時的進度**：1004 已完成 52 格、13 個完整對；1003 已完成 53 格、13 對。實際停下時的格數與對數會補在下一行。
- **之後續跑**：在**同一台（1004）、同計畫、同 harness**，用原來的指令 `--only-providers lms1004`、同一個 root。
  - 每台跑哪些對不變：機器由對的序號決定（`provider_for`：序號 mod 2）。
  - **不把 1004 的對改到 1003 補跑。**如果最後 1004 不再續跑，會另寫附錄，批次照剩下的那一半判。
- 先導幾輪做完就把 1004 還回來並續跑，續跑時間也會補記一筆。
