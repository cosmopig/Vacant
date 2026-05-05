# T4: 多方 Attestation Bootstrap 研究

> **研究問題**：新建立的 trust network 如何從「沒有任何獨立 attester」的零狀態，逐步演進到「有足夠多可信 attester 的成熟狀態」？
>
> **對應問題**：THEORY_V3 §H4「多方 attestation 的『方』從哪來？」；P4_registry §3.2 Layer 3 N-of-M finalization。
>
> **方法**：codex CLI 深度分析（2026-05-01）+ WebSearch/WebFetch 交叉驗證。

---

## 0. 核心觀察（先說結論）

四個歷史案例的共同答案不是「一開始就去中心化」，而是：

> **先承認零狀態不可能憑空產生信任，再用既有 trust anchor、透明紀錄、可替換的 root metadata，把初始信任逐步降權。**

真正成熟的系統通常不是完全沒有中心，而是讓中心的錯誤變成**可偵測、可撤換、可被多方交叉檢查**。

---

## 案例 A：Let's Encrypt (2015-)

### Bootstrap 策略

Let's Encrypt 的 bootstrap 是典型「借用既有 Web PKI」。ISRG 自行產生 ISRG Root X1，但 2015 年剛開始時瀏覽器與作業系統尚未直接信任它。解法：由 **IdenTrust 的 DST Root CA X3 cross-sign** Let's Encrypt 的 intermediate chain。

IdenTrust 被選中的理由：**不是因為更去中心化，而是因為它已在主流 root stores 裡**，並已通過 WebTrust / browser root program 既有審核。因此初始 M 實際上是 **1 個強 trust bridge**。

### M 的演進路徑

