# DECISION 2026-09-21 — 原文搬出鏈、撤回接上去：做了什麼、沒做什麼、舊資料怎麼辦

本檔是 `decisions/DECISION_20260921_TWIN_CONSENT_AND_ERASURE.md` §三-1／§三-2
的**施工紀錄與殘餘清單**。裁決本身不重新討論。

---

## 一、問題是什麼（一句話）

`vacant_network/consent.py` 的檔頭逐字寫著：

> **原文一旦上鏈就刪不掉——那會讓「刪除證明」變成一句謊。** 所以設計前提是：
> 鏈上只有 commitment，原文與 nonce 住在鏈外……`assert_no_plaintext` 是這條
> 前提的可執行防呆，不要繞過。

而 `ops/exhibit/twin/twinstore.py` 把觀眾打的 `card` / `card_text` **原文**
寫進 append-only 鏈的 payload，`assert_no_plaintext` 在 `ops/exhibit/twin/`
`git grep` 零命中。**防呆存在、規格存在、被繞過了。**

---

## 二、做了什麼

### 2.1 新檔案：`ops/exhibit/twin/twinvault.py`

鏈外檔案庫 ＋ 簽章同意鏈。**沒有發明新機制**：簽章、hash 串接、承諾值
（`logbook.review_commitment`）、三個 entry type（`CONSENT_GRANT` /
`CONSENT_WITHDRAW` / `PERSONA_ERASED`）、`assert_no_plaintext`
全部來自 `vacant_network/{consent,logbook}.py`，一個字沒改；
`make_consent_demo.py` 已經用合成捐贈者跑通同一條路。

```
vault/
  plain/<sha256(sub_id)[:32]>/{nonce.hex, card.json, twin.json}   ← 刪得掉
  consent/{chain.ndjson, chain.pub.json, key/, chain.lock}        ← 簽章鏈
```

目錄名用 `sha256(sub_id)` 不是 `sub_id`：`sub_id` 來自公網，直接當目錄名
`"../../etc"` 就寫到別的地方去了（`test_...` 有負控制）。

### 2.2 `twinstore` payload 改存 commitment

`submitted` / `generated` 的 payload 現在是

```json
{"v":2,"sealed":"twinvault.v1","commitment":"<64hex>",
 "card_ref":"plain/<32hex>/card.json","nonce_ref":"plain/<32hex>/nonce.hex",
 "fields":["needs","style"],"grant_hash":"<64hex>","ts":…,"cloud_status":…}
```

`generated` 的 `engine` / `latency_ms` / `reasoning_tokens` 等**量測欄位仍在鏈上**
（誠實邊界：真模型與退化查表不可以長得一樣）；`arrival`/`working`/`handover`
與 `degrade_reason` 搬到鏈外。`degrade_reason` 之所以也搬，是因為它夾帶
`str(模型回應)[:200]`——模型可能逐字複誦卡上的字。鏈上換成 `degrade_kind`
（`empty_content` / `unparseable` / 例外類名）。

`current()` 照樣回得到原文，是因為它去檔案庫**開封**，不是因為鏈上有。
撤回把檔案 `unlink()` 之後，同一支 `current()` 就回 `None`——
「刪了」在讀取面是真的看得到的。

### 2.3 兩層可執行防呆，**都在產品路徑上**

| 層 | 函式 | 擋什麼 | 誤判 |
|---|---|---|---|
| 1 | `twinvault.assert_sealed_shape` | payload 的 key 不在白名單、值不符樣式（commitment ≠ 64hex、ref ≠ `plain/<32hex>/…`） | 零 |
| 2 | `consent.assert_no_plaintext`（**既有那一支，不是複製品**） | 原文／nonce 的字串出現在 payload 任何角落 | 見下 |

唯一寫入路徑是 `twinvault.append_sealed()`：**先跑兩層再 `store.append`**。
鏈是 append-only，所以防呆必須在寫入前跑，事後掃來不及。

