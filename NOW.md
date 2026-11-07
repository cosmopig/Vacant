# NOW — R-loop (auto/qwen27b)

## 第 1152 輪 (2026-11-07 09:00 +0800)
**工單 P20261107_0041-1：鍵級保留審計升級為強制（repair_slice 接線）→ commit eafa6e7e**

- 單一結構化答案檔（answer.txt @key[val]）部分修復時，agent 擅改初始已滿足 key 原為漏防（檔案級 satisfied_* 對單一交付物 by design 為空；r1151 的 kv_* 純資訊性、不改退出碼）。
- 改法：初始驗 PASS 且帶 params.key 的鍵＝kv_satisfied；**部分修復情境**（初始驗存在未滿足必需項，kv_enforced）下：各輪 round_mutated 併入被改寫 key（缺口不提前關閉、不算進度）＋結尾併入 satisfied_preserved/satisfied_mutated → **_exit_code 20 拒收**。
- 不變量守住：good 草稿（無初始缺口）satisfied_* 維持 ()（argon 20261106_1121 全 PASS 重存不得誤拒）；零輪 no_gap 審計不執行、不虛灌證據；kv_preserved/kv_mutated 資訊欄位保留（g2 報告路徑不變）。
- TDD 紅→綠：test_single_deliverable_kv_preservation_enforced（dab_378-pi-C 真切片：(a) 只修 FAIL key⇒8 鍵保留 exit 0；(b) 改寫 pre_mean⇒satisfied_mutated、exit 20、非 gap_closed）。
- 驗收：5 檔 checks/g2/repair/real_slice/g1_gate＝**222 passed**（221 既有＋1 新增、無回歸）。
- 紅線：0 模型呼叫、0 發射、0 元；未動 main、未自 push（loop 自動推）、未讀 hidden/scorer、未加 regex/靜態 prompt/重試。
- 沒驗證：真實模型行為（純離線接線、無新效果數字）。

## 待辦
- [ ] vq-6rp（dabstep-1753 模型側硬缺口）／vq-5nz.6（停滯草稿換方法）仍候需求端點名。
- [ ] 是否擴量＝新決策、需另行授權（11-06#4「證明可修回後再擴量」）。
（MEMORY 上限 6 KB、NOW 上限 3 KB；超過的部分沒有附上，請先把它縮短）
