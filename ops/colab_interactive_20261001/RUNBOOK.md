# i1001 互動式批次（Colab G4）：施工與操作手冊

> 人類 2026-10-01 的要求：在 Colab 上測各式各樣的題目；**先測沒有 Vacant 的**，滿分／沒有解不開的題庫就丟、換題目（要先知道一般 agent 沒裝 Vacant
> 時真的有題目解不開）；**盡可能用互動介面、不要 `pi -p` 只給題目**；固定變數；**最少運算量、最多可用的穩定實驗**；
> 資料備份到有運算單位那個帳號的雲端（Drive）＋本機；**用完資源就關、不要空著**。
> 題目怎麼備的在 `STAGING.md`；pi 的 TUI 實測在 PI_INTERACTIVE_NOTES.md（`i1001/` scratchpad）與 `evidence_pi_tui/`。
> 這份只講：這一批怎麼跑、為什麼這樣排、哪些**沒有**驗過。時間一律 UTC；金鑰、主機名、帳號不進 repo／log（上游用代號 `g4`）。
> **這個資料夾的程式沒有碰過 Colab、沒有起過 VM、沒有花過任何模型呼叫**；本機驗證用的是「機制替身」模型（見第七節）。

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
每格一個新 Linux 使用者＋bwrap（`sandbox.sh`，與第一批逐字相同）、固定的全域並行（`--slots`＝**同時在跑的 pi 對話數**）、
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
- 主跑單位數 ＝ 133 ＋ 通過篩選的任務題庫題數；每單位最多 6 段 session（A、C、R×2、K×2），上限 3 小時。

## 四、檔案地圖（本資料夾）

| 檔 | 做什麼 |
|---|---|
| `vm/tui_cell.py` | **互動版 cell.sh**：tmux＋pi TUI、等頁腳、打字（單行 `send-keys -l`、多行／含 tab 用括號貼上）、完成偵測、Ctrl-D、逾時＝殺＋rc 124、void 判斷、A／C 線、R／K 分支、bridge、計分、meta.json |
| `vm/tui_lib.py` | 純函式：`tail_state`、`SessionTail`（增量讀）、`DoneDetector`、錯誤分類、`classify_session`、K 的失敗文字（KS-1）、`SlotPool`、`LedgerTail` |
| `vm/driver_i1001.py` | 排程、續跑、void 重跑一次、`--phase auto`（篩選→天花板→主跑）、`progress.jsonl`（不含分數）、`DRIVER_DONE` |
| `vm/plan_builder.py` | 篩選計畫、主計畫、天花板規則、成本上限估算 |
| `vm/feasibility_i1001.py` | 護欄：void 率／非 200 率／C 安裝失敗 ⇒ 放 `STOP`（**不看逾時**——題池本來就會撞） |
| `vm/finalize_vm.py` | packer 收尾後核對 Drive 鏡像每個 chunk 的 sha256 ⇒ `MIRROR_OK`／`MIRROR_BAD`、`ALL_DONE` |
| `vm/vm_selfcheck.py`、`vm/smoke_stub.py` | **花 GPU 之前**的整條管線冒煙（機制替身模型）；會量 bridge 的 bwrap 在這台機器起不起得來，起不來自動換 /proc 綁定墊片 |
| `vm/deploy_i1001.sh`、`vm/launch_i1001.sh`、`vm/launch_record.py`、`build_bundle.sh` | 打包、佈署、發射、發射紀錄 |
| `sync_i1001.sh`、`autostop_i1001.sh`、`vm/cu_guard.sh` | **本機**：同步（`colab download`）、自動關機、運算單位護欄 |
| `analyze_i1001.py` | 分析 |
| `vm/{sandbox.sh,orproxy.py,packer.py,cu_guard.sh,vacant_check.py,vm_setup.sh}`、`scorers/`、`stage_*.py`、`bridge/native_acceptance_bridge.py` | **重用**第一批（逐字複本；`MANIFEST_REUSED.json` 記 sha256，`build_manifest.py --check` 驗；沒重用的檔與原因也列在裡面）。bridge 是 PR #82 的檔（本分支 HEAD 還沒有），合進來後改指 `ops/eval/` |
| `STAGING.md`、`stage_pool.py`、`build_pool_lcb.py`、`verify_*.py`、`gauge_task3.py` | 題池與計分器量具（資料側） |
| `stub_model.py`、`pi_tui_probe.py`、`run_probe_suite.sh`、`evidence_pi_tui/` | pi TUI 的機制探針（7 情境） |
| `evidence_selfcheck_local/` | 這個容器上 `vm_selfcheck.py` 的結果（機制替身；**不是**真模型的證據） |
| `tests/test_colab_interactive_20261001.py` | 純函式測試（計畫、完成偵測在錄好的 session 檔上、分析、排程、同步／關機腳本、bundle） |

