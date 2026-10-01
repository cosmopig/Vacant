# Native Acceptance Bridge 審查修正與 R534 封存重算

2026-09-28；分支 `fix/native-acceptance-bridge-audit-20260928`，從 PR #82 head `8d2f2411` 開出，並合入 v3.7／審查所在的上游 `fb32c622`。

## 修正的裁決邊界

> 2026-10-01：下表已改成**目前**的 bridge（`6c2405de` 之上的最小修正，審查見
> [`FINDINGS_20260930_PR82_FIXBRANCH_REVIEW.md`](../../conclusions/FINDINGS_20260930_PR82_FIXBRANCH_REVIEW.md)）。
> `6c2405de` 當時的行為與現在不同的地方，引用舊版時請對照：
> (1) 工作區契約與 receiver 的不同＝judge **HOLD**（記 `infra_void`、燒掉一次嘗試、回 exit 41／`void:false`），release 也拒絕；現在只**回報**。
> (2) 嘗試以 `attempt_started` 的個數計，所以 `--sandbox` 打錯、judge 被殺、OSError、驅動啟不動都會燒掉嘗試；現在**只有裁決**計。
> (3) release 的 infra void 與「發到一半」都回 44；現在 0／43／44／45。
> (4) 沒有沙箱預檢，`auto` 在沒有 bwrap 時悄悄退到 `none`，分開帳號下候選碼就以 receiver 的 uid 執行；現在分開帳號只收 bwrap。
> (5) prepare 不是原子的、`--replace` 被接受卻永遠報錯、`--destination` 說明與行為相反、scaffold 的兩條安全底線被蓋掉；現在都修了。
> (6) 測試 13 條→91 條（另有 `test_replay_r534_gate_scores.py` 5 條）。

| 審查問題 | 現在的行為 |
|---|---|
| agent 改工作區契約 | receiver 只開自己保存並簽鎖的契約（`<receiver_home>/contract.json`，每個指令都驗鎖）。工作區副本只做**位元組**比對，結果印在 judge／release／status 輸出的 `workspace_contract_matches_receiver`；**不 HOLD、不 void、不拒絕、不耗嘗試**（`git clean -fd`、換一個全新 /app 都不會讓格子報廢）。 |
| receiver home 沒給、在工作區或同帳號 | 必須明給外部 receiver home；路徑的每一段都不得是 symlink（`prepare`／`judge`／`release`／`status` 都查）；預設拒絕同帳號。非對抗實驗必須明示 `--insecure-same-account`，記在簽署的契約。 |
| 沙箱後端 | 未加 `--insecure-same-account` 時只收 **bwrap**（`none`／`unshare` 不對候選碼隱藏檔案；`auto` 解析成它們也拒）。解析後的後端、`evaluator_euid` 寫進契約 notes、`attempt_started` 與 judge 輸出。bwrap **不會**替 root 評測端降權：對抗性邊界需要非 root 的評測帳號。 |
| 舊 run 的 accept 被新 run 放行 | 每個 run 使用新的 receiver home 與 `bridge_run_id`；禁止覆蓋既有契約；release 必須給剛接受的 `--artifact`，且它必須是最新裁決。release 結束碼與 `vacant release` 同表：0 已放行且讀回成立、43 void、44 拒絕、45 放行未確認（效果未知或讀回不成立）。 |
| 無限重判／評測端失敗燒掉嘗試 | **只有裁決（accept／reject／hold／escalate）用掉一次嘗試**；`--attempt` 必須是「已有裁決數＋1」（gate／repair 可省略）。judge 在寫 `attempt_started` 之前先做沙箱預檢（`python3 -c 'print(1)'`，30 秒）；失敗記 `infra_void`（stage `preflight`）、exit 43、不計次。`flow.submit` 內的未預期例外同樣記 `infra_void`（stage `judge`）、exit 43；被殺的 judge 只留下 `attempt_started`、沒有裁決，同一個編號可重判。同一編號累積 3 次失敗（`infra_void` 或沒有裁決的 `attempt_started`）就拒絕並 exit 43：「void cap reached…，換新的 receiver home 重跑這一格」。接受後不能再判。`--sandbox` 只收 `auto|bwrap|unshare|none`。 |
| 未預期例外 | `main()` 不印 traceback：其他子指令的未預期例外一行訊息、exit 2；judge 只在 `attempt_started` 之後的例外才是 void／43。 |
| 巢狀測試或錯格式漏跑 | prepare 拒絕：任何不是 `__pycache__` 的子目錄、任何非 `.py` 檔、任何 symlink、沒有頂層 `check_*`／`main` 的測試檔、帶必要參數的頂層 `check_*`（執行器只把最上層 `.py` 送去跑，訊息會點名檔案並這樣寫）。 |
| 工作區套件漂移及收件目錄 | prepare 在 agent 開始前複製套件到 receiver home 旁的唯讀目錄；驗收以這份固定副本為準（被改 ⇒ UNKNOWN ⇒ HOLD）。`--agent-suite`（預設 `<workspace>/tests_visible`，沒有就是無）的雜湊記為 `agent_visible_suite_sha256`，連同 `pinned_suite_sha256`、`agent_visible_suite_matches_pinned` 寫進 prepare 輸出與契約 notes；judge／status 重算並回報（資訊性）。放行目錄必須是 receiver home 內的 `dir:`（`--destination`；預設 `<receiver-home>/released`），評分讀其發布路徑。契約的 `effects.protect_paths` 列出 receiver home 與固定套件，原生**寫入**工具在那裡被拒，shell 指令的**直接**寫法（`>`／`>>`、`tee`／`cp`／`mv`／`rm`／`touch`／`sed -i`／`dd of=`、帶 `open(` 的 `python -c`）也被字串層級的檢查拒絕；**間接寫法（變數拼路徑、先寫腳本再跑）與所有讀取都放行**（`tests/test_native_acceptance_bridge.py::test_shell_guard_denies_direct_writes_but_not_indirect_forms_or_reads`）。 |
| prepare 失敗留下殘餘 | 先做完所有驗證（含沙箱預檢）才建立任何東西；之後任何一步失敗都先 `chmod -R u+w` 再回收這次建立的目錄、唯讀套件副本與兩份契約，然後把例外丟出去。 |
| 評分不能被預設佔位的 claims 蓋掉 | 保留 scaffold 的 `deliverable_present`、`no_secrets_shipped`，在後面加 `visible_acceptance`。 |

