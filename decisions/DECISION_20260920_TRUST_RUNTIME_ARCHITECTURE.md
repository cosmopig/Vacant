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

## 五、✅ 七項先行研究已直驗（2026-09-20 兩條線平行做完）

**43 筆一手來源全文落盤**（MANIFEST 236 → 279，folder `2026-09-20_附身先行研究`，
全部 `A_全文`、逐筆 sha256、引文以 `grep -F`／`pdftotext` 複驗）。
34 條主張：**3 條否證、4 條部分成立、其餘已驗證、零條查不到。**

### 🔴 否證一：**報告的招牌例子在預設組態下不成立**

報告把 GitHub Agentic Workflows 的 SafeOutputs 當成「這次事故的反教材答案」，
說「若 detection FAIL，workflow 停止，**沒有任何 external write 被執行**」。

**權限分離那半（A1–A4）逐條驗證成立**——agent job 只有 read-only token、
輸出 buffered 成 `agent_output.json`＋`aw.patch`、獨立 detection job、
scoped write job 才碰 API。GitHub 自家編譯產物 `q.lock.yml` 是活體佐證。

**但「FAIL ⇒ 不會寫出去」是假的**，三層一手證據逐層收緊：
- 參考文件：`threat-detection.continue-on-error` **預設 `true`**，
  「detection warnings/failures produce a caution notice **instead of blocking safe outputs**」
- 原始碼：`threat_detection_steps.go:264` `continueOnError := true`（註解自己寫 *permissive*）；
  `parse_threat_detection_results.cjs:510` 的 `mustFail` **只在** `agent_failure`／`parse_error`
  成立，偵測到威脅走 `core.warning` **不走** `core.setFailed`
- 編譯產物：`safe_outputs` 的閘門是 `needs.detection.result == 'success'`
  ——**看 job result 不看裁決 output**，而那個步驟帶 `continue-on-error: true`

⇒ **預設組態下偵測到威脅，PR／issue 照樣開出去。** 架構頁那句
「terminates before any writes are externalized」**只在 strict mode 成立**，
GitHub 官方文件在這一點上自相矛盾。
⚠ 誠實邊界：這是**讀碼＋讀編譯產物**的結論，**沒有實跑一次 gh-aw workflow**。

**這條直接回饋到我們的 P0**：`vrun/publish.py` 刻意**沒有** `--force`／
`skip_verify`／`continue_on_error`，而且有測試守著。gh-aw 留了那個逃生口，
於是預設就是不擋。**可以繞過的閘門在需要它的那天一定會被繞過。**

### 🔴 否證二：ClawGuard 有兩篇同名論文，而報告把別人的邊界安在它頭上

- `arXiv:2604.11790v2`（tool-augmented LLM agent 的 runtime security）與
  `arXiv:2605.06205v1`（**用 SDR 收電磁側通道**偵測 workflow 劫持）**同名但無關**。
  ⇒ **引用一律要帶 arXiv id。**
- 報告說「論文明說涵蓋不到繞路的 raw syscall／network path」——
  ClawGuard 全文 `syscall` **0 次**、`out-of-band` **0 次**（實際數過），
  而且部分反向：它的規則集明文涵蓋 outbound network destinations 與 shell-level exec。
  ⇒ **不可以說「論文承認擋不住」。** 那是我們的推論，不是論文的話。
  （AIRGuard 全文 `syscall` 也是 0 次，用詞是 `out-of-band tool execution`。）

### 🔴 否證三：D2 的出處錯了（主張成立但會被抓）

「output guardrail 無法倒轉已發生的外部 tool side effects」**逐字成立，而且官方寫得更完整**
——但**只在 JavaScript/TS 版文件裡**。Python 版對應段落把這句省掉了
（全文語料 5625 筆逐一 regex 掃過，`irreversible`／`cannot recall`／`outside control` 命中皆 **0**）。
⇒ **引用必須指 JS 版網址。**

### ⚠ 部分成立四條

- **gVisor 不是 gh-aw 的預設**（預設是 Docker container isolation）；MCP gateway 那句是條件句。
  AWF 防火牆本身**是**預設開。
