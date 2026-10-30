# e006 研究包：OpenCode 全盤五臂評測（究責／審查／利害，同一算力預算）

> 預註冊：本包在發射前寫死假設、臂、判準。發射後不改判準；要改就開 e006b 並註明。
> 本包為發射前預註冊，**不包含未發生的數據**。量具：`/srv/vlab/bin/report.py`（共用量具，本輪不改動）。

## 0. 背景

- e004 OpenCode 全盤五臂觸發**機構回退**（e004_opencode_polyglot.md §4「觸發事實」）：`/srv/vlab/bin/cell.py:158` 對非 pi agent 且設定 `VLAB_APPEND_SYSTEM` 直接 `SystemExit`，H/M/S 102 格全落在此確定性失敗路徑；佇列檔移 `done/05_e004_opencode_polyglot.fallback.json`，H/M/S 臂不計、infra 格不回填、**無任何結果判定**。
- 機構修復（e005 前提，已落地）：
  - `c76ff988`（DECISION_20261030_OPENCODE_APPEND_SYSTEM）：cell.py 支援 OpenCode 前置指引（prepend 模式）；pi 臂與既有結果不變。
  - `bf1a9f1a`（e002_M 臂檔）：第二 agent 審查指令改 `opencode run`（保留 `pi -p` 備選；subagent 工具亦可用）——M 臂檔 OpenCode 相容。
- e005 OpenCode 五臂冒煙（e005_opencode_five_arm_smoke.md §5）：**5/5 格 complete（100% 出 score.json）、0 infra**，舊 SystemExit 路徑未觸發，C 臂掛載 trace PASS，H/S prepend 成功；M 臂 900s 逾時＋無第二 agent 證據 ⇒ 依條款記 **UNKNOWN**（非負結果；e006 以 1800s 複測此路徑）。
- ⇒ 無確定性 infra 崩潰（放行鐵律 1.4），e004 H/M/S 重發射可依全盤再議；本包即該全盤預註冊（34 題 × 五臂）。
- C 臂版本＝e005 冒煙版本：`vacant_sha = bf1a9f1a`（bf1a9f1afb211460b48611f8f28b1d9433985c4a，含 c76ff988、bf1a9f1a）。

## 1. 五臂設定（agent = opencode，各 34 題 polyglot_py）

| 臂 | 機制 | 配置 |
|---|---|---|
| `A` | 無 Vacant、無額外指引（對照） | opencode 指向本機模型 |
| `C` | 究責：格子內裝 Vacant（e005 已冒煙的 opencode 形式），驗收→擋回→回饋重試（預算上限）→簽收據入鏈 | `vacant_sha = bf1a9f1a` |
| `H` | 更好做法：先規劃→實作→自己跑測試→邊界→修正→再交 | 臂檔 `/srv/vlab/arms/e002_H.md`（VLAB_APPEND_SYSTEM，prepend） |
| `M` | 多 agent：交件前必須另開第二個 agent 當獨立審查者（只評不代寫、一層） | 臂檔 `/srv/vlab/arms/e002_M.md`（VLAB_APPEND_SYSTEM，prepend；bf1a9f1a） |
| `S` | 利害 (a)：後果框架，無任何新方法 | 臂檔 `/srv/vlab/arms/e002_S.md`（VLAB_APPEND_SYSTEM，prepend） |

