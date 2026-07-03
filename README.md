# Vacant — Phase 1 實作（信任 + 持久/復活）

站在獨立 AI agent「**之間那條線**」上的信任層。它不碰 agent 內部，卻給每個 agent
一個**可持久、可究責、可被信譽篩選、可被復活再呼叫**的身份。

> 這個套件實作《[Vacant 架構總規格（單一文件）v1](../共識會議_2026-06/Vacant_架構總規格_單一文件_v1.md)》的 **Phase 1**，
> 並把它做成在**這台 Intel Mac（無 GPU）上就跑得起、驗得了**的「A 層機制模擬」
> ——純 CPU、零 GPU、零 API。上機（RTX 3090 + vLLM + Hermes）只需把一個
> `Substrate` 實作換掉，其餘信任/持久/路由邏輯原封不動。

---

## ✨ 讓你的 agent 變更好（產品用法）

vacant 把你 agent 的「腦」（任何 LLM / Hermes / OpenAI 相容端點）包一層，把**單次、常出錯、無法究責**的呼叫，變成 **verify-fix 組合（更準）＋ 簽章 logbook（可究責）**。實測：同一顆 gemma-12b 在可檢查任務上 **67% → 83%（+17%）**。

```bash
pip install -e .          # 或 pip install git+https://github.com/cosmopig/Vacant.git
```

```python
from vacant import Vacant, LMStudioBrain

# 1) 指向你的腦（LM Studio / 任何 OpenAI 相容端點 / Hermes）
brain = LMStudioBrain("http://localhost:1234", "your-model")   # api="openai" 給非 reasoning 模型

# 2) 包成 vacant —— 多了 verify-fix（更準）+ 簽章究責
v = Vacant(brain, k=3)
r = v.solve("Reverse the string: hello", verifier=lambda a: a == "olleh")
print(r)        # 'olleh' [✓verified, 1 calls, ✓accountable, brain=lmstudio:your-model]
```

**在你自己的模型上證明它更好**（plain vs vacant，開箱即用的可檢查任務）：
```bash
vacant bench --base http://localhost:1234 --model your-model --api responses -n 12 -k 3
#   plain（無 vacant）   正確率 67%   算力 1.0 次/題
#   vacant（verify-fix） 正確率 83%   算力 1.3 次/題
#   → vacant 讓你的模型 +16%（簽章鏈究責：True）
```

> **誠實邊界**：accuracy 增益只在「答案可被檢查」（你能寫出 `verifier(answer)->bool`：跑測試、驗證格式、比對約束…）時成立。不可檢查的主觀任務，vacant 仍給「可究責」，但不保證更準（規格 §10 oracle 問題）。`verifier` 是你提供的；能力上限仍是模型本身（它根本不會的，vacant 不會無中生有）。

腦選擇：`LMStudioBrain`（reasoning 模型走 `/api/v1`、一般走 `/v1`）、`OpenAIBrain`（任何 OpenAI 相容）、`HermesBrain`（本機 Hermes Agent 當腦，Hermes 自己調模型）。也可自訂：任何有 `.name` 與 `.generate(prompt)->str` 的物件。

---

## 讓 Hermes（或任何 agent）用 vacant 強化「自己」（MCP）

不改 agent 一行碼，只在它的 MCP 設定掛上 vacant，agent 的 LLM 就多出工具：

- **`verify_fix(prompt, check, draft, k)`** — agent 把「可客觀檢查的子任務」交給 vacant：vacant 在本地模型上跑 verify-fix（generate→check→錯就帶回饋重試→對才收），回傳通過的答案 ＋ 一張可攜簽章 attestation。`draft` 給定且已通過 → **0 額外算力**。這條就是「agent 用 vacant 強化它自己」。
- `a2a_call` / `get_reputation` / `submit_review` — 把子任務外包給信譽路由到的可究責專家。

`check` 是可序列化的 **check-spec**（因為 MCP 傳不了 Python lambda，得把「怎麼檢查」表達成 JSON）：

```jsonc
{"type":"equals","value":"olleh"}
{"type":"regex","pattern":"^\\d{4}$"}
{"type":"json_schema","schema":{"type":"object","required":["name"]}}
{"type":"run_python","code":"assert solve('ab')=='ba'"}   // 跑測試 ＝ 最強的客觀檢查
```

