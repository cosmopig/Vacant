#!/usr/bin/env bash
# gen_asset.sh —— 文字提示 → Google Flow 生成 → 下載 → 落盤驗證，一次跑完。
#
# 用法：
#   ops/exhibit/flow/gen_asset.sh --prompt-file <檔> --id <唯一id> --out <輸出.mp4>
#   ops/exhibit/flow/gen_asset.sh --id <既有id> --out <輸出.mp4> --resume   # 只續等＋下載，不重送
#
# 其他旗標：--prompt "文字"（取代 --prompt-file）、--timeout 秒（預設 900）、
#           --kind video|image|any（預設 any——**模態是 Flow 自己判的**）、
#           --ref <圖檔>（把參考圖掛進提示詞，走「新增素材 → 上傳媒體檔案」；
#             Flow 會先要人做「我具備必要權限」的聲明，本腳本**預設取消**，
#             人同意了才加 --accept-upload-rights；或加 --pause-at-rights 把對話框
#             **留在畫面上等人自己按**（15 分鐘，逾時也不取消，按完 --resume 續跑）。
#             ⚠ 參考圖不是選配：沒掛參考圖生出來的板與既有板**不是同一個系列**
#             （2026-09-20 實測 s10 vs s03，箱型／質感／機位／符號四項全變）），
#           --max-candidates N（一次准收幾份；Flow 的代理設定可設 x1–x4，
#             這台影片 x1、**圖像 x2**。超過就停下來交給人，不猜）、
#           --no-submit（只跑到 prepare 就停，不花額度）、
#           --quality "原始大小"（預設；1080p/4K 是「已提升畫質」＝另一次付費生成，
#           要就 --allow-upscale）、--log-dir 目錄、--strict-prompt。
#
# ════════════════════════════════════════════════════════════════════════
# 我用什麼判斷「生成完成」，以及這個判準什麼時候會錯
# ════════════════════════════════════════════════════════════════════════
# **判準本身：下載回來的檔案通過 ffprobe（有 video stream、時長 > 0.5 秒、
# 能從中間抽出一格畫面）。** 完成＝手上有一個能播的檔案，不是畫面上看起來好了。
#
# 在那之前的每一個訊號都只是「可以去按下載了」的**觸發條件**，不是完成宣告：
#
#   觸發條件 = 相對於 submit 當下的媒體快照（`.flow/jobs/<id>.json` 的 before），
#              出現**恰好一個**新的 <video>，且 readyState >= 2、duration 有限且 > 0，
#              且**連續兩次輪詢（間隔 6 秒）同一個 key**都滿足。
#
# `cli.js wait` 自己就寫了 `verifiedComplete: false`，它只報「新的媒體候選」。
# 這支不把那個當完成，只把它當「去按下載」的許可。
#
# ── 這個判準什麼時候會錯 ───────────────────────────────────────────────
# 1. **同一個專案有別的生成同時在跑**（人在旁邊操作，或另一個 agent）。
#    新影片可能不是我們的。⇒ 只要同時出現 >1 個新候選就停下回報
#    AMBIGUOUS_CANDIDATES（exit 7），不猜。**單一候選但其實是別人的**這種
#    情況本判準擋不住——時間窗重疊時沒有可觀測的歸屬資訊。要靠「一次只跑一個」
#    的作業紀律（CLI 的 `.flow/submit.lock` 只擋同時點擊，不擋這個）。
# 2. **一次生多支**：Flow「代理設定 → 影片生成預設設定」有 x1/x2/x3/x4。
#    設成 x2 以上時正常結果就是多個候選 ⇒ 會被判成 AMBIGUOUS。
#    這台目前是 **x1**（2026-09-19 讀到的值）。改過就要改這裡的判準。
# 3. **Flow 先放預覽再換最終檔**：連續兩次同 key 的穩定性檢查可能仍然太早。
#    最後一道防線是 ffprobe，且我們下載的是選單裡的「原始大小」檔，
#    不是畫面上那個串流 URL。
# 4. **生成失敗但 UI 留下一個錯誤圖塊**：錯誤圖塊不是 <video>，不會被當候選，
#    於是走到逾時分支 ⇒ 會被報成「沒量到」而不是「失敗」。這是刻意的
#    （鐵律 3：沒量到 ≠ 量到 0），但代表**真失敗也會長得像逾時**，
#    要看 `status_after.json` 的頁面文字才分得出來。
# 5. **逾時 ≠ 生成失敗**（exit 3）。job 紀錄留著，`--resume` 可以續等／續下載，
#    **不會重送、不會再花一次額度**。
# 6. **我們只看得到 DOM 裡真的畫出來的東西**。實測 2026-09-19：Flow 的對話
#    回「我已經為你生成了**兩張**…」，但頁面上只渲染出一張（媒體格可能虛擬化／
#    捲動外不掛載）。⇒ `--max-candidates` 擋得住「看到太多」，擋不住「看得太少」：
#    少拿到的那一份不會報錯，會安靜地沒下載。要確定拿全，去 Flow 的媒體格自己看。
# 7. **UI 改版**：hover 工具列、選單項目、畫質字串任何一個變了，會在
#    UI_DRIFT_* 明確失敗（exit 4）並把當下看到的項目清單落盤，不會安靜跑錯。
#
set -uo pipefail

