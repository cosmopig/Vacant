"""ops.fl — Fast-lane single-round code runner for comparing zero-answer acceptance judges.

Compares home-made acceptance criteria (`EX`, `TF`, `XM`, `MV`, `CT`) that use NO bank
hidden tests and NO answers against a single-shot baseline (`B0`), a same-budget
multi-attempt baseline (`B0x3`), and an oracle-test upper bound (`GT`).

Reuses `ops.e1` sandbox (`bwrap --unshare-net` allowlist proxy, read-only credentials),
negative controls, evaluator sandbox, and atomic file helpers by import (no copies).
"""
from __future__ import annotations

import pathlib

from ops.e1 import (
    DEFAULT_EVALPLUS_DIR,
    DEFAULT_PI_CFG_DIR,
    EVALPLUS_SHA256,
    assert_ks1_clean,
    atomic_write_json,
    atomic_write_text,
    sha256_bytes,
    sha256_file,
    utc_now_iso,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_BANK_PATH = REPO_ROOT / "ops" / "gain" / "data" / "lcb_bank_v3.jsonl"
DEFAULT_INDEX_PATH = REPO_ROOT / "runs" / "INDEX.json"

PLAN_SCHEMA = "vacant.fl.plan/1"
RUN_SCHEMA = "vacant.fl.run/1"
RESULT_SCHEMA = "vacant.fl.task_result/1"
ANALYSIS_SCHEMA = "vacant.fl.analysis/1"

ARMS_FL: tuple[str, ...] = ("B0", "B0x3", "GT", "EX", "TF", "XM", "XMH", "XMVH", "MV", "CT")
JUDGE_ARMS: tuple[str, ...] = ("EX", "TF", "XM", "XMH", "XMVH", "MV", "CT")
GATED_RETRY_ARMS: tuple[str, ...] = ("GT", "EX", "TF", "XM", "XMH", "XMVH")

__all__ = [
    "ANALYSIS_SCHEMA",
    "ARMS_FL",
    "DEFAULT_BANK_PATH",
    "DEFAULT_EVALPLUS_DIR",
    "DEFAULT_INDEX_PATH",
    "DEFAULT_PI_CFG_DIR",
    "EVALPLUS_SHA256",
    "GATED_RETRY_ARMS",
    "JUDGE_ARMS",
    "PLAN_SCHEMA",
    "REPO_ROOT",
    "RESULT_SCHEMA",
    "RUN_SCHEMA",
    "assert_ks1_clean",
    "atomic_write_json",
    "atomic_write_text",
    "sha256_bytes",
    "sha256_file",
    "utc_now_iso",
]
