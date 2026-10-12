# i1001 分析報告（互動式 pi：沒裝／零設定 Vacant／重試／可見驗收把關）

## 主要檢定（精確 McNemar、雙尾、Holm 校正兩個）

| 檢定 | 指標 | 配對 | x 組過 | y 組過 | 只有 y 過（b） | 只有 x 過（c） | p（未校正） | p（Holm） | α=0.05 |
|---|---|---|---|---|---|---|---|---|---|
| K 對 R（x＝R、y＝K） | 被放行且隱藏全過 ／ 隱藏全過 | 3 | 2 | 2 | 1 | 1 | 1 | 1 | 不顯著 |
| C 對 A（x＝A、y＝C） | 隱藏全過 | 5 | 1 | 3 | 2 | 0 | 0.5 | 1 | 不顯著 |

不顯著 ＝ **這一批沒有量到差別**，不是「沒有差別」；顯著也只說明這個題池、這個模型、這個設定（見下面的誠實邊界）。

## 各組描述（主跑、非 void）

| 組 | n | 隱藏全過 | 指標過 | 交了 | 錯交（交了但隱藏沒過） | 沒交 | 逾時 | session 總數 | 牆鐘中位數(s) | 輸入 token | 輸出 token |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 5 | 1 | 1 | 2 | 1 | 3 | 1 | 5 | 19.4 | 150 | 75 |
| C | 5 | 3 | 3 | 4 | 1 | 1 | 1 | 5 | 22.8 | 180 | 90 |
| R | 5 | 3 | 3 | 4 | 1 | 1 | 0 | 10 | 56.8 | 320 | 160 |
| K | 3 | 2 | 2 | 2 | 0 | 1 | 0 | 6 | 40.2 | 230 | 115 |

K、R 的 session 數／token／牆鐘含與 A 共用的第 1 段。

## 篩選階段（只跑 A；天花板規則 ≥ 9/10 丟題庫）

| 題庫 | 跑了 | void | A 答對 | 沒解開的題 |
|---|---|---|---|---|
| dabench | 10 | 0 | 9 | dab_732 |
| databench | 1 | 0 | 1 | — |
| polyglot_py | 1 | 0 | 0 | pg_affine_cipher |

天花板決定（_run_t4）：丟掉的題庫＝['dabench']
- dabench：A passed 9/10 screened tasks (>= 9): the plain agent leaves (almost) nothing unsolved here; bank dropped
- databench：A passed 1/1 (< 9): 0 unsolved task(s) seen without Vacant; bank kept
- polyglot_py：A passed 0/1 (< 9): 1 unsolved task(s) seen without Vacant; bank kept

## 各題庫（描述，不是檢定）

| 題庫 | C 對 A 配對 | A 過 | C 過 | 只有 C 過 | 只有 A 過 | K 對 R 配對 | R 過 | K 過 | 只有 K 過 | 只有 R 過 |
|---|---|---|---|---|---|---|---|---|---|---|
| databench | 1 | 0 | 0 | 0 | 0 | — | — | — | — | — |
| lcb_v1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 0 |
| lcb_v2 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| lcb_v3 | 1 | 0 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 |
| polyglot_py | 1 | 0 | 1 | 1 | 0 | — | — | — | — | — |

## 救回／傷害（描述，相對於 A）

```json
{
 "R_rescues_A_failure": 2,
 "C_rescues_A_failure": 2,
 "K_rescues_A_failure": 1
}
```

## K／R／C 的過程

```json
{
 "K": {
  "n": 3,
  "released": 2,
  "accepted_at_attempt": {
   "1": 1,
   "0": 1,
   "2": 1
  },
  "released_but_hidden_fail": 0,
  "never_released": 1
 },
 "R": {
  "n": 5,
  "retried": 3,
  "retry_reasons": {
   "timeout": 1,
   "no_deliverable": 4
  }
 },
 "C": {
  "n": 5,
  "c_arm_ok": 5,
  "stop_reached": 4,
  "cells_with_sendback": 1,
  "sendbacks_total": 1,
  "install_fail": 0
 }
}
```

## infra_void 與完成偵測稽核

- 最終仍 void 的格：0；被重跑取代的 void：3；K 起不來的單位：0。（逐格清單在 report.json）
- 完成偵測：session 30 段；`late_write_after_done`＝0（非 0 ⇒ IDLE_S 太短）；最終 stop 之後的最大間隔＝0.442 s（IDLE_S＝[15.0]）；完成原因＝{'timeout': 2, 'idle_final': 28}；送出未確認＝0；信任對話框＝0；打字不符＝0。

## 誠實邊界

- 題池不是隨機抽樣的全體：LCB 部分是 C5 的 A 失敗題（93）＋種子抽的 A 成功對照（40），任務題庫是通過天花板規則的題庫；結論只說這個題池。
- A、R、K 共用 A 的第 1 段，工作區有 bridge 寫的 `.vacant/contract.json`（沒裝 Vacant 時不起作用）；C 的工作區沒有契約（有契約會關掉零設定檢查）。這個差別已記進每格 meta.json。
- K 的 bridge 是 non-adversarial 的基準輔助；放行的成品由計分器另行計分，K 的「放行」只代表可見驗收過了。
- 互動式「跑完」是從 session 檔推論的（安靜 IDLE_S 秒）；稽核數字在上面。
- ❌「Vacant 讓 agent 做得更好」不帶條件；❌ 把分項（題庫、角色）當成檢定；❌ 外推到真人互動使用。