**⚠ 第 2 層的 secrets 要篩過，這不是偷懶。** `assert_no_plaintext` 是子字串
比對，payload 骨架本身是 ASCII（`"sealed"`、`"plain/"`、`"needs"`…），
commitment 是 64 個 hex。把觀眾打的 `"e"`、`"ab"` 也當 secret ⇒
**每一張卡都會被自己的防呆擋掉**（`"ab"` 落在某個 commitment 裡的機率約兩成）。
收錄規則：**長度 ≥ 8 或含非 ASCII 字元，再扣掉骨架字串**。
中文（`"整理桌面"`）走第二條，一個字都不漏。
**殘餘：8 字元以下的純 ASCII 原文值第 2 層看不到**，由第 1 層頂住。
`tests/test_twinvault.py::test_short_ascii_values_do_not_false_positive`
把這個殘餘釘成可執行的紀錄。

### 2.4 撤回入口

* `POST /withdraw/<id>`（`twinlink serve --allow-withdraw`，**預設關**）。
* `GET /withdraw/<id>` 只是一張確認頁，**不寫任何東西**——不然瀏覽器預抓／
  爬蟲／聊天軟體展開連結就會把人家的分身刪掉。
* `python3 ops/exhibit/twin/twinlink.py withdraw --id <sub_id>`（紙本那條路）。

**唯讀那一側一點都沒鬆**：`do_GET` 仍然零寫入路徑，仍然
`TwinStore(..., read_only=True)`（SQLite `mode=ro`）；撤回自己開一個可寫的 store。
`tests/test_twinvault.py::test_readonly_reading_does_not_create_the_vault`
連「唯讀讀一遍不可以順手 mkdir 檔案庫」都釘住了，而且配負控制。

順序（順序本身是規格）：
`withdrawn` 一列 ＋ `CONSENT_WITHDRAW` → **真的 `unlink()`（nonce 一起）**
→ `erased` 一列（帶被刪位元組 sha256）＋ `PERSONA_ERASED`。
撤回與刪除分成兩筆是刻意的：合成一筆就看不見「宣告了但沒做」，
而那正是唯一值得上鏈的東西（`consent.py` 誠實邊界 2）。

**而「宣告了但沒做」要補得完。** 第一版寫完自己 review 才發現：
撤回宣告成功、`PERSONA_ERASED` 那一步炸掉（斷電／磁碟滿）之後，
狀態卡在 `withdrawn`，再撤回一次也**永遠**簽不出刪除證明——
「宣告了但沒做」變成死結，那比看不見還糟。修法是重試時**沿用原本那一筆撤回**
（不再宣告一次，帳本不多一筆重複），把刪除補完。
判準：`test_half_done_withdrawal_can_be_finished`。

#### token 要不要（想清楚了，結論記在這裡）

**預設不要共用 token。** 公網頁上印著「你可以隨時要求我們刪除」，
共用 token 只有工作人員有 ⇒ 觀眾自己撤回不了 ⇒ 那句話還是假的。
`sub_id` 本身就是能力憑證（只在觀眾手機上）。

⚠ **誠實邊界：id 猜得到的話，別人可以撤回你的分身。** 那是破壞不是洩漏——
失敗方向朝「刪掉了不該刪的」而不是「該刪的沒刪」，在這件事上是可以接受的那一邊。
要更嚴的場地用 `--withdraw-token`（有測試守著它真的會擋）。

### 2.5 ⚠ 第一版寫出來是 O(N²)，量了才發現——數字記在這裡

展場硬約束 1 是**秒級互動**。封印多做的事是：寫兩個檔、簽一筆 `CONSENT_GRANT`。
第一版每簽一筆就 `Logbook.load()` ＋ `Logbook.save()` 整檔重寫 ⇒ **O(N²)**。

實測（這台 Mac，`tmpfs` 以外的一般磁碟，純本機零模型）：

