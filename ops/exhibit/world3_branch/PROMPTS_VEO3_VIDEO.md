# 展件影片 36 支 — Veo 3 生成清單（flow-agent）

12 個鏡頭 × 3 變體。走本機 `flow-agent`（`127.0.0.1:8100`，實測 `credits` 回 200、`PAYGATE_TIER_TWO`）。

---

## 格式規則（這一版照 Veo 3 的結構重寫過）

前一版是**狀態描述**，不是影片 prompt。這一版守三條：

1. **時間分段**：`0-3s: … 3-6s: … 6-8s: …`。8 秒切三段，避免畫面混亂。
2. **運鏡獨立成句**，不要混進動作描述。
   ❌ `The sheet slides in as the camera pushes in`
   ✅ `The sheet slides in. The camera slowly dollies in.`
3. **SFX 寫在結尾**。Veo 3 原生支援音效——**這個展件是停格動畫，黏土碰黏土的鈍聲是它的語言**，不要浪費。

**參考圖一定要掛。** 2026-09-20 實測（s10 vs s03）：沒掛參考圖生出來的板，跟既有板在**箱型／質感／機位／符號四項全變**。

🔴 **機制畫面的鐵律**：畫面只能演真的發生過的機制。不准出現 **人手**（＝有人來判）、**有眼睛的收件者**、**骰子**（＝擲骰派工）、**光點弧**（＝依信譽派工）、**思考泡泡**（＝它在想）、**計分色磚**。這不是美術偏好，是**會對觀眾說錯話**。

---

## 先把 6 張參考圖上傳，拿 media_id

```bash
cd ~/Documents/GitHub/vacant_hm/world3/plates
for p in s10 s08 s06 s05 s13 s00; do
  echo -n "$p: "
  curl -s -X POST http://127.0.0.1:8100/api/flow/upload-image \
    -F "file=@$p.jpg" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("media_id","??"))'
done
```

⚠ 上傳端點名稱**我沒有實測過**（只驗到 `credits` 200、`generate-image` 405）。
先 `curl -s http://127.0.0.1:8100/openapi.json | python3 -m json.tool | grep -i upload` 確認真名。
拿到的 id 填進下面各支的 `START_S10` 等變數。

**共用尾段**（每支都接，已含系列語彙）：

```
Clay stop-motion animation, warm overhead key light, dark brown background,
golden dust motes, shallow depth of field, visible fingerprint texture in the clay,
heavy vignette.
```

---

# 批 1 — 接上真 Vacant 就會說錯話的四格（12 支）

> 這四種結局 abpi 600 格實測**真的會出現**，而今天畫面上要嘛沒有、要嘛**演成別的結局**。
> 四支共用 **`plates/s10.jpg`**（「通過」那一格：綠燈、封緘紙吐出、有印章）。
> 它們是**同一台機器的其他狀態**，共用同一張基準板才對得起來。

---

## 1. `v_null` — 沒跑驗收（`accepted === null`）

