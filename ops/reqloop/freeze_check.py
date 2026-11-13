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
    # rc 0  且  VERDICT: FROZEN_STATE_OK   —— 十二項全 OK
    # rc 1  且  VERDICT: FROZEN_STATE_BROKEN —— 任一項 BROKEN，detail 點名

背景（2026-11-08 r1273，vq-el4.30）：審查指示 #1 點名「5 passed 守衛」與「ci_contract
（2 passed）嚴禁弱化」，但 anchors/ci_contract 兩項原只比 pytest rc——守衛檔被削掉
測試、剩餘全綠時 rc 仍 0，freeze_check 照樣輸出 FROZEN_STATE_OK＝假綠燈（r1271/r1272
空對/空檔假綠同型）。負控制實測：1 測全綠的「anchors 檔」原判 OK。現改要求 rc 0 且
恰好期望計數 passed（少於＝弱化、多於＝守衛口徑變動須同步更新），並配負控制測試
（tests/test_reqloop_freeze_check.py test_guard_suite_count_negative_controls）。

檢查項（全唯讀、0 model calls、不寫檔、不改分支、不 push）：
  anchors         tests/test_reqloop_frozen_anchors.py——rc 0 且恰好 5 passed（5 passed 守衛）
                  且通過測試名 ⊇ EXPECTED_ANCHOR_TEST_NAMES（r1314 身份守衛，-rA 收集）
  ci_contract     tests/test_reqloop_ci_contract.py——rc 0 且恰好 2 passed（嚴禁弱化）
                  且通過測試名 ⊇ EXPECTED_CI_CONTRACT_TEST_NAMES（r1314 身份守衛，-rA 收集）
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
  queue_empty     /srv/vlab/queue/ 人類核准前必須為空（r1339 起；審查指示 #5）
  bk_state        repo STATE.md（canonical）Current State section 與 ops/STATE.md 鏡像同步
                  （約定＝r1265 實證的 byte-level：鏡像＝canonical 標題＋Current State section，
                  即鏡像是 canonical 的 byte 前綴；canonical 尾部的輪次 log 不屬鏡像）
  bk_now          repo NOW.md 與 ops/loop/NOW.md byte-identical（約定＝cp 鏡像；任一侧 0B
                  為空集測量→BROKEN，r1272 非空守衛）
  now_redline     NOW.md 紅線「凍結 4 檔＋filing N sha256」契約行 vs 磁碟逐條核實（r1393，
                  vq-el4.81；重用 tests/test_reqloop_now_redline.py 之 redline_violations()
                  為唯一實現，無第二份 ruler；守衛檔缺／NOW.md 缺 → BROKEN，I-4）

r1273 起 anchors/ci_contract 的 detail 帶「expected N passed, got M」，計數不符即 BROKEN；
r1285 起另要求匯總行無其它結果類（skipped/xfailed 等＝未測量，I-4）。

背景（2026-11-09 r1296，vq-el4.38）：filing code/sources 段原只查 count==3＋逐條
MATCH——key 被替換成另一條（檔存在、sha 真）後，3 份凍結檔/3 份 phase 檔失去覆蓋，
舊碼仍判「3/3 MATCH」OK＝假綠燈（r1296 實證：run_eval.py key→decoy.py 舊碼判 OK；
phase3 key→phaseX 舊碼判 OK；r1273 同型：計數守住但身份未守；H-0：漏掉一項得到的
綠燈就是漏洞成因；I-4：未測量不是通過）。期望集來源：審查指示 #1 點名的 3 份凍結檔
（tests/test_reqloop_frozen_anchors.py::test_filing_guard_detects_drift 同 3 路徑）＋
builder ops/audits/build_g25_all_gates_filing.py 的 phase1/2/3（同 tail）。

