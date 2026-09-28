# Native Acceptance Bridge 審查修正與 R534 封存重算

2026-09-28；分支 `fix/native-acceptance-bridge-audit-20260928`，從 PR #82 head `8d2f2411` 開出，並合入 v3.7／審查所在的上游 `fb32c622`。

## 修正的裁決邊界

| 審查問題 | 現在的行為 |
|---|---|
| agent 改工作區契約 | receiver 只開自己保存並簽鎖的契約；工作區副本不同時 judge HOLD，不產生接受裁決。 |
| receiver home 沒給、在工作區或同帳號 | 必須明給外部 receiver home；預設拒絕同帳號。非對抗實驗必須明示 `--insecure-same-account`，記在簽署的契約。 |
| 舊 run 的 accept 被新 run 放行 | 每個 run 使用新的 receiver home 與 `bridge_run_id`；禁止覆蓋既有契約；release 必須給剛接受的 `--artifact`，且它必須是最新裁決。 |
| 無限重判 | `attempt_started` 入帳，嘗試次數遞增且受合約上限約束；接受後不能再判。 |
| 巢狀測試或錯格式漏跑 | prepare 拒絕巢狀 `test_*.py` 和沒有頂層 `check_*`／`main` 的檔案。 |
| 工作區套件漂移及收件目錄 | prepare 在 agent 開始前複製套件到 receiver home 旁的唯讀目錄；驗收以這份固定副本為準。放行目錄必須在 receiver home 內，評分讀其發布路徑。 |

安全界限：`python_checks` 與候選 Python 在同一行程，對惡意候選碼不能保證正確判定。
`--insecure-same-account` 只是非對抗回歸的顯式例外，不能用來宣稱同帳號的 agent
無法改簽署金鑰。實際 receiver 須是不同 OS 帳號，其 home 的父目錄不可由 agent 寫入；
REPAIR 的套件副本還需讓 agent 唯讀存取。Pi／OpenCode 仍是原本 native agent；
bridge 在它們的工作階段外先 `prepare`、結束後同步 `judge`、通過才 `release`。
CONFORM 的下一次嘗試由外層啟動完整新 session，bridge 不替換模型路由。

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

以 `MANIFEST.tsv` 驗證 43 個 tar.xz 的 SHA-256／長度；唯讀解析 `score.json`，
沒有解開或執行封存裡的候選碼、認證檔、`.pyc`。重算指令：

```bash
python ops/eval/replay_r534_gate_scores.py \
  --manifest /path/to/MANIFEST.tsv --archive-root /path/to/chunks
```

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

940 對的配對 hidden 結果：共同正確 711、共同錯誤 116、僅 C361 正確 62、
僅 A 正確 51。R534 與先前 C5 的 920 題統計是不同批次，不能混加。

這個重算只給出 **GATE 的事後上限**：GATE 降低錯誤交付，不能讓原本錯的程式變對。
REPAIR／CONFORM 的增益必須重新跑 native Pi／OpenCode 並記錄每輪 feedback、
新 session、成本及放行檔；舊封存無法模擬模型收到回饋後的行為。
大多數封存沒有原始 visible test `.py`（A 缺 939/940，C361 缺 940/940），
但倉庫的 `ops/gain/r534/templates/` 保留題庫樣板。這個執行環境的 `bwrap`
探測失敗、`auto` 退到 `none`，因此未在這裡執行封存中的候選程式；
不能把 score 重算稱為新版 bridge 的 1,880 次實際驗收。

## 待驗證的效果

先在可隔離的機器上做真 Pi / Gemma 小批冒煙，確認 receiver 用自己的帳號、
`judge` 的 artifact SHA 與 release readback 相等、REPAIR 確實收到失敗回饋；
再用未見過的題目比較 NATIVE、RETRY-NOSUITE（相同 session 與時間預算）、
CONFORM 和 REPAIR。主要指標是 `released AND hidden_pass`，另記 wrong release。
目前的 13 條 bridge 單元及端到端回歸，驗證的是機制正確，**尚未證明恢復 main 的答對率增益**。
