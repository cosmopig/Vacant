"""JSON command adapter for the project service (python cli.py REQUEST.json)."""
import argparse
import json
from pathlib import Path
import sys


def dispatch(data):
    from codec import loads
    from service import invoice
    tiers = loads(json.dumps(data["tiers"]))
    return invoice(data.get("lines", []), tiers, data.get("coupons"))


def read_request(path):
    if str(path) == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("request must be an object")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="JSON request path, or - for stdin")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = dispatch(read_request(args.request))
        raw = json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error":str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.output is None:
        sys.stdout.write(raw)
    else:
        args.output.write_text(raw, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
