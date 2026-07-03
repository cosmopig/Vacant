# Vacant 改造藍圖：從信任骨架到實驗平台

**日期** 2026-07-04 · **設計** Fable 5 · **實作** Opus 4.8 / Sonnet · **權威** 依 `專題/Vacant_最新成果彙整_2026-07-03/15_再審核判決` 與 `16_執行總手冊`
**目的**：把現有 vacant（信任＋持久/復活）改造成能跑 X1（記憶→品質）、X3（信任前緣）、demo 的實驗平台。本檔只寫**尚未做**的部分與其接口，已完成者只標狀態。

---

## 0. 當前狀態（git HEAD 94592fa，83 tests green）

| 子系統 | 狀態 | 檔案 |
|---|---|---|
| Identity / Ed25519 / vacant_id | ✅ 完成 | identity.py, crypto.py, canonical.py |
| Logbook hash-chain ＋ **stream_id/branch_id/head()（改動1）** | ✅ 完成 | logbook.py |
| Envelope（call/result）＋ **ReviewEnvelope（改動3）** | ✅ 完成 | envelope.py |
| Gateway ingress/egress ＋ **真簽發 review** | ✅ 完成 | gateway.py |
| Registry：halo＋**record_review 只收驗簽/weight 內生/floor·k 去重（改動3）** | ✅ 完成 | registry.py |
| Reputation 五維 Beta ＋ UCB | ✅ 完成（decay/slash **後推**） | reputation.py |
| EchoSubstrate（假腦）＋ HermesACP stub | ✅ 完成 | substrate.py |
| Composer verify-fix | ✅ 完成 | composer.py |
| **真模型 substrate（qwen3.6）** | ❌ **未做**（NW-1） | substrate.py / brains.py |
| **沙箱 check ＋ MBPP+ 任務** | ❌ **未做**（NW-2） | 新 checks.py, tasks.py |
| **MemoryStream ＋ MemoryManager M0/M1/M2** | ❌ **未做**（NW-3） | 新 memory.py |
| **Auditor（稽核率 p＋probation＋slash 事件）** | ❌ **未做**（NW-4） | 新 auditor.py |
| **X1 實驗 runner ＋ 統計** | ❌ **未做**（NW-5） | 新 experiments/ |
| **工具面 v2 ＋ 信任狀 ＋ CLI ＋ dashboard** | ❌ **未做**（NW-6） | mcp_server.py, cli.py, 新 trustcard.py/dashboard.py |

**紅線（15 號）**：reputation decay/slash 與改動2（key 換三元組）**後推**至 X3/X4 前，本波不做。同源降權維持現況（讀 controller），但 **X4 承重臂不得依賴它**（見 NW-4 附註）。

---

## NW-1 · LMStudioSubstrate（真模型腦）— 【Opus】最高優先

**為何第一**：X1/X3/demo 全部要真模型；現在只有 EchoSubstrate（假腦）。這是所有實驗的地基。

**接口**（實作 `Substrate` ABC，見 substrate.py:40-48）：
```python
class LMStudioSubstrate(Substrate):
    def __init__(self, base="http://192.168.56.1:8765", model="qwen/qwen3.6-35b-a3b",
                 api="/api/v1/chat", max_tokens=None, retry=4, timeout=180): ...
    substrate_id = "lmstudio:qwen3.6-35b-a3b"   # per-substrate 信譽 keying 用
    def run(self, home, prompt, task) -> SubstrateResult: ...
```
**要點**：
- `/api/v1/chat`、`/no_think`（批次）；**不設 max_tokens 上限**（None → 不傳該欄；reasoning 模型會被砍）。demo 模式可傳有界 2–4k。
- `call()` 內建 **retry×4**；四次全失敗 → 回 `SubstrateResult(output="", ..., error="infra_void")`，呼叫端**永不計為一票**（06-30 污染教訓）。
- 解析：strip `<think>...</think>`；取最後 message content。
- **不寫死答案**：真模型自己算，`learned_skill` 由外層依 verifier 結果決定（EchoSubstrate 內建學習是假腦特例，真腦的「學習」走 NW-3 記憶層，不在 substrate 內）。
**測試**：mock HTTP（monkeypatch urllib）驗 retry、infra_void、think-strip、no max_tokens 欄位。**不需**真 VM（真跑在 VM 上）。
**依賴**：無。可與 NW-2 並行。

