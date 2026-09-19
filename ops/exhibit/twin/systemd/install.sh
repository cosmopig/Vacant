#!/usr/bin/env bash
# 把展件裝成「開機自己起來」。**在展場那台 Linux 機器上跑這一支。**
#
# 為什麼要它（DECISION_20260919_EXHIBIT_UNATTENDED.md §二）：在這之前，
# 展場機重開（斷電／清潔人員／排程更新）之後**沒有任何東西會把展件叫回來**。
#
#   sudo ./install.sh                  裝伺服器那一半（system unit）
#   sudo ./install.sh --kiosk          再裝全螢幕瀏覽器（user unit，要圖形工作階段）
#   sudo ./install.sh --uninstall      拆掉
#   ./install.sh --dry-run             只把展開後的 unit 印出來，不寫檔
#
# ⚠ **字型在這一關是硬傷。** 開機那一關（`exhibit_preflight.sh`）只警告不擋，
#   因為開機的時候沒有人能去跑 apt。**但裝的時候有人在**，所以這裡擋——
#   這是最後一個「有人站在鍵盤前面」的時刻。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TWIN="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$TWIN/../../.." && pwd)"
HM="${VACANT_HM:-$(cd "$REPO/.." && pwd)/vacant_hm}"
UNIT_DIR=/etc/systemd/system
DRY=0
KIOSK=0
UNINSTALL=0
# 展件要用哪個使用者跑。`sudo` 之下 $USER 是 root，要回頭問真正的那個人。
RUN_USER="${SUDO_USER:-$USER}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)   DRY=1 ;;
    --kiosk)     KIOSK=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --user)      RUN_USER="$2"; shift ;;
    --hm)        HM="$2"; shift ;;
    *) echo "不認得的參數：$1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$UNINSTALL" = "1" ]; then
  systemctl disable --now vacant-exhibit.service 2>/dev/null || true
  rm -f "$UNIT_DIR/vacant-exhibit.service"
  systemctl daemon-reload
  echo "拆掉了。（kiosk 那一支是 user unit："
  echo "  systemctl --user disable --now vacant-exhibit-kiosk.service ）"
  exit 0
fi

# ── 裝之前先確認這台機器真的撐得住 ───────────────────────────────
[ -f "$HM/world3/index.html" ] || { echo "找不到 $HM/world3/index.html（--hm 指過去）" >&2; exit 2; }
[ -f "$TWIN/twin_pack.json" ]  || { echo "找不到 $TWIN/twin_pack.json" >&2; exit 2; }

if [ "$DRY" = "0" ]; then
  if ! fc-list :lang=zh 2>/dev/null | grep -q .; then
    cat >&2 <<'MSG'
✗ 這台機器一個中文字型都沒有 ⇒ 電視與手機會**整頁豆腐字**（連「機」都畫不出來）。
  現在裝，因為現在有人站在鍵盤前面；開機的時候沒有：

      sudo apt install -y fonts-noto-cjk fonts-noto-cjk-extra
      fc-cache -f
      # 然後**重開瀏覽器**（fontconfig 的快取是行程級的）

  真的要先裝 unit 再處理字型：--dry-run 看內容，或自己 cp 過去。
MSG
    exit 1
  fi
fi

render() {   # $1 = 檔名
  sed -e "s#@@REPO@@#$REPO#g" \
      -e "s#@@HM@@#$HM#g" \
      -e "s#@@USER@@#$RUN_USER#g" \
      -e "s#@@CHROME@@#${CHROME:-$(command -v google-chrome || command -v chromium \
            || command -v chromium-browser || echo /usr/bin/chromium)}#g" \
      "$HERE/$1"
}

if [ "$DRY" = "1" ]; then
  echo "=== vacant-exhibit.service ==="; render vacant-exhibit.service
  [ "$KIOSK" = "1" ] && { echo; echo "=== vacant-exhibit-kiosk.service ==="
                          render vacant-exhibit-kiosk.service; }
  exit 0
fi

chmod +x "$TWIN/exhibit_boot.sh" "$TWIN/exhibit_preflight.sh"
render vacant-exhibit.service > "$UNIT_DIR/vacant-exhibit.service"
systemctl daemon-reload
systemd-analyze verify "$UNIT_DIR/vacant-exhibit.service" \
  || echo "！systemd-analyze 有意見（上面），unit 還是裝上去了" >&2
systemctl enable --now vacant-exhibit.service

echo
echo "裝好了。驗一下（**不要只看 enabled，要看它真的活著**）："
echo "  systemctl status vacant-exhibit.service"
echo "  journalctl -u vacant-exhibit -n 40 --no-pager   ← token 印在這裡"
echo "  $TWIN/venue_check.sh"
echo
echo "⚠ 真正的驗收是**重開機**：sudo reboot，回來之後再跑一次 venue_check.sh。"
echo '  systemctl enable 只證明它被登記了，不證明它起得來。'

if [ "$KIOSK" = "1" ]; then
  U_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)/.config/systemd/user"
  mkdir -p "$U_DIR"
  render vacant-exhibit-kiosk.service > "$U_DIR/vacant-exhibit-kiosk.service"
  chown -R "$RUN_USER": "$(dirname "$U_DIR")"
  loginctl enable-linger "$RUN_USER"
  echo
  echo "kiosk 是 **user unit**，要以 $RUN_USER 的身分啟用（不是 sudo）："
  echo "  systemctl --user daemon-reload"
  echo "  systemctl --user enable --now vacant-exhibit-kiosk.service"
  echo "⚠ enable-linger 已經開了，但它**不會給你一個圖形工作階段**。"
  echo "  自動登入必須是開的，否則開機之後沒有 DISPLAY，瀏覽器起不來。"
fi
