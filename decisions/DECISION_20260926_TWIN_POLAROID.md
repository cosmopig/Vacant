# DECISION 2026-09-26 — 分身做完之後，給觀眾一張拍立得（手機上，他自己決定要不要分享）

人類 2026-09-26：

> 「最後一定要有可以給使用者回饋到他手機上的類似拍立得的東西，讓他可以分享。」
> 「現在每個畫面一堆資料，要最小程度的留下東西。」
> 「拍立得上要放官網 `https://vacant.cosmopig.com` 的 QR code。」
> 「最後資料都先不刪我自己處理」（＝閉展清除 `close_exhibition.py` 先不跑、不自動化；
>   **觀眾自己按撤回的那條照舊要真的刪**）

分支：Vacant `feat/twin-polaroid`、vacant-world-cloud `feat/polaroid`。**都沒有 push、沒有部署。**

---

## 一、拍立得長什麼樣（只有四樣）

> **v2（同日稍晚，§十、§十一）改了四件事**：真相框、相片換成黏土世界（姿勢圖）、那一句改成
> **分身真跑自己寫的**（範例不再有人寫的句子、逐字抄錄時留空不補字）、QR 改 9 px。
> 下表與 §四 已照 v2 改寫；v1 的四張範例（`evidence_polaroid_20260926/polaroid_{1..4}_*.png`，
> 上面那句是人寫死的）留著當歷史，**不再是範例**。

範例（**合成特質**，不是真人；那一句是分身真跑寫的）：`ops/exhibit/twin/evidence_polaroid_20260926/v2/polaroid_p{1..8}_*.png`。

1080×1350（4:5：接近拍立得的 0.82，又是社群直式貼文的原生比例，分享不會被裁）。

| 位置 | 內容 | 來源 |
|---|---|---|
| 相片窗 | 他的分身站在黏土世界的空舞台（`s00` 板）頂光下；有姿勢圖的舉著寫好的紙 | `cast_id`（§二）→ `assets/poses/cNN_show.png`，沒有就 `assets/cast40/cNN.png`（§十一） |
| 白邊下緣 | 最多兩行、手寫感的字：**分身自己寫在 PLAN.md 第一行的那句** | 去 markdown／成對的外引號；兩行平衡斷行；放不下從尾巴截、補「…」；**逐字抄了觀眾原文 ⇒ 留空**（§十） |
| 小字 | `2026.09.26 · VACANT · 收據 xxxxxxxx` | 展場本機時區日期；收據＝`verdict_hash` 前 8 碼 |
| 右下角 | 官網 QR（`https://vacant.cosmopig.com`，**不帶任何參數**） | `ops/exhibit/twin/qr.py`（stdlib） |

**不放**：判決長文、統計、說明、記號、觀眾打的任何一個字。字型：jf 粉圓 2.0（SIL OFL 1.1，
原樣附在 `assets/fonts/`，sha256 釘死；OFL 聲明見 `OFL_NOTICE.txt`）。字型畫不出來的字（emoji）
**丟掉不畫成豆腐框**（`dropped_glyphs` 記數）。

相框：**素材線的真相框**（`assets/polaroid/polaroid_frame.{png,json}`，逐 byte 抄自
`vacant_hm-assets-20260926/polaroid/`；放法見 §十一）。也可設 `VACANT_POLAROID_FRAME_DIR` 換掉；
**放不下（字框太小、QR 靜區出紙、互相重疊、模組 < 8 px、相框縮放後比卡面高、窗下緣沒有白邊）
⇒ 退回程式畫的佔位相框並在 `frame_note` 寫理由**，不會畫出一張壞的。

## 二、`cast_id` 單一來源

電視原本在前端 `pickCastFor` 自己算。拍立得在後端生成，兩邊各算一次就有兩張臉的風險。
⇒ **逐字移植到後端**（`polaroid.pick_cast_for`），`build_view` 的 `people[]` 多一欄 `cast_id`，
`screen_contract.cast_from = "people[].cast_id"`（電視那一側由 T 線改成「有就用它」，本線沒碰 vacant_hm）。

判準（`tests/test_twin_polaroid.py`）：node **真的跑電視頁裡那一段 JS**
（`cast_parity_node_check.mjs` 從 `world3/index.html` 切出 `COLOR_ANCHOR`…`pickCastFor` 結尾），
對 cast40 全表 × 800 種卡（形狀 6＋null＋空字串＋不存在的值＋缺鍵，色系、質感同法）逐一比：
**0 不相等**。負控制：把平手規則改成「取最後一個」⇒ **328 不相等**（量具不是恆綠）。
cast40 manifest 與 40 張精靈圖附進 `assets/cast40/`，與 vacant_hm 那份**逐 byte 相同**（有測試）。

