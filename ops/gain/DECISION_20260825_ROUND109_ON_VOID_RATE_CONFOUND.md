# DECISION 2026-08-25（round 109）：g_on371 的 infra_void 率是 32%，不是「0」——之前 4 輪讀錯了，而且這可能是結構性混淆，不是機制訊號

## 一、開場先發現交接檔本身斷輪

`~/vacant/GAIN_STATE.md`（不在 git）最後一段是 round83（04:16–04:3x UTC）。
但 `git log` 顯示 round84–108 都確實發生過（每輪一個 commit，訊息完整），只是
**沒有人把它們寫回 `GAIN_STATE.md`**——round96 的 commit message 裡寫了一句
「GAIN_STATE.md pushed separately (not tracked in this repo)」，但實查
`~/vacant` 根本不是 git repo，這句話不成立，之後 12 輪都沒人發現也沒人補寫。
本輪先把 round84-108 的摘要補回 `GAIN_STATE.md`（見該檔本輪段落），
不在此文件重複。

## 二、本輪要處理的主發現：ON 臂的 infra_void 率是 32%，不是「0」

round96／round104／round106／round107 的 commit message 都寫「0 infra_void」
或未提及 void，暗示乾淨。**這是錯的。** 用與 round94 對 `g_off371` 完全相同的
方法（`notes.jsonl` 裡帶 `infra_void` 鍵的 `task_id` 集合，減去同一 `task_id`
是否也出現在 `rows.jsonl`——重疊為 0 才是真的「void 沒有變成一筆結果」）
重新量測兩個 run：

```
runs/g_off371_20260825   void=4   rows=367  overlap=0  attempted=371  void_rate=1.08%
runs/g_on371_20260825    void=46  rows=96   overlap=0  attempted=142  void_rate=32.39%
```

`overlap=0` 對兩邊都成立，證明這不是我的量測方法本身有 bug（若有重疊，
代表某個 task 明明有 row 卻被我誤判成 void，兩邊都應該出現才對稱；
`g_off371` 的 1.08% 與 round94 原文的「void_gate 1.08%」逐字元相同，
方法本身已被獨立驗證過一次）。

**void 事件在時間軸上是均勻分布，不是本輪剛爆發**（用 `calls.jsonl` 的
`ts_ms` 找每個 void task 最後一次相關呼叫的時間戳，按 10 分鐘分桶）：
從 09:30（run 剛啟動）到 17:00（本輪），幾乎每個 10 分鐘窗口都有 1–3 個
新 void task，沒有明顯的「某個時間點突然變差」的斷點。**結論：不是本輪
發生的新事故，是整個 run 從頭到尾都帶著這個底噪，只是 round96/104/106/107
沒有正確量到。**

### round96/104/106/107 為什麼會讀成 0？

四輪的 commit message 都只提到 `rows.jsonl` 的內容（err 分布、accepted
筆數），沒有一輪明確寫出檢查 `notes.jsonl` 用的指令。合理推測是用了
類似「`grep infra_void rows.jsonl`」或只讀 `rows.jsonl` 的 `err` 欄位
——這兩者都結構性讀不到 void，因為**被判為 void 的任務定義上不會寫進
`rows.jsonl`**（本輪驗證 overlap=0 就是在確認這件事：void task 完全不出現
在 rows 裡，所以只查 rows 永遠是 0）。這是本輪唯一能複現的解釋，
不是機械證明（沒有拿到那四輪實際打的指令），**照實記為推測**。

## 三、這可能不是「Vacant 比較差」，是呼叫數本身在製造混淆

`g_on371` 每題最多 5 次模型呼叫（worker + 審查 + 修訂），`g_off371` 每題 1 次。
本輪同時量了兩邊的**逐次呼叫**失敗率（`calls.jsonl` 的 `ok` 欄位，非任務級）：
`g_on371` 全程逐次呼叫失敗率約 15%（634 次呼叫、97 次失敗，10 分鐘分桶
在 0–55% 間跳動，沒有單一時段特別差）。若 5 次呼叫近似獨立、單次呼叫在
「4 次重試後仍失敗」的機率是 p，任務級 void 率理論上是 `1-(1-p)^5`——
用觀測 void 率反推 `p ≈ 1-(1-0.3239)^(1/5) ≈ 0.075`（約 7.5%），與逐次失敗率
15% 同量級（重試會把單次 15% 壓低到約 7.5% 才耗盡），量級吻合，
**支持「void 率隨呼叫數結構性放大」這個機制解釋，而不是 ON 臂特別倒楣**。

