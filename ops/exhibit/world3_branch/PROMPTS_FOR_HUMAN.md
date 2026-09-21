# 展件影片 36 支 — 生成清單（人工在 Google Flow 執行）

來源：`ops/exhibit/world3_branch/manifest.json`（分支 `worktree-agent-a5b695c44f45251b0`）

---

## 每一支都要先掛的東西

**參考圖（initial frame）一定要掛。** 實測（2026-09-20，s10 vs s03）：
沒掛參考圖生出來的板，跟既有的板在**箱型／質感／機位／符號四項全變**。

**系列語彙**（可以直接接在每個 prompt 後面）：

```
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

**角色**：人形黏土生物（球莖身體、圓眼睛、土色系）——記憶〈動物園要用人不用抽象生物〉：抽象發光生物已被連續三次否決

🔴 **機制畫面的鐵律**：畫面只能演真的發生過的機制。不准出現：人手（＝有人來判）、有眼睛的收件者（＝有人收有人判）、骰子（＝擲骰派工）、光點弧（＝依信譽派工）、思考泡泡（＝它在想）、計分色磚（＝信譽紀錄）

---


# 批 1：接上真 Vacant 就會對觀眾說錯話的四格（12 支）

> 這四種結局真的會出現（abpi 600 格實測），而今天畫面上要嘛沒有、要嘛演成別的結局。


## 1. `v_null` — accepted === null（ungated，沒跑驗收）

- **檔名**：`scene_v_null_v1.mp4`, `scene_v_null_v2.mp4`, `scene_v_null_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s10.jpg`
- **現有**：0 支
- **今天的問題**：index.html toVerdict() 的 `useBlocked = !row.accepted`——`!null === true` ⇒ 送去 s12，而 s12 烤死的副標是「沒過驗收測資，就退回去重做」。那一格根本沒驗過。大字（verdictBig）是對的（「沒量——這一格沒有跑驗收」），**場景是錯的**。這是 codebase 自己記了三次的那個坑：字改對了、圖沒有。

**畫面**：同一台機器，投件口**完全沒有亮**；機器側面那兩格刻痕燈是暗的；紙**放在地上、在機器外面**，沒有進過投件口。沒有托盤、沒有封緘。

🔴 **不可以出現**：任何燈號顏色（綠＝過、紅＝擋，都會說錯）、任何人、任何手

**Prompt**：
```
same set as reference; slot UNLIT and dark; the two notch lamps on the machine side are dark; one plain clay sheet lying flat on the floor to the LEFT of the machine, clearly outside it, never inserted; no tray, no seal, no glow
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 2. `v_block` — accepted === false, blocked_by = gate

- **檔名**：`scene_v_block_v1.mp4`, `scene_v_block_v2.mp4`, `scene_v_block_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s10.jpg`
- **現有**：0 支
- **今天的問題**：s12 的影片與板**都**在演不存在的機制（櫃檯泥偶隔著櫃檯收紙＝有眼睛的收件者、托盤四色磚＝計分板、後方排隊＝派工），SCENE_VIDEO_DEPICTS 把它整個關掉，SCENE_PLATE_SUB 借 s06 的空地板頂著。展件的頭條是「30 件被擋下」，而那一刻畫面上是一間空房間。

**畫面**：同一台機器，投件口亮**紅**；紙**停在投件口裡沒有出來**——上緣露出一截，其餘還在機器內；紙是平整完好的（閘門不毀件）；機器側面兩格刻痕燈一亮一暗（2 條測資過 1 條）。

🔴 **不可以出現**：撕破的紙、裂縫、透紅光的裂縫（＝毀件）、人手、任何生物在旁邊判

**Prompt**：
```
same set as reference; slot lit RED; the clay sheet is caught HALF-WAY in the slot, only its top edge protruding, flat and undamaged, not torn, not crumpled; of the two small notch lamps on the machine's side one glows and one is dark
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 3. `v_empty` — 空手（有 agent_rc=0 但沒有交付檔案）

- **檔名**：`scene_v_empty_v1.mp4`, `scene_v_empty_v2.mp4`, `scene_v_empty_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s10.jpg`
- **現有**：0 支

**畫面**：同一台機器，投件口亮**中性琥珀**（既不綠也不紅）；**什麼都沒有出來**，機器正面完全空的；地上機器正前方一個乾淨的空黏土淺托盤。

🔴 **不可以出現**：紙（有紙就不是空手）、燈號的對錯顏色、人

**Prompt**：
```
same set as reference; slot lit neutral pale amber (not green, not red); NOTHING has emerged, machine face completely bare; one small empty shallow clay tray on the floor in front of it, clean and unmarked
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 4. `v_timeout` — timed_out === true（跑到牆鐘上限被砍）