啟用（在 vacant MCP server 端設環境變數指向你的模型）：
```bash
VACANT_MCP_MODEL=your-model VACANT_MCP_BASE=http://localhost:1234 python -m vacant.mcp_server
```

> **防「AI 自產自評」**：最強的 check 是 `run_python`（跑測試）/`json_schema`/`equals` —— 客觀、可執行，不是「再問一次 LLM 對不對」。`run_python` 是受限沙箱（`python -I` ＋ 逾時 ＋ CPU rlimit ＋ 暫存 cwd），對「模型自己寫的測試」夠用，但**不是對抗惡意程式碼的安全邊界**（要跑不可信程式請用容器）。

### 可攜的簽章憑證（attestation）＋ 對外究責

`v.solve(...)` 與 `verify_fix` 都回一張 attestation：「答案 X（雜湊）在 T 時通過了檢查 C，由身分 K 產生」。任何人**不必信任送方**即可獨立驗：

```bash
vacant verify-att att.json --answer "olleh"   # ✓ VALID（vacant_id 由 pub 重算、簽章覆蓋整票、答案雜湊對得上）
vacant audit <name>                           # 重驗某 vacant 的 logbook 簽章鏈（PASS/FAIL）
```

### 在「真實 code 任務」上量（不只玩具題）

```bash
vacant bench --suite code --base http://localhost:1234 --model your-model -n 12 -k 3
```

`--suite code` 用 12 題真 code generation、**跑測試當 verifier**（self-repair 的經典適用領域）。實測觀察見〈誠實邊界〉。

---

## 為什麼是這樣切

規格把驗證分兩層（共識定案 §5、總規格 §11）：

- **A 層機制模擬**（免費、CPU）：把信任 + 持久/復活 + 信譽路由整條迴圈跑起來、驗收。
- **B 層系統消融**（本機 GPU、過夜）：把腦換成真 Hermes/vLLM，量學習曲線。

本機（2018 Intel MBP）跑不動 GPU（見自動記憶 `machine_intel_mac_ml_limits`），
所以這裡**完整實作 A 層**：用 `EchoSubstrate`（確定性 CPU「腦」，會真的把學到的
skill 寫回 HERMES_HOME）把 G2–G7 全部跑通。B 層只差把 `EchoSubstrate` 換成
`HermesACPSubstrate`（已附 file:line 整合說明，待 G1 上機接通）。

---

## 快速開始

```bash
cd vacant
PYTHONPATH=. python3 -m pytest tests -q          # 跑全部驗收測試（對應 G2–G7）
PYTHONPATH=. python3 -m vacant.cli selftest      # 端到端冒煙測試
PYTHONPATH=. python3 -m vacant.cli demo          # 跑 §11 C0/C1/C2/C3 對照實驗

# 手動把玩
PYTHONPATH=. python3 -m vacant.cli init alice                          # 鑄一個 requester
PYTHONPATH=. python3 -m vacant.cli init bob --niche reverse --niche caesar3   # 鑄一個 expert
PYTHONPATH=. python3 -m vacant.cli call alice reverse --input hello    # 發一次 a2a_call
PYTHONPATH=. python3 -m vacant.cli info bob                            # 看 bob 的 logbook / skills / 鏈驗
```

（或 `pip install -e .` 後直接用 `vacant …`。唯一相依：`cryptography`。）

`demo` 的輸出長這樣（完全確定性、可重現）：

```
【信任性質】§10 prevents / detects（key custody 假設下）
  冒名被拒（簽章）/ replay 被拒（seq 單調）/ 竄改被抓（hash chain）/ 動作可歸屬   ✓✓✓✓

【學習曲線】等算力對照
  條件                    前1/3  後1/3  整體
  C0 裸 substrate 單次     32%   42%   35%     ← 無累積，平
  C1 naive（隨機+無累積）  38%   38%   40%     ← 同上
  C2 +累積（隨機路由）     48%   85%   69%     ← AutoHarness 引擎貢獻
  C3 +Vacant 信任組合      52%  100%   84%     ← 再加信任層
  C3 − C2（後 1/3）= 信任層淨貢獻 ≈ +15%
```

---

## 實驗模式（2026-07：credit-memory 改動1/3 ＋ W1 基建）

repo 已按 `專題/Vacant_最新成果彙整_2026-07-03` 的裁決（15 號）升級為實驗可用：