# ── ffmpeg 修法（不必重裝）：需要的 lib 在 x265 4.1 底下，
#    符號連結指向只有 .216 的 4.2，所以直接把 4.1 的目錄塞進搜尋路徑。
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/usr/local/Cellar/x265/4.1/lib:/usr/local/lib:/usr/lib}"

FLOW_HOME="${FLOW_HOME:-$HOME/Desktop/flow}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI="$HERE/flow_ui.mjs"
CLI="$FLOW_HOME/src/cli.js"

PROMPT_FILE=""; PROMPT_TEXT=""; ID=""; OUT=""; TIMEOUT=900
QUALITY="原始大小"; RESUME=0; ALLOW_UPSCALE=""; STRICT_PROMPT=0; LOG_DIR=""; NO_SUBMIT=0
KIND="any"; REF=""; MAXC=1; ACCEPT_RIGHTS=""; PAUSE_RIGHTS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt-file) PROMPT_FILE="$2"; shift 2;;
    --prompt) PROMPT_TEXT="$2"; shift 2;;
    --id) ID="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --quality) QUALITY="$2"; shift 2;;
    --kind) KIND="$2"; shift 2;;      # video|image|any（預設 any）
    --ref) REF="$2"; shift 2;;        # 參考圖（圖生圖／i2v）；掛進提示詞後才送出
    --max-candidates) MAXC="$2"; shift 2;;   # 一次准收幾份（圖像預設設定是 x2）
    --accept-upload-rights) ACCEPT_RIGHTS="--accept-upload-rights"; shift;;  # 人已授權才給
    --pause-at-rights) PAUSE_RIGHTS="--pause-at-rights"; shift;;  # 對話框留著等人自己按（15 分鐘）
    --log-dir) LOG_DIR="$2"; shift 2;;
    --resume) RESUME=1; shift;;
    --strict-prompt) STRICT_PROMPT=1; shift;;
    --no-submit) NO_SUBMIT=1; shift;;   # 只跑前置＋prepare 就停，**不花額度**（拿來驗管線前半段）
    --allow-upscale) ALLOW_UPSCALE="--allow-upscale"; shift;;
    -h|--help) sed -n '2,60p' "${BASH_SOURCE[0]}"; exit 0;;
    *) echo "未知參數：$1" >&2; exit 64;;
  esac
