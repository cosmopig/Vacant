"""把四條流（兩批 × 四 shard）各自的 lifecycle 檔合成一份錄影。

規則（刻意最小）：
  · 每一行**原樣**搬過去（位元組不動，不重新序列化）；
  · 依 `ts_ms` 做 k 路合併（heapq.merge），同一個檔內的相對順序**保持不變**
    ⇒ 每個 run_id 只活在一個 shard 檔裡，它的 seq 仍然各自連續
    （`lifecycle.validate_stream` 的判準），整份檔的 ts 單調不減（電視契約 7）；
  · 不增、不刪、不改任何一筆；合併前後行數與逐行 sha256 的多重集合必須相等，否則不寫。

這不是「舊 run 目錄 → lifecycle」的轉換器：輸入全部是同一次 run_twin.py --events 當下寫的。

用法：python3 merge_lifecycle.py OUT.jsonl IN1.jsonl IN2.jsonl ...
"""
import collections
import hashlib
import heapq
import json
import pathlib
import sys


def lines_of(p):
    with open(p, "rb") as f:
        for raw in f:
            if raw.strip():
                if not raw.endswith(b"\n"):
                    raw += b"\n"
                yield json.loads(raw)["ts_ms"], raw


def main():
    out = pathlib.Path(sys.argv[1])
    ins = [pathlib.Path(p) for p in sys.argv[2:]]
    streams = [lines_of(p) for p in ins]
    merged = [raw for _, raw in heapq.merge(*streams, key=lambda t: t[0])]
    src = collections.Counter()
    for p in ins:
        for _, raw in lines_of(p):
            src[hashlib.sha256(raw).hexdigest()] += 1
    dst = collections.Counter(hashlib.sha256(r).hexdigest() for r in merged)
    if src != dst:
        raise SystemExit("合併前後的行集合不相等，不寫")
    ts = [json.loads(r)["ts_ms"] for r in merged]
    if any(a > b for a, b in zip(ts, ts[1:])):
        raise SystemExit("合併後 ts_ms 不單調（某個 shard 檔自己就不單調），不寫")
    out.write_bytes(b"".join(merged))
    print(f"✓ {len(merged)} 行 ← {len(ins)} 個檔 → {out}")


if __name__ == "__main__":
    main()
