# i1001 互動式批次（Colab G4）：施工與操作手冊

> 人類 2026-10-01 的要求：在 Colab 上測各式各樣的題目；**先測沒有 Vacant 的**，滿分／沒有解不開的題庫就丟、換題目（要先知道一般 agent 沒裝 Vacant
> 時真的有題目解不開）；**盡可能用互動介面、不要 `pi -p` 只給題目**；固定變數；**最少運算量、最多可用的穩定實驗**；
> 資料備份到有運算單位那個帳號的雲端（Drive）＋本機；**用完資源就關、不要空著**。
> 預註冊：`decisions/prereg/PREREG_20261001_COLAB_INTERACTIVE_I1001.md`（凍結了才發射；CU 估計、上限、關機檢查點、可說與不可說都在那裡）。
> 題目怎麼備的在 `STAGING.md`；pi 的 TUI 實測在 PI_INTERACTIVE_NOTES.md（`i1001/` scratchpad）與 `evidence_pi_tui/`。
> 這份只講：**一步一步怎麼跑（每步的預期時間與 CU、關機檢查點）**、為什麼這樣排、哪些**沒有**驗過。時間一律 UTC；金鑰、主機名、帳號不進 repo／log（上游用代號 `g4`）。
> **這個資料夾的程式沒有碰過 Colab、沒有起過 VM、沒有花過任何模型呼叫**；本機驗證用的是「機制替身」模型（見第七節）。

## 零、一眼看完：時間線、CU、關機檢查點

預註冊：`decisions/prereg/PREREG_20261001_COLAB_INTERACTIVE_I1001.md`（凍結了才發射；第十節有 CU 估計的推導、上限、關機檢查點的完整條件）。
**CU 一律以 G4 ＝ 8.9 CU／小時算**（GPU 計費從 `colab new` 開始、到 `colab stop` 為止，不論有沒有在用）。

### 時間線（預期；第 3–8 步並行，所以「累計」看窗口不看逐列相加）

| 步 | 做什麼 | 預期牆鐘 | CU（累計，G4 計費起算） |
|---|---|---|---|
| 0 | 本機：測試、wheel、凍結、bundle、記起始餘額（**不計費**） | 15–25 分鐘 | 0 |
| 1 | `colab new`＋開 `cu_cap_i1001.sh` | 1–3 分鐘 | 0.1–0.4 |
| 2 | `colab drivemount`（可能要人類在瀏覽器授權一次） | 與 3–7 並行 | — |
| 3 | 開始 vLLM 安裝與服務（背景；長桿） | 指令 1 分鐘，之後 15–25 分鐘在背景 | — |
| 4 | 上傳 bundle＋`deploy_i1001.sh` | 6–10 分鐘 | — |
| 5 | VM 上核對凍結表（`freeze_i1001.py --check --vm`） | 1 分鐘 | — |
| 6 | `vm_selfcheck.py`（替身模型，不用 GPU；與 vLLM 安裝並行） | 4–7 分鐘 | — |
| 7 | 等 `VLLM_READY`、經代理打一通探針 | 開機後約 20–30 分鐘 | 約 3–4.5（T＋30 分鐘） |
| 8 | 發射前閘門（Drive 可寫、selfcheck ok、vLLM health） | 2 分鐘 | — |
| 9 | 發射 `launch_i1001.sh`（篩選 → 天花板 → 主跑） | 1 分鐘 | 約 4.5–5 |
| 10 | 本機開 `sync_i1001.sh`＋`autostop_i1001.sh`（`cu_cap` 第 1 步已開） | 1 分鐘 | — |
| 11a | 篩選：30 段只跑 A（同時開；最慢的一段撞 1800 秒，後半段 GPU 近乎閒置） | 35–40 分鐘 | ＋5.5（累計約 10，T＋70 分鐘） |
| 11b | 主跑：LCB 133 單位＋通過篩選的任務題庫題 | 4–6.5 小時 | ＋38.5（只有 LCB）到＋52（三個任務題庫都留） |
| 11c | 隊伍排空後的長尾（最後一個單位最長 90 分鐘） | 0.7–1.5 小時 | ＋6 |
| 12 | `DRIVER_DONE` → packer 約 40 秒收尾 → 本機驗最後一個 chunk → `autostop` 關機 | ≤ 10 分鐘 | ＋1.3 |
| | **合計**（S1＝任務題庫全被丟／S2＝全留） | **約 6.3 小時／7.9 小時** | **≈ 56／≈ 70 CU（範圍 40–76／46–107）** |

推導（寫在預註冊第十節）：C5 的 1,840 格（`--print`）在 G4 跑約 6.0 小時、約 54 CU、格子牆鐘加總 267.4 小時 ⇒ 0.202 CU／格·小時；
這個池的 C5 牆鐘 A 平均 1,243 秒、C 平均 1,125 秒（A 失敗題 57／93 撞 1800 秒）；R 觸發約 63 單位、K 觸發約 70 單位；互動式每段多約 20 秒。
最大的不確定是互動式的真實牆鐘與任務題庫的每段時間——**發射後約 60 分鐘用 `progress.jsonl`（不含分數）重估一次**（第 11 步的檢查點 3）。

### 上限（本機 `cu_cap_i1001.sh` 常駐；順序：時限 → 軟上限 → 硬上限）

- **時限**：發射後 8 小時不開新單位（driver 自己的 `--deadline`）。
- **軟上限 80 CU**：放 `STOP`（不開新單位，進行中的單位跑完）。**硬上限 100 CU**：放 `STOP`＋要求最後一包＋等 `ALL_DONE`（最多 3 分鐘）＋本機同步一次＋`colab stop`（進行中、沒寫 DONE 的單位丟掉，報告要列出）。
- 起始餘額不到 115 CU：硬上限＝起始餘額 − 15、軟上限＝硬上限 − 20；硬上限 < 70 ⇒ **不發射、先問人類**。
- 「已花」＝ max（起始餘額 − `colab usage` 餘額、8.9 × 開機至今小時）。

### 【關機檢查點】（任何一條成立就關；driver 還在跑時**不為了等人類而關**，那會丟掉進行中的單位）

| # | 成立條件 | 動作 |
|---|---|---|
| 1 | 開機後 45 分鐘沒 `VLLM_READY`／`deploy_i1001.sh` 沒 `DEPLOY_OK`／第 5 步核對不符／GPU 不是 RTX PRO 6000 | 查最多 20 分鐘；仍不行 ⇒ `colab stop -s i1001`（重開約 30 分鐘＝4.5 CU，比空轉便宜） |
| 2 | `vm_selfcheck.py` 沒全過 | 同上；只有 K 的情境失敗 ⇒ 見第 6 步（`--nested R`）；其餘失敗不發射 |
| 3 | Drive 沒掛好（第 8 步 `DRIVE_OK` 沒出現）超過 30 分鐘 | **不發射**，`colab stop`，等人類授權再開 |
| 4 | `DRIVER_DONE`＋`PACKER_DONE`＋最後一個 chunk 本機 sha256 已驗 | `autostop_i1001.sh` 自動 `colab stop`（它沒關就手動關，不要空著） |
| 5 | 軟上限／硬上限／時限 | 軟上限與時限＝等進行中的單位排空後走 4；硬上限＝自動 `colab stop` |
| 6 | driver 沒在跑（沒有進行中的格子）而要等人類決定 > 10 分鐘 | 確認 Drive／本機有資料 ⇒ `colab stop` |

