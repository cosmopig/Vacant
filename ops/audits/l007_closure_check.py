#!/bin/bash

# Verification script for L007 closure and backlog reconciliation.
# Requirements:
# 1. ops/loop/L007.md contains "CLOSED: NO_MECHANISM"
# 2. BACKLOG.md has "[x] L007 資料損失"
# 3. Exit with code 0 if all pass, else exit 1.

set -e

# Check L007.md
if ! grep -q "CLOSED: NO_MECHANISM" ops/loop/L007.md; then
    echo "FAIL: 'CLOSED: NO_MECHANISM' not found in ops/loop/L007.md"
    exit 1
fi

# Check BACKLOG.md
if ! grep -q "\[x\] L007 資料損失" BACKLOG.md; then
    echo "FAIL: '[x] L007 資料損失' not found in BACKLOG.md"
    exit 1
fi

echo "VERDICT: L007_CLOSURE_OK"
exit 0
