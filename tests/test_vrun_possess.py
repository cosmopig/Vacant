"""`vacant_network/vrun/possess.py` ＋ `gateshim.py` 的可執行防呆。

這一組測試守的是**四件會安靜壞掉的事**（每一件都在 2026-09-19 真的發生過
或差一點發生）：

1. **偵測會騙人。** `bash -lic` 的輸出混著終端機跳脫序列；照單全收會拿到
   一個不存在的路徑然後判「沒裝」。這台機器上因此誤判過兩次。
2. **還原沒還乾淨。** 動了使用者的設定檔而還不回去 ＝ 把人家的環境弄壞。
   所以測的是**逐位元相同**，不是「看起來還原了」。
3. **「沒閘門」長得像「通過」。** `stop_reason="ungated"` 在
   `launcher.exit_code()` 裡是 0；shim 層必須把它分成 21。
4. **憑證被碰到。** `NEVER_TOUCH` 不是註解，是一條會 raise 的擋門。

⚠ 這一組**不碰網路、不裝 launchd／systemd、不動 `$HOME`**：全部在 tmp_path
  底下、`--no-service`。真跑的證據在
  `decisions/DECISION_20260919_DEFAULT_ON_INSTALL.md`。
"""
from __future__ import annotations

import json
import pathlib

import pytest

from vacant_network.vrun import gateshim, possess


# ── 1. 偵測 ────────────────────────────────────────────────────────────

def test_strip_terminal_noise_removes_osc7():
    """`bash -lic` 會把 OSC 7（設定終端機 cwd）混進 `command -v` 的輸出。"""
    dirty = "\x1b]7;file://MacBookPro/tmp\x07\x1b]133;C\x07/usr/local/bin/codex"
    assert possess.strip_terminal_noise(dirty) == "/usr/local/bin/codex"


def test_strip_terminal_noise_removes_csi_and_controls():
    assert possess.strip_terminal_noise("\x1b[0m/bin/pi\r") == "/bin/pi"


def test_detect_by_config_dir_only(tmp_path: pathlib.Path):
    """**設定目錄在就算裝了**，即使 PATH 上完全找不到那支可執行檔。

    這是 2026-09-19 兩台機器上的實測形狀：vacant-dev 的 pi／opencode／hermes、
    人類 Mac 的 pi 都是「設定目錄在、PATH 上沒有」。只看 PATH 會判「沒裝」，
    然後那幾個 agent 一個都不會被接上。
    """
    (tmp_path / ".pi" / "agent").mkdir(parents=True)
    d = possess.detect_one(possess.AGENTS["pi"], tmp_path, probe_shell=False)
    assert d.present is True
    assert d.config_dir is not None
    assert d.binary is None and d.binary_via == "none"


def test_detect_absent(tmp_path: pathlib.Path):
    d = possess.detect_one(possess.AGENTS["hermes"], tmp_path, probe_shell=False)
    assert d.present is False


# ── 2. 憑證紅線 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("rel", possess.NEVER_TOUCH)
def test_never_touch_raises(tmp_path: pathlib.Path, rel: str):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"{}")
    with pytest.raises(PermissionError):
        possess.write_tracked(tmp_path, p, b"nope", tmp_path / "bk")


# ── 3. 逐個 agent 的接線 ＋ 逐位元還原 ─────────────────────────────────

def _seed_home(h: pathlib.Path) -> dict[str, bytes]:
    """造一個「使用者本來就有東西」的 HOME，回原始 bytes。"""
    files = {
        ".claude/settings.json": json.dumps(
            {"model": "sonnet", "permissions": {"allow": ["Bash"]}},
            indent=2).encode() + b"\n",
        ".codex/config.toml": (b'model = "gpt-5"\n'
                               b'approval_policy = "on-request"\n\n'
                               b'[projects."/tmp/x"]\ntrust_level = "trusted"\n'),
        ".config/opencode/opencode.json": json.dumps(
            {"$schema": "x", "provider": {"mine": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": "https://upstream.example/v1"},
                "models": {"m": {"name": "m"}}}}}, indent=2).encode() + b"\n",
        ".pi/agent/models.json": b"{}\n",
        ".hermes/config.yaml": (b"model:\n  default: hermes-4\n"
                                b"tools:\n  enabled: true\n"),
        ".zshrc": b"# mine\nexport FOO=1\n",
    }
    for rel, data in files.items():
        p = h / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return files


def _install(h: pathlib.Path, **kw):
    return possess.install(home=h, port=18790, probe_shell=False,
                           skip_service=True, **kw)