背景（2026-11-09 r1314，vq-el4.49）：anchors/ci_contract 守衛原只守「計數＋無其他結果
類別」——守衛測試被換成同數 assert True dummy（全綠、rc=0、計數足、無 skipped）時舊碼
仍判 OK＝假綠燈（r1314 RED 實證：5 個 dummy 的 anchors 檔舊碼判 ('anchors', True, …)，
既有 test_guard_suite_count_negative_controls fixture (b) 曾字面編碼此期望；r1296 同型：
計數守住但身份未守；H-0：漏掉一項得到的綠燈就是漏洞成因；I-4：未測量不是通過）。
現以 pytest -rA 收集 PASSED 測試名、要求 ⊇ 期望集（EXPECTED_ANCHOR_TEST_NAMES 5／
EXPECTED_CI_CONTRACT_TEST_NAMES 2；來源：兩份守衛檔現行測試函數名，審查指示 #1 點名），
detail 點名 missing；負控制 test_guard_suite_identity_negative_controls。

背景（2026-11-09 r1327，vq-el4.51）：r1324 只擋 plain print 偽「PASSED
<nodeid>」行（偽行在真 summary 標頭前、不進段），但 _parse_passed_names 取輸出中
「第一處」short test summary info 為段首——守衛檔的 dummy 測試可 print 偽標頭＋偽
PASSED 行（-rA 下 PASSES 段顯示通過測試的 captured stdout；capfd.disabled() 更直接），
偽頭必在真頭之前，舊碼以偽頭為段首→偽名進身份集＝假綠燈（r1327 RED 實證：3 真名＋
2 偽名 dummy 檔被舊碼判 ('anchors', True, 'pytest rc=0（身份齊；expected 5 passed,
got 5；…）')；r1296/r1314/r1324 同族：計數守住、身份未守；H-0：漏掉一項得到的
綠燈就是漏洞成因）。修：① 段首＝「最後一處」標頭行——真 summary 由 pytest 於 session
結束時輸出，測試執行期的 print 必在其之前；② 計數錨：真 -rA 段恰每通過測試一行
PASSED，段內行數須 == passed，段內多出一行偽行即破→BROKEN（fail-closed，I-4：未測量
不是通過）。真守衛檔（全綠）仍 OK（測試檔正控制 (c)）；負控制：
tests/test_reqloop_freeze_check.py::test_guard_suite_fake_summary_header_negative_control。
殘留（誠實記錄）：真 summary 之後才 print（conftest.py pytest_terminal_summary hook／
晚到 thread）超出本守衛的單檔威脅模型（既有負控制皆只改守衛檔），與 bk_state 已知
殘留邊界同類。

背景（2026-11-11 r1324，vq-el4.50）：r1314 身份守衛從全量輸出收集「PASSED
<nodeid>」行核對測試名——但測試體本身可 print 以「PASSED 」開頭的行進 stdout，
舊碼會把那些行加進 passed_names：削弱守衛檔（3 真名 dummy＋2 假名 dummy、
print 偽造剩下 2 期望名 summary 行）計數足、無其它結果類、「身份齊」→ OK
＝假綠燈（r1324 RED 實證：('anchors', True, 'pytest rc=0（身份齊；expected 5
passed, got 5；…）')；r1296/r1314 同族：計數守住身份未守；H-0：漏掉一項得到的
綠燈就是漏洞成因）。修：_parse_passed_names 只認「short test summary info」標頭
行以來的段（真 -rA summary，pytest 穩定契約、不受 repo addopts 影響——r1314
實測同形）、nodeid 須含測試檔名（defense in depth）；段不存在＝未測量→空集
→missing→BROKEN（I-4：未測量不是通過）。負控制：tests/test_reqloop_freeze_check.py
::test_guard_suite_printed_summary_spoof_negative_control。

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

背景（2026-11-10 r1393，vq-el4.81）：新增第 12 項 mandated 檢查 now_redline（11→12 項）——
r1392 的 NOW.md 紅線轉抄守衛（tests/test_reqloop_now_redline.py，5 案）只在 pytest
套件內跑；旁路 pytest、只看本 ruler 的 FROZEN_STATE_OK 時，紅線轉抄漂移（一個
hash 前綴／行數、或整行被刪）仍不被一鍵 ruler 測量（H-0 同型：漏掉一項得到的綠燈
就是漏洞成因）。本項調用同一把尺（redline_violations），不重寫解析邏輯（vrun 同原則）；
守衛檔／NOW.md 缺 → BROKEN（I-4：未測量不是通過）。紀律（r1387/r1388 同型）：改
ruler 須同步顯式更新 GUARD_CONTENT_PIN 之 ops/reqloop/freeze_check.py pin 並留記錄。
r1393 改 ruler 但 pin 未更新（守衛照設計抓到、本檔 3 GUARD_CONTENT_PIN 測試紅＝
r1386 同型遺漏）；r1394 依紀律補 pin（cfbfba31…→新值，解凍記錄見
tests/test_reqloop_freeze_check.py）。負控制：
tests/test_reqloop_freeze_check.py::test_now_redline_negative_controls（hash 漂移／
NOW 缺／守衛檔缺，3 路徑全 BROKEN）。

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
DEFAULT_QUEUE = Path("/srv/vlab/queue")  # 審查指示 #5：人類核准前此處必須無任務
FILING = REPO / "ops" / "audits" / "g25_all_gates_filing.json"
IN_SCOPE = ("vacant_network", "tests", "ops")
BASE_BRANCH = "auto/qwen27b"
# r1309：規範三分支 worktree（wt_clean 守衛對象；審查指示 #3 點名 qwen27b/worker/argon）
CANONICAL_WORKTREE_BRANCHES = ("auto/qwen27b", "auto/worker", "auto/argon")
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


def _pytest(test_file: str, cwd: Path = REPO, extra: tuple[str, ...] = ()) -> tuple[int, str, str]:
    """跑 pytest，回 (rc, tail, 全量輸出)（r1314 加全量輸出：收集逐測 PASSED 測試名）。"""
    p = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, *extra],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = (p.stdout or "") + (p.stderr or "")
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return p.returncode, tail, out


SUMMARY_RESULT_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|error|errors|xfailed|xpassed|deselected)"
)



