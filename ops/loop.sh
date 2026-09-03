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
DEFAULT_MODEL="${LOOP_MODEL:-opus}"   # 預設 Opus 5（人類 2026-09-03 指定「遠端的模型改成 opus5」）；每輪可被 NEXT_MODEL 覆蓋一次
NEXT_MODEL="$ROOT/NEXT_MODEL"          # 上一輪寫的建議，讀完就消耗掉（見 pick_model）
PROMPT="$ROOT/LOOP_PROMPT.md"
STOP="$ROOT/STOP"
GAP=${LOOP_GAP:-90}                  # 每輪之間的間隔（秒）
MAX_MIN=${LOOP_MAX_MIN:-45}          # 單輪上限，避免一輪卡死拖垮迴圈

mkdir -p "$LOGS"

# 同一時間只准一份。實測踩到的：`setsid --fork loop.sh` 起了兩份之後，
# 兩份的 `git pull` 撞在一起，git 回
# `fatal: Cannot fast-forward to multiple branches` ——那個訊息看起來
# 完全像分支設定壞了，而手動跑同一行是好的。查了三輪才發現是併發。
LOCK="$ROOT/.loop.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "已經有一份迴圈在跑（$LOCK 被鎖住），這一份不啟動" >&2
  exit 0
fi
echo $$ >&9
[ -x "$CLAUDE" ] || { echo "找不到 claude：$CLAUDE" >&2; exit 2; }
[ -f "$PROMPT" ] || { echo "找不到指令檔：$PROMPT" >&2; exit 2; }

main_log="$LOGS/loop.log"
say() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$main_log"; }

# 從已有的紀錄接續編號，重啟不會覆蓋
n=$(ls "$LOGS"/iter-*.log 2>/dev/null | sed 's/.*iter-\([0-9]*\)\.log/\1/' | sort -n | tail -1)
n=${n:-0}

