"""Small-model backend with sampling and mean logprob."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import torch


@dataclass
class GenResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    mean_logprob: float | None = None


class SmallLM:
    def __init__(self, model_id: str = "Qwen/Qwen2.5-0.5B-Instruct") -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id)
        self.model.eval()
        self.device = "cpu"
        self.model.to(self.device)

    def _encode_chat(self, system: str, user: str) -> torch.Tensor:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return self.tokenizer(text, return_tensors="pt").to(self.device)

    def generate(
        self,
        system: str,
        user: str,
        *,
        max_new_tokens: int = 256,
        temperature: float = 0.0,
        with_logprob: bool = False,
    ) -> GenResult:
        inputs = self._encode_chat(system, user)
        prompt_len = int(inputs["input_ids"].shape[-1])
        t0 = time.perf_counter()
        gen_kw: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            gen_kw.update(do_sample=True, temperature=temperature)
        else:
            gen_kw.update(do_sample=False)
        if with_logprob:
            gen_kw.update(return_dict_in_generate=True, output_scores=True)
        out = self.model.generate(**inputs, **gen_kw)
        latency = time.perf_counter() - t0
        mean_lp = None
        if with_logprob:
            seq = out.sequences[0]
            gen_ids = seq[prompt_len:]
            scores = out.scores
            lps = []
            for i, tid in enumerate(gen_ids):
                if i >= len(scores):
                    break
                logp = torch.log_softmax(scores[i][0], dim=-1)[tid].item()
                lps.append(logp)
            mean_lp = sum(lps) / len(lps) if lps else None
            decoded = self.tokenizer.decode(gen_ids, skip_special_tokens=True)
        else:
            decoded = self.tokenizer.decode(out[0][prompt_len:], skip_special_tokens=True)
        comp = len(self.tokenizer.encode(decoded, add_special_tokens=False))
        return GenResult(decoded, prompt_len, comp, latency, mean_lp)