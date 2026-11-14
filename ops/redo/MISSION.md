# MISSION — 這條分支只回答一個問題

> 人類 2026-11-14（原話）：「你開新的分支我在去讓他自己迭代 把它自己迭代的任務、harness什麼的有的沒的
> 也都寫好讓他可以比較好做 不要再讓他去做沒有意義的開發」
>
> 每一輪開頭讀這一份。這一份和別的檔衝突時，以這一份為準（紅線除外，見 §六）。

## 一、問題

**同一個原生 agent、同一個本機模型、同一個牆鐘上限：「工作區自己的測試沒過，就丟掉工作區、開全新行程重來」
交出通過的成果的比例，是不是比「一次跑到底」高？**

- A＝pi 跑一次，上限 1800 秒。
- R3＝pi 每次最多 600 秒；題目**原本的**測試沒過就重開，最多 3 次，合計不超過 1800 秒。
- 迴圈在父行程（`ops/redo/redo.py`），agent 不裝任何 Vacant 的東西。量的是機制。

## 二、為什麼是這一題（三行）

1. repo 裡所有量到交付變好的設定都是「可執行驗收＋重抽」：R460R、R529、realrun v4／v6／v7。
   但 v4–v7 用的是沒有工具的 `mini_agent`；原生 pi 上量過的只有「同一個工作階段裡退回」
   （e001／e002／e016），沒有量到差別。**原生 agent＋重開這一格沒有跑過。**
2. e001／e002 的 34 題每題 4 跑：12 題永遠過、6 題永遠不過、**16 題時過時不過**。單跑 55%；
   抽 2 跑取過的 68%、抽 3 跑 76%（離線估計，不是量測）。
3. 那 68 跑裡通過的 35 跑**全部在 900 秒內結束**（34 跑在 600 秒內）；沒過的有一半拖超過 900 秒。
   所以把 1800 秒切成 3×600 幾乎不犧牲單次的通過率。

第 2、3 點的數字：`python3 ops/redo/analysis/headroom_from_e001_e002.py`（只讀 repo 內的歸檔，0 次模型呼叫）。
「同模型再跑一次、答案一致才交」為什麼不在這裡：`ops/redo/analysis/agree_sim.py` 的檔頭。

## 三、階梯（照順序；每一階只有一個結束條件）

每一階對應 `ops/redo/tickets/` 的一張票，票裡有逐字的指令與驗收。

| 階 | 做什麼 | 結束條件 | 沒過怎麼辦 |
|---|---|---|---|
| S0 | `selftest`＋`preflight`＋冒煙 2 對 | `REDO_SELFTEST_OK`、`PREFLIGHT_OK`、冒煙 2 對 0 個 infra_void | 修環境（題庫路徑、provider 名稱），**不改 harness 的判定邏輯** |
| S1 | 篩選：16 題 × 1 次 | 16 對跑完，照計畫檔的 `go_rule` 判 GO／NO-GO | NO-GO ⇒ 停，寫結論，回報人類 |
| S2 | 確認：34 題 × 5 次＝170 對 | `REPORT.json` 的 `state` 不是 INCOMPLETE | 只能續跑；不准改計畫 |
| S3 | 只有 S2＝EFFECTIVE 才做：把同一個政策做進產品指令，再用同一支 harness 量 | 見票 T05 | — |
| S4 | 只有 S2＝EFFECTIVE 才做：換模型（qwen3.8-27b）、換 agent（OpenCode） | 見票 T06／T07 | — |

S2 的結果是 UNRESOLVED 或 CONTRADICTS 時：**停下來**，把 `REPORT.md` 原樣放進結論檔，回報人類。
不准加重複數、換題、改時限之後再看一次——那是看結果改實驗。

## 四、什麼算進展

只有兩種東西算這一輪有進展：

1. **`REPORT.json` 多了有效的對數**（真的模型呼叫跑出來的）。
2. **產品碼的改動，而且它讓 harness 量到的數字變了**（S3 之後才有）。

下面這些**不算進展，而且不准做**（過去 1500 輪大部分的時間花在這裡）：

- 替已經結束的實驗寫「結案量具」「複核腳本」「closure check」。
- 替量具再寫量具、替測試再寫守門測試、替 NOW.md／STATE.md 的字句寫守門測試。
- 只改簿記檔（NOW／STATE／BACKLOG）的輪次。簿記只在真的有新數字或新 commit 時順手更新。
- 重新驗收前幾輪已經驗收過的東西（「機械複核輪」）。
- 動 `vacant_network/reqloop/`、`ops/reqloop/`、G 系列、L008。那條線凍結，不是這條分支的事。
- 在一批跑到一半時改 `ops/redo/redo.py` 或計畫檔。真的有 bug：修、commit、**換新的 root 重跑整批**，
  並在結論檔寫明舊的那批為什麼作廢。
