# 零設定 v3.7 的離線驗證（2026-09-28）

裁決：`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` §十一。重播工具：`ops/eval/colab_replay/replay_reviews.py`。

- `replay/v361_*.jsonl`：用當時的版本（`c27641c6`）在錄好的 C 組病歷上、每一次交件前檢查的那一刻重算——**保真**：Colab 1327／1327、u274 81／81、S36-nocap 80／80 次檢查和紀錄的動作與類別相同，全部對齊（`aligned`）。
- `replay/v37_*.jsonl`：同一段紀錄、同一刻，v3.7 的發現與動作（`new_*`）。只有每一跑的**第一次**檢查是乾淨的比較（新版放行的話，錄到的後續回合不會發生）。
- `r530/`：R530 SOLO 59 格經過真的掛鉤重播（`ops/eval/evidence_20260926_local/v35_given_inline/replay_r530_zero.py`）。
- 每一行只有跑的名字、類別、動作、檔名；**沒有題目內容**（Colab 的 MBPP+／HumanEval+ 是不能散布的題庫，原始紀錄只放在暫存區）。

Colab 原始紀錄：人類的 Drive 資料夾 `vacant_colab_20260927`（公開連結），43 包，每包 sha256 對過 `MANIFEST.tsv`；解開時排除 `auth.json`。
