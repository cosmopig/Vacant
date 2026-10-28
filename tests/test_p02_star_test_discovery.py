"""P0-2：`*_test.py` 發現、helper 角色、來源隔離——實作前寫的紅測試。

設計：`ops/packets/p02_testpy_discovery.md`（同 `ops/vlab/packets/`）
上游：`ops/GPT_REVIEW_20261028.md` P0-2；原始工單（e001 前）「`*_test.py`
discovery 與 source isolation 未完成」。

裁決（Packet §2，fail-closed 優先）：
  · 測試檔命名 ＝ `test_*.py` **加** `*_test.py`（兩種都收；`test.py` 不收）。
  · helper 判定：符合命名的檔、靜態 dialect `none`、且被同套件另一個
    測試檔命名的檔靜態 import ⇒ 不執行（role="helper"）。
  · 否則照舊執行：`none` ⇒ 顯式 `driver_error`（round 51/126 C 段 pin 不動：
    單獨一個 `test_utils.py` 仍是 driver_error，見
    `tests/test_visible_suite_dialect.py::test_helper_named_test_file_is_discovered_and_explicitly_rejected`）。
  · 來源隔離：driver 的 sys.path **套件目錄在前、工作區在後**——bank 的
    helper 永遠勝過工作區同檔名檔案（helper 注入攻擊擋死）。
  · 結果多一個純增量 `discovery` 欄位：每個 .py 一筆
    {name, sha256, role, dialect, executed, reason?}；`result_digest` 不改
    （動簽進收據的欄位集合＝全世界既有收據雜湊形狀變，AGENTS.md 紅線）。

零模型呼叫：agent 是 `python3 -c pass`（工作區預先放好候選解）。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacant_network.vrun import acceptance, launcher          # noqa: E402
from vacant_network.vrun.sandbox import make_sandbox          # noqa: E402

UNITTEST_FILE = '''\
import unittest


class WordyTest(unittest.TestCase):
    def test_says_wordy(self):
        from solution import greeting
        self.assertEqual(greeting(), "wordy")
'''

GOOD = "def greeting():\n    return 'wordy'\n"
BAD = "def greeting():\n    return 'brief'\n"


def _setup(tmp_path: Path, files: dict[str, str], solution: str = GOOD,
           extra_ws: dict[str, str] | None = None,
           suite_name: str = "suite", ws_name: str = "ws") -> Path:
    ws = tmp_path / ws_name
    ws.mkdir()
    (ws / "solution.py").write_text(solution, encoding="utf-8")
    for name, body in (extra_ws or {}).items():
        (ws / name).write_text(body, encoding="utf-8")
    sd = tmp_path / suite_name
    sd.mkdir()
    for name, body in files.items():
        (sd / name).write_text(body, encoding="utf-8")
    return sd


def _run(tmp_path: Path, sd: Path, sandbox_name: str = "none") -> dict:
    sb, _meta = make_sandbox(sandbox_name, workdir=tmp_path / f"sb_{sd.name}")
    return acceptance.run_suite(sb, tmp_path / "ws", sd, suite="visible",
                                task_id="p02", verify_root=tmp_path / "verify")


def _disc(res: dict) -> dict[str, dict]:
    return {d["name"]: d for d in res["discovery"]}


# ── A：`*_test.py` 發現與執行 ────────────────────────────────────────────
def test_star_test_py_is_discovered_and_executed(tmp_path: Path):
    """[A1] 34 題 polyglot_py 的真實形狀：對的實現要過。"""
    sd = _setup(tmp_path, {"wordy_test.py": UNITTEST_FILE})
    res = _run(tmp_path, sd)
    f = res["files"][0]
    assert f["file"] == "wordy_test.py"
    assert f["cases"][0]["kind"] == "pass"
    assert res["all_pass"] is True
    assert _disc(res)["wordy_test.py"]["role"] == "test"


def test_star_test_py_failure_is_explicit_assert(tmp_path: Path):
    """[A2] 錯的實現要紅在 assert——不是 `no_suite`、不是假成功。"""
    sd = _setup(tmp_path, {"wordy_test.py": UNITTEST_FILE}, solution=BAD)
    res = _run(tmp_path, sd)
    assert res["empty_reason"] is None
    assert res["files"][0]["cases"][0]["kind"] == "assert"
    assert res["all_pass"] is False


def test_star_test_none_dialect_is_explicitly_rejected(tmp_path: Path):
    """[A3] `*_test.py` 但 dialect `none`（無測試訊號、也無 import 來源）
    ⇒ 照 round 51/126 的紀律：顯式 `driver_error`，絕不靜默跳過。"""
    sd = _setup(tmp_path, {"wordy_test.py": "def helper():\n    return 1\n"})
    res = _run(tmp_path, sd)
    assert res["files"][0]["cases"][0]["kind"] == "driver_error"
    assert res["all_pass"] is False


def test_star_test_is_collected_by_test_files(tmp_path: Path):
    """[A4] 半公開 API `test_files()` 兩種命名都收、決定性排序。"""
    sd = _setup(tmp_path, {"b_z_test.py": "x=1\n", "test_a.py": "x=1\n",
                           "test_utils.py": "x=1\n", "test.py": "x=1\n"})
    names = [p.name for p in acceptance.test_files(sd)]
    assert names == ["b_z_test.py", "test_a.py", "test_utils.py"]   # test.py 不收


# ── B：helper 角色（pg_paasio 形狀） ─────────────────────────────────────
UTILS = "class MockFile:\n    def read(self):\n        return 'x'\n"
PAASIO = (
    "import unittest\n"
    "from test_utils import MockFile\n"
    "\n"
    "class PaasioTest(unittest.TestCase):\n"
    "    def test_reads(self):\n"
    "        from solution import greeting\n"
    "        self.assertEqual(greeting(), 'wordy')\n"
)


def test_helper_imported_by_test_file_is_not_executed(tmp_path: Path):
    """[B1] pg_paasio 真實形狀：`paasio_test.py`（unittest，import
    `test_utils`）＋`test_utils.py`（dialect none）。
    helper 不執行、套件照樣過——且 `from test_utils import …` 要解析得到
    （套件目錄必須在 import 路徑上，今天必然 ModuleNotFoundError）。"""
    sd = _setup(tmp_path, {"paasio_test.py": PAASIO, "test_utils.py": UTILS})
    res = _run(tmp_path, sd)
    assert [f["file"] for f in res["files"]] == ["paasio_test.py"]
    assert res["all_pass"] is True
    d = _disc(res)
    assert d["paasio_test.py"]["role"] == "test" and d["paasio_test.py"]["executed"] is True
    assert d["test_utils.py"]["role"] == "helper"
    assert d["test_utils.py"]["executed"] is False
    assert d["test_utils.py"]["dialect"] == "none"
    assert d["test_utils.py"].get("imported_by") == ["paasio_test.py"]


def test_helper_import_chain_both_helpers_not_executed(tmp_path: Path):
    """[B2] 兩層 helper 鏈：test→test_mid(none)→test_utils(none)。
    兩層都不執行；最底層的 test_utils 因為被 test_mid import 也是 helper。"""
    files = {
        "paasio_test.py": PAASIO.replace("from test_utils import MockFile",
                                         "from test_mid import go"),
        "test_mid.py": "from test_utils import MockFile\n"
                       "def go():\n    return MockFile\n",
        "test_utils.py": UTILS,
    }
    sd = _setup(tmp_path, files)
    res = _run(tmp_path, sd)
    assert [f["file"] for f in res["files"]] == ["paasio_test.py"]
    assert res["all_pass"] is True
    d = _disc(res)
    assert d["test_mid.py"]["role"] == "helper" and d["test_mid.py"]["executed"] is False
    assert d["test_utils.py"]["role"] == "helper" and d["test_utils.py"]["executed"] is False


# ── C：來源隔離——helper 注入擋死 ────────────────────────────────────────
ISOLATED_TEST = (
    "from helpermod import VAL\n"
    "\n"
    "def check_val():\n"
    "    from solution import value\n"
    "    assert value() == VAL\n"
)


def test_workspace_shadow_helper_cannot_flip_verdict(tmp_path: Path):
    """[C1] 壞解＋工作區塞同檔名 helper（VAL=99）想讓壞解過。
    bank 的 helper（VAL=1，套件目錄）必須先被 import ⇒ 99==1 必敗。"""
    sd = _setup(tmp_path, {"wordy_test.py": ISOLATED_TEST, "helpermod.py": "VAL = 1\n"},
                solution="def value():\n    return 99\n",
                extra_ws={"helpermod.py": "VAL = 99\n"})
    res = _run(tmp_path, sd)
    f = res["files"][0]
    assert f["cases"][0]["kind"] == "assert"        # 紅在 assert，不是 import 雜訊
    assert res["all_pass"] is False


def test_correct_solution_passes_despite_workspace_shadow(tmp_path: Path):
    """[C2] 對的解＋工作區同檔名 helper（VAL=99）。
    套件目錄優先 ⇒ VAL 取 bank 的 1 ⇒ 1==1 過。
    （反過來 pin sys.path 順序：工作區在前則 1==99 必敗。）"""
    sd = _setup(tmp_path, {"wordy_test.py": ISOLATED_TEST, "helpermod.py": "VAL = 1\n"},
                solution="def value():\n    return 1\n",
                extra_ws={"helpermod.py": "VAL = 99\n"})
    res = _run(tmp_path, sd)
    assert res["files"][0]["cases"][0]["kind"] == "pass"
    assert res["all_pass"] is True


# ── D：發現紀錄可逐題稽核 ────────────────────────────────────────────────
def test_discovery_records_every_py_file(tmp_path: Path):
    """[D1] discovery 欄位：每個 .py 一筆、sha256 可重算、role/executed 對齊。"""
    files = {"paasio_test.py": PAASIO, "test_utils.py": UTILS,
             "notes.py": "X = 0\n"}
    sd = _setup(tmp_path, files)
    res = _run(tmp_path, sd)
    d = _disc(res)
    assert set(d) == set(files)
    for name, body in files.items():
        assert d[name]["sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert d["paasio_test.py"]["role"] == "test" and d["paasio_test.py"]["executed"] is True
    assert d["test_utils.py"]["role"] == "helper" and d["test_utils.py"]["executed"] is False
    assert d["notes.py"]["role"] == "helper" and d["notes.py"]["executed"] is False


def test_empty_suite_is_no_suite_naming_both_patterns(tmp_path: Path):
    """[D2] 真的沒有測試檔 ⇒ `all_pass` 必為 False（fail-closed）；
    `empty_reason` 兩種命名都提（舊版只提 `test_*.py`）。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "solution.py").write_text(GOOD, encoding="utf-8")
    sd = tmp_path / "empty"
    sd.mkdir()
    sb, _meta = make_sandbox("none", workdir=tmp_path / "sb_empty")
    res = acceptance.run_suite(sb, ws, sd, suite="visible", task_id="p02",
                               verify_root=tmp_path / "verify")
    assert res["all_pass"] is False
    assert res["empty_reason"], "empty_reason 必須存在（fail-closed）"
    assert "test_*.py" in res["empty_reason"]
    assert "*_test.py" in res["empty_reason"]