- 讀 `<題庫>/<題>/hidden/` 或 `scorer.py` 的內容。
- 修與 redo 無關的既有紅燈（`freeze_check`、`ci_tip_check`、`check_repo_links.py` 的舊死連結、別的分支的同步）。
  這條分支開出來的時候它們就是紅的；它們守的是舊線的簿記。

沒有票可以做、長跑還在跑的時候：這一輪就只做一次 `status`，寫一行進 NOW.md，結束。**空輪比亂做好。**

## 五、怎麼跑（長跑不要綁在一輪裡）

```bash
cd ~/dev                                   # repo 根目錄；下面的路徑都相對它
python3 ops/redo/redo.py selftest          # 26/26，約 10 秒，0 次模型呼叫
python3 ops/redo/redo.py preflight --plan ops/redo/plans/redo1_pi_gemma12b_polyglot34.json

# 發射（跑在這一輪之外；同一個 root 只會有一份 runner，重複啟動會被擋）
ROOT=~/dev/ops/redo_runs/redo1             # 在 repo 外面的 ops 碟，不進 git
mkdir -p "$ROOT" && setsid nohup python3 ops/redo/redo.py run \
  --plan ops/redo/plans/redo1_pi_gemma12b_polyglot34.json --root "$ROOT" \
  >> "$ROOT/nohup.log" 2>&1 < /dev/null &

# 之後每一輪最多看一次
python3 ops/redo/redo.py status --root "$ROOT"
```

- 中斷了就用同一行指令再啟動：已完成的格不重跑，做到一半的那一格整格重做。
- 題庫不在預設路徑：`--bank <路徑>` 或 `REDO_BANK=<路徑>`。
- 一格是 `infra_void`（端點掛了）：先把端點弄好，刪掉那一格的目錄
  （`$ROOT/cells/<題>/r<k>/<臂>/`），再啟動同一行指令。不准因為它沒過或過了而刪格。
- 第二台機器：在計畫檔的 `providers` 加一項。**只能在那份計畫第一次發射之前改**（改完 commit）。
  同一對的兩臂一定在同一台。

## 六、紅線（沿用，不新增）

- 鐵律 1–6（`CLAUDE.md`）。KS-1：harness 的提示模板已經過檢查，不要加字。
- 不 push main、不 reset／rebase、`.github/workflows/` 只讀。
- 口徑：EFFECTIVE 時可以說的句子寫在計畫檔的 `prereg.states`，照抄，不要自己發明更強的說法。
  這是 **harness 裡的機制**的數字，不是「裝了 Vacant」的數字，S3 做完之前不可以寫進 README。
- NOW.md 裡「凍結／受控解凍」那一行保持逐字不動（有測試在看它；那四個檔這條分支本來就不碰）。

## 七、可以轉的旋鈕（S2 之後；一次只轉一個）

每轉一個旋鈕＝複製一份計畫檔、只改那一項、取新的 `id`、commit、先用 16 題篩選再上 34 題。

| 旋鈕 | 怎麼改 | 為什麼值得量 |
|---|---|---|
| 產品化 | arm 加 `agent` 覆寫成產品指令（T05） | 機制有效之後，使用者要的是一個指令 |
| 模型 | `providers` 換成 qwen3.8-27b（T06） | 大一點的模型失敗比較是系統性的，重開的空間可能較小 |
| agent | `agent.argv` 換成 OpenCode（T07） | 迴圈在父行程，理論上換平台不用改；要量才知道 |
| 提示 | R3 的 `hint` 改 `first_failure` | v5 在 mini_agent 上沒量到差別；優先度低 |
| 次數／時限 | `max_attempts`、`attempt_timeout_s`（總預算不變） | 2×900 對 3×600 |

不在這張表上的想法：寫進 `ops/redo/IDEAS.md` 一行，不要做。

## 八、人類要做的事（一次）

1. 把本機迴圈指到這條分支；把 `ops/redo/tickets/` 的票放進迴圈取票的地方（照編號順序，一次一張）。
2. 確認題庫路徑與 pi 的 provider 名稱（T01 的 preflight 會直接告訴你對不對）。
3. S1 的 GO／NO-GO、S2 的 state 出來時看一眼 `REPORT.md`。其餘不需要簽字。
