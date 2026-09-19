#!/usr/bin/env bash
# 這支在架構裡承重什麼：把「繞過中介」從**擋不擋得住**改成**看不看得見**。
#
# `block_egress.sh`（V3）的四條規則是一個**閘門**：它試著擋，而 V3 已經量到
# 九條擋不住的路。本支不取代它，**加的是刻度**——同樣以 uid 為單位，但
# 規則放進一條專屬 chain，每一條都有 `iptables` 自己的封包計數器，
# 於是「這一跑有沒有東西走了中介以外的路」從一個沒有欄位的問題
# 變成一個可以前後相減的數字。
#
# 兩個模式，**差別只在最後兩條是 ACCEPT 還是 REJECT**：
#
#   --mode observe  只數不擋。世界跟沒有這支時**逐位元相同**（agent 的行為
#                   不會因為被擋而改變），但每一條路都有計數。
#                   ⇒ 量「agent 自己會不會走第二條路」要用這個。
#   --mode enforce  數 ＋ 擋（＝ V3 的封鎖 ＋ 刻度）。
#
# 規則順序有意義（先命中先算），每一條的**語意**寫在 LABELS：
#
#   1 mediated_proxy   -p tcp -d 127.0.0.1 --dport <proxy>   ← 被中介的那條路
#   2 dns_any          -p udp --dport 53                     ← 任何 DNS 查詢
#   3 dns_redirected   -p udp -d 127.0.0.1 --dport <dnslog>  ← 被導到名稱記錄器的 DNS
#   4 loopback_other   -d 127.0.0.0/8                        ← 迴圈上**不是** proxy 的東西
#   5 lo_other         -o lo                                 ← 其餘走 lo 的（含 ::1）
#   6 udp_offbox       -p udp                                ← 出機器的 UDP（QUIC…）
#   7 offbox           （其餘）                               ← **頭條**：出機器的 TCP/ICMP/raw
#
# 誠實邊界（改碼請保留）：
#  1. 這是**封包計數**不是內容。它說得出「有 N 個封包走了中介以外的路」，
#     說不出那是什麼內容。要內容得另外抓（DNS 名字有 `dnslog.py`）。
#  2. **unix domain socket 一個封包都不會出現在這裡**（不經 netfilter）。
#     V3 已實測 0.038 秒 200 OK。這支對那條路是**瞎的**，不是量到 0。
#  3. `loopback_other` 與 `lo_other` 不是「繞過」的證據，是**繞過的可能**：
#     同機另一個 uid 的 listener 走的就是這兩條。數字 > 0 要人去看那是什麼。
#  4. 計數器是**這條 chain 的**，不是這一跑的。前後各讀一次相減才是這一跑的。
#     相減期間有別的東西用同一個 uid ⇒ 會混進來。一跑一 uid 才乾淨。
#  5. 規則存在 ≠ 規則有效。`--mode enforce` 之後仍然要跑負向控制
#     （`probe.py`），這支自己不驗自己。
#
# 用法（root）：
#   sudo egress_gauge.sh --uid 1001 --port 8899 --mode observe
#   sudo egress_gauge.sh --uid 1001 --port 8899 --mode enforce
#   sudo egress_gauge.sh --undo                     # 拆掉（冪等、會驗）
#   egress_gauge.sh --status                        # 只印，不需要 root 也不改
set -uo pipefail

CHAIN4=VACANT_EG
CHAIN6=VACANT_EG6
UID_AGENT=""; PORT=""; DNSPORT=5353; MODE="observe"; UNDO=0; STATUS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --uid)      UID_AGENT="$2"; shift 2 ;;
    --port)     PORT="$2";      shift 2 ;;
    --dns-port) DNSPORT="$2";   shift 2 ;;
    --mode)     MODE="$2";      shift 2 ;;
    --undo)     UNDO=1;         shift ;;
    --status)   STATUS=1;       shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ "$STATUS" = "1" ]; then
  echo "### iptables -xnvL $CHAIN4"; iptables -xnvL "$CHAIN4" 2>&1
  echo "### ip6tables -xnvL $CHAIN6"; ip6tables -xnvL "$CHAIN6" 2>&1
  exit 0
fi

[ "$(id -u)" = "0" ] || { echo "這支需要 root。請人類自己 sudo。停。" >&2; exit 3; }