**這件事對 round83 的決定性實驗有多重要**：round83 把 OFF-vs-ON 定為「答得出
且不必改實驗條件」的實驗，前提是兩臂的資料品質對等。若 void 率因為呼叫數
不同而系統性偏向 ON 臂（30 倍差距），且 void 若與題目難度相關（round83 §8
本來就懷疑這件事，當時 OFF 只有 4 個 void 樣本不夠測；ON 現在有 46 個，
夠測了），**倖存下來的 96 題 ON 資料可能不是隨機子集，而是「恰好 5 次呼叫
都沒被这個不穩端點卡住」的子集**——這與「Vacant 機制好不好」無關，
是純基礎設施問題滲入比較。

## 四、依既有規則，這個 run 現在算「未完成／不可直接當乾淨比較」

round75 定的規則原文：「若 ON/OFF5 跑到一半 infra_void 大量出現（端點不穩）
⇒ 停止硬等，比照 OFF baseline 的擋門邏輯（>10% 記 incomplete）」。
`32.39% > 10%`，觸發。**本輪動作**：

- **不 kill 這支 run**——它仍在產生資料，且已經是唯一一份「呼叫數放大
  void 率」的直接證據來源，殺掉就沒有樣本可以驗證上面的假說。
- **不再做本輪內的封鎖式等待**（round85-108 用的 `timeout 540 tail --pid`
  模式，本輪判斷在 32% void 率、且已經找到需要人判斷的結構性問題時，
  繼續硬等只是燒時間，不會產生新判斷）。
- **把「run_complete=true 才做正式讀出」這條既有規則加一個前提**：
  即使 371/371 跑滿，**在檢查「void 是否與題目難度相關」之前，
  不能把 OFF-vs-ON 的差異直接歸因於 Vacant 機制**——因為呼叫數本身
  就是混淆變數。round83 §8 的難度檢查工具（`analyze_void_difficulty.py`）
  現在對 ON 臂有 46 個樣本可用（原本 OFF 只有 4 個，round94 判 insufficient_data
  是對的；ON 現在夠了），**下一輪第一件事應該是對 `g_on371` 跑這個檢查**。

## 五、本輪追加：對 34 個 timeout／12 個 http_error void 做了難度代理量檢查（結果：假說不成立）

寫完上面四節後判斷「等下一輪再查」成本比「現在就查」高（工具已經在手上、
只是需要繞過它的一個限制），所以本輪就把問題查完了，沒有留給下一輪。

**`analyze_void_difficulty.py` 原樣跑在 `g_on371` 上會失真**：它的
`measured_task_ids` 寫死只抓 `arm=="OFF"` 的 row（`analyze(...)` 函式
`off_rows = [r for r in rows if r.get("arm") == "OFF"]`）——這是為
`g_off371`（OFF-only run）設計的，原樣套在 ON-only 的 `g_on371` 上
`n_measured=0`，四個分類全部 `insufficient_data`，不是真的沒差，是
根本沒比到東西。而且它只檢查 `finish_reason=length` 這一種 void
（round83 §8 原始假說的目標），`g_on371` 的 46 個 void 裡 0 個是這型，
34 個是 `TimeoutError`、12 個是 `HTTPError`——**主要 void 型態工具完全沒覆蓋**。

沒有改動 `analyze_void_difficulty.py` 本身（它對 `g_off371` 仍然是對的
工具，不動它），改用同一套 `compare()` 邏輯（percentile rank vs 已完成題目
的 `prompt_len`／`hidden_test_count`／`canonical_lines` 中位數，
`n_above_p75/total >= 50%` 即判「系統性更難」）手算兩型 void 對 96 題
ON 已完成資料的位置：

```
TIMEOUT void（n=34，全部比對成功）vs 96 題完成的 ON row：
  prompt_len          measured_median=148  void_mean_percentile=0.419
  hidden_test_count   measured_median=109  void_mean_percentile=0.368
  canonical_lines     measured_median=2    void_mean_percentile=0.629
  n_above_p75 = 24/102 = 23.5%   ⇒ 未過半，「系統性更難」假說不成立

HTTP_ERROR void（n=12，全部比對成功）vs 96 題完成的 ON row：
  prompt_len          measured_median=148  void_mean_percentile=0.589
  hidden_test_count   measured_median=109  void_mean_percentile=0.324
  canonical_lines     measured_median=2    void_mean_percentile=0.622
  n_above_p75 = 12/36 = 33.3%    ⇒ 未過半，「系統性更難」假說不成立
```

**結論：round83 §8 的難度審查假說，套到 ON 臂主要的兩種 void 型態上，
都不成立。** void 題目在三個難度代理量上的位置分布（percentile 0.32–0.63
之間、多數集中在中段）與已完成題目沒有明顯偏移，不像是「挑著難題吃」。
**這件事把 §3 提出的「倖存者偏誤」疑慮實質降低**：32.39% 的高 void 率
看起來更像是與題目內容無關的端點噪音（呼叫數結構性放大重試耗盡機率），
不是挑著難題審查掉。

