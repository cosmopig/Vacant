"""twin/smoke_local_cloud — 本機端到端冒煙（舊 VM，不碰正式雲端、不碰 .102）：

本機起一個雲端（`vacant-world-cloud` 的 server.js，自訂 VENUE_TOKEN／PORT）→ `twinlink loop`（enclose=on、require_tier=B）
指向它 → 用 SYNTH 合成特質投兩張卡（A 正常跑完、B 在 working 時由「手機」撤回）→ 每秒記 `/api/status/:id`
的時間軸（stage／says 句數／review 條數／拍立得）→ 跑完查：stage 順序、says 含段 2 的 thought、review 帶四格 label、
拍立得 200、撤回後雲端與本機都刪乾淨 → 存 lifecycle＋sidecar → 關掉雲端與 loop。

用法（VM 上）：python3 smoke_local_cloud.py --cloud-dir <vacant-world-cloud> --out <dir> [--endpoint URL]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

SYNTH = {
    "A": "（SYNTH 合成特質，不是真人）說話慢、做事細，習慣把東西一件一件排好才安心；"
         "在意別人有沒有看見自己做的事，嘴上卻說不在意。遇到要決定的時候會先停一下。",
    "B": "（SYNTH 合成特質，不是真人）很快、愛熱鬧，哪裡聲音大就往哪裡走，"
         "走到了又想躲到旁邊安靜的角落。怕被看穿，也怕沒人看。",
}


#: 每張卡獨有的一句（撤回後殘留檢查用）。
MARK = {"A": "把東西一件一件排好才安心", "B": "哪裡聲音大就往哪裡走"}


def http(method, url, body=None, headers=None, timeout=15):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--endpoint", default="http://100.119.113.56:5500/v1")
    ap.add_argument("--port", type=int, default=3377)
    ap.add_argument("--work", default="/tmp/vs")
    ap.add_argument("--node", default="node")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(a.work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    token = "smoke-" + os.urandom(6).hex()
    base = f"http://127.0.0.1:{a.port}"
    procs: list[subprocess.Popen] = []
    rep: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "port": a.port}
    try:
        cenv = {**os.environ, "PORT": str(a.port), "VENUE_TOKEN": token, "DATA_DIR": str(work / "clouddata"),
                "RATE_WINDOW_MS": "100", "WITHDRAW_WINDOW_MS": "100"}
        procs.append(subprocess.Popen([a.node, "server.js"], cwd=a.cloud_dir, env=cenv,
                                      stdout=open(work / "cloud.log", "wb"), stderr=subprocess.STDOUT))
        for _ in range(50):
            try:
                if http("GET", base + "/api/status/none")[0] in (404, 400):
                    break
            except Exception:                                   # noqa: BLE001
                time.sleep(0.2)
        db = work / "twinstore.sqlite3"
        live = work / "live.jsonl"
        loop = subprocess.Popen(
            [sys.executable, "ops/exhibit/twin/twinlink.py", "--db", str(db), "--init", "loop", "--cloud", base,
             "--token", token, "--endpoint", a.endpoint, "--interval", "3", "--engine", "agent",
             "--parallel", "2", "--enclose", "on", "--require-tier", "B", "--events", str(live)],
            cwd=str(REPO), stdout=open(work / "loop.log", "wb"), stderr=subprocess.STDOUT)
        procs.append(loop)

        ids, codes = {}, {}
        for k in ("A", "B"):
            st, r = http("POST", base + "/api/submit", {"card_text": SYNTH[k], "self_attested": True, "age_gate": True})
            assert st == 200, (st, r)
            ids[k], codes[k] = r["id"], r["withdraw_code"]
            time.sleep(0.5)
        rep["ids_hash"] = {k: v[:8] for k, v in ids.items()}

        timeline = {k: [] for k in ids}
        last = {k: None for k in ids}
        t0 = time.time()
        withdrawn_at = None
        final = {}
        while time.time() - t0 < 900:
            for k, i in ids.items():
                st, s = http("GET", f"{base}/api/status/{i}")
                if st != 200:
                    continue
                snap = (s.get("status"), s.get("stage"), len(s.get("says") or []), len(s.get("steps") or []),
                        len(s.get("review") or []), bool(s.get("polaroid_url")), bool(s.get("receipt_url")))
                if snap != last[k]:
                    last[k] = snap
                    timeline[k].append({"t": round(time.time() - t0, 1), "status": snap[0], "stage": snap[1],
                                        "says": snap[2], "steps": snap[3], "review": snap[4],
                                        "polaroid": snap[5], "receipt": snap[6]})
                if k == "A" and snap[0] == "done" and snap[1] == "done":
                    final["A"] = s
                if k == "B" and withdrawn_at is None and snap[1] == "working" and snap[2] >= 3:
                    st2, r2 = http("POST", base + "/api/withdraw", {"code": codes["B"]})
                    withdrawn_at = round(time.time() - t0, 1)
                    rep["withdraw_B"] = {"http": st2, "at_s": withdrawn_at}
                if k == "B" and snap[0] == "withdrawn":
                    final["B"] = s
            if "A" in final and "B" in final and time.time() - t0 > (withdrawn_at or 0) + 20:
                break
            time.sleep(1)
        rep["timeline"] = timeline
        A = final.get("A") or {}
        rep["A"] = {"says": A.get("says"), "review": A.get("review"),
                    "outcome": A.get("outcome"), "judgment": A.get("judgment")}
        if A.get("polaroid_url"):
            req = urllib.request.Request(base + A["polaroid_url"])
            with urllib.request.urlopen(req, timeout=15) as r:
                rep["A"]["polaroid_http"], rep["A"]["polaroid_bytes"] = r.status, len(r.read())
        # 撤回後雲端那一份：沒有內容、拍立得／收據 404
        B = final.get("B") or {}
        rep["B_cloud"] = {"status": B.get("status"), "has_says": "says" in B, "has_steps": "steps" in B,
                          "has_review": "review" in B, "has_polaroid": "polaroid_url" in B}
        for kind in ("polaroid", "receipt", "card"):
            try:
                rep["B_cloud"][kind + "_http"] = http("GET", f"{base}/api/{kind}/{ids['B']}")[0]
            except Exception as e:                              # noqa: BLE001
                rep["B_cloud"][kind + "_http"] = repr(e)[:60]
        time.sleep(8)     # 讓 loop 再走一輪（本機收到撤回、做抹除）
    finally:
        for p in reversed(procs):
            try:
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=10)
            except Exception:                                   # noqa: BLE001
                p.kill()
    # ── 本機：撤回的人刪乾淨了嗎 ──
    from ops.exhibit.twin import twinagent
    from ops.exhibit.twin.twinstore import TwinStore
    st = TwinStore(db)
    work_root = twinagent.default_work_root(db)
    for k, i in ids.items():
        cur = st.current(i) or {}
        rep.setdefault("local", {})[k] = {
            "status": cur.get("status"), "card_available": cur.get("card_available"),
            "run_artifacts_present": twinagent.run_artifacts_present(work_root, i)}
    st.close()
    # 撤回後的殘留：用**只有那一張卡才有**的一句當標記；A（沒撤回）的標記當正控制（量得到才算數）。
    marks = {k: MARK[k].encode("utf-8") for k in MARK}

    def _scan(root: pathlib.Path, skip: tuple[str, ...] = ()) -> dict:
        blob = b"".join(p.read_bytes() for p in sorted(root.rglob("*"))
                        if p.is_file() and not any(sk in str(p) for sk in skip))
        return {k: (m in blob) for k, m in marks.items()}
    rep["residue_local"] = _scan(work, skip=("clouddata", "cloud.log"))
    rep["residue_cloud_data"] = _scan(work / "clouddata") if (work / "clouddata").exists() else {}
    ev_blob = b"".join(f.read_bytes() for f in (live, live.with_name("live.sidecar.jsonl")) if f.exists())
    rep["residue_event_streams"] = {k: (m in ev_blob) for k, m in marks.items()}
    for f in (live, live.with_name("live.sidecar.jsonl")):
        if f.exists():
            shutil.copyfile(f, out / f.name)
    (out / "loop.log").write_bytes((work / "loop.log").read_bytes()[-20000:])
    (out / "smoke_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({k: rep[k] for k in ("local", "B_cloud", "withdraw_B", "residue_local", "residue_cloud_data", "residue_event_streams") if k in rep}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
