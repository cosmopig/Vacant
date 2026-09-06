# R451 稽核：套件量具綁進上鏈——擋掉的、擋不掉的，與 R449 §七-2 推翻條件成立

（2026-09-06，Fable 5.1 稽核輪。實作由 Opus 完成並提交為 56a1221；一名 Opus 攻擊者獨立複跑
測試、機率探針與量具數字，並造出作者沒試的第六個變體。本文件只讀
`ops/gain/replay/peer_exec_gauge_gate_k3_s{1,4}.json`、`ops/gain/replay/r451_stateful_gate.json`
與 `vacant/checks.py`；可行性探針 `r451_stateful_suite_probe.py --feasibility` 由本輪親手重跑。零 API。）

## 一、實作了什麼（56a1221，已推）

- `vacant/suitegauge.py`：純函式量具 `gauge_suite(check_code, reference, broken_stubs)`——參考解要過、
  每個已知壞樁都要被擋；`n_broken == 0` 不算過（防空集合空泛成立）。`probe_instrument` 與
  `peerexec.commit_suite` 共用這一份判準。
- `peerexec.commit_suite` 現在**必須**帶 `GaugeRecord`；缺、不符本套件 hash、或量具沒過 ⇒ 拋
  `SuiteGaugeError`，鏈上不留任何條目。`suite_gate`／`open_suite`／`gauged_suite_index`／`form_verdict`
  ／`select_by_quorum` 全部 fail-closed；收據多一欄 `gauge_status`，`Selection.refusal_reason` 把
  「套件爛」和「沒有候選夠好」分開。
- `gain_run.py` 探針路徑**逐鍵相同**：攻擊者以 `r449_probe_equivalence.py --base HEAD~1` 重跑 179 題，
  舊 sha `8395c7a09fdc2a6c`、新舊 8 個鍵含逐題欄位全同；探針列 179/179、179/179 不變；
  `r474_stub_sweep.py --selftest` PASS。測試 42（peerexec）＋45（gain）全過。

## 二、量到什麼（k=3 誠實執行器、真簽章真鏈，全部 chain_ok）

| 套件變體 | MBPP+（371）上鏈 | 交付 vs 真套件 | 假交付 |
|---|---|---|---|
| 真套件 | 371/371（4 樁時 369/371） | 75.20% | 17.8% |
| **trivial（`pass`）** | **0/371，全部 `gauge_failed`** | — | — |
| weak（只留第一條 assert） | 367/371 | −2.16pp [−3.77, −0.81] | 20.8% |
| targeted（雜湊黑名單四樁、其餘全放） | 371/371 | −6.47pp [−8.89, −4.04] | 31.3% |
| **stateful（攻擊者新造）** | **371/371（4 樁時也是 371/371，比真套件還多）** | **−75.20pp [−79.51, −70.89]，交付 0.00%** | 24.8% |

LCB（r443）只有 12/91 題有參考解可量，其餘 79 題以 `ungaugeable_no_reference` 另計，**不是**閘門擋下 79 個攻擊；
n=12 的區間全部跨 0，不作證據。MBPP+ 的 mimic 交付列沒量（缺 1855 格快取），表上留白。

## 三、裁決

1. **閘門確實關掉了 R449 §三-3 那一類**：「載得進就算過」的套件 371/371 在 commit 就被拒，沒花一次沙箱。
2. **56a1221 提交訊息裡「殘餘上限＝targeted −6.47pp」那句作廢。** 攻擊者的 stateful 變體只做三件事：
   候選雜湊在已知壞樁集合裡 ⇒ 擋；/tmp 沒有標記檔 ⇒ 建檔並放行（量具的參考解那一發**必然**是第一發，
   因為 `gauge_suite` 規定參考解先跑、`select_by_quorum` 規定 suite_gate 先於任何草稿）；其餘 ⇒ 跑真套件
   然後**把判準倒過來**。量具兩方向滿分、`suite_sha256` 全程不變、簽章與鏈都驗得過、`gauge_status="ok"`，
   出貨的是真套件會擋下的那一份。單題收據（Mbpp/100）已落盤：四份正確草稿被拒、唯一錯的那份出貨。