- 任務：`/srv/eval/staged/polyglot_py` 全 34 題（unittest 方言；每題工作區含 contract.md/goal.md/*_test.py）。
- 格：A/C/H/M/S × 34 × 1 rep ＝ **170 格**；超時 **1800 s/格**；模型 gemma-4-12b-it-qat（1004 本機，`http://100.86.226.21:1234/v1`）；PAR=2。
- 佇列檔：`07_e006_opencode_polyglot.json`（頂層 `vacant_sha = bf1a9f1a…`、timeout 1800；exp 名 `e006_opencode_polyglot`、run 目錄 `/srv/vlab/runs/e006_opencode_polyglot/`）；其 `packet` 欄位回指本包由另單辦理（本包不改佇列檔）。
- 臂檔為 KS-1 守衛全數 clean 檔（e002 驗證）；H-stakes 文字只存在於實驗臂檔，永不進產品 prompt。
- agent 版本：cell 環境內之 opencode（與 e005 冒煙同一環境）；若版本變動，報告中記為環境變數。

## 2. 預註冊假設（三組，互相競爭）

- **H-acc（究責）**：Vacant 的收據/閘門機制（驗收→擋回→回饋重試→簽收據）本身提升結果。臂：C。
- **H-review（審查）**：「交件前審查」提升結果——H（自檢指引）與 M（第二 agent 審查）為兩種實作，分臂判定。
- **H-stakes（利害，a）**：後果框架提升結果（只「只是講」、無真實後果）。臂：S。
- 答案是「哪個臂最好、差多少、花多少成本」，不是三個獨立的 yes/no。

## 3. 判準（發射前寫死）

每格計分：`score.json`（隱藏評分、不信任自我報告）；`pass=None` 或無 score.json ＝ **infra，不進分母、單列**。
配對比較（同 suite/task/rep 的 A vs X）：`A_only`/`X_only` ＋ 精確雙尾 McNemar p；`C_X` = X 臂 calls_per_success。

| 假設 | 成立（CONFIRMED） | 未建立／回退 |
|---|---|---|
| H-acc | Holm 校正後 p_C < 0.05 且 C_only > A_only 且 C_C ≤ 2×C_A | 不顯著 ⇒ 未建立；顯著但 C_C > 2×C_A ⇒「有效但昂貴」 |
| H-review(H) | Holm 校正後 p_H < 0.05 且 H_only > A_only 且 C_H ≤ 2×C_A | 同上結構 |
| H-review(M) | Holm 校正後 p_M < 0.05 且 M_only > A_only 且 C_M ≤ 2×C_A，且 events.jsonl 有**真第二 agent 證據**（shell 開起 cell 自身 agent 之第二實例，或 subagent 工具呼叫） | 無第二 agent 證據 ⇒ 降級「提示式自檢」、記 **UNKNOWN**（量不到，不是負結果） |
| H-stakes(a) | Holm 校正後 p_S < 0.05 且 S_only > A_only（標註「只是講、無真實後果」） | 不顯著 ⇒ 未建立，禁止寫「利害提示無用」 |

- **成本紅線（所有臂）**：任一臂 calls_per_success 或 tokens_per_success > 2×A 且通過率未顯著提升 ⇒ 記「不划算」；成本必須與結果一起報告。
- **多重性**：4 組 A_vs_X 比較（C/H/M/S）用 Holm–Bonferroni α=0.05 作確認線；未校正 p 只作描述。
- M 臂審查者呼叫在獨立 agent 行程、**不在** cell 的 events.jsonl ⇒ M 的成本指標是**下界**。
- M 臂特別條款（承接 e005）：若第二 agent 證據仍缺 ⇒ H-review(M) 依條款記 UNKNOWN（e005 已 UNKNOWN 一次；e006 再缺仍記 UNKNOWN、不計臂失敗，但報告中註記為機制訊號）。

## 4. 回退邊界與限制

- **判定回退**：不顯著 ⇒「未建立」（不是負結果）；顯著但成本 > 2×A ⇒「有效但昂貴」；量不到 ⇒ UNKNOWN（H-stakes(b)「真實後果＝路由/續約」本輪不測，BACKLOG）。
- **機構回退**：任一臂 infra 連敗（臂檔不被 opencode 接受、第二 agent 命令不存在等）⇒ 該臂不計、先修機構/臂檔並複測冒煙再議發射；infra 格永不回填、結果永不捏造。
- 1 rep/題：配對設計消掉任務難度差異，但無 rep 內變異；rep 擴充另包。
- 模型為 gemma-4-12b 本地量化（H-12 類邊界）：結果不外推到別的模型/預算/任務庫。
- 臂檔為 pi 時期文字（e002_M.md 含 `pi -p` 備選）：opencode 下第二 agent 證據照 §3 證據規則判定；文字落差記為限制、非機制訊號。
- C 臂為 `bf1a9f1a` 版本行為；若版本變動，兩版對照記為紅旗（版本/環境問題），非機制訊號。
- `vacant install` 改 cell 設定（可逆）與 `~/.vacant`（Vacant 自己管）；A/H/M/S 臂不裝 Vacant、不碰 `~/.vacant`。
- labd 串行 ＋ PAR=2：e002 同結構 170 格實際 wall ≈ 10h（36016s），本盤估同量級。

## 5. 實際結果與判準核對

> 留空待賽後回填（依 e005 先例）：數字一律以 `REPORT.json`（report.py）＋ `opencode_cell_audit` 審計為準；通過率、成本、判定核對全部賽後補入（另 commit，**不預填**）。
