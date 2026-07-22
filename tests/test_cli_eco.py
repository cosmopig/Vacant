"""生態子命令的 CLI 測試（12 §5）：toggle/status/scoreboard/verify/ledger tail/resident。

策略：直接呼叫 cli.main(argv)（不走 subprocess，快且可捕 stdout），用假腦與 tmp root。
先手動建一個 Ecosystem 並 delegate 一筆製造資料（logbook/ledger/scoreboard 都有內容）。
不測 `up` 的 serve_forever——只確認 `up --help` 與各子命令 --help 不炸。
"""

from __future__ import annotations

import json

import pytest

from vacant import cli
from vacant.ecosystem import Ecosystem


class FakeBrain:
    name = "fake"

    def generate(self, p: str) -> str:
        return "```python\ndef solve(s):\n    return s[::-1]\n```"


def _seed(root):
    """手動建生態並 delegate 一筆（trust on）製造 logbook/ledger/scoreboard 資料。"""
    eco = Ecosystem(root, FakeBrain())
    eco.toggle(True)
    res = eco.delegate("reverse the string", {"type": "run_python",
                                              "code": "assert solve('abc') == 'cba'"})
    return eco, res


def _run(capsys, argv):
    rc = cli.main(argv)
    out = capsys.readouterr()
    return rc, out.out, out.err


def test_toggle_writes_state(tmp_path, capsys):
    root = tmp_path / "eco"
    rc, out, _ = _run(capsys, ["toggle", "off", "--root", str(root)])
    assert rc == 0
    assert json.loads((root / "state.json").read_text()) == {"trust_on": False}
    assert "off" in out
    rc, out, _ = _run(capsys, ["toggle", "on", "--root", str(root)])
    assert rc == 0
    assert json.loads((root / "state.json").read_text()) == {"trust_on": True}


def test_status(tmp_path, capsys, monkeypatch):
    root = tmp_path / "eco"
    _seed(root)
    monkeypatch.delenv("VACANT_MCP_MODEL", raising=False)
    monkeypatch.delenv("VACANT_MCP_BASE", raising=False)
    rc, out, err = _run(capsys, ["status", "--root", str(root)])
    assert rc == 0
    assert "trust" in out
    # 6 預設居民都該出現在名冊表格
    for name in ("good_1", "saboteur_1", "mediocre_1"):
        assert name in out
    # 離線假腦誠實印出
    assert "offline brain" in err


def test_scoreboard(tmp_path, capsys):
    root = tmp_path / "eco"
    _seed(root)  # 一筆 trust-on 試次
    rc, out, _ = _run(capsys, ["scoreboard", "--root", str(root)])
    assert rc == 0
    assert "trust on" in out
    assert "trust off" in out
    assert "paired_delta" in out


def test_verify(tmp_path, capsys):
    root = tmp_path / "eco"
    eco, res = _seed(root)
    # 找出實際交付者（logbook 有 DELIVER 事件）——用 roster 挑 deliveries>0 的
    deliverer = next(e["name"] for e in eco.roster() if e["deliveries"] > 0)
    rc, out, _ = _run(capsys, ["verify", deliverer, "--root", str(root)])
    assert rc == 0
    assert "PASS" in out


def test_verify_unknown_resident(tmp_path, capsys):
    root = tmp_path / "eco"
    _seed(root)
    rc, out, err = _run(capsys, ["verify", "nobody", "--root", str(root)])
    assert rc == 1
    assert "找不到" in err


def test_ledger_tail(tmp_path, capsys):
    root = tmp_path / "eco"
    _seed(root)  # delegate 會寫 ROUTE/REVIEW/AUDIT/DELIVERED... 進 ledger
    rc, out, _ = _run(capsys, ["ledger", "tail", "-n", "5", "--root", str(root)])
    assert rc == 0
    assert "DELIVERED" in out or "ROUTE" in out
    # 只印最後 5 行
    printed = [ln for ln in out.splitlines() if ln.strip().startswith("[")]
    assert 0 < len(printed) <= 5


