# NOW.md — Vacant 現況（≤3KB；本檔覆寫不追加，歷史看 STATE.md）

## 現況（2026-11-14 人類改向；這條分支＝redo 線）
- **唯一的任務在 `ops/redo/MISSION.md`，每一輪先讀它。** 問題只有一個：原生 pi＋本機 gemma-4-12b，
  同樣 1800 秒，「工作區自己的測試沒過就開全新行程重來（最多 3 次）」是不是比「一次跑到底」交出更多通過的成果。
- 量具＝`ops/redo/redo.py`（已驗：selftest 26/26；真的 pi 0.87.1 對假模型端點跑通兩臂、端點死掉記成 infra_void）。
  **不要改它的判定邏輯。**
- 票＝`ops/redo/tickets/T04…T07`，照編號一次一張。**T01／T02 done（GO）、T03 已發射在跑**（票尾在 `~/dev/ops/tickets/redo/done/`）：
  redo1（34 題×5 次＝170 對，root `~/dev/ops/redo_runs/redo1`）2026-11-14 17:23 發射（preflight PREFLIGHT_OK、計畫 f95f90d86b77 已 commit、runner PID 111807）。
  **下一輪起：每輪最多一次 `status`、貼進「進度」、結束**；runner 死就同一行重啟（PATH 含 `~/.local/bin`）、不因結果刪格；
  跑完（state ∈ {EFFECTIVE, UNRESOLVED, CONTRADICTS}）：查 `harness_changed_mid_run`=false → REPORT 複製進 `ops/redo/results/redo1_REPORT.{md,json}` 並 commit → 做 T04。
- screen16（S1）：EFFECTIVE 16/16 對 A=2/16 R3=9/16 b=0 c=7 p=0.015625、R3 驗收放行卻錯＝0 ⇒ **GO**（計畫檔 `prereg.go_rule`）。
  這 16 題是看過結果挑的（`prereg.role`：「篩選，不是證據」）：**這批數字只是 GO/NO-GO 閘門，不可當成效果引用**；結果在 `ops/redo/results/screen16_REPORT.{md,json}`。
- ⚠ 同批 8 次嘗試（A 2、R3 6）以 `Model reloaded.` 結束（100.86.226.21 伺服器端錯誤、會話被終止，12:02–16:15 分散），
  照預註冊規則計為嘗試（regex 不含 "reloaded"）、未改規則；「要不要歸 void」已照 MISSION §七記一行在 `ops/redo/IDEAS.md`（不做）；
  8 格中 6 格沒過、2 格後續嘗試通過。
  GO 判定對這 8 格不敏感（這 8 題 R3 全過；重跑只可能增大 c、b 恒 0）。端點 17:09 實測正常。詳見票尾。
  redo1 若再出現：報告會列出、照同規則處理；**不要改 infra 規則、不要因為結果刪格**。
- 尚無可引用數字：可引用的句子只有 **redo1** 計畫檔的 `prereg.states` 那幾句（smoke2／screen16 計畫沒有 `states` 欄位，兩批數字不可引用）。

## 這一輪怎麼做
1. 有長跑在跑：`python3 ops/redo/redo.py status --root <root>` 一次，把那一行貼在下面「進度」，結束這一輪。
2. 沒有長跑：做編號最小、前提已滿足的那張票。
3. 沒有票可做：結束這一輪。空輪比亂做好。

