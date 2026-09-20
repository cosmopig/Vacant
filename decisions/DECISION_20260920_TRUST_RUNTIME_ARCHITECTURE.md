# DECISION 2026-09-20 — 從「事後判決器」走向可強制的出口：五層語彙與 Publisher

> 來源：人類 2026-09-20 提供的 deep research 報告
> （`~/Downloads/deep-research-report (4).md`，40,485 bytes，1170 行），
> 對照同日的 Fable 稽核（`DECISION_20260920_ABPI_MEDIATION_AUDIT.md`）與 abpi 那批實跑。
> **本檔只記已驗證的部分與決策；報告對外部系統的引述尚未直驗，見 §五。**

## 一、一句話

> **Vacant 已經能在 agent 行程結束後做獨立判決、留下簽章證據；
> 但預設還不是一個能保證「拒絕的交付物無法離開」的 enforcement boundary。**
> **`exit 20` 是一個需要呼叫者合作的協定，不是安全邊界。**

abpi 那批自己就是最乾淨的反例：`launcher.py:676` 判 `refused`、`:789` 回 20，
而 `abpi_cell.sh:112` **不看 rc 就 `cp solution.py`** ⇒ 7 個拒交格的檔案照樣被複製出去。

⇒ **agent 的 exit 是 verification point，不是 delivery point。
真正的 delivery point 是最後那個握有 copy／upload／push／write 能力的元件。**

## 二、✅ 採用：五層語彙（立刻改口徑）

不要再用「有沒有 gate」或 `PASS/FAIL` 描述。分成五層，**每一層各自宣告 coverage**：

| 層級 | Vacant 證明了什麼 | abpi 那批的狀態 |
|---|---|---|
| **Observed** 觀察到 | 我看到了某些行為／流量／artifact | ✅ 有（2755 則 assistant 全對得上錄到的回應） |
| **Decided** 判決了 | 我獨立判斷這份交付 PASS／FAIL | ✅ **有——22 格 rc=0 仍被判拒交，這是真成果** |
| **Withheld** 扣住了 | FAIL 的 artifact 沒有被 externalize | 🔴 **這批沒有** |
| **Mediated** 中介了 | agent 找不到未經 Vacant 的替代路徑 | 🔴 **預設沒有**（真後端還在 environ 裡） |
| **Attested** 認證了 | 上述事實不可竄改地綁到 artifact／policy／identity | ⚠ 部分（鏈驗得過，但 completeness 不夠） |

**展場那句話因此定為**（只到 Decided，不假裝到 Withheld）：

> ✅「Agent 自己以 rc=0 宣告完成；Vacant 在行程終止後，以獨立的驗收機制判為拒絕，並簽下拒絕收據。」
> ❌「被擋在出口／檔案沒有流出。」——**這批沒有任何東西被阻止離開。**

## 三、✅ 已實作（本檔連帶的改動）

**真上游位址不再進 agent 的環境。** `envmap.py` 新增 `UPSTREAM_ONLY_VARS`
（＝`UPSTREAM_VARS − REDIRECT_VARS`，**算出來不是手寫**），`build_child_env` 剝掉它，
`meta["stripped_upstream"]` 與金鑰分開記。
⚠ **陷阱**：`UPSTREAM_VARS` 裡有 5 個名字（`OPENAI_BASE_URL` 等）同時在 `REDIRECT_VARS`，
**整組剝掉會把中介本身拆掉**；差集算出來只剩 `VACANT_RUN_UPSTREAM_{OPENAI,ANTHROPIC}` 兩個。
測試 `tests/test_vrun_upstream_not_in_child_env.py` 五條，**含負控制**
（重現舊行為必須紅）。

⚠ 這修的是 **hygiene 不是 security**：拿掉變數擋不住 agent 用別的方法找到上游。
> **secret stripping 是 hygiene；network isolation 才是 security boundary。**

**收集器兩個量具洞**（同日、見稽核檔）：計分器逾時改記 `all_pass=False` 保留
`status=timeout`；V/GT needle 門檻 25→12 ＋ JSON-escaped 變體（42→85 個）。

## 四、決策：實作優先序

