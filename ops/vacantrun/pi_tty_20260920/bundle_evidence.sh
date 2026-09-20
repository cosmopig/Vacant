#!/usr/bin/env bash
# 把 vacant-dev 上那一批的**小東西**收成可進版控的證據包。
#
# 收什麼／不收什麼，理由寫在這裡（不是靠記憶）：
#
#   收   `cells/*/run_RUN-ON.json`        閘門的判決原文（單一真相來源）
#   收   `cells/*/wire_RUN-ON/index.jsonl` 中介逐條紀錄（**不含 body**）
#   收   `pty/*.drive.json`                模擬的人做了什麼、什麼時候
#   收   `hooks/*.jsonl`                   掛鉤事件（只有雜湊，沒有原文）
#   收   `argv/*.argv.txt`                 這一格真的下了什麼指令
#   收   `pty/*.plain.txt` 的**前後各 8KB** 給人讀的轉錄（TUI 證據在裡面）
#
#   不收 `wire_RUN-ON/*.req.bin`／`*.resp.bin`  ——每格數 MB，而且含 prompt 全文
#   不收 `ws_*/`                                ——交付物本身，另外計分即可
#   不收 完整 pty 轉錄                          ——一格 700KB＋，而且是 escape 序列
set -u
ROOT=${TTY_ROOT:-/var/tmp/vacant_tty_20260920}
OUT=${1:-$ROOT/evidence}
rm -rf "$OUT"; mkdir -p "$OUT/cells" "$OUT/pty" "$OUT/hooks" "$OUT/argv"
for d in "$ROOT"/cells/*/; do
  n=$(basename "$d")
  mkdir -p "$OUT/cells/$n"
  [ -f "$d/run_RUN-ON.json" ] && cp "$d/run_RUN-ON.json" "$OUT/cells/$n/"
  [ -f "$d/wire_RUN-ON/index.jsonl" ] && cp "$d/wire_RUN-ON/index.jsonl" "$OUT/cells/$n/"
  [ -f "$d/_cell_wall_s.txt" ] && cp "$d/_cell_wall_s.txt" "$OUT/cells/$n/"
  [ -f "$d/_launcher_exit_code.txt" ] && cp "$d/_launcher_exit_code.txt" "$OUT/cells/$n/"
  [ -f "$d/visible_RUN-ON.json" ] && cp "$d/visible_RUN-ON.json" "$OUT/cells/$n/"
done
cp "$ROOT"/pty/*.drive.json "$OUT/pty/" 2>/dev/null || true
cp "$ROOT"/hooks/*.jsonl    "$OUT/hooks/" 2>/dev/null || true
cp "$ROOT"/argv/*.argv.txt  "$OUT/argv/" 2>/dev/null || true
for f in "$ROOT"/pty/*.plain.txt; do
  [ -f "$f" ] || continue
  n=$(basename "$f")
  { echo "=== 前 8KB ==="; head -c 8192 "$f";
    echo; echo "=== 後 8KB ==="; tail -c 8192 "$f"; } > "$OUT/pty/$n.head_tail.txt"
done
cp "$ROOT"/oracle/*.report.json "$OUT/" 2>/dev/null || true
for m in A B C D; do
  [ -f "$ROOT/oracle/$m.pty.plain.txt" ] && head -c 4096 "$ROOT/oracle/$m.pty.plain.txt" > "$OUT/oracle_$m.head.txt"
  [ -f "$ROOT/oracle/$m.err" ] && cp "$ROOT/oracle/$m.err" "$OUT/oracle_$m.err"
done
du -sh "$OUT"
find "$OUT" -type f | wc -l
