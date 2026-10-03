# i1001 分析報告（互動式 pi：沒裝／零設定 Vacant／重試／可見驗收把關）

## 主要檢定（精確 McNemar、雙尾、Holm 校正兩個）

| 檢定 | 指標 | 配對 | x 組過 | y 組過 | 只有 y 過（b） | 只有 x 過（c） | p（未校正） | p（Holm） | α=0.05 |
|---|---|---|---|---|---|---|---|---|---|
| K 對 R（x＝R、y＝K） | 被放行且隱藏全過 ／ 隱藏全過 | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 不顯著 |
| C 對 A（x＝A、y＝C） | 隱藏全過 | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 不顯著 |

不顯著 ＝ **這一批沒有量到差別**，不是「沒有差別」；顯著也只說明這個題池、這個模型、這個設定（見下面的誠實邊界）。

## 各組描述（主跑、非 void）

| 組 | n | 隱藏全過 | 指標過 | 交了 | 錯交（交了但隱藏沒過） | 沒交 | 逾時 | session 總數 | 牆鐘中位數(s) | 輸入 token | 輸出 token |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 2 | 0 | 0 | 2 | 2 | 0 | 0 | 2 | 18.7 | 40 | 20 |
| C | 2 | 0 | 0 | 2 | 2 | 0 | 0 | 2 | 22.1 | 80 | 40 |
| R | 2 | 0 | 0 | 2 | 2 | 0 | 0 | 2 | 18.7 | 40 | 20 |
| K | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 6 | 57.05 | 120 | 60 |

K、R 的 session 數／token／牆鐘含與 A 共用的第 1 段。

## 篩選階段（只跑 A；天花板規則 ≥ 9/10 丟題庫）

| 題庫 | 跑了 | void | A 答對 | 沒解開的題 |
|---|---|---|---|---|
| dabench | 1 | 0 | 0 | dab_039 |
| polyglot_py | 1 | 0 | 0 | pg_phone_number |

天花板決定（_run_t1）：丟掉的題庫＝[]
- dabench：screening incomplete (9 task(s) not run) and the bank could still reach 9/10: undecided, bank kept
- databench：screening incomplete (10 task(s) not run) and the bank could still reach 9/10: undecided, bank kept
- polyglot_py：screening incomplete (9 task(s) not run) and the bank could still reach 9/10: undecided, bank kept

天花板決定（_run_t2）：丟掉的題庫＝[]
- dabench：screening incomplete (9 task(s) not run) and the bank could still reach 9/10: undecided, bank kept
- databench：screening incomplete (10 task(s) not run) and the bank could still reach 9/10: undecided, bank kept
- polyglot_py：screening incomplete (9 task(s) not run) and the bank could still reach 9/10: undecided, bank kept

## 各題庫（描述，不是檢定）

| 題庫 | C 對 A 配對 | A 過 | C 過 | 只有 C 過 | 只有 A 過 | K 對 R 配對 | R 過 | K 過 | 只有 K 過 | 只有 R 過 |
|---|---|---|---|---|---|---|---|---|---|---|
| lcb_v3 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |

## 救回／傷害（描述，相對於 A）

```json
{}
```

## K／R／C 的過程

```json
{
 "K": {
  "n": 2,
  "released": 0,
  "accepted_at_attempt": {
   "0": 2
  },
  "released_but_hidden_fail": 0,
  "never_released": 2
 },
 "R": {
  "n": 2,
  "retried": 0,
  "retry_reasons": {}
 },
 "C": {
  "n": 2,
  "c_arm_ok": 2,
  "stop_reached": 2,
  "cells_with_sendback": 2,
  "sendbacks_total": 2,
  "install_fail": 0
 }
}
```

## infra_void 與完成偵測稽核

- 最終仍 void 的格：0；被重跑取代的 void：0；K 起不來的單位：0。（逐格清單在 report.json）
- 完成偵測：session 10 段；`late_write_after_done`＝0（非 0 ⇒ IDLE_S 太短）；最終 stop 之後的最大間隔＝0.443 s（IDLE_S＝[15.0]）；完成原因＝{'idle_final': 10}；送出未確認＝0；信任對話框＝0；打字不符＝0。

## 誠實邊界

- 題池不是隨機抽樣的全體：LCB 部分是 C5 的 A 失敗題（93）＋種子抽的 A 成功對照（40），任務題庫是通過天花板規則的題庫；結論只說這個題池。
- A、R、K 共用 A 的第 1 段，工作區有 bridge 寫的 `.vacant/contract.json`（沒裝 Vacant 時不起作用）；C 的工作區沒有契約（有契約會關掉零設定檢查）。這個差別已記進每格 meta.json。
- K 的 bridge 是 non-adversarial 的基準輔助；放行的成品由計分器另行計分，K 的「放行」只代表可見驗收過了。
- 互動式「跑完」是從 session 檔推論的（安靜 IDLE_S 秒）；稽核數字在上面。
- ❌「Vacant 讓 agent 做得更好」不帶條件；❌ 把分項（題庫、角色）當成檢定；❌ 外推到真人互動使用。
