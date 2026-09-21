#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把下午第三批（真時鐘、跑在現在活著的那一份）與兩支 GIF 補進 PROVENANCE。

只加不改：前兩批的段落一個字都不動（包含它們自己承認的量具缺陷）。
"""
import hashlib, json, os

ROOT = ("/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/wf_32a45899-6ee-1"
        "/ops/exhibit/twin/evidence_visible_20260921/arrival_beat")
P = os.path.join(ROOT, "PROVENANCE.json")
HM = os.path.expanduser("~/Documents/GitHub/vacant_hm/world3/index.html")
sha = hashlib.sha256(open(HM, "rb").read()).hexdigest()

doc = json.load(open(P, encoding="utf-8"))

doc["read_this_first"] = [
 "這個目錄裡有四批，量的是同一件事但量具不同。**引用之前先看這一份，不要把四批的數字混講。**",
 "看畫面：`v2_clockstep/GIF_busy_before_vs_after.gif`（主證據，會動）與 "
 "`v2_clockstep/SHEET_busy.jpg`（同一件事的靜態版）。",
 "看毫秒：`v3_wall_liveHEAD/SUMMARY_WALL.json` 的 `callbackToPaintMs`（抵達層自己的延遲）。",
 "有解析度的是 v2_clockstep（畫面）與 v3_wall_liveHEAD 的頁內計時（毫秒）。"
 "另外兩批各有已知的量具缺陷，寫在下面，刻意不刪。",
]

doc["batches"]["v3_wall_liveHEAD"] = {
 "when": "2026-09-21 傍晚（14:48 兩臂＋16:06 兩臂）",
 "status": "這一批證的是**現在活著的那一份碼還會動**，不是毫秒解析度的畫面證據",
 "why_it_exists": [
  "v2_clockstep 那七臂跑的時候，index.html 的 sha 是 ebabae34／8e2ec474——"
  "別的 agent 一直在改同一個檔。**收工當下活著的那一份（" + sha[:16] + "）沒有任何一臂跑過它。**",
  "這四臂補的就是這個：同一條產品路徑（寫快照 → bridge.js 輪詢 → onSubmission → arrivals），"
  "跑在活著的那一份上，加一臂 `?arrive=0` 負控制。",
 ],
 "subject_sha256": sha,
 "arms": {
  "W_after_0 / W_after_1": "抵達層開，一人投卡（只有投卡前那一張截圖＋頁內計時）",
  "W2_after": "抵達層開，一人投卡，連續截圖＋錄影",
  "W2_negctl_arrive0": "負控制：同一份碼 + ?arrive=0（單變數）",
 },
 "what_it_shows": [
  "四臂都走真路徑：`arrivals.total` 1／1／1／**0**（負控制）。",
  "`callbackToPaintMs`＝21／31／183 ms（抵達層自己的延遲：回呼進來到那封信第一次被畫出來）。",
  "`writeToCallbackMs`＝4359／2153／3401 ms——**這一段是 bridge.js 的輪詢**，不是這次改的層。"
  "設定 1000 ms，這台被餓到中位 2.7–6.1 秒。",
  "陶牌上的排隊欄位在真路徑上也有：`queueShown` 記到 `place:1` ＋那個人的代號（圖釘罐／木托盤）。",
 ],
 "🔴 defect": "連續截圖的**檔名時間是假的**：這台 load 300–900，Playwright 拍一張要 2.5–3 秒，"
              "`want+150ms` 那一張的 `real` 是 +2811ms。⇒ 這一批**只有零點那一張**（與回呼同步拍的）"
              "可以拿來讀時刻，中間那些只能讀「有沒有那封信」。對照表 `SHEET_wall_liveHEAD.jpg` "
              "因此只放兩格。",
 "not_in_repo": "兩支 `.webm`（8–10 MB，這台只跑得出 1–2.6 fps）留在 scratchpad。"
                "**那個 fps 是量測機的性質不是展場機的**，收進 repo 只會讓人誤讀成展件會頓。",
}

doc["motion_artifacts"] = {
 "what": "會動的對照（給不看碼的人）",
 "files": [
  "v2_clockstep/GIF_busy_before_vs_after.gif — 🔴 主證據：導演正在演別人的故事時投卡，"
  "左邊改動前逐格一樣、右邊改動後信落進投遞口，陶牌出現「投遞口 ▲1 <他的代號>」",
  "v2_clockstep/GIF_negctl_vs_after.gif — 負控制對照：同一份碼只把抵達層關掉",
 ],
 "why_gif_not_mp4": "這台機器的 ffmpeg 壞了（`Library not loaded: libx265.215.dylib`），"
                    "而修它要動 brew、這台正在跑展件（8420）。GIF 用 PIL 就寫得出來。",
 "honesty": "GIF 的每一格來自**假時鐘**批次，所以每一格的時刻是真的（零點＝onSubmission 回呼）；"
            "但**播放速度是給人看的，不是現場秒數**——這句話印在每一格上。",
}

doc["where_the_change_lives"] = {
 "file": "vacant_hm/world3/index.html（另一個 repo，**未提交的工作樹**，同時有十幾個 agent 在動）",
 "block": "`/* ══ 抵達層` → `/* ══ 等待態` 之間 397 行，外加 10 個呼叫點",
 "verbatim_copy": "ARRIVAL_LAYER_extract.js（逐字抄本＋sha＋呼叫點行號）"
                  "——**不是可 apply 的 patch**，是為了那棵樹被 reset 之後這批證據不會指向空氣",
 "revert_in_one_line": "網址加 ?arrive=0",
 "gate_kept_on_purpose": "`Object.keys(byAgent).length >= 6`（劇團到齊才開演）**沒動**。"
                         "拆開抵達與成形之後它可以原封不動留著，這正是拆開的意義。",
}
json.dump(doc, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(P, os.path.getsize(P), "bytes · sha", sha[:16])
