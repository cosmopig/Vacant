"""把記帳閘道裡的模型呼叫（完整輸入＋輸出）歸檔進實驗記錄。

## 為什麼要有這支

真模型實驗（E10/E11）的逐題結果在 `rows.jsonl`，但那只有「通過/沒通過」。
**模型當時實際看到什麼、回了什麼**在閘道那邊（lmstudio-monitor，port 8766）。
兩邊分開存，等於實驗紀錄少了最關鍵的一層：別人無法檢查我們餵了什麼進去。

這支把閘道的紀錄拉下來、和實驗對齊、落進同一個檔案庫，讓「這一題的模型
輸入輸出」變成可離線檢查的東西。

閘道 API 是唯讀的（它不會也不能呼叫 LLM），端點見
http://100.119.113.56:8766/api/llms.txt

## 紀律

  - 只拉、不改。閘道那邊仍是唯一真相來源；這裡是快照。
  - 落 JSONL，一筆一行，附閘道的 id 讓人可以回頭對。
  - 同時算出摘要（筆數/tokens/延遲/錯誤），寫進 index 的 catalog。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics as st
import urllib.request
from pathlib import Path

GW = "http://100.119.113.56:8766"


def fetch(path: str, timeout: int = 120) -> dict:
    with urllib.request.urlopen(f"{GW}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path,
                    help="輸出目錄（通常是該輪實驗記錄的目錄）")
    ap.add_argument("--date", required=True,
                    help="要歸檔的日期 YYYY-MM-DD（依本地時間）")
    a = ap.parse_args()

    day = dt.datetime.strptime(a.date, "%Y-%m-%d")
    since = int(day.timestamp())
    until = int((day + dt.timedelta(days=1)).timestamp())

    print(f"拉取 {a.date}（{since}–{until}）的呼叫紀錄…", flush=True)
    d = fetch(f"/api/requests?since={since}&until={until}"
              f"&include_bodies=true&limit=0")
    rows = d["rows"]
    # 只留真的打到模型的（其餘是閘道自己的 meta 呼叫）
    calls = [r for r in rows if r.get("model")]
    print(f"  總 {len(rows)} 筆，其中打到模型的 {len(calls)} 筆")

    a.out.mkdir(parents=True, exist_ok=True)
    jl = a.out / "model_calls.jsonl"
    with jl.open("w", encoding="utf-8") as f:
        for r in sorted(calls, key=lambda x: x["ts"]):
            r["iso"] = dt.datetime.fromtimestamp(r["ts"]).isoformat(timespec="seconds")
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 閘道把回應存成純文字，含 [reasoning] 與 [content] 兩段——
    # 連模型的推理過程都留著。這裡拆出來，讓後續分析不必重複解析。
    def split_resp(body: str) -> dict:
        if not isinstance(body, str):
            return {"reasoning": None, "content": None, "raw": True}
        rs = cs = None
        if "[reasoning]" in body:
            tail = body.split("[reasoning]", 1)[1]
            rs, _, rest = tail.partition("[content]")
            cs = rest
        elif "[content]" in body:
            cs = body.split("[content]", 1)[1]
        return {"reasoning": (rs or "").strip() or None,
                "content": (cs or "").strip() or None, "raw": False}

    n_reason = sum(1 for r in calls if split_resp(r.get("response_body") or "")["reasoning"])

    lat = [r["latency_ms"] for r in calls if r.get("latency_ms")]
    tok = [r.get("total_tokens") or 0 for r in calls]
    summary = {
        "來源": f"{GW}/api/requests（唯讀記帳閘道）",
        "日期": a.date,
        "筆數": len(calls),
        "模型": sorted({r["model"] for r in calls}),
        "機器": sorted({r["machine"] for r in calls if r.get("machine")}),
        "tokens": {"總計": sum(tok),
                   "prompt": sum((r.get("prompt_tokens") or 0) for r in calls),
                   "completion": sum((r.get("completion_tokens") or 0) for r in calls)},
        "延遲_ms": {"中位數": round(st.median(lat), 1) if lat else None,
                    "平均": round(st.mean(lat), 1) if lat else None,
                    "最大": round(max(lat), 1) if lat else None} if lat else None,
        "錯誤數": sum(1 for r in calls if r.get("error")),
        "含推理段的筆數": n_reason,
        "時間範圍": {"起": dt.datetime.fromtimestamp(min(r["ts"] for r in calls)).isoformat(timespec="seconds"),
                     "訖": dt.datetime.fromtimestamp(max(r["ts"] for r in calls)).isoformat(timespec="seconds")} if calls else None,
        "欄位說明": {
            "id": "閘道的流水號，可回頭用 /api/requests/{id} 對帳",
            "request_body": "送給模型的完整內容（含 messages）",
            "response_body": "模型回的完整內容。純文字，含 [reasoning] 與 [content] "
                             "兩段——推理過程也留著，不只有最終答案。",
            "latency_ms": "端到端延遲",
            "prompt_tokens / completion_tokens / total_tokens": "用量",
            "error": "非 null 代表這一筆失敗",
        },
        "註": "閘道是唯讀的，它不會也無法呼叫 LLM；這份是快照，"
              "真相來源仍是閘道本身。",
    }
    (a.out / "model_calls_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  寫出 {jl}（{jl.stat().st_size/1e6:.2f} MB）")
    print(f"  tokens {summary['tokens']['總計']:,}　"
          f"延遲中位數 {summary['延遲_ms']['中位數'] if summary['延遲_ms'] else '—'} ms　"
          f"錯誤 {summary['錯誤數']}")


if __name__ == "__main__":
    main()
