"""adapters — **把收件口接到 agent 身上**：pi、Claude Code、OpenCode、Codex（＋任何 CLI）。

這支在架構裡承重什麼（`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §四）：

四個 agent 的共通點不在模型通道（Claude Code 33 個 hook 事件、Codex 12 個，
**沒有一個**在模型請求層；Codex 用 ChatGPT 登入時根本沒有 HTTP 線路——
`DECISION_20260920_AGENT_HOOKS_MEASURED.md` §二）。共通點是這五個，由強到弱：

1. **行程＋工作區邊界**：四個都能 headless 跑一題、在一個目錄裡工作、結束。
   ⇒ `run.py`（`vacant do`）：隔離工作區 → 跑 → 收件口。零設定、零 hook 也成立。
2. **shell 工具**：四個都有 ⇒ `vacant check`／`vacant submit` 任何一個都叫得到。
3. **技能／指示檔**：Agent Skills（SKILL.md）四家的文件都說會讀（有沒有真的列給模型，
   見 `ops/intake/evidence_20260924/SUMMARY.md` 的 skill 欄）⇒ 告訴 agent 契約在哪、怎麼先自驗。
4. **生命週期掛鉤**：四個都有「工具執行前、可否決」與「回合／工作階段結束」
   （格式各不相同）⇒ `hook.py` 把它們正規化成同一組事件，由同一份政策判斷。
5. **模型通道**（`vrun/` 的 proxy）：只剩**選配觀測**，從不決定收件。

**保證不建立在 1–4 上**：agent 拆得掉自己的 hook（實測）、shell 可以繞過任何字串規則。
保證在收件端（`intake/recipients.py`）：不管 agent 做了什麼，目的端只收經過驗證與
批准的那個版本。1–4 的價值是**讓 agent 在交件前就看到判準**（增效）、以及**留下它做了
什麼的紀錄**（觀測），不是讓 agent 不能作惡。
"""
