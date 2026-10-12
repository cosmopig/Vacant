"""i1001 的「操作層」小工具與文件的測試：vllm_up_i1001.sh（--dry-run）、vmsh_i1001.sh、cu_cap_i1001.sh、freeze_i1001.py，
以及預註冊／RUNBOOK 與這些檔案的一致性。

全部用假的 colab（本機 bash 腳本）——**沒有碰任何真的 Colab、沒有起任何 VM**。真的 colab CLI 的行為
（`usage` 的輸出格式、console 的排隊、drivemount）沒有被這裡驗到。
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CI = ROOT / "ops" / "colab_interactive_20261001"
PREREG = ROOT / "decisions" / "prereg" / "PREREG_20261001_COLAB_INTERACTIVE_I1001.md"
RUNBOOK = CI / "RUNBOOK.md"


def _load_freeze():
    spec = importlib.util.spec_from_file_location("freeze_i1001", CI / "freeze_i1001.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["freeze_i1001"] = m
    spec.loader.exec_module(m)
    return m


freeze = _load_freeze()


def sh(script, args, env=None, timeout=60):
    return subprocess.run(["bash", str(CI / script), *args], capture_output=True, text=True, errors="replace",
                          env={**os.environ, **(env or {})}, timeout=timeout)


# ── 語法與基本防呆 ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("script", ["vm/vllm_up_i1001.sh", "vmsh_i1001.sh", "cu_cap_i1001.sh"])
def test_new_scripts_parse(script):
    assert subprocess.run(["bash", "-n", str(CI / script)], capture_output=True).returncode == 0


def test_vllm_up_dry_run_prints_the_frozen_serve_command():
    r = subprocess.run(["bash", str(CI / "vm" / "vllm_up_i1001.sh"), "--dry-run"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "VLLM_USE_FLASHINFER_SAMPLER=0" in out                        # sm_120 上 FlashInfer 採樣器會崩（第一批實測）
    for flag in ("--served-model-name gemma-4-12b-it-qat", "--max-model-len 262144", "--gpu-memory-utilization 0.90",
                 "--enable-prefix-caching", "--enable-auto-tool-choice", "--tool-call-parser gemma4", "--reasoning-parser gemma4",
                 "--chat-template /content/tool_chat_template_gemma4.jinja", "--async-scheduling",
                 "--enable-prompt-tokens-details", "--host 127.0.0.1", "--port 18000"):
        assert flag in out, flag
    assert "VLLM_VERSION=0.30.0" in out
    assert "MODEL_SHA=60b6e3989502969d8ae04185d72ecbbc7db63978d5af747a493d53895aa6bfa3" in out


def test_vllm_up_never_listens_on_all_interfaces():
    # Colab 條款：不得對外開網頁服務。第一批的 setup_vllm.sh 結尾那條 serve 聽 0.0.0.0，這一支不准重蹈（註解可以提它，程式碼不行）。
    code = "\n".join(ln for ln in (CI / "vm" / "vllm_up_i1001.sh").read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "0.0.0.0" not in code
    assert "--host 127.0.0.1" in code


# ── vmsh：假的 colab（upload／console／download 都在一個本機目錄上） ─────────────────────────────

FAKE_VM_COLAB = """#!/usr/bin/env bash
cmd=$1; shift; [ "${1:-}" = -s ] && shift 2
case "$cmd" in
  upload)   [ -n "${FAKE_UPLOAD_FAIL:-}" ] && exit 1; cp "$1" "$2";;
  download) [ -f "$1" ] || exit 1; cp "$1" "$2";;
  console)  bash -s;;
  *) exit 9;;
