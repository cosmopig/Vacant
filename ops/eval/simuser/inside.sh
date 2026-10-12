#!/bin/bash
# 模擬使用者（容器裡）：一台已經在用 pi 的機器 → 只照 README 打兩個指令裝 Vacant → 照常用 pi。
# 用法：inside.sh <A|C> <劇本 JSON> <任務文字檔>；輸出在 /o。
# 不設任何 Vacant 環境變數（產品原則 3）；pipx 與 pip 走本機 wheel 目錄（容器不連網）。
set -u
ARM=$1; SCN=$2; TASK=$3; O=/o
# ── 這台機器原本的樣子：node＋pi、一個一般使用者帳號、pipx、pi 設定好自己的模型供應商 ──
ln -sf /opt/node22/bin/node /usr/local/bin/node
printf '#!/bin/sh\nexec node /opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js "$@"\n' > /usr/local/bin/pi
chmod +x /usr/local/bin/pi
useradd -m -s /bin/bash user >/dev/null 2>&1
chown -R user /app
command -v pipx >/dev/null || { echo "this machine has no pipx (install it the distro way first)" > $O/setup_error.txt; exit 3; }
printf 'PIP_NO_INDEX=1\nPIP_FIND_LINKS=/w\n' >> /etc/environment
su - user -c 'mkdir -p ~/.pi/agent && cat > ~/.pi/agent/models.json' <<'JSON'
{"providers": {"mock": {"baseUrl": "http://127.0.0.1:18080/v1", "api": "openai-completions",
  "apiKey": "sk-fake", "compat": {"supportsDeveloperRole": false, "supportsReasoningEffort": false},
  "models": [{"id": "mock-model", "name": "mock-model", "contextWindow": 131072, "maxTokens": 8192}]}}}
JSON
MOCK_SCENARIO=$SCN MOCK_LOG=$O/mock.jsonl MOCK_BODIES=$O/bodies python3 /m/mock_model.py 18080 >/dev/null 2>&1 &
for i in $(seq 50); do (echo > /dev/tcp/127.0.0.1/18080) 2>/dev/null && break; sleep 0.2; done
# ── 人裝 Vacant：README 的兩個指令，各在一個新的登入殼層裡打 ──
if [ "$ARM" = C ]; then
  for cmd in "pipx install vacant-network" "vacant install"; do
    echo "\$ $cmd"
    su - user -c "PIP_NO_INDEX=1 PIP_FIND_LINKS=/w $cmd"
    echo "[exit $?]"
  done > $O/install_transcript.txt 2>&1
fi
# ── 人照常用 pi（和沒裝時同一個指令）──
cp "$TASK" /tmp/task.txt && chmod 644 /tmp/task.txt
su - user -c 'cd /app && pi -p --mode json --provider mock --model mock-model "$(cat /tmp/task.txt)"' \
  > $O/pi_stdout.jsonl 2> $O/pi_stderr.txt
echo $? > $O/pi_exit
cp /app/answer.txt $O/answer.txt 2>/dev/null
cp /home/user/.vacant/trace/projects/*/delivery.* $O/ 2>/dev/null
ls /home/user/.vacant/trace/projects/*/ > $O/vacant_files.txt 2>/dev/null
exit 0
