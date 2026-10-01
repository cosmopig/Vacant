"""twin/grounding_gate — 分身交件的「有沒有根據」四格窗（確定性、不用模型、所有分身同一套）。

## 這支在架構裡承重什麼

裁決：`decisions/DECISION_20261001_TWIN_GROUNDING_GATE.md`；設計：`DESIGN_TWIN_BRANCHES_20261001.md` 第一節。

人類（2026-10-01）：「確保他可以正確的被觸發」「在正確的 vacant 邏輯上」「如果後續有用到那個內容，
他就可以有正確觸發」「vacant 不應該有審查規則」。所以這裡**不是**審查規則——它不看做得好不好、
不看合不合某個人的口味，只問產品原則第 2 條的那件事：**每一句話、每一個數字，在這一跑的紀錄裡
找不找得到根據**（零設定版的 `unread`／`unsourced` 同一個精神）。分身交件前走 `vacant run` 本來就有的
閘門（`launcher.run(suite_dir=…, retry_arm="revise", feedback_into="both")`），驗收套件由這一支生成。

四格窗：

| 窗 | 問什麼 | 資料來源 |
|---|---|---|
| G1 讀過了嗎 | PLAN.md「它牽動到」點名的 `地上/…`，這一跑真的打開過（點名資料夾 ⇒ 裡面至少打開過一件） | 步驟紀錄（工作區外） |
| G2 找得到出處嗎 | 成品裡的數字、片號、印紋名、位置，在這一跑讀過的東西裡找得到（兩個找得到的數相加減、千分位寫法算找得到） | 步驟紀錄＋凍結快照 |
| G3 兩個出處對得上嗎 | 成品對某實體給的值，與它讀過的帳本鏈（世界的權威）說法不同，而這一行沒有指出 | `world/materials/_facts.json` |
| G4 收據只有閘門給 | 成品裡宣稱閘門結果（通過、亮齊、綠光、拿到收據…）的陳述句 | 成品全文 |

## 怎麼接到 `vacant run`（為什麼資料是 `.py`）

`acceptance.run_suite` 只把驗收目錄裡的 `*.py` 複製進沙箱（bwrap 之下 repo 與 run-dir 都不在裡面）。
所以每一跑的 `tests_visible/` 是：`test_grounding.py`（四個 `check_*`）＋`_gg.py`（**這一支的逐字複本**，
零外部依賴）＋`_ledger.py`（這一跑的紀錄：讀過哪些檔、地上檔的內容、世界設定、信、事實表）。
`_ledger.py` 由 `twin_agent.sh` 在**每一次 pi 結束之後、凍結之前**呼叫 `prepare` 重寫（pi 已死，
分身改不到）；它同時把這一次的四格結果預先寫成一筆旁註 `twin_gate`（先於 `gate_ran`，電視才拿得到逐格結果）。
`prepare` 沒跑成就**刪掉** `_ledger.py`——四格窗見到沒有紀錄就一律不亮（量不到不是通過），不用上一次的舊紀錄。

## 失敗訊息的規矩

一句繁體中文，**只寫位置與缺的根據**（「成品第 7 行的『23』，這一跑讀過的東西裡找不到」），
不寫對錯、不寫行動者、不寫應該改成什麼；過 `memory.assert_ks1_clean`（測試逐條跑模板）。
`describe(case, ok, message) -> (id, label)`：`twinprogress` 會自動用它。label 是電視／手機用的短句，
**不得含觀眾內容**：位置只給「成品／計畫」＋行號；地上檔名、值、字詞都不進 label。

## 誠實邊界（改碼時保留）

1. **查的是根據的有無，不是好不好。** 全部有根據 ≠ 做對、≠ 有趣、≠ 合那個人。
2. **G2 是字面比對，會被巧合騙**（也放過「某個讀過的數字加 1」的下一號，真跑 h04／h11 的誤擋修法）（`雙環` 也出現在別的地上檔裡；一個數字剛好出現在別處）。
   只認阿拉伯數字；中文數字（四列、第三行）不查。三個以上相加的總數會被標出（只允許**同一份**內容裡兩個數的加減；
   但一份內容裡數字很多時——例如帳本鏈尾段 418～447——小於 30 的數都「算得出來」，這一格對它就很寬）。
   成品自己數出來的東西（共 N 項、第 N 步）不查。
3. **G3 只對 `_facts.json` 有登記的實體**（帳本鏈 30 片的印紋、第四列張數、小陶印枚數），
   而且只在**它讀過權威檔**、成品用到該實體時才判；成品同一行（或相鄰行）指出兩處對不上就不算。
4. **G4 是詞表**（`GATE_WORDS`／`RESULT_WORDS`／排除詞），改寫世界裡別人的收據句會被擋到——
   逐字引自它讀過的地上檔的句子、轉述地上某一片（含印紋名或 418–449 片號）而沒指向自己成品的句子不算。詞表與排除寫成常數＋測試。
5. 四格窗讀的是凍結快照與工作區外的步驟紀錄；步驟紀錄由 pi 擴充寫、pi 行程結束後才讀。
   **沒有 OS 隔離**：`twin_agent.sh` 外面的行程若有權限仍可改它（見 `twinagent` 誠實邊界 2）。
6. 位置：成品有多個檔時，label 裡的「成品第 N 行」不分是哪個檔（訊息裡有檔名，label 沒有）。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import sys
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent

STEP_LOG_NAME = "twin_steps.ndjson"      # 與 twinagent.STEP_LOG_NAME 同值（測試釘住）
TESTS_DIRNAME = "tests_visible"          # 與 twinprogress.SUITE_DIRNAME 同值（測試釘住）
LEDGER_NAME = "_ledger.py"
TEST_NAME = "test_grounding.py"
GG_NAME = "_gg.py"
FACTS_PATH = HERE / "world" / "materials" / "_facts.json"
CUT_NAME = "gate_cut.json"               # 被時限切掉的嘗試編號（牆鐘或整跑預算）
#: 被切掉的那一次：四格都是「未判」（ok:null），不是四個錯。與 `tv_contract.GATE_CHECK_TIMEOUT_LABEL` 同值（測試釘住）。
TIMEOUT_LABEL = "時間到，這一次沒有交件"
GATE_META_NAME = "gate_meta.json"        # twinagent 寫在 run-dir：旁註與事件檔的位置
PRECHECK_NAME = "gate_precheck.ndjson"   # prepare 每次追加一行（run-dir，撤回時整個刪）
LETTER_COPY_NAME = "letter_final.md"     # twin_letter_guard 存的、段 1 結束時的信（分身之後改不到）

#: 與 `twinagent.NOT_ARTIFACTS`／`GROUND_PREFIX` 同值（測試釘住；這一支要能單獨複製進沙箱，所以不 import 它）。
NOT_ARTIFACTS = frozenset({"TRAITS.md", "WORLD.md", "PLAN.md", "VACANT_FEEDBACK.md", "信.md"})
GROUND_PREFIX = "地上/"
MAX_ARTIFACTS = 12
MAX_ARTIFACT_BYTES = 200_000

#: 與 `twinground.MARKS` 同值（測試釘住）。
MARKS = ("魚骨", "水滴", "梯", "星", "半月", "波", "三點", "鎖扣", "雙環", "蕨葉", "螺旋", "十字")
PLACES = ("投遞口", "捏土處", "長桌廣場", "石頭閘門", "帳本鏈", "草稿角", "紙卡地", "畫架與長椅")

#: 與 `memory.KS1_FORBIDDEN` 同值（測試釘住）；訊息裡出現成品檔名時用來擋掉怪名字。
_KS1 = ("你有責任", "你會被懲罰", "你將被懲罰", "你要負責", "後果自負",
        "you are responsible", "you will be punished", "you will be held accountable")

# ---------------------------------------------------------------------------
# 四格窗的名字、短句（label）
# ---------------------------------------------------------------------------

CASES = ("check_w1_read", "check_w2_source", "check_w3_agree", "check_w4_receipt")
WINDOW_KEY = {"check_w1_read": "w1", "check_w2_source": "w2",
              "check_w3_agree": "w3", "check_w4_receipt": "w4"}
CASE_ID = {"check_w1_read": "G1", "check_w2_source": "G2",
           "check_w3_agree": "G3", "check_w4_receipt": "G4"}
#: 通過時的 label。
PASS_LABEL = {"G1": "讀過了", "G2": "找得到出處", "G3": "兩個出處對得上", "G4": "收據是閘門給的"}
#: 沒過時的 label 前綴（後面接「（成品第 7 行）」）。不含任何觀眾內容。
FAIL_LABEL = {"G1": "點名的東西沒打開", "G2": "找不到出處", "G3": "兩個出處對不上",
              "G4": "收據不是閘門給的"}
#: 沒有紀錄可對照（`_ledger.py` 沒備好）。量不到不是通過。
NO_LEDGER_MSG = "這一跑的步驟紀錄沒有備好，這一格沒辦法對照"

_LOC_RE = re.compile(r"(成品|計畫)(?:『[^』]*』)?第\s?(\d+)\s?行")


def locate(message: str) -> dict | None:
    """訊息裡第一個「成品／計畫第 N 行」→ `{"file": "artifact"|"plan", "line": N}`；沒有 ⇒ None。"""
    m = _LOC_RE.search(message or "")
    if not m:
        return None
    return {"file": "artifact" if m.group(1) == "成品" else "plan", "line": int(m.group(2))}


def describe(case: str, ok: bool, message: str = "") -> tuple[str, str]:
    """`twinprogress` 的介面：`(id, label)`。label 不含觀眾內容（位置只有「成品／計畫」＋行號）。"""
    cid = CASE_ID.get(case)
    if cid is None:
        for c, i in CASE_ID.items():
            if c.replace("check_", "") in (case or "") or i in (case or ""):
                cid = i
                break
    if cid is None:
        return "check", ("過了" if ok else "有一項沒根據")
    if ok:
        return cid, PASS_LABEL[cid]
    if (message or "").strip() == NO_LEDGER_MSG:
        return cid, "沒有紀錄可對照"
    label = FAIL_LABEL[cid]
    where = locate(message)
    if where:
        place = "成品" if where["file"] == "artifact" else "計畫"
        label += f"（{place}第 {where['line']} 行"
        n = len(_LOC_RE.findall(message))
        if n > 1:
            label += f"等 {n} 處"
        label += "）"
    return cid, label


def checks_from_result(result: dict) -> list[dict]:
    """`acceptance.run_suite` 的結果（或預先算的 `evaluate` 結果）→ `[{id,ok,label,file?,line?}]`。"""
    out: list[dict] = []
    for f in result.get("files") or []:
        for c in f.get("cases") or []:
            cid, label = describe(str(c.get("case")), bool(c.get("ok")), str(c.get("message") or ""))
            row: dict[str, Any] = {"id": cid, "ok": bool(c.get("ok")), "label": label}
            if not c.get("ok"):
                # 電視的「發現錯誤」拍要 `line`（正整數）與 `file`（artifact|plan），兩者都不含內容。
                w = locate(str(c.get("message") or ""))
                if w:
                    row["file"], row["line"] = w["file"], w["line"]
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# 讀東西
# ---------------------------------------------------------------------------

def _read(p: pathlib.Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def read_artifacts(ws: pathlib.Path) -> list[tuple[str, str]]:
    """成品＝分身寫的 `.md`／`.txt`（PLAN 等不算；規則與 `twinagent.read_outputs` 相同，但不截字數）。"""
    ws = pathlib.Path(ws)
    out: list[tuple[str, str]] = []
    if not ws.is_dir():
        return out
    for p in sorted(ws.rglob("*")):
        try:
            rel = p.relative_to(ws).as_posix()
        except ValueError:
            continue
        if (not p.is_file() or p.is_symlink() or rel in NOT_ARTIFACTS
                or rel.startswith(GROUND_PREFIX)
                or any(part.startswith(".") for part in p.relative_to(ws).parts)):
            continue
        if p.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            if p.stat().st_size > MAX_ARTIFACT_BYTES:
                continue
        except OSError:
            continue
        text = _read(p)
        if text is not None:
            out.append((rel, text))
        if len(out) >= MAX_ARTIFACTS:
            break
    return out


def _fname(name: str, artifacts: list[tuple[str, str]], idx: int) -> str:
    """訊息裡的成品位置字樣：只有一個成品就不寫檔名。"""
    if len(artifacts) <= 1:
        return "成品"
    low = name.lower()
    if len(name) > 40 or any(k in low for k in _KS1):
        return f"成品第{idx + 1}個檔"
    return f"成品『{name}』"


# ---------------------------------------------------------------------------
# 窗 1：讀過了嗎
# ---------------------------------------------------------------------------

_PATH_CHARS = r"[^\s，,。、；;：:）)」』\"'“”`<>\[\]【】（(*|]"
_PLACE_ALT = "|".join(re.escape(p) for p in PLACES)
_PATH_RE = re.compile(
    rf"(?<![A-Za-z0-9_/])(?:地上/)?(?:{_PLACE_ALT})/{_PATH_CHARS}*|地上/{_PATH_CHARS}*")
_SECTION_HEADS = ("如果你在這裡", "三個想要", "它牽動到", "步驟", "做完的樣子")
_HEAD_STRIP = re.compile(r"^[\s#>*\-+「『【(（\d.、)）]+")


def _section_range(lines: list[str]) -> tuple[int, int]:
    """PLAN 裡「它牽動到」那一節的行範圍（0 起算，左閉右開）；找不到 ⇒ 整份。"""
    start = None
    for i, ln in enumerate(lines):
        if "它牽動到" in ln[:24]:
            start = i
            break
    if start is None:
        return 0, len(lines)
    for j in range(start + 1, len(lines)):
        head = _HEAD_STRIP.sub("", lines[j])[:8]
        if any(head.startswith(h) for h in _SECTION_HEADS if h != "它牽動到"):
            return start, j
    return start, len(lines)


def named_paths(plan_text: str, ground_files: list[str]) -> list[dict]:
    """PLAN 點名的地上東西：`[{line, path, kind}]`，kind＝file／folder／missing（地上沒有這個檔）。"""
    gset = set(ground_files)
    lines = plan_text.splitlines()
    a, b = _section_range(lines)
    out, seen = [], set()
    for i in range(a, b):
        for m in _PATH_RE.finditer(lines[i]):
            p = m.group(0).rstrip(".．-_")
            if not p.startswith(GROUND_PREFIX):
                p = GROUND_PREFIX + p
            folder = p.endswith("/")
            p = p.rstrip("/")
            if p in ("地上", ""):
                continue
            if (i, p) in seen:
                continue
            seen.add((i, p))
            if p in gset:
                kind = "file"
            elif p + ".txt" in gset:
                kind, p = "file", p + ".txt"
            elif any(g.startswith(p + "/") for g in gset):
                kind = "folder"
            else:
                kind = "folder" if folder else "missing"
            out.append({"line": i + 1, "path": p, "kind": kind})
    return out


def check_read(plan_text: str | None, read: set[str], ground_files: list[str]) -> list[dict]:
    if plan_text is None:
        return [{"file": "plan", "line": None, "msg": "計畫檔（PLAN.md）不存在，沒有點名可以對照"}]
    issues = []
    for n in named_paths(plan_text, ground_files):
        p = n["path"]
        if n["kind"] == "folder":
            if not any(r.startswith(p + "/") for r in read):
                issues.append({"file": "plan", "line": n["line"],
                               "msg": f"計畫第{n['line']}行點名的資料夾『{p}』，這一跑沒有打開過裡面任何一件"})
        elif p not in read:
            issues.append({"file": "plan", "line": n["line"],
                           "msg": f"計畫第{n['line']}行點名的『{p}』，這一跑沒有成功打開過"})
    return issues


# ---------------------------------------------------------------------------
# 窗 2：找得到出處嗎
# ---------------------------------------------------------------------------

#: 提到檔名不是宣稱（「出生片_420到440.txt」裡的 420 是檔名的一部分）。
_FILENAME = re.compile(r"[\w\-\u4e00-\u9fff]+\.(?:txt|md)")
_LIST_MARK = re.compile(r"^\s*(?:[#>*\-+]+\s*)?(?:\d+[.、．)）]|[（(]\d+[)）])\s*")
_SELF_STRUCT = re.compile(
    r"第\s?\d+\s?(?:步|次|回|項|條|點|段|節|章)|步驟\s?\d+|"
    r"\d+\s?(?:分鐘|分|秒|小時|天|週|年|項|條|字|步|次|段|節|點|欄)|"
    r"(?<!第)(?<!第 )\d+\s?行")
_THOUSANDS = re.compile(r"(?<![\d,.])\d{1,3}(?:,\d{3})+(?![\d,])")
_DECIMAL = re.compile(r"(?<![\d.])\d+\.\d+(?![\d.])")
_INT = re.compile(r"(?<![A-Za-z\d.])\d+(?![\d.])")
_ADDR_BEFORE = re.compile(r"(?:第\s?|桌\s?)$")
_ADDR_AFTER = re.compile(r"^\s?[列行位桌格窗封片張枚截撮指掌]")
_MARK_CTX = re.compile(
    r"印紋\s*[：:是為]?\s*(?P<a>{m})|"
    r"(?<!\d)\d{{3}}\s*[：:，、的]?\s*(?:印紋\s*)?(?P<b>{m})|"
    r"(?P<c>{m})\s*(?:印紋|的?卡|的?陶片|的?印)".format(m="|".join(MARKS)))
_ZH_DIGIT = {"一": "1", "二": "2", "兩": "2", "三": "3", "四": "4", "五": "5",
             "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}


def tokens(line: str) -> list[tuple[str, str]]:
    """一行成品裡「要有出處」的字：`[(kind, text)]`，kind＝num／dec／mark。"""
    t = _FILENAME.sub(" ", line)
    t = _LIST_MARK.sub("", t, count=1)
    t = _SELF_STRUCT.sub(" ", t)
    out: list[tuple[str, str]] = []
    for m in _THOUSANDS.finditer(t):
        out.append(("num", m.group(0).replace(",", "")))
    t2 = _THOUSANDS.sub(" ", t)
    for m in _DECIMAL.finditer(t2):
        out.append(("dec", m.group(0)))
    t3 = _DECIMAL.sub(" ", t2)
    for m in _INT.finditer(t3):
        s = m.group(0)
        if len(s) >= 2 or (_ADDR_BEFORE.search(t3[:m.start()]) or _ADDR_AFTER.search(t3[m.end():])):
            out.append(("num", s.lstrip("0") or "0"))
    seen_marks = set()
    for m in _MARK_CTX.finditer(t):
        mk = m.group("a") or m.group("b") or m.group("c")
        if mk and mk not in seen_marks:
            seen_marks.add(mk)
            out.append(("mark", mk))
    return out


def _numbers_of(text: str) -> tuple[set[int], set[str]]:
    nums: set[int] = set()
    decs: set[str] = set()
    for m in _THOUSANDS.finditer(text):
        nums.add(int(m.group(0).replace(",", "")))
    t = _THOUSANDS.sub(" ", text)
    for m in re.finditer(r"\d+\.\d+", t):
        decs.add(m.group(0))
    for m in re.finditer(r"\d+", t):
        if len(m.group(0)) <= 9:
            nums.add(int(m.group(0)))
    return nums, decs


def known_numbers(texts: list[str]) -> tuple[list[set[int]], set[str]]:
    """每一份讀過的內容各自的數字集合（加減只在**同一份**裡算），以及所有小數的字串。"""
    per: list[set[int]] = []
    decs: set[str] = set()
    for tx in texts:
        n, d = _numbers_of(tx)
        per.append(n)
        decs |= d
    return per, decs


def number_found(n: int, per: list[set[int]]) -> bool:
    """整個數字在讀過的內容裡、比其中一個數大 1（下一號），或是**同一份**內容裡兩個數的和／差
    （千分位寫法已在 `_numbers_of` 抹平）。不跨檔加減：跨檔會讓巧合多到什麼都找得到。"""
    for nums in per:
        if n in nums or (n - 1) in nums:        # n-1：「接在 447 後面的 448」——自己編的下一號
            return True
        for a in nums:
            if (n - a) in nums or (n + a) in nums:
                return True
    return False


def check_source(artifacts: list[tuple[str, str]], hay_texts: list[str]) -> list[dict]:
    per, decs = known_numbers(hay_texts)
    hay = "\n".join(hay_texts)
    issues = []
    for ai, (name, text) in enumerate(artifacts):
        where = _fname(name, artifacts, ai)
        for ln, line in enumerate(text.splitlines(), 1):
            missing: list[str] = []
            for kind, tok in tokens(line):
                if kind == "num":
                    ok = number_found(int(tok), per)
                elif kind == "dec":
                    ok = tok in decs
                else:
                    ok = tok in hay
                if not ok and tok not in missing:
                    missing.append(tok)
            if missing:
                shown = "".join(f"『{x}』" for x in missing[:3])
                issues.append({"file": "artifact", "line": ln,
                               "msg": f"{where}第{ln}行的{shown}，這一跑讀過的東西裡找不到"})
    return issues


# ---------------------------------------------------------------------------
# 窗 3：兩個出處對得上嗎（只對 _facts.json 有登記的實體）
# ---------------------------------------------------------------------------

#: 同一行（或相鄰行）出現這些字＝成品自己指出了兩處對不上。
DISCREPANCY_WORDS = ("對不上", "不一致", "不同", "矛盾", "衝突", "抄錯", "寫錯", "誤抄", "出入", "不符", "不對",
                     "錯誤", "更正", "修正", "原本")
_CHUNK = re.compile(r"[一-鿿]+")
_PREFIX = re.compile(r"^(?:手上收據|片上|收據)?印紋")


def _marks_after(rest: str) -> list[tuple[str, bool]]:
    """`rest` 裡依序出現的印紋名（單字的印紋要整個詞就是它；「片上印紋X」標成 piece）。"""
    out = []
    for m in _CHUNK.finditer(rest):
        chunk = m.group(0)
        piece = chunk.startswith("片上印紋")
        c = _PREFIX.sub("", chunk)
        for mk in MARKS:
            if (len(mk) == 1 and c == mk) or (len(mk) > 1 and c.startswith(mk)):
                out.append((mk, piece))
                break
    return out


def extract_values(line: str, ent: dict) -> list[str]:
    """一行文字裡，實體 `ent` 的主詞後面說的值（`[]`＝這一行沒對這個實體說值）。"""
    subj = re.compile(ent["subject"])
    vals: list[str] = []
    for m in subj.finditer(line):
        if ent["kind"] == "mark":
            rest = line[m.end(): m.end() + 40]
            d = re.search(r"\d", rest)
            if d:
                rest = rest[: d.start()]
            found = _marks_after(rest)
            if not found:
                continue
            pieces = [x for x, p in found if p]
            vals.append((pieces or [found[0][0]])[0])
        else:
            # 數字要緊接在主詞後面（「第四列：6 張」「第四列共有 6 張」）；「第四列的第二個位置放了一張卡」不是在說張數。
            rest = line[m.end(): m.end() + 12]
            mm = re.match(r"[：:，,\s共有只剩僅是為約]{0,5}([0-9]+|[一二兩三四五六七八九十])\s*"
                          + re.escape(ent["unit"]), rest)
            if mm:
                v = mm.group(1)
                vals.append(_ZH_DIGIT.get(v, v))
    return vals


def mentions_authority(line: str, ent: dict) -> bool:
    """這一行有沒有也寫出權威的值（成品自己把兩個說法並排＝指出了）。"""
    av = ent["authority_value"]
    if ent["kind"] == "mark":
        return av in line
    for m in re.finditer(r"([0-9]+|[一二兩三四五六七八九十])\s*" + re.escape(ent["unit"]), line):
        if _ZH_DIGIT.get(m.group(1), m.group(1)) == av:
            return True
    return False


def load_facts(path: pathlib.Path | None = None) -> dict:
    p = pathlib.Path(path) if path else FACTS_PATH
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"entities": {}, "claims": {}}


def check_agree(artifacts: list[tuple[str, str]], read: set[str], facts: dict) -> list[dict]:
    ents = facts.get("entities") or {}
    claims = facts.get("claims") or {}
    issues = []
    # 權威檔的路徑在 `_facts.json` 裡不帶「地上/」；讀過的集合帶。
    read_rel = {r[len(GROUND_PREFIX):] if r.startswith(GROUND_PREFIX) else r for r in read}
    for ai, (name, text) in enumerate(artifacts):
        where = _fname(name, artifacts, ai)
        lines = text.splitlines()
        for ln, line in enumerate(lines, 1):
            for key, ent in ents.items():
                auth = ent.get("authority_file")
                if auth not in read_rel:
                    continue
                vals = extract_values(line, ent)
                if not vals or ent["authority_value"] in vals or mentions_authority(line, ent):
                    continue
                # 成品自己指出了兩處對不上：同一行有「對不上」之類的字，或相鄰行也提到同一個實體而且有這些字。
                subj = re.compile(ent["subject"])
                pointed = any(w in line for w in DISCREPANCY_WORDS)
                for j in (ln - 2, ln):                      # 前一行、後一行（0 起算的索引）
                    if 0 <= j < len(lines) and subj.search(lines[j]) \
                            and any(w in lines[j] for w in DISCREPANCY_WORDS):
                        pointed = True
                if pointed:
                    continue
                by = [f for f in sorted(read_rel)
                      if f != auth and (claims.get(f) or {}).get(key) in vals]
                a_path = GROUND_PREFIX + auth
                if by:
                    msg = (f"{where}第{ln}行的『{ent['label']}』，這一跑讀過的『{a_path}』與"
                           f"『{GROUND_PREFIX + by[0]}』說法不同，成品沒有指出")
                else:
                    msg = f"{where}第{ln}行的『{ent['label']}』，與這一跑讀過的『{a_path}』說法不同"
                issues.append({"file": "artifact", "line": ln, "msg": msg})
    return issues


# ---------------------------------------------------------------------------
# 窗 4：收據只有閘門給
# ---------------------------------------------------------------------------

#: 句子裡要同時有「閘門那一側的詞」與「結果的詞」才算宣稱閘門結果。
GATE_WORDS = ("閘門", "窗格", "小窗", "窗", "收據", "綠光", "出紙口")
RESULT_WORDS = ("通過", "過關", "過了", "亮齊", "全亮", "都亮", "亮起綠", "綠光", "拿到收據", "領到收據",
                "拿到了收據", "收據垂下", "收到收據", "取得收據", "簽好", "蓋了章", "放行", "驗收通過")
#: 鍵值形的自編收據（「閘門：過」「窗：6 格全亮」）。
_KV_CLAIM = re.compile(r"閘門\s*[：:]\s*(?:過|通過|已過)|窗\s*[：:]?\s*\d*\s*格?\s*(?:全亮|亮齊)")
#: 描述計畫、未來、假設、否定的不算陳述。
EXCLUDE_WORDS = ("會", "要", "準備", "等一下", "等會", "待會", "將", "打算", "預計", "之後", "接著",
                 "希望", "想要", "如果", "若", "假如", "等到", "才能", "就能", "應該", "可能", "需要",
                 "必須", "好讓", "以便", "沒", "未", "尚未", "還沒", "不", "無法", "沒有", "是否", "能不能", "能否",
                 "預留", "留空", "保留", "待填", "填入", "等待", "空白")
#: 句子指向自己的成品／交件（有這些字，轉述地上檔的豁免就不適用）。
SELF_WORDS = ("我", "自己", "這份", "這張", "這件", "這次", "本人", "交件", "交出", "成品", "我的")
_SENT_SPLIT = re.compile(r"[。！？!?；;]")


def _norm(s: str) -> str:
    return re.sub(r"[\s　，,。、；;：:「」『』（）()\"'“”*#>\-]+", "", s)


def check_receipt(artifacts: list[tuple[str, str]], hay_texts: list[str]) -> list[dict]:
    hay_n = _norm("\n".join(hay_texts))
    issues = []
    for ai, (name, text) in enumerate(artifacts):
        where = _fname(name, artifacts, ai)
        for ln, line in enumerate(text.splitlines(), 1):
            hit = False
            for sent in _SENT_SPLIT.split(line):
                if not sent.strip():
                    continue
                spans = [m.span() for m in _KV_CLAIM.finditer(sent)]
                if any(g in sent for g in GATE_WORDS):
                    for rw in RESULT_WORDS:
                        i = sent.find(rw)
                        if i >= 0:
                            spans.append((i, i + len(rw)))
                            break
                if not spans:
                    continue
                if any(w in sent for w in EXCLUDE_WORDS):
                    continue
                a, b = spans[0]
                ctx = _norm(sent[max(0, a - 3): b + 3])
                span = _norm(sent[a:b])
                self_ref = any(w in sent for w in SELF_WORDS)
                if not self_ref and len(ctx) >= 4 and ctx in hay_n:
                    continue                # 逐字引自它讀過的地上檔：不是它自己宣稱的
                if not self_ref and ((len(span) >= 3 and span in hay_n)
                                     or (len(_norm(sent)) >= 4 and _norm(sent) in hay_n)):
                    continue                # 轉述／照抄地上檔裡別人的收據（句子沒有指向自己的成品）
                if not self_ref and (any(mk in sent for mk in MARKS if len(mk) > 1)
                                     or re.search(r"(?<!\d)4[1-4]\d(?!\d)", sent)):
                    continue                # 在說地上某一片（印紋名／片號）的收據，不是自己這件成品
                hit = True
                break
            if hit:
                issues.append({"file": "artifact", "line": ln,
                               "msg": f"{where}第{ln}行寫了閘門通過或收據，這一跑的紀錄裡閘門沒有給過這個結果"})
    return issues


# ---------------------------------------------------------------------------
# 評估
# ---------------------------------------------------------------------------

def evaluate(ws: str | os.PathLike, ledger: Any) -> dict[str, dict]:
    """四格窗的結果：`{w1..w4: {"ok": bool, "issues": [{file,line,msg}]}}`。`ledger` 壞了 ⇒ 全部不亮。"""
    if not isinstance(ledger, dict) or ledger.get("v") != 1:
        bad = {"ok": False, "issues": [{"file": None, "line": None, "msg": NO_LEDGER_MSG}]}
        return {k: dict(bad) for k in ("w1", "w2", "w3", "w4")}
    ws = pathlib.Path(ws)
    plan = _read(ws / "PLAN.md")
    arts = read_artifacts(ws)
    read = set(ledger.get("read") or [])
    gtext = ledger.get("ground_text") or {}
    hay = [gtext[p] for p in sorted(read) if p in gtext]
    if ledger.get("letter"):
        hay.append(ledger["letter"])
    if ledger.get("world"):
        hay.append(ledger["world"])
    res = {
        "w1": check_read(plan, read, list(ledger.get("ground_files") or [])),
        "w2": check_source(arts, hay),
        "w3": check_agree(arts, read, ledger.get("facts") or {}),
        "w4": check_receipt(arts, hay),
    }
    return {k: {"ok": not v, "issues": v} for k, v in res.items()}


def message_of(win: dict, limit: int = 4) -> str:
    iss = win.get("issues") or []
    msg = "；".join(i["msg"] for i in iss[:limit])
    if len(iss) > limit:
        msg += f"；另有 {len(iss) - limit} 處"
    return msg


def assert_window(res: dict, key: str) -> None:
    """test_grounding.py 的 check_* 呼叫這個：沒過就丟 AssertionError（訊息＝位置與缺的根據）。"""
    w = res[key]
    if not w["ok"]:
        raise AssertionError(message_of(w))


# ---------------------------------------------------------------------------
# 每一跑的驗收套件（tests_visible/）與紀錄（_ledger.py）
# ---------------------------------------------------------------------------

TEST_SRC = '''# 由 ops/exhibit/twin/grounding_gate.py 生成。只查「有沒有根據」，不查好不好。
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _gg

_CACHE = {}


def _res():
    if "r" not in _CACHE:
        try:
            import _ledger
            ledger = _ledger.LEDGER
        except Exception:
            ledger = None
        _CACHE["r"] = _gg.evaluate(sys.argv[1], ledger)
    return _CACHE["r"]


def check_w1_read():
    _gg.assert_window(_res(), "w1")


def check_w2_source():
    _gg.assert_window(_res(), "w2")


def check_w3_agree():
    _gg.assert_window(_res(), "w3")


def check_w4_receipt():
    _gg.assert_window(_res(), "w4")
'''


def write_suite(run_dir: str | os.PathLike) -> pathlib.Path:
    """在 `run_dir/tests_visible/` 寫好測試檔與這一支的複本（不寫 `_ledger.py`）。回套件目錄。"""
    d = pathlib.Path(run_dir) / TESTS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    (d / TEST_NAME).write_text(TEST_SRC, encoding="utf-8")
    shutil.copyfile(pathlib.Path(__file__).resolve(), d / GG_NAME)
    ledger = d / LEDGER_NAME
    if ledger.exists():
        ledger.unlink()
    return d


def read_step_rows(rd: pathlib.Path) -> list[dict]:
    p = pathlib.Path(rd) / STEP_LOG_NAME
    rows: list[dict] = []
    text = _read(p)
    if not text:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            break
        if isinstance(r, dict):
            rows.append(r)
    return rows


def read_set(rows: list[dict]) -> list[str]:
    out = set()
    for r in rows:
        if r.get("tool") == "ws_read" and r.get("ok") is True and isinstance(r.get("path"), str):
            parts = [x for x in r["path"].replace("\\", "/").split("/") if x not in ("", ".")]
            if ".." in parts or not parts:
                continue
            out.add("/".join(parts))
    return sorted(out)


def build_ledger(rd: str | os.PathLike, facts_path: pathlib.Path | None = None) -> dict:
    """這一跑的紀錄：步驟紀錄（讀過什麼）＋run-dir 裡備好的凍結材料（地上檔、世界、信）。"""
    rd = pathlib.Path(rd)
    read = read_set(read_step_rows(rd))
    gdir = rd / "stage2_in" / "地上"
    ground_files, ground_text = [], {}
    if gdir.is_dir():
        for p in sorted(gdir.rglob("*")):
            if p.is_file():
                rel = GROUND_PREFIX + p.relative_to(gdir).as_posix()
                ground_files.append(rel)
                if rel in read:
                    ground_text[rel] = _read(p) or ""
    world = ""
    if "WORLD.md" in read:
        world = _read(rd / "stage2_in" / "WORLD.md") or ""
    letter = _read(rd / LETTER_COPY_NAME) or ""
    return {"v": 1, "read": read, "ground_files": ground_files, "ground_text": ground_text,
            "world": world, "letter": letter, "facts": load_facts(facts_path)}


def write_ledger(suite_dir: pathlib.Path, ledger: dict) -> None:
    src = "LEDGER = __import__('json').loads(%r)\n" % json.dumps(ledger, ensure_ascii=False)
    (pathlib.Path(suite_dir) / LEDGER_NAME).write_text(src, encoding="utf-8")


def _learn_run(events_path: str, task_id: str) -> tuple[str | None, int]:
    """事件檔裡這一跑（最後一個 `run_started`）的 run_id，以及它到目前為止的 `attempt_started` 數
    ＝這一次嘗試的真實編號（launcher 在每次 spawn 之前才發，所以現在這一次已經算進去）。"""
    text = _read(pathlib.Path(events_path))
    rid, n = None, 0
    for line in (text or "").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        if e.get("type") == "run_started" and e.get("task_id") == task_id and e.get("arm") == "RUN-ON":
            rid, n = e.get("run_id"), 0
        elif rid and e.get("run_id") == rid and e.get("type") == "attempt_started":
            n += 1
    return rid, n


def timeout_checks() -> list[dict]:
    """被切掉的嘗試的逐格結果：四格都是未判。電視看 `timed_out` 演 B7，不演成四個錯。"""
    return [{"id": CASE_ID[c], "ok": None, "label": TIMEOUT_LABEL} for c in CASES]


def cut_attempts(rd: str | os.PathLike) -> set[int]:
    """這一跑被時限切掉的嘗試編號（1 起算）：launcher 的牆鐘逾時（run_RUN-ON.json）＋整跑預算（gate_cut.json）。"""
    rd = pathlib.Path(rd)
    out: set[int] = set()
    try:
        run = json.loads((rd / "run_RUN-ON.json").read_text(encoding="utf-8"))
        out |= {int(a["attempt"]) for a in run.get("attempts", []) if a.get("agent_timed_out")}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        out |= {int(x) for x in json.loads((rd / CUT_NAME).read_text(encoding="utf-8"))}
    except (OSError, ValueError, TypeError):
        pass
    return out


def attempt_limit(rd: str | os.PathLike, retry: bool) -> str:
    """這一次嘗試 pi 能跑幾秒：min(單次上限, 整跑剩下的預算)；重改時剩不到 `min_attempt_s` ⇒ "SKIP"。
    `gate_meta.json` 沒有預算欄位 ⇒ 不限（回 "0"）。"""
    try:
        meta = json.loads((pathlib.Path(rd) / GATE_META_NAME).read_text(encoding="utf-8"))
        left = float(meta["deadline_ts"]) - time.time()
        cap, floor = float(meta["attempt_cap_s"]), float(meta["min_attempt_s"])
    except (OSError, ValueError, KeyError, TypeError):
        return "0"
    if retry and left < floor:
        return "SKIP"
    return str(max(1, int(min(cap, left))))


def run_limited(secs: float, cmd: list[str]) -> int:
    """跑 `cmd`（stdin 接 /dev/null、stdout／stderr 繼承），超過 `secs` 秒就殺整個行程群組、回 124。"""
    import signal
    import subprocess
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        return proc.wait(timeout=secs if secs > 0 else None)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()
        return 124


def prepare(ws: str | os.PathLike, rd: str | os.PathLike) -> int:
    """pi 結束之後、凍結之前呼叫（`twin_agent.sh`）：重寫 `_ledger.py`，並把這一次的四格結果
    預先寫成一筆旁註 `twin_gate`（先於 `gate_ran`）。出錯 ⇒ 刪掉 `_ledger.py`（不用舊紀錄）。"""
    ws, rd = pathlib.Path(ws), pathlib.Path(rd)
    suite = rd / TESTS_DIRNAME
    try:
        suite.mkdir(parents=True, exist_ok=True)
        ledger = build_ledger(rd)
        write_ledger(suite, ledger)
        res = evaluate(ws, ledger)
    except Exception as exc:                             # noqa: BLE001
        try:
            (suite / LEDGER_NAME).unlink()
        except OSError:
            pass
        print(f"grounding_gate.prepare 失敗：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    result = {"files": [{"cases": [
        {"case": c, "ok": res[WINDOW_KEY[c]]["ok"], "message": message_of(res[WINDOW_KEY[c]])}
        for c in CASES]}]}
    checks = checks_from_result(result)
    passed = all(c["ok"] for c in checks)
    cut = os.environ.get("GATE_CUT") == "1"
    pre = rd / PRECHECK_NAME
    attempt = len((_read(pre) or "").splitlines()) + 1
    try:
        with pre.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"attempt": attempt, "passed": passed, "checks": checks},
                                ensure_ascii=False) + "\n")
    except OSError:
        pass
    # 旁註（電視要在 gate_ran 之前拿到逐格結果）。任何一步缺了就不寫，不影響這一跑。
    try:
        meta = json.loads((rd / GATE_META_NAME).read_text(encoding="utf-8"))
        rid, real_attempt = (_learn_run(meta["events_path"], meta["task_id"])
                             if meta.get("events_path") else (None, 0))
        if cut and real_attempt >= 1:
            try:
                prev = json.loads((rd / CUT_NAME).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                prev = []
            (rd / CUT_NAME).write_text(json.dumps(sorted({*prev, real_attempt})), encoding="utf-8")
        if rid and real_attempt >= 1 and meta.get("sidecar_path"):
            # 旁註的 attempt 是 launcher 的真實嘗試編號（被牆鐘砍掉的那一次沒有 prepare，不會佔號）。
            row = {"schema": "twin.sidecar/1", "type": "twin_gate", "ts_ms": int(time.time() * 1000),
                   "cell_id": meta["cell_id"], "run_id": rid, "attempt": real_attempt,
                   "passed": passed, "checks": checks}
            if cut:
                row["cut"] = True            # 被時限切掉：Folder 改帶四個 ok:null
            sp = pathlib.Path(meta["sidecar_path"])
            sp.parent.mkdir(parents=True, exist_ok=True)
            with sp.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:                                    # noqa: BLE001
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 3 and argv[0] == "prepare":
        return prepare(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "limit":
        print(attempt_limit(argv[1], argv[2] == "1"))
        return 0
    if len(argv) >= 4 and argv[0] == "runlimited" and argv[2] == "--":
        return run_limited(float(argv[1]), argv[3:])
    print("用法：grounding_gate.py prepare|limit <工作區|run_dir> …｜runlimited <秒> -- <命令…>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
