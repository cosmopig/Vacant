# R457：`pz5b_reconstruction_feasible` 在有重試時是**假紅**——加法式修正

2026-09-04 round724（Opus 5）。**本文件在改任何一行程式碼之前 commit。**

## 一、觸發本輪的觀測（round723 → round724 之間唯一變動的例行尺數字）

```
round723  r447_schema_precheck  pz5b_reconstruction_feasible = true
round724  r447_schema_precheck  pz5b_reconstruction_feasible = false
          reconstruct_untagged_gen_calls = 0
          reconstruct_mismatch_n         = 1
          reconstruct_mismatch_sample    = [{"task_id":"lcb_3762","conform_calls":5,"calls_jsonl":6}]
```

同期 `pace_probe` 的 `Q3_timeout_hits` 由 **1 → 2**。

## 二、判準（**寫在查明原因之前**，round724 開場即落文於本輪 transcript）

- 若**每一筆**不符都是 `calls_jsonl > conform_calls`，且超出的那些 gen 呼叫
  正好是失敗／重試的那幾通 ⇒ 成因是**重試被記進 calls.jsonl**，
  這面旗是**假紅**，收官輪必須被告知。
- 若**任一筆**是 `calls_jsonl < conform_calls`，或超出的呼叫全都成功
  ⇒ 是真的資料遺失，**升級**。
- `untagged > 0` ⇒ 另一個獨立的真問題（與上面兩條無關）。

## 三、量測（照上面的判準判）

`CONFORM/lcb_3762` 的 6 通 gen：

```
line 842 ok=True   ct=5193  resp_len=11461
line 843 ok=False  err='TimeoutError: timed out'  ct=None  resp_len=0
line 844 ok=True   ct=4006  resp_len=12546
line 845 ok=True   ct=2891  resp_len=6228
line 846 ok=True   ct=6668  resp_len=13041
line 847 ok=True   ct=2071  resp_len=6832
```

5 通成功 ＝ `conform_calls: 5`；多出來的第 6 通是唯一那通 `ok=False`、`resp_len=0`。
`untagged=0`、方向全是 `>` ⇒ **判定：假紅**。

**語意上的根因**（與結果數字無關，這點是本輪修正方向的唯一許可理由）：
`conform_calls` 是**邏輯呼叫數**（重試在 `generate()` 內被吞掉），
而本尺數的是 calls.jsonl 裡的**物理請求數**。兩者在無重試時恰好相等，
一有重試就分岔 ⇒ 這條恆等式從一開始就比錯了兩個量。
失敗的那通 `resp_len=0`，**結構上不可能攜帶候選** ⇒ 它本來就不屬於重建的母體。

## 四、修正方式：**加法**，既有欄位一個位元組都不動

⚠ 本輪的修正方向對自己有利（讓一面紅旗變綠）。因此：
**舊欄位 `pz5b_reconstruction_feasible` 的公式與值原封不動**，
收官輪同時看得到舊值與新值，仲裁權留在事前文件、不在本輪。

新增（只增不改）：

| 新鍵 | 意義 |
|---|---|
| `reconstruct_failed_gen_calls` | CONFORM gen 裡 `ok is False` 的通數 |
| `reconstruct_mismatch_ok_only_n` / `_sample` | **只數非失敗通**之後還對不上的筆數 |
| `pz5b_reconstruction_feasible_ok_only` | 只數非失敗通的可行性（**收官應引用這個**） |
| `pz5b_mismatch_explained_by_failed_calls` | 舊旗紅、新旗綠 ⇒ 差異完全由失敗通解釋 |

「失敗」定義為 `ok is False`（**明確失敗**才排除；`ok` 不存在視為成功，
夾具不寫 `ok`）。

## 五、新旗必須保留的牙齒（事前寫死，違反就是本輪失敗）

1. **少了一通成功呼叫 ⇒ 新旗也必須是 False。** 修正不得讓量具對真遺失變瞎。
2. **舊旗可能是假綠：** 若同一題同時「少一通成功」＋「多一通失敗」，
   物理總數與 `conform_calls` 巧合相等 ⇒ **舊旗綠、新旗紅**。
   這一格證明新旗擁有舊旗沒有的牙齒（不只是把紅的洗成綠的）。
3. 每個新斷言都要有**指名的**突變體看著；突變體要在**被測函式內部**生效；
   crash 收場不算抓到（判準寫「該吐哪個值」）。

## 六、推翻條件

- 若 r447 收官時 `reconstruct_mismatch_ok_only_n > 0` ⇒ 本輪判定被推翻，
  成因**不是**重試，收官輪必須把 P-Z5b／R453 的重建輸入視為不可信。
- 若收官時 `reconstruct_untagged_gen_calls > 0` ⇒ 同上，且與本輪無關。
- 若 X14（§五-2）在真資料上**曾經**成立（舊旗綠而新旗紅）⇒ 過去各輪記的
  `pz5b_reconstruction_feasible: true` 有一部分是假綠，收官不得直接引用舊值。

## 七、本輪不做

不改 `r447_reject_reconstruct.py`／`prereg_falsifiability_census.py`／任何門檻／
任何既有普查記錄；不對 r447 下收官判斷；不殺 run；不 `git add` run 目錄。
R454 自身的普查（round723 交棒的第 3 項）**本輪未做**，理由：本項是收官輪
即將讀到的一面紅旗，且 r447 距 terminal 不到 20 分鐘，優先序較高。