安全界限：`python_checks` 與候選 Python 在同一行程，對惡意候選碼不能保證正確判定。
`--insecure-same-account` 只是非對抗回歸的顯式例外，不能用來宣稱同帳號的 agent
無法改簽署金鑰。實際 receiver 須是不同 OS 帳號，其 home 的父目錄不可由 agent 寫入；非 root 的評測端要寫得進 agent 擁有的工作區目錄（prepare 要寫 `<workspace>/.vacant/contract.json`，例如 `chgrp <評測端 gid> /app && chmod 775 /app`），否則 prepare 以一行 EACCES 失敗並整批回收（README §8）；
REPAIR 的套件副本還需讓 agent 唯讀存取。Pi／OpenCode 仍是原本 native agent；
bridge 在它們的工作階段外先 `prepare`、結束後同步 `judge`、通過才 `release`。
CONFORM 的下一次嘗試由外層啟動完整新 session，bridge 不替換模型路由。
`$TASK` 是 `--task-id`；`$RUN`＝任務×臂×重複，**每個 run 一個新的 receiver home 與乾淨的工作區**
（失敗的 prepare 已經整批回收，換新的 home 即可重來；judge 不依賴工作區的 `.vacant`，每個 session 換全新的 `/app` 也不會讓格子報廢）。

```bash
python ops/eval/native_acceptance_bridge.py prepare \
  --workspace /app --task-id "$TASK" --mode conform --attempts 5 \
  --receiver-home "/srv/eval/receiver/$RUN/vacant"
# 跑原生 Pi 或 OpenCode；不接受 agent 自己說「測試已過」當裁決。
python ops/eval/native_acceptance_bridge.py judge \
  --workspace /app --attempt 1 --receiver-home "/srv/eval/receiver/$RUN/vacant"
# 只有接受時，從 judge JSON 取得 artifact_sha256，交給 receiver 放行：
python ops/eval/native_acceptance_bridge.py release \
  --workspace /app --artifact "$ACCEPTED_SHA" \
  --receiver-home "/srv/eval/receiver/$RUN/vacant"
```

