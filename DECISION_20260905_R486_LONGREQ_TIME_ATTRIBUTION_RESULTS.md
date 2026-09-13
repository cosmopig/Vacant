# R486 結果：長請求的伺服器端時間去了哪裡

**日期**：2026-09-05 UTC（round757）　**模型**：Opus 5
判準 `8a447c7` ＋ 修訂 A `62fad67`（都在量測之前）／量具 `734a5ea`（結果之前）／本檔＝結果。

## 一句話

**R485 §3 留下的替代解釋「一直排在佇列裡」——本輪量到它是真的：`QUEUE_LIVE`。**
而且排隊的來源**不是別人，是我們自己**——客戶端在 600 秒放手之後繼續送下一題，
伺服器卻沒有放掉舊的那筆，於是**整段 run 有一半以上的時間，端點同時開著 ≥2 個 chat 請求**，
而客戶端以為自己是嚴格依序的。

## 判決（兩個 `ts` 語意假設底下都相同，才採用；見修訂 A）

| 預測 | 判決 | 關鍵數字（start / end 假設） |
|---|---|---|
| P-1 排隊 | **`QUEUE_LIVE`** | `queue_share` **1.000 / 0.833**（門檻 ≥0.50） |
| P-1b 基準率 | `BASERATE_OK` | 外來 chat 請求 **45 筆**（全是 `qwen/qwen3.8-27b`）⇒ P-1 不是空綠燈 |
| P-2 模型重載 | `RELOAD_CONTRIBUTES` | `reload_share` 1.000 / 0.500 ⚠ **見下面「這條是強制綠燈」** |
| P-3 在不在生成 | **`UNSCANNED`**（事前就預期） | 6 筆目標全是 `400 Context size has been exceeded`、`completion_tokens=null` |
| P-4 並行度 | `CONCURRENT_OBSERVED` | `max_concurrency` **5 / 6** |

⚠ **P-1 與 P-4 不獨立**（同一組區間的兩面）⇒ 收官只算**一項**證據。

## 六筆目標（`latency_ms ≥ 600000`、gemma、1004）

```
 id=115223 lat=5990.6s(99.8min) ovl_start=0.885 ovl_end=0.220 status=400 ctok=None
 id=116500 lat=6014.1s(100.2min) ovl_start=0.885 ovl_end=0.734 status=400 ctok=None
 id=117120 lat=5618.1s(93.6min) ovl_start=0.888 ovl_end=0.732 status=400 ctok=None
 id=117323 lat=2666.9s(44.4min) ovl_start=0.774 ovl_end=0.898 status=400 ctok=None
 id=117324 lat= 938.7s(15.6min) ovl_start=1.000 ovl_end=0.556 status=400 ctok=None
 id=117325 lat=2065.1s(34.4min) ovl_start=1.000 ovl_end=0.708 status=400 ctok=None
```

**這 6 筆＝主客戶端 741 筆 chat 的 0.81%，卻吃掉 388.2 / 856.0 分鐘＝伺服器時間的 45.3%。**

## 判準之外（post-hoc，不計入預測帳）：排隊是誰造成的

`ops/gain/r486_posthoc_decomposition.py`：把每筆目標的重疊拆成「自己客戶端」與「外來」。

```
hypo=start   own_client=0.885 0.885 0.888 0.774 1.000 1.000
             foreign  =0.001 0.001 0.001 0.001 0.004 0.002
hypo=end     own_client=0.220 0.734 0.732 0.898 0.556 0.708
             foreign  =0.000 0.000 0.000 0.001 0.000 0.001
```

⇒ **重疊 99.9% 來自我們自己。** 那 45 筆外來 qwen 請求對重疊的貢獻 ≤0.4%。

並行度的時間佔比（整段 9.06 小時）：

```
hypo=start  0個:0.022  1個:0.436  2個:0.497  3個:0.035  4個:0.010  5個:0.000
hypo=end    0個:0.148  1個:0.435  2個:0.288  3個:0.106  4個:0.019  5個:0.003
```

⇒ **start 假設下 54.2% 的牆鐘時間有 ≥2 個 chat 請求同時開著**（end 假設 41.6%）。
`gain_run.py` 是**嚴格依序**的（原始碼三處註解明寫「依序送出、不用 ThreadPoolExecutor」）
⇒ 這個並行度**在客戶端的世界觀裡不存在**。

機制的直接證據：把每個目標的「自己客戶端的重疊夥伴」按開始時刻排：

```
hypo=start: 重疊的自家請求 386 筆，開始時刻早於「目標起點+600s」的只有 3 筆，中位延遲 3210.8s
hypo=end  : 533 筆，早於放手點的 82 筆，中位延遲 2821.0s
```

⇒ 幾乎每一個重疊夥伴，都是**客戶端已經放手、去跑下一題**之後才送出的請求。

## 誠實邊界與本輪抓到的自己的缺陷