- **SLSA G4** 是 `SHOULD` 不是 `MUST`。
- **VSA 欄位表**：報告點名的六項都在，但**三項其實是 optional**
  （`verifier.version`／`inputAttestations`／`timeVerified`），`policy.digest` 只是 SHOULD，
  而且**報告漏了兩個 required**：`resourceUri`、`verifiedLevels`。
  ⚠ 版本陷阱：`timeVerified` **v1.0 必填、v1.1 起選填**。
  ⇒ 照報告對齊收據 schema 會做出「以為必填的可省、真正必填的沒做」的東西。
  **本裁決的 `release.py` 因此是取其結構、自訂欄位**，不是照抄。
- **G7**：SLSA Provenance **v0.2** 曾經有 `metadata.completeness.*`（fail-closed），
  **v1.0 移除**搬去 `builder.id` 指向的散文文件，in-toto v1 也沒有。
  ⇒ 沒有可照抄的欄位，但**可以照抄語意**：VSA `dependencyLevels` 的三態
  （`None` ＝ *the verifier makes no claims*）＋ v0.2 的 fail-closed 措辭。
  **`model_wire` 與 `release.coverage` 已照此實作。**

### ✅ 驗證成立、而且對我們最有用的三件

1. **gh-aw 的 staged permission separation**——「它寫不了」而不是「我們不准它寫」。
   跟 `sandbox.py` 那句「最小 rootfs 之下那條通道**不可表達**」是同一招，
   只是做在**權限層**。`gateshim.py` 靠攔截＋退出碼，**打完整路徑就繞過**；
   權限層繞不過，因為 token 不在手上。
2. **Docker Sandboxes 全部五條成立**（microVM、clone mode 主機 repo 唯讀、
   direct mode 官方自承無邊界、credential 不以 env／file 進 VM）。
   ⚠ **可抄的是文件紀律不是機制**：Docker 在同一頁把兩個 opt-out 講明
   （OAuth `passthrough: true` 跳過 masking、SSH agent forwarding 預設開）。
   `wireproxy.py` 的 docstring 應該用同一種寫法把自己的 opt-out 列全。
3. **GSA MCP firewall 全部五條成立，而它的極限正是 enclosure 打的那一點**：
   升到 protocol primitive 層的代價是必須開 TLS inspection，**而升上去之後
   仍然看不到 stdio／local MCP**（官方原話）。
   ⇒ 展場可以講的一句硬話：**連微軟砸全球 SSE 邊緣做 MCP 防火牆，本機 stdio 那條路還是看不到**
   ——而 Vacant 的 enclosure（netns ＋ **mount ns**）打的正是「把本機那條路拿掉」。
   兩邊都有一手來源。

### ⚠ 一個跟 Vacant 目標直接衝突的反向事實

**gh-aw 的官方 engine 有 pi，沒有 OpenCode**
（OpenCode／Aider／Crush／Cursor／Kiro 是 "samples only … not officially supported"）。
記憶 `vacant-goal-possess-any-agent` 寫「OpenCode 與 pi 絕對一定要」——
**兩者在 gh-aw 的地位不同，不可混講。**

### ❓ 明講查不到的

- GSA MCP firewall 的**獨立 GA 公告查不到**（`whats-new` 回 404）。
  最硬的日期只有文件 `ms.date=2026-08-06` 與該檔唯一 commit `2026-08-06T21:28:35Z`。
  **它是 preview 不是 GA。**
- 五篇論文全是 arXiv preprint，`doi`／`journal_ref` 皆 `None`，**沒另查 DBLP／ACM／IEEE**。
  ⇒ **一律不可說「已發表於 X」。**
- 兩條線的 `WebSearch` 額度都在開始前／第一批就用罄（200/200），全程改 `curl` 直取一手來源。
  好處是每筆都是原件且落盤，**壞處是沒做過廣泛關鍵字掃描**。

## 六、定位（採用，但先當內部用語）

> **Vacant is an external trust control plane for untrusted AI agents: it isolates
> candidate work, mediates privileged channels where coverage is enforceable,
> independently verifies deliverables, and grants a cryptographically attested
> release capability only to accepted artifacts.**

⚠ 這句話**目前還不成立**——`isolates`、`mediates`、`grants release capability`
三個動詞對應的正是 P0／P2 還沒做的部分。**當成目標寫，不當成描述講。**
展場口徑仍照 §二：只講到 **Decided**。
