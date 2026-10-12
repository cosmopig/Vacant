# i1001 本機端到端（沒有 GPU）：指令與觀察到的結果

> 2026-10-01，本機容器（Linux 6.18、root、4 核、tmux 3.4、bwrap 0.9.0、Node 22.22.2、pi 0.87.1、Python 3.11.15）。
> **沒有碰 Colab、沒有起 VM、沒有任何付費模型呼叫、沒有讀任何金鑰檔**；「模型」是按格子編劇的機制替身（`local_e2e/e2e_stub.py`）。
> 這份驗的是**管線**（打字、完成偵測、分支、bridge、計分、打包、續跑、void 重跑、清理），**不是 agent 的表現**；真 vLLM 下的行為沒有被證明（見第七節）。
> 題目內容（敘述、隱藏測資、參考答案）與原始 pane／session 紀錄只在 scratchpad，不進 repo；`evidence_local_e2e/` 過了洩漏掃描
> （`local_e2e/leak_scan.py`：37,745 行題目文字、含負控制，0 筆）。

## 一、結論（先講）

- 用**真題目**（3 題 LCB＋dabench 10 題篩選＋databench 1 題＋polyglot_py 1 題）、**真計分器**、**真 bridge**、**真 pipx 裝的 Vacant wheel**（C 組）、**真 pi TUI（tmux）**、
  真 bwrap／每格新 Linux 使用者、真 orproxy，從 `build_bundle → deploy → vm_selfcheck → launch_i1001.sh（--phase auto）` 整條走完：
  篩選（12 段 A）→ 天花板決定（dabench 9/10 被丟掉）→ 主跑 5 個單位（A、C、R、K 共 20 格＋1 組 void 重跑）→ packer／finalize／鏡像 → 本機同步與自動關機（假的 colab）→ 分析。
- 逐項核對 `verify_e2e.py`：**最終程式碼 210／210 通過**（第 2 次與第 4 次跑；第 4 次是定稿程式碼）。第 1 次跑抓到 5 項失敗，全部是真缺陷（第六節），已修。
  驗證器本身有負控制：對紀錄做 9 種破壞（改 judge 退出碼、改送回次數、改逾時旗標、改 R 的 session 數、改 A 的成績、pane 少了打字、manifest 摘要壞掉、鏡像 chunk 壞掉…）
  **9／9 被抓到**。
- 找到並修掉 **8 個缺陷**（第六節）；單元測試從 89 個到 98 個，新增的防線各做過「把修法拿掉測試就紅」的破壞測試（6／6 抓到）。

## 二、跟 Colab 不一樣的地方（讀結果時要帶著）

| | 本機端到端 | Colab 正式批次 |
|---|---|---|
| 模型 | 按格子編劇的替身（`e2e_stub.py`），經 `tag_front.py → orproxy → 替身` | vLLM，driver 直接打 orproxy |
| 每段牆鐘上限 `--agent-timeout` | **60 秒**（要在合理時間內撞到逾時） | 1800 秒 |
| 代理的重試等待 | `[1,1,1,1]`（次數同為 5 次嘗試；要在 60 秒內讓「5 通 500」透出去） | `[5,15,30,60]` |
| 位置數 | 4 | 32 |
| IDLE_S | 15 秒（**同正式批次**，沒縮短） | 15 秒 |
| 完成偵測的延遲分布 | 替身的（Vacant 送回 0.4 秒） | 沒量過（RUNBOOK 第七節-3） |
| 並行 C 組安裝（pipx，約 20 秒、每格 80 MB） | 要代理（`I1001_INSTALL_ENV`） | 直連 |
| bridge 的 `bwrap --proc /proc` | 這台機器直接可用（`bridge_shim=false`） | 可能要墊片（selfcheck 會量） |

## 三、設計：為什麼是這幾題、這幾種行為

