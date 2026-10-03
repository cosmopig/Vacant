#!/usr/bin/env bash
# 打包要上傳到 VM 的 bundle（本機）。用法：build_bundle.sh <staged 目錄> <wheel 檔> <輸出 .tgz>
#   staged 目錄：含 tasks_index.json、MANIFEST.json、<題庫>/<題>/…（題目內容不進 repo，放在 scratchpad）
#   wheel：從 /home/user/Vacant HEAD 建的 vacant_network-*.whl（C 組與 bridge 的 venv 都裝它）
# 內容：bin/（vm/*.py *.sh ＋ stub_model.py ＋ scorers/）、bridge/ops/eval/native_acceptance_bridge.py、wheel/、staged/、SHA256SUMS。
# 上傳：colab upload -s <session> <輸出 .tgz> /content/deploy_i1001.tgz；然後在 VM 上
#   mkdir -p /root/deploy && tar -xzf /content/deploy_i1001.tgz -C /root/deploy && bash /root/deploy/bin/deploy_i1001.sh
set -euo pipefail
STAGED=$1; WHEEL=$2; OUT=$3
HERE=$(cd "$(dirname "$0")" && pwd)
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
python3 "$HERE/build_manifest.py" --check
[ -f "$STAGED/tasks_index.json" ] && [ -f "$STAGED/MANIFEST.json" ] || { echo "staged 目錄沒有 tasks_index.json／MANIFEST.json" >&2; exit 2; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin/scorers" "$T/bridge/ops/eval" "$T/wheel" "$T/staged"
cp "$HERE"/vm/*.py "$HERE"/vm/*.sh "$T/bin/"
cp "$HERE/stub_model.py" "$T/bin/"
cp "$HERE"/scorers/*.py "$T/bin/scorers/"
cp "$HERE/bridge/native_acceptance_bridge.py" "$T/bridge/ops/eval/"
cp "$WHEEL" "$T/wheel/"
( cd "$T/wheel" && sha "$(basename "$WHEEL")" > wheel.sha256 )
cp -a "$STAGED/." "$T/staged/"
( cd "$T" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS ) 2>/dev/null \
  || ( cd "$T" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
FLAGS=""; if tar --version 2>&1 | grep -qi bsdtar; then FLAGS="--no-mac-metadata --no-xattrs"; fi
COPYFILE_DISABLE=1 tar $FLAGS -czf "$OUT" -C "$T" .
echo "wrote $OUT ($(wc -c < "$OUT") bytes); sha256 $(sha "$OUT" | cut -d' ' -f1)"
