#!/usr/bin/env python3
"""freeze_check — 每輪凍結狀態複核，單一指令、單一裁決行（vq-el4.27, r1268）。

背景：r1236–r1267 的 31 個「複核＋記錄」輪次靠 ~6 條分散手動指令完成（anchors、
ci-contract、兩條 in-scope diff、filing 六個 sha、g3gate --plan）。分散複核的風險
是漏跑其中一項而仍自稱複核過——H-0 的成因正是「漏掉一個旗標得到的綠燈」。
本腳本把審查指示 #1（anchors 守衛＋filing code sha 100% 吻合）與 #3（三分支實質
檔案比對，不得以祖先關係代替）＋ filing sources sha ＋ G3 前置（--plan，NOT FIRED）
收斂為一條指令。

背景（2026-11-08 r1271，vq-el4.28）：自 r1266 起 canonical STATE.md 的「## Current State」
section 停在 r1265、鏡像 ops/STATE.md 停在 r1270——兩者不一致且無任何機械檢查可偵測，
freeze_check 當時仍輸出 FROZEN_STATE_OK＝假綠燈（H-0 同構：漏掉一項得到的綠燈就是
漏洞成因）。故新增 bk_state／bk_now 兩項簿記鏡像檢查，並配漂移負控制測試
（tests/test_reqloop_freeze_check.py）。

    python3 ops/reqloop/freeze_check.py
    # rc 0  且  VERDICT: FROZEN_STATE_OK   —— 九項全 OK
    # rc 1  且  VERDICT: FROZEN_STATE_BROKEN —— 任一項 BROKEN，detail 點名

檢查項（全唯讀、0 model calls、不寫檔、不改分支、不 push）：
  anchors         tests/test_reqloop_frozen_anchors.py（5 測，改凍結檔即紅）
  ci_contract     tests/test_reqloop_ci_contract.py（2 測，安裝合約）
  diff_worker     git diff --name-only auto/worker  auto/qwen27b（in-scope）== 0
  diff_argon      git diff --name-only auto/argon   auto/qwen27b（in-scope）== 0
  filing_code     ops/audits/g25_all_gates_filing.json 的 code 三檔 sha256 重算 MATCH
  filing_sources  同檔 sources 三段 sha256 重算 MATCH
  g3gate_plan     python -m vacant_network.reqloop.g3gate --plan（rc 0、NOT FIRED）
  bk_state        repo STATE.md（canonical）Current State section 與 ops/STATE.md 鏡像同步
                  （約定＝r1265 實證的 byte-level：鏡像＝canonical 標題＋Current State section，
                  即鏡像是 canonical 的 byte 前綴；canonical 尾部的輪次 log 不屬鏡像）
  bk_now          repo NOW.md 與 ops/loop/NOW.md byte-identical（約定＝cp 鏡像；任一侧 0B
                  為空集測量→BROKEN，r1272 非空守衛）

口徑：本腳本只報「凍結狀態是否完好」，不裁 G2.5 成效、不裁 G3 可否發射。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FILING = REPO / "ops" / "audits" / "g25_all_gates_filing.json"
IN_SCOPE = ("vacant_network", "tests", "ops")
BASE_BRANCH = "auto/qwen27b"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail[:160]))


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _pytest(test_file: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", test_file],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = (p.stdout or "") + (p.stderr or "")
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return p.returncode, tail


def check_anchors() -> None:
    rc, tail = _pytest("tests/test_reqloop_frozen_anchors.py")
    record("anchors", rc == 0, f"pytest rc={rc} {tail}")


def check_ci_contract() -> None:
    rc, tail = _pytest("tests/test_reqloop_ci_contract.py")
    record("ci_contract", rc == 0, f"pytest rc={rc} {tail}")


def check_diff(branch: str, name: str) -> None:
    p = subprocess.run(
        ["git", "diff", "--name-only", branch, BASE_BRANCH, "--", *IN_SCOPE],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    files = [l for l in p.stdout.splitlines() if l.strip()]
    detail = (
        f"{len(files)} in-scope file(s) differ ({branch} vs {BASE_BRANCH})"
        + (f": {files[:3]}" if files else "")
    )
    if p.returncode != 0:
        detail = f"git rc={p.returncode}（分支不存在或不可比？）{p.stderr.strip()[:80]}"
    record(name, p.returncode == 0 and not files, detail)


def check_filing_code() -> None:
    d = json.loads(FILING.read_text(encoding="utf-8"))
    names: list[str] = []
    ok = 0
    for key, meta in d["code"].items():
        rel = key[len("/code/"):] if key.startswith("/code/") else key
        path = REPO / rel
        mine = _sha256(path)
        match = mine == meta["sha256"]
        ok += int(match)
        names.append(f"{Path(rel).name}{'MATCH' if match else 'MISMATCH'}")
    total = len(names)
    record("filing_code", ok == total and total == 3, f"{ok}/{total} sha256 {' '.join(names)}")


def check_filing_sources() -> None:
    d = json.loads(FILING.read_text(encoding="utf-8"))
    names: list[str] = []
    ok = 0
    for name, meta in d["sources"].items():
        raw = str(meta["path"])
        marker = "ops/reqloop/"
        tail = raw.split(marker, 1)[1] if marker in raw else Path(raw).name
        path = REPO / "ops" / "reqloop" / tail
        mine = _sha256(path)
        match = mine == meta["sha256"]
        ok += int(match)
        names.append(f"{name}{'MATCH' if match else 'MISMATCH'}")
    total = len(names)
    record("filing_sources", ok == total and total == 3, f"{ok}/{total} sha256 {' '.join(names)}")


def check_g3gate() -> None:
    p = subprocess.run(
        [sys.executable, "-m", "vacant_network.reqloop.g3gate", "--plan"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = p.stdout or ""
    not_fired = "NOT FIRED" in out
    plan_ok = "G3GATE PLAN OK" in out
    record(
        "g3gate_plan",
        p.returncode == 0 and not_fired and plan_ok,
        f"rc={p.returncode} NOT_FIRED={not_fired} PLAN_OK={plan_ok}",
    )


def check_bookkeeping_state(repo: Path = REPO) -> None:
    """bk_state：canonical（repo STATE.md）Current State section 與 ops/STATE.md 鏡像同步。

    約定（r1265 時點逐字實證：git show 684e2ba24:ops/STATE.md == canonical 前 8 行）：
    鏡像＝canonical 標題＋「## Current State」＋section 本體，即鏡像是 canonical 的
    byte 前綴（canonical 尾部為輪次 log，不屬鏡像）。任一侧停滯→BROKEN：r1266–r1270
    實際漂移 7+ 輪未被任何檢查抓住——假綠燈，本檢查就是為堵它而設。
    """
    canon = repo / "STATE.md"
    mirror = repo / "ops" / "STATE.md"
    try:
        c = canon.read_text(encoding="utf-8")
        m = mirror.read_text(encoding="utf-8")
    except OSError as e:
        record("bk_state", False, f"unreadable: {e}")
        return
    if "## Current State" not in m:
        record("bk_state", False, "mirror ops/STATE.md lacks '## Current State' header")
        return
    if c.startswith(m):
        record("bk_state", True, f"mirror {len(m)}B == canonical title+Current State（同步）")
    else:
        record(
            "bk_state", False,
            f"DRIFT: canonical {len(c)}B 不以 mirror {len(m)}B 為前綴（Current State 不同步）",
        )


def check_bookkeeping_now(repo: Path = REPO) -> None:
    """bk_now：repo NOW.md 與 ops/loop/NOW.md byte-identical（約定＝cp 鏡像）。

    非空守衛（r1272）：byte-identical 對兩份 0B 檔也成立，那是空集測量——
    I-4「未測量不是通過」；NOW.md 的約定是承載「現在在哪、下一步」，任一侧 0B
    是簿記壞掉，必須 BROKEN，不得以「兩側一致」放行。
    """
    a = repo / "NOW.md"
    b = repo / "ops" / "loop" / "NOW.md"
    try:
        ba = a.read_bytes()
        bb = b.read_bytes()
    except OSError as e:
        record("bk_now", False, f"unreadable: {e}")
        return
    if not ba or not bb:
        record(
            "bk_now", False,
            f"vacuous: repo NOW.md {len(ba)}B / ops/loop/NOW.md {len(bb)}B——空檔 byte-identity "
            "不是同步（I-4：未測量不是通過）",
        )
        return
    if ba == bb:
        record("bk_now", True, "repo NOW.md == ops/loop/NOW.md（byte-identical）")
    else:
        record("bk_now", False, "DRIFT: repo NOW.md != ops/loop/NOW.md")


def main() -> int:
    check_anchors()
    check_ci_contract()
    check_diff("auto/worker", "diff_worker")
    check_diff("auto/argon", "diff_argon")
    check_filing_code()
    check_filing_sources()
    check_g3gate()
    check_bookkeeping_state()
    check_bookkeeping_now()

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{name:<{width}}  {'OK' if ok else 'BROKEN'}  {detail}")
    all_ok = all(ok for _, ok, _ in results)
    print("VERDICT: " + ("FROZEN_STATE_OK" if all_ok else "FROZEN_STATE_BROKEN"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