def test_install_wires_all_five_then_uninstall_restores_byte_for_byte(
        tmp_path: pathlib.Path):
    h = tmp_path / "home"
    h.mkdir()
    before = _seed_home(h)
    st = _install(h)

    # 五個都接上了（設定目錄都在）
    assert set(st["agents"]) == set(possess.AGENTS)
    for a in possess.AGENTS:
        assert st["channel"][a]["ok"] is True, st["channel"][a]

    # 每一個設定檔裡都真的出現了那個端點
    for a, spec in possess.AGENTS.items():
        body = (h / spec.config_file).read_text("utf-8")
        assert "127.0.0.1:18790" in body, a

    # 改過的檔都有備份，而且備份的 sha256 對得上 before
    for c in st["files"]:
        if c["action"] == "modify":
            assert c["backup"] and pathlib.Path(c["backup"]).is_file()
            assert possess.sha256_file(
                pathlib.Path(c["backup"])) == c["before_sha256"]

    rep = possess.uninstall(home=h)
    assert rep["ok"] is True
    for rel, data in before.items():
        assert (h / rel).read_bytes() == data, f"{rel} 沒有逐位元還原"
    # shim 也清乾淨
    assert not (possess.state_home(h) / "bin").exists()


def test_uninstall_verifies_and_reports_each_file(tmp_path: pathlib.Path):
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    rep = possess.uninstall(home=h)
    assert all(r["ok"] for r in rep["restored"])
    for r in rep["restored"]:
        if r["action"] == "modify":
            assert r["sha256_now"] == r["sha256_expected"]


def test_codex_config_stays_valid_toml_and_keeps_user_keys(
        tmp_path: pathlib.Path):
    """寫壞 `config.toml` ⇒ codex 連載入都失敗（0.147.0 實測是設定層退件）。"""
    import tomllib
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    doc = tomllib.loads((h / ".codex/config.toml").read_text("utf-8"))
    assert doc["model_provider"] == "vacant"
    assert doc["model"] == "gpt-5"                     # 使用者的沒被動
    assert doc["projects"]["/tmp/x"]["trust_level"] == "trusted"
    prov = doc["model_providers"]["vacant"]
    assert prov["base_url"] == "http://127.0.0.1:18790/v1"
    assert prov["wire_api"] == "responses"
    # 內建 id `openai` 不准被覆寫（codex 會 fail-closed 報錯）
    assert "openai" not in doc["model_providers"]


