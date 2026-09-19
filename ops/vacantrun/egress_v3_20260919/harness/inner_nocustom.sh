#!/usr/bin/env bash
# 活體標本（AGENT_COMPAT §12.2 對照 C）：**故意漏設 CUSTOM_BASE_URL**。
# Hermes 0.19.0 解 base_url 的鏈尾是編死的 https://openrouter.ai/api/v1 ⇒
# 沒有封鎖時它會安靜地出網到第三方，而收據上只有 requests_seen 這一欄看得出來。
set -uo pipefail
ENVF="$1"; shift
set -a; source "$ENVF" >/dev/null 2>&1 || true; set +a
umask 0000
export HOME=/var/tmp/v3egress/home
export PATH=/var/tmp/v3egress/hv/bin:/usr/bin:/bin
unset CUSTOM_BASE_URL OPENROUTER_BASE_URL      # ← 刻意漏掉 base url
CFG="$(mktemp -d /var/tmp/v3egress/work/hcfg-XXXXXX)"
export HERMES_HOME="$CFG"
# ⚠ Hermes 以 0600 建檔（不吃 umask）⇒ launcher（另一個 uid）讀不到，
# `_frozen_*` 的 copytree 會 Permission denied 整跑炸掉。這是「agent 降到
# 專屬 uid」這個 V3 前提下 `vacant run` 的**既有缺口**，這裡手工補。
cleanup() { chmod -R a+rwX . 2>/dev/null || true; }
trap cleanup EXIT
hermes -z "$*" --yolo --provider custom -m "${VACANT_AGENT_MODEL}" < /dev/null
rc=$?
cleanup
exit $rc