esac
"""


@pytest.fixture()
def vmdir(tmp_path):
    d = tmp_path / "vmdir"
    d.mkdir()
    colab = tmp_path / "colab"
    colab.write_text(FAKE_VM_COLAB)
    colab.chmod(0o755)
    return d, colab


def vmsh(vmdir, args, **env):
    d, colab = vmdir
    return sh("vmsh_i1001.sh", args, env={"COLAB": str(colab), "VMSH_DIR": str(d), "VMSH_POLL": "1", **env})


def test_vmsh_returns_output_and_the_remote_exit_code(vmdir):
    r = vmsh(vmdir, ["sess", "--wait", "20", "-c", "echo hello; echo oops >&2; exit 3"])
    assert r.returncode == 3, r.stdout + r.stderr
    assert "hello" in r.stdout and "oops" in r.stdout and "__rc=" not in r.stdout       # 2>&1 合併；結束標記不外漏
    r = vmsh(vmdir, ["sess", "--wait", "20", "-c", "true"])
    assert r.returncode == 0


def test_vmsh_runs_a_local_script_file_and_tails(vmdir, tmp_path):
    f = tmp_path / "s.sh"
    f.write_text("for i in 1 2 3 4 5; do echo line$i; done\n")
    r = vmsh(vmdir, ["sess", "--wait", "20", "--tail", "2", str(f)])
    assert r.returncode == 0 and r.stdout.split() == ["line4", "line5"]


def test_vmsh_a_command_that_prints_a_marker_like_line_mid_run_is_not_taken_as_finished(vmdir):
    # 輸出的「目前最後一行」恰好是 `__rc=7` 時（指令還在睡），不能被當成結束——結束標記帶這一次的 ID
    r = vmsh(vmdir, ["sess", "--wait", "20", "-c", "echo '__rc=7'; sleep 3; echo after"])
    assert r.returncode == 0 and "__rc=7" in r.stdout and "after" in r.stdout


def test_vmsh_wait_timeout_is_124_and_says_the_command_may_still_be_running(vmdir):
    r = vmsh(vmdir, ["sess", "--wait", "2", "-c", "echo started; sleep 6; echo finished"])
    assert r.returncode == 124 and "VMSH_WAIT_TIMEOUT" in r.stderr and "還在跑" in r.stderr


def test_vmsh_upload_failure_is_125_and_runs_nothing(vmdir):
    d, _ = vmdir
    r = vmsh(vmdir, ["sess", "--wait", "2", "-c", "touch " + str(d / "ran")], FAKE_UPLOAD_FAIL="1")
    assert r.returncode == 125 and not (d / "ran").exists()


def test_vmsh_usage_without_a_command(vmdir):
    assert vmsh(vmdir, ["sess"]).returncode == 2


# ── cu_cap：軟上限／硬上限（兩個估計取較大者） ────────────────────────────────────────────────────

FAKE_CAP_COLAB = """#!/usr/bin/env bash
cmd=$1; shift; S=""; [ "${1:-}" = -s ] && { S=$2; shift 2; }
case "$cmd" in
  usage)    [ -f "$FAKE/balance" ] && echo "Current balance: $(cat "$FAKE/balance")";;
  console)  cat >> "$FAKE/console.log";;
  download) [ -f "$FAKE/vm$1" ] || exit 1; cp "$FAKE/vm$1" "$2";;
  stop)     echo "STOP -s $S" >> "$FAKE/stop.log";;
  *) exit 9;;
