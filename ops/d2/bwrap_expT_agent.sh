#!/bin/bash
# 實驗 T／確認批次用：把受測的 pi agent 關進 bwrap（2026-11-28；探索批次 449 次執行有 46 次讀到工作區外——教材目錄的未來版本頁面、
# 別組的凍結頁面、c0/flags.json）。agent 只看得到：
#   - 這一格的 live 目錄（ws 工作區、vh 紀錄、cfg 設定、tmp）——讀寫；
#   - 這一輪的輸出目錄（sessions、agent.log 所在）——讀寫；
#   - Vacant 掛鉤用的 venv、pi、node、/usr、/etc——唯讀。
# 教材目錄、run root、別的格、~/dev 都不掛進來（$HOME 是空的 tmpfs）。網路共用（本機的來源伺服器／egress 代理、LM Studio）。
# 網路（2026-11-28 起，環境變數 EXPT_NETNS_PROXY_PORT 有值時）：--unshare-net，沙箱裡只有 loopback；
#   外面的 runner 先把出口代理接成 <live>/tmp/egress.sock，沙箱裡用 sockfwd.py 把 127.0.0.1:<埠> 接回去。
#   agent 只能經過出口代理（模型呼叫與抓頁都被記錄），直連外網會失敗。探索批次與第一次確認初稿因為沒設 https_proxy、
#   也沒隔離網路，agent 直連了線上維基百科。
# 用法：bwrap_expT_agent.sh <live_dir> <out_dir> <venv_dir> -- <argv...>
set -euo pipefail
LIVE="$1"; OUT="$2"; VENV="$3"; shift 3
[ "${1:-}" = "--" ] && shift
H="$HOME"
# 2026-11-28 02:13Z：一個 agent 的指令無限迴圈印字，pi 把輸出寫進 live/tmp 的單一檔案到 11 GB，磁碟寫滿、兩台初稿 runner 一起崩。
# 之後沙箱裡任何行程寫單一檔案上限 1 GiB（RLIMIT_FSIZE；超過的行程收到 SIGXFSZ）。只防磁碟寫滿，不改任何判準。
ulimit -f 1048576
NODE_ROOT="$(dirname "$(dirname "$(readlink -f "$H/.local/bin/node")")")"
args=(--die-with-parent --unshare-pid --unshare-ipc --unshare-uts --proc /proc --dev /dev --tmpfs /tmp
  --ro-bind /usr /usr --ro-bind /etc /etc --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin
  --tmpfs "$H" --ro-bind "$H/.piinstall" "$H/.piinstall" --ro-bind "$NODE_ROOT" "$NODE_ROOT"
  --dir "$H/.local/bin" --symlink "$NODE_ROOT/bin/node" "$H/.local/bin/node" --symlink "$H/.piinstall/node_modules/.bin/pi" "$H/.local/bin/pi"
  --ro-bind "$VENV" "$VENV"
  --bind "$LIVE" "$LIVE" --bind "$OUT" "$OUT"
  --setenv HOME "$H" --setenv PATH "$H/.local/bin:/usr/local/bin:/usr/bin:/bin" --chdir "$LIVE/ws")
if [ -n "${EXPT_NETNS_PROXY_PORT:-}" ]; then
  FWD="$(dirname "$(readlink -f "$0")")/sockfwd.py"
  args+=(--unshare-net --ro-bind "$FWD" /opt/expT/sockfwd.py)
  P="$EXPT_NETNS_PROXY_PORT"; SOCK="$LIVE/tmp/egress.sock"
  exec bwrap "${args[@]}" /bin/sh -c 'python3 -I /opt/expT/sockfwd.py tcp2unix 127.0.0.1:'"$P"' '"$SOCK"' & sleep 0.5; exec "$@"' sh "$@"
fi
exec bwrap "${args[@]}" "$@"
