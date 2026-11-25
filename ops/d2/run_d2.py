#!/usr/bin/env python3
"""D2′ 執行器：同一份初稿，四種維護方式各跑三個週期，逐宣稱配對。

每一組來源（set）：
  c0   agent 依來源填好 report.md（掛 Vacant 的 pi 擴充，病歷記在 `vh/`）。工作區＋病歷封存成快照。
  臂   依計畫的臂序（每組洗牌），每一臂都從 c0 快照還原到**同一個路徑**（病歷的專案鍵＝路徑雜湊，
       所以四臂接的是同一條鏈的同一個前綴），然後跑週期 1..3：網站換成第 k 週期的版本，再
         a  不維護
         b  整份重查：叫 agent 對所有頁面重查每一條
         c  出處重查：`vacant trace sources report.md --check`（產品指令、0 token）列出來源變了的行，
            只把那幾行交給 agent；來源沒記到的行也一起交（附上全部頁面網址）
         d  頁面通知（秘書版 changedetection）：Vacant 這一側比對整組頁面的雜湊，只告訴 agent 哪幾頁變了，
            不給宣稱對應
       每週期結束：存 report.md、用量、agent 日誌、病歷的鏈長。臂結束：整個工作區＋病歷封存。
同一組的臂依序跑（同一個路徑），不同組平行（`jobs`）。

用法：run_d2.py run --plan ops/d2/plans/<計畫>.json --root <輸出目錄>
     run_d2.py selftest      （假 agent，不碰模型）
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import random
import shutil
import signal
import subprocess
import sys
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "ops" / "redo"))
from redo import usage_from_log  # noqa: E402

HOST_FMT = "{set}.d2-sources.example"
LOCK = threading.Lock()
#: 只有 `*.d2-sources.example` 走來源伺服器；模型端點（LM Studio）與本機一律直連
NO_PROXY = "localhost,127.0.0.1,100.119.113.56,100.86.226.21"
#: Claude Code 額外直連 Anthropic API 與 claude.ai（僅設 http_proxy，HTTPS 不走來源伺服器）
CLAUDE_NO_PROXY = NO_PROXY + ",api.anthropic.com,.anthropic.com,claude.ai,.claude.ai,platform.claude.com"
#: Claude Code 允許的工具（自動放行，避免 -p 下卡權限詢問）與禁止的內建抓頁工具（強制用 curl 走 http_proxy）
CLAUDE_ALLOWED_TOOLS = "Bash,Edit,Write,Read,Glob,Grep"
CLAUDE_DISALLOWED_TOOLS = "WebFetch,WebSearch"


class InfraError(RuntimeError):
    """基礎設施失敗（0 次成功的模型回應＋連線錯誤）：不算一次執行；這一組停下，續跑時從頭重做沒完成的部分。"""


def usage_from_claude_log(log_path: pathlib.Path) -> dict | None:
    """解析 `claude -p --output-format stream-json --verbose`（亦相容單筆 `--output-format json`）的用量。

    呼叫數口徑：
    - `stream-json` 下，同一通模型 API 回應若含多個 content block（如平行工具呼叫），Claude Code 會輸出
      多筆同 `message.id` 的 `type="assistant"` 事件，而 `result.num_turns` 計的是回合／區塊數而非 API 呼叫數。
      因此以非錯誤、非 `<synthetic>` 的 `assistant` 事件之不重複 `message.id` 計 `calls`（精確 API 呼叫數）；
      若 log 只有單筆 `result`（`--output-format json`），才退回 `result.num_turns`（僅非錯誤且有實際用量時）。
    - token 總計優先取最終 `type="result"` 的 `usage`（含 `message_delta` 結算後的精確 `output_tokens` 與
      `cache_creation_input_tokens`／`cache_read_input_tokens`）；若行程逾時未印出 `result`，退回加總各
      不重複 `message.id` 最後看到的 `message.usage`。
    - 錯誤（`is_api_error_message`、`error`、`api_error`、`model=="<synthetic>"` 或 `result.is_error`）計入
      `errors` 並留 `final_error`，讓上層套用與 pi 相同的基礎設施失敗判定（0 次成功回應＋錯誤 ⇒ InfraError）。
    """
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    saw_json = False
    saw_assistant = False
    msg_usage: dict[str, dict] = {}
    err_ids: set[str] = set()
    errors = 0
    final_error: str | None = None
    result_obj: dict | None = None
    for idx, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict) or "type" not in obj:
            continue
        saw_json = True
        etype = obj.get("type")
        if etype == "assistant":
            saw_assistant = True
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            is_err = bool(obj.get("is_api_error_message") or obj.get("error")
                          or obj.get("api_error") or msg.get("model") == "<synthetic>")
            mid = msg.get("id")
            if is_err:
                ekey = str(mid) if mid else f"_err_{idx}"
                if ekey not in err_ids:
                    err_ids.add(ekey)
                    errors += 1
                err_txt = None
                content = msg.get("content")
                if isinstance(content, list):
                    parts = [str(c.get("text") or "") for c in content if isinstance(c, dict) and c.get("text")]
                    if parts:
                        err_txt = " ".join(parts)
                final_error = str(err_txt or obj.get("api_error") or obj.get("error") or "error")[:300]
            else:
                key = str(mid) if mid else f"_anon_{idx}"
                u = msg.get("usage")
                msg_usage[key] = u if isinstance(u, dict) else {}
                final_error = None
        elif etype == "result":
            result_obj = obj
            if obj.get("is_error"):
                if errors == 0:
                    errors = 1
                final_error = str(obj.get("result") or obj.get("api_error") or obj.get("subtype") or "error")[:300]
    if not saw_json:
        return None
    if saw_assistant:
        calls = len(msg_usage)
    elif result_obj is not None:
        has_usage = bool(result_obj.get("modelUsage")) or any(
            int((result_obj.get("usage") or {}).get(k) or 0) > 0
            for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        calls = int(result_obj.get("num_turns") or 0) if (not result_obj.get("is_error") and has_usage) else 0
    else:
        calls = 0
    ru = result_obj.get("usage") if isinstance(result_obj, dict) and isinstance(result_obj.get("usage"), dict) else None
    if ru is not None:
        tin = int(ru.get("input_tokens") or 0)
        tout = int(ru.get("output_tokens") or 0)
        cache_create = int(ru.get("cache_creation_input_tokens") or 0)
        cache_read = int(ru.get("cache_read_input_tokens") or 0)
    else:
        tin = sum(int(u.get("input_tokens") or 0) for u in msg_usage.values())
        tout = sum(int(u.get("output_tokens") or 0) for u in msg_usage.values())
        cache_create = sum(int(u.get("cache_creation_input_tokens") or 0) for u in msg_usage.values())
        cache_read = sum(int(u.get("cache_read_input_tokens") or 0) for u in msg_usage.values())
    return {
        "calls": calls,
        "errors": errors,
        "input": tin if (calls > 0 or tin) else None,
        "output": tout if (calls > 0 or tout) else None,
        "cache_creation_input_tokens": cache_create,
        "cache_read_input_tokens": cache_read,
        "final_error": final_error,
    }

PROMPTS = {
    "write": ("Fill in report.md in this directory. Each product has one page: {urls} (read them with curl -s). "
              "Replace every ____ in report.md with the value exactly as that product's page states it, then stop. "
              "Do not change anything else."),
    "b": ("report.md in this directory was filled in earlier from the product pages {urls}. The pages may have "
          "changed since then. Re-read the pages with curl -s and check every value in report.md against them; "
          "correct any value that no longer matches what its page states, then stop. Do not change anything else."),
    "c": ("report.md in this directory was filled in earlier from product pages. The sources of the lines below "
          "have changed since they were written. Re-read each listed source with curl -s and correct the line if its "
          "value no longer matches what the page states, then stop. Do not change any other line.\n{items}"),
    "c_item": "- line {line}: `{text}` (source: {src})",
    "c_nosrc": "source not recorded; the product pages are {urls}",
    "d": ("report.md in this directory was filled in earlier from the product pages {urls}. These pages have changed "
          "since then: {changed}. Re-read them with curl -s and correct any value in report.md that no longer matches "
          "what its page states, then stop. Do not change anything else."),
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p: pathlib.Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True))
    os.replace(tmp, p)


class Run:
    def __init__(self, plan_path: pathlib.Path, root: pathlib.Path, fake: bool = False):
        self.plan_path = plan_path
        self.plan = json.loads(plan_path.read_text())
        self.root = root
        self.fake = fake
        self.mat = pathlib.Path(os.path.expanduser(self.plan["materials"]["dir"]))
        self.manifest_sha = sha_file(self.mat / "manifest.json")
        if self.manifest_sha != self.plan["materials"]["manifest_sha256"]:
            raise SystemExit(f"manifest sha mismatch: {self.manifest_sha}")
        _m = json.loads((self.mat / "manifest.json").read_text())
        self.n_cycles = {s["set"]: len(s["cycles"]) for s in _m["sets"]}
        #: 週期類型只給評分與報告分組用；agent 與 Vacant 都看不到（不進提示、不進病歷）
        self.ctypes = {s["set"]: [c.get("type", "F") for c in s["cycles"]] for s in _m["sets"]}
        self.routes = root / "routes.json"
        self.stop = threading.Event()
        self.procs: set[subprocess.Popen] = set()

    # ---------- 共用 ----------
    def log(self, msg: str) -> None:
        line = f"{now()} {msg}"
        with LOCK:
            print(line, flush=True)
            with open(self.root / "runner.log", "a") as f:
                f.write(line + "\n")

    def set_route(self, host: str, site: pathlib.Path) -> None:
        with LOCK:
            r = json.loads(self.routes.read_text()) if self.routes.exists() else {}
            r[host] = str(site)
            tmp = self.routes.with_suffix(".tmp")
            tmp.write_text(json.dumps(r, indent=1))
            os.replace(tmp, self.routes)

    def urls(self, set_id: str) -> list[str]:
        host = HOST_FMT.format(set=set_id)
        return [f"http://{host}/p{i}.html" for i in range(1, 6)]

    def agent_kind(self) -> str:
        kind = self.plan["model"].get("agent", "pi")
        if kind not in ("pi", "claude"):
            raise SystemExit(f"unsupported model.agent: {kind!r}")
        return kind

    def _claude_settings_path(self, live: pathlib.Path) -> pathlib.Path:
        for cand in (live / "cfg" / "settings.json", live / "cfg" / ".claude" / "settings.json"):
            if cand.is_file():
                return cand
        raise FileNotFoundError(f"claude settings.json not found under {live / 'cfg'}")

    def agent_env(self, live: pathlib.Path) -> dict:
        p = self.plan
        env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
        if self.agent_kind() == "claude":
            # 正式跑時保留使用者的 HOME（沿用登入的 Claude 訂閱憑證），靠旗標隔離設定；
            # 測試時由外部環境提供隔離的 HOME／CLAUDE_CONFIG_DIR 與 ANTHROPIC_BASE_URL／API_KEY。
            # 只設 HTTP 代理（*.d2-sources.example），不設 HTTPS 代理，且 NO_PROXY 排除 Anthropic 端點。
            env.update({"VACANT_HOME": str(live / "vh"),
                        "http_proxy": f"http://127.0.0.1:{p['server']['port']}",
                        "HTTP_PROXY": f"http://127.0.0.1:{p['server']['port']}",
                        "no_proxy": CLAUDE_NO_PROXY, "NO_PROXY": CLAUDE_NO_PROXY,
                        "TMPDIR": str(live / "tmp"),
                        "DISABLE_TELEMETRY": "1",
                        "DISABLE_ERROR_REPORTING": "1",
                        "DISABLE_AUTOUPDATER": "1",
                        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})
            return env
        env.update({"PI_CODING_AGENT_DIR": str(live / "cfg"), "VACANT_HOME": str(live / "vh"),
                    "PI_SKIP_VERSION_CHECK": "1",
                    "http_proxy": f"http://127.0.0.1:{p['server']['port']}",
                    "HTTP_PROXY": f"http://127.0.0.1:{p['server']['port']}",
                    "no_proxy": NO_PROXY, "NO_PROXY": NO_PROXY,
                    "TMPDIR": str(live / "tmp")})
        return env

    def _agent_argv(self, live: pathlib.Path, prompt: str, out: pathlib.Path) -> list[str]:
        p = self.plan
        if self.fake:
            return [sys.executable, str(HERE / "fake_agent.py"), prompt]
        if self.agent_kind() == "claude":
            argv = [
                "claude", "-p",
                "--model", p["model"]["model"],
                "--output-format", "stream-json", "--verbose",
                "--setting-sources", "",
                "--settings", str(self._claude_settings_path(live)),
                "--strict-mcp-config",
                "--disable-slash-commands",
                "--no-session-persistence",
                "--permission-mode", "dontAsk",
                "--allowedTools", CLAUDE_ALLOWED_TOOLS,
                "--disallowedTools", CLAUDE_DISALLOWED_TOOLS,
            ]
            if p["model"].get("max_turns") is not None:
                argv += ["--max-turns", str(p["model"]["max_turns"])]
            argv += ["--", prompt]
            return argv
        return ["pi", "-p", "--mode", "json", "--session-dir", str(out / "sessions"),
                "--provider", p["model"]["provider"], "--model", p["model"]["model"], prompt]

    def run_agent(self, live: pathlib.Path, prompt: str, out: pathlib.Path) -> dict:
        """一次 agent 執行。回用量與結束碼。"""
        out.mkdir(parents=True, exist_ok=True)
        (out / "prompt.txt").write_text(prompt)
        p = self.plan
        t0 = time.time()
        argv = self._agent_argv(live, prompt, out)
        rc = None
        with open(out / "agent.log", "w") as lf:
            pr = subprocess.Popen(argv, cwd=live / "ws", env=self.agent_env(live), stdout=lf,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            with LOCK:
                self.procs.add(pr)
            try:
                rc = pr.wait(timeout=p["agent_timeout_s"])
            except subprocess.TimeoutExpired:
                rc = "timeout"
                self._kill(pr)
            finally:
                with LOCK:
                    self.procs.discard(pr)
        if self.fake:
            u = {"calls": 0, "input": 0, "output": 0}
        elif self.agent_kind() == "claude":
            u = usage_from_claude_log(out / "agent.log")
        else:
            u = usage_from_log(out / "agent.log")
        res = {"rc": rc, "wall_s": round(time.time() - t0, 1), "usage": u}
        write_json(out / "run.json", res)
        if not self.fake and (u is None or (u.get("calls") == 0 and u.get("errors"))):
            raise InfraError(f"infra: {out} usage={u}")
        return res

    def _kill(self, pr: subprocess.Popen) -> None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pr.pid, sig)
            except ProcessLookupError:
                return
            try:
                pr.wait(timeout=10)
                return
            except subprocess.TimeoutExpired:
                continue

    def chain_len(self, live: pathlib.Path) -> int | None:
        """病歷鏈現在最後一筆的 seq（稽核用它切週期；分卷封印之後仍然連續）。"""
        ch = list((live / "vh" / "trace" / "projects").glob("*/chain.ndjson"))
        if len(ch) != 1:
            return None
        last = None
        with open(ch[0]) as f:
            for line in f:
                if line.strip():
                    last = line
        return json.loads(last)["seq"] if last else None

    def sources_check(self, live: pathlib.Path, out: pathlib.Path) -> dict:
        env = self.agent_env(live)
        env.pop("PI_CODING_AGENT_DIR", None)
        t0 = time.time()
        r = subprocess.run([os.path.expanduser(self.plan["vacant_python"]), "-I", "-m", "vacant_network", "trace",
                            "sources", "report.md", "--check", "--json"], cwd=live / "ws", env=env,
                           capture_output=True, text=True, timeout=600)
        (out).mkdir(parents=True, exist_ok=True)
        (out / "sources_check.json").write_text(r.stdout)
        (out / "sources_check.stderr").write_text(r.stderr)
        if r.returncode != 0:
            raise RuntimeError(f"vacant trace sources rc={r.returncode}: {r.stderr[-300:]}")
        res = json.loads(r.stdout)
        res["_wall_s"] = round(time.time() - t0, 1)
        return res

    def install_site(self, set_id: str, k: int, live: pathlib.Path) -> None:
        site = live / "site"
        if site.exists():
            shutil.rmtree(site)
        shutil.copytree(self.mat / "sets" / set_id / f"cycle_{k}" / "site", site)

    # ---------- 一組 ----------
    def do_set(self, set_id: str, arms: list[str]) -> None:
        p = self.plan
        live = self.root / "live" / set_id
        cells = self.root / "cells" / set_id
        host = HOST_FMT.format(set=set_id)
        urls = self.urls(set_id)
        snap = cells / "c0" / "snapshot"
        if not (cells / "c0" / "done.json").exists():
            if live.exists():
                shutil.rmtree(live)
            for d in ("ws", "vh/adapters", "cfg", "tmp"):
                (live / d).mkdir(parents=True, exist_ok=True)
            shutil.copy(self.mat / "sets" / set_id / "template.md", live / "ws" / "report.md")
            cfg = pathlib.Path(os.path.expanduser(p["agentcfg"]["dir"]))
            for f in p["agentcfg"]["copy"]:
                src = cfg / f
                (shutil.copytree if src.is_dir() else shutil.copy)(src, live / "cfg" / f)
            shutil.copy(os.path.expanduser(p["agentcfg"]["install_json"]), live / "vh" / "adapters" / "install.json")
            self.install_site(set_id, 0, live)
            self.set_route(host, live / "site")
            r = self.run_agent(live, PROMPTS["write"].format(urls=" ".join(urls)), cells / "c0" / "run")
            shutil.copy(live / "ws" / "report.md", cells / "c0" / "report.md")
            if snap.exists():
                shutil.rmtree(snap)
            snap.mkdir(parents=True)
            for d in ("ws", "vh"):
                shutil.copytree(live / d, snap / d, symlinks=True)
            write_json(cells / "c0" / "done.json", {**r, "chain_len": self.chain_len(live), "ts": now()})
            self.log(f"{set_id} c0 rc={r['rc']} wall={r['wall_s']}s calls={(r['usage'] or {}).get('calls')}")
        for arm in arms:
            if self.stop.is_set():
                return
            adir = cells / arm
            if (adir / "done.json").exists():
                continue
            if adir.exists():
                shutil.rmtree(adir)
            for d in ("ws", "vh"):
                if (live / d).exists():
                    shutil.rmtree(live / d)
                shutil.copytree(snap / d, live / d, symlinks=True)
            prev_pages = self.page_hashes(set_id, 0)
            for k in range(1, self.n_cycles[set_id] + 1):
                if self.stop.is_set():
                    return
                cdir = adir / f"cycle_{k}"
                cdir.mkdir(parents=True, exist_ok=True)
                self.install_site(set_id, k, live)
                self.set_route(host, live / "site")
                info: dict = {"arm": arm, "cycle": k, "ts_start": now(), "t_start": time.time(), "agent": None,
                              "ctype": self.ctypes[set_id][k - 1]}
                if arm == "b":
                    info["agent"] = self.run_agent(live, PROMPTS["b"].format(urls=" ".join(urls)), cdir / "run")
                elif arm == "c":
                    sc = self.sources_check(live, cdir)
                    lines = (live / "ws" / "report.md").read_text().splitlines()
                    items = []
                    by_line: dict[int, dict] = {}
                    for e in sc["claims"]:
                        if e["status"] != "unchanged":
                            by_line.setdefault(e["line"], e)
                    for ln in sorted(by_line):
                        e = by_line[ln]
                        src = (e.get("source") or {}).get("url") or PROMPTS["c_nosrc"].format(urls=" ".join(urls))
                        items.append(PROMPTS["c_item"].format(line=ln, text=lines[ln - 1].strip(), src=src))
                    info["sources_check"] = {"counts": sc["counts"], "affected_lines": sc["affected_lines"],
                                             "wall_s": sc["_wall_s"]}
                    if items:
                        info["agent"] = self.run_agent(live, PROMPTS["c"].format(items="\n".join(items)), cdir / "run")
                elif arm == "d":
                    cur = self.page_hashes(set_id, k)
                    changed = [f"http://{host}/{f}" for f in sorted(cur) if cur[f] != prev_pages.get(f)]
                    prev_pages = cur
                    info["changed_pages"] = changed
                    if changed:
                        info["agent"] = self.run_agent(
                            live, PROMPTS["d"].format(urls=" ".join(urls), changed=" ".join(changed)), cdir / "run")
                shutil.copy(live / "ws" / "report.md", cdir / "report.md")
                info["chain_len"] = self.chain_len(live)
                info["ts_end"] = now()
                info["t_end"] = time.time()
                write_json(cdir / "cycle.json", info)
                a = info.get("agent") or {}
                self.log(f"{set_id} {arm} cycle {k} agent={'-' if not a else a['rc']} "
                         f"calls={(a.get('usage') or {}).get('calls', 0) if a else 0}")
            fin = adir / "final"
            for d in ("ws", "vh"):
                shutil.copytree(live / d, fin / d, symlinks=True)
            write_json(adir / "done.json", {"ts": now()})

    def page_hashes(self, set_id: str, k: int) -> dict:
        site = self.mat / "sets" / set_id / f"cycle_{k}" / "site"
        return {f.name: sha_file(f) for f in sorted(site.iterdir()) if f.name != "index.html"}

    # ---------- 整批 ----------
    def start_server(self) -> subprocess.Popen:
        port = self.plan["server"]["port"]
        srv = subprocess.Popen([sys.executable, str(HERE / "source_server.py"), "--port", str(port),
                                "--routes", str(self.routes), "--log", str(self.root / "access.jsonl")],
                               stdout=subprocess.DEVNULL, stderr=open(self.root / "server.err", "a"),
                               start_new_session=True)
        for _ in range(50):
            try:
                import socket
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                return srv
            except OSError:
                time.sleep(0.1)
        raise SystemExit("source server did not start")

    def go(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        runj = self.root / "RUN.json"
        plan_sha = sha_file(self.plan_path)
        if runj.exists():
            old = json.loads(runj.read_text())
            if old["plan_sha256"] != plan_sha:
                raise SystemExit("this root was started with a different plan")
        else:
            write_json(runj, {"plan": str(self.plan_path), "plan_sha256": plan_sha, "plan_body": self.plan,
                              "manifest_sha256": self.manifest_sha, "runner_sha256": sha_file(pathlib.Path(__file__)),
                              "started": now()})
        srv = self.start_server()
        rng = random.Random(self.plan["seed"])
        sets = list(self.plan["materials"]["sets"])
        orders = {}
        for s in sets:
            o = list(self.plan["arms"])
            rng.shuffle(o)
            orders[s] = o
        write_json(self.root / "arm_orders.json", orders)
        todo = list(sets)
        errors = []

        def worker():
            while not self.stop.is_set():
                with LOCK:
                    if not todo:
                        return
                    s = todo.pop(0)
                try:
                    self.do_set(s, orders[s])
                except Exception as e:      # noqa: BLE001
                    errors.append((s, repr(e)))
                    self.log(f"{s} ERROR {e!r}")

        def term(*_):
            self.stop.set()
            with LOCK:
                ps = list(self.procs)
            for pr in ps:
                self._kill(pr)
        signal.signal(signal.SIGTERM, term)
        signal.signal(signal.SIGINT, term)
        ths = [threading.Thread(target=worker, daemon=True) for _ in range(self.plan["jobs"])]
        for t in ths:
            t.start()
        for t in ths:
            while t.is_alive():
                t.join(timeout=1)
        srv.terminate()
        self.log(f"batch end; errors={errors}; stopped={self.stop.is_set()}")
        return 1 if errors else (130 if self.stop.is_set() else 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--plan", required=True)
    r.add_argument("--root", required=True)
    r.add_argument("--fake", action="store_true")
    a = ap.parse_args()
    plan = pathlib.Path(a.plan).resolve()
    if not a.fake:
        rel = plan.relative_to(REPO)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", str(rel), "ops/d2", "vacant_network"],
                               cwd=REPO, capture_output=True, text=True).stdout.strip()
        if dirty:
            raise SystemExit(f"refusing: uncommitted changes:\n{dirty}")
    return Run(plan, pathlib.Path(a.root).expanduser().resolve(), fake=a.fake).go()


if __name__ == "__main__":
    raise SystemExit(main())