## 進度
- 2026-11-16 09:29（第 1860 輪）redo1：`INCOMPLETE 107/170 對 A=52/108 R3=73/106 b=4 c=25 infra_void 對=2`（仍在跑；1859→1860 對數 107→107 未動、A 有效格 107→108 +1、A 通過 52→52 未動、R3 有效格 106→106 未動、R3 通過 73→73 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 09:11（第 1859 輪）redo1：`INCOMPLETE 107/170 對 A=52/107 R3=73/106 b=4 c=25 infra_void 對=2`（仍在跑；1858→1859 對數 106→107 +1、A 有效格 107→107 未動、A 通過 52→52 未動、R3 有效格 105→106 +1、R3 通過 73→73 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 08:53（第 1858 輪）redo1：`INCOMPLETE 106/170 對 A=52/107 R3=73/105 b=4 c=25 infra_void 對=2`（仍在跑；1857→1858 對數 106→106 未動、A 有效格 107→107 未動、A 通過 52→52 未動、R3 有效格 105→105 未動、R3 通過 73→73 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 08:35（第 1857 輪）redo1：`INCOMPLETE 106/170 對 A=52/107 R3=73/105 b=4 c=25 infra_void 對=2`（仍在跑；1856→1857 對數 105→106 +1、A 有效格 105→107 +2、A 通過 52→52 未動、R3 有效格 105→105 未動、R3 通過 73→73 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 08:16（第 1856 輪）redo1：`INCOMPLETE 105/170 對 A=52/105 R3=73/105 b=4 c=25 infra_void 對=2`（仍在跑；1855→1856 對數 105→105 未動、A 有效格 105→105 未動、A 通過 52→52 未動、R3 有效格 105→105 未動、R3 通過 73→73 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 07:58（第 1855 輪）redo1：`INCOMPLETE 105/170 對 A=52/105 R3=73/105 b=4 c=25 infra_void 對=2`（仍在跑；1854→1855 對數 105→105 未動、A 有效格 105→105 未動、A 通過 52→52 未動、R3 有效格 104→105 +1、R3 通過 73→73 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 07:38（第 1854 輪）redo1：`INCOMPLETE 105/170 對 A=52/105 R3=73/104 b=4 c=25 infra_void 對=2`（仍在跑；1853→1854 對數 104→105 +1、A 有效格 105→105 未動、A 通過 52→52 未動、R3 有效格 103→104 +1、R3 通過 72→73 +1、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 07:19（第 1853 輪）redo1：`INCOMPLETE 104/170 對 A=52/105 R3=72/103 b=4 c=25 infra_void 對=2`（仍在跑；1852→1853 對數 104→104 未動、A 有效格 105→105 未動、A 通過 52→52 未動、R3 有效格 103→103 未動、R3 通過 72→72 未動、b=4 未動、c=25 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 06:59（第 1852 輪）redo1：`INCOMPLETE 104/170 對 A=52/105 R3=72/103 b=4 c=25 infra_void 對=2`（仍在跑；1851→1852 對數 102→104 +2、A 有效格 102→105 +3、A 通過 50→52 +2、R3 有效格 101→103 +2、R3 通過 70→72 +2、b=4 未動、c 24→25 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 06:41（第 1851 輪）redo1：`INCOMPLETE 102/170 對 A=50/102 R3=70/101 b=4 c=24 infra_void 對=2`（仍在跑；1850→1851 對數 101→102 +1、A 有效格 102→102 未動、A 通過 50→50 未動、R3 有效格 100→101 +1、R3 通過 70→70 未動、b=4 未動、c=24 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 06:24（第 1850 輪）redo1：`INCOMPLETE 101/170 對 A=50/102 R3=70/100 b=4 c=24 infra_void 對=2`（仍在跑；1849→1850 對數 100→101 +1、A 有效格 101→102 +1、A 通過 50→50 未動、R3 有效格 99→100 +1、R3 通過 69→70 +1、b=4 未動、c 23→24 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 06:07（第 1849 輪）redo1：`INCOMPLETE 100/170 對 A=50/101 R3=69/99 b=4 c=23 infra_void 對=2`（仍在跑；1848→1849 對數 100→100 未動、A 有效格 101→101 未動、A 通過 50→50 未動、R3 有效格 99→99 未動、R3 通過 69→69 未動、b=4 未動、c=23 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 05:49（第 1848 輪）redo1：`INCOMPLETE 100/170 對 A=50/101 R3=69/99 b=4 c=23 infra_void 對=2`（仍在跑；1847→1848 對數 100→100 未動、A 有效格 100→101 +1、A 通過 50→50 未動、R3 有效格 99→99 未動、R3 通過 69→69 未動、b=4 未動、c=23 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 05:32（第 1847 輪）redo1：`INCOMPLETE 100/170 對 A=50/100 R3=69/99 b=4 c=23 infra_void 對=2`（仍在跑；1846→1847 對數 99→100 +1、A 有效格 100→100 未動、A 通過 50→50 未動、R3 有效格 98→99 +1、R3 通過 68→69 +1、b=4 未動、c 22→23 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 05:13（第 1846 輪）redo1：`INCOMPLETE 99/170 對 A=50/100 R3=68/98 b=4 c=22 infra_void 對=2`（仍在跑；1845→1846 對數 96→99 +3、A 有效格 97→100 +3、A 通過 48→50 +2、R3 有效格 95→98 +3、R3 通過 65→68 +3、b=4 未動、c 21→22 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 04:55（第 1845 輪）redo1：`INCOMPLETE 96/170 對 A=48/97 R3=65/95 b=4 c=21 infra_void 對=2`（仍在跑；1844→1845 對數 96→96 未動、A 有效格 96→97 +1、A 通過 48→48 未動、R3 有效格 95→95 未動、b=4 未動、c=21 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 04:36（第 1844 輪）redo1：`INCOMPLETE 96/170 對 A=48/96 R3=65/95 b=4 c=21 infra_void 對=2`（仍在跑；1843→1844 對數 95→96 +1、A 有效格 95→96 +1、R3 有效格 95→95 未動、b=4 未動、c 20→21 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 04:19（第 1843 輪）redo1：`INCOMPLETE 95/170 對 A=48/95 R3=65/95 b=4 c=20 infra_void 對=2`（仍在跑；1842→1843 對數 95→95 未動、A 有效格 95→95 未動、R3 有效格 94→95 +1、b=4 未動、c=20 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 04:01（第 1842 輪）redo1：`INCOMPLETE 95/170 對 A=48/95 R3=64/94 b=4 c=20 infra_void 對=2`（仍在跑；1841→1842 對數 95→95 未動、A 有效格 95→95 未動、R3 有效格 94→94 未動、b=4 未動、c=20 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 03:44（第 1841 輪）redo1：`INCOMPLETE 95/170 對 A=48/95 R3=64/94 b=4 c=20 infra_void 對=2`（仍在跑；1840→1841 對數 94→95 +1、A 有效格 94→95 +1、R3 有效格 93→94 +1、b=4 未動、c=20 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 03:25（第 1840 輪）redo1：`INCOMPLETE 94/170 對 A=47/94 R3=63/93 b=4 c=20 infra_void 對=2`（仍在跑；1839→1840 對數 93→94 +1、A 有效格 94→94 未動、R3 有效格 92→93 +1、b=4 未動、c 19→20 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 03:07（第 1839 輪）redo1：`INCOMPLETE 93/170 對 A=47/94 R3=62/92 b=4 c=19 infra_void 對=2`（仍在跑；1838→1839 對數 92→93 +1、A 有效格 92→94 +2、R3 有效格 91→92 +1、b=4 未動、c 18→19 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 02:49（第 1838 輪）redo1：`INCOMPLETE 92/170 對 A=47/92 R3=61/91 b=4 c=18 infra_void 對=2`（仍在跑；1837→1838 對數 91→92 +1、A 有效格 92→92 未動、R3 有效格 90→91 +1、b=4 c=18 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 02:31（第 1837 輪）redo1：`INCOMPLETE 91/170 對 A=47/92 R3=61/90 b=4 c=18 infra_void 對=2`（仍在跑；1836→1837 對數 90→91 +1、A 有效格 90→92 +2、R3 有效格 90→90 未動、b=4 未動、c 17→18 +1、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 02:10（第 1836 輪）redo1：`INCOMPLETE 90/170 對 A=47/90 R3=61/90 b=4 c=17 infra_void 對=2`（仍在跑；1835→1836 對數 89→90 +1、A 有效格 90→90 未動、R3 有效格 88→90 +2、b=4 c=17 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 01:52（第 1835 輪）redo1：`INCOMPLETE 89/170 對 A=47/90 R3=60/88 b=4 c=17 infra_void 對=2`（仍在跑；1834→1835 對數 89→89 未動、A 嘗試 89→90 +1、R3 嘗試 88→88 未動、b=4 c=17 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 01:34（第 1834 輪）redo1：`INCOMPLETE 89/170 對 A=47/89 R3=60/88 b=4 c=17 infra_void 對=2`（仍在跑；1833→1834 對數 89→89 未動、A 嘗試 89→89 未動、R3 嘗試 88→88 未動、b=4 c=17 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 01:17（第 1833 輪）redo1：`INCOMPLETE 89/170 對 A=47/89 R3=60/88 b=4 c=17 infra_void 對=2`（仍在跑；1832→1833 對數 89→89 未動、A 嘗試 89→89 未動、R3 嘗試 88→88 未動、b=4 c=17 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 00:57（第 1832 輪）redo1：`INCOMPLETE 89/170 對 A=47/89 R3=60/88 b=4 c=17 infra_void 對=2`（仍在跑；1831→1832 對數 89→89 未動、A 嘗試 89→89 未動、R3 嘗試 88→88 未動、b=4 c=17 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 00:40（第 1831 輪）redo1：`INCOMPLETE 89/170 對 A=47/89 R3=60/88 b=4 c=17 infra_void 對=2`（仍在跑；1830→1831 對數 88→89 +1、A 嘗試 88→89 +1、R3 嘗試 87→88 +1、b=4 c=17 未動、infra_void 對 2 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 00:20（第 1830 輪）redo1：`INCOMPLETE 88/170 對 A=46/88 R3=59/87 b=4 c=17 infra_void 對=2`（仍在跑；1829→1830 對數 87→88、infra_void 對 1→2、A 嘗試 88→88 未動、R3 嘗試 87→87 未動、b=4 c=17 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-16 00:02（第 1829 輪）redo1：`INCOMPLETE 87/170 對 A=46/88 R3=59/87 b=4 c=17 infra_void 對=1`（仍在跑；1828→1829 對數 87→87 未動、A 嘗試 88→88 未動、R3 嘗試 87→87 未動、b=4 c=17 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 23:44（第 1828 輪）redo1：`INCOMPLETE 87/170 對 A=46/88 R3=59/87 b=4 c=17 infra_void 對=1`（仍在跑；1827→1828 對數 87→87 未動、A 嘗試 88→88 未動、R3 嘗試 87→87 未動、b=4 c=17 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 23:26（第 1827 輪）redo1：`INCOMPLETE 87/170 對 A=46/88 R3=59/87 b=4 c=17 infra_void 對=1`（仍在跑；1826→1827 對數 84→87 +3、A 嘗試 85→88 +3、R3 嘗試 84→87 +3、b=4 未動、c 16→17 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 23:07（第 1826 輪）redo1：`INCOMPLETE 84/170 對 A=45/85 R3=57/84 b=4 c=16 infra_void 對=1`（仍在跑；1825→1826 對數 84→84 未動、A 嘗試 85→85 未動、R3 嘗試 84→84 未動、b=4 c=16 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 22:48（第 1825 輪）redo1：`INCOMPLETE 84/170 對 A=45/85 R3=57/84 b=4 c=16 infra_void 對=1`（仍在跑；1824→1825 對數 84→84 未動、A 嘗試 84→85 +1、R3 嘗試 84→84 未動、b=4 c=16 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 22:30（第 1824 輪）redo1：`INCOMPLETE 84/170 對 A=45/84 R3=57/84 b=4 c=16 infra_void 對=1`（仍在跑；1823→1824 對數 84→84 未動、A 嘗試 84→84 未動、R3 嘗試 84→84 未動、b=4 c=16 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 22:11（第 1823 輪）redo1：`INCOMPLETE 84/170 對 A=45/84 R3=57/84 b=4 c=16 infra_void 對=1`（仍在跑；1822→1823 對數 83→84 +1、A 嘗試 84→84 未動、R3 嘗試 83→84 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 21:54（第 1822 輪）redo1：`INCOMPLETE 83/170 對 A=45/84 R3=56/83 b=4 c=16 infra_void 對=1`（仍在跑；1821→1822 對數 81→83 +2、A 嘗試 82→84、R3 嘗試 81→83、c 14→16、b=4 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 21:36（第 1821 輪）redo1：`INCOMPLETE 81/170 對 A=44/82 R3=54/81 b=4 c=14 infra_void 對=1`（仍在跑；1820→1821 對數 80→81、A 嘗試 80→82、R3 嘗試 81→81 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 21:16（第 1820 輪）redo1：`INCOMPLETE 80/170 對 A=44/80 R3=54/81 b=4 c=14 infra_void 對=1`（仍在跑；1819→1820 對數 80→80 未動、R3 嘗試 81→81 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 20:59（第 1819 輪）redo1：`INCOMPLETE 80/170 對 A=44/80 R3=54/81 b=4 c=14 infra_void 對=1`（仍在跑；1818→1819 對數 80→80 未動、R3 嘗試 80→81）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 20:41（第 1818 輪）redo1：`INCOMPLETE 80/170 對 A=44/80 R3=54/80 b=4 c=14 infra_void 對=1`（仍在跑；1817→1818 對數 80→80 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 20:23（第 1817 輪）redo1：`INCOMPLETE 80/170 對 A=44/80 R3=54/80 b=4 c=14 infra_void 對=1`（仍在跑；1816→1817 對數 75→80 +5）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 20:06（第 1816 輪）redo1：`INCOMPLETE 75/170 對 A=40/76 R3=49/75 b=4 c=14 infra_void 對=1`（仍在跑；1815→1816 對數 73→75 +2）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 19:48（第 1815 輪）redo1：`INCOMPLETE 73/170 對 A=38/73 R3=47/73 b=4 c=13 infra_void 對=1`（仍在跑；1814→1815 對數 72→73 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 19:31（第 1814 輪）redo1：`INCOMPLETE 72/170 對 A=38/72 R3=47/73 b=4 c=13 infra_void 對=1`（仍在跑；1813→1814 對數 72→72 未動）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 19:14（第 1813 輪）redo1：`INCOMPLETE 72/170 對 A=38/72 R3=47/72 b=4 c=13 infra_void 對=1`（仍在跑；1812→1813 對數 71→72 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 18:55（第 1812 輪）redo1：`INCOMPLETE 71/170 對 A=37/71 R3=46/71 b=4 c=13 infra_void 對=1`（仍在跑；1811→1812 對數 70→71 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 18:37（第 1811 輪）redo1：`INCOMPLETE 70/170 對 A=37/70 R3=46/70 b=4 c=13 infra_void 對=1`（仍在跑；1810→1811 對數 69→70 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 18:19（第 1810 輪）redo1：`INCOMPLETE 69/170 對 A=36/69 R3=45/69 b=4 c=13 infra_void 對=1`（仍在跑；1809→1810 對數 68→69 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。
- 2026-11-15 18:02（第 1809 輪）redo1：`INCOMPLETE 68/170 對 A=36/69 R3=44/68 b=4 c=12 infra_void 對=1`（仍在跑；1808→1809 對數 67→68 +1）；screen16 `EFFECTIVE 16/16`、smoke2 `UNRESOLVED 2/2`（已完成批）。