⚠ 誠實邊界：JS 的 `COLOR_ANCHOR["constructor"]` 會拿到原型上的函式；卡上的色系是伺服器收斂過的
枚舉或 null，那種值進不來，後端不去模仿那個怪行為。素材壞了 `cast_id` 回 `null`（電視退回自己算），
**不准讓整份 view 因此炸掉**。

## 三、生成（VM 端 twinlink loop）

```
loop 每一輪：ingest → cloud-erase（§六）→ generate → **polaroid** → publish → export
```

* **只發給「做成了」的那一跑**：`engine=vacant_run:pi:*` ＋ 有 `decision` ＋ 有 `verdict_hash`
  （`twinlink.run_outcome == "made"`）。`accepted=null` 不影響——「沒有客觀標準、不判」與
  「做完了、有收據」是兩件量得到的事。
* 退化／基建壞了（`fallback_deterministic`、`lmstudio:*`、`infra_void`、沒打到模型、沒 PLAN.md）
  ⇒ **不發**，鏈上記一列 `polaroid_skipped`（只有類別），手機上照實說「這一次沒有做成」。
* 圖存進 **twinvault**（`plain/<slug>/polaroid.png`，鏈外、撤回刪）——它畫著分身的決定＝
  觀眾特質的衍生物，**照鏈外原文的規格處理**。鏈上只記一列 `polaroid_made`：ref、cast_id、
  位元組數、版面旗標、QR 內容；**不記那句話**（這一列也過 `assert_payload_clean`）。
* 畫到一半被撤回（serve 那個行程刪了檔案庫）⇒ 剛寫下的圖當場刪、記 `late_polaroid_discarded`。

### 依賴：Pillow（ops 腳本，可選）

CLAUDE.md 說 runtime 依賴只有 `cryptography`——那講的是 `vacant_network/` 套件。這一支在 `ops/`。
理由：要貼有 alpha 的精靈圖、要把中文字點陣化；後者 stdlib 做不到（要自己寫 TrueType 光柵化），
無頭瀏覽器更重。**做成可選**：沒有 Pillow ⇒ `polaroid.available()` 回 `(False, "pillow_missing…")`，
**不寫鏈**（裝好之後下一輪自動補），stderr 講一次，分身照樣上螢幕、手機照樣拿到結果——少的是那張圖。

🔴 **2026-09-26 查過：vacant-dev（VM）的系統 `python3`（3.12.3）沒有 Pillow。** 上線前要裝
（`sudo apt install python3-pil`，或 loop 改用有 Pillow 的 venv 並設 `PYTHON=`）。VM 上有 Noto CJK，
但不靠它——字型隨 repo 走。

## 四、QR：掃得到是量出來的

* 內容：`https://vacant.cosmopig.com`（27 bytes ⇒ v3-M，29 模組）。**不帶 sub_id、記號、utm**——
  分享出去的圖任何人都看得到。
* 模組 **9 px**（碼 261 px ≈ 圖寬 24%；v1 是 8 px／232 px），靜區 4 模組。v2 靜區**不塗色**、
  保留相框紙紋，但先量那一塊最暗的點（`qr_quiet_min_l`，範例 218）；< 200 才塗紙色。
* 驗收（`polaroid_qr_check.py`，外部解碼器 OpenCV 5.0 `QRCodeDetector`，**拿範例 PNG 本身解**）：
  4 張範例 × {原圖、540 px 縮圖、模擬手機在 10／15 cm 拍螢幕} **全部解回官網網址**；
  負控制：QR 塗掉 ⇒ 解不出；同位置換別的網址 ⇒ 解成那個別的網址（`qr_decode.json`）。
* **最小模組尺寸**（`v2/qr_sweep.json`，每格 16 次＝兩張真跑範例 × 8 種子，模擬手機拍螢幕，**素材相框**上）：

  | 模組 | 10 cm | 15 cm | 20 cm | 25 cm |
  |---|---|---|---|---|
  | 5 px | 13/16 | 0/16 | 0/16 | 0/16 |
  | 6 px | 16/16 | 4/16 | 0/16 | 0/16 |
  | 7 px | 16/16 | 12/16 | 0/16 | 0/16 |
  | 8 px（v1 採用） | 16/16 | **14/16** | 0/16 | 0/16 |
  | **9 px（v2 採用）** | **16/16** | **16/16** | **16/16** | 3/16 |

  **為什麼從 8 改 9**：v1 的表（佔位相框）8 px 在 15 cm 是 16/16；換上素材相框（紙色較深、有紙紋）
  後同一格掉到 14/16。開發時另做一次 80 次對照（同種子、同兩張卡，只換相框；腳本在暫存區、沒進版控）：
  素材相框 70/80、佔位相框 80/80；只把靜區塗白 79/80、塗紙色 72–74/80——門檻在「那一塊夠不夠白」，
  而塗白會在紙上浮出一張貼紙。**選了加大一級**：9 px 在 15 cm 16/16，20 cm 也 16/16。代價是碼
  大了 12%（232 → 261 px），字那一欄窄了 30 px（一行約 14 字）。

  物理模型（寫死在 `CAMERA`）：手機頁把拍立得畫成 min(92vw,420px)；390 pt ≈ 65.9 mm ⇒
  9 px 模組在螢幕上 ≈ **0.51 mm**、整個碼 ≈ 14.7 mm；掃碼 app 分析 1920 px 寬、69° 視角的預覽畫面。
  ⇒ **20 cm 以內掃得到；25 cm 在這個代理量下大多解不開**（照實記，不算過）。
