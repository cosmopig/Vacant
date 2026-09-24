#!/bin/sh
# 重新取得本目錄的公開資料集（2026-09-24 取得；sha256 見 SHA256SUMS，對不上就不是同一份）。
# IFEval（Apache-2.0）入庫；RAGTruth 全檔 36MB 不入庫（.gitignore），實驗用到的樣本另存於 ../samples/。
set -e
cd "$(dirname "$0")"
B=https://raw.githubusercontent.com/google-research/google-research/master/instruction_following_eval
curl -sSf $B/data/input_data.jsonl -o input_data.jsonl
curl -sSf $B/data/input_response_data_gpt4_20231107_145030.jsonl -o input_response_data_gpt4_20231107_145030.jsonl
mkdir -p ifeval_lib ragtruth
for f in instructions.py instructions_registry.py instructions_util.py evaluation_lib.py; do curl -sSf $B/$f -o ifeval_lib/$f; done
for f in response.jsonl source_info.jsonl; do curl -sSf https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/$f -o ragtruth/$f; done
sha256sum -c SHA256SUMS
