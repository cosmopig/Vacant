#!/bin/bash
# 把這一批的證據搬進 Vacant repo 的證據目錄（**這一支只複製，不量測**）。
#
# 搬的是：對照表（人看）＋每一臂的連續截圖與 strip.json（機器看）＋量具本身
# （strip.py／probe.py／blockwatchdog.js／sheet.py／motion.py／summarize.py，
# 讓外人重跑得起來）。
#
# ⚠ 影片（.webm，每支 13 MB）**不進 repo**，留在 scratchpad。對照表已經把
#   同樣的資訊壓成一張圖，而 repo 不該為了方便多背 60 MB。
set -eu
SRC="$(cd "$(dirname "$0")" && pwd)/out"
DST="/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/wf_32a45899-6ee-1/ops/exhibit/twin/evidence_visible_20260921/arrival_beat/v2_clockstep"
HM="$HOME/Documents/GitHub/vacant_hm/world3/index.html"

mkdir -p "$DST/tools"
for a in S01_before_single S02_after_single S03_negctl_arrive0 \
         S04_after_triple S05_before_triple S06_before_busy S07_after_busy v1_smallcard/S02_after_single; do
  if [ -d "$SRC/$a" ]; then
    mkdir -p "$DST/$a"
    cp "$SRC/$a"/*.jpg "$DST/$a/" 2>/dev/null || echo "  ⚠ $a 沒有 jpg"
    cp "$SRC/$a"/strip.json "$DST/$a/" 2>/dev/null || echo "  ⚠ $a 沒有 strip.json（那一臂沒跑完）"
  else
    echo "  ⚠ $a 整個不存在——**不要把它讀成 0，讀成沒跑**"
  fi
done
cp "$SRC"/SHEET_*.jpg "$DST/" 2>/dev/null || echo "  ⚠ 沒有對照表"
for f in SUMMARY.json motion.json manifest.json t_reload.json RUN_FINAL.log RUN_BUSY.log; do
  cp "$SRC/$f" "$DST/" 2>/dev/null || echo "  ⚠ 沒有 $f"
done
for f in strip.py probe.py sheet.py motion.py summarize.py manifest.py \
         blockwatchdog.js t_reload.py serve.py run_final.sh run_busy.sh strip_busy.py smoke.py collect_final.sh; do
  cp "$(dirname "$SRC")/$f" "$DST/tools/" 2>/dev/null || echo "  ⚠ 沒有 tools/$f"
done
cp "$(dirname "$SRC")/wd/wd.html" "$DST/tools/wd_reload_replica.html" 2>/dev/null || true
cp "$(dirname "$SRC")/wd/wdfreeze.html" "$DST/tools/wd_freeze_replica.html" 2>/dev/null || true
shasum -a 256 "$HM" > "$DST/SUBJECT_index.html.sha256"
# 三批量測各自的缺陷寫在這一份，放**證據目錄的根**（不是 v2 底下）——
# 它管的是整個目錄怎麼讀，包含上午那兩批不可引用的部分。
cp "$(dirname "$SRC")/PROVENANCE.json" "$(dirname "$DST")/PROVENANCE.json"
echo "--- 落盤 ---"
du -sh "$DST"
find "$DST" -type f | wc -l
