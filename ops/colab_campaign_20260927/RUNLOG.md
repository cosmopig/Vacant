# Colab 批次：pi ＋／－ Vacant v3.6.1（RUNLOG）

> 人類 2026-09-27 的要求（原話摘要）：把 redesign 分支的 Vacant 丟到 Colab 測、不要用 1003／1004（其他 session 在跑）；
> 題目不要跟 DABstep 那批一樣，要「更多公開、新、有公信力」的；邏輯一定是**裝 pi → 裝好 Vacant → 它就被應用**；
> token/s 要高、測得快又完整；平行時每個 pi 要隔離、不能互吃記憶；除了過去的五組題庫，有餘裕再找「任務導向」題組；
> **每個 raw log 都要保存好、本機要有備份**；**做的所有事都要記錄**。
>
> 時間一律 UTC。金鑰、主機名不進這份檔（上游用代號 `g4`）。

## 一、算力選型（2026-09-27）

| 時間 | 做了什麼 | 結果 |
|---|---|---|
| 早段 | Colab CLI（google-colab-cli 0.7.4）登入；有運算單位的帳號是另一個帳號（200 CU） | A100-40GB 5.30 CU/h、A100-80GB（`--high-mem`）6.77、G4 8.90、L4 1.54；H100 沒有權限 |
| 早段 | A100 上用 LM Studio（同 GGUF、同引擎 2.46.0）複製 1003／1004 的後端 | 1 條 64、4 條 106 tok/s；GPU 只用 34–40%，卡在 LM Studio 的 CPU ⇒ 見 `ops/colab_gemma_backend_20260927/` |
| 早段 | A100 上 llama.cpp（9adc7f42，`-np 16 -kvu -fa on`），長對話 4 條（4.6 萬→6.5 萬 token） | 第一通中位數 146 秒、之後 24.3 秒、每分鐘 4.5 通 ⇒ 瓶頸在 prefill |
| 早段 | 查別人的經驗（網路） | vLLM 的 INT4 單條比 llama.cpp 快約 40%；llama.cpp 的甜蜜點 8–16 條；G4 的每 token 成本比 H100 好 |
| ~13:00 | G4（RTX PRO 6000 Blackwell 96 GB、48 vCPU、176 GB RAM）起 vLLM 0.30.0（torch 2.13.0+cu130） | 第一次崩：FlashInfer 的 top-k/top-p 採樣器在 sm_120 誤判「低於 sm75」⇒ `VLLM_USE_FLASHINFER_SAMPLER=0` 後正常。KV 快取 2,084,211 token（262,144 上下文 7.95 條） |
| 13:29 | pi 相容性探針（直打 vLLM） | 基本請求 200；`reasoning_effort:"none"` 200；串流工具呼叫＋`include_usage` 正常；**預設不思考**（推理 token 0），`chat_template_kwargs.enable_thinking` 才會思考 |
| 13:30–13:45 | 長對話吞吐（`bench_long.py`：每條從約 4.6 萬 token 起、10 回合、每回合加 1,500 token、回 200 token） | 見下表 |
| 13:46 | 開 A100-80GB 想比「每 CU 能跑幾題」 | **13:52 在出數字前停掉**（人類問「5600 t/s 不好嗎、為什麼還要測 A100」；另外 A100 只有 12 vCPU，平行 20 幾個 pi＋測試時 CPU 會先卡）。花掉約 0.7 CU、沒有結果 |

長對話吞吐（G4，vLLM，同一個 QAT 權重的 W4A16 版本）：

| 並行條數 | 第一通中位數 | 之後每通中位數 | p90 | 每分鐘幾通 |
|---|---|---|---|---|
| 4 | 33.1 秒 | 5.0 秒 | 5.5 | 30.1 |
| 16 | 131.6 秒 | 13.9 秒 | 15.2 | 37.7 |
| 32 | 255.4 秒 | 27.7 秒 | 31.2 | 37.9 |
| 對照：A100＋llama.cpp，4 條 | 146 秒 | 24.3 秒 | 87.5 | 4.5 |

