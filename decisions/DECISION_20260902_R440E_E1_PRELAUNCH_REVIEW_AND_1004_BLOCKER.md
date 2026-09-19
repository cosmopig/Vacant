# R440E：E1 發射前審查（19 條發現）、watcher 被迴圈重跑的結果、1004 的真正阻塞

（2026-09-02 04:35 UTC，Fable 5.1，Mac 端 session「vacant」。人類 02:0x UTC 殺掉
watcher 並把 vacant-dev 全權交給本 session；本文件記錄之後兩小時發生的事、審查
結果、以及現在唯一擋住 E1 的東西。發射動作本身尚未發生。）

## 一、發射前審查（Workflow：3 個找碴者 × 3 個視角，反駁階段因 session 上限失敗）

三個獨立審查者（shell 正確性／LM Studio API／實驗有效性）對
`ops/gain/queue_e1_after_scale2.sh` 給出 19 條發現；**反駁驗證階段全部撞到
session 上限沒跑成，所以這 19 條是「未被反駁」不是「已確認」**。本 session 逐條
對照原始碼後採納的（都寫進 `ops/gain/launch_e1.sh`）：

| # | 嚴重度 | 發現 | 修法 |
|---|---|---|---|
| 1 | 高 | 單 run 檢查只做一次，之後載入／探針要幾分鐘，迴圈可在這段起別的 run | 發射前**重做**單 run＋目錄檢查 |
| 2 | 高 | 迴圈的 `local` 層叫 qwen，1004 的 JIT 會重載 22 GB qwen 把 gemma 擠掉（`localagent.py` 2026-08-30 註解已記錄過「搶記憶體時模型被換出、回 200 但 body=Model unloaded」） | LOOP_PROMPT 加 E1 視窗規則：不寫 `local`、不起 run、不殺 E1 |
| 3 | 高 | gemma 載入後沒驗 context_length；裸載走 LM Studio 預設（實測＝262144） | 驗 ctx==32768 否則停；快照存 `runs/g_r441_gemma_only_mbpp.backend.json` |
| 4 | 中 | 步驟 A（與 qwen 並存）成功會違反 R440C P0「gemma 單獨載入」 | prep 結束時印出 `resident_non_gemma=[…]`，非空要寫進 DECISION |
| 5 | 中 | hub 探針只看 HTTP 200；8765 會回 200＋error body（`brain_cline.py:129-135` 就是為此寫的） | 探針驗 body 有 `choices[0].message.content` 且無 `error` |
| 6 | 低 | 沒帶 `--probe-sample 0`：決定性 run（g_r342／g_r356 summary.json）量具是 179/179，預設只驗 12 | 加 `--probe-sample 0`（零 API 呼叫） |
| 7 | 低 | 120 秒後 pid 還活著就宣稱 launched，但 preflight 可能還沒跑完 | 等 launch.log 出現 preflight 的 ✓（最多 900s），PYTHONUNBUFFERED=1 |
| 8 | 低 | launch.log 用 `>` 覆寫，重試會沖掉失敗證據；已存在時不擋 | 改 `>>`，且 launch.log 已存在就停 |
| 9 | 低 | pid 用 ps\|grep 抓、`\|\| echo 000` 變 000000、重複啟動不留痕 | `$!`＋驗 cmd；`\|\| true`；flock 失敗寫 log |

沒採納的：「context 32768 會截斷」——同一審查者自己量了 g_r356 的 2162 通呼叫，
最大 prompt 是 revise 的 2776 tokens，<9% of 32768；32768 保留，但列為 E1 的
明示後端條件（決定性 run 的 gemma context 從沒被記錄過）。

## 二、watcher 在本 session 不知情下又被跑了一次（04:24 UTC）

人類 02:0x 殺掉的是迴圈第 4845 輪起的那份。04:24:15 UTC 又有一份啟動——
iter-4908.log 當時 0 bytes（claude -p 收尾才寫），時間點在第 4908 輪（sonnet，
04:21:11 開始）3 分鐘後，判斷是第 4908 輪照 R440C／R440D 的指令列又起了它。
它跑完了整個流程，結果（`~/vacant/logs/queue_e1.log`）：

```
load {"model":"gemma-4-12b-it-qat","context_length":32768}
  → HTTP 500 model_load_failed: Failed to load LLM engine … llm_engine_cuda12.node.
    The paging file is too small for this operation to complete.
load {"model":"gemma-4-12b-it-qat"}   （裸載＝預設 context 262144）
  → HTTP 500 model_load_failed: this model requires approximately 44.87 GB of memory
    … adjust the model loading guardrails in settings.
unload {"instance_id":"qwen_qwen3.6-35b-a3b"} → HTTP 404 not loaded
unload {"model":…}                          → HTTP 400 Missing required field 'instance_id'
（再試兩次載入，同樣兩個錯誤）
E1_LAUNCH_RESULT=abort_gemma_load_failed
```

