#!/usr/bin/env python3
"""e016 failed-step ablation 結案機械複核（票 P20261112_0923-2；0 model calls、只讀）。

結案證據：verdict json（state=NO_MECHANISM、3 對 McNemar Holm 皆未顯著、
pass A 18/C 17/C-nf 16、target 全 false）；packet §9 回填（通過率 A 18/34、
C 17/34、C-nf 16/34；p=1.0/0.7539/1.0；每成功呼叫 60.2/80.5/87.4；裁決句
NO_MECHANISM＋界線「不改產品」）；BACKLOG 第 8 行 `- [x] **完賽後（round 906+）**`
＋NO_MECHANISM 結案註記（~/dev/ops/BACKLOG.md 為 byte 一致活檔鏡像）。
架構對齊 e004/l007；REPO 自 __file__ 推導、CI-home 相容（不依賴 Path.home()）；
BACKLOG 為共用檔，釘住接受目標行 sha256 相符（argon 合併收斂法）。
"""
import argparse
import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
PACKET_DEFAULT = REPO / "ops/vlab/packets/e016_failed_step_ablation.md"
VERDICT_DEFAULT = REPO / "ops/audits/e016_failed_step_ablation_verdict.json"
BACKLOG_DEFAULT = REPO / "ops/BACKLOG.md"
PACKET_SHA256 = "541ec933570f194c6f829a88c14a3c49cfdb7d86c1d3f8f44404b3b6097994cf"
VERDICT_SHA256 = "20a69b63ffccc9c3e68027ed3e28960c3bdced68791afc35eea53dc64fc30e5d"
BACKLOG_SHA256 = "d541af4d317c2462a80d1aeee34d0c2ae5dcd047fde227901f0f30ecf7355fe9"
BACKLOG_LINE_SHA256 = "c752af0ca37a309c7654719fde3d919202672e8f2daae9893485514f77c94bb8"
BACKLOG_KEY = "完賽後（round 906+）"
COST_PASS = {"A": 18, "C": 17, "C-nf": 16}
PACKET_REQUIRED = (
    ("通過率 A", "A 18/34"), ("通過率 C", "C 17/34"), ("通過率 C-nf", "C-nf 16/34"),
    ("McNemar A vs C p", "p=1.0"), ("McNemar A vs C-nf p", "p=0.7539"),
    ("每成功呼叫 A", "60.2"), ("每成功呼叫 C", "80.5"), ("每成功呼叫 C-nf", "87.4"),
    ("裁決句", "裁決＝NO_MECHANISM"), ("界線", "不改產品"),
)
PINS = {PACKET_DEFAULT: PACKET_SHA256, VERDICT_DEFAULT: VERDICT_SHA256,
        BACKLOG_DEFAULT: BACKLOG_SHA256}


def check(packet_text: str, verdict_text: str, backlog_text: str) -> list[str]:
    """回傳違規清單；空列表＝全部判準成立。"""
    out: list[str] = []
    try:
        d = json.loads(verdict_text)
    except json.JSONDecodeError:
        return ["verdict json 無法解析"]
    if d.get("state") != "NO_MECHANISM":
        out.append(f"verdict state={d.get('state')!r} != NO_MECHANISM")
    pairs = d.get("pairs")
    if not (isinstance(pairs, list) and len(pairs) == 3):
        out.append(f"verdict pairs n={len(pairs) if isinstance(pairs, list) else 'N/A'} != 3")
    elif any(p.get("holm_significant") for p in pairs):
        out.append("verdict 有顯著 pair（Holm）；應 3 對全未顯著")
    costs = d.get("costs", {})
    for arm, want in COST_PASS.items():
        got = (costs.get(arm) or {}).get("pass")
        if got != want:
            out.append(f"costs[{arm}] pass={got!r} != {want}")
    target = d.get("target")
    if not (isinstance(target, dict) and set(target) == set(COST_PASS)
            and all(v is False for v in target.values())):
        out.append(f"verdict target={target!r}（應 A/C/C-nf 全 false）")
    for name, needle in PACKET_REQUIRED:
        if needle not in packet_text:
            out.append(f"packet 缺{name}: {needle!r}")
    found = next((l for l in backlog_text.splitlines() if BACKLOG_KEY in l), None)
    if found is None:
        out.append(f"BACKLOG 找不到項: {BACKLOG_KEY!r}")
    else:
        if not found.lstrip().startswith("- [x]"):
            out.append(f"BACKLOG e016 項未勾選 [x]: {found.lstrip()[:60]}")
        if "NO_MECHANISM" not in found:
            out.append(f"BACKLOG e016 項缺 NO_MECHANISM 結案註記: {found.lstrip()[:60]}")
    return out