## 五、操作順序

> 以下指令我**沒有執行過**（沒有碰 Colab CLI）；`colab` 子命令與旗標照第一批 skill 的記載。每一步開始前先看 `df -h`、`colab usage`。

### 0. 本機準備（一次）
```bash
cd ops/colab_interactive_20261001
python3 build_manifest.py --check                    # 重用檔沒被改過
.venv/bin/python -m pytest tests/test_colab_interactive_20261001.py -q
# wheel：從目前 HEAD 建（C 組與 bridge 的 venv 都裝它）；題目 staged 樹在 scratchpad（不進 repo）
bash build_bundle.sh <staged 目錄> <vacant_network-*.whl> /tmp/deploy_i1001.tgz
```

### 1. 開機與佈署（約 15 分鐘，**GPU 計費從這裡開始**）
```bash
colab new -s i1001 --gpu G4 --high-mem               # 8.90 CU/h
colab drivemount -s i1001 /content/drive             # 人類說已授權；沒掛的話 packer 的鏡像會失敗（launch 會警告）
colab upload -s i1001 /tmp/deploy_i1001.tgz /content/deploy_i1001.tgz
# 在 VM 上（colab console／vmrun.sh）：
mkdir -p /root/deploy && tar -xzf /content/deploy_i1001.tgz -C /root/deploy && bash /root/deploy/bin/deploy_i1001.sh g4
# vLLM：照第一批（ops/colab_gemma_backend_20260927/backend/setup_vllm.sh、serve_vllm.sh；FLASHINFER 採樣器要關、port 18000）
```

### 2. 發射前的冒煙（不花 GPU 的部分先做；7 個情境走完才准發射）
```bash
python3 /opt/eval/bin/vm_selfcheck.py            # a,k,r,timeout,void,driver,c；全過才寫 ok；launch 會讀它
```
這一步同時量 **bridge 的 bwrap 在 Colab 上起不起得來**（它用 `--proc /proc`，Colab 不准掛新 /proc）：起不來會自動換墊片並記進 `selfcheck.json` 的
`bridge_shim`；兩者都起不來 ⇒ K 相關情境失敗 ⇒ **不要發射**（K 組沒法跑，改為 `--nested R` 只跑 A／C／R）。

### 3. 發射
```bash
bash /opt/eval/bin/launch_i1001.sh i1 32 2026-10-02T06:00:00Z /content/drive/MyDrive/vacant_i1001
#     前綴 位置數 時限（過了就不開新單位，已開始的跑完）  Drive 鏡像
```
先小跑一輪量真實成本也可以：`… /content/drive/MyDrive/vacant_i1001 --max-units 8`（driver 的額外參數放在最後）。

### 4. 本機同時開三支（缺一不可；**關機護欄**）
```bash
bash sync_i1001.sh i1001 ~/Vacant_colab_raw/i1001 600 &          # 拉 chunk＋驗 sha256 → VERIFIED.tsv
bash vm/cu_guard.sh i1001 25 &                                    # 餘額 < 25 CU ⇒ VM 上放 STOP（driver 不開新單位）
bash autostop_i1001.sh i1001 ~/Vacant_colab_raw/i1001 --interval 60 &   # DRIVER_DONE＋PACKER_DONE＋最後一個 chunk 本機驗過 ⇒ colab stop
```
`autostop` 在「本機沒驗完（Mac 睡著）」時：預設等 2700 秒，若 VM 上 `MIRROR_OK`（Drive 鏡像逐 chunk 核對過）才照樣關機並印警告；沒有 `MIRROR_OK` 就一直等、不賭。

