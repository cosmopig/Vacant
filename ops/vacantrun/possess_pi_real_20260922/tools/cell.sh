#!/usr/bin/env bash
# 一格 ＝ 一題 × 真 pi × 真模型 × **vacant install 的 extension 路徑**。
#
# 與 `ops/vacantrun/pi_tty_20260920/pi_tty_cell.sh`（凍結）的**唯一刻意差異**：
# 那一批走 `vacant run -- wrap_agent.sh pi`（relocate 路，每次要打指令）；
# 本批走 **PATH shim**（`vacant install` 之後使用者照舊打 `pi`，命令列零個 vacant）。
# 其餘逐字沿用：prompt、工作區四個檔、純度 fail-closed 擋門、`--sandbox none`、
# test-timeout 120、retry none、模型 gemma-4-12b-it-qat。
#
# ⚠ 上游是**公開 Funnel** 不是 LAN 的 1003 ⇒ 必須明講 VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1，
#   而且那一格會以 `upstreams_public_allowed: true` 落進收據。兩批不可混講。
set -u
S=/tmp/claude-0/-home-user-Vacant/95031510-877c-5775-9ca5-176a6cda6673/scratchpad
R=$S/five
REPO=/home/user/Vacant
TPL=$REPO/ops/gain/r534/templates
export HOME=$R/home
export PATH=$S/pi/node_modules/.bin:$PATH
PROMPT='Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.'

tid="$1"; rep="${2:-1}"; name="${tid}_r${rep}"
ws=$R/ws_$name
mkdir -p "$R/logs" "$R/argv"
rm -rf "$ws"; mkdir -p "$ws"
cp "$TPL/$tid/goal.md" "$TPL/$tid/contract.md" "$TPL/$tid/run_tests.sh" "$ws/"
cp -r "$TPL/$tid/tests_visible" "$ws/"

# 工作區純度擋門（fail-closed），與凍結那批逐字同一套
want="./contract.md ./goal.md ./run_tests.sh ./tests_visible/test_visible.py"
got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ' | sed 's/ $//')"
if [ "$got" != "$want" ]; then
  echo "工作區不乾淨，停。" >&2; echo "  want: $want" >&2; echo "  got : $got" >&2; exit 3
fi

# 權威的驗收在工作區**外**（`launcher` 會擋工作區內的 suite）。
export VACANT_SUITE="$TPL/$tid/tests_visible"
export VACANT_TEST_TIMEOUT=120
export VACANT_AGENT_MODEL=gemma-4-12b-it-qat
export VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1

{
  echo "task=$tid rep=$rep"
  echo "route=PATH shim（vacant install 的 extension 路徑）"
  echo "prompt=$PROMPT"
  echo "suite=$VACANT_SUITE"
  echo "upstream=（見 install state）公開 Funnel"
  echo "workspace_files=$got"
} > "$R/argv/$name.txt"

t0=$(date +%s)
cd "$ws" || exit 2
timeout 1500 "$HOME/.vacant/possess/bin/pi" -p "$PROMPT" < /dev/null \
    > "$R/logs/$name.stdout" 2> "$R/logs/$name.stderr"
rc=$?
t1=$(date +%s)
echo "$rc" > "$R/logs/$name.rc"
echo "$((t1-t0))" > "$R/logs/$name.wall_s"
echo "=== $name rc=$rc wall=$((t1-t0))s"
grep '\[vacant\] pi' "$R/logs/$name.stderr" | tail -1
