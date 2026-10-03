<!-- 狀態：**草稿，等 lead 凍結**。凍結流程在第四節末：（1）本機 `freeze_i1001.py --fill` 填兩張表、（2）lead commit（這個 commit 就是凍結點）、（3）VM 佈署後 `freeze_i1001.py --check --vm` 全過才准發射。凍結之後這一份與它釘住的東西不准再改；要改＝另一份預註冊。第四節的兩張表與 Vacant 來源 commit 在凍結前是占位字（見 freeze_i1001.py 的 PLACEHOLDER）。 -->

# 預註冊：互動式 pi 0.87.1 × 「沒裝 Vacant 時解不開的題」——沒裝 vs 零設定 Vacant（v3.7）、只重試 vs 可見驗收把關（Colab G4、gemma-4-12b QAT）

依據：人類 2026-10-01 的要求（第十三節〈授權〉有原話）；`ops/colab_interactive_20261001/RUNBOOK.md`（怎麼跑、每步的時間與 CU）、`STAGING.md`（題池怎麼備、計分器量具）、
`LOCAL_E2E.md`（本機端到端）；`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` 第十一節（v3.7）；
`decisions/conclusions/CONCLUSION_20260928_COLAB_C5_PI_VACANT361.md`（C5，同一台 G4、同一個模型，但是 `pi --print`；在 `feat/colab-campaign-20260927` 分支）；
`decisions/conclusions/FINDINGS_20260928_PR82_BRIDGE_REVIEW.md`（K 臂用的 bridge；審查指出 CONFORM 的上限大半是「撞時限重跑」，需要「不用套件、預算相同的重跑對照組」＝這裡的 R）。
格式與停止規則沿用 `PREREG_20260927_NOCAP_UNSEEN.md` 與 colab 分支的 `PREREG_20260927_COLAB_CODE5_A_VS_C361.md`。

## 一、為什麼要這一份

先前三批預註冊的測量（付費 DABstep 正式批次、Colab 程式題 920 題 C5、u274）都沒有量到 Vacant 零設定與沒裝的差別。兩個共通的限制：
（1）題目大半 A 本來就會解（C5：A 748／920＝81%），不一致對少、檢定力低；（2）都用 `pi --print`——只給題目、沒有互動介面。
人類 2026-10-01 的要求把這兩點都改了，也加了成本與收尾的要求。這份預註冊把每一句話變成一條可執行的規則：

| 人類的要求 | 這份預註冊的規則 |
|---|---|
| 先測沒有 Vacant 的；沒有解不開的題、或滿分，就不要繼續測、換題目；要先知道一般 agent 沒裝時真的有題解不開 | 題池只收「沒裝時已經解不開」的題：LCB 取 C5 的 A 失敗題＋少量 A 成功的對照；任務題庫先**只跑 A**篩選，A ≥ 9/10 就整庫丟掉（第五節）。主跑結果裡「A 沒解開的題數」是首要的描述數字 |
| 盡可能用互動介面、不要 `pi -p` 只給題目 | 每一段 session 都是真的 pi TUI 跑在 tmux 裡：等頁腳出現、打同一句話、按 Enter、等它做完、Ctrl-D 離開（第三、四節）。沒有任何 `--print`／`-p` |
| 盡可能維持固定變因 | 第四節的整張表；A 與 C 同時開；位置數、牆鐘上限、終端機大小、模型、計分器全部固定 |
| 最少運算資源內完成最多的可用穩定實驗 | 題目順序種子洗牌、一個單位（A＋C＋巢狀的 R／K）完整才進分析 ⇒ 任何時候停下來，手上都是一個隨機子集的完整配對；第十節的 CU 上限；失敗的基礎設施格自動重跑一次、不手工補 |
| 資料備份到那個帳號的雲端 | 三份：VM（每 10 分鐘一個 chunk＋sha256）、Google Drive 鏡像（`colab drivemount`，有運算單位那個帳號）、本機（`sync_i1001.sh` 逐 chunk 驗 sha256）；Drive 沒掛好不發射（第十節） |
| 用完資源就關掉、不要空著 | 三道自動關機（第十節）：批次收完＋備份驗完 ⇒ `colab stop`；CU 軟／硬上限；時限。driver 沒在跑時 VM 不准空著 |

這一批只花運算單位，**沒有付費模型呼叫**。本專案的交付是展覽，不是論文：這一批的用途是讓展場與對外口徑有根據（哪些話能說、哪些不能），
不是統計發表——第十二節的措辭規則因此比一般報告更嚴。

## 二、問題

**Q1（主要檢定 T2，產品問題）**：同一個 agent（pi 0.87.1）、同一個模型與伺服器、同一個隔離環境、同一句任務、同一個互動方式、不設回合上限，
**只差有沒有打使用者的安裝指令**（`pipx install <wheel> && vacant install`，之後零設定）：C（裝了）的隱藏測試通過率和 A（沒裝）有沒有不同？（雙尾：變好或變差都算。）
零設定 Vacant 只在 agent 說做完時檢視它自己的紀錄，只在五種情況退回（要求的檔不存在、失敗的步驟被略過、測試說法對不上、值沒有出處、點名的檔沒讀；`vacant_network/trace/review.py`）；
**它不判斷答案對錯，也看不到隱藏測試**。

**Q2（主要檢定 T1，機制問題）**：只有 LCB 題才有可見驗收套件。給同一段第 1 次嘗試，之後
**K**（用可見驗收把關：不過就帶著檢查的回報就地再來，最多 3 段，只放行過的）對 **R**（沒有任何驗收：只在逾時或沒交件才在複本上重來，最多 3 段）——
被放行且隱藏測試全過的比例有沒有不同？R 是 K 的預算對照：它回答「K 的好處是不是只來自多給幾次機會」。
K 用的是 PR #82 的 native acceptance bridge（`conform` 模式）：它需要一份可執行的驗收套件（＝契約），**不是**零設定產品路徑；T1 的結論不能講成零設定 Vacant 的效果。

兩個問題都是「同一題配對」。K、R 與 A、C 的預算不同（K、R 最多 3 段 session，A、C 一段），所以**不做 K／R 對 A／C 的優劣比較**，只描述（第八節）。

## 三、四組