讀法：
- 同樣 4 條，G4＋vLLM 比 A100＋llama.cpp 快 **6.7 倍**；16 條時每分鐘 37.7 通＝**8 倍多**。
- 16 條以上每分鐘通數不再增加 ⇒ 這種**長**對話在 16 條左右吃滿 GPU。第一通（冷的 4.6 萬 token 全部要讀）的 prefill 約每秒 5,600 token；
  之後每通只有新的那段要讀（prefix cache 有作用：沒有快取的話每通要 150 秒以上，實測 14 秒），瓶頸變成每一步都要讀一遍長長的 KV 快取（記憶體頻寬）。
- 真實的程式題對話短很多（起點約數千 token），可以開更多條；實際開幾條由冒煙量出來再定。
- ⚠ vLLM 預設不回報 `cached_tokens`（表中沒列快取命中率）；正式批次前會加 `--enable-prompt-tokens-details`，讓帳本記得到。

模型身分：
- 1003／1004 跑的是 GGUF（`google/gemma-4-12B-it-qat-q4_0-gguf` @ f6e7774e，sha256 faff1a63…）＋LM Studio。
- 這裡跑的是**同一組 QAT 權重的 vLLM 原生格式** `google/gemma-4-12B-it-qat-w4a16-ct`（compressed-tensors W4A16）：
  `model.safetensors` sha256 `60b6e3989502969d8ae04185d72ecbbc7db63978d5af747a493d53895aa6bfa3`，
  `chat_template.jinja` `ae53464b…`，vLLM 的工具呼叫樣板 `tool_chat_template_gemma4.jinja` `afdbb2ab…`。
- ⇒ **不是逐位元相同的模型**（量化格式與推論引擎都不同），A／C 的比較都在這台、同一個設定裡做，不和 1003／1004 的數字混著比。

## 二、隔離設計（為什麼不用 Docker）

Colab 的 VM 本身就是一個容器，開不了 dockerd；而且人類說「不一定要 Docker，用別的方式隔離就好」。做法（`sandbox.sh`、`cell.sh`）：
1. **每一格一個新的 Linux 使用者**（`a000001`、`a000002`…），home／`/tmp`／工作區全是新的空目錄（700）⇒ pi 的設定、session、Vacant 的 `~/.vacant` 格子之間不可能共用。跑完刪掉使用者。
2. **bwrap 圍牆**：根目錄唯讀；只有自己那一格的 home、/tmp、/app、/logs/agent 可寫；`/home`、`/content`、`/root`、`/srv` 蓋成空的 ⇒ 看不到別格、看不到題庫與隱藏測試、看不到 Colab 上的模型與 log。
3. **計分另開一個新使用者**、另一道圍牆，隱藏測試只在那一步出現。
4. 誠實邊界：沒有獨立 PID 空間（Colab 不准 bwrap 掛新的 /proc，實測 `Can't mount proc`）⇒ 行程列表看得到別格（看不到別人的環境變數）；網路是通的（要連模型）；沒有 cgroup（計分用 RLIMIT_AS 2 GB）。

13:51 佈署時的圍牆自我檢查（`vm_setup.sh` 第 5 步）：負控制「新使用者讀 `/srv/eval`」→ 讀不到 ✅；圍牆裡 `ls /srv/eval` → 不存在 ✅；`/home` 只看得到自己 ✅。

## 三、產品版本（v3.6.1 wheel）

- 從 redesign 分支 commit `c27641c6` 建，照交接檔 §4（`SOURCE_DATE_EPOCH=1790490188`、`setuptools==84.0.0`、uv 0.8.17）。
- Mac（uv 0.6.16）建出來是 `ba5699cc…`（逐檔 114／114 相同，差在 zip 壓縮位元組）；**13:51 在 G4 的 Linux 上重建 ⇒ `4ec156d6648d214baa9bc5be4093f8b8731112f16a6ee61b6118d70b41def0b4`，與交接檔一字不差** ✅，逐檔比對 114／114、0 不同。批次用的是 Linux 建的這一個。
- pi 0.87.1（`@earendil-works/pi-coding-agent`，`--ignore-scripts`），node v22.23.2；bubblewrap 0.9.0；pipx 1.4.3（apt）。

