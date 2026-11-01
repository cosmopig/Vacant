# Research Packet e010 — 大工作區用量格子（主軸 2）

日期：2026-11-01（round 823）。作者：研發負責人。DECISION：`decisions/DECISION_20261101_BIGWORK_USAGE_CELL.md`。

## 1. 問題與可推翻假說
- **問題**：repo 級工作區（299M／6,541 檔案，≈10/28 事件 2G／23,594 快照的 28% 規模）上，
  現行版本（683bbb83）的 C 臂 `~/.vacant` 實際長多大？
- **假說 H**：現行 retention（trace 64MiB 上限／穩態 256MiB 封頂＋自動 GC）把 C 臂
  `vacant_home_bytes` 壓在 ≤256MiB，且 <0.5× workspace（149.5M）——即 10/28 事件
  （872M≈0.44× repo）的失敗模式在新版本不復發。
- **推翻條件**：任一 C 格 `vacant_home_bytes` >256MiB（封頂在真機環境未生效）或
  ≥149.5M（「不能是 repo 的一半大」驗收線破）⇒ H 不成立。
- **什麼算沒用／量不到**：格子 infra、`vacant_home_bytes` 缺失 ⇒ UNKNOWN，不寫 PASS。

## 2. 基線與負對照
- **基線（小工作區 regime）**：既有 183 個 C 臂格子 workspace 全部 ≤23.1 MiB
  （dabstep 單一資料檔）、`vacant_home_bytes` 34K~232K B（69 格口径，envelope_compliance 全 PASS）。
- **基線（大工作區、非實驗室）**：真機序列 72 點／86.9h（本機 2G repo）：peak 82.3 MiB、
  latest 67.5 MiB、24h 視窗最大增長 16.3 MiB、淨增長 −14.8 MiB、gc ok／target_reached
  （`~/dev/ops/data/vacant_growth.jsonl`＋`growth_report.py` verdict=PASS）。
- **負對照（已知失敗模式）**：10/28 事件——舊版本 23,594 快照→829M objects；
  本實驗即在新版本上重試該場景（28% 規模）。

## 3. 程式碼變更
無（純量測）。新增量測素材：`/srv/eval/staged/bigwork/bw_repo_readme`（**新增**，
不改既有題庫、不改 cell.py／labd.py／report.py）。工單：
`~/dev/ops/tickets/open/R20261101_1107-1-stage-bigwork-e010.md`（助手在 1004 執行）。

## 4. 來源
- vacant_sha：`683bbb83`（auto/qwen27b，CI 4612 passed 綠；與 HEAD 61d14ebd 執行期程式碼同一份）
- workspace：`~/dev/Vacant` 副本，排除 `.git`/`.venv`/`node_modules`/`runs`/`tmp`/`ops/gain`
  ＝ 299M／6,541 檔案；`workspace_sha256` 以 cell.json 記錄值為準
- 模型：gemma-4-12b-it-qat（1004）；agent：pi；格子：A-r1（可行性對照）＋C-r1（主指標）
- 原始格子：`/srv/vlab/runs/e010_bigwork_pi_AC/`

## 5. 實際結果（完賽後回填；只引用 REPORT.json／cell.json）
- [ ] C-r1 `vacant_home_bytes` ≤256MiB 且 <149.5M（0.5× workspace）
- [ ] `vacant_objects_bytes` 與 `vacant_home_bytes` 落盤可核
- [ ] `report.py e010_bigwork_pi_AC --rescore` 0 格不一致（score 為完成信號，A/C 各 1 格）
- [ ] `envelope_compliance.py e010_bigwork_pi_AC` verdict=PASS
- [ ] 任一未量到＝UNKNOWN（分開列，不併入 PASS）

## 6. 限制與回退
- 28% 規模，非全規模：若 PASS 且 1004 磁碟有餘（e009 完賽後），再排全規模
  1.3G／41k 檔案格（BACKLOG）；若此格已近封頂，加 rep2 看變異。
- 單 C 格無變異估計；agent 1800s 內未必讀遍所有檔——但 retention 首次掃描即按專案
  檔案計（retention.py docstring），用量數是下限偏保守，條目內標注。
- 回退：刪 `/srv/vlab/queue/11_e010_bigwork_pi_AC.json`（若在 queue）＋
  `/srv/eval/staged/bigwork/`（僅本次新增）；repo 無功能碼改動。

## 7. 獨立重驗指令
```bash
python3 /srv/vlab/bin/report.py e010_bigwork_pi_AC --rescore
python3 - <<'EOF'
import json, pathlib
for p in sorted(pathlib.Path("/srv/vlab/runs/e010_bigwork_pi_AC").glob("*/cell.json")):
    d = json.loads(p.read_text())
    print(p.parent.name, d.get("pass"), d.get("vacant_home_bytes"), d.get("vacant_objects_bytes"))
EOF
cd ~/dev/Vacant && .venv/bin/python ops/vlab/tools/envelope_compliance.py e010_bigwork_pi_AC
```