done
[ -n "$ID" ]  || { echo "--id 必填" >&2; exit 64; }
[ -n "$OUT" ] || { echo "--out 必填" >&2; exit 64; }
case "$ID" in (*[!a-zA-Z0-9_-]*) echo "--id 只能是 [A-Za-z0-9_-]（CLI 的 jobPath 規則）" >&2; exit 64;; esac
OUT="$(cd "$(dirname "$OUT")" 2>/dev/null && pwd)/$(basename "$OUT")" || { echo "--out 的目錄不存在" >&2; exit 64; }

# 逐步落盤：日誌放在 FLOW_HOME/.flow 底下（那個目錄本來就 gitignore，
# 而日誌會含提示詞與媒體 URL，不該進版控）。
LOG_DIR="${LOG_DIR:-$FLOW_HOME/.flow/runs/$ID}"
mkdir -p "$LOG_DIR"
STARTED_EPOCH=$(date +%s)
: > "$LOG_DIR/trace.log"

say()  { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG_DIR/trace.log" >&2; }
fail() { local code="$1"; shift; say "✗ $*"; printf '{"ok":false,"exit":%s,"id":"%s","reason":%s,"log_dir":"%s"}\n' \
         "$code" "$ID" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$*")" "$LOG_DIR"; exit "$code"; }
# 跑一個步驟：stdout 存檔、回傳其 exit code。stderr 也收進同一個檔尾。
step() { local name="$1"; shift; say "→ $name: $*"; "$@" >"$LOG_DIR/$name.json" 2>>"$LOG_DIR/trace.log"; local rc=$?;
         say "   $name rc=$rc $(head -c 200 "$LOG_DIR/$name.json" | tr '\n' ' ')"; return $rc; }
jget() { python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));
k=sys.argv[2]
for p in k.split("."):
    d = d[int(p)] if p.isdigit() else d.get(p)
    if d is None: break
print("" if d is None else d)' "$1" "$2" 2>/dev/null; }

# ───────────────────────────── 0. 環境 ────────────────────────────────
{ printf '{"at":"%s","id":"%s","flow_home":"%s","node":"%s","ffprobe":"%s","out":"%s","timeout":%s,"quality":"%s","resume":%s}\n' \
    "$(date -u +%FT%TZ)" "$ID" "$FLOW_HOME" "$(node --version)" \
    "$(ffprobe -version 2>/dev/null | head -1)" "$OUT" "$TIMEOUT" "$QUALITY" "$RESUME"; } > "$LOG_DIR/00_env.json"
[ -f "$CLI" ] || fail 2 "找不到 flow CLI：$CLI（設 FLOW_HOME 指到它的目錄）"
command -v ffprobe >/dev/null || fail 2 "沒有 ffprobe，無法驗證影片"
[ -e "$OUT" ] && fail 2 "輸出檔已存在，不覆蓋：$OUT"

# ───────────────────────────── 1. 前置檢查 ────────────────────────────
# doctor 不 ok 就停。注意：doctor ok **不代表 UI 操作得了**（見 flow_ui.mjs 檔頭），
# 所以 focus 也算前置檢查的一部分。
step 01_doctor node "$CLI" doctor || fail 2 "doctor 失敗——Chrome 9223 沒起來？跑 $FLOW_HOME/scripts/flow-chrome.sh"
[ "$(jget "$LOG_DIR/01_doctor.json" ok)" = "True" ] || fail 2 "doctor 回 ok:false"
[ "$(jget "$LOG_DIR/01_doctor.json" promptFields)" = "1" ] || fail 2 "提示詞欄位不是剛好一個（UI 可能改版）"

step 02_focus node "$UI" focus || fail 2 "無法把專案分頁帶到前景；背景分頁會讓所有 hover/click 永遠 timeout"
# 久開的分頁會出現「無法載入影片／重試」（簽名 URL 過期）。按重試不花額度。
step 03_repair node "$UI" repair || say "   repair 失敗，繼續（非致命）"
step 04_status_before node "$CLI" status || fail 2 "讀不到頁面狀態"

