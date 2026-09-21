#!/bin/bash
# seq.sh <outdir> name:query ...   —— 依序截圖（平行超過 2 個 Chrome 會卡住）
SC=/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad
out="$1"; shift
DWELL="${DWELL:-12000}"
p=9540
mkdir -p "$out"
for spec in "$@"; do
  name="${spec%%:*}"; q="${spec#*:}"
  rm -rf "/tmp/vacant-twinshot-cdp-$p"
  "$SC/shot2.sh" "$out" "$name" "$q" "$DWELL" "$p" > "$out/$name.json" 2>&1
  python3 - "$out/$name.json" "$name" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print(sys.argv[2], "PARSE_FAIL", e); raise SystemExit
print(sys.argv[2], "ok=", d.get("ok"), "|", d.get("title"), "|", (d.get("why") or "")[:100])
for c in (d.get("console") or [])[-3:]: print("   ", c[:150])
PY
  p=$((p+1))
done
