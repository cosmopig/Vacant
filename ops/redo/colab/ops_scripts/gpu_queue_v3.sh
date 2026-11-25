#!/bin/bash
# GPU 佇列 v3（2026-11-25，rfh4）：同 gpu_queue.sh，佇列行多了選填的額外參數（例如 --only-providers lms1003）。
# 原本的說明：等這台機器目前的批次跑完，就發射佇列檔裡的下一份「已 commit、preflight 過」的預註冊計畫。
# 用法：gpu_queue.sh <queue_file> <current_runner_pid|0>
# 起 unit 一律帶記憶體上限與 OOMPolicy=continue（11/24：confirm2 期間 agent 寫出的無窮迴圈把整台機器的記憶體吃光，
# 全域 OOM 之後 systemd 把佇列 unit 判 failed、佇列腳本死掉）：
#   systemd-run --user --unit=redo-queue-XXXX -p KillMode=process -p MemoryHigh=3500M -p MemoryMax=4G -p OOMPolicy=continue \
#     --setenv=PATH=$PATH --working-directory=$HOME/dev/ops $HOME/dev/ops/gpu_queue.sh <queue_file> <pid|0>
# 有上限時，OOM 只會發生在這個 cgroup 裡、殺掉最大的那個行程（失控的那一個），批次與佇列照常。
# 佇列檔一行一批：<repo_dir> <plan_relpath> <root_dir> [bank_dir|-] [redo.py run 的額外參數…]   （# 開頭為註解；發射後該行改成 #DONE 前綴＝已發射，不是已跑完）
# 規則：計畫一定要已 commit（redo.py 自己也會擋）；preflight 不過就停在那一行、寫 BLOCKED 並結束，不跳過、不改計畫。
set -u
Q=$1; CUR=${2:-0}
LOG=${Q%.txt}.log
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
while true; do
  if [ "$CUR" != 0 ]; then
    while kill -0 "$CUR" 2>/dev/null; do sleep 60; done
    say "批次 pid=$CUR 結束"
  fi
  line=$(grep -m1 -vE '^\s*(#|$)' "$Q" || true)
  if [ -z "$line" ]; then [ "${EMPTY_SAID:-0}" = 1 ] || say "佇列空了，等新的一行"; EMPTY_SAID=1; CUR=0; sleep 300; continue; fi; EMPTY_SAID=0
  set -- $line; repo=$1; plan=$2; root=$3; bank=${4:-}; shift $(( $# < 4 ? $# : 4 )); extra=("$@")
  barg=(); [ -n "$bank" ] && [ "$bank" != "-" ] && barg=(--bank "$bank")
  if ! (cd "$repo" && git diff --quiet HEAD -- "$plan" && git ls-files --error-unmatch "$plan" >/dev/null 2>&1); then
    say "BLOCKED 計畫沒 commit 或有未提交修改：$repo/$plan"; exit 2
  fi
  if ! (cd "$repo" && timeout 600 python3 ops/redo/redo.py preflight --plan "$plan" "${barg[@]}" 2>&1 | tail -1 | grep -q PREFLIGHT_OK); then
    say "BLOCKED preflight 不過：$repo/$plan"; exit 3
  fi
  mkdir -p "$root"
  # 11/24：pid 直接從背景行程取（$!），不再「5 秒後用 pgrep 找」——批次在 5 秒內就結束（例如冒煙 4 格都 exit 43）時，
  # 舊版會誤判成「找不到 runner」而 BLOCKED，佇列停住。舊版留在 gpu_queue_v1.sh。
  rm -f "$root/runner.pid"
  (cd "$repo" && { TMPDIR=$HOME/dev/ops/tmp_redo setsid nohup python3 ops/redo/redo.py run --plan "$plan" "${barg[@]}" --root "$root" "${extra[@]}" \
      >> "$root/nohup.log" 2>&1 < /dev/null & echo $! > "$root/runner.pid"; })
  CUR=$(cat "$root/runner.pid" 2>/dev/null || true)
  say "發射 $plan → $root（pid=${CUR:-?}）"
  esc=$(printf '%s' "$line" | sed 's/[][\.*^$/]/\\&/g')
  sed -i "0,/^$esc\$/s//#DONE $esc/" "$Q"
  [ -z "${CUR:-}" ] && { say "BLOCKED 發射失敗（沒有取得 pid）"; exit 4; }
done
