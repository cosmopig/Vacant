<!-- 狀態：**凍結**（2026-09-27，發射前 commit）。凍結之後這一份與它釘住的東西不准再改；要改＝另一份預註冊。 -->

# 預註冊：五組程式題庫 × pi 0.87.1，沒裝 vs 零設定 Vacant v3.6.1（Colab G4、gemma-4-12b QAT）

分支 `feat/colab-campaign-20260927`（不動 `claude/vacant-verification-redesign-jv7eou`）。工具與逐步紀錄：`ops/colab_campaign_20260927/`（`RUNLOG.md`）。

## 一、為什麼要這一份

redesign 分支正在 1003／1004 上跑 DABstep 的 274 題（u274）。人類 2026-09-27 要求：把**同一個 Vacant（v3.6.1）**丟到 Colab 測、
題目**不要跟那批一樣**、邏輯一定是「**裝 pi → 裝好 Vacant → 它就被應用**」、要快、要完整；除了過去的五組題庫，有餘裕再找任務導向的題組。
這一份是第一批：**過去的五組程式題庫，全部題目**。任務導向的題組另寫一份。

## 二、問題

同一個 agent（pi 0.87.1）、同一個模型與伺服器、同一個隔離環境、不設回合上限，**只差有沒有打使用者的安裝指令**：
**主要**：裝了 Vacant v3.6.1（C361）之後，隱藏測試全過的比例和沒裝（A）有沒有不同？（雙尾：變好或變差都算。）

零設定 Vacant 在 agent 說做完時檢視它自己的紀錄，只在五種情況退回（`vacant_network/trace/review.py`，redesign 分支）：
要求的檔不存在（`missing_output`）、失敗的步驟（`failed_step`）、測試說法與紀錄不符（`test_claim`）、值沒有出處（`unsourced`）、點名的檔沒讀（`unread`）。
**它不判斷答案對錯**，也看不到隱藏測試。

## 三、兩組

| 組 | 做什麼 |
|---|---|
| A | pi 0.87.1，照 Harbor 6cb9ff31 的 pi agent 呼叫（`cell.sh`） |
| C361 | 同上，另外在**那一格的使用者底下**先打 `pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install`（redesign 分支 `ops/eval/harbor_vacant.py` 的同一行） |

不設任何 Vacant 環境變數、不寫契約、不開提醒。C361 沒裝上照算 C361（意向治療）。

## 四、釘住的東西

| 項目 | 值 |
|---|---|
| 算力 | Google Colab G4（NVIDIA RTX PRO 6000 Blackwell Server Edition 96 GB、48 vCPU、176 GB RAM），一台 |
| 推論 | vLLM 0.30.0（torch 2.13.0+cu130），`VLLM_USE_FLASHINFER_SAMPLER=0`；旗標見 `ops/colab_campaign_20260927/backend/serve_vllm.sh`（上下文 262144、prefix caching、`--tool-call-parser gemma4 --reasoning-parser gemma4`、`--enable-prompt-tokens-details`） |
| 模型 | `google/gemma-4-12B-it-qat-w4a16-ct`：`model.safetensors` sha256 `60b6e3989502969d8ae04185d72ecbbc7db63978d5af747a493d53895aa6bfa3`、`chat_template.jinja` `ae53464b…`；工具樣板 `tool_chat_template_gemma4.jinja` `afdbb2ab…`；對外名 `gemma-4-12b-it-qat`；**思考關**（代理強制 `reasoning_effort:"none"`） |
| agent | `@earendil-works/pi-coding-agent@0.87.1`（`--ignore-scripts`），node v22.23.2；models.json＝Harbor 自訂端點格式（`openai-completions`）；**沒有回合上限**；時限 1800 秒 |
| C361 wheel | `vacant_network-0.8.0-py3-none-any.whl` sha256 `4ec156d6648d214baa9bc5be4093f8b8731112f16a6ee61b6118d70b41def0b4`（在 G4 的 Linux 上從 `c27641c6` 重建，與交接檔一字不差；114 檔逐位元組相同） |
| 記帳代理 | redesign 分支 `ops/eval/orproxy.py` 逐字複製（sha256 `bf2d7291dbba06784e5f6fa856f5742ab9e044ea12b0cb60bd8b24276fcb1525`），本機模式、上游代號 `g4` |
| 隔離 | 每格一個新的 Linux 使用者＋bwrap（`sandbox.sh`）；計分另一個新使用者；見 RUNLOG 第二節 |
| 題庫 | 五組，由題庫轉換（`ops/vacantrun/colab_banks_20260927/`；MBPP+／HE+ 的題目檔在 `.vacant-private/`，不進 repo）後 staged；staged 樹的 sha256（檔名＋每檔 sha256 依序串起來）：LCB v1 `c1ff347f…`（89 題）、LCB v2 `f5294430…`（118）、LCB v3 `73004ec4…`（189）、MBPP+ `a45f1f45…`（371 取 369）、HumanEval+ `aef3d619…`（156 取 155）＝**920 題**；全長雜湊在 `launch_record_c5.json`。plan `plan_code5.json` sha256 `dadc283f427aed840c9e31523fea6b2f1f919e420b175226389591747dc1803d` |
| 排除 | 3 題：`HumanEval/32`、`Mbpp/590`、`Mbpp/623`——參考解在這台的計分環境（Linux、Python 3.13.15）隱藏沒全過（多項式求根收斂到另一根、複數、負次方的浮點差），計分器在這幾題判不準。其餘：參考解 524／524 全過（MBPP+、HE+；LCB 沒有參考解）、退化樁 920／920 不過（可見與隱藏都不過） |
| 給 pi 的那一句 | `Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.`（同 2026-09-24 BCB 批次） |
| 計分 | `scorers/code_suite.py`（sha256 `298396bc…`）＝題庫量具用的判準（`acceptance.run_suite`：一個測試檔所有 `check_*` 同一個行程、DRIVER_SRC 逐字）；整檔時限 60 秒（量具 30 秒的 2 倍，VM 較忙）、RLIMIT_AS 2 GB；`pass`＝隱藏（可見 ∪ 隱藏）全過；可見用題目**原本**那一份 |
| 驅動與分析 | `driver.py`、`cell.sh`、`sandbox.sh`、`packer.py`、`analyze.py`、`vacant_check.py`（本 commit 的版本，sha256 見 `launch_record.json`） |