## 使用者提供的 R534 歷史封存

> 2026-10-01 更正（審查 F06）：這一節原本寫「R534 與先前 C5 的 920 題統計是不同批次，不能混加」，並給出每臂 940 格的表。
> **那不成立**：43 個分包是**同一份封存、兩個批次**，以 cell 名稱第一段分開——
>
> - `calib1`（分包 0001–0004，40 格）：20 題 × 2 臂，吞吐校準；Colab RUNLOG 宣告「不是預註冊批次、不看分數」，用**凍結前的舊評分器**；
> - `c5`（分包 0006–0042，1,840 格）：920 題 × 2 臂，正式批次，**就是 C5 README 的那 920 對**（0005 與 0043 沒有計分格）。
>
> 原本的 940 格表把兩者混加：它不是額外證據，不是 C5 的基準，還混了兩版評分器。下面先給 c5 與 calib1 各自的表，
> 原本的合併表保留在最後、重新標示，**不要引用**。數字全部由同一支腳本重算，沒有改動（原表的數字一個都沒變）。

以 `MANIFEST.tsv` 驗證 43 個 tar.xz 的 SHA-256／長度；唯讀解析 `score.json`，
沒有解開或執行封存裡的候選碼、認證檔、`.pyc`。重算指令（預設分批次輸出；`--campaign c5` 時頂層的 `arms`／`paired_*`
就是 c5；兩批合併只在明給 `--merged` 時以 `merged_*` 鍵印出）：

```bash
python ops/eval/replay_r534_gate_scores.py \
  --manifest /path/to/MANIFEST.tsv --archive-root /path/to/chunks --campaign c5
```

### c5（正式批次，920 對；與 C5 README 的 748／758、p＝0.3866 相同）

| 指標 | A（Pi） | C361（Pi + Evidence） |
|---|---:|---:|
| 格數 | 920 | 920 |
| hidden 正確 | 748 | 758 |
| 最終有 `solution.py` | 878 | 886 |
| 有檔但 hidden 錯 | 130 | 128 |
| 可見驗收過 | 837 | 846 |
| GATE 可放行且 hidden 正確 | 748 | 758 |
| GATE 仍放行錯誤 | 89 | 88 |
| GATE 擋住有檔的錯誤 | 41 | 40 |

920 對的配對 hidden 結果：共同正確 699、共同錯誤 113、僅 C361 正確 59、僅 A 正確 49（exact McNemar p＝0.3866）。

### calib1（校準，20 對，舊評分器；**單獨看，不要和 c5 加起來**）

| 指標 | A（Pi） | C361（Pi + Evidence） |
|---|---:|---:|
| 格數 | 20 | 20 |
| hidden 正確 | 14 | 15 |
| 最終有 `solution.py` | 19 | 16 |
| 可見驗收過 | 15 | 15 |
| GATE 仍放行錯誤 | 1 | 0 |
| GATE 擋住有檔的錯誤 | 4 | 1 |

配對 hidden：共同正確 12、共同錯誤 3、僅 C361 正確 3、僅 A 正確 2。40 個 calib 格的 `score.json` 沒有
`suite_timeout_s`／`timed_out`／`n_visible_files`（c5 的 1,764 格有），佐證它們是凍結前的舊評分器。

### 原本的合併表（2026-10-01 重新標示：calib1＋c5，兩版評分器；**不是 C5 的基準，不要引用**）

| 指標 | A（Pi） | C361（Pi + Evidence） |
|---|---:|---:|
| 格數 | 940 | 940 |
| hidden 正確 | 762 | 773 |
| 最終有 `solution.py` | 897 | 902 |
| 有檔但 hidden 錯 | 135 | 129 |
| 可見驗收過 | 852 | 861 |
| GATE 可放行且 hidden 正確 | 762 | 773 |
| GATE 仍放行錯誤 | 90 | 88 |
| GATE 擋住有檔的錯誤 | 45 | 41 |

