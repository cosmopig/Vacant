"""稽核端：獨立驗一條收據鏈。

這支不讀 runs/、不讀 cache、不跑模型——只拿鏈檔 ＋ 簽章公鑰，
重算每一筆的 hash、驗每一筆的簽章、檢查 seq/prev_hash 連續，
然後把「誰交付了什麼、誰被拒絕、每題花了幾次呼叫」重新數一遍。

觀眾在展場看到的那張收據，就是這支能重算出來的東西。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from vacant.identity import PublicIdentity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402


def main(d: str) -> int:
    p = pathlib.Path(d)
    lb = Logbook.load(p / "chain.ndjson")
    signer = json.loads((p / "signer.json").read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(signer["vacant_id"], signer["pub"])
    ok = lb.verify_chain(who)
    print(f"鏈長 {len(lb)} 筆；stream_id={lb.stream_id()[:16]}… head={lb.head()[:16]}…")
    print(f"簽章＋hash-chain 全鏈驗證：{'通過' if ok else '失敗'}")
    if lb.stream_id() != signer["stream_id"] or lb.head() != signer["head"]:
        print("！ signer.json 記的 stream_id/head 與鏈不符")
        ok = False
    c = collections.Counter(e.type for e in lb.entries)
    deliv = [e for e in lb.entries if e.type == "delivery"]
    refus = [e for e in lb.entries if e.type == "refusal"]
    att = [e for e in lb.entries if e.type == "attempt"]
    calls = sum(e.payload["calls_used"] for e in deliv + refus)
    tasks = len({e.payload["task_id"] for e in lb.entries if e.type == "request"})
    by_worker = collections.Counter(e.payload["worker"] for e in deliv)
    print(f"事件別：{dict(c)}")
    print(f"題數 {tasks}；交付 {len(deliv)}；拒絕 {len(refus)}；"
          f"具名嘗試 {len(att)} 次 ＝ 模型呼叫 {calls} 次（{calls/tasks:.2f} 次／題）")
    print(f"交付內附具名轉接器：{sum(1 for e in deliv if e.payload['adapter_attached'])}")
    print("交付數（依 worker）：" + ", ".join(f"{k}={v}" for k, v in by_worker.most_common()))
    bad = [e.payload["task_id"] for e in att
           if e.payload["accepted"] and e.payload["asserts_passed"] != e.payload["asserts_total"]]
    print(f"「宣稱通過但逐條證據不足」的嘗試：{len(bad)}（應為 0）")
    ex = refus[0].payload if refus else None
    if ex:
        print("\n拒絕收據範例：", json.dumps(ex, ensure_ascii=False)[:600])
    return 0 if ok and not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
