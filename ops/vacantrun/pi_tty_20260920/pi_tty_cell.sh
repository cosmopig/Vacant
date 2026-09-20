#!/usr/bin/env bash
# 一格 ＝ 一題 × 一個「呼叫形態」× 一次 `vacant run`。
#
# 這一批回答的是 2026-09-20 人類的質疑：**600 格全走 `pi -p`，而沒有人那樣用 pi。**
# 所以這裡把「呼叫形態」變成唯一的變因，其餘逐字沿用
# `runs/pbgate2_agents_lcb2_20260920/pbgate2_cell.sh`（＝ abpi 那批的形狀）。
#
# ## 三臂（**PTP ↔ INT 只差一個 token**，這才是乾淨的對照）
#
# | 臂 | 外層 | launcher | wrapper | pi 實際模式 |
# |---|---|---|---|---|
# | `PRT` | 直跑 | `--json`（stdout 進檔）、stdin 預設 devnull | `wrap_agent.sh`（凍結） | print |
# | `PTP` | `tty_drive.py`（真 pty） | `--stdin inherit`、**不給 `--json`** | `wrap_agent.sh`（凍結） | print |
# | `INT` | `tty_drive.py`（真 pty） | `--stdin inherit`、**不給 `--json`** | `wrap_agent_tty.sh` | **interactive** |
#
# · `PRT` ＝ 600 格那批的參考形狀（只改 task-id 與落點）。
# · `PTP` ＝ **同一張 pty、同一組 launcher 旗標**，但 wrapper 仍是凍結那支
#   （`pi -p … < /dev/null`）⇒ 它與 `INT` 的差別**只有 `-p` 與 `< /dev/null`**。
#   有了它才分得開「pty 這個外殼造成的差」與「互動模式造成的差」。
# · 模式不是我們宣稱的，是量出來的：`ops/vacantrun/pi_tty_20260920/mode_oracle.sh`
#   （`PI_STARTUP_BENCHMARK` 三態矩陣）＋轉錄裡的 TUI escape sequence。
#
# ## ⚠ 互動臂的「結束」與 `-p` 的「結束」不是同一件事
#
# `interactive-mode.js` 跑完 initialMessage 之後進 `while (true) { getUserInput() … }`
# ⇒ TUI 不會自己結束。這一格的結束是 `tty_drive.py` 在 hook log 出現
# `agent_end` 之後按 Ctrl-D。**寫報告時不可以講成「agent 退出碼 0 走人」。**
#
# ## 掛鉤是常數不是變因
#
# 三臂**都**設 `VACANT_HOOK_LOG`（互動臂要用它當確定性的「做完了」訊號）。
# 代價：每格多一通 canary（`/v1/models?vacant_canary=…`）⇒ 判讀 `requests_seen`
# 時要分開數。**凍結那批沒有設它**，所以本批的 `requests_seen` 不可與 600 格直接並排。
set -u
ROOT=${TTY_ROOT:-/var/tmp/vacant_tty_20260920}
REPO=$ROOT/repo
TPL=$REPO/ops/gain/r534/templates
PY=/usr/bin/python3
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/home/user1/.local/bin:$PATH
# 🔴 1003 only（1004 的 4 串是別人的實驗在用）
export VACANT_RUN_UPSTREAM_OPENAI=${TTY_UPSTREAM_OPENAI:-http://100.119.113.56:1234/v1}
export VACANT_RUN_UPSTREAM_ANTHROPIC=${TTY_UPSTREAM_ANTHROPIC:-http://100.119.113.56:1234}
export VACANT_AGENT_MODEL=${TTY_MODEL:-gemma-4-12b-it-qat}
TEST_TIMEOUT=${TTY_TEST_TIMEOUT:-120}
AGENT_TIMEOUT=${TTY_AGENT_TIMEOUT:-900}
OUTER_TIMEOUT=${TTY_OUTER_TIMEOUT:-1200}
PROMPT='Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.'

tid="$1"; arm="${2:-INT}"; rep="${3:-1}"
name="${tid}_${arm}_r${rep}"
ws=$ROOT/ws_$name; rd=$ROOT/cells/$name
mkdir -p "$ROOT/logs" "$ROOT/argv" "$ROOT/hooks" "$ROOT/cells" "$ROOT/pty"
rm -rf "$ws" "$rd"; mkdir -p "$ws"
cp "$TPL/$tid/goal.md" "$TPL/$tid/contract.md" "$TPL/$tid/run_tests.sh" "$ws/"
cp -r "$TPL/$tid/tests_visible" "$ws/"
# 工作區純度擋門（fail-closed），與 pbgate2／abpi 逐字同一套
want="./contract.md ./goal.md ./run_tests.sh ./tests_visible/test_visible.py"
got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ' | sed 's/ $//')"
if [ "$got" != "$want" ]; then
  echo "工作區不乾淨，停。arm=$arm" >&2
  echo "  want: $want" >&2
  echo "  got : $got" >&2
  exit 3
fi

TASKID="ttymode_$name"
HOOKLOG=$ROOT/hooks/$name.jsonl
: > "$HOOKLOG"
export VACANT_HOOK_LOG="$HOOKLOG"
export VACANT_RUN_ID="$TASKID"
export VACANT_HOOK_AGENT=pi
export VACANT_PY="$PY"
export PYTHONPATH="$REPO"

cd "$REPO" || exit 2
echo "=== BEGIN $name $(date -u +%FT%T.%NZ) ==="
{
  echo "cwd=$REPO  arm=$arm  task=$tid  rep=$rep"
  echo "task_id=$TASKID"
  echo "hooklog=$HOOKLOG"
  echo "ENV VACANT_RUN_UPSTREAM_OPENAI=$VACANT_RUN_UPSTREAM_OPENAI"
  echo "ENV VACANT_AGENT_MODEL=$VACANT_AGENT_MODEL"
  echo "ENV VACANT_HOOK_LOG=(set, 三臂皆同)"
  echo "workspace_files=$got"
} > "$ROOT/argv/$name.argv.txt"

t0=$(date +%s.%N)
case "$arm" in
PRT)
  # 600 格那批的形狀（`--json` ⇒ agent stdout 進檔 ⇒ pi 必為 print）
  echo "cmd=launcher --json -- wrap_agent.sh pi <prompt>" >> "$ROOT/argv/$name.argv.txt"
  timeout "$OUTER_TIMEOUT" $PY -m vacant_network.vrun.launcher \
      --workspace "$ws" --run-dir "$rd" --suite "$TPL/$tid/tests_visible" \
      --task-id "$TASKID" --sandbox none \
      --test-timeout "$TEST_TIMEOUT" --timeout "$AGENT_TIMEOUT" --retry none --json \
      -- "$REPO/ops/vacantrun/wrap_agent.sh" pi "$PROMPT" \
      > "$ROOT/logs/$name.stdout" 2> "$ROOT/logs/$name.stderr"
  rc=$?
  ;;
PTP|INT|INT2|INTQ)
  if [ "$arm" = "PTP" ]; then W="$REPO/ops/vacantrun/wrap_agent.sh"
                        else W="$REPO/ops/vacantrun/wrap_agent_tty.sh"; fi
  # `INT2` ＝ 互動 ＋ **人在第一回合結束後又打了一句**。
  # ⚠ 它與 `-p` 的差同時包含「有 TUI」與「多了一輪人類輸入」兩件事
  #   ⇒ **不可以拿來跟單輪的臂相減**。它回答的是另一個問題：
  #   「Vacant 的中介與閘門在**多回合**下還成不成立」。
  # ⚠ 這一句逐字落盤（`argv/*.argv.txt` 與 `pty/*.drive.json`）。
  #   它不含任何隱藏測資（鐵律 2），也不含「你有責任／會被懲罰」（鐵律 1）。
  TURNS=1; TURNTEXT=""; MINRUN=5; POSTDONE=4
  if [ "$arm" = "INT2" ]; then
    TURNS=2
    TURNTEXT=${TTY_TURN2_TEXT:-'Please run "sh run_tests.sh" now and show me the output. If anything fails or hangs, fix solution.py and run it again.'}
  fi
  # `INTQ` ＝ **人提早關掉終端機**（agent 還在做就按 Ctrl-D）。
  # 這一臂回答的是「閘門在互動模式下**擋不擋得下來**」——單靠 INT 答不了：
  # INT 大多會過，而「全過」證明不了閘門會拒交（沒有負控制的綠燈不算數）。
  if [ "$arm" = "INTQ" ]; then TURNS=0; MINRUN=${TTY_QUIT_AT:-8}; POSTDONE=0; fi
  echo "cmd=tty_drive --turns $TURNS -- launcher --stdin inherit -- $(basename "$W") pi <prompt>" \
      >> "$ROOT/argv/$name.argv.txt"
  echo "turn2_text=$TURNTEXT" >> "$ROOT/argv/$name.argv.txt"
  # ⚠ **不給 `--json`**：給了 agent 的 stdout 就進檔案 ⇒ pi 落回 print
  #   （`mode_oracle.sh` 的 D 格就是量這一條）。summary 改從 run_RUN-ON.json 讀。
  timeout "$OUTER_TIMEOUT" $PY "$REPO/ops/vacantrun/tty_drive.py" \
      --transcript "$ROOT/pty/$name.pty" --report "$ROOT/pty/$name.drive.json" \
      --done-when-hooklog "$HOOKLOG" --turns "$TURNS" --turn-text "$TURNTEXT" \
      --idle "${TTY_IDLE:-120}" --cap "${TTY_CAP:-1000}" --grace 25 \
      --min-run "$MINRUN" --post-done "$POSTDONE" \
      -- $PY -m vacant_network.vrun.launcher \
          --workspace "$ws" --run-dir "$rd" --suite "$TPL/$tid/tests_visible" \
          --task-id "$TASKID" --sandbox none \
          --test-timeout "$TEST_TIMEOUT" --timeout "$AGENT_TIMEOUT" --retry none \
          --stdin inherit \
          -- "$W" pi "$PROMPT" \
      > "$ROOT/logs/$name.stdout" 2> "$ROOT/logs/$name.stderr"
  rc=$?
  ;;
*) echo "不認得的臂：$arm（有 PRT｜PTP｜INT｜INT2｜INTQ）。停。" >&2; exit 2 ;;
esac
t1=$(date +%s.%N)
echo "exit_code=$rc"
echo "$rc" > "$rd/_launcher_exit_code.txt" 2>/dev/null || true
awk -v a="$t0" -v b="$t1" 'BEGIN{printf "cell_wall_s=%.2f\n", b-a}' | tee "$rd/_cell_wall_s.txt"
echo "$arm" > "$rd/_arm.txt" 2>/dev/null || true
echo "=== END $name $(date -u +%FT%T.%NZ) ==="
echo
