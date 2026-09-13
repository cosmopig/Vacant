# DECISION 2026-08-24（round 23）：把 arm_on 的 3 個 reviewer、arm_off5 的 5 個
generate 從併發改成序列送出——併發正在讓這支 run 永遠無法 complete

## 一、量到什麼（`runs/g_onoff5_qwenonly_v2_20260824`，PID 1782584 跑到 round23
開場時：43 筆 `calls.jsonl`、4/60 rows、跑了約 81 分鐘）

review 呼叫（`arm_on` 的 3 個 reviewer，`ThreadPoolExecutor.map` 同時送出）
失敗率：

```
role     total  fail  fail_rate
gen      7      0     0%
revise   4      0     0%
review   30     17    56.7%
```

按 agent 拆開，失敗**不是**集中在單一 agent（5/6 個 review agent 都有失敗）：

```
agent      total  fail
hasty-1    4      2
careful-1  3      0
hasty-2    9      6
plain-1    6      3
careful-2  4      4
plain-2    4      2
```

7 個已處理的 task-row 裡，3 個判 `infra_void`（`mbppplus_Mbpp/283`、`463`、
`734`，全部死因是「reviewer 重試 2 次仍失敗：TimeoutError」）⇒ **infra_void
率 3/7 ≈ 43%**，且round21(33%)→round22(2/6→仍33%持平)→round23(43%)沒有下降
趨勢。

## 二、為什麼這比「跑很慢」嚴重——它會讓這支 run 永遠無法產出判定

`gain_run.py:915`：`"complete": n_void == 0`——這是整個 arm 跑完 60 題之後
**累計**的 void 數，不是某一段窗口。`analyze_onoff5.py:verdict()` 要求
`on.get("complete")` 與 `off5.get("complete")` **都要是 true** 才判定；
`write_summary()` 裡 `equal_budget_valid` 同樣要求兩臂 `complete=true`
(gain_run.py:796-801)。`SPEC_GAIN.md` §112-114 明講這是刻意設計
（「部分臂或部分題的漂亮比例」不能拿來把 `run_complete` 設成 true）,
不是本文要推翻的規則。

問題在於：**只要 60 題裡有任何一題因為併發搶資源而 void，`complete` 就永遠
是 false**，而以目前 33-43% 的單題 void 率外推，60 題全部零 void 的機率
趨近於 0（就算保守估 void 率只有 20%，`0.8^60 ≈ 6×10⁻⁷`）。也就是說：
**照原本的併發寫法，這支 run 不管再跑幾個小時，幾乎確定永遠拿不到
`equal_budget_comparison_valid=true`，criterion 3（等預算的答案）就永遠答
不出來。** 每多等一個小時都是在往一個不會達成的終點多花算力，不是「慢」
而是「跑不到」。

## 三、因果推論：不是選錯 timeout 數字，是併發本身在製造逾時

round12 把 `--review-timeout-s` 訂在 250s（OFF baseline 單發序列呼叫量到
的 p95=205s ~ max=359s 之間）。round22 已經指出：`arm_on` 用
`ThreadPoolExecutor.map` **同時**送出 3 個 reviewer 請求，而端點很可能是
單一 GPU / 單一 LM Studio 實例（非本專案獨占）——client 端「併發」在這種
後端上換不到真正的平行運算，三個請求會在伺服器端排隊。**client 端每個
請求各自的 timeout 時鐘，從送出那一刻就開始跑**，所以隊列裡排第二、第三
的請求，即使它自己真正被處理的時間很短，也可能因為在隊列裡空等就先撞牆。

round23 新增的證據支持這個機制推論，而不是「單一 reviewer agent 特別慢」
的另一種解釋：失敗分布在 5/6 個 agent，沒有一個 agent 是 0% 或 100%
失敗——如果是某個 agent 本身有問題（例如某個模型家族特別慢），失敗應該
高度集中在那一個 agent，而不是均勻散布。

`arm_off5` 的 k=5 generate 呼叫用同一種
`ThreadPoolExecutor.map` 併發送出（`request_timeout_s=600`，比 review 的
250s 寬鬆，但 5 個併發比 3 個併發排隊更久，且尚未實測，因為 OFF5 排在
ON 之後才跑）——同一個機制、同一個後端，沒有理由它會倖免。

## 四、決定：兩處都改成序列送出，不改 timeout 數字、不改判準

`ops/gain/gain_run.py` 的 `arm_on()`（reviewer 迴圈）與 `arm_off5()`
（generate 迴圈）都把 `ThreadPoolExecutor.map` 換成單純的
`[f(x) for x in xs]` 序列呼叫。

**為什麼是序列化，不是調大 timeout 或放寬 `complete` 定義：**

1. **放寬 `complete` 的定義違反 SPEC_GAIN.md §112-114 的明文規則**——那是
   為了防止「漂亮比例」污染完整率判定而刻意寫的，不是本文要動的範圍。
2. **調大 timeout 治標不治本**：如果併發排隊的因果推論成立，光是拉高
   `--review-timeout-s` 只會讓每一題卡更久才判 void，不會降低 void 發生的
   機率（隊列裡最後一個請求還是要等前面兩個處理完，時間拉長只是把懸崖往
   後移，不是拆掉懸崖）。
