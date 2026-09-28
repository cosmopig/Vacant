#!/usr/bin/env python3
"""Read-only score replay for the archived R534 A/C361 native Pi cells.

Only score.json and the presence of app_final/solution.py are read from each
archive. No agent code, archived credentials, or test bytecode is extracted or
executed. This estimates a one-shot GATE from already recorded visible scores;
it cannot estimate CONFORM/REPAIR or the benefit of a new agent session.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import tarfile


def replay(manifest: pathlib.Path, archive_root: pathlib.Path) -> dict:
    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    pairs: dict[str, dict[str, bool]] = collections.defaultdict(dict)
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        name, expected_sha, size, expected_cells, _created = line.split("\t")
        matches = list(archive_root.rglob(name)) + list(archive_root.rglob(name + ".bin"))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one archive for {name}: {len(matches)}")
        archive = matches[0]
        data = archive.read_bytes()
        if len(data) != int(size) or hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError(f"archive checksum mismatch: {name}")
        checked += 1
        with tarfile.open(archive, "r:xz") as tf:
            members = {m.name: m for m in tf if m.isfile()}
            seen_cells = 0
            for member_name, member in members.items():
                if not member_name.startswith("cells/") or not member_name.endswith("/score.json"):
                    continue
                cell = member_name.split("/")[1]
                parts = cell.split("-", 2)
                if len(parts) != 3 or parts[1] not in {"A", "C361"}:
                    continue
                seen_cells += 1
                score_file = tf.extractfile(member)
                assert score_file is not None
                score = json.load(score_file)
                arm = parts[1]
                hidden = score.get("pass") is True
                visible = score.get("visible_pass") is True
                has_file = f"cells/{cell}/app_final/solution.py" in members
                c = counts[arm]
                c["cells"] += 1
                c["hidden_pass"] += hidden
                c["visible_pass"] += visible
                c["submitted_file"] += has_file
                c["wrong_submitted_file"] += has_file and not hidden
                c["gate_released_correct"] += has_file and visible and hidden
                c["gate_released_wrong"] += has_file and visible and not hidden
                c["gate_refused_file"] += has_file and not visible
                if f"cells/{cell}/app_final/tests_visible/test_visible.py" not in members:
                    c["visible_source_absent"] += 1
                key = parts[0] + "-ARM-" + parts[2]
                if arm in pairs[key]:
                    raise ValueError(f"duplicate cell {cell}")
                pairs[key][arm] = hidden
            if seen_cells != int(expected_cells):
                raise ValueError(f"cell count mismatch in {name}: {seen_cells}")
    paired = collections.Counter(f"A={x['A']},C361={x['C361']}"
                                 for x in pairs.values() if set(x) == {"A", "C361"})
    return {"archives_sha256_verified": checked,
            "arms": {k: dict(v) for k, v in sorted(counts.items())},
            "paired_cells": sum(set(x) == {"A", "C361"} for x in pairs.values()),
            "paired_hidden_pass": dict(sorted(paired.items())),
            "scope": "recorded scores only; no candidate execution or new agent sessions"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--archive-root", type=pathlib.Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.manifest, args.archive_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
