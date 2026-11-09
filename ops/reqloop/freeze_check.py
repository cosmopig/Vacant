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

背景（2026-11-08 r1273，vq-el4.30）：審查指示 #1 點名「5 passed 守衛」與「ci_contract
（2 passed）嚴禁弱化」，但 anchors/ci_contract 兩項原只比 pytest rc——守衛檔被削掉
測試、剩餘全綠時 rc 仍 0，freeze_check 照樣輸出 FROZEN_STATE_OK＝假綠燈（r1271/r1272
空對/空檔假綠同型）。負控制實測：1 測全綠的「anchors 檔」原判 OK。現改要求 rc 0 且
恰好期望計數 passed（少於＝弱化、多於＝守衛口徑變動須同步更新），並配負控制測試
（tests/test_reqloop_freeze_check.py test_guard_suite_count_negative_controls）。

檢查項（全唯讀、0 model calls、不寫檔、不改分支、不 push）：
  anchors         tests/test_reqloop_frozen_anchors.py——rc 0 且恰好 5 passed（5 passed 守衛）
  ci_contract     tests/test_reqloop_ci_contract.py——rc 0 且恰好 2 passed（嚴禁弱化）
  diff_worker     另一分支錨定被測 commit 的「同步對應 commit」（同簿記身份，r1303）後
  diff_argon      git diff --name-only <counterpart> <base>（in-scope）== 0
                  （r1300/vq-el4.45：base＝被測 commit；r1303/vq-el4.46：另一分支不再對
                  live tip diff——tip 每輪前進，已同步的舊 commit 量 tip 必假紅燈
                  （r1301 CI 實證）；無同步對應＝該輪從未同步→fail-closed BROKEN）
  filing_code     ops/audits/g25_all_gates_filing.json 的 code 三檔 sha256 重算 MATCH
                  （r1296/vq-el4.38：key 集＝恰 3 份凍結檔——身份替換的削弱但照綠守衛）
  filing_sources  同檔 sources 三段 sha256 重算 MATCH
                  （r1296/vq-el4.38：key 集＝phase1/2/3、派生 tail 集＝3 份互異 phase 檔）
  g3gate_plan     python -m vacant_network.reqloop.g3gate --plan（rc 0、NOT FIRED）
  bk_state        repo STATE.md（canonical）Current State section 與 ops/STATE.md 鏡像同步
                  （約定＝r1265 實證的 byte-level：鏡像＝canonical 標題＋Current State section，
                  即鏡像是 canonical 的 byte 前綴；canonical 尾部的輪次 log 不屬鏡像）
  bk_now          repo NOW.md 與 ops/loop/NOW.md byte-identical（約定＝cp 鏡像；任一侧 0B
                  為空集測量→BROKEN，r1272 非空守衛）

r1273 起 anchors/ci_contract 的 detail 帶「expected N passed, got M」，計數不符即 BROKEN；
r1285 起另要求匯總行無其它結果類（skipped/xfailed 等＝未測量，I-4）。

背景（2026-11-09 r1296，vq-el4.38）：filing code/sources 段原只查 count==3＋逐條
MATCH——key 被替換成另一條（檔存在、sha 真）後，3 份凍結檔/3 份 phase 檔失去覆蓋，
舊碼仍判「3/3 MATCH」OK＝假綠燈（r1296 實證：run_eval.py key→decoy.py 舊碼判 OK；
phase3 key→phaseX 舊碼判 OK；r1273 同型：計數守住但身份未守；H-0：漏掉一項得到的
綠燈就是漏洞成因；I-4：未測量不是通過）。期望集來源：審查指示 #1 點名的 3 份凍結檔
（tests/test_reqloop_frozen_anchors.py::test_filing_guard_detects_drift 同 3 路徑）＋
builder ops/audits/build_g25_all_gates_filing.py 的 phase1/2/3（同 tail）。

背景（2026-11-09 r1297，vq-el4.39）：任一檢查執行中拋異常（FILING JSON 損毀、
FILING 缺失、filing 條目非 dict、git 缺席、子程超時…）時，舊 main() 直接 traceback
——r1297 實證：FILING JSON 損毀 → JSONDecodeError 逃逸 → stdout 全空（前 5 項結果
也丟）、無裁決行、detail 未點名、後 4 項（filing_sources/g3gate_plan/bk_state/
bk_now）根本未跑——本檔自載契約「單一裁決行」「任一項 BROKEN，detail 點名」失守；
I-4：未測量不是通過，且操作者須看得到「哪項未跑」。故 main() 每項檢查經
run_check 包層：異常被點名記 BROKEN（CRASH: <ExcType>: <msg>），其餘各項照跑、
裁決行必現（SystemExit/KeyboardInterrupt 不吞）。