* 範例外部解碼（`v2/qr_decode.json`，OpenCV 5.0 `QRCodeDetector`，拿 8 張範例 PNG 本身解）：
  原圖 8/8、540 px 縮圖 8/8、模擬手機 10 cm 8/8、15 cm 8/8、（20 cm 8/8，不算門檻）；
  負控制：QR 塗掉 ⇒ 8/8 解不出；同位置換別的網址 ⇒ 8/8 解成那個別的網址。
* 誠實邊界：「手機拍螢幕」是**模擬**（縮放＋旋轉＋透視＋模糊＋對比漂移＋雜訊＋JPEG），
  OpenCV 比 iOS／Android 內建相機的解碼器弱（偏保守），但它仍是代理量——**要在展場用兩支真手機對拍一次**。
* 要更小：改 `QR_MODULE_PX`（下限 `QR_MIN_MODULE_PX=8`）並重跑
  `polaroid_qr_check.py --sweep --samples v2/samples.json`；上表是代價。

## 五、送到手機、分享、收據帶走

* **傳送**：沿用 `publish` → `POST /api/result`，多三個欄位：`outcome`（made／not_made）、
  `polaroid_png`（dataURL）、`receipt`（收據副本）。雲端存 `polaroids/<id>.png`、`receipts/<id>.json`，
  `/api/status/:id` 多回 `outcome`／`polaroid_url`／`receipt_url`。
* **權限**：沿用 `/api/status/:id` 的模型——**id 就是權限**（randomUUID，122 bits）。
  `GET /api/polaroid/:id`、`/api/receipt/:id`：非 UUID ⇒ 400、猜的 id／撤回後 ⇒ 404、
  `Cache-Control: private, no-store`、`X-Robots-Tag: noindex`；**沒有任何列舉口**帶出它們
  （`/api/all` 刻意不帶；拍立得上的收據 8 碼也**不是查詢鑰匙**）。有測試。
* **手機頁**（極簡）：
  * 等待那一屏只畫**一句話**（「你前面還有 N 個人」／「下一個就是你」／「輪到你了」）＋**他的記號**。
    其餘（階段條、計時器、長提示、記號說明、走路小人）由 CSS 收起來；例外：連不上伺服器時那一句更正
    要出現（凍住的序位會騙人）。示範分身那一行留著。`?full=1` 回詳細版（工作人員）。
    ⚠ 那些元素仍在 DOM、JS 照舊寫字——WAIT-V2 的邏輯與 77 條既有測試沒動。
  * 做成了：一張拍立得＋「分享」＋「存到相簿」＋一行「也可以長按圖片存下來」＋小連結「自己驗收據」。
  * 沒做成：「這一次沒有做成」＋「這一跑沒有做完一件事，所以沒有拍立得。」
  * 電視先回了卡圖（展場還沒回報）⇒ 先給卡圖、每 8 秒再問，拍立得到了就換上去（不重演抬頭動畫）。
* **分享在 iOS／Android 上的行為**（碼的設計；**沒有在實體 iPhone／Android 上測過**）：
  * 「分享」＝ `navigator.share({files:[png]})`（iOS Safari 15+、Android Chrome 有）。圖在顯示那一刻
    就預先抓好成 File——iOS 要求 share 在點擊當下呼叫，先 await 下載會 NotAllowedError。
    不支援帶檔案分享 ⇒ 改講「長按圖片」。**不自動分享、分享內容只有那張圖**（有測試）。
  * 「存到相簿」：**iOS Safari 沒有直接寫相簿的 API** ⇒ iOS 上也是叫分享選單，並說要選「儲存影像」；
    Android／桌機 ⇒ 直接下載（Android 進「下載」、相簿看得到）。
  * 實測到的只有：macOS 桌機 Chrome（本機起雲端）`navigator.canShare({files})` = true、
    拍立得與收據頁正常顯示；node DOM 替身裡 iOS／Android 兩條分支各有測試。