**沒有動到任何已載入的模型**（它要卸的是 qwen3.6，而 1004 上現在載的是
qwen3.8-27b——見 §三），fail-closed 如設計。順便確認了 LM Studio v1 的
unload schema 是 `{"instance_id": …}`。

為了不再被迴圈重跑，`queue_e1_after_scale2.sh` 已改成只寫一行 log 就 `exit 2`
的停用殼；LOOP_PROMPT E1 視窗規則第 5 點明寫「E1 的發射不歸迴圈」。

## 三、1004 現況與真正的阻塞（本 session 04:20–04:30 UTC 讀到的）

- 02:00 之後有人在 1004 上**手動載入了 `qwen/qwen3.8-27b`**（17.7 GB，
  context 262144，parallel 4）；qwen3.6 已不在卡上。這是人類的動作，本 session
  不會擅自卸它（1004 不是被授權的那台 VM）。
- 在 3.8 常駐的狀態下，gemma **連 32768 context 都載不進**：錯誤是 Windows 的
  「分頁檔太小」（commit charge 不足），不是 VRAM 保護。裸載則觸發 44.87 GB 保護。
- 也就是說 E1 的阻塞是 **1004 這台 Windows 機器的記憶體／分頁檔配置＋3.8 常駐**，
  不是 hub、不是腳本、不是 vacant-dev。

## 四、給人類的決定（只有這一件）

要讓 E1 跑，1004 上必須：**卸掉 qwen3.8**（或把分頁檔加大到能同時放兩顆），
然後以 32768 context 載 gemma。三種做法，任一都行：

1. **REST（本 session 或 vacant-dev 都能發）**：
   ```
   curl -X POST http://100.86.226.21:1234/api/v1/models/unload \
     -H 'Content-Type: application/json' -d '{"instance_id":"qwen/qwen3.8-27b"}'
   cd ~/vacant/Vacant && bash ops/gain/launch_e1.sh prep      # 載 gemma@32768、驗 ctx
   bash ops/gain/launch_e1.sh launch                          # 探針 3/3 → 發射
   ```
   或一行：`UNLOAD_FIRST=1 bash ops/gain/launch_e1.sh all`。
2. **在 1004 的 LM Studio GUI**：Eject qwen3.8 → Load gemma-4-12b-it-qat，context 32768
   → 再跑 `bash ops/gain/launch_e1.sh launch`（prep 會偵測到已載入並驗 ctx）。
3. 保留 3.8、放棄 E1 gemma-only 條件——那就回到 R440D 的結論：infra 未修前
   不起任何 run，階梯 L0 記「無法在現有硬體上執行」。

本 session 的 auto-mode 分類器擋掉了對 1004 的 `POST /api/v1/models/load`
（連「與 3.8 並存」那次零擾動嘗試都擋），所以做法 1 要人類跑，或人類明確加一條
Bash 允許規則後由本 session 跑。

## 五、E1 發射條件（最終版，取代 R440C §三.5）

```
PYTHONUNBUFFERED=1 VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions CLINE_KEYS=/nonexistent \
python3 ops/gain/gain_run.py --out runs/g_r441_gemma_only_mbpp --n 179 \
  --seed g-r212-route-20260828 --models gemma-4-12b-it-qat \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0
```
後端條件（明示，決定性 run 沒記錄過）：1004 只載 gemma-4-12b-it-qat，
context_length=32768；快照存 `runs/g_r441_gemma_only_mbpp.backend.json`。
預測沿用 R440 P1–P4 與 R440C P0。

## 六、推翻條件

- 若人類選 3（保留 3.8），本文件 §四.1/2 作廢，E1 改記「硬體不可執行」，
  L1–L5 全部凍結直到 1004 換配置。
- 若卸掉 3.8 後 gemma@32768 仍回「paging file too small」，問題在 Windows 分頁檔
  而非常駐模型，需要人到 1004 前面調（本 session 無 SSH）。

## 七、發射時的實際後端條件（2026-09-02 05:14 UTC 補記，發射前寫定）

- 人類約 05:13 UTC 在 1004 卸掉 qwen3.8；本 session 的唯讀探針隨即觸發 JIT，gemma 以
  LM Studio 預設 **context_length=262144** 載入（不是 §五寫的 32768），hub 探針回 200、
  內容 "OK"。1004 上此刻只有 gemma 一個實例（R440C P0 的「單獨載入」條件成立）。
