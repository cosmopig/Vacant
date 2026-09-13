#!/usr/bin/env python3
"""本地模型的工具迴圈——讓迴圈的機械輪次不燒 Anthropic token。

**為什麼是這支而不是讓 Claude Code 接本地模型**（人類 2026-08-28 指定）：
Claude Code 說的是 Anthropic Messages API，本地端點說的是 OpenAI
chat/completions。要接上就得寫一層雙向協定轉換（含 SSE 串流、tool_use／
tool_result 區塊對應），那層本身就是一個會壞、會需要維護的東西。
直接寫工具迴圈少掉整個轉換層。

後端：`http://100.119.113.56:8765/v1/chat/completions`（算力中轉）
模型：`qwen/qwen3.8-27b`

## 只給一個工具

`run_bash` 一個。理由不是偷懶：27B 級的模型工具選項越多越容易選錯，而讀檔、
寫檔、git、跑測試**全部都能經過 shell**。附帶好處是每一個動作都以指令的形式
落盤，稽核的人看到的是可以自己重跑的東西，不是「模型說它做了什麼」。

## 為什麼有硬擋門

比較弱的模型握著 shell，光靠指令文字勸它「不要做 X」不夠——那是把安全性
建立在模型的服從度上。`DENY` 是可執行的擋門，跟 `memory.assert_ks1_clean`
同一個性質：規則要能執行，不能只是寫在文件裡。

擋下來的指令**照樣落盤**（`blocked: true`），因為「模型試圖做什麼」比
「模型做成了什麼」更值得留著看。

## 全 I/O 落盤（鐵律 3）

每一輪的完整 request／response、每一次工具呼叫與它的 stdout／stderr／
returncode，逐筆進 JSONL，不截斷。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_API = "http://100.119.113.56:8765/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.6-35b-a3b"   # 2026-08-28 人類停掉 3.8，改跟實驗同一顆

# 不可逆或會毀掉稽核鏈的動作。指令文字裡也寫了，但那是勸導；這裡是擋門。
# 每一條都對應一個真的會發生的壞結果，不是想像出來的：
DENY = [
    (r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf]", "rm -rf：run 目錄是證據，刪掉就沒有了"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "force push：會改寫別人也在用的歷史"),
    (r"\bgit\s+reset\s+--hard\b", "reset --hard：會丟掉未提交的實驗產物"),
    (r"\bgit\s+clean\b", "git clean：會刪掉 untracked 的 run 目錄"),
    (r"\bgit\s+checkout\s+\.", "checkout .：同上，會丟掉未提交的改動"),
    (r"\bsudo\b", "sudo：需要人類決定"),
    (r"\bshutdown\b|\breboot\b|\bpoweroff\b", "關機／重開"),
    (r"\bmkfs\b|\bdd\s+if=", "磁碟層級操作"),
    (r">\s*/dev/sd", "直接寫磁碟裝置"),
    (r"\btouch\s+.*\bSTOP\b", "touch STOP：迴圈要一直迭代，停止只有人類能決定"),
    (r"\bkill\b.*\bloop\.sh\b|\bpkill\b.*loop", "殺掉迴圈本身"),
    (r"\.cline-keys|\.hf-token|identity\.key|\.git-credentials",
     "秘密憑證：不要讀、不要印、不要複製"),
]

TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_bash",
        "description": (
            "Run a bash command in the repository working directory and return its "
            "stdout, stderr and exit code. Use this for everything: reading files "
            "(cat/sed -n), searching (grep/find), writing files (heredoc), running "
            "tests, and git operations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run."},
                "timeout_s": {"type": "integer",
                              "description": "Seconds before the command is killed (default 120, max 900)."},
            },
            "required": ["command"],
        },
    },
}]


def deny_reason(command: str) -> str | None:
    for pattern, why in DENY:
        if re.search(pattern, command):
            return why
    return None


def git_rev(cwd: pathlib.Path, ref: str = "HEAD") -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cwd), "rev-parse", ref],
                            capture_output=True, text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:                                    # noqa: BLE001
        return None


def git_branch(cwd: pathlib.Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"],
                            capture_output=True, text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:                                    # noqa: BLE001
        return None


def git_remote_rev(cwd: pathlib.Path, remote: str, branch: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(cwd), "ls-remote", remote, branch],
                            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.split()[0]
    except Exception:                                    # noqa: BLE001
        pass
    return None


class Session:
    def __init__(self, *, cwd: pathlib.Path, log_path: pathlib.Path,
                 api: str, model: str, timeout_s: int) -> None:
        self.cwd = cwd
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.api = api
        self.model = model
        self.timeout_s = timeout_s
        self.tool_calls = 0
        self.blocked = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def log(self, rec: dict) -> None:
        rec["ts_ms"] = int(time.time() * 1000)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())          # 中途被砍也要留得住

    # ── 模型 ────────────────────────────────────────────────────────
    def complete(self, messages: list[dict], *, retries: int = 9) -> dict:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "tools": TOOLS,
            "temperature": 0.3,
            "stream": False,
        }).encode()
        last = ""
        for attempt in range(1, retries + 1):
            t0 = time.time()
            req = urllib.request.Request(
                self.api, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    payload = json.load(r)
                if "choices" not in payload and payload.get("error"):
                    # 中轉會回 HTTP 200 但 body 是錯誤物件（實測 {"error":"terminated"}）
                    raise RuntimeError(f"端點回 200 但 body 是錯誤：{payload['error']!r}")
                msg = payload["choices"][0]["message"]
                usage = payload.get("usage") or {}
                self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
                self.completion_tokens += int(usage.get("completion_tokens") or 0)
                self.log({"kind": "model", "ok": True, "attempt": attempt,
                          "latency_ms": int((time.time() - t0) * 1000),
                          "usage": usage, "request_messages": messages,
                          "response_message": msg})
                return msg
            except Exception as e:                        # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
                self.log({"kind": "model", "ok": False, "attempt": attempt,
                          "latency_ms": int((time.time() - t0) * 1000),
                          "error": last, "request_messages": messages})
                if attempt < retries:
                    # 2026-08-31 round396/397 實測：8765 中轉偶發整批 400
                    # Bad Request 風暴（19s、30s 兩次），與決定性 run
                    # PID 2266603 自己的 calls.jsonl 同時間戳也在噴 400
                    # ——是後端整體風暴不是這支專屬，決定性 run 有
                    # retries=4 撐得過去，這支原本 retries=4（2/4/8s＝
                    # 14s 退避）撐不過 19-30s 的風暴而整輪失敗。
                    # retries 提到 6（2/4/8/16/32s＝62s 累積退避）。
                    #
                    # 2026-08-31 round398 實測：retries=6 的同步本身確認
                    # 生效（localagent-4726.jsonl 真的看到 attempt 1-6），
                    # 但這次風暴從 attempt1 起算到 attempt6 結束跨了約
                    # 180s（attempt6 本身的請求就掛了 88.7s 才回 400，不是
                    # 秒退的快速失敗）——62s 累積退避撐不過去。這是連續
                    # 第二次「上一輪抓到的風暴時長，這一輪就被更長的蓋過」
                    # ，不再逐次照觀測到的時長微調，改成 retries 提到 9
                    # 且退避封頂在 32s（2/4/8/16/32/32/32/32＝158s 累積），
                    # 用「更寬的固定預算」取代「跟著上一次風暴長度微調」。
                    #
                    # 2026-08-30 實測：中轉的 LM Studio 後端在跟決定性 run
                    # （同時吃兩顆模型 qwen3.6-35b-a3b／gemma-4-12b-it-qat）
                    # 搶記憶體時會把這支的模型換出，回 HTTP 200 但
                    # body={"error":"Model unloaded."}——換頁到重新載入
                    # 35B 量化模型的時間遠超過原本 2/4/8s 的指數退避，
                    # 一律重試到底、不會等到它換回來。這種情況給固定 30s。
                    if "unloaded" in last.lower():
                        time.sleep(30.0)
                    else:
                        time.sleep(min(2.0 * (2 ** (attempt - 1)), 32.0))
        raise SystemExit(f"模型連續 {retries} 次失敗：{last}")

    # ── 工具 ────────────────────────────────────────────────────────
    def run_bash(self, command: str, timeout_s: int = 120) -> str:
        timeout_s = max(1, min(int(timeout_s or 120), 900))
        why = deny_reason(command)
        if why:
            self.blocked += 1
            self.log({"kind": "tool", "name": "run_bash", "blocked": True,
                      "command": command, "reason": why})
            return (f"BLOCKED: {why}\n"
                    f"這個動作被硬擋門擋下。如果你確信它必要，把理由寫進 "
                    f"GAIN_STATE.md 讓人類決定，不要換個寫法繞過去。")
        self.tool_calls += 1
        t0 = time.time()
        try:
            p = subprocess.run(["bash", "-lc", command], cwd=str(self.cwd),
                               capture_output=True, text=True, timeout=timeout_s)
            out, err, rc = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired:
            out, err, rc = "", f"(逾時 {timeout_s}s 被中止)", 124
        self.log({"kind": "tool", "name": "run_bash", "blocked": False,
                  "command": command, "timeout_s": timeout_s, "returncode": rc,
                  "latency_ms": int((time.time() - t0) * 1000),
                  "stdout": out, "stderr": err})
        # 回給模型的要截斷（context 有限），但**落盤的是全文**。
        def clip(s: str, n: int = 6000) -> str:
            return s if len(s) <= n else s[:n] + f"\n…(截斷，全文在 {self.log_path.name})"
        return f"exit={rc}\n--- stdout ---\n{clip(out)}\n--- stderr ---\n{clip(err)}"


def main() -> None:
    ap = argparse.ArgumentParser(description="本地模型工具迴圈")
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--cwd", default=os.path.expanduser("~/vacant/Vacant"))
    ap.add_argument("--log", default=os.path.expanduser("~/vacant/logs/localagent.jsonl"))
    ap.add_argument("--api", default=os.environ.get("VACANT_LOCAL_API", DEFAULT_API))
    ap.add_argument("--model", default=os.environ.get("VACANT_LOCAL_MODEL", DEFAULT_MODEL))
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--max-minutes", type=int, default=40)
    ap.add_argument("--request-timeout-s", type=int, default=600)
    ap.add_argument("--require-commit-push", action="store_true", default=True)
    ap.add_argument("--no-require-commit-push", dest="require_commit_push",
                     action="store_false")
    ap.add_argument("--remote", default="origin")
    args = ap.parse_args()

    cwd = pathlib.Path(args.cwd)
    prompt = pathlib.Path(args.prompt_file).read_text(encoding="utf-8")
    s = Session(cwd=cwd, log_path=pathlib.Path(args.log),
                api=args.api, model=args.model, timeout_s=args.request_timeout_s)

    start_head = git_rev(cwd)
    branch = git_branch(cwd)

    commit_clause = (
        "\nHard, code-enforced requirement (not just advice): before you stop, you must "
        "have created a new git commit AND pushed it, such that `git rev-parse HEAD` "
        f"equals `git ls-remote {args.remote} {branch or '<branch>'}`. This script checks "
        "that itself after you finish — it does not trust your summary. If your task "
        "doesn't otherwise produce a code change, still update the handoff file "
        "(e.g. GAIN_STATE.md) with what you did and commit+push that. Finishing without a "
        "verified commit+push makes this whole round count as failed, even if every "
        "command you ran succeeded.\n"
        if args.require_commit_push else ""
    )
    system = (
        "You are an autonomous engineer working in a git repository on a Linux VM. "
        "You have exactly one tool: run_bash. Use it for everything — reading files "
        "(cat, sed -n), searching (grep, find), editing (heredoc or python), running "
        "tests, and git.\n"
        "Work in small verified steps: run a command, read its real output, then decide. "
        "Never claim something succeeded without having seen the output that proves it.\n"
        "Some commands are blocked by a hard guard and will return BLOCKED with a reason. "
        "Do not try to work around a block; write the reason down instead."
        + commit_clause +
        "When you are finished, reply with a short plain-text summary and no tool call."
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": prompt}]

    t0 = time.time()
    s.log({"kind": "start", "model": args.model, "api": args.api,
           "cwd": args.cwd, "prompt_bytes": len(prompt.encode())})
    print(f"── 本地模型輪次　{args.model} @ {args.api}", flush=True)

    # 2026-08-31 round406 實測（iter-4741）：模型在預算內（33/40 步、
    # 29.8/40 分鐘，兩者都還沒到頂）自己判斷「做完了」、吐出純文字摘要
    # 收尾，但從頭到尾沒有執行過任何一次 git commit——是「模型自認完成」
    # 不是「真的完成」，而 require_commit_push 的驗證只在事後才抓到，
    # 已經浪費掉整輪 1788s。與其事後才發現，在模型交回純文字（沒有再要
    # 工具）的當下先檢查有沒有真的 commit 過，沒有就用一句話逼它現在就
    # 執行 git 指令，而不是接受它的「完成」宣稱——最多逼問
    # `nudge_budget` 次，避免模型死不聽話時無限迴圈。
    nudge_budget = 2
    for step in range(1, args.max_steps + 1):
        if time.time() - t0 > args.max_minutes * 60:
            print(f"── 到達 {args.max_minutes} 分鐘上限，收尾", flush=True)
            break
        msg = s.complete(messages)
        calls = msg.get("tool_calls") or []
        text = (msg.get("content") or "").strip()
        # reasoning_content 不回灌——它是思考不是對話，灌回去會讓 context 爆掉
        messages.append({"role": "assistant",
                         "content": msg.get("content") or "",
                         **({"tool_calls": calls} if calls else {})})
        if text:
            print(f"[{step}] {text[:400]}", flush=True)
        if not calls:
            if (args.require_commit_push and nudge_budget > 0
                    and git_rev(cwd) == start_head):
                nudge_budget -= 1
                print(f"── 模型交回純文字但還沒 commit，逼問一次"
                      f"（剩 {nudge_budget} 次額度）", flush=True)
                messages.append({
                    "role": "user",
                    "content": (
                        "You have not created any git commit yet "
                        f"(HEAD is still {start_head}). Stop analyzing further "
                        "and run the actual `git add`/`git commit`/`git push` "
                        "commands right now, using whatever you have already "
                        "found. This is a hard requirement, not a suggestion."
                    ),
                })
                continue
            print("── 模型沒有再要工具，結束", flush=True)
            break
        for c in calls:
            fn = c.get("function", {})
            try:
                a = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                a = {}
            if fn.get("name") != "run_bash" or "command" not in a:
                result = f"ERROR: 只有 run_bash 可用，且必須有 command 參數。收到 {fn.get('name')!r}"
            else:
                cmd = a["command"]
                print(f"    $ {cmd[:160]}", flush=True)
                result = s.run_bash(cmd, a.get("timeout_s", 120))
            messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                             "content": result})

    dur = int(time.time() - t0)
    end_head = git_rev(cwd)
    remote_head = git_remote_rev(cwd, args.remote, branch) if branch else None
    committed = bool(end_head) and end_head != start_head
    pushed = bool(remote_head) and remote_head == end_head
    s.log({"kind": "end", "steps": step, "wall_s": dur,
           "tool_calls": s.tool_calls, "blocked": s.blocked,
           "prompt_tokens": s.prompt_tokens,
           "completion_tokens": s.completion_tokens,
           "start_head": start_head, "end_head": end_head,
           "remote_head": remote_head, "committed": committed, "pushed": pushed})
    print(f"── 結束：{step} 步、{s.tool_calls} 次工具呼叫、{s.blocked} 次被擋、"
          f"{dur}s、本地 token {s.prompt_tokens}+{s.completion_tokens}（$0）", flush=True)
    print(f"── 收尾驗證：commit {'✓' if committed else '✗'}（{start_head}→{end_head}）　"
          f"push {'✓' if pushed else '✗'}（remote={remote_head}）", flush=True)
    if args.require_commit_push and not (committed and pushed):
        print("── 沒有驗證到新的 commit+push，判定這一輪失敗（rc=1），"
              "讓呼叫端退回較強的模型，不要用「模型自認完成」當通過標準。",
              flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
