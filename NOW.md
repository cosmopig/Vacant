# NOW

## 現在在哪（r1147）
- P20261106_2241-1 驗收完成（124e86d4）：real_slice 擴充為 **4 格最小對照**（1 失敗＋1 正確真草稿 × generic/localized），FROZEN_PENDING_NAMING 維持、0 模型呼叫。
- 正確草稿 dab_378-pi-A（e008 pass=true/1.0、draft 06ff239a…、與 dab_378-pi-C 共用 task 目錄/需求/CSV）入 manifest；drafts[0] 維持 bad（針守衛依賴）。
- 驗收：real_slice 8 passed（工單「7」未計新增 baseline 測試，誤算已如實記）；5 檔 219 passed；--dry-run「2 drafts · 4 cells」；--baseline C 9/11 PASS（pre/post_kurtosis FAIL）＋ A 11/11 PASS；針 -1.13 守衛綠。

## 對 11-06 指示 2 的意義
- 「正確成果是否退步（right_to_wrong=0）」現有三重客觀基線：
  1. 真實正確草稿基線（A 11/11 PASS）；
  2. 兩臂同草稿起點（每 draft 一個 pin hash，兩臂同檔）；
  3. r1145 單 rep 實跑已量 2 格（C 兩臂 9P/2F→11P、regressed=0、generic 更省）。
- 4 格全量（A＋C × 兩臂）＝授權後的最小完整對照；發射＝新成本另報。

## 下一步（候需求端）
- 授權 fire 4 格（A＋C × 兩臂、同預算 60/4M/300s）→ 一次回答：localized 是否多修好、正確成果是否退步、成本是否值得。
- 或點名 vq-6rp（dabstep-1753 模型側硬缺口）/ vq-5nz.6（停滯草稿換方法）。
- 124e86d4 CI 待 loop 自動推後核。

## 紅線
不碰 main、不自 push、不讀 /srv/eval hidden／scorer、缺值＝UNKNOWN 不填 0、不為每輪有 commit 加水工單／regex／靜態 prompt、tamper/UNKNOWN 不算成功、批內開發選樣不宣稱 localized 較好。
