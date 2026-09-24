"""twin/smoke_vm — **VM 跑法**的冒煙：在 vacant-dev 上用 systemd 起整條分身線，合成特質真跑一次。

## 這支在架構裡承重什麼

人類裁決（2026-09-24）：分身迴圈跑在 VM（vacant-dev），不在 1003 Windows 上；
run 產物展期內保留、展期結束即刪。這一支把 START.md「VM 跑法」那一節**真的跑一次**：

1. 量具先證明量得動（pi、bwrap、LM Studio、磁碟）；
2. `probe_twin_enclosure.py`：pi 行程本身被圍住了嗎（**負控制先跑**）；
3. 用 **systemd 暫態 unit**（`systemd-run --collect`，停了就沒有，不留常駐服務）起兩支：
   `exhibit_boot.sh --lan --bind-all`（serve_twin＋靜態站＋唯讀端點）與
   `twin_loop.sh --rounds 1`（一位合成分身、`VACANT_TWIN_ENCLOSE=on`、`REQUIRE_TIER=B`）。
   兩支讀**同一份** `twin-paths.env`（正式布展時是 `/etc/vacant/twin-paths.env`）；
4. 停在一個關卡等 Mac 那一側從 **1003** 敲 VM 的三個埠（`smoke_vm.sh` 做）；
5. 磁碟水位閘門真的擋得住（門檻調到天花板 ⇒ `held_for_disk=1`）；
6. `close_exhibition.py`：dry-run 一個檔都不動 ⇒ 真刪 ⇒ 抹除證明 ⇒ 收據再驗一次；
7. 掃事件檔／loop 的 journal 裡有沒有合成特質原文（設計上應該沒有）。

⚠ **特質是合成的**，不是任何真人——所以它的產出可以進版控當證據。
⚠ 埠用 18420／18899／18901：vacant-dev 上 8420／8899 已經有別人的展件在跑，**不去動它**。
⚠ 這一支**不裝任何常駐服務**；收尾停掉兩支暫態 unit（`smoke_vm.sh` 再確認一次）。

用法（由 `smoke_vm.sh` 在 VM 上呼叫）：
    python3 ops/exhibit/twin/smoke_vm.py --base /var/tmp/vacant_twin_vm_smoke
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SYN = [("SYN-vm-20260924-a",
        {"need": "想把陽台的植物照顧好", "vibe": "細心、有點健忘、喜歡記錄",
         "first_line": "先幫薄荷澆水。"},
        "（合成的特質，不是真人）我在陽台種了十幾盆香草，常常忘記哪一盆什麼時候澆過水，"
        "想要一個不用手機也看得懂的照顧方法。"),
       ("SYN-vm-20260924-b",
        {"need": "想整理舊信件", "vibe": "念舊、慢熱", "first_line": "那一疊信還在抽屜裡。"},
        "（合成的特質，不是真人）抽屜裡有一疊國中時的信，想整理但一直拖。")]
UNIT_EXHIBIT = "vacant-smoke-exhibit"
UNIT_LOOP = "vacant-smoke-loop"
PORTS = {"tv": 18420, "twin": 18899, "store": 18901}
EXHIBITION = "smoke-20260924"


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)


def seed(db: pathlib.Path, i: int) -> str:
    from ops.exhibit.twin import twinvault
    from ops.exhibit.twin.twinstore import KIND_SUBMITTED, TwinStore
    sid, card, text = SYN[i]
    st = TwinStore(db)
    try:
        payload, secs = st.vault.seal_card(sid, card, text, ts=int(time.time() * 1000))
        twinvault.append_sealed(st, KIND_SUBMITTED, sid, payload, secs,
                                source="smoke:synthetic", what="card")
    finally:
        st.close()
    return sid


def tree_digest(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def du(p: pathlib.Path) -> int:
    return sum(q.stat().st_size for q in p.rglob("*") if q.is_file()) if p.exists() else 0


def get(url: str) -> tuple[int | None, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except Exception as e:                                   # noqa: BLE001
        return None, f"{type(e).__name__}: {e}".encode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--endpoint", default="http://192.168.76.1:1234/v1")
    ap.add_argument("--node", default=str(pathlib.Path.home()
                                          / ".local/opt/node-v22.23.2-linux-x64"))
    ap.add_argument("--hm", default=str(pathlib.Path.home() / "vacant" / "vacant_hm"))
    ap.add_argument("--wait-1003-s", type=float, default=240)
    a = ap.parse_args(argv)
    base = pathlib.Path(a.base)
    state, ev = base / "state", base / "evidence"
    state.mkdir(parents=True, exist_ok=True)
    ev.mkdir(parents=True, exist_ok=True)
    pi = pathlib.Path(a.node) / "bin" / "pi"
    db = state / "twinstore.sqlite3"
    events = state / "twin_lifecycle.jsonl"
    work_root = state / "twinstore.agentruns"
    rep: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "synthetic": True, "ports": PORTS, "steps": {}}
    S = rep["steps"]

    def save():
        (ev / "smoke_vm_report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        # ── 0. 量具先證明量得動 ────────────────────────────────────────────
        code, body = get(a.endpoint.rstrip("/") + "/models")
        S["0_gauges"] = {
            "hostname": sh(["hostname"]).stdout.strip(),
            "pi_version": (lambda r: (r.stdout + r.stderr).strip())(sh(
                [str(pi), "--version"],
                env=dict(os.environ, PATH=f"{a.node}/bin:" + os.environ.get("PATH", "")))),
            "bwrap": shutil.which("bwrap"),
            "enclosure_probe": json.loads(sh([sys.executable, str(TWIN / "twinenclose.py"),
                                              "--probe"]).stdout or "{}"),
            "lmstudio_models_http": code,
            "lmstudio_has_gemma": b"gemma" in body,
            "df_root_free_bytes": shutil.disk_usage("/").free,
        }
        save()

        # ── 1. pi 行程本身被圍住了嗎（負控制先跑）────────────────────────
        env = dict(os.environ, PATH=f"{a.node}/bin:" + os.environ.get("PATH", ""))
        r = sh([sys.executable, str(TWIN / "probe_twin_enclosure.py"), "--out", str(ev)],
               env=env, timeout=600)
        S["1_probe"] = {"rc": r.returncode, "stdout_tail": r.stdout[-800:],
                        "stderr_tail": r.stderr[-800:]}
        save()

        # ── 2. 路徑檔（正式布展時就是 /etc/vacant/twin-paths.env 的內容）────
        paths_env = state / "twin-paths.env"
        paths_env.write_text("\n".join([
            f"VACANT_TWIN_DB={db}",
            f"VACANT_EVENTS={events}",
            f"VACANT_TWIN_AGENTRUNS={work_root}",
            f"VACANT_TWIN_OUT={state / 'visitors.json'}",
            f"VACANT_TWIN_PI={pi}",
            "VACANT_TWIN_ENCLOSE=on",
            "VACANT_TWIN_REQUIRE_TIER=B",
            "VACANT_TWIN_MIN_FREE_MB=2048",
            "VACANT_TWIN_PARALLEL=1",
            f"VACANT_TWIN_ENDPOINT={a.endpoint}",
            "VACANT_EXHIBIT_BIND_ALL=1",
            f"VACANT_HM={a.hm}",
        ]) + "\n", encoding="utf-8")
        secret_env = state / "twin.env"
        # 冒煙不接公網郵箱：雲端指到一個一定連不上的位址（ingest 記 ingest_gap，不致命）
        secret_env.write_text("VACANT_TWIN_CLOUD_TOKEN=smoke-not-a-real-token\n"
                              "VACANT_TWIN_CLOUD=http://127.0.0.1:9\n"
                              "VACANT_TWIN_INTERVAL=5\n", encoding="utf-8")
        os.chmod(secret_env, 0o600)
        sid_a = seed(db, 0)
        events.touch()

        # ── 3. systemd 暫態 unit（停了就沒有）─────────────────────────────
        common = ["sudo", "-n", "systemd-run", "--collect", "--no-block",
                  "-p", f"User={os.environ.get('USER', 'user1')}",
                  "-p", f"EnvironmentFile={paths_env}",
                  "-p", f"WorkingDirectory={REPO}", "-p", "KillMode=control-group",
                  "--setenv=PYTHONUNBUFFERED=1"]
        r1 = sh(common + ["--unit", UNIT_EXHIBIT,
                          str(TWIN / "exhibit_boot.sh"), "--lan", "--dwell", "30",
                          "--tv-port", str(PORTS["tv"]), "--twin-port", str(PORTS["twin"]),
                          "--store-port", str(PORTS["store"]), "--no-twin-loop",
                          "--live", str(events)])
        r2 = sh(common + ["-p", f"EnvironmentFile={secret_env}", "--unit", UNIT_LOOP,
                          str(TWIN / "twin_loop.sh"), "--rounds", "1"])
        S["3_units_started"] = {"exhibit_rc": r1.returncode, "exhibit_err": r1.stderr[-300:],
                                "loop_rc": r2.returncode, "loop_err": r2.stderr[-300:]}
        save()
        t0 = time.time()
        while time.time() - t0 < 600:
            st = sh(["systemctl", "is-active", UNIT_LOOP]).stdout.strip()
            if st not in ("active", "activating"):
                break
            time.sleep(3)
        S["3_loop_wall_s"] = round(time.time() - t0, 1)
        jl = sh(["sudo", "-n", "journalctl", "-u", UNIT_LOOP, "--no-pager", "-o", "cat"]).stdout
        je = sh(["sudo", "-n", "journalctl", "-u", UNIT_EXHIBIT, "--no-pager", "-o", "cat"]).stdout
        (ev / "journal_loop.txt").write_text(jl.replace("smoke-not-a-real-token", "***"),
                                             encoding="utf-8")
        (ev / "journal_exhibit.txt").write_text(je, encoding="utf-8")

        from ops.exhibit.twin import twinagent
        from ops.exhibit.twin.twinstore import TwinStore
        from vacant_network.vrun import lifecycle
        from vacant_network.vrun import verify_receipts as vrr
        st = TwinStore(db)
        tw = (st.current(sid_a) or {}).get("twin") or {}
        st.close()
        ws, rd = twinagent.paths_for(work_root, sid_a)
        door = work_root / "doors" / twinagent.slug_for(sid_a)
        evs = lifecycle.read(events)
        S["4_twin"] = {
            **{k: tw.get(k) for k in (
                "engine", "degrade_kind", "decision", "lines_from", "stop_reason",
                "accepted", "requests_seen", "count_semantics", "tier", "enclosed",
                "enclosure_applied", "door_calls", "twin_id", "run_id", "verdict_hash",
                "latency_ms")},
            "n_artifacts": len(tw.get("artifacts") or []),
            "artifact_names": [x.get("name") for x in (tw.get("artifacts") or [])],
            "receipts": [{k: x.get(k) for k in ("verdict", "tier", "mediated")}
                         for x in vrr.verify_run(rd)],
            "lifecycle": {"n": len(evs), "types": [e["type"] for e in evs],
                          "validate_stream": lifecycle.validate_stream(evs)},
            "bytes_on_disk": {"run_dir": du(rd), "door_journal": du(door),
                              "workspace": du(ws),
                              "wire_RUN-ON": du(rd / "wire_RUN-ON")},
        }
        shutil.copyfile(events, ev / "lifecycle.jsonl")
        save()

        # ── 4. 關卡：Mac 那一側從 1003 敲 VM 的三個埠 ──────────────────────
        #   先等電視那一支真的起來（exhibit_boot 自己會等 20 秒再判死）
        t0 = time.time()
        while time.time() - t0 < 90 and get(f"http://127.0.0.1:{PORTS['twin']}/state")[0] != 200:
            time.sleep(2)
        S["5_exhibit_up_after_s"] = round(time.time() - t0, 1)
        local = {n: get(u) for n, u in {
            "state": f"http://127.0.0.1:{PORTS['twin']}/state",
            "visitors": f"http://127.0.0.1:{PORTS['store']}/visitors.json"}.items()}
        S["5_local"] = {n: {"http": c, "bytes": len(b)} for n, (c, b) in local.items()}
        try:
            vis = json.loads(local["visitors"][1])
            S["5_local"]["visitors_intake"] = vis.get("intake")
            S["5_local"]["visitors_people"] = len(vis.get("people") or [])
        except ValueError:
            pass
        (base / "READY_FOR_1003").write_text("1")
        save()
        t0 = time.time()
        while time.time() - t0 < a.wait_1003_s and not (base / "DONE_1003").exists():
            time.sleep(1)
        S["5_1003_barrier"] = {"done": (base / "DONE_1003").exists(),
                               "waited_s": round(time.time() - t0, 1)}

        # ── 5. 磁碟水位閘門：門檻調到天花板 ⇒ 不收新分身 ─────────────────
        sid_b = seed(db, 1)
        genv = dict(os.environ, PATH=f"{a.node}/bin:" + os.environ.get("PATH", ""),
                    VACANT_TWIN_MIN_FREE_MB="99999999", VACANT_TWIN_PI=str(pi),
                    VACANT_TWIN_AGENTRUNS=str(work_root), VACANT_EVENTS=str(events))
        g = sh([sys.executable, str(TWIN / "twinlink.py"), "--db", str(db), "generate",
                "--endpoint", a.endpoint, "--engine", "agent", "--enclose", "on",
                "--require-tier", "B", "--parallel", "1"], env=genv, timeout=300)
        try:
            gr = json.loads(g.stdout)
        except ValueError:
            gr = {"raw": g.stdout[-500:]}
        v = sh([sys.executable, str(TWIN / "twinlink.py"), "--db", str(db), "view"], env=genv)
        try:
            intake_view = json.loads(v.stdout).get("intake")
        except ValueError:
            intake_view = None
        st = TwinStore(db)
        b_status = (st.current(sid_b) or {}).get("status")
        pending = sid_b in st.pending("generated")
        st.close()
        S["6_disk_gate"] = {"generate_rc": g.returncode,
                            "held_for_disk": gr.get("held_for_disk"),
                            "submitted": gr.get("submitted"),
                            "intake_in_report": gr.get("intake"),
                            "stderr_warning": [ln for ln in g.stderr.splitlines()
                                               if "intake_paused" in ln][:1],
                            "view_intake": intake_view,
                            "held_person_still_pending": pending,
                            "held_person_status": b_status,
                            "negative_control": ("同一條路徑、門檻 2048 MB 的那一輪（第 3 步）"
                                                 "真的起了 run：submitted=1")}
        # 撤回那位沒跑過的人（閉展時要被正確略過）
        from ops.exhibit.twin import twinlink
        st = TwinStore(db)
        os.environ["VACANT_TWIN_AGENTRUNS"] = str(work_root)
        w = twinlink.withdraw(st, sid_b, reason="smoke:withdraw")
        st.close()
        S["6_withdraw_b"] = {k: w.get(k) for k in ("ok", "fully_erased",
                                                  "run_artifacts_erased")}
        save()

        # ── 6. 停掉電視那一支（閉展是在展場關掉之後做的）───────────────────
        sh(["sudo", "-n", "systemctl", "stop", UNIT_EXHIBIT])

        # ── 7. 閉展：dry-run 一個檔都不動 ⇒ 真刪 ⇒ 抹除證明 ⇒ 收據再驗 ──────
        cenv = dict(os.environ, VACANT_TWIN_AGENTRUNS=str(work_root))
        before = tree_digest(work_root)
        d = sh([sys.executable, str(TWIN / "close_exhibition.py"), "--db", str(db),
                "--exhibition", EXHIBITION, "--dry-run", "--events", str(events)], env=cenv)
        after = tree_digest(work_root)
        dsum = json.loads(d.stdout[: d.stdout.index("\n}") + 2]) if "\n}" in d.stdout else {}
        c = sh([sys.executable, str(TWIN / "close_exhibition.py"), "--db", str(db),
                "--exhibition", EXHIBITION, "--yes-close", EXHIBITION,
                "--events", str(events), "--events", str(ev / "journal_loop.txt")], env=cenv)
        csum = json.loads(c.stdout) if c.stdout.strip().startswith("{") else {"raw": c.stdout}
        proof = state / f"twinstore.close_{EXHIBITION}.jsonl"
        if proof.is_file():
            shutil.copyfile(proof, ev / "close_proof.jsonl")
        left = sorted(str(p.relative_to(work_root)) for p in work_root.rglob("*")
                      if p.is_file())
        syn_texts = [t for _, _, t in SYN] + [c2["need"] for _, c2, _ in SYN]
        hits = {}
        for label, root in (("work_root", work_root), ("events", events),
                            ("journal_loop", ev / "journal_loop.txt"),
                            ("journal_exhibit", ev / "journal_exhibit.txt")):
            files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
            hits[label] = sum(1 for f in files for t in syn_texts
                              if t.encode("utf-8") in f.read_bytes())
        S["7_close"] = {
            "dry_run_rc": d.returncode, "dry_run_changed_nothing": before == after,
            "dry_run_would_erase_files": dsum.get("would_erase_files"),
            "dry_run_would_erase_bytes": dsum.get("would_erase_bytes"),
            "close_rc": c.returncode,
            "summary": {k: csum.get(k) for k in (
                "clean", "actions", "files_erased", "bytes_erased", "problems", "residue",
                "receipts_verified", "receipts_failed", "twinstore_chain",
                "content_scan", "vault_plaintext_subjects")},
            "work_root_files_left": left,
            "receipts_after_close": [x.get("verdict") for x in vrr.verify_run(rd)],
            "synthetic_text_hits": hits,
            "note": ("hits 掃的是合成特質原文與需求欄。events／journal 命中 0 ＝設計上不帶內容"
                     "那一條在真跑上量到了；work_root 命中 0 ＝閉展刪乾淨了"),
        }
        save()
    finally:
        for u in (UNIT_LOOP, UNIT_EXHIBIT):
            sh(["sudo", "-n", "systemctl", "stop", u])
        units = sh(["systemctl", "list-units", "--all", "--no-legend", "vacant-smoke-*"]).stdout
        rep["units_left_after_stop"] = [ln for ln in units.splitlines() if ln.strip()]
        save()
    print(json.dumps({"saved": str(ev / "smoke_vm_report.json")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
