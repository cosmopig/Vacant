# MCP 工具面措辭（Fable，2026-09-18）：`delegate` 不准把居民生態叫作 `trusted`

裁決者：Fable。人類複核兩項關鍵事實後放行施工。
施作範圍：`vacant/mcp_server.py` 三處同行替換、`CHANGELOG.md` 一段更正、
`tests/test_cleanroom_blockers.py` 兩條防回流測試。

## 〇、一句話

**`vacant/mcp_server.py:187` 的 `trusted` 被刪掉（不是換字），模組 docstring 的
「信任閘道」／「信任生態」改成「究責閘道」／「究責生態」。理由不是禁語表，是同字反義：
同一個 repo 用 `trusted` 表示「不驗、直接假設」，而居民生態恰恰是唯一被路由、互審、稽核、
簽章綁定的對象——docstring 對它自己描述的機制說錯話。識別子與其自然語言寫法（`trust card`、
`trust OFF vs ON`、「信任狀」）全部保留。**

「改 prompt＝改行為」這件事沒有被否認，被否認的是「會破壞與既有 run 的可比性」——
**沒有任何歸檔證據 run 走過這條路徑**（見 §三）。

## 一、改了什麼（逐字）

| # | 位置 | 前 | 後 |
|---|---|---|---|
| 1 | `vacant/mcp_server.py:187` | `writing the code yourself, hand it to Vacant's trusted, accountable resident` | `writing the code yourself, hand it to Vacant's accountable resident` |
| 2 | `vacant/mcp_server.py:1` | `把信任閘道生態暴露成 MCP 工具` | `把究責閘道生態暴露成 MCP 工具` |
| 3 | `vacant/mcp_server.py:7` | `把有客觀 check 的 coding 子任務交給信任生態` | `把有客觀 check 的 coding 子任務交給究責生態` |

第 1 條是**刪除不是替換**：同一片語裡已經有 `accountable`，換成 `accountable` 會變成
`accountable, accountable`。

三處都是同行替換，`vacant/mcp_server.py` 仍是 315 行（`git diff --numstat` ＝ `3 3`）。
行號不得漂移的理由：`AGENTS.md:59`、`AGENTS.md:198`、`README.md:199`、`README.md:348`
四處都引用 `vacant/mcp_server.py:184-210`。

## 二、為什麼要改（六條）

**(a) `trusted` 不在識別子豁免內。** `AGENTS.md:520` 的 `terminology.scope` 逐字寫
「user-visible output and prose. Identifiers are API surface and keep their names:
trust_dir, trust_card, trust_on, --trust, and the trust/ directory.」——
`trusted` 不是其中任何一個，它是形容詞，不是 API 表面。

**(b) 同字反義：本 repo 對 `trusted` 有精確用法，而且正好相反。**
`vacant/peerexec.py:186,196` 的 `SUITE_FIXED_POINT_NOTE` 用 `trusted` 表示 TCB 語意的
「不驗、直接假設」：

> the committed suite is DATA ... rendered by the executor's own **trusted** renderer
>
> coverage and comparator config **remain a trusted input, and so do the renderer and
> the sandbox it renders for**

`AGENTS.md:451` 的 H-8 同義：「The renderer and the sandbox are trusted inputs. Trust is
*relocated*, not eliminated.」

而 `delegate` 描述的居民生態，是本系統裡**唯一**被路由、互審、稽核、簽章綁定的對象——
它是 repo 裡最不「trusted」的東西，正因為它全程被驗。把它叫 `trusted`，等於讓 docstring
對它自己描述的機制說反話。

**(c) 與同句的 `accountable` 自相矛盾，所以是刪不是換。**
`trusted, accountable` 這個並列本身就在打架：一個說「不必驗」，一個說「驗得出來」。
刪掉前者，句子才回到它實際描述的機制。

**(d) 比 `vacant/controller.py:7-8` 的誠實邊界樂觀。** 那裡逐字寫：

> 誠實邊界：保證只涵蓋透過本 controller 啟動的子行程；無法阻止同一 OS 使用者繞過
> 本命令直接執行 agent。

同一個 repo 裡，**強制力最強**的形態（controller）自己承認邊界，而**強制力為零**的形態
（MCP，`AGENTS.md:59` 定性為 persuasion only）卻用最樂觀的形容詞。這個落差是倒的。

**(e) 來源早於口徑紀律本身。** 這段文案來自 `3c0e967`（2026-06-18，
「feat: vacant 產品 API — 把任何 agent 的腦包成『更好+可究責』(verify-fix)」）。
`CLAUDE.md`「唯一交付物」節第 5 條（口徑用「可究責性 / 讓依賴有根據」，不要用「信任」）
是 2026-08-06 才寫上去的；`AGENTS.md` 的 `never_use` 清單更晚，`8508f87`（2026-09-18，
release 0.7.0）才進 repo。兩者都晚於這段文案——它不是被裁決過而保留，是**沒被看過**。

**(f) 執行防呆掃不到，也不該掃到。** `tests/test_cleanroom_blockers.py:35` 的
`BANNED = ("信任", "trust layer", "trusted layer", "信任層")` 不含單獨的 `trusted`，
而且**不該**含——加進去會誤殺 (b) 的正當 TCB 用法，而那些句子是誠實邊界句，是規格的一部分
（CLAUDE.md 慣例第三條）。機械黑名單在這裡沒有可用的解，所以這一處只能靠人裁決。