## 不准做（MISSION §四）
- 結案量具、複核腳本、替量具／簿記寫守門測試、只改簿記的輪次、重新驗收以前驗收過的東西。
- reqloop／G 系列／L008（凍結，不是這條分支的事）。freeze_check／ci_tip_check 的紅燈屬於那條線：不修、不追。
- 一批跑到一半改 `redo.py` 或計畫檔；因為結果刪格；讀題庫的 hidden／scorer。

## 紅線
- 凍結／受控解凍：repair.py 2795 行／blob 5147f8c3…、run_eval.py 1298 行／blob b6d2f37f…（仍凍結）；extract.py 1295 行／blob b502741b…、checks.py 2907 行／blob d401a8ae…（受控解凍、只加法、預設＝舊行為）；g25 filing（6 sha256）；g3_1/g3_2 歷史未動。
- 不 push main；無 reset/rebase；.github/workflows/ 只讀；鐵律 1–6 照舊。
- 口徑：redo 的數字是 harness 裡的機制，不是「裝了 Vacant」的數字；可以說的句子只有計畫檔 `prereg.states` 那幾句。

## 進度（每輪覆寫這一段，一行）
- 2026-11-15 17:05（1806 輪）status：redo1 `INCOMPLETE 66/170 對 A=36/67 R3=44/66 b=4 c=12 infra_void 對=1`（INCOMPLETE＝還沒跑完、只能續跑，照計畫檔 `prereg.states`；1805→1806 對數 66→66 未動；本輪未查 runner 存活，下一輪先查再續跑或照規重啟）；screen16 `EFFECTIVE 16/16 對 A=2/16 R3=9/16 b=0 c=7 infra_void 對=0`（GO 閘門，不可引用）；smoke2 `UNRESOLVED 2/2 對 A=1/2 R3=2/2 b=0 c=1 infra_void 對=0`（不可引用）；本輪照指示只做 status