| 組 | 做什麼 | 計分的工作區 | 跑在哪些題 |
|---|---|---|---|
| **A** | 互動式 pi，沒裝 Vacant。打同一句、等它做完（一段 session） | 第 1 段結束時的工作區快照 | 全部 |
| **C** | 同上，另外在**那一格使用者的環境**先打使用者自己的安裝指令：`pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install`（與 `cell.sh` 逐字同一行；失敗重試最多 3 次）。**沒有契約、不設任何 Vacant 環境變數、回合預算提醒維持預設關**。Vacant 在 agent 說做完時可在同一段 session 內退回（一個要求內最多 2 回合） | 最後的工作區 | 全部 |
| **R**（RETRY-NOSUITE，巢狀在 A） | A 的第 1 段就是第 1 次嘗試。**逾時或沒有交件**（交付檔不存在或 0 位元組）才在 A 最後工作區的**複本**上開新的互動 session（同一句話、**沒有任何回饋**），最多 3 段，留最後一段。A **沒逾時且有交件** ⇒ R＝A（不重試，成績沿用 A 的）；**逾時就重試，即使逾時前工作區裡已有交付檔**（規格寫的是「逾時或沒有交件」；`tui_lib.needs_retry`；LCB 池裡 C5 的 A 格屬這一種的有 29 個，第十節的 R 單位數 63 就是照這條數的） | 最後一段的工作區 | 全部 |
| **K**（CONFORM，巢狀在 A） | bridge `prepare --mode conform`（`stop_check` 關）在 A 的第 1 段**之前**以接收端（root、receiver home 在工作區之外、agent 是另一個帳號、驗證沙箱 bwrap）跑；每段 session 之後 `judge`：accept ⇒ `release --artifact` 並停；否則在 A 的**原工作區就地**開新 session（同一句話＋可見檢查的原文回報＋一句中性的請求，過 KS-1 防呆），最多 3 段。**沒被 accept 過＝什麼都沒放行＝沒交** | **被放行的成品**（沒放行＝沒交；放行的檔與 A 第 1 段那份逐位元相同時沿用 A 的成績） | 只有 LCB（任務題庫沒有 `check_*` 形狀的可見驗收；polyglot 要另包一層，沒做、沒驗） |

- **巢狀**：A、R、K 共用 A 的第 1 段 session。差別只來自第 1 段之後。
- **工作區對等**：LCB 單位的 A、R、K 的第 1 段工作區有 bridge 寫的 `.vacant/contract.json`（沒裝 Vacant 時不起作用）；C 的工作區**沒有**契約（有契約會關掉零設定檢查）。任務題庫單位的 A 與 C 工作區一樣（都沒有契約，K 不跑）。meta 欄位 `workspace_has_bridge_contract` 記下這個差別。
- **K 的指標**：被放行且隱藏測試全過。隱藏測試是可見的超集（`pass`＝可見∪隱藏全過），所以「把關擋下的解」不會是隱藏全過的解（除了計分器 60 秒時限那幾題慢解，見第十三節）。
- **一個單位**＝一題。A 線與 C 線**同時開**（同一時段的負載對兩組一樣）；A 的第 1 段結束後 R、K 才開（各自拿位置，接續段優先於新單位）。

## 四、釘住的東西

### 固定變數

| 項目 | 值 |
|---|---|
| 算力 | Google Colab G4（NVIDIA RTX PRO 6000 Blackwell Server Edition 96 GB、48 vCPU、176 GB RAM），**一台、整批同一台**；8.90 CU／小時（RUNLOG 第一節） |
| 推論 | vLLM **0.30.0**（獨立 venv、torch 2.13.0+cu130）；`VLLM_USE_FLASHINFER_SAMPLER=0`；旗標逐字：`--served-model-name gemma-4-12b-it-qat --max-model-len 262144 --gpu-memory-utilization 0.90 --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 --chat-template /content/tool_chat_template_gemma4.jinja --limit-mm-per-prompt '{"image": 0, "audio": 0}' --async-scheduling --enable-prompt-tokens-details --host 127.0.0.1 --port 18000`（`vm/vllm_up_i1001.sh`，旗標取自 C5 實際跑完 1,840 格的 `serve_vllm.sh`）；只聽 127.0.0.1 |
| 模型 | `google/gemma-4-12B-it-qat-w4a16-ct`：`model.safetensors` sha256 `60b6e3989502969d8ae04185d72ecbbc7db63978d5af747a493d53895aa6bfa3`；`chat_template.jinja` 前綴 `ae53464b`；工具樣板 `tool_chat_template_gemma4.jinja` 前綴 `afdbb2ab`（`vllm_up_i1001.sh` 會核對，不符就停）；**思考關**（記帳代理 `think/off`＝`reasoning_effort:"none"`） |
| agent | `@earendil-works/pi-coding-agent@0.87.1`（`npm --ignore-scripts`）、node v22.23.2；models.json＝Harbor 自訂端點格式（`openai-completions`）；**不設回合上限**；`PI_OFFLINE=1`（所有組：pi 啟動不去下載 `fd`，模型請求位元組相同；這是與 C5 唯一多出來的環境變數） |
| 互動方式 | tmux（每格自己的 socket）160×50、`TERM=xterm-256color`、history-limit 50000；等頁腳 `(harbor-endpoint) <模型>` 出現才打字；單行用 `send-keys -l`、多行（K 的回報）用括號貼上；打字後 10 秒內沒動靜再按一次 Enter（`submit_unconfirmed` 記下）；第一則 user 訊息必須逐字等於打進去的字，否則該段 void |
| 給 pi 的那一句 | `Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.`（C5 同一句；任務題庫同一句，見 `PLAN_BATCH2_TASK3.md`） |
| 每段牆鐘上限 | **1800 秒**（從 pi 行程開始算，同 C5）；逾時＝殺 tmux、殺該使用者全部行程、記 rc 124，**不是 void**，照樣計分 |
| 完成偵測 | session jsonl 的結尾是最終的 assistant 條目（`stop`／`length`／`aborted`，或重試用完的 `error`）、沒有活著的 `vacant_network hook` 行程（C）、且 session 位元組／代理帳本／hook 事件檔安靜 **`IDLE_S`＝15 秒**；之後 Ctrl-D。15 秒是實測最大間隔（Vacant 送回 0.37–0.48 秒）的約 30 倍、pi 最長退避（8 秒）的約 2 倍；在錄好的 6 種結尾上重播過、含負控制。稽核欄位 `late_write_after_done`、`max_gap_after_final_s` 一定要報 |
| 隔離 | 每格一個新的 Linux 使用者＋bwrap（`sandbox.sh`，與 C5 逐字相同）；計分另開新使用者；沒有 PID 空間、網路是通的（同 C5） |
| 並行 | **`--slots 32`**＝同時在跑的 pi 對話數，整批固定（長對話在 16–32 條吃滿 vLLM；C5 用 48 條）。位置數會影響逾時率——報告要寫 |
| 隨機種子 | `20261001`：LCB 對照的抽樣、任務題庫篩選的抽樣、主跑的題目順序（`random.Random(f"{seed}-main")`） |
| Vacant | **v3.7**：wheel 由 repo HEAD 建一次、凍結、整批共用（C 組與 bridge 的 venv 都裝它）。來源 commit `a5abd7597364f5222f99aeedd6a1a5d6a550f008`；wheel 內 `vacant_network/` 與該 commit 逐檔相同（`freeze_i1001.py --wheel-vs-git`）；wheel 檔本身的 sha256 在下面工具表的 `wheel` 列 |
| 計分器 | `scorers/{code_suite,dabench,databench,polyglot_py}.py`＋`code_checks.py`（第一批逐字複本，`MANIFEST_REUSED.json`）；LCB 整檔時限 60 秒、RLIMIT_AS 2 GB；任務題庫的計分器把例外收成 `scorer_error` ⇒ 這批的 `tui_cell.parse_score` 一律當 infra_void（不算 agent 答錯）；量具結果見 `STAGING.md` 第四節 |
| 驅動與分析 | `vm/driver_i1001.py`、`vm/tui_cell.py`、`vm/tui_lib.py`、`vm/plan_builder.py`、`analyze_i1001.py`、`vm/feasibility_i1001.py`（本 commit 的版本；下面的表） |
| 發射紀錄 | 發射時 `launch_record_i1.json` 另記 VM 上量到的：tmux／bwrap／python／kernel 版本、vLLM 版本與完整指令列、GPU、pi、node、模型 sha256、每個 `/opt/eval/bin` 檔的 sha256、selfcheck 摘要（含 bridge 的 `/proc` 墊片有沒有用）、傳給 driver 的全部參數 |

