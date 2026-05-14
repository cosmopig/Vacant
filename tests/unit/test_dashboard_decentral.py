"""Tests for the `去中心化信任` page helpers in `vacant.mvp.dashboard`.

The dashboard module runs `main()` at import time, so importing it
inside a test has side effects. We import-time-protect by stubbing
`streamlit.set_page_config`/`sidebar.radio` to no-op and skip the actual
streamlit rendering — only the pure helper (`_epoch_anchor_summary`) is
exercised here. The full page-render is integration-tested by running
streamlit out-of-band; this test just locks the helper's output shape.
"""

from __future__ import annotations

from vacant.mvp import dashboard as d
from vacant.registry import MerkleEpoch


def test_epoch_anchor_summary_full_row_shape() -> None:
    e = MerkleEpoch(
        epoch_id=7,
        first_seq=1,
        last_seq=4,
        tree_size=4,
        root_hash=b"\xab" * 32,
        sealed_at=1_700_000_000_000,
        registry_signature=b"\xcd" * 64,
        git_commit_sha="0123456789abcdef0123456789abcdef01234567",
        git_branch="transparency-log",
        pushed_at=1_700_000_001_000,
        ots_proof_hash=b"\xee" * 32,
        ots_upgraded_at=1_700_000_002_000,
    )
    row = d._epoch_anchor_summary(e)
    assert row["epoch_id"] == 7
    assert row["tree_size"] == 4
    assert row["root_hex"].startswith("ab" * 4)  # first 8 hex chars match
    assert row["git_commit_sha"] == "0123456789ab"  # truncated to 12
    assert row["git_branch"] == "transparency-log"
    assert row["ots_pending"] == "✅"
    assert row["ots_upgraded"] == "✅"


def test_epoch_anchor_summary_empty_anchors_render_dashes() -> None:
    e = MerkleEpoch(
        epoch_id=1,
        first_seq=1,
        last_seq=1,
        tree_size=1,
        root_hash=b"\x00" * 32,
        sealed_at=1,
        registry_signature=b"\x00" * 64,
    )
    row = d._epoch_anchor_summary(e)
    assert row["git_commit_sha"] == "—"
    assert row["git_branch"] == "transparency-log"  # schema default
    assert row["pushed_at"] == "—"
    assert row["ots_pending"] == "—"
    assert row["ots_upgraded"] == "—"


def test_decentralized_trust_page_registered() -> None:
    """The new page must be in the PAGES dict so the sidebar renders it."""
    assert "去中心化信任" in d.PAGES
    assert d.PAGES["去中心化信任"] is d.render_decentralized_trust