def _passed_lines(out: str, test_file: str) -> list[str]:
    """從 pytest -rA short test summary 段收集匹配 test_file 的 PASSED 行（r1327，vq-el4.51）。

    r1324 只認「short test summary info」標頭行以來的段、但取「第一處」標頭為段首——
    守衛檔的 dummy 測試可 print 偽標頭＋偽「PASSED <nodeid>」行（-rA 下 PASSES 段顯示
    通過測試的 captured stdout；capfd.disabled() 更直接），偽頭必在真頭之前，舊碼以偽頭
    為段首→偽名進身份集＝假綠燈（r1327 RED 實證；r1296/r1314/r1324 同族：計數守住
    身份未守）。真 summary 由 pytest 於 session 結束時輸出：測試執行期的 print 必在其
    之前，故段首＝「最後一處」標頭行；nodeid 須含測試檔名（defense in depth）；段不存在
    （pytest 未跑／-rA 缺席＝未測量）→空列表→caller 的 missing 非空→BROKEN
    （I-4：未測量不是通過）。段內行數另由 caller 與 passed 計數對帳（見 _check_guard_suite）。
    """
    lines = out.splitlines()
    try:
        start = max(
            i for i, ln in enumerate(lines) if "short test summary info" in ln
        )
    except ValueError:
        return []
    out_lines: list[str] = []
    for ln in lines[start + 1:]:
        ln = ln.strip()
        if ln.startswith("PASSED ") and test_file in ln and "::" in ln:
            out_lines.append(ln)
    return out_lines


def _parse_passed_names(out: str, test_file: str) -> set[str]:
    """同段 PASSED 行→通過測試名集合（r1324 起只認 short test summary 段，見 _passed_lines）。"""
    names: set[str] = set()
    for ln in _passed_lines(out, test_file):
        names.add(ln.split("::", 1)[1].strip())
    return names


