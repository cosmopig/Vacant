# NOW

## 現在在哪（r1142）
- r1142：切片 A（realtask_manifest.json）補齊六要素規格 six_elements＋機器可驗測試（P20261106_2121-1、commit f4391686）——資深審查 2026-11-06 #3 要求兩切片同口徑，切片 B 已有、切片 A 補齊；TDD 先紅後綠、reqloop 四檔 207 passed、A dry-run/baseline 皆 EXIT=0；未 fire（無新授權、新成本另報）。
- r1141 驗證輪：審查三點核對＋雙切片現樹複驗全綠（A/B dry-run＋baseline 皆 EXIT=0、無洩漏；reqloop 206 passed）；未 fire（無新授權、新成本另報）。
- r1141 redo：點名三檔補實讀（effects_20261105_summary.json 全結構、multideliv summary.md＋CSV＋manifest、repair.py L1817-1995）——STATE/NOW 依賴斷言全部核實一致、0 更正。
- r1140：工單 P20261106_2040-2 完成：realtask_manifest.json 補入真實正確草稿 `dabstep-11-pi-A`（e014 lab pass=true、本地 req_max_eur_amount PASS）→ 3 草稿（2 bad＋1 good）×2 臂＝6 格對照基準；status 維持 NOT_fired。
- commit 7ad97fbe（2 檔：manifest＋test_reqloop_g2.py 兩測試擴充）。驗收 2 passed；dry-run 6 cells EXIT=0；baseline 1 PASS 2 FAIL EXIT=0；reqloop 四測試檔 206 passed。0 模型呼叫、0 發射。
- ⚠ 工單針「4990.0」非本切片任何題重算值（實際 col_max(eur_amount)=4811.76＝good 草稿值；無欄位 max 近 4990）——已改以 4811.76 入針並註記於票尾，避免空洞斷言。

## 雙切片（皆 NOT_fired）
- A=realtask_manifest.json（6 格、2 bad＋1 good；離線三門 verify_frozen＋--dry-run＋--baseline 全綠；六要素規格 r1142 補齊＋測試鎖定）。
- B=real_slice/manifest.json（dab_378、2 格、7 測試；六要素規格齊備）。

## 下一步
- 若授權：fire A 或 B（二擇一／分批、不並跑）——模型流量＝新成本、先另報。
- 未授權：維持雙凍結、0 新票、不加 regex／靜態 prompt／重跑；候需求端點名 vq-6rp、vq-5nz.6。

## 紅線
不碰 main、不自 push（loop 自動推 auto/qwen27b）、不讀 /srv/eval hidden／scorer 源、缺值＝UNKNOWN 不填 0、不為「每輪有 commit」加 regex／靜態 prompt／未授權重跑／純文檔修補、批內開發選樣不宣稱 localized 較好、兩臂起始 hash 不一致不稱同草稿公平比較、tamper/UNKNOWN 不算成功。
