#!/usr/bin/env bash
# 一格 ＝ 一題 × 一臂（ON=有 Vacant／OFF=純 pi），**兩臂都走對話介面（真 pty，打字）**。
#
# 唯一的差異是「有沒有 Vacant」：
#   ON  : vacant on pi …   ⇒ 模型通道經 Vacant 的 proxy、結束時跑驗收、簽收據、退出碼是裁決
#   OFF : pi               ⇒ pi 自己的設定直接指到上游，沒有 proxy、沒有閘門、沒有收據
# 其餘全部相同：同一題、同一個工作區內容、**同一句打進輸入框的話**、同一套完成判定、
# 同一種離開方式（/quit → Ctrl-D → SIGTERM）、同一個模型與上游。
set -u
S=/tmp/claude-0/-home-user-Vacant/95031510-877c-5775-9ca5-176a6cda6673/scratchpad
H=$S/lcb
REPO=/home/user/Vacant
VEN=$REPO/.venv/bin
UPSTREAM=${HE_UPSTREAM:-https://1003.taild870c4.ts.net/v1}
MODEL=${HE_MODEL:-gemma-4-12b-it-qat}
# 打進輸入框的那一句。**兩臂逐字相同**，而且不含隱藏測資、不含「你有責任／會被懲罰」（鐵律 1、2）。
TEXT=${HE_TEXT:-'Read goal.md and contract.md in this directory and do what they say. Use your tools to write solution.py.'}

export PATH=$S/pi/node_modules/.bin:$PATH
export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
export VACANT_AGENT_MODEL=$MODEL
export VACANT_RUN_ALLOW_PUBLIC_UPSTREAM=1
export VACANT_RUN_UPSTREAM_OPENAI=$UPSTREAM

tid="$1"; arm="$2"
TPL=$H/tasks/$tid
ws=$H/run/ws_${tid}_${arm}; rd=$H/run/rd_${tid}_${arm}; log=$H/run/logs
mkdir -p "$log"
rm -rf "$ws" "$rd"; mkdir -p "$ws"
cp "$TPL/goal.md" "$TPL/contract.md" "$TPL/run_tests.sh" "$ws/"
cp -r "$TPL/tests_visible" "$ws/"
# 工作區純度 fail-closed 擋門
want="./contract.md ./goal.md ./run_tests.sh ./tests_visible/test_visible.py"
got="$(cd "$ws" && find . -type f | sort | tr '\n' ' ' | sed 's/ $//')"
[ "$got" = "$want" ] || { echo "工作區不乾淨，停。got=$got" >&2; exit 3; }

t0=$(date +%s); date -u +%FT%T.%NZ > "$log/${tid}_${arm}.t_start"
if [ "$arm" = "ON" ]; then
  cd "$ws"
  timeout "${HE_TIMEOUT:-1500}" python3 $H/drive.py \
      --transcript "$log/${tid}_ON.pty" --report "$log/${tid}_ON.drive.json" \
      --text "$TEXT" --idle "${HE_IDLE:-45}" --min-run "${HE_MINRUN:-25}" --cap "${HE_CAP:-1200}" \
      -- $VEN/vacant on pi \
           --workspace "$ws" --run-dir "$rd" --suite "$TPL/tests_visible" \
           --task-id "he_${tid}_ON" --sandbox none --test-timeout 120 \
           --retry none --allow-public-upstream \
      > "$log/${tid}_ON.stdout" 2> "$log/${tid}_ON.stderr"
  rc=$?
else
  # 完全沒有 Vacant：pi 自己的設定直接指上游
  # 🔴 **逐欄對齊 `vacant_network/vrun/agentwrap.py::wire_pi`**（provider id／api／compat／
  #    contextWindow／maxTokens／模型 name／啟動旗標全部一樣）。2026-09-22 第一次跑時
  #    contextWindow 兩臂不同（131072 vs 262144），那是**量具造成的干擾不是 Vacant 的差異**，
  #    抓到之後整批作廢重跑。兩臂唯一的差別必須只有「有沒有 Vacant」。
  cfg=$H/run/cfg_off_$tid; rm -rf "$cfg"; mkdir -p "$cfg"
  cat > "$cfg/models.json" <<JSON
{"providers":{"vacantproxy":{"baseUrl":"$UPSTREAM","api":"openai-completions",
 "apiKey":"sk-vacant-run","compat":{"supportsDeveloperRole":false,"supportsReasoningEffort":false},
 "models":[{"id":"$MODEL","name":"m","contextWindow":262144,"maxTokens":16384}]}}}
JSON
  export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
  export PI_CODING_AGENT_DIR=$cfg
  cd "$ws"
  timeout "${HE_TIMEOUT:-1500}" python3 $H/drive.py \
      --transcript "$log/${tid}_OFF.pty" --report "$log/${tid}_OFF.drive.json" \
      --text "$TEXT" --idle "${HE_IDLE:-45}" --min-run "${HE_MINRUN:-25}" --cap "${HE_CAP:-1200}" \
      -- pi --provider vacantproxy --model m \
      > "$log/${tid}_OFF.stdout" 2> "$log/${tid}_OFF.stderr"
  rc=$?
fi
t1=$(date +%s); date -u +%FT%T.%NZ > "$log/${tid}_${arm}.t_end"
echo "$rc" > "$log/${tid}_${arm}.rc"
echo "$((t1-t0))" > "$log/${tid}_${arm}.wall_s"
# 隱藏尺（run 結束之後才跑，不回饋給模型）
python3 $H/score.py "$tid" "$ws/solution.py" > "$log/${tid}_${arm}.hidden.json" 2>&1
echo "=== $tid $arm rc=$rc wall=$((t1-t0))s hidden=$(python3 -c "
import json;print(json.load(open('$log/${tid}_${arm}.hidden.json')).get('ok'))" 2>/dev/null)"