背景（2026-11-09 r1300，vq-el4.45）：diff_worker/diff_argon 原為
`git diff <worktree> auto/qwen27b`（live refs）。CI（ci.sh）以 detached checkout
量被測 commit，repo 內的分支 ref 指向執行時點的 live 分支 HEAD——worktree 已同步
到新 tip 時，舊 commit 自己的 in-scope 檔（簿記等）與 worktree 不同，舊碼仍判 0
file differ、OK＝假綠燈（r1300 沙盒實證：被測 commit ops/STATE.md=v1、兩 ref 皆
指 v2 tip → ref 基 0 files OK／HEAD 基 1 file BROKEN；H-0 同構：量錯對象得到的
綠燈就是漏洞成因；I-4：未測量不是通過）。改：HEAD detached 時 base 錨定 HEAD
（被測 commit）；attached 分支（本地 dev/worktree）保持分支 ref——不變量的口徑
（worktree 鏡像 qwen27b tip）不變。負控制：test_diff_anchor_negative_control。

背景（2026-11-09 r1303，vq-el4.46）：r1300 把 base 錨定被測 commit，但 check_diff 仍對
另一分支的 live tip（branch ref）diff——分支 tip 每輪前進，已正確同步的舊 commit 一旦
分支前進必 diff≠0→假紅燈。r1301 CI 實證：被測 r1301@bd93d42e2，CI 執行時 worker tip
已進 r1301 redo（569d7f625）→ diff_worker/diff_argon 皆 BROKEN（2 in-scope file differ:
ops/STATE.md、ops/loop/NOW.md）、pytest 2 failed；但該輪實際同步乾淨——三分支的
r1301 trio（bd93d42e2／812391cbf／38477561d）4 簿記檔 blob 全同、in-scope diff=0。
H-0 同構：量錯對象得到的紅燈同样是壞裁決。改：check_diff 錨定「同步對應 commit」——
同輪次（同簿記身份＝STATE.md/NOW.md/ops/STATE.md/ops/loop/NOW.md 的 path→blob 對）在該
分支上的 commit——量其 in-scope 內容；無對應（該輪從未同步到該分支；r1296「sync 漏掉
canonical 簿記」/r1297「worker/argon 未同步」缺陷類）→BROKEN（fail-closed，I-4 未測量
不是通過）；base 無簿記檔→輪次身份未測量→BROKEN。守衛未弱化：未同步輪仍紅燈、
同步輪的 in-scope 內容漂移仍紅燈；消除的只是「分支前進」這個結構性假紅燈。
負控制：tests/test_reqloop_freeze_check.py::test_diff_sync_counterpart_anchor。

口徑：本腳本只報「凍結狀態是否完好」，不裁 G2.5 成效、不裁 G3 可否發射。
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FILING = REPO / "ops" / "audits" / "g25_all_gates_filing.json"
IN_SCOPE = ("vacant_network", "tests", "ops")
BASE_BRANCH = "auto/qwen27b"
# 條目邊界約定（r1279）：條目行以「（YYYY-MM-DD…」起始——live canonical 24/24 條目行
# 逐條實證。只守「（」前綴不夠：多行條目的續行本身可以「（」開頭（r1279 負控制實測
# 假綠燈），須按日期錨定才算條目邊界。
ENTRY_START_RE = re.compile(r"（\d{4}-\d{2}-\d{2}")

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail[:160]))


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _pytest(test_file: str, cwd: Path = REPO) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-m", "pytest", test_file],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = (p.stdout or "") + (p.stderr or "")
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return p.returncode, tail


SUMMARY_RESULT_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|error|errors|xfailed|xpassed|deselected)"
)


