#!/usr/bin/env python3
"""Render a pi models.json from models.json.tmpl and a vLLM config (stdlib only).

Sets baseUrl (default http://127.0.0.1:8000/v1), model id, contextWindow (= max_model_len),
maxTokens, and reasoning settings for colab-vllm / colab-vllm-nothink / colab-vllm-think
(plus any custom provider_name requested by config or --provider).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import sys
from typing import Any


def build_provider_entry(
    *,
    base_url: str,
    api_key: str,
    model_id: str,
    label: str,
    context_window: int,
    max_tokens: int,
    reasoning_on: bool,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    model_obj: dict[str, Any] = {
        "id": model_id,
        "name": f"{model_id} ({label})",
        "reasoning": bool(reasoning_on),
        "contextWindow": int(context_window),
        "maxTokens": int(max_tokens),
    }
    if not reasoning_on:
        model_obj["samplingParams"] = {"reasoning_effort": "none"}
    elif reasoning_effort:
        model_obj["samplingParams"] = {"reasoning_effort": reasoning_effort}

    return {
        "baseUrl": base_url,
        "api": "openai-completions",
        "apiKey": api_key,
        "compat": {
            "supportsDeveloperRole": False,
            "supportsReasoningEffort": bool(reasoning_on),
        },
        "models": [model_obj],
    }


def render(
    template_path: pathlib.Path,
    *,
    base_url: str,
    model_id: str,
    context_window: int,
    max_tokens: int,
    api_key: str,
    provider_name: str,
    reasoning_mode: str,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    tmpl = json.loads(template_path.read_text(encoding="utf-8"))
    out = copy.deepcopy(tmpl)
    reasoning_on = reasoning_mode.lower() in ("on", "true", "1", "yes")

    providers = out.setdefault("providers", {})
    providers["colab-vllm"] = build_provider_entry(
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
        label="colab-vllm",
        context_window=context_window,
        max_tokens=max_tokens,
        reasoning_on=reasoning_on,
        reasoning_effort=reasoning_effort,
    )
    providers["colab-vllm-nothink"] = build_provider_entry(
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
        label="colab-vllm-nothink",
        context_window=context_window,
        max_tokens=max_tokens,
        reasoning_on=False,
    )
    providers["colab-vllm-think"] = build_provider_entry(
        base_url=base_url,
        api_key=api_key,
        model_id=model_id,
        label="colab-vllm-think",
        context_window=context_window,
        max_tokens=max_tokens,
        reasoning_on=True,
        reasoning_effort=reasoning_effort,
    )
    if provider_name and provider_name not in providers:
        providers[provider_name] = build_provider_entry(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
            label=provider_name,
            context_window=context_window,
            max_tokens=max_tokens,
            reasoning_on=reasoning_on,
            reasoning_effort=reasoning_effort,
        )

    out["defaultProvider"] = provider_name or ("colab-vllm-think" if reasoning_on else "colab-vllm-nothink")
    out["defaultModel"] = model_id
    return out


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", default=str(here / "models.json.tmpl"))
    ap.add_argument("--config", help="vLLM config JSON (sets defaults for model, max_model_len, port, reasoning)")
    ap.add_argument("--out", help="Output path for models.json (required unless --dry-run)")
    ap.add_argument("--base-url", help="Override OpenAI-compatible baseUrl (default: http://<host>:<port>/v1)")
    ap.add_argument("--model", help="Override served model id")
    ap.add_argument("--max-model-len", type=int, help="Override contextWindow (= vLLM max_model_len)")
    ap.add_argument("--max-tokens", type=int, help="Override maxTokens")
    ap.add_argument("--api-key", default=None, help="Override apiKey (default: vllm-local)")
    ap.add_argument("--provider", help="Default/alias provider name")
    ap.add_argument("--reasoning", choices=("off", "on"), help="Default reasoning setting for colab-vllm / alias")
    ap.add_argument("--reasoning-effort", help="Optional samplingParams.reasoning_effort when reasoning=on")
    ap.add_argument("--dry-run", action="store_true", help="Print rendered JSON to stdout without writing")
    args = ap.parse_args(argv)

    cfg: dict[str, Any] = {}
    if args.config:
        cfg = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8"))

    host = str(cfg.get("host", "127.0.0.1"))
    port = int(cfg.get("port", 8000))
    base_url = args.base_url or cfg.get("base_url") or f"http://{host}:{port}/v1"
    model_id = args.model or cfg.get("served_model_name") or "gemma-4-12b-it-qat"
    context_window = int(args.max_model_len or cfg.get("max_model_len") or 262144)
    max_tokens = int(args.max_tokens or cfg.get("max_tokens") or 16384)
    api_key = args.api_key or cfg.get("api_key") or "vllm-local"
    reasoning_mode = args.reasoning or str(cfg.get("reasoning", "off"))
    reasoning_effort = args.reasoning_effort or cfg.get("reasoning_effort")
    default_provider = args.provider or cfg.get("provider_name") or (
        "colab-vllm-think" if reasoning_mode.lower() in ("on", "true", "1", "yes") else "colab-vllm-nothink"
    )

    rendered = render(
        pathlib.Path(args.template),
        base_url=base_url,
        model_id=model_id,
        context_window=context_window,
        max_tokens=max_tokens,
        api_key=api_key,
        provider_name=default_provider,
        reasoning_mode=reasoning_mode,
        reasoning_effort=reasoning_effort,
    )
    text = json.dumps(rendered, ensure_ascii=False, indent=2) + "\n"

    if args.dry_run:
        sys.stdout.write(text)
        return 0

    if not args.out:
        print("error: --out is required unless --dry-run is set", file=sys.stderr)
        return 2

    out_path = pathlib.Path(os.path.expanduser(args.out))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + f".tmp.{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
