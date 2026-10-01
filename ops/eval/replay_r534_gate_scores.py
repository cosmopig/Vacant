#!/usr/bin/env python3
"""Read-only score replay for the archived R534 A/C361 native Pi cells.

Only score.json and the presence of app_final/solution.py are read from each
archive. No agent code, archived credentials, or test bytecode is extracted or
executed. This estimates a one-shot GATE from already recorded visible scores;
it cannot estimate CONFORM/REPAIR or the benefit of a new agent session.

The 43 archives are ONE archive holding two campaigns, told apart by the first
dash-separated part of the cell name (`<campaign>-<arm>-<task>`):

- `calib1` (chunks 0001-0004; 20 tasks x 2 arms): a throughput calibration that the
  Colab RUNLOG declares "not the preregistered batch, scores not to be looked at",
  scored with the pre-freeze scorer;
- `c5` (chunks 0006-0042; 920 tasks x 2 arms): the formal batch.

Results are reported per campaign (`campaigns`); that is the whole default output. With
`--campaign c5` the top-level `arms` / `paired_*` keys hold that one campaign (the C5 README's
748 / 758 and exact McNemar p=0.3866 are c5 only). The two campaigns MERGED (940 cells per arm,
two scorer versions) are only printed with `--merged`, under `merged_*` keys, and must not be
quoted as the C5 batch.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import tarfile


def _summary(counts: dict[str, collections.Counter], pairs: dict[str, dict[str, bool]]) -> dict:
    paired = collections.Counter(f"A={x['A']},C361={x['C361']}"
                                 for x in pairs.values() if set(x) == {"A", "C361"})
    return {"arms": {k: dict(v) for k, v in sorted(counts.items())},
            "paired_cells": sum(set(x) == {"A", "C361"} for x in pairs.values()),
            "paired_hidden_pass": dict(sorted(paired.items()))}


def replay(manifest: pathlib.Path, archive_root: pathlib.Path,
           campaign: str | None = None, merged: bool = False) -> dict:
    """`campaign` (e.g. "c5") keeps only the cells whose name starts with `<campaign>-`.
    `merged=True` (no campaign filter) adds the cross-campaign totals as `merged_*` keys."""
    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    pairs: dict[str, dict[str, bool]] = collections.defaultdict(dict)
    camp_counts: dict[str, dict[str, collections.Counter]] = {}
    camp_pairs: dict[str, dict[str, dict[str, bool]]] = {}
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
                camp, arm = parts[0], parts[1]
                if campaign is not None and camp != campaign:
                    continue
                score_file = tf.extractfile(member)
                assert score_file is not None
                score = json.load(score_file)
                hidden = score.get("pass") is True
                visible = score.get("visible_pass") is True
                has_file = f"cells/{cell}/app_final/solution.py" in members
                visible_absent = f"cells/{cell}/app_final/tests_visible/test_visible.py" not in members
                per_camp = camp_counts.setdefault(camp, collections.defaultdict(collections.Counter))
                for c in (counts[arm], per_camp[arm]):
                    c["cells"] += 1
                    c["hidden_pass"] += hidden
                    c["visible_pass"] += visible
                    c["submitted_file"] += has_file
                    c["wrong_submitted_file"] += has_file and not hidden
                    c["gate_released_correct"] += has_file and visible and hidden
                    c["gate_released_wrong"] += has_file and visible and not hidden
                    c["gate_refused_file"] += has_file and not visible
                    c["visible_source_absent"] += visible_absent
                key = camp + "-ARM-" + parts[2]
                if arm in pairs[key]:
                    raise ValueError(f"duplicate cell {cell}")
                pairs[key][arm] = hidden
                camp_pairs.setdefault(camp, collections.defaultdict(dict))[key][arm] = hidden
            if seen_cells != int(expected_cells):
                raise ValueError(f"cell count mismatch in {name}: {seen_cells}")
    out = {"archives_sha256_verified": checked,
           "campaign_filter": campaign,
           "campaigns": {name: _summary(camp_counts[name], camp_pairs[name])
                         for name in sorted(camp_counts)},
           "scope": "recorded scores only; no candidate execution or new agent sessions"}
    if campaign is not None:
        out.update(_summary(counts, pairs))
        out["scope_note"] = (f"`arms` / `paired_*` are only campaign {campaign!r}; the same "
                             f"numbers are under `campaigns.{campaign}`")
    elif merged:
        total = _summary(counts, pairs)
        out["merged_arms"] = total["arms"]
        out["merged_paired_cells"] = total["paired_cells"]
        out["merged_paired_hidden_pass"] = total["paired_hidden_pass"]
        out["merged_note"] = ("the `merged_*` keys add every campaign in the archive (calib1 + "
                              "c5, scored by different scorer versions): do NOT quote them as "
                              "the C5 batch, use `campaigns.c5`")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=pathlib.Path, required=True)
    parser.add_argument("--archive-root", type=pathlib.Path, required=True)
    parser.add_argument("--campaign",
                        help="only cells of this campaign (c5 = the formal 920-task batch, "
                             "calib1 = the 20-task throughput calibration); default: all, "
                             "reported per campaign")
    parser.add_argument("--merged", action="store_true",
                        help="also print the cross-campaign totals as `merged_*` keys (not the "
                             "C5 batch: two scorer versions); ignored with --campaign")
    args = parser.parse_args()
    print(json.dumps(replay(args.manifest, args.archive_root, args.campaign, args.merged),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
