#!/usr/bin/env python3
"""稽核端：`examples/receipt_viewer.html` 在展場講的話，這裡用 Python 再算一次。

這支在架構裡承重什麼（CLAUDE.md §展件可直接複用的、DECISION_20260903_R440P §四）：
收據牆那一頁的整個宣稱是「你眼前這台機器自己重算了一次」。如果頁內那份 JS 的
位元組佈局跟 `vacant/logbook.py` 差一個字元，畫面會照樣顯示綠色的「驗證通過」——
**一把會 PASS 的瞎尺**。所以每一條乾淨斷言旁邊都有一條竄改斷言，而且 JS 的
正規化規則在這裡被**重寫一次**（不是呼叫 `vacant.canonical`），再拿去對
`LogEntry.hash()`：兩條獨立的路走到同一個 hash，才算對得起來。

檢查項（任一項 BROKEN ⇒ 退出碼 1）：
  C1 `Logbook.verify_chain` 對真檔為真（權威實作）
  C2 JS 正規化規則的 Python 鏡像，逐筆等於 `LogEntry.hash()`（482/482）
  C3 邊界案例（非 ASCII、非 BMP 鍵、控制字元、U+2028、負數、2^53−1）鏡像等於
     `vacant.canonical.canonical_bytes`
  C4 頁內內嵌的樣本與**它自己宣稱的來源 run**（g_r445）逐位元組相同
     ——這是頁面的性質不是 run 的性質，所以 `--run` 指向別的 run 時它照樣比 g_r445
  C5 竄改斷言：翻一個 `visible_ok` ⇒ hash 變、簽章驗不過、下一筆 prev_hash 接不上
  C6 措辭紅線：全檔不得出現「信任」「防止」「保證」（CLAUDE.md 鐵律：展場口徑）
  C7 離線紅線：沒有任何外部資源（http(s)://、link/img/iframe/script src、fetch、
     XHR、WebSocket、@import、url()）
  C8 必要標語在檔案裡：真實資料標示、示範標示、以及不支援 Ed25519 時的退化說明
  C9 浮點數守門員：`lineHasOnlySafeIntegers` 的鏡像對含小數／超大整數的行回 False
     （那正是 JS 與 Python 的數字格式會分岔的地方，頁面在那裡選擇說「不知道」）

用法：
  .venv/bin/python ops/gain/replay/receipt_viewer_crosscheck.py            # 只跑 g_r445
  .venv/bin/python ops/gain/replay/receipt_viewer_crosscheck.py --all      # g_r445 ＋ g_r447
  .venv/bin/python ops/gain/replay/receipt_viewer_crosscheck.py \\
      --run runs/g_r445_conform_mbpp_ext --arm CONFORM --json out.json

node-free：本檔只用標準函式庫＋`vacant`。想跑「真的那份 JS」而不是鏡像，
用同目錄的 `receipt_viewer_node_check.mjs`（有 node 才跑得動，非必要）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from vacant.canonical import canonical_bytes  # noqa: E402
from vacant.identity import PublicIdentity  # noqa: E402
from vacant.logbook import LogEntry, Logbook, _signed_bytes  # noqa: E402

VIEWER = REPO / "examples" / "receipt_viewer.html"
DEFAULT_RUN = REPO / "runs" / "g_r445_conform_mbpp_ext"
# 頁面內嵌的那份樣本來自哪裡。C4 比的永遠是這一個——「頁內樣本沒有被改過」是
# 頁面的性質，不是被檢查的那個 run 的性質；`--run` 指到 g_r447 時 C4 不該因此變紅。
EMBEDDED_RUN = REPO / "runs" / "g_r445_conform_mbpp_ext"
EMBEDDED_ARM = "CONFORM"
# `--all` 要涵蓋的 run：兩條獨立簽出來的鏈（不同 keypair、不同題庫），
# 一條過關可能是巧合，兩條都過才排得掉「鏡像剛好跟著錯」。
ALL_RUNS = [
    (REPO / "runs" / "g_r445_conform_mbpp_ext", "CONFORM"),
    (REPO / "runs" / "g_r447_conform_lcb2", "CONFORM"),
]

CANON_BEGIN = "/* === CANON-BEGIN ==="
CANON_END = "/* === CANON-END === */"

# ---------------------------------------------------------------------------
# 頁內那份 JS 的 Python 鏡像。**逐段對著 HTML 裡的函式抄**，不要改寫成
# 「反正呼叫 canonical_bytes 就好」——那樣這支腳本就只是在測 Python 測自己。
# ---------------------------------------------------------------------------

_JS_SHORT_ESCAPE = {0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r"}


def js_stringify_string(s: str) -> str:
    """鏡像 `JSON.stringify(<string>)`。

    JS 只跳脫 `"`、`\\` 與 <0x20 的控制字元（`\\b\\t\\n\\f\\r` 用短式，其餘 `\\u00xx`
    小寫十六進位），並把落單的代理對編成 `\\udxxx`；其餘字元原樣輸出（含非 ASCII、
    U+2028/U+2029、DEL）。這與 Python `json.dumps(ensure_ascii=False)` 的輸出相同，
    也就是 `vacant/canonical.py` 用的那一套。
    """
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o in _JS_SHORT_ESCAPE:
            out.append(_JS_SHORT_ESCAPE[o])
        elif o < 0x20 or 0xD800 <= o <= 0xDFFF:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def js_format_number(n) -> str:
    """鏡像 `formatNumber`：只承諾安全整數，其餘丟例外。

    JSON.parse 之後 `5.0` 與 `5` 在 JS 裡已經分不出來，而 Python 的 float repr
    與 JS 的 Number→String 規則不同（`1e-07` vs `1e-7`、`100000.0` vs `100000`）。
    所以整數以外的東西頁面一律拒答，不會算出一個看起來很像的錯 hash。
    """
    if isinstance(n, bool):
        raise TypeError("bool 不走數字這條路")
    if isinstance(n, float) and n.is_integer():
        n = int(n)  # JS 的 Number.isInteger(5.0) 為真
    if isinstance(n, int) and abs(n) <= 2 ** 53 - 1:
        return str(n)
    raise ValueError("非整數或超出安全整數範圍的數值：%r" % (n,))


def js_canonical_string(v) -> str:
    """鏡像 `canonicalString`。鍵排序用 Python 預設的字串比較，

    它與 JS 那支 `cmpCodePoint` 同義：兩者都是逐 code point 比大小
    （JS 預設的字串比較是 UTF-16 code unit，會在 BMP 外分岔，所以頁面沒有用它）。
    """
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return js_format_number(v)
    if isinstance(v, str):
        return js_stringify_string(v)
    if isinstance(v, list):
        return "[" + ",".join(js_canonical_string(x) for x in v) + "]"
    if isinstance(v, dict):
        keys = sorted(v.keys())
        return "{" + ",".join(
            js_stringify_string(k) + ":" + js_canonical_string(v[k]) for k in keys) + "}"
    raise TypeError("無法正規化的型別：%s" % type(v).__name__)


def js_core_of(e: dict) -> dict:
    return {
        "stream_id": e["stream_id"], "branch_id": e["branch_id"], "seq": e["seq"],
        "prev_hash": e["prev_hash"], "ts_ms": e["ts_ms"], "type": e["type"],
        "payload": e["payload"],
    }


def js_entry_hash(e: dict) -> str:
    return hashlib.sha256(js_canonical_string(js_core_of(e)).encode("utf-8")).hexdigest()


def js_tamper_target(dicts: list[dict]) -> int:
    """鏡像頁面的 `tamperTarget`：挑一筆「不是最後一筆」的通過紀錄，取候選的中位。

    為什麼不能挑最後一筆：沒有 Ed25519 的瀏覽器只剩 hash 鏈，而最後一筆的內容
    沒有下一筆的 prev_hash 可以互相對照，示範會少掉一半。
    """
    cand = [i for i, d in enumerate(dicts)
            if i < len(dicts) - 1 and d["type"] == "conform_attempt"
            and isinstance(d.get("payload"), dict) and d["payload"].get("visible_ok") is True]
    if cand:
        return cand[len(cand) // 2]
    return 0 if len(dicts) > 1 else -1


_JS_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def js_line_has_only_safe_integers(line: str) -> bool:
    """鏡像 `lineHasOnlySafeIntegers`：把字串挖掉之後，剩下的數字字面值有沒有
    小數點／指數／超過安全整數位數。"""
    bare = _JS_STRING_RE.sub('""', line)
    if re.search(r"[0-9](?:\.|[eE])", bare):
        return False
    if re.search(r"[0-9]{16,}", bare):
        return False
    return True


# ---------------------------------------------------------------------------
# 檢查
# ---------------------------------------------------------------------------

def _mark(results: list, cid: str, ok: bool, msg: str) -> bool:
    results.append({"check": cid, "verdict": "OK" if ok else "BROKEN", "msg": msg})
    return ok


def extract_embedded(html: str) -> tuple[str, str]:
    """把頁內內嵌的樣本挖出來（與磁碟檔比對用）。"""
    def grab(elem_id: str) -> str:
        m = re.search(
            r'<script[^>]*id="%s"[^>]*>\n(.*?)\n</script>' % re.escape(elem_id),
            html, re.S)
        if not m:
            raise ValueError("頁面裡找不到 id=%s 的內嵌樣本" % elem_id)
        return m.group(1)
    return grab("embedded-chain"), grab("embedded-pub")


CANON_FIXTURES = [
    {"b": "a", "a": "b"},
    {"z": 1, "A": 2, "_": 3, "0": 4},
    {"k": '引號" 反斜線\\ 換行\n tab\t 控制\x1f 刪除\x7f'},
    {"中文": "值", "英": ["a", 1, True, None, {"x": []}]},
    {"emoji": "🌱🀄", "key🌱": "非 BMP 的鍵"},
    # 跨平面「鍵」排序（不只是值裡有非 BMP 字元）：五個鍵的第一個字元就跨
    # BMP／非 BMP 邊界，逼排序真的在這條邊界上做決定，不是被前面的字元先分出
    # 高下。JS 那邊同一組鍵、同一份期望值見
    # `ops/gain/replay/receipt_viewer_node_check.mjs` 的 N5b（"blind ruler"
    # 教訓：曾經只有 cmpCodePoint 的孤立單元測試，canonicalString 本體卻換成
    # 沒吃比較器的 Object.keys(v).sort()，三邊 check 照樣全線）。
    {"🌱": 2, "�": 1, "Ａ": 3, "a": 4, " ": 5},
    {"u2028": "  "},
    {"nested": {"b": {"d": 1, "c": [{"z": 0, "y": -7}]}, "a": []}},
    {"neg": -1, "zero": 0, "big": 2 ** 53 - 1, "ts": 1788474567745},
    [], {}, "純字串", 123, True, None,
]

FORBIDDEN_WORDS = ["信任", "防止", "保證"]
FORBIDDEN_NET = [
    "http://", "https://", "fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
    "importScripts", "@import", "url(", "<link", "<img", "<iframe", "<script src",
    "<audio", "<video", "srcset",
]
REQUIRED_TEXT = [
    "以下是 2026-09-03 22:29 → 09-04 01:21（UTC）真實實驗 g_r445 的紀錄，不是模擬",
    "這是示範，不是資料",
    "此瀏覽器不支援 Ed25519 驗簽，只驗了 hash 鏈",
    '<meta charset="utf-8">',
]


def run(run_dir: pathlib.Path, arm: str, viewer: pathlib.Path) -> dict:
    results: list = []
    chain_path = run_dir / f"receipts_{arm}.ndjson"
    pub_path = run_dir / f"receipts_{arm}.pub.json"
    raw = chain_path.read_text(encoding="utf-8")
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    dicts = [json.loads(ln) for ln in lines]
    book = Logbook.load(chain_path)
    meta = json.loads(pub_path.read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
    html = viewer.read_text(encoding="utf-8")

    # C1 —— 權威實作
    _mark(results, "C1", book.verify_chain(who),
          "Logbook.verify_chain：%d 筆，stream_id=%s… head=%s…"
          % (len(book), (book.stream_id() or "")[:12], book.head()[:12]))

    # C2 —— 鏡像 vs LogEntry.hash()，逐筆
    bad = [i + 1 for i, (d, e) in enumerate(zip(dicts, book.entries))
           if js_entry_hash(d) != e.hash()]
    _mark(results, "C2", not bad,
          "JS 正規化鏡像 vs LogEntry.hash()：%d/%d 筆相同%s"
          % (len(dicts) - len(bad), len(dicts),
             "" if not bad else "；不同的：%s" % bad[:10]))

    # C3 —— 邊界案例
    diffs = [i for i, c in enumerate(CANON_FIXTURES)
             if js_canonical_string(c).encode("utf-8") != canonical_bytes(c)]
    _mark(results, "C3", not diffs,
          "邊界案例 %d 組（含非 BMP 鍵、控制字元、U+2028、2^53−1）鏡像＝canonical_bytes%s"
          % (len(CANON_FIXTURES), "" if not diffs else "；不同的：%s" % diffs))

    # C4 —— 頁內樣本 vs 它宣稱的來源 run（永遠是 EMBEDDED_RUN，不是 --run 指的那個）
    try:
        emb_chain, emb_pub = extract_embedded(html)
        src_chain = (EMBEDDED_RUN / f"receipts_{EMBEDDED_ARM}.ndjson").read_text(encoding="utf-8")
        src_pub = (EMBEDDED_RUN / f"receipts_{EMBEDDED_ARM}.pub.json").read_text(encoding="utf-8")
        same_chain = emb_chain == src_chain.rstrip("\n")
        same_pub = emb_pub == src_pub.strip()
        _mark(results, "C4", same_chain and same_pub,
              "頁內內嵌樣本與 %s 逐位元組相同：ndjson=%s（%d 筆／%d bytes）、pub.json=%s"
              % (EMBEDDED_RUN.name, same_chain,
                 len([ln for ln in emb_chain.split("\n") if ln.strip()]),
                 len(emb_chain.encode("utf-8")), same_pub))
    except (ValueError, OSError) as exc:
        _mark(results, "C4", False, str(exc))

    # C5 —— 竄改斷言（乾淨路徑通過不算數）。挑的是頁面〔竄改示範〕會挑的同一筆。
    idx = js_tamper_target(dicts)
    tam = json.loads(lines[idx])
    tam["payload"]["visible_ok"] = not tam["payload"]["visible_ok"]
    tam_entry = LogEntry.from_json(tam)
    sig_of = lambda d: who.verify(  # noqa: E731
        _signed_bytes(d["stream_id"], d["branch_id"], d["seq"], d["prev_hash"],
                      d["ts_ms"], d["type"], d["payload"]),
        bytes.fromhex(d["sig"]))
    tampered_book = Logbook([LogEntry.from_json(json.loads(ln)) for ln in lines])
    tampered_book.entries[idx] = tam_entry
    checks = {
        "改之前這一筆的簽章驗得過": sig_of(dicts[idx]),
        "鏡像 hash 變了": js_entry_hash(tam) != js_entry_hash(dicts[idx]),
        "logbook hash 變了": tam_entry.hash() != book.entries[idx].hash(),
        "鏡像與 logbook 對竄改後的那一筆仍然同意": js_entry_hash(tam) == tam_entry.hash(),
        "改之後簽章驗不過": not sig_of(tam),
        "下一筆 prev_hash 接不上": dicts[idx + 1]["prev_hash"] != tam_entry.hash(),
        "整條鏈 verify_chain 為假": not tampered_book.verify_chain(who),
    }
    _mark(results, "C5", all(checks.values()),
          "竄改第 %d 筆的 visible_ok：%s"
          % (idx + 1, "、".join("%s=%s" % (k, v) for k, v in checks.items())))

    # C6 —— 措辭紅線
    hits = [w for w in FORBIDDEN_WORDS if w in html]
    _mark(results, "C6", not hits,
          "措辭紅線（信任／防止／保證）：%s" % ("全檔皆無" if not hits else "出現 %s" % hits))

    # C7 —— 離線紅線
    net = [p for p in FORBIDDEN_NET if p.lower() in html.lower()]
    _mark(results, "C7", not net,
          "外部資源：%s" % ("一個都沒有" if not net else "出現 %s" % net))

    # C8 —— 必要標語
    missing = [t for t in REQUIRED_TEXT if t not in html]
    _mark(results, "C8", not missing,
          "必要標語：%s" % ("四條都在" if not missing else "缺 %s" % missing))

    # C9 —— 浮點數守門員
    unsafe = [i + 1 for i, ln in enumerate(lines) if not js_line_has_only_safe_integers(ln)]
    guard = (
        js_line_has_only_safe_integers('{"a":1,"b":true,"c":"1.5e7"}') is True
        and js_line_has_only_safe_integers('{"a":1.5}') is False
        and js_line_has_only_safe_integers('{"a":1e7}') is False
        and js_line_has_only_safe_integers('{"a":12345678901234567}') is False
    )
    _mark(results, "C9", not unsafe and guard,
          "真檔 %d 行的數字全在安全整數內（%d 行例外）；守門員對小數／指數／超大整數皆回 False=%s"
          % (len(lines), len(unsafe), guard))

    ok = all(r["verdict"] == "OK" for r in results)
    return {
        "verdict": "OK" if ok else "BROKEN",
        "run_dir": str(run_dir), "arm": arm, "viewer": str(viewer),
        "n_entries": len(dicts), "vacant_id": meta["vacant_id"],
        "checks": results,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="收據牆頁面 vs vacant/logbook.py 對照")
    ap.add_argument("--run", default=str(DEFAULT_RUN))
    ap.add_argument("--arm", default="CONFORM")
    ap.add_argument("--viewer", default=str(VIEWER))
    ap.add_argument("--all", action="store_true",
                    help="跑 ALL_RUNS 裡的每一條鏈（g_r445 482 筆 ＋ g_r447 325 筆）")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    viewer = pathlib.Path(a.viewer)

    targets = ALL_RUNS if a.all else [(pathlib.Path(a.run), a.arm)]
    outs = []
    for run_dir, arm in targets:
        out = run(run_dir, arm, viewer)
        outs.append(out)
        if len(targets) > 1:
            print("=== %s / %s ===" % (run_dir.name, arm))
        for r in out["checks"]:
            print("[%-6s] %s  %s" % (r["verdict"], r["check"], r["msg"]))
        print("總判定：%s（%s，%d 筆）" % (out["verdict"], out["run_dir"], out["n_entries"]))

    ok = all(o["verdict"] == "OK" for o in outs)
    if len(outs) > 1:
        print("合計：%s —— %s"
              % ("OK" if ok else "BROKEN",
                 "、".join("%s %d 筆 %s"
                           % (pathlib.Path(o["run_dir"]).name, o["n_entries"], o["verdict"])
                           for o in outs)))
    payload = outs[0] if len(outs) == 1 else {
        "verdict": "OK" if ok else "BROKEN", "viewer": str(viewer), "runs": outs}
    if a.json:
        pathlib.Path(a.json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
