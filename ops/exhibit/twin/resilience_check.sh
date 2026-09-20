#!/usr/bin/env bash
# resilience_check.sh — 「展場沒有解說員」那條硬約束的失效演練。
#
# ## 這支在架構裡承重什麼
#
# `CLAUDE.md` 展場硬約束 2：**離線可跑、可無人值守循環**。`twinlink loop` 是那個
# 無人值守循環，但在這支之前它的**失效行為從來沒有被系統性演練過**——
# `e2e_twinchain.sh` 量的是「一切正常時整條鏈會不會通」，那是另一件事。
# 展場一天一開機、沒有人守著，會出事的不是快樂路徑。
#
# 八項演練（每一項都有負控制）：
#   1 公網斷      2 1003 斷      3 兩個都斷     4 kill -9 後重啟（最重要）
#   5 磁碟寫滿    6 畸形卡       7 時鐘倒退     8 同一張卡重複投遞
#
# ## 紀律（違反就不要看結果）
#
# * **每一個綠燈都要有負控制。** 故意弄壞一個東西，證明檢查會紅。
#   沒有負控制的綠燈不算數——這支自己的量具（`run` 取不取得到退出碼、
#   `http_code=000` 是不是真的代表斷了）也一樣要先自證。
# * **不吞 stderr、不吞退出碼。** 一律先重導向落盤再取 `$?`；
#   `cmd | tee f` 之後的 `$?` 是 tee 的，`cmd | grep x || echo 沒問題` 會說謊。
# * **「沒量到」寫 `null`，不准寫 0 或 False。** 演練不成立時（例如這台機器
#   做不出 ramdisk）要說「沒量到」，不准把沒量到說成「沒問題」。
# * **只殺自己起的行程。** 每一個背景行程的 PID 都是這支自己 `$!` 拿到的，
#   殺之前先 `ps -o command=` 確認那個 PID 真的是自己起的那一支。
#   ⚠ `( cd X && cmd & echo $! )` 拿到的是 subshell 的 PID 不是 cmd 的——
#   `e2e_twinchain.sh` 的註解記著那次教訓（斷網演練變成假的），這裡不重蹈。
# * **斷網要輪詢確認 `http_code=000` 才敢宣稱斷了。** 殺了 PID 不等於埠關了。
#
# ## 這支量的是什麼、不是什麼（誠實邊界）
#
# 1. **雲端是替身不是 `server.js`。** 演練需要餵進真伺服器產不出來的畸形回應
#    （`/api/all` 是 twinlink 眼中的外部輸入），所以第 6 節用替身。
#    「觀眾能不能真的送出那種卡」是另一個問題，第 6b 節用**真的 `server.js`**
#    在本機另一個埠上單獨量，量不到就寫 `null`。
# 2. **模型也是替身。** 這支不打 1003、不花機時：要量的是「模型不回話時
#    loop 會怎樣」，那用一個秒回的替身比用真模型精確（真模型還會逾時、
#    會被思考擠掉，那些是 `e2e_1003.sh` 的事）。
# 3. **「時鐘倒退」沒有真的動系統時鐘**（那會影響整台機器）。量的是
#    「事件流裡的時間戳倒退時，摺疊與驗鏈會不會出錯」——用 `append(ts_unix_ms=...)`
#    把 NTP 校正後會長出來的那種事件流直接造出來。系統呼叫層的時鐘跳躍沒量到。
# 4. **磁碟寫滿用自己造的 2–6MB ramdisk**，絕不塞爆任何一台機器的真磁碟。
#    做不出 ramdisk 就記 `null`。
#
# 用法：
#   bash ops/exhibit/twin/resilience_check.sh              # 全部，約 1–2 分鐘
#   OUT=/tmp/xx bash ops/exhibit/twin/resilience_check.sh  # 換證據目錄
#   SKIP_DISK=1 bash ops/exhibit/twin/resilience_check.sh  # 跳過 ramdisk 那一節
#   # Linux 展場機（沒有 hdiutil）：自己掛一個小 tmpfs 再把路徑交給它。
#   # 大於 128MB 的檔案系統會被**拒絕**——這一節會塞到一個 byte 都不剩。
#   sudo mount -t tmpfs -o size=6m tmpfs /mnt/twinfull && sudo chown "$USER" /mnt/twinfull
#   FULL_DIR=/mnt/twinfull bash ops/exhibit/twin/resilience_check.sh
# 退出碼：0＝全綠；1＝有紅燈；2＝拒絕啟動（埠被佔等，fail-closed）
set -u

WT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TWINLINK="$WT/ops/exhibit/twin/twinlink.py"
TWINSTORE="$WT/ops/exhibit/twin/twinstore.py"

PY="${PY:-}"
if [ -z "$PY" ]; then
  if [ -x "$WT/.venv/bin/python" ]; then PY="$WT/.venv/bin/python"
  elif [ -x /Users/cosmopig/Documents/GitHub/Vacant/.venv/bin/python ]; then
    PY=/Users/cosmopig/Documents/GitHub/Vacant/.venv/bin/python
  else PY="$(command -v python3)"; fi
fi

OUT="${OUT:-$WT/ops/exhibit/twin/evidence_resilience_20260920}"
CLOUD_PORT="${CLOUD_PORT:-38911}"
MODEL_PORT="${MODEL_PORT:-38912}"
REAL_CLOUD_PORT="${REAL_CLOUD_PORT:-38913}"
TOKEN="${TOKEN:-resilience-local-token}"
CLOUD="http://127.0.0.1:$CLOUD_PORT"
MODEL_EP="http://127.0.0.1:$MODEL_PORT/v1"
MODEL_NAME="fake-1003"
CLOUD_REPO="${CLOUD_REPO:-/Users/cosmopig/Documents/GitHub/vacant-world-cloud}"
SKIP_DISK="${SKIP_DISK:-0}"
RAM_VOL="${RAM_VOL:-VACANTRES}"
RAM_MB="${RAM_MB:-6}"
#: 收尾時把可重建的大檔（各節的 sqlite 庫、畸形卡那些 MB 級 items）刪掉，
#: 但**先把刪掉什麼列成清單**落盤——證據不可以安靜地消失。TRIM=0 全部留著。
TRIM="${TRIM:-1}"

# probe.py 要 import 得到 ops.exhibit.twin.twinstore。用環境變數傳，
# 不要讓它從自己的路徑往上數（證據目錄搬走就會安靜地數錯）。
export VACANT_ROOT="$WT"

# 證據目錄整個重生：舊檔留著時，下面那些「讀檔比較」會讀到上一輪的東西，
# 兩邊就都在說謊（`e2e_twinchain.sh` 實測踩過）。
rm -rf "$OUT"; mkdir -p "$OUT"
H="$OUT/_helpers"; mkdir -p "$H"

PASS=0; FAIL=0; NOTES=0
step() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
ok()   { PASS=$((PASS+1)); echo "  [OK] $*"; echo "OK|$*" >> "$OUT/_verdicts.txt"; }
bad()  { FAIL=$((FAIL+1)); echo "  [紅] $*"; echo "紅|$*" >> "$OUT/_verdicts.txt"; }
note() { NOTES=$((NOTES+1)); echo "  [記] $*"; echo "記|$*" >> "$OUT/_verdicts.txt"; }
chk()  { if [ "$1" = "$2" ]; then ok "$3（得 $1）"; else bad "$3（期望 $2，實得 $1）"; fi; }

# 🔴 不可以寫成 `cmd | tee f` 然後看 `$?`——那是 tee 的退出碼，幾乎永遠 0。
run() { local f="$1"; shift; "$@" > "$OUT/$f" 2>&1; return $?; }
kv()  { grep -m1 "^$2=" "$1" 2>/dev/null | sed "s/^$2=//"; }

http_code() { curl -sS --max-time 4 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null; }
# 「斷了」的判準只有一個：輪詢到 `http_code=000`。殺了 PID 不等於埠關了。
wait_down() { local i=0; while [ $i -lt 40 ]; do
    [ "$(http_code "$1")" = "000" ] && return 0; i=$((i+1)); sleep 0.2; done; return 1; }
wait_up()   { local i=0 c; while [ $i -lt 60 ]; do
    c="$(http_code "$1")"; [ -n "$c" ] && [ "$c" != "000" ] && return 0
    i=$((i+1)); sleep 0.2; done; return 1; }

CLOUD_PID=""; MODEL_PID=""; REALCLOUD_PID=""; RAM_DEV=""
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
# 殺之前先確認那個 PID 真的是自己起的那一支（命令列要對得上），
# 不是「我記得我起過」。PID 會被回收，記錯就會殺到別人的東西。
kill_mine() {  # kill_mine PID 指紋 [訊號]
  local pid="$1" fp="$2" sig="${3:--TERM}"
  [ -n "$pid" ] || return 0
  if ! ps -p "$pid" -o command= 2>/dev/null | grep -q "$fp"; then
    echo "  [記] PID $pid 的命令列對不上指紋「${fp}」，不殺（可能已結束或被回收）"
    return 1
  fi
  kill "$sig" "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; return 0
}
cleanup() {
  kill_mine "$CLOUD_PID" fakecloud.py >/dev/null 2>&1
  kill_mine "$MODEL_PID" fakemodel.py >/dev/null 2>&1
  kill_mine "$REALCLOUD_PID" server.js >/dev/null 2>&1
  if [ -n "$RAM_DEV" ]; then hdiutil detach "$RAM_DEV" >/dev/null 2>&1; fi
}
trap cleanup EXIT

