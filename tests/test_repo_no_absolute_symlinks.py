"""Guard: no tracked file may be a symlink to an absolute path.

A committed absolute symlink (target string starts with "/") is only
resolvable on the machine that created it. Any other checkout -- fresh clone,
CI worktree on another host, another worktree of this repo -- sees a BROKEN
file and fails with FileNotFoundError.

This is the exact defect class that red-lit auto/worker CI on 2026-11-07
(real_slice_dab055/manifest.json committed as an absolute symlink whose target
did not exist in the worker worktree). The last remaining offender on
auto/qwen27b was audits/e016_failed_step_ablation_r905_attempt1_envleak_recompute.py
-> /home/user1/dev/ops/audits/... (r1219, vq-0tr).

Fix rule: target inside the repo -> RELATIVE symlink; target outside the repo
-> commit the real file (or drop the pointer).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _tracked_symlinks() -> list[tuple[str, str]]:
    """(path, committed target string) for every tracked symlink (mode 120000)."""
    out = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=REPO, check=True, capture_output=True, text=True,
    ).stdout
    blobs: dict[str, str] = {}
    result: list[tuple[str, str]] = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)  # "mode sha stage<TAB>path"
        mode, sha, _stage = meta.split(" ")
        if mode != "120000":
            continue
        if sha not in blobs:
            blobs[sha] = subprocess.run(
                ["git", "cat-file", "blob", sha],
                cwd=REPO, check=True, capture_output=True, text=True,
            ).stdout
        result.append((path, blobs[sha]))
    return result


def test_no_tracked_absolute_symlinks() -> None:
    bad = [(p, t) for p, t in _tracked_symlinks() if t.startswith("/")]
    assert not bad, (
        "tracked absolute symlinks (broken on any other checkout/machine): "
        f"{bad!r} -- use a relative link for in-repo targets, or commit the "
        "real file for out-of-repo targets"
    )