3. **序列化不需要新旋鈕**：不增加任何新的可調參數，也不改變任何既有判準
   的門檻值——純粹是「怎麼送出既有的 3/5 個呼叫」的實作細節，跟
   `holefill2.py --blockset`（展件那邊的教訓）是同一種「先問能不能直接
   拆掉問題本身」的做法。
4. **序列化理論上不會顯著拉長總耗時**：如果後端本來就是單線程排隊處理，
   3 個併發請求排隊等待的總時間，跟依序送出 3 個請求各自處理的總時間，
   理論上該收斂到同一個數字——差別只在於併發時每個請求都背著從 t=0 開始
   倒數的 timeout（容易撞牆），序列時每個請求的 timeout 從它真正開始處理
   時算起（不容易撞牆）。**這一點本文只給出推論，沒有拿序列化後的資料驗證
   —— 下一輪要用重跑的資料回頭核對「序列化後總 wall_s 有沒有顯著變長」，
   如果變長很多，代表因果推論有缺漏（例如後端其實有一定的平行處理能力，
   序列化反而浪費掉），要回來重新檢討。**

**主要比較指標不受影響**：`correct_delivery_rate` 與 `calls_per_task` 看的
是 `calls_used`／`meets_demand`，不是呼叫送出的時序；序列化改變的只是
「這一題的 review 階段花多少牆鐘時間」，不改變審查本身的內容或判定邏輯。

## 五、代價與已知風險（照實寫，不留到下一輪才發現）

- **OFF5 的序列化改動完全沒有實測資料支持**——本文是用「同一個後端、同一種
  併發機制」的推論預先修的，不是量到它失敗才修。這違反「先量再改」的一般
  原則，是本輪刻意的例外，理由是：等到 OFF5 真的開始跑、真的觀察到同一個
  問題，會是又一次數小時等級的浪費，而修法在邏輯上與 review 那邊完全對稱，
  風險判斷上值得先做。**下一輪 OFF5 開始跑之後，要專門核對它的 infra_void
  率有沒有跟 review 一樣的問題被序列化壓下去**，不能假設它一定有效。
- **`calibrate_pool()`（`gain_run.py:582`）還有第三處同款
  `ThreadPoolExecutor` 併發呼叫**，本文沒有動它——目前這支 run 的指令沒有
  `--calibration-n`，這條路徑不會被觸發，改了也驗證不到。留給真的要跑
  calibration 的那一輪處理，不在這裡先斬後奏動一個測不到的東西。
- **序列化會讓 ON 手臂的 wall_s 變得比 OFF5 更不利**（round22 §三已經預見
  這個副作用）：ON 從 3 個 reviewer 併發等待，變成 3 次依序等待，總 review
  階段耗時可能上升（即使排隊時間本身不變，序列化少了「後面的請求在等待期間
  搭前面請求的順風車」這件事——如果後端其實有一點點平行處理能力，序列化就
  是實打實的浪費）。**這件事只影響 wall_s／完成這支 run 需要的時間，不影響
  `correct_delivery_rate` 或 `calls_used` 這兩個主要比較指標**（round22 §三
  的論證在序列化之後依然成立），因此判斷「不改變正在被比較的東西本身」——
  但如果人類後續在意展示或報告 ON 的實際牆鐘成本，這是一個要交代的副作用。

## 六、這份決定什麼條件下該被推翻

- 若重啟後的新 run 量到序列化並沒有降低 infra_void 率（例如還是撞牆，
  只是撞牆位置從「排隊中」變成「真正處理中」）⇒ 表示因果推論錯了，
  併發不是主因，要回頭找別的原因（例如端點本身有速率限制、或
  `request_timeout_s`/`review_timeout_s` truly 不夠長）。
- 若序列化後 `wall_s` 大幅超出「排隊等待時間不變」的預期（例如變成原本的
  2-3 倍以上）⇒ 代表後端其實有一定平行處理能力，序列化是不必要的犧牲，
  要重新評估是否該退回併發＋改成更高的 timeout。
- 若 OFF5 開始跑之後完全沒有 void（甚至併發版本可能也不會 void）⇒
  §五第一點的「預先修」判斷應被記錄為「不必要但無害」，不用回退，
  但要更新這份文件承認預判過度謹慎。

## 七、本輪採取的行動（順序）

1. 診斷（本文第一、二節）。
2. 改 `ops/gain/gain_run.py`：`arm_on`／`arm_off5` 序列化，移除已死的
   `threading.Lock`／`import threading`。
3. `--arms probe` 快速驗證改動沒有破壞既有的量具驗證路徑（不需要模型呼叫）。
4. **kill PID 1782584**（舊的併發版本，已跑 81 分鐘、7/60 完成度）——
   保留 `runs/g_onoff5_qwenonly_v2_20260824/` 全部既有產物，不刪除、不覆寫
   （鐵律 3：不刪任何 run 目錄）。這支 run 的 `run_complete` 永遠是
   `false`，它的價值變成「證明併發假說」的診斷資料，不是等預算比較的來源。
5. 用新的 `--out runs/g_onoff5_qwenonly_v3_20260824`（同 seed、同題序、同
   models、同 timeout 參數）重新啟動，套用序列化後的程式碼。
