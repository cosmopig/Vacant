# C5 / Pi 原生平台整合審查：Evidence ≠ Acceptance

> 後續 bridge 安全修正與 R534 封存重算見 [BRIDGE_AUDIT_FIX_R534_REPLAY.md](BRIDGE_AUDIT_FIX_R534_REPLAY.md)。
> 本頁第 5 節的舊 CLI 範例屬 PR #82 審查前版本；實際接線請用後續文件的
> `--receiver-home`、`--artifact` 和隔離目的地規則。

日期：2026-09-28  
來源分支：`claude/vacant-verification-redesign-jv7eou`  
本審查基準：`122a424c3e29e190871ce13a41b049e08900dc4e`  
實作分支：`review/c5-native-acceptance-v2-20260928`

## 一句話結論

C5 沒有重現論文裡「單純 Vacant / CONFORM」的幅度，最主要的原因是 **C361 實際測的是
`mode: evidence`，而不是 CONFORM 的 executable acceptance + retry**。

C5 同時還真的踩到一個 Evidence bug：Pi 用 `sh run_tests.sh` 跑完 visible tests，
舊版卻說「沒有跑測試」，造成大量無效重跑。這個問題在本審查進行期間已由上游 v3.7
用較一般化的 `SCRIPT_RUNNER` 修正；**本分支不再覆寫 evidence.py**，只建立上游尚未接上的
native acceptance bridge。

## 1. C361 實際跑的是什麼

Drive 原始 cell 裡：

```json
{"install_json":{"mode":"evidence","agents":["pi"]}, ...}
```

`vacant_home/adapters/install.json` 亦為：

```json
{"mode":"evidence", ...}
```

這條路徑是在 native agent 宣告完成時檢查 trace 是否支持它的敘述，例如：

- 點名的材料有沒有讀；
- 數值是否可追溯；
- 說 tests passed 時 trace 裡有沒有測試；
- 失敗步驟是否被略過。

它**不知道任務正確答案**，也沒有 receiver-owned V 去決定 candidate 是否能 release。
所以這是 consistency/provenance review，不是 CONFORM。

## 2. 原始 C5 資料重算

使用者提供的 Drive 中 `chunk_0006.tar.xz`～`chunk_0043.tar.xz` 共 38 包；
逐包依 `MANIFEST.tsv` 重算 SHA-256 與檔案長度均一致。

C5 共 920 個 A/C361 pair，1,840 runs。

| 指標 | A: native Pi | C361: Pi + Evidence |
|---|---:|---:|
| hidden pass | 748 / 920 (81.30%) | 758 / 920 (82.39%) |
| visible pass | 837 | 846 |
| missing solution.py | 42 | 34 |
| timeout | 71 | 65 |
| mean wall | 508.59 s | 537.77 s |
| median wall | 293.45 s | 355.20 s |
| wire requests | 7,648 | 8,594 |
| prompt + completion tokens | 55,291,115 | 60,584,748 |

配對：C-only 59、A-only 49，差 **+1.087 pp**；探索性 exact two-sided McNemar
**p=0.38657**。這份資料沒有建立 C361 的品質增益。

C361 的成本則增加：
- wire requests +12.37%
- prompt+completion tokens +9.57%
- mean wall +5.74%
- median wall +21.04%
- token / hidden-pass candidate 約 +8.13%

A 自己已經平均 8.31 wire requests/task，所以它不是論文的 single-shot OFF；
native Pi 本身已會讀檔、測試、修訂。這也會壓低額外 feedback 的邊際效果。

## 3. 已證實的 Evidence 誤退

最清楚的 cell：

`c5-C361-humanevalplus-humanevalplus_HumanEval_141-s1`

Pi 第一次 `sh run_tests.sh` 就輸出 26 個具名 pass，最後：

```
0 check(s) failed
```

assistant 說 “All tests passed.”，舊版 Vacant 卻回：

> The final message says "All tests passed", but no test or build command ran in the recorded steps.

模型又跑第二次，仍收到同樣誤退，再跑第三次。該 cell 最終 hidden 1026/1026、
visible 26/26。

上游 v3.7 的 replay 現在直接佐證同一診斷：

| replay | rows | continue | allow | test_claim/none |
|---|---:|---:|---:|---:|
| v3.6.1 | 1,327 | 472 | 855 | 543 findings |
| v3.7 | 1,327 | 32 | 1,295 | 0 |

v3.7 剩下的 findings 是 `failed_step`、`missing_output`、`unsourced`、
`test_claim/stale`，不再是「跑過 test script 卻看不到」。

因此：**Evidence parser 的 bug 已由 upstream 正確接手，不應在本 PR 再做一份平行 patch。**

## 4. 為什麼 v3.7 還是不等於論文 Vacant

修掉誤退後，Evidence 只會變得「比較不浪費」，不會自動得到 CONFORM 的機制：

