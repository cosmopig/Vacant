#!/usr/bin/env python3
"""Colab 帳號預算看門 v2（2026-11-24，W3-5 JS 重跑 VOID 的根因 4）。取代 colab2_budget_watch.py。

v1 只看「要保護的那一批」：那批取回後看門就退出；另一批取回失敗（keepalive 刻意留著 session 等人工檢查）之後
就沒有任何東西會關它，VM 空燒到帳號餘額歸零。v2：

- 看這個帳號（--colab-bin）底下**所有**還沒取回、也還沒停機的批次（redo_runs_colab/*/state.json，以 colab_bin 比對），
  不只一批；直到這個帳號上沒有任何活著的批次 session 才結束。
- 預估：每批剩餘對數 ÷ 實測速度 × 每台單價；合計超過「餘額 − margin」時，從**不受保護**、預估最貴的一批開始停
  （先做一次快照取回再 colab stop）；受保護的那批（--protect，可給多次）不因預估超支而停，只記警告。
- **取回失敗的批次**：keepalive.log 出現 FETCH_FAILED 而 session 還在，等 --fetch-failed-grace 小時（預設 2，給人工接手）
  後，先做一次快照取回，再 colab stop，寫 FETCH_FAILED_STOPPED.txt。
- **跑完但沒人取回**（BATCH_DONE 之後 keepalive 已經不在）：同樣在 grace 之後停。
- 餘額低於 --floor（預設 5 單元）：所有批次（含受保護的）快照後停機。
用法：colab_budget_watch.py --colab-bin ~/.local/bin/colab2 [--protect <state.json>]... [--margin 10] [--interval 600]
乾跑：BW_DRY=1。
"""
import argparse
import glob
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone

OPS = os.path.expanduser(os.environ.get("BW_OPS", "~/dev/ops"))
SNAP = ('import subprocess\nr=subprocess.run("tar czf /content/redo_snapshot.tar.gz -C /srv/redo --exclude=node_modules '
        "--exclude='attempt_*/w' --exclude='snap-*' --exclude='start-copy-*' --exclude='start-snap-*' --exclude='bkp-*' "
        '--exclude=__pycache__ run; rc=$?; [ $rc -le 1 ] && sha256sum /content/redo_snapshot.tar.gz", shell=True, '
        'capture_output=True, text=True)\nprint("SNAP_RC", r.returncode); print(r.stdout.strip()); print(r.stderr[-300:])\n')


def now_s():
    return f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}"