def test_ledger_tail_empty(tmp_path, capsys):
    root = tmp_path / "eco"
    Ecosystem(root, FakeBrain())  # 建生態但不 delegate → ledger 不存在
    rc, out, _ = _run(capsys, ["ledger", "tail", "--root", str(root)])
    assert rc == 0
    assert "空" in out


def test_resident_inspect(tmp_path, capsys):
    root = tmp_path / "eco"
    eco, _ = _seed(root)
    deliverer = next(e["name"] for e in eco.roster() if e["deliveries"] > 0)
    rc, out, _ = _run(capsys, ["resident", "inspect", deliverer, "--root", str(root)])
    assert rc == 0
    assert deliverer in out
    assert "episode" in out


def test_resident_wipe(tmp_path, capsys):
    root = tmp_path / "eco"
    eco, _ = _seed(root)
    deliverer = next(e["name"] for e in eco.roster() if e["deliveries"] > 0)
    rc, out, _ = _run(capsys, ["resident", "wipe", deliverer, "--root", str(root)])
    assert rc == 0
    assert deliverer in out
    # wipe 後重建生態，該居民交付計數歸零、episode 清空
    eco2 = Ecosystem(root, FakeBrain())
    entry = next(e for e in eco2.roster() if e["name"] == deliverer)
    assert entry["deliveries"] == 0
    assert entry["episodes"] == 0


def test_lmstudio_brain_from_env(tmp_path, monkeypatch):
    """兩個環境變數都設 → 走 LMStudioBrain（不實際連線，只驗選擇邏輯）。"""
    monkeypatch.setenv("VACANT_MCP_BASE", "http://localhost:1234")
    monkeypatch.setenv("VACANT_MCP_MODEL", "some-model")
    brain = cli._build_brain()
    assert brain.__class__.__name__ == "LMStudioBrain"


def test_offline_brain_fallback(capsys, monkeypatch):
    monkeypatch.delenv("VACANT_MCP_MODEL", raising=False)
    monkeypatch.delenv("VACANT_MCP_BASE", raising=False)
    brain = cli._build_brain()
    assert isinstance(brain, cli.EchoLikeBrain)
    assert "offline brain" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    ["up", "--help"],
    ["toggle", "--help"],
    ["status", "--help"],
    ["scoreboard", "--help"],
    ["resident", "--help"],
    ["resident", "inspect", "--help"],
    ["ledger", "tail", "--help"],
    ["verify", "--help"],
])
def test_help_does_not_crash(argv):
    """--help 觸發 argparse SystemExit(0)，不得是別的例外。"""
    with pytest.raises(SystemExit) as ei:
        cli.main(argv)
    assert ei.value.code == 0


def test_up_no_dashboard(tmp_path, capsys):
    """up --no-dashboard 只建生態就返回（不 serve），確認前景不阻塞。"""
    root = tmp_path / "eco"
    rc, out, _ = _run(capsys, ["up", "--no-dashboard", "--root", str(root)])
    assert rc == 0
    assert "生態就緒" in out
    assert (root / "residents" / "resident_1").is_dir()
    assert not (root / "residents" / "saboteur_1").exists()


def test_up_demo_roster_is_explicit(tmp_path, capsys):
    root = tmp_path / "demo"
    rc, _, _ = _run(capsys, [
        "up", "--no-dashboard", "--demo-roster", "--root", str(root),
    ])
    assert rc == 0
    assert (root / "residents" / "saboteur_1").is_dir()


def test_demo_roster_cannot_contaminate_product_root(tmp_path, capsys):
    root = tmp_path / "product"
    rc, _, _ = _run(capsys, ["up", "--no-dashboard", "--root", str(root)])
    assert rc == 0
    rc, _, err = _run(capsys, [
        "up", "--no-dashboard", "--demo-roster", "--root", str(root),
    ])
    assert rc == 1
    assert "不可" in err and "~/.vacant-demo" in err