def _check_guard_suite(
    name: str, test_file: str, expected_passed: int,
    expected_names: tuple[str, ...], cwd: Path = REPO,
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

    r1314（vq-el4.49）：計數足必要但不充分（r1296 同型：計數守住身份未守）——
    守衛測試被換成同數 assert True dummy（全綠、rc=0、計數足、無 skipped）時舊計數
    守衛仍判 OK＝假綠燈（r1314 RED 實證）。故以 pytest -rA 的 short test summary
    逐行 `PASSED <nodeid>` 收集通過測試名（-rA 不受 repo addopts -q 影響——
    r1314 實測：pyproject addopts="-q …" 令 -v 被抵消、無逐測行；-rA 穩定）、
    要求 ⊇ 期望集（EXPECTED_ANCHOR_TEST_NAMES／EXPECTED_CI_CONTRACT_TEST_NAMES）；
    缺失即 BROKEN 且 detail 點名。

    r1327（vq-el4.51）：r1324 只擋 plain print（偽行在標頭前、不進段），但測試體
    可 print 偽「short test summary info」標頭＋偽 PASSED 行，舊碼取第一處標頭為段首
    →偽名進身份集＝假綠燈（r1327 RED 實證）。收緊：段首＝最後一處標頭行（真 summary
    於 session 結束時輸出、測試執行期的 print 必在其之前）＋計數錨（段內 PASSED 行數
    == passed；段內多出一行偽行即破→BROKEN，fail-closed，I-4）。
    """
    rc, tail, out = _pytest(test_file, cwd, extra=("-rA",))
    counts: dict[str, int] = {}
    for n, cat in SUMMARY_RESULT_RE.findall(tail):
        counts[cat] = counts.get(cat, 0) + int(n)
    passed = counts.get("passed")
    other = {k: v for k, v in counts.items() if k != "passed"}
    # 身份守衛（r1314，r1296 同型；r1324 收緊：只認 -rA short test summary 段、
    # nodeid 須含測試檔名；r1327 再收緊：段首＝最後一處「short test summary info」
    # ——真 summary 於 session 結束時輸出、測試執行期的 print 偽頭必在其之前，見
    # _passed_lines——＋計數錨：真 -rA 段恰每通過測試一行 PASSED，段內行數須 ==
    # passed，段內多出一行偽行即破→BROKEN）。
    passed_lines = _passed_lines(out, test_file)
    passed_names = {ln.split("::", 1)[1].strip() for ln in passed_lines}
    missing = [n for n in expected_names if n not in passed_names]
    count_bad = passed is not None and len(passed_lines) != passed
    ok = (
        rc == 0
        and passed == expected_passed
        and not count_bad
        and not other
        and not missing
    )
    # detail 截斷 160 字（record）：缺名置首（r1314），長測試名不被截斷。
    record(
        name, ok,
        f"pytest rc={rc}（"
        + (f"缺守衛測試: {', '.join(missing)}" if missing else "身份齊")
        + (
            f"；summary 段 PASSED 行 {len(passed_lines)}≠passed {passed}（偽 summary 段？）"
            if count_bad
            else ""
        )
        + f"；expected {expected_passed} passed, got {passed}；summary: {tail}"
        + (f"；其它結果類 {other}）" if other else "；無其它結果類）"),
    )


def check_anchors(cwd: Path = REPO) -> None:
    _check_guard_suite(
        "anchors", "tests/test_reqloop_frozen_anchors.py", 5,
        EXPECTED_ANCHOR_TEST_NAMES, cwd,
    )


def check_ci_contract(cwd: Path = REPO) -> None:
    _check_guard_suite(
        "ci_contract", "tests/test_reqloop_ci_contract.py", 2,
        EXPECTED_CI_CONTRACT_TEST_NAMES, cwd,
    )


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

# 守衛測試身份（r1314，vq-el4.49；r1296 同型：計數守住身份未守）：
# 來源＝tests/test_reqloop_frozen_anchors.py 與 tests/test_reqloop_ci_contract.py
# 現行測試函數名（審查指示 #1 點名的兩份守衛檔）。
EXPECTED_ANCHOR_TEST_NAMES = (
    "test_repair_py_is_frozen",
    "test_extract_py_boundary_is_frozen",
    "test_guard_detects_tampered_copy",
    "test_g25_filing_code_hashes_match_repo",
    "test_filing_guard_detects_drift",
)
EXPECTED_CI_CONTRACT_TEST_NAMES = (
    "test_reqloop_tests_never_execute_non_contract_imports",
    "test_guard_negative_control_scipy_numpy_flagged",
)


# 2026-11-13 人類裁決 §3 受控解凍：extract.py 與 checks.py 解凍；run_eval.py 仍凍結。
# g25 filing 為歷史備案（不改）：extract.py 記 51abfec3…、checks.py 記 c7589c61…；
# 仍凍結的 run_eval.py 須與現行 repo 100% 吻合；
# 解凍檔之現行基線由 tests/test_reqloop_frozen_anchors.py 與 now_redline 把守。
HISTORICAL_CODE_FILING_SHA256 = {
    "vacant_network/reqloop/extract.py": "51abfec319d21813d7223bc5aa48417417680ba09aa0bd4d097b2c49ea223da7",
    "vacant_network/reqloop/checks.py": "c7589c610c629380f8919a08e1e707bb7ad65143cd4e0131a301158ab82fd4f4",
}


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
        if rel in HISTORICAL_CODE_FILING_SHA256:
            match = bool(mine is not None and mine == meta.get("sha256")) or (
                meta.get("sha256") == HISTORICAL_CODE_FILING_SHA256[rel]
            )
        else:
            match = mine is not None and meta.get("sha256") is not None and mine == meta["sha256"]
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


def check_g3gate(cmd: list[str] | None = None) -> None:
    """G3 發射前置：`g3gate --plan` 收斂＝rc 0 且 NOT FIRED 且 G3GATE PLAN OK，
    三者缺一即 BROKEN（I-4：未測量不是通過）。

    r1321：cmd 參數可注入（預設＝真命令，main() 行為逐位不變），供紅路負控制
    ——本項曾是 10 項 mandated 中唯一沒有負控制的一項（repo 紀律：先證明守衛會紅）。
    假命令＝純 print 腳本：0 模型呼叫、不觸真 g3gate 模組（紅線：G3 未 --fire）。
    """
    if cmd is None:
        cmd = [sys.executable, "-m", "vacant_network.reqloop.g3gate", "--plan"]
    p = subprocess.run(
        cmd,
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


def check_queue_empty(queue: Path | None = None) -> None:
    """queue_empty：/srv/vlab/queue/ 在人類核准前必須為空（審查指示 #5：核准前
    嚴禁向 /srv/vlab/queue/ 放入新任務）。

    口徑：g3gate_plan 只驗「未發射」（NOT FIRED），不驗「queue 是否有任務」——
    本檢查補上該缺口（r1309/r1321 同型：把人工紅線機械化；I-4：未測量不是通過）。
    r1343（vq-el4.56）收緊：隱藏條目（dotfile）也計數——r1339 首版以
    `startswith(".")` 跳過隱藏項，非空 queue（僅隱藏檔）被計成「0 任務檔」判 OK＝
    假綠燈（r1272 空檔 vacuous、r1288 null-sha 同族；I-4：未測量不是通過）；
    隱藏任務檔也是任務檔（紅線 #5 是「嚴禁放入新任務」，不區分可見/隱藏）。
    語義：
      - queue 為目錄且空 → OK（無任務、符合紅線）；
      - queue 為目錄但非空（含僅隱藏條目）→ BROKEN（detail 點名任務檔；紅線 #5 違反）；
      - queue 不存在/非目錄 → OK（無 queue 即無任務；detail 點名 scope=absent）。
    queue 路徑可注入（CI/沙盒用 tmp_path，不碰真 /srv/vlab/queue/）。
    唯讀：只列目錄，不寫、不刪、不發射（0 model calls）。
    """
    if queue is None:
        queue = DEFAULT_QUEUE
    if not queue.is_dir():
        record("queue_empty", True,
               f"queue {queue} 不存在/非目錄 → 無任務可入隊（scope=absent；"
               "審查指示 #5 未違反）")
        return
    try:
        # r1343：計數所有條目（含隱藏）——跳過隱藏項＝非空 queue 可被讀成空（假綠燈）。
        entries = sorted(p.name for p in queue.iterdir())
    except OSError as e:
        record("queue_empty", False,
               f"queue {queue} 不可列讀: {e}（未測量、I-4）")
        return
    if entries:
        record("queue_empty", False,
               f"queue {queue} 非空（{len(entries)} 任務檔（含隱藏）: {entries[:3]}…）"
               "——人類核准前嚴禁入隊（審查指示 #5；r1343 起隱藏檔也計數）")
    else:
        record("queue_empty", True,
               f"queue {queue} 空（0 任務檔（含隱藏）；審查指示 #5 未違反）")


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

    r1386 單位修正（vq-l6u）：訊息裡的 {len(m)}B 實為 str 字元數被標成位元組（CJK
    多字位元組 → wc -c 對不上：鏡像實 1868B 卻報 1372B＝綠燈無法用 wc 複核，H-0 同構）。
    改為 len(s.encode('utf-8'))；檢查邏輯（startswith／行邊界／條目錨點）全部不變——
    UTF-8 無歧義性保證字元前綴 ⟺ 位元組前綴。
    """
    canon = repo / "STATE.md"
    mirror = repo / "ops" / "STATE.md"
    try:
        c = canon.read_text(encoding="utf-8")
        m = mirror.read_text(encoding="utf-8")
    except OSError as e:
        record("bk_state", False, f"unreadable: {e}")
        return
    # r1386：訊息報 UTF-8 位元組數（可被 wc -c 複核）；len(str) 是字元數，CJK 下兩者不同。
    cb, mb = len(c.encode("utf-8")), len(m.encode("utf-8"))
    if "## Current State" not in m:
        record("bk_state", False, "mirror ops/STATE.md lacks '## Current State' header")
        return
    if not c.startswith(m):
        record(
            "bk_state", False,
            f"DRIFT: canonical {cb}B 不以 mirror {mb}B 為前綴（Current State 不同步）",
        )
        return
    if not m.endswith("\n"):
        record(
            "bk_state", False,
            f"TRUNCATED: mirror {mb}B 為 canonical 之 byte 前綴但非行邊界結尾"
            "（最新條目尾部被砍）——截斷鏡像不是同步（I-4：未測量不是通過）",
        )
        return
    if len(m) < len(c) and ENTRY_START_RE.match(c, len(m)) is None:
        record(
            "bk_state", False,
            f"TRUNCATED: mirror {mb}B 為 canonical 之 byte 前綴但餘部非日期條目起始"
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
            f"NO_ENTRY: mirror {mb}B 末行不是 canonical 最新條目行"
            "（鏡像零條目/末行停滯——餘部雖以新條目起始，鏡像本身未承載當前狀態，"
            "不是同步；I-4：未測量不是通過）",
        )
        return
    record("bk_state", True, f"mirror {mb}B == canonical title+Current State（同步）")


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


def check_worktree_clean(repo: Path = REPO) -> None:
    """wt_clean：規範三分支 worktree in-scope（vacant_network/tests/ops）無 staged/未
    commit/未追蹤殘留（r1309、審查指示 #3 機械化）。

    審查指示 #3：「跨三分支（qwen27b, worker, argon）必須及時同步，嚴禁 staged 未
    commit 殘留引發 in-scope diff 導致 CI live 測試紅燈」。本輪實證洞（舊碼、主
    repo live）：in-scope 殘留 `?? ops/reqloop/zz_scratch_r1309.txt` 存在時，舊
    freeze_check（9 項）仍輸出 VERDICT: FROZEN_STATE_OK rc=0＝假綠燈（H-0 同構：
    漏檢查項得到的綠燈就是洞的成因；I-4：未測量不是通過）。
    口徑（與 r1300「CI 量被測 commit」一致）：
      attached（本地 dev/worktree）→量三分規範 worktree（任一缺失＝該分支 worktree
      未測量→fail-closed BROKEN）；detached（CI 沙盒）→只量 checkout 本身（被測
      commit），local worktrees 不可達、detail 點名 scope、不冒充已量。
    """
    attached = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).returncode == 0
    if attached:
        p = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo, capture_output=True, text=True,
        )
        if p.returncode != 0:
            record("wt_clean", False, f"git worktree list rc={p.returncode}（未測量、I-4）")
            return
        branch_to_path: dict[str, str] = {}
        block: list[str] = []

        def flush() -> None:
            d: dict[str, str] = {}
            for line in block:
                k, _, v = line.partition(" ")
                if v:
                    d[k] = v
            block.clear()
            b = d.get("branch", "")
            if b.startswith("refs/heads/") and "worktree" in d:
                branch_to_path[b[len("refs/heads/"):]] = d["worktree"]

        for line in p.stdout.splitlines():
            if line == "":
                flush()
            else:
                block.append(line)
        flush()
        missing = [b for b in CANONICAL_WORKTREE_BRANCHES if b not in branch_to_path]
        if missing:
            record("wt_clean", False,
                   f"no worktree for {missing}（未測量、I-4：未測量不是通過）")
            return
        targets = [(b, branch_to_path[b]) for b in CANONICAL_WORKTREE_BRANCHES]
        scope = "local attached"
    else:
        targets = [("<checkout>", str(repo))]
        scope = "detached checkout（CI：只量被測 commit、local worktrees 未測量）"

    parts: list[str] = []
    dirty = False
    for label, path in targets:
        sp = subprocess.run(
            ["git", "status", "--porcelain", "--", *IN_SCOPE],
            cwd=path, capture_output=True, text=True,
        )
        if sp.returncode != 0:
            record("wt_clean", False,
                   f"git status rc={sp.returncode} at {path}（未測量、I-4）")
            return
        entries = [l for l in sp.stdout.splitlines() if l.strip()]
        if entries:
            dirty = True
            parts.append(f"{label}: RESIDUE {entries[:3]}")
        else:
            parts.append(f"{label}: clean")
    if dirty:
        record("wt_clean", False, f"DIRTY（{scope}）: " + "；".join(parts))
    else:
        record("wt_clean", True,
               f"in-scope clean {len(targets)}/{len(targets)}（{scope}）: " + "；".join(parts))