def _check_guard_suite(
    name: str, test_file: str, expected_passed: int, cwd: Path = REPO
) -> None:
    """守衛測試套件＝rc 0 且「恰好 expected_passed passed」（r1273 計數守衛）。

    審查指示 #1 點名「5 passed 守衛」與「tests/test_reqloop_ci_contract.py（2 passed）
    嚴禁弱化」：守衛檔被削掉測試、剩餘全綠時 rc 仍為 0——只比 rc 即假綠燈（與
    r1271/r1272 空對/空檔假綠同型）。故足額必須機械化：少於或多於期望計數皆 BROKEN
    （套件縮小＝弱化；增大＝守衛口徑變動，須同步更新本守衛的期望值，不得靜默放行）。

    r1285：同型殘餘假綠——守衛檔以 @pytest.mark.skip 禁用一個守衛測試（藏失敗斷言）、
    另補足量測試使 passed 計數不變時，pytest 匯總為「5 passed, 1 skipped」；只抽
    passed 計數仍判 OK。skipped/xfailed 等即「未測量」（I-4：未測量不是通過）：
    匯總行出現任何非 passed 結果類（skipped/failed/error(s)/xfailed/xpassed/
    deselected）即 BROKEN。
    """
    rc, tail = _pytest(test_file, cwd)
    counts: dict[str, int] = {}
    for n, cat in SUMMARY_RESULT_RE.findall(tail):
        counts[cat] = counts.get(cat, 0) + int(n)
    passed = counts.get("passed")
    other = {k: v for k, v in counts.items() if k != "passed"}
    ok = rc == 0 and passed == expected_passed and not other
    record(
        name, ok,
        f"pytest rc={rc} {tail}（expected {expected_passed} passed, got {passed}"
        + (f"；其它結果類 {other}）" if other else "；無其它結果類）"),
    )


def check_anchors(cwd: Path = REPO) -> None:
    _check_guard_suite("anchors", "tests/test_reqloop_frozen_anchors.py", 5, cwd)


def check_ci_contract(cwd: Path = REPO) -> None:
    _check_guard_suite("ci_contract", "tests/test_reqloop_ci_contract.py", 2, cwd)


def _diff_base() -> str:
    """diff 的 base 錨定被測 commit（r1300，vq-el4.45）。

    CI（ci.sh）detached checkout 被測 commit，repo 內分支 ref 指向執行時點的 live
    分支 HEAD：舊碼 ref 基 diff 量的是 tip 狀態而非被測 commit——worktree 已同步
    新 tip 時，舊 commit 自己的 in-scope 檔與 worktree 不同仍判 0 file differ、OK
    ＝假綠燈（r1300 沙盒實證；H-0 同構：量錯對象得到的綠燈就是漏洞成因）。
    HEAD detached（CI 沙盒）→ base=HEAD（被測 commit）；attached 分支（本地 dev/
    worktree）→ base=auto/qwen27b（舊口徑：worktree 鏡像 qwen27b tip）。
    """
    p = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        h = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if h.returncode == 0 and h.stdout.strip():
            return h.stdout.strip()
    return BASE_BRANCH


# 輪次身份＝四簿記檔（canonical＋鏡像）的 path→blob 對（r1303，vq-el4.46）。
# 任一侧漂移（r1296「sync 漏掉 2 canonical 簿記檔」類）即身份不符→無對應→BROKEN。
BOOKKEEPING_PATHS = ("STATE.md", "NOW.md", "ops/STATE.md", "ops/loop/NOW.md")
# 在另一分支歷史中向前找同步對應 commit 的窗口（每輪三分支鎖步前進，對應 commit
# 通常在最近 ~10 commit 內；窗口外＝該輪從未同步→fail-closed）。
COUNTERPART_WINDOW = 100


