"""Guard: no tracked file may be a git conflict-residue file.

When ``git merge``/``git rebase`` hits a conflict and the user aborts or
resolves sloppily, git's rename-on-conflict leaves files named
``<original>~HEAD`` / ``<original>~<branch>`` (e.g. ``manifest.json~auto_argon``,
``dab_055-pi-C~HEAD``). If such a residue file gets ``git add``-ed and
committed, it is dead weight at best and a FileNotFoundError landmine at worst:
the 2026-11-07 auto/worker red light (r1218) contained exactly two tracked
residue files plus a broken absolute symlink that did not resolve in the
worker worktree.

Fix rule: conflict residue is never a deliverable -- delete it; if the real
file was lost, restore it from the branch that still has it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Basename ends with "~" + a git-ref-looking token (HEAD or a branch/tag name).
# Git's conflict rename is exactly "<original>~<ref>".
_RESIDUE = re.compile(r"~(HEAD|[A-Za-z0-9][A-Za-z0-9/._-]*)$")


def _tracked_paths() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO, check=True, capture_output=True, text=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def test_no_tracked_conflict_residue() -> None:
    bad = [p for p in _tracked_paths() if _RESIDUE.search(Path(p).name)]
    assert not bad, (
        "tracked git conflict-residue files (*~HEAD / *~<branch> are merge "
        f"abort residue, never a deliverable): {bad!r} -- delete them; restore "
        "the real file from the branch that still has it"
    )