class Watch:
    def __init__(self, a):
        self.a = a
        self.cb = os.path.expanduser(a.colab_bin)
        self.log = os.path.join(OPS, f"colab_budget_watch_{os.path.basename(self.cb)}.log")
        self.protect = {os.path.realpath(os.path.expanduser(p)) for p in a.protect}
        self.dry = os.environ.get("BW_DRY") == "1"

    def say(self, m):
        with open(self.log, "a") as f:
            f.write(f"{now_s()} {m}\n")

    def sh(self, cmd, timeout=120, inp=None):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=inp)
            return r.returncode, r.stdout + r.stderr
        except subprocess.TimeoutExpired:
            return 124, "timeout"

    def balance(self):
        rc, out = self.sh([self.cb, "usage"], 60)
        m = re.search(r"Current balance: ([0-9.]+)", out)
        return (float(m.group(1)) if m else None), " ".join(out.split())

    def sessions(self):
        rc, out = self.sh([self.cb, "sessions"], 60)
        if rc != 0:
            return None
        return set(re.findall(r"^\[([^\]]+)\]", out, re.M))

    def live_states(self, listed):
        out = []
        for st in glob.glob(os.path.join(OPS, "redo_runs_colab", "*", "state.json")):
            try:
                d = json.load(open(st))
            except (OSError, ValueError):
                continue
            if os.path.expanduser(d.get("colab_bin") or "colab") != self.cb and os.path.basename(d.get("colab_bin") or "colab") != os.path.basename(self.cb):
                continue
            if d.get("fetched_utc") or d.get("stopped_utc"):
                continue
            if listed is not None and d.get("session") not in listed:
                continue
            out.append((st, d))
        return out

    def progress(self, st):
        kl = os.path.join(os.path.dirname(st), "keepalive.log")
        done = tot = ready = None
        failed_at = None
        if os.path.exists(kl):
            for line in open(kl, errors="replace"):
                m = re.search(r"(\d+)/(\d+) 對", line)
                if m:
                    done, tot = int(m.group(1)), int(m.group(2))
                r = re.search(r"VM_READY : yes \((\S+)\)", line)
                if r:
                    ready = r.group(1)
                if "FETCH_FAILED" in line:
                    failed_at = line.split()[0]
        return done, tot, ready, failed_at

    def est_cost(self, st):
        done, tot, ready, _ = self.progress(st)
        if done is None or tot is None:
            return self.a.price * self.a.default_hours
        rate = self.a.default_rate
        if ready and done >= 5:
            h = (datetime.now(timezone.utc) - datetime.fromisoformat(ready.replace("Z", "+00:00"))).total_seconds() / 3600
            if h > 0.3:
                rate = max(done / h, 0.5)
        return (tot - done) / rate * self.a.price

    def snapshot_and_stop(self, st, d, why):
        s = d["session"]
        out = os.path.join(os.path.dirname(st), "snapshots")
        os.makedirs(out, exist_ok=True)
        self.say(f"STOPPING {os.path.basename(os.path.dirname(st))} session={s}: {why}")
        if self.dry:
            self.say("DRY: would snapshot + stop")
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rc, txt = self.sh([self.cb, "exec", "-s", s, "--timeout", "1800"], 1900, SNAP)
        sha = re.search(r"^([0-9a-f]{64})", txt, re.M)
        ok = False
        if "SNAP_RC 0" in txt and sha:
            dst = os.path.join(out, f"snap_stop_{ts}.tar.gz")
            rc2, _ = self.sh([self.cb, "download", "-s", s, "/content/redo_snapshot.tar.gz", dst], 1800)
            ok = rc2 == 0 and os.path.exists(dst) and self.sh(["sha256sum", dst])[1][:64] == sha.group(1)
        self.say(f"  snapshot {'OK' if ok else 'FAILED'}")
        rc3, o3 = self.sh([self.cb, "stop", "-s", s])
        self.say(f"  colab stop rc={rc3} {o3.strip()[-160:]}")
        with open(os.path.join(os.path.dirname(st), "BUDGET_STOP.txt"), "a") as f:
            f.write(f"{ts} stopped by colab_budget_watch: {why}; snapshot ok={ok}\n")

    def run(self):
        self.say(f"START colab_bin={self.cb} protect={sorted(self.protect)} margin={self.a.margin} floor={self.a.floor} dry={self.dry}")
        stopped = set()
        while True:
            listed = self.sessions()
            if listed is None:
                self.say("sessions query failed; no action")
                time.sleep(self.a.interval)
                continue
            live = [(st, d) for st, d in self.live_states(listed) if st not in stopped]
            if not live:
                self.say(f"no live batch sessions on this account; exits. {self.balance()[1]}")
                return
            bal, raw = self.balance()
            if bal is None:
                self.say(f"usage query failed; no action: {raw[-120:]}")
                time.sleep(self.a.interval)
                continue
            # 1) 取回失敗／跑完沒人取回：grace 之後停
            for st, d in live:
                _, _, _, failed_at = self.progress(st)
                done_json = os.path.join(os.path.dirname(st), "BATCH_DONE.json")
                ka_alive = subprocess.run(["pgrep", "-f", f"colab_keepalive_[a-z]+[0-9]*\\.sh {st}"], capture_output=True).returncode == 0
                if failed_at or (os.path.exists(done_json) and not ka_alive):
                    t0 = failed_at or datetime.fromtimestamp(os.path.getmtime(done_json), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds() / 3600
                    if age_h >= self.a.fetch_failed_grace:
                        self.snapshot_and_stop(st, d, f"fetch failed / not fetched for {age_h:.1f}h (grace {self.a.fetch_failed_grace}h)")
                        with open(os.path.join(os.path.dirname(st), "FETCH_FAILED_STOPPED.txt"), "a") as f:
                            f.write(f"{now_s()} stopped after {age_h:.1f}h without a successful fetch\n")
                        stopped.add(st)
            live = [(st, d) for st, d in live if st not in stopped]
            # 2) 餘額地板：全部停
            if bal < self.a.floor:
                for st, d in live:
                    self.snapshot_and_stop(st, d, f"balance {bal} < floor {self.a.floor}")
                    stopped.add(st)
                continue
            # 3) 預估超過餘額：先停不受保護、最貴的（受保護的只記警告）
            costs = {st: self.est_cost(st) for st, _ in live}
            need = sum(costs.values())
            self.say(f"balance={bal} need={need:.0f} limit={bal - self.a.margin:.0f} | " +
                     "; ".join(f"{os.path.basename(os.path.dirname(st))[:28]}={costs[st]:.0f}{'*' if os.path.realpath(st) in self.protect else ''}" for st, _ in live))
            if need > bal - self.a.margin:
                order = sorted(live, key=lambda x: (os.path.realpath(x[0]) in self.protect, -costs[x[0]]))
                for st, d in order:
                    if need <= bal - self.a.margin:
                        break
                    if os.path.realpath(st) in self.protect:
                        # 受保護的批次不因預估超支而停（只記警告）；真的快沒錢時由餘額地板（--floor）處理
                        self.say(f"WARN: protected {os.path.basename(os.path.dirname(st))} alone exceeds balance-margin; not stopping (floor={self.a.floor})")
                        continue
                    self.snapshot_and_stop(st, d, f"budget: need {need:.0f} > balance {bal} - margin {self.a.margin}")
                    stopped.add(st)
                    need -= costs[st]
            time.sleep(self.a.interval)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--colab-bin", required=True)
    ap.add_argument("--protect", action="append", default=[])
    ap.add_argument("--margin", type=float, default=10)
    ap.add_argument("--floor", type=float, default=5)
    ap.add_argument("--price", type=float, default=6.4)
    ap.add_argument("--default-rate", type=float, default=9.7)
    ap.add_argument("--default-hours", type=float, default=17)
    ap.add_argument("--fetch-failed-grace", type=float, default=2)
    ap.add_argument("--interval", type=int, default=600)
    Watch(ap.parse_args()).run()


if __name__ == "__main__":
    main()
