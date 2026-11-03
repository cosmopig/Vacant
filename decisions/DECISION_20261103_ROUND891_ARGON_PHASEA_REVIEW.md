# DECISION — round 891：auto/argon Phase A（步鏈分卷封印）commit 審查

> 日期：2026-11-03（`date` 實量）
> 審查人：研發負責人（round 891，qwen27b 分支）
> 被審：`auto/argon` `a167d091`（merge qwen27b）之上的兩 commit——
> `c0b94747`（Phase A core：`recorder.py` +190/−31、`tests/test_stepchain_sealing.py` +149）
> 與 `af3c1d14`（GC fix R2：`retention.py` +77/−18、`tests/test_retention.py` +52）。
> 依據：資深指示 #2「它在 auto/argon 上修好了的 commit，你審查過才 merge」；
> 凍結設計 `decisions/DECISION_20261103_STEPCHAIN_SEALING.md`（Phase A＝§3.1+§3.2，驗收 C1/C2/C6）。

## 0. 裁決

**Merge HOLD。** 不是「拒絕」，是「門未齊」：

1. **CI**（ASSIGNMENT 合併規則：「該 sha CI 🟢 且收錄測試數不少於現 HEAD」）：
   開場實量三分支皆「還沒跑完」；**本輪末更新**——argon 當前 HEAD `af3c1d14` 已 **🟢**
   （4,634 passed/70 skipped、收集 4,703 ≥ qwen27b 4,698），qwen27b `7d987f66` 🟢
   （4,629/70、與基線一致）；argon 在審查期間又推進（`c0b94747` → `af3c1d14`），
   補門條後需對**最終 sha** 重新綠。
2. **Phase A 預註冊驗收缺口未補**（§3，G1–G4）——缺口補齊前，「Phase A 完成」不成立。
3. **一個潛在覆寫 bug**（§4，B1）——Phase A 不可達、Phase C 必踩；建議本批一併修（一行級）。

機制本身**審查通過**（§1、§2、§5 實測證據）；R2 GC 修正確。以上三門齊後，
本批可直接 merge（無待重審的實質設計問題）。

## 1. 機制審查（逐點對照設計 §3.1）

| 設計要求 | 實作 | 判定 |
|---|---|---|
| seal 事件 payload（設計 §3.1 七鍵）：`sealed_file / sha256_prefix / first_seq / last_seq / entry_count / last_entry_hash / sealed_at_ms` | `recorder.py:372-381`：設計七鍵全數＋`schema` 封套（共八鍵；**無 `sealed_by`**——設計未要求，seal 事件簽章者＝該事件自身簽章識別、與其他事件同） | ✅ 寫路徑 `hashlib.sha256(raw_bytes)`（封印前檔案原始位元組、含末條換行）；verify 路徑 `hashlib.sha256(raw[:cut+1])`（除 seal 行外全部位元組）；兩者在「末條行已換行終結」時逐位元組相同（寫格式每條 `+b"\n"`＋`_repair_tail` 兜底半行撕裂）——實測封印後 verify=True 即此一致性的證據 |
| 封印卷命名 `chain-000001.ndjson`（6 位 0 補零、遞增）；活動卷保留 `chain.ndjson`；`os.replace` 原子 | `sealed_name = f"chain-{next_vol_num:06d}.ndjson"`；`os.replace(chain_path, dir/sealed_name)`；新卷寫回 `chain.ndjson` | ✅ |
| 新卷首條 prev_hash＝seal 事件 hash；seq 連續 | `book = Logbook([genesis, seal_e])` 後 `_append` 續 seq（seal 事件本身取 seq＝卷末條＋1、入跨卷鏈） | ✅ 實測（活鏈快照）：N＝21,356 條 → seal（seq 21,357）→ 新卷首條 finding（seq 21,358）、verify 全鏈 21,358 條真；公式 N 條 → 封印卷 N+1 行、seal seq N+1、新卷首條 seq N+2、全鏈 N+2 條（同日 N＝21,425 重驗同式） |
| 活動卷＝舊格式，verify 不變 | legacy 路徑（無 `chain-*.ndjson`）完全不走新分支 | ✅ 兩條真鏈實測（§5） |
| 缺卷 ⇒ UNKNOWN（不是 True、不 crash）；卷內改動/刪 seal 行 ⇒ BROKEN | `_sealed_volume_paths` 依 6 位零補零編號排序；斷號回 `(False, "UNKNOWN: volume sequence broken … missing volume")`；卷末非 seal／prefix 不符／計數不符／末條 hash 不符 ⇒ 無 "UNKNOWN" 前綴的 BROKEN 訊息 | ✅ 實測（12 步合成、缺卷/篡改/刪 seal 三負控制） |
| MixedSignerRefused 不回歸 | 未觸該路徑；測試在案 | ✅（`tests/test_stepchain_mixed_signer.py` 綠） |
| fail-open：seal 失敗不殺 agent | hook `main()` 全包 `except Exception → errors.jsonl → return 0` | ✅ 見 §4 建議 R1（更細部） |
| 不新增必填設定；無卷時行為逐位元組不變 | `volume_max_entries: int | None = None`（預設關閉）＋`volume_max_bytes` 2MiB；舊路徑零改動 | ✅ |