* **收據帶走**（做到了）：
  * 內容先確認過：分身那一跑的收據鏈 2 筆（`ws_attempt`＋`ws_verdict`），payload 只有別名
    （`task_id=twin:tw-…`）、雜湊、計數、固定枚舉。**白名單**（`twinagent.RECEIPT_PAYLOAD_KEYS`）
    多一個不認得的鍵就整份不發；VM 與雲端**各驗一次**（雲端是公網，不相信上游）；
    鏈頭必須等於拍立得上那 8 碼的來源（`expect_head`），對不上不發。
  * `receipt.html?id=` 在瀏覽器裡從創世重算到鏈頭＋Ed25519 驗簽＋公鑰對 vacant_id。
    驗證邏輯**不是新寫的**：`examples/twin_viewer.html` 的 CANON／LOGIC 兩段**逐字**抄入
    （`sync_receipt_logic.py --check` 驗逐字相同，有負控制）。瀏覽器不支援 Ed25519 ⇒ 退成只驗 hash 鏈並講出來。
  * ⚠ 誠實邊界：`ws_start_sha256`（＝TRAITS.md 的樹雜湊）與 `conversation_sha256`（wire 位元組）
    是**原文的無鹽雜湊**：倒推不回去（TRAITS.md 含整段貼回來的原文），但**已經握有逐字原文的人**
    可以拿它確認「就是這份」。這一份只在他自己的連結後面、撤回就刪；VM 上的收據照舊留著（既有裁決）。

## 六、撤回：刪什麼、列在哪

| 在哪 | 刪什麼 | 抹除證明列在哪 |
|---|---|---|
| VM twinvault | `polaroid.png`（加進 `ERASABLE_NAMES`，跟 nonce／card／twin 一起） | `erased` 事件＋簽章鏈 `PERSONA_ERASED`（ref＋被刪位元組 sha256） |
| 雲端（觀眾在手機上撤回） | `polaroids/<id>.png`、`receipts/<id>.json`（跟原文、卡圖、nonce 一起） | 雲端 `withdrawn` 事件；`ingest` 帶回本機 ⇒ `erased.cloud_copy{by:"cloud", erased:[{ref,bytes_n}]}` |
| 雲端（會場撤回：紙本／serve） | 同上，loop 下一輪 `sync_cloud_erasure` 走工作人員路徑 `POST /api/withdraw {id, token}` | 一列 `cloud_erased` note；**連不上不寫鏈、下一輪再試**；雲端 404 記一列不再試 |

* 手機頁撤回後不再顯示（`status=withdrawn` ⇒ 已刪掉那一屏；拍立得網址 404）。
* 抹除證明裡雲端 ref 的 id 換成 `<id>`（帳本本來就以 sub_id 為鍵，內容不再抄一次撤回的鑰匙）。
* 這順手補了 twinvault 誠實邊界 2（「雲端那一份刪不到」）：**會場撤回的人，雲端那一份原文現在也刪得到了**
  （要 loop 連得上雲端）。`serve` 撤回頁與 `erasure_honesty` 的字已改。
* **閉展清除**：照人類指示**沒有動**、沒有自動化。

## 七、倫理判斷

1. **分享是觀眾自己的決定。** 頁面不自動分享、不自動上傳；按了才叫系統選單，選哪個 app 是他按的。
2. **拍立得上不出現可識別本人的原文。** 上面只有：分身的決定（衍生物）、日期、展名、收據短碼、官網 QR。
   沒有記號（記號是 sub_id 推出來的）、沒有需求／氣質／第一句話、沒有他貼回來的任何字。
   * 分身的句子**逐字抄**觀眾原文連續 8 個字以上 ⇒ **那一行留空**（v2；v1 會換成一句人寫的中性句，
     人類要求拿掉，§十）
     （`caption_leaks_original`，去標點與空白後比對；有正負控制）。
   * ⚠ 這是一把尺不是一道牆：擋不住改寫、擋不住模型自己編的名字。系統提示詞已要求不逐字抄 TRAITS.md，這是第二層。
3. **分享出去的收不回來。** 撤回刪得到的是 VM 與雲端那兩份；他存下來、傳出去的不在射程內——
   所以從一開始就不放可識別本人的東西。撤回回應的 honest 字串照實寫了這一句。
4. QR 不帶任何可追蹤參數：掃的人到的是官網首頁，我們不知道是誰分享、誰掃的。
5. PNG 不帶 metadata（tEXt／iTXt／zTXt／eXIf 零個，有測試）。

## 八、測試與證據

