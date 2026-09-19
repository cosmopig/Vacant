# DECISION 2026-09-20：收據上看得出「這一跑有沒有在圍牆裡跑過」了

**回答**：`DECISION_20260920_COMPLETE_MEDIATION.md` §二 P0 的**另一半**
（機制那一半已經量完：`DECISION_20260920_ENCLOSURE_MEASURED.md`）。
在這一份之前，enclosure **只產生資料不產生宣稱**——收據上一個相關欄位都沒有。

**一句話**：`enclosure` / `framework_hook` / `reconciled` / `tier` 四個欄位落地、
**簽進簽章鏈**、每一格都配負控制在**真的圍牆裡**量過；
⇒ **「這一跑有沒有在圍牆裡跑過」現在看得出來**，新口徑可以講，**但有效範圍見 §四**。

---

## 〇、程式在哪

| 檔 | 承重什麼 |
|---|---|
| `vacant_network/vrun/attest.py` | 四個欄位的探針、對帳、分級（A／B／B′／C）、三態防呆 |
| `vacant_network/vrun/hookcli.py` | 掛鉤契約 `vacant-hook/1` 的唯一落地點 ＋ canary |
| `vacant_network/vrun/launcher.py` | 認證**簽進 `ws_verdict`**（`tier`／`attested`／`attestation_sha256`…） |
| `vacant_network/vrun/gateshim.py` | 退出碼 `24`／`25`／`26`、`VACANT_ATTEST` 三模式、C 級拒發收據 |
| `vacant_network/vrun/verify_receipts.py` | `attestation_of()`、`--require-tier`（**預設關**） |
| `ops/vacantrun/enclosure_20260920/run_attest.sh` | 四組（含三個負控制）的實跑 |
| `tests/test_vrun_attest.py` | 47 格可執行防呆 |

---

## 一、Linux 實跑（vacant-dev，2026-09-20，上游 1003）

`bash ops/vacantrun/enclosure_20260920/run_attest.sh` ⇒ **`fail=0`（13/13）**。
四組跑在同一台機器、同一分鐘、**同一支探針**，唯一的差別就是那一個變因。
證據：`ops/vacantrun/enclosure_20260920/evidence/attest_20260920/`。

| 組 | tier | applied | ns_id | canary | relay | hook_ev | unexplained |
|---|---|---|---|---|---|---|---|
| `noenc`（**負控制**：不套 enc.sh） | **C** | **false** | `net:[4026531840]` | null | null | null | null |
| `enc` | **A** | true | `net:[4026532736]` | true | 1 | 3 | **0** |
| `nohook`（**負控制**：掛鉤拆掉） | **B** | true | `net:[4026532736]` | **false** | 0 | null | null |
| `rogue`（**負控制**：多一通沒有工具事件的） | **B** | true | `net:[4026532736]` | true | 2 | 3 | **1** |

`policy_sha256` 兩面驗：圍牆裡讀到的 == 主機上那一份（`9080c1e1…`），
且**換一份政策就換一個雜湊**（enc `9080c1e1` ≠ nohook `a6b4bc6f`）
——不然「對得上」有可能只是常數對常數。

---

## 二、量具說謊，兩個，都是負控制抓到的（第 20、21 個案例）

1. **`session_start` 被算成「一個回合額度」⇒ 對帳假陰性。**
   `rogue` 那一格**真的**多打了一通，第一版對帳卻回 `unexplained=0`：
   `session_start` 與 `canary` 都被當成回合開端，於是多出來的那一通被
   `session_start` 的空額度吸收掉。⇒ `TURN_OPENING_EVENTS` **拿掉
   `session_start`**（它不會自己引起一通模型呼叫）。
   ⚠ 代價：沒有 `user_prompt_submit` 這一類事件的框架（OpenCode 的 plugin
   API）**第一通會對不上** ⇒ 那個 agent 在補上對應事件之前到不了 A 級。
2. **canary 那一通打在事件寫下來之前 ⇒ 對帳假陽性**（canary 自己變成
   `unexplained`）。⇒ `hookcli` 改成**先寫 `canary`、再打、再寫
   `canary_result`**。順序是規格不是風格。

另外兩個在腳本這一側：`enc.sh` 每跑一格就重寫一次 `policy.json`
（bwrap 參數含工作區路徑）⇒ 收工才 hash 抓到的是**最後那一格的**；
以及圍牆裡少 ro-bind 一個目錄時 `bwrap` 只印 `No such file or directory`
而外層 `rc=0`。

---

