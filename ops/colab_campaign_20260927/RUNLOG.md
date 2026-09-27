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
