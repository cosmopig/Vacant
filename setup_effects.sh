#!/bin/bash
set -e

# 建立工作目錄
mkdir -p /home/user1/dev/ops/effects2cap_20261106
cd /home/user1/dev/ops/effects2cap_20261106

# 確認 code 目錄存在（應該已經有了）
if [ ! -d "code" ]; then
  echo "Error: 'code' directory not found."
  exit 1
fi

# 建立必要的檔案
touch before_after.json
touch dry_run.txt
touch progress.json
touch provenance.json
touch reviewer_question.json
touch summary.json

# 確認 run_cells.py 存在
if [ ! -f "run_cells.py" ]; then
  echo "Error: 'run_cells.py' not found."
  exit 1
fi

echo "Setup complete."