## 一、這一批問什麼（兩個主要檢定，其餘全是描述）

| | 組 | 做什麼 | 計分 |
|---|---|---|---|
| A | 沒裝 Vacant | 互動式 pi，打同一句任務，等它做完 | **第 1 段**結束時的工作區快照 |
| C | 零設定 Vacant（產品） | 使用者自己的安裝指令（`pipx install <wheel> && PI_CODING_AGENT_DIR=… vacant install`），其餘與 A 相同；工作區**沒有**契約 | 最後的工作區 |
| R | RETRY-NOSUITE（巢狀在 A） | A 的第 1 段是第 1 次嘗試；**逾時或沒交件**才在 A 最後工作區的**複本**上開新 session（同一句、沒有任何回饋），共最多 3 段，留最後一段 | 最後一段的工作區 |
| K | CONFORM（巢狀在 A，只有 LCB） | bridge `prepare --mode conform`（`stop_check` 關）在 A 的第 1 段**之前**跑；每段之後 `judge`；accept ⇒ `release` 並停；否則在 A 的原工作區**就地**開新 session（同一句＋可見檢查的回報，無責任措辭），共最多 3 段；沒 accept 過＝什麼都沒放行 | **被放行的成品**，沒放行＝沒交 |

- **主要檢定 1：K 對 R**——指標「被放行 且 隱藏測試全過」（K）對「隱藏測試全過」（R），配對、精確 McNemar。R 與 K 共用 A 的第 1 段，差別只來自「有沒有可見驗收＋回報」。
- **主要檢定 2：C 對 A**——指標「隱藏測試全過」，配對、精確 McNemar。
- 雙尾、α＝0.05，**Holm 校正這兩個**。infra_void 排除並列出；同一格有重跑（`v2`）取最後一次。其餘（各題庫、各題池角色、救回／傷害、錯交、session 數、token、牆鐘）只描述。
- 分析：`analyze_i1001.py --chunks <本機 chunk 目錄> --out <目錄>`（直接串流讀 chunk 裡的 meta.json／score.json，不解壓整包）。

## 二、固定變數（所有組相同；記在每格 meta.json 與發射紀錄）

模型 `google/gemma-4-12B-it-qat-w4a16-ct`（vLLM 0.30.0、`--served-model-name gemma-4-12b-it-qat`、關思考＝代理 `think/off`）、pi 0.87.1、同一份
models.json、同一句任務（C5 那句；任務題庫照 PLAN_BATCH2_TASK3）、每段 session 牆鐘上限 1800 秒（同 C5，從 pi 行程開始算）、**不設回合上限**、
tmux 160x50／`TERM=xterm-256color`／history-limit 50000、`PI_OFFLINE=1`（所有組；pi 啟動時不去下載 `fd`，模型請求位元組相同——這是和 C5 唯一多出來的環境變數）、
每格一個新 Linux 使用者＋bwrap（`sandbox.sh`，與第一批逐字相同）、固定的全域並行（`--slots 32`＝**同時在跑的 pi 對話數**）、
一個單位的 A 與 C **同時開**（同一時段的負載對兩組一樣）、計分一律另開新使用者。

**已知、刻意、已記錄的差別（不是疏忽）**
1. A／R／K 的第 1 段工作區有 bridge 寫的 `.vacant/contract.json`（沒裝 Vacant 時不起作用）；C 沒有（有契約會關掉零設定檢查）。meta 欄位 `workspace_has_bridge_contract`。
2. C 的安裝在那一格的圍牆裡跑（約 20–30 秒，期間佔著一個位置），A 立刻開始；兩者仍在同一個時段。
3. 互動式（TUI）與 C5 的 `--print` 不同：C5 的數字**不能**直接和這一批比。

## 三、題池與篩選

- **LCB 池 133 題**（`STAGING.md`）：C5 的 A 失敗題 93（v1 27、v2 30、v3 36）＋種子 20261001 抽的 A 成功對照 40。不篩選。
- **任務題庫**（dabench 30、databench 30、polyglot_py 34）：**先篩選**——各抽 10 題（MANIFEST 的 `screen_sample`）、只跑 A、前綴 `<前綴>s`。
  **A 答對 ≥ 9/10 ⇒ 整個題庫丟掉**（記進 `ceiling_decision.json`，不是安靜略過）；其餘題庫的**全部**題進主跑池——含被抽去篩選的 10 題，
  但主跑**重新跑 A**（篩選的 A 結果不重用：「因為 A 在這些題上表現差而選了這個題庫」會把選擇偏誤灌進 C 對 A）。void 的篩選格先重跑一次；仍 void 的算沒過（保守）。
- K 只跑 LCB（任務題庫沒有 `check_*` 形狀的可見驗收；polyglot 要另包一層，沒做、沒驗）。
- 主跑單位數 ＝ 133 ＋ 通過篩選的任務題庫題數；每單位最多 6 段 session（A、C、R×2、K×2）；一個單位的牆鐘最長約 90 分鐘（A 一段＋R 或 K 的接續兩段，兩條分支並行；C 與 A 同時）。

## 四、檔案地圖（本資料夾）