```
Evidence:
native agent -> trace review -> maybe feedback -> allow

CONFORM / Acceptance:
native agent -> freeze candidate -> receiver-owned visible verifier
                                  -> FAIL: retry
                                  -> PASS: release exactly that frozen artifact
```

真正缺的不是更多 regexp，而是 **acceptance / release boundary**。

## 5. 本分支新增：native acceptance bridge

新增：

`ops/eval/native_acceptance_bridge.py`

它不呼叫任何 model API，也不自己造 agent loop；它只把現有 native platform 接到 repo
已經有的 `intake/{contract,flow,verifiers}.py`。

### prepare

在 agent 開始前：

1. 建立 `.vacant/contract.json`。
2. 將 evaluator 的 visible suite 註冊為 `input:visible_suite`。
3. 用 `python_checks` 作 required claim。
4. `flow.lock` 先計算 suite hash 並簽 contract lock。
5. repair 模式才開 native Stop feedback；conform/gate 不開。
6. 關閉背景 `submit_on_end`，避免與 outer harness 的同步 judge 競爭。

推薦把 verifier copy 放在 agent workspace 外、由 score/receiver account 擁有：

```
/app/tests_visible                         # agent 可讀、自己測
/srv/eval/receiver/$TASK/tests_visible    # receiver copy，agent 不可寫
/srv/eval/receiver/$TASK/vacant           # receiver keys/ledger
```

### judge

agent session 結束後，由 evaluator 同步執行：

```bash
python ops/eval/native_acceptance_bridge.py judge \
  --workspace /app \
  --attempt 1 \
  --receiver-home /srv/eval/receiver/$TASK/vacant
```

它走正式 `flow.submit`：

```
freeze candidate
 -> content-addressed artifact SHA
 -> verify pinned suite on frozen copy
 -> signed decision
 -> ledger
```

FAIL / UNKNOWN / CONFLICT 都不是 PASS。

### release

只有 accepted artifact 才經 receiver gate release；release 的是隔離區內**同一個 SHA**，
不是重新從可變的 `/app` 複製一次。

## 6. 三種實驗臂

bridge 支援：

| mode | native Stop feedback | 外層行為 |
|---|---|---|
| gate | 無 | 一次 candidate，FAIL 就拒交 |
| repair | 有 | FAIL 回同一個 native session 修 |
| conform | 無 | FAIL 後外層啟一個**新的完整 native session**，預設最多 5 次 |

重要：CONFORM 的 retry 必須是新的完整 Pi session，不是直接再呼叫裸模型。

## 7. 建議下一輪四臂確認實驗

| Arm | acceptance | retry |
|---|---|---|
| NATIVE | 無；hidden 只事後評分 | platform 原行為 |
| GATE-ONLY | pinned visible suite | 無 |
| NATIVE-CONFORM | pinned visible suite | fresh full native session |
| NATIVE-REPAIR | pinned visible suite | same native session + visible failure feedback |

Evidence v3.7 可另列第五臂，但不要再叫 CONFORM。

主要指標應改成：
- `released AND hidden_pass`
- wrong release
- reject / HOLD / verifier infra void
- candidate hidden quality
- token / wall / requests / cost per correct release

hidden GT 只能在 selection/release 之後評分，不得回流 retry。

## 8. 信任邊界

`python_checks` 適合這批 C5 的非對抗 coding benchmark，但 repo 自己也明示：
candidate code 與 Python checks 在同一 interpreter，**防意外、不防惡意**。

若要把研究推到「對抗性 agent 的可信交付」，下一步應換成 receiver-side `command`
verifier / data-driven suite，並把 receiver keys、suite、runner 放到另一個 OS account/process
甚至另一台機器。

這也是 bridge 加 `--receiver-home` 的原因：signing state 不需要再像 C5 archive 那樣
落在 agent 的 `VACANT_HOME`。

## 9. Archive 安全性

原 C5 archive 內含：

`vacant_home/intake/keys/*/identity.key`

本審查沒有讀取 private-key 內容。下一版 exporter 應 deny-list：
- `**/identity.key`
- auth/token/session secret
- receiver signing state

若該批 key 曾跨 cell 或用於非實驗環境，應 rotate；僅從 archive 內存在 key 無法證明
它們是否真的被重用。

## 10. 本 PR 的邊界

這份 PR **不再修改 v3.7 Evidence**。它只做：
- 保存 C5 根因與重算結果；
- 加入 native executable acceptance bridge；
- 加入 pin / reject / accept / release / drift / conform-attempt 的 E2E tests。

它不宣稱：
- C5 舊結果因為修 parser 就能改寫；
- native acceptance 已量到論文相同增益；
- C5 可以再次充當完全 unseen confirmation set。

要回答「移植到 native agent platform 後是否真的恢復增益」，仍需要用上面的四臂設計重跑
一個新的 holdout。
