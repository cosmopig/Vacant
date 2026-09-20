# DECISION 2026-09-20 — abpi 那批的獨立稽核：中介是不是假象

> 稽核由 Fable 執行（**唯讀、零模型呼叫**），人類 2026-09-20 指示：
> 「去用 fable 調查在過程中是否真的都要被 vacant 監測到，有用到 vacant 不是假象」。
> 稽核者先確認 vacant-dev 上的 10 支 `vrun/*.py` ＋ `wrap_agent.sh` 與本機 HEAD `a500f9bb`
> **逐 byte 相同**，所以下引行號就是跑這批的那份碼。數字為獨立重算，非照抄 `abpi_report.py`。

## 判決

> **「每一通模型呼叫都經過 Vacant」在這批資料上 ⚠ 只在一個更窄的意義上成立。**
> **不是假象**——proxy 真的中介了每一通它看得到的呼叫，資料沒有造假。
> **但拿它講「每一通」是把 C 級收據當 A 級用。**

成立的：proxy 看到的那條對話 **沒有缺口**（391 格、2755 則 assistant 回合，每一則都對得上
proxy 自己錄到的某一個 200 回應，0 則對不上；相鄰請求 `messages` 嚴格前綴延伸
1332＋1444 次檢查 0 失敗）；零請求 0 格；收據鏈 195/195 驗過（負控制 `--selftest` 先 PASS）。

不成立的：沒有圍牆（391/391 `enclosure.applied=false`）、沒有出網封鎖
（`iptables -P OUTPUT ACCEPT`、`--sandbox none`）、沒有掛鉤。**「沒有別的通」沒有任何
獨立管道量過。** 391 格全是 **C 級**，`attested=false` 簽在每一張收據上。

## 🔴 四個會改口徑的發現

**1. `refused` 是標記＋退出碼，不是物理阻擋。**
`launcher.py:676` `"refused": not ok`、`:789` 退出碼 20、`:697-760` 簽 `accepted=false`
——**沒有任何一行動工作區**。交付物留在工作區，也留在 `_frozen_RUN-ON/`。
而本批 harness `abpi_cell.sh:112` `[ -f "$ws/solution.py" ] && cp …` **不看 rc**
⇒ 59 個拒交格裡**有檔案的那 7 格，檔案被複製出來進了事後計分**。
- ✅ 可講：「agent 自己退出碼 0 走人，出口那一關仍在行程結束那一刻判了拒交、簽了收據」（22 格）
- ❌ **不可講**：「被擋在出口／檔案沒有流出」。**這批裡沒有任何東西被阻止離開。**
  真的擋住要靠**讀退出碼的那一方**，而這批的那一方沒讀。

**2. 真後端位址寫在 agent 自己的環境變數裡。**
`envmap.build_child_env`（`envmap.py:472-507`）複製整個父環境、只剝 `SECRET_VARS`
（`:253-263`），而 `VACANT_RUN_UPSTREAM_OPENAI/ANTHROPIC` **不在名單上**。
實讀跑到一半的 pi 子行程 `/proc/<pid>/environ`：`OPENAI_BASE_URL=http://127.0.0.1:38109/v1`
（proxy）**與** `VACANT_RUN_UPSTREAM_OPENAI=http://100.86.226.21:1234/v1`（真後端）同時在。
pi 的 bash 工具一句 `curl $VACANT_RUN_UPSTREAM_OPENAI/...` 就繞過去，proxy 不會知道。
（實掃所有 request body 找 `100.119.113.56`／`100.86.226.21`／`VACANT_RUN_UPSTREAM`／`curl `：
 **0 命中** ⇒ 這批沒發生，但**路是開的**。）