def check_snapshot(p: pathlib.Path, want: str) -> list[str]:
    """凍結快照須存在且 sha256 與釘住值一致（BACKLOG 為共用檔，接受目標行 sha256 相符）。"""
    if not p.is_file():
        return [f"snapshot missing: {p}"]
    raw = p.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got == want:
        return []
    if want == BACKLOG_SHA256:
        ln = next((s for s in raw.decode("utf-8", errors="replace").splitlines() if BACKLOG_KEY in s), "")
        if hashlib.sha256(ln.encode("utf-8")).hexdigest() == BACKLOG_LINE_SHA256:
            return []
    return [f"snapshot sha256 drift {p.name}: {got[:12]}… != 釘住 {want[:12]}…（凍結紀錄，改動即紅）"]


def _pinned(p: pathlib.Path) -> list[str]:
    """只有 repo 內缺省快照受釘住；以 --packet/--verdict/--backlog 明確覆蓋時不釘（內容判準照跑）。"""
    want = PINS.get(p)
    return check_snapshot(p, want) if want else []


def selftest(packet_p: pathlib.Path, verdict_p: pathlib.Path, backlog_p: pathlib.Path) -> int:
    p_text = packet_p.read_text(encoding="utf-8")
    v_text = verdict_p.read_text(encoding="utf-8")
    b_text = backlog_p.read_text(encoding="utf-8")
    v = check(p_text, v_text, b_text) + _pinned(packet_p) + _pinned(verdict_p) + _pinned(backlog_p)
    if v:
        print("SELFTEST 正控制 FAIL（真檔）:")
        for s in v:
            print("  " + s)
        return 1

    def run(tag: str, p: str, v: str, b: str, must_hit: str) -> bool:
        vv = check(p, v, b)
        if not (vv and any(must_hit in s for s in vv)):
            print(f"SELFTEST 負控制 FAIL [{tag}]: violations={vv}（應含 {must_hit!r}）")
            return False
        return True

    ok = True
    ok &= run("n1 verdict state", p_text, v_text.replace('"state": "NO_MECHANISM"',
              '"state": "MECHANISM_CONFIRMED"', 1), b_text, "state")
    ok &= run("n2 pass 數", p_text, v_text.replace('"pass": 18', '"pass": 19', 1), b_text, "pass")
    ok &= run("n3 BACKLOG 未勾選", p_text, v_text, b_text.replace(
        f"- [x] **{BACKLOG_KEY}", f"- [ ] **{BACKLOG_KEY}", 1), "未勾選 [x]")
    ok &= run("n4 BACKLOG 註記", p_text, v_text, b_text.replace(
        "裁決＝**NO_MECHANISM**", "裁決＝**REOPENED**", 1), "結案註記")
    if not ok:
        return 1
    print("VERDICT: E016_CLOSURE_OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="正控制＋4 負控制")
    ap.add_argument("--packet", type=pathlib.Path, default=PACKET_DEFAULT)
    ap.add_argument("--verdict", type=pathlib.Path, default=VERDICT_DEFAULT)
    ap.add_argument("--backlog", type=pathlib.Path, default=BACKLOG_DEFAULT)
    args = ap.parse_args()
    if args.selftest:
        return selftest(args.packet, args.verdict, args.backlog)
    v = check(args.packet.read_text(encoding="utf-8"),
              args.verdict.read_text(encoding="utf-8"),
              args.backlog.read_text(encoding="utf-8"))
    v += _pinned(args.packet) + _pinned(args.verdict) + _pinned(args.backlog)
    for s in v:
        print(s)
    print("VERDICT: " + ("E016_CLOSURE_OK" if not v else "E016_CLOSURE_FAIL"))
    return 0 if not v else 1


if __name__ == "__main__":
    raise SystemExit(main())