* Vacant：`tests/test_twin_polaroid.py` 29 條（合成尺寸／字不出界／截斷／豆腐字／逐字抄錄／PNG 讀回 QR 矩陣／
  外部解碼（沒 OpenCV 就 skip，證據檔是開發機跑的）／cast 前後端 node 對照＋負控制／manifest 逐 byte／
  產品路徑：做成 → 拍立得 → publish 帶圖＋收據、收據夾帶欄位不發、鏈頭不符不發、基建壞了不發、
  沒 Pillow 不寫鏈之後補得回來、撤回刪拍立得且抹除證明列它、畫到一半被撤回、手機撤回的雲端清單進證明、
  會場撤回同步雲端、連不上不寫鏈、loop 順序、收據頁逐字同一套邏輯＋負控制）。
* 雲端：`test/polaroid_flow.test.mjs` 19 條（存讀、權限：猜 id／壞 id／列舉、撤回刪檔、形狀閘門、
  非 PNG、not_made、手機頁：完成頁、分享、不支援分享、iOS／Android 存相簿、沒做成、卡圖升級拍立得、
  再做一個清畫面、極簡 CSS＋`?full=1`、收據頁真簽章驗過＋三個負控制）。收據 fixture＝Vacant fixture agent
  真跑一次（合成特質）簽出來的。
* 證據：`ops/exhibit/twin/evidence_polaroid_20260926/`（v1：4 張人寫句子的範例，歷史）；
  **`v2/`**（8 張真跑範例、`runs.json`、`samples.json`、`qr_decode.json`、`qr_sweep.json`）。
* v2 之後 `tests/test_twin_polaroid.py` 是 38 條：多了兩行平衡斷行＋負控制、引號只剝成對的、
  留空不補字（量墨色＋負控制）、空句／純 emoji 留空、範例逐張對回真跑紀錄、真相框放進 4:5＋窗比例＋
  墊圖、相框不合格退回佔位（兩種負控制）、背景板 sha 釘死、10 位用姿勢圖其餘 30 位用自己的原圖、
  **缺姿勢圖絕不借別人的臉**（逐 byte 相同＋連結也不認）、cast40 碎屑清掉；QR 證據改驗 v2 並驗
  「採用的模組 15 cm 全過、小一級沒有全過」。`tests/test_twin_agent_run.py` 多一條 prompt 不准舉例（＋負控制）。

## 九、上線前要人類做／同意的事

1. **同意 push 與部署**（Vacant `feat/twin-polaroid`、雲端 `feat/polaroid`；雲端 push＝Zeabur 上線）。
   部署順序：雲端先（新欄位是加的，舊展場端不送也能跑），再更新 VM 上的 twinlink。
2. **VM 裝 Pillow**（`apt install python3-pil`）；沒裝的話線照跑、只是沒有拍立得。
3. **兩支真手機對拍一次**拍立得上的 QR（15 cm 內），iPhone 上按一次「分享」「存到相簿」、Android 各一次。
4. 電視那一側（T 線）改成「有 `cast_id` 就用它」。
5. ~~A 線的相框素材到了放進 `assets/polaroid/`~~ **v2 已換上**，範例與 QR 驗收已重跑（§四、§十一）。
6. 判斷：QR 261 px（圖寬 24%）是否「夠小」；要更小的代價寫在 §四的表（8 px 在素材相框上 15 cm 只剩 14/16）。
7. 其餘 24 位的姿勢圖（另一條線）交件後放進 `assets/poses/`（檔名 `cNN_show.png`），**不用改碼**；
   順手把 `assets/poses/manifest.json` 補上來源與 sha256。
8. 看過 §十 的 prompt 改動（它改變之後**所有**分身的行為）。

## 十、那一句要是分身自己生成的（v2，同日稍晚）

人類 2026-09-26（看了 v1 範例拍立得「寫一封謝卡給國小導師」）：

> 「那個字是不是應該要讓他是 AI agent 生成的，不要隨便刻板」

主線查到三處人寫的罐頭／刻板來源，三處都改了：

1. **分身的 system prompt 在帶風向**（`twinagent.SYSTEM_PROMPT` 第 1 步）。
   * 舊：「1. 決定一件你想在這個世界完成的實務小事——寫在檔案裡就能完成的事，例如一封信、一份計畫、一張清單。不要寫程式。」
   * 新：「1. 決定一件你想在這個世界完成的實務小事——寫進你房間裡的一個檔案就能完成。不要寫程式。」
   * 只拿掉例子，約束照留（寫進自己房間的一個檔案、不寫程式、PLAN.md 第一行是決定）。三段固定文字仍逐字
     全場相同、import 時過 KS-1（`assert_ks1_clean`，沒有繞過）。
   * ⚠ **這會改變之後所有分身的行為**（每一位都吃這一段）。2026-09-26 以前跑過的分身（含 54 格錄影、
     `evidence_agentrun_20260924`）是舊 prompt 生的，不重跑、不改寫。
   * 測試：`tests/test_twin_agent_run.py::test_system_prompt_gives_no_examples`（prompt 裡不准有
     「例如／比如／像是／一封信／一份計畫／一張清單／謝卡」；負控制：舊版那一步逐字量得到例子）。
     既有釘 prompt 的測試：`test_fixed_texts_are_ks1_clean_and_the_guard_bites` 只驗 KS-1 與「不要寫程式」，
     沒釘舊字串，**不用改**；全 repo 沒有其他地方逐字抄舊 prompt（`grep "例如一封信"` 只剩這份裁決與那支測試的負控制常數）。