- **改動1**：logbook 綁 `stream_id/branch_id`（stream_id＝創世事件 hash）＋真 `head()`。
  ⚠️ wire-format break：舊 `~/.vacant-mcp` 等資料須清掉重鑄。
- **改動3**：review 升級為簽章 `ReviewEnvelope`；registry 只收驗簽＋head 新鮮＋去重，
  weight 內生（Sybil reviewer ≈ 0）、同源降權非線性 `floor/k`；MCP 的無驗簽
  `submit_review` 已廢止。
- **W1 基建**：`auditor.py`（確定性稽核）、`router.py`（trust on/off 單開關）、
  `memory.py`（MemoryStream＋M0/M1/M2 記憶政策＝X1 的實驗處理）、
  `batch.py`（斷點續跑＋端點看門狗）、`x1.py`（任務族＋三臂迴圈）。

```bash
# X1 遷移 pilot（oracle-lesson 一票否決判準，10 §4.2）——先開 LM Studio 端點
python examples/x1_pilot.py --base http://192.168.56.1:8765 \
    --model qwen3.6-35b-a3b --arm M2 --oracle --seed s0
# 三臂配對：--arm M0 / M1 / M2 各跑一次（同 seed；斷點續跑自動跳過已完成格）
```

鐵律與後推項見 `CLAUDE.md`（KS-1 防呆、A4 教訓洩漏防呆都是可執行的，違反即 raise）。

---

## 程式對應規格分層（總規格 §3）

| 層 | 檔案 | 做什麼 |
|---|---|---|
| L0 腦 | `substrate.py` | `EchoSubstrate`（CPU 模擬）/ `HermesACPSubstrate`（3090 stub，附 file:line） |
| L1 身體 | `identity.py` `logbook.py` `reputation.py` `body.py` | keypair+vacant_id、簽章 hash chain、五維 Beta 信譽、信任庫+能力庫綁定 |
| L2 閘道 | `envelope.py` `gateway.py` | 簽章信封、ingress（驗章→防replay→信譽把關→喚醒）、egress（路由→簽→送→評審） |
| L3 host/waker | `waker.py` `host.py` | vacant_id→HERMES_HOME 映射、喚醒對的身體+resume+寫回（**復活**） |
| L4 網路 | `registry.py` | halo 發現 + 信譽路由索引（UCB），非中央路由器 |
| 真值錨 | `verifier.py` `tasks.py` | 可檢查任務 → 環境真值簽 review（非循環 oracle） |

---

## 里程碑對應（總規格 §12 G1–G8）

| G | 內容 | 狀態 |
|---|---|---|
| G1 | 裝 Hermes、`hermes -z` 指 3090 vLLM | ⏳ 上機（B 層）；整合點已在 `HermesACPSubstrate` 文件化 |
| **G2** | 閘道骨架：keypair + 簽/驗 Envelope + logbook(hash chain) | ✅ `crypto/identity/logbook/envelope` + `test_primitives.py`；registry 身份綁定 + ingress 收件人檢查已補（見下「Codex 審查」） |
| **G3** | waker：vacant_id→HOME + 綁 HOME + resume（復活帶回累積） | 🟡 **A 層模擬**：確實從硬碟載回（`test_revive.py` 用 p_base=0 證明），但仍是同程序內呼叫 `Substrate.run`；規格的「獨立 spawn `hermes-acp` + 精確 session resume」待 B 層接通 |
| **G4** | Ingress 把關（驗章→收件人→replay→信譽）接 waker | ✅ `gateway.ingress` + `test_gateway.py`（replay 為 per-process，跨重啟限制見下） |
| **G5** | Egress `a2a_call` + 唯一出口 | ✅ **MCP 工具已包**：`mcp_server.py` 暴露 `a2a_call`／`verify_fix`（Hermes 直接叫 vacant 強化自己）／`get_reputation`／`submit_review`；egress 路由/簽章/記帳在 `gateway.call`。**仍未做**：容器 egress allowlist（部署層） |
| **G6** | Registry + 信譽路由 + 自動 verifier | 🟡 **大致**：`registry.py` UCB 信譽路由 ✅；`verifier.py` 用環境真值評分 ✅，但 review 由 caller 端記/簽（非獨立 verifier 身份）；同源降權只實作 controller（substrate/behavior 未做） |
| **G7** | 2–3 vacant 跑「有閘道 vs 沒閘道」A/B | 🟡 **機制演示**：`experiment.py` 跑得出 C0/C1/C2/C3 對照表與信任性質；但曲線分離是 `EchoSubstrate` 的確定性機制**設計使然**，只證明「管線接對了」，**不**構成「真模型也會分離」的證據——那要 B 層（見下） |
| G8 | Composer 多輪（Phase 2 起點） | ⬜ Phase 2，尚未做（界線見總規格 §9） |

