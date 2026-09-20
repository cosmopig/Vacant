# twinanchor 證據（2026-09-20）

補 `twinstore.py` 誠實邊界 1：「拿得到檔案的人可以整條重算，`verify()` 就會通過」。
這一批是「那個弱點現在有東西擋著」的落盤證據。

## 檔案

| 檔 | 是什麼 | 怎麼重跑 |
|---|---|---|
| `selftest.txt` | `twinanchor.py selftest` 的 20 條判準（含 6 個負控制） | `python3 ops/exhibit/twin/twinanchor.py selftest` |
| `negctl_on_the_selftest.txt` | **對 selftest 本身的負控制**——證明那 20 個綠燈量得動 | `python3 ops/exhibit/twin/negctl_anchor_selftest.py` |
| `e2e_anchor_run.txt` | 端到端 20 條（離線；出口①③④） | `PY=.venv/bin/python bash ops/exhibit/twin/e2e_anchor.sh` |
| `live_1003_mirror.txt` | **出口②活體**：真的 scp 到 1003 再抓回來當 pin | 見下 |
| `pytest.txt` | `tests/test_twinanchor.py` 41 條 | `.venv/bin/python -m pytest tests/test_twinanchor.py -q` |
| `pytest_negctl.txt` | **對測試的負控制**：三個蓄意破壞各自紅在哪 | 見下 |

## 出口②活體那一跑（`live_1003_mirror.txt`）

在 Mac 上跑，對手是 **1003 ＝ `w401@100.119.113.56`**（Windows）。

- `ssh` 那一側用 `/c/Users/w401/...`、`scp` 那一側用 `C:/Users/w401/...`
  （MSYS 只轉換裸參數，這個坑造成過一次假綠）。
- 兩台的 `anchors.jsonl` sha256 逐字相同：
  `9dcc710f828f4e1e05c03bb24ddcec3d2a5aca6efd528daea4a2eab58f2596c4`
- 然後把 1003 上那份 `anchor_pub.txt` 抓回來當 `--pin-file`，
  對**被整條重算過**的 store 重驗 ⇒ 退出碼 1（紅）。
- 那一跑用完的遠端目錄 `C:/Users/w401/twinanchor_test/` 已經刪掉。

## 對測試的負控制（`pytest_negctl.txt`）

三個蓄意破壞，各自紅在不同的地方——**這證明七道關不是同一道關重複七次**：

| 破壞 | 紅的測試 |
|---|---|
| `verify_checkpoint` 永遠回 True | `test_full_rewrite_is_caught_by_anchor`、`test_full_rewrite_without_dropping_anything_is_still_caught` |
| 公鑰比對永遠 match | `test_resign_with_stolen_key_IS_caught_with_an_offmachine_pin`、`test_mirrored_pin_actually_catches_a_resign` |
| `no_rollback` 永遠 ok | `test_truncation_is_caught_by_anchor` |

## 🔴 這批證據**不**證明什麼

1. **不證明「竄改不可能」。** 錨定讓「截斷與整條重算」被偵測到，
   **擋不住拿到金鑰的人重新簽一條**——那一種在
   `test_resign_with_stolen_key_is_NOT_caught_without_a_pin` 裡是**綠的**，
   刻意的，那條測試在釘誠實邊界不是在釘功能。
2. **不證明沒漏收。** `twinstore.py` 誠實邊界 3 原封不動。
3. **不證明可用性。** `rm -rf store/` 之後這一支什麼都說不出來。