esac
"""
T0 = 1_000_000


@pytest.fixture()
def cap(tmp_path):
    fake = tmp_path / "fake"
    (fake / "vm" / "srv" / "eval").mkdir(parents=True)
    colab = tmp_path / "colab"
    colab.write_text(FAKE_CAP_COLAB)
    colab.chmod(0o755)

    def run(balance, elapsed_h, extra=(), **env):
        if balance is None:
            (fake / "balance").unlink(missing_ok=True)
        else:
            (fake / "balance").write_text(str(balance))
        e = {"COLAB": str(colab), "FAKE": str(fake), "CU_CAP_NOW": str(T0 + int(elapsed_h * 3600)),
             "CU_CAP_GRACE_S": "2", "CU_CAP_POLL_S": "1", **env}
        return sh("cu_cap_i1001.sh", ["sess", "--b0", "100", "--t0", str(T0), "--soft", "70", "--hard", "90",
                                       "--max-loops", "1", *extra], env=e)
    return fake, run


def console_text(fake):
    p = fake / "console.log"
    return p.read_text() if p.exists() else ""


def test_cap_below_soft_does_nothing(cap):
    fake, run = cap
    r = run(95, 0.5)                                    # 餘額估計 5、時間估計 4.45
    assert r.returncode == 0 and "spent=5.00" in r.stdout
    assert console_text(fake) == "" and not (fake / "stop.log").exists()


def test_cap_soft_places_stop_only_and_does_not_stop_the_vm(cap):
    fake, run = cap
    r = run(25, 3)                                      # 餘額估計 75 ≥ 70
    assert r.returncode == 0 and "SOFT_CAP" in r.stdout
    assert "/srv/eval/STOP" in console_text(fake) and "DRIVER_DONE" not in console_text(fake)
    assert not (fake / "stop.log").exists()


def test_cap_hard_stops_the_vm_after_requesting_the_final_pack(cap):
    fake, run = cap
    (fake / "vm" / "srv" / "eval" / "ALL_DONE").write_text("{}")
    r = run(5, 3)                                       # 餘額估計 95 ≥ 90
    assert r.returncode == 6 and "HARD_CAP" in r.stdout and "ALL_DONE=1" in r.stdout and "STOPPED" in r.stdout
    c = console_text(fake)
    assert "/srv/eval/STOP" in c and "touch /srv/eval/DRIVER_DONE" in c
    assert (fake / "stop.log").read_text().strip() == "STOP -s sess"


def test_cap_hard_stops_even_when_all_done_never_appears(cap):
    fake, run = cap
    r = run(5, 3)
    assert r.returncode == 6 and "ALL_DONE=0" in r.stdout and (fake / "stop.log").exists()


def test_cap_time_estimate_guards_when_usage_is_unreadable(cap):
    fake, run = cap
    r = run(None, 11)                                   # 讀不到餘額；11 h × 8.9 = 97.9 ≥ 90
    assert r.returncode == 6 and "balance=?" in r.stdout and "STOPPED" in r.stdout


def test_cap_unreadable_balance_is_not_taken_as_zero_spend_or_as_a_stop(cap):
    fake, run = cap
    r = run(None, 0.5)                                  # 讀不到餘額、才 0.5 h ⇒ 只靠時間估計：4.45，不動作
    assert r.returncode == 0 and "spent=4.45" in r.stdout and not (fake / "stop.log").exists()


def test_cap_takes_the_larger_estimate(cap):
    fake, run = cap
    r = run(99, 8)                                      # 餘額估計 1、時間估計 71.2 ⇒ 軟上限（usage 落後時時間估計補位）
    assert "spent=71.20" in r.stdout and "SOFT_CAP" in r.stdout


def test_cap_dry_run_calls_neither_console_nor_stop(cap):
    fake, run = cap
    r = run(5, 3, extra=["--dry-run"])
    assert r.returncode == 0 and "DRY-RUN: colab stop" in r.stdout
    assert console_text(fake) == "" and not (fake / "stop.log").exists()


def test_cap_hard_pulls_one_last_local_sync_before_stopping(cap, tmp_path):
    fake, run = cap
    rec = tmp_path / "sync.args"
    fakesync = tmp_path / "fakesync.sh"
    fakesync.write_text(f'#!/usr/bin/env bash\necho "$@" > {rec}\n')
    r = run(5, 3, extra=["--sync-dir", str(tmp_path / "raw")], SYNC_SH=str(fakesync))
    assert r.returncode == 6 and rec.read_text().strip() == f"sess {tmp_path / 'raw'} 1 --once"


def test_cap_rejects_bad_thresholds(tmp_path):
    r = sh("cu_cap_i1001.sh", ["sess", "--b0", "100", "--t0", "1", "--soft", "90", "--hard", "70"])
    assert r.returncode == 2


# ── freeze_i1001：表的填寫與核對 ─────────────────────────────────────────────────────────────────

def mini_root(tmp_path):
    root = tmp_path / "root"
    for rel, body in {"vm/tui_cell.py": "a", "vm/launch_i1001.sh": "b", "scorers/code_suite.py": "c", "stub_model.py": "d",
                      "bridge/native_acceptance_bridge.py": "e", **{n: "x" + n for n in freeze.LOCAL_ONLY}}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return root


TABLE_DOC = f"head\n{freeze.TOOLS[0]}\n| 檔案 | sha256 |\n|---|---|\n| `vm/tui_cell.py` | `{freeze.PLACEHOLDER}` |\n{freeze.TOOLS[1]}\ntail\n"
STAGED_DOC = f"mid\n{freeze.STAGED[0]}\n{freeze.STAGED[1]}\n"          # fill 會整塊重寫，所以標記之間放什麼都可以


def mini_staged(tmp_path):
    st = tmp_path / "staged"
    for b in freeze.STAGED_BANKS:
        (st / b / "t1").mkdir(parents=True)
        (st / b / "t1" / "instruction.txt").write_text("i-" + b)
    for f in freeze.STAGED_FILES:
        (st / f).write_text("{}" + f)
    return st


def run_freeze(args):
    return subprocess.run([sys.executable, str(CI / "freeze_i1001.py"), *map(str, args)], capture_output=True, text=True)


def test_freeze_fill_then_check_roundtrip_and_tamper_detection(tmp_path):
    root = mini_root(tmp_path)
    wheel = tmp_path / "v.whl"
    wheel.write_bytes(b"wheel")
    doc = tmp_path / "prereg.md"
    doc.write_text(TABLE_DOC, encoding="utf-8")
    assert run_freeze(["--check", doc, "--root", root, "--wheel", wheel]).returncode == 1          # 沒填過＝不能發射
    r = run_freeze(["--fill", doc, "--root", root, "--wheel", wheel])
    assert r.returncode == 0, r.stdout + r.stderr
    text = doc.read_text(encoding="utf-8")
    assert text.startswith("head\n") and text.endswith("tail\n") and freeze.PLACEHOLDER not in text
    assert run_freeze(["--check", doc, "--root", root, "--wheel", wheel]).returncode == 0
    (root / "vm" / "tui_cell.py").write_text("changed")                                              # 負控制：改一個檔就要被抓
    r = run_freeze(["--check", doc, "--root", root, "--wheel", wheel])
    assert r.returncode == 1 and "vm/tui_cell.py: sha256 不同" in r.stdout
    (root / "vm" / "tui_cell.py").write_text("a")
    (root / "vm" / "extra.py").write_text("new file")                                                # 多一個檔、表上沒有
    r = run_freeze(["--check", doc, "--root", root, "--wheel", wheel])
    assert r.returncode == 1 and "vm/extra.py: 檔案在（清單／佈署）裡、表上沒有這一列" in r.stdout


def test_freeze_vm_mode_maps_the_deployed_layout_and_skips_local_only_rows(tmp_path):
    root, st = mini_root(tmp_path), mini_staged(tmp_path)
    wheel = tmp_path / "v.whl"
    wheel.write_bytes(b"wheel")
    doc = tmp_path / "prereg.md"
    doc.write_text(TABLE_DOC + STAGED_DOC, encoding="utf-8")
    assert run_freeze(["--fill", doc, "--root", root, "--wheel", wheel, "--staged", st]).returncode == 0
    vm_bin, vm_bridge, vm_wheels = tmp_path / "bin", tmp_path / "bridge", tmp_path / "wheel"
    for rel, dst in (("vm/tui_cell.py", vm_bin / "tui_cell.py"), ("vm/launch_i1001.sh", vm_bin / "launch_i1001.sh"),
                     ("scorers/code_suite.py", vm_bin / "scorers" / "code_suite.py"), ("stub_model.py", vm_bin / "stub_model.py"),
                     ("bridge/native_acceptance_bridge.py", vm_bridge / "native_acceptance_bridge.py")):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((root / rel).read_bytes())
    vm_wheels.mkdir()
    (vm_wheels / "v.whl").write_bytes(b"wheel")
    base = ["--check", doc, "--root", root, "--vm", "--vm-bin", vm_bin, "--vm-bridge", vm_bridge, "--vm-wheel-dir", vm_wheels, "--staged", st]
    r = run_freeze(base)
    assert r.returncode == 0, r.stdout + r.stderr
    (vm_bin / "tui_cell.py").write_text("tampered on the VM")
    r = run_freeze(base)
    assert r.returncode == 1 and "vm/tui_cell.py: sha256 不同" in r.stdout
    (vm_bin / "tui_cell.py").write_text("a")
    (vm_wheels / "v.whl").write_bytes(b"another wheel")
    assert run_freeze(base).returncode == 1
    (vm_wheels / "v.whl").write_bytes(b"wheel")
    (vm_bin / "sneaked_in.py").write_text("not in the frozen table")                                 # 佈署了表上沒有的檔也要被抓
    r = run_freeze(base)
    assert r.returncode == 1 and "vm/sneaked_in.py: 檔案在（清單／佈署）裡、表上沒有這一列" in r.stdout
    (vm_bin / "sneaked_in.py").unlink()
    (vm_bin / "__pycache__").mkdir()
    (vm_bin / "__pycache__" / "x.pyc").write_bytes(b"\0")                                           # 執行後出現的 __pycache__ 不算
    assert run_freeze(base).returncode == 0
    (vm_bin / "launch_i1001.sh").unlink()                                                            # 少一個檔
    r = run_freeze(base)
    assert r.returncode == 1 and "vm/launch_i1001.sh: 表上有、這個環境找不到這個檔" in r.stdout


def test_wheel_vs_git_comparison_names_differing_and_missing_files(tmp_path):
    import zipfile
    w = tmp_path / "w.whl"
    with zipfile.ZipFile(w, "w") as z:
        z.writestr("vacant_network/a.py", "A")
        z.writestr("vacant_network/b.py", "changed")
        z.writestr("vacant_network/__pycache__/a.pyc", "ignored")
        z.writestr("vacant_network-0.8.0.dist-info/METADATA", "not part of the package tree")
    tree = {"vacant_network/a.py": b"A", "vacant_network/b.py": b"B", "vacant_network/c.py": b"C"}
    res = freeze.wheel_mismatches(w, tree)
    assert res == {"wheel": 2, "git": 3, "differ": ["vacant_network/b.py"], "missing_in_wheel": ["vacant_network/c.py"]}
    same = freeze.wheel_mismatches(w, {"vacant_network/a.py": b"A", "vacant_network/b.py": b"changed"})
    assert not same["differ"] and not same["missing_in_wheel"]


def test_freeze_tree_sha_is_the_same_algorithm_as_launch_record(tmp_path):
    spec = importlib.util.spec_from_file_location("launch_record_i1001", CI / "vm" / "launch_record.py")
    lr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lr)
    st = mini_staged(tmp_path)
    for b in freeze.STAGED_BANKS:
        assert freeze.tree_sha(st / b) == lr.tree(st / b)


def test_freeze_staged_table_fill_check_and_tamper(tmp_path):
    root, st = mini_root(tmp_path), mini_staged(tmp_path)
    wheel = tmp_path / "v.whl"
    wheel.write_bytes(b"wheel")
    doc = tmp_path / "prereg.md"
    doc.write_text(TABLE_DOC + STAGED_DOC, encoding="utf-8")
    r = run_freeze(["--fill", doc, "--root", root, "--wheel", wheel, "--staged", st])
    assert r.returncode == 0, r.stdout + r.stderr
    text = doc.read_text(encoding="utf-8")
    assert freeze.PLACEHOLDER not in text and set(freeze.parse_table(text, freeze.STAGED)) == set(freeze.STAGED_BANKS) | set(freeze.STAGED_FILES)
    ok = ["--check", doc, "--root", root, "--wheel", wheel, "--staged", st]
    assert run_freeze(ok).returncode == 0
    (st / "dabench" / "t1" / "instruction.txt").write_text("someone edited a task")                  # 負控制：改一題的內容
    r = run_freeze(ok)
    assert r.returncode == 1 and "staged/dabench: sha256 不同" in r.stdout
    (st / "dabench" / "t1" / "instruction.txt").write_text("i-dabench")
    (st / "MANIFEST.json").write_text("changed")
    assert "staged/MANIFEST.json: sha256 不同" in run_freeze(ok).stdout


def test_freeze_check_also_catches_a_hand_filled_placeholder_outside_the_tables(tmp_path):
    root = mini_root(tmp_path)
    wheel = tmp_path / "v.whl"
    wheel.write_bytes(b"wheel")
    doc = tmp_path / "prereg.md"
    doc.write_text(TABLE_DOC + f"\n| Vacant | 來源 commit `{freeze.PLACEHOLDER}` |\n", encoding="utf-8")
    r = run_freeze(["--fill", doc, "--root", root, "--wheel", wheel])
    assert r.returncode == 0 and "1 placeholder(s) outside the tables" in r.stdout
    r = run_freeze(["--check", doc, "--root", root, "--wheel", wheel])
    assert r.returncode == 1 and "表以外還有沒填的占位字" in r.stdout
    doc.write_text(doc.read_text(encoding="utf-8").replace(freeze.PLACEHOLDER, "abc1234"), encoding="utf-8")
    assert run_freeze(["--check", doc, "--root", root, "--wheel", wheel]).returncode == 0


def test_freeze_missing_markers_is_an_error(tmp_path):
    doc = tmp_path / "p.md"
    doc.write_text("no markers here")
    assert run_freeze(["--check", doc]).returncode != 0


# ── 預註冊／RUNBOOK 與檔案的一致性 ────────────────────────────────────────────────────────────────

def test_prereg_tables_list_exactly_the_files_and_banks_we_ship():
    text = PREREG.read_text(encoding="utf-8")
    table = freeze.parse_table(text, freeze.TOOLS)
    actual = freeze.repo_files(CI) + [freeze.WHEEL_ROW]
    assert sorted(table) == sorted(actual), (set(table) ^ set(actual))
    staged = freeze.parse_table(text, freeze.STAGED)
    assert sorted(staged) == sorted(set(freeze.STAGED_BANKS) | set(freeze.STAGED_FILES))
    assert all(v == freeze.PLACEHOLDER or re.fullmatch(r"[0-9a-f]{64}", v) for v in [*table.values(), *staged.values()])


def _doc_files(text):
    toks = set(re.findall(r"[\w./-]*_i1001\.(?:sh|py)", text)) | set(re.findall(r"\bvm/[\w]+\.(?:py|sh)\b", text))
    return sorted(t for t in toks if not t.startswith(("/", "~")))


@pytest.mark.parametrize("doc", [PREREG, RUNBOOK], ids=["prereg", "runbook"])
def test_every_i1001_tool_named_in_the_docs_exists(doc):
    for name in _doc_files(doc.read_text(encoding="utf-8")):
        base = pathlib.PurePosixPath(name).name
        assert any((CI / d / base).is_file() for d in (".", "vm")), f"{doc.name} names {name} but no such file"


def test_runbook_mentions_every_new_helper_and_the_turn_off_checkpoints():
    text = RUNBOOK.read_text(encoding="utf-8")
    for needle in ("vmsh_i1001.sh", "vllm_up_i1001.sh", "cu_cap_i1001.sh", "freeze_i1001.py", "autostop_i1001.sh", "sync_i1001.sh",
                   "colab stop", "colab usage", "colab drivemount", "launch_i1001.sh"):
        assert needle in text, needle


def test_prereg_and_runbook_agree_on_the_cap_numbers():
    pre, run = PREREG.read_text(encoding="utf-8"), RUNBOOK.read_text(encoding="utf-8")
    soft, hard = (re.search(rf"{k}\s*[＝=]\s*(\d+)\s*CU", pre) for k in ("軟上限", "硬上限"))
    assert soft and hard, "prereg 要寫『軟上限＝<數字> CU』與『硬上限＝<數字> CU』"
    assert f"--soft {soft.group(1)}" in run and f"--hard {hard.group(1)}" in run
