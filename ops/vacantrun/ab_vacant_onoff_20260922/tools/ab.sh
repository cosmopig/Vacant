#!/usr/bin/env bash
# 一題 × 三臂：**沒有 Vacant** ↔ **Vacant V0（閘門，單次）** ↔ **Vacant V1（閘門＋重試）**
#
# 三臂唯一刻意的差異就是那三件事。其餘逐字相同：同一題、同一個 prompt、同一個模型、
# 同一個上游、同一份權威驗收（在工作區外）、同一套工作區純度 fail-closed 擋門。
#
# ⚠ **V1 臂的 prompt 多一個 `{VACANT_FEEDBACK}` placeholder**，但 launcher 保證
#   **第 1 次嘗試會把它換成空字串 ⇒ 第一次的 argv 與另外兩臂逐位元相同**
#   （`retry.py` §V2 規則 2，`tests/test_vacant_run_retry.py` 有可執行證明）。
#
# ⚠ OFF 臂**沒有 proxy 也沒有收據**：它的「可見／隱藏」是我們在**事後**自己算的
#   反事實——「如果沒有 Vacant，那一份東西就這樣出貨了」。不是收據，不可混講。
set -u
S=/tmp/claude-0/-home-user-Vacant/95031510-877c-5775-9ca5-176a6cda6673/scratchpad
A=$S/ab
REPO=/home/user/Vacant
TPL=$REPO/ops/gain/r534/templates
PY=$REPO/.venv/bin/python
UPSTREAM=${AB_UPSTREAM:-https://1003.taild870c4.ts.net/v1}
MODEL=${AB_MODEL:-gemma-4-12b-it-qat}
PROMPT='Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.'
export PATH=$S/pi/node_modules/.bin:$PATH
export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
export VACANT_AGENT_MODEL=$MODEL
export VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1
export VACANT_RUN_UPSTREAM_OPENAI=$UPSTREAM

tid="$1"; arm="$2"
ws=$A/ws_${tid}_${arm}; rd=$A/rd_${tid}_${arm}
mkdir -p $A/logs
rm -rf "$ws" "$rd"; mkdir -p "$ws"
cp "$TPL/$tid/goal.md" "$TPL/$tid/contract.md" "$TPL/$tid/run_tests.sh" "$ws/"
cp -r "$TPL/$tid/tests_visible" "$ws/"
want="./contract.md ./goal.md ./run_tests.sh ./tests_visible/test_visible.py"
got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ' | sed 's/ $//')"
[ "$got" = "$want" ] || { echo "工作區不乾淨，停。got=$got" >&2; exit 3; }

t0=$(date +%s)
case "$arm" in
OFF)
  # **完全沒有 Vacant**：pi 自己的設定直接指到上游，沒有 proxy、沒有閘門、沒有收據。
  cfg=$A/cfg_off_$tid; rm -rf $cfg; mkdir -p $cfg
  cat > $cfg/models.json <<JSON
{"providers":{"direct":{"baseUrl":"$UPSTREAM","api":"openai-completions",
 "apiKey":"sk-none","compat":{"supportsDeveloperRole":false,"supportsReasoningEffort":false},
 "models":[{"id":"$MODEL","name":"$MODEL","contextWindow":131072,"maxTokens":16384}]}}}
JSON
  printf '{"defaultProvider":"direct","defaultModel":"%s"}\n' "$MODEL" > $cfg/settings.json
  export PI_CODING_AGENT_DIR=$cfg
  cd "$ws" && timeout 1500 pi -p "$PROMPT" < /dev/null \
      > $A/logs/${tid}_OFF.stdout 2> $A/logs/${tid}_OFF.stderr
  rc=$?
  ;;
V0)
  # 閘門，單次嘗試（`vacant install` 的 shim 走的就是這條）
  export VACANT_SUITE="$TPL/$tid/tests_visible"
  cd "$ws" && timeout 1500 $PY -m vacant_network.vrun.launcher \
      --workspace "$ws" --run-dir "$rd" --suite "$TPL/$tid/tests_visible" \
      --task-id "ab_${tid}_V0" --sandbox none --test-timeout 120 \
      --timeout 900 --retry none --allow-public-upstream \
      -- $PY -m vacant_network.vrun.agentwrap pi "$PROMPT" \
      > $A/logs/${tid}_V0.stdout 2> $A/logs/${tid}_V0.stderr
  rc=$?
  ;;
V1)
  # 閘門 ＋ 重試（`revise`：保留工作區、把**可見驗收的失敗原文**回饋、再跑一次）
  cd "$ws" && timeout 3000 $PY -m vacant_network.vrun.launcher \
      --workspace "$ws" --run-dir "$rd" --suite "$TPL/$tid/tests_visible" \
      --task-id "ab_${tid}_V1" --sandbox none --test-timeout 120 \
      --timeout 900 --retry revise --max-attempts 3 --feedback-into both \
      --allow-public-upstream \
      -- $PY -m vacant_network.vrun.agentwrap pi "${PROMPT}{VACANT_FEEDBACK}" \
      > $A/logs/${tid}_V1.stdout 2> $A/logs/${tid}_V1.stderr
  rc=$?
  ;;
*) echo "arm 只有 OFF|V0|V1" >&2; exit 2 ;;
esac
t1=$(date +%s)
echo "$rc" > $A/logs/${tid}_${arm}.rc
echo "$((t1-t0))" > $A/logs/${tid}_${arm}.wall_s
echo "=== $tid $arm rc=$rc wall=$((t1-t0))s"
tail -2 $A/logs/${tid}_${arm}.stderr | head -2
