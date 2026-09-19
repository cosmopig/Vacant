#!/usr/bin/env bash
# 這支在架構裡承重什麼：把 `vacant run` 從 L3 變成 L4。
#
# proxy 單獨只是一個**建議**：agent 的 base_url 被指向它，但同一個 OS 使用者
# 隨時可以自己開一條連線直連真上游，proxy 不會知道，也擋不住
# （`vacant_network/controller.py:7-8` 原本就寫著這條）。
# 「agent 一旦被接上就逃不掉」要成為真的，唯一的辦法是讓**別的路徑連不上**：
# 以 uid 為單位封鎖出網，只留 proxy 那個埠。
#
#   iptables -m owner --uid-owner <agent-uid> ! --dport <proxy-port> -j REJECT
#
# ⚠ **這需要 root，而且不要讓 agent／本工具自己執行。** 本檔是給人類跑的：
#   讀過、確認 uid 與埠沒寫錯、自己 sudo。工具自己 sudo 等於把「需要人類同意」
#   這件事做成一個沒有人在看的步驟。
#
# ⚠ **一次性、而且會影響那個 uid 的所有行程**（不是只有這一次 run）。
#   拆掉用 `--undo`。展場機器是 Linux VM（`user1@100.124.254.83` 可測）。
#
# 誠實邊界（改碼請保留）：
#   1. 這擋的是**網路層的出口**，不是「agent 的行為」。它不會讓框架自己發起的
#      本機動作（lint、git、內建重試）變得可見。
#   2. `--uid-owner` 只認**發出封包的那個 uid**。agent 如果能 `sudo`、能寫
#      setuid 執行檔、或能請另一個 uid 的服務代發請求，這條規則就繞得過。
#      所以它要跟「agent 用一個專屬的低權限 uid 跑」一起用才有意義。
#   3. DNS（53/udp）預設也被擋掉——這是刻意的：放行 DNS 就等於留下一條
#      低頻寬的外洩通道。需要 DNS 的東西請走 proxy。
#   4. 迴圈位址（127.0.0.0/8）放行，否則 proxy 自己就連不上。
#      **proxy 必須跑在不同的 uid 上**，否則這條放行等於沒封。
#
# 用法（root）：
#   sudo ops/vacantrun/block_egress.sh --uid 1234 --port 8899
#   sudo ops/vacantrun/block_egress.sh --uid 1234 --port 8899 --undo
#   ops/vacantrun/block_egress.sh --uid 1234 --port 8899 --dry-run   # 不需要 root
set -euo pipefail

UID_AGENT=""; PORT=""; UNDO=0; DRY=0; CHAIN="OUTPUT"
while [ $# -gt 0 ]; do
  case "$1" in
    --uid)     UID_AGENT="$2"; shift 2 ;;
    --port)    PORT="$2";      shift 2 ;;
    --undo)    UNDO=1;         shift ;;
    --dry-run) DRY=1;          shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ -n "$UID_AGENT" ] && [ -n "$PORT" ] || {
  echo "要給 --uid <agent 的 uid> 與 --port <proxy 埠>。停。" >&2; exit 2; }
case "$UID_AGENT" in ''|*[!0-9]*) echo "--uid 必須是數字。停。" >&2; exit 2 ;; esac
case "$PORT"      in ''|*[!0-9]*) echo "--port 必須是數字。停。" >&2; exit 2 ;; esac
[ "$UID_AGENT" = "0" ] && { echo "不要封 root 的出網。停。" >&2; exit 2; }

# 規則三條，**順序有意義**：先放行迴圈，再放行 proxy 埠，最後 REJECT 其餘。
# 用 `-I`（插到最前面）而不是 `-A`：`-A` 會排在既有的 ACCEPT 後面而完全不生效。
RULES=(
  "-m owner --uid-owner ${UID_AGENT} -o lo -j ACCEPT"
  "-m owner --uid-owner ${UID_AGENT} -d 127.0.0.0/8 -j ACCEPT"
  "-m owner --uid-owner ${UID_AGENT} -p tcp -d 127.0.0.0/8 --dport ${PORT} -j ACCEPT"
  "-m owner --uid-owner ${UID_AGENT} -j REJECT --reject-with icmp-admin-prohibited"
)

run_rule() {   # $1 = -I|-D
  local op="$1" r
  # `-I` 要反序插入，插完之後順序才等於 RULES 的字面順序。
  if [ "$op" = "-I" ]; then
    for (( i=${#RULES[@]}-1 ; i>=0 ; i-- )); do r="${RULES[$i]}"
      echo "iptables ${op} ${CHAIN} 1 ${r}"
      [ "$DRY" = "1" ] || iptables "${op}" "${CHAIN}" 1 ${r}
    done
  else
    for r in "${RULES[@]}"; do
      echo "iptables ${op} ${CHAIN} ${r}"
      [ "$DRY" = "1" ] || iptables "${op}" "${CHAIN}" ${r} || true
    done
  fi
}

if [ "$DRY" != "1" ] && [ "$(id -u)" != "0" ]; then
  echo "這支需要 root。請人類自己 sudo（工具不代跑）。停。" >&2; exit 3
fi

if [ "$UNDO" = "1" ]; then
  run_rule -D
  echo "已拆除 uid=${UID_AGENT} 的出網封鎖。"
else
  run_rule -I
  echo "已對 uid=${UID_AGENT} 封鎖出網，只留 127.0.0.1:${PORT}。"
  echo "⚠ 封鎖生效 ≠ 封鎖有效。請跑負向控制："
  echo "    sudo -u '#${UID_AGENT}' python3 ops/vacantrun/verify_egress_block.py \\"
  echo "        --proxy-port ${PORT} --upstream <真上游 host:port>"
fi
