"""L0 substrate：真正的 Hermes Agent 當腦（vacant 跑在 Hermes 之上）。

waker 每次喚醒 → spawn `hermes -z`，HERMES_HOME 綁這個 vacant 的身體 →
Hermes 自己呼叫本地模型(LM Studio)、用該 HOME 的 skills/記憶/SOUL、自我進化。
vacant 只在外層包簽章/驗證/信譽/究責。Hermes 內部一行不改。
"""
from __future__ import annotations
import os, subprocess
from pathlib import Path
from typing import Any
from .substrate import Substrate, SubstrateResult, load_skills, save_skills, append_memory
from .tasks import NICHE_SOLVERS

HERMES_DIR = Path(os.path.expanduser("~/hermes-agent"))
HERMES_BIN = HERMES_DIR / "venv/bin/hermes"
BASE_URL = os.environ.get("VACANT_LMS_URL", "http://192.168.76.1:1234/v1")

NICHE_INSTR = {
  "reverse": "Reverse the order of the characters in the given string.",
  "caesar3": "Apply a Caesar cipher: shift each lowercase letter forward by 3 (a->d, b->e, ... x->a, y->b, z->c); leave digits and other characters unchanged.",
  "sort_chars": "Sort all characters of the given string in ascending ASCII order.",
  "sum_digits": "Add together all the digits that appear in the given string; give the integer sum.",
  "vowel_count": "Count how many vowels (a, e, i, o, u) appear in the given string; give the integer count.",
}
CONFIG_YAML = f"model:\n  provider: vllm\n  base_url: {BASE_URL}\n  default: google/gemma-4-e4b\n  context_length: 65536\n"

class HermesSubstrate(Substrate):
    def __init__(self, model="google/gemma-4-e4b", toolsets="", timeout=180, learn=True):
        self.model = model; self.toolsets = toolsets; self.timeout = timeout
        self.learn = learn   # 組合實驗要隔離跨任務累積時設 False
        self.substrate_id = f"hermes:{model}"

    def _ensure_home(self, home: Path):
        home.mkdir(parents=True, exist_ok=True)
        cfg = home / "config.yaml"
        if not cfg.exists():
            cfg.write_text(CONFIG_YAML, encoding="utf-8")

    def _ask(self, home: Path, prompt: str) -> str:
        self._ensure_home(home)
        env = dict(os.environ); env["HERMES_HOME"] = str(home); env["CUSTOM_BASE_URL"] = BASE_URL
        try:
            r = subprocess.run([str(HERMES_BIN), "-z", prompt, "-m", self.model, "--provider", "vllm", "-t", self.toolsets],
                               cwd=str(HERMES_DIR), env=env, capture_output=True, text=True, timeout=self.timeout)
            return (r.stdout or "").strip() or f"[empty rc={r.returncode}]"
        except subprocess.TimeoutExpired:
            return "[timeout]"

    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:
        if task is None:
            return SubstrateResult(self._ask(home, prompt), self.substrate_id, None)
        niche, inp = task["niche"], task["input"]
        skills = load_skills(home); instr = NICHE_INSTR.get(niche, "")
        hint = " (You have solved this kind of task before.)" if niche in skills else ""
        fb = (task.get("feedback") or "").strip()  # Composer verify-fix 互查回饋
        p = f"{instr}{hint} Output ONLY the answer, no other words, no quotes.\nInput: {inp}{(' ' + fb) if fb else ''}\nAnswer:"
        raw = self._ask(home, p)
        ans = (raw.splitlines()[-1].strip().strip('"').strip("'")) if raw else raw
        learned = None
        if self.learn and str(NICHE_SOLVERS[niche](inp)) == ans and niche not in skills:
            skills.add(niche); save_skills(home, skills); learned = niche
            append_memory(home, {"event": "skill_acquired", "niche": niche})
        return SubstrateResult(ans, self.substrate_id, learned)