- 子集 staged 樹（`local_e2e/build_e2e_inputs.py` 產生）：3 題 LCB（各有 repo 既有的手寫探針解，用真計分器驗過「對的過、錯的不過、沒寫不過」）＋
  dabench 真 `screen_sample` 的 10 題（替身讓 A 答對 9 題 ⇒ 剛好在 ≥9/10 的門檻上被丟掉）＋databench 1 題＋polyglot_py 1 題（篩選 n=1，不可能到 9 ⇒ 保留）。
  ⇒ `--phase auto` 在真的流程裡走過天花板規則，主跑＝「3 題 LCB＋每個保留題庫 1 題」＝5 單位。
- 替身要「按格子編劇」：A 與 C 同時開、R 與 K 同時跑，順序不固定，`smoke_stub.py` 按「第幾個對話」選行為會錯。orproxy 轉給上游時丟掉了網址的標籤，
  所以 pi 與代理之間放 `tag_front.py`（只把 `/t/<標籤>/` 寫進請求本文的 `user` 欄位，其餘原樣穿透；**Colab 上沒有這一層**）。
- 劇本（5 個單位；每格的標籤＝`<前綴>-<組>-<題庫>-<題>-s1[v2].n<第幾段>`）：

| 單位 | 題 | A（沒裝） | C（零設定 Vacant） | R（重試，巢狀在 A） | K（bridge 把關，巢狀在 A） | 要驗的路徑 |
|---|---|---|---|---|---|---|
| U1 | lcb_v2 | 第 1 次：前 **5 通請求 500**（超過代理的 5 次嘗試）⇒ void；v2 重跑：寫對 | 寫對 | 沒有重試的理由（R＝A） | judge **第 1 次就 accept**、release | infra_void→整條 A 線 v2 重跑；K 零回報就放行 |
| U2 | lcb_v1 | 寫錯、說做完 | 寫錯；**第 1 通請求被注入 1 次 500（被代理的重試吃掉）** | R＝A（有交件） | judge 退回(40)→就地新 session（帶可見檢查回報，括號貼上）寫對→accept→release | K 用「被放行的成品」計分、A 用第 1 段快照計分；單次 500 不 void |
| U3 | lcb_v3 | 讀完檔說「已寫好」但沒寫 | 同 A，但 **Vacant 送回**後寫對 | 第 2 段又 claim、第 3 段寫對 | 就地新 session 連續寫錯 2 次 ⇒ judge 退回 ×3 ⇒ **沒放行** | R 第 3 段救回；K 次數用完＝沒交；C 的送回與完成偵測 |
| U4 | databench | 讀了 goal.md 後**卡住**（撞 60 秒） | 同（撞 60 秒） | 逾時 ⇒ 在**複本**上重試，第 2 段寫對 | （任務題庫沒有可見驗收，不跑） | 逾時記錄（rc 124、不 void、照樣計分）；R 的逾時重試 |
| U5 | polyglot_py | claim | 寫對 | 兩次重試都 claim ⇒ 3 段都沒交 | （不跑） | R 次數用完；沒交 |

## 四、指令（可重現；`$S`＝scratchpad 的 `i1001/`）

