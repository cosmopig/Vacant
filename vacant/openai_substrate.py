"""B 層 substrate：把『腦』換成本地真模型（OpenAI 相容端點，如 LM Studio）。

與 EchoSubstrate 同介面，但真的呼叫模型解可檢查任務；解對且尚未習得該 niche →
把「方法提示」寫回 HERMES_HOME 當 skill，下次同 niche 注入提示（context engineering
= 規格的 skills）。於是「越用越準」可在真模型上觀測，而非模擬。
"""
from __future__ import annotations
import json, urllib.request
from pathlib import Path
from typing import Any
from .substrate import Substrate, SubstrateResult, load_skills, save_skills, append_memory
from .tasks import NICHE_SOLVERS

HINTS = {
 "reverse": "Reverse the characters of the input string.",
 "caesar3": "Caesar cipher: shift each lowercase letter forward by 3 (a->d, z->c), leave others unchanged.",
 "sort_chars": "Sort all characters of the input ascending.",
 "sum_digits": "Sum every digit in the input; output the integer.",
 "vowel_count": "Count vowels aeiou in the input; output the integer.",
}

class OpenAISubstrate(Substrate):
    def __init__(self, base_url: str, model: str = "local", timeout: int = 60,
                 temperature: float = 0.0, learn: bool = True):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature   # >0 給多次取樣多樣性（naive 自一致 / 重試）
        self.learn = learn               # 跨任務 skill 累積；組合實驗要隔離效應時設 False
        self.substrate_id = f"lmstudio:{model}"

    def _chat(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.model, "temperature": self.temperature, "max_tokens": 64,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            d = json.load(r)
        return (d["choices"][0]["message"]["content"] or "").strip()

    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:
        if task is None:
            return SubstrateResult(self._chat("You are helpful.", prompt), self.substrate_id, None)
        niche, inp = task["niche"], task["input"]
        skills = load_skills(home)
        sysmsg = "You solve small string puzzles. Output ONLY the answer token, no prose, no quotes."
        if niche in skills and niche in HINTS:
            sysmsg += " Method you have used before: " + HINTS[niche]
        # 互查回饋（Composer 的 verify-fix 迴圈會把「先前答案錯」放進 task['feedback']）
        user = f"Task type [{niche}] on input: {inp}\nAnswer:"
        fb = (task.get("feedback") or "").strip()
        if fb:
            user = f"Task type [{niche}] on input: {inp}.{fb}\nAnswer:"
        raw = self._chat(sysmsg, user)
        ans = raw.splitlines()[0].strip().strip('"').strip("'") if raw else raw
        learned = None
        if self.learn:
            truth = str(NICHE_SOLVERS[niche](inp))
            if ans == truth and niche not in skills:
                skills.add(niche); save_skills(home, skills); learned = niche
                append_memory(home, {"event": "skill_acquired", "niche": niche})
        return SubstrateResult(ans, self.substrate_id, learned)


class ResponsesSubstrate(Substrate):
    """LM Studio /api/v1/chat（responses-style）—— 給 reasoning 模型用。

    reasoning 模型在 OpenAI /v1 的 message.content 常為空（答案被放進 reasoning_content）；
    /api/v1/chat 回 output=[{type:reasoning},{type:message}]，取 message 即最終答案。
    介面/feedback/learn 與 OpenAISubstrate 一致，可直接給 Composer 用。
    """
    def __init__(self, base_url: str, model: str, timeout: int = 200,
                 learn: bool = False):
        # base_url 給 http://host:1234（可含 /v1，會自動去掉）
        self.base = base_url.rstrip("/")
        if self.base.endswith("/v1"):
            self.base = self.base[:-3]
        self.model = model
        self.timeout = timeout
        self.learn = learn
        self.substrate_id = f"lmstudio-resp:{model}"

    def _chat(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.model, "system_prompt": system, "input": user}).encode()
        req = urllib.request.Request(self.base + "/api/v1/chat", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            d = json.load(r)
        msgs = [o.get("content", "") for o in d.get("output", []) if o.get("type") == "message"]
        return (msgs[-1] if msgs else "").strip()

    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:
        if task is None:
            return SubstrateResult(self._chat("You are helpful.", prompt), self.substrate_id, None)
        niche, inp = task["niche"], task["input"]
        sysmsg = "You solve small string puzzles. Output ONLY the answer, no prose, no quotes."
        user = f"Task type [{niche}] on input: {inp}"
        fb = (task.get("feedback") or "").strip()
        if fb:
            user += f".{fb}"
        user += "\nAnswer:"
        raw = self._chat(sysmsg, user)
        ans = raw.splitlines()[-1].strip().strip('"').strip("'") if raw else raw
        return SubstrateResult(ans, self.substrate_id, None)
