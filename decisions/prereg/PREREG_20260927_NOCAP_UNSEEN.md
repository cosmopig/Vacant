<!-- 狀態：**凍結**（agent 在開跑之前 commit；見最下面「授權」）。凍結之後這一份與它釘住的東西不准再改；要改＝另一份預註冊。 -->

# 預註冊：沒用過的 274 題 DABstep hard 題、不設回合上限，沒裝 vs 零設定 Vacant（v3.6.1），本機 gemma-4-12b

依據：`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` 第十一節（篩選與判準）、第十二節（缺檔退回探針）、第十三節（篩選結果：GO）；
`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` 第十節（v3.6／v3.6.1：回合預算提醒預設關）。

## 一、為什麼要這一份

S36-nocap（36 題、每題 2 次、不設回合上限）照事先寫死的判準判定 GO：72 對裡 C 單獨對 13、A 單獨對 2，傷害 0，缺檔退回 9 跑。
但那 36 題是看正式批次的 A 選的，**篩選不是證據**。這一份在**沒有任何一輪跑過**的題目上做一次事先寫死的檢定。

## 二、問題

同一個 agent（pi 0.87.1）、同一個模型（人類自己兩台機器上的 gemma-4-12b-it-qat，關思考）、同一個環境、**不設回合上限**（一般互動使用的樣子），
只差有沒有裝 Vacant：**主要**：裝了現在的產品（C361＝v3.6.1，裝完就是預設：提醒關、交件前檢查開）的答對率有沒有比沒裝（A）高？

## 三、兩組

| 組 | 做什麼 |
|---|---|
| A | Harbor 官方的 pi agent（`--agent pi`） |
| C361 | 同上＋使用者的安裝指令（`ops/eval/harbor_vacant.py`），Vacant v3.6.1（wheel 見第四節） |

不設任何 Vacant 環境變數、不寫契約、不開提醒。不設回合上限時，v3.6.1 送給模型的東西和 S36-nocap 的 v3.6 相同
（v3.6→v3.6.1 在 `vacant_network/` 只改兩個檔：`adapters/cli.py` 的安裝／解除安裝旗標，和 `trace/zerostop.py` 只在「只剩最後一回合」時才走到的一句——沒有上限就沒有最後一回合）；
退回的字句（`trace/review.py`）從 v3 起沒有改過。

## 四、釘住的東西

| 項目 | 值 |
|---|---|
| 評測框架 | Harbor `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` |
| agent | pi `@earendil-works/pi-coding-agent@0.87.1`；`--ak model_api=openai-completions --ak version=0.87.1`，**沒有** `max_turns`（`MAX_TURNS=none`：系統提示裡沒有預算那一行）；題目自己的 agent 時限 1800 秒 |
| 環境映像 | `vacant-eval/dabstep-env:1`（同正式批次） |
| 題目 | `ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json`（sha256 `43a8f4eebd94da98ccdb31822115e5ec64f36c789d7f6807f01094f5baf28ef0`）：Harbor 的 450 題減掉正式 79 題、減掉付費校準的 1716、減掉留出批次的 100 題＝**274 題，全部是 hard 題**；每一題的題目目錄 sha256 都釘住（`make_unseen.py` 先用留出清單的 100 個雜湊驗證釘死的目錄沒變） |
| 模型 | `gemma-4-12b-it-qat`，兩台 LM Studio（`w401c-15`、`1003`；兩台都是 Max Concurrent Predictions 4、上下文 262144、Unified KV Cache），記帳代理本機模式強制 `reasoning_effort=none` |
| C361 wheel | `vacant_network-0.8.0-py3-none-any.whl` sha256 `4ec156d6648d214baa9bc5be4093f8b8731112f16a6ee61b6118d70b41def0b4`（commit `c27641c6` 的 `git archive`、`SOURCE_DATE_EPOCH`＝commit 時間、`uv build --wheel`；建兩次同一個雜湊；裡面 `vacant_network/` 114 個檔與 `c27641c6` 逐位元組相同） |
| 驅動與分析 | `ops/eval/local/run_pairs.py`、`run_local.sh`、`rerun_void.py`、`analyze_local.py`、`s36nc_analyze.py`、`unseen_analyze.py`、`archive_raw.py`、`archive_loop.sh`、`monitor.sh`（本 commit 的版本） |

## 五、跑的方式與停止規則

```
MAX_TURNS=none python3 ops/eval/local/run_pairs.py --harbor <harbor> --jobs <暫存>/local/u274 --dataset <釘死的 450 題目錄> \
  --manifest ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json --arms A=- C361=<wheel> --samples 1 \
  --upstreams w401:4 1003:4 --seed 20260929 --prefix u274 --deadline 2026-09-28T00:00:00Z
```
（實際的啟動檔 `ops/eval/local/launch_u274.sh`。）

