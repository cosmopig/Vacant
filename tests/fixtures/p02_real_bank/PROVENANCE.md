# P0-2 real-bank `*_test.py` fixtures — provenance

GPT 審查 P0-2 的最強證據（2026-10-28，round 155）：**真實任務庫的 `*_test.py`
檔案**，不是合成檔。

| file | sha256 | source |
|---|---|---|
| `bowling_test.py` | `6b9a80b6835828f575ce0aba66876850f75c59f764014ac509fe1df7e3a9ee20` | **bank 原始檔**（visible test，非 scorer 隱藏檔）。取自 e001 A 臂 cell `polyglot_py-pg_bowling-pi-A-r1/app_final.tgz` 的 `app/bowling_test.py`；與 C 臂 cell `polyglot_py-pg_bowling-pi-C-r1` 的同一檔案**逐位元相同**（同一任務、同一份 visible test ⇒ 真 bank 檔的證據）。31 個 case，`class BowlingTest(unittest.TestCase)`，import `from bowling import BowlingGame`。 |
| `bowling_bad.py` | `fd5dcbe9782103f939271b140c0c4ad91f631844e23c89a4bf612d86643c8dd7` | **真實 agent 產出的負控**：e001 A 臂 `polyglot_py-pg_bowling-pi-A-r1` 的 `app/bowling.py`，該 cell 的 `score.json` 記 `pass=false, tests_passed=15/31`（bad=16）。逐位元未改。 |
| `bowling_good.py` | `9e92c89c7d0162f98a1b2933848bb66e7fb1b2d61edc6c427e03572c8690da38` | **本地寫的正控**（非 agent 輸出）：e001 兩臂候選都 fail（A 15/31、C 26/31），沒有「真實且正確」的候選可用，故依 `bowling_test.py` 的 API（`BowlingGame.roll/score`，31 case 全數通過）本地實作。`DECISION: 正控用本地正確解｜負控保留真實失敗候選，因為 bank 只給 test 檔不給答案。` |

## 為何這組檔案能封 P0-2

1. `bowling_test.py` 的名字是 **`*_test.py`**（exactly the shape the GPT 審查
   懷疑「沒有跑過」的那種），dialect = `unittest`（`class ... (unittest.TestCase)`）。
2. 31 個 case，覆蓋 score 計算與**所有 raise 路徑**（負分、>10 分、frame 超 10、
   10th-frame bonus 規則、incomplete game、roll-after-complete）。
3. 負控 `bowling_bad.py` 是**真實 agent 在真實 run 裡失敗過的程式**，不是為
   測試而造的 stub。
4. 兩臂 `bowling_test.py` 逐位元相同 ⇒ 這**是**任務庫檔（bank file），不是某
   agent 自己寫的 test。

## 邊界（誠實欄）

- `score.json` 的 15/31、26/31 是 **scorer（隱藏端）** 的計分；本 repo 的
  acceptance driver 在 visible `bowling_test.py` 上對 `bowling_bad.py` 的計數
  可能不同（visible ≠ hidden 的題）。兩者在 `tests/test_p02_real_bank_cli_e2e.py`
  裡分開記錄，不混用。
- `/srv/eval/staged/`（34 題 bank 原件）本機無權讀取（`Permission denied`，
  2026-10-28 重驗）。本 fixture 是 e001 run 留存的**同一份 visible test**，
  非 staged 原件；「staged 原件本身跑過」仍為 **UNKNOWN**，只能由有權者跑。
- 本 fixture 不含任何 scorer 隱藏檔；只含 visible test 與 agent 產物。