# ── E：launcher 層 e2e（假 agent） ───────────────────────────────────────
def test_launcher_accepts_star_test_suite(tmp_path: Path):
    """[E1] `*_test.py` 套件＋工作區已有對解 ⇒ `visible_pass`、accepted=True。
    現行（只認 test_*）＝ no_suite 假面——本測試今天紅。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "solution.py").write_text(GOOD, encoding="utf-8")
    sd = tmp_path / "suite"
    sd.mkdir()
    (sd / "wordy_test.py").write_text(UNITTEST_FILE, encoding="utf-8")
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run_p02", suite_dir=sd, vacant_on=True,
                     task_id="p02", sandbox_name="none")
    assert s["stop_reason"] == "visible_pass"
    assert s["accepted"] is True


def test_launcher_refuses_star_test_wrong_impl(tmp_path: Path):
    """[E2] 錯解 ⇒ `visible_fail`、refused——發現之後的負對照（不能只測假成功）。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "solution.py").write_text(BAD, encoding="utf-8")
    sd = tmp_path / "suite"
    sd.mkdir()
    (sd / "wordy_test.py").write_text(UNITTEST_FILE, encoding="utf-8")
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run_p02b", suite_dir=sd, vacant_on=True,
                     task_id="p02", sandbox_name="none")
    assert s["stop_reason"] == "visible_fail"
    assert s["accepted"] is False and s["refused"] is True
