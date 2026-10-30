# e004 研究包：OpenCode 全盤五臂評測（究責／審查／利害，同一算力預算）

> 預註冊：本包在發射前寫死假設、臂、判準。發射後不改判準；要改就開 e004b 並註明。
> 本包為發射前預註冊，**不包含未發生的數據**。量具：`/srv/vlab/bin/report.py`（共用量具，本輪不改動）。

## 0. 背景

- e003 OpenCode 冒煙 **GO**（`e003_opencode_smoke.md` §5；AUDIT.json n_cells=4、bad=[]）：
  4 格（A/C × pg_pig_latin、pg_affine_cipher）皆正常結束、**0 infra**；C 臂 install_rc=0、
  trace 16+75 筆 prev_hash 重算相符、review 168 全 allow。⇒ 可發 OpenCode 全盤。
- 結構模板：e002 五臂（pi agent、34/34 完賽；H-acc／H-harness／H-multi／H-stakes 在 Holm 下皆「未建立」）。
  e004 把 agent 換成 OpenCode，五臂結構、判準形式對齊 e002。
- C 臂版本＝e003 GO 版本：`vacant_sha = 12d1dc2a`（12d1dc2a61592193a7c13a2b236dc5aa8f24e6d1）。

## 1. 五臂設定（agent = opencode，各 34 題 polyglot_py）

| 臂 | 機制 | 配置 |
|---|---|---|
| `A` | 無 Vacant、無額外指引（對照） | opencode 指向本機模型 |
| `C` | 究責：格子內裝 Vacant（e003 已 GO 的 opencode 形式），驗收→擋回→回饋重試（預算上限）→簽收據入鏈 | `vacant_sha = 12d1dc2a` |
| `H` | 更好做法：先規劃→實作→自己跑測試→邊界→修正→再交 | 臂檔 `/srv/vlab/arms/e002_H.md`（VLAB_APPEND_SYSTEM） |
| `M` | 多 agent：交件前必須另開第二個 agent 當獨立審查者（只評不代寫、一層） | 臂檔 `/srv/vlab/arms/e002_M.md`（VLAB_APPEND_SYSTEM） |
| `S` | 利害 (a)：後果框架，無任何新方法 | 臂檔 `/srv/vlab/arms/e002_S.md`（VLAB_APPEND_SYSTEM） |

- 任務：`/srv/eval/staged/polyglot_py` 全 34 題（unittest 方言；每題工作區含 contract.md/goal.md/*_test.py）。
- 格：A/C/H/M/S × 34 × 1 rep = **170 格**；超時 **1800 s/格**；模型 gemma-4-12b-it-qat（1004 本機，`http://100.86.226.21:1234/v1`）；PAR=2。
- 佇列檔**頂層** `vacant_sha = 12d1dc2a61592193a7c13a2b236dc5aa8f24e6d1`（labd 驗收要求頂層；＝e003 GO 版本）。
  exp 名 `e004_opencode_polyglot`、run 目錄 `/srv/vlab/runs/e004_opencode_polyglot/`；佇列檔編號沿現況。
- 臂檔為 KS-1 守衛全數 clean 檔（e002 驗證）；H-stakes 文字只存在於實驗臂檔，永不進產品 prompt。
- agent 版本：cell 環境內之 opencode（與 e003 冒煙 GO 同一環境）；若版本變動，報告中記為環境變數。

## 2. 預註冊假設（三條，互相競爭）

- **H-acc（究責）**：Vacant 的收據/閘門機制（驗收→擋回→回饋重試→簽收據）本身提升結果。臂：C。
- **H-review（審查）**：「交件前審查」提升結果——H（自檢指引）與 M（第二 agent 審查）為兩種實作，分臂判定。
- **H-stakes（利害，a）**：後果框架提升結果（只「只是講」、無真實後果）。臂：S。
- 答案是「哪個臂最好、差多少、花多少成本」，不是三個獨立的 yes/no。

## 3. 判準（發射前寫死）

每格計分：`score.json`（隱藏評分、不信任自我報告）；`pass=None` 或無 score.json = **infra，不進分母、單列**。
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

## 4. 回退邊界與限制

- **判定回退**：不顯著 ⇒「未建立」（不是負結果）；顯著但成本 > 2×A ⇒「有效但昂貴」；量不到 ⇒ UNKNOWN（H-stakes(b)「真實後果＝路由/續約」本輪不測，BACKLOG）。
- **機構回退**：任一臂 infra 連敗（臂檔不被 opencode 接受、第二 agent 命令不存在等）⇒ 該臂不計、先修機構/臂檔並複測冒煙再議發射；infra 格永不回填、結果永不捏造。
- 1 rep/題：配對設計消掉任務難度差異，但無 rep 內變異；rep 擴充另包。
- 模型為 gemma-4-12b 本地量化（H-12 類邊界）：結果不外推到別的模型/預算/任務庫。
- 臂檔為 pi 時期文字（e002_M.md 含 `pi -p` 字面）：opencode 下第二 agent 證據照 §3 證據規則判定；文字落差記為限制、非機制訊號。
- C 臂為 `12d1dc2a` 版本行為；若版本變動，兩版對照記為紅旗（版本/環境問題），非機制訊號。
- `vacant install` 改 cell 設定（可逆）與 `~/.vacant`（Vacant 自己管）；A/H/M/S 臂不裝 Vacant、不碰 `~/.vacant`。
- labd 串行 ＋ PAR=2：e002 同結構 170 格實際 wall ≈ 10h（36016s），本盤估同量級。
