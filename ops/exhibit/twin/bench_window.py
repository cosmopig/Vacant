"""twin/bench_window — 視窗與退役在「第七天規模」下還跑不跑得動。

## 這支在架構裡承重什麼

`--recent` 的預設值（60）與 `RETIRE_SHOW_MAX`（12）是**用數字定的**，
這一支就是那些數字的來源，也是日後改預設值時重跑的那一支。

判準：`loop --interval` 預設 10 秒 ⇒ **一輪 `export` 必須遠小於 10 秒**，
否則展場的無人值守迴圈會追不上自己。

⚠ **這裡不量磁碟。** 那件事已經量過（600 人＝1MB、605 bytes/event、線性），
  而且它從來不是瓶頸——瓶頸是電視的出場佇列。

實跑（Mac，2026-09-21，每格取 7 次最小值）。
**數字的唯一真相是落盤的那份 JSON**：`evidence_window_20260921/bench_mac_20260921.json`
——下面這張表是從它抄的，改了要一起改（表跟證據對不上＝敘述超出實際交付）。

| 人數 | 第一輪退役幾位 | 第一輪（含大批退役） | 穩態（有視窗） | 穩態（關窗對照） | 落盤 JSON |
|---|---|---|---|---|---|
| 100 | 40 | 119.8 ms | 32.1 ms | 34.1 ms | 45.8 KB |
| 300 | 240 | 423.9 ms | 111.3 ms | 144.6 ms | 48.6 KB |
| 600 | 540 | 1894.1 ms | **448.1 ms** | 292.7 ms | 52.7 KB |
| 1000 | 940 | 4437.1 ms | 395.3 ms | 532.8 ms | 58.2 KB |

讀法：

* 600 人（展期規模）穩態一輪 **448.1 ms ＝ 10 秒迴圈的 4.5%**。夠。
* **看不出視窗與退役本身有成本**——注意方向是**反的**：600 人時有視窗那邊慢
  155 ms，1000 人時有視窗那邊**快** 138 ms。同一個比較兩個方向 ⇒ 這個差
  **在雜訊裡**，不可以講成「視窗省了多少」或「視窗花了多少」。真正的成本在
  `store.roster()`（改動之前就有的），想再快要動它，現在不划算。
* **落盤 JSON 45.8 → 58.2 KB（100 → 1000 人），≈ +13.8 bytes/人。**
  兩件事各佔一半：
  - `retiring[]` 有 `RETIRE_SHOW_MAX` 上限 ⇒ **告別那一段不隨人數長**
    （沒有上限時，大批退役那一輪會把幾百個人的告別全塞進去，600 人實測 182 KB）；
  - `roster_ids` **刻意**不設上限 ⇒ 這 12.4 KB 的成長就是它。那是電視那端
    對帳用的，設了上限會讓帳銷不掉（見 `twinlink.build_view` 該欄的長註解）。
  ⚠ 所以**不可以再說「JSON 不隨人數成長」**——它會，只是每人 14 bytes。
* 第一輪成本隨人數成長（119.8／423.9／1894.1／4437.1 ms）。⚠ **那一欄只跑一次、
  不是最小值**，而這一輪機器上同時有三個 agent 在跑；前一次量同一段是
  141.7／404.2／860.1／1397.8 ms。**兩次差到三倍 ⇒ 那一欄只能讀出
  「1000 人的第一輪仍在 10 秒之內」，不能拿來談成長曲線。**

⚠ **這台 Mac 不是展場那台**（展場＝1003，Windows）。這些數字是量級參考，
  用途是「10 秒迴圈追不追得上」這個是非題，不是效能承諾。

用法：
    python3 ops/exhibit/twin/bench_window.py <repo 根目錄>
"""
import json
import pathlib
import sys
import tempfile
import time

REPO = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import twinlink as T          # noqa: E402
from ops.exhibit.twin.twinstore import (            # noqa: E402
    KIND_GENERATED, KIND_SUBMITTED, TwinStore,
)

DAY = 86_400_000
REPS = 7


def build(n, db):
    st = TwinStore(db)
    base = int(time.time() * 1000) - 6 * DAY
    for i in range(n):
        ms = base + i * 1000
        st.append(KIND_SUBMITTED, f"p{i:05d}", {"card": {
            "need": "把一件小事做完" * 3, "shape": "圓潤", "texture": "光滑",
            "color": "暖土", "vibe": "慢", "first_line": "你好"}},
            source="bench", ts_unix_ms=ms)
        st.append(KIND_GENERATED, f"p{i:05d}", {
            "arrival": "我到了" * 4, "working": "讓我試試" * 4, "handover": "做完了" * 4,
            "engine": "lmstudio:gemma-4-12b-it-qat", "latency_ms": 11400}, source="bench",
            ts_unix_ms=ms + 500)
    return st


rows = []
for n in (100, 300, 600, 1000):
    with tempfile.TemporaryDirectory() as td:
        db = pathlib.Path(td) / "b.sqlite3"
        st = build(n, db)
        out = pathlib.Path(td) / "v.json"
        first0 = time.perf_counter()
        r1 = T.export(st, out, recent=60, record_retire=True)
        first = (time.perf_counter() - first0) * 1000
        best_new, best_old = 1e9, 1e9
        for _ in range(REPS):
            t = time.perf_counter()
            T.export(st, out, recent=60, record_retire=True)
            best_new = min(best_new, (time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            T.export(st, out, recent=0, record_retire=False)
            best_old = min(best_old, (time.perf_counter() - t) * 1000)
        rows.append({
            "n": n, "retired_first_round": r1["retired"],
            "first_round_ms": round(first, 1),
            "steady_windowed_ms": round(best_new, 1),
            "steady_unwindowed_ms": round(best_old, 1),
            "db_kb": round(db.stat().st_size / 1024, 1),
            "events": st.count(),
            "json_kb": round(out.stat().st_size / 1024, 1),
        })
        st.close()
print(json.dumps(rows, ensure_ascii=False, indent=2))