# ───────────────────────────── 2. 填提示 → 送出 ──────────────────────
if [ "$RESUME" = "1" ]; then
  say "→ --resume：跳過 prepare/submit，直接續等 id=$ID"
  step 06_submit node "$CLI" job --id "$ID" || fail 8 "--resume 但找不到 job 紀錄：$ID"
else
  [ -f "$FLOW_HOME/.flow/jobs/$ID.json" ] && fail 8 "job id 已存在（$ID）。CLI 永不重送同一個 id。要續跑請加 --resume，要新跑請換 id。"
  if [ -n "$PROMPT_TEXT" ]; then printf '%s' "$PROMPT_TEXT" > "$LOG_DIR/prompt.raw"
  elif [ -n "$PROMPT_FILE" ]; then cp "$PROMPT_FILE" "$LOG_DIR/prompt.raw"
  else fail 64 "--prompt-file 或 --prompt 要給一個"; fi
  if [ -n "$REF" ]; then
    [ -f "$REF" ] || fail 64 "--ref 檔案不存在：$REF"
    step 04b_attach node "$UI" attach --ref "$REF" $ACCEPT_RIGHTS $PAUSE_RIGHTS \
      || fail 4 "參考圖掛不上去：$(jget "$LOG_DIR/04b_attach.json" error)（看 04b_attach.json）"
  fi
  # 提示詞正規化。實測（2026-09-19）：提示詞欄位是 ProseMirror contenteditable，
  # CLI 的 prepare 會用 innerText 回讀比對，**只要有換行（含結尾那個 \n）就
  # FILL_VERIFICATION_FAILED**。所以在這裡攤平成一行，並把原文與 sha256 一起落盤。
  python3 - "$LOG_DIR" "$STRICT_PROMPT" <<'PY' || fail 64 "提示詞含換行，且 --strict-prompt 不准攤平"
import hashlib, pathlib, re, sys
d = pathlib.Path(sys.argv[1]); strict = sys.argv[2] == "1"
raw = d.joinpath("prompt.raw").read_text(encoding="utf-8")
one = re.sub(r"\s*\n+\s*", " ", raw).strip()
if one != raw.strip() and strict: sys.exit(1)
d.joinpath("prompt.one").write_text(one, encoding="utf-8")   # 無結尾換行
d.joinpath("05_prompt.json").write_text(__import__("json").dumps(
    {"ok": True, "normalized": one != raw, "chars": len(one),
     "sha256_raw": hashlib.sha256(raw.encode()).hexdigest(),
     "sha256_one": hashlib.sha256(one.encode()).hexdigest(), "text": one},
    ensure_ascii=False, indent=2), encoding="utf-8")
PY
  [ "$(jget "$LOG_DIR/05_prompt.json" normalized)" = "True" ] && say "   ⚠ 提示詞有換行，已攤平成一行（原文與 sha256 在 05_prompt.json）"
  step 05_prepare node "$CLI" prepare --prompt-file "$LOG_DIR/prompt.one" || fail 2 "prepare 失敗（FILL_VERIFICATION_FAILED 通常＝提示詞有怪字元）"
  if [ "$NO_SUBMIT" = "1" ]; then
    say "✓ --no-submit：前置與 prepare 都過了，停在送出之前（沒花額度）"
    printf '{"ok":true,"stopped_before":"submit","id":"%s","log_dir":"%s"}\n' "$ID" "$LOG_DIR"; exit 0
  fi
  # ← 這一步開始花額度。CLI 在點擊**之前**就把 job 寫死，任何不確定都不會自動重試。
  step 06_submit node "$CLI" submit --id "$ID" --execute || fail 8 "submit 失敗（按鈕 disabled？提示詞空的？.flow/submit.lock 殘留？——不要盲目刪 lock）"
