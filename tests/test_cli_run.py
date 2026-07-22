"""產品 `vacant run`：低摩擦 check、任意 argv agent，以及真正的 fail-closed。"""

from __future__ import annotations

import json
import sys

from vacant import cli
from vacant.ecosystem import Ecosystem, PRODUCT_ROSTER


class GoodBrain:
    name = "good"

    def generate(self, prompt):
        return "def solve(s):\n    return s[::-1]"


class WrongBrain:
    name = "wrong"

    def generate(self, prompt):
        return "def solve(s):\n    return s"


def _eco(tmp_path, brain):
    return Ecosystem(
        tmp_path / "eco", brain, roster=PRODUCT_ROSTER,
        k_reviewers=2, audit_rate=1.0,
    )


def _agent_script(tmp_path):
    script = tmp_path / "agent.py"
    script.write_text(
        """import json, pathlib, sys
marker, context_path = sys.argv[1], sys.argv[2]
context = json.loads(pathlib.Path(context_path).read_text())
pathlib.Path(marker).write_text(context['task_id'])
print('agent received ' + context['task_id'])
""",
        encoding="utf-8",
    )
    return script


def test_cli_run_launches_custom_agent_only_after_gate(tmp_path, capsys, monkeypatch):
    eco = _eco(tmp_path, GoodBrain())
    monkeypatch.setattr(cli, "_build_product_eco", lambda args: eco)
    marker = tmp_path / "agent-ran"
    script = _agent_script(tmp_path)
    agent_argv = json.dumps([
        sys.executable, str(script), str(marker), "{context_path}",
    ])

    rc = cli.main([
        "run", "Reverse a string.",
        "--test", "assert solve('abc') == 'cba'",
        "--agent-argv", agent_argv,
        "--root", str(eco.root),
    ])
    captured = capsys.readouterr()
    assert rc == 0
    assert marker.exists()
    assert marker.read_text() in captured.out
    assert "Vacant-first gate" in captured.out
    assert "agent received" in captured.out


def test_cli_run_bad_delivery_cannot_create_agent_marker(tmp_path, capsys, monkeypatch):
    eco = _eco(tmp_path, WrongBrain())
    monkeypatch.setattr(cli, "_build_product_eco", lambda args: eco)
    marker = tmp_path / "must-not-exist"
    script = _agent_script(tmp_path)
    agent_argv = json.dumps([
        sys.executable, str(script), str(marker), "{context_path}",
    ])

    rc = cli.main([
        "run", "Reverse a string.",
        "--test", "assert solve('abc') == 'cba'",
        "--attempts", "2",
        "--agent-argv", agent_argv,
        "--root", str(eco.root),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert not marker.exists()
    assert "VACANT_GATE_REJECTED" in captured.err
    assert "外部 agent 未啟動" in captured.err


def test_cli_run_json_without_agent(tmp_path, capsys, monkeypatch):
    eco = _eco(tmp_path, GoodBrain())
    monkeypatch.setattr(cli, "_build_product_eco", lambda args: eco)
    rc = cli.main([
        "run", "Reverse a string.",
        "--check-json", json.dumps({
            "type": "run_python", "code": "assert solve('ab') == 'ba'",
        }),
        "--json",
        "--root", str(eco.root),
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["agent"]["ran"] is False
    assert data["answer"].endswith("return s[::-1]")
    assert data["receipt_path"].endswith("receipt.json")


def test_cli_run_without_real_model_fails_closed(capsys, monkeypatch):
    monkeypatch.delenv("VACANT_MCP_MODEL", raising=False)
    rc = cli.main(["run", "Return OK", "--expect", "OK"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "缺模型" in captured.err
    assert "外部 agent 未啟動" in captured.err
