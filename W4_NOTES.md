# W4 — 乾淨環境新手體驗（rc2，0.9.2rc2）

做法：`pipx install vacant_network-0.9.2rc2-py3-none-any.whl` 到隔離的 PIPX_HOME，HOME 換成空目錄、
PATH 只留 pipx bin＋系統＋node，不設 VIRTUAL_ENV／PYTHONPATH。腳本：`~/dev/ops/w4_run.sh`，
完整紀錄：`~/dev/ops/w4_transcript_rc2.txt`。agent 用腳本假 agent（`--cmd`），不打模型。

| 專案 | 結果 |
|---|---|
| unittest | 基線 FAIL 0/1 → 第 1 次 PASS 1/1，寫回 calc.py |
| pytest 風格、沒有 venv（系統 python 無 pytest） | 走 python_bare（stdlib runner），PASS |
| pytest、專案自己的 .venv 有 pytest | 用 `.venv/bin/python -m pytest`，PASS |
| npm（`node calc.test.js`） | 基線 FAIL → PASS；package.json、calc.test.js 列為受保護 |
| 沒有測試 | 跑一次、明講什麼都沒檢查 |
| `vacant do pi`，pi 不在 PATH | 開跑前就說找不到 pi，exit 43，專案不動（rc2 修） |
| pi 在但一啟動就崩潰（舊 node） | 第 1 次就停、印出 agent 的錯誤，exit 43（rc2 修；之前靜靜燒 3 次） |
| `vacant --version` | `vacant 0.9.2rc2`（rc2 補） |
| `vacant audit list` | 每次執行一筆、verified yes |

還沒做：真模型（pi＋本機 gemma）的 W4 實跑——兩台 GPU 都在跑確認批，插隊會污染那兩批，等 Colab 或批次空檔。