> **「真正的 publish gate」排在所有新 agent adapter 前面。**
> 現在最值得修的不是「Vacant 能不能看見更多」，而是
> **「Vacant 說 FAIL 時，到底有沒有任何東西真的依賴這個 FAIL」。**

| # | 做什麼 | 為什麼排這裡 |
|---|---|---|
| **P0** | **Publisher 能力分離**：agent 在 private workspace 產 candidate（無對外寫入權）→ verifier 判 → **只有帶有效 release attestation 才 publish**。安全性從「每個 harness 記得 `if rc=0`」變成「沒有 PASS token 就沒有 publish capability」。 | 這是唯一能讓「被擋在出口」變成真話的一層 |
| **P1** | **收據 coverage schema**：`requests_seen: 17` 要變成帶 `count_semantics: lower_bound\|exact`、`wire_quiesced`、`requests_indexed` vs `request_blobs` 的結構。規定 `wire_quiesced=false ⇒ completeness != complete`。 | 稽核實測 53 格磁碟 blob 多於索引，而收據說不出自己是下界 |
| **P2** | **substrate 取代 env 接線**：把 `block_egress.sh` 從「使用者另外 sudo 的 optional V3」變成 **runtime 本身的 invariant**（netns ＞ 專用 UID ＞ 同使用者 iptables）。 | 「有一個 proxy」≠ 完整中介 |
| **P3** | **三態全面 schema 化**：`all_requests_explained`／`all_tool_calls_observed`／`all_network_egress_mediated`／`artifact_externalization_blocked`／`upstream_identity_verified` 一律 TRUE／FALSE／**UNMEASURED**。 | 我們已經在做，要擴大成規格 |
| **P4** | adapter（Claude hook／Codex／pi／OpenCode） | **降級為 semantic enrichment，不是 root of trust** |

🔴 **口徑新增禁語**：把 hook／MCP／SDK guardrail 講成「root of trust」。
它們依賴 cooperative framework，只能當**語意增強**。

⚠ **`null` 的邊界要守住**：`lcb_3649` 那種「測試有效、程式真的跑、時間內沒完成」＝ **FAIL**。
真正的 `null/VOID` 保留給**基礎設施產不出有效判決**（verifier crash、測試檔缺失、證據損毀）。
`FAIL → UNKNOWN` 不只是低估錯誤率，**是改掉 gate 的語意**。

## 五、🔴 尚未直驗的部分（引用前必須補）

報告引述了五個外部系統作為先行研究：**GitHub Agentic Workflows（Safe Outputs／
Agent Workflow Firewall）、Docker Sandboxes（clone mode／credential proxy）、
Microsoft Global Secure Access MCP firewall、OpenAI Agents SDK guardrails、
AgentTrust／AIRGuard／ClawGuard、SLSA／Sigstore（VSA、Rekor）**。

**這些我一個都還沒直驗。** 依 CLAUDE.md §3（先行研究重要的理由是「**不能對觀眾說錯話**」）
與 `examples/archive_citations.py` 的三級落盤紀律（A 全文／B 僅摘要／人工核對引文，含 sha256），
**在進入展場文案或任何對外文件之前，這七項要先進 `參考文獻/_引用備份/MANIFEST.json`。**
拿不到也要記下拿不到。

⚠ 報告聲稱查的是 `cosmopig/Vacant` 的 **`main`**，而本輪工作在 `integrate/20260919`。
它對 `envmap.py` 的那條指控**我已逐行直驗為真**（而且比它說的更嚴重：
本檔第 15 行的誠實邊界句早就承諾了這個行為）。**其餘對本 repo 的指控尚未逐條驗。**

## 六、定位（採用，但先當內部用語）

> **Vacant is an external trust control plane for untrusted AI agents: it isolates
> candidate work, mediates privileged channels where coverage is enforceable,
> independently verifies deliverables, and grants a cryptographically attested
> release capability only to accepted artifacts.**

⚠ 這句話**目前還不成立**——`isolates`、`mediates`、`grants release capability`
三個動詞對應的正是 P0／P2 還沒做的部分。**當成目標寫，不當成描述講。**
展場口徑仍照 §二：只講到 **Decided**。