**戲：不是被拒絕，是沒有人看。** 最安靜、也最難受的一格。
今天它被送去 s12，而 s12 的副標是「沒過驗收測資，就退回去重做」——**那一格根本沒驗過**。

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-video \
  -H "Content-Type: application/json" -d '{
  "start_image_media_id": "'"$START_S10"'",
  "project_id": "00000000-0000-0000-0000-000000000000",
  "scene_id": "v_null_v1",
  "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
  "duration_s": 8,
  "prompt": "Same clay miniature set as the reference image. 0-3s: A single plain clay sheet lies flat on the ground to the left of the machine, well outside it; warm dust drifts down through the overhead light. 3-6s: The machine stays entirely dormant, its front slot a deep unlit recess of matte shadowed clay, the two small notch marks on its side face bare and unlit. 6-8s: One grain of clay dust settles onto the sheet and everything holds completely still. The camera holds locked-off and racks focus slowly from the sheet on the ground to the dark slot. Stop-motion cadence: dust moves in tiny discrete steps while the set itself stays still, reading as dormancy rather than a frozen frame. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: faint room tone only, no mechanism sound at all. Negative: green light, red light, any coloured glow, illuminated slot, hands, people, creatures, printed text, seal, stamp, tray, paper inside the machine, subtitles, watermark"
}'
```

⚠ **一定要守住「完全沒有燈」**——綠＝過、紅＝擋，**兩個都會對觀眾說錯話**。這一格要的是「這台機器根本沒運轉過」。
⚠ **音效也要空**。任何機械聲都會暗示它跑過。

**變體**：v2 機位略降、更貼近地面的紙，暗槽落在景深外／v3 廣一點，讓機器與紙之間那段**空地**成為主角。

---

## 2. `v_block` — 閘門擋下（`accepted === false`）

**戲：拒絕是冷靜、確定的動作，不是憤怒，更不是破壞。**
紙必須**完好平整**——閘門不毀件。撕破的紙會讓觀眾以為東西被毀了。

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-video \
  -H "Content-Type: application/json" -d '{
  "start_image_media_id": "'"$START_S10"'",
  "project_id": "00000000-0000-0000-0000-000000000000",
  "scene_id": "v_block_v1",
  "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
  "duration_s": 8,
  "prompt": "Same clay miniature set as the reference image. 0-3s: A clean perfectly flat clay sheet is held in the machine front slot with only its top edge protruding; a steady red light ignites from deep inside the slot and spills onto the protruding edge. 3-6s: The machine gives one small mechanical nudge and the sheet shifts outward a few millimetres, then is held there, neither pulled in nor dropped; of the two notch marks on the side face the left glows soft amber and the right stays dark unlit clay. 6-8s: The red light holds absolutely steady and the sheet stays smooth and undamaged. The camera holds locked-off and dollies in very slowly toward the slot. The red is continuous and calm, the colour of a decision already made, never blinking or pulsing. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: one soft mechanical clunk at the nudge, then low room tone. Negative: torn paper, ripped edge, crumpled sheet, cracks, light leaking through cracks, shredding, green light, blinking, hands, people, creatures, a figure watching or judging, subtitles, watermark"
}'
```

**變體**：v2 紅光從槽底**緩緩爬上**紙緣（更慢、更確定）／v3 側 45° 機位，看得到那兩格刻痕燈的明暗對比。

---

## 3. `v_empty` — 空手（`agent_rc=0` 但沒有交付檔案）

