"""Wrapper: run repo mock_model unchanged, but also dump every raw request body to MOCK_RAW (jsonl)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_model as M
RAW = os.environ.get("MOCK_RAW")
_orig = M.H._body
def _body(self):
    b = _orig(self)
    if RAW:
        with open(RAW, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "path": self.path, "body": b}, ensure_ascii=False) + "\n")
    return b
M.H._body = _body
sys.exit(M.main())
