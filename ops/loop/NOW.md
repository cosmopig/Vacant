# NOW.md — 現況（每輪覆寫，≤3KB）

## 狀態（2026-11-12 r1484；CI 紅燈根因修＋argon fe731a230 審查吸收；freeze_check 12/12）
- **r1484（CI 紅根因修）：**本機 CI 以 HOME=/var/tmp/ci-home（空目錄）＋worktree 跑 pytest→e010_closure_check 的 Path.home() 證據解析不到 ~/dev/ops→test_selftest_ok／test_check_detects_byte_tamper 紅。修：證據進 repo 為凍結快照（ops/packets/e010_bigwork.md＋ops/BACKLOG.md，快照時刻與 ~/dev/ops byte 一致）＋缺省指 repo 路徑（不依賴 HOME）＋sha256 釘住（packet 1e84ad57…／backlog 6599f4d3…；n6 負控暫態篡改必紅）＋2 pin 測試＋test_selftest_ok 以空 HOME 模擬 CI（回歸護欄）；~/dev/ops/BACKLOG.md 仍為活檔，repo 副本＝結案時刻凍結紀錄。
- **r1484（argon fe731a230 審查吸收）：**其 HOME fallback 硬編碼 /home/user1 不採（mainline vendoring 較強）；採其 stray-labd verdict 語義修（bool(checks) 塞 all([]) 空集偽真洞＋unrelated 壞行不否決＋parse_errors 仍記錄）——真 session 重驗：目標 93a55755 找到、7 checks 全過（nohup 命令逐字＝根因敘事）、line 190 為唯一 unrelated 截斷行、PID 734502／733374 關聯→verdict NOT_ESTABLISHED→OK（假陰性修）＋1 語義測試。
- **r1484（三分支收斂）：**argon 於 r1483 後自行推進 fe731a230（HOME 修）→diff_argon 5 檔分岔；mainline 正典（已吸收其良件），7 in-scope 檔＋2 簿記鏡像同步進 argon／worker worktree＋commit→diff 0。
- **驗收（本輪新跑）：**e010 5 passed（含 2 新）＋selftest OK＋非 selftest RC=0；stray-labd 8 passed（含 1 新）＋selftest OK＋--run VERDICT OK rc=0；freeze_check 12/12 FROZEN_STATE_OK；CI 模擬（HOME=空目錄）e010＋stray-labd 13 passed（修前同環境即紅）；anchors 5 passed；0 model calls。

## 紅線（契約，不改）
- 無 push（迴圈自推 auto/qwen27b）、無 main、無 reset/rebase；.github/workflows/ 只讀。
- 凍結 4 檔不改：repair.py 2795 行／blob 5147f8c3…、extract.py 1217 行／blob e757aec5…、checks.py c7589c61…、run_eval.py 332cd324…；g25 filing（6 sha256）；g3_1/g3_2 歷史不改。
- 不讀 /srv/eval/hidden/ 或 scorer.py；缺值 UNKNOWN 不填 0。
- 不寫 /srv/vlab/queue；不 poll CI；不跑 full pytest。

## 未完成（≤3，交接下輪）
1. G 系列候人類裁決（H2_REFUTED 停止規則）：解凍 extract/checks 或終止；vq-kax 候裁；新 G 票不接。
2. CI：三分支新 HEAD（qwen27b／argon／worker）下次跑預期轉綠→下輪輪首 ci_status.py 一次讀取（不 poll）。

## 下輪入口（≤3）
- CI 狀態一次讀取（不 poll）：驗 e010 2 項＋stray-labd 應轉綠；若仍紅→讀 log 根因（不猜）。
- G 系列若人類裁決（解凍／終止）→依裁決開新票；不代決。
- 守衛：anchors 綠、freeze_check 12/12、鏡像 byte 一致、NOW.md ≤3KB。
