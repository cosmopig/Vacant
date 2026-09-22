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

from vacant_network.vrun import gateshim, piext, possess


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
    """⚠ 兩個探測預設**關掉**：`startable_probe` 會**真的把 agent 跑起來**
    （那是它的重點），`gate_reach_probe` 會跑 `bash -lic`。兩個都會碰到這台
    機器上真實存在的東西，不該出現在單元測試裡。它們各自有自己的測試。
    """
    kw.setdefault("startable_probe", False)
    kw.setdefault("gate_reach_probe", False)
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


# ── 6. 洞 4：per-run 設定目錄的收尾（2026-09-20 Linux 那一輪量到的洩漏）──
#
#    量到的形狀：codex 把 plugins git repo 整個 clone 進 per-run `CODEX_HOME`
#    ⇒ **每格 ~100 MB**，5 格 400 MB，而且 `uninstall` 不碰它。
#    下面這一組守的是收尾契約的三層與**四道不刪的門**
#    （`gateshim.sweep_cfg_dirs` 的 docstring）。

def _mk_cfg(parent: pathlib.Path, name: str, *, pid: int | None,
            age_s: float = 0.0, payload: int = 0,
            start_key: str | None = "") -> pathlib.Path:
    import time as _t
    d = parent / name
    d.mkdir(parents=True)
    if payload:
        (d / "blob.bin").write_bytes(b"x" * payload)
    if pid is not None:
        gateshim._write_owner(d, pid, _t.time() - age_s, start_key=start_key)
    return d


def _dead_pid() -> int:
    """一個保證不存在的 pid（開一個子行程再收屍，那個號碼馬上就死了）。"""
    import subprocess as _sp
    p = _sp.Popen(["/bin/sh", "-c", "exit 0"])
    p.wait()
    return p.pid


def test_sweep_never_touches_dirs_it_did_not_create(tmp_path: pathlib.Path):
    """⚠ **不要順手刪掉不是自己建的東西。**

    沒有 owner 標記的目錄一律 `skipped_not_ours`，**一個 byte 都不碰**。
    """
    par = tmp_path / "vacant-possess"
    stranger = _mk_cfg(par, "somebody-elses", pid=None, payload=64)
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=0.0)
    assert str(stranger) in rep["skipped_not_ours"]
    assert (stranger / "blob.bin").read_bytes() == b"x" * 64
    assert rep["removed"] == []


def test_sweep_keeps_dirs_whose_owner_is_still_alive(tmp_path: pathlib.Path):
    """別的 session 正在跑的那一份不准收——判準是 pid 還活著。"""
    import os as _os
    par = tmp_path / "vacant-possess"
    live = _mk_cfg(par, "run-codex-live", pid=_os.getpid(), age_s=99999)
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=0.0)
    assert [x["path"] for x in rep["kept_alive"]] == [str(live)]
    assert live.is_dir()


def test_sweep_falls_back_to_the_age_gate_when_owner_state_is_unknown(
        tmp_path: pathlib.Path):
    """⚠ 問不出來的擁有者（沒有 `start_key`、pid 又還在）**不是「死了」**。

    那種格子退回保守的歲數門檻——寧可晚一點收，也不要刪掉別人正在用的設定。
    """
    import os as _os
    par = tmp_path / "vacant-possess"
    unknown = _mk_cfg(par, "run-codex-unknown", pid=_os.getpid(), age_s=5,
                      start_key=None)
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=3600)
    assert [x["path"] for x in rep["kept_young"]] == [str(unknown)]
    assert rep["kept_young"][0]["owner"] == "unknown"
    assert unknown.is_dir()


def test_sweep_collects_the_sigkill_leftover_on_the_very_next_run(
        tmp_path: pathlib.Path):
    """**這一格就是 `kill -9` 那一格。**

    擁有者確定死了 ⇒ **不等歲數門檻，下一跑就收**（這裡 `max_age_s=3600`
    卻仍然收掉，就是在證明那一條）。沒有這一條，`SIGKILL` 的垃圾要躺到
    6 小時後，而無人值守的迴圈在那之前照樣是線性成長。

    ⚠ 它保證的是「**不隨格數累積**」，**不是**「當下不留」——被 `kill -9`
      的那一份確實會留到**下一次有人經過閘門**（或 `--sweep`）。
    """
    par = tmp_path / "vacant-possess"
    dead = _mk_cfg(par, "run-codex-dead", pid=_dead_pid(), age_s=10,
                   payload=4096)
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=3600)
    assert not dead.exists()
    assert [x["path"] for x in rep["removed"]] == [str(dead)]
    assert rep["removed"][0]["bytes"] >= 4096


