#!/usr/bin/env bash
# 本機備份（Mac／Linux，常駐迴圈）：照 VM 上的 MANIFEST.tsv 把還沒拉的 chunk 用 `colab download` 拉回來、逐個驗 sha256。
# 用法：sync_i1001.sh <colab session 名> <本機目錄> [間隔秒數，預設 600] [--once]
# - 只拉 chunk 與旗標，不解壓、不讀內容（批次跑完之前不看分數）。全部走 `colab download`（Jupyter 的檔案介面），不走 `colab exec`
#   （2026-09-27 實測 kernel 的 exec 會隨機卡住好幾分鐘）。
# - sha256 對不上就刪掉下一輪重拉；對上的記進 <本機目錄>/VERIFIED.tsv（autostop_i1001.sh 讀這份）。
# - 旗標（有就拉回、沒有就刪掉本機舊的）：DRIVER_DONE、PACKER_DONE、ALL_DONE、MIRROR_OK、MIRROR_BAD。
# - PACKER_DONE 在、而且最終的 MANIFEST 每一個 chunk 都驗過 ⇒ 印 SYNC_ALL_DONE 並結束。
# - Mac 睡著時這支停住，VM 照跑（packer 另外鏡像到 Drive）；醒來後從缺的那個 chunk 接著拉。
# - `COLAB` 環境變數可指定 colab CLI（預設 PATH 上的 `colab`；測試用假的）。
set -u
S=$1; D=$2; INT=${3:-600}; ONCE=${4:-}
COLAB=${COLAB:-colab}
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
mkdir -p "$D"
flag() {  # flag <遠端路徑> <本機名>：有就拉回、沒有就刪本機舊的；回傳 0＝遠端有
  if "$COLAB" download -s "$S" "$1" "$D/$2.tmp" </dev/null >/dev/null 2>&1 && [ -f "$D/$2.tmp" ]; then mv "$D/$2.tmp" "$D/$2"; return 0; fi
  rm -f "$D/$2.tmp" "$D/$2"; return 1
}
while true; do
  if ! "$COLAB" download -s "$S" /srv/eval/archive/MANIFEST.tsv "$D/MANIFEST.remote.tsv" </dev/null >/dev/null 2>&1; then
    echo "$(date -u +%FT%TZ) 拉不到 MANIFEST（VM 可能已停，或還沒有第一個 chunk）"
    [ "$ONCE" = --once ] && exit 3
    sleep "$INT"; continue
  fi
  new=0
  while IFS=$'\t' read -r name digest bytes ncells stamp; do
    [ -n "$name" ] || continue
    grep -q "^$name	$digest" "$D/VERIFIED.tsv" 2>/dev/null && continue
    "$COLAB" download -s "$S" "/srv/eval/archive/$name" "$D/$name" </dev/null >/dev/null 2>&1
    got=$(sha "$D/$name" 2>/dev/null)
    if [ "$got" = "$digest" ]; then
      printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$digest" "$bytes" "$ncells" "$stamp" "$(date -u +%FT%TZ)" >> "$D/VERIFIED.tsv"
      new=$((new+1))
    else
      echo "$(date -u +%FT%TZ) $name sha256 不符（${got:-沒拉到}），刪掉下一輪重拉"; rm -f "$D/$name"
    fi
  done < "$D/MANIFEST.remote.tsv"
  nv=$(grep -c . "$D/VERIFIED.tsv" 2>/dev/null || echo 0); nr=$(grep -c . "$D/MANIFEST.remote.tsv")
  flag /srv/eval/DRIVER_DONE DRIVER_DONE; flag /srv/eval/ALL_DONE ALL_DONE
  flag /srv/eval/archive/MIRROR_OK MIRROR_OK; flag /srv/eval/archive/MIRROR_BAD MIRROR_BAD
  echo "$(date -u +%FT%TZ) 本輪新拉 $new 個；本機已驗證 $nv / 遠端 $nr"
  if flag /srv/eval/archive/PACKER_DONE PACKER_DONE && [ "$nv" -ge "$nr" ]; then
    echo "$(date -u +%FT%TZ) SYNC_ALL_DONE"; exit 0
  fi
  [ "$ONCE" = --once ] && exit 4
  sleep "$INT"
done