## 四、一格怎麼跑（逐字對照 Harbor 6cb9ff31 的 pi agent 與 redesign 分支 `ops/eval/harbor_vacant.py`）

- A 組：只有 pi。C361 組：在那一格的使用者底下打使用者會打的安裝指令
  `pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install`（PyPI 下載失敗最多重試 3 次，每次都記）。**不設任何 Vacant 環境變數。**
- pi：`PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent pi --print --mode json --session-dir /logs/agent/pi/sessions --provider harbor-endpoint --model gemma-4-12b-it-qat "<題目>"`，
  models.json＝Harbor 的自訂端點格式（`api: openai-completions`、`apiKey: $OPENROUTER_API_KEY`＝假金鑰 `sk-dummy`）。
- 模型呼叫全部經過記帳代理（redesign 分支 `ops/eval/orproxy.py`，逐字複製，sha256 `bf2d7291…`），網址 `/t/<格子名>/up/g4/think/off/api/v1` ⇒ 每一通的請求與回應全文進 `io.jsonl`、逐通帳進 `ledger.jsonl`；思考強制關（`reasoning_effort:"none"`，同 1004／u274）。
- 時限 1800 秒、**不設回合上限**（同 u274 的條件）。
- C 組跑完讀 `~/.vacant`（redesign 分支的 `_CHECK` 逐字：有沒有裝上、病歷步驟數、交件前檢查次數）。

## 五、raw log 保存（三份）

1. VM：`/srv/eval/cells/<格子>/`（整格）＋代理全文紀錄；`packer.py` 每 10 分鐘把跑完的格子與代理紀錄切成 `chunk_NNNN.tar.xz`＋sha256＋`MANIFEST.tsv`。
2. **本機（Mac）**：`sync_from_colab.sh` 每 10 分鐘照 MANIFEST 拉回、逐個驗 sha256（只存不解壓，批次跑完前不看分數）。
3. Google Drive（`colab drivemount`，要人類在瀏覽器授權一次）：packer 的 `--mirror`，VM 掛掉時的第二份。

## 六、時間線（接續）

- 13:51 G4 佈署完成（`deploy_vm.sh`）：wheel 雜湊相符、pi 0.87.1、圍牆自我檢查通過、記帳代理起來（只聽 127.0.0.1）。
- 13:54 冒煙 1（R534 `lcb_3522`，A＋C361 各一格）：管線通；**C 組 `pipx install` 失敗**（`install_rc=1`）——Colab 把 `/usr/bin/python3` 換成 3.13、卻沒有 3.13 的 ensurepip，pipx 建不了 venv。
  修法：補裝 `python3.13-venv`（修機器、不改使用者的安裝指令；一台正常的 Ubuntu 裝 pipx 就會帶對應的 -venv），寫進 `vm_setup.sh`。
- 13:55 思考檢查：帳本每通 `reasoning_tokens=2`，但 `io.jsonl` 的回應裡**沒有任何推理文字**（串流 delta 沒有 `reasoning`／`reasoning_content`），代理送出的都是 `reasoning_effort:"none"` ⇒ 判讀為空的思考標記，思考實際上是關的。記下，不當成偏差。
- 13:55 計分器負控制：同一題放 `return None` 的樁 ⇒ 隱藏 0/27、可見 0/3；放「全回 -1」的錯解 ⇒ 5/27 ⇒ 都判不過 ✅（冒煙 1 的兩格正解都是 27/27）。
- 13:57 冒煙 2（同一題）：C 組 `install_rc=0`、`vacant install` 認到 pi（`/tmp/harbor-pi-agent/extensions/vacant.ts`）、病歷 6 步、交件前檢查 2 次（`continue` 退回一次 → `allow`）⇒ **「裝 pi → 裝 Vacant → 它就被應用」在 Colab 上成立**。A 組 3.3 秒、C 組 7.7 秒。
- 13:58 vLLM 重開，加 `--enable-prompt-tokens-details`（帳本才記得到 `cached_tokens`；實測第二通 3,008 token 命中）、改只聽 127.0.0.1。
  ⚠ 第一次用 `pkill -f "vllm serve"` 把下指令的那個 shell 也殺了（它的命令列也含那個字串），改分兩步重開。
