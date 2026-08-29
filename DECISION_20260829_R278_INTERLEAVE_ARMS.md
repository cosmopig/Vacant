# 2026-08-29（round278, Opus 5）：實作 round138 交棒但 140 輪沒人做的 arm 交錯；順帶把 240s review deadline 依 n=36 的分佈重訂

## 被叫來判斷什麼

round277 交棒的問題是「review 逾時率三個時間點都 >10%，
`DECISION_20260829_REVIEW_TIMEOUT_TOO_SHORT_FOR_HET_POOL.md` 的推翻條件
算不算觸發」。**答案是：字面上觸發了，但它保護的東西沒有受損；而同一份
DECISION 的第二條推翻條件（沒人查過的那條）才是真正觸發的那條。**

---

## 量到什麼（原始數字，不是轉述）

`runs/g_het2_r274_20260829`，開場 etime 01:59:50，rows 6→8。

### A) review 逾時率＝10.7%（28 次呼叫 3 次失敗），但**零資料損失**

```
role=review agent=plain-2   model=gemma-4-12b-it-qat   attempt=1 timeout_s=240 latency=240.1s
role=review agent=plain-1   model=qwen/qwen3.6-35b-a3b attempt=1 timeout_s=240 latency=240.0s
role=review agent=careful-1 model=qwen/qwen3.6-35b-a3b attempt=1 timeout_s=240 latency=240.1s
```

三筆全部 attempt=1、latency 貼齊 240s ⇒ 是真逾時（對照
`DECISION_20260826` 判斷 1 的教訓：latency 沒貼齊 timeout 的那種
不是逾時，是 `finish_reason=length`，調 timeout 是錯的旋鈕。這次貼齊了，
**timeout 確實是對的旋鈕**）。

但逐列查 `rows.jsonl`：**8 列每一列都拿到剛好 3 票**
（`votes per row = [3,3,3,3,3,3,3,3]`），`infra_void=0`。
retries=2 把逾時全部吸收掉了。

⇒ **逾時是「時間稅」不是「資料損失」。** r271 那次是 6/6 列全滅
（infra_void），這次是 0 列受損。兩者差一個數量級，不該用同一個門檻詞
（「顯著」）帶過。原 DECISION 寫的 `>10%` 是拿逾時率**當資料損失的代理量**；
現在直接量得到資料損失本身（0），代理量就不該再當判準用
——這正是記憶裡那條「代理量會被修復動作改寫就不是判別量」的同型情況。

### B) 為什麼是 ~10%——不是運氣，是 240s 剛好坐在 p90 上

`calls.jsonl` 按 role/model 拆（成功呼叫的延遲分位數）：

```
role         model                        n   ok  fail%   p50 /  p90 /  max (秒)
calibration  qwen/qwen3.6-35b-a3b        36   36   0.0%  102.4 / 230.5 / 252.0
calibration  gemma-4-12b-it-qat          36   36   0.0%   12.0 /  19.6 /  20.9
gen          qwen/qwen3.6-35b-a3b         2    2   0.0%  153.1 / 153.1 / 153.1
review       qwen/qwen3.6-35b-a3b        11    9  18.2%   90.3 / 204.7 / 204.7
review       gemma-4-12b-it-qat          11   10   9.1%    7.3 / 129.1 / 129.1
```

**qwen 的 p90 = 230.5s、max = 252.0s。240s 這條線落在 p90 與 max 之間。**
把 deadline 放在 p90 上，每次呼叫約 10% 逾時是**算得出來的必然**，
不是長尾異常。

原 DECISION 選 240s 的理由是「比目前觀測到的 qwen 最大延遲 161s 留有安全
邊界」——那個 161s 是從 **n=7 次 gen 呼叫**估的。現在 calibration 給了
**n=36**，max 是 252s。**參數沒選錯，是當時的樣本太小。**

### C) 真正觸發的是第二條推翻條件（140 輪沒人算過）

原 DECISION 的第二條：「如果單題總耗時暴漲導致 n=179 在合理時間內跑不完」。

```
ON 臂：8 列 / 40.1 分鐘（gen+review+revise 呼叫的時間跨度）= 6.7 分鐘/列
       179 列 ⇒ 20.0 小時
OFF5 ：參照 runs/g_het2_r263_20260829 的 OFF（wall_s=9783.2s / 179 列 = 54.7s/列，
       1 呼叫/列）× 5 呼叫 ⇒ 約 4.6 分鐘/列 ⇒ 179 列 ⇒ 13.7 小時
合計 ≈ 33.7 小時
```

