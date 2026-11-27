#!/bin/bash
# 控制器實驗用：把 agent 關進 bwrap，只看得到自己的工作區、logs 目錄、agent 設定目錄、pi 與 node（唯讀）與系統目錄（唯讀）。
# 題庫目錄（含 hidden/ 那一半測試）、~/dev、其他使用者檔案都不掛進來。網路共用（要連本機 LM Studio）。
# 用法：先 ln -s 本檔 ~/.local/bin/redo-bwrap-agent；計畫的 agent.argv：["redo-bwrap-agent", "{logs}", "pi", "-p", ...]
set -euo pipefail
LOGS="$1"; shift
WS="$PWD"; CFG="${PI_CODING_AGENT_DIR:?}"
H="$HOME"
NODE_ROOT="$(dirname "$(dirname "$(readlink -f "$H/.local/bin/node")")")"
args=(--die-with-parent --unshare-pid --unshare-ipc --unshare-uts --proc /proc --dev /dev --tmpfs /tmp
  --ro-bind /usr /usr --ro-bind /etc /etc --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin
  --tmpfs "$H" --ro-bind "$H/.piinstall" "$H/.piinstall" --ro-bind "$NODE_ROOT" "$NODE_ROOT"
  --dir "$H/.local/bin" --symlink "$NODE_ROOT/bin/node" "$H/.local/bin/node" --symlink "$H/.piinstall/node_modules/.bin/pi" "$H/.local/bin/pi"
  --bind "$WS" "$WS" --bind "$LOGS" "$LOGS" --bind "$CFG" "$CFG"
  --setenv HOME "$H" --setenv PATH "$H/.local/bin:/usr/local/bin:/usr/bin:/bin" --chdir "$WS")
exec bwrap "${args[@]}" "$@"