def test_claude_settings_keeps_other_keys_and_never_writes_a_key(
        tmp_path: pathlib.Path):
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    doc = json.loads((h / ".claude/settings.json").read_text("utf-8"))
    assert doc["model"] == "sonnet"
    assert doc["permissions"] == {"allow": ["Bash"]}
    assert doc["env"]["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:18790"
    # ⚠ 憑證紅線：任何金鑰欄位都不准被寫進去
    assert not any("KEY" in k or "TOKEN" in k for k in doc["env"])


def test_opencode_redirects_existing_providers_and_adds_one(
        tmp_path: pathlib.Path):
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    doc = json.loads((h / ".config/opencode/opencode.json").read_text("utf-8"))
    assert doc["$schema"] == "x"
    # 使用者原本的 provider 被改道（不是被刪掉）
    assert doc["provider"]["mine"]["options"]["baseURL"] == \
        "http://127.0.0.1:18790/v1"
    assert doc["provider"]["mine"]["models"] == {"m": {"name": "m"}}
    # 內建雲端 provider 也被蓋掉，否則那條路直連
    assert "127.0.0.1" in doc["provider"]["openai"]["options"]["baseURL"]
    assert "127.0.0.1" in doc["provider"]["anthropic"]["options"]["baseURL"]
    # 另外加一個可以直接指到本地模型的
    assert "vacant" in doc["provider"]


def test_hermes_gets_provider_and_base_url_together(tmp_path: pathlib.Path):
    """⚠ 少了 `provider: custom` ⇒ Hermes 0.19.0 停在
    `No LLM provider configured`、`requests_seen == 0`，而閘門照樣判拒交
    ——那是**假的拒交格**。所以這兩行是一組。"""
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    body = (h / ".hermes/config.yaml").read_text("utf-8")
    assert "provider: custom" in body
    assert "base_url: http://127.0.0.1:18790/v1" in body
    assert "default: hermes-4" in body                 # 使用者的沒被吃掉


def test_path_block_is_delimited_and_removed_cleanly(tmp_path: pathlib.Path):
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    rc = (h / ".zshrc").read_text("utf-8")
    assert possess.BEGIN_MARK in rc and possess.END_MARK in rc
    assert "export FOO=1" in rc
    possess.uninstall(home=h)
    assert (h / ".zshrc").read_text("utf-8") == "# mine\nexport FOO=1\n"


def test_reinstall_is_idempotent_no_duplicate_blocks(tmp_path: pathlib.Path):
    """重裝不可以把區塊疊上去——疊了就還原不回去。"""
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    possess.uninstall(home=h)
    _install(h)
    rc = (h / ".zshrc").read_text("utf-8")
    assert rc.count(possess.BEGIN_MARK) == 1
    toml = (h / ".codex/config.toml").read_text("utf-8")
    assert toml.count("[model_providers.vacant]") == 1


def test_install_refuses_second_time(tmp_path: pathlib.Path):
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    with pytest.raises(RuntimeError, match="已經裝過"):
        _install(h)


def test_status_separates_wired_from_proven(tmp_path: pathlib.Path):
    """**「我寫了設定檔」不是「被中介了」**（`envmap` 誠實邊界 1）。"""
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    s = possess.status(home=h)
    assert s["installed"] is True
    for a, v in s["channel"].items():
        assert v["wired"] is True
        assert v["proven"] is False          # 還沒有任何 requests_seen
    possess.mark_proven("codex", 3, home=h)
    s2 = possess.status(home=h)
    assert s2["channel"]["codex"]["proven"] is True
    assert s2["channel"]["pi"]["proven"] is False
    # 每一個改過的檔都要說得出「還原會做什麼」
    for f in s2["files"]:
        assert f["uninstall_will"]


def test_mark_proven_ignores_zero(tmp_path: pathlib.Path):
    """`requests_seen == 0` **不算證據**，不可以把 proven 點亮。"""
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    possess.mark_proven("codex", 0, home=h)
    assert possess.status(home=h)["channel"]["codex"]["proven"] is False


def test_upstream_falls_back_to_sink_not_public_api(tmp_path: pathlib.Path,
                                                    monkeypatch):
    """沒有人指定上游 ⇒ **本機 sink**，不是公開 API（`envmap.SINK_UPSTREAM`）。"""
    from vacant_network.vrun import envmap
    for _w, names in envmap.UPSTREAM_VARS:
        for n in names:
            monkeypatch.delenv(n, raising=False)
    h = tmp_path / "home"
    h.mkdir()
    ups = possess.discover_install_upstreams(h)
    for wire in ("openai", "anthropic"):
        assert envmap.is_sink(ups[wire]["url"])


# ── 4. gateshim：驗收來源與退出碼 ──────────────────────────────────────

def test_resolve_suite_prefers_env(tmp_path: pathlib.Path, monkeypatch):
    s = tmp_path / "explicit"
    s.mkdir()
    (s / "test_a.py").write_text("def check_x(): pass")
    monkeypatch.setenv("VACANT_SUITE", str(s))
    got, src = gateshim.resolve_suite(tmp_path)
    assert got == s and src == "env:VACANT_SUITE"


def test_resolve_suite_finds_tests_visible(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("VACANT_SUITE", raising=False)
    (tmp_path / ".git").mkdir()
    tv = tmp_path / "tests_visible"
    tv.mkdir()
    (tv / "test_visible.py").write_text("def check_x(): pass")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    got, src = gateshim.resolve_suite(sub)
    assert got == tv and src == "dir:tests_visible"


def test_resolve_suite_dot_vacant_wins_over_tests_visible(
        tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("VACANT_SUITE", raising=False)
    (tmp_path / ".git").mkdir()
    for name in (".vacant/suite", "tests_visible"):
        d = tmp_path / name
        d.mkdir(parents=True)
        (d / "test_a.py").write_text("def check_x(): pass")
    got, src = gateshim.resolve_suite(tmp_path)
    assert src == "dir:.vacant/suite"


def test_resolve_suite_toml(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("VACANT_SUITE", raising=False)
    (tmp_path / ".git").mkdir()
    d = tmp_path / "acceptance"
    d.mkdir()
    (d / "test_a.py").write_text("def check_x(): pass")
    (tmp_path / ".vacant.toml").write_text('suite = "acceptance"\n')
    got, src = gateshim.resolve_suite(tmp_path)
    assert got == d.resolve() and src == "toml:.vacant.toml"


def test_resolve_suite_none_is_not_an_error(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.delenv("VACANT_SUITE", raising=False)
    (tmp_path / ".git").mkdir()
    got, src = gateshim.resolve_suite(tmp_path)
    assert got is None and src == "none"


def test_exit_codes_are_all_distinct():
    """**「沒量」與「量到過」不可以在資料上同形**——退出碼是第一道分界。"""
    from vacant_network.vrun import launcher
    codes = {launcher.EXIT_ACCEPTED, launcher.EXIT_REFUSED,
             launcher.EXIT_VOID, gateshim.EXIT_UNGATED,
             gateshim.EXIT_NO_MEDIATION}
    assert len(codes) == 5
    assert gateshim.EXIT_UNGATED != launcher.EXIT_ACCEPTED


def test_passthrough_lets_version_and_help_through():
    """`codex --version` 被包起來只會壞掉日常操作，然後 Vacant 被解除安裝。

    ⚠ **這是一條明示的繞過路**，寫成測試是為了它數得出來、不是意外。
    """
    assert gateshim.is_passthrough("codex", ["--version"]) is True
    assert gateshim.is_passthrough("claude", ["mcp", "list"]) is True
    assert gateshim.is_passthrough("codex", []) is True


def test_real_binary_excludes_shim_dir(tmp_path: pathlib.Path, monkeypatch):
    """shim 目錄留在 PATH 上 ⇒ shim 會 exec 自己 ⇒ 無限遞迴。"""
    shim = tmp_path / "shim"
    real = tmp_path / "real"
    shim.mkdir()
    real.mkdir()
    for d in (shim, real):
        f = d / "codex"
        f.write_text("#!/bin/sh\n")
        f.chmod(0o755)
    monkeypatch.delenv("VACANT_POSSESS_REAL_BIN", raising=False)
    monkeypatch.setenv("PATH", f"{shim}:{real}")
    assert gateshim.real_binary("codex", str(shim)) == str(real / "codex")