## 2. R2 修復審查（`af3c1d14`）

- **缺陷（round 889 審查發現）**：`compact_trace` 的 blob keep-set 只掃活動 `chain.ndjson`＋
  一個 `chain-000001`——多卷後，封印卷內 blob 引用被當孤兒回收 ⇒ 步鏈 verify 後期 UNKNOWN。
- **修復**：keep-set 改掃**全部殘存卷**（`chain-*.ndjson` 與前瞻 `chain-*.ndjson.gz`）＋活動卷。
- **同批一併修**：`usage_report` 跨卷計數、`verify_trace_chains` 偵測含 `chain-*.ndjson*`
  的項目（原先只認單一 `chain.ndjson` 存在性）。
- 判定：**正確、必要、與 Phase B（gzip 冷卷）前瞻相容**。測試 52 行新增、綠。

## 3. Phase A 預註冊驗收缺口（G1–G4，merge 前需補）

設計檔 §五 C1–C6 是**預註冊**驗收。對照 `tests/test_stepchain_sealing.py`（149 行）：

- **G1（C1 未達）**：C1 要求「30k-step 合成專案：無單檔 > VOLUME_MAX_BYTES、verify 全真、
  跨卷 verify_since 可用、篡改中段卷 ⇒ BROKEN、刪 seal 行 ⇒ BROKEN（非 UNKNOWN）」。
  現行測試＝12 步、3 卷。需 30k-step 規模測試（機制已具規模能力，見 §5 21.6MB 實測；
  缺口是**測試本身**）。
- **G2（C2 未達）**：C2 要求「兩條真鏈（`b0a568dfe7dbe3b0` 21.6MB、`535f1510326fb03a` 15MB）
  升級前後 verify 一致、仍可追加」。現行只有合成 legacy 測試。
  （round 891 審查時已在**副本**上實測通過——§5；但驗收測試應入庫，不靠審查者手動。）
- **G3（C6 未達）**：C6 要求「30k-step 下 append P99 延遲增量 ≤10%、verify ≤5s，
  對照升級前基準」。完全缺失。實測觀察（§5）：21.6MB 單次 seal＝0.218s（含全檔 sha256）；
  但**每次 append 的大小/行數掃描**在接近 2MiB 時會讀全檔——O(檔案大小) per append，
  30k-step 下累積不可忽視。C6 的 ≤10% 門檻需要實測數據；建議 argon 補基準測試
  （或明確記錄「C6 待量測」為 Phase A 未收口項，不得宣稱 Phase A 完成）。
- **G4（負控制斷言不足）**：「刪 seal 行 ⇒ BROKEN（非 UNKNOWN）」測試只斷言 `not ok`，
  未釘死 why 不為 UNKNOWN（實現訊息正確、缺口在斷言）。一行級修正。

## 4. 發現的問題

- **B1（潛在覆寫 bug，建議本批修）**：`next_vol_num = len(vols) + 1`。若卷號出現缺口
  （L3 回收刪除某卷、或手動移除），`len+1` 會等於一個**已存在**的封印卷號，
  `os.replace` 直接覆蓋它＝靜默銷毀已封印證據。修法：`max(既存卷號) + 1`（空則 1）。
  Phase A 無回收⇒不可達；**Phase C（預算回收）必踩**。
- **R1（堅實性建議，非阻門）**：seal block 對整卷 `json.loads`——若卷內有一行腐損
  且已達封印門檻，seal 會 raise；hook 層 fail-open 接住（該步未錄、鏈完好），但更優雅是
  seal try/except ⇒ 跳過本次封印、照常 append、下次再試。
- **O2（觀察）**：`_append` 每次對活動卷做大小/行數檢查（<2MiB 時讀全檔數行）——
  單卷 2MiB 上限下每次 ≤2MiB 讀取，30k-step ≈ 60GB 讀取/專案；C6 的 P99 ≤10%
  門檻正是要量這個。建議 argon 在 C6 基準裡明列。

## 5. 實測證據（round 891，全部在副本／合成目錄，**未動 `~/.vacant`**）

- **測試**（argon worktree、`.venv` python）：`tests/test_stepchain_sealing.py` **5/5 綠**；
  trace/recorder/retention/mixed-signer 回歸集群 **162 綠**。