## 五、跑的方式與停止規則

```
bash /opt/eval/bin/launch_batch.sh c5 /srv/eval/plan_code5.json 48 <發射時間＋12 小時> PREREG_20260927_COLAB_CODE5_A_VS_C361.md
```
- 每題 1 次；`random.Random(20260928)` 打亂題目順序；**同一題的兩組同時開始**（一起佔位置）；48 格同時（＝24 題）。
  48 是看校準（R534 20 題 × 2 組 40 格一起開：0 逾時、KV 只用 10%）定的，校準**沒有看分數**。
- **時間上限**：過了不再拿沒開始過的題；已開始的題兩組都跑完。只看時間，不看評分。題目順序隨機 ⇒ 停下時跑完的是隨機子集。
- **可行性規則**（只看例外類型與時間，不看評分）：最先跑完的 40 格裡，若 ≥ 30% 碰到 1800 秒時限、或代理非 200 的通數 ≥ 10%、
  或 C361 裝不上 ≥ 3 格 ⇒ 放停止檔、不分析、改設計另寫一份。
- **運算單位**：餘額低於 25 CU 就放停止檔（留給收尾與任務導向那一批）。
- **infra_void**（`analyze.py`）：沒有 DONE、沒有可解析的 score.json、代理帳本裡這一格 0 通、或任何一通最終不是 200／有串流錯誤。
  驅動結束後把 void 的格子移開、同一組參數再叫一次（只補開始過的題）；補跑也 void ⇒ 那一題不進分析、列出來。
- **盲**：批次跑完之前不打開任何 score.json；進度紀錄（`progress.jsonl`）與監看只有 rc、牆鐘、逾時、安裝、token。
- **原始資料**：每 10 分鐘 `packer.py` 打包（格子全部內容＋代理全文 io.jsonl 輪替段＋帳本）＋sha256；本機 Mac 每 10 分鐘拉回驗 sha256
  （`~/Vacant_colab_raw/colab_campaign_20260927/`）；收尾後 chunk 與 MANIFEST 進 repo（或註明放哪）。

## 六、分析（`analyze.py`，本 commit 的版本；批次與補跑都結束後跑一次）

- **完整配對**：同一題 A 與 C361 都不是 void。
- **主要檢定（只有一個）**：五組合併，`pass` 的不一致對 b（只有 C361 過）對 c（只有 A 過），**McNemar 精確檢定，雙尾 α＝0.05**。
- 同時要報的（描述，不檢定）：五組分開的配對表；每組可見全過、**假完成**（可見全過但隱藏沒全過）、沒交 solution.py、1800 秒時限次數、牆鐘、token；
  C361 的退回（有沒有走到交件前檢查、退回幾次、每次的 finding 類別）；**「跑過 `run_tests.sh` 之後仍被判 `test_claim/none`」的格數**（誤退，見第八節 9）；
  **「只有 A 過」的格子逐一列出**，附 C 的退回類別、逾時、有沒有交檔（可能的傷害）。

