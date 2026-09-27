#!/usr/bin/env bash
# 本機備份（Mac，常駐迴圈）：照 VM 上的 MANIFEST.tsv 把還沒拉的 chunk 拉回來、逐個驗 sha256。
# 用法：sync_from_colab.sh <colab session 名> <本機目錄> [間隔秒數，預設 600]
# - 只拉 chunk 與 MANIFEST，不解壓、不讀內容（批次跑完之前不看分數）。
# - sha256 對不上就刪掉重拉（下一輪）；對上了寫進本機的 VERIFIED.tsv。
# - Mac 睡著時這支停住，VM 照跑；醒來後從缺的那個 chunk 接著拉。VM 那邊的第二份在 Google Drive（packer --mirror）。
set -u
S=$1; D=$2; INT=${3:-600}
COLAB=${COLAB:-$HOME/.local/bin/colab}
mkdir -p "$D"
PY=$(mktemp -t syncpy); trap 'rm -f "$PY"' EXIT
printf '%s\n' 'import pathlib' 'p = pathlib.Path("/srv/eval/archive/MANIFEST.tsv")' 'print("MANIFEST_BEGIN"); print(p.read_text() if p.exists() else "", end=""); print("MANIFEST_END")' \
  'print("DONE_FLAG", pathlib.Path("/srv/eval/DRIVER_DONE").exists(), pathlib.Path("/srv/eval/archive").joinpath("PACKER_DONE").exists())' > "$PY"
while true; do
  out=$("$COLAB" exec -s "$S" --timeout 120 -f "$PY" 2>&1)
  if ! grep -q MANIFEST_END <<<"$out"; then
    echo "$(date -u +%FT%TZ) 連不上 $S（VM 可能已停）：$(tail -1 <<<"$out")"; sleep "$INT"; continue
  fi
  sed -n '/MANIFEST_BEGIN/,/MANIFEST_END/p' <<<"$out" | sed '1d;$d' > "$D/MANIFEST.remote.tsv"
  new=0
  while IFS=$'\t' read -r name digest bytes ncells stamp; do
    [ -n "$name" ] || continue
    grep -q "^$name	$digest" "$D/VERIFIED.tsv" 2>/dev/null && continue
    "$COLAB" download -s "$S" "/srv/eval/archive/$name" "$D/$name" </dev/null >/dev/null 2>&1
    got=$(shasum -a 256 "$D/$name" 2>/dev/null | cut -d' ' -f1)
    if [ "$got" = "$digest" ]; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$digest" "$bytes" "$ncells" "$stamp" "$(date -u +%FT%TZ)" >> "$D/VERIFIED.tsv"
      new=$((new+1))
    else
      echo "$(date -u +%FT%TZ) $name sha256 不符（$got），刪掉下一輪重拉"; rm -f "$D/$name"
    fi
  done < "$D/MANIFEST.remote.tsv"
  echo "$(date -u +%FT%TZ) 本輪新拉 $new 個；本機已驗證 $(wc -l < "$D/VERIFIED.tsv" 2>/dev/null || echo 0) / 遠端 $(grep -c . "$D/MANIFEST.remote.tsv")"
  if grep -q "DONE_FLAG True True" <<<"$out" && [ "$(wc -l < "$D/VERIFIED.tsv" 2>/dev/null || echo 0)" -ge "$(grep -c . "$D/MANIFEST.remote.tsv")" ]; then
    echo "$(date -u +%FT%TZ) SYNC_ALL_DONE"; exit 0
  fi
  sleep "$INT"
done