⚠ **這個結論的邊界要寫清楚**：
- 樣本數不大（34、12），percentile rank 檢定本身沒有做顯著性檢定（沿用
  round83 §8 的簡單 p75 計數規則，不是本輪發明的更嚴格方法），「沒有
  達到 50% 過半的粗略訊號」不等於「嚴格統計上證明沒有差異」。
- 只檢查了三個**代理量**（prompt 長度、hidden test 數、canonical 行數），
  沒有檢查「模型自己覺得這題多難」（例如 reasoning token 數）——這件事
  round83 原本的假說（`finish_reason=length` 型）才會直接量到，但那型
  void 在 ON 臂目前是 0 筆，查無可查。

## 六、修正後的下一輪建議（不再建議強制升級 opus）

草稿（見上方版本控制前的文字）原本建議下一輪升級 opus 去做這個難度檢查——
**本輪已經把那個檢查做完，而且結論是「假說不成立」**，不是「留了一個
需要重新設計實驗的判斷缺口」。剩下要做的事都屬於「跑既定的檢查、套用
既有 precedent」，不是新的實驗設計取捨：

⚠ **本節原稿誤引用了一個不存在的 precedent，已更正**：原稿寫「round76
已經驗證過 backfill」，**這是錯的**。查證後發現：round76 的 commit message
只是**建議**用 backfill 而非整跑重來，但**下一輪（round77，
`DECISION_20260825_ROUND77_BOUNDS_OVER_BACKFILL.md`）明確推翻了這個建議**，
改用「區間法」（把沒量到的格子當成悲觀/樂觀兩端的區間，若排序在區間
兩端都成立就不需要補資料）——**backfill 從頭到尾沒有被實作或執行過**，
`gain_run.py` 沒有 `--backfill` 旗標（`DECISION_20260825_V3_NEAR_COMPLETE_INFRA_VOID_GAP.md`
第 73 行明講「幫 `gain_run.py` 加 `--backfill` 模式」是**提案**，第 104 行
「沒有動 `gain_run.py`（backfill 功能只是提案，沒有實作）」）。而且
round77 用區間法能繞開的前提是 **void 只有 4/60＝6.7%**，區間夠窄、
兩端排序一致；`g_on371` 現在是 **46/142＝32.4%**，量級差 5 倍，區間法
在這個 void 率下大機率兩端不一致（悲觀端與樂觀端會落在正負相反的方向），
**不能直接套用同一招**。

1. **等 `g_on371` 跑完 371 次嘗試**（目前 96 rows + 46 void = 142，還有
   ~229 個 index 待跑；不 kill，理由同 round83：殺掉會失去唯一一份
   能繼續驗證「void 率隨呼叫數放大」這個機制假說的資料）。
2. **跑完之後，先用區間法（`analyze_void_bounds.py`，round77 已寫好）
   試算一次**——若 371 題累積下來 void 的絕對數字夠大但佔比不變
   （~32%），區間法大概率無法 resolve；若確實 resolve 不了，才需要
   在「真的實作 `--backfill`」與「接受 incomplete、只報 bounds」之間
   做選擇，**這是一個尚未被任何一輪實際驗證過的新判斷，不是套用
   precedent**。
3. **void 率若仍 > 10% 且區間法/backfill 都無法給出乾淨答案，才需要
   真的判斷要不要接受 incomplete 的比較**——那個判斷屬於「跑既定實驗、
   收數字」還是需要 opus 屬於當時的具體數字，留給那一輪按現場狀況
   判斷，本輪不預先鎖死。
4. 若之後又有新的 void 型態（不是 timeout／http_error／length 三種之一）
   大量出現，或難度代理量檢查在更大樣本下翻盤（過半 p75），**那才是
   真的「前一輪推翻自己」的情況，那一輪才需要 opus**。

## 七、什麼條件下這份決定該被推翻

- **§五的難度檢查已經做完、結論是假說不成立**——「呼叫數放大 void 率」
  仍然成立（這是量測到的事實），但「void 造成倖存者偏誤」這個延伸推論
  不成立：void 率雖高，但看起來是難度無關的隨機噪音，倖存的 96 題
  在這三個代理量上仍是無偏子集，OFF-vs-ON 的比較邏輯上仍然乾淨
  （只是有效 n 變小、power 需要重算）。若之後樣本數變大（backfill 或
  跑滿 371 之後 void 數更多）重新做這個檢查、結果翻盤過半 p75，
  這條結論要撤回。
- 若本輪或下一輪重新檢查 round96/104/106/107 的原始指令紀錄（若能找到），
  發現它們其實有正確檢查 `notes.jsonl`、只是本輪的分桶方法有誤，
  則「之前四輪讀錯」這個結論要撤回——**但 `overlap=0` 與 `void_rate=32.39%`
  這兩個數字本身不受影響**，那是直接對兩個 JSONL 檔案的存在性核對，
  與「之前誰讀對讀錯」無關。