### 5. 監看（只看 rc、牆鐘、逾時、void、安裝、token；**不看分數**）
`/srv/eval/progress.jsonl`、`driver_<前綴>.log`、`feasibility_i1001.json`、`proxy/ledger.jsonl`。異常才處理：STOP 檔出現＝護欄觸發（原因在檔內）；
void 一直出現＝先看 `void_reason`（`footer_timeout`＝TUI 沒起來、`proxy_non200`＝vLLM 5xx／429、`bridge_prepare_failed`＝K 起不來）。
**不要為了看起來順手去改計分器或題目**（鐵則 4）。

### 6. 收完
1. `autostop` 自動關機；沒關就手動 `colab stop -s i1001`，**不要空著**。
2. `python3 analyze_i1001.py --chunks ~/Vacant_colab_raw/i1001 --out <目錄>` → `report.md`／`report.json`／`cells.jsonl`。先看 `void_final`、`audit`（`late_write_after_done` 非 0 ⇒ IDLE_S 太短，結果要保留這句）。
3. 結果與報告進 repo；原始紀錄**不進 repo**（含題目內容與模型輸出）。

## 六、為什麼這樣設計（會影響技術決策的幾條）

- **完成偵測**（互動式沒有「行程結束」）：`DoneDetector`＝session jsonl 的結尾是最終（assistant `stop`／`length`／`aborted`，或重試用完的 `error`）
  ＋ 沒有活著的 `vacant_network hook` 行程（C 組）＋ 安靜 `IDLE_S`＝**15 秒**（session 位元組、代理帳本、hook 事件檔都沒動）。15 秒是實測最大間隔（Vacant 送回 0.37–0.48 s）的約 30 倍、
  pi 最長退避（8 s）的約 2 倍。在 pi 0.87.1 實測錄下的 6 種結尾上重播測過，**含負控制**（IDLE_S＝0.2 s 會在送回前判完成）。
  結束後繼續看到 pane 退出，記 `late_write_after_done` 與 `max_gap_after_final_s`，整批跑完用它們回頭稽核 15 秒。
- **頁腳才打字**：`(harbor-endpoint) <模型>` 出現前送的鍵會被丟掉（pi 進 raw mode 時清 stdin）。打字後 10 秒內沒看到 `Working`（或 session／帳本動靜）會再按一次 Enter
  （空編輯器上 Enter 什麼都不做）；`submit_unconfirmed` 記進 meta。第一則 user 訊息必須逐字等於打進去的字，否則該段 void（`input_mismatch`）。
- **信任對話框**：工作區有 `.pi/settings.json`、`.pi/extensions` 等會讓互動 pi 停在「Trust project folder?」。出現就選「這次不信任」（Down×4＋Enter，與 `--print` 靜默略過等價），記 `trust_dialog`。
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
4. **信任對話框的按鍵**（Down×4＋Enter）：筆記裡量過選單文字，沒有在真 pi 上按過。
5. **Vacant 在「零工具呼叫就說做完」時看不到東西**（筆記 §4 的 n=1 觀察）：C 組對這種跑沒有作用，不是這批的 bug。
6. **替身模型不解題**：`vm_selfcheck.py` 驗的是管線與紀錄，不是 agent 的表現。
7. **成本**：未預測。`plan.json` 的 `estimate` 只給**上限**（每段都撞 1800 秒）；A 失敗題近六成會撞時限、R／K 的接續段又是 1800 秒，
   主跑量級粗估在「數十 CU」——**先用 `--max-units 8` 小跑量真實的每單位分鐘數再決定位置數與時限**。位置數建議從 32 起（vLLM 長對話 32 條飽和；程式題對話較短）。
8. **重用的 packer／orproxy／sandbox.sh 沒有改**；packer 只打包 `cells/*/DONE`，所以 A 線的 DONE 在整條線結束時才寫（見上）。

## 八、口徑（寫報告時）

- ✅「在這個題池、本機 gemma-4-12b（vLLM、關思考）、互動式 pi 0.87.1、1800 秒／段、不設回合上限下，**C 對 A**（或 **K 對 R**）的隱藏測試通過數配對比較為 …（Holm 校正後 p＝…）」。
- ✅「沒有量到差別」＝這一批沒有檢出；不是「沒有差別」。
- ❌「Vacant 讓 agent 做得更好」不帶條件；❌ 把分項當檢定；❌ 外推到真人互動使用；❌ 把 `vm_selfcheck.py` 的結果說成 agent 的表現；❌ 和 C5 的 `--print` 數字直接比。