---

## 判斷 1：真正的缺陷是 arm 順序，而它 140 輪前就被寫成規格了

`ops/gain/gain_run.py:890` 仍然是 `for arm in arms:` 外層、
`for i, t in enumerate(tasks)` 內層。

**`DECISION_20260826_PAIRED_ANALYSIS_AND_ARM_ORDER.md`（round138, Opus）
的「判斷 4」已經把這件事查清楚、寫成規格、交棒——然後 140 輪沒有人實作。**
round138 當時算的是同一件事的另一個 run：「第一列 OFF5 還要等 302 列 ON
≈ 22 小時」。今天 r274 是「第一列 OFF5 要等 179 列 ON ≈ 20 小時」。
**同一個缺陷、同一個代價、隔了 140 輪又發生一次。**

後果具體是：**r274 在第 20 小時之前被中斷的話，OFF5 資料是零**，
而 OFF5 是唯一能回答判準 3（等預算下 ON 打不打得贏 self-consistency）的臂。
這不是假想——r271 在 1h49m 被中止、`g_onoff5_371_r123_20260825` 也是中途停的。
歷史上這個 run 家族**被中斷過的次數比跑完的次數多**。

## 判斷 2：交錯在統計上是免費的——這次是**量到的**，不是論證

round138 用讀碼論證過（tasks 在 arm 迴圈外建一次、每臂各一顆 rng/rep/calls、
`grep "random\." | grep -v rng` 為空）。本輪把它**跑出來驗**：

離線確定性樁（`/dev/shm/eqtest/fake_server.py`，固定回應、不碰中轉、
不干擾線上 run），同 seed 同題序，舊碼與新碼各跑 `--arms ON,OFF5 --n 8`：

```
舊碼執行序：ON1..ON8, OFF5_1..OFF5_8
新碼執行序：ON1, OFF5_1, ON2, OFF5_2, ... ON8, OFF5_8
逐格比對 (arm, task_id) → 16 格
  抽樣欄位（worker/involved/responsible_agent/votes/...）不符：0
  整列比對（僅忽略執行序 i）不符：0
```

**16 格全部逐欄位相同。**

### 植入缺陷測試（否則上面的綠燈沒有意義）

把「每臂各一顆 rng」改成「兩臂共用一顆 rng」——這在循序版看起來人畜無害，
在交錯版一定會改變抽樣：

```
cells: 16   sampling mismatches vs sequential baseline: 44
VERDICT: FAIL-as-required（測試有牙齒）
  ('OFF5','mbppplus_Mbpp/162') worker 舊=careful-2 壞=plain-1
```

⇒ 比對確實抓得到真的分歧，所以 0 不符是有意義的綠燈。

## 判斷 3：交錯會讓一個舊 bug 變成可觸發的，必須同時修

循序版的 `complete` 判準是 `n_void == 0`，這在循序版夠用——因為
`summary[arm]` 只在該臂整個題目迴圈跑完之後才寫一次。
**交錯版每跑完一題就重寫 summary ⇒ 一個才跑到第 2 題、還沒遇到 void 的臂
會被寫成 `complete=True`。** 這正是程式碼註解裡記的 round224 同型錯誤
（`run_complete` 說跑完了、其實一格都沒量到）。

改成 `n_void == 0 and processed == len(tasks)`，並新增 `processed` 欄位。
植入缺陷測試（n=200 跑 45 秒後砍掉）：

```
新碼        ON: processed=3/200 infra_void=0 complete=False   ← 對
拿掉守衛    ON: processed=2/200 infra_void=0 complete=True    ← 錯，且會騙到後面每一輪
```

其他隨交錯一起改的語意（照實記，不是無痛）：
- `wall_s`：循序版是 `t_end - t_start`；交錯版兩臂在時間上交纏，這個定義失效。
  改成**逐格累加該格實際耗時**＝該臂的作用時間。循序版兩者幾乎相同，
  交錯版只有累加版有意義。**跨 run 比 `wall_s` 時要知道定義換過。**
- `cost_usd`/`market_cost_usd`：循序版用臂前後快照相減；交錯版改成逐格累加
  差額（等價且交錯下才正確）。
