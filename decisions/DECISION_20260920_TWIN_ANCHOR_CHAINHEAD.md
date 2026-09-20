# DECISION 2026-09-20 — 鏈頭錨定：把 twinstore 的已知弱點變成「有東西擋著」

缺口 E 的原話：

> 雜湊鏈證明的是「改一列看得出來」，不是「竄改不可能」——拿得到檔案的人可以整條重算。

`ops/exhibit/twin/twinstore.py` 的 docstring 自己已經誠實寫了這條邊界。
這次把它從「已知弱點」變成「有東西擋著」。**新檔一支：
`ops/exhibit/twin/twinanchor.py`。**

---

## 一、先回答「能不能重用 checkpoint.py」——能，而且重用了

`vacant_network/checkpoint.py`（18 §2 V1 存檔點）做的就是這件事，
而且**存檔點自身成鏈**。對照一下缺的東西：

| 存檔點要的 | twinstore 給得出的 |
|---|---|
| `logbook.entries`（每個有 `.seq`、`.hash()`） | `twin_event` 每列的 `seq`、`row_sha256` |
| `logbook.stream_id()` | `store.genesis()`（含 `store_id`） |
| `logbook.head()` | 最後一列的 `row_sha256` |

⇒ 只需要一個**唯讀視圖** `TwinChainView`（約 30 行），把 SQLite 的列偽裝成
`Logbook`。`issue_checkpoint()` / `verify_checkpoint()` /
`verify_checkpoint_chain()` **一個 byte 都沒改**，測試
`test_it_really_reuses_checkpoint_module` 釘住這件事（比對 `CHECKPOINT_VERSION`
與 `_CLAIM_FIELDS`，抄一份就會紅）。

免費拿到的：簽章覆蓋整個 claim、`vacant_id` 必須由 `pub` 重算（擋換 pub 冒名）、
`entries_hash` 窗口承諾、`chain_head` 一致性、存檔點自身成鏈。

**唯一沒重用的是 `retro_audit_window()`**——那支拿 `checks.py` 沙箱重跑交付答案，
分身卡沒有「答案對不對」這回事。但它留下的兩個欄位照用，而且用在三態上：

- `retro_audits = {"twinstore_verify": bool, "prev_anchor_holds": bool}`
- `retro_missing = ["prev_anchor_holds"]` **當第一枚沒有前一枚可比時**
  ——🔴 量不到就進 missing，**不寫 false**。`checkpoint.py` 的 docstring
  本來就是這樣定義 missing 的（「稽核不到是被斷言的，不是被跳過的」），
  這裡是照著它的語意用，不是借殼。

### 兩個刻意的設計決定

1. **窗口是累積的 `[1, 鏈頭]`，不是增量。** 增量窗口下抽掉中間一枚錨，
   那一段歷史就沒有人承諾過；累積窗口下**最新那一枚自己蓋住全部歷史**。
   代價 O(N)，展場 N 是幾百到幾千。
   測試：`test_window_is_cumulative_so_the_latest_anchor_covers_all_history`
   （只留最後一枚，仍抓得到改第 2 列）。
2. **`TwinChainView` 刻意沒有 `append()`。** twinstore 的寫入只有
   `TwinStore.append()` 一條路（trigger 擋其他路），視圖補一個寫入口
   就等於在 append-only 的牆上自己開後門。測試 `test_the_view_has_no_append_door`。

---

## 二、錨定到哪（每個出口在斷網之下退化成什麼）

離線是紅線 ⇒ **四個出口沒有一個依賴外部服務**。

