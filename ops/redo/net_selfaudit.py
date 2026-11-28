#!/usr/bin/env python3
"""net_selfaudit — 自我稽核：已存的 agent 紀錄裡有沒有連外網的證據（只讀，不呼叫模型，零費用）。

這支在架構裡承重什麼
====================
另一條實驗線發現 agent 經 https 直連外網（只設了 http_proxy）。本檔掃我們自己這條線
（Claude Haiku 與 Devin 的批次）每格每次嘗試留下的 agent 紀錄，回答三件事：
  1. 有沒有網頁工具呼叫（WebFetch／WebSearch／web_search／webfetch／browse…），有沒有被拒；
  2. 殼層指令（Claude 的 Bash、Devin 的 exec）有沒有連外動作（curl／wget／requests／urllib／pip／git clone／nc…），
     結果是失敗還是拿到內容；
  3. 有沒有碰 codeforces／github／題解站（題目來自 Codeforces，查得到題解＝洩漏）。

輸入
----
  Claude：`<root>/cells/<cell>/<rep>/<arm>/<attempt>/agent.log`（stream-json；tool_use／tool_result 以 id 配對）
  Devin ：`.../logs/devin_export.json`（ATIF；steps[].tool_calls[] ＋ observation.results[]）

誠實邊界（改碼請保留）
----------------------
- 只掃**有留紀錄**的嘗試；沒有 agent.log／devin_export.json 的嘗試列在 `no_record`，不能當成「沒連」。
- 指令文字比對是**啟發式**：`url_literal`（指令裡只出現網址字面值，多半是寫進程式碼裡的字串）與
  `net_cmd`（有連外動詞）分開算；成功／失敗由回傳內容判斷，判不出的歸 `unclear`，須人工看例子。
- 掃紀錄證明不了「沒有能力連」：能力要靠負控制（實際在同一設定下連一次）。本檔只回答「紀錄裡有沒有發生」。
- 例子輸出會去識別（家目錄、帳號、主機位址）。

用法：python3 -I ops/redo/net_selfaudit.py [--runs /opt/ctlwork/runs] [--devin-sessions sessions.db的複本] [--exams-calls calls.jsonl] [--json out.json]
  Devin 逾時被殺的嘗試沒有 --export 檔；給 --devin-sessions 才能補到它們（以 devin_wrapper.json 的 workspace 對回）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

WEB_TOOLS = {"webfetch", "websearch", "web_search", "web_fetch", "browse", "browser_preview", "fetch",
             "read_url", "open_url", "search_web"}
SHELL_TOOLS = {"bash", "exec", "shell", "run_command"}

# 連外動作。分兩組：指令動詞（只在「指令位置」才算：行首或 ; & | ( ` 之後，且先去掉 heredoc 本文，
# 否則寫進程式碼裡的 host／ping／dig 等字會誤中）；程式碼層的連線 API（全文都掃，因為
# `python3 - <<EOF ... urllib ... EOF` 就是在執行它）
VERB_RE = re.compile(
    r"(?:^|[;&|(`]|\n)\s*(?:\w+=\S+\s+)*(?:sudo\s+|timeout\s+\d+\s+|env\s+|command\s+)*(?:"
    r"curl|wget|aria2c|lynx|w3m|nc|ncat|netcat|telnet|ssh|scp|sftp|ftp|rsync|dig|nslookup|host|ping|traceroute|"
    r"pip3?\s+(?:install|download)|python3?\s+-m\s+pip|uv\s+(?:pip|add|sync)|poetry\s+(?:add|install)|"
    r"npm\s+(?:install|i|ci|add|view|pack)|npx|yarn\s+(?:add|install)|pnpm\s+(?:add|install)|"
    r"git\s+(?:clone|fetch|pull|ls-remote|submodule)|gh|apt(?:-get)?\s+(?:install|update)|"
    r"cargo\s+(?:fetch|install|add|search)|go\s+(?:get|mod\s+download|install)|gem\s+install|brew\s+install"
    r")(?=$|[\s;&|)`'\"])", re.I)
CODE_RE = re.compile(
    r"requests\.(?:get|post|put|head|request|Session)|urllib\.request|urlopen|http\.client|httplib|"
    r"socket\.(?:socket|create_connection|getaddrinfo|gethostbyname)|aiohttp|httpx\.|"
    r"/dev/tcp/|XMLHttpRequest|require\(['\"]https?['\"]\)|from\s+['\"]node:https?['\"]|"
    r"Net::HTTP|reqwest|java\.net\.URL|curl_easy|fetch\(\s*['\"]https?:", re.I)
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?:\n|$)", re.S)
URL_RE = re.compile(r"https?://[^\s'\"<>)\]]+", re.I)
LOCAL_HOST_RE = re.compile(r"^https?://(?:localhost|127\.|0\.0\.0\.0|\[::1\])", re.I)
INTEREST_RE = re.compile(r"codeforces|github\.com|githubusercontent|gitlab|stackoverflow|geeksforgeeks|leetcode|"
                         r"atcoder|luogu|cnblogs|csdn|blog|editorial|exercism|rosettacode|pastebin|gist\.", re.I)

# 結果判讀
FAIL_RE = re.compile(
    r"could not resolve|couldn'?t resolve|name or service not known|temporary failure in name resolution|"
    r"network is unreachable|no route to host|connection refused|failed to connect|connection (?:timed out|reset)|"
    r"timed out|max retries exceeded|urlerror|connectionerror|newconnectionerror|gaierror|errno -?\d+|"
    r"proxy|403 forbidden|407|denied|not permitted|permission|blocked|sandbox|unable to access|"
    r"could not (?:connect|download)|no matching distribution|network error|enotfound|econnrefused|"
    r"dial tcp|failed to fetch|unreachable|offline|ssl.*error|certificate|command not found|not found: |"
    r"curl: \(\d+\)|(?:rc|exit)[= ]+(?:56|7|6|28|35|60)\b",
    re.I)
CONTENT_RE = re.compile(r"<!doctype html|<html|<head>|<body|^\s*[\[{]\s*\"|HTTP/\d(?:\.\d)? 200|200 OK|"
                        r"content-type:|\"status\"\s*:\s*\"?ok|<title>", re.I | re.M)


def scrub(s: str, n: int = 220) -> str:
    s = re.sub(r"/(?:home|root|Users)/[^\s'\":)]+", "<path>", s)
    s = re.sub(r"/(?:opt/ctlwork|var/ctlws\w*|tmp/redo-\w+|mnt|srv)[^\s'\":)]*", "<path>", s)
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<email>", s)
    s = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", "<ip>", s)
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "…"


def cmd_text(inp) -> str:
    if isinstance(inp, dict):
        return str(inp.get("command") or inp.get("cmd") or inp.get("script") or json.dumps(inp, ensure_ascii=False))
    return str(inp)


def result_text(c) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for x in c:
            out.append(x.get("text", "") if isinstance(x, dict) else str(x))
        return "\n".join(out)
    return json.dumps(c, ensure_ascii=False) if c is not None else ""


def classify_cmd(cmd: str) -> tuple[str, list[str]]:
    """none / url_literal / net_cmd；回 (類別, 非本機網址清單)"""
    urls = [u for u in URL_RE.findall(cmd) if not LOCAL_HOST_RE.match(u)]
    stripped = HEREDOC_RE.sub("\n", cmd)
    if VERB_RE.search(stripped) or CODE_RE.search(cmd):
        return "net_cmd", urls
    if urls:
        return "url_literal", urls
    return "none", urls


def classify_result(res: str, is_error: bool | None) -> str:
    """fail（連線錯誤／被擋）／content（像拿到網頁或 JSON）／unclear"""
    if CONTENT_RE.search(res or "") and not re.search(r"could not resolve|unreachable|refused|denied", res or "", re.I):
        return "content"
    if is_error or FAIL_RE.search(res or ""):
        return "fail"
    return "unclear"


def iter_claude(path: pathlib.Path):
    """yield (kind, name, input_or_None, result_text, is_error)"""
    uses: dict[str, tuple[str, object]] = {}
    order: list[str] = []
    results: dict[str, tuple[str, bool | None]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        msg = ev.get("message") if isinstance(ev, dict) else None
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                uses[b.get("id")] = (b.get("name", ""), b.get("input"))
                order.append(b.get("id"))
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id")] = (result_text(b.get("content")), b.get("is_error"))
    for i in order:
        name, inp = uses[i]
        res, err = results.get(i, ("", None))
        yield name, inp, res, err, (i in results)


def iter_devin(path: pathlib.Path):
    d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    for s in d.get("steps", []):
        calls = s.get("tool_calls") or []
        obs = {r.get("source_call_id"): r.get("content") for r in ((s.get("observation") or {}).get("results") or [])}
        for tc in calls:
            cid = tc.get("tool_call_id")
            yield (tc.get("function_name", ""), tc.get("arguments"), result_text(obs.get(cid)), None, cid in obs)


def load_sessions(db: pathlib.Path) -> dict[str, list[list]]:
    """Devin 本機 sessions.db（唯讀）：working_directory -> [[name, input, result, err, has_res], ...]。
    逾時被殺的嘗試沒有 --export 檔，但這個資料庫有完整工具呼叫；以 devin_wrapper.json 的 workspace 對回嘗試。"""
    import sqlite3
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    wd = {sid: w for sid, w in c.execute("select id, working_directory from sessions")}
    out: dict[str, list[list]] = defaultdict(list)
    for sid, tj, uj in c.execute("select session_id, tool_call_json, tool_call_update_json from tool_call_state"):
        w = wd.get(sid)
        if w is None:
            continue
        try:
            tc = json.loads(tj) if tj else {}
            up = json.loads(uj) if uj else {}
        except Exception:
            continue
        meta = tc.get("_meta") or up.get("_meta") or {}
        name = meta.get("cognition.ai/inferenceToolName") or str(tc.get("kind"))
        res = []
        for b in (up.get("content") or []):
            cc = b.get("content") if isinstance(b, dict) else None
            if isinstance(cc, dict) and cc.get("type") == "text":
                res.append(cc.get("text", ""))
            elif isinstance(b, dict) and b.get("type") == "diff":
                res.append("[diff]")
        rejected = bool((up.get("_meta") or {}).get("cognition.ai/rejected"))
        out[w].append([name, tc.get("rawInput"), "\n".join(res), rejected or up.get("status") == "failed",
                       bool(uj)])
    return out


def attempts(root: pathlib.Path):
    for p in sorted(root.rglob("agent.log")):
        yield p.parent
    # 沒有 agent.log 但有 devin_export 的也算
    seen = {q.parent for q in root.rglob("agent.log")}
    for p in sorted(root.rglob("devin_export.json")):
        a = p.parent.parent
        if a not in seen:
            yield a


def scan_root(root: pathlib.Path, label: str, agg: dict, sessions: dict | None = None):
    r = agg.setdefault(label, {"attempts": 0, "no_record": [], "web_calls": Counter(), "web_denied": 0,
                               "web_other": 0, "shell_calls": 0, "net_cmd": 0, "url_literal": 0,
                               "net_result": Counter(), "hosts": Counter(), "interest_hits": 0,
                               "examples": defaultdict(list), "affected_attempts": defaultdict(set),
                               "web_attempts": set(), "src": Counter()})
    for a in dict.fromkeys(attempts(root)):
        rel = str(a.relative_to(root)).replace("/attempt_", "#").replace("cells/", "")
        stream = a / "agent.log"
        export = a / "logs" / "devin_export.json"
        wrapper = a / "logs" / "devin_wrapper.json"
        ws = None
        if wrapper.exists():
            try:
                ws = json.loads(wrapper.read_text()).get("workspace")
            except Exception:
                ws = None
        if sessions is not None and ws and ws in sessions:
            it, agent = iter(sessions[ws]), "devin"
            r["src"]["devin_sessions_db"] += 1
        elif export.exists():
            it, agent = iter_devin(export), "devin"
            r["src"]["devin_export"] += 1
        elif stream.exists() and stream.stat().st_size > 0 and stream.read_text(errors="replace")[:1] == "{":
            it, agent = iter_claude(stream), "claude"
            r["src"]["claude_stream"] += 1
        else:
            r["no_record"].append(rel)
            continue
        r["attempts"] += 1
        for name, inp, res, err, has_res in it:
            low = (name or "").lower()
            if low in WEB_TOOLS:
                r["web_calls"][name] += 1
                r["web_attempts"].add(rel)
                q = scrub(json.dumps(inp, ensure_ascii=False) if inp is not None else "")
                denied = bool(re.search(r"permission denied|denied|not allowed|deny rule|disallowed|no such tool|"
                                       r"unavailable|not available|blocked", res or "", re.I)) or bool(err)
                if denied:
                    r["web_denied"] += 1
                else:
                    r["web_other"] += 1
                    r["affected_attempts"]["web_tool_not_denied"].add(rel)
                if INTEREST_RE.search(q):
                    r["interest_hits"] += 1
                if len(r["examples"]["web"]) < 6:
                    r["examples"]["web"].append(f"{rel} {name} {q} -> {scrub(res, 100)}")
                continue
            if low in SHELL_TOOLS or "bash" in low or "exec" in low:
                cmd = cmd_text(inp)
                r["shell_calls"] += 1
                kind, urls = classify_cmd(cmd)
                if kind == "none":
                    continue
                for u in urls:
                    h = re.sub(r"^https?://", "", u).split("/")[0].split(":")[0].lower()
                    r["hosts"][h] += 1
                if INTEREST_RE.search(cmd):
                    r["interest_hits"] += 1
                if kind == "url_literal":
                    r["url_literal"] += 1
                    if len(r["examples"]["url_literal"]) < 4:
                        r["examples"]["url_literal"].append(f"{rel} {scrub(cmd, 160)}")
                    continue
                r["net_cmd"] += 1
                outcome = classify_result(res, err) if has_res else "no_result"
                r["net_result"][outcome] += 1
                if outcome in ("content", "unclear", "no_result"):
                    r["affected_attempts"][outcome].add(rel)
                key = f"net_cmd_{outcome}"
                if len(r["examples"][key]) < 6:
                    r["examples"][key].append(f"{rel} `{scrub(cmd, 160)}` -> {scrub(res, 140)}")


def scan_exam_calls(path: pathlib.Path) -> dict:
    """考卷批次（`claude -p --tools ""`，無任何工具）：calls.jsonl 每通回應的 num_turns／server_tool_use／permission_denials。"""
    n = 0
    turns: Counter = Counter()
    web = 0
    denials = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
            r = d.get("response")
            r = json.loads(r) if isinstance(r, str) else r
        except Exception:
            continue
        if not isinstance(r, dict):
            continue
        n += 1
        turns[r.get("num_turns")] += 1
        stu = (r.get("usage") or {}).get("server_tool_use") or {}
        web += int(stu.get("web_search_requests") or 0) + int(stu.get("web_fetch_requests") or 0)
        denials += len(r.get("permission_denials") or [])
    return {"calls": n, "num_turns": dict(turns), "server_web_requests": web, "permission_denials": denials}


def to_jsonable(agg):
    out = {}
    for k, r in agg.items():
        out[k] = {kk: (dict(v) if isinstance(v, (Counter, defaultdict)) else
                       (sorted(v) if isinstance(v, set) else v)) for kk, v in r.items()}
        out[k]["examples"] = {a: b for a, b in r["examples"].items()}
        out[k]["affected_attempts"] = {a: sorted(b) for a, b in r["affected_attempts"].items()}
        out[k]["web_attempts"] = sorted(r["web_attempts"])
        out[k]["no_record_n"] = len(r["no_record"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="/opt/ctlwork/runs")
    ap.add_argument("--extra-root", action="append", default=[])
    ap.add_argument("--devin-sessions", help="Devin 的 sessions.db（唯讀開啟；建議先複製一份）")
    ap.add_argument("--exams-calls", help="exams_haiku_20261127/calls.jsonl")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    agg: dict = {}
    roots = [p for p in sorted(pathlib.Path(a.runs).iterdir()) if p.is_dir()] if pathlib.Path(a.runs).is_dir() else []
    roots += [pathlib.Path(x) for x in a.extra_root]
    sess = load_sessions(pathlib.Path(a.devin_sessions)) if a.devin_sessions else None
    for p in roots:
        scan_root(p, p.name, agg, sess)
    js = to_jsonable(agg)
    print(f"{'root':46} {'att':>5} {'web':>4} {'deny':>4} {'shell':>6} {'netcmd':>6} {'fail':>5} {'cont':>5} {'uncl':>5} {'url_l':>5} {'norec':>5}")
    for k, r in js.items():
        nr = r["net_result"]
        print(f"{k:46} {r['attempts']:5d} {sum(r['web_calls'].values()):4d} {r['web_denied']:4d} {r['shell_calls']:6d} "
              f"{r['net_cmd']:6d} {nr.get('fail',0):5d} {nr.get('content',0):5d} "
              f"{nr.get('unclear',0)+nr.get('no_result',0):5d} {r['url_literal']:5d} {r['no_record_n']:5d}")
    if a.exams_calls:
        js["_exams_calls"] = scan_exam_calls(pathlib.Path(a.exams_calls))
        print("exams calls:", js["_exams_calls"])
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(js, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
