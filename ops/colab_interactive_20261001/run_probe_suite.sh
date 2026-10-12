#!/usr/bin/env bash
# run_probe_suite.sh <out-dir> ['<install env for arm C>'] — the 7 pi-TUI probe scenarios, all with the passive event logger.
# Exit 0 only if every expectation of every scenario held.  ~3 minutes, no GPU, no model.
set -u
OUT=${1:?out dir}; PENV=${2:-}
HERE=$(cd "$(dirname "$0")" && pwd); rc=0
for spec in plain:A claim:A claim:C error:A errorfinal:A length:A abort:A; do
  sc=${spec%%:*}; arm=${spec##*:}
  python3 "$HERE/pi_tui_probe.py" --scenario "$sc" --arm "$arm" --evlog --out "$OUT" --install-env "$PENV" || rc=1
done
exit $rc
