"""v3.3 的工作階段結束說明，在正式批次 C2 錄好的病歷上離線重跑（複本；原檔不動）。

用法：replay_ended.py <trial 目錄> <aborted 0|1> <final_answer 0|1>
v3 當時寫的那一筆 `ended` 會被截掉（只在複本上；截尾巴鏈仍然有效，head.json 跟著改），讓 v3.3 重寫。
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile

trial = pathlib.Path(sys.argv[1])
aborted = sys.argv[2] == "1"
final = sys.argv[3] == "1"
tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(trial / "agent" / "vacant_home", tmp / "vh")
os.environ["VACANT_HOME"] = str(tmp / "vh")

from vacant_network.trace import capture, zerostop  # noqa: E402
from vacant_network.trace.recorder import Recorder  # noqa: E402

capture.workspace_for = lambda cwd, _x=None: pathlib.Path("/app")
zerostop._run_child = zerostop.check
rec = Recorder("/app")
raw = rec.chain_path.read_text().splitlines()
cut = next((i for i, ln in enumerate(raw) if '"type":"ended"' in ln), None)
if cut is not None:
    e = json.loads(raw[cut])
    rec.chain_path.write_text("\n".join(raw[:cut]) + "\n")
    (rec.dir / "head.json").write_text(json.dumps({"seq": int(e["seq"]) - 1, "hash": e["prev_hash"]}))
    st = json.loads(rec.state_path.read_text())
    st["verified"] = None
    rec.state_path.write_text(json.dumps(st))
sid = next(e["session"] for e in rec.events() if e["type"] == "prompt" and e.get("source") == "user")
out = zerostop.ended("pi", sid, "/app", mode="evidence", turn=15 if final else 16, budget=15,
                     final_answer=final, final_text=None)
print(json.dumps(out.get("ended")))
print((rec.dir / "delivery.md").read_text())
