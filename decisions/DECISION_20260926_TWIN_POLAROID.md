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

範例（**合成特質**，不是真人）：`ops/exhibit/twin/evidence_polaroid_20260926/polaroid_{1..4}_*.png`。

1080×1350（4:5：接近拍立得的 0.82，又是社群直式貼文的原生比例，分享不會被裁）。

| 位置 | 內容 | 來源 |
|---|---|---|
| 相片窗 | 他的分身（cast40 黏土小人）站在小桌旁，桌上一張寫過的紙 | `cast_id`（§二） |
| 白邊下緣 | 一行手寫感的字：**分身決定做的那件事** | PLAN.md 第一行；去 markdown／引號；放不下從尾巴截、補「…」 |
| 小字 | `2026.09.26 · VACANT · 收據 xxxxxxxx` | 展場本機時區日期；收據＝`verdict_hash` 前 8 碼 |
| 右下角 | 官網 QR（`https://vacant.cosmopig.com`，**不帶任何參數**） | `ops/exhibit/twin/qr.py`（stdlib） |

**不放**：判決長文、統計、說明、記號、觀眾打的任何一個字。字型：jf 粉圓 2.0（SIL OFL 1.1，
原樣附在 `assets/fonts/`，sha256 釘死；OFL 聲明見 `OFL_NOTICE.txt`）。字型畫不出來的字（emoji）
**丟掉不畫成豆腐框**（`dropped_glyphs` 記數）。

相框：現在是**程式畫的佔位相框**。A 線的 `polaroid_frame.png`＋`polaroid_frame.json`（至少要有
`window`；可選 `caption`／`footer`／`qr`）放進 `ops/exhibit/twin/assets/polaroid/` 或設
`VACANT_POLAROID_FRAME_DIR` 就會換上；**放不下（字框太小、QR 靜區出紙、互相重疊、模組 < 6 px）
⇒ 退回佔位相框並在 `frame_note` 寫理由**，不會畫出一張壞的。

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
* 模組 **8 px**（碼 232 px ≈ 圖寬 21%），靜區 4 模組，塗紙色（亮度 ≈ 245）。
* 驗收（`polaroid_qr_check.py`，外部解碼器 OpenCV 5.0 `QRCodeDetector`，**拿範例 PNG 本身解**）：
  4 張範例 × {原圖、540 px 縮圖、模擬手機在 10／15 cm 拍螢幕} **全部解回官網網址**；
  負控制：QR 塗掉 ⇒ 解不出；同位置換別的網址 ⇒ 解成那個別的網址（`qr_decode.json`）。
* **最小模組尺寸**（`qr_sweep.json`，每格 16 次，模擬手機拍螢幕）：

  | 模組 | 10 cm | 15 cm | 20 cm |
  |---|---|---|---|
  | 5 px | 10/16 | 0/16 | 0/16 |
  | 6 px | 15/16 | 7/16 | 0/16 |
  | 7 px | 16/16 | 14/16 | 0/16 |
  | **8 px（採用）** | **16/16** | **16/16** | 0/16 |

  物理模型（寫死在 `CAMERA`）：手機頁把拍立得畫成 min(92vw,420px)；390 pt ≈ 65.9 mm ⇒
  8 px 模組在螢幕上 ≈ **0.45 mm**、整個碼 ≈ 13 mm；掃碼 app 分析 1920 px 寬、69° 視角的預覽畫面。
  ⇒ **15 cm 以內掃得到；20 cm 在這個代理量下解不開**（照實記，不算過）。
* 誠實邊界：「手機拍螢幕」是**模擬**（縮放＋旋轉＋透視＋模糊＋對比漂移＋雜訊＋JPEG），
  OpenCV 比 iOS／Android 內建相機的解碼器弱（偏保守），但它仍是代理量——**要在展場用兩支真手機對拍一次**。
* 版面在「小」跟「掃得到」之間取了後者：6 px 較小但 15 cm 只有一半解得開。人類要更小，
  改 `QR_MODULE_PX`（下限 `QR_MIN_MODULE_PX=6`）並重跑 `polaroid_qr_check.py --sweep`。

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
   * 分身的句子**逐字抄**觀眾原文連續 8 個字以上 ⇒ 換成中性句「他在這裡完成了一件事」
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
* 證據：`ops/exhibit/twin/evidence_polaroid_20260926/`（4 張範例、`samples.json`、`qr_decode.json`、`qr_sweep.json`）。

## 九、上線前要人類做／同意的事

1. **同意 push 與部署**（Vacant `feat/twin-polaroid`、雲端 `feat/polaroid`；雲端 push＝Zeabur 上線）。
   部署順序：雲端先（新欄位是加的，舊展場端不送也能跑），再更新 VM 上的 twinlink。
2. **VM 裝 Pillow**（`apt install python3-pil`）；沒裝的話線照跑、只是沒有拍立得。
3. **兩支真手機對拍一次**拍立得上的 QR（15 cm 內），iPhone 上按一次「分享」「存到相簿」、Android 各一次。
4. 電視那一側（T 線）改成「有 `cast_id` 就用它」。
5. A 線的相框素材到了放進 `assets/polaroid/`（或設 `VACANT_POLAROID_FRAME_DIR`），重跑 sample 與 QR 驗收。
6. 判斷：QR 232 px（圖寬 21%）是否「夠小」；要更小的代價寫在 §四的表。
