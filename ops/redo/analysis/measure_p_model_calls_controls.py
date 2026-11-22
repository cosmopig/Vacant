"""同一份正負控制比較三版分析器；隔離副本執行，不改動工作樹。"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[3]
    module = pathlib.Path("ops/redo/analysis/p_model_calls.py")
    test = pathlib.Path("tests/test_redo_p_model_calls.py")
    print("version         passed/total    pass rate", flush=True)
    for version in ("026ffeea3", "3c833a4e9", "working-tree"):
        source = (root / module).read_bytes() if version == "working-tree" else subprocess.check_output(
            ["git", "show", f"{version}:{module}"], cwd=root)
        with tempfile.TemporaryDirectory(prefix="p-model-controls-") as directory:
            copy = pathlib.Path(directory)
            (copy / module).parent.mkdir(parents=True)
            (copy / test).parent.mkdir(parents=True)
            (copy / module).write_bytes(source)
            (copy / test).write_bytes((root / test).read_bytes())
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test), "-q", "--junitxml=results.xml"],
                cwd=copy, text=True, capture_output=True)
            if result.returncode not in (0, 1):
                print(result.stdout + result.stderr)
                return result.returncode
            suites = ET.parse(copy / "results.xml").getroot().findall("testsuite")
            total = sum(int(s.get("tests", 0)) for s in suites)
            failed = sum(int(s.get(k, 0)) for s in suites for k in ("failures", "errors", "skipped"))
            if not total:
                raise RuntimeError("沒有收集到控制測試")
            print(f"{version:16}{total - failed}/{total:<12}{(total - failed) / total:.1%}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