| 檔 | 做什麼 |
|---|---|
| `vm/tui_cell.py` | **互動版 cell.sh**：tmux＋pi TUI、等頁腳、打字（單行 `send-keys -l`、多行／含 tab 用括號貼上）、完成偵測、Ctrl-D、逾時＝殺＋rc 124、void 判斷、A／C 線、R／K 分支、bridge、計分、meta.json |
| `vm/tui_lib.py` | 純函式：`tail_state`、`SessionTail`（增量讀）、`DoneDetector`、錯誤分類、`classify_session`、K 的失敗文字（KS-1）、`SlotPool`、`LedgerTail` |
| `vm/driver_i1001.py` | 排程、續跑、void 重跑一次、`--phase auto`（篩選→天花板→主跑）、`progress.jsonl`（不含分數）、`DRIVER_DONE` |
| `vm/plan_builder.py` | 篩選計畫、主計畫、天花板規則、成本上限估算 |
| `vm/feasibility_i1001.py` | 護欄：void 率／非 200 率／C 安裝失敗 ⇒ 放 `STOP`（**不看逾時**——題池本來就會撞） |
| `vm/packer_i1001.py` | `packer.py` 的外殼（**呼叫它的原函式，packer.py 本身逐字不動**）：driver 一寫 `DRIVER_DONE` 就收尾，不多睡最多 10 分鐘（G4 每小時 8.9 CU）；實測 DRIVER_DONE 後約 40 秒 PACKER_DONE |
| `vm/finalize_vm.py` | packer 收尾後核對 Drive 鏡像每個 chunk 的 sha256 ⇒ `MIRROR_OK`／`MIRROR_BAD`、`ALL_DONE` |
| `vm/vm_selfcheck.py`、`vm/smoke_stub.py` | **花 GPU 之前**的整條管線冒煙（機制替身模型）；會量 bridge 的 bwrap 在這台機器起不起得來，起不來自動換 /proc 綁定墊片 |
| `vm/deploy_i1001.sh`、`vm/launch_i1001.sh`、`vm/launch_record.py`、`build_bundle.sh` | 打包、佈署、發射、發射紀錄 |
| `sync_i1001.sh`、`autostop_i1001.sh` | **本機**：同步（`colab download`）、自動關機（`vm/cu_guard.sh` 仍是第一批的逐字複本，這批改用 `cu_cap_i1001.sh`） |
| `analyze_i1001.py` | 分析 |
| `vm/vllm_up_i1001.sh` | **VM：vLLM 0.30.0＋權重＋聊天樣板的安裝與 serve**（合成第一批 `setup_vllm.sh` 的安裝與 `serve_vllm.sh` 的旗標；核對 vLLM 版本與權重／樣板 sha256；只聽 127.0.0.1；`--dry-run` 印出指令）。**沒有在 Colab 上跑過** |
| `vmsh_i1001.sh` | 本機：在 VM 上跑一段 bash 並拿回輸出與結束碼（`colab upload`＋`console`＋`download`，不走 kernel 的 `exec`） |
| `cu_cap_i1001.sh` | 本機：CU 軟上限（放 `STOP`）／硬上限（最後一包＋同步＋`colab stop`）；已花＝max（餘額估計、時間估計）。取代第一批 `cu_guard.sh` 的單一門檻 |
| `freeze_i1001.py` | 預註冊兩張 sha256 表（工具＋wheel、題目樹）的填寫與核對（本機／VM）；wheel 對 git 逐檔比 |
| `tests/test_colab_i1001_ops.py` | 上面四支的測試（假 colab）＋預註冊／RUNBOOK 與檔案的一致性 |
| `vm/{sandbox.sh,orproxy.py,packer.py,cu_guard.sh,vacant_check.py,vm_setup.sh}`、`scorers/`、`stage_*.py`、`bridge/native_acceptance_bridge.py` | **重用**第一批（逐字複本；`MANIFEST_REUSED.json` 記 sha256，`build_manifest.py --check` 驗；沒重用的檔與原因也列在裡面）。bridge 是 PR #82 的檔（本分支 HEAD 還沒有），合進來後改指 `ops/eval/`。⚠ `vm/cu_guard.sh` 有一處複製後別人改的差異（`$TH）`→`${TH}）`，只影響一行訊息文字），已登記在 manifest 的 `modification` |
| `STAGING.md`、`stage_pool.py`、`build_pool_lcb.py`、`verify_*.py`、`gauge_task3.py` | 題池與計分器量具（資料側） |
| `stub_model.py`、`pi_tui_probe.py`、`run_probe_suite.sh`、`evidence_pi_tui/` | pi TUI 的機制探針（7 情境） |
| `evidence_selfcheck_local/` | 這個容器上 `vm_selfcheck.py` 七個情境的結果與各情境的格子紀錄（機制替身；**不是**真模型的證據） |
| `evidence_launch_rehearsal_local/` | 本機**全套排練**：bundle→deploy→selfcheck→`launch_i1001.sh`（`--max-units 2`，替身模型當上游）→ driver／packer／finalize／analyze 一路走完的紀錄（見第九節） |
| `local_e2e/` | **本機端到端**（真題目、真計分器、真 bridge、真 pipx 裝的 Vacant wheel、真 pi TUI；只有模型是按格子編劇的替身）：`e2e_stub.py`（按標籤編劇的替身）、`tag_front.py`（把代理標籤寫進請求本文給替身讀）、`build_e2e_inputs.py`（子集 staged 樹＋劇本＋預期，**含參考答案，只落在 scratchpad**）、`e2e_services.sh`、`kill_resume.py`、`verify_e2e.py`（逐項核對）、`fake_colab.sh`（假的 colab，驗 sync／autostop）。結果見第十節與 `LOCAL_E2E.md`、`evidence_local_e2e/` |
| `tests/test_colab_interactive_20261001.py` | 純函式測試（計畫、完成偵測在錄好的 session 檔上、分析、排程、同步／關機腳本、bundle） |

## 五、操作順序（逐步；每步的預期時間與 CU；【關機檢查點】）

> 這些指令的**邏輯**（`vmsh_i1001.sh`、`cu_cap_i1001.sh`、`freeze_i1001.py`、`sync`／`autostop`）在本機用假的 colab 驗過（`tests/test_colab_i1001_ops.py`、`tests/test_colab_interactive_20261001.py`）；
> **沒有碰過真的 colab CLI、沒有起過 VM、`vm/vllm_up_i1001.sh` 沒有在 Colab 上跑過**（只驗了語法與 `--dry-run`）。`colab` 的子命令與旗標照第一批 skill 的記載
> （`new -s 名 --gpu G4`、`upload`／`download`／`console`／`usage`／`sessions`／`stop`／`drivemount`）；G4 要不要 `--high-mem` 沒有記載（RUNLOG 只在 A100-80GB 標了它），照 `new -s 名 --gpu G4`，開機後用 `nproc`／`free -g` 核對是 48 vCPU／約 176 GB。
> 時間是預期、沒量過乾淨的一次。每步開始前先 `df -h`、`colab usage`。
> **VM 上長跑的程式一律 `setsid nohup … &`**；`colab console` 是同一個 tmux 殼，前景長指令會把後面的指令（含 `cu_cap` 的硬上限動作）排在後面。
> 這個工具的 shell 狀態不會跨呼叫保留：每個區塊開頭 `. ~/Vacant_colab_raw/i1001.env`（第 0 步寫的）。

### 第 0 步　本機準備（不計費；15–25 分鐘）

