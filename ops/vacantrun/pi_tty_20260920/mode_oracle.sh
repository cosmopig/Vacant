#!/usr/bin/env bash
# 量具：**pi 這一跑到底進了哪一個模式？**——判準取自 pi 自己的碼，不是我們猜的。
#
# `dist/main.js`（pi 0.85.1）逐字：
#
#     const startupBenchmark = isTruthyEnvFlag(process.env.PI_STARTUP_BENCHMARK);
#     if (startupBenchmark && appMode !== "interactive") {
#         console.error(chalk.red("Error: PI_STARTUP_BENCHMARK only supports interactive mode"));
#         process.exit(1);
#     }
#
# ⇒ `PI_STARTUP_BENCHMARK=1` 之下：
#     exit 1 ＋ 那一行 stderr  ⇒ **不是** interactive（print／json／rpc）
#     exit 0 ＋ Startup Timings ⇒ **是** interactive
#   而且互動那條路只做 `interactiveMode.init()` 就收工，**不呼叫模型**
#   ⇒ 這支量具零機時、可以任意重跑。
#
# 用法：`mode_oracle.sh <plain|print|stdoutfile> [stdout 檔]`
#   plain       pi …            （沒有 -p）
#   print       pi -p …
#   stdoutfile  pi … > 檔        （stdin 仍是 pty、只有 stdout 不是）
#
# ⚠ 這支**只回答模式**，不回答中介成不成立。中介的證據在 `run_*.json`
#   的 `requests_seen` 與 `wire_*/index.jsonl`。
set -u
MODE="${1:-}"
OUT="${2:-}"
BASE="${ORACLE_BASE:-http://100.119.113.56:1234}"
MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"

CFG="$(mktemp -d "${TMPDIR:-/tmp}/vacant-oracle-XXXXXX")"
trap 'rm -rf "$CFG"' EXIT INT TERM HUP
cat > "$CFG/models.json" <<EOF
{"providers":{"vacantproxy":{
  "baseUrl":"$BASE/v1",
  "api":"openai-completions",
  "apiKey":"${OPENAI_API_KEY:-sk-vacant-run}",
  "compat":{"supportsDeveloperRole":false,"supportsReasoningEffort":false},
  "models":[{"id":"$MODEL","name":"m","contextWindow":262144,"maxTokens":16384}]}}}
EOF
export PI_CODING_AGENT_DIR="$CFG"
export PI_OFFLINE=1 PI_SKIP_VERSION_CHECK=1 PI_TELEMETRY=0
export PI_STARTUP_BENCHMARK=1

# ⚠ **不可以寫成 `$([ -t 1 ] && …)`**：命令替換會把 stdout 換成一條 pipe
#   ⇒ 那個測試永遠回 0，量具自己說謊（2026-09-20 第一版就是這樣，A 格明明
#   跑出 TUI 卻自報 `stdout_tty=0`）。先測、再印。
if [ -t 0 ]; then SI=1; else SI=0; fi
if [ -t 1 ]; then SO=1; else SO=0; fi
echo "ORACLE mode=$MODE stdin_tty=$SI stdout_tty=$SO" >&2
case "$MODE" in
plain)      pi    --provider vacantproxy --model m "hello" ;;
print)      pi -p --provider vacantproxy --model m "hello" ;;
stdoutfile) pi    --provider vacantproxy --model m "hello" > "$OUT" ;;
*) echo "用法：mode_oracle.sh <plain|print|stdoutfile> [檔]" >&2; exit 2 ;;
esac
rc=$?
echo "ORACLE_EXIT=$rc" >&2
exit $rc
