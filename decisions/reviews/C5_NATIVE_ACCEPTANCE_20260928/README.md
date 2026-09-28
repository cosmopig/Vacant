# C5 / Pi 原生平台整合審查

日期：2026-09-28  
來源分支：`claude/vacant-verification-redesign-jv7eou`  
審查分支：`review/c5-native-acceptance-20260928`

## 結論

C5 沒有重現論文中「單純 Vacant」的效果，主要不是模型突然失效，而是**目前測到的不是同一個處置**。

C361 的保存紀錄明確顯示：

```json
{"install_json":{"mode":"evidence","agents":["pi"]}, ...}
```

而 `vacant_home/adapters/install.json` 也記錄 `"mode": "evidence"`。目前無契約路徑在
agent 說完成時做 trace evidence review，最多退回兩輪；它不會以接收端持有的可執行
visible suite 對凍結候選做驗收，也不會以該驗收結果決定「交付同一候選 / 拒交 /
重新抽樣」。因此它不能被當成 CONFORM 的原生平台版本。

此外 C5 還有一個可直接修掉的量測 bug：Pi 實際用 `sh run_tests.sh` 跑 visible tests，
但 `trace/evidence.py` 的 `RUNNERS` 不認這個 wrapper，所以 Vacant 反覆告訴模型
「沒有跑測試」，造成不必要的重跑與額外模型請求。

## 資料完整性與重算

從使用者提供的 Drive 直接讀取 `chunk_0006.tar.xz` ～ `chunk_0043.tar.xz`。
38 個 archive 均依 `MANIFEST.tsv` 重算 SHA-256 與長度後一致。

C5 有 920 個 task pair，共 1,840 runs。

| 指標 | A: native Pi | C361: Pi + evidence Vacant |
|---|---:|---:|
| runs | 920 | 920 |
| hidden pass | 748 (81.30%) | 758 (82.39%) |
| visible pass | 837 | 846 |
| 沒有 solution.py | 42 | 34 |
| timeout | 71 | 65 |
| mean wall time | 508.59 s | 537.77 s |
| median wall time | 293.45 s | 355.20 s |
| wire requests | 7,648 | 8,594 |
| prompt + completion tokens | 55,291,115 | 60,584,748 |

配對結果：C-only 59、A-only 49，差 +1.087 percentage points；探索性雙尾 exact
McNemar p=0.38657。這份資料沒有建立 C361 的品質增益。

代價則已經可見：wire request +12.37%，prompt+completion token +9.57%，平均 wall
time +5.74%，median +21.04%。每個 hidden-pass 候選的 token 約從 73,918.6 升到
79,927.1（+8.13%）。

這些是目前資料的描述性結果，不把獨立生成的 C-only/A-only pair 解讀成「Vacant
救回/害掉」的因果件數。

### 分題庫

| bank | n | A pass | C361 pass | C-only / A-only | delta pp |
|---|---:|---:|---:|---:|---:|
| HumanEval+ | 155 | 150 | 150 | 2 / 2 | 0.000 |
| LCB v1 | 89 | 62 | 68 | 15 / 9 | +6.742 |
| LCB v2 | 118 | 88 | 87 | 16 / 17 | -0.847 |
| LCB v3 | 189 | 153 | 149 | 11 / 15 | -2.116 |
| MBPP+ | 369 | 295 | 304 | 15 / 6 | +2.439 |

## 已證實 bug：測試明明執行，Vacant 卻說沒執行

C361 有 472 次 zero-config feedback rounds，分布於 309 runs。其中 455 次 finding 是
`test_claim/sub=none`，也就是「final 說 tests pass，但記錄裡沒有 matching test」。

對保存的 Pi session 做嚴格重放：只在前面確實有**直接**
`sh run_tests.sh`、對應 tool result 由具名 `pass test_visible.py::...` 組成、最後唯一
摘要是 `0 check(s) failed`、且回饋前沒有後續未知 shell/write/edit 時才算。即使採這個
保守規則，仍有**至少 437 / 455 (96.0%)** 的「沒有跑測試」回饋可直接證明是誤報。
這是誤報下界，不是整個 Evidence detector 的一般 precision 估計。

可重現案例：

`c5-C361-humanevalplus-humanevalplus_HumanEval_141-s1`

第一次 `sh run_tests.sh` 顯示 26 個具名 pass + `0 check(s) failed`；assistant 回覆
“All tests passed.”，Vacant 卻回：

> The final message says "All tests passed", but no test or build command ran in the recorded steps.

模型照要求再跑，同樣 26 pass + 0 failed，第二次仍收到完全相同的 Vacant 回饋，之後又跑
第三次。這一格最後 hidden 1026/1026、visible 26/26。

根因在 `Evidence._test_claim()`：它先用 `RUNNERS` 過濾 command，而既有 pattern
不含 `sh run_tests.sh`。

## 本審查分支已直接修改

`vacant_network/trace/evidence.py` 已增加保守的 C5 direct wrapper parser：

- 只認 `sh run_tests.sh` / `bash ./run_tests.sh` 這種直接 invocation。
- tool error、正的 failed count、既有 FAIL_OUT 優先判 failed。
- success 必須有至少一個具名 case，最後一行恰為唯一的 `0 check(s) failed`。
- 空 suite、未知輸出、重複摘要維持 unreadable，不誤升為 pass。
- 原本 pytest/npm/go/cargo/... path 不變。
- 通過後若又改 code，原本 stale 檢查仍生效。

`tests/test_zero_evidence.py` 已新增回歸案例：direct pass、direct fail、pass 後 edit
變 stale、只是 echo wrapper 不算執行、empty suite 不升格。