- **檔名**：`scene_v_timeout_v1.mp4`, `scene_v_timeout_v2.mp4`, `scene_v_timeout_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s10.jpg`
- **現有**：0 支

**畫面**：同一台機器，投件口亮中性琥珀；被送進口中的紙**只寫了上半截**，下半部空白，紙的下緣是**毛邊、撕斷的**（寫到一半就被拿走）；機器旁邊一個黏土沙漏，沙已經全部漏完。

🔴 **不可以出現**：任何暗示「為什麼跑那麼久」的東西（我們沒有量，不要猜）、人

**Prompt**：
```
same set as reference; the clay sheet entering the slot is written only on its TOP half, the lower half blank, its bottom edge visibly ragged and torn off mid-stroke; a small clay hourglass stands beside the machine with all its sand run through
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

# 批 2：live 路徑上六個啞拍裡的四個（12 支）

> s05 s06 s07 s08 四拍在真 Vacant 那條路上一定會演到，而四支既有影片全部被 SCENE_VIDEO_DEPICTS 關掉（它們演的是評審層／路由層／思考，那條路上都沒有）。關掉之後退回靜態板＝那四拍整整 40 秒畫面不動。


## 5. `m_gate` — s07 拍、has_review_layer === false ⇒ 演的是閘門（gateBeat），不是同儕評審

- **檔名**：`scene_m_gate_v1.mp4`, `scene_m_gate_v2.mp4`, `scene_m_gate_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s10.jpg`
- **現有**：0 支

**畫面**：紙滑進機器；機器側面一排小刻痕燈**由左到右逐一亮起**（一格＝一條測資）。整個畫面裡沒有人。

🔴 **不可以出現**：任何人形在旁邊看或舉牌（＝有人在判）

**Prompt**：
```
same set as reference; a clay sheet sliding into the slot; along the machine's side a row of small carved notch lamps lighting up one by one left to right; absolutely no creatures anywhere
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 6. `m_rerun` — s08 拍、revised（retry=revise，同一個 agent 帶著自己的失敗原文再跑一次）

- **檔名**：`scene_m_rerun_v1.mp4`, `scene_m_rerun_v2.mp4`, `scene_m_rerun_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s08.jpg`
- **現有**：0 支

**畫面**：一張矮石桌，**同一個位置**：桌上一張新的空白紙，旁邊整齊疊著上一張寫過的紙（1 張或 2 張，對應 attempt 2/3）。桌前只有**一隻**生物，低頭在寫。

🔴 **不可以出現**：第二隻生物、紅牌、任何『被推翻』的手勢

**Prompt**：
```
same set as reference; ONE clay creature alone at the low stone table writing on a fresh blank sheet, with the previous written sheets stacked neatly beside it; no second creature, no red slip, no one watching
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 7. `m_noroute` — s06 拍、route_basis === 'random' 或 null（＝沒有路由層，誰做是人指定的）

- **檔名**：`scene_m_noroute_v1.mp4`, `scene_m_noroute_v2.mp4`, `scene_m_noroute_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s06.jpg`
- **現有**：0 支

**畫面**：三張一樣的矮石桌並排，**只有中間那張桌上有一張紙**，左右兩張空著。左冷藍右暖金的雙光柱保留（那兩條光標的是兩條臂，兩條臂真的都跑過）。

🔴 **不可以出現**：骰子、光點虛線弧、任何『選中』的動作

**Prompt**：
```
same set as reference, keeping BOTH light shafts (cool blue-white left, warm gold right); three identical low stone tables in a row, a single clay sheet lying on the MIDDLE one only, the other two bare; no dice, no dotted glowing arcs, no creatures
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 8. `m_brief` — s05 拍（目標）——SCENE_VIDEO_DEPICTS 給 s05 的判準是 ok:()=>false，**永久關閉**