```bash
cd /home/user/Vacant/ops/colab_interactive_20261001
# 0. 輸入（真題目的子集＋劇本＋預期；含參考答案，只落在 scratchpad）
python3 local_e2e/build_e2e_inputs.py --staged $S/staged --refs $S/src/ops/vacantrun/task_banks_20260927 \
  --probe-v12 ../gain/data/lcb_probe_solutions.json --probe-v3 ../gain/data/lcb_v3_probe_solutions.json --out $S/e2e --prefix t4
# 1. 打包＋佈署（跟 Colab 同一條：build_bundle.sh → deploy_i1001.sh；wheel＝目前 HEAD 的 vacant_network，內容與 HEAD 逐檔相同）
bash build_bundle.sh $S/e2e/staged_e2e $S/e2e/vacant_network-0.8.0-py3-none-any.whl $S/e2e/deploy_i1001.tgz
mkdir -p /root/deploy && tar -xzf $S/e2e/deploy_i1001.tgz -C /root/deploy && bash /root/deploy/bin/deploy_i1001.sh g4 http://127.0.0.1:18000
# 2. 三個服務：替身(18000)、tag_front(18950)、orproxy(18900；重試等待縮短)
bash local_e2e/e2e_services.sh start $S/e2e/stub_script.json $S/e2e/run4
# 3. 發射前冒煙（7 情境）；launch 要它 ok
export I1001_INSTALL_ENV="HTTPS_PROXY=… HTTP_PROXY=… PIP_CERT=/opt/eval/ca-bundle.crt SSL_CERT_FILE=/opt/eval/ca-bundle.crt REQUESTS_CA_BUNDLE=/opt/eval/ca-bundle.crt NO_PROXY=127.0.0.1,localhost"
python3 /opt/eval/bin/vm_selfcheck.py --wheel /opt/eval/wheel/vacant_network-0.8.0-py3-none-any.whl     # 7/7
# 4. 發射（--phase auto；只多了 --agent-timeout 60 與 --proxy 指向 tag_front）
bash /opt/eval/bin/launch_i1001.sh t4 4 2026-10-02T23:00:00Z $S/e2e/mirror_drive4 --agent-timeout 60 --proxy http://127.0.0.1:18950
# 5. 續跑測試：主跑中途 SIGKILL driver（等 U1 的 void 重跑完成、至少 4 格 DONE、還有進行中的格子），中途打包一次，用 driver_cmd 重啟
python3 local_e2e/kill_resume.py --prefix t4 --min-done 4 --snapshot $S/e2e/run4/kill_snapshot.json --interim-pack $S/e2e/mirror_drive4 \
  --restart-cmd-file <(echo "bash /srv/eval/driver_cmd_t4.sh") --require-done t4-A-lcb_v2-lcb_3594-s1v2 --require-done t4-K-lcb_v2-lcb_3594-s1v2 --require-done t4-R-lcb_v2-lcb_3594-s1v2
# 6. 逐項核對
python3 local_e2e/verify_e2e.py --expect $S/e2e/expect_scenario.json --stub-log $S/e2e/run4/stub_requests.jsonl \
  --mirror $S/e2e/mirror_drive4 --out verify.json --kill-snapshot $S/e2e/run4/kill_snapshot.json
# 7. 本機同步＋自動關機（真的 sync_i1001.sh／autostop_i1001.sh，假的 colab：把「VM」當成這台機器）＋分析
export COLAB=$PWD/local_e2e/fake_colab.sh FAKE_COLAB_LOG=/tmp/fake_colab.log
bash sync_i1001.sh i1001 $S/e2e/local_raw4 1 --once && bash autostop_i1001.sh i1001 $S/e2e/local_raw4 --max-loops 1 --interval 1
python3 analyze_i1001.py --chunks $S/e2e/local_raw4 --out $S/e2e/analysis4 --prefix t4
```
總時間（第 4 次跑）：篩選 12 段 60 秒；主跑（含 kill／重啟）約 3.2 分鐘；DRIVER_DONE 後 46 秒 `PACKER_DONE`＋`MIRROR_OK`＋`ALL_DONE`。每段正常 session 牆鐘 18.7–23.3 秒（IDLE_S 15 秒占大宗；footer 0.6–1.5 秒出現；Ctrl-D 退出 0.22–0.44 秒）。

## 五、觀察到的結果（定稿程式碼，第 4 次跑；`evidence_local_e2e/run4_final/`）

### 每個單位、每一組（逐格；括號是 verify_e2e 的核對項）