**3. `requests_seen` 是下界，而且收據說不出自己是下界。**
ON 29 格／TEE 24 格磁碟上的 `*.req.bin` 比 `index.jsonl` 多 1–2 個，
**每一格都恰好 `wire_quiesced == false`**（排空逾時，交叉表零例外）。
多出的 79 個 body：47 個是逐 byte 重複（pi 對卡住的請求重送）、33 個是被 `-9` 砍那一刻在途的下一通。
全部都經過 proxy，所以不影響「有沒有經過」——但 `requests_seen` 與 `wire_digest`
（`launcher.py:620`，在 quiesce 之後算）**不含它們**，而 `wire_quiesced` 只在未簽章那一份、
`proxy.stats["quiesce_timeout"]`（`wireproxy.py:368-370`）**launcher 完全沒落盤**。

**4. 「每一通都對得上一個工具事件」沒有資格講——掛鉤根本沒裝。**
`abpi_cell.sh` 沒 export `VACANT_HOOK_LOG` ⇒ `wrap_agent.sh:106` 整段不執行
⇒ `canary_fired=null`、`reconcile()`（`attest.py:459-503`）在 `hook_events is None` 時
直接回 `unexplained=None`、`grade()` 要求 `== 0` 而 `None` 不滿足 ⇒ C 級。
**三態在資料上守住了**（沒有人把 null 當 0）。

## ✅ 稽核確認為真的

- **TEE 真的只記錄不裁決**：`wireproxy.py:463-464` 的 `RuntimeError("OFF/ON 都不准重序列化 body")`
  成立、`body_rewritten` 0/392、**同題同後端同重複的 ON/TEE 第一通 request body
  正規化後 193/193 逐 byte 相同**。TEE 與 ON 在 wire 上唯一的差別是索引裡的 `mode` 字串。
- 收據鏈：run 197、鏈 195、entries 390、驗過 390、失敗 0、壞鏈 0、mediated 195、零請求 0。
  `--require-tier A` ⇒ **195/195 BROKEN（got C）**——這是對的，不是壞掉。

## 兩個量具修法的複驗結果（已照做）

- **V/GT**：修法方向對，獨立以 JSON-escaped ＋空白折疊變體重掃 592 格**全部 0 命中**，
  in-memory 正控制會紅。⚠ **但 `len >= 25` 讓 hidden-only 短行不在量程內**
  （`lcb_3548` 77/83 行、`lcb_3779` 74/81 行看不見）⇒ 已降為 12 並加 JSON 變體
  （needle 42→85）。**結論寫成「整檔外洩 0 命中」，不是「V/GT 零外洩」。**
- **`lcb_3649` 三格逾時**：稽核判**是真失敗不是量具的洞**——`solution.py` 是
  `itertools.permutations` 的 n! 列舉撞上隱藏測資長輸入；同一隱藏檔對退化樁 0.0 秒回
  （26 cases）、同題其餘 12 格 120 秒內過、該解可見測資 2/2 秒過。
  ⇒ 已改記 **`all_pass=False` 且保留 `status=timeout`**（原本記 None ＝把真失敗寫成沒量到，
  而那一格還是閘門放行過的）。措辭用「600 秒（5× 限時）內不終止」。

## 🔴 BARE 的 null：誠實，但措辭要改

「沒量到」對；「**無管道可量**」說過頭了——1004 自己有 LM Studio server log
（`C:\Users\w401\.cache\lm-studio\server-logs\`）。只是跑的時候沒人接、三臂與 4 條 lane
從同一個 client IP 同時打**沒有 per-cell 標記無法歸屬**、且已輪替。
⇒ `meta.json` 的 `measurement_gap` 改成「**沒有接量測管道**」；下一批要量 BARE，
發射前加 per-cell 標記即可。

## 待辦（稽核指出、本檔不做——Fable 只稽核）

1. `VACANT_RUN_UPSTREAM_*` 要從子環境剝掉（`envmap.SECRET_VARS` 或另立名單）。
2. `wire_quiesced`／`quiesce_timeout` 要進收據，否則通數說不出自己是下界。
3. **展場的 cell runner 必須讀 rc=20**，否則「擋」只是一個欄位。