**誠實版圖**：G2/G4 在本機名實相符且測試守住；G3/G6/G7 是忠實的 **A 層機制模擬**
（接對了、跑得動、可驗收「機制成立」），但「獨立 spawn／獨立 verifier 身份／真模型學習曲線」
等仍待 B 層（3090）；G5 的 MCP 工具與 egress allowlist、G1、G8 也待上機。**不宣稱 A 層數字＝實測。**

---

## 誠實邊界（總規格 §10，照搬不藏）

- **prevents（密碼學，key custody 假設下）**：冒名/竄改/replay —— Ed25519 + hash chain
  + seq 單調 + 協議拒收。
- **detects**：行為漂移/偷工 —— 信譽下降、後驗異常。
- **raises-cost**：同源刷分 —— 同源降權（地板 0.1）；公開閾值可被繞，**誠實標明**。
- **A 層模擬非模型實測**：`demo` 的數字是 `EchoSubstrate`（確定性 CPU 模型）下的結果，
  用來證明**機制成立、曲線可分離**；絕對值待 B 層（3090）以真模型校準（§12 M2）。
- **egress allowlist 是部署層**：規格要求容器 egress 只放行「閘道 + model」（A38）。
  本套件在程式層已強制「substrate 不持有對外通道、對外一律經 gateway」；真正的網路
  封鎖（擋 5 類繞過工具）屬上機部署，不在本 CPU 模擬內。
- **可檢查任務 scope**：自動 verifier 的「便宜非循環真值」只在任務可檢查時成立；
  模糊任務仍回到互批的 oracle 問題（MVP 刻意把 scope 釘在可檢查任務）。
- **verify-fix 增益 ＝ recoverable-error（實測，2026-06-18 `--suite code`，跑測試當 verifier）**：
  強 coder 模型（gemma-12b-coder）這些題第一次幾乎全對 → verify-fix 鮮少觸發（算力 ~1.0/題）
  → 88%→100% 的差落在**非決定性雜訊**，不可歸功迴圈；較弱模型（qwen3.6-35b-a3b）會犯可修正
  的錯 → verify-fix **真的開火**（算力 1.2/題、可見 `plain x → 2calls` 的回收）→ 75%→100%（+25%）。
  **強模型上 vacant 的價值是 attestation（可究責）而非準確率**；準確率增益集中在「模型會犯、
  且可修正的錯」。看 `calls`：=1 的勝出是變異、≥2 才是 verify-fix。詳見
  `實驗記錄/實驗筆記_verify-fix真有效於agent_2026-06-18.md`。
- **AI 自產自評風險**：本實作由 AI 產出，關鍵主張請人工終審（見自動記憶
  `vacant_critique_2026-06`）。已修掉舊 repo 的 `seq` 永遠=1 bug（`test_primitives.py` 守住）。

### Production 硬化（2026-06-18，已做、有測試 `tests/test_hardening.py`）

- **原子寫入**：identity / logbook / reputation / capability_card / ingress_guard 全走
  `atomic.py`（tmp + fsync + `os.replace`）→ 崩潰只會留下「舊的或新的完整檔」，不會半截壞鏈。
- **並發鎖**：`waker.wake` 的整個 load→改→persist 週期由 `file_lock`（POSIX flock）序列化
  → 杜絕同一身體被並發喚醒造成 lost-update。
- **跨重啟防 replay**：ingress `ChannelGuard` 持久化到 `trust/ingress_guard.json`、啟動載回
  → **host 重啟後仍 prevents replay**（不再退化為 detects）。
- **不可信邊界輸入驗證**：`Envelope.from_json` 驗型別/必填/`prev_hash` 64-hex/`sig` hex，
  並限 body ≤256KB；logbook 單筆 payload ≤64KB → 畸形/超大輸入乾淨拒收，不往下游崩。