| 出口 | 指令 | 斷網之下退化成 | 擋得住整條重算嗎 |
|---|---|---|---|
| ① 本機錨鏈 | `emit` | **不退化**（本來就不用網路） | ❌ 單獨不行。跟 store 同一顆磁碟。它擋的是**偷懶與意外**（只改 store 忘了改錨鏈），不是有決心的人。 |
| ② 另一台機器 | `mirror --scp` | **停**。`ok=false` ＋ rc ＋ stderr 原文，**不寫 0**。已送出的副本照常有效，只是不再更新 ⇒ 偵測解析度停在最後一次成功那一枚。 | ✅ 只要那台沒被同時攻下 |
| ③ 可攜媒體／掛載點 | `mirror --dest` | **不退化**（USB 不需要網路）。退化的是**人**：沒人去插就沒有新副本。 | ✅ 展場最實際：開館前插一次、閉館後插一次 |
| ④ 印出來的紙／QR | `slip` / `slip --qr` | **不退化**（紙不需要電）。代價：紙上只有摘要前 128 bit，**能比對不能獨立驗簽**。 | ✅ 唯一連「磁碟整顆被換掉」都還在的出口 |

**`vacant_network/logbook.py` 的既有鏈刻意沒列進來**：它跟 store 同一顆磁碟，
安全性等於①，卻要多養一條鏈與一把金鑰。要多一層就走②③④。

②③④ 共同前提：**送出去的不只是錨鏈，還有公鑰**（`anchor_pub.txt`）。
沒有離機公鑰，`verify` 只驗得出「這條錨鏈自洽」。

---

## 三、誰簽、金鑰放哪

- **一把專用的 Ed25519**，`Identity.generate()` → `Identity.save()`，
  預設落在 `ops/exhibit/twin/store/anchor_key/identity.key`。
- 兩道不相干的紀律同時蓋住它：`.gitignore` 第 25 行整個 `store/`；
  檔名 `identity.key` 是 `record.py` RECORD_SPEC §7 排除私鑰的對象。
  測試 `test_private_key_is_0600_and_under_a_gitignored_default` 直接讀
  `.gitignore` 驗這件事。
- 🔴 **沒有碰任何既有憑證**：不讀 `auth.json`，不共用 G 實驗或收據那幾條鏈的身份。
- `init` 不覆寫既有金鑰（覆寫＝舊錨全部變無主）；其他子命令**不會偷偷產金鑰**
  （`load_key` 直接 `FileNotFoundError`，連目錄都不建）。

---

## 四、偵測得到什麼、偵測不到什麼

`verify` 跑**七道關**，退出碼 0 綠 / 1 紅：

1. `store_verify` — twinstore 自己的鏈（**錨不取代它**，見下）
2. `anchor_chain` — 錨自身成鏈（抽掉中間一枚會紅）
3. `per_anchor` — 每一枚對現在的 store 重驗（簽章＋`entries_hash`＋`chain_head`）
4. `stream_bound` — 每一枚的 `stream_id` 必須等於這個 store 的創世串
5. `no_rollback` — 現在的鏈頭 seq 不得低於任何一枚錨的窗口尾
6. `single_signer` — 所有錨同一把公鑰
7. `pubkey_pinned` — 跟**離機**公鑰比對；沒有可比的東西 ⇒ **`null`**

### 🔴 偵測不到的（誠實邊界，逐字寫進 docstring）

1. **拿到金鑰的人重新簽一條**——他重算 store、重簽整條錨鏈，本機完全乾淨。
   反制只有離機的公鑰或紙條。沒給 ⇒ `pubkey_pinned` 寫 **`null` 不是 `false`**
   （`false` 會被讀成「比對過、不符」）。`--require-pin` 把這個 `null` 變紅。
   **展場那條線必須開 `--require-pin`。**
   這一條有**可執行標本**：`test_resign_with_stolen_key_is_NOT_caught_without_a_pin`
   斷言 `rep["ok"] is True`——**那條測試在釘邊界不是在釘功能**，
   哪天它紅了是好消息，但 docstring 要跟著改。
2. **偵測解析度＝錨的間隔。** 最後一枚錨之後追加的列，錨一句話都沒說。
3. **錨定不取代 `twinstore.verify()`。** 錨的 `entries_hash` 串的是每列
   `row_sha256`，不重算 `payload_json` 的雜湊 ⇒ 單改 `payload_json` 而不動
   `payload_sha256`，錨看不到、`twinstore.verify()` 會抓到。所以 `verify` 兩個都跑。