3. **R449 §七 第二條推翻條件成立**：「壞解被擋」綁進 commit 之後仍造得出通過量具卻交垃圾的套件
   ⇒ R449 §四-3 第二點（量具作為套件固定點的部分解）**作廢**，套件固定點回到「無解」——
   但比 R449 寫的更精確：**量具量的是一次執行，不是一件工件。** 驗收碼是任意 Python，跑在 runner 行程裡；
   `vacant/checks.py` 的 AST allowlist 只約束候選碼不約束驗收碼（本輪親手重跑 `--feasibility`：同一份驗收碼
   分四次沙箱呼叫得 pass/fail/fail/fail，`candidate.py` 逐位元組等於候選原始碼）。只要驗收碼能分辨
   「現在是量具在看」和「現在是出貨」，有限次測試對它就沒有任何約束力；加樁、換樁、比對樁的失敗細節、
   堵住讀原始碼的管道，四條全部無效（攻擊者逐條驗過）。
4. 誰跑量具也是同一個洞的另一面：`GaugeRecord` 由套件提交者簽，提交者若腐化根本不必跑量具就能簽出
   一份滿分紀錄。本輪沒有再量這條，因為它被第 3 點涵蓋——修法相同。

## 四、修法方向（下一輪，R452；本輪不動碼）

觀察：兩個題庫的驗收碼**本來就是 loader 從資料渲染出來的**——同一段固定前置（`__aeq`、旗標）＋
一串 `(輸入, 期望)`；MBPP+ 371 題的前置去掉旗標後只有一種。所以「驗收套件」的正確形態是**資料不是程式**：

- 套件＝`SuiteSpec`（canonical JSON：entry_point、tests=[{args, expected}]、比對設定），hash 算在資料上。
- 執行器**只執行自己的可信渲染器**產生的驗收碼，永遠不執行供應者寫的 Python。有狀態、雜湊黑名單、
  擬態，三種攻擊在這個形態裡**不可表達**，不是「被擋」。
- 量具照舊跑在渲染後的碼上；且因為渲染是確定性的，任何第三方拿到 spec＋參考解＋樁就能重算同一份
  `GaugeRecord`——紀錄從「因為有簽章所以可信」變成「可重算」。
- 剩下能表達的攻擊只有**覆蓋不足**（少測、挑容易的輸入）與**比對旗標放寬**（若旗標可由供應者選）。
  這兩個要量：真套件轉 spec 後在 1855＋455 個候選上可見標籤逐位相同（無損轉換）；「事後諸葛挑一條最鬆
  的測資但仍擋得住樁」的最壞單測資殘餘；旗標放寬的殘餘。這才是可以老實講的上限。
- 「期望輸出錯」不是攻擊，是需求本身——客戶說 2+2=5，系統就該交 5；有參考解時量具會抓到，沒有時本來就無從分辨。

## 五、對展場那句話的影響

R449 §五 的尾句「如果那套驗收測資本身是爛的，k 台機器會一致地、可驗證地交出一個錯的答案，畫面上一個
警告都不會亮」**維持原文**；本輪證明它在加了量具之後仍然成立，而且成立得更徹底（收據上還會多一個綠燈）。
R452 若做成，能改講：「驗收測資只能是輸入與期望輸出的清單，機器用自己的解釋器跑它；清單先證明擋得住
已知壞解、參考解全過，才能上鏈；之後剩下的問題只有一個——清單夠不夠多。」在那之前不准這樣講。

## 六、誠實邊界

- 全部數字來自重放與模擬（真簽章真鏈，但候選是 r446／r443 已歸檔的 5 份草稿），不是真跑多方執行。
- MBPP+ mimic 交付列未量；LCB 只有 12 題可量。
- 全套測試另有 3 個失敗，皆非本輪所致：`tests/test_archive_index.py` 兩個（`gain.signal_exists` 裁決值
  `'held'` 不在合法集合——另一個 session 的 verdicts 改動，待該 session 處理）、
  `tests/test_r448_launcher_prereg.py` 一個（本機存在 `runs/g_r448_eq5_mbpp_seed2`，環境性）。
- `CLAUDE.md` 程式碼地圖尚未列入 `vacant/suitegauge.py`，留待 R452 一併更新。

## 七、落盤證據

攻擊者的探針與結果一併提交：`ops/gain/replay/r451_stateful_suite_probe.py`、`r451_stateful_gate.json`、
`cache/peerexec_stateful_gauge_g_r446_eq5_mbpp.json`（量具普查 371/371 通過）、
`cache/peerexec_stateful_g_r446_eq5_mbpp.json`（1855 格逐格真沙箱標籤，放行 255/1855）。
