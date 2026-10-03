#!/usr/bin/env bash
# 一格＝一題 × 一組 × 第幾次（root 呼叫）。用法：cell.sh <格子名> <題目目錄> <組：A|C361> <代理標籤>
# 題目目錄（staged，root 700 底下）：instruction.txt、workspace/、hidden/、scorer.py
#
# 流程（逐字對照 Harbor 6cb9ff31 的 pi agent 與 redesign 分支的 ops/eval/harbor_vacant.py）：
#  1. 開一個**新的** Linux 使用者（這一格專用），home／/tmp／工作區全是新的空目錄 ⇒ 格子之間不共用任何 pi 設定、session、記憶。
#  2. C 組：在那個使用者的圍牆裡 `pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install`
#     ——就是使用者會打的安裝指令（harbor_vacant.py:66-78）。A 組不做。**不設任何 Vacant 環境變數。**
#  3. 寫 pi 的自訂端點設定 /tmp/harbor-pi-agent/models.json（Harbor pi.py 的 _build_custom_models_json）。
#  4. `PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent pi --print --mode json --session-dir /logs/agent/pi/sessions
#      --provider harbor-endpoint --model <MODEL> <題目>`，stdout 過濾 message_update 後 tee 成 pi.txt（Harbor pi.py run()）。
#     時限 AGENT_TIMEOUT（預設 1800 秒，同 DABstep／程式題的 Harbor 設定），沒有回合上限（不掛 max-turns 擴充）。
#  5. 殺光那個使用者的行程 → 收紀錄（pi.txt、session、~/.vacant、C 組檢查、最後的工作區）→
#     另開一個**計分專用的新使用者**、在圍牆裡跑 scorer.py（隱藏測試只在這一步、只進計分使用者的目錄）→ 刪兩個使用者。
# 紀錄寫在 /srv/eval/cells/<格子名>/（root 700）；最後寫 DONE。**這支不印分數**（批次跑完之前不看分數）。
set -u
CELL=$1; T=$2; ARM=$3; TAG=$4
MODEL=${MODEL:-gemma-4-12b-it-qat}
PROXY=${PROXY:-http://127.0.0.1:18900}
UP=${UP:-g4}
# vacant-dev 複製批次（2026-10-02）：UP=auto ⇒ 依題目路徑的 cksum 固定分到 g1003／g1004（同一題的各組、各次都在同一台，台的差不進組別的差）
# 2026-10-02 12:55 起（偏離，記在 RUNLOG）：改成「每個單位開跑時分給進行中格數較少的那台」（平手給 g1003），同一單位（同題同次）的各組照樣在同一台。
# 第一個開跑的那一組在鎖裡決定、寫進 /srv/eval/unit_up/<題目雜湊>-s<次>，其餘組讀同一個檔。進行中＝有 upstream 檔、還沒有 DONE 的格子。
if [ "$UP" = auto ]; then
  _uk=$(printf %s "$T" | sha1sum | cut -c1-16)-s${CELL##*-s}; mkdir -p /srv/eval/unit_up
  UP=$(flock /srv/eval/unit_up.lock bash -c '
    f=/srv/eval/unit_up/'"$_uk"'
    if [ -f "$f" ]; then cat "$f"; exit 0; fi
    n3=0; n4=0
    for u in /srv/eval/cells/*/upstream; do d=${u%/upstream}; [ -f "$d/DONE" ] && continue
      case $(cat "$u") in g1003) n3=$((n3+1));; g1004) n4=$((n4+1));; esac; done
    # 10-03 加：健康檢查——那台的 LM Studio 要真的載著 gemma（/api/v0/models state=loaded）才分給它；兩台都不行就每 60 秒再看一次
    # （10-02 18:27 起 1003 沒有模型、格子幾秒內失敗，「進行中最少」反而一直把新單位分過去）
    ok() { curl -s -m 8 "http://$1:1234/api/v0/models" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if any(m.get(\"id\")==\"gemma-4-12b-it-qat\" and m.get(\"state\")==\"loaded\" for m in d.get(\"data\",[])) else 1)" 2>/dev/null; }
    while true; do
      h3=0; h4=0; ok 100.119.113.56 && h3=1; ok 100.86.226.21 && h4=1
      if [ $h3 = 1 ] && [ $h4 = 1 ]; then if [ $n3 -le $n4 ]; then up=g1003; else up=g1004; fi; break; fi
      if [ $h3 = 1 ]; then up=g1003; break; fi
      if [ $h4 = 1 ]; then up=g1004; break; fi
      echo "$(date -u +%FT%TZ) no healthy upstream" >> /srv/eval/unhealthy.log; sleep 60
    done
    echo $up > "$f"; echo $up')
fi
AGENT_TIMEOUT=${AGENT_TIMEOUT:-1800}
# DABstep × v3.7（2026-10-02）：回合上限＝Harbor 6cb9ff31 pi.py 的 max-turns 擴充逐字；空字串＝不設
MAX_TURNS=${MAX_TURNS:-}
# C37R：使用者的安裝指令加 `--budget-reminder`（v3.6 起回合預算提醒預設關）；其他 C 組照常 `vacant install`
VFLAG=""; [ "$ARM" = C37R ] && VFLAG="--budget-reminder"
SCORE_TIMEOUT=${SCORE_TIMEOUT:-900}
BIN=/opt/eval/bin
L=/srv/eval/cells/$CELL
C=/srv/runs/$CELL
SC=/srv/runs/${CELL}_score
WHEEL=$(ls /opt/eval/wheel/*.whl | head -1)
rm -rf "$L" "$C" "$SC"; mkdir -p "$L"
echo "$UP" > "$L/upstream"
now() { date -u +%FT%TZ; }
jq_str() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

# --- 1. 新使用者（useradd 共用 /etc/passwd 鎖 ⇒ 序列化）---
seq=$(flock /srv/eval/seq.lock bash -c 'n=$(( $(cat /srv/eval/seq 2>/dev/null || echo 0) + 1 )); echo $n > /srv/eval/seq; echo $n')
U=$(printf 'a%06d' "$seq"); S=$(printf 's%06d' "$seq")
flock /srv/eval/useradd.lock useradd -M -d /home/$U -s /bin/bash -K UMASK=077 "$U"
flock /srv/eval/useradd.lock useradd -M -d /home/$S -s /bin/bash -K UMASK=077 "$S"
mkdir -p "$C"/{home,tmp,app,agentlog}; chmod 711 "$C"
cp -a "$T/workspace/." "$C/app/"
chown -R "$U:$U" "$C"/{home,tmp,app,agentlog}; chmod 700 "$C"/{home,tmp,app,agentlog}
( cd "$C/app" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum ) > "$L/workspace_before.sha256"
BASE="$PROXY/t/$TAG/up/$UP/think/off/api/v1"
INSTR=$(cat "$T/instruction.txt")
t_start=$(now)

# --- 2. C 組：使用者的安裝指令（最多試 3 次：PyPI 下載失敗不該算成 C 組的表現；每次都記）---
install_rc=null
if [ "$ARM" != A ]; then
  for k in 1 2 3; do
    echo "=== install attempt $k $(now)" >> "$L/install.log"
    bash $BIN/sandbox.sh "$U" "$C" -- bash -c "set -euo pipefail; pipx install '$WHEEL' && mkdir -p /tmp/harbor-pi-agent && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install $VFLAG" >> "$L/install.log" 2>&1
    install_rc=$?; [ $install_rc = 0 ] && break
    bash $BIN/sandbox.sh "$U" "$C" -- bash -c 'pipx uninstall vacant-network >/dev/null 2>&1; true'
    sleep $((k * 10))
  done
  bash $BIN/sandbox.sh "$U" "$C" -- bash -c 'pipx runpip vacant-network freeze' > "$L/vacant_pip_freeze.txt" 2>&1
fi

# --- 3. pi 的自訂端點設定（Harbor：models.json chmod 600，放在 PI_CODING_AGENT_DIR）---
mkdir -p "$C/tmp/harbor-pi-agent"
python3 - "$C/tmp/harbor-pi-agent/models.json" "$BASE" "$MODEL" <<'EOF'
import json, sys
p, base, model = sys.argv[1:]
json.dump({"providers": {"harbor-endpoint": {"baseUrl": base, "apiKey": "$OPENROUTER_API_KEY",
          "api": "openai-completions", "models": [{"id": model}]}}}, open(p, "w"), indent=2)
open(p, "a").write("\n")
EOF
EXTARG=""
if [ -n "$MAX_TURNS" ]; then
  cat > "$C/tmp/harbor-pi-agent/max-turns.ts" <<'TSEOF'
export default function (pi: any) {
  const maxTurns = __N__;
  let completedTurns = 0;

  pi.on("before_agent_start", (event: any) => ({
    systemPrompt: `${event.systemPrompt}\n\nYou have a hard budget of ${maxTurns} model turns. Complete the task and provide your final answer within that budget.`,
  }));

  pi.on("turn_end", (_event: any, ctx: any) => {
    completedTurns += 1;
    if (completedTurns >= maxTurns) {
      ctx.abort();
    }
  });
}
TSEOF
  sed -i "s/__N__/$MAX_TURNS/" "$C/tmp/harbor-pi-agent/max-turns.ts"
  EXTARG="--extension /tmp/harbor-pi-agent/max-turns.ts"
fi
chown -R "$U:$U" "$C/tmp/harbor-pi-agent"; chmod 700 "$C/tmp/harbor-pi-agent"; chmod 600 "$C/tmp/harbor-pi-agent/models.json"

# --- 4. 跑 pi ---
t0=$(date +%s.%N)
timeout -k 30 "$AGENT_TIMEOUT" bash $BIN/sandbox.sh "$U" "$C" OPENROUTER_API_KEY=sk-dummy "OPENROUTER_BASE_URL=$BASE" "INSTR=$INSTR" "MODEL=$MODEL" "EXTARG=$EXTARG" -- \
  bash -c 'mkdir -p /logs/agent/pi/sessions && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent pi --print --mode json --session-dir /logs/agent/pi/sessions --provider harbor-endpoint --model "$MODEL" $EXTARG "$INSTR" 2>&1 </dev/null | grep -v "\"type\":\"message_update\"" | stdbuf -oL tee /logs/agent/pi.txt' \
  > "$L/pi_stdout.txt" 2> "$L/pi_stderr.txt"
rc=$?
t1=$(date +%s.%N)
wall=$(python3 -c "print(round($t1-$t0,1))")

# --- 5. 收尾：殺光這個使用者的行程（沒有 PID 空間，靠 uid）---
for k in 1 2 3 4 5; do pkill -KILL -u "$U" 2>/dev/null; pgrep -u "$U" >/dev/null || break; sleep 1; done
left=$(pgrep -u "$U" | wc -l)
if [ "$ARM" != A ]; then
  cp "$BIN/vacant_check.py" "$C/tmp/_vacant_check.py"; chown "$U:$U" "$C/tmp/_vacant_check.py"
  bash $BIN/sandbox.sh "$U" "$C" -- bash -c 'py=$(ls -d "$HOME"/.local/share/pipx/venvs/vacant-network/bin/python 2>/dev/null); "${py:-python3}" /tmp/_vacant_check.py' > "$L/vacant_check.json" 2>&1
  pkill -KILL -u "$U" 2>/dev/null
  [ -d "$C/home/.vacant" ] && cp -a "$C/home/.vacant" "$L/vacant_home"
fi
cp -a "$C/agentlog" "$L/agentlog"
cp -a "$C/tmp/harbor-pi-agent" "$L/pi_agent_dir" 2>/dev/null
( cd "$C/app" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum ) > "$L/workspace_after.sha256"
# 最後的工作區：只存新增或改過的檔（題目原有、沒動過的檔只留雜湊），單檔上限 50 MB（超過只留雜湊）
python3 - "$C/app" "$L/workspace_before.sha256" "$L/workspace_after.sha256" "$L/app_final" <<'EOF'
import os, shutil, sys
app, before, after, out = sys.argv[1:]
b = dict(reversed(l.split("  ", 1)) for l in open(before).read().splitlines() if l)
b = {k: v for k, v in b.items()}
kept, skipped = 0, []
for line in open(after).read().splitlines():
    if not line: continue
    h, name = line.split("  ", 1)
    if b.get(name) == h: continue
    src = os.path.join(app, name)
    if os.path.getsize(src) > 50 * 1024 * 1024:
        skipped.append(name); continue
    dst = os.path.join(out, name); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst); kept += 1
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "..", "app_final_note.txt"), "w").write(f"kept {kept}; over 50MB (hash only): {skipped}\n")
EOF

# --- 6. 計分：新的計分使用者、自己的圍牆；隱藏測試只在這裡出現 ---
mkdir -p "$SC"/{home,tmp,app,agentlog}; chmod 711 "$SC"
cp -a "$C/app/." "$SC/app/"
cp -a "$T/hidden" "$SC/agentlog/hidden"; cp "$T/scorer.py" "$SC/agentlog/scorer.py"
chown -R "$S:$S" "$SC"/{home,tmp,app,agentlog}; chmod 700 "$SC"/{home,tmp,app,agentlog}
timeout -k 10 "$SCORE_TIMEOUT" bash $BIN/sandbox.sh "$S" "$SC" -- python3 /logs/agent/scorer.py /logs/agent/hidden /app > "$L/score.json" 2> "$L/score.stderr"
score_rc=$?
for k in 1 2 3; do pkill -KILL -u "$S" 2>/dev/null; pgrep -u "$S" >/dev/null || break; sleep 1; done

# --- 7. 清掉兩個使用者與他們的目錄（紀錄已經複製到 $L）---
flock /srv/eval/useradd.lock userdel "$U" 2>/dev/null; flock /srv/eval/useradd.lock userdel "$S" 2>/dev/null
rm -rf "$C" "$SC"
cat > "$L/meta.json" <<EOF
{"cell": "$CELL", "task_dir": $(jq_str "$T"), "arm": "$ARM", "tag": "$TAG", "model": "$MODEL", "upstream": "$UP",
 "user": "$U", "score_user": "$S", "started": "$t_start", "ended": "$(now)", "rc": $rc, "timeout": $([ $rc = 124 ] && echo true || echo false),
 "agent_timeout_s": $AGENT_TIMEOUT, "wall_s": $wall, "install_rc": $install_rc, "leftover_procs": $left, "score_rc": $score_rc,
 "wheel": $(jq_str "$(basename "$WHEEL")"), "pi_version": "0.87.1", "max_turns": $(jq_str "$MAX_TURNS"), "vacant_install_flags": $(jq_str "$VFLAG")}
EOF
touch "$L/DONE"
echo "cell $CELL arm=$ARM rc=$rc wall=${wall}s install_rc=$install_rc"