```bash
mkdir -p ~/Vacant_colab_raw
cat > ~/Vacant_colab_raw/i1001.env <<'EOF2'
export S=i1001                                           # Colab session 名
export CI=/home/user/Vacant/ops/colab_interactive_20261001
export PRE=/home/user/Vacant/decisions/prereg/PREREG_20261001_COLAB_INTERACTIVE_I1001.md
export STAGED=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/i1001/staged   # 題目 staged 目錄（不進 repo；本次 session 的路徑，換 session 要換）
export RAW=$HOME/Vacant_colab_raw/i1001                  # 本機備份（預估 0.1–0.3 GB；這個容器曾只剩 0.8 GB，先 df）
export MIRROR=/content/drive/MyDrive/vacant_i1001        # Drive 鏡像（VM 上的路徑；有運算單位那個帳號的 Drive）
vmsh() { bash "$CI/vmsh_i1001.sh" "$S" "$@"; }           # 在 VM 上跑 bash：vmsh [--wait 秒] [--tail N] (-c '指令' | 檔)
EOF2
. ~/Vacant_colab_raw/i1001.env
df -h "$HOME" /tmp | tail -2
cd /home/user/Vacant
.venv/bin/python -m pytest tests/test_colab_interactive_20261001.py tests/test_colab_i1001_ops.py -q       # 全綠
python3 $CI/build_manifest.py --check                                                                       # 重用檔沒被改過
# 免費的計畫預覽：30 單位（篩選）／227 單位（主跑，未套天花板）
python3 $CI/vm/plan_builder.py screen --staged $STAGED --out /tmp/i1001_plan_screen.json
python3 $CI/vm/plan_builder.py main   --staged $STAGED --out /tmp/i1001_plan_main.json
# wheel：從 HEAD 建一次（C 組與 bridge 的 venv 都裝它）；必須與 git 的 vacant_network/ 逐檔相同
rm -rf /tmp/i1001_wheel && mkdir -p /tmp/i1001_wheel
.venv/bin/python -m pip wheel --no-deps -q -w /tmp/i1001_wheel .
WHL=$(ls /tmp/i1001_wheel/*.whl); echo "$WHL"; git rev-parse HEAD
python3 $CI/freeze_i1001.py --wheel-vs-git "$WHL"                                                           # 要印 SAME
```

**凍結**（預註冊第四節末的程序）：填兩張表、手填 Vacant 來源 commit、核對、**lead commit ＝凍結點**；**之後不准再改任何工具檔**，然後才建 bundle。
```bash
. ~/Vacant_colab_raw/i1001.env; cd /home/user/Vacant; WHL=$(ls /tmp/i1001_wheel/*.whl)
python3 $CI/freeze_i1001.py --fill "$PRE" --wheel "$WHL" --staged "$STAGED"
python3 - "$PRE" "$(git rev-parse HEAD)" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
old = "來源 commit `〔凍結時填〕`"; assert t.count(old) == 1
p.write_text(t.replace(old, f"來源 commit `{sys.argv[2]}`"), encoding="utf-8")
PY
python3 $CI/freeze_i1001.py --check "$PRE" --wheel "$WHL" --staged "$STAGED"                                 # 要印 OK（有殘留占位字也會擋）
# （lead）git add／commit 這份預註冊與所有新檔 ＝ 凍結
bash $CI/build_bundle.sh "$STAGED" "$WHL" /tmp/deploy_i1001.tgz                                              # 印大小與 sha256
```

### 第 1 步　開機與護欄（【GPU 計費從這裡開始】；1–3 分鐘；CU 0.1–0.4）

```bash
. ~/Vacant_colab_raw/i1001.env; mkdir -p "$RAW"
B0=$(colab usage | sed -n 's/.*Current balance: \([0-9.]*\).*/\1/p'); echo "B0=$B0"          # 空的＝讀不到：停，先看 colab usage 印了什麼
HARD=$(awk -v b="$B0" 'BEGIN{h=b-15; if (h>100) h=100; printf "%d", h}'); SOFT=$((HARD-20)); echo "SOFT=$SOFT HARD=$HARD"
# 名目：--soft 80 --hard 100（B0 ≥ 115）；B0 較低時用上面算出來的；HARD < 70 ⇒ 不要往下做，先問人類
T0=$(date +%s)                                                                                       # 一定在 colab new 之前記
printf 'export B0=%s T0=%s SOFT=%s HARD=%s\n' "$B0" "$T0" "$SOFT" "$HARD" >> ~/Vacant_colab_raw/i1001.env
colab new -s "$S" --gpu G4
colab sessions                                                                                       # 看得到 i1001
nohup bash "$CI/cu_cap_i1001.sh" "$S" --b0 "$B0" --t0 "$T0" --soft "$SOFT" --hard "$HARD" --interval 300 --sync-dir "$RAW" >> ~/Vacant_colab_raw/cu_cap.log 2>&1 &
```
`cu_cap` 一開機就開：連「vLLM 一直裝不起來」也受 8 小時以內的 CU 上限保護（此時 VM 上還沒有 `/srv/eval`，軟上限那條 `echo > /srv/eval/STOP` 會失敗，無害；硬上限仍會 `colab stop`）。

### 第 2 步　掛 Google Drive（與 3–7 並行；可能要人類）

```bash
colab drivemount -s "$S" /content/drive
```
第一批這一步「印出授權網址、等 Enter」，要人類在瀏覽器按一次（人類說權限已開，但每台新 VM 仍可能要按）。**把網址交給人類，不要空等**——先做第 3、4 步。人類原有的檔不要讀。
沒掛好就不發射（第 8 步閘門；【關機檢查點 3】）。

### 第 3 步　起 vLLM（背景、長桿；指令 1 分鐘，之後 15–25 分鐘）

```bash
. ~/Vacant_colab_raw/i1001.env
colab upload -s "$S" "$CI/vm/vllm_up_i1001.sh" /content/vllm_up_i1001.sh
vmsh --wait 90 -c 'setsid nohup bash /content/vllm_up_i1001.sh > /dev/null 2>&1 < /dev/null & sleep 3; tail -n 3 /content/vllm_up.log; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader'
```
要看到 GPU 名稱含 `RTX PRO 6000`（預註冊的固定變數）；不是就 `colab stop`。腳本做：獨立 venv 裝 `vllm==0.30.0`、核對樣板與權重的 sha256、`VLLM_USE_FLASHINFER_SAMPLER=0 vllm serve …`（旗標逐字見預註冊第四節、只聽 127.0.0.1:18000）；最後一行 `VLLM_READY`（失敗是 `VLLM_FAIL <原因>`）。

### 第 4 步　上傳 bundle 並佈署（與第 3 步並行；6–10 分鐘）

```bash
. ~/Vacant_colab_raw/i1001.env
colab upload -s "$S" /tmp/deploy_i1001.tgz /content/deploy_i1001.tgz
vmsh --wait 900 --tail 30 -c 'mkdir -p /root/deploy && tar -xzf /content/deploy_i1001.tgz -C /root/deploy && rm -f /content/deploy_i1001.tgz && bash /root/deploy/bin/deploy_i1001.sh g4 http://127.0.0.1:18000'
```
最後要有 `bundle sha256 ok`、`bridge venv ok`、`pandas … (as nobody, clean env)`、`DEPLOY_OK`。deploy 在圍牆裡的使用者 import 不了 pandas／numpy 時會 `exit 5`（第一次本機端到端就是栽在這裡）。

### 第 5 步　VM 上核對凍結表（1 分鐘）

