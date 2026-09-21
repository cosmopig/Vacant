"""把一份 twinlink 快照按時間改寫，驅動展件走完整條產品路徑。

用法：python3 drive.py <steps>   例如 "3:A 14:D" ＝ 第 3 秒寫 A、第 14 秒寫 D。
狀態：E 空、A 只投了卡（status=submitted）、D 退化（engine=fallback_deterministic
      但還沒有話）、F 分身真的生出來了（三句話＋lmstudio engine）。

⚠ 這不是「假裝」：頁面那一側走的是 `bridge.js` 的 snapshot 那一層 → `deliver()`
  → `WorldBridge.onSubmission` → `arrivals.arrive()` ＋ `routeSubmission()`，
  跟展場真的有人投卡時**同一條碼**。這支只負責扮演 `twinlink loop`（寫快照的那一方）。
"""
import json, os, sys, time, datetime, pathlib

LIVE = pathlib.Path("/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/"
                    "ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/srv/world3/live")
OUT = LIVE / "visitors_probe.json"
# ⚠ 每一次錄影要換一個 id：`bridge.js` 的 `seenIds` 會落 localStorage
#   （48 小時 TTL），同一個 id 第二次進來會被當成「看過了」直接跳過——
#   第一次錄完之後第二次就不會有人進來，而畫面上看起來只是「什麼都沒發生」。
PID = os.environ.get("PROBE_ID", "probe-2026-09-21-wait")
CARD = {"color": "暖土", "shape": "圓潤", "texture": "粗陶",
        "need": "（探針）把散在桌上的收據整理成一份清單",
        "first_line": "（探針）這裡的光有點暖。"}


def envelope(people):
    return {
        "_what": "等待態證據用的探針快照。drive.py 扮演 twinlink loop 寫它。",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "store_id": "probe", "chain": None,
        "counts": {"visitors": len(people), "events": None, "gaps": None, "errors": None},
        "people": people,
        "honesty": "engine=lmstudio:* 才是真的有模型回話；fallback_deterministic 是離線查表。",
    }


def person(**kw):
    base = {"id": PID, "card": CARD, "arrival": None, "working": None,
            "handover": None, "engine": None, "status": "submitted", "errors": 0}
    base.update(kw)
    return base


STATES = {
    "E": lambda: envelope([]),
    "A": lambda: envelope([person()]),
    "D": lambda: envelope([person(engine="fallback_deterministic")]),
    "F": lambda: envelope([person(
        arrival="（探針）這裡的光有點暖。",
        working="每一張都要對齊，就算慢一點也要把位置擺正。",
        handover="已經全部歸類整齊了，請收好這份清單。",
        engine="lmstudio:gemma-4-12b-it-qat", status="generated")]),
}


def write(k):
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATES[k](), ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)          # 原子替換：輪詢不會讀到寫到一半的檔
    print("[drive] t=%.1f  state=%s" % (time.time() - T0, k), flush=True)


T0 = time.time()
write("E")
for step in sys.argv[1:]:
    at, k = step.split(":")
    d = T0 + float(at) - time.time()
    if d > 0:
        time.sleep(d)
    write(k)