- `endpoint_latency_ms`：`latency_summary()` 是按 `meta.arm` 濾的，
  與執行順序無關，不受影響。

## 判斷 4：review deadline 240s → 380s，用同一條規則、換成更好的樣本

不是「因為觸發門檻所以調高」，是**原決策的選值規則套在 n=36 上會得出不同的值**：
原規則＝「高於觀測到的 qwen 最大延遲，留安全邊界」。
- 當時：n=7，max=161s ⇒ 選 240s（+49%）
- 現在：n=36，max=252s ⇒ 同樣 +50% 邊界 ⇒ **380s**

預期時間影響接近中性（逾時的那 10% 從「等 240s 再重試一次」變成「等一次就成功」），
但完整性嚴格較好。380 仍遠低於 `request_timeout_s=600`。

**壞處照實寫**：單題 review 階段最壞情況從 3×2×240=24 分鐘變成 3×2×380=38 分鐘。
三個評審全部逾時兩次的機率極低，但這個尾巴確實變長了。

### 這算不算「挑對自己有利的設定」

不算，而且要說清楚為什麼：這個參數**只影響 ON 臂**（OFF/OFF5 沒有 review 呼叫），
所以它不是中性的。但它影響的方向是「ON 臂的評審意見更完整地被收集到」，
不是「ON 臂的答案變好」——評審逾時被 retry 吸收之後，票數本來就是 3/3
（實測 8/8 列都是 3 票）。**改這個參數不會改變任何一票的內容**，
只會減少為了拿到那 3 票而浪費的 240 秒。
若之後量到 ON 的表現隨 deadline 改變，那才是要回頭懷疑這條的訊號。

## 判斷 5：n 維持 179，且**事前**寫死不准看結果決定停

交錯之後任何時刻中斷都留下兩臂格數相等的可分析資料——這會讓「看一眼再決定
停不停」變得很誘人，那就是 optional stopping／p-hacking。

**事前約定：不因為結果好看或難看而提早停。** run 跑到完，或被外力
（機器、額度、人類）中止；分析時照實報當下的 n。
n=179 對 OFF 基準率 72.3% 而言約可偵測 13pp 的差異（雙比例、80% 檢定力）；
若最後只跑到 n=60，可偵測差異約 22pp——**這要寫進結論，不能只報 p 值。**

---

## 決定

1. `ops/gain/gain_run.py` 改為 `for task: for arm:` 交錯，
   per-arm 狀態收進 `st` dict，`finalize(arm)` 可隨時呼叫，
   每跑完一題重寫一次 `summary.json`。
2. `complete` 加上 `processed == len(tasks)` 守衛，新增 `processed` 欄位。
3. 中止 r274（PID 2180613）。**產物一格不刪**，原樣 commit
   （8 列 ON、119 行 calls、完整 calibration）。
4. 用新目錄 `runs/g_het3_r278_20260829` 重跑，`--review-timeout-s 380`，
   其餘參數與 r274 完全相同（同 seed、同池、同 n）。
   calibration **重新量**（12 題×6 agent），不沿用 r274 的數字。

### 成本，照實寫

重跑要付 calibration 約 76 分鐘（r274 實測 08:11→09:27）＋丟掉 8 列 ON
（約 54 分鐘）＝**約 2.2 小時**。換到的是：第一列 OFF5 從第 20 小時提前到
第 1 小時內，以及此後任何時刻中斷都有兩臂平衡的資料。
**重跑並不會讓整個 run 更早跑完**（總工作量不變，仍約 34 小時），
它買的是「中途被砍也拿得到答案」，不是速度。

## 什麼條件下這個決定該被推翻

- 交錯之後若 `rows.jsonl` 出現兩臂格數持續不相等（差 >1），代表交錯迴圈有
  bug，回去看 `st` 的狀態隔離。
- 380s 之後 review 逾時率若**仍 >10%**，代表 qwen 延遲的長尾比 n=36 看到的
  還長，那時候該做的**不是再往上調**（已經調過兩次、每次都是追著分佈跑），
  而是承認 qwen 在這個中轉上不適合當 reviewer，改回同質池並接受
  `DECISION_20260829_R260_POOL_HOMOGENEITY_CEILING` 的天花板。
- 若 380s 讓單題耗時中位數明顯上升（ON 從 6.7 分/列升到 >9 分/列），
  代表「時間中性」的預估錯了，要回頭重估。