2. **拿掉中性罐頭句**：`polaroid.NEUTRAL_CAPTION = "他在這裡完成了一件事"` 刪掉。逐字抄了觀眾原文、
   或清完是空的（只有 emoji、只有引號）⇒ **那一行留空**，拍立得照發、只少那一句；畫面與手機頁都不補字
   （手機頁本來就只顯示那張圖，雲端不用改）。meta／鏈上多一個 `caption_blank`。測試：留空時那一格
   **量不到墨色**（像素 < 120 的點數 == 0）；負控制：正常句子那一格 > 500 個墨色點。
3. **範例改成真跑**：`polaroid.SAMPLES`（人寫死的四句）刪掉。`ops/exhibit/twin/polaroid_realrun.py`：
   * `run`（vacant-dev）：8 位**合成**特質（`PERSONAS`，刻意多樣；**卡上不寫 need**——需求那一格最容易替它
     預設要做什麼；特質是我寫的，做什麼由它自己決定），每位一個拋棄式 store，走產品路徑
     `twinlink generate --engine agent`（`launcher.run` → `twin_agent.sh` → pi，在 `vacant run` 底下、
     同一支 `SYSTEM_PROMPT`），記下它寫的 PLAN.md、run_id、收據鏈頭、收據驗章結果，然後撤回、刪暫存。
   * `compose`（開發機，VM 沒有 Pillow）：用**與 `twinlink.make_polaroid` 相同的輸入**做拍立得。
     沒有真跑成功的不產範例（`skipped` 照實列；這一次 8/8 都做成了）。
   * 模型：**1004**（`gemma-4-12b-it-qat`，`http://100.86.226.21:1234/v1`，經 vacant-dev 打過去；
     探針 `"Reply with exactly: OK"` ⇒ 無 `reasoning_content`＝非 thinking，wire 上 29 通回應也都沒有）。
     1003 那時被素材線拿去跑 Wan，沒用。`enclose=off` ⇒ 收據級別 C（與 2026-09-24 冒煙同一種跑法）。
   * 暫存在 vacant-dev `/var/tmp/vacant_polaroid_20260926`（程式碼子集 14 MB），跑完已刪。

| 範例 | 分身自己寫的第一行 | cast | run_id | 收據鏈頭（前 16） | 它交出的檔 |
|---|---|---|---|---|---|
| `polaroid_p1_c09_pose.png` | 我決定整理一份「週末登山清單」。 | c09 姿勢圖 | `5930fbe90bf64425bfc350d9ac04cab8` | `facee37cc36d19ed` | Hiking_Checklist.md |
| `polaroid_p2_c33_pose.png` | 我決定在房間裡記錄一份關於木材質感的觀察筆記。 | c33 姿勢圖 | `42fae8d548a64cdd927348ab20fb234f` | `50f330de858b6d33` | wood_texture_notes.md |
| `polaroid_p3_c28_pose.png` | 我決定寫一份「日文單字記憶小撇步」。 | c28 姿勢圖 | `ec3b251fe8d34636bd9884ac243f27aa` | `520be42653fb53de` | 日文學習筆記.md |
| `polaroid_p4_c19_pose.png` | 我打算在房間裡建立一份「公園路線導覽」。 | c19 姿勢圖 | `809c9b193e4a4d0d82ea292352becae7` | `7b4c49b509bbc000` | Park_Routes.md |
| `polaroid_p5_c08_cast40.png` | 我決定為自己寫一份「深夜護理師的放鬆清單」。 | c08 原圖 | `01ec51cbb1a74f2d8befd5eab11218a4` | `6c4eb9b02ba19e37` | Relaxation_List.md |
| `polaroid_p6_c38_cast40.png` | 我決定在房間裡寫一個關於「如果恐龍有外星科技」的奇幻構想。 | c38 原圖 | `024497d777894d7ca9d07076b046ab9f` | `4c145ad883580b26` | Dinosaur_Tech_Concept.md |
| `polaroid_p7_c01_cast40.png` | 我決定建立一份「借貸與心意清單」。 | c01 原圖（卡上沒選任何特質） | `a8d7ad948aec433e95ba9ac0626d1bb3` | `b3374afa958e56ec` | Debt_and_Kindness_Log.md |
| `polaroid_p8_c20_cast40.png` | 我決定為這個房間編寫一份「導遊故事集」。 | c20 原圖 | `b3f725da5c1c481b89c01cb6e88c3fa2` | `3c031c6f6f3893d1` | Guide_Stories.md |

