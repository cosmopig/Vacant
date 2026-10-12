#!/usr/bin/env bash
# 用 console（不走 kernel）在 VM 上跑一支本機 python 檔，輸出拉回來印出。用法：vmrun.sh <session> <local.py> [等待秒數]
S=$1; F=$2; W=${3:-90}; n=$(basename "$F" .py)_$$
~/.local/bin/colab upload -s "$S" "$F" "/content/$n.py" >/dev/null 2>&1 || { echo UPLOAD_FAIL; exit 1; }
(printf 'timeout %s python3 /content/%s.py > /content/%s.out 2>&1; echo "__rc=$?" >> /content/%s.out\nexit\n' "$W" "$n" "$n" "$n" | ~/.local/bin/colab console -s "$S" >/dev/null 2>&1 & p=$!; for i in $(seq 1 $((W+30))); do kill -0 $p 2>/dev/null || break; sleep 1; done; kill $p 2>/dev/null)
~/.local/bin/colab download -s "$S" "/content/$n.out" "/tmp/$n.out" >/dev/null 2>&1 && cat "/tmp/$n.out" || echo DOWNLOAD_FAIL