## 三、可比性不是議題（人類已複核）

| 查證 | 結果 |
|---|---|
| `runs/INDEX.md` 對 `mcp` / `delegate` / `verify_fix` | **0 命中**（598 個項目、98 個 real_run） |
| `ops/` 底下 import `mcp_server` | **0 個** |
| `ops/gain/gain_run.py` 的 vacant import | 只有 `codebench` / `crypto` / `identity` / `logbook` / `suitegauge` |

⇒ **零個歸檔證據 run 走過 MCP 路徑。** G 實驗（R44x–R53x）全部是 harness 自己擁有 loop
的形態（`AGENTS.md:59` 表格第四列），不經 `mcp_server`。

`CHANGELOG.md` 原本寫「editing it changes behaviour **and breaks comparability with
existing runs**」——後半句沒有任何 run 撐著，本次一併更正。

## 四、明確保留（不在本裁決的改動範圍內）

| 保留項 | 位置 | 理由 |
|---|---|---|
| `trust card` | `mcp_server.py:190,207,215,223,225` | `trust_card` 工具名／JSON 鍵（`:127`）／輸出表頭 `── trust card ──`（`:98`，被 `tests/test_mcp_v2.py:45` 釘住）的自然語言寫法 |
| `trust OFF vs ON`／`trust on or off` | `mcp_server.py:248-249` | `trust_on` 狀態鍵／`--trust` 旗標／scoreboard 輸出欄（`:177-178`）的自然語言寫法 |
| 「信任狀」 | `mcp_server.py:7,8` | `trust_card` 的中文專名，跨 `vacant`／`tests`／`examples`／`docs` 共 17 檔 39 行；改名是**獨立裁決** |
| `trusted`（TCB 用法） | `peerexec.py:186,196` | §二(b)：正當且精確，動它會讓收據看起來比實際乾淨 |
| 其他中文 docstring 的「信任」 | `ecosystem.py` 13 處等 | 機械替換不讓任何宣稱變真；不在本裁決內 |

## 五、誠實邊界（四條）

1. **「改 prompt＝改行為」原則上成立。** 能證明的是**沒有任何歸檔 run 走過這條路徑**
   （§三）。**不能證明**的是「刪一個形容詞對 MCP client 模型的工具選擇零影響」——
   這裡只能引 `AGENTS.md:59` 把這段 docstring 定性為 persuasion only，
   且**沒有任何量測在看它**。沒量測不等於影響為零，等於影響未知。

2. **client 端行為未在本 repo 內驗證。** MCP client 會把 `tools/list` 的 description
   顯示給人，但本 repo 的 `vacant trace`（`vacant/cli.py:937-938`）只印一行
   （`[t] · Hermes 列工具 tools/list`），不印 description。client 怎麼渲染、模型怎麼讀，
   本 repo 沒有證據。

3. **同段 docstring 的「THE PREFERRED PATH」與「a better answer」是另一類宣稱**
   （效能宣稱／指令性宣稱，不是同字反義），**不在本裁決內**。它們該不該動是另一次裁決。

4. **`examples/acp_a2a_test.py:7` 的 PROMPT 也寫 `trusted expert agent`**，
   但它驅動的 `a2a_call` 已廢止（`vacant/mcp_server.py:15`：「廢止（12 §3，工具面 v2
   取代）：a2a_call / get_reputation / submit_review 與 EchoSubstrate 玩具 host 整段移除」）。
   同類問題、死碼、**不在本裁決內**，僅記錄。

（本次順帶觀察，同樣不在裁決內：`examples/demo_trust.py` 的 argparse description 與輸出
仍寫「信任閘道」。它是 examples 不是 `vacant` console script，
`tests/test_cleanroom_blockers.py` 的 `build_parser()` 掃描涵蓋不到它。）

## 六、加上的執行防呆（`tests/test_cleanroom_blockers.py`）

| 測試 | 釘住什麼 |
|---|---|
| `test_no_banned_term_in_any_mcp_tool_description` | 掃 FastMCP `_tool_manager.list_tools()` 的 description（＝ client 送給模型看的那份文字）有沒有 `BANNED`。CLI 的三條掃的是**人**看的輸出，這一條掃**模型**看的輸出。 |
| `test_the_word_trusted_alone_is_not_and_must_not_be_in_the_banned_list` | **誤殺防線**：`assert "trusted" not in BANNED`，並正向確認 `peerexec.SUITE_FIXED_POINT_NOTE` 的兩句 TCB 用法還活著。誰把 `trusted` 加進 `BANNED`，這一條先燒。 |
| `test_delegate_docstring_does_not_call_the_ecosystem_trusted` | 逐點釘子，範圍只有 `delegate` 一支 description；負向控制確認 `accountable resident` 還在、沒有變成 `accountable, accountable`、`trust card` 沒被順手殺掉。 |

`trusted` 為什麼只能逐點釘不能進黑名單，理由寫在測試的 docstring 裡，不只寫在這裡。