### 題目（staged 樹）

題目內容（敘述、隱藏測試、參考解）**不進 repo**，放在 scratchpad 的 staged 目錄、經 bundle 上傳。來源與重現：`STAGING.md`。
LCB 三題庫的隱藏測試與樣板取自 `origin/feat/colab-campaign-20260927`（b19395a5）的 `ops/vacantrun/colab_banks_20260927/lcb_v{1,2,3}`；
整庫重新 staged 與 C5 發射時釘的樹雜湊逐一相同（v1 `c1ff347f…`〔89 題〕、v2 `f5294430…`〔118〕、v3 `73004ec4…`〔189〕）。池裡的子集樹雜湊（凍結時重算填表）：

<!-- STAGED_SHA256_BEGIN -->
| 名稱（題庫＝目錄樹雜湊；其餘＝檔案） | sha256 |
|---|---|
| `MANIFEST.json` | `f6e46b93f4f8624cfbf58bc7a7691fe8acd6683140acc56744207b74597ddd46` |
| `dabench` | `da5bad0417f1b2d625eb48476bf260fdc6aa17e7a8f7fb87a16ad9f55d497fed` |
| `databench` | `e2343f4febd62baf23eae7d922777035f4567f931701b3a662cdbb54bb51bb8b` |
| `lcb_v1` | `b6b26fb7f8fbf2aa72618eec67fb1565603cc2f6b2f749727688e7c340a27e61` |
| `lcb_v2` | `6c9b8e556bbc3483fcdb3f49a33d3bd850c4dbb54ed1b80723daae9901a49502` |
| `lcb_v3` | `c47db5cc7e163cdc1789d193cd8f771d20d2a41f92b4645b7e60ef0392794f31` |
| `polyglot_py` | `fa1929c198d7218fd1529247f0d6a8e21529ef7fc3b095acfff72f80f2394a0a` |
| `tasks_index.json` | `d7f41a23de1855426d3c9855caf5b138c325ad7ec012f4ee21f48236c02e6410` |
<!-- STAGED_SHA256_END -->

### 工具與 wheel 的 sha256（凍結時填）

`vm/` 底下的檔經 bundle 佈署到 `/opt/eval/bin/`、`scorers/` 到 `/opt/eval/bin/scorers/`、bridge 到 `/opt/eval/bridge/ops/eval/`；其餘是本機專用。
重用第一批的檔（`MANIFEST_REUSED.json` 另有來源 sha256 與 `--check`）。**這張表與 VM 上實際佈署的檔逐位元相同，才准發射。**

