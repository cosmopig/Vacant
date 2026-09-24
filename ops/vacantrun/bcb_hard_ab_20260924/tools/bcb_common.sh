# BCB-Hard 夜間批次共用設定（預註冊 decisions/prereg/PREREG_20260924_BCB_HARD_VACANT_AB.md）。
# 後端設定（上游、HOME、金鑰）沿用 pilot 目錄；本批的格子寫在 $RUN/<後端>/。
R=/var/tmp/vacant_piext_20260924
B=$R/bcb
RUN=${BCB_RUN:-$R/bcb_run}          # 煙霧測試可另指
T=$R/bcb_tools
BACKEND=${BACKEND:?要先 export BACKEND=1004|1003|gemini}
P=$R/pilot_$BACKEND            # backend.env、home_off、home_on、api.key、repo 都在這裡
source $P/backend.env
REPO=$P/repo
PI=$R/pi/node_modules/.bin/pi
VENV=$B/venv
TPL=${BCB_TPL:-$B/bank/templates}
HIDDEN=${BCB_HIDDEN:-$B/bank/hidden}
NODE_BIN=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin
PROMPT='Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.'
OUT=$RUN/$BACKEND
base_env() {   # $1 = HOME
  export HOME=$1
  # venv 排最前面：agent 自己跑的 python3、閘門驗收的 python3、計分的 python3 都是同一個（題目要的函式庫在裡面）
  export PATH=$VENV/bin:$R/pi/node_modules/.bin:$NODE_BIN:/usr/local/bin:/usr/bin:/bin
  export PYTHONPATH=$REPO
  export MPLBACKEND=Agg
  unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_API_KEY \
        VACANT_AGENT_MODEL PI_CODING_AGENT_DIR VACANT_SUITE VACANT_RUN_ALLOW_PUBLIC_UPSTREAM PILOT_KEY
  [ -f $P/api.key ] && export PILOT_KEY="$(cat $P/api.key)"
  export PI_SKIP_VERSION_CHECK=1
  export PI_OFFLINE=1
}
# ── 圍住 agent（預註冊補充 A1）：pi 沒有內建沙箱，無人看管跑 7 小時又在共用機器上 ⇒
#    每一個 pi 行程（含 GATE 的 shim／launcher）包進 bwrap：根目錄唯讀；只有這一格的工作區、這個後端的
#    HOME、私有 /tmp 可寫；獨立 PID 空間（kill 碰不到外面）；網路保留（要連模型）。四組一樣。
#    ⚠ 這是保護機器，不是安全邊界：網路是通的。
bw() {   # $1 = 工作區；其餘是要跑的指令
  local ws=$1; shift
  bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp \
        --bind "$ws" "$ws" --bind "$HOME" "$HOME" \
        --unshare-pid --die-with-parent --chdir "$ws" "$@"
}
