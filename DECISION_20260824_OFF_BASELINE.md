# DECISION 2026-08-24：先量 OFF 失敗率，判準寫在量測之前

**寫這份文件的時刻：2026-08-24 06:0x UTC，本輪尚未發出任何模型呼叫。**
這份先 commit、再跑，git 歷史可以證明判準不是看到數字之後才訂的
（理由：量完再訂判準，數字高低兩個方向都會誘導人）。

## 一、要解的問題

2026-08-20 的 smoke（`runs/g_smoke_20260820/summary.json`，實測數字）：

| 臂 | 呼叫 | correct_delivery_rate | leaked |
|---|---|---|---|
| OFF | 6 | 1.0（6/6） | 0 |
| ON | 30 | 1.0（6/6） | 0 |
| OFF5 | 30 | 1.0（6/6） | 0 |

三臂全對 ⇒ 天花板效應 ⇒ **OFF 沒有失敗，ON 就沒有空間顯示增益**。
所以本輪不跑三臂、不加題數跑 371 題，只做一件事：**量 OFF 的失敗率**。
那個數字決定後面所有事。

## 二、量測設定（本輪要跑的那一條指令）

```
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz \
python3 ops/gain/gain_run.py \
  --out runs/g_off60_20260824 --n 60 --seed g-smoke-20260820 \
  --arms OFF --probe-sample 0 --calibration-n 0 \
  --models cline-pass/glm-5.2,cline-pass/deepseek-v4-flash,cline-pass/kimi-k3
```

三個刻意的選擇，以及放棄了什麼：

1. **seed 沿用 smoke 的 `g-smoke-20260820`，不換新 seed。**
   `load_tasks` 是「按 seed 排序取前 n」，所以 n=60 的前 6 題**就是** smoke 那 6 題，
   n=6 是 n=60 的前綴。換來的是巢狀性與可重放（同 seed 同題序、OFF 的路由 RNG
   `seed:OFF` 也同序）；放棄的是「換 seed 看題目抽樣運氣」——那個要等有訊號再說。
2. **`--calibration-n 0`**（smoke 用 3）。calibration 是信譽路由的成立前提，
   OFF 是隨機路由不吃它。省 18 次呼叫（約 $0.12）與約 2 分鐘。
   代價：本輪不重量池子異質性（smoke 量到 accuracy_spread=0.333，沿用它當前提）。
3. **worker 池不動**（POOL 6 個 agent × 3 個模型家族，與 smoke 逐字相同）。
   「換更弱的 worker（只用 hasty）」是**還沒動**的旋鈕——先量現況再決定要不要動它，
   因為換 worker 是實驗條件的改變，量到的差異會混進條件差異。

**已先查證、不必再動的一件**：人類提的第三個方向「確認 `hidden_check` 真的用了
`plus_input`」——`vacant/codebench.py:660` 是 `_check_check_code(..., base + plus, atol)`，
plus 加強測資**已經在**隱藏判定裡。所以「調難度」這個旋鈕在題庫側已經是最緊的了，
沒有東西可以調。

## 三、判準（現在寫死，跑完照這張表對，不准改）

令 `measured = 60 - infra_void`，`f = 1 - correct_delivery_rate`（OFF 全接受，
所以 f 就是 raw 失敗率）。**分母是 measured 不是 60**——infra_void 是「這一格沒量到」，
不算成功也不算失敗（SPEC_GAIN §7、人類鐵律 2）。

先擋門：

- **`infra_void > 6`（>10%）⇒ 這一輪的 f 不准拿去對下面任何一條**，
  run 記成 incomplete，本輪結論只寫「端點不穩，沒量到」。

f 的判決（Wilson 95% 區間一起報，點估計不單獨用）：

| f 落點 | 判決 | 下一輪做什麼 |
|---|---|---|
| `f ≥ 0.20` | **量測窗口可用** | 直接在這 60 題上跑三臂（ON／OFF5），worker 池不動 |
| `0.05 ≤ f < 0.20` | 邊緣 | 兩條路二選一：加大 n 到 150 縮小區間，或改 hasty-only worker 池；**擇一並記成條件改變** |
| `f < 0.05` | **天花板確認** | 現池答不出這題 ⇒ 必須動條件：改 hasty-only worker 池重量 OFF |
| `f > 0.60` | 太難 | 池子太弱，反而量不到「機制能不能救」；要換強一點的 worker |

同時要落盤、下一輪會用到的兩張明細（不是判準，是素材）：

- **失敗題 ID 清單**——下一輪要用它組「難題子集」，比整批 60 題便宜。
- **逐 worker 的失敗分佈**——若失敗集中在 hasty-1/hasty-2，那就同時是
  「hasty-only 池會更難」的直接證據，不必再花一輪去試。

## 四、什麼條件下這份決定該被推翻

- 若 `f ≥ 0.20` 但失敗**全部**來自同一個 worker 或同一個模型家族的端點異常
  （例如某家族回傳空字串、被 `extract_code` 原樣吞下），那 f 量到的是後端故障
  不是題目難度 ⇒ 上表作廢，先修後端。**跑完要逐條看失敗的 err 欄位**，不能只看比例。
- 若失敗題的 `err` 大量是 sandbox timeout／記憶體，那是服務容量邊界不是能力邊界
  （371 題子集已排除 7 題就是為了這個）⇒ 要重新看排除清單夠不夠。

## 五、成本

smoke 實測 OFF 6 題 = $0.0388、77.4s ⇒ 每次呼叫約 $0.0065、每題約 13s。
本輪 60 題預估 **約 $0.39、約 13 分鐘**。人類本輪明文指定跑
`--arms OFF --n 60`，額度授權在此範圍內；超出範圍的加跑要先問。
