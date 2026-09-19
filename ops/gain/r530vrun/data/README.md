# r530vrun 落盤證據（2026-09-19）

⚠ **非預註冊。** 判讀紀律見上一層的 `README.md` 最上面那一節：
**不准做統計檢定、不准與 R535／R530 原始結果合併、不准寫「複製」「效果消失」
「等價」。** 能說的只有「在這 20 題上、用 pi，X 是 a/b」。

| 檔 | 是什麼 | 怎麼重算 |
|---|---|---|
| `timeout_probe.json` | `--test-timeout` 的量測，n=200 個單檔觀測（參考解 80 ＋ 已知壞樁 120） | `probe_timeout.py --out <dir> --parallel 2 --include-bad` |
| `manifest.json` | 這一跑的凍結參數：題庫 sha256、20 題的 `--suite` sha256、prompt、模型、推論模式、`test_timeout_source` | `run_r530vrun.py` 首次啟動時寫，之後不覆寫 |
| `cells.jsonl` | **40 格的逐格原始列**（每格一列） | 發射時逐格 append |
| `report_20260919T140446Z.md` | 機器產的收官表（逐格／逐臂／M7 三層／牆鐘分佈／紀律欄位） | `score_r530vrun.py --out <run 目錄>` |
| `receipts_verify.json` | 收據鏈驗證：40 鏈 / 108 entries / 0 失敗 / 總判 OK | `python3 -m vacant_network.vrun.verify_receipts --glob '<run>/cells/*/run'` |

**沒有進 repo 的**：`scores_*.json`（515 KB，含每格 wire 分類的原始清單）與
每格的 `ws/`／`run/`（wire 逐通全文、凍結快照、收據鏈）。
它們留在 vacant-dev 的 `/var/tmp/vacant_r530vrun/run/`。
⚠ **那台沒有備份**——要引用逐通 wire 就要先把它搬出來。

## 兩個先讀的提醒

1. **`report_*.md` 是機器產的，`../RESULTS.md` 是人寫的摘要。** 衝突時以前者為準。
2. **`cells.jsonl` 裡 `cell_status != "measured"` 的列不是失敗格**（鐵律 3）。
   本批 `infra_void` ＝ 0，但讀的人不該依賴這件事——要看欄位。
