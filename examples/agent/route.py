"""Thin shim around ``vacant route`` for users who'd rather invoke
the script directly. Prefer::

    uvx --from vacant-network vacant route \\
      --name alice --model gemma4:e2b \\
      "Translate this..."

The module-level logic lives in ``vacant.cli.route`` so it's also
reachable from any host that has the vacant-network wheel installed.
"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    from vacant.cli import route as route_mod

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prompt", help="User task")
    p.add_argument("--name", default=os.environ.get("VACANT_NAME", "alice"))
    p.add_argument("--model", default=os.environ.get("LLM_MODEL", "gemma4:e2b"))
    p.add_argument(
        "--base-url",
        default=os.environ.get("LLM_BASE_URL") or os.environ.get("OLLAMA_BASE_URL"),
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("LLM_API_KEY") or os.environ.get("OLLAMA_API_KEY") or "",
    )
    p.add_argument("--max-rounds", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--vacant-home", default=os.environ.get("VACANT_HOME"))
    p.add_argument("--uvx", default=os.environ.get("UVX", "uvx"))
    args = p.parse_args()
    if not args.base_url:
        print(
            "error: --base-url (or LLM_BASE_URL / OLLAMA_BASE_URL env) required",
            file=sys.stderr,
        )
        return 2
    return route_mod.main(
        prompt=args.prompt,
        name=args.name,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        max_rounds=args.max_rounds,
        temperature=args.temperature,
        vacant_home=args.vacant_home,
        uvx=args.uvx,
    )


if __name__ == "__main__":
    raise SystemExit(main())