<!-- TOOLS_SHA256_BEGIN -->
| 檔案（相對於 `ops/colab_interactive_20261001/`） | sha256 |
|---|---|
| `MANIFEST_REUSED.json` | `6960486195625733a28c09e0119a7ef77f37a4d60c29f4fe6a14de707a3297e8` |
| `analyze_i1001.py` | `e3b7271fd6d4f9b618a99ffe39754df61653de31f88cf4e94fa8c574ce4c8bed` |
| `autostop_i1001.sh` | `3c820a998946a6cf457fb203782b81fa6fdfe94223dad9cfa30672bc4d19c062` |
| `bridge/native_acceptance_bridge.py` | `5104ae0035c86609a43a679e49820371384ed0e5640cd558d66698857c9eeeec` |
| `build_bundle.sh` | `5e5ca0caadc80af5c34833b04a71062151ed1d1386b54233650614c84cf28d92` |
| `build_manifest.py` | `d613718d472d6f1113b66a61b939397587aa31a5d502c6a983a3d5a72fa077fa` |
| `cu_cap_i1001.sh` | `c82285225799bb688e867f44617565e03fc2bf2a19e1273429e0811b4f43794a` |
| `scorers/code_checks.py` | `d6b145b74621092de73605dbfd38758d02bd21dcdf5f46861833048abceecd36` |
| `scorers/code_suite.py` | `298396bcc6cabe68d9129870ef1be0d7f94b153cc8cd4219504931759714649d` |
| `scorers/dabench.py` | `a541dceda5d091da9ff5fa323dd14220c5c8302935ac85d6f043d79f356435b1` |
| `scorers/databench.py` | `ac5bd5be233e01ba1060ec1e698cd8eb4a73b8a4a023836587d3f415bb057b38` |
| `scorers/polyglot_py.py` | `25ed44f4643200c006f9b8780783366050c2637660ae7873e7f2010a5366f182` |
| `stub_model.py` | `c2e74615f2fc2cb133aec2c828788582c479a087f8b961cf89824620b711e863` |
| `sync_i1001.sh` | `9a123ccd1c595ae6e144a83d36d74566f33429423a2a48f6d8bd9951553fc72d` |
| `vm/cu_guard.sh` | `452a95185339fd79aefe2f5b2a50e308f10b04e32dc37d99e99cc30cedba6122` |
| `vm/deploy_i1001.sh` | `46c7436906ac355840b458ef4826198ef99a6010d636c352e82a50c408b1217a` |
| `vm/driver_i1001.py` | `0caaaaf5ae63327f407a7c5758acc75690f32b9418af775e938ddba838881b42` |
| `vm/feasibility_i1001.py` | `a21768f3d6edd09ca40a5c995fc6cbdd0c18d90fb0eaddc1779ff129656a4d01` |
| `vm/finalize_vm.py` | `e9995a1a891e355f6a962fda5e4c332224088ac92e582365a382ccfddc7921fd` |
| `vm/launch_i1001.sh` | `32ff7f08227673d2918fe84a7f3966110f3e1699722464ed58e30da590acc289` |
| `vm/launch_record.py` | `584694fd133798d64dde5a309283dc13133192f41eaac314030d62019d712db9` |
| `vm/orproxy.py` | `bf2d7291dbba06784e5f6fa856f5742ab9e044ea12b0cb60bd8b24276fcb1525` |
| `vm/packer.py` | `d206cf001276c7c9ff480c0c35f02d149a23f4dcafae85a2e02cd85dcdfe709d` |
| `vm/packer_i1001.py` | `f28c99e02e9f66cc42e472a2b28207942694f3ff52e829581d183e0f9df6aa99` |
| `vm/plan_builder.py` | `26e05555f3fbe25f9c4e120a3af07350c8e8ff3e56c0a396cb5546585f75948f` |
| `vm/sandbox.sh` | `4855e8e4d0a56a06d24fa7d54e28c09e291d738d3646d5095ab8a0c0997a6af3` |
| `vm/smoke_stub.py` | `11757ab9afc42cddc0f80236be6048f5a6ac3378f7c9f55fe6cf197d17ac12ac` |
| `vm/tui_cell.py` | `782273ced78fef3f6151eb3fbcde1076f2dc1faec0341e8360ee54d2c34d27e4` |
| `vm/tui_lib.py` | `8934bc6622e816f495db6914f7d2915252c7fbc4315c14f28eb78474a79f74b5` |
| `vm/vacant_check.py` | `07afff4f22ee23115e507f94c4c8f7276317793bf5ff3a83f7141349295e8661` |
| `vm/vllm_up_i1001.sh` | `f8b96141ff0f5d4cb4e6fd5ad34b5e1ff71a7894df1c9ef39cb7c7e1f662038e` |
| `vm/vm_selfcheck.py` | `06438728ffe4bba451a3e451c7568dc9d097ea278260439d855efa3105950ab1` |
| `vm/vm_setup.sh` | `57348920af55032c7c8015278856f3ef794222a72de4242eaa4957e8ca1cf179` |
| `vmsh_i1001.sh` | `9c6d9a26d9a3968ac40d9e9dc149362fd7957671ffdeeb9be7e68c72b1292d53` |
| `wheel` | `e367d520ad3f80db03bfff7b51c81f95be896941e8a1a90eee6b3810b5a0c818` |
<!-- TOOLS_SHA256_END -->

**凍結程序**：（1）`python3 build_manifest.py --check` 與 `pytest tests/test_colab_interactive_20261001.py tests/test_colab_i1001_ops.py` 全綠；
（2）wheel 從 HEAD 建、`freeze_i1001.py --wheel-vs-git <wheel>` ＝ SAME、填上來源 commit；
（3）`python3 freeze_i1001.py --fill <這份> --wheel <wheel> --staged <staged>`（兩張表）；（4）lead commit ＝凍結；
（5）VM 佈署後 `python3 freeze_i1001.py --check <這份> --vm` 全過；有任何一列不同 ⇒ 不發射（要換檔＝另一份預註冊）。

## 五、題池與篩選規則

**LCB 池 133 題（不篩選）**：C5 的 A 組**沒過**的 LCB 題全部 93 題（v1 27、v2 30、v3 36；拆解：撞時限且沒交 29、撞時限但有交 28、沒交但沒撞時限 5、可見全過隱藏沒過〔假完成〕23、其他可見沒過 8）
＋ A 組**過了**的 LCB 題裡以種子 20261001 抽 40 題作對照（v1 5、v2 16、v3 19；`random.Random(20261001).sample(排序後的 (bank, unit) 清單, 40)`）。
C5 沒有 void 格，池裡沒有因 void 排除的題。池裡 5 題在 C5 的計分撞到整檔 60 秒時限（慢解），判決受機器速度影響，已在 `pool_lcb.json` 標出（第十三節）。
不篩選的理由：它們本來就是「沒裝時已知解不開」（93）與「已知解得開」（40，回歸／傷害對照）。

**任務題庫（dabench 30、databench 30、polyglot_py 34）先篩選**：
1. 每個題庫以 `random.Random(f"i1001-{seed}-{bank}").sample(排序後的 id, 10)` 抽 10 題（MANIFEST 的 `screen_sample`），**只跑 A**，前綴 `i1s`；
2. **A 答對 ≥ 9/10 ⇒ 整個題庫丟掉**（`ceiling_decision.json` 記下理由；不是安靜略過）；其餘題庫的**全部**題進主跑池——含被抽去篩選的 10 題，但主跑**重新跑 A**（篩選的 A 結果不重用：「因為 A 在這些題上表現差而選了這個題庫」會把選擇偏誤灌進 C 對 A）；
3. void 的篩選格先重跑一次；仍 void 的算**沒過**（保守：題庫只在「看到答對」時才被丟）；篩選沒跑完（停止檔／時限）：已看到的答對數 ≥ 9 就決定丟（沒跑的格只會讓數字不變或變大），否則 undecided ⇒ 保留；
4. 這條規則是**規格定的門檻，不是估出來的**：以每題單次、真實通過率 p 計，一個題庫被丟掉的機率 p＝0.5：1%、0.6：5%、0.7：15%、**0.8：38%**、0.9：74%。也就是說真實通過率約 8 成的題庫有三分之一以上的機會被丟——這是人類「滿分就換題」的意思，不是疏忽；
5. MBPP+、HumanEval+ 不在池裡（HumanEval+ 在 C5 的 A 已 150／155＝天花板；MBPP+ 的官方 EvalPlus 包在準備環境沒有）。LCB 池不設天花板規則（A 失敗題 93 題本來就是已知解不開的）。

主跑單位數＝133＋通過篩選的任務題庫題數（最多 227）。

