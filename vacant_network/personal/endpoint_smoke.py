"""§14 步驟 2：唯一的端點相容性預檢。

不帶 --dry-run 時正好送出一個請求，並計入 profile／相容性 4 次上限。
這個檔案被 import 時不連線。預設不要對任何端點執行它。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from vacant_network.brains import OpenAIBrain, _post

from .backend import brain_from_config
from .budget import BudgetLedger
from .runner import load_config


def build_payload(model_id: str, *, max_tokens: int) -> dict[str, Any]:
    return {
        "model": model_id,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": "Reply with the single word pong."},
            {"role": "user", "content": "ping"},
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="§14 Step 2 compatibility pre-check. One request, counted in the profile/compat budget. "
                    "Use --dry-run to print the payload without sending.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", help="where to write the smoke report")
    parser.add_argument("--dry-run", action="store_true", help="do not send a request")
    parser.add_argument("--max-tokens", type=int, default=16)
    args = parser.parse_args(argv)
    config = load_config(Path(args.config))
    model = config.get("model") or {}
    brain = brain_from_config(model)
    if not isinstance(brain, OpenAIBrain):
        print("compat-check expected an OpenAI-compatible brain", file=sys.stderr)
        return 2
    payload = build_payload(brain.model, max_tokens=args.max_tokens)
    url = brain.base_url + "/chat/completions"
    report: dict[str, Any] = {
        "schema_version": "vacant.personal.endpoint_smoke.v1",
        "step": "§14 Step 2 compatibility pre-check",
        "sent": False,
        "url": url,
        "request_has_max_tokens": "max_tokens" in payload,
        "request_has_tools": "tools" in payload,
        "model_id_configured": brain.model,
        "pricing": model.get("pricing"),
    }
    if args.dry_run:
        report["dry_run"] = True
        _emit(report, args.out)
        return 0
    ledger = BudgetLedger(config.get("budget"), pricing=str(model.get("pricing") or "unset"), rates=model)
    allowed, why = ledger.authorize(purpose="compat-check", estimated_output_tokens=args.max_tokens)
    if not allowed:
        print(f"compat-check not sent: {why}", file=sys.stderr)
        return 2
    started = time.perf_counter()
    try:
        body = _post(url, payload, brain.timeout, api_key=brain.api_key)
    except Exception as exc:  # noqa: BLE001 — 預檢失敗要落成報告，不能偷偷再打一通
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["wall_ms"] = int((time.perf_counter() - started) * 1000)
        _emit(report, args.out)
        print(report["error"], file=sys.stderr)
        return 1
    usage = body.get("usage") if isinstance(body, dict) else None
    message = {}
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        message = {}
    content = message.get("content")
    report.update({
        "sent": True,
        "requests": 1,
        "wall_ms": int((time.perf_counter() - started) * 1000),
        "response_model_id": body.get("model") if isinstance(body, dict) else None,
        "content_empty": content is None or content == "",
        "content_chars": len(content or ""),
        "usage_fields": sorted(usage) if isinstance(usage, dict) else None,
        "usage": usage if isinstance(usage, dict) else None,
        "pricing_note": "local; API USD is not inferred" if model.get("pricing") == "local" else "see budget rates",
    })
    _emit(report, args.out)
    return 0


def _emit(report: dict[str, Any], out: str | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    raise SystemExit(main())