- 14:00 **吞吐校準**（不是預註冊批次）：R534 全部 20 題 × A／C361，40 格同時開。只看牆鐘、逾時、錯誤碼、GPU；**不看分數**。
  （R534 是 LCB 衍生的 20 題，可能和 LCB 題庫重疊；所以不看它的分數。）
- 14:00 打包（`packer.py`，每 10 分鐘）與本機同步（Mac `~/Vacant_colab_raw/sync_from_colab.sh`，每 10 分鐘）開始；14:02 第一個 chunk 已拉回本機、sha256 相符。
- 14:01 Google Drive 掛載要人類在瀏覽器授權（`colab drivemount` 印出授權網址、等 Enter）⇒ 待人類操作。
- 14:05–14:28 **`colab exec`（走 kernel）隨機卡住**：監看腳本 14:04 之後每一次 exec 都等到逾時；同時一支只印 `alive` 的 exec 卻會回。
  沒有重開 kernel（vLLM、驅動、打包都是從 kernel 底下 nohup 起的，重開可能連帶殺掉）。改法：**狀態查詢改走 `colab console`（tmux 殼）跑、結果寫檔再 `colab download` 拉回**（`vmrun.sh`）；
  本機同步也改成只用 `colab download`（拉 MANIFEST.tsv 與 chunk），不再用 exec。
- 14:27 **校準結束**（14:00:51 → 14:27:13，40 格一起開）：40／40 完成、**0 逾時**、C361 20／20 裝上且有作用（`c_arm_ok`）、安裝失敗 0、代理非 200 共 0 通。
  - 每格牆鐘：A 中位數 607 秒（最長 1595）、C361 449 秒（最長 1427）；每格模型呼叫中位數 A 11、C 10 通（最多 29／30）。
  - 465 通呼叫：輸出 token 中位數 68，但 **33 通 ≥ 8,000、不少頂到 16,384（pi 對自訂模型的預設 `maxTokens`）**——模型原地打轉，吃掉大部分牆鐘（輸出總數 74 萬 token）。A 20 通、C 13 通。不改 pi 的設定（這就是使用者會遇到的樣子），照實記。
  - 輸入 token 中位數 7,057、p90 48,942、最大 117,675；**快取命中 87%**。
  - 14:06 的 vLLM 指標（當時 13 條在跑）：生成 2,289 token/秒、prompt 7,583 token/秒、KV 只用 10% ⇒ 還有很多空間，正式批次可以開更多格。
  - 看的只有牆鐘、逾時、錯誤碼、token；**沒有打開任何 score.json**。
- 14:40 題庫 agent 確認五組題目檔是最終版；staged 到 VM（923 題；工作區只有 goal.md／contract.md／run_tests.sh／test_visible.py，掃過沒有參考解與隱藏測試）。
- 14:45 **計分器改成量具同一套判準**（`scorers/code_suite.py`）：原本每條 `check_*` 另開行程，HumanEval+ 每題約 1,000 條會拖到逾時被判 void；
  改成 `acceptance.run_suite` 的做法（整檔一個行程、DRIVER_SRC 逐字），整檔 60 秒（量具 30 秒的 2 倍）。
- 14:50 **計分器驗證**（VM 上 1,450 次，40 並行，每次中位數 0.2 秒）：退化樁 923／923 不過；參考解 524／527 過。
  沒過的 3 題（HumanEval/32、Mbpp/590、Mbpp/623）是浮點平台差（求根收斂到另一根、複數、負次方），Mac 上量具是過的 ⇒ **具名排除**，剩 920 題。
- 14:52 任務導向題庫 agent 交件（InfiAgent-DABench 30、DataBench／SemEval-2025 30、Aider Polyglot Python 34；計分器全部驗過），
  並回報 **v3.6.1 不認 `sh run_tests.sh` 是跑測試** ⇒ 跑過測試還是會被退回 `test_claim/none`。
  校準的病歷（不看分數）印證：C 的 12 次退回裡 11 次是 `test_claim/none`，6 格都跑過 `run_tests.sh`（指令本文在 `~/.vacant/trace/objects/`）。
  決定：**不改題目去配合產品**，照原樣量淨效果，誤退的格數列成描述數字（預註冊第八節 9）。
