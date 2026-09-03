# R440O：E3（gemma-only ＋ LiveCodeBench）預註冊——答 H-B「題目太簡單」

（2026-09-03 05:5x UTC，Fable 5.1，Mac 端 session「vacant」。人類 09-03 指示「繼續」，
依 LOOP_PROMPT §七 的授權自己拍板。**本文件在發射前寫定；預測寫在前面，跑完不准改。**
run 名 `runs/g_r443_gemma_lcb` 即 R440G 閘門所需的預註冊授權。）

## 一、為什麼是 E3，不是 E2

R440 原本的分工：E2＝混合池（qwen3.6＋gemma）＋LCB 隔離 H-B；E3＝gemma-only＋LCB 兩者並用。

**E2 現在做不到，而且不是排程問題是硬體問題**：混合池要 qwen3.6（22.3 GB）與 gemma（7.2 GB）
同時在 1004 的單張 24 GB 卡上。09-02 實測過這個組合的每一種順序，全部撞到
「paging file is too small」或 LM Studio 的 44.87 GB 保護（R440E §三、R465）。E2 不是「還沒排到」，
是**在現有硬體上不可執行**。

**E3 現在反而變成單變因比較**：E1（gemma-only＋MBPP+）已經跑完（R516／R440N），
E3 只把題庫換成 LCB，worker、seed 邏輯、request_policy、量具紀律全部沿用。
E1 → E3 的唯一差異＝題目難度，這正是 H-B 要隔離的東西。R440 當初把這個角色給 E2，
是因為當時 E1 還沒跑；E1 跑完之後，E3 自己就是 H-B 的乾淨測試。

**放棄的選項**：等硬體升級再跑 E2（無限期）；用 qwen-only＋LCB 代打（R466 的 E2q，已被
R440D「infra 未修前不起 qwen run」與時序問題否決，且 worker 換家族＝兩個變因一起動）。

## 二、發射指令（唯一與 E1 的差異＝`--bank lcb`／`--n 91`／`--seed`）

```
cd ~/vacant/Vacant && \
PYTHONUNBUFFERED=1 VACANT_GAIN_API=http://100.119.113.56:8765/v1/chat/completions \
CLINE_KEYS=/nonexistent \
setsid nohup python3 ops/gain/gain_run.py --out runs/g_r443_gemma_lcb --n 91 \
  --decision DECISION_20260903_R440O_E3_LCB_PREREG.md \
  --seed g-r442-lcb --bank lcb --models gemma-4-12b-it-qat \
  --request-timeout-s 600 --review-timeout-s 380 --probe-sample 0 \
  >>runs/g_r443_gemma_lcb.launch.log 2>&1 < /dev/null &
```

題庫：`ops/gain/data/lcb_bank_v1.jsonl`，sha256 `eb2a5876…`（發射前已核，與 R440 記錄一致），
91 題 medium+hard，LeetCode functional，contest_date 2024-08→2025-04。

## 三、預註冊預測（跑完對答案，不准事後改）

| # | 預測 | 為什麼這樣猜 |
|---|---|---|
| **P-E3-1**（H-B 主測） | OFF 失敗率 **顯著高於 E1 的 31.8%**，落在 50–80% | LCB medium+hard 對 12B 模型比 MBPP+ 難得多；R440 P4 對混合池猜 >50%，gemma 更弱應更高 |
| **P-E3-2**（主結論） | ON vs OFF5 等預算配對 **仍不顯著**（p>0.05） | E1（n=167 p=1.0）與 r356（p=0.4531）兩次都不顯著；R518/R528 量到瓶頸是評審給不出精確反例，換題庫不改變這件事 |
| **P-E3-3**（L2 門檻） | 評審準確率 grounded (TN−FN)/n **仍 < +5pp** | 同上；E1 是 +4.19pp 且 95% 下界貼 0 |
| **P-E3-4**（機制天花板） | 反例精確度 A 的 **Wilson 上界仍 < 0.80** | R518 §十一 事前定的門檻，E1 量到 A=0.609（上界 0.68），R528 拆桶後 0.604 |
| **P-E3-5**（infra） | ON void 率 **< 20%**（R440 中止準則） | E1 gemma 單獨在卡上是 6.70% |

**翻盤窗（H-B 成立長什麼樣）**：P-E3-1 成立（題目確實更難、真失敗更多）**且** P-E3-2 或 P-E3-4
被推翻——也就是「難題上評審終於有東西可攔、且攔得準」。那時 R440B 的階梯 L1／L2 前提復活，
可以繼續往上爬。**只有 P-E3-1 成立而 P-E3-2/3/4 都照預測，代表 H-B 也被排除**：
不是題目太簡單，是這個量級的模型當評審就是給不出精確反例。

## 四、中止準則（沿用 R440，不新增）

- 任一臂 infra_void > 20% ⇒ 中止，先修 infra（R356/R440 教訓）。
- OFF 失敗率 > 70% ⇒ 題庫對這個 worker 太難、配對統計失去意義；照實記錄，
  考慮只取 medium 子集（54 題）重跑，**不當作 H-B 成立的證據**。
