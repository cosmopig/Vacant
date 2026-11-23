# Reply-reported Vacant gate results

Source: vacant_replies.json; raw file SHA256: `850e9a9b5f3bed1639b7274a9e5ccc51c3e48f57a8793a237b9583525f06f488`.
The 24 branch/session pairs match the frozen launch table and scored cells.

**25 numbered submissions shown/reported: 24 exit 0, one exit 20, no shown other/unknown exit codes.**
**23 first-submission acceptances; 24 final acceptances; no cell reports never running the gate.**

These are assistant-reported/pasted outputs, not independently verified receipts. Actual total executions,
unshown attempts, receipt integrity and binding to the final pushed tree remain UNKNOWN.
Duplicate copies of a message/output count once; the per-invocation `1/1 次` is not a session submission count.

| Instance | Sample | Reported submissions | Exit codes in order | Final gate verdict | Never run |
|---|---:|---:|---|---|---|
| astropy__astropy-13236 | 1 | 1 | 0 | accepted | false |
| astropy__astropy-13236 | 2 | 1 | 0 | accepted | false |
| astropy__astropy-14598 | 1 | 1 | 0 | accepted | false |
| astropy__astropy-14598 | 2 | 1 | 0 | accepted | false |
| django__django-13344 | 1 | 1 | 0 | accepted | false |
| django__django-13344 | 2 | 1 | 0 | accepted | false |
| django__django-15563 | 1 | 1 | 0 | accepted | false |
| django__django-15563 | 2 | 1 | 0 | accepted | false |
| django__django-15732 | 1 | 1 | 0 | accepted | false |
| django__django-15732 | 2 | 1 | 0 | accepted | false |
| matplotlib__matplotlib-24870 | 1 | 2 | 20, 0 | accepted | false |
| matplotlib__matplotlib-24870 | 2 | 1 | 0 | accepted | false |
| scikit-learn__scikit-learn-25747 | 1 | 1 | 0 | accepted | false |
| scikit-learn__scikit-learn-25747 | 2 | 1 | 0 | accepted | false |
| sphinx-doc__sphinx-7985 | 1 | 1 | 0 | accepted | false |
| sphinx-doc__sphinx-7985 | 2 | 1 | 0 | accepted | false |
| sphinx-doc__sphinx-8548 | 1 | 1 | 0 | accepted | false |
| sphinx-doc__sphinx-8548 | 2 | 1 | 0 | accepted | false |
| sympy__sympy-14248 | 1 | 1 | 0 | accepted | false |
| sympy__sympy-14248 | 2 | 1 | 0 | accepted | false |
| sympy__sympy-15875 | 1 | 1 | 0 | accepted | false |
| sympy__sympy-15875 | 2 | 1 | 0 | accepted | false |
| sympy__sympy-21612 | 1 | 1 | 0 | accepted | false |
| sympy__sympy-21612 | 2 | 1 | 0 | accepted | false |

## Export decoding and uncertainty

scikit-learn-25747 vacant s1 is not a never-run/unknown-verdict case: its history listing is truncated,
but the JSON inside final_reply contains escaped Unicode. Decoding `contents.message` reveals:

```text
[vacant run] RUN-ON　交付（visible_pass）　1/1 次　ws 4a8319878882→4a8319878882
EXIT 0
```

See gate-evidence.json: event-01a206637d717673ac5c1495eed1689a, source `final_reply.contents.message`.
The exported sys.prefix/sys.exec_prefix warnings precede acceptance; they are not an observed refusal.

Matplotlib s1 reports exit 20 for a skipped PDF P2P test (missing Ghostscript), then exit 0 after installing it.
The session says no source code changed between those submissions; no before/after receipt trees were exported to verify that claim.

All 24 report acceptance, but only 20/24 final handbacks resolve in the independent official harness.
Reported gate acceptance is therefore not the correctness outcome, nor evidence that every accepted version satisfies the issue.

**ACUs remain UNKNOWN**: the user-reported API 0.0 values for all 72 are not interpreted as measured zero usage.

Re-extract with `python ops/sandbox/v3/results/devin-v3-cmp-20261123/parse_gates.py /path/to/vacant_replies.json`.
