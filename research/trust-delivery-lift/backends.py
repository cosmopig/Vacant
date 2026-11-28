"""Small-model backends for the lift study."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Protocol


class ChatBackend(Protocol):
    def complete(self, system: str, user: str, *, max_new_tokens: int = 512) -> "CallResult": ...


@dataclass
class CallResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


class StubBackend:
    """Deterministic backend for unit tests."""

    def complete(self, system: str, user: str, *, max_new_tokens: int = 512) -> CallResult:
        m = re.search(r"TASK_ID:\s*(\S+)", user)
        tid = m.group(1) if m else "unknown"
        gold = {}
        gm = re.search(r"GOLD_HINT:\s*(\{.*\})", user)
        if gm:
            gold = json.loads(gm.group(1))
        partial = {k: (v if k != list(gold.keys())[-1] else f"WRONG_{v}") for k, v in gold.items()} if gold else {}
        return CallResult(json.dumps(partial, ensure_ascii=False), 10, 20, 0.01)


class TransformersBackend:
    def __init__(self, model_id: str = "Qwen/Qwen2.5-0.5B-Instruct", device: str = "cpu") -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # lazy

        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id)
        self.model.to(device)
        self.device = device

    def complete(self, system: str, user: str, *, max_new_tokens: int = 512) -> CallResult:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        t0 = time.perf_counter()
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        prompt_tokens = int(inputs["input_ids"].shape[-1])
        out = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        latency = time.perf_counter() - t0
        gen = out[0][prompt_tokens:]
        completion_tokens = int(gen.shape[-1])
        decoded = self.tokenizer.decode(gen, skip_special_tokens=True)
        return CallResult(decoded, prompt_tokens, completion_tokens, latency)