```bash
. ~/Vacant_colab_raw/i1001.env
colab upload -s "$S" "$CI/freeze_i1001.py" /content/freeze_i1001.py
colab upload -s "$S" "$PRE" /content/prereg.md
vmsh --wait 120 -c 'python3 /content/freeze_i1001.py --check /content/prereg.md --vm'            # 要印 OK
```
有任何一列不同＝**不發射**（凍結的表與 VM 上實際的檔不是同一份；要換檔＝另一份預註冊）。【關機檢查點 1】

### 第 6 步　selfcheck（替身模型，不用 GPU；與 vLLM 安裝並行；4–7 分鐘）

```bash
. ~/Vacant_colab_raw/i1001.env
vmsh --wait 900 --tail 40 -c 'python3 /opt/eval/bin/vm_selfcheck.py --wheel /opt/eval/wheel/*.whl'
```
七個情境（a、k、r、timeout、void、driver、c）全過才寫 `ok`（發射會讀它）。這一步同時量 **bridge 的 bwrap 在 Colab 上起不起得來**（`--proc /proc` 在 Colab 可能不被允許）：起不來會自動換 /proc 綁定墊片、記進 `selfcheck.json` 的 `bridge_shim`；
墊片也不行 ⇒ K 相關情境失敗 ⇒ **K 不可用**：第 9 步改以 `--nested R` 發射（預註冊第六節；此時只有 T2，用未校正 p）。其餘情境失敗＝不發射。【關機檢查點 2】

### 第 7 步　等 vLLM 就緒、經代理打一通探針（開機後約 20–30 分鐘；累計 CU 約 3–4.5）

```bash
. ~/Vacant_colab_raw/i1001.env
vmsh --wait 60 --tail 4 -c 'tail -n 4 /content/vllm_up.log'          # 每隔幾分鐘看一次，直到最後一行是 VLLM_READY（VLLM_FAIL ⇒ 看 /content/vllm_server.log）
cat > /tmp/i1001_probe.sh <<'EOF2'
curl -s -m 100 http://127.0.0.1:18900/t/probe/up/g4/think/off/api/v1/chat/completions -H 'content-type: application/json' \
  -d '{"model":"gemma-4-12b-it-qat","messages":[{"role":"user","content":"Reply with the single word: ok"}],"max_tokens":8}' | head -c 600; echo
tail -n 1 /srv/eval/proxy/ledger.jsonl | head -c 400; echo
EOF2
vmsh --wait 120 /tmp/i1001_probe.sh                                    # 要有一則含 ok 的回答與一列狀態 200 的帳本
```
開機後 45 分鐘還沒 `VLLM_READY` ⇒ 【關機檢查點 1】。

### 第 8 步　發射前閘門（2 分鐘）

```bash
. ~/Vacant_colab_raw/i1001.env
cat > /tmp/i1001_gate.sh <<'EOF2'
set -e
[ -d /content/drive/MyDrive ] || { echo "DRIVE_NOT_MOUNTED（/content/drive/MyDrive 不存在；不要 mkdir -p 它——那會在 VM 本機磁碟上造出一個假的 Drive）"; exit 3; }
mkdir -p /content/drive/MyDrive/vacant_i1001
touch /content/drive/MyDrive/vacant_i1001/.write_test && rm /content/drive/MyDrive/vacant_i1001/.write_test && echo DRIVE_OK
df -h /srv/eval /content | tail -n 2
nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader
curl -s -o /dev/null -w 'vllm_health=%{http_code}\n' http://127.0.0.1:18000/health
python3 - <<'PY'
import json; d = json.load(open('/srv/eval/_selfcheck/selfcheck.json')); print('selfcheck ok =', d.get('ok'), '| bridge_shim =', d.get('bridge_shim'))
PY
EOF2
vmsh --wait 60 /tmp/i1001_gate.sh
```
要同時看到 `DRIVE_OK`、`vllm_health=200`、`selfcheck ok = True`。沒有 `DRIVE_OK` ⇒ 不發射（人類要求資料在 Drive；【關機檢查點 3】）。

### 第 9 步　發射（1 分鐘；累計 CU 約 4.5–5）

```bash
. ~/Vacant_colab_raw/i1001.env
DEADLINE=$(date -u -d '+8 hours' +%Y-%m-%dT%H:%M:%SZ)          # macOS：date -u -v+8H +%Y-%m-%dT%H:%M:%SZ
printf 'export DEADLINE=%s\n' "$DEADLINE" >> ~/Vacant_colab_raw/i1001.env
vmsh --wait 120 --tail 20 -c "bash /opt/eval/bin/launch_i1001.sh i1 32 $DEADLINE $MIRROR"
# K 不可用時（第 6 步）：在最後多加  --nested R
```
輸出要有 `LAUNCHED i1` 與四個行程（packer_i1001、feasibility_i1001、finalize_vm、driver_i1001）。`launch_i1001.sh` 會讀 selfcheck 的 `ok`、寫發射紀錄 `launch_record_i1.json`（每個工具、題目樹、wheel 的 sha256 與 driver 的全部參數）、把 driver 指令存成 `/srv/eval/driver_cmd_i1.sh`。
**預設 `--phase auto`**：篩選（`i1s`，30 段只跑 A）→ 天花板規則 → 主跑（`i1`）。

### 第 10 步　本機開兩個常駐迴圈（`cu_cap` 第 1 步已開；缺一不可）

```bash
. ~/Vacant_colab_raw/i1001.env
nohup bash "$CI/sync_i1001.sh" "$S" "$RAW" 600 >> ~/Vacant_colab_raw/sync.log 2>&1 &              # 拉 chunk＋驗 sha256 → $RAW/VERIFIED.tsv
nohup bash "$CI/autostop_i1001.sh" "$S" "$RAW" --interval 60 >> ~/Vacant_colab_raw/autostop.log 2>&1 &   # 收完＋最後一個 chunk 本機驗過 ⇒ colab stop
pgrep -af "cu_cap_i1001|sync_i1001|autostop_i1001" | cut -c1-120                                       # 三個都在
```
`autostop` 在「本機沒驗完（睡著、磁碟滿）」時：預設等 2700 秒，VM 上有 `MIRROR_OK`（Drive 鏡像逐 chunk 核對過）才照樣關機並印警告；沒有 `MIRROR_OK` 就一直等、不賭。

### 第 11 步　監看與檢查點（只看 rc、牆鐘、逾時、void、安裝、token；**不看分數**）