- **檔名**：`scene_m_brief_v1.mp4`, `scene_m_brief_v2.mp4`, `scene_m_brief_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s05.jpg`
- **現有**：0 支

**畫面**：中央一塊圓形光池；一張寫著字的紙**落進地面一個淺凹槽**（＝工作區）。凹槽邊緣是黏土捏出來的。沒有生物、沒有泡泡。

🔴 **不可以出現**：思考泡泡、頭頂浮光、發光小方塊、任何『它在想』的符號

**Prompt**：
```
same set as reference; a warm pool of light on the centre floor; a single written clay sheet settling into a shallow hand-pinched recess in the floor; no creature, no thought bubble, no floating glow above anything
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

# 批 3：雙世界對照與變化量（12 支）

> 『一定要多才能讓更多人看得都不同』。收尾兩拍（receipt／chain）每一位訪客都會走到，而 s13 只有 1 支變體 ⇒ 所有人的結尾完全一樣。r_receipt_none 是展件雙世界對照裡『沒有 Vacant 那一邊』的畫面，今天沒有。


## 9. `r_receipt_none` — OFF 臂 has_receipt === false（那一臂不簽收據）

- **檔名**：`scene_r_receipt_none_v1.mp4`, `scene_r_receipt_none_v2.mp4`, `scene_r_receipt_none_v3.mp4`
- **參考圖**：`vacant_hm/world3/plates/s13.jpg`
- **現有**：0 支

**畫面**：同一台機器，但**出口下面沒有收據槽**——那一塊是平的、光滑的黏土，什麼都沒有；地上沒有任何可以帶走的東西。

🔴 **不可以出現**：空的收據槽（空槽＝有槽但這次沒出，那是另一件事）

**Prompt**：
```
same set as reference but the receipt chute below the machine's mouth is ABSENT — that part of the machine is smooth unbroken clay; nothing on the floor to pick up
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 10. `r_chain_more` — chain 拍（每位訪客結尾都會走到）

- **檔名**：`scene_r_chain_v3.mp4`, `scene_r_chain_v4.mp4`
- **參考圖**：`vacant_hm/world3/plates/s13.jpg`
- **現有**：1 支

**畫面**：收據鏈：一串刻著記號的黏土小牌，一枚接一枚串在一條細黏土繩上，最新一枚剛被扣上去。變體差在串的長度與鏡位。

🔴 **不可以出現**：

**Prompt**：
```
same set as reference; a chain of small notched clay tiles threaded on a thin clay cord, the newest tile just clipped on at the near end
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 11. `v_pass_more` — accepted === true（放行）

- **檔名**：`scene_s10_v5.mp4`, `scene_s10_v6.mp4`
- **參考圖**：`vacant_hm/world3/plates/s10.jpg`
- **現有**：1 支

**畫面**：同 s10_v4：投件口綠燈、完整封緘的紙垂到箱子正面。變體差在塵埃、光閃、機位微調。

🔴 **不可以出現**：

**Prompt**：
```
same set as reference, same green-lit slot and intact sealed clay scroll; vary only dust motes, light flicker and a slight camera offset
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

## 12. `ambient_more` — 無分支——待機（s00）與廣角常態（s11）

- **檔名**：`scene_s00_v4.mp4`, `scene_s00_v5.mp4`, `scene_s11_v4.mp4`, `scene_s11_v5.mp4`, `scene_s11_v6.mp4`
- **參考圖**：`vacant_hm/world3/plates/s00.jpg`
- **現有**：s00 2 支、s11 3 支 支

**畫面**：

🔴 **不可以出現**：

**Prompt**：
```
same wide claymation set as reference; vary crowd arrangement, dust and ceiling-lamp flicker only
clay stop-motion animation, warm top light, dark brown background, golden dust motes,
shallow depth of field, visible fingerprint texture, heavy vignette, 16:9
```

---

# 另外：4 張 overlay 徽章（不是影片）

> 證據等級不生影片，生 4 張透明 overlay PNG（放 plates/）。這是砍掉 ×4 維度的代價，必須補上。

- `?`：
- `?`：
- `?`：
- `?`：

⚠ 徽章只畫框與底，**字由引擎現場排**——鐵律：真資料不烙進畫面。