def check_now_redline(
    now: Path | None = None,
    guard: Path | None = None,
) -> None:
    """now_redline：NOW.md 紅線「凍結 4 檔＋filing N sha256」契約行 vs 磁碟逐條核實（r1393）。

    背景：r1392 的轉抄守衛只在 pytest 套件內跑——旁路 pytest、只看本 ruler 的
    FROZEN_STATE_OK 時，紅線轉抄漂移（一個 hash 前綴／行數，或整行被刪）仍不被
    一鍵 ruler 測量（H-0 同型）。本項把它接進 ruler，使審查指示 #4 的「轉抄精度」
    在 12 項一鍵裁決內可驗證。

    唯一實現：載入 tests/test_reqloop_now_redline.py 並調用其 redline_violations()
    （同一把尺、無第二份解析邏輯、vrun 同原則）。該檔缺／NOW.md 缺 → BROKEN
    （I-4：未測量不是通過；沙盒裡本 ruler 被拷走時即走此 fail-closed 路徑）。
    """
    import importlib.util

    if guard is None:
        guard = REPO / "tests" / "test_reqloop_now_redline.py"
    if now is None:
        now = REPO / "NOW.md"
    if not guard.is_file():
        record("now_redline", False, f"BROKEN：紅線守衛模組缺（未測量，I-4）：{guard}")
        return
    spec = importlib.util.spec_from_file_location("reqloop_now_redline_guard", guard)
    if spec is None or spec.loader is None:
        record("now_redline", False, f"BROKEN：紅線守衛模組不可載入（未測量，I-4）：{guard}")
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    violations = mod.redline_violations(now)
    if violations:
        record("now_redline", False, "NOW.md 紅線漂移: " + "; ".join(violations))
    else:
        record("now_redline", True, "NOW.md 紅線（凍結 4 檔＋filing sha256）與磁碟逐條相符（唯一實現：redline_violations）")


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
    # 其餘各項照跑，12 項全在輸出＋單一裁決行（I-4：未測量不是通過；r1393 起 12 項）。
    run_check("anchors", check_anchors)
    run_check("ci_contract", check_ci_contract)
    run_check("diff_worker", lambda: check_diff("auto/worker", "diff_worker"))
    run_check("diff_argon", lambda: check_diff("auto/argon", "diff_argon"))
    run_check("filing_code", check_filing_code)
    run_check("filing_sources", check_filing_sources)
    run_check("g3gate_plan", check_g3gate)
    run_check("queue_empty", check_queue_empty)
    run_check("bk_state", check_bookkeeping_state)
    run_check("bk_now", check_bookkeeping_now)
    run_check("wt_clean", check_worktree_clean)  # r1309：三分支 worktree in-scope 殘留
    run_check("now_redline", check_now_redline)  # r1393：NOW.md 紅線契約行 vs 磁碟（指示 #4 機械化進一鍵 ruler）

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{name:<{width}}  {'OK' if ok else 'BROKEN'}  {detail}")
    all_ok = all(ok for _, ok, _ in results)
    print("VERDICT: " + ("FROZEN_STATE_OK" if all_ok else "FROZEN_STATE_BROKEN"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