1. 🔴 **P-2 是強制綠燈（`FORCED_GREEN`），本輪自己抓到、照實記，不當場改判準。**
   窗口內 1004 有 **16 個 load/unload 事件、平均間隔 34.0 分鐘**；目標請求長 15.6–100.2 分鐘。
   對應的**時長匹配 Poisson 虛無期望**是 **0.761**——而我事前把
   `RELOAD_CONTRIBUTES` 的門檻寫成 0.30。`RELOAD_RULED_OUT` 需要 6 筆全都不含事件，
   機率約 `(1-0.761)^6 ≈ 2e-4` ⇒ **這條判準結構上不可能吐出反例**。
   對照：短請求（中位 22.3 秒）的命中率只有 **16/780 = 2.05%**，差距完全由**時長**解釋。
   ⇒ **P-2 這一輪不算證據。** 下輪要修的是判準形式（跟時長匹配的虛無比，不是固定佔比門檻），
   不是門檻數字。
2. 🔴 **`n_foreign_chat` 我寫成 `by_ip + by_model` ＝重複計數**：45 筆外來列同時滿足兩個條件，
   工具報 90。P-1b 的門檻是「>0」⇒ **判決不受影響**，但那個數字本身不准引用。
   正確數字是 **45**。
3. 🔴 **第一份快照漏了 22% 的 chat 列。** `/api/requests` 的時間切片分頁掉了 690 個 id
   （其中 **173 筆是 chat**）。id 連續性檢查抓到的（`missing ids inside range: 690`）。
   已逐 id 重抓補齊成 v2。**v1 與 v2 的五個判決完全相同**，v2 只是把 P-1 推得更強
   （`queue_share` start 0.667→1.000）。兩份都留檔：
   `ops/gain/data/r486_result_v1_incomplete.json`（**已知不完整、不准引用**）與 `..._v2.json`。
   ⇒ **通則：分頁抓完要驗 id 連續性，不能只看回傳筆數。**
4. **P-3 沒有正面證據**：6 筆目標全部沒有 token 記錄 ⇒ 「那 100 分鐘到底有沒有在生成」
   **本輪答不了**。`400 Context size has been exceeded` 直覺上指向「一路生成到把上下文塞爆」，
   但那是推論不是量測，判準 T-4 明文禁止用消去法補上這一格。
5. **客戶端 651 筆呼叫 vs 閘道 741 筆主客戶端 chat 列**：對不起來（閘道比客戶端多）。
   本輪沒有解釋這個差，也**沒有**拿它下任何結論。（時鐘偏差已排除：兩台差 <1 秒。）
6. `ts` 語意仍是 `TS_AMBIGUOUS`（反序對數 start=1 / end=17，兩個都不是 0）
   ⇒ 依修訂 A，判決只在兩邊一致時採用。五個判決**全部一致**。

## 這對「timeout 該怎麼動」的意思

R485 說「調小 timeout 是錯方向」。本輪**加強**了那個結論並補上機制：

- 客戶端放手**不只**沒有釋放伺服器，它還**主動製造並行**——放手之後送出的下一題，
  跟那個沒人讀的舊請求**搶同一張卡**，而後者還會再活 15–100 分鐘。
- 因此「調小 timeout」會讓並行度**更高**、讓還在讀的那些請求**更慢**。
- 6 筆佔 45.3% 伺服器時間 ⇒ **要動的是「讓這些請求根本不要長到那麼長」**，
  也就是 R485 已經指出的 `max_tokens` 上限（400 Context exceeded 也指向同一處），
  **不是放手時刻**。
- ⚠ 這仍**不是**改參數的授權。要改要另開 DECISION，且不准套用到在跑的 run。

## 量具健康

```
$ python3 ops/gain/r486_longreq_attrib.py --selftest
selftest 42/42 passed

$ python3 ops/gain/r486_mutation_check.py
baseline: rc=0 crash=0 failed=[] -> CLEAN
M0_NOOP  expect_catch=N caught=N  OK        （雙向校準的負對照）
M1..M9   expect_catch=Y caught=Y  OK  crash=0 全部由**具名檢查**抓到
10/10 mutants behaved as prereg'd
```

`M7_TOPK` 型的單調性教訓有套用：`M3_OVERLAP_THRESHOLD_ZERO` 把門檻調小只會讓
`QUEUE_LIVE` 更容易成立 ⇒ 看得見它的方向是 `QUEUE_RULED_OUT` 那一邊，夾具 A 就是那個方向。

## 快照

- `ops/gain/data/r486_gateway_snapshot.json`（v1，**不完整**）
  sha256 `90368bd1c4c3c052f4c02e6fbe165e2cf0078e4ce6e50543879023e2632ee035`
- `ops/gain/data/r486_gateway_snapshot_v2.json`（**本檔所有數字的來源**）
  sha256 `060efe0ce91975269b73de61de65c4e3c7fb447bb83b3273d96a73af950ce59c`
  2899 列／786 chat／500 事件／窗口 9.06 小時

## 本輪沒做什麼

零模型呼叫；`gain_run.py` 一個 byte 沒改；沒有起／殺任何 run；沒有 `git add` 主 run 目錄；
8766 只讀（`GET`）；沒有動任何門檻檔；沒有碰 `world/`／`design/`／`vacant_hm`。
