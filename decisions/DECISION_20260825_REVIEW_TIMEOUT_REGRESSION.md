# DECISION 2026-08-25（round 123）：`--review-timeout-s` 在 371 題長跑中掉了，13 小時的 ON 資料作廢重跑

**寫這份文件的時刻**：已經 kill 掉 `g_on371_20260825`（PID 1849859，跑了
13:15:16、167 rows），已經用補回旗標的參數啟動
`g_onoff5_371_r123_20260825`（PID 1875845），本文寫於確認新行程
量具 371/371、preflight 過關、`request_policy.review_timeout_s=250` 生效之後。
**舊目錄 `runs/g_on371_20260825/` 原樣保留，一個 byte 都沒刪。**

## 一、先訂判準（在看任何數字之前就該成立的規則）

round122 交棒要 opus 判斷「b 恆為 3、c 單調上升 7→10、required_n 首度
跌破容量」算不算真發現。判斷規則寫在前面：

- **配對檢定的證據單位是 discordant pair，不是 paired point。** 拿
  「新增 36 個配對點」當證據量是錯的分母。
- **從觀測效應反推的 required_n 是 p 值的單調重述**（post-hoc power
  謬誤），`answerable_within_capacity` 翻 true 不是獨立的新資訊。
- **累積讀數不是獨立觀察。** 同一份會長大的資料讀 6 次，不等於 6 個證據。

## 二、round122 的「新發現」不成立（本輪訂正）

照 ON 完成順序把 13 個 discordant 事件逐一列出（`accepted and meets_demand`，
與 `analyze_fullbank_off.py` 同定義）：

```
n_common時  task_id            誰贏       b   c
     1      Mbpp/450           ON_only    0   1
     3      Mbpp/111           OFF_only   1   1
     7      Mbpp/726           OFF_only   2   1
    21      Mbpp/777           ON_only    2   2
    92      Mbpp/273           OFF_only   3   2
   105/106/113/115/124/128/148/160  全 ON_only   3   3→10
```

round115（n=127）之後**新增的 discordant 事件只有 3 個**（不是 36）。
3 個同方向在虛無假設下 P=1/8=0.125（單尾）——**這不是證據**。而且這 3 個
事件的資訊**已經完全包含在 `exact_mcnemar_p=0.0923` 裡**，沒有任何額外訊息。

我自己驗了工具沒錯：b=3,c=10 ⇒ 雙尾 exact 二項
`2×(1+13+78+286)/8192 = 756/8192 = 0.092285`，與工具輸出逐字元相同。
**工具是對的，是上一輪的讀法錯了。**

## 三、真正的問題：ON 的 infra_void 有 30%，而且**挑難題 void**

| | 嘗試 | 完成 rows | infra_void | void 率 |
|---|---|---|---|---|
| OFF（`g_off371`） | 371 | 367 | 4 | **1.1%** |
| ON（`g_on371`） | 237 | 165 | 72 | **30.4%** |

決定性檢定——**用 OFF 臂當難度尺**（OFF 對這 371 題全部有成績，
包含 ON void 掉的那些）：

```
ON 完成的 166 題 → OFF 正確 139/166 = 0.8373
ON void 的  69 題 → OFF 正確  48/69  = 0.6957
難度差 = +14.17 pp    Fisher 雙尾 p = 0.0203
```

**ON void 掉的題目顯著比它完成的題目難。** 拆原因後訊號集中在逾時：

```
Timeout   n=54  這些題在 OFF 的正確率 = 0.647   ← 挑難題
HTTP 400  n=17  這些題在 OFF 的正確率 = 0.824   ← 與基線持平，難度中性
```

## 四、根因：一個已經修好的 bug 被改回去了（不是新 bug）

各 role 的實測延遲（`calls.jsonl`，成功呼叫）：

```
role      成功n     p50     p90     p95     p99     max   timeout_s
gen         228    46.0    92.8   118.4   158.2   237.4       600
review      531    31.9    50.6    55.2    59.6    60.0        60   ← 硬右設限
revise      166    45.3    72.3    76.0   101.3   102.6       600
```

`review` 失敗 145/674 = **21.5%**，而且 145 通失敗的延遲**全部落在
23.4–60.1s**＝全部貼在 60s 上限。成功的 review 在 50–60s 那一格還有
55 通——分佈明顯被切掉，不是自然收斂。

死掉的行程的完整指令（`/proc/1849859/cmdline` 讀出）：

```
python3 ops/gain/gain_run.py --out runs/g_on371_20260825 --n 371 \
  --seed g-smoke-20260820 --arms ON --probe-sample 0 \
  --models qwen/qwen3.6-35b-a3b --request-timeout-s 600
```

**沒有 `--review-timeout-s`** ⇒ 吃預設 60。run 自己記的
`summary.json:request_policy.review_timeout_s = 60` 也印證。

這正是 `DECISION_20260824_REVIEW_TIMEOUT_BUG.md`（round 12）**前一天就
診斷過並修好**的同一個 bug：60 是 cline 官方端點時代的常數
（`gain_run.py:679` 註解「clinepass-clean-v2 的死因修復」），換到 8765
中轉之後沒重新校準。那一輪已經改用 `--review-timeout-s 250` 重跑。
**這次啟動 371 題長跑時旗標沒帶上，修復被靜默地丟掉了。**

round 12 那份文件 §5 寫的推翻條件是「若 infra_void 依然大量出現（>10% 擋門）」
——**現在 30.4%，條件成立**。`gain_run.py:752` 的註解也記著同一個
30%（18/60）指紋。