| 時間 | M 狀態 |
|---|---|
| 2015-04（Launch） | M=1：IdenTrust DST Root CA X3 cross-sign，無獨立信任 |
| 2016 | Mozilla 接受 ISRG Root X1 直接信任 |
| 2018-08 | Microsoft 加入後，ISRG Root X1 被 Microsoft / Google / Apple / Mozilla / Oracle / BlackBerry 等**所有主流 root programs** 直接信任 [(Let's Encrypt 2018)](https://letsencrypt.org/2018/08/06/trusted-by-all-major-root-programs/) |
| 2021-09 | DST Root CA X3 到期；大多數裝置改用 ISRG Root X1 chain |
| 2024-02 | ACME API 預設不再提供 cross-signed chain |
| 2024-06-24 | 完全停止提供 cross-signed chain [(shortening chain, 2023)](https://letsencrypt.org/2023/07/10/cross-sign-expiration) |

**結論：從 M=1 cross-signer 到 browser root programs 直接信任，花了約 3 年；完全擺脫歷史 cross-sign，花了約 9 年。**

### ACME 的角色

RFC 8555 (2019) 把 domain control validation 標準化，讓大量獨立 domain holders 可自動證明控制權。Trust 因此從「IdenTrust 信 ISRG」擴展成：
- **Root programs** 信 ISRG 的 CA operation
- **ACME challenge** 信 domain control（domain holder 自動成為分散的 attester）

### 現代多方 attestation（SCT）

Chrome 現行政策要求 embedded SCT 至少來自 **N 個 distinct logs，且至少 2 個不同 log operators**：
- ≤ 180 天憑證：需 2 個 SCT
- > 180 天憑證：需 3 個 SCT

### 攻擊視角

| 攻擊者能力 | 效果 | 緩解 |
|---|---|---|
| 控制 IdenTrust 或 LE intermediate 私鑰（bootstrap 期） | 簽出受信任憑證 | Root program audit、短期 cert、自動撤銷、CT log |
| BGP / DNS / HTTP hijack ACME validation | 取得錯誤 DV cert | CAA record、ACME 多角度驗證、CT log |
| 污染 Let's Encrypt CA | 大規模 cert misissuance | CT monitor、revocation、browser root program 可移除 CA |

### 風險窗口

**2015–2018（約 3 年）**：若 IdenTrust 被攻陷或作惡，或 IdenTrust cross-sign 關係中斷，整個 Let's Encrypt 信任鏈崩潰。

---

## 案例 B：Sigstore / Fulcio / Rekor (2021-)

### Bootstrap 策略

Sigstore 不是從匿名社群開始，而是從**高聲譽組織背書**開始。2021 年 Linux Foundation 宣布 Sigstore，由 **Red Hat、Google、Purdue University** 領導；後續納入 OpenSSF 治理 [(Linux Foundation 2021)](https://www.linuxfoundation.org/press/press-release/linux-foundation-announces-free-sigstore-signing-service-to-confirm-origin-and-authenticity-of-software)。

初始 trust assumption：使用者相信這些組織的營運能力、Sigstore root-signing ceremony、TUF metadata，以及 Fulcio / Rekor Public Good Instance。

### Public Good Instance 運營

由 OpenSSF 管理，實際 on-call 來自 **Chainguard、GitHub、Google Open Source Security Team、Red Hat、Stacklok** 等多家公司；基礎設施在 GCP。這不是完全去中心化，但避免單人或單公司維運 [(OpenSSF 2023)](https://openssf.org/blog/2023/10/03/running-sigstore-as-a-managed-service-a-tour-of-sigstores-public-good-instance/)。

### TUF 根信任

Sigstore trust root 透過 **TUF (The Update Framework)** 分發；公開 TUF repository 顯示：
- Root / targets 由 **5 位 keyholders 中 3 位簽署**即可更新（3-of-5）
- keyholders 來自多組織 [(Sigstore root-signing)](https://github.com/sigstore/root-signing)

### Fulcio 的 Trust 來源

兩層：
1. Fulcio CA root 被 TUF 信任
2. Fulcio 簽發短效 code-signing certificate 時，依賴 **OIDC providers**（GitHub Actions、Google Workspace、Microsoft 等）証明身份

因此 GitHub Actions / Google / Microsoft 等 identity provider 成為「**身份 attester**」。

### Rekor 的 Witness 現況（2025-2026）

- 早期 M：單一 Public Rekor log operator + 外部 monitor（Purdue University + 社群）
- **目前沒有「Rekor checkpoint 必須由 N-of-M independent witnesses cosign 才被 client 接受」的強制政策**
- Rekor v2 (2025 GA) 改用 tile-backed log，timestamp 信任移向獨立 TSA；witness cosigning 在 tlog-witness spec 裡已定義但尚未強制 [(Rekor v2 GA)](https://blog.sigstore.dev/rekor-v2-ga/)
- witness-network.org 標示：**experimental / work-in-progress**，由「少數 community members」維護

### M 的演進路徑

| 時間 | M 狀態 |
|---|---|
| 2021（Launch） | M≈3-5：founding orgs（Google/Red Hat/Purdue）+ TUF 5 keyholders + 1 Rekor operator |
| 2023 | Multi-company ops、OIDC multi-provider（GitHub/Google/Microsoft）、Rekor monitor |
| 2025-2026 | TUF 3-of-5 root、Rekor v2 + TSA、witness spec ready but not enforced |
| 未來 | 計劃強制 checkpoint witness cosigning（公開 witness network 成熟後） |

### 攻擊視角

| 攻擊者能力 | 效果 | 緩解 |
|---|---|---|
| 控制 OIDC account / CI token | 簽出看似合法 artifact | 短效 cert、OIDC audience / issuer binding |
| 控制 Fulcio | 給錯身份的 cert | TUF 3-of-5 root、root program audit |
| 控制 Rekor | 短期隱藏 / equivocate log view | TUF metadata、Purdue monitor、domain owner monitoring |
| 控制 TUF keyholder（1-of-5） | 無效（需 3-of-5） | 多組織 keyholder |

---

## 案例 C：PGP Web of Trust (1991-)（反例）

### Bootstrap 策略

PGP 的 bootstrap 幾乎是**反例**。Zimmermann 1991 年發布 PGP 時，沒有 root CA，也沒有治理型 root program；key trust 來自人與人交換 fingerprint、key-signing party、朋友簽朋友的 key。M 理論上可無限增長，但實務上：

- 缺乏可操作的 identity verification
- 缺乏統一 policy
- 缺乏 revocation / discovery UX
- **簽章語意不一致**（Alice 簽 Bob 的 key 可能代表看過護照、只見過面、只是社交禮貌）

### SKS Keyserver 的問題

SKS 的 append-only gossip federation 對可用性有利，對 abuse resistance 很差。

**2019 certificate flooding attack (CVE-2019-13050)**：
- **攻擊者能力**：向別人的 OpenPGP certificate 附加大量垃圾 third-party certifications（无上限）
- **效果**：GnuPG 匯入或更新受影響 key 時嚴重降速、記憶體溢出，形成 DoS；Dirmngr / keyring 可能掛掉
- **受害者**：包含知名 OpenPGP 社群成員（Robert Hansen、Daniel Gillmor）
- **緩解**：Hagrid/keys.openpgp.org 選擇**不加入 SKS pool**、預設不發布 third-party signatures、要求 email consent

早在 1999 年的 *"Why Johnny Can't Encrypt"*（Whitten & Tygar, USENIX Security 1999）就指出 PGP usability 問題讓多數 novice 無法正確完成安全任務。

### WoT 仍有效的場景

**小型封閉社群**仍然有效：Debian key-signing、核心維護者圈、公司內部 release signing——因為身份驗證規則可被社群共同理解，M 數量可控。

### 對 Vacant 的啟示

| 問題 | PGP 的錯誤 | Vacant 應避免 |
|---|---|---|
| 任意第三方貼 metadata | 無上限 third-party sig → DoS | event_finalization 需要 attester 先是 registered vacant |
| 社交信任 ≠ 安全 attestation | key-signing party 語意模糊 | attestation 欄位 schema-strict、attester_kind 精確定義 |
| 無 revocation | key 一旦被污染難以清理 | revocation_list + freeze，歷史保留但 status 明確 |
| 去中心但無 abuse resistance | 攻擊者成本 ≈ 零 | 需要 attester 是 registered vacant（有 stake / reputation 代價）|

---

## 案例 D：Certificate Transparency Bootstrap (2013-)

### Bootstrap 策略

CT 的 bootstrap 也是先集中再分散。RFC 6962 (2013, Laurie/Langley/Kasper) 定義 append-only Merkle log、SCT、STH。Chrome 先要求 EV / Symantec CT，再於 2018 年對所有 2018-04-30 後 publicly trusted TLS cert **強制 CT**。

**從規格到強制執行：約 5 年。**

### Log Operators 演進

初始 log operators：Google、DigiCert、Cloudflare（這三家在 2013-2018 期間撐起了初期生態）。

Chrome log list (2026-04-19 版) 現含：
- **Google**（solera/2025h1, solera/2025h2, crucible 等）
- Cloudflare（nimbus2025 等）
- DigiCert（yeti/nessie 等）
- Sectigo (mammoth/sabre 等)
- Let's Encrypt (oak/2025h1, h2 等)
- TrustAsia、Geomys、IPng Networks 等
- **約 8 個組織、30+ 個 active log shards**（temporal sharding：每半年一個 shard）

### Chrome 的 N-of-M 政策

| cert lifetime | 要求 SCT 數量 | 要求 operator 多樣性 |
|---|---|---|
| ≤ 180 天 | ≥ 2 | 至少 2 個不同 operator |
| > 180 天 | ≥ 3 | 至少 2 個不同 operator |

這是 **N-of-M 的成熟化**：不相信某一個 log，而是要求 operator diversity。

### 攻擊視角 + 緩解

| 攻擊者能力 | 效果 | 緩解 |
|---|---|---|
| 控制 1 個 log operator，給自己 CA 假 SCT | 惡意 cert 通過 CT policy | MMD 內必須 merge、monitor 拉全量 log |
| Log operator 不 include SCT 對應 entry | 違約可被 auditor 抓 | Chrome 把 log 從 trusted list 移除 |
| Split-view（給不同 client 不同 STH） | 隱藏惡意 cert 直到被比對 | CT gossip、cross-monitor 比 STH |

### Sunlight / Static CT API（後期演進）

把 log storage 變成更容易 mirror、monitor、checkpoint 的 tile-based model。Chrome policy 接受 static-ct-api，static logs MMD ≤ 1 分鐘。這提高了**多方監控**的可行性——任何人都可以 mirror 整個 log 並做 inclusion proof 驗證。

Governance 仍由 Chrome / Apple Root Program 決定（Log Policy 文件）。

---

## 跨案例共通 Bootstrap 模式

### Primitive 1：借用既有 trust anchor

| 案例 | 借用的 anchor |
|---|---|
| Let's Encrypt | IdenTrust DST Root CA X3（已在 browser root store） |
| Sigstore | Linux Foundation / OpenSSF / Google / Red Hat（組織信譽）+ OIDC providers |
| CT | Chrome / Apple root programs（決定哪些 log 被信任） |
| PGP | **無 anchor**（失敗根因） |

### Primitive 2：用 transparency 補償 centralization

Rekor、CT log、ACME issuance audit 都承認初期會有中心，但**要求行為留下公開證據**。PGP keyserver 也公開，但沒有 abuse-resistant semantics，所以透明不等於安全。

**關鍵區分**：CT 要求每筆 cert 進 log（結構性強制），任何人可驗。PGP 簽章是自願的、語意模糊的、abuse-free 的。

### Primitive 3：把 root metadata 做成可輪替

| 案例 | 輪替機制 |
|---|---|
| Let's Encrypt | Browser root store（browser vendor 可移除 / 新增 CA） |
| Sigstore | TUF root（3-of-5 輪替）；log list 可更新 |
| CT | Chrome / Apple CT log policy（daily log list update） |
| PGP | WoT **沒有**，keyserver 污染難以清除 |

---

## M 的演進曲線對比

```
M（有效 independent attesters）
↑
10 ┤                                         CT log operators (stable)
   │                          ···············
 5 ┤          ············Sigstore TUF key·····
   │     ·Let's Encrypt root progs·
 2 ┤····Let's Enc IdenTrust cross-sign start
 1 ┤─────────────────────────────────────────────────────
   └────────────────────────────────────────────────────→ time
       Y0        Y3         Y5          Y10+
              (risk window)  (mature)
```

| 案例 | Bootstrap（M≈1-2） | Mature（M≥5） | 花了幾年 |
|---|---|---|---|
| Let's Encrypt | 2015（1 cross-signer） | 2018（browser root programs） | 3 年 |
| Sigstore | 2021（founding orgs） | 2025+（多公司 ops + TUF 3-of-5）；witness 還未完整 | 4+ 年（未完成） |
| CT | 2013（少數 Google/DigiCert logs） | 2018（8 operator，Chrome 強制）；2025 static logs | 5 年 |
| PGP | 1991（Zimmermann） | **從未達到**（大規模 Internet） | N/A |

**結論**：從 M≈1-2 到成熟多方，**現實案例都花了 3-5 年以上**。MVP 設計必須接受「bootstrap 脆弱窗口」而非試圖避免。

---

## M 小時（M=2-3）的攻擊向量

| 攻擊 | 需要控制 | 效果 |
|---|---|---|
| N-of-M quorum compromise（N=2, M=3） | 2 個 attester | 任意事件可被 finalize，包括偽造 reputation / capability |
| Root metadata hijack | bootstrapper 的 signing key | 替換整個 attester set |
| 選擇性 censorship | 1 個 attester + registry operator 配合 | 阻止特定事件被 finalize，讓合法 vacant 被封殺 |
| Timing attack | bootstrap 期間的規格窗口 | 在 attester 數不夠前快速 finalize 大量惡意事件 |
| Log split-view | Registry operator | 給不同 client 看不同歷史（直到 witness cosign 成熟才能防）|

---

## Vacant MVP 的具體建議

### N-of-M 初始值

**建議：MVP production policy 從 2-of-5 開始。**

推導：
- CT 案例顯示，2 individual SCTs 是實務可行的「最低多方」底線
- Sigstore TUF 用 3-of-5，但它的 5 個 keyholder 從一開始就有高聲譽組織撐
- Vacant MVP 初期生態較小，5 個 attester 是可招募到的現實目標
- 若只招到 3 個：用 2-of-3，但在 API 與 UI 上明確標注「bootstrap-limited-attesters」

**明示階段**：

| 階段 | 條件 | 客戶端顯示 | finalization policy |
|---|---|---|---|
| **Bootstrap Preview** | M < 5 或不滿 3 種組織類型 | `⚠ bootstrap-trust: limited attester set (M=N)` | 2-of-N（N 是當前 M） |
| **Bootstrap** | M ≥ 5，≥ 3 種組織類型 | `bootstrap-trust: M/5 attesters` | 2-of-5 |
| **Federated** | M ≥ 9，≥ 5 種組織類型，多 Registry | 正常顯示；individual event proof 可查 | 3-of-9（reputation-weighted） |

### Trusted Bootstrapper 的角色類型（優先序）

| 類型 | 角色 | 備注 |
|---|---|---|
| **中立開源基金會**（OpenSSF 類） | Root metadata steward | 不持 root、是 governance structure |
| **大學研究單位**（CMU / 成大 / MIT 等） | Audit / monitor / adversarial review | 學術公信力；不是商業利益方 |
| **Agent framework vendor**（Anthropic / Google DeepMind / Microsoft 等） | Ecosystem attester | 可 1-2 家；不應超過 N-of-M quorum 的 majority |
| **獨立 supply-chain / security org**（如 Chainguard、Purdue Sigstore 等） | 技術 monitor | 補充技術深度 |

**原則**：vendor 可以當 attester，**不應單獨持 root**；任一單一 vendor 不得在 N-of-M 中佔 ≥ 1/N 的 quorum 位置（CT 的教訓：一開始 Google 佔多數 log，這是已知風險）。

### 脆弱期公示設計

**建議公開定義脆弱期為：啟動後 90 天，或直到達成 M=5 後連續 30 天（以較晚者為準）。**

公示機制：
1. Registry `/v1/epoch_root/latest` 回傳 `attester_set_size` + `bootstrap_phase: true/false`
2. 客戶端 SDK 在 bootstrap_phase=true 時顯示 banner
3. `GET /v1/attesters` 公開列出當前 attester 組織名、類型、加入時間（公開透明）
4. Monitor API 允許任何人追蹤 attester 加入 / 退出事件

### 第一個 Milestone（「攻守易勢」事件）

> **M=5 independent attesters、至少 3 種組織類型、2-of-5 client enforcement、公開 transparency log、2 個以上外部 monitor（至少 1 個學術單位）、root metadata 可輪替。**

達成後：
- 把 bootstrapper 從 signing threshold 中移除或降為普通 attester（不需強制遷移）
- 更新 TUF-style root metadata，移除 bootstrapper 的特殊地位
- 公開宣布脫離 bootstrap_phase

這參照 Let's Encrypt 的「有機替換」模式：IdenTrust 的重要性在 browser root programs 直接信任 ISRG Root X1 後**自然降低**，不是被強制移除的。

### 「有機替換」的具體機制

```
bootstrapper 重要性衰減曲線：

    bootstrapper 的角色
    ↑
100%│▓▓▓▓▓▓▓▓▓▓▓
    │          ▓▓▓▓
 50%│              ▓▓▓▓▓
    │                   ▓▓▓▓▓
 10%│                        ▓▓▓▓▓▓▓▓▓▓▓▓▓ (退為 1 票)
    └────────────────────────────────────→
        Launch  M=5達成  M=9達成   分散化
```

機制：
1. root metadata 中，bootstrapper 的 key 可被 governance vote 移除（透過 TUF root threshold 更新）
2. 客戶端軟體在拿到 N 個非 bootstrapper 的 attester cosign 後，可選擇不再信任 bootstrapper 簽章
3. bootstrapper 的角色轉換為 audit / monitor 而非必要 attester

---

## 總引用

### Let's Encrypt
- Let's Encrypt (2018) *Trusted by All Major Root Programs* — letsencrypt.org/2018/08/06
- Let's Encrypt (2021) *DST Root CA X3 Expiration* — letsencrypt.org/docs/dst-root-ca-x3-expiration-september-2021
- Let's Encrypt (2023) *Shortening the Chain of Trust* — letsencrypt.org/2023/07/10/cross-sign-expiration
- RFC 8555 (2019) *ACME: Automatic Certificate Management Environment*
- Let's Encrypt (2024) *Chains of Trust* — letsencrypt.org/certificates/

### Sigstore
- Linux Foundation (2021) *Sigstore Press Release*
- OpenSSF (2023) *Running Sigstore as a Managed Service*
- Sigstore root-signing: github.com/sigstore/root-signing
- Newman Z., Meyers J., Torres-Arias S. et al. (CCS 2022) *Sigstore: Software Signing for Everybody*
- Sigstore Blog (2025) *Rekor v2 GA* — blog.sigstore.dev/rekor-v2-ga/
- C2SP tlog-witness spec — github.com/C2SP/C2SP/blob/main/tlog-witness.md
- transparency-dev/witness — github.com/transparency-dev/witness

### PGP / WoT
- Whitten A., Tygar J. (USENIX Security 1999) *Why Johnny Can't Encrypt*
- Hansen R. (2019) *SKS Keyserver Network Under Attack* — gist.github.com/rjhansen/67ab921ffb4084c865b3618d6955275f
- CVE-2019-13050: Certificate Spamming Attack Against SKS Keyservers
- keys.openpgp.org FAQ — keys.openpgp.org/about/faq/

### Certificate Transparency
- Laurie B., Langley A., Kasper E. (2013) RFC 6962 — *Certificate Transparency*
- Laurie B., Messeri E., Stradling R. (2021) RFC 9162 — *CT v2*
- Chrome CT Policy — googlechrome.github.io/CertificateTransparency/ct_policy.html
- Chrome CT Log List — chromium.googlesource.com/chromium/src/+/master/net/docs/certificate-transparency.md
- SSLMate CT Stats — sslmate.com/resources/certspotter_stats

### 理論框架
- THEORY_V3.md §H4 — 多方 attestation 的「方」從哪來
- P4_registry.md §3.2 Layer 3 — N-of-M finalization policy