940 對的配對 hidden 結果：共同正確 711、共同錯誤 116、僅 C361 正確 62、僅 A 正確 51（合併 exact McNemar p＝0.347）。

這個重算只給出 **GATE 的事後上限**：GATE 降低錯誤交付，不能讓原本錯的程式變對。
REPAIR／CONFORM 的增益必須重新跑 native Pi／OpenCode 並記錄每輪 feedback、
新 session、成本及放行檔；舊封存無法模擬模型收到回饋後的行為。C5 的 NATIVE 臂事後上限表見
[README.md](README.md) 第 2.1 節。
大多數封存沒有原始 visible test `.py`（c5：A 缺 919／920，C361 缺 920／920；合併計 939／940 與 940／940）。
`ops/gain/r534/templates/` 只保留 **20 題校準集（＝`calib1` 的 20 題）**的樣板：這 20 個題目 id 在 c5 的 LCB 格出現過 35 次，
但那些格的 `test_visible.py` 雜湊與樣板不同，所以 920 題正式批次沒有一題的樣板可用；拿樣板做「bridge 對 visible_pass 的一致性檢查」
只涵蓋約 2% 的格，不能當成 c5 的零成本一致性檢查。這個執行環境的 `bwrap`
探測失敗、`auto` 退到 `none`，因此未在這裡執行封存中的候選程式；
不能把 score 重算稱為新版 bridge 的 1,880 次實際驗收。

## 待驗證的效果

先在可隔離的機器上做真 Pi / Gemma 小批冒煙，確認 receiver 用自己的帳號、
`judge` 的 artifact SHA 與 release readback 相等、REPAIR 確實收到失敗回饋；
冒煙時每臂回報 reject／hold／void 各幾格，以及 **REPAIR 真的收到回饋的格數**（操弄檢查，見下一節）。
再用未見過的題目比較 NATIVE、RETRY-NOSUITE、CONFORM 和 REPAIR。
RETRY-NOSUITE＝**預算相同、不用套件**：同樣的最多 session 數與每個 session 的時限，撞時限或沒有檔就重跑一個新的完整 native session、留最後一次。
確認性的比較是 CONFORM 對 RETRY-NOSUITE，主要指標 `released AND hidden_pass`，wrong release 是 Holm 共同主要；
巢狀的臂不要對 NATIVE 做 McNemar；920 題、每題跑一次大約只看得到 +3.2 個百分點（設計與檢定力見 [README.md](README.md) 第 7 節）。
2026-10-01：bridge 單元與端到端回歸現在是 89 條（原本 13 條；另有 replay 的 5 條）。它們驗證的是機制正確，
**尚未證明恢復 main 的答對率增益**。

## 已知還沒修的（2026-10-01；逐條處置見審查文件文末）

- **REPAIR 的處理組可能靜默失效（F18）**：Stop 掛鉤失敗一律放行，bridge 沒有「回饋真的送達」的量測；預註冊要寫操弄檢查（真的收到回饋的格數），見 README 第 6 節。
- **「是不是同帳號」是啟發式（F19）**：只比較工作區 owner 的 uid 與評測端 euid；請讓 agent 以工作區 owner 的 uid 執行，並記錄實際 uid。
- **`status.destination_live` 是 release 當下的讀回（F15）**：評分器必須自己對已發布的檔案算 sha256，不能讀 `status`。
- **後端沒有簽進 decision（F01／F17）**：只在 `attempt_started`、契約 notes 與輸出；repair 的 Stop 掛鉤（`flow.check` 預設 `auto`）與 judge 可能用不同後端。
- 掛鉤取**最近的**契約（F20b）：agent 在子目錄放一份契約，repair 回饋評估的是另一份；bridge 的漂移比對只看 `<workspace>/.vacant/contract.json`。
- prepare 沒有真的跑過套件（F04 的 `--reference` 預檢沒做）；預檢之後才出現的 `python3` rc=127（競態）仍是 FAIL（F05）。
- `python_checks` 偽造與同帳號繞過：已文件化，沒有行程外的 verifier（M8、H2）。
- 契約 notes 沒有記 `vacant_network` 的版本（W3 只做到 `sys.path` 一半）；`_task_id` 與 attempts 範圍檢查的重複守衛還在（W5）。
