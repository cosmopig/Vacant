# vacant-dev＋1003／1004 複製批次（任務導向 94 題 → DABstep 79 題）— RUNLOG

預註冊：`decisions/prereg/PREREG_20261002_VACANTDEV_REPLICATION_V37.md`。時間 UTC。

| 時間 | 事件 |
|---|---|
| 09:53 | 人類：「把這些東西都丟去 vm 上測試，用 1003 1004 去跑，可以跑很久沒關係，儘速丟上去」；09:57「先以任務導向的那些」 |
| 09:54 | vacant-dev（Ubuntu 24.04、8 核、7 GB、磁碟剩 4 GB、load 0）；1003／1004 都載著 `gemma-4-12b-it-qat`（262k context）、`reasoning_effort: none` 時沒有 reasoning、延遲 1.2–1.5 秒。分身專用的 .102 不碰 |
| 09:58 | 舊實驗的 repo 副本都只有幾 MB，清不出空間 ⇒ 改成「格子打包進 chunk 後只留 DONE／meta／score／vacant_check」（`cleanup_packed.sh`）；DABstep 的 7 個資料檔在 79 題之間用硬連結（23 MB 一份） |
| 10:00 | `setup_vd.sh`：apt 補 pipx、python3-pandas（2.1.4）；wheel 在這台重建 ⇒ **sha256 `92ddc44d…` 與 Colab 那顆相同**、114／114；node v22.23.2、pi 0.87.1。第一次圍牆自我檢查失敗：bwrap 要蓋 `/content` 但這台沒有 ⇒ 建空的 `/content`，重跑通過（負控制 OK）。代理 upstreams `g1003`／`g1004` |
| 10:02 | 經代理打兩台：都沒有 reasoning。磁碟剩 3.0 GB |
| 10:03 | 預註冊凍結（本 commit） |
