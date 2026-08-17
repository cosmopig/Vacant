#!/bin/bash
# Vacant 執行端的 24 小時迴圈。
#
# 每一輪跑一個全新的 claude session（print mode），指令是 LOOP_PROMPT.md。
# 全新 session 代表沒有記憶——連續性靠 STATE.md，而那讓每一輪都可被稽核。
#
# 停止方式：`touch ~/vacant/STOP`，當輪跑完就會停。
# 不要用 kill，那會讓一輪做到一半沒收尾（沒 commit ＝ 那一輪的工作看不見）。

set -u
ROOT="$HOME/vacant"
LOGS="$ROOT/logs"
CLAUDE="$HOME/.local/bin/claude"     # 寫死路徑：非互動 shell 的 PATH 沒有它
MODEL="${LOOP_MODEL:-sonnet}"        # 2026-08-17 人類指定 Sonnet 5（原本吃預設的 Opus 5）
PROMPT="$ROOT/LOOP_PROMPT.md"
STOP="$ROOT/STOP"
GAP=${LOOP_GAP:-90}                  # 每輪之間的間隔（秒）
MAX_MIN=${LOOP_MAX_MIN:-45}          # 單輪上限，避免一輪卡死拖垮迴圈

mkdir -p "$LOGS"
[ -x "$CLAUDE" ] || { echo "找不到 claude：$CLAUDE" >&2; exit 2; }
[ -f "$PROMPT" ] || { echo "找不到指令檔：$PROMPT" >&2; exit 2; }

main_log="$LOGS/loop.log"
say() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$main_log"; }

# 從已有的紀錄接續編號，重啟不會覆蓋
n=$(ls "$LOGS"/iter-*.log 2>/dev/null | sed 's/.*iter-\([0-9]*\)\.log/\1/' | sort -n | tail -1)
n=${n:-0}

say "迴圈啟動（pid $$，從第 $((10#$n + 1)) 輪繼續，模型 ${MODEL}，間隔 ${GAP}s，單輪上限 ${MAX_MIN}min）"

while true; do
  if [ -f "$STOP" ]; then
    say "偵測到 STOP 檔，停止。移除它再啟動即可繼續。"
    exit 0
  fi

  n=$((10#$n + 1))
  iter=$(printf '%04d' "$n")
  ilog="$LOGS/iter-${iter}.log"

  say "── 第 ${n} 輪開始 → $(basename "$ilog")"

  # 每輪先同步：這台可能落後好幾輪，也可能有別人推的東西
  for r in Vacant vacant_hm vacant-docs-web; do
    git -C "$ROOT/$r" pull -q --ff-only 2>>"$main_log" \
      || say "  警告：$r pull 失敗（多半是本地有未提交改動）"
  done

  start=$(date +%s)
  # < /dev/null 是必要的：無人值守時沒有 stdin，claude -p 會先等 3 秒才放棄。
  # 那 3 秒本身無害，但「在等一個永遠不會來的輸入」在別的情境會變成整輪卡住。
  timeout "${MAX_MIN}m" "$CLAUDE" -p "$(cat "$PROMPT")" \
      --model "$MODEL" \
      --dangerously-skip-permissions \
      < /dev/null > "$ilog" 2>&1
  rc=$?
  dur=$(( $(date +%s) - start ))

  case $rc in
    0)   say "  第 ${n} 輪結束（${dur}s）" ;;
    124) say "  第 ${n} 輪逾時被中止（${MAX_MIN}min）——那一輪多半沒收尾" ;;
    *)   say "  第 ${n} 輪異常結束 rc=$rc（${dur}s）" ;;
  esac

  # 這一輪有沒有留下產物？只數 commit，不看返回值。
  for r in Vacant vacant_hm vacant-docs-web; do
    ahead=$(git -C "$ROOT/$r" rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
    [ "${ahead:-0}" -gt 0 ] && say "  ⚠ $r 有 ${ahead} 筆未推送的 commit"
  done

  python3 "$ROOT/bin/progress.py" >>"$main_log" 2>&1 \
    || say "  警告：進度頁產生失敗"

  sleep "$GAP"
done
