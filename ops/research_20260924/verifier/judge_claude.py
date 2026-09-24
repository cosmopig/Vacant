"""LLM 評審後端：子行程 `claude -p`（本 session 唯一能開的模型通道），**全 I/O 落盤**。

鐵律 3：每一通的 prompt、原始回覆、usage、成本、重試都寫進 `results/judge_calls_<exp>.jsonl`；
retry×4；同一個 (model, system, prompt) 已經有成功紀錄就直接讀回（斷點續跑，不是跨臂共享：
不同策略的 prompt 不同，雜湊就不同）。

KS-1：system prompt 只描述工作，不含「你有責任／會被懲罰」類措辭（`assert_clean`）。

token 帳：`claude -p` 自帶一段固定開銷（系統提示殘餘）。`overhead_probe()` 用一個幾乎空的
prompt 量它，報告時 raw 與 net（扣掉固定開銷）兩個數字都給。thinking 關掉
（`MAX_THINKING_TOKENS=0`），工具關掉（`--tools ""`），設定來源關掉。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import threading
import time

CLAUDE = "/opt/node22/bin/claude"
HERE = pathlib.Path(__file__).resolve().parent
CFG = pathlib.Path(os.environ.get("JUDGE_CFG", "/tmp/claude-0/judge_cfg"))
_lock = threading.Lock()
STRIP = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_MESSAGING_SOCKET",
         "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_REMOTE_SESSION_ID")
_BANNED = re.compile(r"responsib|punish|penal|責任|懲罰|處罰", re.I)


def assert_clean(system: str) -> None:
    if _BANNED.search(system):
        raise ValueError("KS-1：評審提示不可以有責任／懲罰類措辭")


def _key(model: str, system: str, prompt: str) -> str:
    return hashlib.sha256(json.dumps([model, system, prompt]).encode()).hexdigest()


class Judge:
    def __init__(self, exp: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self.model = model
        self.log = HERE / "results" / f"judge_calls_{exp}.jsonl"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.cache: dict[str, dict] = {}
        if self.log.exists():
            for ln in open(self.log, encoding="utf-8"):
                r = json.loads(ln)
                if r.get("ok"):
                    self.cache[r["key"]] = r
        CFG.mkdir(parents=True, exist_ok=True)
        (CFG / "settings.json").write_text("{}")

    def ask(self, system: str, prompt: str, tag: str) -> dict:
        assert_clean(system)
        k = _key(self.model, system, prompt)
        if k in self.cache:
            return self.cache[k]
        env = {kk: v for kk, v in os.environ.items() if kk not in STRIP}
        env.update(CLAUDE_CONFIG_DIR=str(CFG), MAX_THINKING_TOKENS="0")
        argv = [CLAUDE, "-p", prompt, "--model", self.model, "--system-prompt", system,
                "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
                "--setting-sources", "", "--no-session-persistence", "--output-format", "json"]
        rec = None
        for attempt in range(1, 5):
            t0 = time.time()
            p = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=300,
                               stdin=subprocess.DEVNULL, cwd=str(CFG))
            rec = {"key": k, "tag": tag, "model": self.model, "attempt": attempt,
                   "t": t0, "wall_s": round(time.time() - t0, 2), "rc": p.returncode,
                   "system": system, "prompt": prompt, "stderr": p.stderr[-2000:], "ok": False}
            try:
                d = json.loads(p.stdout)
                mu = (d.get("modelUsage") or {}).get(self.model) or {}
                rec.update(ok=(not d.get("is_error")), text=d.get("result"),
                           usage=d.get("usage"), model_usage=mu,
                           tokens_in=mu.get("inputTokens", 0) + mu.get("cacheReadInputTokens", 0)
                           + mu.get("cacheCreationInputTokens", 0),
                           tokens_out=mu.get("outputTokens", 0),
                           cost_usd=d.get("total_cost_usd"))
            except ValueError:
                rec["stdout"] = p.stdout[-2000:]
            with _lock, open(self.log, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if rec["ok"]:
                self.cache[k] = rec
                return rec
            time.sleep(2 * attempt)
        return rec  # 四次都失敗：呼叫端當 infra_void（unknown），不是 rejected


def parse_json(text: str | None):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def overhead_probe(j: Judge, n: int = 3) -> dict:
    """固定開銷：system='x'、prompt='x' 的輸入 token 數。"""
    xs = [j.ask("x", f"x{i}", f"overhead_probe_{i}") for i in range(n)]
    ins = [r["tokens_in"] for r in xs if r and r.get("ok")]
    return {"model": j.model, "input_tokens": ins, "fixed_overhead_in": min(ins) if ins else None}
