# NOW

## 現在在哪（r1145）
- r1145 發射了已授權的最小 A/B（11-06 #4「先證明可修回一種內容錯誤才擴量」＋ #7 已授權小型原型不等點名＋審查 #3 條件式指示）；0 新票、repo 零代碼改動。
- 切片＝唯一真實內容錯誤切片 real_slice dab_378-pi-C（e008 真實 CSV；kurtosis 重算錯 -1.17 vs 真值 -1.13；9 滿足行須保留）× generic/localized＝2 格；碼態釘住 cd747e53（git archive）；model lms1004nothink/gemma-4-12b-it-qat；雙臂同預算（60 calls/4M tok/300s 每輪）。
- 兩臂起始草稿 sha256 相同（16754dc3…）→ 同草稿公平比較成立。

## 原始結果（raw；完整在 ops/realab_dab378_20261106/＋audits/realab_dab378_20261106_summary.json）
| 臂 | 停機 | 修復 | regressed | tamper | 獨立 scorer | 成本（session/calls/tok/s） |
|---|---|---|---|---|---|---|
| generic | gap_closed | pre+post_kurtosis 修回（9P/2F→11P） | 0 | 否 | pass=true | 1/24/440,238/89.2 |
| localized | gap_closed | pre+post_kurtosis 修回（9P/2F→11P） | 0 | 否 | pass=true | 1/32/417,236/300.2（觸 300s 上限） |

- 審查問題的直接回答：localized 修回 pre/post_kurtosis＝是；保住其餘 9 鍵＝是（檢查層 9/9 仍 PASS、獨立 scorer pass=true；位元組層另重排 2 行 median 格式 19711.00→19711.0，數值相同、scorer 接受）；成本 ≤ generic＝否（calls +33%、tokens −5%、wall 3.4x）。
- 關鍵原始觀察：對照臂 generic（單輪重驗）在同一草稿修回同樣錯誤且更省——單 rep 未顯示 localized 優於 generic。「此類內容錯誤可修回」成立（1 rep）；擴量＝新決策，需另行授權。
- 11-06#3 停止條件：effects2 28 格批已判定未觸發（localized 修回更多）；本批是內容錯誤切片最小對照，不推翻該判定。

## 下一步（候需求端，不自行擴量）
- 需求端決策：是否就 dab_378 類內容錯誤擴量（多草稿/多 rep/新成本另報）；或點名 vq-6rp（dabstep-1753 模型側硬缺口）/ vq-5nz.6（停滯草稿換方法）。
- c7755793 CI 仍待 loop 自動推後核。

## 紅線
不碰 main、不自 push（loop 自動推 auto/qwen27b）、不讀 /srv/eval hidden／scorer 源、缺值＝UNKNOWN 不填 0、不為「每輪有 commit」加 regex／靜態 prompt／未授權重跑／純文檔修補／補欄位水工單、批內開發選樣不宣稱 localized 較好、兩臂起始 hash 不一致不稱同草稿公平比較、tamper/UNKNOWN 不算成功。