if [ "$UNDO" = "1" ]; then
  # 冪等：`-D` 跑到沒得刪為止，再驗 chain 真的不見了。
  for i in 1 2 3 4 5 6 7 8; do
    iptables  -D OUTPUT -m owner --uid-owner "${UID_AGENT:-0}" -j "$CHAIN4" 2>/dev/null || break
  done
  for i in 1 2 3 4 5 6 7 8; do
    ip6tables -D OUTPUT -m owner --uid-owner "${UID_AGENT:-0}" -j "$CHAIN6" 2>/dev/null || break
  done
  iptables  -F "$CHAIN4" 2>/dev/null || true; iptables  -X "$CHAIN4" 2>/dev/null || true
  ip6tables -F "$CHAIN6" 2>/dev/null || true; ip6tables -X "$CHAIN6" 2>/dev/null || true
  left4=$(iptables  -S 2>/dev/null | grep -c "$CHAIN4" || true)
  left6=$(ip6tables -S 2>/dev/null | grep -c "$CHAIN6" || true)
  echo "已拆除刻度 chain。殘留 v4=${left4} v6=${left6}（兩個都要是 0）"
  [ "$left4" = "0" ] && [ "$left6" = "0" ] || exit 4
  exit 0
fi

[ -n "$UID_AGENT" ] && [ -n "$PORT" ] || { echo "要給 --uid 與 --port。停。" >&2; exit 2; }
case "$UID_AGENT" in ''|*[!0-9]*) echo "--uid 必須是數字。停。" >&2; exit 2 ;; esac
case "$PORT"      in ''|*[!0-9]*) echo "--port 必須是數字。停。" >&2; exit 2 ;; esac
[ "$UID_AGENT" = "0" ]    && { echo "不要量 root。停。" >&2; exit 2; }
[ "$UID_AGENT" = "1000" ] && { echo "不要量 user1（那是 proxy／ssh 的 uid）。停。" >&2; exit 2; }
case "$MODE" in observe|enforce) ;; *) echo "--mode 只收 observe|enforce。停。" >&2; exit 2 ;; esac

TAIL="ACCEPT"
[ "$MODE" = "enforce" ] && TAIL="REJECT --reject-with icmp-admin-prohibited"
TAIL6="ACCEPT"
[ "$MODE" = "enforce" ] && TAIL6="REJECT --reject-with adm-prohibited"

iptables -N "$CHAIN4" 2>/dev/null || { echo "chain $CHAIN4 已存在——先 --undo。停。" >&2; exit 5; }
iptables -A "$CHAIN4" -p tcp -d 127.0.0.1 --dport "$PORT"    -j ACCEPT   # 1 mediated_proxy
iptables -A "$CHAIN4" -p udp --dport 53                      -j ACCEPT   # 2 dns_any
iptables -A "$CHAIN4" -p udp -d 127.0.0.1 --dport "$DNSPORT" -j ACCEPT   # 3 dns_redirected
iptables -A "$CHAIN4" -d 127.0.0.0/8                         -j ACCEPT   # 4 loopback_other
iptables -A "$CHAIN4" -o lo                                  -j ACCEPT   # 5 lo_other
iptables -A "$CHAIN4" -p udp                                 -j $TAIL    # 6 udp_offbox
iptables -A "$CHAIN4"                                        -j $TAIL    # 7 offbox
iptables -I OUTPUT 1 -m owner --uid-owner "$UID_AGENT" -j "$CHAIN4"

ip6tables -N "$CHAIN6" 2>/dev/null || true
ip6tables -A "$CHAIN6" -p tcp -d ::1 --dport "$PORT" -j ACCEPT           # 1 mediated_proxy6
ip6tables -A "$CHAIN6" -p udp --dport 53             -j ACCEPT           # 2 dns_any6
ip6tables -A "$CHAIN6" -d ::1/128                    -j ACCEPT           # 3 loopback_other6
ip6tables -A "$CHAIN6" -o lo                         -j ACCEPT           # 4 lo_other6
ip6tables -A "$CHAIN6" -p udp                        -j $TAIL6           # 5 udp_offbox6
ip6tables -A "$CHAIN6"                               -j $TAIL6           # 6 offbox6  ← V3 一行都沒碰的那一條
ip6tables -I OUTPUT 1 -m owner --uid-owner "$UID_AGENT" -j "$CHAIN6"

echo "刻度已上：uid=${UID_AGENT} proxy=127.0.0.1:${PORT} mode=${MODE}（v4 ＋ v6）"
[ "$MODE" = "observe" ] && echo "⚠ observe ＝**只數不擋**。這一跑沒有任何東西被封鎖。"
exit 0