**池的性質（結論一定要帶）**：這個池**不是任何母體的隨機樣本**——它是「C5 的 A 失敗題」加對照加「沒被天花板丟掉的題庫」。絕對通過率沒有意義；
A 與 C 都是**重新跑**的新抽樣，所以對 C5 的選擇（A 失敗）造成的均值回歸對 A、C 兩組一樣（C 對 A 的配對檢定不受它偏）；但**兩組的絕對數字都會比 C5 的 0 對 A 失敗題高**。

## 六、跑的方式與停止規則

```
bash /opt/eval/bin/launch_i1001.sh i1 32 <發射時間＋8 小時 UTC> /content/drive/MyDrive/vacant_i1001
```
（`--phase auto`：篩選 → 天花板規則 → 主跑。完整指令與每步時間見 RUNBOOK。）

- **共用一條佇列**：題目種子洗牌；一個單位的 A、C 一起拿位置；接續段（R、K 的第 2、3 段）優先於新單位，池子不會被新單位塞滿。
- **時限**：`launch + 8 小時`之後不再開**新單位**；已開始的單位照樣跑完（配對不會被切一半）。**只看時間，不看評分。**題目順序隨機 ⇒ 停下時完成的是隨機子集。
- **停止檔** `/srv/eval/STOP`：同樣只擋新單位。誰放：`feasibility_i1001.py`（基礎設施壞了）、`cu_cap_i1001.sh`（軟上限）、lead（只有基礎設施或 CU 的理由）。
- **續跑**：檔案系統就是狀態；driver 被殺後照 RUNBOOK 第五節-7 重啟（不重發射）；已 DONE 的單位一格不重跑。
- **分析的母體**：一個單位的 A、C（以及 R、K，若適用）都有最終的格子才算完整；沒完成的單位（硬上限切掉的、driver 被殺沒續上的）**不進分析**，報告要把它們列出來。
- **盲**：批次跑完之前不打開任何 `score.json`；進度紀錄 `progress.jsonl` 與監看只有 rc、牆鐘、逾時、void、安裝、token。**唯一預先規定的看分數**是篩選階段的天花板規則（只有 A 的答對數、不含任何 C／R／K）。
- **K 整批不可用**：若 `vm_selfcheck.py` 的 K 相關情境在 Colab 上失敗（例如 bridge 的 bwrap 與 `/proc` 墊片都起不來），以 `--nested R` 發射（只跑 A、C、R）——這個決定只看 selfcheck、不看任何分數，且**必須在發射前做**。此時 T1 不做，主要檢定只剩 T2、**用未校正的雙尾 p（α＝0.05）**；`analyze_i1001.py` 輸出的 `p_holm` 在這種情況下不採用（它固定把 T1 的 p＝1 放進家族而加倍 T2 的 p），以 `p_mcnemar_exact_two_sided` 為準。

## 七、主要檢定（兩個，Holm 校正）

兩個檢定都用 `analyze_i1001.py --chunks <本機 chunk 目錄> --out <目錄> --prefix i1`（本 commit 的版本；批次與 void 補跑結束後跑一次）。**精確 McNemar（只看不一致對、二項、p＝0.5、雙尾）**。

| | 母體（配對） | x 組 vs y 組 | 指標 | b／c |
|---|---|---|---|---|
| **T2 C 對 A** | 主跑所有單位（LCB＋通過篩選的任務題庫題）中，A、C 都不是 void 的 | x＝A、y＝C | 隱藏測試全過（A 計第 1 段結束的快照；C 計最後的工作區） | b＝只有 C 過、c＝只有 A 過 |
| **T1 K 對 R** | 有 K 的單位（LCB）中，K、R 都不是 void 的 | x＝R、y＝K | K：被放行**且**隱藏測試全過；R：隱藏測試全過 | b＝只有 K 過、c＝只有 R 過 |

- **多重檢定**：Holm step-down 校正這兩個，家族 α＝0.05（較小的 p 與 0.025 比，較大的與 0.05 比）。結論只講 Holm 之後的。
- 配對的**單位**＝(題庫, 題)；每題每組跑 1 次（`samples: [1]`）。篩選階段的格子（前綴 `i1s`）**不進**這兩個檢定。
- 不一致對數 b＋c < 6 時，這個檢定在數學上不可能達到 p < 0.05（全倒向一邊也 ≥ 0.0625）：報告寫「沒有足夠的不一致對」，不寫「不顯著」。
- **檢定力（估計，寫明不是承諾）**：`vacant_network.research.mcnemar_power`，α＝0.025（Holm 最嚴的一關）。不一致對佔配對的比例（p_disc）用 20–30%
  （C5 在這個池的對照 40 題裡 A、C 不一致 9 題＝22.5%；A 失敗的 93 題裡 42 題不一致，但那被「A 失敗」這個選擇灌大了）。ψ＝不一致對裡倒向「Vacant／K」那一邊的比例：

| 配對數 n（約不一致對） | ψ＝0.55 | 0.6 | 0.7 | 0.8 |
|---|---|---|---|---|
| 133（LCB 池；p_disc 0.2→27 對） | 0.03 | 0.08 | 0.37 | 0.79 |
| 133（p_disc 0.3→40 對） | 0.04 | 0.13 | 0.57 | 0.95 |
| 227（全池；p_disc 0.2→45 對） | 0.04 | 0.15 | 0.64 | 0.97 |
| 227（p_disc 0.3→68 對） | 0.06 | 0.24 | 0.85 | 1.00 |

  讀法：C5 全部 920 題的點估計（b＝59、c＝49，ψ≈0.55）若是真的，這一批的檢定力**不到 0.1**——這一批只有在效果大（ψ ≥ 0.7）時才檢得出來。
  「沒有量到差別」因此大概率是結果，它不是「沒有差別」。

## 八、描述（不檢定；`analyze_i1001.py` 的報告全部會出）