## 三、明講的偏離（**要人類／Fable 裁的那一格**）

裁決 §二 P0 原文：「任一不成立 ⇒ 收據寫『未認證』、**退出碼不是 0**」。

本實作 `VACANT_ATTEST` **預設 `warn`**，不是 `fail`：

| 值 | 收據 | 退出碼 |
|---|---|---|
| `off` | `tier=null`＝**沒量到** | 不受影響 |
| `warn`（**預設**） | `attested:false` ＋ `tier` ＋ 那一級能說的那句話＝**未認證** | **不受影響** |
| `fail` | C 級**拒發收據**（改落 `NOT_CERTIFIED.json`） | B→24、B′→25、C→26 |

理由兩條，都不是偷懶：

1. 沒有 root 的 macOS **永遠**到不了 A 級（沒有 bwrap） ⇒ 預設 `fail` 等於
   今天起 macOS 上每一跑都拒發收據，那是產品層級的停擺，而裁決講的是展場那條線。
2. 它會動到既有退出碼的實際行為，而本輪驗收第 6 項明文禁止。

⇒ 「未認證」那一半**照做**（`warn` 之下沒有人讀得成「這張是認證過的」）；
「退出碼不是 0」那一半**要明講才打開**。
**展場的 profile 必須 `VACANT_ATTEST=fail`**，驗章器那一側用
`--require-tier A`（同樣預設關，否則 98 個歸檔 run 會整批改判）。

---

## 四、口徑：可以講什麼、不可以講什麼

**可以講**（每一句都對應一個量到的欄位）：

> 這一跑的收據上寫著它在哪一個 network namespace 裡跑、用的是哪一份圍牆政策
> （sha256）、框架掛鉤有沒有真的燒起來、中繼看到的通數與工具事件對不對得上，
> 以及由這三件事**量出來**的級別。A 級的那一跑，
> **每一通模型呼叫都經過 Vacant，而且都對得上一個工具事件**。

**不可以講**：

1. **「不會被繞過」** ——圍牆外面跑的 agent 什麼都連得到；本份一個字都沒改變那件事。
2. **「這個 agent 是 A 級」** ——級別是**這一跑**的屬性，換一台機器就換一級。
3. **「掛鉤裝了所以在」** ——`canary_fired` 只證明**這一次**燒了。
   `--bare`／`disableAllHooks`／Codex 的 `trusted_hash` 改一個空白就 fail-silent。
4. **「`unexplained=0` ⇒ 沒有人多叫模型」** ——對帳是**通數與次序**的對帳，
   抓得到「沒有任何工具事件卻多出一通」，抓不到「在一個合法的回合視窗裡多塞一通」。
5. **「探針擋得住偽造」** ——圍牆裡的探針防的是**我們自己的量具說謊**，
   不是「agent 偽造探針輸出」。後者要主機側自己讀 `/proc/<pid>/ns/net`
   （`--host-ns-of-pid`，已實作，**尚未接進 `run_attest.sh` 的判準**）。
6. **`applied=true` ≠ 「這台機器上不存在別的路」** ——它說的是「這個行程只有
   loopback 一張介面」。硬證據是 `ns_differs_from_outer`。

---

## 五、**沒做的那一半**（不要讀成做完了）

1. 🔴 **沒有任何一個 agent 框架的掛鉤真的燒過。**
   `run_attest.sh` 的 canary 是**直接呼叫契約**（`hookcli session_start`），
   證明的是「契約與兩個探針在真的圍牆裡會動」，**不是**「Claude Code／
   OpenCode／Codex 的掛鉤會燒」。安裝器只寫了 `claude` 與 `opencode` 兩份
   （`hookcli.INSTALLERS`），**兩份都沒有跟真 agent 跑過一次**。
   ⇒ 在那之前，真實世界的 agent 跑出來會是 **B 級**，不是 A 級。
2. `codex`／`pi`／`hermes` 的安裝器沒寫 ⇒ 那三個的 `canary_fired` 是
   `null`（沒量到）不是 `false`。
3. **`attestation` 的全文不在鏈上**，鏈上只有 `tier`／`attested`／
   `attestation_sha256`（`logbook.MAX_PAYLOAD_BYTES` 是 64 KiB 硬限制）。
   全文在 `run_<ARM>.json`，雜湊對得上才算數。
4. **macOS 這條線沒有圍牆**（pf-per-uid 那一格沒做）⇒ Mac 上永遠 C 級。
5. `--host-ns-of-pid` 實作了但沒接進判準（見 §四-5）。