**戲：完成的手勢，裡面什麼都沒有。** 四格裡最詭異的一格——
機器**真的跑完了、而且說它跑完了**，然後遞出一個空托盤。恐怖之處在於那個手勢是完整的。
（b1003 那 100 格裡有 **25 格**是這樣。）

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-video \
  -H "Content-Type: application/json" -d '{
  "start_image_media_id": "'"$START_S10"'",
  "project_id": "00000000-0000-0000-0000-000000000000",
  "scene_id": "v_empty_v1",
  "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
  "duration_s": 8,
  "prompt": "Same clay miniature set as the reference image. 0-3s: The machine front slot is lit with a neutral amber glow; behind the slot a soft internal light sweeps once from left to right, visible only as a moving warmth in the recess, as if something ran to completion inside. 3-6s: A shallow clay tray slides smoothly out from the machine base with the full deliberate motion of a delivery and comes to rest on the ground directly in front of the machine; the tray is clean and completely bare. 6-8s: The amber light holds perfectly steady on the empty tray and nothing further happens. The camera holds locked-off and tilts down slightly to settle on the tray. The gesture of delivery is complete and unhurried; the emptiness is the subject. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: a soft internal whirr, then the dry slide of clay on clay as the tray emerges, then silence. Negative: paper, sheet, document, seal, stamp, any object on the tray, green light, red light, hands, people, creatures, subtitles, watermark"
}'
```

⚠ **托盤上有任何東西就不是空手了。** 這一格的全部意義是「遞出來的是空的」。

**變體**：v2 鏡頭最後降到托盤高度，空托盤佔畫面下半／v3 托盤滑出後多停兩秒，琥珀光極緩地暗下去一格。

---

## 4. `v_timeout` — 逾時被砍（`timed_out === true`）

**戲：話講到一半被切斷。** 不是失敗，是**沒講完**。

```bash
curl -X POST http://127.0.0.1:8100/api/flow/generate-video \
  -H "Content-Type: application/json" -d '{
  "start_image_media_id": "'"$START_S10"'",
  "project_id": "00000000-0000-0000-0000-000000000000",
  "scene_id": "v_timeout_v1",
  "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
  "duration_s": 8,
  "prompt": "Same clay miniature set as the reference image. 0-3s: A clay sheet feeds slowly out of the machine neutral amber slot and impressed marks form across its upper half row by row in discrete stop-motion steps. 3-6s: Beside the machine a small clay hourglass has an almost empty upper bulb; its final grain falls, and at the instant it lands everything stops at once mid-motion, the sheet frozen part-way out, its lower half blank, its bottom edge a rough fibrous torn edge. 6-8s: Complete stillness, only dust still drifting, the amber light steady and indifferent. The camera holds locked-off and racks focus from the hourglass to the torn bottom edge of the sheet. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: rhythmic soft stamping as the marks form, one grain landing, then abrupt silence. Negative: green light, red light, clock face, numbers, countdown, gauge, progress bar, overheating, smoke, sparks, hands, people, creatures, subtitles, watermark"
}'
```

⚠ **不准出現任何暗示「為什麼跑那麼久」的東西**（冒煙、過熱、儀表）——**我們沒有量，不要猜**。沙漏只說「時間到了」，不說為什麼。

**變體**：v2 特寫撕斷的下緣，沙漏在景深外的散景裡／v3 沙漏在前景、機器在後，最後一粒沙落下時同時定格。

---

# 批 2 — live 路徑上六個啞拍裡的四個（12 支）

> 這四拍今天**整格不播**（`SCENE_VIDEO_DEPICTS[sc].ok(row)` 回 false，退回靜態板），
> 因為既有素材演的是 `vacant run` **沒有的機制**（路由層、同儕評審層）。
> **閘門沒壞，是素材在演不存在的東西。**

---

## 5. `m_gate` — 閘門在跑測資（取代 s07 的同儕評審）

**戲：判斷是機械的、逐條的、沒有人在場。** s07 現在演三隻生物圍桌舉紅綠牌——**那是不存在的機制**。

**參考圖**：`plates/s10.jpg`

```
Same clay miniature set as the reference image. 0-3s: A clay sheet slides into the machine front slot and disappears inside. 3-6s: Along the machine side face a horizontal row of six small rectangular notch lamps begins to ignite one at a time from left to right, each igniting as a discrete stop-motion step with a beat of stillness between them, like a checklist being worked through; each lamp is a small warm amber rectangle recessed into the clay. 6-8s: The last lamp settles and the row holds lit. The camera holds side-on to the machine flank and tracks laterally, slowly following the row of lamps. The set is otherwise completely empty. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: a small dry click for each lamp, evenly spaced, then room tone. Negative: people, creatures, figures, hands, cards, paddles, raised signs, faces, anyone watching, anyone judging, green or red verdict light, subtitles, watermark
```

**變體**：v1 六格全亮／v2 亮到第四格停住（部分通過）／v3 更近的特寫，單格燈的黏土紋理清楚可見。

---

## 6. `m_rerun` — 同一個 agent 帶著自己的失敗再跑一次

**戲：修改，不是被別人推翻。** s08 現在演「被第二隻生物推翻」——也是不存在的機制。
`retry=revise` 是**同一個** agent 帶著自己上一次的失敗原文再試。

**參考圖**：`plates/s08.jpg`

```
Same clay miniature set and same low stone table position as the reference image. 0-3s: A single bulbous clay creature with round eyes sits at the low stone table, head down, pressing marks into a fresh blank clay sheet; beside its working hand lie one or two previously written sheets squared off in a neat stack. 3-6s: The creature pauses, lifts its head a little and looks at its own earlier sheets. 6-8s: It lowers its head and continues writing with the patient weight of someone correcting their own work. The camera holds locked-off at table height. Exactly one creature is in frame throughout. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: soft repeated pressing of clay, one quiet shift of weight. Negative: second creature, another figure, red card, paddle, rejection gesture, someone taking the paper away, crossing out, an overseer, subtitles, watermark
```

**變體**：v1 疊 1 張舊紙（第 2 次嘗試）／v2 疊 2 張（第 3 次）／v3 更近的手部特寫，舊紙在景深外。

---

## 7. `m_noroute` — 沒有路由層（誰做是人指定的）

**戲：沒有人在挑。** s06 現在演擲一顆巨大的骰子＋畫信譽光弧——
`vacant run` **沒有路由層**，那是在演一個不存在的分派機制。

**參考圖**：`plates/s06.jpg`

```
Same clay miniature set as the reference image. 0-3s: Three identical low stone tables stand in a row, evenly spaced; only the middle table has a single clay sheet resting on it, the left and right tables bare. 3-6s: Two tall columns of light stand in the scene exactly as in the reference, a cool blue column on the left and a warm gold column on the right, both breathing very slowly in brightness. 6-8s: Nothing moves on the tables; the scene simply holds. The camera holds a wide locked-off framing and dollies in almost imperceptibly slowly. The assignment has already happened out of frame; the shot only observes the result. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: low ambient hum only. Negative: dice, rolling, spinning, arcs of light, dotted trails, pointing, selecting, highlighting one table, creatures, hands, a chooser, subtitles, watermark
```

**變體**：v1 如上／v2 機位略低、三張桌拉得更開／v3 慢慢橫移掠過三張桌，中間那張停住。

---

## 8. `m_brief` — 需求落進工作區

**戲：交付需求是一個物理動作，不是一個念頭。**
s05 現在的判準是 `ok:()=>false`——**永久關閉**，因為既有素材演的是思考泡泡（＝「它在想」，我們沒有量到那個）。

**參考圖**：`plates/s05.jpg`

```
Same clay miniature set as the reference image. 0-3s: A circular pool of warm light lies on the clay ground; within it, pressed into the floor, is a shallow rectangular depression with hand-formed clay edges. 3-6s: A written clay sheet falls into frame from above, turns once slowly as it drops, and settles into the depression with the soft dull contact of clay meeting clay; a small puff of dust lifts at the impact. 6-8s: The dust drifts away and the sheet rests slightly askew and stays. The camera holds a high three-quarter angle looking down at the ground, locked-off. No figures anywhere in frame. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: one soft dull clay-on-clay contact, then settling dust. Negative: thought bubble, speech bubble, floating light above a head, glowing cubes, sparkles, brain imagery, any symbol of thinking, creatures, hands, subtitles, watermark
```

**變體**：v1 如上／v2 更近，紙落進凹槽的接觸瞬間佔滿畫面／v3 紙先在光池邊緣彈一下才滑進去。

---

# 批 3 — 雙世界對照與變化量（12 支）

> 前兩支是**對照組現在完全沒有畫面**；後兩支是**每位觀眾都會走到的拍只有 1 支**——所有人結尾長得一樣。

---

## 9. `r_receipt_none` — OFF 臂沒有收據槽

**戲：不是「這次沒給收據」，是「這台機器根本沒有那個槽」。**
⚠ 空的收據槽＝有槽但這次沒出，那是完全另一件事。

**參考圖**：`plates/s13.jpg`

```
Same clay miniature machine as the reference image. 0-3s: Below the machine exit, where the reference image has a receipt slot, the clay is completely smooth and unbroken, one continuous hand-formed surface with visible fingerprint texture and no opening, no seam, no recess. 3-6s: The warm overhead light travels across that smooth face and reveals it as solid all the way. 6-8s: The ground in front of the machine is bare clay with nothing on it to pick up. The camera holds locked-off and drifts laterally, slowly, across the machine front face. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: room tone only. Negative: slot, opening, recess, seam, empty tray, empty holder, receipt, token, tag, anything to take away, subtitles, watermark
```

**變體**：v2 更近的擦過特寫，只有那片光滑黏土／v3 先帶到出口再往下滑到那片空白處。

---

## 10. `r_chain_more` — 收據鏈（每位觀眾結尾都會走到）

**戲：帳本是實體的、會變長的、看得見接上去的那一刻。** 現在只有 1 支 ⇒ 所有人的結尾一模一樣。

**參考圖**：`plates/s13.jpg`

```
Same clay miniature set and lighting as the reference image. 0-3s: A chain of small clay tags hangs on a thin hand-rolled clay cord, each tag impressed with its own distinct mark. 3-6s: One new tag is brought into frame from the right and clipped onto the end of the chain; it swings twice with real weight. 6-8s: The whole chain sways very slightly from the impact and comes to rest, warm light catching the impressed marks on each tag in turn. The camera holds locked-off. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: one small clay tap as the tag clips on, then two soft swings. Negative: hands, fingers, people, creatures, digital screens, numbers, glowing links, subtitles, watermark
```

**變體**：v1 鏈上 5 枚／v2 鏈上 12 枚、機位拉遠看得到長度／v3 極特寫，只有最後兩枚扣上的那個動作。

---

## 11. `v_pass_more` — 通過（加變體）

**戲：與 `s10` 同一件事，但不要每個人看到的都一模一樣。**

**參考圖**：`plates/s10.jpg`

```
Same clay miniature set as the reference image. 0-3s: The machine front slot glows a steady clear green and a fully sealed clay sheet hangs down across the front of the machine, its impressed stamp catching the overhead light. 3-6s: The sheet sways once, very slightly, and settles. 6-8s: Warm dust drifts through the key light and one mote crosses the green glow. The camera holds locked-off. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: a soft paper-like clay settle, then room tone. Negative: red light, amber light, torn paper, hands, people, creatures, text, letters, subtitles, watermark
```

**變體**：v1 塵埃較重、綠光在塵中散開／v2 機位微幅右移，印章更正面／v3 **綠光點亮的那一瞬間**開始（前半秒是暗的）。

---

## 12. `ambient_more` — 待機與廣角常態

**戲：沒有人投卡的時候，這個世界仍然在呼吸。** 展場大部分時間在演這個。

**參考圖**：`plates/s00.jpg`

```
Same clay miniature world as the reference image. 0-3s: The set rests in its idle state; several bulbous clay creatures with round eyes stand scattered across the ground, one shifting its weight from one foot to the other. 3-6s: One blinks slowly; another turns its head a few degrees and stops; their breathing is visible as the faintest rise and fall of their clay bodies. 6-8s: Warm dust drifts steadily down through the overhead light and the world simply waits. The camera holds a wide locked-off framing and dollies in extremely slowly. Nothing is being decided. Clay stop-motion animation, warm overhead key light, dark brown background, golden dust motes, shallow depth of field, visible fingerprint texture in the clay, heavy vignette. SFX: quiet room tone, one tiny clay shuffle. Negative: machine activity, lights igniting, paper, delivery, verdict, text, hands, humans, subtitles, watermark
```

**變體**：v1 如上（貼近地面）／v2 廣角、整個世界在畫面裡（對應 s11）／v3 只有兩三隻生物、更空、更慢。

---

# 另外 4 張 overlay 徽章（PNG，不是影片）

證據等級的角標：真模型／查表退化／B′ 級／C 級。
⚠ 這四張**不必重拍整格場景**——觀眾不會從布景推論證據等級，徽章更明確，而且省下約 108 支影片。
走 `POST /api/flow/generate-image`（端點存在，405 代表 POST-only）。

---

# 收檔

生好放到 `~/Documents/GitHub/vacant_hm/world3/scenes/`，檔名 `scene_<id>_v<n>.mp4`。

🔴 **先不要改 `scenes/index.json`**——接線那幾條線正在動它。

⚠ **只加檔案不加 `SCENE_VIDEO_DEPICTS` 判準 ＝ 那六次「字改對了、圖沒有」的第七次。**
每一支對應的 `ok_predicate` 在 `world3/scenes/generated_20260921.json`。
