# 自驗 2026-09-22：Claude Code 給自己套 Vacant（`vacant install --agent claude`）

> **證據等級：L-real**（真上游 `api.anthropic.com`、真模型 `claude-haiku-4-5-20251001`）。
> 量的是 **Claude Code 這個 agent**，不是「正在跟人講話的那個 session」——那個行程已經啟動，
> `ANTHROPIC_BASE_URL` 是啟動時讀的，改設定影響不到它。這一批全部是**子行程** `claude -p`。
> 人類 2026-09-22 批准用 Haiku 4.5；共 9 通模型呼叫（7 格通道 ＋ 2 格閘門）。

- 執行端：Claude Code 遠端容器（`VERSIONS.txt`）；`claude 2.1.278`；HOME 隔離（`--home`），
  **沒有動容器的真 `~/.claude`**；`--service bare`；沒有 bwrap ⇒ 每格 **B′**。
- 真上游：`api.anthropic.com` 在這台的 `NO_PROXY` 裡 ⇒ proxyd 直連得到；容器的 agent proxy
  **不注入金鑰**（裸打 `/v1/models` 是 401）。子行程的憑證由 Claude Code 自己帶，
  proxyd `sentinel=""` 原樣穿透，**本批沒有讀寫任何憑證**。

## 一、通道：七格，一個變數決定 settings.json 有沒有用

`vacant install --agent claude` 寫的是 `~/.claude/settings.json` 的 `env.ANTHROPIC_BASE_URL`
（`resident/settings.json.installed`）。子行程用完整路徑 `/opt/node22/bin/claude -p "reply with the single word OK"`，
命令列上零個 vacant。判準＝常駐 proxyd journal 有沒有 `POST /v1/messages`（`resident/proxyd_index.jsonl`）。

| 格 | base URL 來源 | `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` | `CLAUDE_CODE_USE_CCR_V2` | 回答 | journal `POST /v1/messages` |
|---|---|---|---|---|---|
| baseline | 都沒有（沒裝 Vacant） | 保留 | 保留 | `OK` | —（沒裝） |
| channel | **settings.json** | 保留 | 保留 | `OK` | **0** 🔴 |
| A | **環境變數** | 保留 | 保留 | `OK` | **2** ✅ |
| B | settings.json | 拆掉 | 拆掉 | `OK` | **2** ✅ |
| C | settings.json | **拆掉** | 保留 | `OK` | **2** ✅ |
| D | settings.json | 保留 | **拆掉** | `OK` | **0** |
| E（channel 重跑） | settings.json | 保留 | 保留 | `OK` | **0** |

⇒ **`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 的環境下，Claude Code 忽略 `settings.json` 的
`env.ANTHROPIC_BASE_URL`，而且照樣正常回答。** 環境變數那條不受影響。
`USE_CCR_V2` 與此無關（D 格）。

這是 `goal.md` §五-9 那個形狀的**又一個活體標本**：除了 `requests_seen`，一切看起來都成功。
`vacant possess status` 對這一格會說「設定 ✓ 已寫入、中介 **未證實**」——量具沒說謊，
但「裝好就有」對**被 host 管理 provider 的 Claude Code**不成立。哪些環境會設這個變數
（Claude Code on the web／Cowork／企業託管？）**本批沒量**，只知道這台有。

## 二、閘門：shim 那條，真模型，兩格都成立

`~/.vacant/possess/bin/claude -p "…" --model claude-haiku-4-5-20251001 --permission-mode acceptEdits`，
驗收 `tests_visible/test_add.py`（`check_add`：`from solution import add; add(2,3)==5`）放在工作區外。
gateshim 的 claude 段走的是**環境變數** `ANTHROPIC_BASE_URL`＝這一跑的 ephemeral proxy（§一 A 格那條），
所以不受 host-managed 影響。

| 格 | 提示句 | agent 寫出來的 | 退出碼 | `accepted` | `agent_rc` | `requests_seen` | 收據 |
|---|---|---|---|---|---|---|---|
| 拒交格 | 只寫 `mul(a,b)`，不准有別的函式 | `solution.py` 只有 `mul` | **20** | `false` | 0 | 10 | `runs/possess_claude_1790056460_acc66a` |
| 交付格 | 寫 `add(a,b)` | `solution.py` 有 `add` | **0** | `true` | 0 | 10 | `runs/possess_claude_1790056467_8a3048` |

兩格 `agent_rc` 都是 0——agent 兩次都宣告完成，裁決來自驗收。`verify_receipts --selftest` 先 PASS，
兩張收據總判 **OK**，級別 **B′**（掛鉤燒了、沒有圍牆）。

⚠ **`requests_seen=10` 裡只有 3 通是模型**（`wire_by_protocol: {"openai": 7, "anthropic": 3}`）。
那 7 通是 Claude Code 啟動時對 base URL 探 `GET /v1/code/agent-proxy/ca-cert`（回 sink 502），
被 `wireproxy.route()` **按 path 猜成 `openai` 家族**。它們進 journal 是對的（每一通都經過），
但 `wire_by_protocol` 的 `openai` 計數在 Claude Code 上**不是模型呼叫**，讀的時候要扣掉。
`route()` 按 path 猜家族這件事 `goal.md` §五-3 早就標著沒修。

## 二-1、⚠ 兩個 run 的 `*.req.bin`（模型請求 body）**刻意不入庫**

Claude Code 送出的請求 body 裡有它自己的系統提示，而那段提示帶著**這個帳號的識別資料**
（電子郵件、帳號／組織 UUID）。那不是 Vacant 的東西，也不該出現在公開 repo 裡，所以
`wire_RUN-ON/*.req.bin` 六個檔在入庫前刪掉；`wire_RUN-ON/index.jsonl` 仍留每一通的 sha256、
path、status，`*.resp.bin`（模型回應）照留。收據鏈簽的是 `wire_digest`，不依賴 body 檔在場。

## 三、還原

`vacant uninstall --home <HOME>`：`ok: true`，`settings.json`（我們建的）與 environment.d 刪掉、埠關閉
（`resident/uninstall_report.json`）。

## 四、不能說的

1. **不能說「Claude Code 裝好就有」**：在 host-managed 環境下 settings.json 那條為假（§一）。
   能說的是「環境變數那條成立；settings 那條在 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` 未設時成立」。
2. **不能說這個 session 被中介了**：本批全是子行程。被閘門的 agent 就是有權改 `settings.json` 的 agent
   （`AGENT_HOOKS_MEASURED` §三），我給自己套 Vacant 在保證層上是空的，只在紀錄層有意義。
3. **不能說 A 級**：沒有 bwrap。
4. 只量 `-p` 一題；互動、長任務、MCP 沒量。Claude Code 沒有 extension API ⇒ 沒有 `/vacant on|off` 開關。

## 重跑

```
vacant install --agent claude --home <HOME> --service bare --port 18788 --upstream anthropic=https://api.anthropic.com --no-shell-probe --no-startable-probe
CLAUDE_CONFIG_DIR=<HOME>/.claude env -u ANTHROPIC_BASE_URL -u CLAUDECODE … /opt/node22/bin/claude -p "reply with the single word OK" --model claude-haiku-4-5-20251001
#   ⇒ 看 <HOME>/.vacant/possess/proxyd/wire/index.jsonl；再拆掉 CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST 跑一次
<HOME>/.vacant/possess/bin/claude -p "…" --model claude-haiku-4-5-20251001 --permission-mode acceptEdits   # 工作區旁放 tests_visible/
vacant uninstall --home <HOME>
```