**為什麼沒被擋下來**：10% 那道 infra_void 擋門在
`DECISION_20260824_OFF_BASELINE.md` §3 的判決表裡，是**分析時**的門檻，
runtime 不會 abort。所以這支 run 可以安穩燒 21 小時，最後才在判決表被
整臂作廢。這是流程缺口，不是誰失職。

## 五、為什麼舊資料不能靠「跑更多題」或「用 bounds」救回來

配對檢定在**存活下來的子集**上內部效度沒問題（兩臂同題）。壞掉的是
另外兩件事，兩件都不是加大 n 能解決的：

1. **分母不對，而這正是人類鐵律第 2 條要守的。** review 逾時發生在
   Vacant 機制**內部**——評審答不出來就是 Vacant 沒交付。把它記成
   「這一格沒量到」，等於**讓 ON 可以對 30% 的題目不作答、只被拿有作答的
   那些打分，而 OFF 作答了 99%**。
2. **全題庫估計的 bounds 已經寬到沒有資訊。** 以 235 題共同集計：
   OFF 正確 187/235 = 0.796；ON 最壞（69 個 void 全記失敗）= 145/235 = **0.617**，
   最好（全記成功）= 214/235 = **0.911**。真值區間 [0.617, 0.911] 把 OFF 的
   0.796 包在中間 ⇒ **這支 run 在任何 n 下都答不出三臂比較。**

## 六、做了什麼

1. `--arms probe` 量具雙向驗證（零模型呼叫，可與線上 run 併行）：
   **參考解通過 371/371、壞解被擋 371/371**，兩個方向滿分
   （`runs/g_probe_20260825_r123`）。
2. `kill -TERM -1849859`（process group），確認死亡、確認沒有第二支
   gain_run 在跑。**舊目錄保留**（167 rows／1089 calls／73 notes）。
3. 重啟，補回旗標，換新目錄：

```
setsid nohup env \
  VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
  VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
  CLINE_KEYS=/nonexistent \
  python3 ops/gain/gain_run.py \
  --out runs/g_onoff5_371_r123_20260825 --n 371 --seed g-smoke-20260820 \
  --arms ON,OFF5 --probe-sample 0 --models qwen/qwen3.6-35b-a3b \
  --request-timeout-s 600 --review-timeout-s 250 \
  > runs/g_onoff5_371_r123_20260825.log 2>&1 < /dev/null &
```

啟動後實測：量具 371/371 兩向、模型池預檢 ✓、
`request_policy.review_timeout_s = **250**`（生效）、
`[ON 1/371] 需求符合=True 接受=True 累計呼叫=5`。

## 七、這一輪改動的實驗條件（照實登記）

- **`--review-timeout-s` 60 → 250。** 這是實驗條件的改變，不是 bug-fix 就
  可以不記。**250 不是本輪新挑的**，是沿用 round 12 已經定案的值；本輪只
  補做了 round 12 §5 要求但當時做不到的事：**直接量 review 呼叫自己的分佈**
  （之前只能拿 gen 當代理）。結果支持 250：review 的無設限上界可用 gen 代理
  （review 的 prompt 與輸出都比 gen 短），gen 實測 max=237.4s，
  **0/228 通超過 250s**。250 覆蓋整個已觀測分佈仍保持有界
  （worst case 2×250+backoff ≈ 502s/reviewer）。
- **`--arms` 從 `ON` 改成 `ON,OFF5`**：不是為了好看，是為了保證 ON 與 OFF5
  的 `request_policy` 逐字相同（等預算比較是人類鐵律第 1 條的核心），
  並免除未來某一輪漏啟動 OFF5 的風險。**注意 `gain_run.py:836` 是
  `for arm in arms` 外層迴圈 ⇒ 兩臂是先後跑完、不是交錯**，所以這樣做
  **沒有**買到時間配對，只買到設定一致與流程可靠。
- **沒有改任何 `ops/gain/*.py` 程式碼**、沒有改判準、沒有換題庫、沒有換
  worker 池、沒有動 seed 與題序。

## 八、什麼條件下這份決定該被推翻

- **新 run 的 review 失敗率若沒有明顯低於 21.5%**，代表 60s 不是主因，
  問題在中轉本身的結構性壅塞——那時不該再加大 timeout（已逼近 gen 的
  max=237.4s），而要重新檢討這個共用中轉適不適合跑數十小時等級的實驗。
- **新 run 的 infra_void 若仍 >10%**，同上，且要重新檢查 HTTP 400 那一支
  （17 題，本輪判定為難度中性、未處理；若佔比升高要單獨查，很可能是
  context length 超限而不是網路問題）。
- **若 void 率降下來之後 ON 對 OFF 的落差也跟著消失**，那就是本輪這份
  分析預測的結果之一（存活者偏誤原本在灌水），**要照實寫成「Vacant 在
  這個題庫上沒有可測增益」，不准回頭去找別的切法**。
- 本輪**不能**把 `g_on371_20260825` 與 `g_onoff5_371_r123_20260825` 的資料
  混算同一臂——實驗條件（review timeout）不同，混算會污染等預算比較。
  這條沿用 round 12 §5 的同一條紀律。

## 九、成本

殺掉的是 13 小時 15 分的 ON 資料（167 rows）。**沉沒成本是真的，不粉飾。**
但第五節已經證明那 13 小時在任何 n 下都答不出問題，繼續跑完剩下的
~8 小時再接 OFF5 的 ~23 小時，只會把一個答不出來的結論跑得更貴。
新 run 全部 $0（本機中轉）。預估 ON ≈ 20 小時、OFF5 ≈ 23 小時，
兩臂合計約 43 小時，會橫跨多輪 loop——**這是背景行程，不綁在任何一輪裡。**
