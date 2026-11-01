# DECISION 20261101 — L001：C 臂 venv 加 `--system-site-packages`（共用量具修改）

**日期**：2026-11-01（round 827）
**決定**：修改 `/srv/vlab/bin/cell.py:52` 的 venv 建法，`python3 -m venv <dir>` →
`python3 -m venv --system-site-packages <dir>`。只影響**此後新建**的 C 臂 venv；
已建的 6 個 venv（含 e009 在用的 cf62d258、以及先行凍結的 e010 用的 683bbb83）不受影響。
舊實驗（e001–e008）的結果不因此改變，也不重述。

**理由**（證據鏈，全部可重現）：
1. e008（dabench）唯一兩臂結果分歧的 2 格（dab_039 A 過 C 掛、dab_378 A 過 C 6/8）的
   C 臂 python 環境都缺 pandas/scipy：
   - dab_039 C：`ModuleNotFoundError: No module named 'pandas'/'scipy'`，`pip install`
     因 bwrap 無網路失敗（`Temporary failure in name resolution`）→ 任務依賴的
     Shapiro–Wilk 算不出 → answer.txt 從未寫出 → scorer 判 missing → 0/1。
   - dab_378 C：agent 手寫統計，kurtosis 慣例混合（biased 4 階矩 ÷ unbiased 變異數）
     → −1.17 對 A 的 scipy 值 −1.13 → 6/8。該格 0 條 Vacant 訊息。
2. 環境差異的唯一來源是 cell.py 本身：`cell.py:143` 只給 C 臂建 venv、`cell.py:91`
   只給 C 臂把 venv/bin 前置 PATH、`cell.py:52` 建 venv 時未帶 `--system-site-packages`
   → venv 的 python 看不到系統 site-packages（pandas 2.1.4／scipy 1.11.4／numpy 1.26.4
   都在 /usr/lib/python3/dist-packages，A 臂直接可用）。
3. 產品側排除：`vacant install` 不建 venv、不改 PATH／PYTHONPATH（adapters/agents.py；
   hook 以 `sys.executable -m` 執行）；vacant_network 全域無相關程式碼。
   C 臂在 dab_039 收到的 2 次 turn-end 退回是事實陳述（answer.txt 確實不存在）且 advisory。
4. 成本多出（C 562 對 A 374 呼叫）69% 集中在 3 個**兩臂都過、零退回**的格
   （dab_688/723/249，模型試錯循環）→ 不是回應 Vacant。

**風險與守則**：
- **pip「已滿足」跳過風險**：系統 python 已裝 vacant_network 0.9.1；加上
  system-site-packages 後，`pip install <src>` 若認同已滿足而跳過，venv 將用到系統
  0.9.1 而非 pin 的 commit。→ 建完每個新 venv 必驗：
  `venv/bin/python3 -c "import vacant_network, pandas, scipy, numpy"` 中
  `vacant_network.__file__` 必須在 venv 的 site-packages 內（不驗不發）。
  若跳過發生，補 `--ignore-installed vacant-network` 於 cell.py 的 pip install。
- 系統 jsonschema 4.10.3／cryptography 41.0.7 低於 vacant 需求（4.21／42）→ pip 會照裝
  venv 內新版並遮蔽系統版，行為不變。
- 本修改只改「C 臂 agent 的 python 看見什麼套件」，不改評分、不改 bwrap 隔離、
  不改 A 臂、不改 `~/.vacant` 的結構與用量計量口徑。
- 舊 venv（含 e009 在用的）維持原狀；e010（vacant_sha 683bbb83）的 venv 在修改前
  以舊 cell.py 先行建好凍結，保證 Axis 2 實驗的量具不中途變動。
- 撤銷方式：把 `--system-site-packages` 刪掉、對受影響的新 venv 重build 即回到舊行為。

**驗收**（＝ L001 §3 判準 C1–C4，見 `~/dev/ops/loop/L001.md`）：
C1 新 C 格可見 pandas/scipy/numpy；C2 dab_039-C 寫出 answer.txt（理想＝過）；
C3 smoke 6 題無新「A 過 C 掛」；C4 對照格 C/A 呼叫比 ≤1.5。C3 未達 → 撤本修改。