- **共用一條佇列**：題目照種子打亂；一個位置空出來先做這台機器已接下的另一組，沒有才拿下一題——**同一題的兩組同一台機器、幾乎同時開始**。
- **停止**：過了 `2026-09-28T00:00:00Z` 不再拿沒開始過的題；已經接下的題兩組都跑完。**只看時間，不看任何評分**。題目順序是隨機的，停下時跑完的是隨機子集。
- **並行的基礎設施規則**（只看代理與機器，不看評分）：開跑後 20 分鐘內，若代理的請求錯誤（非 200 或串流錯誤）超過 10%、或任一台機器 5 分鐘沒有任何回應
  ⇒ 兩台都降成 3 個位置（停驅動、同一組參數改 `w401:3 1003:3` 重叫；續跑會把已接下一半的題排回原來那台），記在 RUNLOG。
- **infra_void**（沒有評分，或模型一個回答都沒拿到；`analyze_local.cells`）：驅動結束後 `rerun_void.py` 移開、同一組參數再叫一次 `run_pairs.py`
  （過了時間上限也只補開始過的題）；補跑也壞 ⇒ 那一題從分析拿掉並列出來。C361 沒裝上照算（意向治療）。
- 原始資料：`archive_loop.sh` 每 2 小時把每一跑的 Harbor 目錄、代理全文與帳、驅動紀錄歸檔進 `ops/eval/evidence_20260927_nocap/u274/raw/`（`MANIFEST.jsonl` 記 sha256），commit＋push；
  `monitor.sh` 每分鐘監測（沒有結果的跑變多、磁碟、代理、dockerd、驅動）。每 3 小時給人一份繁體中文報告（只報進度與運作，**不報中途評分**）。

## 六、分析（`unseen_analyze.py`，本 commit 的版本；批次與補跑結束後跑一次）

- **完整配對**：兩組都有評分、都不是 infra_void 的題。只有一組跑完的題（不應該發生）列出來、不進分析。
- **主要檢定（只有一個）**：`C 單獨對`（C361 對、A 不對）對 `A 單獨對`（A 對、C361 不對），**McNemar 精確檢定，雙尾 α＝0.05**。
- 同時要報的（描述，不檢定）：每組答對／答錯（有檔、評分 0）／沒交；多出來的錯；C361 的退回次數、類別、之後的結果；
  **傷害**（第一次退回那一刻答案檔已經是評分器會收的值，最後錯）；A「說做完卻沒寫檔」的跑數；1800 秒時限每組幾跑；兩台機器分開列；
  **不變式**：同一題第一通請求兩組逐位元組相同。依 C 的路徑拆的數字只描述，不分配功勞。

## 七、事先寫死的說法

- 顯著、C361 較好：「在這 N 題沒用過的 DABstep hard 題、本機 gemma-4-12b 關思考、pi 0.87.1、不設回合上限下，裝了 Vacant v3.6.1 的答對率較高（p＝…）」，
  並一定要同時說**機制**：主要是 agent 說做完、卻沒有照要求把答案寫進檔時，Vacant 在交件前退回，agent 把它**已經說出口的答案**寫進要求的檔（第十二節探針）——
  評分器只看檔，所以沒檔＝0 分；**不是答案本身變好**。對一個在對話裡看得到那一則回覆的人，差別是答案放到了他要的地方。
- 不顯著：「這一輪沒有量到差別」＋點估計與配對表；**不說**「沒有效果」。
- C361 較差且顯著：照實寫，列出傷害與時限。
- 不外推到別的模型、別的題庫、有回合上限的使用、easy 題、開思考。

## 八、已知的偏差

1. 官方 DABstep 用 smolagents、10 步；這裡用 Harbor＋pi、**不設回合上限**、1800 秒時限。
2. 題目沒用過，但**機制**是看過 S36（題目取自正式批次）與正式批次之後才選來測的；退回的字句從 v3 起沒改。
3. 每台同時 4 跑會讓每一跑變慢；1800 秒時限兩組一樣，但 C361 退回之後要多幾回合，碰到時限的機會可能多一點——時限每組幾跑一定要報。
4. hard 題對 12B 關思考很難：答對率低、不一致的配對少，檢定力有限。每題只跑 1 次：單次的抽樣雜訊都在配對裡。
5. 寫這一份時已經看過 S36-nocap 的全部結果與探針的結果（第十三節、第十二節）；**這 274 題沒有任何一跑**。

## 授權

人類 2026-09-27（對話原話）：「提醒預設關掉，測不設上限的缺檔退回……」「好，繼續跑，有結果再跟我報告」「你可以去用好用滿」；
第十一節的 GO 動作（排一批沒用過的題的預註冊批次）是跑篩選之前寫下、人類看過之後說繼續跑的。agent 在開跑之前凍結；
**人類沒有逐條簽字**——結果只能說「預註冊的批次量到／沒量到」，對外當成「證明」之前要人類補簽。