每一跑：收據 `verify_run` = OK、`chain_ok`、mediated；wire 3–4 通；牆鐘 5.6–8.2 秒。完整紀錄
`evidence_polaroid_20260926/v2/runs.json`（PLAN.md 全文、特質、engine、收據、事件流自檢），
`samples.json` 逐張對回（`tests/test_twin_polaroid.py::test_samples_are_real_agent_runs_not_hand_written`）。

⚠ 照實記：
* 拿掉例子之後，8 句裡仍有 3 句是「清單」、全部以「我決定／我打算」開頭——這是這個模型對
  「第一行用一句話說你決定做什麼」的寫法，**不是我們放進去的**；要不要再動 prompt 是人類的判斷，本線沒動。
* 這是「這個模型、這一次」的產出（n=8、各跑一次），不代表分身一般會寫什麼。
* **沒有一句長到要截斷**（最長 28 字，兩行放得下）。截斷的機制由測試用一段測試字串驗
  （`test_long_decision_is_truncated_and_fits`），**不是範例**——不為了湊一張截斷範例去挑或改句子。

## 十一、相框與相片（v2）

**相框：按寬度縮放進 1080×1350、下緣白邊往下延長**（不是改成相框原比例輸出）。理由：

* 相框素材 829×930（0.89）。照原比例輸出（1080 寬 ⇒ 1211 高）下緣白邊只有 240 px；
  9 px 模組的 QR 連靜區要 333 px、8 px 也要 296 px ⇒ **QR 放不進去**，要嘛縮 QR（掃不到，§四的表），
  要嘛字與 QR 擠成一團。
* 4:5 是社群直式貼文的原生比例（v1 的理由不變），分享不被裁。
* 做法（`_frame_fit`／`_build_frame`）：裁到不透明外框（素材外圍有 3 px 透明邊）→ 寬度縮到 1080
  （×1.3139）→ 下緣白邊上下各留 1/4 不動（窗緣陰影與圓角），中段**上下鏡射接續**補滿 137 px。
  紙紋是細雜訊，鏡射接縫看不出來，也不會把紙紋拉長變形。相片窗維持素材比例 730:686（測試驗 < 1%）。
  素材的圓角（約 10 px）外面墊紙色 ⇒ 輸出是方角 RGB PNG（手機頁本來就自己畫 2 px 圓角＋陰影）。
* 相片從窗格底下墊進去、四邊多墊 5 px（素材說 4 px，×縮放）。
* 字：一行 48 px 只放得下 13 字，而分身寫的句子 14–28 字 ⇒ 改**最多兩行、44 px**，兩行時找
  最平衡的斷點（不留孤字）、避頭尾、盡量不斷在引號裡；清引號只剝**成對包住整句**的那一對
  （v2 修掉一個 bug：「…「週末登山清單」。」會被剝掉句尾的 」）。

**相片：黏土世界**（取代 v1 程式畫的平面桌子）。

* 背景：`vacant_hm/world3/plates/s00.jpg`（空舞台＋頂光；無文字、無 QR、沒有烤進去的生物；
  與電視待機畫面同一個世界、同一盞燈），逐 byte 抄進 `assets/polaroid/plate_s00.jpg`、sha256 釘死
  （對不上 ⇒ `available()` 回 false、不發拍立得，與字型同一條規則）。從頂光中心欄（x=812，量的）
  置中裁成相片窗比例。
* 分身：**有 `assets/poses/<cast_id>_show.png` 就用**（素材線的去背姿勢圖，舉著寫好的紙給人看＝
  「做完了一件事」；10 位：c02／09／10／17／19／25／28／31／33／40，逐 byte 抄自素材線、sha256 在
  `assets/poses/manifest.json`），**沒有就退回同一位的 cast40 原圖＋同一張背景**。
  🔴 **絕不拿別位的姿勢頂替**（那是別人的臉）：`figure_for` 只組 `<cast_id>_show.png` 這一個檔名，
  連結指向別的檔名也不認。負控制測試：姿勢資料夾只有 c02 ⇒ c03 的相片與「資料夾是空的」**逐 byte 相同**；
  `c03_show.png → c02_show.png` 的連結 ⇒ 仍用 c03 原圖。
