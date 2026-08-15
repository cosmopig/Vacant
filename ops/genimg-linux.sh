#!/bin/bash
# genimg.sh — 在這台 Linux VM (user1-2) 上用 codex 生圖的**唯一正確方式**。
#
# 為什麼需要這支包裝，而不是直接叫 codex：
#
# 1. codex 的生圖模型在這台機器上能用，但它**寫不進你指定的路徑**（沙箱權限）。
#    圖會落在 ~/.codex/generated_images/<session>/exec-*.png，
#    而 codex 自己會回報「已完成」。這是假成功——狀態說沒事，產物不在該在的地方。
#    我們在這個專案上已經被這種形狀的錯誤騙過十三次，每一次都是「看返回值」害的。
#
# 2. codex 撞到容量上限時會印 "Selected model is at capacity" 然後 **exit 0**。
#    所以**永遠不要看返回值，只能數產物**。這支就是把那條紀律變成工具本身的行為。
#
# 3. 這台 root 只有 19G（剩約 10G）。圖累積在 ~/.codex 遲早爆掉，所以生完是**搬**不是複製。
#
# 4. **`codex` 不在非互動 shell 的 PATH 裡**（它在 ~/.local/bin，只有 login shell
#    才載入）。腳本如果直接寫 `codex ...`，用 ssh 跑非互動命令或排程時會
#    **靜默地找不到指令**——那又是一個「回報成功但沒有產物」的入口。
#    所以下面寫死絕對路徑，不依賴 PATH。
#
# 用法：
#   genimg.sh <輸出檔路徑.png> <提示詞...>
#
# 產物驗不過就 exit 1。驗過才印 ✓。不會有第三種結果。

set -u

if [ $# -lt 2 ]; then
  echo "用法：genimg.sh <輸出檔.png> <提示詞...>" >&2
  exit 2
fi

OUT="$1"; shift
PROMPT="$*"
POOL="$HOME/.codex/generated_images"
CODEX="${CODEX_BIN:-$HOME/.local/bin/codex}"
[ -x "$CODEX" ] || { echo "✗ 找不到 codex：$CODEX" >&2; exit 2; }
MINW=1024

mkdir -p "$(dirname "$OUT")" "$POOL"

# 已存在的先記下來——之後用差集找出這次新生的，不靠檔名猜
BEFORE=$(mktemp)
find "$POOL" -name '*.png' 2>/dev/null | sort > "$BEFORE"

ATTEMPTS=${GENIMG_ATTEMPTS:-4}
NEW=""
for try in $(seq 1 "${ATTEMPTS}"); do
  timeout 900 "$CODEX" exec --sandbox workspace-write --skip-git-repo-check \
"${PROMPT}

硬性要求：
- 必須用生圖模型 image_gen。**不准用 ImageMagick 或任何程式繪圖。**
- 橫幅構圖，至少 ${MINW}px 寬。
- 不要生成看起來像真實特定人物的臉。
- 不要寫任何 HTML/CSS/JS。" >/dev/null 2>&1

  # 每一輪都重新數產物——codex 的回報不可信（見上面第 2、4 條）
  AFTER_TRY=$(mktemp)
  find "$POOL" -name '*.png' 2>/dev/null | sort > "$AFTER_TRY"
  NEW=$(comm -13 "$BEFORE" "$AFTER_TRY" | while read -r f; do
          printf '%s\t%s\n' "$(stat -c %Y "$f" 2>/dev/null || echo 0)" "$f"
        done | sort -rn | head -1 | cut -f2-)
  rm -f "$AFTER_TRY"
  [ -n "${NEW}" ] && break
  echo "  … 第 ${try}/${ATTEMPTS} 次沒產出（PowerShell 起不來或撞容量），等 25 秒重試" >&2
  sleep 25
done

rm -f "$BEFORE"

if [ -z "${NEW}" ] || [ ! -f "${NEW}" ]; then
  echo "✗ ${ATTEMPTS} 次都沒有新圖產出：${OUT}" >&2
  echo "  診斷：ssh 進去跑 codex exec 看 powershell 是不是回 -1073741502" >&2
  exit 1
fi

mv "${NEW}" "${OUT}" || { echo "✗ 搬不動：${NEW} → ${OUT}" >&2; exit 1; }

# 驗證：真的是 PNG，而且寬度夠。純標準庫讀 IHDR，這台沒有 ImageMagick 也沒有 PIL。
DIM=$(python3 - "${OUT}" <<'PY' 2>/dev/null
import struct, sys
try:
    d = open(sys.argv[1], 'rb').read(24)
    if d[:8] != b'\x89PNG\r\n\x1a\n':
        sys.exit(1)
    w, h = struct.unpack('>II', d[16:24])
    print(f"{w}x{h}")
except Exception:
    sys.exit(1)
PY
)

if [ -z "${DIM}" ]; then
  echo "✗ 不是有效的 PNG：${OUT}" >&2
  rm -f "${OUT}"
  exit 1
fi

W=${DIM%x*}
if [ "${W}" -lt "${MINW}" ]; then
  echo "✗ 太小（${DIM}，需要寬 >= ${MINW}）：${OUT}" >&2
  rm -f "${OUT}"
  exit 1
fi

echo "✓ ${OUT}  ${DIM}  $(du -h "${OUT}" | cut -f1)"
