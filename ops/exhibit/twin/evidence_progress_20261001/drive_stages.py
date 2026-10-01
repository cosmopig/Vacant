"""手機即時進度——每個 stage 的手機截圖（2026-10-01，PROC4 線 A）。

起**真的**雲端（`vacant-world-cloud` 的 node 伺服器，本機埠），投一張卡，
用**真的** `twinprogress.ProgressReporter` 對一個手工放檔的 run 目錄推進度
（檔案長相與 launcher／pi 寫的一模一樣：agent_stdout.log、twin_steps.ndjson、
visible_*.json、_frozen_*、run_*.json），再用 Chrome（手機視窗 390x844）開
`/?id=<id>` 截圖。

⚠ 分身說的話、特質、審查句**全是合成的**，每一句都以 `SYNTH：` 開頭——
這份證據驗的是「手機會不會跟著階段換畫面」，不是模型說了什麼。

用法：
  python ops/exhibit/twin/evidence_progress_20261001/drive_stages.py \
      --cloud ../vacant-world-cloud-wt-p4a --out <截圖目錄>
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from ops.exhibit.twin import twinagent, twinlink, twinprogress  # noqa: E402


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def say_log(path, items):
    rows = [{"type": "turn_start"}]
    for k, (text, ntools) in enumerate(items):
        content = ([{"type": "text", "text": text}] if text else []) + \
            [{"type": "toolCall", "arguments": {"path": "x.md"}}] * ntools
        rows.append({"type": "message_end", "message": {"role": "assistant", "content": content,
                                                         "timestamp": 1790000000000 + k}})
        rows.append({"type": "turn_start"})
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def steps_log(path, rows):
    path.write_text("".join(json.dumps({"seq": i, "tool": t, "path": p, "bytes": b, "ok": True,
                                         "ts_ms": 1}) + "\n" for i, (t, p, b) in enumerate(rows, 1)),
                    encoding="utf-8")


def visible(rd, name, cases):
    res = {"all_pass": all(c[1] for c in cases), "passed": sum(c[1] for c in cases), "total": len(cases),
           "files": [{"file": "test_review.py", "cases": [
               {"case": c, "ok": ok, "kind": "assert", "message": m} for c, ok, m in cases]}]}
    (rd / name).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cloud = pathlib.Path(a.cloud).resolve()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="progress_drive_"))
    port, token = free_port(), "drive-token"
    proc = subprocess.Popen(["node", "server.js"], cwd=str(cloud), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            env={**os.environ, "PORT": str(port), "VENUE_TOKEN": token,
                                 "DATA_DIR": str(tmp / "cd"), "RATE_WINDOW_MS": "5"})
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            twinlink._http_json(base + "/api/status/nope", timeout=1)
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) == 404:
                break
            time.sleep(0.1)
    log = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome")
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                 is_mobile=True, has_touch=True)
            pg = ctx.new_page()

            def submit(tag):
                st, sub = twinlink._http_json(base + "/api/submit", {
                    "card_text": f"需求：SYNTH：{tag}", "self_attested": True, "age_gate": True})
                assert st == 200, sub
                return sub["id"]

            def shot(name, sid, wait=3.2):
                pg.goto(f"{base}/?id={sid}")
                time.sleep(wait)
                pg.screenshot(path=str(out / name))
                d = twinlink._http_json(f"{base}/api/status/{sid}")[1]
                log.append({"shot": name, "status": d.get("status"), "stage": d.get("stage"),
                            "queue_position": (d.get("queue") or {}).get("position"),
                            "title": pg.inner_text("#p5title"), "qpos": pg.inner_text("#queuepos"),
                            "procWaitTitle": pg.inner_text("#procWaitTitle"),
                            "lines": pg.eval_on_selector_all("#procWaitList li", "e=>e.map(x=>x.textContent)")})
                print(json.dumps(log[-1], ensure_ascii=False))

            sid = submit("before")
            shot("0_before_fix_queued_position1.png", sid)          # 卡住的原樣（沒人推進度）

            wr = tmp / "agentruns"
            ws, rd = twinagent.paths_for(wr, sid)
            rep = twinprogress.ProgressReporter(base, token, wr, min_interval_s=0.0)
            rep.track(sid, [])
            rep.tick_once()
            shot("1_claimed.png", sid)

            rd.mkdir(parents=True)
            rep.tick_once()
            shot("2_forming.png", sid)

            say_log(rd / twinagent.AGENT_STDOUT_NAME,
                    [("SYNTH：我想先看看自己房間裡有什麼。", 1),
                     ("SYNTH：先讀一下你的特質，再決定做什麼。", 1)])
            steps_log(rd / twinagent.STEP_LOG_NAME, [("ws_list", None, None), ("ws_list", None, None),
                                                      ("ws_read", "TRAITS.md", 312)])
            rep.tick_once()
            shot("3_working_says.png", sid)

            # 沒有 says、只有步驟：連續相同的步驟行要合併成 ×2
            shutil.move(str(rd / twinagent.AGENT_STDOUT_NAME), str(tmp / "stdout.bak"))
            (rd / twinagent.AGENT_STDOUT_NAME).write_text(
                json.dumps({"type": "turn_start"}) + "\n", encoding="utf-8")
            rep.tick_once()
            shot("3b_working_steps_folded.png", sid)
            shutil.move(str(tmp / "stdout.bak"), str(rd / twinagent.AGENT_STDOUT_NAME))

            (rd / twinprogress.SUITE_DIRNAME).mkdir()
            fz = rd / "_frozen_on"; fz.mkdir()
            now = time.time()
            for f in (rd / twinagent.AGENT_STDOUT_NAME, rd / twinagent.STEP_LOG_NAME):
                os.utime(f, (now - 9, now - 9))
            os.utime(fz, (now, now))
            visible(rd, "visible_on.json", [("test_r1_plan", True, ""),
                                             ("test_r2_grounded", True, ""),
                                             ("test_r4_matches", False, "SYNTH：成品跟決定對不上")])
            rep.tick_once()
            shot("4_reviewing_attempt1_fail.png", sid)

            # 重改：agent 又動手（比凍結新）→ working，再審一次
            os.utime(rd / twinagent.AGENT_STDOUT_NAME, (now + 5, now + 5))
            say_log(rd / twinagent.AGENT_STDOUT_NAME,
                    [("SYNTH：我想先看看自己房間裡有什麼。", 1),
                     ("SYNTH：先讀一下你的特質，再決定做什麼。", 1),
                     ("SYNTH：被退回了，我把成品改成跟決定對得上。", 1)])
            os.utime(rd / twinagent.AGENT_STDOUT_NAME, (now + 5, now + 5))
            rep.tick_once()
            shot("5_revising_back_to_working.png", sid)

            fz2 = rd / "_frozen_on_a2"; fz2.mkdir(); os.utime(fz2, (now + 9, now + 9))
            visible(rd, "visible_on_a2.json", [("test_r1_plan", True, ""),
                                                ("test_r2_grounded", True, ""),
                                                ("test_r4_matches", True, "")])
            rep.tick_once()
            shot("6_reviewing_attempt2_pass.png", sid)

            (rd / "run_on.json").write_text("{}", encoding="utf-8")
            rep.tick_once()
            shot("7_done_wrapping_up.png", sid)
            br.close()
    finally:
        proc.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    (out / "stages.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
