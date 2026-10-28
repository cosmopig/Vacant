# P0-2 Packet — `*_test.py` 發現、helper 區分、來源隔離

- 日期：2026-10-28（round 131）
- 分支：`auto/qwen27b`（`/home/user1/dev/Vacant`）
- 上游依據：`ops/GPT_REVIEW_20261028.md` P0-2；`ops/STATE.md` §5/§6；
  原始工單（e001 前）：`P0-2: *_test.py discovery 與 source isolation 未完成。`
- 前情：round 130 完成 P0-1（unittest driver），P0-2 被排為 release 前必做。

## 1. 問題（實測，非推測）

`vacant_network/vrun/acceptance.py` 與 `launcher.py`／`gateshim.py` 的測試檔發現
**只認 `test_*.py`**：

| 位置 | 現行 | 後果 |
|---|---|---|
| `acceptance.py:240` `test_files()` | `d.glob("test_*.py")` | 半公開 API 漏掉 `*_test.py` |
| `acceptance.py:758` `run_suite()` | `n.startswith("test_")` | **gate 漏掉 `*_test.py`** |
| `acceptance.py:759` | `no_suite` 訊息只提 `test_*.py` | 誤導使用者 |
| `launcher.py:389` `has_suite` | `glob("test_*.py")` | CLI 層「沒有驗收」判定同錯 |
| `gateshim.py:204` | `cand.glob("test_*.py")` | 自動找 suite 目錄同錯 |
| `launcher.py:956` | help 文字只提 `test_*.py` | 同上 |

而 `/srv/eval/staged/polyglot_py` 的 **34 題全部**用 `*_test.py`
（`ls /srv/eval/staged/polyglot_py/pg_* /workspace/*.py` 逐題核過）。
⇒ 現行 `vacant run --suite <polyglot_py 套件>` 對每一題都是 `no_suite`；
加 `--allow-no-suite` 則**零測試假成功**。這就是 GPT 指出的假成功面。

第二個洞（實測重現，2026-10-28，本 Packet 附實驗）：driver 只把**工作區**
插進 `sys.path`，**套件目錄本身不在 import 路徑上**。`pg_paasio` 的
`paasio_test.py` 有 `from test_utils import MockSock, MockFile, MockException, ZEN, SuperMock`——
照現行代码即使檔名被發現，import 也必然 `ModuleNotFoundError`。
`test_files()` 的 docstring 宣稱「目錄裡允許放 helper 給測試 import」，
**但實測 import 失敗**（`check_ok` → `exception`，`all_pass=false`）。

## 2. 設計裁決（fail-closed 優先，保持 round 51/126 既有 pin）

既有 pin（`tests/test_visible_suite_dialect.py:157`，round 51/126 裁決）：
單獨一個 `test_utils.py`（dialect `none`、沒有 `check_*`/`main`/TestCase）
**必須顯式 `driver_error`，不准靜默跳過**。

P0-2 需求：`pg_paasio` 的 `test_utils.py`（同形：dialect `none`）
**必須不執行**（它是 `paasio_test.py` 的 helper）。

兩者同形、要求相反 ⇒ 唯一能區分的訊號是「**被誰 import**」。裁決：

> **helper 判定（P0-2-1）**：一個符合測試檔命名的檔（`test_*.py` 或
> `*_test.py`），靜態分類 dialect 為 `none`，且**同套件內至少另一個
> 測試檔命名的檔靜態 import 它**（AST `import`/`from … import`，level 0，
> 不執行）⇒ 它是 helper，不執行、記 `role="helper"`。
>
> 否則（`none` 但沒被 import；或任何 `check`/`unittest`/`mixed`）⇒ 照舊
> **執行**：`none` → 顯式 `driver_error`；`mixed` → 顯式 `protocol`。

結果：
- 舊 pin（單獨 `test_utils.py`）→ 仍 `driver_error`（**紅測試保綠**）。
- `pg_paasio` → `test_utils.py` 是 helper、`paasio_test.py` 正常跑。
- 「helper 注入」攻擊（agent 在工作區塞一個同檔名 helper 想讓壞解過）→
  **不可能**：見下條 sys.path 順序。

**來源隔離（P0-2-2）**：driver 的 `sys.path` 順序改為
**套件目錄在前、工作區在後**。bank 的 helper（套件目錄，operator 管）
永遠 shadow 掉工作區同檔名檔案（agent 管）。套件目錄又必須在工作區外
（`launcher.py:293` 既有擋門：「agent 改得到的驗收不是驗收」）＋
沙箱 `ro_binds` 唯讀 ⇒ 來源是凍結的。receipt 的 `suite_sha256`
（全目錄 sha256）把「跑的是哪一份」簽死。