**這個 patch 只修 trace 被錯讀，沒有把 agent 自己的 stdout 變成可信驗收。**

## 為什麼修完這個 bug 還不會等於論文 Vacant

### 1. C361 的 zero-config evidence 沒有 correctness oracle

`evidence.py` 的設計本來就明示「沒有契約、不知道正確答案」。它能檢查：
未讀素材、無來源數值、測試宣稱是否與 trace 對得上、忽略失敗步驟等。

這些是 consistency / provenance checks，不是任務正確性。

### 2. Stop hook 最終 fail-open

`zerostop.py`：
- `ZERO_MAX_ROUNDS = 2`
- checker timeout/error => allow
- feedback budget 用完 => allow
- 沒 findings => allow

這是合理的「不要讓旁路 observer 弄死 agent」產品選擇，但它不是 delivery gate。

### 3. A 已經不是論文裡的 single-shot OFF

A 本身有 7,648 個 wire requests，平均約 8.31 requests/task，原生 Pi 已經會讀檔、寫檔、
跑測試、自己修訂。C361 是在一個本來就很強的 agentic loop 上追加 evidence feedback。
因此不能把論文「單次生成 -> 外部 V 驗收 -> 最多五次重抽」的增益直接當作 C361 的期望值。

### 4. 可見測試若仍由 agent 控制，不能當信任根

即使修掉 wrapper parser，`run_tests.sh` / stdout 若可被 agent 修改或偽造，只能算觀察
證據。真正的 acceptance suite 必須由接收端在 agent 權限外持有或至少在 agent 開始前
被 pin/freeze。

## 正確的原生平台整合

保留 Pi/Claude Code/Codex 等平台本身，不改成 Vacant 自己造一個裸 LLM loop：

```
native agent
    |
    v
candidate snapshot -------> immutable artifact SHA
    |
    v
receiver-owned visible verifier (pinned suite/env)
    | FAIL / UNKNOWN
    +---------------------> visible feedback -> same native session
    |                                      or fresh full native session
    v PASS
signed acceptance receipt
    |
    v
release THE SAME frozen artifact
```

核心不在「攔每個模型 API」，而在 **settle/release boundary**：

1. agent 要結束時凍結 candidate。
2. 收件端自己的 verifier 在隔離環境執行。
3. FAIL 時：
   - NATIVE-REPAIR：把 visible failure 回原 native session。
   - NATIVE-CONFORM：開一個新的完整 native session，獨立重試。
4. PASS 時 release 同一個 artifact SHA，不再從可變 workspace 複製。
5. UNKNOWN / verifier crash / timeout / conflict 一律不冒充 PASS。
6. hidden GT 只做事後評分，不可流回生成與早停。

repo 既有 `vacant_network/intake/{contract,flow,verifiers}.py` 已經有 freeze、contract、
verifier、decision、reverify/release 的大部分基礎，不應在 zero evidence checker 裡重新
造一套 oracle。

## 下一個確認性實驗

保持「完整 native platform」的四臂：

| Arm | 外部 visible acceptance | fail 後行為 |
|---|---|---|
| NATIVE | 無，hidden 僅事後評分 | platform 原行為 |
| GATE-ONLY | 有 | 拒交，不增加生成 |
| NATIVE-CONFORM | 有 | 新的完整 native session |
| NATIVE-REPAIR | 有 | visible feedback 回原 native session |

修好的 Evidence 可額外當第五臂，但不能叫 CONFORM。

主要指標改成：
- `released AND hidden_pass`
- wrong release
- reject / UNKNOWN / verifier timeout
- candidate hidden quality（和 release 分開）
- tokens、wall time、requests、cost per correct release

固定 task-level token/wall budget；開發資料與 confirmation holdout 分開；C5 已經用來找 bug，
不能再宣稱是完全未看過的最終確認集。

## P0 必做 plumbing tests

在花模型算力前先用 fake native agent 跑 E2E：

1. wrong draft -> visible FAIL -> feedback -> fixed draft -> PASS -> release same SHA。
2. always wrong -> attempts exhausted -> no release。
3. missing output -> reject。
4. verifier crash/timeout -> UNKNOWN/void -> no release。
5. PASS 後 workspace 被改 -> released SHA 仍是先前 frozen artifact。
6. 接收端不讀 exit code / decision 的 harness 應直接讓測試失敗。
7. trace-only evidence finding 不可產生 acceptance receipt。

## Archive 安全性

C5 原始 archive 內含：
`vacant_home/intake/keys/*/identity.key`。

這次審查沒有讀取私鑰內容。即使它們只是每格實驗用 ephemeral key，也不應出現在可分享的
研究 archive。下一版 exporter 應明確 deny-list private keys/auth/token/session secrets。
如果這批 key 曾被跨 cell / 非實驗環境重用，應視為已暴露並 rotate；僅憑 archive 路徑
本身不能判定它們有沒有被重用。

## 本次變更邊界

已做：
- 直接重算 C5 38 archives 與 pair-level 結果。
- 找到並修正 `run_tests.sh` evidence 誤判。
- 補回歸測試。
- 定義原生 acceptance bridge 與下一輪實驗。

尚未宣稱：
- 沒有宣稱 C361 修完就一定會得到論文幅度。
- 沒有把 evidence mode 改名冒充 CONFORM。
- 沒有把 agent-controlled stdout 當成可信 verifier。
- 沒有合併到使用者工作分支。
- acceptance bridge 完整 E2E 尚需在真正 Pi eval 環境接線並跑 smoke/confirmation。
