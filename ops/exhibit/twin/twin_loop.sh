#!/usr/bin/env bash
# `twinlink loop` 的**唯一一條**命令列。開機腳本與 systemd unit 都走這一支。
#
# 為什麼要獨立成一支（2026-09-21）：在這之前，「手機→公網→庫→1003→螢幕」
# 那條鏈**一個字都沒有出現在開機路徑上**——`exhibit_boot.sh`、`venue_check.sh`、
# 三個 systemd 檔對 `twinlink|twinstore|visitors.json|&twin=` 的 grep 全是 0
# （正控制：同一個 grep 打在 `twinlink.py` 上 16 命中 ⇒ grep 量得動）。
# 於是布展當天 `venue_check.sh` 會印綠，而整條數位分身線沒有被量過一個字。
#
# 命令列寫在 unit 檔裡的問題是它**測不動**，而且 systemd 會先展開 `$VAR`，
# `${FOO:-預設}` 那種寫法在 unit 裡不成立（systemd 不支援 `:-`）。
# 寫成腳本就兩個問題一起沒有了：unit 只寫一個路徑，這一支自己能跑能測。
#
#   ./twin_loop.sh                 真的跑（永不結束，展場無人值守）
#   ./twin_loop.sh --print-cmd     只印出它會跑什麼（token 遮成 ***），退出 0
#   ./twin_loop.sh --rounds 1      跑一輪就結束（驗收用）
#
# 環境變數（**token 只從環境進來，不進版控**）：
#   VACANT_TWIN_CLOUD_TOKEN  必要。沒有就 **exit 78 並說為什麼**，不是安靜不做事。
#   VACANT_TWIN_CLOUD        預設 https://vacant-world.cosmopig.com
#   VACANT_TWIN_DB           預設 <repo>/ops/exhibit/twin/store/twinstore.sqlite3
#   VACANT_TWIN_INIT         設成 1 才准建一張**新的空庫**（第一次布展）。
#                            預設不准：路徑打錯要紅，不要安靜地演一個空世界。
#   VACANT_HM                預設 <repo>/../vacant_hm
#   VACANT_TWIN_OUT          預設 $VACANT_HM/world3/live/visitors.json
#   VACANT_TWIN_INTERVAL     預設 15（秒）
#   VACANT_TWIN_ENDPOINT     不設就由 twinlink 自己探（127.0.0.1 → VMware → Tailscale）
#
# ⚠ **`--out` 指的那個檔就是電視 snapshot 那一層讀的檔。** commit 進 vacant_hm 的
#   那一份是 `people: []`＋`generated_at: null` 的佔位檔；**在這一支跑起來之前，
#   沒有任何東西會去寫它**。`venue_check.sh` 第八節量的就是這件事。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
PY="${PYTHON:-python3}"
HM="${VACANT_HM:-$(cd "$REPO/.." && pwd)/vacant_hm}"
DB="${VACANT_TWIN_DB:-$REPO/ops/exhibit/twin/store/twinstore.sqlite3}"
OUT="${VACANT_TWIN_OUT:-$HM/world3/live/visitors.json}"
CLOUD="${VACANT_TWIN_CLOUD:-https://vacant-world.cosmopig.com}"
INTERVAL="${VACANT_TWIN_INTERVAL:-15}"
ROUNDS=0
PRINT_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --print-cmd) PRINT_ONLY=1 ;;
    --rounds)    ROUNDS="$2"; shift ;;
    --out)       OUT="$2"; shift ;;
    --db)        DB="$2"; shift ;;
    --cloud)     CLOUD="$2"; shift ;;
    --interval)  INTERVAL="$2"; shift ;;
    *) echo "twin_loop：不認得的參數 $1" >&2; exit 2 ;;
  esac
  shift
done

TOKEN="${VACANT_TWIN_CLOUD_TOKEN:-}"

# 🔴 fail-loud。沒有 token ＝ 這條鏈**收不到任何新觀眾**，那不是「跑起來但是 0 個人」。
#    安靜地空轉一整天是這個 repo 反覆抓到的病（「判成 0 之前先證明量得動」）。
if [ "$PRINT_ONLY" = "0" ] && [ -z "$TOKEN" ]; then
  cat >&2 <<'MSG'
✗ 沒有 VACANT_TWIN_CLOUD_TOKEN ⇒ twinlink loop 不啟動。
  沒有它，公網那個郵箱抄不進來：**觀眾用手機投的卡永遠不會變成分身**。
  這不是「0 個觀眾」，是這條線根本沒接上——所以這裡是 exit 78 不是安靜跳過。

  systemd：把它寫進 /etc/vacant/twin.env（chmod 600，不要進版控）
      VACANT_TWIN_CLOUD_TOKEN=<公網那把>
  手動：  VACANT_TWIN_CLOUD_TOKEN=<公網那把> ./twin_loop.sh
  展件本身照樣跑（凍結重放＋庫裡已有的分身）；缺的只有「新的人」。
