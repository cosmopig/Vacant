"""Demo CLI: `python -m vacant.mvp.demo --scenario=<name> [--substrate=<backend>] [--seed=N]`.

Prints a JSON-encoded `ScenarioResult` to stdout for piping into
`jq` / unit tests / fixture-snapshot tooling.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any

from vacant.mvp.scenarios import DEFAULT_SEEDS, get_runner
from vacant.substrate import (
    AnthropicSubstrate,
    DeterministicSubstrate,
    GeminiSubstrate,
    HermesSubstrate,
    MistralSubstrate,
    MockSubstrate,
    OllamaSubstrate,
    OpenAISubstrate,
    OpenClawSubstrate,
    SubstrateBackend,
)

_SUBSTRATE_CHOICES = (
    "mock",
    "deterministic",
    "anthropic",
    "ollama",
    "openai",
    "gemini",
    "mistral",
    "hermes",
    "openclaw",
)


def _build_substrate(name: str, *, seed: int) -> SubstrateBackend:
    if name == "mock":
        return MockSubstrate(seed=seed)
    if name == "deterministic":
        return DeterministicSubstrate()
    if name == "anthropic":
        return AnthropicSubstrate()
    if name == "ollama":
        return OllamaSubstrate()
    if name == "openai":
        return OpenAISubstrate()
    if name == "gemini":
        return GeminiSubstrate()
    if name == "mistral":
        return MistralSubstrate()
    if name == "hermes":
        return HermesSubstrate()
    if name == "openclaw":
        return OpenClawSubstrate()
    raise SystemExit(f"unknown substrate {name!r}")


def _serialise(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="vacant.mvp demo runner")
    parser.add_argument(
        "--scenario", required=True, choices=sorted(DEFAULT_SEEDS.keys()), help="scenario to run"
    )
    parser.add_argument(
        "--substrate",
        default="mock",
        choices=list(_SUBSTRATE_CHOICES),
        help="substrate backend (default: mock)",
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="override default seed for the scenario"
    )
    args = parser.parse_args(argv)

    scenario = args.scenario
    seed = args.seed if args.seed is not None else DEFAULT_SEEDS[scenario]
    substrate = _build_substrate(args.substrate, seed=seed)

    runner = get_runner(scenario)

    async def _go() -> Any:
        return await runner(substrate=substrate, seed=seed)

    result = asyncio.run(_go())
    json.dump(_serialise(result), sys.stdout, indent=2, default=str, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
