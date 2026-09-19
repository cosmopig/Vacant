#!/usr/bin/env bash
# 正向控制：接線正確（CUSTOM_BASE_URL 由 launcher 指到 proxy）。
# 封鎖之後這一格**必須照樣會動**——擋住了但把正常路也擋死，那叫壞掉不叫封鎖。
set -uo pipefail
ENVF="$1"; shift
set -a; source "$ENVF" >/dev/null 2>&1 || true; set +a
umask 0000
export HOME=/var/tmp/v3egress/home
export PATH=/var/tmp/v3egress/hv/bin:/usr/bin:/bin
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