| 格 | 觀察到 |
|---|---|
| 篩選 12 段（A） | dabench 9/10（唯一答錯的是替身指定的那題）⇒ **丟掉**；databench 1/1、polyglot 0/1 ⇒ 保留；12 格全 DONE、無 void。主跑計畫＝3 LCB＋databench＋polyglot＝5 單位，A 在主跑**重新跑**（沒重用篩選的 A） |
| U1 A 第 1 次 | `void: proxy_non200`（帳本有 1 筆 status 500、`attempts=5`）；R、K 同標「group void」；driver 記**恰好 1 筆** `infra_void_rerun`；A／R／K 以 `s1v2` 重跑、非 void |
| U1 A v2／R v2／K v2／C | A 過；K：judge 第 1 次 accept（rc 0）、release 成功＋讀回、1 段、放行的檔與 A 的逐位元相同（沿用 A 的成績）；R＝A（不重試）；C 過、0 次送回、**模型呼叫數與 A 相同（4）** |
| U2 | A 寫錯 ⇒ 不過（第 1 段快照）；K：judge `[40, 0]`、2 段、**放行的成品通過**（A 仍不過）、fix 文字＝同一句＋可見檢查原文、無責任措辭、括號貼上；R＝A；C 寫錯不過、單次 500 被代理吃掉（第 1 通 `attempts=2`、status 200、**不 void**） |
| U3 | A 沒交 ⇒ 不過；R：3 段 `[first, retry, retry]`、`retry_reasons=[no_deliverable×2]`、第 3 段救回 ⇒ **過**；K：judge `[40,40,40]`、3 段、**沒放行**、`delivered=False`、無 `released_artifact`；C：**Vacant 送回 1 次**（pane 上看得到 `[vacant-check] Before delivery: … The request asks for solution.py, but it does not exist…`）、之後寫對、第 2 次檢查通過 ⇒ 過；完成偵測在送回**之後**才判完成（送回後有 2 則 assistant、最終 stop 之後沒再寫東西） |
| U4 | A、C 都 `timeout=True`、rc 124、`done_reason=timeout`、牆鐘 62.4 秒（上限 60＋收尾）、**不 void**、照樣計分（沒交⇒不過）；R：`retry_reasons=[timeout]`、2 段、在 A 最後工作區的**複本**上寫對 ⇒ 過，A 仍不過；沒有 K 格 |
| U5 | R 3 段都沒交 ⇒ 不過、非 void；A 沒交；C 過 |
| 每一段 session（共 30 段：篩選 12＋主跑 18；另有 U1 A 第 1 次那 1 段是 void） | footer 出現後才打字、`typed_ok`、pane 有打進去的那句與 agent 的輸出（最終 assistant 文字在 pane 上）、timeline `ready→enter→change…`、`idle_final` 後 Ctrl-D 乾淨退出（rc 0，0.2–0.45 秒）、結束後 session 檔沒再被寫、沒有殘留行程 |
| 帳本對得上 | 每段非逾時、非 void 的 session：帳本通數＝模型端在該段起跑之後服務的非錯誤請求數（含被殺後重跑的格子） |
| 續跑 | driver 在 U2、U5 進行中被 SIGKILL（6 個進行中的格子目錄、12 個殘骸行程）；重啟時 `startup sweep` 殺 3 個 tmux、刪 4 個使用者、清 5 個 /srv/runs 目錄；kill 前已 DONE 的 14 格 `meta.ended` 都沒變（沒重跑）；6 個殘骸格搬到 `cells_aborted/` 並從頭重跑出新的 DONE 格；全程沒有任何一個 (組, 單位) 有兩個非 void 的最終格 |
| 打包 | `MANIFEST.tsv` 3 個 chunk（中途打包 1 個＋收尾 2 個）、每個 chunk 的 sha256 與 `.sha256` 檔、manifest 一致、大小對；**每個 DONE 格剛好在一個 chunk 裡**（34 格，無缺無重）；chunk 裡沒有私鑰（`*.key`）；鏡像（Drive 的替身目錄）每個 chunk 逐位元相同＋ MANIFEST；`MIRROR_OK`、`ALL_DONE` |
| 本機同步／關機 | 真的 `sync_i1001.sh`：3 個 chunk 驗過 ⇒ `SYNC_ALL_DONE`；真的 `autostop_i1001.sh`：`DRIVER_DONE＋PACKER_DONE＋最後一個 chunk 本機已驗` ⇒ 呼叫 `colab stop`（假的，只記一行） |
| 分析 | `analyze_i1001.py` 讀 chunk：K 對 R、C 對 A 的配對數（3、5）、各組通過數（A1／C3／R3／K2）、void 排除與逐題庫表都與劇本預期一致 |
| 清理 | 結束時沒有 cell／score 使用者、沒有 tmux server、沒有 pi 行程、`/srv/runs` 空 |
| 另一條路徑：時限已過 | 用過去的 `--deadline` 發射（前綴 t3）：「stop file / deadline: no new units」、天花板決定＝未完成篩選的題庫「undecided、保留」、只有 `_run_t3` 一格、`DRIVER_DONE`→chunk→`MIRROR_OK`（5 chunk）→`ALL_DONE` |

