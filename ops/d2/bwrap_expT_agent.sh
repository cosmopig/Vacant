#!/bin/bash
# 實驗 T／確認批次用：把受測的 pi agent 關進 bwrap（2026-11-28；探索批次 449 次執行有 46 次讀到工作區外——教材目錄的未來版本頁面、
# 別組的凍結頁面、c0/flags.json）。agent 只看得到：
#   - 這一格的 live 目錄（ws 工作區、vh 紀錄、cfg 設定、tmp）——讀寫；
#   - 這一輪的輸出目錄（sessions、agent.log 所在）——讀寫；
#   - Vacant 掛鉤用的 venv、pi、node、/usr、/etc——唯讀。
# 教材目錄、run root、別的格、~/dev 都不掛進來（$HOME 是空的 tmpfs）。網路共用（本機的來源伺服器／egress 代理、LM Studio）。
# 用法：bwrap_expT_agent.sh <live_dir> <out_dir> <venv_dir> -- <argv...>
set -euo pipefail
LIVE="$1"; OUT="$2"; VENV="$3"; shift 3
[ "${1:-}" = "--" ] && shift
H="$HOME"
NODE_ROOT="$(dirname "$(dirname "$(readlink -f "$H/.local/bin/node")")")"
args=(--die-with-parent --unshare-pid --unshare-ipc --unshare-uts --proc /proc --dev /dev --tmpfs /tmp
  --ro-bind /usr /usr --ro-bind /etc /etc --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin
  --tmpfs "$H" --ro-bind "$H/.piinstall" "$H/.piinstall" --ro-bind "$NODE_ROOT" "$NODE_ROOT"
  --dir "$H/.local/bin" --symlink "$NODE_ROOT/bin/node" "$H/.local/bin/node" --symlink "$H/.piinstall/node_modules/.bin/pi" "$H/.local/bin/pi"
  --ro-bind "$VENV" "$VENV"
  --bind "$LIVE" "$LIVE" --bind "$OUT" "$OUT"
  --setenv HOME "$H" --setenv PATH "$H/.local/bin:/usr/local/bin:/usr/bin:/bin" --chdir "$LIVE/ws")
exec bwrap "${args[@]}" "$@"