**發現紀錄（P0-2-3）**：`run_suite` 結果新增 `discovery` 欄位（純增量、
進 `files` 旁），每個 `.py` 檔案一筆：
`{name, sha256, role: "test"|"helper", dialect, executed, reason?}`。
34 題每一題都可查「發現了什麼、什麼角色、有沒有跑」。
`result_digest`（簽進收據的欄位集合）**不改**——判準欄位（files/cases/
suite_sha256）已涵蓋；discovery 是稽核欄位，避免動既有收據雜湊形狀
（AGENTS.md：動 canonical 形狀＝全世界鏈斷）。

**命名規則（P0-2-4）**：`test_*.py` **加** `*_test.py`，兩種都收。
`test.py`／`tests.py` 不收（與現行一致，fail-closed）。
`test_files()`、`run_suite()`、`launcher.has_suite`、`gateshim` 自動偵測
全部改走同一個判定函式（單一來源，避免五處字串漂移）。

## 3. 不改變的（回歸紅線）

- `test_*.py` 套件的行為逐字不變（既有 6 個測試檔全綠才算數：
  `test_visible_suite_dialect`、`test_unittest_driver`、`test_unittest_driver_p0_pin`、
  `test_acceptance_completeness`、`test_vacant_run`、`test_vrun_lifecycle`）。
- `no_suite` 的 fail-closed 語意不變：真的沒有測試檔 ⇒ `empty_reason="no_suite"`、
  `all_pass=false`；`--allow-no-suite` 的 `accepted=null` 語意不變。
- dialect 分類、對帳、driver 協定、I-4/I-6 全部不動。

## 4. 驗證矩陣（紅測試先寫，`tests/test_p02_star_test_discovery.py`）

| # | 案例 | 預期 |
|---|---|---|
| A1 | `foo_test.py`（check 方言）＋對解 | 發現、執行、`all_pass=true`、discovery role=test |
| A2 | `foo_test.py`（check 方言，斷言失敗） | 顯式 `assert` 失敗，**不是** `no_suite` |
| A3 | `foo_test.py`（`none` 方言、無 import 來源） | 顯式 `driver_error`（對稱 A 舊 pin） |
| B1 | pg_paasio 形：`paasio_test.py`(unittest, import test_utils)＋`test_utils.py`(none)＋對解 | `all_pass=true`；test_utils 不執行、role=helper |
| B2 | helper 鏈：test 檔→`test_mid.py`(none)→`test_utils.py`(none) | 兩層 helper 都不執行、套件過 |
| B3 | 舊 pin：單獨 `test_utils.py`(none) | 仍 `driver_error`（round 51/126 保綠） |
| C1 | 工作區塞同名 helper（`VAL=99`）想讓壞解過 | **必敗**：套件目錄的 bank helper 先被 import |
| C2 | 對解＋工作區同名 helper | 過（bank helper 為準，shadow 被擋） |
| D1 | discovery 欄位：每個 `.py` 一筆 role/sha256/executed | 逐字可查 |
| D2 | 空套件 | 仍 `no_suite`，reason 同時提兩種命名 |
| E1 | launcher e2e：`*_test.py` 套件＋假 agent（good） | `accepted=true`（現行＝no_suite 假面） |
| E2 | CLI 實機：`vacant run --suite <*_test 目錄> -- <寫解 agent>` | receipt 接受、discovery 落盤 |

## 5. 實測證據（2026-10-28，`.venv` python 3.12，`auto/qwen27b@<pre-commit>`）

1. `ls /srv/eval/staged/polyglot_py/pg_* | grep _test.py` → 34/34 題全有
   `*_test.py`；`test_*.py` 為 0（`pg_paasio` 另有 `test_utils.py` helper）。
2. helper import 實驗（見 §1 第二洞）：`test_a.py` 內 `from helpermod import HELP`
   → `check_ok` `exception`、`all_pass=false`——套件目錄不在 sys.path。
3. `grep -rn "test_\*\.py" vacant_network/` → 六處（§1 表）。

## 6. 邊界（不准誇大）

- 本 Packet 只改**發現與角色判定**，不解決 H-2（過可見≠滿足需求）；
  polyglot_py 的 hidden scorer 仍在格外（`/srv/eval/hidden`，不讀）。
- 「helper 判定靠靜態 import」防的是**無意**與**一般**場景；惡意 operator
  可以把 helper 寫進 test 檔本身——那超出本條（H-6：沙箱非安全邊界）。
- e2e 34 題全量（`vacant run` × 34 × 真 gemma）不在本 commit：
  排 lab 隊列（`03_e002_hypothesis_arms.json` 之後），本輪只做單題實機 e2e＋
  假 agent e2e。