- **首要**：每個題庫與每個池角色（A 失敗／對照／篩選抽樣／任務題庫其餘）的 **A 答對數與沒解開的題數**；篩選階段每個題庫的 A 答對數與天花板決定（丟掉的題庫本身是一個要報的發現：「一般 agent 在這個題庫已接近滿分」）。
- 各組（A、C、R、K）：n、隱藏全過、指標過、**交了**、**錯交**（交了但隱藏沒過）、**沒交**、1800 秒逾時次數、session 總數與平均、牆鐘（總和、中位數）、呼叫數、輸入／輸出 token。K、R 的 session 數／token／牆鐘含與 A 共用的第 1 段。
- 各題庫的 C 對 A、K 對 R 配對表（**描述，不是檢定**；每個題庫檢定力不足）。
- **救回／傷害**（相對於 A）：C／R／K 各「A 沒過它過」與「A 過它沒過」的題，逐題列出；C 的傷害要附 C 的退回類別、逾時、有沒有交檔。
- C 的過程：`c_arm_ok`（Vacant 有沒有真的被載入）、`stop_reached`、有送回的格數與次數、**每次送回的類別**（五類）與送回之後的結果、安裝失敗數。K 的過程：第幾次被接受、放行但隱藏沒過、從未放行。R 的過程：重試原因（逾時／沒交件）與次數。
- 完成偵測稽核：`late_write_after_done`（非 0 ⇒ IDLE_S 太短，要明講）、`max_gap_after_final_s`、完成原因分布、`submit_unconfirmed`、`trust_dialog`、打字不符、離開不乾淨、壓縮（compaction）次數。
- **A 與 C 各自的 void 率**；兩者差 > 5 個百分點時，結論第一行要寫（void 與組別有關會偏）。
- 花費：實際 CU（`colab usage` 前後餘額）、VM 牆鐘、每單位的 session 分鐘（給下一次估計用）。
- **不拿 C5 的任何數字當比較對象**（C5 是 `pi --print`；這一批是互動式）。C5 只用來選池。

## 九、infra_void 規則（沒有評分、或模型一個回答都沒拿到）

不算任何一組的失敗；**整條線**（A 線＝A＋R＋K；或 C 線）以 `v2` 後綴重跑**一次**，第二次仍 void 就留著 void（分析列出、不進配對）。判定（`tui_lib.classify_session` 與 `tui_cell`，全部是基礎設施、不是 agent 的表現）：

- 頁腳一直沒出現（`footer_timeout`）、信任對話框沒處理掉、打字不符（`input_mismatch`）；
- 最終 assistant 條目是 5xx／429／408／402／串流中斷；代理帳本任何一通非 200 或帶 `stream_error`；沒有任何模型呼叫；pi 在第一通請求前就死了；逾時但沒有任何一通完成；
- **C 安裝失敗**（3 次都失敗）——**與 C5 不同**：C5 把沒裝上算成 C（意向治療）；這一批把它當 void（pipx 要從 PyPI 取 `cryptography`，網路問題不是產品的表現）。
  有任何一格因此被排除時，報告要另外給「把這些單位算成 C 沒過」的 T2 敏感度（用配對表手算）；
- 計分器壞掉：任務題庫計分器回 `scorer_error`、計分行程沒輸出（`no_score_reason`）、bridge `prepare`／`judge`／`release` 失敗、工具例外（`harness_exception`）；
- **不是 void（是這一跑自己的結果）**：`length`（被 max tokens 切斷）、其他 4xx（例如 400 上下文太長）、1800 秒逾時但有模型回答、agent 沒交件。

driver 被殺、整台 VM 被回收造成的未完成單位不是 void，而是「未完成」（第六節），不進分析。補跑只由 driver 自動做一次，**不手工挑格子補**。

## 十、運算單位（CU）預算、上限與關機

### 估計（寫明不是承諾；RUNBOOK 第〇節有每一步）

換算的基礎：C5 的 1,840 格（`pi --print`）在 G4 上跑了約 6.0 小時、約 54 CU、格子牆鐘加總 267.4 小時（48 位置、平均同時約 44 格）⇒ **0.202 CU／格·小時**；
全機生成約 470 token／秒、約 45 通／分鐘（TRITON_ATTN，對話一長就慢）。這個池的 C5 牆鐘（拿來估計，不是結果）：A 平均 1,243 秒、C 平均 1,125 秒；
**C5 的 A 失敗題有 57／93 撞 1800 秒（含對照 40 題裡的 1 題＝池裡 58／133）**；R 觸發的單位（A 逾時或沒交件）63／133、K 觸發的單位（C5 的 A 可見檢查沒過）70／133（兩個數都是對 `pool_lcb.json` 逐格數的，不是估的）。互動式多出來的是每段約 +20 秒（IDLE_S 15 秒＋頁腳＋離開）。

| 項目 | 假設 | 中位估計（CU） | 範圍 |
|---|---|---|---|
| 開機 → vLLM 就緒＋發射前檢查 | 約 30 分鐘（vLLM 安裝與下載與佈署／selfcheck 並行；第一批沒量過乾淨的一次） | 4.5 | 3.5–7 |
| 篩選（30 段只跑 A） | 30 段同時開、最慢的一段撞 1800 秒：約 35–40 分鐘，後半段 GPU 近乎閒置（driver 在篩選全部結束才進主跑） | 5.5 | 3.5–7 |
| LCB 主跑 133 單位 | A 47＋C 43＋R 42＋K 40＝約 172 格·小時（R：63 單位 × 1.6 段 × 25 分鐘；K：70 單位 × 1.6 段 × 22 分鐘）。GPU 吞吐限制的換算 ≈ 38（× 0.202 × 1.1）；位置數限制的換算 ≈ 48（172 ÷ 32 位置 × 8.9）；**取兩者中點**（見下面的交叉檢查） | 43 | 29–55 |
| 任務題庫主跑（三庫都留；A、C 各 94 單位 × 15 分鐘＋R 約 25% × 1.6 段） | 約 63 格·小時：GPU 吞吐限制 ≈ 14、位置數限制 ≈ 17.5，取中點。**每段平均牆鐘沒有量過**（第一批的這三庫「約 10–15 CU」也是估計） | 16 | 6–31 |
| 收尾長尾 | 隊伍排空後最後一個單位可能還有 A 一段＋R／K 各兩段＝最長 90 分鐘，GPU 近乎閒置但照計費 | 6 | 3–10 |
| 打包、同步、`colab stop` | packer 在 `DRIVER_DONE` 後約 40 秒收尾 | 1.3 | 1–2 |
| **合計 S1（三個任務題庫都在篩選被丟）** | | **≈ 60**（約 6.8 小時） | 40–81 |
| **合計 S2（三個任務題庫都留）** | | **≈ 76**（約 8.6 小時） | 46–112 |

