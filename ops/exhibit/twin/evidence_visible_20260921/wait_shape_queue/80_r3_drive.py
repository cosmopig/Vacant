"""多人版的快照驅動器：扮演 `twinlink loop`，按時間改寫一份 visitors 快照。

`44_drive_snapshot.py` 只驅動得動**一個人**，所以「一班學生同時投卡」那一格
一直沒有被錄過（`wait_shape/README.md` §十一 自己列的缺口）。這一支把人數打開。

用法：python3 r3_drive.py <steps...>
  步驟格式 `<秒>:<動作><編號>`
    `A1` 第 1 位投了卡（status=submitted、engine=null）＝**等待態的輸入**
    `D2` 第 2 位被判定為查表湊的（engine=fallback_deterministic，還沒有話）
    `F3` 第 3 位分身真的生出來了（三句話 ＋ lmstudio engine）
  例：`3:A1 9:A2 15:A3 70:F1`

⚠ 走的是產品路徑：頁面那一側是 `bridge.js` 的 snapshot 層 → `deliver()` →
  `WorldBridge.onSubmission` → `arrivals.arrive()` ＋ `routeSubmission()`。
  這支只負責寫快照，**不碰頁面裡的任何變數**。
"""
import json, os, sys, time, datetime, pathlib

LIVE = pathlib.Path(os.environ.get(
    "R3_LIVE",
    "/private/tmp/claude-501/-Users-cosmopig-Documents-GitHub-Vacant/"
    "ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad/mirror3/world3/live"))
OUT = LIVE / "visitors_probe.json"

# ⚠ 每一次錄影要換一組 id：`bridge.js` 的 `seenIds` 會落 localStorage（48h TTL），
#   同一個 id 第二次進來會被當成「看過了」直接跳過，畫面上看起來像「什麼都沒發生」。
PID = os.environ.get("PROBE_ID", "probe-r3")

# 三張**不一樣**的卡：顏色／造型／質地都不同，才看得出「那一團是他的」不是通用 loading。
CARDS = {
    1: {"color": "暖土", "shape": "圓潤", "texture": "粗陶",
        "need": "（探針）把散在桌上的收據整理成一份清單",
        "first_line": "（探針）這裡的光有點暖。"},
    2: {"color": "灰藍", "shape": "方正", "texture": "細砂",
        "need": "（探針）把兩份名單對起來，找出只出現在其中一邊的",
        "first_line": "（探針）我來核對的。"},
    3: {"color": "苔綠", "shape": "細長", "texture": "粗粒",
        "need": "（探針）幫我把一段很長的紀錄縮成三句話",
        "first_line": "（探針）我話不多。"},
}
STATE = {}          # k -> person dict


def pid(k):
    return f"{PID}-{k}"


def person(k, **kw):
    base = {"id": pid(k), "card": CARDS[k], "arrival": None, "working": None,
            "handover": None, "engine": None, "status": "submitted", "errors": 0}
    base.update(kw)
    return base


ACT = {
    "A": lambda k: person(k),
    "D": lambda k: person(k, engine="fallback_deterministic"),
    "F": lambda k: person(
        k,
        arrival=CARDS[k]["first_line"],
        working="每一張都要對齊，就算慢一點也要把位置擺正。",
        handover="已經全部歸類整齊了，請收好這份清單。",
        engine="lmstudio:gemma-4-12b-it-qat", status="generated"),
}


def envelope():
    people = [STATE[k] for k in sorted(STATE)]
    return {
        "_what": "等待態第三輪（多人同時投卡）的探針快照。r3_drive.py 扮演 twinlink loop。",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "store_id": "probe", "chain": None,
        "counts": {"visitors": len(people), "events": None, "gaps": None, "errors": None},
        "people": people,
        "honesty": "engine=lmstudio:* 才是真的有模型回話；fallback_deterministic 是離線查表。",
    }


def write(tag):
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(envelope(), ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)          # 原子替換：輪詢不會讀到寫到一半的檔
    print("[drive] t=%.1f  %s  people=%d" % (time.time() - T0, tag, len(STATE)), flush=True)


T0 = time.time()
write("EMPTY")
for step in sys.argv[1:]:
    at, act = step.split(":")
    k = int(act[1:])
    d = T0 + float(at) - time.time()
    if d > 0:
        time.sleep(d)
    STATE[k] = ACT[act[0]](k)
    write(act)