- **C2 spot-check（真鏈；活鏈、數值為快照）**：`~/.vacant/trace/projects/{b0a568dfe7dbe3b0, 535f1510326fb03a}`
  複製到 /tmp 後以 argon 新代碼 verify（行數＝splitlines、末行無換行故 `wc -l` 少 1）：
  - `b0a568dfe7dbe3b0`：21,355 行 → `verify=True`（21,355 entries）
  - `535f1510326fb03a`：14,944 行 → `verify=True`（14,944 entries）
- **C2 migration（真鏈、副本上；真鏈為活鏈、e014 併行追加中，數值為各時刻快照）**：b0a5 副本 `volume_max_bytes=1` 強制封印＋append（時鏈已長至 N＝21,356 條）：
  - 封印卷 `chain-000001.ndjson`＝**21,357 行＝21,356 條＋1 seal 行（seal 為末行、type `volume_seal`）**；
    seal payload（八鍵）：`entry_count=21357`（＝封印卷總行數；recorder.py:380 `len(vol_entries)+1`、
    verify 路徑 recorder.py:1147 以 `!= len(lines)` 核對、同一計算式）、`first_seq=1`、`last_seq=21356`（＝seal 前末條 seq）、
    `last_entry_hash`（＝seal 前末條之 hash）、`sealed_file=chain-000001.ndjson`、`sha256_prefix`（32 hex）、`sealed_at_ms`、`schema=vacant-trace/1`。
  - seal 事件本身 seq＝21,357（入跨卷鏈）；新活動 `chain.ndjson`＝1 條（finding、seq 21,358）。
  - `verify=True`（全鏈 21,358 條＝N＋seal＋新條）、`verify_since(None)` 可用、**封印耗時 0.218s**（含 21.6MB 全檔 sha256）。
  - **公式重驗（同日、N＝21,425 快照）**：封印卷 21,426 行（末行 `volume_seal`）、`entry_count=21426`、`last_seq=21425`、seal seq 21,426、新卷首條 seq 21,427、全鏈 verify=True（21,427 條）——與 N＝21,356 快照完全同式（N 條 → 封印卷 N+1 行、seal seq N+1、新卷首條 seq N+2、全鏈 N+2 條）。
- **全量套件（完整 checkout，兩分支並跑）**：argon **exit 0（0 失敗）**、qwen27b **exit 0（0 失敗）**；
  收集數本地＝CI 逐位一致：argon **4,703**（CI af3c1d14 4,634 passed/70 skipped）、
  qwen27b **4,698**（CI 7d987f66 4,629 passed/70 skipped）⇒ argon 新增 5 個測試全綠、無回歸、
  滿足「收錄測試數不少於現 HEAD」。

## 6. 環境發現（非 argon 缺陷，留給 argon/監督者知會）

`~/dev/wt/argon` 曾設 sparse-checkout（`/*`＋`!/runs/`，省 825MB），導致
`tests/test_appendix_bg_census_r480.py::test_census_clean` 在該 worktree 假失敗
（`UNSCANNED`＝掃不到 `runs/`；同測試在 qwen27b 完整 checkout **通過**）。
round 891 已 `git sparse-checkout disable`（物化 `runs/` 356 目錄、可逆）後重跑全量＝**exit 0**（與 qwen27b 同環境對照一致）。
⚠ 若 argon agent 依賴稀疏狀態省磁碟，注意此改動（恢復＝`git sparse-checkout set /* !/runs/`）；磁碟現 66G free，不急。

## 7. Merge 門（全齊即放行）

1. 最終 sha CI 🟢＋收錄測試數不少於現 HEAD（ASSIGNMENT 規則）。**狀態（本輪末）**：
   `af3c1d14` 🟢 4,634 passed/70 skipped、收集 4,703 ≥ qwen27b 4,698——已滿足於當前 HEAD；
   argon 補門條後需對新 sha 重新綠。
2. G1（30k-step 測試）＋G2（真鏈驗收入庫）＋G3（C6 基準或明列未收口）＋G4（斷言）補齊。
3. B1 修法（`max+1`）或明文留給 Phase C 並加防護註記。
4. 全量套件 ≥ 基線（4,629 passed / 70 skipped 口徑、完整 checkout）。

## 8. 誠實邊界

- 本審查＝**審查者獨立實測＋逐行閱讀**，非 argon 的驗收證據；G2 的「真鏈」實測是
  round 891 手動 spot-check（副本），不替代入庫測試。
- 「機制審查通過」不意味著「Phase A 完成」——完成＝設計 §五 C1–C6 全數以測試收據落地。
- C6 的 ≤10% 延遲門檻目前**沒有數據**；任何「Phase A 已完賽」的表述都屬不實，
  直到 G3 補齊或明列未收口。
