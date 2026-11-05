# 當前狀態（2026-11-05，r1029 審查輪）

## 本輪（vq-kpb，in_progress）
- **P0 ✔**：2aa0c077 已含於 auto/qwen27b（c7077528）；五項修復逐項核對在樹；152 reqloop 測試綠。
- **P1 發射中**：3 草稿 × 2 臂 × 1 輪單格對照 → `~/dev/ops/effects_p1_20261105`（獨立目錄；
  base 逐檔 hash＝凍結；before＝凍結 independent.json；after＝當前 HEAD＋獨立評分；缺值 UNKNOWN）。
  1/6 完成（dab_507 generic）；progress.json 實時；收後出 before→after 表＋成本真值。
- **P2 ✔（TDD 綠）**：localized 提示在 crash→放棄觀察時點名「禁止裸 except 靜默吞解析錯」
  （dabstep-1753 失效模式）；generic 臂不變；155 reqloop 測試＋selftest 11/11。

## 待辦（按序）
1. **vq-kpb**：P1 收（6 格＋獨立評分）→ before/after 表、api_model_calls_true/tokens_true/wall_ms_total、
   generic 3 格 regression 檢查；commit P2 代碼。
2. **vq-6rp**（P2）：dabstep-1753 硬缺口——先要需求方可執行 acceptance 口徑；無口徑＝H-1 前提不成立。
3. **vq-5nz.6**（P3，待點名）：G2 停滯換方法 8 格——點名前不發射。
4. **vq-p9g**（P3）：CI 穩定 xpass 後除 xfail marker。**vq-ifn**（P3）：P99 門重設計。

## 紅線（每輪照舊）
- 未點名＝未發射；不讀 /srv/eval hidden 與 scorer.py；不向修復模型餵 hidden 答案/評分反饋。
- 不改 effects 凍結批；缺值 UNKNOWN（不填 0/PASS）；不 push、不動 main；只跑相關測試；不宣稱提升。
