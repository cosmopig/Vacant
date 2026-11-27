#!/usr/bin/env python3
"""credscan — 掃描 redo 執行根目錄（每個 attempt 的工作區與 logs）有沒有像憑證的字串。

比對：(1) Devin 認證檔裡的值（只在記憶體比對，不印出）；(2) `sk-[A-Za-z0-9]{20,}`；(3) `Bearer\\s+[A-Za-z0-9._\\-]{20,}`；
(4) 長 base64（≥60 字元的 [A-Za-z0-9+/=] 連續字串，且不在已知良性清單：sha256 十六進位長度 64 不算 base64 命中）。
輸出 JSON：每個命中只記檔案、規則、前 4 字元；不記值。**不讀、不複製、不更新憑證檔以外的任何東西。**
Usage: credscan.py <run root> [--out FILE]
"""
import argparse
import json
import pathlib
import re

CRED = pathlib.Path("/root/.local/share/devin/credentials.toml")
RULES = {"sk": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
         "b64": re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{60,}={0,2}(?![A-Za-z0-9+/=])")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out")
    a = ap.parse_args()
    vals = []
    try:
        vals = re.findall(r"[A-Za-z0-9_\-\.=+/]{20,}", CRED.read_text())
    except OSError:
        pass
    hits, n = [], 0
    for f in pathlib.Path(a.root).rglob("*"):
        if not f.is_file() or f.stat().st_size > 8_000_000:
            continue
        try:
            t = f.read_bytes().decode("utf-8", "replace")
        except OSError:
            continue
        n += 1
        for v in vals:
            if v in t:
                hits.append({"file": str(f), "rule": "devin_credential_value", "head": v[:4]})
        for name, rx in RULES.items():
            for m in rx.finditer(t):
                g = m.group(0)
                if name == "b64" and m.start() > 0 and t[m.start() - 1] in "/-_.:":   # 路徑／UUID 片段（例如系統提示裡的 skill 快取路徑）
                    continue
                if name == "b64" and (re.fullmatch(r"[0-9a-f/]+", g) or re.fullmatch(r"n?[01]+", g) or "/" in g and g.count("/") > 3):
                    continue
                hits.append({"file": str(f), "rule": name, "head": g[:4]})
                break
    res = {"files_scanned": n, "hits": len(hits), "detail": hits[:200]}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: res[k] for k in ("files_scanned", "hits")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