- OFF 失敗率 < 35% ⇒ LCB 對 gemma 沒有比 MBPP+ 難多少，P-E3-1 被推翻，H-B 這條路本身要重想。

## 五、誠實邊界（先寫死）

1. **n=91 檢定力比 E1 弱**：McNemar 在 91 對下約可辨 12–15pp 級不對稱（R440 §誠實邊界 3）。
   不顯著**不等於**等效；沒跑出差異只能說「這個樣本量看不到」。
2. **量具覆蓋率遠低於 E1**：LCB 沒有官方參考解，`lcb_probe_solutions.json` 只有 12 題手寫解
   （R441），所以 `--probe-sample 0` 在 LCB 上實際只驗得到 **12/91**，不是 E1 的 179/179。
   這是已知缺口，不是本輪造成的，但報告時不能講成「全題庫雙向驗證」。
3. **污染不可證偽**：gemma 訓練截止未公開，2025-04 前的比賽題不能宣稱 zero-contamination
   （R440 §誠實邊界 1）。日期戳是定界工具不是免罪證明。
4. **`separateSquares`（lcb_3763）已知量具假陽性**（R441）：浮點容忍度 1e-6 對上資料集只存 5 位
   小數，任何正確解都會被判失敗。它**在 91 題實驗池內**。若某題三臂全滅，先查是不是這題。
5. **平台偏斜**：排除 stdin 型後全部是 LeetCode，風格單一。

## 六、發射時的基礎設施狀態（實測，寫進紀錄）

- 1004：`gemma-4-12b-it-qat` 單獨載入，`context_length=262144`，**`remaining_ttl_seconds=None`**
  ——人類手動載入，沒有 TTL 倒數，E1 期間那個「每小時卸載又重載 9 秒」的 churn 不會重演（R440N §四.2）。
- **JIT 仍無法遠端確認或關閉**：1004 沒有 settings REST 端點（`/api/v0/settings`、`/api/v1/settings`
  皆 404），JIT 是 GUI 設定。殘餘風險＝w1004（100.118.96.3）若在 run 期間要 qwen3.8，
  JIT 會載入並擠掉 gemma。E1 的 11h23m 期間 w1004 零請求，但那是運氣不是保證。
  **監看方式**：`8766/api/events` 出現任何非 gemma 的 loaded 事件＝gemma 被擠掉，立刻停手記錄。
- **`Linger=no` 未修**：`sudo loginctl enable-linger user1` 被 Mac 端分類器擋下（系統設定，
  人類動作）。E1 在同樣的 `setsid nohup` 寫法下存活 11h23m 才被 logind 收掉，
  E3 預估 5–7 小時（91 題 vs 179 題），落在已觀測的存活範圍內，判斷可以跑。
  **這是判斷不是保證**：若 E3 也被 logind 中途收掉，那就證明 linger 是硬前提，
  下一個 run 之前必須由人類執行那一行。

## 七、推翻條件

- 若 8766 事件出現非 gemma 的 loaded ⇒ 這個 run 的 void 與延遲數字全部不可信，作廢重跑。
- 若 P-E3-1 被推翻（OFF 失敗率 <35%）⇒ 本 run 對 H-B 無資訊量，不要拿 P-E3-2 的「不顯著」
  當成「難題上也沒用」的證據。
- 若量具在 LCB 上 12/12 沒過 ⇒ 立刻停，不要在壞尺上跑實驗（鐵律）。

## 八、run 中途的基礎設施條件變更（必須記錄，SPEC_GAIN §7 把延遲當實驗條件）

**2026-09-03 06:0x UTC，peer session 停掉了 win1003 上的 ComfyUI 場景重生**，理由是我指出
「推論在 1004，但中轉 hub 進程跑在 win1003，重生打滿那台會讓延遲混進 E3 的資料」。
GPU 由 peer 回報的 100%／19 GB 降到 125 MiB／5%，`/d/lock_*` 已清空。

**因此 E3 的呼叫橫跨兩種中轉主機負載狀態，分析時必須檢查斷點**：

| 10 分鐘桶（UTC） | n | p50 | mean | max |
|---|---|---|---|---|
| 05:40 | 6 | 3.0s | 22.9s | 99.4s |
| 05:50 | 19 | 15.7s | 21.2s | 81.0s |
| 06:00 | 1 | 380.1s | 380.1s | **380.1s＝`review_timeout_s` 天花板** |

06:0x 那一通是本 run 第一筆失敗呼叫（26 通裡 25 ok），時間點正好落在重生滿載／被停掉的
交界。**n=26、單一觀察，這是紀錄不是歸因**——不能說「重生害的」，也不能假裝沒發生。

**收官分析要做的事**（寫在這裡，免得跑完忘記）：以 06:05 UTC 為切點把 calls.jsonl 分兩段，
比較 p50 延遲與失敗率；若兩段有明顯差異，前段的 void／逾時要在結論裡標明是在
「中轉主機共用負載」條件下產生的。若無差異，這一節就只是一筆負面紀錄。

**我沒做的**：沒有要求 peer 停重生（我只指出風險，停是它的決定），也沒有因為這個變更
中止或重啟 E3——重啟會丟掉已跑的資料，而條件變更本身可以被記錄與檢驗，不需要重來。
