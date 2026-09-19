#!/bin/bash
# enclosure：bwrap ＋ netns ＋ mount ns ＋ 最小 rootfs ＋ 私有 /tmp ＋ 唯一一扇門。
#
# 用法：ENC_WS=<工作區> [ENC_RO=a:b:c] [ENC_RW=d:e] [ENC_DOOR=<門目錄>]
#       [ENC_MASK=f:g] [ENC_PATH=...] [ENC_SETENV="K=V K2=V2"]  enc.sh  <cmd...>
#
# ⚠ 這支**不做**任何防火牆規則。圍牆的成立方式是「路不存在」不是「路被擋」。
#
# ⚠ **`--unshare-net` 與 mount namespace 缺一不可**（2026-09-20 實測）：
#   只有 `unshare -n` 的話**路徑型 unix socket 照連**，圍牆等於沒有。
#
# ⚠ **門的目錄是 `--ro-bind` 不是 `--bind`**（2026-09-20 改）。實測兩件事：
#   (1) 唯讀綁定之下 unix socket **照樣連得上**（拿得回 `HTTP/1.1 200 OK`）；
#   (2) 舊的 `--bind` 之下 enclosure **寫得進主機的門目錄**（量到 `WROTE /run/vacant`）。
#   ⇒ 唯讀不花任何代價，而可寫是白送出去的一個寫入點。
#   `ENC_DOOR_RW=1` 是**只給負控制用**的開關（要證明「量得出可寫」才有資格說
#   「量到唯讀」）。正式跑一律不要設。
set -u
WS="${ENC_WS:?ENC_WS required}"
ARGS=(
  --unshare-all
  --die-with-parent
  --ro-bind /usr /usr
  --symlink usr/bin /bin
  --symlink usr/sbin /sbin
  --symlink usr/lib /lib
  --symlink usr/lib64 /lib64
  --ro-bind /etc /etc
  --proc /proc
  --dev /dev
  --tmpfs /tmp
  --tmpfs /run
  --tmpfs /var/tmp
  --bind "$WS" "$WS"
  --chdir "$WS"
  --setenv HOME "$WS"
  --setenv TMPDIR /tmp
  --setenv LANG C.UTF-8
  --setenv LC_ALL C.UTF-8
  --setenv PATH "${ENC_PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
)
if [ -n "${ENC_RO:-}" ]; then
  IFS=':' read -ra P <<< "$ENC_RO"
  for p in "${P[@]}"; do [ -n "$p" ] && ARGS+=(--ro-bind "$p" "$p"); done
fi
if [ -n "${ENC_RW:-}" ]; then
  IFS=':' read -ra P <<< "$ENC_RW"
  for p in "${P[@]}"; do [ -n "$p" ] && ARGS+=(--bind "$p" "$p"); done
fi
# 憑證檔遮蔽（possess.NEVER_TOUCH 的 enclosure 版本）：用 /dev/null 蓋過去。
if [ -n "${ENC_MASK:-}" ]; then
  IFS=':' read -ra P <<< "$ENC_MASK"
  for p in "${P[@]}"; do [ -n "$p" ] && ARGS+=(--ro-bind /dev/null "$p"); done
fi
if [ -n "${ENC_DOOR:-}" ]; then
  if [ "${ENC_DOOR_RW:-0}" = "1" ]; then
    # ⚠ 負控制專用。看到這一行出現在正式跑的紀錄裡＝那一跑的門目錄可寫。
    echo "enc.sh: ⚠ ENC_DOOR_RW=1 —— 門目錄是**可寫**的（只有負控制該這樣跑）" >&2
    ARGS+=(--bind "$ENC_DOOR" /run/vacant)
  else
    ARGS+=(--ro-bind "$ENC_DOOR" /run/vacant)
  fi
fi
for kv in ${ENC_SETENV:-}; do ARGS+=(--setenv "${kv%%=*}" "${kv#*=}"); done
exec bwrap "${ARGS[@]}" "$@"