MSG
  exit 78
fi

# `loop --out` 只在 export 的時候 mkdir 到那一層，但如果連 world3/live 都不在，
# 那多半是 VACANT_HM 指錯了——與其安靜地在別的地方生一個沒人讀的檔，不如現在講。
if [ "$PRINT_ONLY" = "0" ] && [ ! -d "$(dirname "$OUT")" ]; then
  echo "✗ 快照要寫進 $(dirname "$OUT")，但那個目錄不在。" >&2
  echo "  VACANT_HM 指對了嗎（現在是 ${HM}）？電視讀的是同源的 world3/live/visitors.json。" >&2
  exit 2
fi

# 🔴 庫不在就**現在**講，不要讓 twinlink 安靜地建一張空庫再回綠
#    （缺陷 C，2026-09-22）。twinlink 自己也擋（rc 5），這裡多擋一層是因為
#    展場看得到的是這一支印的字，不是 journal 裡那段 JSON。
WANT_INIT=0
if [ "${VACANT_TWIN_INIT:-0}" = "1" ]; then
  WANT_INIT=1
  echo "⚠ VACANT_TWIN_INIT=1 ⇒ 允許建一張新的空庫：$DB" >&2
elif [ "$PRINT_ONLY" = "0" ] && [ ! -f "$DB" ]; then
  echo "✗ 真相來源不在：$DB" >&2
  echo "  這一支**不會**替你建一個空庫再回綠——那會讓「我沒找到庫」看起來" >&2
  echo "  跟「今天沒有人來」一樣，而展場沒有人守著。" >&2
  echo "  · 路徑打錯了？VACANT_TWIN_DB 現在是 ${VACANT_TWIN_DB:-（沒設，用預設）}" >&2
  echo "  · 真的要開新場地（第一次布展）⇒ VACANT_TWIN_INIT=1 ./twin_loop.sh" >&2
  exit 5
fi

# ⚠ **不要用 `"${ARR[@]}"` 展開一個空陣列。** `set -u` 之下 bash 3.2（macOS 內建）
#   會判 `unbound variable` 直接死掉——判準：
#   tests/test_exhibit_twin_wiring.py::test_twin_loop_print_cmd_masks_the_token。
CMD=("$PY" "$REPO/ops/exhibit/twin/twinlink.py" --db "$DB")
if [ "$WANT_INIT" = "1" ]; then
  CMD+=(--init)
fi
CMD+=(loop --cloud "$CLOUD" --token "$TOKEN"
      --interval "$INTERVAL" --rounds "$ROUNDS" --out "$OUT")
if [ -n "${VACANT_TWIN_ENDPOINT:-}" ]; then
  CMD+=(--endpoint "$VACANT_TWIN_ENDPOINT")
fi
# 分身怎麼生（2026-09-24，decisions/DECISION_20260924_TWIN_AGENT_RUN.md）：
#   agent（預設）＝分身在 vacant run 底下用 pi 真跑、自己決定任務；
#   chat ＝舊路徑（直打模型要三句台詞，沒有收據）。
#   這台沒有 pi 的話 agent 會**誠實地**退到 chat 並標 degrade_kind=agent_unavailable
#   ——**明講出來**，不要讓展場以為在真跑。
CMD+=(--engine "${VACANT_TWIN_ENGINE:-agent}"
      --parallel "${VACANT_TWIN_PARALLEL:-2}")
if [ -n "${VACANT_EVENTS:-}" ]; then
  CMD+=(--events "$VACANT_EVENTS")
fi
if [ "$PRINT_ONLY" = "0" ] && [ "${VACANT_TWIN_ENGINE:-agent}" = "agent" ] \
   && ! command -v "${VACANT_TWIN_PI:-pi}" >/dev/null 2>&1; then
  echo "⚠ 這台找不到 pi（${VACANT_TWIN_PI:-pi}）⇒ 分身**不會**真跑，" >&2
  echo "  會退到直打模型（engine=lmstudio:*，degrade_kind=agent_unavailable，沒有收據）。" >&2
  echo "  要真跑：把 pi 0.85.x 放進 PATH，或 VACANT_TWIN_PI=<pi 的完整路徑>。" >&2
fi

if [ "$PRINT_ONLY" = "1" ]; then
  # ⚠ token 遮掉。這一行會被貼進紀錄與 journal。
  for a in "${CMD[@]}"; do
    case "$a" in
      "$TOKEN") [ -n "$TOKEN" ] && printf '%s ' '***' || printf '%s ' "$a" ;;
      *) printf '%s ' "$a" ;;
    esac
  done
  echo
  exit 0
fi

echo "[twin_loop] db=$DB out=$OUT cloud=$CLOUD interval=${INTERVAL}s rounds=$ROUNDS"
exec "${CMD[@]}"
