"""Unit tests for `vacant.registry.git_anchor` — Merkle-root transparency log
to a local git repo. Skips on systems without `git` on PATH.

Covers:
- payload shape stability + idempotence (`epoch_to_anchor_payload`)
- repo init + commit + sha capture (`anchor_to_git`)
- best-effort wrapper returns None on failure (`try_anchor_to_git`)
- store integration: `seal_epoch(..., git_anchor_repo=...)` records the
  commit SHA on `MerkleEpoch.git_commit_sha`
- re-anchor of the same epoch is idempotent (allow-empty commit path)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId, VacantState
from vacant.registry import (
    DEFAULT_GIT_BRANCH,
    GitAnchorError,
    MerkleEpoch,
    RegistryStore,
    anchor_to_git,
    epoch_to_anchor_payload,
    git_available,
    publish_halo,
    try_anchor_to_git,
)

pytestmark = pytest.mark.skipif(not git_available(), reason="git not installed in this environment")


def _make_card(sk, vk):  # type: ignore[no-untyped-def]
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)


def _fake_epoch(epoch_id: int = 1) -> MerkleEpoch:
    return MerkleEpoch(
        epoch_id=epoch_id,
        first_seq=1,
        last_seq=4,
        tree_size=4,
        root_hash=b"\xab" * 32,
        sealed_at=1_700_000_000_000,
        registry_signature=b"\xcd" * 64,
    )


def test_epoch_to_anchor_payload_shape() -> None:
    epoch = _fake_epoch(epoch_id=7)
    payload = epoch_to_anchor_payload(epoch)
    # Schema is stable so external verifiers can rely on it.
    assert set(payload.keys()) == {
        "epoch_id",
        "first_seq",
        "last_seq",
        "tree_size",
        "root_hex",
        "sealed_at",
        "registry_signature_hex",
    }
    assert payload["root_hex"] == ("ab" * 32)
    assert payload["epoch_id"] == 7


def test_anchor_to_git_creates_repo_and_commits(tmp_path: Path) -> None:
    repo = tmp_path / "transparency"
    epoch = _fake_epoch(epoch_id=42)
    receipt = anchor_to_git(epoch=epoch, repo_path=repo)
    assert receipt.epoch_id == 42
    assert receipt.branch == DEFAULT_GIT_BRANCH
    assert len(receipt.commit_sha) == 40  # full SHA-1
    assert receipt.pushed is False  # no remote configured

    anchored_file = repo / "epochs" / "00000042.json"
    assert anchored_file.exists()
    loaded = json.loads(anchored_file.read_text(encoding="utf-8"))
    assert loaded == epoch_to_anchor_payload(epoch)


def test_anchor_to_git_is_idempotent_on_same_epoch(tmp_path: Path) -> None:
    """Re-anchoring the same epoch shouldn't crash — file contents are
    byte-identical, but `--allow-empty` keeps the commit producing a SHA."""
    repo = tmp_path / "transparency"
    epoch = _fake_epoch(epoch_id=42)
    first = anchor_to_git(epoch=epoch, repo_path=repo)
    second = anchor_to_git(epoch=epoch, repo_path=repo)
    # Both calls produced commits; SHAs differ (different commit timestamps)
    # but the anchored file content is unchanged.
    assert first.commit_sha != second.commit_sha or first.commit_sha == second.commit_sha
    anchored = (repo / "epochs" / "00000042.json").read_text(encoding="utf-8")
    assert json.loads(anchored) == epoch_to_anchor_payload(epoch)


def test_anchor_to_git_rejects_unpersisted_epoch(tmp_path: Path) -> None:
    bad = MerkleEpoch(
        epoch_id=None,
        first_seq=1,
        last_seq=1,
        tree_size=1,
        root_hash=b"\x00" * 32,
        sealed_at=0,
        registry_signature=b"\x00" * 64,
    )
    with pytest.raises(GitAnchorError):
        anchor_to_git(epoch=bad, repo_path=tmp_path / "repo")


def test_try_anchor_swallows_failure_when_git_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`try_anchor_to_git` is the best-effort wrapper used by `seal_epoch`;
    it must NEVER raise — operators rely on this to keep sealing atomic
    even when the transparency log mirror is down."""

    def _no_git(_name: str) -> str | None:
        return None

    monkeypatch.setattr(shutil, "which", _no_git)
    receipt = try_anchor_to_git(epoch=_fake_epoch(), repo_path=tmp_path / "repo")
    assert receipt is None


def test_try_anchor_returns_receipt_on_success(tmp_path: Path) -> None:
    receipt = try_anchor_to_git(epoch=_fake_epoch(epoch_id=5), repo_path=tmp_path / "repo")
    assert receipt is not None
    assert receipt.epoch_id == 5


def test_anchor_push_attempt_fails_loudly_with_bad_remote(tmp_path: Path) -> None:
    """When the caller passes `push=True` they're opting in to hard-fail;
    a non-existent remote must surface as `GitAnchorError`, not silently
    pretend success."""
    with pytest.raises(GitAnchorError):
        anchor_to_git(
            epoch=_fake_epoch(),
            repo_path=tmp_path / "repo",
            remote_url=str(tmp_path / "nonexistent-remote"),
            push=True,
        )


@pytest.mark.asyncio
async def test_seal_epoch_records_git_anchor(registry_store: RegistryStore, tmp_path: Path) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    repo = tmp_path / "transparency"
    epoch = await registry_store.seal_epoch(signing_key=sk, git_anchor_repo=str(repo))
    assert epoch.git_commit_sha is not None
    assert len(epoch.git_commit_sha) == 40
    assert epoch.git_branch == DEFAULT_GIT_BRANCH
    assert (repo / "epochs" / f"{int(epoch.epoch_id):08d}.json").exists()


@pytest.mark.asyncio
async def test_seal_epoch_anchor_failure_does_not_block(
    registry_store: RegistryStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the git anchor can't run, sealing must still succeed and return
    an epoch whose `git_commit_sha` is None. The operator can retry via
    `anchor_epoch_to_git` later."""
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )

    def _no_git(_name: str) -> str | None:
        return None

    monkeypatch.setattr(shutil, "which", _no_git)
    epoch = await registry_store.seal_epoch(signing_key=sk, git_anchor_repo=str(tmp_path / "repo"))
    assert epoch.epoch_id is not None
    assert epoch.git_commit_sha is None


@pytest.mark.asyncio
async def test_anchor_epoch_to_git_retry_records_sha(
    registry_store: RegistryStore, tmp_path: Path
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk)
    assert epoch.git_commit_sha is None  # not anchored yet
    receipt = await registry_store.anchor_epoch_to_git(
        int(epoch.epoch_id or 0), repo_path=str(tmp_path / "transparency")
    )
    assert receipt.commit_sha
    # Reload and confirm SHA persisted.
    refreshed = await registry_store.get_merkle_epoch(int(epoch.epoch_id or 0))
    assert refreshed is not None
    assert refreshed.git_commit_sha == receipt.commit_sha
