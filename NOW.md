# 當前狀態（2026-11-05，r1028 收尾）

## 本輪完成（vq-5nz.18，已閉）
本地 readable 門 vs 獨立 scorer 分歧（effects_20261105 凍結批）根因判定＋修復：
- **dabstep-1273（3 格假 PASS）**：`_scheme_fee_avg` 靜默排除 is_credit=null 行（0.117667）；
  owner 口徑含 null（0.120132；effects 純數字 0.120132 得 reward 1）→ 歧義行改判 UNKNOWN。
- **dab_055（1 格假 FAIL）**：`mean_int_col` 靜默忽略 544 個 '630308[495000-801000]' 型格
  （2199.55）；owner 口徑取首數值（2081990 得 reward 1）→ 歧義格改判 UNKNOWN。
- 重排 plain/kv 檢查：先驗交付物格式（FAIL）再重算（可 UNKNOWN），保 e014 bad 草稿 FAIL 紅線。
- 防洩漏：重算值與兩解讀值皆不進 detail/evidence。
- 驗證：effects 6 格重放全 UNKNOWN（原假判定消失）；tests/test_reqloop* **125 passed**（+3 先紅後綠）。
- dabstep-1753 4 格＝本地與獨立同向未解決→模型側硬缺口，轉新票 **vq-6rp**（待點名，不改驗證器）。
- 紀律：未讀 scorer.py/hidden；effects 只讀；0 模型呼叫；未 push。

## 待辦（按序）
1. **vq-6rp**（P2，open）：dabstep-1753 硬缺口——先要需求方可執行 acceptance 口徑；無口徑＝H-1 前提不成立。
2. **vq-5nz.6**（P3，open，待點名）：G2 停滯草稿換方法 8 格 2 輪——點名前不發射（未點名＝未發射）。
3. **vq-p9g**（P3，open）：CI 穩定 xpass 後除 xfail marker（先查 r1028 CI 終態＋穩定性）。
4. **vq-ifn**（P3，open）：P99 門重設計——對回歸模式敏感的鑑別測試（r1018 證據）。

## 紅線（每輪照舊）
- 未點名＝未發射：G2/G3 預註冊批（vq-5nz.6 等）點名前 0 發射。
- 不讀 /srv/eval hidden 與 scorer.py 設計解法；不向修復模型餵 hidden 答案/評分反饋。
- 不改 effects 凍結快照/manifest/結果；缺值 UNKNOWN（不填 0/PASS）；不 push、不動 main。
- 只跑相關測試；不宣稱提升；成本缺值 UNKNOWN。
