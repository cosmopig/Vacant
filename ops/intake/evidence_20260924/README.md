# 四個 agent 的收件口端到端量測（2026-09-24，L-fake）

裁決：[`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md`](../../../decisions/DECISION_20260924_UNIVERSAL_INTAKE.md) §七。
結果：[`SUMMARY.md`](SUMMARY.md)（人讀）、[`results.json`](results.json)（機器讀；暫存路徑已換成 `<lab>`／`<scratch>`）。

## 量的是什麼

同一份**非程式**任務契約（報告要有 Summary／Limits 兩段；報告裡的總數要等於**委託者釘住的 CSV**
重算出來的數；引用記號要對得到 `sources.json`，引文要在**委託者釘住的快照**（`inputs/snaps`，不是 agent 自己帶的那份）裡逐字出現——所以總數與引用兩條都是**事實主張**；不准帶憑證檔），交給
四個**未修改的真 agent**：pi 0.87.1、Claude Code 2.1.281、OpenCode 1.18.32、Codex 0.156.1。

每個 agent 一個隔離的「使用者」（自己的 HOME、自己的 provider 設定、外加一條他原本就有的
hook／MCP 設定），然後：

| 情境 | 劇本（假模型） | 量的是 |
|---|---|---|
| `fixes` | 先寫總數 999，**看到 Vacant 的回饋**後改成 60 | 掛鉤把回饋送到模型手上嗎？改對的版本被收下、發布、讀回嗎？ |
| `stays_bad` | 寫 999，不理回饋 | 錯的版本**進不了目的端**嗎？ |
| `tries_effect` | 先跑 `touch EFFECT_HAPPENED && git push origin main`（契約禁止），再寫對的 | agent 自己的工具前掛鉤擋下了嗎？**效果真的沒發生嗎**（標記檔）？ |
| `vacant do --no-hooks` | 寫對的 | 只靠行程＋工作區那一層也能交件嗎？原專案沒被動嗎？ |
| 解除安裝 | — | 使用者原本的設定檔逐位元還原嗎？ |
| `vacant do`（拆掉之後，**每一跑**的掛鉤） | 同 `tries_effect` | 每一跑的加法式注入（`--settings`／`-e`／`OPENCODE_CONFIG_CONTENT`／`-c`）真的載入、擋得下嗎？使用者設定仍然沒被寫嗎？ |

另外量一件事：模型收到的請求裡**有沒有 Vacant 技能的描述**（假模型逐次記錄；SUMMARY 的
「Vacant skill listed to model」欄）——技能檔放對位置是文件說的，列給模型才是量到的。

**命令列上沒有 `vacant`**：agent 是用它自己平常的指令跑的（`pi -p`、`claude -p`、`opencode run`、
`codex exec`），Vacant 只透過 `vacant install` 寫進它自己設定裡的掛鉤與技能出現。

## 重跑

```bash
# 四個 agent 的 binary（claude 另外裝）
npm install --prefix /tmp/agents @openai/codex@0.156.1 opencode-ai@1.18.32 \
    @earendil-works/pi-coding-agent@0.87.1
python3 ops/intake/e2e_four_agents.py --bin /tmp/agents/node_modules/.bin \
    --out /tmp/vacant-e2e --agents pi,claude,opencode,codex
```

零 API key、零對外模型呼叫：模型是 `ops/intake/mock_model.py`（Anthropic Messages／OpenAI
Responses／Chat Completions 三種 SSE，照劇本回答）。OpenCode 第一次跑會從 npm 抓
`@ai-sdk/openai-compatible`。

## 誠實邊界（引用這份結果時一起講）

1. **L-fake**：真 agent、真工具迴圈、真掛鉤，**假模型**。它證明的是四個 agent 接得起來，
   不是任何模型的能力。「回饋後改對」是劇本寫的。
2. 「錯的版本進不了目的端」只對 `vacant release` 寫的那個目錄成立。agent 在自己的專案目錄裡
   寫了什麼，本來就寫了。
3. 「`git push` 被擋」是**工具層**的：同一條指令用別的寫法（base64、另一個直譯器）字串規則看不出來，
   而且 agent 拆得掉自己的掛鉤（`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §三）。
4. OpenCode 的 `fixes` 情境是 **reject**：`opencode run` 在第一個 `session.idle` 就結束，
   外掛 API 沒有能讓一回合繼續的掛鉤——這一格量到的就是這個限制，不是失敗被藏起來。
   外掛因此在 `opencode run` 裡**不跑**停止檢查（回饋送不到，只會拖時間）；交件照樣在 `dispose()` 做。
5. 每個情境只跑一次（n=1）；這是接線的證明，不是統計。
6. 這一份結果是**對抗審查修正之後**的程式碼跑的（同日 14:59 起；裁決 §十一）：契約鎖、hermetic 驗證沙箱、
   路徑元件規則、非同步外掛都在裡面。引用那一條是**事實主張**，引文對的是委託者釘住的快照。
