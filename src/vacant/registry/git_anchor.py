"""Git anchor for sealed Merkle epoch roots (anti-tamper layer 3 / technical.html §6-Layer Defense).

The Merkle root of every sealed epoch is also written to a git repository
("transparency log"). Once pushed to an external mirror, the commit SHA is
recorded back on the `MerkleEpoch` row. This makes the central registry's
history *externally auditable*: a third party who clones the transparency-log
repo can re-derive every root and verify the operator's epoch signature
without trusting the central database.

The anchor is intentionally separate from the OpenTimestamps anchor
(`ots_anchor.py`): git anchors give us human-readable, indexable history
backed by a hosting provider; OTS gives us calendar-server-backed
proof-of-existence with no hosting trust at all. Together they cover the
"git anchor" and "OpenTimestamps" rows of the 6-layer defense table.

Design constraints:
- Pure functions over `git` subprocess calls — no in-memory mutation of
  the registry; the store is responsible for persisting `git_commit_sha`
  + `pushed_at` back onto the `MerkleEpoch` row.
- Anchoring is *advisory*: if `git` is missing or the remote is
  unreachable, sealing must still succeed. The store calls
  `try_anchor_to_git(...)` which returns `GitAnchorReceipt | None`; the
  None branch means "we couldn't anchor this epoch right now, surface
  the failure to the operator but don't roll back the epoch".
- Repo layout is one file per epoch: `epochs/{epoch_id:08d}.json`,
  containing `{"epoch_id", "first_seq", "last_seq", "tree_size",
  "root_hex", "sealed_at", "registry_signature_hex"}`. Stable schema so
  external verifiers can be tiny scripts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vacant.registry.errors import RegistryError
from vacant.registry.models import MerkleEpoch

__all__ = [
    "DEFAULT_GIT_BRANCH",
    "GitAnchorError",
    "GitAnchorReceipt",
    "anchor_to_git",
    "epoch_to_anchor_payload",
    "git_available",
    "try_anchor_to_git",
]


DEFAULT_GIT_BRANCH = "transparency-log"


class GitAnchorError(RegistryError):
    """Raised by `anchor_to_git(...)` when the operator explicitly asked
    for hard-fail behavior and the anchor could not be written.

    `try_anchor_to_git(...)` swallows this and returns `None` instead.
    """


@dataclass(frozen=True)
class GitAnchorReceipt:
    """Outcome of a successful git anchor write.

    `commit_sha` is the local commit; `pushed` records whether the
    operator's remote push succeeded. We split the two because a local
    commit is still externally verifiable to anyone who can read the
    bare repo, even before push lands.
    """

    epoch_id: int
    commit_sha: str
    branch: str
    repo_path: str
    remote_url: str | None
    pushed: bool


def git_available() -> bool:
    """True iff a `git` executable is on PATH.

    Used by the store to decide whether to even attempt anchoring;
    keeps test environments without git from spamming subprocess
    errors.
    """
    return shutil.which("git") is not None


def epoch_to_anchor_payload(epoch: MerkleEpoch) -> dict[str, object]:
    """Build the JSON payload written to the transparency-log repo.

    The shape is deliberately minimal + stable: external verifiers only
    need the operator-signed root + sealing metadata. We include
    `registry_signature_hex` so a verifier can check the root signature
    against the operator's published pubkey without touching the DB.
    """
    return {
        "epoch_id": int(epoch.epoch_id or 0),
        "first_seq": int(epoch.first_seq),
        "last_seq": int(epoch.last_seq),
        "tree_size": int(epoch.tree_size),
        "root_hex": epoch.root_hash.hex(),
        "sealed_at": int(epoch.sealed_at),
        "registry_signature_hex": epoch.registry_signature.hex(),
    }


def _run_git(repo_path: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """Run a `git` subcommand inside `repo_path`. Raises `GitAnchorError`
    on non-zero exit, carrying stderr so operators can diagnose.

    We capture both stdout and stderr; on success we return stdout
    stripped, so callers can use the helper for `rev-parse HEAD` and
    similar one-liners.
    """
    # argv is constants + repo state; PATH-resolved `git` is intentional
    # (we pre-check with `git_available()` before getting here).
    git_cmd = ["git", *args]
    proc = subprocess.run(  # noqa: S603
        git_cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise GitAnchorError(
            f"git {' '.join(args)} failed in {repo_path}: "
            f"exit={proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _ensure_repo(repo_path: Path, branch: str) -> None:
    """Initialise `repo_path` as a git repo on `branch` if it isn't one.

    Idempotent. The branch is created at the initial commit if absent;
    subsequent calls reuse the existing branch.
    """
    repo_path.mkdir(parents=True, exist_ok=True)
    if not (repo_path / ".git").exists():
        _run_git(repo_path, "init", "-q", "-b", branch)
        # Seed config to keep `git commit` working without a global ~/.gitconfig.
        _run_git(repo_path, "config", "user.email", "transparency-log@vacant.local")
        _run_git(repo_path, "config", "user.name", "vacant-transparency-log")
        # The transparency log's authenticity comes from the embedded
        # Ed25519 `registry_signature` on each epoch payload — git's own
        # GPG/SSH commit signatures add no extra trust. Force-disable
        # signing on the LOCAL repo only so anchoring works on operator
        # machines that have `commit.gpgsign=true` set globally.
        _run_git(repo_path, "config", "commit.gpgsign", "false")
        _run_git(repo_path, "config", "tag.gpgsign", "false")
        # Create an initial empty commit so the branch exists before we add files.
        _run_git(repo_path, "commit", "--allow-empty", "-q", "-m", "initial empty commit")
        return
    # Repo exists — make sure the target branch exists and is checked out.
    branches = _run_git(repo_path, "branch", "--list", branch)
    if not branches:
        # No `branch` yet: check the current HEAD; if it's `main` we
        # rename it, otherwise create the branch off HEAD.
        head = _run_git(repo_path, "symbolic-ref", "--short", "HEAD")
        if head != branch:
            _run_git(repo_path, "checkout", "-q", "-b", branch)
    else:
        _run_git(repo_path, "checkout", "-q", branch)


def anchor_to_git(
    *,
    epoch: MerkleEpoch,
    repo_path: Path | str,
    branch: str = DEFAULT_GIT_BRANCH,
    remote_url: str | None = None,
    push: bool = False,
) -> GitAnchorReceipt:
    """Write `epoch`'s root payload to a transparency-log repo and commit it.

    Args:
        epoch: The sealed `MerkleEpoch` to anchor.
        repo_path: Filesystem path to the local transparency-log repo
            (created if absent).
        branch: Branch name to commit onto. Defaults to
            `transparency-log` (D006 anchor convention).
        remote_url: Optional remote URL. When non-None we run `git
            remote set-url origin <url>` so subsequent pushes know where
            to go; we don't fetch — the local commit is created either
            way.
        push: If True, attempt `git push origin <branch>` after committing.
            Failure to push raises `GitAnchorError` (the operator chose
            hard-fail by setting `push=True`); the local commit is
            preserved either way.

    Returns:
        `GitAnchorReceipt(epoch_id, commit_sha, branch, repo_path,
        remote_url, pushed)` on success.

    Raises:
        GitAnchorError: When `git` is missing, the repo is unusable, or
            a step (init / commit / push) fails.
    """
    if not git_available():
        raise GitAnchorError("git executable not found on PATH")
    if epoch.epoch_id is None:
        raise GitAnchorError("cannot anchor an epoch with no epoch_id (was it persisted?)")
    repo = Path(repo_path)
    _ensure_repo(repo, branch)

    epochs_dir = repo / "epochs"
    epochs_dir.mkdir(exist_ok=True)
    payload = epoch_to_anchor_payload(epoch)
    out_file = epochs_dir / f"{int(epoch.epoch_id):08d}.json"
    out_file.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _run_git(repo, "add", str(out_file.relative_to(repo)))
    # `--allow-empty` covers the case where the file already exists with
    # identical contents (re-anchoring the same epoch). Empty commits
    # still produce a SHA, which we record.
    _run_git(
        repo,
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        f"anchor epoch {int(epoch.epoch_id)} root={epoch.root_hash.hex()[:16]}",
    )
    commit_sha = _run_git(repo, "rev-parse", "HEAD")

    pushed = False
    if remote_url is not None:
        # Idempotent set-url so we don't care whether `origin` exists.
        remotes = _run_git(repo, "remote")
        if "origin" in remotes.splitlines():
            _run_git(repo, "remote", "set-url", "origin", remote_url)
        else:
            _run_git(repo, "remote", "add", "origin", remote_url)
    if push:
        # Push may fail (no remote configured, network down, auth). The
        # caller asked for hard-fail by setting push=True, so we raise.
        try:
            _run_git(repo, "push", "-q", "origin", branch)
            pushed = True
        except GitAnchorError:
            raise

    return GitAnchorReceipt(
        epoch_id=int(epoch.epoch_id),
        commit_sha=commit_sha,
        branch=branch,
        repo_path=str(repo),
        remote_url=remote_url,
        pushed=pushed,
    )


def try_anchor_to_git(
    *,
    epoch: MerkleEpoch,
    repo_path: Path | str,
    branch: str = DEFAULT_GIT_BRANCH,
    remote_url: str | None = None,
    push: bool = False,
) -> GitAnchorReceipt | None:
    """Best-effort wrapper: returns a `GitAnchorReceipt` on success, `None`
    on any failure.

    Use this from `seal_epoch(..., git_anchor=True)`: a missing `git`
    binary or unreachable remote must not block sealing — the operator
    can retry the anchor later via `vacant registry anchor <epoch>`
    without re-sealing the epoch.
    """
    try:
        return anchor_to_git(
            epoch=epoch,
            repo_path=repo_path,
            branch=branch,
            remote_url=remote_url,
            push=push,
        )
    except GitAnchorError:
        return None