- **金鑰靜態加密（選用）**：`Identity.save(passphrase=...)` 用 PKCS8 加密私鑰；私鑰檔 0600、目錄 0700。
- **產品路徑容錯**：`Vacant.solve` 對腦（網路/逾時/畸形）失敗永不崩 —— 視為一次失敗嘗試，
  verify-fix 自然重試或誠實回報未通過；即使腦全崩，簽章鏈仍完整可驗。

### 仍未做（誠實，多屬硬體/部署/研究層）

- **root 級 custody → 需 TEE/HSM（硬體）**：單人開發機上 controller 有 root，仍可繞過軟體層
  （demo custody）。passphrase 加密擋得住偷檔，擋不住 root。production 上 HSM/TEE 才是 prevents。
- **容器 egress allowlist**：規格 §6 的「只放行閘道+model」屬部署層（iptables/namespace），未做。
- **substrate 自身的 `home/` 寫入原子性**：`trust/` 已原子化；`home/`（skills/memory）由 substrate
  擁有，其原子性是 substrate 的責任（真 Hermes 用 state.db WAL）。
- **同源降權只實作 controller**：same-substrate/behavior 未做（規格框定為 raises-cost、可繞）。
- **冷啟動 Sybil**：新身份（obs<3）一律過把關（給新人探索流量的刻意設計）。
- **不可檢查任務的 oracle 問題**：verify-fix 的客觀真值只在可檢查任務成立（規格 §10）。
- **禁止經閘道自呼**：`gateway.call` 對 `callee==caller` 直接拒絕（避免同一身體被同時載入覆蓋）。
- **同源降權只實作 controller**：`registry._same_signal` 只比對 controller 標籤；
  same-substrate / same-behavior（同款式）尚未實作。符合總規格「raises-cost 非 prevents、
  公開閾值可被繞」的誠實框定，但 Sybil 換 controller 字串即可繞過，待 Phase 2 補。
- **冷啟動可被當 Sybil 管道**：新身份（obs<3）一律過信譽把關（這是給新人探索流量的
  刻意設計）；配合上一條，等於「狂開新身份」能繞把關——已知，屬同源/Sybil 議題範圍。

### 兩輪獨立審查與修補（對「AI 自產自評」的對策）

本實作刻意過了**兩道獨立審查**，不只自評：

1. **Claude 對抗式 workflow**（5 維、22 agents）：修了 try/finally 持久化、self-call 防護、
   信譽把關改 substrate-specific、`observations` min→avg、same-signal 語義、UCB 常數具名等。
2. **Codex（GPT-5 級）獨立驗證**：抓到並已修的**真 bug**——
   - **Bug 1 registry 未驗身份綁定**（可用「別人 vacant_id + 自己 pubkey」污染 registry 冒名）
     → `registry.announce` 現在重算 `multibase(multihash(pubkey))` 比對，不符即拒（`test_registry_rejects_forged_identity_binding`）。
   - **Bug 2 ingress 未驗收件人** → 現在拒絕 `env.to != self.vacant_id`（`test_ingress_rejects_wrong_recipient`）。
   - **Bug 3 未簽 task 旁路** → ingress 改為**只**依已簽章的 `env.body` 建構執行輸入，移除旁路。
   - **demo 衛生**：改寫進暫存目錄，不再 `rmtree` 使用者的 `~/.vacant`。
   Codex 另指出的 overclaim（G5/G7/verifier 措辭）已在上方里程碑表更正為 🟡。
   *（Codex 報告中「`experiments/experiment.py` 不存在」是路徑誤判：檔案在 `vacant/experiment.py`、可正常執行。）*

---

## 上機（B 層）怎麼接

唯一要改的是注入的 substrate：

```python
from vacant.host import Host
from vacant.substrate import HermesACPSubstrate

host = Host(root, substrate=HermesACPSubstrate(
    base_url="http://localhost:8000/v1",   # 3090 上的 vLLM
    model="hermes-3-8b",
))
```

`HermesACPSubstrate.run` 的整合點（ACP stdio、`HERMES_HOME` 綁定、resume、反代攔截）
已在 `substrate.py` 內以 file:line 文件化；待 G1 在測試機上接通與上機驗證（§10 的 14 項）。
