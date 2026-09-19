#!/usr/bin/env python3
"""這支在架構裡承重什麼：R534 的**零容忍預檢**——不過就拒跑。

為什麼需要一支專門的預檢，而不是「跑跑看有問題再說」：R534 有四格，
而四格裡最容易出事的失敗方式不是「整個炸掉」，是**一部分安靜地失效**——
`reasoning_effort` 沒送到、沙箱退到沒有隔離的後端、`hidden/` 在沙箱裡看得見、
題庫在磁碟上漂了一個位元組。這幾種失敗都不會讓行程掛掉，它們只會讓你拿到
一批**看起來很正常**的數字，而那批數字說的不是你以為的那件事。

所以這一支的立場是：**每一條都要有實測證據，任何一條紅就 rc=1，不給旗標繞過。**
（`--json` 只決定把結果寫到哪，不影響判準；沒有 `--force`，故意的。）

檢查清單（每一條都附實跑證據，寫進 `preflight.json`）：

  P1  node / pi 裝好了，版本落盤
  P2  題庫沒漂：`build_bank.py --check` 為真、`bank_manifest.sha256` 對得上、
      `lcb_bank_v2.jsonl` 的 sha256 對得上
  P2b 樣板與計分樹逐檔逐 sha256 對得上 manifest，**而且一個多的檔案都沒有**
      （macOS 送檔案留下的 `._*` 就是這樣混進工作區的）
  P3  紅線：`templates/` 底下沒有任何一個檔案出現 `hidden` 字樣
  P4  沙箱後端起得來，而且**三條隔離實測為真**：無網路、寫不出界、
      repo（裡面有 `hidden/`）在沙箱的檔案系統裡不存在
  P5  sidecar 的 unix socket 在這台機器上通得了（`ping` ＋ `hello`）
  P6  端點層：兩台後端 `/v1/models` 有那個模型；**直打**一次確認
      不帶旗標 ⇒ `reasoning_tokens > 0`（think 格）、
      帶 `reasoning_effort:"none"` ⇒ `== 0`（nothink 格）
  P7  wire tap 這條路通得了，而且**真的把 bytes 寫下來了**（逐字落盤的底座）
  P9  閘門本身會不會擋：`gate_selftest.py` 的六條（nudge／回饋／通過／拒交／
      plain 連錯的解也照收／收據鏈 verify）——零模型呼叫
  P8  pi 這一層：用**這一次要用的那一份 models.json**，每一格各跑一次
      最小呼叫，從 tap 的 JSONL 讀回 wire 上到底有沒有 `reasoning_effort`、
      以及 `usage.completion_tokens_details.reasoning_tokens` 是不是預期值

⚠ P6 與 P8 是兩件事，不可以只做一件：P6 證明**端點**會那樣反應，
  P8 證明**我們的設定真的把那個旗標送到了 wire 上**。
  只做 P6 就會發生「端點沒問題、pi 的設定沒生效、四格其實是兩格」。

⚠ 誠實邊界：預檢證明的是「**發射前那一刻**這些條件成立」。它不保證整批跑完
  的每一秒都成立——那由 wire tap 的逐筆紀錄與擴充的逐通斷言接手
  （`pi_ext/vacant_gate.ts` 的 `before_provider_request` 一通不對就作廢那一格）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from ops.gain.r530.sandbox import make_sandbox  # noqa: E402
from ops.gain.r530.wshash import EXCLUDED_DIRS  # noqa: E402
from ops.gain.r534 import piarms  # noqa: E402

NODE_BIN_DEFAULT = os.path.expanduser(
    "~/.local/opt/node-v22.23.2-linux-x64/bin")
TEMPLATES = os.path.join(HERE, "templates")
HIDDEN = os.path.join(HERE, "hidden")
MANIFEST = os.path.join(HERE, "bank_manifest.json")
MANIFEST_SHA = os.path.join(HERE, "bank_manifest.sha256")


def _sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(results: list[dict], cid: str, ok: bool, detail: dict) -> bool:
    results.append({"id": cid, "ok": bool(ok), **detail})
    return bool(ok)


# ══ P1 ═══════════════════════════════════════════════════════════════════
def p1_toolchain(results: list[dict], node_bin: str) -> bool:
    env = dict(os.environ)
    env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    out = {}
    ok = True
    for name, argv in (("node", ["node", "-v"]), ("npm", ["npm", "-v"]),
                       ("pi", ["pi", "--version"])):
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=120, env=env)
            out[name] = (r.stdout or r.stderr).strip()
            ok = ok and r.returncode == 0
        except Exception as exc:                        # noqa: BLE001
            out[name] = f"ERR {exc!r}"
            ok = False
    ext = os.path.join(HERE, "pi_ext", "vacant_gate.ts")
    out["extension"] = ext
    out["extension_sha256"] = _sha256_file(ext) if os.path.exists(ext) else None
    ok = ok and out["extension_sha256"] is not None
    return _check(results, "P1_toolchain", ok, {"versions": out})


# ══ P2 ═══════════════════════════════════════════════════════════════════
def p2_bank(results: list[dict]) -> bool:
    detail: dict = {}
    ok = True
    for p in (MANIFEST, MANIFEST_SHA):
        if not os.path.exists(p):
            return _check(results, "P2_bank", False, {"missing": p})
    detail["bank_manifest_sha256"] = _sha256_file(MANIFEST)
    detail["bank_manifest_sha256_file"] = \
        open(MANIFEST_SHA, encoding="utf-8").read().split()[0]
    ok = ok and detail["bank_manifest_sha256"] == detail["bank_manifest_sha256_file"]
    r = subprocess.run([sys.executable, os.path.join(HERE, "build_bank.py"),
                        "--check"], capture_output=True, text=True, timeout=600)
    detail["build_bank_check_rc"] = r.returncode
    detail["build_bank_check_tail"] = (r.stdout or "")[-800:] + (r.stderr or "")[-800:]
    ok = ok and r.returncode == 0
    return _check(results, "P2_bank", ok, detail)


# ══ P2b ══════════════════════════════════════════════════════════════════
def p2b_tree_exact(results: list[dict]) -> bool:
    """樣板與計分樹**逐檔逐 sha256 對得上 manifest，而且一個多的都不准有**。

    為什麼「多的也不准」是硬需求而不是潔癖（2026-09-18 實測抓到的）：
    從 macOS 用 `tar` 把 `templates/` 送過來，會在對端留下一堆 AppleDouble
    `._goal.md`／`._tests_visible` 之類的檔案。它們
      · 會出現在 agent 看得到的檔案清單裡（`_tree_listing` 逐檔列出來），
      · 會進起點樹雜湊 ⇒ 每台機器複製出來的「同一份樣板」其實不同，
      · 而 `build_bank.py --check` 只驗它自己寫出來的那幾個檔案，**看不見多的**。
    三件事合起來就是一批看起來正常、其實 prompt 不同的資料。
    （治本：送檔案時用 `COPYFILE_DISABLE=1 tar …`。這一條是擋門。）
    """
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    bad: list[dict] = []

    def _files(root: pathlib.Path) -> dict[str, str]:
        # `__pycache__`／`.pytest_cache`／`.git` 用 `wshash.EXCLUDED_DIRS`
        # 那一份定義排除——**同一個集合**，不另外抄一份。它們進不了樹雜湊，
        # 也不進 agent 看到的檔案清單（`_tree_listing` 走的就是 `tree_leaves`），
        # 所以它們在這裡不算漂移；`._*` 那種東西**會**進，所以會被抓到。
        out: dict[str, str] = {}
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root)
            if set(rel.parts) & EXCLUDED_DIRS:
                continue
            out[rel.as_posix()] = _sha256_file(p)
        return out
    for task_id, meta in manifest["tasks"].items():
        want = dict(meta["sha256"])
        hid_key = f"hidden/{task_id}/test_hidden.py"
        hid_want = want.pop(hid_key, None)
        tpl = pathlib.Path(TEMPLATES) / task_id
        got = _files(tpl)
        extra = sorted(set(got) - set(want))
        missing = sorted(set(want) - set(got))
        drift = sorted(k for k in set(got) & set(want) if got[k] != want[k])
        hid = pathlib.Path(HIDDEN) / task_id / "test_hidden.py"
        hid_got = _sha256_file(hid) if hid.exists() else None
        hid_extra = sorted(k for k in _files(pathlib.Path(HIDDEN) / task_id)
                           if k != "test_hidden.py")
        if extra or missing or drift or hid_got != hid_want or hid_extra:
            bad.append({"task_id": task_id, "extra": extra, "missing": missing,
                        "drift": drift, "hidden_ok": hid_got == hid_want,
                        "hidden_extra": hid_extra})
    return _check(results, "P2b_tree_exact", not bad,
                  {"tasks_n": len(manifest["tasks"]), "bad": bad[:10],
                   "bad_n": len(bad)})


# ══ P3 ═══════════════════════════════════════════════════════════════════
def p3_red_line(results: list[dict]) -> bool:
    """樣板裡不准出現 `hidden` 字樣——紅線的可執行版本。"""
    hits: list[str] = []
    for root, _dirs, files in os.walk(TEMPLATES):
        for name in files:
            p = os.path.join(root, name)
            try:
                raw = open(p, "rb").read().decode("utf-8", errors="replace")
            except OSError:
                continue
            if "hidden" in raw.lower() or "hidden" in name.lower():
                hits.append(os.path.relpath(p, HERE))
    n_tpl = len([d for d in os.listdir(TEMPLATES)
                 if os.path.isdir(os.path.join(TEMPLATES, d))])
    n_hid = len([d for d in os.listdir(HIDDEN)
                 if os.path.isdir(os.path.join(HIDDEN, d))])
    return _check(results, "P3_red_line", not hits and n_tpl == n_hid > 0,
                  {"hits": hits, "templates_n": n_tpl, "hidden_n": n_hid})


# ══ P4 ═══════════════════════════════════════════════════════════════════
def p4_sandbox(results: list[dict], backend: str) -> tuple[bool, dict]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="r534_probe_"))
    try:
        sb, meta = make_sandbox(backend, workdir=str(tmp / "ws"))
    except SystemExit as exc:
        _check(results, "P4_sandbox", False, {"error": str(exc)})
        return False, {}
    need = ("network_isolated", "write_confined", "repo_hidden_from_sandbox")
    ok = all(meta.get(k) is True for k in need)
    _check(results, "P4_sandbox", ok,
           {"backend": meta.get("backend"), "requested": backend,
            "checks": {k: meta.get(k) for k in need}, "meta": meta})
    shutil.rmtree(tmp, ignore_errors=True)
    return ok, meta


# ══ P5 ═══════════════════════════════════════════════════════════════════
def p5_sidecar(results: list[dict], sock_dir: str) -> bool:
    r = subprocess.run([sys.executable, os.path.join(HERE, "sidecar.py")],
                       capture_output=True, text=True, timeout=180)
    return _check(results, "P5_sidecar", r.returncode == 0,
                  {"rc": r.returncode,
                   "stdout": (r.stdout or "")[-1200:],
                   "stderr": (r.stderr or "")[-800:],
                   "sock_dir": sock_dir,
                   "sock_dir_len": len(sock_dir)})


# ══ P6 ═══════════════════════════════════════════════════════════════════
def _chat(base: str, extra: dict, timeout: int = 300) -> dict:
    body = {"model": piarms.MODEL_ID,
            "messages": [{"role": "user",
                          "content": "Reply with the single word OK."}],
            "max_completion_tokens": 64, "stream": False}
    body.update(extra)
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer lmstudio"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _reasoning_tokens(resp: dict) -> int | None:
    u = resp.get("usage") or {}
    det = u.get("completion_tokens_details") or {}
    v = det.get("reasoning_tokens", u.get("reasoning_tokens"))
    return None if v is None else int(v)


def p6_endpoints(results: list[dict], upstream: str) -> bool:
    base = piarms.UPSTREAM[upstream]
    detail: dict = {"upstream": upstream, "base": base}
    ok = True
    try:
        req = urllib.request.Request(base.rstrip("/") + "/v1/models",
                                     headers={"Authorization": "Bearer lmstudio"})
        with urllib.request.urlopen(req, timeout=60) as r:
            ids = [m.get("id") for m in (json.loads(r.read()).get("data") or [])]
        detail["models"] = ids
        ok = ok and piarms.MODEL_ID in ids
    except Exception as exc:                            # noqa: BLE001
        detail["models_error"] = repr(exc)
        ok = False
    for label, extra, want in (("think", {}, "gt0"),
                               ("nothink", {"reasoning_effort": "none"}, "eq0")):
        try:
            resp = _chat(base, extra)
            rt = _reasoning_tokens(resp)
            detail[label] = {"reasoning_tokens": rt, "usage": resp.get("usage")}
            good = (rt is not None and rt > 0) if want == "gt0" else (rt == 0)
            detail[label]["expected"] = want
            detail[label]["ok"] = good
            ok = ok and good
        except Exception as exc:                        # noqa: BLE001
            detail[label] = {"error": repr(exc), "ok": False}
            ok = False
    return _check(results, "P6_endpoints", ok, detail)


# ══ P9 ═══════════════════════════════════════════════════════════════════
def p9_gate(results: list[dict]) -> bool:
    """閘門本身會不會擋——`gate_selftest.py` 的六條，零模型呼叫。

    只量端點與沙箱、不量閘門，就會發生「基建全綠、閘門其實沒在擋」。
    """
    r = subprocess.run([sys.executable, os.path.join(HERE, "gate_selftest.py")],
                       capture_output=True, text=True, timeout=900)
    tail = (r.stdout or "")[-4000:]
    return _check(results, "P9_gate_selftest", r.returncode == 0,
                  {"rc": r.returncode, "stdout_tail": tail,
                   "stderr_tail": (r.stderr or "")[-800:]})


# ══ P7 / P8 ══════════════════════════════════════════════════════════════
class _Tap:
    """預檢用的臨時 wire tap（正式跑由 driver 起，用的是同一支程式）。"""

    def __init__(self, port: int, upstream: str, log: str) -> None:
        self.port, self.upstream, self.log = port, upstream, log
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> "_Tap":
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "wire_tap.py"),
             "--listen", f"127.0.0.1:{self.port}",
             "--upstream", self.upstream, "--log", self.log],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", self.port), 0.3):
                    return self
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"wire tap 沒起來（port {self.port}）")

    def __exit__(self, *exc) -> None:
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def p7_wiretap(results: list[dict], upstream: str, port: int,
               workdir: pathlib.Path) -> bool:
    base = piarms.UPSTREAM[upstream]
    log = str(workdir / "preflight_wire_p7.jsonl")
    detail: dict = {"port": port, "log": log}
    try:
        with _Tap(port, base, log):
            resp = _chat(f"http://127.0.0.1:{port}", {})
        detail["reasoning_tokens"] = _reasoning_tokens(resp)
        lines = [json.loads(l) for l in open(log, encoding="utf-8")
                 if l.strip()]
        detail["records"] = len(lines)
        dirs = sorted({l.get("dir") for l in lines})
        detail["dirs"] = dirs
        body_ok = any(l.get("dir") == "request" and piarms.MODEL_ID in (l.get("body") or "")
                      for l in lines)
        detail["request_body_verbatim"] = body_ok
        ok = len(lines) >= 2 and dirs == ["request", "response"] and body_ok
    except Exception as exc:                            # noqa: BLE001
        detail["error"] = repr(exc)
        ok = False
    return _check(results, "P7_wiretap", ok, detail)


def p8_pi_wire(results: list[dict], *, node_bin: str, pi_conf_dir: str,
               upstream: str, tap_ports: dict[str, int], workdir: pathlib.Path,
               cells: tuple[str, ...]) -> bool:
    """**最重要的一條**：用這一次真的要用的 models.json，量 wire 上的旗標。

    每一格跑一次最小的 pi 呼叫（`--no-tools`，一句話），然後從 tap 的 JSONL
    讀回：wire 上有沒有 `reasoning_effort`、`reasoning_tokens` 是不是預期值。
    只做 P6 不做這一條，就會發生「端點沒問題、pi 的設定沒生效、四格其實是兩格」。
    """
    env = dict(os.environ)
    env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    env["PI_CODING_AGENT_DIR"] = pi_conf_dir
    base = piarms.UPSTREAM[upstream]
    all_ok = True
    per_cell: dict = {}
    for cell in cells:
        want_none = not piarms.CELLS[cell]["think"]
        # **必須是 models.json 裡那一個埠**：這兩邊一旦不同，pi 會連到沒有人
        # 在聽的地方、自己重試三次、然後 rc=0 安靜退出——看起來像跑過了。
        port = tap_ports[cell]
        log = str(workdir / f"preflight_wire_{cell}.jsonl")
        cwd = workdir / f"pi_{cell}"
        cwd.mkdir(parents=True, exist_ok=True)
        rec: dict = {"port": port, "log": log, "want_reasoning_effort_none": want_none}
        try:
            with _Tap(port, base, log):
                r = subprocess.run(
                    ["pi", "--model", f"r534_{cell.lower()}/{piarms.MODEL_ID}",
                     "--mode", "json", "-p", "Reply with the single word OK.",
                     "--no-tools", "--no-context-files", "--no-extensions",
                     "--no-skills", "--no-prompt-templates", "--no-themes",
                     "--no-approve", "--no-session", "--offline"],
                    capture_output=True, text=True, timeout=600, env=env,
                    cwd=str(cwd), stdin=subprocess.DEVNULL)
            rec["pi_rc"] = r.returncode
            rec["pi_stderr_tail"] = (r.stderr or "")[-600:]
            # pi 連不上時會自己重試三次然後 **rc=0** 退出 ⇒ rc 不足以判斷成敗。
            rec["provider_error"] = "Connection error." in (r.stdout or "")
            rec["pi_stdout_tail"] = (r.stdout or "")[-800:]
            lines = [json.loads(l) for l in open(log, encoding="utf-8") if l.strip()]
            reqs = [json.loads(l["body"]) for l in lines
                    if l.get("dir") == "request" and (l.get("body") or "").strip().startswith("{")]
            rec["requests_n"] = len(reqs)
            has = [("reasoning_effort" in b) for b in reqs]
            vals = [b.get("reasoning_effort", "<absent>") for b in reqs]
            rec["reasoning_effort_on_wire"] = vals
            rec["model_on_wire"] = sorted({b.get("model") for b in reqs})
            flag_ok = (all(v == "none" for v in vals) if want_none
                       else (len(has) > 0 and not any(has)))
            # usage 從 SSE 串流的最後一段裡撈（`stream_options.include_usage`）
            rt: int | None = None
            for line in lines:
                if line.get("dir") != "response":
                    continue
                for chunk in (line.get("body") or "").split("\n"):
                    chunk = chunk.strip()
                    if not chunk.startswith("data: ") or chunk.endswith("[DONE]"):
                        continue
                    try:
                        d = json.loads(chunk[6:])
                    except ValueError:
                        continue
                    got = _reasoning_tokens(d)
                    if got is not None:
                        rt = got
            rec["reasoning_tokens"] = rt
            token_ok = (rt == 0) if want_none else (rt is None or rt > 0)
            rec["flag_ok"] = flag_ok
            rec["token_ok"] = token_ok
            rec["ok"] = bool(r.returncode == 0 and len(reqs) > 0 and flag_ok
                             and token_ok and not rec["provider_error"])
        except Exception as exc:                        # noqa: BLE001
            rec["error"] = repr(exc)
            rec["ok"] = False
        per_cell[cell] = rec
        all_ok = all_ok and rec["ok"]
    return _check(results, "P8_pi_wire", all_ok, {"cells": per_cell})


# ══ models.json ══════════════════════════════════════════════════════════
def build_models_json(upstream_think: str, upstream_nothink: str,
                      tap_ports: dict[str, int]) -> dict:
    """四格各一個 provider，**旗標的有無是 provider 之間唯一的差別**。

    `compat.supportsReasoningEffort:false` 讓 pi **自己永遠不送**
    `reasoning_effort` ⇒ 這個欄位在 wire 上的有無 100% 由
    `samplingParams` 決定（`--thinking` 旗標完全不介入）。
    `samplingParams` 是「原樣 merge 進每一個 request body」的自由物件。
    """
    providers: dict = {}
    for cell, cfg in piarms.CELLS.items():
        name = f"r534_{cell.lower()}"
        model: dict = {"id": piarms.MODEL_ID,
                       "name": f"{piarms.MODEL_ID}-{cell}",
                       "contextWindow": 262144, "maxTokens": 16384}
        if not cfg["think"]:
            model["samplingParams"] = {"reasoning_effort": "none"}
        providers[name] = {
            "baseUrl": f"http://127.0.0.1:{tap_ports[cell]}/v1",
            "api": "openai-completions",
            "apiKey": "lmstudio",
            "compat": {"supportsDeveloperRole": False,
                       "supportsReasoningEffort": False},
            "models": [model],
        }
    return {"providers": providers}


def write_pi_conf(pi_conf_dir: str | os.PathLike, tap_ports: dict[str, int],
                  upstream_think: str, upstream_nothink: str) -> dict:
    """把一份**跑完就丟**的 pi 設定目錄寫出來（`PI_CODING_AGENT_DIR`）。

    為什麼不用 `~/.pi/agent`：那裡有使用者自己的 provider、擴充、skills。
    用它等於讓「這台機器當時裝了什麼」變成量到的東西的一部分。
    """
    d = pathlib.Path(pi_conf_dir)
    d.mkdir(parents=True, exist_ok=True)
    models = build_models_json(upstream_think, upstream_nothink, tap_ports)
    (d / "models.json").write_text(
        json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (d / "settings.json").write_text(
        json.dumps({"extensions": [], "quietStartup": True},
                   ensure_ascii=False) + "\n", encoding="utf-8")
    if not (d / "auth.json").exists():
        (d / "auth.json").write_text("{}\n", encoding="utf-8")
    (d / "extensions").mkdir(exist_ok=True)
    return models


# ══ 主流程 ═══════════════════════════════════════════════════════════════
def run(*, node_bin: str, backend: str, upstream: str, base_port: int,
        workdir: pathlib.Path, cells: tuple[str, ...],
        skip_pi: bool = False) -> dict:
    results: list[dict] = []
    workdir.mkdir(parents=True, exist_ok=True)
    tap_ports = {c: base_port + piarms.TAP_PORTS[c] - min(piarms.TAP_PORTS.values())
                 for c in piarms.CELL_ORDER}
    pi_conf = workdir / "piconf"
    models = write_pi_conf(pi_conf, tap_ports, upstream, upstream)

    p1_toolchain(results, node_bin)
    p2_bank(results)
    p2b_tree_exact(results)
    p3_red_line(results)
    sb_ok, sb_meta = p4_sandbox(results, backend)
    p5_sidecar(results, str(workdir / "s"))
    p9_gate(results)
    p6_endpoints(results, upstream)
    p7_wiretap(results, upstream, base_port + 90, workdir)
    if skip_pi:
        _check(results, "P8_pi_wire", False,
               {"skipped": True,
                "why": "--skip-pi 只給偵錯用；正式跑這一條必須真的量過"})
    else:
        p8_pi_wire(results, node_bin=node_bin, pi_conf_dir=str(pi_conf),
                   upstream=upstream, tap_ports=tap_ports,
                   workdir=workdir, cells=cells)

    ok = all(r["ok"] for r in results)
    return {
        "ok": ok,
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": socket.gethostname(),
        "upstream": upstream,
        "upstream_base": piarms.UPSTREAM[upstream],
        "cells": list(cells),
        "tap_ports": tap_ports,
        "sandbox_meta": sb_meta,
        "models_json": models,
        "checks": results,
        "honest_bound": ("預檢證明的是發射前那一刻這些條件成立，"
                         "不保證整批跑完的每一秒都成立——那由 wire tap 的逐筆紀錄"
                         "與擴充的逐通斷言接手。"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="R534 零容忍預檢（不過就拒跑；沒有 --force）")
    ap.add_argument("--node-bin", default=NODE_BIN_DEFAULT)
    ap.add_argument("--backend", default="bwrap",
                    choices=["auto", "bwrap", "unshare", "none"])
    ap.add_argument("--upstream", default="1003", choices=sorted(piarms.UPSTREAM))
    ap.add_argument("--base-port", type=int, default=8541)
    ap.add_argument("--workdir", default=None,
                    help="預檢產物放哪（預設開一個暫存目錄）")
    ap.add_argument("--cells", default=",".join(piarms.CELL_ORDER))
    ap.add_argument("--json", default=None, help="把結果寫到這個檔案")
    ap.add_argument("--skip-pi", action="store_true",
                    help="跳過 P8（**只給偵錯**；正式跑一定要量）")
    args = ap.parse_args(argv)

    workdir = pathlib.Path(args.workdir or tempfile.mkdtemp(prefix="r534_pre_"))
    cells = tuple(c.strip() for c in args.cells.split(",") if c.strip())
    bad = [c for c in cells if c not in piarms.CELLS]
    if bad:
        raise SystemExit(f"未知的格：{bad}（可用 {piarms.CELL_ORDER}）")

    rec = run(node_bin=args.node_bin, backend=args.backend,
              upstream=args.upstream, base_port=args.base_port,
              workdir=workdir, cells=cells, skip_pi=args.skip_pi)
    rec["workdir"] = str(workdir)
    blob = json.dumps(rec, ensure_ascii=False, indent=2)
    if args.json:
        pathlib.Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json).write_text(blob + "\n", encoding="utf-8")
    for c in rec["checks"]:
        print(f"{'OK  ' if c['ok'] else 'FAIL'}  {c['id']}")
    print(f"workdir={workdir}")
    print("PREFLIGHT " + ("OK" if rec["ok"] else "FAILED — 拒跑"))
    if not rec["ok"] and not args.json:
        print(blob)
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
