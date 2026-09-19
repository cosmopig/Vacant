#!/usr/bin/env bash
# V/GT 分離的可執行證據：掃 20 格的 **wire 原始位元組**（送出去與收回來的 body）
# 與最終工作區，看隱藏測資或工作區外的路徑有沒有漏進去。
# 命中不是 0 ⇒ 這一批作廢（隱藏測資進了模型的輸入）。
cd /var/tmp/vacant_pbgate || exit 2
echo "# V/GT 分離掃描  $(date -u +%FT%TZ)"
echo "# 掃三個字串：test_hidden / \"/hidden/\" / r534/templates"
echo "# 範圍：每格的 wire_RUN-ON/*.req.bin ＋ *.resp.bin ＋ index.jsonl ＋ 最終工作區全部檔案"
echo
total=0
for rd in rd_*; do
  n="${rd#rd_}"
  w="ws_$n"
  hw=$(grep -rl "test_hidden\|/hidden/\|r534/templates" "$rd/wire_RUN-ON" 2>/dev/null | wc -l)
  hs=$(grep -rl "test_hidden\|/hidden/\|r534/templates" "$w" 2>/dev/null | wc -l)
  hf=$(find "$w" -name "test_hidden*" 2>/dev/null | wc -l)
  total=$((total+hw+hs+hf))
  printf "%-18s wire_hits=%s workspace_hits=%s hidden_files_in_ws=%s\n" "$n" "$hw" "$hs" "$hf"
done
echo
echo "TOTAL_HITS=$total"
[ "$total" -eq 0 ] && echo "verdict = OK（隱藏測資沒有出現在工作區、回饋或 wire 上）" \
                   || echo "verdict = FAIL（這一批作廢）"