| | 第一版 | 修好之後 |
|---|---|---|
| 每張卡（第 1 張） | 26 ms | 24 ms |
| 每張卡（第 200 張） | **395 ms** | 8.3 ms |
| 每張卡（第 600 張） | 未量（會更糟） | **7.7 ms** |
| 撤回一次（N=200） | **2.0 s** | 0.47 s |
| 撤回一次（N=600） | 未量 | **1.23 s** |
| `roster()` 讀 600 人 | — | 1.17 s |

對照組：**舊寫法（原文直接上鏈）每張 1.3 ms**。所以封印的代價是
**每張多約 6 ms**，這個數字不隨張數長。

修法（`TwinVault.book()` / `_append_new()`）：
1. 簽章鏈以 `(size, mtime_ns)` 當指紋做記憶體快取——**不是假設「只有我在寫」**，
   別的行程（`serve --allow-withdraw` vs `loop`）動過檔案就重讀；
2. 寫入改成**附加**到 ndjson 尾巴，不整檔重寫。
   ⚠ 這放棄了 `atomic_write_bytes` 的原子性：當機當在 write 中間，尾巴可能是半行，
   `Logbook.load` 會在那一行炸掉。**吵，不是安靜壞掉**，這是刻意的——
   真相來源是 `twinstore` 那個 SQLite（`synchronous=FULL`），簽章鏈是它的
   **附加**證明不是替代品。

**撤回仍然是 O(N)**（約 2 ms × 鏈長）：`consent.audit()` 會把整條簽章鏈
逐筆驗簽之後才准動它。**這是故意的**——不驗就往上加，等於在一條可能已經壞掉的
鏈上簽名。N=600 ⇒ 1.2 秒，觀眾按下「確定撤回」等得起；N=2000 ⇒ 約 4 秒，
到那個量級要再看一次。

---

## 三、🔴 既有資料怎麼辦（人類明令：資料不要刪除）

**一列都沒刪、一列都沒改。** 兩件事分開講：

### 3.1 舊鏈裡的原文**拿不掉**

2026-09-21 之前寫進 `twinstore` 的 `submitted`/`generated` payload 帶著原文，
而那條鏈由 SQLite trigger `RAISE(ABORT)` 強制 append-only。
**拿不掉就是拿不掉。** 不假裝、不靜靜處理：

* `current()` 對那些主體回 `plaintext_on_chain: True`，`build_view()` 把它
  出到畫面層——**這個旗標不准隱藏**。
* 那些主體撤回時，`erased` 事件帶 `residual_plaintext_seqs: [seq…]`
  與 `fully_erased: false`。**不准對他們說「已完全刪除」。**

### 3.2 `twinvault migrate`：抄一份出來，讓舊主體撤回得了

```
python3 ops/exhibit/twin/twinvault.py migrate --db <庫>
```

做兩件事，都不是刪除：

1. 把舊列裡的原文**另外抄一份**到鏈外檔案庫（於是那位主體從此撤回得了，
   而且之後的讀取走檔案庫）；
2. 追加一列 `note`，把「這幾個 seq 的鏈上原文永遠拿不掉」記進帳本。

**這不是「清乾淨」。** 跑完之後鏈上那一份還在。
**新鏈開始才乾淨，舊的只能誠實標記。**

### 3.3 1003 上那個庫

`/c/Users/w401/vacant_twin/store/twinstore.sqlite3` 是真相來源，
本次**沒有動它**（沒刪、沒覆寫、沒跑 migrate）。
要在展前處理的話，順序是：`twinstore verify` → 離機備份 → `twinvault migrate`
→ 再 `verify`。migrate 只追加一列，鏈驗得過。

---

## 四、⚠ 這次**沒有**解掉的（不准說「原文問題處理好了」）

