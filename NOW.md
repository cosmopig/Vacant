# 現在（第 1215 輪後，2026-11-07 21:42 UTC）

## r1215：CI 巡燈（無新工單：vq-el4 面已清空，open/doing 皆空）
- **auto/qwen27b 2b6e6f92（HEAD，r1214 後狀態）：🟢 GREEN 5031 passed / 0 failed / 74 skipped（840s）**。
  r1213/r1214 的 commit 全部被 HEAD 樹收編，CI 已補齊（ea66f391 🟢 5031/0；2b6e6f92 🟢 5031/0）。
- auto/argon 2db8afa5：🟢（5031/0，11-06 審查指示1 的合併對象，狀態不變）。
- **auto/worker b7cb338d：🔴 6 failed——診斷完成，非本分支/本次變更造成**：
  - 3 例（dabstep10 draft sha、effect_manifest、全庫 manifest 掃鎖）：worker commit **bbd54fff**
    「Fix merchant identification error in dabstep-10-pi-C」改了凍結草稿
    `ops/reqloop/g2/smoke_e014/dabstep-10-pi-C/draft/answer.txt`（624b60c5…→c834c2ee…），
    effect_manifest pin 破損。qwen27b/argon 樹仍是 624b60c5（＝pin），故只紅 worker。
    這是 guard 按設計抓到了凍結快照被改（H-0 同型防線在位）。
  - 3 例（real_slice_dab055 三測）：worker 樹把 `ops/reqloop/g2/real_slice_dab055/manifest.json`
    提交成**絕對路徑 symlink**（指向 /home/user1/dev/wt/worker/…/smoke_e013/dab_055-pi-C/manifest.json，
    目標在 worker 自己 worktree 也不存在）→ CI worktree（/var/tmp/ci-wt）FileNotFoundError；
    同樹還混入 `dab_055-pi-C~HEAD` symlink 與 `manifest.json~auto_argon` 備份檔（後者內容
    ＝qwen27b 的 manifest.json 同 blob）。合併解衝突殘骸被 auto-commit 掃進去。
  - **處置：不動 auto/worker**（活躍 agent 的 WIP 分支，末次 commit 19:49；且修法含產品判斷：
    草稿改動要麼還原、要麼重新凍結——重新凍結需授權，不歸我裁）。留修復 recipe 給 worker/審查：
    1) 還原草稿＝從 auto/qwen27b 取回 624b60c5 版（或經授權重凍 c834c2ee）；
    2) `git rm` 該 symlink，以 `manifest.json~auto_argon`（或 qwen27b blob dcae41d7）還原為正檔，
       刪除 `dab_055-pi-C~HEAD`、`manifest.json~auto_argon` 兩件殘骸。
- 本輪零產品改動、零模型呼叫、零 commit（worktree 乾淨）；無新工單可領。

## 下一步
1. 等審查新派工／G2.5 後續（主線＝G2.5 自動需求抽取）。
2. 下輪巡 CI：預期 worker 仍紅直到其自修；qwen27b/argon 綠燈已齊。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden/scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照／官方鎖檔 eval_phase3_glm53.json；成本缺值＝UNKNOWN 不填 0。