```bash
. ~/Vacant_colab_raw/i1001.env
cat > /tmp/i1001_status.sh <<'EOF2'
python3 - <<'PY'
import json, collections, statistics as st, pathlib
rows = [json.loads(l) for l in open('/srv/eval/progress.jsonl') if l.strip()]
by = collections.defaultdict(list)
for r in rows:
    if 'cell' in r: by[(r['cell'].split('-')[0], r['arm'])].append(r)          # (i1s 篩選／i1 主跑, 組)
for k, v in sorted(by.items()):
    w = [r['wall_s'] for r in v if r.get('wall_s') is not None]
    print(k, 'n=%d void=%d timeout=%d sessions=%d wall_med_s=%s' % (len(v), sum(1 for r in v if r.get('void')), sum(1 for r in v if r.get('timeout')),
          sum(r.get('n_sessions') or 0 for r in v), round(st.median(w)) if w else None))
vr = collections.Counter((r.get('void_reason') or '')[:60] for r in rows if r.get('void'))
print('void reasons:', dict(vr))
p = pathlib.Path('/srv/eval/plan_main.json')
print('planned main units:', len(json.load(open(p))['tasks']) if p.exists() else '(main plan not written yet)')
PY
echo '--- driver'; tail -n 4 /srv/eval/driver_i1.log | cut -c1-240
echo '--- ceiling'; grep -h "ceiling decision" /srv/eval/driver_i1.log | cut -c1-300
echo '--- feasibility'; tr -d '\n' < /srv/eval/feasibility_i1001.json | cut -c1-320; echo
echo '--- flags'; ls /srv/eval/STOP /srv/eval/DRIVER_DONE /srv/eval/ALL_DONE 2>&1 | cut -c1-80
echo '--- last chunk'; tail -n 1 /srv/eval/archive/MANIFEST.tsv 2>&1 | cut -c1-110
EOF2
vmsh --wait 60 /tmp/i1001_status.sh
colab usage | sed -n 's/.*Current balance: \([0-9.]*\).*/balance=\1/p'
```
`progress.jsonl` 的列只有組別、牆鐘、逾時、void、session 數；A 線的列在「整條線（A＋R＋K）結束」時才寫，所以 `i1/A` 的列數＝已完成的主跑單位數。

**檢查點（時間以發射為 0）**

| # | 何時 | 看什麼 | 正常 | 不正常時 |
|---|---|---|---|---|
| 1 | 約 10 分鐘 | 狀態腳本；一個活著的 TUI（見下） | `void` 為 0 或很少；`i1s` 的 A 格都在跑；沒有 `footer_timeout`／`input_mismatch`；第一個 chunk 出現 | void 多：看 `void reasons`——`footer_timeout`＝TUI 沒起來、`proxy_non200`＝vLLM 5xx／429、`bridge_prepare_failed`＝K 起不來；基礎設施壞 ⇒ 放 `STOP`（`vmsh -c 'touch /srv/eval/STOP'`）、查原因；查不出且 > 20 分鐘 ⇒ 【關機檢查點 1 的精神】`colab stop` |
| 2 | 約 40 分鐘 | `ceiling` 那行：每個任務題庫 A 答對幾題（**這是唯一預先規定要看的分數，只有 A**）、哪些題庫被丟 | 日誌印出 `ceiling decision: {…}`，之後 `i1` 主跑開始 | 全部任務題庫被丟＝S1（主跑只有 LCB），正常，繼續；不要為了「換題」手動加題庫（那是另一份預註冊） |
| 3 | 約 60–90 分鐘 | **花費重估**：`colab usage` 的餘額（已花＝B0 − 餘額）、`i1/A` 的列數（已完成單位）、`planned main units` | 預測總花費 ≤ 軟上限 | 預測 > 軟上限：算法在下面；要提早收就 `touch /srv/eval/STOP`（只擋新單位），**不改任何參數、不手工挑單位** |
| 4 | 每 1–2 小時 | 狀態腳本、`feasibility`、`colab usage` | 同上 | 同上 |
| 5 | `DRIVER_DONE` 出現後 | `autostop.log` 出現 `STOPPED` | 約 10 分鐘內 | 沒關 ⇒ 手動 `colab stop -s i1001`、確認 `colab sessions` 沒有它（**不要空著**） |

- **看一個活著的 TUI（行為，不是分數）**：`vmsh -c 'for s in $(ls /tmp/tmux-0 | head -2); do echo "== $s"; tmux -L $s capture-pane -p -J -t $s | grep -v "^$" | tail -n 12; done'`（每格一個 tmux socket，名字 `i<序號>`）。
  要看到打進去的那一句與 agent 在工作；看到頁腳卡住或輸入框空的＝打字被吃掉（會被判 void 並重跑，但出現多了就是系統性問題）。
- **花費重估**：預測總花費 ≈ 已花 ＋ （計畫單位數 − 已完成單位數）× （已花 − 開機到篩選結束的固定成本 約 10）／ 已完成單位數 ＋ 長尾 6。**早期完成的單位偏快（長鏈的單位還沒結束），所以這個預測會低估；把括號那項乘 1.3 當上界。**
  例：發射後 90 分鐘，已花 17.5，完成 20 單位，計畫 227：（17.5 − 10）／ 20 ＝ 0.375 CU／單位 ⇒ 預測 17.5 ＋ 207 × 0.375 ＋ 6 ≈ 101（上界約 125）⇒ 會撞軟上限，到時停在約 150–190 單位——可以接受（隨機子集的完整配對）。
- **不要為了看起來順手去改計分器、題目、位置數、IDLE_S**（鐵則 4；位置數改了就是另一個固定變數）。

### 第 12 步　收完、分析、關機確認

1. `autostop_i1001.sh` 自動關機；`autostop.log` 要有 `STOPPED`。沒關就 `colab stop -s i1001`；再 `colab sessions` 確認沒有 `i1001`、`colab usage` 記下最後餘額（**花費＝B0 − 最後餘額**，寫進報告）。
2. 備份核對：`$RAW/VERIFIED.tsv` 的列數＝VM 最終 MANIFEST 的列數；`ls $RAW/ALL_DONE $RAW/MIRROR_OK`（`MIRROR_OK`＝Drive 鏡像每個 chunk 的 sha256 對）。Drive 在 `MyDrive/vacant_i1001/`。三份：VM（已關、沒了）、Drive、本機。
3. **先只看 void 與稽核，再看分數**：
```bash
. ~/Vacant_colab_raw/i1001.env
python3 $CI/analyze_i1001.py --chunks "$RAW" --out /tmp/i1001_analysis --prefix i1 > /dev/null
python3 - <<'PY'
import json; d = json.load(open('/tmp/i1001_analysis/report.json'))
print('void_final:', d['void_final']); print('void_superseded_by_rerun:', len(d['void_superseded_by_rerun'])); print('k_unavailable_units:', d['k_unavailable_units'])
print('audit:', d['audit'])                      # late_write_after_done 非 0 ⇒ IDLE_S 太短，結論要保留這句
PY
```
   最終仍 void 的格先看原因（基礎設施？）；void 率與組別是否有關（A、C 各自的 void 率差 > 5 個百分點要寫進結論第一行）。
