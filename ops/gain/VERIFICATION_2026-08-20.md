# G 實驗交付包驗證紀錄（2026-08-20，Claude/opencode 本機執行）

驗證對象：`~/Downloads/Vacant_DOWNLOAD_ALL/`（Codex 交付的 download-recovery 包），
內含 git bundle（HEAD `f72aa6e`，base `b4e350d`）、source ZIP、workspace ZIP、
`evidence/22db0d7.patch`、以及 `Vacant-gain-delivery-2026-08-19.zip`（真模型 pilot 資料）。

本紀錄只寫我實際重跑過的東西。沒重跑的，標「未驗證」。

## 一、完整性（全部通過）

- `shasum -a 256 -c SHA256SUMS.txt`：12 項全 OK。
- `unzip -t` SOURCE／WORKSPACE 兩個 ZIP：無 CRC 錯誤。
- bundle `git clone` ＋ `git fsck --full`：無損毀（僅 dangling commits，正常）。
- bundle HEAD `f72aa6e` 的 8 個改動檔與 delivery zip `changed/` 內對應檔案
  **逐位元相同**（8/8 SAME）。
- 本機 `.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz` 的 sha256 與
  `codebench.py` 釘死值 `af43697e…` 一致。

## 二、測試（實跑）

| 環境 | 指令 | 結果 |
|---|---|---|
| bundle clone，py3.13.1 乾淨 venv | `pytest tests/test_gain_runner.py` | 16 passed |
| 同上 | `pytest tests/ --ignore=test_mcp_v2.py` | 550 passed, 1 skipped |
| 本 repo 融合後，py3.12.10 `.venv` | `pytest tests/`（全套含 mcp） | **562 passed** |

- bundle 上 `test_mcp_v2.py` 的失敗是環境問題（mcp 2.0 移除了
  `mcp.server.fastmcp` 匯入路徑），不是這次改動的回歸；本 repo 舊版 mcp 下全過。
- 交付自述的「targeted pytest 在 py3.13 達 120s 硬 timeout」：我這邊同檔 6 秒跑完。
  原因無從考證，但不影響結論——測試本身是真過的。

## 三、量具雙向驗證（實跑，零模型呼叫）

```
VACANT_EVALPLUS_PATH=<本機官方包> python ops/gain/gain_run.py \
  --out /tmp/vacant-probe-371-claude --n 371 --seed vm-canonical-371 \
  --arms probe --probe-sample 0
→ 參考解通過 371/371　壞解被擋 371/371
```

與交付宣稱的 VM 結果一致。這同時驗證了：MBPP+ 官方反序列化修正、
7 題 resource-exclusion（pin 在 `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS`，有測試釘住）、
sandbox 記憶體上限與非有限浮點 wire 編碼都是真的。

## 四、真模型 pilot 資料（內部一致性核對，未重跑）

- `v8r/summary.json` 與 SUMMARY.md 數字逐項相符：OFF 10/12（2 leak）、
  ON 10/12（1 leak）、improved=0／harmed=0、OFF5 缺 7 題（infra_void）。
- `clinepass-clean-v2/ABORTED.json`：OFF 12/12、ON 8/12 中止、OFF5 未跑，
  `equal_budget_comparison_valid=false`。
- **結論方向誠實**：ON 沒有提高正確交付率（0.8333 對 0.8333），只有接受精度
  較高（0.909 vs 0.833）。依 SPEC_GAIN §4 自己的判準，這只能說「比較可依賴」，
  不能說「產出變好」——交付文件也是這樣寫的。這點與 CLAUDE.md 鐵律 5 一致。

## 五、敘述與實物的落差（重要）

對話中最後那篇「最終交付已完成」描述了**另一個更大的 v2 包**（當時全部下載失敗）。
實際能下載、能驗證的是 22db0d7 這個較小的包。以下宣稱**不在**實際交付物內：

1. **Deadline quorum**（reviewer 不等最慢模型）：程式裡沒有。reviewer 仍是
   `ThreadPoolExecutor.map` 同步等全部回來。SUMMARY.md 自己把它列為「下一步」。
2. **五呼叫重新配置**（generator＋2 反例搜尋者＋裁決者＋reviser）：沒有。
   目前 ON 臂是 generator＋3 reviewer＋reviser＝5 呼叫，無獨立裁決者角色。
3. **Corpus 13/4/9 命名修正與 canonical aliases**：交付物內無 corpus manifest、
   無此拆分。題庫就是 EvalPlus 371 題子集按 seed 排序取前 n。
4. **「OFF5 不再是安全漏洞」**：**不成立，且是本包的真實缺口。**
   `gain_run.py:behavior_signature()` 用 `subprocess.run([sys.executable, …])`
   直接執行模型產生的程式——沒有 RLIMIT、沒有 import 白名單、沒有 env 清理，
   與 `vacant/checks.py` 的受限 worker 不同。OFF5 臂的多數決因此仍在
   非受限環境跑模型碼。要修：behavior signature 應改走 `run_python_check`
   的受限 worker 路徑。

## 六、憑證狀態（安全）

- 對話中貼出的兩把 Cline key，2026-08-20 實測**仍然有效**（各一次最小 probe，
  HTTP 200）。前一份交付已建議撤銷，但至今日未撤。**請立即到 Cline 後台撤銷
  並重發**。本 repo 與我的紀錄均未寫入金鑰。

## 七、融合

- 分支 `claude/fuse-gain-verified-20260820`：本機 HEAD（`99698d1`，展件工作）
  與 patch 改的 8 檔**零重疊**，patch 乾淨套上，測試 562 passed。
- 結論：這個包值得收——它修的是真 bug（官方反序列化、sandbox 記憶體、
  非有限浮點、infra_void 分類、可執行反例、reviser 不改壞），且自我宣稱克制。
  但它**不是**「增益已證明」：v8r 是 n=12 pilot 且 OFF5 不完整；
  依 SPEC_GAIN §7 與鐵律 5，展場只能說「可靠性訊號」，不能說增益。
