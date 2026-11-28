#!/usr/bin/env python3
"""B51(3) 沙箱負控制（硬條件）：用和正式執行同一份沙箱腳本（bwrap_expT_agent.sh，netns 模式），在 live 根目錄底下開一個測試格，
在沙箱裡逐項測：
  N1 `ls -la <live 根>` 只列出本格目錄；N2 `find <live 根> -maxdepth 2` 只有本格；
  N3 以別格絕對路徑讀檔失敗；N4 以 `../<別格名>` 讀檔失敗；N5 以萬用字元 `<live 根>/*/ws/report.md` 讀不到別格；
  N6 讀教材目錄（${D2_PRIVATE} 與 realrev3 各修訂）失敗或目錄不存在；N7 列出沙箱內全部掛載點（/proc/self/mountinfo），和允許清單一致。
輸出：JSON（逐項指令、結果、是否通過）＋允許的掛載點清單；全過才回 0。測試格留在原地（刪除規則），路徑記在輸出裡。
用法：sandbox_negctl.py --venv <venv> --d2-private <dir> --label <名字> --out <json>
"""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--venv", required=True); ap.add_argument("--d2-private", required=True)
    ap.add_argument("--label", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    H = pathlib.Path.home(); L = H / "dev" / "ops" / "d2_private_live"
    me = L / f"nst_negctl_{a.label}_{int(time.time())}"
    for d in (me / "ws", me / "tmp", me / "vh", me / "cfg", me / "out"):
        d.mkdir(parents=True, exist_ok=True)
    (me / "ws" / "report.md").write_text("own report\n")
    others = [p for p in sorted(L.iterdir()) if p.is_dir() and not p.name.startswith("nst_") and (p / "ws").exists()][:3]
    other = others[0] if others else None
    d2 = pathlib.Path(a.d2_private)
    mats = [d2 / "realrev3_football" / "sets" / "s01" / "cycle_1" / "site", d2 / "realrev3_companies" / "manifest.json", d2]
    tests = [
        ("N1_ls_live_root", f"ls -la {L}"),
        ("N2_find_live_root", f"find {L} -maxdepth 2"),
        ("N3_read_other_abs", f"cat {other}/ws/report.md" if other else "true"),
        ("N4_read_other_dotdot", f"cd {me}/ws && cat ../../{other.name}/ws/report.md" if other else "true"),
        ("N5_read_wildcard", f"cat {L}/*/ws/report.md"),
        ("N6a_ls_d2_private", f"ls {d2}"),
        ("N6b_ls_future_revision", f"ls {mats[0]}"),
        ("N6c_cat_manifest", f"cat {mats[1]}"),
        ("N7_mountinfo", "cat /proc/self/mountinfo"),
    ]
    script = "; ".join(f"echo '@@{n}'; ({c}) 2>&1; echo \"@@rc=$?\"" for n, c in tests)
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    env["EXPT_NETNS_PROXY_PORT"] = "39999"          # 和正式執行同一條 netns 路徑（裡面起 tcp2unix；這裡不接上游）
    r = subprocess.run([str(HERE / "bwrap_expT_agent.sh"), str(me), str(me / "out"), a.venv, "--", "/bin/sh", "-c", script],
                       env=env, capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    parts = {}
    for chunk in out.split("@@")[1:]:
        head, _, body = chunk.partition("\n")
        if head.startswith("rc="):
            continue
        rc_i = body.rfind("@@rc=")
        parts[head.strip()] = body
    rcs = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("@@") and not line.startswith("@@rc="):
            cur = line[2:].strip()
        elif line.startswith("@@rc=") and cur:
            rcs[cur] = int(line[5:]); cur = None
    res = []; ok_all = True
    def add(name, ok, detail):
        nonlocal ok_all
        ok_all &= ok; res.append({"name": name, "pass": ok, "rc": rcs.get(name), "detail": detail[:600]})
    body = lambda n: parts.get(n, "").split("@@rc=")[0]
    ls = body("N1_ls_live_root"); entries = [l.split()[-1] for l in ls.splitlines() if l and not l.startswith("total") and l.split()[-1] not in (".", "..")]
    add("N1_ls_live_root", entries == [me.name], f"entries={entries}")
    fd = [l for l in body("N2_find_live_root").splitlines() if l.strip()]
    add("N2_find_live_root", all(l == str(L) or l.startswith(str(me)) for l in fd), f"lines={len(fd)} non_own={[l for l in fd if not (l == str(L) or l.startswith(str(me)))][:5]}")
    for n in ("N3_read_other_abs", "N4_read_other_dotdot"):
        add(n, other is None or rcs.get(n, 0) != 0, body(n).strip()[:200])
    w = body("N5_read_wildcard").strip()
    add("N5_read_wildcard", w in ("own report", "") or (w.startswith("own report") and len(w.splitlines()) == 1), w[:200])
    for n in ("N6a_ls_d2_private", "N6b_ls_future_revision", "N6c_cat_manifest"):
        add(n, rcs.get(n, 0) != 0, body(n).strip()[:200])
    mounts = sorted({l.split()[4] for l in body("N7_mountinfo").splitlines() if len(l.split()) > 4})
    nodeinst = str(H / ".piinstall")
    allowed_prefixes = ["/", "/proc", "/dev", "/tmp", "/usr", "/etc", str(H), nodeinst, str(me), str(me / "out"), a.venv, "/opt/expT/sockfwd.py"]
    node_root = os.path.dirname(os.path.dirname(os.path.realpath(H / ".local/bin/node")))
    allowed_prefixes.append(node_root)
    bad = [m for m in mounts if not any(m == p or m.startswith(p + "/") for p in allowed_prefixes if p != "/") and m != "/"
           and not m.startswith(("/dev/", "/proc/"))]
    leaks = [m for m in mounts if m.startswith(str(d2)) or (m.startswith(str(L)) and not m.startswith(str(me)))]
    add("N7_mounts_match_allowlist", not bad and not leaks, f"mounts={mounts} bad={bad} leaks={leaks}")
    allow = {"allowed_mount_prefixes": sorted(set(allowed_prefixes)), "observed_mounts": mounts}
    rep = {"label": a.label, "test_cell": str(me).replace(str(H), "~"), "other_cell_used": other.name if other else None,
           "wrapper_sha256": hashlib.sha256((HERE / "bwrap_expT_agent.sh").read_bytes()).hexdigest(),
           "tests": res, "allowlist": allow, "allowlist_sha256": hashlib.sha256(json.dumps(allow, sort_keys=True).encode()).hexdigest(),
           "all_pass": ok_all}
    s = json.dumps(rep, ensure_ascii=False, indent=1).replace(str(d2), "${D2_PRIVATE}").replace(str(H), "~")
    pathlib.Path(a.out).write_text(s)
    for t in res:
        print(("PASS " if t["pass"] else "FAIL ") + t["name"] + "  " + t["detail"][:140].replace(str(d2), "${D2_PRIVATE}").replace(str(H), "~"))
    print("ALL PASS" if ok_all else "NOT ALL PASS")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
