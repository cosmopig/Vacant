#!/usr/bin/env python3
"""H 臂的 V/GT 洩漏動態稽核（跑在 run 的產物上，零模型呼叫）。

規格：`docs/HARNESS_STUDY_2026-09-07.md` §5.8。

**為什麼一定要跑在 rows／calls 上，不能只讀原始碼**：
「程式碼裡沒有 import 隱藏測資」不能證明「沒有 GT 進 prompt」——例如未來有人把
`conform_failure_detail` 的輸出擴充成帶期望值，靜態檢查照樣全綠。這支唯一的
輸入是**實際送出去的文字**（`calls.jsonl` 的 `messages`／`prompt` 全文）。

⚠ **D7：可見測資的內容（args／got／want）在 H 臂是刻意進 worker prompt 的**
  （HARNESS_STUDY §5.8；**本 repo 第一次**——既有的 OFF／CONFORM／OFF5 只送題目敘述）。
  合法性依據：`visible` 測資照設計就是給供應者看的驗收條件
  （LCB 的 assert 訊息三個欄位全部來自 `visible_tests`），
  **只有 `hidden \\ visible`（隱藏測資扣掉可見測資）那一段才是 GT**。
  所以這支稽核的對象逐字是 **`hidden \\ visible`**，不是「有沒有測資進 prompt」
  ——那個問題的答案是「有，而且是設計要的」，
  斷言「visible 沒出現」會**必然失敗**，因為它按設計就在裡面。

三條斷言（任何一條命中 ⇒ 整個 run 作廢，照 SPEC_GAIN §7 落盤並公開，
不得只修不報）：

  1. 送出的文字不含驗收碼專屬識別字（那幾個雙底線名字、`exec(`）
     ⇒ 驗收碼的**原始碼**從來沒有被送給模型，只有 `str(exc)` 被轉發。
     ⚠ 例外只有一個：`harness_arms._RULES` 那句給模型的禁令本身含 `exec(`
       （「Do not call … exec() …」）。掃描前把那個**凍結常數**整段扣掉；
       扣的是逐字相等的那一段，任何別處出現的 `exec(` 照樣會被抓到。
  2. 對該題「隱藏測資 \\ 可見測資」的每一個 case，`repr(args)` 與 `repr(expected)`
     都不出現在任何送出的文字裡。
  3. MBPP+ 的複製跑：另外斷言不含只在隱藏側出現的輸入運算式（同一條規則，
     只是那個題庫的驗收碼形狀不同）。

**誠實邊界**：`repr(expected)` 太短時（`0`、`[]`、`True`）子字串比對必然命中，
那不是洩漏而是量具沒有鑑別力。這支**不**把那種 needle 算成違規，但會**單獨列出
被跳過的數量**（`needles_skipped_trivial`）——跳過的東西要說出來，
不能讓「沒有違規」順手把「沒有檢查」蓋掉。

⚠ **round460e：量具修過一次，改的是量具不是判準**（2026-09-08）。
  R460 冒煙（n=3）跑出 **24 筆 `hidden_case_leak`，全部**的 needle 是 `True`／`False`
  ——來源是**模型自己**在回應裡寫的 `SELFTEST: […] -> True` 那幾行，
  而隱藏測資的 `expected` 剛好也是布林值。四個字的 needle 在自然語言裡必然命中：
  那是量具沒有鑑別力，不是 GT 洩漏。判準因此改成
  「`repr` 落在**凍結的瑣碎字面值集合** `TRIVIAL_NEEDLE_REPRS` 內、
  或長度 < `MIN_NEEDLE_CHARS`（6）⇒ 跳過並單獨計數」。
  ⚠ 這一格放寬了偵測面，所以它必須**同時**有反向牙齒：
  `tests/test_gain_harness_arms.py` 有一條負控——把一個**真的**隱藏 case 的 repr
  塞進送出的文字，仍然必須判 VIOLATION。放寬而沒有負控＝把稽核關掉。

⚠ **round460r：稽核範圍改成 v2——只查 harness 自己寫的文字**（2026-09-11，
  在任何 r460r 資料之前；Fable R5）。v1 把**整段送出文字**當掃描對象，
  於是 R460 六塊共報 90 筆 `hidden_case_leak`／`check_code_identifier`，
  逐筆分類之後**全部**是偽陽性（`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §一）：
  題目原文 54、模型自己的回覆 15（含一筆把 Rules 那行改寫、因此帶著 `exec(`）、
  harness 回饋引述模型自己 SELFTEST 的 12、可見測資失敗訊息的 `want=`／`got=` 回聲 9。
  **量具偽陽性會把真訊號淹掉**：90 筆噪音之下，第 91 筆真的洩漏沒有人看得出來。

  v2 的判準是**這段文字是誰寫的**，逐條：
    (a) **題目原文不查**——`task['prompt']` 逐字扣掉。它六臂共用、與 OFF 相同，
        題目自己提到某個陣列不是 harness 洩漏。
    (b) **assistant 訊息完全不查**——模型自己寫的東西不是 harness 寫進 prompt 的。
        （flattened 線路模式下整段對話被攤平成一則 user 訊息 ⇒ 先依
        `--- REPLY n ---` 標記切回角色再套這一條，見 `split_flattened`。）
    (c) **回饋訊息裡的回聲不算 harness 的話**，三條、各自很窄：
        · `visible_check_source`：needle 逐字在該題 `visible_check` 原始碼裡
          （D7：可見測資照設計就給 worker 看，它不是 `hidden \\ visible`）。
        · `model_own_selftest_same_request`：needle **等於**（不是包含）
          harness 用**自己那支解析器**從同一次請求的模型回覆裡讀出來的
          某個 `SELFTEST` 值——`SELFTEST_SUFFIX` 只是把它原封不動印回去。
        · `got=` 那一格是**沙箱回聲**，掃描前扣掉：它逐字是
          `repr(候選函式(*可見測資的 args))`，harness 沒有任何管道能把隱藏 GT
          放進去；真要從隱藏側取值，變的會是 `args=`／`want=`／`you expected=`，
          **那三格照查**。
    (d) **凍結的 Rules 那行照舊扣掉**（v1 就有；`exec(` 唯一的合法出處）。
  其餘 harness 自己寫進 system／user 的文字**一律照查**；`system` 訊息
  **一格豁免都不給**（persona 文字沒有回聲的理由），而且
  `CODE_NEEDLES`（`__tests`／`__aeq`／`__canon`）**不給 (c) 的豁免**——
  驗收碼原始碼被貼進 user 訊息永遠是紅的。

  ⚠ **與 Fable 原文的一處明文偏離**：R5 寫的是「the immediately preceding
  assistant message」，那擋不住 HOC 的 14 筆——`SELFTEST` 的來源是**計畫輪**
  的回覆，不是緊鄰的前一則。因此範圍改成「同一次請求裡的任何一則 assistant
  訊息」，但**同時把判準收得比原文更緊**：不是子字串比對，而是「等於 harness
  自己解出來的那個 SELFTEST 值」（見 `model_selftest_reprs` 的 docstring：
  模型寫 `["NS", 1]`、harness 印 `['NS', 1]`，子字串比對本來就會漏）。
  淨效果是**豁免面比 R5 原文小**，理由與逐筆對帳在
  `DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md` §五。

  R460 六塊逐筆對帳（90 筆 v1 命中 → v2 的去向，`--scope v1`／`v2` 各跑一次可重算）：
  題目原文 (a) 54、assistant 訊息 (b) 17、SELFTEST 豁免 14、可見驗收碼豁免 4、
  `got=` 沙箱回聲 1 ⇒ **v2 六塊全 CLEAN、零違規**。
  （與 `DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md` §一那份人工分類總數相同、
  分格不同：機械規則對每一筆只記**第一條**適用的排除理由。）

  ⚠ v1 **沒有被刪掉**：`--scope v1` 逐字重現 R460 那 90 筆，
  收官紀錄因此仍然可重跑（`tests/test_r460r_scheduler.py` 對釘兩個 scope 的數字）。

用法（D9：**六塊各跑一次，六塊都要綠才算過**）：
    for b in a1 a2 a3 b1 b2 b3; do
      python3 ops/gain/harness_vgt_audit.py --run runs/g_r460_harness_lcb2_$b --bank lcb2
    done
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.harness_arms import (FLATTEN_HEADER,  # noqa: E402
                                   RULES_NO_CALL_LINE, VARIANTS, _RULES)

# 驗收碼專屬的識別字。`exec(` 是最弱的一條（凍結常數會撞到，見上面的例外說明），
# 其餘三個只可能來自驗收碼本身。
CODE_NEEDLES = ("__canon", "exec(", "__aeq", "__tests")

# 短到子字串比對沒有鑑別力的 needle 不算違規，但要單獨計數。
# 6：`True`(4)／`False`(5) 是冒煙實測踩到的兩個——模型自己會在回應裡寫
# `SELFTEST: … -> True`，而隱藏 case 的 `expected` 剛好也是布林。
MIN_NEEDLE_CHARS = 6

#: **凍結**的瑣碎字面值集合：這些 repr 在任何一段自然語言／程式碼裡都會出現，
#: 命中它們證明不了任何事。逐字凍結（不是用型別判斷）是為了讓「跳過什麼」
#: 這件事可被逐字稽核——放寬偵測面的那一格必須自己說得出放寬了哪幾個字串。
TRIVIAL_NEEDLE_REPRS = frozenset({
    "True", "False", "None", "0", "1", "-1", "[]", "{}", "()", "''", '""',
})


def is_trivial_needle(needle: str) -> bool:
    """這個 needle 有沒有鑑別力。沒有 ⇒ 跳過並單獨計數，**不算成 CLEAN 的證據**。"""
    return needle in TRIVIAL_NEEDLE_REPRS or len(needle) < MIN_NEEDLE_CHARS


#: 送出文字裡**唯一**允許出現 `exec(` 的地方：給模型的那句禁令（`harness_arms`
#: 的 `RULES_NO_CALL_LINE`，逐字凍結）。掃描前只扣掉這一行與整段 Rules 模板，
#: 別處的 `exec(` 照樣算違規。
FROZEN_SENT_CONSTANTS = (RULES_NO_CALL_LINE, _RULES)


def strip_frozen_constants(text: str) -> str:
    """把 H 臂的凍結 prompt 常數逐字扣掉（相等才扣，不做模糊比對）。"""
    out = text or ""
    for frozen in FROZEN_SENT_CONSTANTS:
        out = out.replace(frozen, "")
    return out


def sent_texts(rec: dict) -> list[str]:
    """一筆 `calls.jsonl` 實際送出去的全部文字（system ＋ 每一則訊息）。

    v1 的掃描對象就是這個列表的每一格。v2 改用 `classify_texts()`
    ——同一批文字，但每一格帶著**角色**，好讓「誰寫的」成為判準。
    """
    return [t for _role, _i, t in classify_texts(rec)]


# ── v2：角色歸屬（誰寫的）────────────────────────────────────────────────
AUDIT_SCOPES = ("v1", "v2")

#: flattened 線路模式的段落標記（`harness_arms.flatten_messages` 逐字產生）。
#: `REQUEST n`／`CURRENT REQUEST` ＝ user、`REPLY n` ＝ assistant。
_FLAT_SECTION_RE = re.compile(r"^--- (CURRENT REQUEST|REQUEST \d+|REPLY \d+) ---$",
                              re.MULTILINE)


def split_flattened(text: str) -> list[tuple[str, str]] | None:
    """攤平成一則 user 訊息的對話 → `[(role, text), …]`；不是攤平格式回 None。

    ⚠ 為什麼一定要做這件事：flattened 之下**整段對話**（含模型自己的回覆）
    被包進一則 `role="user"` 的訊息裡。不還原角色的話，v2 的 (b)
    「assistant 訊息不查」會整條失效——模型寫的東西會被當成 harness 寫的。
    R460 六塊全是 multiturn（G6），所以這段在 R460 上不改變任何數字；
    它擋的是**下一次**線路退回攤平模式時量具安靜地變回 v1。
    """
    if not (text or "").startswith(FLATTEN_HEADER):
        return None
    labels = _FLAT_SECTION_RE.findall(text)
    parts = _FLAT_SECTION_RE.split(text)
    if not labels:
        return None
    out: list[tuple[str, str]] = []
    # parts = [header, label1, body1, label2, body2, …]
    for i, label in enumerate(labels):
        body = parts[2 * i + 2] if 2 * i + 2 < len(parts) else ""
        out.append(("assistant" if label.startswith("REPLY") else "user", body))
    return out


def classify_texts(rec: dict) -> list[tuple[str, int, str]]:
    """一筆 `calls.jsonl` 送出的文字，逐格帶上角色。

    回 `[(role, message_index, text), …]`，`role ∈ {"system","user","assistant"}`。
    `message_index` 與 v1 的編號**逐格相同**（system 佔 0），
    好讓 v1／v2 的違規清單可以逐筆對照。
    攤平的那一則另外展開成多格，`message_index` 沿用那一則的編號。
    """
    out: list[tuple[str, int, str]] = []
    idx = 0
    if rec.get("system"):
        out.append(("system", idx, rec["system"]))
        idx += 1
    msgs = rec.get("messages")
    if isinstance(msgs, list) and msgs:
        for m in msgs:
            if not isinstance(m, dict):
                continue
            content = m.get("content", "")
            role = m.get("role") or "user"
            flat = split_flattened(content) if role == "user" else None
            if flat:
                out += [(r, idx, t) for r, t in flat if t]
            elif content:
                out.append((role, idx, content))
            idx += 1
    elif rec.get("prompt"):
        out.append(("user", idx, rec["prompt"]))
    return [(r, i, t) for r, i, t in out if t]


#: 沙箱回聲欄位：`got=` 之後、到下一個**凍結**欄位名（或行尾）之前的那一段。
#: 兩個來源逐字都是凍結模板：
#:   `vacant/codebench.py::_lcb_check_code` 的
#:     f"args={…!r} got={__got!r} want={…!r}"        ← 可見測資的 assert 訊息
#:   `harness_arms.SELFTEST_SUFFIX` 的
#:     "args={args!r} got={got} you expected={expected!r}"
#: `got` 逐字是 `repr(候選函式(*可見測資的 args))` ⇒ 它是**模型自己程式的輸出**，
#: harness 沒有任何管道把隱藏 GT 送進這一格；真要從隱藏側取值，
#: 變的會是 `args=`／`want=`／`you expected=`，而那三格**照查**。
_GOT_ECHO_RE = re.compile(r"got=.*?(?= want=| you expected=|\n|$)", re.DOTALL)
GOT_ECHO_PLACEHOLDER = "got=<sandbox-echo>"


def redact_harness_text(text: str, task: dict | None) -> str:
    """v2：把**不是 harness 寫的**那幾段從一格 harness 文字裡扣掉再掃。

    順序固定：(d) 凍結 Rules → (a) 題目原文 → (c) `got=` 沙箱回聲。
    扣掉的都是**逐字相等**的段落，不做模糊比對。
    """
    out = strip_frozen_constants(text)                      # (d)
    prompt = (task or {}).get("prompt")
    if prompt:
        out = out.replace(prompt, " ")                      # (a)
    out = _GOT_ECHO_RE.sub(GOT_ECHO_PLACEHOLDER, out)       # (c) 沙箱回聲
    return out


def model_selftest_reprs(assistant_texts: list[str]) -> set[str]:
    """同一次請求裡，模型自己那幾行 `SELFTEST:` 被 harness 解出來的 repr 集合。

    ⚠ 為什麼不是「needle 有沒有逐字出現在 assistant 訊息裡」：模型寫的是
    `SELFTEST: ["NS", 1] -> 2`（雙引號），而 `SELFTEST_SUFFIX` 印的是
    `args={args!r}` ＝ `['NS', 1]`（單引號）——**同一個值、不同寫法**，
    逐字子字串比對會漏掉它（R460 b2 實測 2 筆）。
    所以這裡走**與 harness 完全相同的那一支解析器**（`harness_arms.parse_selftests`）
    再 `repr()`：豁免的判準逐字是「這個值就是 harness 從模型自己的回覆裡讀出來、
    原封不動印回去的那一個」，不是「長得像」。
    範圍窄：只解 `SELFTEST:` 那個凍結格式，**同一次請求**之內；
    HPI／HMIX 沒有計畫輪 ⇒ 這個集合是空的 ⇒ 它們一格豁免都拿不到。
    """
    from ops.gain.harness_arms import parse_selftests
    out: set[str] = set()
    for text in assistant_texts:
        cases, _bad = parse_selftests(text)
        for args, expected in cases:
            out.add(repr(args))
            out.add(repr(expected))
            for a in (args if isinstance(args, list) else []):
                out.add(repr(a))
    return out


def needle_excuse(needle: str, task: dict, selftest_reprs: set[str]) -> str | None:
    """(c) 的兩條豁免；沒有豁免回 None（＝這一筆是真的違規）。

    1. `visible_check_source`：needle 逐字在該題可見驗收碼裡
       ⇒ D7 說可見測資本來就給 worker 看，它不是 `hidden \\ visible`。
       （會走到這裡是因為 needle 是**欄位層級**的 repr：某個隱藏 case 的
       `expected` 可以剛好等於某個可見 case 的 `expected`，而整個 case 不同。）
    2. `model_own_selftest_same_request`：needle 恰好等於 harness 從**同一次請求**
       的模型回覆裡解出來的某個 `SELFTEST` 值 ⇒ 那個值是模型自己算的，
       harness 只是原封不動印回去（`SELFTEST_SUFFIX`）。
       ⚠ 判準是**相等**不是子字串：`'[1, 2]' in '[1, 2, 3]'` 為真，
       用子字串會讓「模型寫過一個大陣列」順手豁免掉它的每一段。
    """
    if needle in (task.get("visible_check") or {}).get("code", ""):
        return "visible_check_source"
    if needle in selftest_reprs:
        return "model_own_selftest_same_request"
    return None


def lcb_cases(check_code: str) -> list[dict] | None:
    """LCB 形狀：`__tests = <list literal>`。認不出來回 None（**不猜**）。"""
    try:
        tree = ast.parse(check_code)
    except SyntaxError:
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__tests"):
            try:
                tests = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                return None
            return tests if isinstance(tests, list) else None
    return None


def mbpp_inputs(check_code: str) -> list[str] | None:
    """MBPP+ 形狀：尾端一串 `assert __aeq(entry(*<expr>), …)`；回 `<expr>` 的原始碼。"""
    try:
        tree = ast.parse(check_code)
    except SyntaxError:
        return None
    exprs: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assert):
            continue
        for call in ast.walk(node.test):
            if isinstance(call, ast.Call):
                for arg in call.args:
                    if isinstance(arg, ast.Starred):
                        exprs.append(ast.unparse(arg.value))
    return exprs or None


def hidden_only_needles(task: dict) -> tuple[list[str], list[str]]:
    """回 `(needles, skipped)`：只在隱藏側出現的 case 的 repr。"""
    vis_code = task["visible_check"]["code"]
    hid_code = task["hidden_check"]["code"]
    needles: list[str] = []
    skipped: list[str] = []

    vis_cases, hid_cases = lcb_cases(vis_code), lcb_cases(hid_code)
    if vis_cases is not None and hid_cases is not None:
        vis_repr = {repr(c) for c in vis_cases}
        for case in hid_cases:
            if repr(case) in vis_repr:
                continue
            for key in ("args", "expected"):
                if key not in case:
                    continue
                needle = repr(case[key])
                (skipped if is_trivial_needle(needle) else needles).append(needle)
        return needles, skipped

    vis_in, hid_in = mbpp_inputs(vis_code), mbpp_inputs(hid_code)
    if vis_in is not None and hid_in is not None:
        seen = set(vis_in)
        for expr in hid_in:
            if expr in seen:
                continue
            seen.add(expr)
            for needle in {expr, _literal_repr(expr)} - {None}:
                (skipped if is_trivial_needle(needle) else needles).append(needle)
        return needles, skipped

    raise SystemExit(f"認不出驗收碼形狀：{task['task_id']}——認不出來不是通過，是沒接上。停。")


def _literal_repr(expr: str) -> str | None:
    try:
        return repr(ast.literal_eval(expr))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None


def audit_run(run_dir: pathlib.Path, tasks: dict[str, dict], *,
              scope: str = "v2") -> dict:
    """回一份可落盤的稽核結果；`violations` 非空 ⇒ 整個 run 作廢。

    `scope="v1"` ＝ round460e 的讀法（整段送出文字都掃）——留著只為了讓
    R460 收官那 90 筆逐字可重跑。`scope="v2"` ＝ round460r 起的正式判準
    （只掃 harness 自己寫的 system／user 文字，見模組 docstring）。
    """
    if scope not in AUDIT_SCOPES:
        raise SystemExit(f"unknown audit scope: {scope}（可用 {list(AUDIT_SCOPES)}）")
    calls_path = run_dir / "calls.jsonl"
    if not calls_path.exists():
        raise SystemExit(f"{calls_path} 不存在——沒有 calls 就沒有稽核對象。停。")
    violations: list[dict] = []
    excused: list[dict] = []
    n_records = n_texts = n_skipped = n_checked = n_texts_scanned = 0
    cache: dict[str, tuple[list[str], list[str]]] = {}
    unknown_tasks: set[str] = set()
    per_arm: dict[str, int] = {}
    with calls_path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            rec = json.loads(line)
            arm = (rec.get("meta") or {}).get("arm")
            if arm not in VARIANTS:
                continue
            n_records += 1
            per_arm[arm] = per_arm.get(arm, 0) + 1
            task_id = (rec.get("meta") or {}).get("task_id")
            task = tasks.get(task_id)
            classified = classify_texts(rec)
            n_texts += len(classified)
            # (b) assistant 訊息完全不查——但先留一份，(c) 的豁免要用它。
            assistant_texts = [t for role, _i, t in classified if role == "assistant"]
            selftest_reprs = (model_selftest_reprs(assistant_texts)
                              if scope == "v2" else set())
            if scope == "v1":
                targets = [(role, i, t, t) for role, i, t in classified]
            else:
                targets = [(role, i, t, redact_harness_text(t, task))
                           for role, i, t in classified if role != "assistant"]
            n_texts_scanned += len(targets)

            for role, i, raw, red in targets:
                scrubbed = strip_frozen_constants(raw) if scope == "v1" else red
                for needle in CODE_NEEDLES:
                    if needle in scrubbed:
                        violations.append({
                            "line": ln, "arm": arm, "rule": "check_code_identifier",
                            "needle": needle, "message_index": i, "role": role,
                            "task_id": task_id,
                            "excerpt": scrubbed[max(0, scrubbed.find(needle) - 80):
                                                scrubbed.find(needle) + 80]})
            if task is None:
                unknown_tasks.add(str(task_id))
                continue
            if task_id not in cache:
                cache[task_id] = hidden_only_needles(task)
            needles, skipped = cache[task_id]
            n_skipped += len(skipped)
            n_checked += len(needles)
            for needle in needles:
                for role, i, raw, red in targets:
                    hay = raw if scope == "v1" else red
                    if needle not in hay:
                        continue
                    why = (None if scope == "v1" or role == "system"
                           else needle_excuse(needle, task, selftest_reprs))
                    hit = {"line": ln, "arm": arm, "rule": "hidden_case_leak",
                           "needle": needle, "message_index": i, "role": role,
                           "task_id": task_id,
                           "excerpt": hay[max(0, hay.find(needle) - 80):
                                          hay.find(needle) + 80]}
                    if why:
                        hit["excused_as"] = why
                        excused.append(hit)
                    else:
                        violations.append(hit)
    out = {
        "run": str(run_dir), "scope": scope, "records_audited": n_records,
        "texts_audited": n_texts, "texts_scanned": n_texts_scanned,
        "per_arm": per_arm,
        # 檢查了幾個 needle、跳過幾個——跳過的要說出來，
        # 不能讓「沒有違規」順手把「沒有檢查」蓋掉（見模組 docstring 的誠實邊界）。
        # `needles_skipped_trivial` ＝ 落在 TRIVIAL_NEEDLE_REPRS 或長度 < 6 的那些。
        "needles_checked": n_checked,
        "needles_skipped_trivial": n_skipped,
        # v2 專屬：被 (c) 豁免掉的命中要**逐筆留著**，不准只留一個總數——
        # 「豁免了什麼」跟「違規了什麼」一樣是稽核證據。
        "excused_n": len(excused),
        "excused": excused,
        "excused_by_rule": {
            k: sum(1 for e in excused if e.get("excused_as") == k)
            for k in ("visible_check_source", "model_own_selftest_same_request")},
        "unknown_task_ids": sorted(unknown_tasks),
        "violations": violations,
        "verdict": "CLEAN" if not violations and not unknown_tasks else "VIOLATION",
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="H 臂 V/GT 洩漏動態稽核（零模型呼叫）")
    ap.add_argument("--run", required=True)
    ap.add_argument("--bank", default="lcb2",
                    help="題庫名（summary.json 沒有記 bank，必須顯式給，不猜）")
    ap.add_argument("--seed", default=None, help="預設讀 summary.json 的 seed")
    ap.add_argument("--out", default=None, help="稽核結果 JSON 落盤路徑")
    ap.add_argument("--scope", default="v2", choices=list(AUDIT_SCOPES),
                    help="v2（預設，round460r）只查 harness 自己寫的文字；"
                         "v1 是 round460e 的讀法，留著讓 R460 那 90 筆可重跑")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    seed = args.seed or summary["seed"]
    from ops.gain.gain_run import load_tasks
    tasks = {t["task_id"]: t for t in load_tasks(args.bank, seed, 0)}
    result = audit_run(run_dir, tasks, scope=args.scope)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    if result["verdict"] != "CLEAN":
        raise SystemExit(
            f"V/GT 稽核不通過：{len(result['violations'])} 筆違規／"
            f"{len(result['unknown_task_ids'])} 個對不到題目的 task_id"
            "——整個 run 作廢（SPEC_GAIN §7），不得只修不報。")


if __name__ == "__main__":
    main()