**交叉檢查（0.202 的換算和 32 位置要對得上）**：0.202 CU／格·小時 ＝ 8.9 ÷ 44，它**隱含平均同時 44 格**（C5 開 48 位置）。這一批只有 32 位置，
而且這個池的 A 組在 C5 有 58／133 撞 1800 秒的牆（C5 全部 1,840 格只有 136 個＝7%）：撞牆的格子牆鐘固定，不會因為伺服器變空而變短（A 組光是這一項就約 29 格·小時）。所以主跑**不是純 GPU 吞吐限制**：
- 純 GPU 吞吐限制（C5 的換算）：172 格·小時 × 0.202 × 1.1 ≈ 38 CU——但這要求平均同時約 40 格，超過 32 位置，所以這只是**下界**；
- 純位置數限制（C5 的牆鐘一點都不縮短）：172 ÷ 32 ＝ 5.4 小時 × 8.9 ≈ 48 CU——伺服器沒那麼擠時沒撞牆的格子會變快，所以這是**大致的上界**（排空的長尾另計在下一列）。

中位數取兩者的中點（LCB 主跑 43、任務題庫 16），**沒有量過、沒有更好的依據**。
**上限刻意定在中位估計附近（軟上限 60 CU）**：人類的要求是「最少的運算資源內完成最多的可用穩定實驗」，發射前帳號餘額 109.9 CU，這一批之後要留至少約 35 CU。
S1（任務題庫全丟）的中位估計 ≈ 60 剛好碰到軟上限；S2（全留）≈ 76 **一定**會撞軟上限——那是設計內的結果（停在完整單位的隨機子集，第六節），不是失敗；
樣本數會比 227 少，第七節檢定力表要改用實際完成的單位數重算。

最大的不確定是互動式 session 的真實牆鐘（與 `--print` 的 C5 是否相近）、R／K 的接續段會再撞多少次 1800 秒、任務題庫的每段時間。**發射後約 60 分鐘用 `progress.jsonl` 的牆鐘（不看分數）重估一次**（RUNBOOK 檢查點 3）。

### 上限（只有 CU 與時間，不看分數）

- **軟上限＝60 CU**：已花 ≥ 60 ⇒ 放停止檔（不開新單位，進行中的單位跑完）。
- **硬上限＝75 CU**：已花 ≥ 75 ⇒ 放停止檔、要求 packer 做最後一包、等 `ALL_DONE`（最多 3 分鐘）、本機同步一次、`colab stop`。進行中、還沒寫 DONE 的單位就此丟掉，**報告要列出**。
  （起始餘額不到 90 CU 時：硬上限＝起始餘額 − 15 CU、軟上限＝硬上限 − 15 CU；硬上限低於 50 CU ⇒ 不發射，先問人類——連篩選加一部分主跑都撐不住。）
- 「已花」＝ max（起始餘額 − `colab usage` 現在的餘額、8.9 × 開機至今小時數）：`colab usage` 可能延遲或失敗，時間估計是不靠它的保險。實作 `cu_cap_i1001.sh`（本機常駐；`--b0`＝`colab new` 之前讀到的餘額、`--t0`＝`colab new` 的 epoch 秒）。
- **時限**：發射後 8 小時不開新單位（第六節）。三道上限的順序：時限（8 h）→ 軟上限（60 CU）→ 硬上限（75 CU）。
- 軟上限與時限讓停下來的樣子是**乾淨的**（完整單位的隨機子集）；硬上限是最後保險、**會丟掉進行中的單位**。硬上限與軟上限之間留 15 CU（約 1.7 小時）給進行中的單位排空——最長的單位鏈約 90 分鐘。

### 關機檢查點（任何一條成立就關機；細節與指令在 RUNBOOK）

| # | 成立條件 | 動作 |
|---|---|---|
| 1 | 開機後 45 分鐘 vLLM 還沒 `VLLM_READY`、或 `deploy_i1001.sh` 沒有 `DEPLOY_OK`、或工具表核對不符 | 查原因最多 20 分鐘；仍不行 ⇒ `colab stop`（重開約 30 分鐘＝4.5 CU，比空轉便宜） |
| 2 | `vm_selfcheck.py` 失敗 | 同上；只有 K 的情境失敗＝見第六節「K 整批不可用」，其餘失敗不發射 |
| 3 | Drive 沒掛好（`touch` 測試失敗）超過 30 分鐘 | **不發射**（人類要求資料在 Drive）；`colab stop`，等人類授權後再開 |
| 4 | 批次收完：`DRIVER_DONE`＋`PACKER_DONE`＋最後一個 chunk 本機 sha256 已驗 | `autostop_i1001.sh` 自動 `colab stop`；本機沒驗完而 VM 上 `MIRROR_OK` 時等 45 分鐘後照樣關機並警告 |
| 5 | 軟上限／硬上限／時限 | 第十節上限；硬上限自動 `colab stop` |
| 6 | 任何時候 driver 沒在跑（沒有進行中的格子）而還要等人類決定超過 10 分鐘 | 資料先確認在 Drive／本機 ⇒ `colab stop`；**driver 還在跑時不為了等人類而關**（會丟掉進行中的單位） |

## 十一、停止規則一覽

| 規則 | 看什麼 | 條件 | 動作 | 看分數？ |
|---|---|---|---|---|
| 天花板（任務題庫） | 篩選階段 A 的答對數 | 該庫 ≥ 9/10 | 整庫丟掉、記進 `ceiling_decision.json` | 只看 A |
| void 率／基礎設施 | `feasibility_i1001.py`：最近 30 個 A／C 線格子的 void 率、這些格子代理呼叫（≥ 50 通）的非 200 率、C 的安裝失敗累計 | void 率 ≥ 30%（至少 10 格）、或非 200 率 ≥ 10%、或 C 安裝失敗 ≥ 3 | 放 `STOP`（不開新單位） | 否 |
| 逾時 | — | **不是規則**：這個池本來就近六成會撞 1800 秒（C5 的 `feasibility.py` 的「逾時率 ≥ 30% 就停」在這裡會誤停，所以換掉） | 只記錄 | 否 |
| CU／時間 | 第十節 | 時限、軟上限、硬上限 | 同上 | 否 |
| LCB 池的天花板 | — | **沒有**：池本來就是 A 失敗題；A 在池上若意外接近滿分，會在最後的 A 答對數看到、如實報告 | — | — |

## 十二、事先寫死的說法

- T2 顯著、C 較好：「在這個題池（C5 的 A 失敗 LCB 題＋對照＋通過天花板篩選的任務題庫題）、Colab 上的 gemma-4-12b QAT（vLLM、關思考）、**互動式** pi 0.87.1、1800 秒／段、不設回合上限下，
  只多打使用者的安裝指令，隱藏測試全過的題數較多（b 對 c，Holm 後 p＝…）」，並一定要同時說**機制**：Vacant 零設定不判斷答案對錯，只在紀錄對不上時退回——用 C 的退回類別與退回後的結果說明差別從哪裡來；
  不說「答案變好」。