def _bookkeeping_identity(ref: str) -> dict[str, str] | None:
    """ref 的簿記身份：BOOKKEEPING_PATHS 中「存在於該 commit」的 path→blob sha 對。

    單次 git ls-tree（不存在的路徑被靜默跳過、rc 0）；ref 不可解析→None（未測量，I-4）。
    """
    p = subprocess.run(
        ["git", "ls-tree", ref, "--", *BOOKKEEPING_PATHS],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        return None
    ident: dict[str, str] = {}
    for line in p.stdout.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            ident[path] = parts[2]
    return ident


def _sync_counterpart(branch: str, base: str) -> str | None:
    """在 branch 歷史中找與被測 commit base 同簿記身份（輪次身份）的同步對應 commit（r1303，vq-el4.46）。

    r1300 把 base 錨定被測 commit，但仍對另一分支的 live tip diff；分支 tip 每輪前進——
    已正確同步的舊 commit 一旦分支前進必 diff≠0→假紅燈（r1301 CI 實證：被測
    r1301@bd93d42e2、worker tip 已進 r1301 redo→2 in-scope file differ BROKEN、
    2 failed；該輪實際同步乾淨：三分支 4 簿記檔 blob 全同、in-scope diff=0；
    H-0 同構：量錯對象得到的紅燈同样是壞裁決）。
    改：錨定「同步對應 commit」——同輪次在該分支上的 commit——量其 in-scope 內容。
    無對應（base 的輪次從未同步到該分支；r1296/r1297 缺陷類）→None→BROKEN（fail-closed）。
    """
    target = _bookkeeping_identity(base)
    if not target:  # None＝ref 不可解析；{}＝無簿記檔＝輪次身份未測量（I-4）
        return None
    p = subprocess.run(
        ["git", "log", "--format=%H", "-n", str(COUNTERPART_WINDOW), branch],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        return None  # 分支不存在→未測量→fail-closed
    for sha in (l.strip() for l in p.stdout.splitlines()):
        if sha and _bookkeeping_identity(sha) == target:
            return sha
    return None


def check_diff(branch: str, name: str) -> None:
    base = _diff_base()
    counterpart = _sync_counterpart(branch, base)
    if counterpart is None:
        record(
            name, False,
            f"no sync counterpart on {branch}: 被測 {base[:9]} 的簿記身份（STATE.md/NOW.md"
            f"/ops 鏡像）在 {branch} 最近 {COUNTERPART_WINDOW} commit 內無對應"
            f" commit——該輪從未同步到 {branch}？（fail-closed，I-4 未測量不是通過）",
        )
        return
    p = subprocess.run(
        ["git", "diff", "--name-only", counterpart, base, "--", *IN_SCOPE],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    files = [l for l in p.stdout.splitlines() if l.strip()]
    detail = (
        f"{len(files)} in-scope file(s) differ "
        f"({branch}@{counterpart[:9]} vs {base[:9]})"
        + (f": {files[:3]}" if files else "")
    )
    if p.returncode != 0:
        detail = (
            f"git rc={p.returncode}（{branch}@{counterpart[:9]} vs {base[:9]} 不可比？）"
            f"{p.stderr.strip()[:80]}"
        )
    record(name, p.returncode == 0 and not files, detail)


# r1296（vq-el4.38）：filing 覆蓋集身份期望集（來源與理由見模組 docstring）。
EXPECTED_CODE_KEYS = frozenset({
    "vacant_network/reqloop/extract.py",
    "vacant_network/reqloop/checks.py",
    "ops/reqloop/extract/run_eval.py",
})
EXPECTED_SOURCE_KEYS = frozenset({"phase1", "phase2", "phase3"})
EXPECTED_SOURCE_TAILS = frozenset({
    "extract/out/all/phase1.json",
    "extract/out/all/phase2.json",
    "extract/out/all/phase3.json",
})


def check_filing_code() -> None:
    d = json.loads(FILING.read_text(encoding="utf-8"))
    keys = set(d["code"])
    missing = sorted(EXPECTED_CODE_KEYS - keys)
    extra = sorted(keys - EXPECTED_CODE_KEYS)
    if missing or extra:
        record(
            "filing_code", False,
            f"COVERAGE: code key 集缺 {missing}、多 {extra}"
            "（期望恰為 3 份凍結檔；count==3 但身份被替換＝假綠燈；r1273 同型；I-4）",
        )
        return
    names: list[str] = []
    ok = 0
    for key, meta in d["code"].items():
        rel = key[len("/code/"):] if key.startswith("/code/") else key
        path = REPO / rel
        mine = _sha256(path)
        # r1288（vq-el4.36）：備案 sha256 為 null（未 pin）＝未測量；檔不存在時
        # _sha256→None，舊碼 None == None → True＝「3/3 MATCH」假綠燈（實測）。
        # pin 與實算 sha 皆須非 null 才可 MATCH（I-4：未測量不是通過；H-0 同構）。
        match = mine is not None and meta["sha256"] is not None and mine == meta["sha256"]
        ok += int(match)
        names.append(f"{Path(rel).name}{'MATCH' if match else 'MISMATCH'}")
    total = len(names)
    record("filing_code", ok == total and total == 3, f"{ok}/{total} sha256 {' '.join(names)}")


def check_filing_sources() -> None:
    d = json.loads(FILING.read_text(encoding="utf-8"))
    keys = set(d["sources"])
    missing = sorted(EXPECTED_SOURCE_KEYS - keys)
    extra = sorted(keys - EXPECTED_SOURCE_KEYS)
    if missing or extra:
        record(
            "filing_sources", False,
            f"COVERAGE: sources key 集缺 {missing}、多 {extra}"
            "（期望恰為 phase1/2/3；削弱但照綠；r1273 同型）",
        )
        return
    marker = "ops/reqloop/"
    tails: list[str] = []
    for k in sorted(d["sources"]):
        raw = str(d["sources"][k]["path"])
        tails.append(raw.split(marker, 1)[1] if marker in raw else Path(raw).name)
    tmissing = sorted(EXPECTED_SOURCE_TAILS - set(tails))
    dup = len(tails) != len(set(tails))
    if tmissing or dup:
        record(
            "filing_sources", False,
            f"COVERAGE: sources 派生路徑集與 3 份 phase 檔不符——缺 {tmissing}"
            f"{'、重複' if dup else ''}（三條須各量一份互異 phase 檔；削弱但照綠；r1273 同型）",
        )
        return
    names: list[str] = []
    ok = 0
    for name, meta in d["sources"].items():
        raw = str(meta["path"])
        marker = "ops/reqloop/"
        tail = raw.split(marker, 1)[1] if marker in raw else Path(raw).name
        path = REPO / "ops" / "reqloop" / tail
        mine = _sha256(path)
        # r1288（vq-el4.36）：同 check_filing_code——null pin（未測量）不得 MATCH
        # （實測：六 sha 全 null 備案 filing_sources 舊碼判 OK＝假綠燈）。
        match = mine is not None and meta["sha256"] is not None and mine == meta["sha256"]
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

    r1278 截斷守衛（vq-el4.31）：「byte 前綴」必要但不充分——截斷鏡像（最新條目尾部
    被砍）仍是 canonical 的 byte 前綴，舊檢查照樣判 OK＝假綠燈（實測：live 鏡像砍
    60B/1B 仍輸出「同步」；與 r1271/r1272 空對/空檔假綠同型，H-0：漏掉一項得到的
    綠燈就是漏洞成因）。條目邊界約定：每輪條目各占一行、以「（」（U+FF08）起始——
    canonical 現有條目逐條實證、負控制 fixture 同形。故鏡像必須以行邊界（'\n'）結尾，
    且 canonical 餘部為空（無輪次 log）或自新條目起始。

    r1279 邊界錨定（vq-el4.32）：「（」前綴必要但不充分——多行條目的續行本身可以
    「（」開頭（如「（續行…）」），條目中途被砍的鏡像仍被判「同步」＝假綠燈
    （r1279 實測：('bk_state', True, 'mirror 46B…同步')，與 r1278 截斷假綠同型）。
    條目邊界約定收緊為 live 檔實證的「（YYYY-MM-DD…」起始（24/24 條目行逐條核實）：
    餘部非日期條目起始即視為條目內截斷→BROKEN。代價：非日期條目行會被判不同步——
    那是簿記違反約定，應修簿記而非放寬守衛。

    r1282 零條目鏡像守衛（vq-el4.34）：餘部守衛必要但不充分——鏡像本身零條目行
    （只有標題＋'## Current State'）時，餘部恰為最新條目、自然日期起始，舊碼判
    「同步」（r1282 實測：('bk_state', True, 'mirror 22B…同步')，與 r1271–r1279
    同型假綠燈）。鏡像約定＝標題＋'## Current State'＋最新條目（單行，r1278 約定），
    故鏡像末行必須恰為 canonical 的最新條目行（'## Current State' 後首個非空行）；
    canonical 無條目行（空狀態段）亦 BROKEN（I-4：未測量不是通過）。
    已知殘留邊界（如實）：多行條目在行邊界截斷且續行恰好形如「（YYYY-MM-DD…」時，
    與「正確狀態＋兩個單行條目」逐位元組不可區分——任何 byte 級守衛都無法判別；
    緩解＝「每輪條目各占一行」的簿記約定（違约定即修簿記），不在 byte 檢查裡假裝能分辨。
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
    if not c.startswith(m):
        record(
            "bk_state", False,
            f"DRIFT: canonical {len(c)}B 不以 mirror {len(m)}B 為前綴（Current State 不同步）",
        )
        return
    if not m.endswith("\n"):
        record(
            "bk_state", False,
            f"TRUNCATED: mirror {len(m)}B 為 canonical 之 byte 前綴但非行邊界結尾"
            "（最新條目尾部被砍）——截斷鏡像不是同步（I-4：未測量不是通過）",
        )
        return
    if len(m) < len(c) and ENTRY_START_RE.match(c, len(m)) is None:
        record(
            "bk_state", False,
            f"TRUNCATED: mirror {len(m)}B 為 canonical 之 byte 前綴但餘部非日期條目起始"
            "「（YYYY-MM-DD…」（多行條目內行邊界截斷，續行形如新條目）——截斷鏡像不是同步（I-4：未測量不是通過）",
        )
        return
    # r1282（vq-el4.34）：鏡像末行＝canonical 最新條目行（'## Current State' 後首個
    # 非空行）。零條目鏡像（只有標題＋表頭）的餘部恰為最新條目、日期起始，上面的
    # 餘部守衛放行＝假綠燈（r1282 實測）；此守衛要求鏡像本身承載當前狀態條目。
    c_lines = c.split("\n")
    h = c_lines.index("## Current State")  # 前綴檢查已保證 canonical 含表頭
    entry = next((ln for ln in c_lines[h + 1:] if ln.strip()), None)
    if entry is None:
        record(
            "bk_state", False,
            "canonical STATE.md '## Current State' 下無條目行——空狀態段不是同步"
            "（I-4：未測量不是通過）",
        )
        return
    # r1292（vq-el4.37）：錨點行本身必須是日期條目行——r1282 守衛取「首個非空行」
    # 為錨點但從未驗其為條目行；section 首個非空行是非日期行（如 NOTE）時，鏡像＝
    # 標題＋表頭＋該行（零條目行）仍判「同步」（r1292 實測：mirror 27B 判 OK＝
    # r1271–r1282 同型假綠燈、H-0 同構）。非條目行＝簿記違反約定，應修簿記。
    if ENTRY_START_RE.match(entry) is None:
        record(
            "bk_state", False,
            f"NO_ENTRY: canonical '## Current State' 首個非空行非日期條目行「（YYYY-MM-DD…」"
            f"（實際 {entry[:40]!r}）——錨點非條目時零條目鏡像仍判同步＝假綠燈；"
            "非條目行是簿記違反約定，應修簿記（I-4：未測量不是通過）",
        )
        return
    m_lines = m.split("\n")
    if m_lines and m_lines[-1] == "":
        m_lines = m_lines[:-1]  # 上面已保證 m 以 '\n' 結尾
    if not m_lines or m_lines[-1] != entry:
        record(
            "bk_state", False,
            f"NO_ENTRY: mirror {len(m)}B 末行不是 canonical 最新條目行"
            "（鏡像零條目/末行停滯——餘部雖以新條目起始，鏡像本身未承載當前狀態，"
            "不是同步；I-4：未測量不是通過）",
        )
        return
    record("bk_state", True, f"mirror {len(m)}B == canonical title+Current State（同步）")


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


def run_check(name: str, fn: Callable[[], None]) -> None:
    """單項檢查異常包層（r1297，vq-el4.39）：檢查執行中拋異常（FILING JSON 損毀、
    FILING 缺失、filing 條目非 dict、git 缺席、子程超時…）時，點名記 BROKEN
    （CRASH: <ExcType>: <msg>）而非讓異常逃逸到 main() 頂層——r1297 實證舊碼：
    JSONDecodeError 逃逸 → stdout 全空（前 5 項結果也丟）、無裁決行、detail 未
    點名、後 4 項（filing_sources/g3gate_plan/bk_state/bk_now）根本未跑，本檔
    自載契約「單一裁決行／detail 點名」失守；I-4：未測量不是通過，且操作者須
    看得到「哪項未跑」。SystemExit/KeyboardInterrupt 不吞（except Exception）。"""
    try:
        fn()
    except Exception as exc:
        record(name, False, f"CRASH: {type(exc).__name__}: {exc}")


def main() -> int:
    # r1297（vq-el4.39）：每項檢查經 run_check——任一項崩潰被點名記 BROKEN，
    # 其餘各項照跑，9 項全在輸出＋單一裁決行（I-4：未測量不是通過）。
    run_check("anchors", check_anchors)
    run_check("ci_contract", check_ci_contract)
    run_check("diff_worker", lambda: check_diff("auto/worker", "diff_worker"))
    run_check("diff_argon", lambda: check_diff("auto/argon", "diff_argon"))
    run_check("filing_code", check_filing_code)
    run_check("filing_sources", check_filing_sources)
    run_check("g3gate_plan", check_g3gate)
    run_check("bk_state", check_bookkeeping_state)
    run_check("bk_now", check_bookkeeping_now)

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{name:<{width}}  {'OK' if ok else 'BROKEN'}  {detail}")
    all_ok = all(ok for _, ok, _ in results)
    print("VERDICT: " + ("FROZEN_STATE_OK" if all_ok else "FROZEN_STATE_BROKEN"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