say "迴圈啟動（pid $$，從第 $((10#$n + 1)) 輪繼續，預設模型 ${DEFAULT_MODEL}，間隔 ${GAP}s，單輪上限 ${MAX_MIN}min）"

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
  # ⚠ 一定要指明 remote 與**當前分支**。裸 `git pull --ff-only` 在
  #   remote 有多個追蹤分支時會失敗（`Cannot fast-forward to multiple
  #   branches`），而且錯誤訊息完全不像真正的原因——實測時它讓我以為
  #   是「本地有未提交改動」，三個 repo 每輪都靜默拿不到新東西。
  for r in Vacant vacant_hm vacant-docs-web; do
    br=$(git -C "$ROOT/$r" branch --show-current 2>/dev/null)
    if [ -z "${br}" ]; then
      say "  警告：$r 不在任何分支上（detached HEAD？），跳過 pull"
      continue
    fi
    git -C "$ROOT/$r" pull -q --ff-only origin "${br}" 2>>"$main_log" \
      || say "  警告：$r（${br}）pull 失敗——看 $main_log 的真正原因，不要猜"
  done

    # 2026-08-24 人類：「要要求他聰明切換模型 opus5 sonnet5」。
  # 寫在指令裡只是建議，沒有機制就不會發生——所以做成一個一次性的交接檔：
  # 上一輪在自己判斷「下一輪該用什麼」之後 `echo opus > ~/vacant/NEXT_MODEL`，
  # 這裡讀出來用一次就刪掉。刪掉是關鍵：不刪的話一輪寫了 opus 會黏住，
  # 之後每一輪都用 opus 收數字，那正是要避免的浪費。
  # 2026-09-02（R440J 教訓）：迴圈一直在讀 ~/vacant/LOOP_PROMPT.md 的 8/28 副本，
  # repo 裡 ops/LOOP_PROMPT.md 寫的模型政策、平行規則、E1 視窗規則一條都沒生效。
  # 從此每輪 pull 之後直接讀 repo 檔；副本只當 repo 檔不存在時的後備。
  if [ -f "$ROOT/Vacant/ops/LOOP_PROMPT.md" ]; then
    PROMPT="$ROOT/Vacant/ops/LOOP_PROMPT.md"
  else
    PROMPT="$ROOT/LOOP_PROMPT.md"
    say "  警告：repo 沒有 ops/LOOP_PROMPT.md，退回副本 $PROMPT"
  fi
  say "  指令檔：$PROMPT（$(wc -l < "$PROMPT") 行）"

  model="$DEFAULT_MODEL"
  if [ -f "$NEXT_MODEL" ]; then
    want=$(tr -d "[:space:]" < "$NEXT_MODEL" | tr "[:upper:]" "[:lower:]")
    rm -f "$NEXT_MODEL"
    case "$want" in
      opus|sonnet|local) model="$want"; say "  上一輪指定模型：$model" ;;
      # 2026-09-01 人類：「使用 fable 5.1 但要讓他聰明選擇模型，主要做到稽核」
      # ——fable 是稽核／裁決層：寫 DECISION、判 run 收官、每 10 輪一次總稽核。
      # 日常監控仍是 sonnet，設計 opus，探針 local（見 LOOP_PROMPT 模型政策）。
      fable)       model="claude-fable-5-1"; say "  上一輪指定模型：fable（稽核輪）" ;;
      "")          say "  NEXT_MODEL 是空的，用預設 $model" ;;
      *)           say "  NEXT_MODEL 寫著「$want」，不是 opus/sonnet/local/fable，用預設 $model" ;;
    esac
  fi

  start=$(date +%s)
  if [ "$model" = "local" ]; then
    # 本地模型走自己的工具迴圈（ops/localagent.py），不經過 claude。
    # 2026-08-28 人類：「不用讓他進入 claude code，你可以讓 claude 用 API
    # harness 去做他的控制」——省掉 Anthropic↔OpenAI 的協定轉換層，
    # 那層本身就是一個會壞、會要維護的東西。本地推理 $0。
    # 9>&- 關掉繼承來的鎖 fd：不關的話這一輪的子行程會一路握著
    # .loop.lock 的 flock，就算 loop.sh 本身死了／被重啟，鎖仍卡著
    # （round188/189 實測踩到：重啟監督程序時新 loop.sh flock -n 失敗，
    # `fuser` 一查，握著鎖的是還在跑的那一輪 timeout/claude，不是舊監督）。
    timeout "${MAX_MIN}m" python3 "$ROOT/bin/localagent.py" \
        --prompt-file "$PROMPT" --cwd "$ROOT/Vacant" \
        --log "$LOGS/localagent-${iter}.jsonl" \
        --max-minutes "$((MAX_MIN - 3))" \
        < /dev/null > "$ilog" 2>&1 9>&-
    rc=$?
  else
    # < /dev/null 是必要的：無人值守時沒有 stdin，claude -p 會先等 3 秒才放棄。
    # 那 3 秒本身無害，但「在等一個永遠不會來的輸入」在別的情境會變成整輪卡住。
    # 9>&- 理由同上（local 分支）。
    timeout "${MAX_MIN}m" "$CLAUDE" -p "$(cat "$PROMPT")" \
        --model "$model" \
        --dangerously-skip-permissions \
        < /dev/null > "$ilog" 2>&1 9>&-
    rc=$?
  fi
  dur=$(( $(date +%s) - start ))

  case $rc in
    0)   say "  第 ${n} 輪結束（${dur}s，模型 ${model}）" ;;
    124) say "  第 ${n} 輪逾時被中止（${MAX_MIN}min）——那一輪多半沒收尾" ;;
    *)   say "  第 ${n} 輪異常結束 rc=$rc（${dur}s）" ;;
  esac

  # 本地模型比 Sonnet 弱得多，撞牆是預期內的。一輪失敗就把下一輪退回 sonnet，
  # 不要連續空轉——省 token 的前提是那一輪真的有做事。
  if [ "$model" = "local" ] && [ "$rc" -ne 0 ]; then
    echo sonnet > "$NEXT_MODEL"
    say "  本地輪次 rc=$rc，下一輪退回 sonnet"
  fi

  # 這一輪有沒有留下產物？只數 commit，不看返回值。
  for r in Vacant vacant_hm vacant-docs-web; do
    ahead=$(git -C "$ROOT/$r" rev-list --count @{u}..HEAD 2>/dev/null || echo 0)
    [ "${ahead:-0}" -gt 0 ] && say "  ⚠ $r 有 ${ahead} 筆未推送的 commit"
  done

  python3 "$ROOT/bin/progress.py" >>"$main_log" 2>&1 \
    || say "  警告：進度頁產生失敗"

  sleep "$GAP"
done
