# 環境決定：這台 VM 沒有 ImageMagick／PIL／pip——去背改純標準庫

**2026-08-18 執行端拍板**（規則七授權，不需要 sudo，所以不必等人類）。

## 撞到的事

`ops/exhibit/cutout.sh`（既有檔案）呼叫 `magick`。這一輪第一次真的去跑它，
撞到 `magick: command not found`。查了一輪：

- `command -v magick` → 找不到，整個檔案系統 `find / -iname '*magick*'` 也沒有。
- 沒有 PIL（`python3 -c 'import PIL'` → ModuleNotFoundError）。
- 沒有 pip（`python3 -m pip` → No module named pip），所以也裝不了 PIL。
- 沒有 node/npm、沒有 docker/podman。
- `sudo -n true` → `a password is required`。裝 ImageMagick 要 sudo，
  是規則七明訂三個要停下來等人類的事之一。

**這其實不是新聞**：`genimg.sh`（既有腳本，不是我寫的）檔頭本來就寫
「這台沒有 ImageMagick 也沒有 PIL」，它自己驗證 PNG 尺寸時就是用
`struct` 手讀 IHDR，不敢碰 PIL/magick。`cutout.sh` 顯然是在別的環境
（或設想中的環境）寫的，這台從沒真的跑過它就進了 DECISION_PIPELINE.md
被記成「已實測」。**這是這一輪要更正的一筆紀錄**：cutout.sh 本身能不能跑
在這台 VM 上没有被驗過；「淹沒填色去背比 -transparent white 好」這個
演算法層級的結論仍然成立（那次比較的邏輯不依賴用哪個工具實作），
但「cutout.sh 這支檔案能用」是錯的，要修。

## 決定

寫 `ops/exhibit/cutout.py`——純標準庫（`zlib` + `struct`），自己實作：
1. PNG 解碼（只支援 8-bit 非交錯 RGB/RGBA，codex 生出來的都是這個格式，
   `decode_png` 撞到別的格式會直接報錯不猜）。
2. 從四角淹沒填色（比對「目前像素」與「該角種子色」的距離，不是比對
   前一個像素，避免沿漸層一路吃穿）。
3. Trim 到 alpha>0 的 bounding box。
4. PNG 編碼（RGBA、filter type 0）。

`cutout.sh` 改成瘦身包裝，呼叫 `cutout.py`——**介面不變**（其他輪次、
`SPRINT_PROMPT.md`、`PLAN.md` 裡對 `cutout.sh` 的呼叫方式不用改）。

另外寫 `ops/exhibit/paste_on_dark.py`（同樣純標準庫）——SPRINT_PROMPT.md
要求「貼在深色底上看一次確認沒破洞」，這支就是那一步的工具。

## 驗證，不是猜

用 `design/sprites/sp_write.png`（既有、已知乾淨的角色圖）跑過一次：

```
$ bash cutout.sh ~/vacant/design/sprites/sp_write.png /tmp/sp_write_cut.png
  /tmp/sp_write_cut.png  490x725  不透明比例 0.62
```

1536×1024 裁到 490×725（trim 生效），不透明比例 0.62（不是 >0.97 的
「背景沒被吃掉」也不是 <0.25 的「主體被吃掉」）。貼到深色底上（用
`paste_on_dark.py`）用 Read 工具肉眼看過：眼白、鞋子、上衣邊緣都完整，
沒有破洞——跟 DECISION_PIPELINE.md 記錄的失敗模式（`-transparent white`
吃掉紙疊／鞋子／眼白）比對，這次沒有那個問題。

## 什麼情況下這個決定該被推翻

- 人類跑 `sudo apt install imagemagick`（或給了可用的 pip/PyPI 鏡像）
  之後——那時可以直接用 `magick`，不必自己維護 PNG 編解碼。
  但沒有急迫性：純標準庫版本已經驗過能用。
- 如果之後撞到 16-bit 或交錯（interlaced）PNG，或 codex 開始吐調色盤
  （colortype 3）格式，`cutout.py` 會直接報錯——那時再擴充，不要事先猜。
