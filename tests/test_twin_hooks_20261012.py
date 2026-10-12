"""分身走 Vacant 0.9.x 掛鉤（`ops/exhibit/twin/twin_hooks.py`，2026-10-12 過渡版）。

守的是：
  · 預設關——沒設 `VACANT_TWIN_HOOKS=1`，pi 的 argv 與沒有這個功能時逐位元相同；開了才多一個 `-e <擴充>`；
    缺擴充檔／缺 VACANT_HOME 時 fail-open（照舊跑、argv 不變）。
  · 圍牆的額外綁定（VACANT_HOME 可寫、擴充目錄唯讀）只在開、且接得上時才有。
  · 撤回要刪乾淨——**有正控制**：撤回前分身寫的字在 VACANT_HOME 裡找得到、撤回後找不到；
    被別的專案引用的共用 blob 不刪；開關關掉（回滾）之後撤回照刪。
  · `install()` 用的是產品自己的 `vacant install --agents pi`（mode=evidence、budget_reminder 關）。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TWIN = ROOT / "ops" / "exhibit" / "twin"

from ops.exhibit.twin import twin_hooks as TH  # noqa: E402
from ops.exhibit.twin import twinagent  # noqa: E402
from vacant_network.adapters import hook  # noqa: E402
from vacant_network.adapters import install as INS  # noqa: E402
from vacant_network.trace import zerostop  # noqa: E402
from vacant_network.trace.recorder import project_key  # noqa: E402

LETTER = "親愛的你：我把窗台上那盆快枯的薄荷救了回來，這件事我只想讓你知道。"


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE", "CLAUDE_CONFIG_DIR",
              "CODEX_HOME", "XDG_CONFIG_HOME", "PI_CODING_AGENT_DIR", TH.ENV_FLAG, TH.ENV_PIDIR, TH.ENV_EXT):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(zerostop, "_run_child", zerostop.check)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


def _record(ws: pathlib.Path, session: str, text: str) -> None:
    """用真的掛鉤（pi 擴充送的形狀）記一個「寫了一個檔」的步驟——產生真的 chain／blob／state。"""
    (ws / ".git").mkdir(parents=True, exist_ok=True)
    base = {"session_id": session, "cwd": str(ws)}
    hook.handle("pi", "prompt", {**base, "prompt": "Write 信.md"})
    pre = {**base, "tool": "ws_write", "call_id": "t1", "input": {"path": "信.md", "content": text}}
    hook.handle("pi", "pre_tool", pre)
    (ws / "信.md").write_text(text, encoding="utf-8")
    hook.handle("pi", "post_tool", {**pre, "output": "ok", "is_error": False})


def _scan(root: pathlib.Path, needle: str) -> list[str]:
    n = needle.encode()
    return [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and n in p.read_bytes()]


# ── 開關 ────────────────────────────────────────────────────────────────

def test_off_by_default_and_extras_need_everything(env, monkeypatch):
    assert TH.enabled() is False and TH.encl_extras() is None
    monkeypatch.setenv(TH.ENV_FLAG, "1")
    assert TH.encl_extras() is None, "開了但沒有擴充檔 ⇒ 不接（fail-open）"
    ext = env / "pivh" / "extensions" / "vacant.ts"
    ext.parent.mkdir(parents=True)
    ext.write_text("// ext")
    monkeypatch.setenv(TH.ENV_EXT, str(ext))
    x = TH.encl_extras()
    assert x["setenv"][TH.ENV_FLAG] == "1" and x["rw"] == [str(env / "vh")] and x["ro"] == [str(env / "pivh")]
    monkeypatch.setenv(TH.ENV_FLAG, "0")
    assert TH.encl_extras() is None


def test_vacant_home_inside_repo_is_refused(env, monkeypatch):
    ext = env / "e" / "extensions" / "vacant.ts"
    ext.parent.mkdir(parents=True)
    ext.write_text("x")
    monkeypatch.setenv(TH.ENV_FLAG, "1")
    monkeypatch.setenv(TH.ENV_EXT, str(ext))
    monkeypatch.setenv("VACANT_HOME", str(ROOT / "ops" / "_vh_test"))
    assert TH.encl_extras() is None, "repo 是唯讀綁進圍牆的，VACANT_HOME 不能在裡面"


def _run_wrapper(tmp_path, extra_env):
    ws, rd = tmp_path / "ws", tmp_path / "rd"
    ws.mkdir(parents=True), rd.mkdir(parents=True)
    (ws / "TRAITS.md").write_text("- 氣質：慢\n", encoding="utf-8")
    (rd / "stage2_in").mkdir()
    (rd / "stage2_in" / "WORLD.md").write_text("世界\n", encoding="utf-8")
    (rd / "stage2_in" / "地上").mkdir()
    fake = tmp_path / "pi"
    fake.write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > " + str(rd) + "/argv.txt\n", encoding="utf-8")
    fake.chmod(0o755)
    letter = tmp_path / "letter.py"
    letter.write_text("import pathlib, sys\npathlib.Path(sys.argv[2], '信.md').write_text('這個人手慢。\\n', encoding='utf-8')\n",
                      encoding="utf-8")
    e = {k: v for k, v in os.environ.items() if not k.startswith("VACANT_TWIN_HOOK")}
    e.update({"VACANT_RUN_PROXY": "http://127.0.0.1:1", "VACANT_TWIN_PI": str(fake),
              "VACANT_TWIN_PY": sys.executable, "VACANT_TWIN_LETTER": str(letter), **extra_env})
    r = subprocess.run(["bash", str(TWIN / "twin_agent.sh"), "S1", "M1", str(rd), "SYS", "MSG"],
                       cwd=ws, env=e, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return (rd / "argv.txt").read_text(encoding="utf-8").splitlines(), (rd / "agent_stderr.log").read_text(encoding="utf-8")


def test_wrapper_argv_unchanged_when_off_or_incomplete_and_gets_one_dash_e_when_on(tmp_path):
    off, _ = _run_wrapper(tmp_path / "a", {})
    ext = tmp_path / "pivh" / "extensions" / "vacant.ts"
    ext.parent.mkdir(parents=True)
    ext.write_text("// ext")
    # 開了但沒給 VACANT_HOME ⇒ 不接，argv 逐位元相同
    incomplete, err = _run_wrapper(tmp_path / "b", {"VACANT_TWIN_HOOKS": "1", "VACANT_TWIN_HOOK_EXT": str(ext)})
    assert incomplete == off and "不接" in err
    missing, _ = _run_wrapper(tmp_path / "c", {"VACANT_TWIN_HOOKS": "1", "VACANT_HOME": str(tmp_path / "vh"),
                                               "VACANT_TWIN_HOOK_EXT": str(tmp_path / "nope.ts")})
    assert missing == off
    on, _ = _run_wrapper(tmp_path / "d", {"VACANT_TWIN_HOOKS": "1", "VACANT_HOME": str(tmp_path / "vh"),
                                          "VACANT_TWIN_HOOK_EXT": str(ext)})
    i = on.index(str(ext))
    assert on[i - 1] == "-e" and on.count(str(ext)) == 1
    assert on[:i - 1] + on[i + 1:] == off, "除了多一個 -e <擴充> 之外，argv 逐位元相同"
    # 擴充排在 twin 自己的工具擴充之後、--no-extensions 之前
    assert on.index("--no-extensions") > i


def test_flag_off_in_wrapper_source_is_default():
    sh = (TWIN / "twin_agent.sh").read_text(encoding="utf-8")
    assert '"${VACANT_TWIN_HOOKS:-0}" = "1"' in sh


# ── 安裝：產品自己的指令 ───────────────────────────────────────────────

def test_install_uses_the_product_installer(env, monkeypatch):
    monkeypatch.setenv(TH.ENV_FLAG, "1")
    r = TH.install(python=sys.executable)
    assert r["rc"] == 0 and r["ext_exists"] and r["mode"] == "evidence", r
    ext = pathlib.Path(r["ext"])
    assert "Vacant (vacant-intake)" in ext.read_text(encoding="utf-8")
    inst = json.loads((env / "vh" / "adapters" / "install.json").read_text())
    assert inst["mode"] == "evidence" and inst.get("budget_reminder") is False
    assert not (pathlib.Path.home() / ".pi").exists(), "不准寫進真的 ~/.pi"


# ── 撤回 ────────────────────────────────────────────────────────────────

def test_erase_has_a_positive_control_and_leaves_other_projects_alone(env):
    vh = env / "vh"
    a, b = env / "work" / "ws" / "a", env / "work" / "ws" / "b"
    a.mkdir(parents=True), b.mkdir(parents=True)
    _record(a, "SA", LETTER)
    _record(b, "SB", "別人寫的另一封信，內容完全不同。")
    # 正控制：撤回前找得到（量具量得動）
    before = _scan(vh, "薄荷")
    assert before and any("objects" in x or "chain" in x for x in before), before
    assert TH.present(a, vh) and TH.present(b, vh)
    rep = TH.erase(a, vh)
    assert rep["projects"] == 1 and rep["blobs"] >= 1 and not rep["problems"], rep
    assert _scan(vh, "薄荷") == [], "撤回後 VACANT_HOME 裡不能再有分身寫的字"
    assert not TH.present(a, vh)
    # 別人的專案完好
    assert TH.present(b, vh) and _scan(vh, "完全不同"), "別位觀眾的紀錄不能被刪"
    assert not (vh / "trace" / "projects" / project_key(a)).exists()
    # 冪等
    assert TH.erase(a, vh)["projects"] == 0


def test_erase_keeps_a_blob_that_another_project_still_uses(env):
    vh = env / "vh"
    a, b = env / "work" / "ws" / "a", env / "work" / "ws" / "b"
    a.mkdir(parents=True), b.mkdir(parents=True)
    shared = "共用的世界檔：三棵老樹、一口井。"
    _record(a, "SA", shared)
    _record(b, "SB", shared)
    rep = TH.erase(a, vh)
    assert rep["blobs_kept_shared"] >= 1, rep
    assert _scan(vh, "三棵老樹"), "b 還在用的 blob 不能刪"


def test_withdraw_path_erases_trace_even_after_the_switch_is_rolled_back(env, monkeypatch):
    """twinagent.erase_run_artifacts：開關是關的（回滾之後）、只要 VACANT_HOME 還設著就照刪。"""
    work = env / "twinwork"
    sub = "SYN-x"
    ws, rd = twinagent.paths_for(work, sub)
    ws.mkdir(parents=True), rd.mkdir(parents=True)
    _record(ws, "SW", LETTER)
    assert not TH.enabled()
    assert twinagent.run_artifacts_present(work, sub)
    assert _scan(env / "vh", "薄荷")
    rep = twinagent.erase_run_artifacts(work, sub)
    assert any(e["what"] == "vacant_trace" for e in rep["erased"]), rep
    assert not rep["problems"], rep
    assert _scan(env / "vh", "薄荷") == []
    assert not twinagent.run_artifacts_present(work, sub)


def test_erase_without_vacant_home_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("VACANT_HOME", raising=False)
    rep = TH.erase(tmp_path / "ws" / "z")
    assert rep["home_set"] is False and rep["projects"] == 0
    assert TH.present(tmp_path / "ws" / "z") is False


# ── pi 0.85.1 沒有 session 內的檢查：結束後補跑（只寫交件說明）───────────────

def test_post_check_runs_only_when_there_is_a_trace_and_no_delivery_note(env, monkeypatch):
    vh = env / "vh"
    ws = env / "work" / "ws" / "p"
    ws.mkdir(parents=True)
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    assert TH.post_check_if_needed(ws, vh)["why"] == "no_project"
    _record(ws, "SP", LETTER)
    d = TH._project_dirs_for(vh, ws)[0]
    assert not (d / "delivery.json").exists()
    r = TH.post_check_if_needed(ws, vh, python=sys.executable)
    assert r["ran"] is True and r["rc"] == 0, r
    assert (d / "delivery.json").is_file(), "補跑後要有交件說明"
    assert "after the run ended" in (d / "delivery.md").read_text(encoding="utf-8")
    # 已經有交件說明（session 內查過）⇒ 不再動
    assert TH.post_check_if_needed(ws, vh, python=sys.executable) == {
        "ran": False, "why": "in_session_check_already_ran"}
    # 交件說明在 VACANT_HOME 裡，不在工作區（不進分身看得到的地方）
    assert not list(ws.rglob("delivery.*"))


def test_erase_all_clears_orphans_but_keeps_the_install(env):
    vh = env / "vh"
    ws = env / "work" / "ws" / "orphan"
    ws.mkdir(parents=True)
    _record(ws, "SO", LETTER)
    assert _scan(vh, "薄荷")
    r = TH.erase_all(vh)
    assert set(r["removed"]) == {"trace", "intake/hooks"} or "trace" in r["removed"], r
    assert _scan(vh, "薄荷") == []
    assert (vh / "adapters" / "install.json").is_file(), "安裝狀態要留著（儀表板還要顯示已安裝）"