---

## NW-2 · 沙箱 check ＋ MBPP+ 任務 — 【Sonnet】

**為何**：X1/X3 用真程式任務，需要「跑隱藏測資判對錯」的沙箱（= 稽核器與 verifier 的底層）。現有 verifier.py 的 `check` 是 task dict 裡的閉包；MBPP+ 需要真的執行候選 code＋assert。

**NW-2a `checks.py`**（新，~120 行）：
```python
def run_python_check(candidate_code: str, test_code: str, *, timeout=8) -> bool:
    # subprocess ["python3","-I","-c", candidate + "\n" + test]，returncode==0 為過
def compile_check(spec: dict) -> Callable[[str], bool]:
    # spec: {"type":"run_python","tests":"<asserts>"} | equals | contains | regex
```
沙箱紀律：`-I`（隔離）、timeout、捕捉 stdout/stderr、例外即判 False（不崩主程序）。
**NW-2b MBPP+ 載入**（`tasks.py` 擴充或新 `codebench.py`）：
- 載 EvalPlus MBPP+（釘版本、資料 hash）；每題產出 `{task_id, family, prompt, visible_check, hidden_check}`。
  - `visible_check` = 題述基礎測資（= 形式化需求 V）；`hidden_check` = EvalPlus 擴增隱藏測資（= GT，評分用，系統跑中看不到）。
- **任務族 tag**（X1 遷移需要）：按坑型分族（邊界/off-by-one/空輸入…），族內變體規則可重現。
- pilot 用；正式子集凍結函式 `freeze_subset(seed, n>=215, exclude_saturated)`。
**測試**：已知好 code 全過、已知壞 code 全 fail（各 ≥10 例）；沙箱逾時不掛。
**依賴**：無。與 NW-1 並行。

---

## NW-3 · MemoryStream ＋ MemoryManager（M0/M1/M2）— 【Opus】X1 科學核心

**為何**：X1 的三臂處理本身。這是畢業論文主命題「被審記憶提升品質」的載體。

**NW-3a `MemoryStream`**（新 memory.py）：episode 序列，寫入即經 logbook 簽章上鏈。
```python
@dataclass
class Episode:
    task_id: str; spec_digest: str; answer_digest: str
    verdicts: list[dict]        # peer/audit 判決（含 reviewer_id, verdict）
    audit: dict | None          # {"ran": bool, "passed": bool}
    outcome: str; lesson: str | None; ts_ms: int
class MemoryStream:
    def append(self, ep: Episode, identity) -> None   # 經 body.log 上鏈
    def episodes(self) -> list[Episode]
```
**NW-3b `MemoryManager`**（政策 = 實驗處理，三臂）：
```python
class MemoryManager:
    def __init__(self, policy: str, budget_tokens=2000): ...  # "M0"|"M1"|"M2"
    def context_block(self, task, stream) -> str: ...
```
- **M0**：回空字串（stateless 基線）。
- **M1**：最近 k 個 episode 原文塞入（無篩選；文獻預測傷長程 → 真對照，非稻草人）。守 budget。
- **M2**：只取**被稽核/被審確認過**的 episode → 蒸餾成教訓（失敗剖析＋成功模式）→ 依任務族相關性取 top-k ＋其稽核結論；守固定 token budget B；舊教訓 decay。
  - **蒸餾 = 每被審 episode +1 模型呼叫**（寫入時一次性，O(1) 攤提）——**離線/週期執行，絕不塞進 delegate 回應路徑**（MCP 60s 逾時，見 16 手冊 B1）。
- **KS-1 防呆（硬規則）**：三臂的 system prompt 與任務模板**逐字相同**，唯一差異＝MemoryManager 注入的記憶區塊。禁止任何「你有責任/會被懲罰」措辭。違反此條的 run 作廢。
- **A4 資訊洩漏防線（硬規則）**：教訓只許**坑型層級抽象**（例「注意空輸入邊界」），**禁止逐字隱藏測資內容/輸入輸出對**；交付前自動抽查教訓字串不含 hidden test 片段。
**測試**：三政策在同 stream 產生的 context 逐 byte 不同且 M1/M2 都守 budget（token 計數斷言）；M2 只納入 audit.passed 的 episode；教訓不含隱藏測資字串。
**依賴**：logbook（已完成）。可與 NW-1/2 並行（純新檔）。