1. **雲端郵箱那一份原文刪不到。** `vacant-world-cloud` 的 `app.delete` 零路由。
   `withdraw()` 回傳的 `cloud_copy` 永遠是 `"not_attempted_no_endpoint"`
   ——**不是 `false`、更不是省略**。有了端點再改。
   （已做的是：撤回之後 `publish` 不再往雲端送新的。）
2. **鏈記的是「我們記下我們刪了，而且刪掉的位元組 sha256 是 X」，
   不是「世上沒有副本」。** 作業系統快取、WAL、備份、觀眾手機截圖都不在射程內。
   raises-cost 不是 prevents。
3. **跨程序互斥靠 `atomic.file_lock`，那在 Windows 上退化成 no-op**
   （`atomic.py` 自己寫明）。展場的 loop 與 serve 跑在 1003 上面那台 Linux VM，
   這條線成立；搬到 Windows 原生跑就沒有互斥了。
4. **公共大螢幕改代號＋類別**（裁決 §三-3，`vacant_hm/world3/index.html:1775`）
   **不在本次範圍**。本次只做到 `build_view` 對撤回過的人不再吐 card 與三句話。
5. 裁決 §四列的同意九條殘餘（§5.1-1 可以替別人投、§5.1-3 敏感推論無防呆、
   §5.1-5 可以拒絕、§5.1-7 退役程序、§5.1-8 未成年）**一條都沒動**。
6. **`ops/exhibit/twin/loadtest_twin.py` 還走舊的直接 `store.append` 路徑。**
   它量到的吞吐**不再是產品路徑的吞吐**（少了封印那 6 ms／張）。
   §2.5 的表是手量的替代數字，不是那支量出來的。要正式的壓測數字得先改它。
7. **`ingest` 的封印防呆擋下一張卡時，那張卡的原文已經寫進檔案庫了**
   （封印是先寫檔再組 payload）。鏈上乾淨，但檔案庫裡留著一份沒有人指得到的
   副本（`error` 事件標 `vault_copy_kept: true`）。它刪得掉——
   只是要用 `sub_id` 手動 `withdraw`，不會自己消失。

**可以說的**：原文不上鏈、撤回可驗、撤回之後畫面上什麼都不留。
**不准說**：倫理處理好了。

---

## 五、怎麼自己驗（每一條都有負控制）

```bash
python3 ops/exhibit/twin/twinvault.py selftest     # 6 節，含 5 個負控制
python3 ops/exhibit/twin/twinlink.py  selftest     # 原本那 7 節，仍全綠
.venv/bin/python -m pytest tests/test_twinvault.py tests/test_twinstore.py \
                          tests/test_twinlink_resilience.py -q
```

`tests/test_twinvault.py` 第一條是**量具的負控制**：
先用 2026-09-21 之前的寫法把原文寫上鏈、證明「鏈上找得到原文」這件事量得出來，
後面那些「鏈上找不到原文」的綠燈才不是因為我找錯地方。

---

## 六、改到的檔案

| 檔案 | 改了什麼 |
|---|---|
| `ops/exhibit/twin/twinvault.py` | **新增**。檔案庫＋兩層防呆＋撤回＋migrate＋selftest |
| `ops/exhibit/twin/twinstore.py` | `SEAL_TAG`、`withdrawn`/`erased` 兩個 kind、`vault` 惰性屬性、`current()` 鏈外開封＋`plaintext_on_chain` 旗標 |
| `ops/exhibit/twin/twinlink.py` | `ingest`/`generate` 改走 `append_sealed`；`degrade_kind`；`withdraw()`；`serve` 的 `/withdraw/<id>`；`build_view` 的 `erasure_honesty`；CLI `withdraw` |
| `tests/test_twinvault.py` | **新增**，含量具負控制與「產品路徑真的呼叫防呆」那一條 |
| `tests/test_twinlink_resilience.py` | 一處：`degrade_reason` 改從 `current()` 讀（它搬到鏈外了），另加 `degrade_kind` 斷言 |

**append-only trigger、雜湊鏈、摺疊狀態一個字都沒動。**