- T2 顯著、C 較差：照實寫，列出「只有 A 過」的題、C 的退回類別、逾時。
- T2 不顯著：「這一批沒有量到差別」＋配對表與點估計；**不說**「沒有效果」「裝了不影響」（那要另做等效檢定）。
- T1 的任何結論：「在 LCB 池、…、K（可見驗收把關＋回報、最多 3 段）的『被放行且隱藏全過』數對 R（只重試、最多 3 段）為 …」，並說明 K 需要一份可執行的驗收套件（契約）、bridge 是 non-adversarial 的基準輔助、**不是零設定產品路徑**。
- 一律要帶的條件：題池不是隨機樣本（第五節）；位置數 32；互動式 pi 由腳本打字（沒有真人、沒有追問）；模型是 W4A16 QAT 不是逐位元同一個 GGUF；`IDLE_S` 稽核數字。
- ❌「Vacant 讓 agent 做得更好」不帶條件；❌「Vacant 判斷答案對錯」；❌ 把分項（題庫、角色）當檢定；❌ 把 K 或 R 的通過數與 A 或 C 比優劣（預算不同）；
  ❌ 外推到別的模型／別的 agent／開思考／有回合上限的使用／真人互動；❌ 和 C5、u274、DABstep 的數字混著比（C5 是 `--print`）；❌ 把 `vm_selfcheck.py` 或本機端到端（替身模型）的結果說成 agent 的表現；
  ❌ 把「A 沒解開的題」說成「這些題對所有 agent 都難」（只是這個模型、這個 agent）。
- 展場口徑：用「可究責性／讓依賴有根據」，不用「信任」；任何引用這批的展件要標「預註冊批次量到／沒量到」、「題池是沒裝時解不開的題、不是代表性樣本」、「這是真模型真跑，不是機制模擬」。

## 十三、已知的偏差與沒驗過的事

1. **選擇與均值回歸**：池是 C5 的 A 失敗題（93）加對照（40）。A、C 都是新抽樣，所以 C 對 A 的配對不受選擇偏，但兩組絕對通過率都高於「0」（C5 的 C 在這 93 題過了 42、在 40 題對照過了 31）；不能把絕對數字當成「Vacant 的救回率」。
2. **寫這一份的人看過 C5 的逐題結果**（A 與 C361 都看過，選池用的是 A）；**v3.7 是看過 C5 的 C 組紀錄之後設計的**（離線在 Colab c5 的 C 組病歷上重播：誤退 288 跑放行、新增缺檔 10 跑，`DECISION_20260926_ZERO_CONFIG_V3.md` §十一）。
   所以對 C 來說這個池不是「沒看過」；v3.7 的改動只是去掉誤退與在模型壞掉時硬叫回來，對答對率的上限很小（§十一）。**互動式、K、R 這三件事在這些題上一跑都沒有過**。
3. **互動式不等於真人使用**：腳本打同一句、等 15 秒安靜就判完成、沒有追問。完成偵測是推論（讀 session 檔），稽核數字在報告裡。信任對話框（`.pi/` 之類）的按鍵（Down×4＋Enter）只在筆記裡量過選單、沒在真 pi 上按過；這個池的工作區在本機端到端 31 段 TUI 裡一次都沒觸發過。
4. **模型不是逐位元相同**：1003／1004 跑 GGUF＋LM Studio；這裡是同一組 QAT 權重的 W4A16＋vLLM。A、C 都在這裡比。
5. **沒有 Docker**（Colab 的 VM 本身是容器）：每格新使用者＋bwrap，**沒有獨立 PID 空間、網路是通的、沒有 cgroup**（同 C5）。DABench／DataBench 的答案公開在網路上，agent 有網路就查得到（汙染面，沒擋）；polyglot 的 `example.py` 在公開 repo。
6. **計分器的慢解**：LCB 整檔 60 秒時限，少數慢解（池裡 5 題在 C5 就撞過）的判決取決於機器速度與負載，不是這一批新增的偏差；K 放行的檔與 A 第 1 段那份逐位元相同時沿用 A 的成績（同一份檔不重算）。
7. **K 的 bridge 是 non-adversarial 的基準輔助**（root 接收端；PR #82 的檔，本分支 HEAD 還沒有，這裡是複本，`MANIFEST_REUSED.json` 記 sha256）。bridge 的 `bwrap --proc /proc` 在 Colab 核心上沒驗過（墊片只在本機用假 bwrap 驗過）。
8. **沒在 Colab 上驗過的**：tmux／apt 的 Colab 版本、真 vLLM 下「最終 stop → 下一個條目」的間隔分布與自動壓縮、Drive 的 I/O、真的 `colab` CLI（`usage` 的格式、console 排隊、drivemount 授權）、`vm/vllm_up_i1001.sh`（只驗了語法與 `--dry-run`）、`cu_cap_i1001.sh`／`vmsh_i1001.sh`（只用假 colab 驗過邏輯）。成本是估計，沒有量過。
9. **位置數與逾時**：32 條與 C5 的 48 條不同；A、C、K、R 在同一個位置數下比，但絕對逾時率不能和 C5 比。
10. **檢定力**：見第七節；題庫分項沒有檢定力。每題每組只跑 1 次，單次抽樣雜訊都在配對裡。
11. 這一批的 A 與 C 在同一時段同時開，但 R、K 的接續段在 A 結束之後、負載不同；K 與 R 彼此是同一時段的（同時開始接續）。
12. 重用第一批的工具（沙箱、代理、packer、計分器）逐字不改；本批新寫的驅動（tmux 互動版）在本機只用替身模型端到端驗過（210／210）——驗的是管線，不是 agent 的表現。

## 授權

人類 2026-10-01（對話原話，由 harness 轉述）：

> 沒錯你弄完就去上面測試，測各式各樣的題目，先測沒有vacant的然後如果沒有的情況以及滿分請不要繼續測，去換題目，要先知道一般agent在沒有vacant之下他會有題目解不開才行，然後盡可能使用互動介面不要用pi -p 只給題目 盡可能的維持固定變因 我希望你可以在最少的運算資源消耗內完成最多的可用穩定實驗，以及你的資料應該都要備份在那個帳號的雲端 我之前已經開權限了 且最重要的是用完資源就關掉不要空著

agent 在開跑之前凍結；**人類沒有逐條簽字**——結果只能說「預註冊的批次量到／沒量到」，對外當成「證明」之前要人類補簽。