---

## NW-4 · Auditor（稽核 ＋ probation ＋ slash 事件）— 【Opus】

```python
class Auditor:
    def __init__(self, audit_rate: float, sandbox: Callable, probation_m=2, seed=0): ...
    def should_audit(self, task_id, deliverer) -> bool   # rate 抽樣 + 新身份前 m 次強制
    def audit(self, candidate_code, hidden_check) -> dict # {"ran":True,"passed":bool}
    def provable_fault(self, deliverer, reviewers, audit_result) -> list[SlashEvent]
```
- 稽核 = 跑 NW-2 的 hidden_check（確定性、非模型呼叫）。
- **slash 事件只寫 ledger**（本波不改 reputation 真扣分——decay/slash 後推）。事件供 dashboard 與 X4 分析。
- **附註（15 號 A2）**：X4 的「同源降權承重」不得依賴 registry 現有的 `_same_signal`（讀 ground-truth controller）；X4 實驗版必須改行為推斷或誠實框為「若歸屬可得則有效」。此為實驗層設計約束，NW-4 只需把 slash 事件產出乾淨。
- **demo 模式**：`audit_rate=1.0`（或靠 probation 強制），使種植的 saboteur 必被稽核抓到，slash 事件必跳出（16 手冊 B3）。
**測試**：抽樣率統計、probation 強制、好/壞 code 判定、slash 事件格式。
**依賴**：NW-2（沙箱）。

---

## NW-5 · X1 實驗 runner ＋ 統計 — 【Opus】畢業核心

- runner：單一 Resident 走連續任務流（T≥215、族內、固定序），三臂 M0/M1/M2 同題序同 seed 配對（**禁快取**，行為依賴記憶）；≥3 生成 seed；稽核率 100%（X1 驗記憶通道，稀缺留給 X3）。
- 消融：**只做 1 個「−稽核結論」**（責任 vs 日記分界）。B 掃描 **2 檔 {1k,4k}**。
- 統計：McNemar 精確＋bootstrap CI，Holm family={H-A1,H-A2}（判準 H-A1 M2−M0≥+8pp、H-A2 M2−M1≥+5pp）。附 power 計算（T≥215 @ +8pp）。
- **批次強韌**：checkpoint/斷點續跑（重啟自動跳過已完成 (arm,task,seed)）＋LM Studio 看門狗（定期 ping、掛掉重啟＋通知）。
- **X1 遷移 pilot**（先於正式 run）：oracle-lesson 遷移存在 ＋ 加驗「非 oracle 實現遷移率＋變體相似度上界」；一票否決（三次重選不過回退 X3）。
**依賴**：NW-1,2,3,4。

---

## NW-6 · 工具面 v2 ＋ 信任狀 ＋ CLI ＋ dashboard — 【Sonnet，delegate 延遲部分 Opus】

- mcp_server 工具：`delegate(task, tests, risk)`（demo path k=1＋確定性互審 0 模型呼叫；批次 path 讀 code 判 PASS/FAIL——同一份 code 兩模式，見 16 手冊 B1）、`trust_card`、`residents`、`report`、`scoreboard`；廢除對外 `submit_review`（改動3 已廢無驗簽版）。
- `trustcard.py`：信任狀組裝＋人可讀渲染；**audit/flag 風險欄為必有且顯眼**（15 號 A4／JCOM 捷思陷阱：只顯正面出處會讓人更不查核）。
- CLI：`up/toggle on|off/status/scoreboard/resident inspect|wipe/verify/ledger tail/batch`。
- dashboard.py：localhost SSE tail ledger（居民卡片/信用曲線/路由流/slash 事件即時）。
**依賴**：NW-3,4。demo 用。

---

## 實作順序與指派

```
Wave A（並行，純新檔/加法）：NW-1 substrate〔Opus〕 · NW-2 checks+MBPP〔Sonnet〕 · NW-3 memory〔Opus〕
Wave B（依 A）：NW-4 auditor〔Opus，依 NW-2〕
Wave C（依 A+B）：NW-5 X1 runner〔Opus〕 · NW-6 工具面/CLI/dashboard〔Sonnet〕
```
每個單元：新檔為主、加既有檔為輔（不動已綠的信任骨架）；**每單元附單元測試、跑 pytest 必須維持全綠**（當前 83）；在分支 `feat/experiment-platform` 上做。