* 其餘 24 位由另一條線續做、檔名同規則 ⇒ **資料驅動**：放進 `assets/poses/` 就生效，不用改碼。
* 融進場景：高度 = 相片窗 50%（寬的由寬度 52% 收住）、腳踩在光圈裡（窗高 86%）、乘一層「上亮下暗、
  偏暖」的漸層（頂光）、腳下一圈柔和接觸陰影。cast40 原圖裡有 5 位（c01／02／20／21／34）邊上有
  脫離本體的碎屑，貼到深色舞台上會變白線 ⇒ alpha 連通塊 < 最大塊 2% 的清掉（有測試）。
* ⚠ 已知：素材線 QA.md 記的「姿勢圖的眼睛比 cast40 大一號」在拍立得上看得出來（姿勢圖 vs 原圖並排時）；
  c01 的 cast40 原圖本身左右手臂被裁到圖邊，拍立得上看得到那一刀。都是素材本身，本線沒修。

## 十二、其餘 24 位上架＋換行不切詞＋v3（2026-09-26 晚，Sonnet 執行）

接續 §十一「其餘 24 位由另一條線續做」與 `PLAN_INTEGRATE_SONNET.md` §C：素材線
`vacant_hm-assets-20260926/poses/` 那 24 位（加上 c09／c10／c31 的 eyefix 新版）到位。

1. **姿勢圖上架**：`assets/poses/` 從 10 張補到 34 張（cast40 扣掉班底 6 位
   c01/c03/c13/c20/c22/c37；資料驅動，本線沒改 `figure_for` 一行程式碼）。c09／c10／c31 換成
   eyefix 輪之後的新版（sha256 換了，與素材線 `poses/manifest.json` 現在的值逐位元組相同）；
   其餘 7 位（c02/c17/c19/c25/c28/c33/c40）逐位元組沒動。`assets/poses/manifest.json`
   同步重寫（34 個項目）。
2. **測試跟著改**（兩處既有測試因為多了姿勢圖而過時，不是壞掉）：
   - `POSE_IDS`：10 位改成 34 位（`c{i:02d} for i in 1..40 排除班底 6 位`，逐檔驗過與磁碟一致）。
   - `test_samples_are_real_agent_runs_not_hand_written`：v2 那 8 張範例是**上架前**合成的，
     `samples.json` 記的 `meta.figure` 是**那個時間點**的事實（那時只有 10 位有姿勢圖，
     c08／c38 那兩張範例當時是 `cast40`）；改成跟 `_V2_POSE_IDS_AT_GENERATION`（凍住的 10 位）
     比對，不是跟現在（34 位）的 `figure_for()` 比——不然 c08／c38 上架後現在會變成 `pose`，
     測試會誤判成漂了。
3. **換行不切詞**（`wrap_caption`，`polaroid.py`）：原本「只看兩行寬度差最小」的版本會把
   「如果」「因為」這類常見兩字詞從中間切開（真跑範例 p6：「…關於「如／果恐龍…」）。改法：
   先找「斷在標點之後、或斷在『的／在／和／與』這類連接字之後、且不在引號裡」的斷點，這一層裡
   一樣挑最平衡的；找不到符合這一層的斷點才退回原本的純平衡版（歷史行為不變）。字一個都沒改，
   只改斷點的挑法。新增兩條測試：一條用構造句證明新法真的會改變結果（附負控制：純平衡版
   `真的會`切在「如｜果」中間）；另一條誠實記錄 p6 那句本身是修不掉的邊界案例——窮舉過，
   目前版寬（一行最多 14 字）下兩行都放得下的切法只有一種（14/14），剛好卡在「如｜果」中間，
   換哪一種找斷點的演算法結果都一樣（不是這次沒修好，是這句話配這個版寬本來就沒有別條路）。
4. **v3 範例**：`polaroid_realrun.py compose --runs v2/runs.json --out v3/`（沒有重跑 agent，
   用同一組 8 位真跑紀錄），8/8 都做成。跟 v2 比：p1–p4 沒變（本來就有姿勢圖）；**p5（c08）／
   p6（c38）從 `cast40` 換成 `pose`**（這兩位是新上架的 24 位裡的）；p7（c01）／p8（c20）
   還是 `cast40`（班底，永遠沒有姿勢圖）。QR 驗收（`polaroid_qr_check.py`，OpenCV 5.0）：
   8 張 × {原圖、540px 縮圖、模擬手機 10cm、15cm} 全過，同 v2。
5. 界線：沒有動 `assets/poses/` 以外的素材、沒有動電視那一側（T 線）、沒有重新生成任何圖或跑
   agent、v2 的 4 張範例與判準原樣保留當歷史（v3 是新的參考範例，不是取代 v2 的證據）。