echo "證據目錄：$OUT"
echo "python：$PY"
{ date -u +"UTC %Y-%m-%dT%H:%M:%SZ"; echo "PY=$PY"; "$PY" -V; uname -a; } > "$OUT/00_env.txt" 2>&1
cat "$OUT/00_env.txt"

# ---------------------------------------------------------------------------
# 替身：雲端郵箱與模型。兩支都是這支腳本自己起的，所以殺它們是安全的。
# ---------------------------------------------------------------------------
cat > "$H/fakecloud.py" <<'PYCLOUD'
"""替身雲端郵箱。**不是 server.js**——存在的理由是要餵進真伺服器產不出來的
畸形 `/api/all` 回應（那是 twinlink 眼中的外部輸入）。

用法：fakecloud.py PORT TOKEN ITEMS_JSON
ITEMS_JSON 每次請求重讀，所以演練中途可以換內容。格式：
    {"mode": "ok"|"nonjson"|"http500"|"noitems"|"no_all", "items": [...]}
"""
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[1]); TOKEN = sys.argv[2]; ITEMS = pathlib.Path(sys.argv[3])


def load():
    try:
        d = json.loads(ITEMS.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"mode": "ok", "items": [], "_err": str(e)}
    if isinstance(d, list):
        return {"mode": "ok", "items": d}
    return d


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("cloud %s\n" % (fmt % a))

    def _send(self, code, obj=None, raw=None, ctype="application/json"):
        # ensure_ascii=True（預設）：這樣連 lone surrogate 都送得出去，
        # 跟 Node 的 JSON.stringify 一樣是逃脫成 \\udXXX。
        body = raw if raw is not None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        tok = (q.get("token") or [""])[0]
        cfg = load()
        mode = cfg.get("mode", "ok")
        if u.path not in ("/api/all", "/api/queue"):
            return self._send(404, {"error": "not found"})
        if u.path == "/api/all" and mode == "no_all":
            return self._send(404, {"error": "no /api/all on this build"})
        if tok != TOKEN:
            return self._send(401, {"error": "bad token"})
        if mode == "http500":
            return self._send(500, {"error": "boom"})
        if mode == "nonjson":
            return self._send(200, raw=b"<html>not json</html>", ctype="text/html")
        if mode == "noitems":
            return self._send(200, {"ok": True})
        return self._send(200, {"items": cfg.get("items", [])})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        if self.path != "/api/result":
            return self._send(404, {"error": "not found"})
        return self._send(200, {"ok": True})


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
PYCLOUD

cat > "$H/fakemodel.py" <<'PYMODEL'
"""替身 LM Studio。用法：fakemodel.py PORT [DELAY_MS]

這支不是 1003。要量的是「模型不回話時 loop 會怎樣」，替身比真模型精確：
真模型還會逾時、會被思考擠掉，那些是 e2e_1003.sh 的事。
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]); DELAY = float(sys.argv[2]) / 1000.0 if len(sys.argv) > 2 else 0.0
N = {"calls": 0}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("model %s\n" % (fmt % a))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        if not self.path.endswith("/chat/completions"):
            body = json.dumps({"error": "not found"}).encode()
            self.send_response(404); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if DELAY:
            time.sleep(DELAY)
        N["calls"] += 1
        content = json.dumps({"arrival": "替身：我到了。", "working": "替身：動手了。",
                              "handover": "替身：交給你。"}, ensure_ascii=False)
        body = json.dumps({
            "choices": [{"message": {"content": content, "reasoning_content": ""}}],
            "usage": {"completion_tokens": 40,
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
PYMODEL

cat > "$H/probe.py" <<'PYPROBE'
"""量具。輸出扁平 key=value，讓 bash 拿得到而不用 jq。

三態鐵律：量不到的東西印 `null`，不印 0、不印 False。
"""
import json
import os
import pathlib
import sqlite3
import sys

# repo root 由呼叫端傳進來，不要從 sys.argv[0] 往上數——證據目錄搬到別處
# （`OUT=/tmp/...`）時往上數會數到別的地方，而且會安靜地數錯。
sys.path.insert(0, os.environ["VACANT_ROOT"])
from ops.exhibit.twin.twinstore import TwinStore  # noqa: E402


def counts(db):
    p = pathlib.Path(db)
    if not p.exists():
        print("exists=0"); return 0
    # ⚠ 這裡**不能**用 read_only=True：kill -9 之後主檔旁邊還躺著 `-wal`，
    # `mode=ro` 開檔時做不了 WAL 回復，會直接炸。而「重開時把 WAL 回復回來」
    # 正是第 4 節要量的東西。
    st = TwinStore(p)
    rows = list(st.conn.execute("SELECT seq,sub_id,kind,payload_json FROM twin_event"
                                " ORDER BY seq ASC"))
    kinds, per_sub, engines = {}, {}, {}
    with_reason = 0
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        d = per_sub.setdefault(r["sub_id"], {})
        d[r["kind"]] = d.get(r["kind"], 0) + 1
        if r["kind"] == "generated":
            try:
                pl = json.loads(r["payload_json"]) or {}
            except Exception:  # noqa: BLE001
                pl = {}
            e = pl.get("engine", "unparsable")
            engines[e] = engines.get(e, 0) + 1
            if e == "fallback_deterministic" and pl.get("degrade_reason"):
                with_reason += 1
    v = st.verify()
    print("exists=1")
    print("events=%d" % len(rows))
    for k in ("submitted", "generated", "published", "error", "ingest_gap", "note"):
        print("k_%s=%d" % (k, kinds.get(k, 0)))
    print("subs=%d" % len([s for s, d in per_sub.items() if d.get("submitted")]))
    print("verify_ok=%d" % (1 if v["ok"] else 0))
    print("verify_checked=%d" % v["checked"])
    print("verify_broken_at=%s" % ("null" if v["broken_at"] is None else v["broken_at"]))
    real = sum(n for e, n in engines.items() if str(e).startswith("lmstudio:"))
    fb = engines.get("fallback_deterministic", 0)
    print("engine_real=%d" % real)
    print("engine_fallback=%d" % fb)
    print("engine_other=%d" % (sum(engines.values()) - real - fb))
    print("degraded_with_reason=%d" % with_reason)
    print("store_bytes=%d" % p.stat().st_size)
    mx = 0
    for s, d in per_sub.items():
        if d.get("submitted"):
            mx = max(mx, d.get("generated", 0))
    print("max_generated_per_sub=%d" % mx)
    mxs = max([d.get("submitted", 0) for d in per_sub.values()] or [0])
    print("max_submitted_per_sub=%d" % mxs)
    st.close()
    return 0


def viewfile(path):
    p = pathlib.Path(path)
    if not p.exists():
        print("exists=0"); return 0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print("exists=1"); print("parses=0"); print("err=%s" % type(e).__name__); return 0
    print("exists=1"); print("parses=1")
    ppl = d.get("people") or []
    print("people=%d" % len(ppl))
    print("chain_ok=%d" % (1 if ((d.get("chain") or {}).get("ok")) else 0))
    print("v_real=%d" % len([p for p in ppl if str(p.get("engine") or "").startswith("lmstudio:")]))
    print("v_fallback=%d" % len([p for p in ppl if p.get("engine") == "fallback_deterministic"]))
    print("v_noengine=%d" % len([p for p in ppl if not p.get("engine")]))
    print("gaps=%s" % ((d.get("counts") or {}).get("gaps")))
    print("errors=%s" % ((d.get("counts") or {}).get("errors")))
    print("bytes=%d" % p.stat().st_size)
    return 0


def clockfold(db):
    """時鐘倒退：造一條 ts 遞減的事件流，看摺疊與驗鏈會不會出錯。

    負控制在這裡是**內建**的：同時算一次「如果照 ts 排序會摺出什麼」。
    兩者若相同，這個檢查就沒有解析度（證明不了 fold 不看 ts）。
    """
    p = pathlib.Path(db)
    st = TwinStore(p)
    st.append("submitted", "v1", {"card": {"need": "整理桌面"}}, source="probe",
              ts_unix_ms=3_000_000)
    st.append("generated", "v1", {"arrival": "第一版", "engine": "e_old"},
              source="probe", ts_unix_ms=2_000_000)
    # NTP 把時鐘往回校 40 分鐘之後才發生的那一列：ts 更小，但 seq 更大。
    st.append("generated", "v1", {"arrival": "第二版", "engine": "e_new"},
              source="probe", ts_unix_ms=1_000_000)
    cur = st.current("v1") or {}
    by_seq = (cur.get("twin") or {}).get("engine")
    rows = list(st.conn.execute("SELECT ts_unix_ms,payload_json FROM twin_event"
                                " WHERE kind='generated'"))
    by_ts = json.loads(sorted(rows, key=lambda r: r["ts_unix_ms"])[-1]["payload_json"])["engine"]
    v = st.verify()
    ts = [r["ts_unix_ms"] for r in st.conn.execute(
        "SELECT ts_unix_ms FROM twin_event ORDER BY seq ASC")]
    print("fold_by_seq=%s" % by_seq)
    print("fold_if_sorted_by_ts=%s" % by_ts)
    print("discriminates=%d" % (1 if by_seq != by_ts else 0))
    print("verify_ok=%d" % (1 if v["ok"] else 0))
    print("ts_monotonic=%d" % (1 if all(b >= a for a, b in zip(ts, ts[1:])) else 0))
    print("flagged_by_anything=null")   # 沒有任何地方檢查 ts 單調——沒量到就是 null
    st.close()
    return 0


def tamper(db):
    """負控制：繞過 trigger 改一列，證明 verify 真的會紅（在**副本**上做）。"""
    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute("PRAGMA writable_schema=ON")
    raw.execute("DELETE FROM sqlite_master WHERE type='trigger'")
    raw.execute("PRAGMA writable_schema=OFF"); raw.close()
    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute("UPDATE twin_event SET payload_json='{\"tampered\":1}' WHERE seq=1")
    raw.close()
    st = TwinStore(db)
    v = st.verify()
    print("verify_ok=%d" % (1 if v["ok"] else 0))
    print("broken_at=%s" % ("null" if v["broken_at"] is None else v["broken_at"]))
    st.close()
    return 0


def seed(db, n):
    st = TwinStore(db)
    for i in range(int(n)):
        st.append("submitted", "seed-%02d" % i,
                  {"card": {"need": "整理第 %d 疊紙" % i, "shape": "圓潤",
                            "texture": "光滑", "color": "暖土", "vibe": "慢"},
                   "card_text": "需求：整理第 %d 疊紙" % i}, source="probe:seed")
    print("seeded=%d" % int(n))
    st.close()
    return 0


CMDS = {"counts": counts, "viewfile": viewfile, "clockfold": clockfold,
        "tamper": tamper, "seed": seed}
sys.exit(CMDS[sys.argv[1]](*sys.argv[2:]))
PYPROBE

cat > "$H/mkitems.py" <<'PYITEMS'
"""寫 items 檔。用法：mkitems.py OUT.json CASE [N]

