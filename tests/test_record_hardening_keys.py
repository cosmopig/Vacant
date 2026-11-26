"""紀錄強化 3：簽署私鑰路徑設定、權限檢查與同帳號可讀警告。

驗證：
1. 預設金鑰位於 `$VACANT_HOME/intake/keys/verifier/identity.key`，`signing_key_posture`、
   `vacant trace verify` 與 `statusboard.install_status` 均明確警告同 OS 帳號可讀。
2. `VACANT_SIGNING_KEY_PATH`（檔案路徑與目錄路徑）、`VACANT_KEYS_DIR` 與 `$VACANT_HOME/intake/config.json`
   可將私鑰置於工作區與 `$VACANT_HOME` 之外，自動以 0600／0700 建立並登記進 `trust.json`，
   簽章鏈可正常寫入與驗證，且 `hookpolicy` 亦拒絕工具讀寫該外部金鑰路徑。
3. 權限過寬（如 0644／0755）或金鑰置於工作區內時發出對應警告；唯讀檢查不建立任何檔案。
"""
from __future__ import annotations

import json
import os
import pathlib
import stat

import pytest

from vacant_network import statusboard as SB
from vacant_network.adapters import hookpolicy as HP
from vacant_network.intake import keys
from vacant_network.trace import cli as trace_cli
from vacant_network.trace import recorder as R


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    vh = tmp_path / "vh"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    for k in (keys.SIGNING_KEY_PATH_ENV, keys.KEYS_DIR_ENV):
        monkeypatch.delenv(k, raising=False)
    ws = tmp_path / "proj"
    ws.mkdir()
    return tmp_path, vh, ws


def test_default_key_warns_in_verify_and_statusboard_and_is_readonly(env, monkeypatch, capsys):
    """未建金鑰前 posture 唯讀不建檔；建鏈後預設金鑰在 VACANT_HOME 下，verify 與 statusboard 皆出警告。"""
    _tmp, vh, ws = env
    p0 = keys.signing_key_posture("verifier", workspace=ws)
    assert p0["exists"] is False
    assert p0["source"] == "default"
    assert p0["in_vacant_home"] is True
    assert not vh.exists(), "signing_key_posture 必須嚴格唯讀"

    rec = R.Recorder(ws)
    rec.baseline()
    assert rec.verify()[0]

    p1 = keys.signing_key_posture("verifier", workspace=ws)
    assert p1["exists"] is True
    assert p1["in_vacant_home"] is True
    assert p1["readable_by_current_user"] is True
    assert p1["isolated"] is False
    assert any("VACANT_HOME" in w and "same user" in w for w in p1["warnings"])

    monkeypatch.chdir(ws)
    rc = trace_cli.main(["trace", "verify"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("OK ")
    assert "WARNING:" in out and "VACANT_HOME" in out

    rc_j = trace_cli.main(["trace", "verify", "--json"])
    jout = json.loads(capsys.readouterr().out)
    assert rc_j == 0
    assert jout["signing_key"]["in_vacant_home"] is True
    assert jout["signing_key"]["isolated"] is False

    st = SB.install_status()
    assert st["signing_key"]["path"] == p1["path"]
    assert st["signing_key"]["warnings"]


def test_env_signing_key_path_outside_vacant_home_and_workspace(env, monkeypatch, capsys):
    """`VACANT_SIGNING_KEY_PATH` 指到工作區與 VACANT_HOME 外的檔案：0600 落盤、可簽可驗、hook 阻擋讀取。"""
    tmp_path, vh, ws = env
    ext_key = tmp_path / "outside_keys" / "verifier.key"
    monkeypatch.setenv(keys.SIGNING_KEY_PATH_ENV, str(ext_key))

    rec = R.Recorder(ws)
    rec.baseline()
    assert ext_key.is_file()
    assert not (vh / "intake" / "keys" / "verifier" / "identity.key").exists()
    assert stat.S_IMODE(ext_key.stat().st_mode) == 0o600
    assert stat.S_IMODE(ext_key.parent.stat().st_mode) == 0o700
    assert rec.verify()[0]

    posture = keys.signing_key_posture("verifier", workspace=ws)
    assert posture["source"] == f"env:{keys.SIGNING_KEY_PATH_ENV}"
    assert posture["in_vacant_home"] is False
    assert posture["in_workspace"] is False
    assert posture["group_or_world_readable"] is False
    assert posture["readable_by_current_user"] is True
    assert posture["isolated"] is False
    assert any("separate-account signing helper is not yet implemented" in w for w in posture["warnings"])

    # hookpolicy 字串層也拒絕 agent 讀這把外部私鑰
    ev = HP.HookEvent(agent="claude", kind="pre_tool", tool="Read",
                      paths=[str(ext_key)], cwd=str(ws))
    dec = HP.decide_pre_tool(ev, None)
    assert dec.action == "deny"

    # 故意放寬權限 ⇒ posture 與 verify 必須指出權限過寬
    os.chmod(ext_key, 0o644)
    os.chmod(ext_key.parent, 0o755)
    bad = keys.signing_key_posture("verifier", workspace=ws)
    assert bad["group_or_world_readable"] is True
    assert bad["dir_group_or_world_accessible"] is True
    assert any("0644" in w for w in bad["warnings"])
    assert any("0755" in w for w in bad["warnings"])


def test_config_json_and_keys_dir_and_workspace_warning(env, monkeypatch):
    """`intake/config.json` 與 `VACANT_KEYS_DIR` 皆生效；金鑰誤放在工作區內時發出工作區警告。"""
    tmp_path, vh, ws = env
    cfg_dir = vh / "intake"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    ws_key = ws / "leaked_verifier.key"
    (cfg_dir / "config.json").write_text(json.dumps({"signing_key_path": str(ws_key)}), encoding="utf-8")

    rec = R.Recorder(ws)
    rec.baseline()
    assert ws_key.is_file()
    p_ws = keys.signing_key_posture("verifier", workspace=ws)
    assert p_ws["source"] == "config:signing_key_path"
    assert p_ws["in_workspace"] is True
    assert any("inside the workspace" in w for w in p_ws["warnings"])

    # VACANT_KEYS_DIR 優先於 config.json
    kd = tmp_path / "all_keys_dir"
    monkeypatch.setenv(keys.KEYS_DIR_ENV, str(kd))
    assert keys.signing_key_path("verifier") == kd / "verifier" / "identity.key"
    assert keys.signing_key_path("owner") == kd / "owner" / "identity.key"
