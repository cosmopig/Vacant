#!/usr/bin/env bash
# 錄一份**離線備援**用的 lifecycle 錄影（L-none，零模型、零網路）。
#
# 為什麼要這一支（2026-09-24「刪事後推導，留錄影重播」）：
# 展場只剩一條路——lifecycle 事件流 → `live_events.Folder` → 電視。
# 離線備援＝重播**錄下來的** lifecycle.jsonl，走同一支 Folder。
# 這一支產生的就是那一份錄影，進版控，讓 `serve_twin.py` 開箱就有東西可以播。
#
# ⚠ **它錄的是 fixture，不是 AI。** `run_twin.py --fixture` 的 agent 是一支腳本：
#   把題庫裡現成的參考解（寫明介面那一格）或壞樁（扣住介面那一格）抄成
#   solution.py 就結束。`requests_seen` 恆為 0 ⇒ 每一格的證據等級都是 **L-none**，
#   電視與手機會照實講「交件是腳本寫的」。閘門、重試迴圈、收據是真的跑過的；
#   站在 agent 位置上的不是 AI。把這份錄影講成「分身做的事」就是把模擬講成證明。
#
# ⚠ **目前只有 L-none 錄影。** 54 格 L-real 那一批（`runs/twin_real_20260919`）
#   是在 lifecycle 事件流出現**之前**跑的，沒有錄影；要在 1003 上用
#   `run_twin.py --events` 重跑才會有。**不准**寫轉換器把舊 run 目錄轉成
#   lifecycle——那等於把事後推導從後門留下來。
#
# ⚠ 刻意用 `--retry revise --max-attempts 2`：扣住介面那一格的腳本兩次都交同一份
#   壞樁 ⇒ 閘門 → 回饋 → 再 spawn 一次 → 再擋下，迴圈在錄影裡看得見。
#   腳本不讀回饋，所以第二次一定一樣——那是腳本的性質，不是 Vacant 的。
#
#   ./record_fixture.sh                  錄 3 位居民 × 9 題 × 2 份題面（54 格，約 2 分鐘）
#   ./record_fixture.sh --residents 1    少錄一點（冒煙用）
#   STAMP=20260924 ./record_fixture.sh   檔名的日期（預設今天）
#
# 產出：ops/exhibit/twin/recordings/fixture_<STAMP>.jsonl ＋ 同名 .pack.json（配對收據）
#       ＋ 同名 .sidecar.jsonl（分身自己的旁註：OFF 臂的事後稽核，`sidecar.py`）
#
# ⚠ 旁註**不是** Vacant 的事件（2026-09-24 人類裁決「分身側自己記一份補回」）：
#   run_twin 在 postaudit_off 完成當下寫進 lifecycle 旁邊的 `.sidecar.jsonl`。
#   配對收據綁它的 sha256（pair_receipts.check_sidecar），改一個位元組就不收。
#   這一支錄的 fixture 兩臂都跑 ⇒ 旁註**一定要有**，沒有就停（不准錄出一份沒有
#   postaudit 的新錄影，然後讓人以為那是舊錄影）。
# 錄完當場用 `serve_twin.py --check` 驗（lifecycle 契約＋電視契約＋路徑不外漏），
# 過不了**不寫進 recordings/**。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
PY="${PYTHON:-python3}"
STAMP="${STAMP:-$(date +%Y%m%d)}"
OUT="$HERE/recordings/fixture_${STAMP}.jsonl"
EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --residents) EXTRA+=(--residents "$2"); shift ;;
    --tasks)     EXTRA+=(--tasks "$2"); shift ;;
    --out)       OUT="$2"; shift ;;
    *) echo "不認得的參數：$1" >&2; exit 2 ;;
  esac
  shift
done

WORK="$(mktemp -d -t twinfixture.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

"$PY" "$REPO/ops/exhibit/twin/run_twin.py" --fixture --out "$WORK/batch" \
  --sandbox "${TWIN_SANDBOX:-auto}" --retry revise --max-attempts 2 \
  --events "$WORK/lifecycle.jsonl" "${EXTRA[@]+"${EXTRA[@]}"}"

# 錄影會被印上展場螢幕：暫存目錄的路徑一個字都不准跟著進去。
if grep -q "$WORK" "$WORK/lifecycle.jsonl"; then
  echo "✗ 錄影裡有暫存目錄的絕對路徑，不收" >&2
  exit 1
fi
if [ ! -s "$WORK/lifecycle.sidecar.jsonl" ]; then
  echo "✗ 沒有旁註（OFF 臂的事後稽核）：run_twin 應該在 postaudit_off 完成時寫它，不收" >&2
  exit 1
fi
if grep -q "$WORK" "$WORK/lifecycle.sidecar.jsonl"; then
  echo "✗ 旁註裡有暫存目錄的絕對路徑，不收" >&2
  exit 1
fi
"$PY" "$REPO/ops/exhibit/twin/serve_twin.py" --check --recording "$WORK/lifecycle.jsonl"

# ── 同一次執行的收據：錄影要有**自己那一批**的收據頁資料，觀眾才驗得到 ──────
# 先在暫存目錄裡配好、驗過，兩個檔才一起搬進 recordings/（不留「有錄影沒收據」的半套）。
# 綁定＝錄影的 sha256 ＋ 逐格鏈頭（pair_receipts.py 的 check_pair）。
# 1003 重跑 L-real 用的是同一條：run_twin.py --events → pair_receipts.py --runs。
NAME="$(basename "$OUT")"
cp "$WORK/lifecycle.jsonl" "$WORK/$NAME"
PAIR_NAME="${NAME%.jsonl}.pack.json"
SIDE_NAME="${NAME%.jsonl}.sidecar.jsonl"
# 旁註要在 pair_receipts 之前就位：build_pair 才會把它的 sha256 綁進資料包。
cp "$WORK/lifecycle.sidecar.jsonl" "$WORK/$SIDE_NAME"
"$PY" "$REPO/ops/exhibit/twin/pair_receipts.py" --recording "$WORK/$NAME" \
  --runs "$WORK/batch" --out "$WORK/$PAIR_NAME"

mkdir -p "$(dirname "$OUT")"
cp "$WORK/$NAME" "$OUT"
cp "$WORK/$SIDE_NAME" "$(dirname "$OUT")/$SIDE_NAME"
cp "$WORK/$PAIR_NAME" "$(dirname "$OUT")/$PAIR_NAME"
"$PY" "$REPO/ops/exhibit/twin/serve_twin.py" --check --recording "$OUT"
"$PY" "$REPO/ops/exhibit/twin/pair_receipts.py" --check --recording "$OUT"
echo "✓ 錄影 → ${OUT}（$(wc -l < "$OUT" | tr -d ' ') 行，L-none：交件是腳本寫的）"
echo "✓ 配對收據 → $(dirname "$OUT")/${PAIR_NAME}"
echo "✓ 旁註 → $(dirname "$OUT")/${SIDE_NAME}（$(wc -l < "$(dirname "$OUT")/$SIDE_NAME" | tr -d ' ') 筆事後稽核：分身補量的，不是 Vacant 的裁決）"
