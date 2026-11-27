# 題庫重建紀錄（2026-11-27，Haiku 接手；DECISION 雲端修正 C4）

- 來源：公開 `https://github.com/exercism/python`，clone 的 HEAD＝`479f11b44b02337b0413e805b948491c2179615a`
  （2026-11-07），**和原 manifest 釘住的 commit 相同**。
- `config.json` sha256 前綴＝`ebf067c6e09a6e11`，**與 11-27 決策檔釘住的前綴一致**（HEAD 與釘住 commit 的 config.json 都是這個值）。
- 重建方法：`build_exercism_py_unused.py --take-all`（polyglot 排除清單取自 `exercism_py_pool.json` 的 34 個 slug；
  這 34 題的目錄只用來取 slug，不進題庫）→ 106 題 425 檔。**逐檔 sha256 與 repo 內 `exercism_py_pool.json`／`exercism_py_hard.json`／
  `exercism_py_unused.json` 的 `files_sha256` 全部一致**（425／104／161 檔，0 缺、0 不符）。
- 切半：`build_ctl16.py --tasks <37 題>`（固定種子 20261127），產出 `ctl37`（修正 3 的 37 題候選）與 `ctl_smoke4`
  （ex_matrix／ex_point_mutations／ex_acronym／ex_bob）。每題參考解（`.meta/example.py`）兩半都過、空殼兩半都不過
  （MANIFEST 的 verification 欄）。manifest 副本：`bank_ctl37_MANIFEST.json`、`bank_ctl_smoke4_MANIFEST.json`。
- ex_alphametics 單獨重建驗證：`reference failed acceptance half: ok=False 4/5` → 與修正 3 一致（排除；hard＝19 題）。
- hard 候選＝`exercism_py_hard`（26）裡測試方法數 ≥10 的 20 題，扣 alphametics＝19 題；加原 18 題＝37。
- 題庫放在容器內 `/opt/ctlwork/bm_tasks/`（不在 repo、worker 讀不到）；容器是暫時的，要重建就照上面的指令。
- 與 9B 時代的差異：repo 外的題庫目錄從 `~/dev/ops/ref/bm_tasks/` 改成 `/opt/ctlwork/bm_tasks/`（計畫檔的 `bank` 欄隨之改）。