4. 然後讀 `/tmp/i1001_analysis/report.md`（兩個主要檢定＋描述）。**K 不可用（`--nested R`）時 T2 用 `p_mcnemar_exact_two_sided`（未校正），不用 `p_holm`。**
5. 結果（`report.md`、`report.json`、`cells.jsonl`，沒有題目內容）與發射紀錄進 repo；**原始 chunk（含題目內容與模型輸出）不進 repo**。把「花費、void、被硬上限切掉的單位、A 沒解開的題數、天花板決定」寫進結論。口徑照預註冊第十二節。

### 恢復與手動中止

- **driver 被殺了（OOM、誤殺）而 VM 還活著——重啟，不要重發射**：`launch_i1001.sh` 把 driver 的指令存成 `/srv/eval/driver_cmd_<前綴>.sh`：
  `vmsh -c 'setsid nohup bash /srv/eval/driver_cmd_i1.sh >> /srv/eval/driver_i1.log 2>&1 < /dev/null &'`。
  **不要**再跑 `launch_i1001.sh`（它會把進度檔搬走、再多起一組 packer／feasibility／finalize；後三個本來就還在跑）。
  重啟時 driver 自己做的事：拿 `driver.lock`（同一個 eval 根只准一個 driver，第二個直接結束、退出碼 4）→ **清上一個 driver 的殘骸**（它的 tmux server 與 pi 不會跟著死；不清的話它們會用同一個代理標籤繼續打模型）
  → 已經 DONE 的單位一格都不重跑 → 沒寫完的單位整條線（A／R／K 或 C）搬到 `cells_aborted/`、從頭重跑。
  ⚠ `cells_aborted/` **不在 packer 的打包範圍**（packer 只收 `cells/*/DONE`）：被殺的那幾格的殘骸只留在 VM 上，要的話收工前手動備份。
  ⚠ **整台 VM 重開／被回收**＝ `/srv/eval` 全沒了，這個程序不適用；只剩 Drive 鏡像與本機裡已打包的 chunk（未完成的單位丟掉、不進分析）。
- **想提早收（人類要求、CU 吃緊）**：`vmsh -c 'touch /srv/eval/STOP'`（不開新單位、進行中的單位跑完 ⇒ `DRIVER_DONE` ⇒ 第 5 檢查點）。
  要立刻收：`vmsh -c 'touch /srv/eval/DRIVER_DONE'`（packer 約 40 秒做最後一包，**進行中的單位丟掉**）→ 等本機 `sync` 驗完 → `colab stop`（這就是 `cu_cap` 硬上限做的事）。

## 六、為什麼這樣設計（會影響技術決策的幾條）

- **完成偵測**（互動式沒有「行程結束」）：`DoneDetector`＝session jsonl 的結尾是最終（assistant `stop`／`length`／`aborted`，或重試用完的 `error`）
  ＋ 沒有活著的 `vacant_network hook` 行程（C 組）＋ 安靜 `IDLE_S`＝**15 秒**（session 位元組、代理帳本、hook 事件檔都沒動）。15 秒是實測最大間隔（Vacant 送回 0.37–0.48 s）的約 30 倍、
  pi 最長退避（8 s）的約 2 倍。在 pi 0.87.1 實測錄下的 6 種結尾上重播測過，**含負控制**（IDLE_S＝0.2 s 會在送回前判完成）。
  結束後繼續看到 pane 退出，記 `late_write_after_done` 與 `max_gap_after_final_s`，整批跑完用它們回頭稽核 15 秒。
- **頁腳才打字**：`(harbor-endpoint) <模型>` 出現前送的鍵會被丟掉（pi 進 raw mode 時清 stdin）。打字後 10 秒內沒看到 `Working`（或 session／帳本動靜）會再按一次 Enter
  （空編輯器上 Enter 什麼都不做）；`submit_unconfirmed` 記進 meta。第一則 user 訊息必須逐字等於打進去的字，否則該段 void（`input_mismatch`）。
- **信任對話框**：工作區有 `.pi/settings.json`、`.pi/extensions` 等會讓互動 pi 停在「Trust project folder?」。出現就選「這次不信任」（Down×4＋Enter，與 `--print` 靜默略過等價），記 `trust_dialog`。
- **計分器壞了≠agent 答錯**：重用的任務題庫計分器把任何例外（含圍牆裡 pandas／dateutil 匯入失敗）收成 `pass:false, note:scorer_error…`；`tui_cell.parse_score` 把它擋成 void（原因 `scorer_error: …`），不算任何一組的失敗。`deploy_i1001.sh` 另外用「沒有特權、乾淨環境的使用者」檢查 pandas／numpy（root 的 user site 在圍牆裡看不到）。
- **infra_void**：footer 逾時／打字不符／最終 assistant 條目是 5xx／429／408／402／串流中斷／代理帳本任何一通非 200 或 stream_error／沒有任何模型呼叫／pi 在第一通請求前就死了／
  逾時但沒有任何一通完成／C 安裝失敗／bridge prepare 或 release 失敗／工具例外。**不算任何一組的失敗**；整條線以 `v2` 重跑一次，第二次仍 void 就留著 void。
  `length`（被 max tokens 切斷）與其他 4xx（例如 400 上下文太長）是這一跑自己的結果，不是 void。
- **K 的失敗文字**：取 bridge `judge` 的 `results[].detail`（可見檢查的原文，例如 `args=… got=… want=…`）＋一句中性前言與結語；寫出前過 `ks1_clean`（含「責任／懲罰／blame」等詞會直接拒絕）。
- **R 的複本**在 A 的第 1 段快照上建（K 就地改 A 的工作區，所以 R 必須在 K 動手前先有快照）。
- **K 的計分**：放行的檔與 A 第 1 段那一份逐位元相同時沿用 A 的成績（LCB 計分器只讀 `solution.py`；同一份檔不重算，避免慢解在 60 秒時限上因負載不同而翻面）。
- **續跑**：檔案系統就是狀態；A 線的 DONE 在整條線（A、R、K）結束時才一起寫，中斷的殘骸搬到 `cells_aborted/` 整條線重跑。

## 七、沒有驗過的事（Colab 上才知道；不要當成已知）

