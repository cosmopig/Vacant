# CONCLUSION 2026-11-22 — W3-5 JS 篩選（原生 pi 兩次，exercism JavaScript 池 137 題，Colab L4 vLLM）＋確認批 VOID

篩選批 state＝UNRESOLVED（設計上兩臂完全相同，A 對 A2 本來就不該有差別；這批的用途是選題，不是檢定），harness＝**3c74139794f1**（nonpy）。
數字來源：[`ops/redo/results/w35js_screen_REPORT.json`](../../ops/redo/results/w35js_screen_REPORT.json)。

## 0. 完整分母與選題

- 137 題，每題原生 pi 跑 2 次（A、A2 完全相同）；137 題兩次都有效、void 0 題。
- 2/2 過 **95** 題、1/2 過 **22** 題、0/2 過 **20** 題；整體 A 106/137、A2 106/137（約 77%，比 Python 池的 95% 有空間）。
- 過 ≤1 次的 **42** 題符合條件，超過上限 N=30，照 sha256(task＋`:w35-js-2026-11-21`) 升冪取前 30 題（規則見 `ops/redo/analysis/screen_select.py`，篩選前寫死）；
  選題紀錄 `ops/redo/plans/w35confirm_js_vacantdo_rc4_colab.json.selection.json`。vacant-hope 的查證 agent 從 274 個 cell 重算，選題完全相同。

## 1. 篩選批 REPORT.md（原樣）

# screen_native_jspool_colab — UNRESOLVED

計畫 sha256 `94032b63c3739e4e…`　完成 137/137 對（有效 137，infra_void 0）　產生於 2026-11-21T12:53:54Z

| 臂 | 通過／有效格 | 比率 | 平均嘗試數 | 平均 agent 牆鐘 | 逾時次數 | 驗收放行卻錯 | 平均模型呼叫 |
|---|---|---|---|---|---|---|---|
| A | 106/137 | 0.7737 | 1.0 | 420.4s | 13 | 0 | 12.2 |
| A2 | 106/137 | 0.7737 | 1.0 | 428.6s | 13 | 0 | 11.9 |

**配對（A 對 A2）**：只有對照過 b＝11、只有處理過 c＝11、都過 95、都沒過 20；精確 McNemar 雙尾 p＝1.0；差 0.0 個百分點；題數上淨正 11／淨負 11。

| rep | 對數 | 對照過 | 處理過 | b | c | p |
|---|---|---|---|---|---|---|
| 1 | 137 | 106 | 106 | 11 | 11 | 1.0 |

**驗收訊號對評分器（每一次嘗試）**：放行且對 212、放行卻錯 0、擋下卻對 0、擋下且錯 62。

引用規則：只有 state=EFFECTIVE 且 harness_changed_mid_run=false 的整批數字可以引用；引用時要同時講：模型、agent、題庫、對數、等預算的定義、mean_attempts。INCOMPLETE／UNRESOLVED 不是負結果。


## 2. 確認批：VOID（基礎設施中斷）

確認批（30 題 × 5、A 對 rc4、Colab）跑到約 100/150 對時遺失，**沒有可引用的數字**；原因與處置見
[`ops/redo/results/void/w35js_confirm/VOID.md`](../../ops/redo/results/void/w35js_confirm/VOID.md)（責任在操作者：批次中途換了 keepalive）。
當時決定不在 Colab 重跑（JS 產品臂的判斷依據是 1003 的 hardjs34，快後端）；**後來改變**：有了第二個帳號與 A100 之後改成重跑——同樣 30 題、rc5-final、Colab A100 jobs 4、因預算為 30 題×3 次，計畫 [`w35confirm_js_vacantdo_rc5_a100.json`](../../ops/redo/plans/w35confirm_js_vacantdo_rc5_a100.json)（修訂 f9ab2aed1）。重跑結案時另寫結論，不與這一批合併。

## 3. 後端速度（篩選批、確認批共用同一後端）

Colab L4、vLLM 0.30.0、jobs 6。**篩選批自己的數字**（`python3 ops/redo/analysis/turn_latency.py <篩選批 run root>`，11/22 重跑）：

- 每輪模型回應：中位 4.0 秒／平均 31.4 秒／p90 75.2 秒（n＝3292 輪；兩個原生臂 A、A2 各自 4.0／30.2／72.5 與 4.0／32.6／77.7）
- 原生單次（A）：中位牆鐘 123.3 秒、逾時 13/137
- 篩選批兩臂都是原生 pi，沒有 P 臂，所以沒有「P 內層撞上限」這一項

對照：本機 confirm1c 每輪 5.6／11.8／21.8 秒、confirm2 5.4／11.1／21.4 秒。中位數接近本機，平均與長尾約為本機的 2.5–3.5 倍——和同後端其他批（hardpy26、W3-5 Python）一樣是慢後端的樣子。確認批遺失，沒有可量的完整資料。