fi
# 牆鐘的起點是**真正按下送出的那一刻**：--resume 時從 job 紀錄裡把它讀回來，
# 不然續跑會報出一個假的「很快」。
SUBMIT_AT=$(python3 -c '
import datetime, json, sys, time
try:
    at = json.load(open(sys.argv[1]))["at"]
    print(int(datetime.datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()))
except Exception:
    print(int(time.time()))' "$LOG_DIR/06_submit.json")
# 送出後立刻拍一張頁面文字：如果 Flow 跳了額度確認對話框（README 明說程式不自動接受），
# 這裡就看得到，不必等到逾時才知道卡在哪。
step 06b_status_after_submit node "$CLI" status || true
[ "$(jget "$LOG_DIR/06_submit.json" status)" = "submitted" ] || fail 8 "submit 紀錄不是 submitted（$(jget "$LOG_DIR/06_submit.json" status)）——submission_unknown 表示點擊後斷線，人工確認後再決定，不要重送"

# ───────────────────────────── 3. 等生成 ─────────────────────────────
step 07_await node "$UI" await-media --id "$ID" --timeout "$TIMEOUT" --interval 6 --stable-polls 2 \
     --kind "$KIND" --max-candidates "$MAXC" --trace "$LOG_DIR/07_await_trace.jsonl"
AWAIT_RC=$?
if [ $AWAIT_RC -ne 0 ]; then
  ERR="$(jget "$LOG_DIR/07_await.json" error)"
  step 08_status_after node "$CLI" status || true
  case "$ERR" in
    AMBIGUOUS_CANDIDATES) fail 7 "新素材多於 --max-candidates=$MAXC，不猜是哪一份（看 07_await.json）";;
    TIMEOUT_UNVERIFIED)   fail 3 "${TIMEOUT}s 內沒量到穩定的新素材。**沒量到 ≠ 生成失敗**（鐵律 3）：額度已經花了，job=$ID 還在，用 --resume 續等／續下載，不要重送。真失敗會在 08_status_after.json 的頁面文字看到錯誤字樣。";;
    *)                    fail 3 "等待階段失敗：$ERR";;
  esac
fi
NCAND="$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(len(d.get("candidates") or [d["candidate"]]))' "$LOG_DIR/07_await.json")"
[ -n "$NCAND" ] && [ "$NCAND" -ge 1 ] || fail 3 "await 回 ok 但沒有候選（不該發生）"
# 交叉對照：用 CLI 自己的 wait 再確認一次同一件事（它只報候選、不報完成）
step 08_cli_wait node "$CLI" wait --id "$ID" --timeout 5 || say "   cli wait 交叉對照失敗，不致命"

# ─────────────────────── 4+5. 逐份下載並驗證 ─────────────────────────
# 一次可能拿回多份（圖像預設 x2）。每一份都各自下載、各自驗，
# **任何一份驗不過就整批失敗**——不做「至少一份好就算過」那種寬鬆判準。
OUT_STEM="${OUT%.*}"; OUT_EXT="${OUT##*.}"
FILES=""
for i in $(seq 1 "$NCAND"); do
  KEY="$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1])); c=d.get("candidates") or [d["candidate"]]