CASE=good        乾淨的卡 N 張
CASE=<畸形代號>  一張乾淨的（鄰居，當負控制）＋一張畸形的
"""
import json
import sys

out, case = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2


def good(i, sid=None):
    return {"id": sid or ("c%02d" % i), "ts": 1758000000000 + i,
            "status": "queued",
            "card": {"need": "整理第 %d 疊紙" % i, "shape": "圓潤", "texture": "光滑",
                     "color": "暖土", "vibe": "慢、固執", "first_line": None},
            "card_text": "需求：整理第 %d 疊紙" % i}


NEIGH = good(99, "neighbour")   # 每個畸形案例都配一個乾淨鄰居：
                                # 「毒卡沒有毒死隔壁的卡」才是真正要證的事。

CASES = {
    "long":       lambda: [NEIGH, {**good(1, "bad-long"),
                                   "card": {**good(1)["card"], "need": "長" * 50000}}],
    "ctrl":       lambda: [NEIGH, {**good(1, "bad-ctrl"),
                                   "card": {**good(1)["card"],
                                            "need": "整理" + chr(0) + chr(7) + "\r" + chr(27) + "[31m桌面"}}],
    "emoji":      lambda: [NEIGH, {**good(1, "bad-emoji"),
                                   "card": {**good(1)["card"],
                                            "need": "整理🧑‍🚀👩🏽‍🦰🇹🇼桌面"}}],
    "fullwidth":  lambda: [NEIGH, {**good(1, "bad-fw"),
                                   "card": {**good(1)["card"],
                                            "need": "整理　ＡＢＣ１２３　桌面"}}],
    "empty":      lambda: [NEIGH, {"id": "bad-empty", "ts": 1, "card": None,
                                   "card_text": ""}],
    "jsoninj":    lambda: [NEIGH, {**good(1, "bad-json"),
                                   "card": {**good(1)["card"],
                                            "need": '"}],"items":[{"id":"evil"}],"x":"'}}],
    "huge":       lambda: [NEIGH, {**good(1, "bad-huge"),
                                   "card": {**good(1)["card"], "need": "巨" * 400000}}],
    "idnewline":  lambda: [NEIGH, {**good(1, "bad\nid")}],
    "idempty":    lambda: [NEIGH, {**good(1, "")}],
    "cardstr":    lambda: [NEIGH, {"id": "bad-cardstr", "ts": 1,
                                   "card": "整理桌面", "card_text": "整理桌面"}],
    "cardlist":   lambda: [NEIGH, {"id": "bad-cardlist", "ts": 1,
                                   "card": ["整理桌面"], "card_text": "x"}],
    "needint":    lambda: [NEIGH, {"id": "bad-needint", "ts": 1,
                                   "card": {"need": 123, "shape": "圓潤"},
                                   "card_text": "x"}],
    "vibedict":   lambda: [NEIGH, {"id": "bad-vibedict", "ts": 1,
                                   "card": {"need": "x", "vibe": {"a": 1}},
                                   "card_text": "x"}],
    "surrogate":  lambda: [NEIGH, {"id": "bad-surrogate", "ts": 1,
                                   "card": {"need": json.loads('"\\ud800 整理桌面"')},
                                   "card_text": json.loads('"\\ud800"')}],
    "notdict":    lambda: [NEIGH, "我不是物件", 42, None],
    "dupsame":    lambda: [good(1, "dup-1"), good(1, "dup-1"), good(2, "dup-2")],
    "dupcontent": lambda: [good(1, "diff-a"), good(1, "diff-b")],
}

if case == "good":
    items = [good(i) for i in range(n)]
else:
    items = CASES[case]()
with open(out, "w", encoding="utf-8") as f:
    json.dump({"mode": "ok", "items": items}, f)   # ensure_ascii=True：surrogate 也寫得出去
print("wrote %s case=%s items=%d" % (out, case, len(items)))
PYITEMS

port_free() {  # port_free PORT ；被佔就 fail-closed，不要安靜地跑在別人的伺服器上
  if lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "拒絕啟動：埠 $1 已經有人在聽。先確認那是什麼："
    lsof -nP -iTCP:"$1" -sTCP:LISTEN
    echo "（本腳本不替你殺不是自己起的行程）"
    exit 2
  fi
}
port_free "$CLOUD_PORT"; port_free "$MODEL_PORT"

start_cloud() {  # start_cloud ITEMS_JSON
  "$PY" "$H/fakecloud.py" "$CLOUD_PORT" "$TOKEN" "$1" >> "$OUT/_cloud.log" 2>&1 &
  CLOUD_PID=$!
  wait_up "$CLOUD/api/all?token=$TOKEN" || { bad "替身雲端起不來"; return 1; }
}
stop_cloud() {
  kill_mine "$CLOUD_PID" fakecloud.py >/dev/null 2>&1; CLOUD_PID=""
  wait_down "$CLOUD/api/all?token=$TOKEN"
}
start_model() {  # start_model [DELAY_MS]
  "$PY" "$H/fakemodel.py" "$MODEL_PORT" "${1:-0}" >> "$OUT/_model.log" 2>&1 &
  MODEL_PID=$!
  local i=0
  while [ $i -lt 60 ]; do
    if curl -sS --max-time 2 -o /dev/null -X POST -H 'Content-Type: application/json' \
        -d '{}' "$MODEL_EP/chat/completions" 2>/dev/null; then return 0; fi
    i=$((i+1)); sleep 0.2
  done
  bad "替身模型起不來"; return 1
}
stop_model() {
  kill_mine "$MODEL_PID" fakemodel.py >/dev/null 2>&1; MODEL_PID=""
  wait_down "$MODEL_EP/chat/completions"
}

# 一次 loop。所有參數明寫，`--db` 是 top-level 參數要放在子命令之前。
loop_once() {  # loop_once LOGNAME DB OUTJSON [ROUNDS]
  local log="$1" db="$2" outj="$3" rounds="${4:-1}"
  run "$log" "$PY" "$TWINLINK" --db "$db" loop --cloud "$CLOUD" --token "$TOKEN" \
      --endpoint "$MODEL_EP" --model "$MODEL_NAME" --interval 0.2 \
      --rounds "$rounds" --out "$outj"
}

# ===========================================================================
step "0. 量具自證（🔴 負控制先跑；沒有負控制的綠燈不算數）"
# ===========================================================================
D0="$OUT/d0"; mkdir -p "$D0"

# 0a. `run` 真的取得到退出碼嗎？（這條在本專案造成過「四輪印綠燈而根本沒在量」）
run "d0/00_rc_negctl.txt" "$PY" -c 'import sys; sys.stderr.write("蓄意失敗\n"); sys.exit(7)'
chk "$?" "7" "0a 負控制：run 取得到非零退出碼"
if grep -q "蓄意失敗" "$OUT/d0/00_rc_negctl.txt"; then ok "0a 負控制：stderr 有落盤沒被吞"
else bad "0a stderr 被吞了"; fi

# 0b. `http_code=000` 真的代表斷了嗎？先對一個確定沒人聽的埠量。
DEAD_CODE="$(http_code http://127.0.0.1:1/api/all)"
chk "$DEAD_CODE" "000" "0b 負控制：沒人聽的埠回 000"

"$PY" "$H/mkitems.py" "$D0/items.json" good 2 > "$OUT/d0/01_items.txt" 2>&1
start_cloud "$D0/items.json" || exit 1
start_model 0 || exit 1
UP_CODE="$(http_code "$CLOUD/api/all?token=$TOKEN")"
chk "$UP_CODE" "200" "0c 正控制：替身雲端活著回 200"
BADTOK_CODE="$(http_code "$CLOUD/api/all?token=wrong")"
chk "$BADTOK_CODE" "401" "0c 負控制：token 錯回 401（證明量具分得出「連得上」與「有權限」）"
NOPATH_CODE="$(http_code "$CLOUD/api/nope")"
chk "$NOPATH_CODE" "404" "0c 負控制：不存在的路徑回 404（不是什麼都回 200）"

# 0d. 「必中的輸入」先試：模型活著時 engine 一定要是 lmstudio:*，
#     否則後面「退到 fallback」那些綠燈全部沒有意義（本來就一直 fallback）。
loop_once "d0/02_loop_up.log" "$D0/s.sqlite3" "$D0/visitors.json" 1
chk "$?" "0" "0d loop 退出碼"
run "d0/03_counts.txt" "$PY" "$H/probe.py" counts "$D0/s.sqlite3"
C="$OUT/d0/03_counts.txt"
chk "$(kv "$C" k_submitted)" "2" "0d 兩張卡進庫"
chk "$(kv "$C" engine_real)" "2" "0d 模型活著時 engine=lmstudio:*（必中輸入）"
chk "$(kv "$C" engine_fallback)" "0" "0d 沒有無謂退化"
chk "$(kv "$C" verify_ok)" "1" "0d 鏈綠"

# 0e. 負控制：竄改一列，verify 必須紅（在副本上做，不動演練用的庫）
cp "$D0/s.sqlite3" "$D0/tampered.sqlite3"
run "d0/04_tamper.txt" "$PY" "$H/probe.py" tamper "$D0/tampered.sqlite3"
chk "$(kv "$OUT/d0/04_tamper.txt" verify_ok)" "0" "0e 負控制：竄改後 verify 變紅"
chk "$(kv "$OUT/d0/04_tamper.txt" broken_at)" "1" "0e 負控制：指得出第一個壞掉的 seq"

# ===========================================================================
step "1. 公網斷 ⇒ 已在庫的照常生成上螢幕、ingest_gap 遞增、鏈仍綠"
# ===========================================================================
D1="$OUT/d1"; mkdir -p "$D1"
"$PY" "$H/mkitems.py" "$D1/items.json" good 3 > /dev/null 2>&1
stop_cloud; start_cloud "$D1/items.json" || exit 1
stop_model; start_model 0 || exit 1

# 先在雲端活著的時候把卡抄進來，但**不生成**（只跑 ingest）——
# 這樣「斷網後還生得出分身」量的才是庫裡的存貨。
run "d1/00_ingest_up.json" "$PY" "$TWINLINK" --db "$D1/s.sqlite3" ingest \
    --cloud "$CLOUD" --token "$TOKEN"
chk "$?" "0" "1a 雲端活著時 ingest 退出碼"
run "d1/01_counts_before.txt" "$PY" "$H/probe.py" counts "$D1/s.sqlite3"
chk "$(kv "$OUT/d1/01_counts_before.txt" k_submitted)" "3" "1a 三張卡進庫"
GAP0="$(kv "$OUT/d1/01_counts_before.txt" k_ingest_gap)"
chk "$GAP0" "0" "1a 負控制：雲端活著時 ingest_gap 不會無故遞增"

kill_mine "$CLOUD_PID" fakecloud.py; CLOUD_PID=""
if wait_down "$CLOUD/api/all?token=$TOKEN"; then
  ok "1b 斷網演練成立：輪詢到 http_code=000（不是「我殺了 PID 所以應該斷了」）"
else
  bad "1b 殺了 PID 但埠還通——演練不成立，後面的綠燈全部作廢"
fi
echo "http_code(after kill)=$(http_code "$CLOUD/api/all?token=$TOKEN")" \
    > "$OUT/d1/02_cloud_down.txt"

loop_once "d1/03_loop_offline.log" "$D1/s.sqlite3" "$D1/visitors.json" 2
chk "$?" "0" "1c 公網斷時 loop 退出碼（不准崩）"
run "d1/04_counts_after.txt" "$PY" "$H/probe.py" counts "$D1/s.sqlite3"
CA="$OUT/d1/04_counts_after.txt"
chk "$(kv "$CA" k_ingest_gap)" "2" "1c 每一輪記一列 ingest_gap（跑兩輪）"
chk "$(kv "$CA" engine_real)" "3" "1c 已在庫的三張照常用真模型生成"
chk "$(kv "$CA" verify_ok)" "1" "1c 鏈仍綠"
if grep -q '"pulled": null' "$OUT/d1/03_loop_offline.log"; then
  ok "1c pulled 寫 null 不寫 0（沒量到 ≠ 量到零）"
else
  bad "1c pulled 不是 null：$(grep -o '"pulled":[^,}]*' "$OUT/d1/03_loop_offline.log" | head -2 | tr '\n' ' ')"
fi
# 斷網時 publish 每一輪都對每一張未回寫的卡重試一次、每次失敗記一列 error。
# 這不是錯誤路徑（`twinlink` 的誠實邊界 1 就這樣寫），但**成長率要量出來**：
# 無人值守跑一整天的話，那是多少列。
ERRN="$(kv "$CA" k_error)"
SUBN="$(kv "$CA" k_submitted)"
if [ -n "$ERRN" ] && [ -n "$SUBN" ] && [ "$SUBN" -gt 0 ]; then
  PER_ROUND=$((ERRN / 2))
  echo "error_events=$ERRN rounds=2 cards=$SUBN per_round=$PER_ROUND store_bytes=$(kv "$CA" store_bytes)" \
      > "$OUT/d1/06_publish_retry_growth.txt"
  note "1e 斷網期間 publish 每輪對每張卡重試一次：兩輪 $ERRN 列 error（每輪 ${PER_ROUND}＝卡數）。展場預設 --interval 10 ⇒ 每張卡每小時 360 列；100 張卡斷網一天約 86 萬列，verify／export 是 O(列數) 且每輪都跑一次 ⇒ 會愈跑愈慢。沒有退避、沒有上限"
fi
run "d1/05_view.txt" "$PY" "$H/probe.py" viewfile "$D1/visitors.json"
chk "$(kv "$OUT/d1/05_view.txt" people)" "3" "1d 螢幕那份 JSON 有三個人"
chk "$(kv "$OUT/d1/05_view.txt" chain_ok)" "1" "1d 螢幕那份 JSON 自己說鏈是綠的"

# ===========================================================================
step "2. 1003 斷 ⇒ 退到 fallback_deterministic，engine 欄位跟著變"
# ===========================================================================
D2="$OUT/d2"; mkdir -p "$D2"
"$PY" "$H/mkitems.py" "$D2/items.json" good 2 > /dev/null 2>&1
start_cloud "$D2/items.json" || exit 1
stop_model; start_model 0 || exit 1

loop_once "d2/00_loop_model_up.log" "$D2/s.sqlite3" "$D2/visitors.json" 1
chk "$?" "0" "2a 正控制：模型活著時 loop 退出碼"
run "d2/01_counts_up.txt" "$PY" "$H/probe.py" counts "$D2/s.sqlite3"
chk "$(kv "$OUT/d2/01_counts_up.txt" engine_real)" "2" "2a 正控制：兩張都是真模型"

kill_mine "$MODEL_PID" fakemodel.py; MODEL_PID=""
if wait_down "$MODEL_EP/chat/completions"; then
  ok "2b 1003 斷線演練成立：輪詢到 http_code=000"
else
  bad "2b 殺了模型 PID 但埠還通——演練不成立"
fi

# 換兩張新卡（舊的已經生成過，不會再被 pending 抓到）
"$PY" "$H/mkitems.py" "$D2/items.json" good 4 > /dev/null 2>&1
loop_once "d2/02_loop_model_down.log" "$D2/s.sqlite3" "$D2/visitors.json" 1
chk "$?" "0" "2c 1003 斷時 loop 退出碼（不准崩）"
run "d2/03_counts_down.txt" "$PY" "$H/probe.py" counts "$D2/s.sqlite3"
C2="$OUT/d2/03_counts_down.txt"
chk "$(kv "$C2" engine_fallback)" "2" "2c 新卡退到 fallback_deterministic"
chk "$(kv "$C2" engine_real)" "2" "2c 舊卡的 engine 沒有被改寫（append-only）"
chk "$(kv "$C2" verify_ok)" "1" "2c 鏈仍綠"
run "d2/04_view.txt" "$PY" "$H/probe.py" viewfile "$D2/visitors.json"
chk "$(kv "$OUT/d2/04_view.txt" v_fallback)" "2" "2d 螢幕那一層分得出退化（v_fallback=2）"
chk "$(kv "$OUT/d2/04_view.txt" v_real)" "2" "2d 螢幕那一層分得出真跑（v_real=2）"
chk "$(kv "$OUT/d2/04_view.txt" v_noengine)" "0" "2d 沒有 engine 是空的（空＝畫面分不出來）"
chk "$(kv "$C2" degraded_with_reason)" "2" "2d 每一次退化都寫得出 degrade_reason（不是只換個 engine 字串）"

# ===========================================================================
step "3. 兩個都斷 ⇒ 螢幕讀本機 export"
# ===========================================================================
D3="$OUT/d3"; mkdir -p "$D3"
stop_model; start_model 0 || exit 1
"$PY" "$H/mkitems.py" "$D3/items.json" good 3 > /dev/null 2>&1
stop_cloud; start_cloud "$D3/items.json" || exit 1
loop_once "d3/00_seed.log" "$D3/s.sqlite3" "$D3/visitors.json" 1
chk "$?" "0" "3a 正控制：兩邊都活著時先把三張卡做完"

kill_mine "$CLOUD_PID" fakecloud.py; CLOUD_PID=""
kill_mine "$MODEL_PID" fakemodel.py; MODEL_PID=""
DOWN_OK=1
wait_down "$CLOUD/api/all?token=$TOKEN" || DOWN_OK=0
wait_down "$MODEL_EP/chat/completions" || DOWN_OK=0
chk "$DOWN_OK" "1" "3b 兩邊都輪詢到 000（演練成立）"

BEFORE_BYTES="$(wc -c < "$D3/visitors.json" | tr -d ' ')"
loop_once "d3/01_loop_both_down.log" "$D3/s.sqlite3" "$D3/visitors.json" 1
chk "$?" "0" "3c 兩個都斷時 loop 退出碼（不准崩）"
run "d3/02_view.txt" "$PY" "$H/probe.py" viewfile "$D3/visitors.json"
V3="$OUT/d3/02_view.txt"
chk "$(kv "$V3" parses)" "1" "3c 螢幕那份 JSON 還解析得動"
chk "$(kv "$V3" people)" "3" "3c 三個人都還在（螢幕演得下去）"
chk "$(kv "$V3" chain_ok)" "1" "3c 鏈仍綠"
echo "before=$BEFORE_BYTES after=$(kv "$V3" bytes)" > "$OUT/d3/03_bytes.txt"
# 負控制：這一輪真的是在離線狀態下跑的嗎？
echo "cloud=$(http_code "$CLOUD/api/all?token=$TOKEN") model=$(http_code "$MODEL_EP/chat/completions")" \
    > "$OUT/d3/04_still_down.txt"
if grep -q "cloud=000 model=000" "$OUT/d3/04_still_down.txt"; then
  ok "3d 負控制：這一輪全程離線（事後再量一次還是 000）"
else
  bad "3d 這一輪其實不是離線的：$(cat "$OUT/d3/04_still_down.txt")"
fi

# ===========================================================================
step "4. kill -9 之後重啟（🔴 最重要：展場一天一開機）"
# ===========================================================================
D4="$OUT/d4"; mkdir -p "$D4"
stop_cloud; stop_model
"$PY" "$H/mkitems.py" "$D4/items.json" good 24 > /dev/null 2>&1
start_cloud "$D4/items.json" || exit 1
# 模型每發拖 40ms ⇒ 一輪 24 張約 1 秒，隨機時點 kill 才打得中「寫到一半」。
start_model 40 || exit 1

# 🔴 **不要用「睡 N 秒再殺」。** 第一版就是那樣寫的，結果五次 kill 全部落在
#    **python 還在啟動**的那 0.8 秒裡（實測 `twinlink.py --help` 要 0.83s），
#    一列事件都還沒寫，於是「kill -9 之後鏈仍綠」量到的其實是一個**空庫**——
#    綠得非常漂亮，而且完全沒有意義。改成**輪詢事件數到達目標才殺**，
#    殺的時點就一定落在真的在寫的時候。
count_events() {  # 表還沒建＝一列都還沒寫，這個 0 是真的 0 不是「沒量到」
  local n
  n="$(sqlite3 "$1" "select count(*) from twin_event;" 2>/dev/null)"
  case "$n" in ''|*[!0-9]*) echo 0 ;; *) echo "$n" ;; esac
}
wait_events() {  # wait_events DB 目標列數 最多試幾次（每次 50ms）
  local db="$1" want="$2" tries="$3" i=0
  while [ "$i" -lt "$tries" ]; do
    [ "$(count_events "$db")" -ge "$want" ] && return 0
    i=$((i+1)); sleep 0.05
  done
  return 1
}

MID_HIT=0
i=0
# 目標列數都落在第一輪之內（一輪＝24 submitted＋24 generated＋24 published＝72 列），
# 而且分佈在 ingest／generate／publish 三個階段，不要每次都殺在同一個地方。
for WANT in 3 12 20 28 40; do
  i=$((i+1))
  "$PY" "$TWINLINK" --db "$D4/s.sqlite3" loop --cloud "$CLOUD" --token "$TOKEN" \
      --endpoint "$MODEL_EP" --model "$MODEL_NAME" --interval 0.1 --rounds 0 \
      --out "$D4/visitors.json" >> "$OUT/d4/00_loop.log" 2>&1 &
  LP=$!
  REACHED=1
  wait_events "$D4/s.sqlite3" "$WANT" 200 || REACHED=0   # 最多等 10 秒
  if [ "$REACHED" = "0" ]; then
    bad "4a 第 $i 次：等了 10 秒事件數還沒到 ${WANT}（$(count_events "$D4/s.sqlite3") 列），這一次的 kill 不算數"
  fi
  if ! ps -p "$LP" -o command= 2>/dev/null | grep -q twinlink.py; then
    bad "4a 第 $i 次：要殺的 PID 不是我起的那支 loop（不殺，演練作廢）"
    break
  fi
  ALIVE_BEFORE=1; alive "$LP" || ALIVE_BEFORE=0
  kill -9 "$LP" 2>/dev/null
  wait "$LP" 2>/dev/null
  sleep 0.2
  ALIVE_AFTER=0; alive "$LP" && ALIVE_AFTER=1
  run "d4/01_counts_cycle$i.txt" "$PY" "$H/probe.py" counts "$D4/s.sqlite3"
  CC="$OUT/d4/01_counts_cycle$i.txt"
  SUB="$(kv "$CC" k_submitted)"; GEN="$(kv "$CC" k_generated)"
  echo "cycle=$i want=$WANT reached=$REACHED alive_before=$ALIVE_BEFORE alive_after=$ALIVE_AFTER sub=$SUB gen=$GEN events=$(kv "$CC" events) verify=$(kv "$CC" verify_ok)" \
      >> "$OUT/d4/02_cycles.txt"
  if [ "$ALIVE_BEFORE" != "1" ] || [ "$ALIVE_AFTER" != "0" ]; then
    bad "4a 第 $i 次 kill -9 沒打中（before=$ALIVE_BEFORE after=${ALIVE_AFTER}）"
  fi
  if [ "$(kv "$CC" verify_ok)" != "1" ]; then
    bad "4b 第 $i 次 kill -9 之後鏈就紅了（broken_at=$(kv "$CC" verify_broken_at)）"
  fi
  # 「打中寫到一半」的證據：這一輪只做了一部分（有卡進來但還沒全部生成）
  if [ -n "$SUB" ] && [ -n "$GEN" ] && [ "$SUB" -gt 0 ] && [ "$GEN" -lt "$SUB" ]; then
    MID_HIT=1
  fi
done
cat "$OUT/d4/02_cycles.txt" 2>/dev/null

if [ "$MID_HIT" = "1" ]; then
  ok "4a 至少有一次是在「做到一半」被 kill -9 的（submitted>generated）"
else
  note "4a 五次 kill 都落在輪與輪之間，**沒有**證明打中寫入中途 ⇒ 這一節對「半寫入」的解析度寫 null，不是綠"
fi

run "d4/03_counts_after_kill.txt" "$PY" "$H/probe.py" counts "$D4/s.sqlite3"
CK="$OUT/d4/03_counts_after_kill.txt"
chk "$(kv "$CK" verify_ok)" "1" "4b kill -9 五次之後鏈仍綠（沒有半寫入的列）"
run "d4/04_integrity.txt" sqlite3 "$D4/s.sqlite3" "PRAGMA integrity_check;"
if grep -qx "ok" "$OUT/d4/04_integrity.txt"; then
  ok "4b SQLite PRAGMA integrity_check=ok"
else
  bad "4b integrity_check 不是 ok：$(head -3 "$OUT/d4/04_integrity.txt" | tr '\n' ' ')"
fi
ls -1 "$D4" > "$OUT/d4/05_files.txt"
TMPLEFT="$(ls -1 "$D4" | grep -c '\.tmp$' | tr -d ' ')"
echo "tmp_leftovers=$TMPLEFT" >> "$OUT/d4/05_files.txt"
if [ "$TMPLEFT" = "0" ]; then
  ok "4b 沒有留下半寫的 visitors.json.tmp"
else
  note "4b 留下 $TMPLEFT 個 .tmp 殘檔（原子換檔的中間產物；不影響螢幕讀到的那一份，但沒人清）"
fi

# 重啟：狀態摺疊得回來嗎？
loop_once "d4/06_restart.log" "$D4/s.sqlite3" "$D4/visitors.json" 3
chk "$?" "0" "4c 重啟後 loop 退出碼"
run "d4/07_counts_restart.txt" "$PY" "$H/probe.py" counts "$D4/s.sqlite3"
CR="$OUT/d4/07_counts_restart.txt"
chk "$(kv "$CR" k_submitted)" "24" "4c 24 張卡一張不多一張不少"
chk "$(kv "$CR" max_generated_per_sub)" "1" "4c 沒有任何一張卡被生成兩次（重啟不會長出雙胞胎）"
chk "$(kv "$CR" max_submitted_per_sub)" "1" "4c 沒有任何一張卡被抄進來兩次"
chk "$(kv "$CR" verify_ok)" "1" "4c 鏈綠"
run "d4/08_view.txt" "$PY" "$H/probe.py" viewfile "$D4/visitors.json"
chk "$(kv "$OUT/d4/08_view.txt" people)" "24" "4c 螢幕那份 JSON 摺出 24 個人"
# 負控制：同一個庫用**另一個新行程**重算一次，摺疊結果要一樣（狀態真的在事件流裡，
# 不是活在剛才那個行程的記憶體裡——bridge.js 當初就是輸在這一點）。
run "d4/09_view_reopen.txt" "$PY" "$TWINLINK" --db "$D4/s.sqlite3" view
"$PY" - "$D4/visitors.json" "$OUT/d4/09_view_reopen.txt" > "$OUT/d4/10_fold_same.txt" 2>&1 <<'PYFOLD'
import json
import sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
ka = [(p["id"], p.get("engine"), p.get("arrival")) for p in a["people"]]
kb = [(p["id"], p.get("engine"), p.get("arrival")) for p in b["people"]]
print("same=%d" % (1 if ka == kb else 0))
print("n=%d" % len(ka))
PYFOLD
chk "$(kv "$OUT/d4/10_fold_same.txt" same)" "1" "4c 負控制：新行程重新摺疊，結果逐人相同"

# ===========================================================================
step "5. 磁碟寫滿 ⇒ 會安靜壞掉還是會講話？（自己造 ${RAM_MB}MB ramdisk，不塞爆任何真磁碟）"
# ===========================================================================
D5="$OUT/d5"; mkdir -p "$D5"
RAM_MNT="/Volumes/$RAM_VOL"
DISK_MEASURED=0
if [ "$SKIP_DISK" = "1" ]; then
  note "5 SKIP_DISK=1，這一節沒量 ⇒ 磁碟寫滿的行為＝null（不是「沒問題」）"
elif [ -n "${FULL_DIR:-}" ]; then
  # 外面已經掛好一個小檔案系統（Linux 展場機走這條）。
  # 🔴 **拒絕在大於 128MB 的檔案系統上做這一節**——這一節會把目標塞到一個 byte
  #    都不剩，指錯地方就是把那台機器塞爆。fail-closed，不要讓人手滑。
  RAM_MNT="$FULL_DIR"
  TOT_K="$(df -k "$RAM_MNT" 2>/dev/null | tail -1 | awk '{print $2}')"
  if [ ! -w "$RAM_MNT" ]; then
    note "5 FULL_DIR=$FULL_DIR 不可寫 ⇒ 這一節＝null"
  elif [ -z "$TOT_K" ] || [ "$TOT_K" -gt 131072 ]; then
    bad "5 拒絕執行：FULL_DIR 的檔案系統有 ${TOT_K}KB（>128MB）。這一節會把它塞滿，不對著真磁碟做"
  else
    DISK_MEASURED=1
    echo "external_mount=$RAM_MNT total_k=$TOT_K" > "$OUT/d5/00_attach.txt"
  fi
elif [ ! -x /usr/bin/hdiutil ]; then
  note "5 這台沒有 hdiutil（非 macOS？）⇒ 磁碟寫滿的行為＝null。Linux 展場機自己掛一個小 tmpfs 再跑：sudo mount -t tmpfs -o size=6m tmpfs /mnt/twinfull && sudo chown \$USER /mnt/twinfull && FULL_DIR=/mnt/twinfull bash ops/exhibit/twin/resilience_check.sh"
elif [ -e "$RAM_MNT" ]; then
  note "5 $RAM_MNT 已經存在，不動別人的東西 ⇒ 這一節＝null"
else
  # ⚠ hdiutil 的輸出是「/dev/disk11<TAB><TAB>」——`tr -d ' '` 只刪空白**不刪 tab**，
  #   帶著 tab 去餵 diskutil 會得到「Unable to find disk for /dev/disk11」。實測踩過。
  RAM_DEV="$(hdiutil attach -nomount "ram://$((RAM_MB * 2048))" 2>"$OUT/d5/00_attach.err" | awk 'NR==1{print $1}')"
  if [ -z "$RAM_DEV" ]; then
    note "5 ramdisk 建不起來（$(head -1 "$OUT/d5/00_attach.err")）⇒ 這一節＝null"
  else
    echo "dev=$RAM_DEV" > "$OUT/d5/00_attach.txt"
    if run "d5/01_format.txt" diskutil eraseVolume HFS+ "$RAM_VOL" "$RAM_DEV"; then
      DISK_MEASURED=1
    else
      note "5 ramdisk 格式化失敗 ⇒ 這一節＝null"
      hdiutil detach "$RAM_DEV" >/dev/null 2>&1; RAM_DEV=""
    fi
  fi
fi

if [ "$DISK_MEASURED" = "1" ]; then
  RDB="$RAM_MNT/twinstore.sqlite3"; RJSON="$RAM_MNT/visitors.json"
  stop_cloud; "$PY" "$H/mkitems.py" "$D5/items.json" good 2 > /dev/null 2>&1
  start_cloud "$D5/items.json" || exit 1
  stop_model; start_model 0 || exit 1

  # 5a 正控制：磁碟還沒滿的時候，同一道指令是綠的。
  loop_once "d5/02_loop_before_full.log" "$RDB" "$RJSON" 1
  chk "$?" "0" "5a 正控制：磁碟沒滿時 loop 退出碼 0"
  run "d5/03_counts_before.txt" "$PY" "$H/probe.py" counts "$RDB"
  chk "$(kv "$OUT/d5/03_counts_before.txt" engine_real)" "2" "5a 正控制：兩張卡做完了"
  cp "$RJSON" "$D5/visitors_before_full.json" 2>/dev/null
  BEFORE_SHA="$(shasum -a 256 "$RJSON" | cut -d' ' -f1)"

  # 塞爆（塞的是我自己造的 ramdisk，不是任何一台機器的真磁碟）
  dd if=/dev/zero of="$RAM_MNT/filler" bs=1024 count=$((RAM_MB * 1024 + 4096)) \
      > "$OUT/d5/04_fill.txt" 2>&1
  df -k "$RAM_MNT" >> "$OUT/d5/04_fill.txt" 2>&1
  FREE_K="$(df -k "$RAM_MNT" | tail -1 | awk '{print $4}')"
  echo "free_k=$FREE_K" >> "$OUT/d5/04_fill.txt"
  if [ "${FREE_K:-1}" -le 8 ]; then
    ok "5b ramdisk 真的滿了（剩 ${FREE_K}KB）"
  else
    bad "5b 沒塞滿（剩 ${FREE_K}KB），後面的結論不成立"
  fi

  "$PY" "$H/mkitems.py" "$D5/items.json" good 5 > /dev/null 2>&1
  loop_once "d5/05_loop_full.log" "$RDB" "$RJSON" 1
  FULL_RC=$?
  echo "rc=$FULL_RC" > "$OUT/d5/06_full_rc.txt"
  tail -25 "$OUT/d5/05_loop_full.log" >> "$OUT/d5/06_full_rc.txt"
  if [ "$FULL_RC" != "0" ]; then
    ok "5c 磁碟滿了會講話：loop 退出碼 ${FULL_RC}（不是安靜地假裝跑完）"
  else
    if grep -qiE "no space|disk is full|OSError|Errno 28" "$OUT/d5/05_loop_full.log"; then
      note "5c 退出碼 0 但輸出裡有講磁碟滿——**會講話但不會紅**，無人值守時沒人看 stdout"
    else
      bad "5c 磁碟滿了卻安靜回 0，而且輸出裡一個字都沒提（展場最壞的一種壞法）"
    fi
  fi
  AFTER_SHA="$(shasum -a 256 "$RJSON" 2>/dev/null | cut -d' ' -f1)"
  run "d5/07_view_full.txt" "$PY" "$H/probe.py" viewfile "$RJSON"
  chk "$(kv "$OUT/d5/07_view_full.txt" parses)" "1" "5c 螢幕那份 JSON 沒有被寫成半截（原子換檔守住）"
  echo "before_sha=$BEFORE_SHA after_sha=$AFTER_SHA" > "$OUT/d5/08_sha.txt"

  rm -f "$RAM_MNT/filler"
  loop_once "d5/09_loop_recovered.log" "$RDB" "$RJSON" 1
  chk "$?" "0" "5d 清出空間後自己恢復（loop 退出碼 0）"
  run "d5/10_counts_recovered.txt" "$PY" "$H/probe.py" counts "$RDB"
  chk "$(kv "$OUT/d5/10_counts_recovered.txt" verify_ok)" "1" "5d 撞過 ENOSPC 之後鏈仍綠"
  cp "$RDB" "$D5/twinstore_after_enospc.sqlite3" 2>/dev/null
  cp "$RJSON" "$D5/visitors_after_recover.json" 2>/dev/null
  if [ -n "$RAM_DEV" ]; then
    hdiutil detach "$RAM_DEV" > "$OUT/d5/11_detach.txt" 2>&1
    RAM_DEV=""
  else
    # FULL_DIR 是外面掛的，不是我掛的 ⇒ 不卸載（只殺自己起的、只拆自己掛的）
    echo "external_mount=$RAM_MNT 由呼叫端自己卸載" > "$OUT/d5/11_detach.txt"
  fi
fi

# ===========================================================================
step "6. 畸形卡 ⇒ 會不會讓 loop 整個死掉？（每一案配一張乾淨的鄰居卡當負控制）"
# ===========================================================================
D6="$OUT/d6"; mkdir -p "$D6"
CASES="long ctrl emoji fullwidth empty jsoninj huge idnewline idempty cardstr cardlist needint vibedict surrogate notdict"
# 替身雲端**每次請求重讀** items 檔，所以一個行程跑完三十個案例就好——
# 不要每個案例都殺一次、起一次（PID 愈換愈多，殺錯的機會也愈多）。
stop_cloud; start_cloud "$D6/items.json" || exit 1
cat > "$H/neigh.py" <<'PYNEIGH'
import json
import sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as e:  # noqa: BLE001
    print("neighbour_has_twin=0"); print("err=%s" % type(e).__name__); sys.exit(0)
p = [x for x in d.get("people", []) if x.get("id") == "neighbour"]
print("neighbour=%d" % len(p))
print("neighbour_has_twin=%d" % (1 if (p and p[0].get("engine")) else 0))
PYNEIGH
# 兩種後端狀態都要跑：有些崩潰**只在退化路徑上**（也就是 1003 已經斷了的時候）
# 才會發生——那是最壞的一種，因為它挑在展場已經出事的時刻才現身。
for MODE in modelup modeldown; do
  if [ "$MODE" = "modelup" ]; then
    stop_model; start_model 0 || exit 1
  else
    stop_model
    wait_down "$MODEL_EP/chat/completions" || bad "6 模型沒真的斷，modeldown 這一輪作廢"
  fi
  for CASE in $CASES; do
    CD="$D6/${MODE}_${CASE}"; mkdir -p "$CD"
    "$PY" "$H/mkitems.py" "$D6/items.json" "$CASE" > "$CD/items.txt" 2>&1
    run "d6/${MODE}_${CASE}.log" "$PY" "$TWINLINK" --db "$CD/s.sqlite3" loop \
        --cloud "$CLOUD" --token "$TOKEN" --endpoint "$MODEL_EP" --model "$MODEL_NAME" \
        --interval 0.1 --rounds 1 --out "$CD/visitors.json"
    RC=$?
    run "d6/${MODE}_${CASE}.counts" "$PY" "$H/probe.py" counts "$CD/s.sqlite3"
    CF="$OUT/d6/${MODE}_${CASE}.counts"
    NEIGH_OK=0
    if [ -f "$CD/visitors.json" ]; then
      "$PY" "$H/neigh.py" "$CD/visitors.json" > "$CD/neigh.txt" 2>&1
      [ "$(kv "$CD/neigh.txt" neighbour_has_twin)" = "1" ] && NEIGH_OK=1
    fi
    EXC="$(grep -oE '[A-Za-z_.]+(Error|Exception):' "$OUT/d6/${MODE}_${CASE}.log" | tail -1)"
    echo "case=$CASE mode=$MODE rc=$RC verify=$(kv "$CF" verify_ok) events=$(kv "$CF" events) neighbour=$NEIGH_OK exc=${EXC:-none}" \
        >> "$OUT/d6/00_matrix.txt"
    if [ "$RC" = "0" ] && [ "$(kv "$CF" verify_ok)" = "1" ] && [ "$NEIGH_OK" = "1" ]; then
      ok "6 [$MODE] ${CASE}：loop 活著、鏈綠、乾淨鄰居照樣拿到分身"
    else
      bad "6 [$MODE] ${CASE}：rc=$RC verify=$(kv "$CF" verify_ok) 鄰居有分身=$NEIGH_OK exc=${EXC:-none}"
    fi
  done
done
echo; cat "$OUT/d6/00_matrix.txt" 2>/dev/null

# 6b 真伺服器可達性：觀眾**真的送得出**那種卡嗎？（用真 server.js，本機另一個埠）
step "6b. 真 server.js 可達性（不是替身；量不到就寫 null）"
if [ ! -f "$CLOUD_REPO/server.js" ]; then
  note "6b 找不到 $CLOUD_REPO/server.js ⇒ 可達性＝null"
elif ! command -v node > /dev/null 2>&1; then
  note "6b 這台沒有 node ⇒ 可達性＝null"
elif lsof -nP -iTCP:"$REAL_CLOUD_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  note "6b 埠 $REAL_CLOUD_PORT 被佔，不動別人的東西 ⇒ 可達性＝null"
else
  D6B="$OUT/d6b"; mkdir -p "$D6B/clouddata"
  ( PORT="$REAL_CLOUD_PORT" VENUE_TOKEN="$TOKEN" DATA_DIR="$D6B/clouddata" \
    exec node "$CLOUD_REPO/server.js" ) > "$OUT/d6b/00_boot.log" 2>&1 &
  REALCLOUD_PID=$!
  REAL="http://127.0.0.1:$REAL_CLOUD_PORT"
  if wait_up "$REAL/api/all?token=$TOKEN"; then
    ok "6b 真 server.js 起來了（PID ${REALCLOUD_PID}）"
    # submit 的 http_code 要自己取。⚠ 這裡有一個會讓結論整個反過來的坑：
    #   `/api/submit` 有**每個 IP 十秒一張**的頻率限制（`RATE_WINDOW_MS`）。
    #   第一版沒等就連送兩張，第二張拿到 429，而我把它讀成「伺服器擋掉了畸形卡」
    #   ——429 跟 422 是完全不同的事，那句話是假的。所以現在逐一取 http_code，
    #   422 才叫「被擋」，429 一律判成**沒量到**。
    post_card() {  # post_card 標籤 資料檔名（都相對於 d6b/）→ 印出 http_code
      curl -sS --max-time 5 -X POST "$REAL/api/submit" \
          -H 'Content-Type: application/json' --data-binary @"$OUT/d6b/$2" \
          -o "$OUT/d6b/$1.body" -w '%{http_code}' 2>"$OUT/d6b/$1.err"
    }
    printf '{"card_text":"\\u9700\\u6c42\\uff1a\\u6574\\u7406\\u684c\\u9762"}' \
        > "$OUT/d6b/01_clean_payload.json"
    C1="$(post_card 01_clean 01_clean_payload.json)"
    chk "$C1" "200" "6b-1 正控制：乾淨的卡送得進真伺服器"

    # 6b-2 同一個 IP 馬上再送一張（展場實況：大家都在同一個 wifi 後面）
    C2="$(post_card 02_clean_again 01_clean_payload.json)"
    echo "second_submit_http=$C2" > "$OUT/d6b/02_ratelimit.txt"
    cat "$OUT/d6b/02_clean_again.body" >> "$OUT/d6b/02_ratelimit.txt"
    if [ "$C2" = "429" ]; then
      note "6b-2 同一個 IP 十秒內第二張卡被擋（429「送太快了」）。server.js 用 req.ip 做視窗，而它**沒有設 trust proxy** ⇒ 展場所有人在同一個 NAT 後面時會互相排擠。⚠ 線上是不是也這樣＝null（沒量：要量就得往生產環境投卡）"
    else
      note "6b-2 同一個 IP 十秒內第二張卡回 ${C2}（不是 429）"
    fi

    # 6b-3 lone surrogate（`\ud800`）——手機打不出來，但公網上任何人 curl 得出來。
    #      先等過頻率視窗（10 秒），否則量到的是 429 不是 PII 判定。
    sleep 11
    printf '{"card_text":"\\u9700\\u6c42\\uff1a\\ud800 \\u6574\\u7406\\u684c\\u9762"}' \
        > "$OUT/d6b/03_surrogate_payload.json"
    C3="$(post_card 03_surrogate 03_surrogate_payload.json)"
    echo "surrogate_http=$C3" > "$OUT/d6b/04_surrogate_verdict.txt"
    cat "$OUT/d6b/03_surrogate.body" >> "$OUT/d6b/04_surrogate_verdict.txt"
    case "$C3" in
      200) note "6b-3 真伺服器**收下了** lone surrogate（200；PII 過濾不擋這個）⇒ 這條路徑觀眾端可達，不是只有替身雲端才做得出來" ;;
      422) note "6b-3 真伺服器以 422 擋掉 lone surrogate（PII 過濾順手擋到）⇒ 觀眾端不可達" ;;
      *)   note "6b-3 lone surrogate 可達性＝null（http=${C3}，既不是 200 也不是 422，沒量到）" ;;
    esac
    curl -sS --max-time 5 "$REAL/api/all?token=$TOKEN" > "$OUT/d6b/05_all.json" 2>&1
    run "d6b/06_ingest.json" "$PY" "$TWINLINK" --db "$D6B/s.sqlite3" ingest \
        --cloud "$REAL" --token "$TOKEN"
    ING_RC=$?
    run "d6b/07_counts.txt" "$PY" "$H/probe.py" counts "$D6B/s.sqlite3"
    echo "clean=$C1 second=$C2 surrogate=$C3 ingest_rc=$ING_RC" \
        > "$OUT/d6b/08_verdict.txt"
    if [ "$ING_RC" = "0" ]; then
      ok "6b-4 ingest 吃得下真伺服器回的那份 /api/all（退出碼 0）"
    else
      bad "6b-4 ingest 被真伺服器的回應打死（rc=${ING_RC}，$(grep -oE '[A-Za-z_.]+(Error|Exception):' "$OUT/d6b/06_ingest.json" | tail -1)）"
    fi
  else
    note "6b 真 server.js 起不來（$(head -3 "$OUT/d6b/00_boot.log" | tr '\n' ' ')）⇒ 可達性＝null"
  fi
  kill_mine "$REALCLOUD_PID" server.js >/dev/null 2>&1; REALCLOUD_PID=""
fi

# ===========================================================================
step "7. 時鐘倒退（NTP 校正）⇒ 事件流的時間戳會不會讓摺疊出錯"
# ===========================================================================
D7="$OUT/d7"; mkdir -p "$D7"
run "d7/00_clockfold.txt" "$PY" "$H/probe.py" clockfold "$D7/s.sqlite3"
CF7="$OUT/d7/00_clockfold.txt"
cat "$CF7"
chk "$(kv "$CF7" discriminates)" "1" \
    "7a 這個檢查有解析度（照 seq 摺與照 ts 摺會得到不同答案，所以下一項不是廢話）"
chk "$(kv "$CF7" fold_by_seq)" "e_new" "7a 時鐘倒退後仍摺出「後寫進去的那一列」"
chk "$(kv "$CF7" verify_ok)" "1" "7a 時鐘倒退不會讓驗鏈變紅（鏈算的是 seq 與雜湊，不是時間）"
chk "$(kv "$CF7" ts_monotonic)" "0" "7a 負控制：這條事件流的 ts 真的是倒退的"
note "7b 沒有任何地方檢查 ts 單調（flagged_by_anything=null）⇒ 時鐘倒退**不會出錯也不會被發現**。展場影響：畫面上的時間可能倒著走，排序／摺疊不受影響"
note "7c 沒量到：系統層時鐘跳躍（沒有動這台機器的時鐘，也沒有 faketime）。loop 的間隔用 time.sleep，不看牆鐘"

# ===========================================================================
step "8. 同一張卡重複投遞 ⇒ 會不會生出兩隻分身"
# ===========================================================================
D8="$OUT/d8"; mkdir -p "$D8"
stop_model; start_model 0 || exit 1
"$PY" "$H/mkitems.py" "$D8/items_same.json" dupsame > /dev/null 2>&1
stop_cloud; start_cloud "$D8/items_same.json" || exit 1
# 同一個 id 在同一份回應裡出現兩次，而且連抄三輪
loop_once "d8/00_loop_dupsame.log" "$D8/same.sqlite3" "$D8/visitors_same.json" 3
chk "$?" "0" "8a loop 退出碼"
run "d8/01_counts_same.txt" "$PY" "$H/probe.py" counts "$D8/same.sqlite3"
C8="$OUT/d8/01_counts_same.txt"
chk "$(kv "$C8" max_submitted_per_sub)" "1" "8a 同一個 id 投三輪只進庫一次"
chk "$(kv "$C8" max_generated_per_sub)" "1" "8a 同一個 id 只生一隻分身"
chk "$(kv "$C8" subs)" "2" "8a 兩個不同 id ＝ 兩個人"
run "d8/02_view_same.txt" "$PY" "$H/probe.py" viewfile "$D8/visitors_same.json"
chk "$(kv "$OUT/d8/02_view_same.txt" people)" "2" "8a 螢幕上是兩個人不是四個"

# 負控制：不同 id、內容一模一樣 ⇒ **一定要**生出兩隻。
# 沒有這一項，上面的「只生一隻」可能只是因為根本沒抄進來。
"$PY" "$H/mkitems.py" "$D8/items_diff.json" dupcontent > /dev/null 2>&1
stop_cloud; start_cloud "$D8/items_diff.json" || exit 1
loop_once "d8/03_loop_dupcontent.log" "$D8/diff.sqlite3" "$D8/visitors_diff.json" 1
run "d8/04_counts_diff.txt" "$PY" "$H/probe.py" counts "$D8/diff.sqlite3"
chk "$(kv "$OUT/d8/04_counts_diff.txt" subs)" "2" \
    "8b 負控制：內容相同但 id 不同 ⇒ 真的會變成兩個人（去重不是「什麼都沒抄進來」造成的假綠）"
note "8c 誠實邊界：去重的鍵是**雲端給的 id**，不是卡的內容。觀眾在手機上連按兩次送出，雲端會發兩個 id ⇒ 螢幕上就是兩隻分身。要擋那個得在雲端或用內容雜湊，這一層擋不到"

# ===========================================================================
step "收尾"
# ===========================================================================
if [ "$TRIM" = "1" ]; then
  # 刪的是「重跑就會一模一樣再長出來」的大檔（各節的 sqlite 庫、畸形卡那些
  # MB 級 items）。**先列清單再刪**——證據不可以安靜地消失。
  find "$OUT" \( -name '*.sqlite3' -o -name '*.sqlite3-wal' -o -name '*.sqlite3-shm' \) \
      -exec ls -la {} \; > "$OUT/00_trimmed.txt" 2>&1
  find "$OUT" -type f -size +256k ! -name '00_trimmed.txt' -exec ls -la {} \; \
      >> "$OUT/00_trimmed.txt" 2>&1
  find "$OUT" \( -name '*.sqlite3' -o -name '*.sqlite3-wal' -o -name '*.sqlite3-shm' \) \
      -delete 2>/dev/null
  find "$OUT" -type f -size +256k ! -name '00_trimmed.txt' -delete 2>/dev/null
  echo "（TRIM=1：以上大檔已刪，清單在 00_trimmed.txt；TRIM=0 可全部留著）" \
      >> "$OUT/00_trimmed.txt"
  echo "  已瘦身，刪掉 $(grep -c '^-' "$OUT/00_trimmed.txt") 個可重建的大檔（清單：00_trimmed.txt）"
fi

step "總結"
{
  echo "resilience_check.sh — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "綠 ${PASS}／紅 ${FAIL}／記錄 $NOTES"
  echo
  echo "== 紅燈 =="
  grep '^紅|' "$OUT/_verdicts.txt" 2>/dev/null | sed 's/^紅|/  - /' || echo "  （無）"
  echo
  echo "== 記錄（沒量到／誠實邊界，不是綠也不是紅）=="
  grep '^記|' "$OUT/_verdicts.txt" 2>/dev/null | sed 's/^記|/  - /' || echo "  （無）"
} > "$OUT/SUMMARY.txt"
cat "$OUT/SUMMARY.txt"
echo
echo "證據：$OUT"
[ "$FAIL" = "0" ] && exit 0 || exit 1
