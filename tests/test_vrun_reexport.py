"""搬家契約的擋門：**一份判準、兩個 import 路徑、進得了 wheel。**

2026-09-18 把 `vacant run`／`vacant demo gate` 的判斷層從 `ops/gain/r530/` 與
`ops/vacantrun/` 搬進 `vacant_network/vrun/`，理由是 `ops/` 不進 wheel ⇒
`pip install vacant-network` 的人跑不了第一屏。搬家會壞三種東西，這一批各對一條：

  · `test_old_import_paths_are_the_same_module_object`
      R530／R531／R534 的既有引用（83 處）不准壞，而且**不准變成第二份**。
      判準是 `is`：同一個 module 物件，不是「內容看起來一樣」。
  · `test_envmap_has_exactly_one_home`
      `envmap` 是一份名單，漏一格不會有錯誤訊息 ⇒ 舊位置刻意**不留** re-export，
      免得未來有人改到一個不再被讀的檔案。
  · `test_vrun_is_self_contained`
      套件裡的碼不准 import `ops.*`——那會讓 wheel 裝起來但一跑就 ImportError。
      這是「wheel 裝得到」這句話的可執行版本（比 `pip install` 早一步抓到）。
  · `test_pyproject_ships_vrun`／`test_pyproject_ships_every_subpackage`
      漏了 `packages` 這一行，wheel 就少一整包，而且**不會有任何錯誤訊息**
      ——安裝成功、跑起來才炸。前者釘死 `vacant_network.vrun` 這一格（它是本次搬家的主體），
      後者是**下一次**的擋門：`packages` 是手寫名單（刻意的，見 pyproject 的註解），
      而手寫名單的失敗方式就是「下一個子套件沒人記得加」。
  · `test_the_ruler_is_still_runnable_at_its_old_path`
      `ops/gain/replay/verify_run_receipts.py` 是 repo 裡到處被引用的那把尺
      （README×3、AGENTS.md、裁決檔、佇列腳本）。它必須**還是那個路徑、
      還是直接跑得動**，而且負控制（抓得到壞鏈）要過。
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import vacant_network.vrun.acceptance          # noqa: E402
import vacant_network.vrun.demo                # noqa: E402
import vacant_network.vrun.launcher            # noqa: E402
import vacant_network.vrun.receipts            # noqa: E402
import vacant_network.vrun.retry               # noqa: E402
import vacant_network.vrun.sandbox             # noqa: E402
import vacant_network.vrun.verify_receipts     # noqa: E402
import vacant_network.vrun.wireproxy           # noqa: E402
import vacant_network.vrun.wshash              # noqa: E402

#: 舊路徑 → 新模組。**這張表就是搬家契約**；少一列＝那條舊引用沒人守。
PAIRS = {
    "ops.gain.r530.acceptance": vacant_network.vrun.acceptance,
    "ops.gain.r530.receipts": vacant_network.vrun.receipts,
    "ops.gain.r530.wshash": vacant_network.vrun.wshash,
    "ops.gain.r530.sandbox": vacant_network.vrun.sandbox,
    "ops.gain.replay.verify_run_receipts": vacant_network.vrun.verify_receipts,
    "ops.vacantrun.launcher": vacant_network.vrun.launcher,
    "ops.vacantrun.wireproxy": vacant_network.vrun.wireproxy,
    "ops.vacantrun.demo": vacant_network.vrun.demo,
    # V1／V2 的政策層。`launcher` 直接 `from . import retry` ⇒ 它**必須**住在套件裡，
    # 否則 `test_vrun_is_self_contained` 會紅（而那條紅的真正意思是 wheel 裝起來會炸）。
    # 舊路徑留 re-export 是因為 `tests/test_vacant_run_retry.py` 從那裡 import。
    "ops.vacantrun.retry": vacant_network.vrun.retry,
}


def test_old_import_paths_are_the_same_module_object():
    import importlib

    for old, new in PAIRS.items():
        got = importlib.import_module(old)
        assert got is new, f"{old} 不是 {new.__name__} 本人——那就是第二份"
        # `from <pkg> import <name>` 這條路（import 系統會把 submodule 掛回父套件）
        pkg, _, name = old.rpartition(".")
        parent = importlib.import_module(pkg)
        assert getattr(parent, name) is new, f"from {pkg} import {name} 拿到別的東西"


def test_envmap_has_exactly_one_home():
    """`envmap` 是**一份名單**，而名單漏一格不會有錯誤訊息 ⇒ 只准有一個家。

    所以它刻意**沒有** re-export：`ops/vacantrun/envmap.py` 已經不存在。
    放一個看起來也是名單的檔案在舊位置，就是給未來的人一個改錯地方的機會。
    """
    assert not (ROOT / "ops" / "vacantrun" / "envmap.py").exists()
    assert (ROOT / "vacant_network" / "vrun" / "envmap.py").is_file()


#: **具名例外**：唯一准在套件裡提到 `ops.*` 的地方，理由寫在它自己的 docstring
#: ——它走 `importlib` 而且抓不到時丟 `OpsRunnerUnavailable`（一句話說得清楚的錯），
#: 不是一個裸的 `ModuleNotFoundError`。CHANGELOG 0.7.0「兩個只在呼叫時才咬人的缺陷」
#: 就是為這條寫的。**新增例外要在這裡具名，不准靜靜跳過。**
OPS_LAZY_ALLOWED = {"vacant_network/suitegauge.py"}


def test_vrun_is_self_contained():
    """套件裡的碼不准依賴 `ops.*`——wheel 裡根本沒有 `ops`。

    兩種寫法都掃：靜態 `import` 與 `importlib.import_module("ops…")` 的字面值。
    只掃靜態那一種的話，把 import 藏進 `importlib` 就能繞過這條擋門，
    而繞過的後果正是 0.7.0 修過的那個形狀：**裝得起來、一呼叫才炸**。
    """
    offenders: list[str] = []
    for py in sorted((ROOT / "vacant_network").rglob("*.py")):
        rel = str(py.relative_to(ROOT))
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif (isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "import_module"):
                names = [a.value for a in node.args
                         if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                if rel in OPS_LAZY_ALLOWED:
                    continue
            for n in names:
                if n == "ops" or n.startswith("ops."):
                    offenders.append(f"{rel}:{node.lineno} → {n}")
    assert not offenders, "套件裡不准依賴 ops/：\n  " + "\n  ".join(offenders)


def test_pyproject_ships_vrun():
    txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"vacant_network.vrun"' in txt, "pyproject 的 packages 少了 vacant_network.vrun ⇒ wheel 會少一整包"
    # 反面：頂層 `ops` 不准進 wheel（PyPI 上 `ops` 是 Juju 的套件，會撞名）
    assert '"ops"' not in txt and "'ops'" not in txt


def test_pyproject_ships_every_subpackage():
    """`vacant_network/` 底下每一個可 import 的子套件都必須列進 `packages`。

    這支在架構裡承重什麼：`[tool.setuptools] packages` 是**手寫名單**（刻意的：
    pyproject 的註解寫了為什麼不用 find——頂層 `ops` 不准被自動掃進去）。手寫名單
    只有一種失敗方式，而它很安靜：下一個子套件沒人記得加 ⇒ wheel 少一整包 ⇒
    `pip install` 成功、`import` 成功、**呼叫到那一包才炸**。0.7.0 已經被這個形狀
    咬過一次（`vacant_network.suitegauge` 的 `import ops.gain.gain_run`）。

    反向也查：名單裡寫了但磁碟上不存在的項目（改名／刪除之後沒同步）——setuptools
    對那種項目**不會報錯**，它只是什麼都不打包。
    """
    import tomllib

    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    listed = set(cfg["tool"]["setuptools"]["packages"])

    found = set()
    for init in (ROOT / "vacant_network").rglob("__init__.py"):
        if "__pycache__" in init.parts:
            continue
        found.add(".".join(init.parent.relative_to(ROOT).parts))
    missing = sorted(found - listed)
    assert not missing, (
        "這些子套件不在 pyproject 的 packages 裡，wheel 會少掉它們（且沒有錯誤訊息）："
        + ", ".join(missing))

    ghosts = sorted(p for p in listed
                    if not (ROOT / pathlib.Path(*p.split("."))).is_dir())
    assert not ghosts, f"packages 列了磁碟上不存在的目錄：{', '.join(ghosts)}"


def test_the_ruler_is_still_runnable_at_its_old_path():
    ruler = ROOT / "ops" / "gain" / "replay" / "verify_run_receipts.py"
    assert ruler.is_file()
    out = subprocess.run([sys.executable, str(ruler), "--selftest"],
                         capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert "PASS" in out.stdout, out.stdout[-2000:]


def test_the_ruler_is_runnable_as_a_module_too():
    """`pip install` 之後唯一跑得動的那一行（demo 畫面上印的就是它）。"""
    out = subprocess.run(
        [sys.executable, "-m", "vacant_network.vrun.verify_receipts", "--selftest"],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert "PASS" in out.stdout


def test_the_doc_line_numbers_still_point_at_the_all_pass_line():
    """README×3 與 AGENTS.md 用**絕對行號**指著「量不到不是通過」那一行。

    搬家把那一行的行號從 `ops/gain/r530/acceptance.py:272` 變成
    `vacant_network/vrun/acceptance.py:268`。絕對行號的失敗方式是**安靜地指到別行**
    ——讀的人會以為看到的是判準，其實是旁邊那一行。所以把它變成可執行的：
    文件裡寫幾就去讀第幾行，內容不對就紅。
    """
    import re

    src = (ROOT / "vacant_network" / "vrun" / "acceptance.py").read_text(
        encoding="utf-8").splitlines()
    pat = re.compile(r"vacant_network/vrun/acceptance\.py:(\d+)")
    seen = 0
    for doc in ("README.md", "README.en.md", "README.ja.md", "AGENTS.md"):
        txt = (ROOT / doc).read_text(encoding="utf-8")
        for m in pat.finditer(txt):
            n = int(m.group(1))
            seen += 1
            assert "all_pass" in src[n - 1], (
                f"{doc} 指著 acceptance.py:{n}，但那一行是 {src[n - 1]!r}")
    assert seen >= 7, f"只找到 {seen} 處行號引用——文件被改過就該同步這個下界"