4. **「錨鏈完整」≠「沒漏收」**（twinstore 誠實邊界 3 原封不動）。
5. **紙條驗的是摘要不是簽章。**
6. **可用性不在守備範圍。** `rm -rf store/` 之後這一支什麼都說不出來。

---

## 五、實跑（每個綠燈都配負控制）

| 判準 | 結果 | 檔 |
|---|---|---|
| `twinanchor.py selftest` | **20/20**（含 6 個負控制 A–F） | `evidence_anchor_20260920/selftest.txt` |
| **對 selftest 本身的負控制** | 三個蓄意破壞全部讓它變紅（rc=1） | `negctl_on_the_selftest.txt` |
| `tests/test_twinanchor.py` | **41 passed** | `pytest.txt` |
| **對測試的負控制** | 三個破壞紅在三組**不同**的測試 | `pytest_negctl.txt` |
| `e2e_anchor.sh`（離線，出口①③④） | **20/20** | `e2e_anchor_run.txt` |
| **出口②活體**：真的 scp 到 1003 | **18/18** | `live_1003_mirror.txt` |

### 核心那兩條（缺口 E 的正題）

```
負控制 A：整條重算（drop seq 3、全部重新編號重算雜湊）
  前提  twinstore.py verify      → rc=0 綠   ← 弱點屬實，紅燈才有對象
  判準  twinanchor.py verify     → rc=1 紅
        錨 #0（窗口尾 7）驗不過：entries_hash 不符（窗口內 episode 被竄改或不完整）
        鏈頭退回去了：錨過 seq 7，現在只到 6

負控制 B：截掉鏈尾 2 列
  前提  twinstore.py verify      → rc=0 綠   ← 合法前綴，它只往前走
  判準  twinanchor.py verify     → rc=1 紅
        no_rollback = {ok: false, anchored_max_seq: 6, store_head_seq: 4}

對照組：沒被動過的鏈 ＋ --require-pin ＋ 紙條 → rc=0 綠
```

**「兩關互為備援不是重複」有證據**：破壞 `no_rollback` 之下整條重算那兩條
沒紅（`entries_hash` 自己抓到）；破壞 `verify_checkpoint` 之下截斷那條沒紅
（`no_rollback` 自己抓到）。

### 出口②活體（1003）

對手 `w401@100.119.113.56`（Windows）。**`ssh` 用 `/c/...`、`scp` 用 `C:/...`**
（MSYS 只轉換裸參數，這個坑造成過一次假綠）。兩台的 `anchors.jsonl` sha256
逐字相同 `9dcc710f…96c4`；再把 1003 上那份 `anchor_pub.txt` 抓回來當
`--pin-file`，對被整條重算過的 store 重驗 ⇒ rc=1。用完的遠端目錄已刪。

---

## 六、沒有做的事（明講）

- **沒有 push 任何遠端、沒有部署。** 只有本機 commit。
- **沒有碰 vacant-dev**（`/var/tmp/vacant_abpi/` 與那邊的長跑行程一個都沒動）。
- **沒有碰展場那個 store**：所有實跑都在 `mktemp -d` 或 scratchpad 裡。
- **沒有把 twinanchor 接進 `exhibit_boot.sh` / `venue_check.sh` / systemd**。
  接線是下一步，要人類決定「多久錨一次、副本插到哪」——那是營運決定不是技術決定。
  建議的最小接法（**尚未實作**）：開館前 `emit` 一枚、閉館後 `emit` 一枚＋
  `mirror --dest <USB>`，`venue_check.sh` 加一行
  `twinanchor verify --require-pin --pin-file <USB>/anchor_pub.txt`。
- **1003 上沒有留任何常駐的東西**（測試目錄已刪）。
