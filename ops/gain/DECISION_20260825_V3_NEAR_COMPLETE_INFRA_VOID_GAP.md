# 2026-08-25 round 76/77 — v3 run 到 60/60 attempted，但 4 格 infra_void 卡住官方判定

## 發生了什麼

`runs/g_onoff5_qwenonly_v3_20260824`（PID 1790934，ON+OFF5 兩臂、qwen only、
n=60，round69 就在跑，round76 開場時仍活著 etime 15:34:07）在本輪（round76，
2026-08-25 03:00-03:12 UTC 之間）**process 自然結束**（`main()` 正常跑完，
不是 crash——`ps`/`pgrep` 都找不到這個 PID 了，且 summary.json 被完整寫出、
帶著 SPEC_GAIN §7 要求的 `⚠ run_complete=False` 警告訊息，這是程式設計好的
正常收尾路徑，不是意外中斷）。

**兩臂都跑到 tasks=60**（i 跑滿 1-60），但：

```
ON:   infra_void=1（mbppplus_Mbpp/223, careful-1, TimeoutError 重試2次仍失敗）
      measured=59, accepted=48, correct_delivery_rate=71.19%
OFF5: infra_void=3（mbppplus_Mbpp/297,232,744，三筆都是 HTTPError 400 Bad Request
      重試4次仍失敗，三個不同 persona：careful-2/careful-1/plain-2）
      measured=57, accepted=57, correct_delivery_rate=71.93%
OFF baseline（既有的 g_off60_qwenonly_20260824，complete=true）:
      measured=60, correct_delivery_rate=78.33%
```

`gain_run.py` 的 `complete` 定義是 `n_void == 0`（逐字元）——**任何非零
infra_void 都讓那條臂判定為不完整**，`analyze_onoff5.py` 的 `verdict()`
看到任一臂 `complete=false` 就直接拒答：「ON 或 OFF5 尚未跑完 ⇒ 不判定」。
這不是工具寫得保守，是 **SPEC_GAIN.md §7 的逐字規定**：

> 端點 timeout／人工中止的 run 必須寫成 incomplete；部分臂或部分題的漂亮比例
> 不得拿來比較。

## 為什麼這是本輪最重要的判斷點

**這是這個實驗跑了 76+ 輪以來，第一次兩條臂都到了 60/60 attempted**（v1/v2
之前都在更早的進度就被交接／中止）。120 個 (arm×task) 格子裡，116 個量到了，
只差 4 個（3.3%）。

但 SPEC_GAIN §7 的規則是**零容忍**：只要有一個 infra_void，「有成效」判準
第 2、3 條（三臂有差異、等預算下誰贏）就不能用這份資料回答——即使數字已經
擺在眼前（OFF 78.33% > OFF5 71.93% > ON 71.19%，看起來像是反直覺的「兩個
機制都輸給最土的單發」）。**這組數字目前只能當「初步觀察」，不能當「結果」
寫進結論。**

## round64 四條推翻條件——這條線可以現在判，跟上面那條線分開

`analyze_off5_matched.py`（唯讀、只用 OFF5 288 通 gen 呼叫裡 `ok=true` 的
278 通，58 題）：

```
min n/persona = 40（careful-1）  ⇒ ≥30 條件 (1) ✓ 達成（第一次）
題內配對劣勢 = -19.21pp（≥15pp）        條件 (2) ✓
配對置換 p = 0.001350（<0.05）；
本輪是第5次連續 look（round63×3+round64×1+本輪×1），
Bonferroni ×5 = 0.00675，仍 <0.05        條件 (3) ✓
重算混合效應 = +0.61pp（|效應|<3.0pp）   條件 (4) ✗ 不成立
```

**四條要全中才推翻「不開新臂」，(4) 不成立 ⇒ round61/64 的決定維持**（不開
ON-random-routing 臂）。這條線本身不需要更多判斷，是機械套用 round64 已經
寫死的規則——已經在本輪做完，不留給下一輪。

## 卡住的是完全另一件事：怎麼把最後 4 個 infra_void 格子填掉