- **決定：接受 262144，不再卸載重載成 32768。** 理由：(1) 32768 的原意是為了跟 qwen
  並存時塞得下 VRAM，現在卡上只有 gemma，這個理由消失；(2) 決定性 run 的 gemma 從沒
  記錄 context，當時也是 JIT 預設，262144 反而更接近決定性 run 的真實條件；
  (3) 再做一次 unload/load 是對 1004 的額外狀態變更，收益只有「數字跟 §五一致」。
- 這是判斷不是量測。**推翻條件**：若 E1 第一個 20 題檢查點 ON 臂 void 率 >35%
  （R440C P0 失敗），先懷疑 262k 的 KV 預留把 gemma 推到慢速路徑，屆時才值得重載成
  32768 重跑（新 run 名，本 run 保留）。
- 發射指令：`GEMMA_CTX=262144 bash ops/gain/launch_e1.sh all`（prep 會驗到 ctx==262144
  放行；`--probe-sample 0`、`--decision` 指向本文件）。後端快照存
  `runs/g_r441_gemma_only_mbpp.backend.json`。

## 八、第一次發射失敗的事故紀錄與重發條件（2026-09-02 05:35 UTC 補記）

**時間線（hub `/api/events`＋`/api/requests`，UTC）**
- 05:13:35 人類在 1004 卸 qwen3.8；05:13:45 本 session 探針觸發 JIT，gemma 載入（ctx 262144）
- 05:15:23–24 `launch_e1.sh` 探針 3/3 → 200；05:15:27 E1 起跑（PID 2544160），量具 179/179 過
- **05:15:50 vacant-dev（100.124.254.83）向 hub 要 `qwen_qwen3.6-35b-a3b`** → JIT 載 22 GB，
  **05:15:52 gemma 被卸**；05:16:09/05:16:14 E1 preflight 對 gemma → 400 → E1 退出（exited_early）
- 05:16:18 起 vacant-dev 每幾秒打一次 qwen3.6：`ss -tnp` 指到 **迴圈第 4915 輪的 localagent**
  （PID 2544682）。同時 05:12:40 **w1004（100.118.96.3）** 也在向 hub 要 qwen3.8。

**根因兩層**
1. 1004 的 LM Studio **JIT 開著且會為了載新模型卸掉現有模型**：任何人向 hub 要非 gemma
   的模型，gemma 就死。這就是 R440E §一表格第 2 條（審查者的高嚴重度發現）。
2. 迴圈實際讀的 prompt 是 `~/vacant/LOOP_PROMPT.md`（Aug 28 版，195 行），**不是** repo 的
   `ops/LOOP_PROMPT.md`——round440b 的模型政策、平行規則、本 session 的 E1 視窗六條，
   迴圈一條都沒讀到。第 4914 輪（sonnet）照舊版 prompt 寫了 `local`，第 4915 輪就去叫 qwen。

**已做（vacant-dev，人類授權）**：把 repo prompt 的「模型政策／平行實驗規則／E1 視窗」三節
追加到 `~/vacant/LOOP_PROMPT.md`（備份 `.bak_r440j`）；`~/vacant/bin/localagent.py`
`DEFAULT_MODEL` 改為哨兵值 `disabled-during-E1-see-R440J`（備份同名 .bak），hub
`strict_model` 會回 404 讓 local 輪快速失敗退回 sonnet；`NEXT_MODEL=sonnet`。
**未做（分類器擋）**：終止第 4915 輪的 localagent（PID 2544681/2544682）。

**重發條件（缺一不可，人類在 1004 GUI 做）**
1. 終止正在打 qwen 的 local 輪：`ssh user1@100.124.254.83 'kill 2544681'`
2. 1004 LM Studio：Eject `qwen_qwen3.6-35b-a3b` → Load `gemma-4-12b-it-qat`（context 任意，
   預設 262144 即可）→ **關掉 Just-in-Time model loading**（設定裡的 JIT 開關）。
   JIT 關掉後，任何人要 qwen 都只會拿到 404，不會再把 gemma 擠掉；這是唯一能撐 35 小時的狀態。
3. 重發用新名字（原目錄已有失敗 preflight 的 calls/notes，鐵律不刪）：
   `runs/g_r441_gemma_only_mbpp_b` —— 本段文字即為閘門所需的預註冊。
   ```
   cd ~/vacant/Vacant && git pull -q --ff-only origin feat/v2-four-stages && \
   E1_OUT=runs/g_r441_gemma_only_mbpp_b GEMMA_CTX=262144 bash ops/gain/launch_e1.sh all
   ```
   預測、request_policy、`--probe-sample 0` 全部沿用 §五／§七；`runs/g_r441_gemma_only_mbpp/`
   保留為事故證據（1 筆量具 note＋2 筆 preflight 400）。
