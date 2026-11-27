#!/usr/bin/env python3
"""redo-claude-agent-poly — same sandbox as claude_sandbox_agent.py, with C++/Go/Rust toolchains reachable.

Only the child environment differs (decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HAIKUBAND.md, candidate 2):
PATH gains /opt/polytools/rust/bin (a copy of the stable Rust toolchain, because /root is denied) and /usr/local/go/bin;
build caches go under <workspace>/node_modules/ (a directory name redo.py skips when it copies workspaces), no network
(GOPROXY=off, CARGO_NET_OFFLINE=true). Filesystem deny rules, tools, permission flags are the base module's, unchanged.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import claude_sandbox_agent as base  # noqa: E402

_orig_clean_env = base.clean_env


def clean_env(home: pathlib.Path) -> dict[str, str]:
    env = _orig_clean_env(home)
    ws = pathlib.Path.cwd().resolve()
    cache = ws / "node_modules" / ".polycache"
    env["PATH"] = f"/opt/polytools/rust/bin:/usr/local/go/bin:{env['PATH']}"
    env.update({"GOCACHE": str(cache / "go-build"), "GOPATH": str(cache / "gopath"), "GOFLAGS": "-mod=mod", "GOPROXY": "off",
                "GOTOOLCHAIN": "local", "CARGO_HOME": str(cache / "cargo"), "CARGO_TARGET_DIR": str(cache / "target"),
                "CARGO_NET_OFFLINE": "true"})
    return env


base.clean_env = clean_env

if __name__ == "__main__":
    raise SystemExit(base.main(sys.argv[1:]))