這才是需要判斷、留給下一輪（建議 Opus）的部分。`gain_run.py` **沒有
resume/backfill 模式**——`--out` 指到已有內容的目錄會被擋（防止污染），
但也沒有「只重跑缺的那幾格」的路。選項：

1. **整條重跑**（新 `--out` 目錄，n=60 兩臂）——乾淨但貴：這輪耗時
   實測約 15-16 小時（round69 開場 etime 12:10 到本輪結束 etime 15:34+），
   而且不保證下一輪就不再有 infra_void（HTTP 400 這三筆看起來像 relay
   在長時間高負載下偶發，不是特定題目的結構性問題——同一題其他 persona
   都成功，見下方證據）。
2. **幫 `gain_run.py` 加 `--backfill <existing_out_dir>` 模式**：讀
   既有 `notes.jsonl` 抓出哪些 (arm, task_id, persona) 是 infra_void，
   只重跑那幾格，用 `'a'` 模式 append 進同一份 `rows.jsonl`/`calls.jsonl`，
   重算 `summary.json`。好處：4 格幾分鐘內能填完，不用再等 15 小時。
   風險：969 行的成熟 runner，backfill 邏輯要小心不要跟主迴圈的抽籤／
   一致性機制（OFF5 的多數決、ON 的信譽路由份額）產生副作用——**這是本輪
   沒有動手做的原因**，倉促改一個正在被當成主要證據來源的 runner 風險
   太高，值得下一輪用完整的注意力設計。
3. **人工補測**：寫一支獨立唯讀腳本，只對這 4 個 (arm,task,persona) 组合
   呼叫端點、手動組出跟 `gain_run.py` 完全相同格式的 `rows.jsonl`/
   `calls.jsonl` 條目 append 進去。比選項 2 風險更高（格式對不齊會產生
   壞掉但看起來正常的資料，之後很難查）。**不建議**，除非選項 2 被判斷
   太冒險。
4. **修 SPEC_GAIN §7 的零容忍門檻**，允許小比例 infra_void（例如 ≤5%）
   時仍可判定 `complete=true`、附帶容忍率一起報。這是**改動性活動規則
   本身**，SPEC_GAIN.md 是規格文件，改它需要人類過目（不屬於「花錢／
   不可逆／sudo」三條紅線，但改「誠實邊界」這一節份量重，建議至少讓
   下一輪的判斷寫清楚為什麼，而不是本輪自己單方面改規格）。

## 支持選項 2 優先於選項 1 的證據（不是猜測）

3 筆 OFF5 的 HTTP 400 都不是「這題本質上打不通」——**同一題的其他 persona
呼叫全部成功**（`mbppplus_Mbpp/297`：`plain-1/hasty-2/plain-2` 皆 OK，只有
`careful-2` 那一次 400；`232`：`plain-1/hasty-2/careful-2/plain-2` 皆 OK，
只有 `careful-1` 那一次 400；`744` 同理）。ON 的那筆 `223` 也一樣，`careful-1`
本身在其他題目上正常運作（`297` 題 `careful-1` 第一次 timeout、第二次重試
就成功）。⇒ **這是端點在 15 小時馬拉松高負載下的偶發失敗，不是特定
prompt/task 內容觸發的結構性 400**，符合選項 2「重打那幾格就好」的前提。

## 沒做的事（照實寫）

- 沒有動 `gain_run.py`（backfill 功能只是提案，沒有實作）。
- 沒有嘗試選項 3（人工組資料）或選項 4（改 SPEC）。
- 沒有把 OFF 78.33% vs ON 71.19% vs OFF5 71.93% 寫成「結果」——這組數字
  現在只是 `analysis_onoff5_verdict.json` 裡的原始 arm 統計，`verdict`
  欄位本身就寫著拒答，GAIN_STATE.md 的結論段落會照抄這個拒答狀態。

## 下一輪建議

Opus——這是「實驗設計的取捨」（選項 1-4 怎麼選）疊加「結果反直覺、要判斷
是真發現還是 bug」（OFF 贏兩個機制不是不可能，但也可能是路由/評審機制的
真實缺陷，需要跟 round64 已經做過的路由歸因分析放在一起看，不能只看
表面數字就下結論）。