### 逐項核對的數字
`verify_e2e.py`：第 2 次 210／210、第 4 次 210／210（`evidence_local_e2e/run4_final/verify_run4.json`）；第 1 次 188／193（5 失敗，`run1_defects_found/`；當時驗證器只有 193 項，後來為了「帳本對得上」「timeline」「清殘骸」又加了 17 項）。

## 六、找到並修掉的缺陷

| # | 現象（怎麼發現） | 根因 | 修法 | 防線 |
|---|---|---|---|---|
| F1 | 第 1 次跑：databench 篩選 A 判 0/1，databench 的 R、C 全判沒過 | 重用的任務題庫計分器把**任何例外**收成 `pass:false, note:scorer_error`；圍牆裡的使用者 import 不了 pandas 的依賴 dateutil（只裝在 root 的 user site）⇒「計分環境壞了」被記成「agent 答錯」，連天花板規則都會被誤導 | `tui_cell.parse_score` 把 `scorer_error` 擋成 None ⇒ 該格 void（原因 `scorer_error: …`）；`deploy_i1001.sh` 改用 `runuser -u nobody -- env -i …` 檢查 pandas／numpy（舊檢查用 root、看不到問題） | `test_scorer_error_is_infra_not_an_agent_failure`；deploy 在缺依賴時 exit 5（實測先紅後綠） |
| F2 | 第 1 次跑：driver 被 SIGKILL 後 12 個殘骸行程、5 個使用者、`/srv/runs` 殘留；重啟後**同一格用同一個代理標籤**重跑，殘骸 pi 仍在打模型——帳本與模型端計數被兩個對話混在一起 | driver 沒有「一個 eval 根只能有一個 driver」與啟動清殘骸 | `driver_i1001.py`：`driver.lock`（flock，第二個 driver 退出碼 4）＋啟動時 `tui_cell.sweep_orphans`（殺這個工具的 tmux server、刪 `a/s＋6位數` 使用者、清 /srv/runs 的格子目錄；日誌 `startup sweep:`、progress 事件 `startup_sweep`） | `test_sweep_orphans_…`、`test_driver_refuses_a_second_instance_…`；續跑檢查 `resume: the restarted driver swept…` |
| F3 | （F2 的第二半）被殺那一次的帳本列還在，重跑那次用同一個標籤 ⇒ 通數翻倍、上一次的 5xx 會把重跑判成 void | `LedgerTail.stats(tag)` 不分時間 | `stats(tag, since)`／`final_stats(tag, since)`：只算請求時間 ≥ 該段 session 起跑時間的列；`run_session` 全部改用 | `test_ledger_since_ignores_an_earlier_incarnation_of_the_same_tag`；`ledger` 核對（帳本通數＝模型端服務數） |
| F4 | 第 1 次跑：chunk 裡有 `cells/<C 格>/vacant_home/intake/keys/*/identity.key`（4 把私鑰） | `vacant_collect` 用 `cp -a ~/.vacant`，把 C 組使用者的 Vacant 私鑰一起帶進紀錄（會進 Drive 與本機備份）；專案規矩（RECORD_SPEC §7）是打包不留私鑰 | `copy_vacant_home`：複製時略過 `*.key`（公鑰與 `vacant_id` 留著） | `test_vacant_home_copy_drops_private_keys_but_keeps_the_rest`；`pack: no private key file inside any chunk` |
| F5 | 發射紀錄寫 `agent_timeout_s: 1800`，但這次 driver 用 `--agent-timeout 60` | `launch_record.py` 把固定變數寫死成常數 | 固定變數取自**實際傳給 driver 的參數**（另記 `idle_s`、`max_units`、`driver_extra_args`）；`launch_i1001.sh` 把額外參數轉給它 | `test_launch_record_fixed_variables_come_from_the_driver_args_not_from_a_constant` |
| F6 | driver 被殺之後**沒有文件的重啟程序**；`launch_i1001.sh` 重跑會把進度檔搬走、再起一組 packer | RUNBOOK 沒寫、driver 指令沒存檔 | `launch_i1001.sh` 把 driver 指令存成 `/srv/eval/driver_cmd_<前綴>.sh`；RUNBOOK 第五節-7（重啟、鎖、清殘骸、`cells_aborted/` 不在打包範圍） | 本機端到端用它重啟（續跑檢查） |
| F7 | 我殺掉一個跑到一半的 selfcheck 後再跑一次：k 情境的 A 「寫對了」（劇本是先寫錯）——新的替身綁不上埠，`wait_port` 因為**舊的替身還在聽**而成功，整個情境在跟舊腳本的舊替身講話 | `vm_selfcheck.Servers` 沒確認埠是空的 | 起替身／代理前先 `assert not port_in_use(...)`（訊息指出是殘留的行程） | 實測：舊替身殺掉後 7/7；這個檢查本身沒有單元測試（需要真的佔埠；留在 selfcheck 的 assert） |
| F8 | 篩選沒跑完（時限已過）時天花板理由寫「A passed 0/1 … 0 unsolved task(s) seen」，看起來像跑過 | 理由字串沒提「沒跑」 | 理由加上「N screened task(s) were not run (stop/deadline)」（決定不變） | 既有 ceiling 測試仍綠 |