def test_sweep_notices_a_reused_pid(tmp_path: pathlib.Path):
    """pid 還在、但**行程啟動時刻對不上** ⇒ 是別人接手了這個號碼，原主已死。"""
    import os as _os
    par = tmp_path / "vacant-possess"
    reused = _mk_cfg(par, "run-codex-reused", pid=_os.getpid(), age_s=1,
                     start_key="not-the-one-that-is-running-now")
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=3600)
    assert not reused.exists()
    assert [x["path"] for x in rep["removed"]] == [str(reused)]


def test_sweep_does_not_collect_the_run_that_is_asking(tmp_path: pathlib.Path):
    """`keep=` 那一份是正在跑的自己，不准被自己的開場掃地機收掉。"""
    par = tmp_path / "vacant-possess"
    mine = _mk_cfg(par, "run-codex-mine", pid=_dead_pid(), age_s=10)
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=0.0, keep=mine)
    assert mine.is_dir()
    assert rep["removed"] == []


def test_release_does_not_delete_a_dir_the_caller_supplied():
    """`VACANT_POSSESS_CFG` 是呼叫端指定的位置 ⇒ **誰指定誰負責**。"""
    r = gateshim.release_cfg_dir(None)
    assert r["owned"] is False


def test_release_removes_its_own_dir(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("VACANT_POSSESS_TMPROOT", str(tmp_path))
    d = gateshim.new_cfg_dir("run-codex")
    (d / "big").write_bytes(b"y" * 1024)
    assert d.is_dir()
    r = gateshim.release_cfg_dir(d)
    assert r["ok"] is True and not d.exists()


def test_release_failure_leaves_a_mark_for_the_next_sweep(
        tmp_path: pathlib.Path, monkeypatch):
    """**刪不掉怎麼辦**：不 raise、不靜默，把 owner 標記改寫成死的交給下一次。

    ⚠ `rmtree` 有可能**先把標記刪掉才失敗** ⇒ 這裡是「改寫」不是「保留」，
      不改寫的話那個目錄會變成 `skipped_not_ours`，從此沒人收得到。
    """
    import shutil as _sh
    par = tmp_path / "vacant-possess"
    d = _mk_cfg(par, "run-codex-stuck", pid=None)
    (d / gateshim.OWNER_MARK).unlink(missing_ok=True)

    def _boom(_p):
        raise OSError("Device or resource busy")
    monkeypatch.setattr(_sh, "rmtree", _boom)
    r = gateshim.release_cfg_dir(d)
    assert r["ok"] is False and "busy" in r["error"]
    monkeypatch.undo()
    # 標記回來了，而且是死的 ⇒ 下一次掃地機收得到
    info = json.loads((d / gateshim.OWNER_MARK).read_text("utf-8"))
    assert info["pid"] == 0
    rep = gateshim.sweep_cfg_dirs(parent=par, max_age_s=0.0)
    assert [x["path"] for x in rep["removed"]] == [str(d)]


def test_sweep_never_looks_outside_its_own_parent(tmp_path: pathlib.Path,
                                                  monkeypatch):
    """掃地機只掃 `$TMPDIR/vacant-possess/`，**不掃 `$TMPDIR` 本身**。"""
    monkeypatch.setenv("VACANT_POSSESS_TMPROOT", str(tmp_path))
    sibling = tmp_path / "someone-elses-tmpdir"
    sibling.mkdir()
    (sibling / "important").write_bytes(b"keep me")
    gateshim.new_cfg_dir("run-codex")
    rep = gateshim.sweep_cfg_dirs(max_age_s=0.0)
    assert rep["parent"] == str(tmp_path / gateshim.CFG_PARENT_NAME)
    assert (sibling / "important").read_bytes() == b"keep me"


# ── 7. 洞 1：`wired` 不等於 `startable`（乾淨 Linux 上 codex 起不來）──

def _fake_agent(path: pathlib.Path, body: str) -> str:
    import sys as _sys
    path.write_text(f"#!{_sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def test_startable_is_none_when_there_is_no_binary(tmp_path: pathlib.Path):
    """L-none：沒有可執行檔 ⇒ `None`＝**沒量到**，不是「起不來」（鐵律 3）。"""
    r = possess.probe_startable("hermes", home=tmp_path, binary=None)
    assert r["startable"] is None and r["measured"] is False
    assert "不量" in r["reason"]


def test_startable_is_none_when_we_have_no_one_shot_invocation(
        tmp_path: pathlib.Path):
    """hermes 有可執行檔但沒有已知的一次性叫法 ⇒ 仍然是 `None`，不是 False。"""
    b = _fake_agent(tmp_path / "hermes", "raise SystemExit(0)\n")
    r = possess.probe_startable("hermes", home=tmp_path, binary=b)
    assert r["startable"] is None and r["measured"] is False


def test_startable_true_when_the_agent_opens_a_connection(
        tmp_path: pathlib.Path):
    """判準＝**探測 listener 收到連線**，而且全程**沒有任何模型呼叫**。

    假 agent 做的事跟真 codex 一樣：讀 `$CODEX_HOME/config.toml` 的
    `base_url`，開一條 TCP。另一頭是本機 listener，只回 503。
    """
    b = _fake_agent(tmp_path / "codex", "\n".join([
        "import os, socket, sys",
        'cfg = open(os.path.join(os.environ["CODEX_HOME"],'
        ' "config.toml")).read()',
        'port = int(cfg.split("127.0.0.1:")[1].split("/")[0])',
        'sock = socket.create_connection(("127.0.0.1", port), 5)',
        'sock.sendall(b"POST /v1/responses HTTP/1.1")',
        "sock.recv(64)",
        "sys.exit(0)",
    ]) + "\n")
    r = possess.probe_startable("codex", home=tmp_path, binary=b, timeout_s=20)
    assert r["measured"] is True
    assert r["startable"] is True and r["connected"] is True
    assert r["connections"] >= 1


def test_startable_false_reproduces_the_missing_env_key_pathology(
        tmp_path: pathlib.Path, monkeypatch):
    """**2026-09-20 在 vacant-dev 上量到的那一格**：設定寫了、proxy 活著、
    `install-status` 說「✓ 已寫入」，而 codex 在開任何連線之前就

        ERROR: Missing environment variable: OPENAI_API_KEY

    ⇒ `wired` 仍然是 True，但 `startable` 必須是 **False**。
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    b = _fake_agent(tmp_path / "codex", """
import os, sys
if not os.environ.get("OPENAI_API_KEY"):
    sys.stderr.write("ERROR: Missing environment variable: OPENAI_API_KEY\\n")
    sys.exit(1)
""")
    r = possess.probe_startable("codex", home=tmp_path, binary=b, timeout_s=20)
    assert r["measured"] is True
    assert r["startable"] is False and r["connected"] is False
    assert r["env_key"] == "OPENAI_API_KEY" and r["env_key_present"] is False
    assert "OPENAI_API_KEY" in r["reason"]


def test_startable_probe_never_injects_a_key(tmp_path: pathlib.Path,
                                             monkeypatch):
    """⚠ 探測**刻意不補金鑰**——補了就正好把要量的那個洞蓋掉。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    b = _fake_agent(tmp_path / "codex", """
import os, sys
sys.stderr.write("KEY=%r\\n" % os.environ.get("OPENAI_API_KEY"))
""")
    r = possess.probe_startable("codex", home=tmp_path, binary=b, timeout_s=20)
    assert "KEY=None" in r["stderr_head"]


def test_status_prints_three_separate_columns(tmp_path: pathlib.Path):
    """`wired` / `startable` / `proven` **三欄，不可互相冒充**。"""
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    st = _install(h, agents=["codex"])
    # install 當時沒量 ⇒ None（不是 False）
    s = possess.status(home=h)
    assert s["channel"]["codex"]["wired"] is True
    assert s["channel"]["codex"]["startable"] is None
    assert s["channel"]["codex"]["proven"] is False
    txt = possess._fmt_status(s)
    assert "設定 ✓ 已寫入" in txt and "啟動 － 沒量到" in txt
    # 手動把「起不來」寫進 state ⇒ status 要說得出來
    sp = possess.state_home(h) / "state.json"
    doc = json.loads(sp.read_text("utf-8"))
    doc["channel"]["codex"]["startable"] = False
    doc["channel"]["codex"]["startable_reason"] = "**起不來**：缺 OPENAI_API_KEY"
    sp.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
    txt = possess._fmt_status(possess.status(home=h))
    assert "啟動 **✗ 起不來**" in txt and "OPENAI_API_KEY" in txt
    assert st["channel"]["codex"]["ok"] is True


# ── 8. 洞 2：PATH 區塊（出現兩次＋非互動 shell 收不到）────────────────

def _bash_path_after(script: str) -> list[str]:
    import subprocess as _sp
    r = _sp.run(["bash", "-c", f'PATH=/usr/bin:/bin\n{script}\nprintf "%s" "$PATH"'],
                capture_output=True, text=True, timeout=30)
    return r.stdout.split(":")


def test_path_block_is_idempotent_even_if_sourced_twice(
        tmp_path: pathlib.Path):
    """⚠ 2026-09-20 量到的 bug：`.profile` 與 `.bashrc` 都加 ⇒ `bash -lic`
    底下 shim 目錄在 PATH 上**出現兩次**，開一次終端機加一次，會累積。
    """
    shim = tmp_path / "shim"
    blk = tmp_path / "blk.sh"
    blk.write_text(possess._path_block(shim), encoding="utf-8")
    once = _bash_path_after(f'. {blk}')
    twice = _bash_path_after(f'. {blk}\n. {blk}')
    assert once.count(str(shim)) == 1
    assert twice.count(str(shim)) == 1, "source 兩次不可以在 PATH 上出現兩次"
    assert twice[0] == str(shim)


def test_bashrc_block_goes_before_the_noninteractive_return(
        tmp_path: pathlib.Path):
    """Ubuntu stock `~/.bashrc` **第 6 行就 `return`** ⇒ 區塊附加在檔尾等於
    在 `ssh 主機 '指令'` 底下根本不會被執行到（裁決檔 §五 第 10 條）。

    這一格量的是**行為不是位置**：非互動地 source `.bashrc`，shim 要在 PATH 上。
    """
    h = tmp_path / "home"
    h.mkdir()
    (h / ".bashrc").write_text(
        "# ~/.bashrc\n\n"
        "# If not running interactively, don't do anything\n"
        "case $- in\n"
        "    *i*) ;;\n"
        "      *) return;;\n"
        "esac\n\n"
        "export MINE=1\n", encoding="utf-8")
    shim = tmp_path / "shim"
    shim.mkdir()
    possess.install_path_block(h, shim, tmp_path / "bk")
    body = (h / ".bashrc").read_text("utf-8")
    assert body.index(possess.BEGIN_MARK) < body.index("case $- in")
    out = _bash_path_after(f'. {h / ".bashrc"} >/dev/null 2>&1')
    assert out.count(str(shim)) == 1, "非互動 source .bashrc 收不到 shim"
    # 使用者原本的內容還在（那一行在 return 之後，非互動本來就跑不到）
    assert "export MINE=1" in body


def test_profile_block_still_appends_at_the_end(tmp_path: pathlib.Path):
    """只有 `.bashrc` 有那個守衛；別的檔維持附加在檔尾，不亂動人家的順序。"""
    h = tmp_path / "home"
    h.mkdir()
    (h / ".profile").write_text("export FIRST=1\n", encoding="utf-8")
    shim = tmp_path / "shim"
    possess.install_path_block(h, shim, tmp_path / "bk")
    body = (h / ".profile").read_text("utf-8")
    assert body.index("export FIRST=1") < body.index(possess.BEGIN_MARK)


def test_noninteractive_guard_detection_needs_a_real_return(
        tmp_path: pathlib.Path):
    """一個剛好長得像的 `case` 不算守衛——後面 6 行內要真的有 `return`。"""
    assert possess._noninteractive_guard_at(
        "case $- in\n  *i*) ;;\n  *) return;;\nesac\n") == 0
    assert possess._noninteractive_guard_at(
        '[ -z "$PS1" ] && return\n') == 0
    assert possess._noninteractive_guard_at(
        "case $- in\n  *i*) echo hi;;\nesac\n") is None
    assert possess._noninteractive_guard_at("export X=1\n") is None


def test_gate_reach_reports_bash_c_as_not_covered(tmp_path: pathlib.Path):
    """⚠ **不准安靜地只覆蓋一半。**

    `bash -c` 一個 rc 檔都不讀 ⇒ 那一格永遠是 ❌，而 `status` 要說得出來。
    """
    shim = tmp_path / "shim"
    shim.mkdir()
    r = possess.probe_gate_reach(shim, timeout_s=40)
    assert r["forms"]["bash -c"]["on_path"] is False
    assert "bash -c" in r["not_covered"]
    assert r["headline"]
    assert "不會被繞過" not in r["headline"]


# ── 9. 洞 3：`Linger` 只還原**我們開的**那一次 ─────────────────────────

def test_linger_is_left_alone_when_it_was_already_on():
    """⚠ 本來就開著的不准動——關掉會弄死別人要的常駐服務。"""
    r = possess._restore_linger({"linger_user": "nobody-x",
                                 "linger_before": "yes",
                                 "linger_enabled_by_us": False})
    assert r["action"] == "skipped" and "不是我們開的" in r["reason"]


def test_linger_is_left_alone_when_we_never_measured_it():
    """`unknown`／舊版 state ⇒ 不動（鐵律 3：「沒量到」≠「量到 no」）。"""
    assert possess._restore_linger({"linger_user": "nobody-x"})["action"] \
        == "skipped"
    r = possess._restore_linger({"linger_user": "nobody-x",
                                 "linger_before": "unknown",
                                 "linger_enabled_by_us": False})
    assert r["action"] == "skipped"


def test_linger_is_turned_back_off_when_we_turned_it_on(monkeypatch):
    """`Linger=no` 的機器 install→uninstall 之後要回到 `no`。"""
    calls = []
    seq = iter(["yes", "no"])          # 動之前 yes，disable 之後 no
    monkeypatch.setattr(possess, "read_linger", lambda u=None: next(seq))

    class _R:
        returncode, stderr = 0, ""

    def _run(argv, **kw):
        calls.append(argv)
        return _R()
    monkeypatch.setattr(possess.subprocess, "run", _run)
    r = possess._restore_linger({"linger_user": "u1", "linger_before": "no",
                                 "linger_enabled_by_us": True})
    assert r["action"] == "restored" and r["after"] == "no"
    assert calls == [["loginctl", "disable-linger", "u1"]]


def test_read_linger_says_unknown_not_no_when_it_cannot_tell(monkeypatch):
    """⚠ 問不出來要回 `"unknown"`，**不可以回 `"no"`**。"""
    monkeypatch.setattr(possess.shutil, "which", lambda _n: None)
    assert possess.read_linger("whoever") == "unknown"


def test_uninstall_reports_what_it_kept_on_purpose(tmp_path: pathlib.Path):
    """`uninstall` 不是「零殘留」——留下來的東西要逐條講得出來。"""
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    _install(h)
    rep = possess.uninstall(home=h)
    assert rep["ok"] is True
    assert any("journal" in x for x in rep["kept_on_purpose"])
    assert "cfg_sweep" in rep


# ── 10. agent 自己的防護：install 釘沙箱＋收據記姿態（Fable 2026-09-20）──

def test_install_pins_codex_sandbox_to_workspace_write(tmp_path: pathlib.Path):
    """⚠ `install` 以前對沙箱姿態**完全無作為**，等於把一層白拿的防護放著
    不用——codex 預設的 `workspace-write` **本來就不給 shell 指令網路**，
    而那正是最致命那一類洞（agent 直接 `curl` 模型端點，wire 零紀錄、
    收據照樣 `accepted=true`）的一半來源。
    """
    import tomllib
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    st = _install(h, agents=["codex"])
    doc = tomllib.loads((h / ".codex/config.toml").read_text("utf-8"))
    assert doc["sandbox_mode"] == possess.CODEX_SANDBOX_DEFAULT
    assert doc["model"] == "gpt-5"                     # 使用者的沒被動
    p = st["agent_posture"]["codex"]
    assert p["measured"] is True
    assert p["sandbox_mode"] == "workspace-write"
    # ⚠ 裝上去就要拔得掉
    assert possess.uninstall(home=h)["ok"] is True
    assert "sandbox_mode" not in (h / ".codex/config.toml").read_text("utf-8")


def test_codex_sandbox_override_is_allowed_but_leaves_a_trace(
        tmp_path: pathlib.Path, monkeypatch):
    """逃生口存在，但**覆寫要留痕**——不可以安靜地把牆拆掉。"""
    import tomllib
    monkeypatch.setenv("VACANT_POSSESS_CODEX_SANDBOX", "danger-full-access")
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    st = _install(h, agents=["codex"])
    doc = tomllib.loads((h / ".codex/config.toml").read_text("utf-8"))
    assert doc["sandbox_mode"] == "danger-full-access"
    assert any("danger-full-access" in w for w in st["warnings"]), st["warnings"]
    assert st["codex_sandbox_requested"] == "danger-full-access"


def test_codex_sandbox_keep_does_not_touch_the_users_posture(
        tmp_path: pathlib.Path, monkeypatch):
    """`keep` ⇒ 一個字都不改使用者原本的姿態，但仍然在 warnings 裡留痕。"""
    import tomllib
    monkeypatch.setenv("VACANT_POSSESS_CODEX_SANDBOX", "keep")
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    (h / ".codex/config.toml").write_bytes(
        b'model = "gpt-5"\nsandbox_mode = "read-only"\n')
    st = _install(h, agents=["codex"])
    doc = tomllib.loads((h / ".codex/config.toml").read_text("utf-8"))
    assert doc["sandbox_mode"] == "read-only"
    assert any("沒有被釘住" in w for w in st["warnings"])


def test_existing_sandbox_line_is_replaced_with_the_original_in_a_comment(
        tmp_path: pathlib.Path):
    """原值要留在肉眼看得到的地方，而且重裝要冪等（不可以疊兩行）。"""
    import tomllib
    h = tmp_path / "home"
    h.mkdir()
    _seed_home(h)
    (h / ".codex/config.toml").write_bytes(
        b'sandbox_mode = "danger-full-access"\nmodel = "gpt-5"\n')
    _install(h, agents=["codex"])
    body = (h / ".codex/config.toml").read_text("utf-8")
    assert body.count("sandbox_mode") == 2      # 新的一行 ＋ 註解裡的原值
    assert "原值：sandbox_mode = \"danger-full-access\"" in body
    assert tomllib.loads(body)["sandbox_mode"] == "workspace-write"


def test_posture_is_null_not_empty_string_when_unmeasurable(
        tmp_path: pathlib.Path):
    """⚠ 鐵律 3：讀不出來寫 `None`，**不准寫空字串**。"""
    h = tmp_path / "home"
    h.mkdir()
    for a in ("pi", "opencode", "hermes"):
        p = possess.read_agent_posture(h, a)
        assert p["sandbox_mode"] is None and p["approval_policy"] is None
        assert p["measured"] is False


def test_gate_receipt_records_the_posture_it_actually_ran_under():
    """一個 `workspace-write` 下的 `accepted=true` 跟一個 `danger-full-access`
    下的 `accepted=true` **不可以在收據上長得一模一樣**。"""
    p = gateshim.inner_posture("codex", ["exec", "hello"])
    assert p["sandbox_mode"] == "danger-full-access"   # 閘門那條路的**現況**
    assert p["approval_policy"] == "never"
    assert p["flags"] == []
    p2 = gateshim.inner_posture("claude",
                                ["-p", "x", "--dangerously-skip-permissions"])
    assert p2["flags"] == ["--dangerously-skip-permissions"]
    # 沒有已知讀法的 agent ⇒ None，不是空字串
    p3 = gateshim.inner_posture("pi", ["-p", "x"])
    assert p3["sandbox_mode"] is None and p3["approval_policy"] is None


# ── 10. pi：extension，不碰 models.json（2026-09-22） ──────────────────────

def _pi_ext(h: pathlib.Path) -> pathlib.Path:
    return h / possess.AGENTS["pi"].config_file


def test_pi_install_writes_extension_and_leaves_models_json_byte_identical(
        tmp_path: pathlib.Path):
    """`vacant install --agent pi` 寫的是 `~/.pi/agent/extensions/vacant.ts`，
    使用者的 `models.json` **一個位元都不動**（使用者自己的 provider 不改道）。"""
    h = tmp_path / "home"
    (h / ".pi" / "agent").mkdir(parents=True)
    mj = h / ".pi" / "agent" / "models.json"
    original = b'{"providers": {"mine": {"baseUrl": "https://keep.example/v1"}}}\n'
    mj.write_bytes(original)
    st = _install(h, agents=["pi"])
    assert st["channel"]["pi"]["ok"] is True, st["channel"]["pi"]
    ext = _pi_ext(h)
    assert ext.is_file()
    body = ext.read_text("utf-8")
    assert body.startswith(piext.MARK)
    assert "http://127.0.0.1:18790" in body
    assert 'registerProvider("vacant"' in body or "registerProvider(PROVIDER" in body
    assert 'registerCommand("vacant"' in body
    assert "vacant_network.vrun.hookcli" in body
    assert mj.read_bytes() == original, "models.json 被動了"
    # 🔴 **裝了不等於被中介**：`proven` 只有 `mark_proven`（requests_seen > 0）點得亮，
    #    `install` 自己永遠點不亮它。2026-09-22 `CHANNEL_MEASURED["pi"]` 填上真模型日期
    #    之後 `verified` 會是 True——那一欄記的是「這條路**有人量過**」，
    #    **不是「這一次被中介了」**。兩欄不可互相冒充，所以這裡兩條都驗。
    assert st["channel"]["pi"]["verified"] is bool(possess.CHANNEL_MEASURED["pi"])
    assert st["channel"]["pi"].get("proven") is not True
    written = {c["path"] for c in st["files"]}
    assert str(mj) not in written


def test_pi_uninstall_removes_extension_and_restores_previous_one(
        tmp_path: pathlib.Path):
    """使用者原本就有一支同名 extension ⇒ 備份、覆寫、還原逐位元相同。"""
    h = tmp_path / "home"
    ext = h / ".pi" / "agent" / "extensions" / "vacant.ts"
    ext.parent.mkdir(parents=True)
    theirs = b"// theirs\nexport default function (pi) {}\n"
    ext.write_bytes(theirs)
    st = _install(h, agents=["pi"])
    assert ext.read_bytes() != theirs
    ch = [c for c in st["files"] if c["path"] == str(ext)][0]
    assert ch["action"] == "modify" and ch["backup"]
    rep = possess.uninstall(home=h)
    assert rep["ok"] is True
    assert ext.read_bytes() == theirs


def test_pi_uninstall_deletes_extension_we_created(tmp_path: pathlib.Path):
    h = tmp_path / "home"
    (h / ".pi" / "agent").mkdir(parents=True)
    _install(h, agents=["pi"])
    ext = _pi_ext(h)
    assert ext.is_file()
    assert possess.uninstall(home=h)["ok"] is True
    assert not ext.exists()


def test_piext_render_is_pure_and_bakes_models():
    body = piext.render(port=18790, state_dir="/x/state", python="/py",
                        package_path="/pkg", models=["a", "b"])
    assert '"/py"' in body and '"/pkg"' in body and '"/x/state"' in body
    assert '["a", "b"]' in body
    assert body.count("http://127.0.0.1:18790") >= 1
    # 每個掛鉤事件都在（與 2026-09-20 A 級那一跑同一組，見 hookcli.install_pi）
    for ev in ("session_start", "user_prompt_submit", "pre_tool_use", "tool_result",
               "before_provider_request", "stop", "session_end"):
        assert f'"{ev}"' in body, ev
    # 關掉要留痕
    assert '"vacant_off"' in body


def test_piext_is_valid_javascript():
    """extension 是純 JS（副檔名 .ts 只因為 pi 只認 .ts／.js）。
    `node --check` 驗語法；沒有 node 就 **skip 並印理由**，不是通過。"""
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        pytest.skip("這台沒有 node ⇒ extension 語法沒量到（不是通過）")
    body = piext.render(port=18790, state_dir="/x", python="/py", package_path="/pkg")
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "vacant.mjs"
        f.write_text(body, "utf-8")
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_pi_probe_models_returns_empty_not_error_when_nothing_listens():
    assert piext.probe_models(1, timeout=0.5) == []
