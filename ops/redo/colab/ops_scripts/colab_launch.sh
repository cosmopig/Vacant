#!/bin/bash
# 用法：[COLAB_BIN=colab2] [GPU_ORDER="A100 L4"] colab_launch.sh <name> <plan_relpath> <bank_dir> [launch_batch 額外參數...]
# 依序試 GPU_ORDER（預設 L4 → G4 → A100）；某種失敗就把開出來的 session 關掉再試下一種；成功就接 keepalive＋自動 fetch/stop。
# COLAB_BIN：用哪個 Colab 帳號的指令（預設 colab；第二個帳號是 colab2），會寫進 state.json，之後的 poll／fetch／keepalive／守門／快照都照它。
NAME=$1; PLAN=$2; BANK=$3; shift 3
CB=${COLAB_BIN:-colab}; CBP=$(command -v "$CB" || echo "$CB")
cd $HOME/dev/wt/nonpy
LOG=$HOME/dev/ops/colab_launch_$NAME.log
echo "$(date -u +%FT%TZ) colab_bin=$CBP gpu_order=${GPU_ORDER:-L4 G4 A100}" >> $LOG
for g in ${GPU_ORDER:-L4 G4 A100}; do
  echo "$(date -u +%FT%TZ) try $g" >> $LOG
  out=$(timeout 3000 bash ops/redo/colab/launch_batch.sh "$PLAN" "$BANK" --gpu $g --colab-bin "$CBP" "$@" 2>&1)
  echo "$out" | tail -40 >> $LOG
  if echo "$out" | grep -q LAUNCH_OK; then
    echo "$(date -u +%FT%TZ) LAUNCH_OK $g" >> $LOG
    # 11/24（W3-5 JS 重跑 VOID 的根因 4）：每個帳號一支預算看門，看這個帳號上所有批次（沒在跑才起）
    BU="redo-budget-$(basename "$CBP")"
    systemctl --user is-active -q "$BU" || systemd-run --user --unit="$BU" -p KillMode=process --setenv=PATH="$PATH" \
      /usr/bin/python3 $HOME/dev/ops/colab_budget_watch.py --colab-bin "$CBP" >> $LOG 2>&1
    st=$(echo "$out" | grep -oE "State file : .*" | awk '{print $4}')
    # 量測專用的短命 session（probe_*）：跑完 1 對後在同一台 VM 量並行數再停機；實驗批次一律走下面那行
    case "$NAME" in probe_e4b*) exec $HOME/dev/ops/colab_keepalive_probe2.sh "$st" gemma-4-e4b-it-qat ;; probe_12b*) exec $HOME/dev/ops/colab_keepalive_probe2.sh "$st" gemma-4-12b-it-qat ;; esac
    exec $HOME/dev/ops/colab_keepalive_fetch3.sh "$st"   # 連續三次確認、照 state.json 的 colab_bin
  fi
  s=$(echo "$out" | grep -oE "new -s [^ ]+" | head -1 | awk '{print $3}')
  [ -n "$s" ] && timeout 120 "$CBP" stop -s "$s" >> $LOG 2>&1
  echo "$(date -u +%FT%TZ) FAIL $g (stopped session ${s:-none})" >> $LOG
done
exit 1
