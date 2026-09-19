#!/usr/bin/env bash
# 一個 agent × 一種接線方式。**跑在 uid 1001 上**（outer.sh 降過來的）。
#
#   用法：inner.sh <envfile> <agent> <variant> <prompt...>
#   （envfile 在最前面是 outer.sh 的呼叫約定：它把 ENVF 插在第一個）
#   variant ∈ {wired, half}
#     wired ── 走 `ops/vacantrun/wrap_agent.sh`：`envmap.CONFIG_ROUTE` 那份名單
#              的可執行版本，**接線正確**。這是正向控制。
#     half  ── **故意只接一半**：環境變數是 launcher 設好的（agent 一定拿得到），
#              但框架自己的設定路線完全不做。問的是：它會安靜走預設上游嗎？
#
# ⚠ 每個 agent 的 half 長什麼樣不一樣，因為「一半」對每個框架的意思不同。
#   逐格寫在下面的 case，每一條都是**這一輪實測的那一條**，不是推論。
#
# ⚠ **這支不准用 `exec`**：exec 會換掉行程，下面那個 `trap cleanup EXIT` 就永遠
#   不會跑，而 cleanup 正是「Hermes 以 0600 建檔害 launcher 炸掉」的手工緩解。
set -uo pipefail
R=/var/tmp/vbypass
ENVF="$1"; AGENT="$2"; VARIANT="$3"; shift 3
PROMPT="$*"
set -a; source "$ENVF" >/dev/null 2>&1 || true; set +a
umask 0000
export HOME="$R/work/home"
export PATH="$R/hv/bin:/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:/home/user1/.local/bin:/usr/bin:/bin"
export XDG_CONFIG_HOME="$R/work/xdg-$$" XDG_DATA_HOME="$R/work/xdgd-$$" XDG_CACHE_HOME="$R/work/xdgc-$$"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
MODEL="${VACANT_AGENT_MODEL:-gemma-4-12b-it-qat}"

# ⚠ Hermes（以及別的框架）會在 cwd 以 **0600** 建檔，而 launcher 是另一個 uid
#   ⇒ `_frozen_*` 的 copytree 會 PermissionError **把整跑炸掉、沒有收據**。
#   這個 trap 是**手工補的緩解**；真正的修法（讓它落成 infra_void）在
#   `launcher_freeze_infra_void.patch`，本輪另外量了它沒有 trap 時的樣子
#   （`VB_NO_CHMOD=1`）。
cleanup() { [ "${VB_NO_CHMOD:-0}" = "1" ] || chmod -R a+rwX . 2>/dev/null || true; }
trap cleanup EXIT

if [ "$VARIANT" = "wired" ]; then
  "$R/repo/ops/vacantrun/wrap_agent.sh" "$AGENT" "$PROMPT" < /dev/null
  rc=$?; cleanup; exit $rc
fi

# ── half：只有環境變數，沒有任何框架專屬接線 ──────────────────────────
case "$AGENT" in
pi)
  # 沒有 models.json、沒有 --provider。pi 的內建 provider baseUrl 是編進
  # bundle 的常數（envmap 誠實邊界 1）⇒ 這一格問的是它會不會去打那個常數。
  pi -p "$PROMPT" < /dev/null ;;
opencode)
  # 沒有 OPENCODE_CONFIG_CONTENT。只有 launcher 設的 OPENAI_BASE_URL，
  # 模型 id 是**本地模型**（不在 models.dev 註冊表裡）——這正是真實的誤用：
  # 使用者要接本地模型卻忘了設定路線。
  opencode run -m "openai/$MODEL" "$PROMPT" < /dev/null ;;
claude)
  # Claude Code 本來就是零接線（ANTHROPIC_BASE_URL 直接生效）⇒ 這一格的
  # 「一半」其實等於「全部」。留著是為了量它**有沒有別的路**（B 類），
  # 不是為了證明它漏。
  claude -p "$PROMPT" --model "$MODEL" --permission-mode bypassPermissions < /dev/null ;;
codex)
  # 沒有 CODEX_HOME、沒有自訂 provider。HOME 是全新的 ⇒ `~/.codex` 不存在
  # ⇒ **使用者自己的憑證一個 byte 都碰不到**（而且 auth.json 是 0600，
  # 這個 uid 本來就讀不到）。問的是它會不會走內建 openai provider 出網。
  codex exec --skip-git-repo-check "$PROMPT" < /dev/null ;;
hermes)
  # V3 的活體標本：provider 選了 custom，但 **CUSTOM_BASE_URL 被拿掉**。
  # Hermes 0.19.0 解 base_url 的鏈尾是編死的 https://openrouter.ai/api/v1。
  unset CUSTOM_BASE_URL OPENROUTER_BASE_URL
  CFG="$(mktemp -d "$R/work/hcfg-XXXXXX")"
  export HERMES_HOME="$CFG"
  hermes -z "$PROMPT" --yolo --provider custom -m "$MODEL" < /dev/null ;;
*)
  echo "unknown agent: $AGENT" >&2; exit 2 ;;
esac
rc=$?; cleanup; exit $rc