## 七、事先寫死的說法

- 顯著、C361 較好：「在這 N 題（五組程式題庫）、Colab 上的 gemma-4-12b QAT（vLLM、關思考）、pi 0.87.1、不設回合上限下，
  只多打使用者的安裝指令，隱藏測試全過的比例較高（b 對 c，p＝…）」，並一定要同時說**機制**：Vacant 不判對錯，它只在紀錄對不上時退回
  ——要用退回的類別與退回後的結果說明差別從哪裡來，不說「答案變好」。
- 顯著、C361 較差：照實寫，列出「只有 A 過」的格子、退回、時限。
- 不顯著：「這一批沒有量到差別」＋點估計與配對表；**不說**「沒有效果」，也**不說**「裝了不影響」（那要另做等效檢定）。
- 不外推到別的模型、別的 agent、開思考、有回合上限的使用，也不和 1003／1004、u274 的數字混著比。

## 八、已知的偏差

1. **模型不是逐位元相同**：1003／1004 跑 GGUF＋LM Studio；這裡是同一組 QAT 權重的 W4A16 版本＋vLLM。A／C 都在這裡比。
2. **沒有 Docker**（Colab 的 VM 本身是容器）：隔離改成每格新使用者＋bwrap；**沒有獨立 PID 空間**、**網路是通的**、沒有 cgroup。
3. Colab 的系統 python 是 3.13（補裝了 `python3.13-venv` 讓 pipx 能用）；題目的測試也用這個 python 跑。
4. 題庫汙染：MBPP+／HumanEval+ 是 2021 年的題目，模型很可能看過；LCB 三版有日期窗（見題庫 README）。兩組一樣，但**天花板**可能讓不一致對變少。
5. 可見／隱藏的切法沿用 repo 既有的 V/GT 定義（題庫 README 寫出處），不是各題庫官方的。
6. 校準用的 R534 20 題是 LCB 衍生的，可能和 LCB 題庫重疊；校準只看了牆鐘、逾時、token，**沒有看分數**。
7. 長輸出打轉：校準 465 通裡 33 通 ≥ 8,000 輸出 token（pi 對自訂模型的預設上限 16,384）；兩組都有，牆鐘因此拉長；不改 pi 設定。
8. 寫這一份的人看過這些題庫在**別的設定**（G 實驗、R529、R532）的結果；這個設定（pi＋v3.6.1＋Colab）在這些題上**一跑都沒有**（校準的 R534 除外）。
9. **已知的產品缺陷（寫這一份之前就知道）**：v3.6.1 只把 pytest／`python -m unittest` 之類的指令認成「跑測試」，**不認 `sh run_tests.sh`**；
   而這五組的 contract.md 叫 agent 用 `sh run_tests.sh`。⇒ agent 跑過測試、說測試過了，C361 仍會退回 `test_claim/none`（還可能附一條「tests_visible 沒打開」）。
   證據：任務題庫 agent 的 L-fake 探針（`task_banks_20260927/common/runtests_sh_probe_report.json`）與本批校準（R534：C 的 12 次退回裡 11 次是 `test_claim/none`，
   6 格都跑過 `run_tests.sh`；只看了病歷、沒看分數）。**不改題目去配合產品**：這一批量的就是 v3.6.1 原樣在這種題目上的淨效果（真的退回＋誤退）。
10. 計分器在校準之後、凍結之前改過一次（每條另開行程 → 量具同一套、整檔一個行程），原因是 HumanEval+ 每題約 1,000 條檢查；校準的分數沒有被看過。

## 授權

人類 2026-09-27（對話原話）：「你就把它那個分支的vacant丟到colab去測……你題目也不要找跟他一樣……我要的邏輯一定是你去裝pi然後裝好vacant他就可以被應用」、
「我希望可以token/s多，然後快速測好測完整」、「如果要平行測試你也應該要用隔離的方式去做」、「除了我們過去的五組題組，有餘裕的話……每個log raw都要很好的保存跟我本機的備份」。
agent 在開跑之前凍結；**人類沒有逐條簽字**——結果只能說「預註冊的批次量到／沒量到」，對外當成「證明」之前要人類補簽。