另：踩到兩次 `pkill -f`／`pgrep -f` 殺掉呼叫它的 shell（指令列比對會比到自己）——`e2e_services.sh` 改用 /proc 掃描。

## 七、仍然沒驗過的事（本機端到端也驗不到）

1. **真 vLLM 的行為與延遲**：IDLE_S＝15 秒是否足夠（真模型下「最終 stop → 下一個條目」的間隔分布、自動壓縮）；真 gemma 在這 133＋題上的表現。
2. **bridge 的 `bwrap --proc /proc` 在 Colab 核心上**（本機直接可用；墊片只用「會拒絕 `--proc` 的假 bwrap」驗過）。
3. **Colab 的 tmux／apt 版本、`/content`、Drive 掛載**（鏡像只用本機目錄代替；`MIRROR_OK` 的邏輯驗了，Drive 的 I/O 沒驗）。
4. **32 位置的並行與負載**（這裡 4 位置；慢解的 60 秒計分時限在 G4 上的判決取決於機器速度，STAGING.md 已記）。
5. **信任對話框**（`Trust project folder?`，Down×4＋Enter）：這個題池的工作區（含 bridge 寫的 `.vacant/contract.json`）在本機 31 段 TUI 裡**一次都沒觸發**（`trust_dialog` 全 null），所以按鍵沒有被驗過、也不會在這批用到。
6. **整台 VM 被回收**後的續跑（RUNBOOK 第五節-7：只剩 Drive 鏡像）。
7. 真的 `colab` CLI（sync／autostop／cu_guard 只用假的驗過邏輯）。
8. C 組在真模型下 Vacant 的行為（替身只驗了「說做完卻沒寫」這一種送回）。

## 八、檔案

- 程式：`local_e2e/{e2e_stub.py,tag_front.py,build_e2e_inputs.py,e2e_services.sh,kill_resume.py,verify_e2e.py,fake_colab.sh,leak_scan.py}`；
  修在 `vm/{tui_cell.py,tui_lib.py,driver_i1001.py,launch_i1001.sh,launch_record.py,deploy_i1001.sh,vm_selfcheck.py,plan_builder.py}`；測試 `tests/test_colab_interactive_20261001.py`（98 個）。
- 證據（只有數字與格子名稱，無題目內容）：`evidence_local_e2e/`（`run1_defects_found/`、`run4_final/`、`run3_deadline/`、`selfcheck_final.json`）。
- 原始紀錄（pane、session、劇本含參考答案）在 scratchpad `i1001/e2e/`，**不進 repo**。
