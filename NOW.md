# NOW

## 現在在哪（r1148）
- P20261106_2241-2 驗收完成（d33a1ac8，工單已入 done/）：`audit_kv_preservation` 實裝於 reqloop/checks.py——
  鍵值交付物（@key[value] 文字檔或頂層 JSON dict）行級/鍵級保留審計：
  兩側恰好各出現一次且值相等（JSON 另需型別一致）→ preserved；值改動/鍵刪/鍵重複/檔案缺失/草稿無此鍵 → mutated。
  audit 側計算、免模型自評（11-06 指示 4「修復只改未滿足產物並保留其餘成果」的機器可驗判定能力）。
- 驗收：票面指令 RC=0、1 點過（無 -q 口徑「1 passed, 54 deselected」）；5 檔 checks/g2/repair/real_slice/g1_gate 220 passed 無回歸；0 模型呼叫 0 元。

## 對 11-06 指示 2 的意義
- 「正確成果是否退步（right_to_wrong=0）」客觀基線維持三重（A 11/11 PASS 基線、同草稿 pin hash、r1145 單 rep regressed=0），現再加第四重：
  任何 fire 後都可對 answer.txt/result.json 跑 audit_kv_preservation 客觀列出 preserved/mutated，不靠模型自評。

## 下一步（候需求端）
- 授權 fire 4 格（A＋C × generic/localized、同預算 60/4M/300s）→ 一次回答 localized 是否多修好、正確成果是否退步、成本是否值得。
- 或點名 vq-6rp（dabstep-1753 模型側硬缺口）/ vq-5nz.6（停滯草稿換方法）。
- 可選下票（不阻塞）：把 audit_kv_preservation 接進 real_slice 的 before_after 報告。
- d33a1ac8 CI 待 loop 自動推 auto/qwen27b 後核。

## 紅線
不碰 main、不自 push、不讀 /srv/eval hidden/scorer、缺值＝UNKNOWN 不填 0、不為每輪有 commit 加水工單/regex/靜態 prompt、tamper/UNKNOWN 不算成功、批內開發選樣不宣稱 localized 較好。