1. **bridge 的 bwrap 在 Colab 上**：`--unshare-all --proc /proc` 可能不被允許；`vm_selfcheck.py` 會量，墊片是我在本機用「會拒絕 `--proc` 的假 bwrap」模擬驗過的，**沒有在真的 Colab 核心上跑過**。
2. **tmux／pi 在 Colab 的版本與行為**：本機是 tmux 3.4；Colab 的 apt 可能給別的版本。`vm_selfcheck.py` 的 `a` 情境就是這個檢查。
3. **真 vLLM 下的延遲分布**：IDLE_S＝15 秒來自替身模型；真模型下「最終 stop → 下一個條目」的間隔分布沒有量過。自動壓縮（compaction）在最終 stop 之後會不會出現沒量過。
4. **信任對話框的按鍵**（Down×4＋Enter）：筆記裡量過選單文字，沒有在真 pi 上按過；這個題池（含 bridge 寫的 `.vacant/`）在本機端到端的 31 段 TUI 裡一次都沒觸發過，所以按鍵沒驗、也不會用到。
5. **Vacant 在「零工具呼叫就說做完」時看不到東西**（筆記 §4 的 n=1 觀察）：C 組對這種跑沒有作用，不是這批的 bug。
6. **替身模型不解題**：`vm_selfcheck.py` 驗的是管線與紀錄，不是 agent 的表現。
7. **成本**：估計在第零節與預註冊第十節（S1 ≈ 56 CU、S2 ≈ 70 CU；範圍 40–107；以 C5 的 0.202 CU／格·小時換算，**沒有量過互動式**）。`plan_builder` 算的是**上限**（每段都撞 1800 秒，不是預測）：篩選 30 單位＝30 段、900 session‑分鐘；主跑（沒有題庫被丟）227 單位＝最多 1,174 段（A、C 各 227 ＋ R 最多 454 ＋ K 最多 266）、35,220 session‑分鐘；位置數 32 時 ≈ 18 小時 ≈ 163 CU。真實用量遠低於上限；第 11 步檢查點 3 在發射後 60–90 分鐘用 `progress.jsonl` 重估。
8. **重用的 packer／orproxy／sandbox.sh 沒有改**；packer 只打包 `cells/*/DONE`，所以 A 線的 DONE 在整條線結束時才寫（見上）。
9. **`vm/vllm_up_i1001.sh`**：沒有在 Colab 上跑過（這個容器沒有 GPU、沒有 vLLM）；旗標逐字取自第一批實際跑完的 `serve_vllm.sh`，但「`pip install vllm==0.30.0` 今天還裝得到、`uv venv -p 3.12` 的下載、樣板 URL 的內容雜湊前綴還是 `afdbb2ab`」都沒驗。
10. **真的 `colab` CLI**：`usage` 的「Current balance:」格式沿用第一批 `cu_guard.sh` 的剖析；`console` 排隊行為、`drivemount` 的授權互動（要不要人類）、G4 要不要 `--high-mem`、`upload`／`download` 對目錄與大檔的行為——`vmsh`／`cu_cap`／`sync`／`autostop` 只用假 colab 驗過邏輯。
11. **第 7 步的探針與第 8 步的 Drive 閘門**：路徑與格式照第一批與本機端到端，沒有在 Colab 上跑過。Drive 的 I/O 速度（packer 每 10 分鐘鏡像一次）沒量過。
## 八、口徑（寫報告時）

- ✅「在這個題池、本機 gemma-4-12b（vLLM、關思考）、互動式 pi 0.87.1、1800 秒／段、不設回合上限下，**C 對 A**（或 **K 對 R**）的隱藏測試通過數配對比較為 …（Holm 校正後 p＝…）」。
- ✅「沒有量到差別」＝這一批沒有檢出；不是「沒有差別」。
- ❌「Vacant 讓 agent 做得更好」不帶條件；❌ 把分項當檢定；❌ 外推到真人互動使用；❌ 把 `vm_selfcheck.py` 的結果說成 agent 的表現；❌ 和 C5 的 `--print` 數字直接比。

## 九、本機全套排練（我做過的；Colab 上做之前可以先在任何有 root＋tmux＋bwrap＋pi 的機器上再做一次）

不花 GPU、不花模型呼叫：用 `smoke_stub.py` 當「上游」（它對任何題目都回「寫一個 solve_add 到 solution.py」，所以題目本身都會判沒過——
這裡驗的是管線，不是 agent 的表現）。
```bash
bash build_bundle.sh <staged> <wheel> /tmp/deploy_i1001.tgz
mkdir -p /root/deploy && tar -xzf /tmp/deploy_i1001.tgz -C /root/deploy && bash /root/deploy/bin/deploy_i1001.sh g4 http://127.0.0.1:18000
export I1001_INSTALL_ENV='HTTPS_PROXY=… PIP_CERT=… SSL_CERT_FILE=… NO_PROXY=127.0.0.1,localhost'   # 只有這台機器要 proxy 才需要；不會出現在 ps
python3 /opt/eval/bin/smoke_stub.py --port 18000 --script <腳本.json> &       # 腳本：{"plain":["right"],"solutions":{"right":"…","wrong":"…"}}
python3 /opt/eval/bin/vm_selfcheck.py                                           # 七個情境
bash /opt/eval/bin/launch_i1001.sh t2 4 <時限> <鏡像目錄> --max-units 2
```
結果（`evidence_launch_rehearsal_local/`）：篩選 2 單位（只跑 A）→ 天花板決定（任務題庫 `undecided`、保留）→ 主跑 2 個 LCB 單位（A、C、R＝A、K 3 段都沒被放行）→ `DRIVER_DONE` 後約 40 秒 `PACKER_DONE`、`MIRROR_OK`、`ALL_DONE`
→ `analyze_i1001.py` 出報告。踩到並修掉的：`launch_i1001.sh` 用 `A || B &` 會讓子殼抓著輸出管線（改成 `if`）、packer 睡滿 10 分鐘才收尾（改用 `packer_i1001.py`）、
selfcheck 的 driver 情境會刪掉別的情境的紀錄、`progress.jsonl` 的事件列沒被 selfcheck／feasibility 略過。
**排練不代表 Colab 上一定過**：沒有 GPU、沒有真 vLLM、tmux 3.4 不等於 Colab 的版本、bridge 的 bwrap /proc 只在本機用「會拒絕 `--proc` 的假 bwrap」模擬過（墊片路徑通）。

## 十、本機端到端（2026-10-01；**真題目、真計分器、真 bridge、真 Vacant wheel、真 pi TUI**，只有模型是按格子編劇的替身）

完整指令、劇本、逐格觀察與缺陷清單在 `LOCAL_E2E.md`（證據：`evidence_local_e2e/`）。一句話：`build_bundle → deploy → vm_selfcheck → launch_i1001.sh --phase auto`
整條走完（篩選 12 段 → dabench 9/10 被天花板規則丟掉 → 主跑 5 單位＝3 LCB＋databench＋polyglot_py，含 infra_void 重跑、driver 被 SIGKILL 後重啟、時限已過的發射），
`verify_e2e.py` 210／210（對紀錄做 9 種破壞全被抓到）；第 1 次跑找到的 8 個缺陷已修（計分器 `scorer_error` 被當成 agent 答錯、driver 殘骸與同標籤帳本混算、C 組紀錄裡的私鑰、
發射紀錄寫死 1800 秒、重啟程序沒寫、selfcheck 對著殘留替身講話…）。⚠ 這驗的是管線，不是 agent 的表現；真 vLLM 的延遲分布、Colab 上的 bwrap／tmux／Drive 都沒驗（`LOCAL_E2E.md` 第七節）。
**發射前請在 Colab 上再跑一次 `deploy_i1001.sh`（它現在會用乾淨環境的使用者檢查 pandas／numpy）與 `vm_selfcheck.py`。**