- 15:0x 預註冊凍結（`decisions/prereg/PREREG_20260927_COLAB_CODE5_A_VS_C361.md`）。
- 14:58 發射前核對：VM 上 11 支工具的 sha256 與凍結 commit `45564cb5` 逐支相同；plan 920 題 sha256 `dadc283f…`；抽 6 題 staged 的 scorer.py 與 code_suite.py 相同；vLLM 200、代理在線。
- 14:59 人類完成 Google Drive 授權（`colab drivemount`）⇒ VM 上 `/content/drive/MyDrive` 可寫（agent 的圍牆把 `/content` 整個蓋掉，看不到 Drive）。鏡像目錄 `MyDrive/vacant_colab_20260927/`。
- **15:00:0x 發射 `c5`**（`launch_batch.sh c5 … 48 2026-09-28T02:59:50Z`）；`launch_record_c5.json` 在 VM 的 `/srv/eval/`（會隨 chunk 歸檔）。
- 15:02 **可行性規則判定：通過**（最先 40 格：逾時 0、代理非 200 0／280 通、C 裝不上 0）。
- 15:04 打包程式換成帶 `--mirror` 的版本（先前那支一啟動就看到校準的完成旗標、收完尾自己結束；launch_batch 起的那支沒帶鏡像）。
  ⚠ 又一次 `pkill -f <字串>` 殺到自己的殼（命令列含同一字串）⇒ 之後一律用 Popen 的清單參數啟動、不在同一條殼指令裡 pkill＋啟動。
- 15:05 本機同步重開（14:41 它看到校準的 PACKER_DONE 就結束了）；運算單位護欄開（< 25 CU 放停止檔）；監看每 5 分鐘（不讀分數）。
- 15:05 狀態：64 格完成、0 逾時、C 30／30 生效、每格牆鐘中位數 35 秒。
- 16:0x 題庫 agent 交件（`1548369c`，量具零排除；參考解 12/12、12/12、12/12、371/371、156/156；退化樁在可見全擋；與既有判準 5,350 份比對 43 份不一致、全是既有判準較嚴、原因全歸類）。
  **核對**：用它最終 commit 的樹重新 staged，五組樹雜湊與發射前釘在預註冊的 `c1ff347f`／`f5294430`／`73004ec4`／`a45f1f45`／`aef3d619` **逐一相同** ⇒ 第一批跑的就是交件的題目。已併進本分支。
- 15:00–21:02 c5 跑完：1,840／1,840 格；逾時 136（7.4%）；代理 16,242 通、非 200 共 0；C 920／920 生效。中途的監看從頭到尾沒讀分數。
  ⚠ 吞吐比校準低（全機約 500 生成 token/秒）：vLLM 對 Gemma 4（全域層 head 維度 512）強制用 TRITON_ATTN，長對話 decode 慢；凍結中不改引擎。
- 21:05 infra_void 檢查（只印 void 清單）：**0 格** ⇒ 不需補跑。
- 21:06 **第一次打開分數**，跑凍結的 analyze.py：A 748／920、C361 758／920；b＝59、c＝49；McNemar 精確雙尾 p＝0.387 ⇒ **不顯著**。
  退回 472 次：`test_claim/none` 455（293 格跑過 run_tests.sh 仍被判沒跑＝誤退）、`failed_step` 21、`unsourced` 1、`missing_output` 0。結果與事後拆解見 `results_c5/README.md`。
- 21:13 本機同步收齊 43／43 chunk（sha256 全對）、SYNC_ALL_DONE。
- 🔴 21:02–約 22:10 **G4 空轉約 1 小時、浪費約 10 運算單位**：沒有設「批次收完自動關機」（只有低餘額護欄）。22:10 左右 session 已不在（不是我下的 stop）。人類質問後補上教訓：之後同步完成即 `colab stop`。
- 報告：`decisions/conclusions/CONCLUSION_20260928_COLAB_C5_PI_VACANT361.md`（另存一份在 Mac 備份目錄 `REPORT.md`）。
