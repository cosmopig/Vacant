"""twin/loadtest_twin — 缺口 C：展期同時十幾個人投卡，SQLite append-only 撐不撐得住。

## 這支在架構裡承重什麼

`DECISION_20260920_TWIN_STORE_APPEND_ONLY.md` 第七節自己承認：

    「沒有量『展場實際併發』。所有數字都是 2-3 張卡的量級……不要當成量過。」

這一支就是去量那一段。**只讀 `twinstore.py`／`twinlink.py`，不改它們**——找到的問題
用重現腳本記錄，需要改動就另外產一份 `.patch`（見下方「發現」一節），不直接動那兩支
（另一個代理正在改那一區）。

## 量了什麼、用什麼手法量（先講方法論，免得結果被誤讀）

1. **併發寫入（N=5/20/50）**：每個 worker 各開自己的 `TwinStore` 連線（不共用連線），
   用 `threading.Barrier` 讓它們盡量同時起跑，對同一顆 SQLite 檔案呼叫 `append()`。
   這在 OS 鎖的層級上跟「N 個獨立行程」是同一件事——SQLite 的鎖是檔案層級的
   advisory lock，不分是誰的行程或執行緒。為了不只靠這個論證，N=5 另外**再跑一次
   跨行程版**（真的 `subprocess` 起 N 個 python 行程），交叉核對執行緒版沒有失真。
2. **鏈的完整性**：併發跑完之後開一個全新連線 `verify()`，並且**先證明 `verify()`
   真的抓得到壞掉的鏈**（把 `twinstore.py` 自己那招——拔 trigger、直改一列——搬過來
   當本檔案的負控制），才敢採信後面「verify 綠」的意義。
3. **generate 的排隊行為**：這裡有兩個各自獨立、都要交代的量法：
   a. **結構量測（不打 1003）**：起一個本機 stub HTTP server，模擬
      `/chat/completions` 固定延遲 `T` 秒回話，跑 `generate(store, endpoint=stub, limit=0)`
      量 N 筆時的總牆鐘時間。`twinlink.generate()` 本體是 `for sid in todo:` 的
      **單執行緒序列迴圈**（讀 `twinlink.py` 第 382-401 行可確認），跟 1003 那顆
      LM Studio 能不能同時吃 4 串完全無關——**因為呼叫端從來沒有並發送出去過**。
      這個 stub 測試把這件事量出來：N 筆的總時間 ≈ N × T，不是 N/4 × T。
   b. **race 量測（也不打 1003，逼 endpoint 連不上讓它退到 fallback）**：
      同一顆 store、同一批待生成的 sub_id，起多個並發 `generate()` 呼叫（模擬「Mac 的
      loop 跟 1003 自己的 loop 同時對同一顆 store 跑」，`e2e_1003.sh` 那個場景的併發版），
      看 `pending()` 選出來的名單會不會重疊——會的話同一位觀眾會被生成兩次，
      這是真的資源浪費，跟鎖不鎖得住是兩件事。
   c. **極小 N 真模型**（預設關閉，`--hit-1003-n`，硬上限 3）：只用來對照一下
      stub 量出來的結構性結論跟真實延遲量級對不對得上，**不是拿來量併發**。
4. **磁碟**：從併發測試留下的庫直接量檔案大小（含 `-wal`／`-shm`，以及
   `wal_checkpoint(TRUNCATE)` 之後的穩態大小兩種都報），算出 bytes/event，
   套幾個**標明是假設、不是量到**的展期情境去外推。

## 先證明打得動（鐵律：判成「0」之前先證明量得動）

每一段測試前都有一個「N=1 基準」：先確認 `append()` 真的讓 `count()` +1，
再去談併發。`verify()` 綠燈也先跑過負控制證明它抓得到壞鏈，才採信。

## 使用

    python3 ops/exhibit/twin/loadtest_twin.py                       # 全套，預設關真模型
    python3 ops/exhibit/twin/loadtest_twin.py --levels 5,20,50
    python3 ops/exhibit/twin/loadtest_twin.py --hit-1003-n 2 \\
        --endpoint http://100.119.113.56:1234/v1                    # 加測極小 N 真模型
    python3 ops/exhibit/twin/loadtest_twin.py --out evidence.json

隱藏子指令（跨行程交叉核對用，父行程用 subprocess 呼叫自己）：
    python3 ops/exhibit/twin/loadtest_twin.py _worker_append --db PATH --sub-id S --payload '{}' --source X
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
sys.path.insert(0, str(TWIN.parents[2]))

from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_ERROR, KIND_GENERATED, KIND_NOTE, KIND_PUBLISHED, KIND_SUBMITTED,
    TwinStore,
)
from ops.exhibit.twin import twinlink  # noqa: E402

FAILS: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> bool:
    print(("  [OK] " if cond else "  [紅] ") + name + (f" — {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)
    return cond


def _p(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _sample_card(i: int) -> dict[str, Any]:
    return {
        "need": f"loadtest 第 {i} 件小事",
        "shape": "圓潤", "texture": "光滑", "color": "暖土",
        "vibe": "測試用、不是真觀眾", "first_line": None,
    }


# ---------------------------------------------------------------------------
# 0. 先證明打得動
# ---------------------------------------------------------------------------

def prove_writer_works(db: pathlib.Path) -> dict[str, Any]:
    print("\n=== 0. 先證明壓測打得動（N=1 基準） ===")
    st = TwinStore(db)
    before = st.count()
    st.append(KIND_NOTE, "_baseline", {"v": 1}, source="loadtest")
    after = st.count()
    st.close()
    ok = chk("append 一列，count 真的 +1", after == before + 1,
             f"before={before} after={after}")
    return {"ok": ok, "before": before, "after": after}


def prove_verify_catches_corruption(tmpdir: pathlib.Path) -> dict[str, Any]:
    """在斷言任何一次併發測試的 `verify().ok is True` 有意義之前，
    先證明 `verify()` 真的抓得到壞掉的鏈——不然「綠燈」可能只是量具沒在看。
    負控制手法照抄 `twinstore.py::selftest`：拔 trigger、直改一列。"""
    print("\n=== 0b. 負控制：verify() 抓不抓得到壞鏈（証明檢查本身沒有睡著）===")
    db = tmpdir / "negctrl.sqlite3"
    st = TwinStore(db)
    for i in range(3):
        st.append(KIND_NOTE, "x", {"i": i}, source="negctrl")
    clean_ok = chk("乾淨的鏈：verify().ok", st.verify()["ok"] is True)
    st.close()

    raw = sqlite3.connect(str(db))
    raw.isolation_level = None
    raw.execute("PRAGMA writable_schema=ON")
    raw.execute("DELETE FROM sqlite_master WHERE type='trigger'")
    raw.execute("PRAGMA writable_schema=OFF")
    raw.close()
    # ⚠ 一定要關掉重開：SQLite 把 trigger 定義快取在連線裡，同一條連線繼續用
    # 還是會被剛剛「已經從 sqlite_master 刪掉」的 trigger 擋下來（實測踩到過
    # 一次——照抄 twinstore.py::selftest 的寫法：兩段各自開一條新連線）。
    raw = sqlite3.connect(str(db))
    raw.isolation_level = None
    raw.execute("UPDATE twin_event SET payload_json='{\"tampered\":true}' WHERE seq=2")
    raw.close()

    st2 = TwinStore(db)
    v = st2.verify()
    st2.close()
    corrupt_ok = chk("竄改後：verify().ok 變 False", v["ok"] is False, v.get("reason", ""))
    at_ok = chk("broken_at 指到第 2 列（不是 0、不是別的）", v.get("broken_at") == 2,
                repr(v.get("broken_at")))
    return {"clean_ok": clean_ok, "corrupt_detected": corrupt_ok,
            "broken_at_correct": at_ok, "verify_after_corruption": v}


def prove_lock_contention_is_detectable(tmpdir: pathlib.Path, n: int = 8) -> dict[str, Any]:
    """在採信「N=5/20/50 併發下 0 個 database is locked」之前，先證明這個偵測器
    真的抓得到鎖衝突——不然「0 個」可能只是我們沒在看，不是真的沒有鎖衝突。

    手法：開一條**不經過 `TwinStore`**的原生連線（`TwinStore` 把 busy timeout
    寫死 30 秒，故意繞過它），`timeout=0.0` 幾乎不給重試機會，並且 `BEGIN IMMEDIATE`
    後刻意睡一下撐住鎖，逼其他 worker 真的撞上。這不是在測 `twinstore.py`
    本身的行為（正常路徑一律走 30 秒 timeout），是在測**這一支量測腳本抓不抓得到**
    這類錯誤——確保後面「0 個 locked」是量到的事實，不是偵測器沒在看。"""
    print("\n=== 0c. 負控制：故意用極短 busy timeout 逼出 'database is locked' ===")
    db = tmpdir / "lockneg.sqlite3"
    st = TwinStore(db)  # 借正常路徑把 schema／WAL 模式建好
    st.close()

    barrier = threading.Barrier(n)
    errors: list[str] = []
    lock = threading.Lock()

    def hammer(i: int) -> None:
        barrier.wait()
        conn = sqlite3.connect(str(db), timeout=0.0)
        conn.isolation_level = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            time.sleep(0.05)  # 撐住鎖，逼其他人真的撞上而不是僥倖交錯過去
            conn.execute(
                "INSERT INTO twin_event(seq, ts_unix_ms, ts_utc, sub_id, kind, source,"
                " payload_json, payload_sha256, prev_sha256, row_sha256) VALUES"
                " (?,?,?,?,?,?,?,?,?,?)",
                (100000 + i, 0, "1970-01-01T00:00:00+00:00", f"negctrl-{i}", KIND_NOTE,
                 "negctrl", "{}", "x", "x", f"dummy-{i}"))
            conn.execute("COMMIT")
        except Exception as e:  # noqa: BLE001
            with lock:
                errors.append(f"{type(e).__name__}: {e}")
            try:
                conn.execute("ROLLBACK")
            except Exception:  # noqa: BLE001
                pass
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=n) as ex:
        list(ex.map(hammer, range(n)))

    locked = [e for e in errors if "locked" in e.lower()]
    chk("極短 timeout 下確實撞出至少一個 'database is locked'（證明偵測器沒瞎）",
        len(locked) >= 1, f"errors={errors}")
    return {"n": n, "errors": errors, "locked_count": len(locked),
            "note": "這是繞過 TwinStore、刻意用 timeout=0 的負控制，"
                    "不代表 twinstore.py 正常路徑會這樣"}


# ---------------------------------------------------------------------------
# 1+2. 併發寫入 ＋ 鏈完整性
# ---------------------------------------------------------------------------

def _thread_worker(db: pathlib.Path, sub_id: str, i: int,
                   barrier: threading.Barrier) -> dict[str, Any]:
    barrier.wait()  # 盡量同一瞬間起跑，才是在打「同時投」不是在打「陸續投」
    t0 = time.perf_counter()
    try:
        st = TwinStore(db)
        row = st.append(KIND_SUBMITTED, sub_id,
                        {"card": _sample_card(i), "cloud_status": "queued"},
                        source="loadtest:thread")
        st.close()
        return {"ok": True, "sub_id": sub_id, "seq": row["seq"],
                "elapsed_s": time.perf_counter() - t0}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "sub_id": sub_id, "error": f"{type(e).__name__}: {e}",
                "elapsed_s": time.perf_counter() - t0}


def concurrent_writers_thread(db: pathlib.Path, n: int, tag: str) -> dict[str, Any]:
    print(f"\n=== 1. 併發寫入（thread，N={n}，{tag}） ===")
    st = TwinStore(db)
    before = st.count()
    st.close()

    barrier = threading.Barrier(n)
    t0 = time.perf_counter()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_thread_worker, db, f"{tag}-t{i}", i, barrier)
                for i in range(n)]
        for f in as_completed(futs):
            results.append(f.result())
    wall_s = time.perf_counter() - t0

    ok_results = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    locked = [r for r in failed if "locked" in r.get("error", "").lower()]

    st = TwinStore(db)
    after = st.count()
    v = st.verify()
    seqs = [e["seq"] for e in st.events()]
    st.close()

    chk(f"N={n}：{n} 個 worker 全部沒有例外", len(failed) == 0,
        f"失敗 {len(failed)} 個，其中 'database is locked' {len(locked)} 個："
        f"{[r['error'] for r in failed[:5]]}")
    chk(f"N={n}：count 增加量＝成功寫入數（before={before}）",
        after - before == len(ok_results),
        f"before={before} after={after} ok_writes={len(ok_results)}")
    chk(f"N={n}：seq 連號無重複無跳號", seqs == list(range(1, len(seqs) + 1)),
        f"len={len(seqs)} 前 5 個={seqs[:5]} 後 5 個={seqs[-5:]}")
    chk(f"N={n}：verify() 仍然綠（鏈沒斷）", v["ok"] is True, v.get("reason", ""))

    lat = [r["elapsed_s"] for r in ok_results]
    return {
        "n": n, "mode": "thread", "wall_s": round(wall_s, 4),
        "ok": len(ok_results), "failed": len(failed),
        "database_is_locked_count": len(locked),
        "errors_sample": [r["error"] for r in failed[:10]],
        "latency_s": {
            "min": round(min(lat), 4) if lat else None,
            "median": round(statistics.median(lat), 4) if lat else None,
            "max": round(max(lat), 4) if lat else None,
        },
        "count_before": before, "count_after": after,
        "chain_verify": v,
        "seq_continuous_no_dupes": seqs == list(range(1, len(seqs) + 1)),
    }


def concurrent_writers_process(db: pathlib.Path, n: int, tag: str) -> dict[str, Any]:
    """跨行程交叉核對（預設只在 N=5 跑一次，subprocess 開銷不小）。
    每個 worker 是獨立 python 行程呼叫本檔的隱藏子指令 `_worker_append`。"""
    print(f"\n=== 1b. 併發寫入（process 交叉核對，N={n}，{tag}） ===")
    st = TwinStore(db)
    before = st.count()
    st.close()

    def launch(i: int) -> subprocess.Popen:
        payload = json.dumps({"card": _sample_card(i)}, ensure_ascii=False)
        return subprocess.Popen(
            [sys.executable, str(HERE), "_worker_append",
             "--db", str(db), "--sub-id", f"{tag}-p{i}",
             "--kind", KIND_SUBMITTED, "--payload", payload,
             "--source", "loadtest:process"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    t0 = time.perf_counter()
    procs = [launch(i) for i in range(n)]  # 盡量背靠背起跑；行程啟動本身就有抖動，見報告註記
    outs = [(p, *p.communicate()) for p in procs]
    wall_s = time.perf_counter() - t0

    failed = []
    for p, out, err in outs:
        if p.returncode != 0:
            failed.append({"returncode": p.returncode, "stdout": out.strip(),
                           "stderr": err.strip()[:300]})
    ok_count = n - len(failed)

    st = TwinStore(db)
    after = st.count()
    v = st.verify()
    st.close()

    chk(f"process N={n}：全部行程 returncode==0", len(failed) == 0,
        f"失敗 {len(failed)} 個：{[f['stderr'][:120] for f in failed[:3]]}")
    chk(f"process N={n}：count 增加量＝成功數", after - before == ok_count,
        f"before={before} after={after} ok={ok_count}")
    chk(f"process N={n}：verify() 仍然綠", v["ok"] is True, v.get("reason", ""))

    return {"n": n, "mode": "process", "wall_s": round(wall_s, 4),
            "ok": ok_count, "failed": len(failed),
            "errors_sample": failed[:5],
            "count_before": before, "count_after": after, "chain_verify": v}


# ---------------------------------------------------------------------------
# 3a. generate 的排隊行為——結構量測（本機 stub，不打 1003）
# ---------------------------------------------------------------------------

def _make_stub_server(delay_s: float, garble: bool = False):
    """回一個假的 `/chat/completions`，睡 `delay_s` 秒再回合法（或故意亂碼）JSON。
    只為了量 `generate()` 呼叫端的排隊行為，跟真模型的內容無關。"""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    call_log: list[float] = []
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            t_recv = time.perf_counter()
            with lock:
                call_log.append(t_recv)
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            time.sleep(delay_s)
            if garble:
                content = "這不是合法 json 也沒有大括號"
            else:
                content = json.dumps({
                    "arrival": "stub 到了", "working": "stub 在做事",
                    "handover": "stub 交件了",
                })
            body = json.dumps({
                "choices": [{"message": {"content": content}}],
                "usage": {"completion_tokens": 10,
                          "completion_tokens_details": {"reasoning_tokens": 0}},
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # noqa: D102, ANN002
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port, call_log


def generate_serial_structure_test(tmpdir: pathlib.Path, n_values: list[int],
                                   delay_s: float = 1.5) -> dict[str, Any]:
    """量 `twinlink.generate()` 是不是把 N 筆待生成的卡並發送出去。

    方法：本機 stub 固定延遲 `delay_s`，餵 N 筆待生成的卡進 `generate()` 一次呼叫，
    量總牆鐘時間。若呼叫端有利用到「1003 最多 4 串」的餘裕，N 筆的總時間應該
    明顯小於 N × delay_s（例如接近 ceil(N/4) × delay_s）；若是嚴格序列，
    會等於 N × delay_s（±HTTP 開銷）。"""
    print(f"\n=== 3a. generate 排隊行為（結構量測，stub 延遲={delay_s}s，不打 1003） ===")
    srv, port, call_log = _make_stub_server(delay_s)
    endpoint = f"http://127.0.0.1:{port}/v1"
    out = {"delay_s": delay_s, "runs": []}
    try:
        for n in n_values:
            db = tmpdir / f"genstruct_{n}.sqlite3"
            st = TwinStore(db)
            for i in range(n):
                st.append(KIND_SUBMITTED, f"gs-{n}-{i}", {"card": _sample_card(i)},
                          source="loadtest")
            call_log.clear()
            t0 = time.perf_counter()
            r = twinlink.generate(st, endpoint=endpoint, model="stub", limit=0,
                                  timeout=30.0, allow_fallback=True)
            wall_s = time.perf_counter() - t0
            st.close()

            expect_serial = n * delay_s
            # 併發上限抓 1003 講的 4 串當對照基準，只是拿來算「假如有並發會是多快」，
            # 這支呼叫端本身沒有做並發（見下面斷言）。
            expect_if_4way = (n / 4) * delay_s + delay_s  # 粗估，含尾批
            is_serial = wall_s >= expect_serial * 0.85  # 留 15% HTTP/排程抖動

            chk(f"N={n}：generate() 是嚴格序列（總時間≈N×delay，不是 N/4×delay）",
                is_serial,
                f"實得 {wall_s:.2f}s；N×delay={expect_serial:.2f}s；"
                f"若有 4 串並發理論值≈{expect_if_4way:.2f}s")
            chk(f"N={n}：{n} 筆全部處理完、沒有卡住", r["generated"] == n,
                f"generated={r['generated']} remaining={r['remaining']}")

            out["runs"].append({
                "n": n, "wall_s": round(wall_s, 3),
                "expect_serial_s": round(expect_serial, 3),
                "expect_if_4way_s": round(expect_if_4way, 3),
                "is_serial": is_serial,
                "generate_result": r,
                "stub_calls_received": len(call_log),
            })
    finally:
        srv.shutdown()
    return out


def generate_fallback_trigger_test(tmpdir: pathlib.Path) -> dict[str, Any]:
    """stub 回亂碼（模擬「答案被 thinking 擠掉」或格式錯）時，
    `generate()` 的 `degraded` 計數會不會跟著動——這是展場螢幕判斷
    `fallback_deterministic` 有沒有被觸發唯一能看的欄位。"""
    print("\n=== 3a-2. fallback_deterministic 觸發計數（stub 回亂碼）===")
    srv, port, _ = _make_stub_server(delay_s=0.05, garble=True)
    endpoint = f"http://127.0.0.1:{port}/v1"
    db = tmpdir / "gen_garble.sqlite3"
    st = TwinStore(db)
    n = 5
    for i in range(n):
        st.append(KIND_SUBMITTED, f"garble-{i}", {"card": _sample_card(i)}, source="loadtest")
    try:
        r = twinlink.generate(st, endpoint=endpoint, model="stub", limit=0,
                              timeout=10.0, allow_fallback=True)
    finally:
        srv.shutdown()
    engines = [c["twin"]["engine"] for c in st.roster() if c.get("twin")]
    st.close()
    chk("亂碼觸發全部退化為 fallback_deterministic", r["degraded"] == n,
        f"degraded={r['degraded']}/{n}")
    chk("roster 上的 engine 欄位也確實標成 fallback_deterministic",
        all(e == "fallback_deterministic" for e in engines), str(engines))
    return {"generate_result": r, "engines": engines}


# ---------------------------------------------------------------------------
# 3b. generate 的排隊行為——race 量測（多個 generate() 併發打同一顆 store）
# ---------------------------------------------------------------------------

def generate_race_test(tmpdir: pathlib.Path, n_pending: int = 20,
                       n_concurrent_loops: int = 3) -> dict[str, Any]:
    """模擬「Mac 的 loop 跟 1003 自己的 loop 同時對同一顆 store 跑 generate」
    （`e2e_1003.sh` 那個場景的併發版）。endpoint 故意打不通，逼全部走 fallback，
    這樣才能只看 `pending()` 選片會不會重疊，不用等真模型也不用打 1003。"""
    print(f"\n=== 3b. generate race（{n_concurrent_loops} 個併發 generate() 打同一顆 store）===")
    db = tmpdir / "gen_race.sqlite3"
    st = TwinStore(db)
    for i in range(n_pending):
        st.append(KIND_SUBMITTED, f"race-{i}", {"card": _sample_card(i)}, source="loadtest")
    st.close()

    barrier = threading.Barrier(n_concurrent_loops)

    def loop_worker(_: int) -> dict[str, Any]:
        barrier.wait()
        s = TwinStore(db)
        r = twinlink.generate(s, endpoint="http://127.0.0.1:1/v1", model="nope",
                              limit=0, timeout=2.0, allow_fallback=True)
        s.close()
        return r

    with ThreadPoolExecutor(max_workers=n_concurrent_loops) as ex:
        results = [f.result() for f in
                  [ex.submit(loop_worker, i) for i in range(n_concurrent_loops)]]

    st = TwinStore(db)
    per_sub_generated_count = {
        sid: st.count(KIND_GENERATED) and len(list(st.events(sub_id=sid, kind=KIND_GENERATED)))
        for sid in st.sub_ids()
    }
    st.close()

    dupes = {sid: c for sid, c in per_sub_generated_count.items() if c > 1}
    total_generated_events = sum(per_sub_generated_count.values())

    # 這裡**不是**負控制式的 chk(紅/綠)——重複生成是真的觀察結果，記錄下來，
    # 不預設「不該發生」就強行判紅（`pending()` 本來就沒有互斥鎖，這支只負責量出來）。
    print(f"  [量到] {n_pending} 個待生成、{n_concurrent_loops} 個併發 generate()："
          f"共產生 {total_generated_events} 個 GENERATED 事件，"
          f"其中 {len(dupes)} 位觀眾被生成超過一次：{dict(list(dupes.items())[:5])}")
    chk("每位觀眾至少被生成一次（沒有人被漏掉）",
        all(c >= 1 for c in per_sub_generated_count.values()),
        f"={per_sub_generated_count}")
    chk("鏈本身仍然完整（race 造成的是重複事件，不是壞鏈）",
        TwinStore(db).verify()["ok"] is True)

    return {
        "n_pending": n_pending, "n_concurrent_loops": n_concurrent_loops,
        "per_generate_call": results,
        "total_generated_events": total_generated_events,
        "expected_if_no_race": n_pending,
        "duplicated_subjects": dupes,
        "duplicate_rate": round(len(dupes) / n_pending, 3) if n_pending else None,
    }


# ---------------------------------------------------------------------------
# 3c. 極小 N 真模型（預設關閉，硬上限 3）
# ---------------------------------------------------------------------------

def hit_1003_small_n(tmpdir: pathlib.Path, n: int, endpoint: str, model: str) -> dict[str, Any]:
    assert n <= 3, "硬上限：這一段最多 3 發，不准拿 1003 的機時做大量 generate"
    print(f"\n=== 3c. 極小 N 真模型對照（N={n}，endpoint={endpoint}，只是對照量級，不是併發量測）===")
    db = tmpdir / "hit1003.sqlite3"
    st = TwinStore(db)
    for i in range(n):
        st.append(KIND_SUBMITTED, f"real-{i}", {"card": _sample_card(i)}, source="loadtest")
    t0 = time.perf_counter()
    r = twinlink.generate(st, endpoint=endpoint, model=model, limit=0,
                          timeout=twinlink.DEFAULT_GEN_TIMEOUT, allow_fallback=True)
    wall_s = time.perf_counter() - t0
    engines = [c["twin"]["engine"] for c in st.roster() if c.get("twin")]
    latencies = [c["twin"].get("latency_ms") for c in st.roster() if c.get("twin")]
    st.close()
    chk(f"真模型 N={n}：全部有結果（真跑或退化都算，不能卡住）", r["generated"] == n)
    return {"n": n, "wall_s": round(wall_s, 2), "generate_result": r,
            "engines": engines, "latency_ms_per_card": latencies,
            "note": "這是對照量級用的極小樣本，不是併發量測；不要拿來講排隊時間"}


# ---------------------------------------------------------------------------
# 4. 磁碟
# ---------------------------------------------------------------------------

def disk_usage_test(tmpdir: pathlib.Path, n_visitors: int = 50) -> dict[str, Any]:
    print(f"\n=== 4. 磁碟（{n_visitors} 位觀眾，submitted+generated(fallback)+published(模擬) 全生命週期）===")
    db = tmpdir / "disk.sqlite3"
    st = TwinStore(db)

    def size_now() -> dict[str, int]:
        d = {"main": db.stat().st_size if db.exists() else 0}
        for suf in ("-wal", "-shm"):
            p = pathlib.Path(str(db) + suf)
            d[suf.lstrip("-")] = p.stat().st_size if p.exists() else 0
        d["total_live"] = sum(d.values())
        return d

    size_0 = size_now()
    for i in range(n_visitors):
        st.append(KIND_SUBMITTED, f"disk-{i}", {"card": _sample_card(i)}, source="loadtest")
    size_after_submit = size_now()

    fb_engine_count = 0
    for sid in st.sub_ids():
        cur = st.current(sid) or {}
        twin = twinlink.fallback_twin(cur.get("card"))
        st.append(KIND_GENERATED, sid, twin, source="local:fallback")
        fb_engine_count += 1
    size_after_generate = size_now()

    for sid in st.sub_ids():
        st.append(KIND_PUBLISHED, sid,
                 {"cloud": "https://vacant-world.cosmopig.com", "http": 200,
                  "at": "2026-09-20T00:00:00+00:00"},
                 source="cloud:https://vacant-world.cosmopig.com")
    size_after_publish = size_now()

    total_events = st.count()
    st.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    size_checkpointed = size_now()
    st.close()

    bytes_per_event_live = (size_after_publish["total_live"] - size_0["total_live"]) / total_events
    bytes_per_event_checkpointed = size_checkpointed["main"] / total_events

    chk(f"{n_visitors} 位觀眾 × 3 事件 = {n_visitors*3} 筆，實際筆數相符",
        total_events == n_visitors * 3, f"total_events={total_events}")

    # 外推——這是**假設**不是量到，標清楚每一個係數
    scenarios = []
    for label, visitors_per_day in (("保守：50 人/天", 50),
                                     ("中：150 人/天", 150),
                                     ("展場硬約束說的『十幾個人同時』乘整天：300 人/天", 300)):
        events_7d = visitors_per_day * 7 * 3  # 每人 3 事件（submitted/generated/published）
        est_bytes = events_7d * bytes_per_event_checkpointed
        scenarios.append({
            "assumption": label, "visitors_per_day": visitors_per_day,
            "days": 7, "events_est": events_7d,
            "bytes_est": int(est_bytes),
            "mb_est": round(est_bytes / 1e6, 2),
        })

    return {
        "n_visitors": n_visitors, "total_events": total_events,
        "size_bytes": {
            "empty_db": size_0, "after_submit": size_after_submit,
            "after_generate_fallback": size_after_generate,
            "after_publish": size_after_publish,
            "after_wal_checkpoint_truncate": size_checkpointed,
        },
        "bytes_per_event": {
            "live_incl_wal_shm": round(bytes_per_event_live, 1),
            "checkpointed_main_file_only": round(bytes_per_event_checkpointed, 1),
        },
        "seven_day_projection_ASSUMPTIONS_NOT_MEASURED": scenarios,
    }


# ---------------------------------------------------------------------------
# 隱藏子指令：跨行程 worker
# ---------------------------------------------------------------------------

def _worker_append_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--sub-id", required=True)
    ap.add_argument("--kind", default=KIND_SUBMITTED)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--source", default="loadtest:process")
    a = ap.parse_args(argv)
    try:
        st = TwinStore(a.db)
        row = st.append(a.kind, a.sub_id, json.loads(a.payload), source=a.source)
        st.close()
        print(json.dumps({"ok": True, "seq": row["seq"]}))
        return 0
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1


# ---------------------------------------------------------------------------
# CLI / 主流程
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if argv and argv[0] == "_worker_append":
        return _worker_append_main(argv[1:])

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--levels", default="5,20,50",
                    help="併發寫入要測的 N 清單，逗號分隔")
    ap.add_argument("--process-crosscheck-n", type=int, default=5,
                    help="跨行程交叉核對用的 N（subprocess 開銷大，預設只測一個小值）")
    ap.add_argument("--stub-delay", type=float, default=1.5,
                    help="generate 排隊結構量測用的 stub 延遲（秒）")
    ap.add_argument("--race-pending", type=int, default=20)
    ap.add_argument("--race-loops", type=int, default=3)
    ap.add_argument("--disk-visitors", type=int, default=50)
    ap.add_argument("--hit-1003-n", type=int, default=0,
                    help="打真模型的張數，硬上限 3，預設 0＝不打（不要用 1003 機時做大量 generate）")
    ap.add_argument("--endpoint", default=twinlink.DEFAULT_ENDPOINT)
    ap.add_argument("--model", default=twinlink.DEFAULT_MODEL)
    ap.add_argument("--out", default=None, help="把整份報告寫成 JSON 到這個路徑")
    ap.add_argument("--keep-tmpdir", action="store_true",
                    help="測試完不要刪暫存目錄（除錯用）")
    a = ap.parse_args(argv)

    if a.hit_1003_n > 3:
        print(f"拒絕：--hit-1003-n={a.hit_1003_n} 超過硬上限 3", file=sys.stderr)
        return 2

    levels = [int(x) for x in a.levels.split(",") if x.strip()]

    tmp_ctx = tempfile.TemporaryDirectory(prefix="twin_loadtest_")
    tmpdir = pathlib.Path(tmp_ctx.name)
    print(f"暫存目錄：{tmpdir}（不是 ops/exhibit/twin/store/，跟正式真相來源完全分開）")

    report: dict[str, Any] = {
        "generated_at": twinlink._now(), "tmpdir": str(tmpdir),
        "levels": levels, "sections": {},
    }

    try:
        db_writers = tmpdir / "concurrency.sqlite3"
        report["sections"]["baseline"] = prove_writer_works(db_writers)
        report["sections"]["verify_negative_control"] = prove_verify_catches_corruption(tmpdir)
        report["sections"]["lock_detection_negative_control"] = (
            prove_lock_contention_is_detectable(tmpdir))

        concurrency_runs = []
        for n in levels:
            concurrency_runs.append(concurrent_writers_thread(db_writers, n, tag=f"n{n}"))
        report["sections"]["concurrent_writers_thread"] = concurrency_runs

        db_proc = tmpdir / "concurrency_process.sqlite3"
        report["sections"]["concurrent_writers_process_crosscheck"] = (
            concurrent_writers_process(db_proc, a.process_crosscheck_n, tag="px"))

        report["sections"]["generate_serial_structure"] = generate_serial_structure_test(
            tmpdir, [n for n in levels if n <= 20] or [5], delay_s=a.stub_delay)
        report["sections"]["generate_fallback_trigger"] = generate_fallback_trigger_test(tmpdir)
        report["sections"]["generate_race"] = generate_race_test(
            tmpdir, n_pending=a.race_pending, n_concurrent_loops=a.race_loops)

        if a.hit_1003_n > 0:
            report["sections"]["real_model_small_n"] = hit_1003_small_n(
                tmpdir, a.hit_1003_n, a.endpoint, a.model)
        else:
            report["sections"]["real_model_small_n"] = {
                "skipped": True, "reason": "--hit-1003-n 未指定（預設 0），沒有打 1003"}

        report["sections"]["disk_usage"] = disk_usage_test(tmpdir, a.disk_visitors)

    finally:
        if a.keep_tmpdir:
            print(f"\n（保留暫存目錄：{tmpdir}）")
        else:
            tmp_ctx.cleanup()

    report["fails"] = FAILS
    report["all_green"] = len(FAILS) == 0

    print("\n" + "=" * 70)
    if FAILS:
        print(f"紅：{len(FAILS)} 項 → {FAILS}")
    else:
        print("全部檢查綠（負控制與正控制都有跑過）")

    if a.out:
        pathlib.Path(a.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"報告寫到 {a.out}")
    else:
        print("\n=== 完整報告 JSON ===")
        _p(report)

    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