print(c[int(sys.argv[2])-1]["key"])' "$LOG_DIR/07_await.json" "$i")"
  if [ "$NCAND" = "1" ]; then F="$OUT"; else F="${OUT_STEM}_${i}.${OUT_EXT}"; fi
  [ -e "$F" ] && fail 2 "輸出檔已存在，不覆蓋：$F"
  step "09_download_$i" node "$UI" download --key "$KEY" --out "$F" --quality "$QUALITY" $ALLOW_UPSCALE \
    || { step "09b_status_$i" node "$CLI" status || true; fail 5 "下載第 $i 份失敗：$(jget "$LOG_DIR/09_download_$i.json" error) $(jget "$LOG_DIR/09_download_$i.json" detail)"; }
  [ -s "$F" ] || fail 5 "下載回報成功但檔案不存在／為空：$F"

  # ── 驗證（唯一的完成宣告）
  ffprobe -v error -print_format json -show_format -show_streams "$F" > "$LOG_DIR/10_ffprobe_$i.json" 2>>"$LOG_DIR/trace.log" \
    || fail 6 "ffprobe 讀不動第 $i 份——下載到的不是有效媒體"
  # 模態由**檔案本身**決定，不是由旗標決定：Flow 自己判要生圖還是生片
  # （實測 2026-09-19：「一顆石頭放在木桌上…」它回了 1376×768 的圖，不是影片）。
  DETECTED="$(python3 "$HERE/verify_media.py" "$LOG_DIR/10_ffprobe_$i.json")" \
    || fail 6 "第 $i 份 ffprobe 通過但內容不合格：$DETECTED"
  FRAME="$LOG_DIR/10_frame_$i.png"
  # 最後一關：真的把像素解出來。容器讀得動 ≠ 影像解得開。
  # ⚠ 圖片**不能給 -ss**：jpeg_pipe/image2 只有一格，`-ss 0` 會把它跳掉，
  #   而且 ffmpeg **回 exit 0 卻什麼都沒寫**（2026-09-19 實測）⇒ 只看 exit code
  #   會拿到一個假成功。所以下面永遠再檢查一次檔案真的有內容。
  if [ "$DETECTED" = "video" ]; then
    SEEK="$(python3 -c 'import json,sys;print(max(0.1,float(json.load(open(sys.argv[1]))["format"]["duration"])/2))' "$LOG_DIR/10_ffprobe_$i.json")"
    ffmpeg -v error -ss "$SEEK" -i "$F" -frames:v 1 -y "$FRAME" 2>>"$LOG_DIR/trace.log" \
      || fail 6 "第 $i 份抽不出畫格——容器能讀但影像解不開"
  else
    ffmpeg -v error -i "$F" -frames:v 1 -y "$FRAME" 2>>"$LOG_DIR/trace.log" \
      || fail 6 "第 $i 份解不開"
  fi
  [ -s "$FRAME" ] || fail 6 "第 $i 份抽出的畫格是空檔（ffmpeg 回 0 但沒寫出東西）"
  FILES="$FILES$F"$'\n'
done

# ───────────────────────────── 6. 收尾 ───────────────────────────────
node "$UI" close-menus > "$LOG_DIR/11_cleanup.json" 2>>"$LOG_DIR/trace.log" || true
NOW=$(date +%s)
python3 - "$LOG_DIR" "$ID" "$((NOW-SUBMIT_AT))" "$((NOW-STARTED_EPOCH))" "$NCAND" <<'PY' | tee "$LOG_DIR/12_result.json"
import glob, json, os, sys
log, jid, wall_submit, wall_total, ncand = sys.argv[1:6]
items = []
for i in range(1, int(ncand) + 1):
    pr = json.load(open(f"{log}/10_ffprobe_{i}.json"))
    vs = next(s for s in pr["streams"] if s["codec_type"] == "video")
    dl = json.load(open(f"{log}/09_download_{i}.json"))
    kind = "video" if (pr["format"].get("format_name", "").find("_pipe") < 0
                       and "image2" not in pr["format"].get("format_name", "")
                       and float(pr["format"].get("duration") or 0) > 0.5) else "image"
    items.append({
        "file": dl["file"], "bytes": os.path.getsize(dl["file"]), "kind": kind,
        "width": vs["width"], "height": vs["height"], "codec": vs.get("codec_name"),
        "duration_s": (float(pr["format"]["duration"]) if kind == "video" else None),
        "suggested_filename": dl.get("suggestedFilename"),
        "frame_png": f"{log}/10_frame_{i}.png",
    })
print(json.dumps({
    "ok": True, "id": jid, "count": len(items), "assets": items,
    "wall_submit_to_file_s": int(wall_submit), "wall_total_s": int(wall_total),
    "log_dir": log,
    "verified_by": "ffprobe(format+streams) + ffmpeg 真的解出一格像素（每一份都驗）",
}, ensure_ascii=False, indent=2))
PY
say "✓ 完成（$NCAND 份）：$(printf '%s' "$FILES" | tr '\n' ' ')"
