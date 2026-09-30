#!/bin/bash
# tui.sh — drive pi's REAL interactive TUI under tmux and read the pane.
#
# Why tmux and not a pty library: the thing under test is the interactive
# interface. `pi -p` takes a different code path (it is the non-interactive
# mode), so a headless run proves nothing about this. tmux gives a real terminal
# with a real size, which is what the TUI lays itself out against.
#
# Usage:
#   tui.sh start <session> <workdir> [env KEY=VAL ...]
#   tui.sh send  <session> <keys...>       # tmux send-keys
#   tui.sh line  <session> <text>          # send literally, then Enter
#   tui.sh wait  <session> <regex> [secs]  # poll the pane until it matches
#   tui.sh pane  <session>                 # dump the visible pane
#   tui.sh stop  <session>
set -u

cmd=${1:?subcommand}
shift

case "$cmd" in
start)
  sess=${1:?session}; wd=${2:?workdir}; shift 2
  tmux kill-session -t "$sess" 2>/dev/null || true
  # 120x36: wide enough that the TUI does not collapse its panels, which would
  # hide exactly the text we are looking for.
  tmux new-session -d -s "$sess" -x 120 -y 36 -c "$wd" "$@"
  sleep 3
  echo "started $sess in $wd"
  ;;
send)
  sess=$1; shift
  tmux send-keys -t "$sess" "$@"
  ;;
line)
  sess=$1; text=$2
  tmux send-keys -t "$sess" -l "$text"
  sleep 1
  tmux send-keys -t "$sess" Enter
  ;;
wait)
  sess=$1; re=$2; limit=${3:-90}
  i=0
  while [ "$i" -lt "$limit" ]; do
    if tmux capture-pane -p -t "$sess" 2>/dev/null | grep -qiE "$re"; then
      echo "MATCH after ${i}s: $re"
      exit 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "NO MATCH after ${limit}s: $re"
  exit 1
  ;;
pane)
  sess=$1
  tmux capture-pane -p -t "$sess" 2>/dev/null
  ;;
history)
  sess=$1
  tmux capture-pane -p -S -200 -t "$sess" 2>/dev/null
  ;;
stop)
  tmux kill-session -t "$1" 2>/dev/null || true
  echo "stopped $1"
  ;;
*) echo "unknown subcommand: $cmd" >&2; exit 2 ;;
esac
