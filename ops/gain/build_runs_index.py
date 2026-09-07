"""把 `runs/` 掃成機器可讀索引＋人讀說明（round457）。

## 這支在架構裡承重什麼

`runs/` 已經長到 315 個項目、1000 多個檔、113 MB。裡面混著三種完全不同性質的
東西，而**目錄名看不出是哪一種**：

  1. 真的跑過模型、進得了統計的 run（44 個有 `summary.json`）
  2. 冒煙／探針／被殺掉的半成品（有 `calls.jsonl` 沒 `summary.json`）
  3. 迴圈每一輪寫下的重算工作目錄 `_analysis_r*`（132 個）——**那是衍生物，
     不是證據**；它們會隨著分析工具改版而變，拿它當原始資料就是把結論
     餵回給自己

沒有索引的時候，任何人（包含 agent）要回答「支撐 X 的原始資料在哪、那個 run
跑完沒、用的是哪一版題庫」只能全盤掃描，而且**很容易把 (3) 當成 (1)**。
本檔產生的 `runs/INDEX.json` 就是為了讓這個分類不必靠記憶。

紀律沿用 `examples/build_archive_index.py`（E 系列檔案庫索引）那一套：

  - **只讀不寫**。除了 `runs/INDEX.json` 與 `runs/INDEX.md`，一個位元組都不動。
    這支是**編目**不是清理：不刪、不搬、不改任何資料檔。
  - **逐檔 sha256**。索引本身要能被驗；資料被動過就對不上。
  - **索引不准比資料樂觀**（`examples/verdicts.py` 的教訓）。所以
    `kind` 會誠實地把冒煙／中止／衍生分析標出來，`record_spec` 會誠實地
    寫「G 系列的 run 目錄**不是** RECORD_SPEC 包」，`headline` 挑不出
    專屬裁決時標 `—` 而不拿別人的裁決來充數。
  - **零網路、零模型呼叫**。全部從磁碟與 `git log` 導出。
  - **可重跑、無時間戳**。輸出裡沒有任何 wall-clock 欄位，所以同一份資料
    重跑必然逐位元組相同；`--check` 就是靠這個做迴歸。

## MBPP+ 的私有性

`.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz` 是**不轉散布**的官方包
（`.gitignore` 第 18 行 `.vacant-private/` 擋住整個目錄）。索引裡只記
**路徑字串、`vacant/codebench.py` 裡的 sha256 釘值、378 這個題數**，
不含任何一個位元組的題目內容，也不去讀它的內容。

## 用法

    python ops/gain/build_runs_index.py              # 產生兩份索引
    python ops/gain/build_runs_index.py --check      # 重算並比對，不寫檔
    python ops/gain/build_runs_index.py --out DIR    # 寫到別處（測試用）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"

# ── 分類規則（寫死在這裡，不從目錄名猜第二次）────────────────────────
#
# kind 的值域刻意只有六個，因為索引的用途是「這東西能不能當證據」，
# 不是把每個目錄講清楚。更細的性質放 subkind，不影響判讀。
KIND_REAL = "real_run"      # 真跑過模型、有 summary.json 與 rows.jsonl
KIND_SMOKE = "smoke"        # 冒煙／探針／量具檢查——不進統計
KIND_ABORTED = "aborted"    # 發射過但沒收官（被殺、掛掉、或只剩 calls/notes）
KIND_ANALYSIS = "analysis"  # 事後重算的工作目錄——衍生物，不是證據
KIND_REPLAY = "replay"      # 離線重放產物
KIND_OTHER = "other"        # B 層掃描、展件抓圖、唯讀快照……

# 名字裡出現這些字＝診斷用途，即使有 summary.json 也不算證據級 run。
_SMOKE_TOKENS = ("smoke", "probe", "_test")

# RECORD_SPEC §1 的必要項。G 系列 run **沒有**用這個 layout，
# 索引要把這件事講出來而不是靜靜跳過。
RECORD_SPEC_REQUIRED = ("manifest.json", "ledger_events.jsonl",
                        "chain_verify.txt", "anomalies.md", "SHA256SUMS")

# 裁決檔的檔名特徵。headline 只從這些檔的標題**逐字抄**，不自己造句。
# 除了 DECISION_*，收官結論也可能寫成 CONCLUSION_* / FINDINGS_*——round457 首版
# 只掃 DECISION_*，於是 `g_r444_conform_mbpp` 的收官（寫在 CONCLUSION_ 裡）整份被漏掉。
_VERDICT_FILENAME_RE = re.compile(
    r"(FABLE_AUDIT|INDEPENDENT_AUDIT|_AUDIT|WRAPUP|SETTLEMENT|VERDICT|KILL)", re.I)
_VERDICT_PREFIXES = ("CONCLUSION_", "FINDINGS_")
# PREREG／CRITERION 是**量測之前**寫的判準，不是裁決。混進來會讓索引把
# 「我們打算怎麼判」講成「判決是什麼」——正是索引最不該犯的錯。
_NOT_A_VERDICT_RE = re.compile(r"(PREREG|CRITERION)", re.I)
_ROUND_TOKEN_RE = re.compile(r"^g_(r\d+[a-z]?)", re.I)
_FILENAME_ROUND_RE = re.compile(r"^[A-Z]+_(\d{8})_R?(\d+)")
_RUNS_PATH_RE = re.compile(r"runs/([A-Za-z0-9_]+)")
# 「開頭」＝標題＋前言＋**第一個小節**（也就是第二個 `##` 之前的全部）。
#
# 為什麼是第二個而不是第一個：這個專題的裁決檔把「資料：runs/<run>」寫在兩個
# 位置之一——前言裡（R440T_E3_WRAPUP、R516），或第一個小節「獨立重算」的開頭
# （R440X 就是這樣，`runs/g_r445_conform_mbpp_ext` 在第 8 行、第一個 `##` 在第 6 行）。
# 界線劃在第一個 `##` 會漏掉後者；劃在第二個 `##` 兩種都收得到，而且仍然擋得住
# 「內文第 84 行順帶提一句」那種（R440T_E3_WRAPUP 的 §二 在第 24 行就開始了）。
_SECTION_RE = re.compile(r"^##\s", re.M)


def _verdict_class(fname: str) -> int:
    """裁決檔的份量。同樣點名這個 run 時，用它決定誰才是「這個 run 的裁決」。

    純比新舊會挑錯：`g_r441_gemma_only_mbpp_b`（E1）的三份文件裡，最新的
    R519 是在稽核 round518 的天花板宣稱（只是**用到**這個 run），真正收官它的
    是較早的 R516；`g_r445_conform_mbpp_ext` 的 R440X 獨立稽核也會輸給同日
    但輪次號較大的自我收官結論。所以先比份量再比新舊。
    """
    if re.search(r"INTERIM", fname, re.I):
        return 0                                    # 期中，不是收官
    if re.search(r"(SETTLEMENT|WRAPUP|FINAL)", fname, re.I):
        return 3                                    # 收官裁決
    if re.search(r"(FABLE_AUDIT|INDEPENDENT_AUDIT)", fname, re.I):
        return 2                                    # 獨立稽核（另一雙眼睛）
    return 1                                        # 其餘裁決／結論


def _opening_of(text: str) -> str:
    """取「這份文件在裁決誰」的宣告區：第二個 `##` 之前的全部。

    不足兩個小節的文件，整份就是宣告區（但設 8000 字上限，免得一份沒分節的
    長文把每個 run 都掃進來）。
    """
    hits = list(_SECTION_RE.finditer(text))
    return text[:hits[1].start()] if len(hits) >= 2 else text[:8000]


_DATE_IN_NAME_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")

_TEXT_SUFFIXES = {".jsonl", ".json", ".txt", ".md", ".py", ".log", ".ndjson",
                  ".html", ".csv", ".sh", ".out", ""}


# ── 檔案層 ──────────────────────────────────────────────────────────
def _hash_and_count(path: Path) -> tuple[str, int, int | None]:
    """回傳 (sha256, bytes, lines)。二進位檔不數行（lines=None）。"""
    h = hashlib.sha256()
    size = 0
    newlines = 0
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
            size += len(chunk)
            newlines += chunk.count(b"\n")
    lines: int | None = newlines
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        lines = None
    return h.hexdigest(), size, lines


def _scan_files(d: Path) -> list[dict[str, Any]]:
    out = []
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        sha, size, lines = _hash_and_count(p)
        out.append({"name": p.relative_to(d).as_posix(),
                    "bytes": size, "sha256": sha, "lines": lines})
    return out


def _first_json_line(p: Path) -> dict[str, Any] | None:
    try:
        with p.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    return json.loads(line)
    except (OSError, ValueError):
        return None
    return None


def _count_lines(p: Path) -> int:
    n = 0
    try:
        with p.open("rb") as fh:
            while chunk := fh.read(1 << 20):
                n += chunk.count(b"\n")
    except OSError:
        return 0
    return n


# ── 日期 ────────────────────────────────────────────────────────────
def _git_first_seen(repo: Path) -> dict[str, str]:
    """一次 git log 掃出每個 runs/ 子項目**最早被加進版控**的日期。

    為什麼不用 mtime：worktree 是 checkout 出來的，全部檔案的 mtime 都是
    checkout 當下——那個數字完全沒有資訊。git 的加入時間才是穩定的。
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--reverse", "--diff-filter=A",
             "--format=%x00%aI", "--name-only", "--", "runs/"],
            capture_output=True, text=True, timeout=180, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    first: dict[str, str] = {}
    date = ""
    for line in out.splitlines():
        if line.startswith("\x00"):
            date = line[1:].strip()
            continue
        line = line.strip()
        if not line.startswith("runs/") or not date:
            continue
        top = line.split("/", 2)[1] if line.count("/") >= 1 else ""
        if top and top not in first:
            first[top] = date[:10]
    return first


def _date_for(d: Path, summary: dict[str, Any] | None,
              git_first: dict[str, str]) -> tuple[str | None, str]:
    m = _DATE_IN_NAME_RE.search(d.name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "run_name"
    for fn in ("rows.jsonl", "calls.jsonl", "notes.jsonl"):
        rec = _first_json_line(d / fn)
        if rec and isinstance(rec.get("ts_ms"), (int, float)):
            ts = _dt.datetime.fromtimestamp(rec["ts_ms"] / 1000.0,
                                            tz=_dt.timezone.utc)
            return ts.date().isoformat(), f"{fn}:ts_ms"
    if d.name in git_first:
        return git_first[d.name], "git_first_commit"
    return None, "unknown"


# ── 題庫 ────────────────────────────────────────────────────────────
def _load_banks() -> dict[str, Any]:
    """讀三個 LCB 題庫的 task_id 與中繼資料。只讀 repo 內的檔案。"""
    banks: dict[str, Any] = {}
    for v in ("v1", "v2", "v3"):
        p = ROOT / f"ops/gain/data/lcb_bank_{v}.jsonl"
        if not p.exists():
            continue
        recs = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        banks[v] = {"path": p.relative_to(ROOT).as_posix(), "records": recs,
                    "ids": {r["task_id"] for r in recs}}
    return banks


def _codebench_pins() -> dict[str, Any]:
    """從 `vacant/codebench.py` 抄釘值——**不 import**，避免把 runtime 帶進來。

    這裡刻意用文字解析而非 import：索引要能在沒裝 cryptography 的環境跑，
    而且釘值本來就該是「原始碼裡寫死的那個字串」，不是某次執行的結果。
    """
    src = (ROOT / "vacant/codebench.py").read_text()

    def grab(name: str) -> str | None:
        m = re.search(rf'^{name}\s*=\s*"([^"]+)"', src, re.M)
        return m.group(1) if m else None

    def grab_int(name: str) -> int | None:
        m = re.search(rf"^{name}\s*=\s*(\d+)", src, re.M)
        return int(m.group(1)) if m else None

    def grab_families() -> list[str]:
        m = re.search(r"_FAMILY_BUILDERS:.*?\{(.*?)\}", src, re.S)
        return re.findall(r'"([a-z_]+)":', m.group(1)) if m else []

    return {
        "evalplus_sha256": grab("EVALPLUS_MBPP_PLUS_SHA256"),
        "evalplus_count": grab_int("EVALPLUS_MBPP_PLUS_COUNT"),
        "evalplus_path": grab("EVALPLUS_DEFAULT_PATH"),
        "lcb": {v: {"sha256": grab(f"LCB_BANK_{v.upper()}_SHA256"),
                    "count": grab_int(f"LCB_BANK_{v.upper()}_COUNT")}
                for v in ("v1", "v2", "v3")},
        "builtin_families": grab_families(),
    }


def _known_bad() -> dict[str, list[str]]:
    """從 `ops/gain/check_bank_precision.py` 抄 KNOWN_BAD（同樣不 import）。"""
    p = ROOT / "ops/gain/check_bank_precision.py"
    if not p.exists():
        return {}
    m = re.search(r"^KNOWN_BAD = \{(.*?)\}\n", p.read_text(), re.M | re.S)
    if not m:
        return {}
    out: dict[str, list[str]] = {}
    for key, body in re.findall(r'"(\w+)":\s*\{([^}]*)\}', m.group(1)):
        out[key] = sorted(re.findall(r'"([^"]+)"', body))
    return out


def _bank_for_run(d: Path, banks: dict[str, Any]) -> dict[str, Any]:
    """從 rows.jsonl 的 task_id 前綴推題庫；LCB 再用集合包含關係定版本。

    集合比對而非相信名字：`g_r449_eq5_lcb2` 這種名字只是人取的，
    真正的證據是「這個 run 碰過的 189 個 task_id 全部落在 v3 裡」。
    """
    rows = d / "rows.jsonl"
    if not rows.exists():
        return {"family": None, "version": None, "match": "no_rows",
                "n_task_ids": 0, "candidates": []}
    ids: set[str] = set()
    fams: set[str] = set()
    with rows.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line).get("task_id", "")
            except ValueError:
                continue
            if not t:
                continue
            ids.add(t)
            fams.add("mbppplus" if t.startswith("mbppplus_")
                     else "lcb" if t.startswith("lcb_") else "other")
    if not fams:
        return {"family": None, "version": None, "match": "no_task_ids",
                "n_task_ids": 0, "candidates": []}
    family = fams.pop() if len(fams) == 1 else "mixed"
    info: dict[str, Any] = {"family": family, "version": None,
                            "n_task_ids": len(ids), "candidates": []}
    if family != "lcb":
        # MBPP+ 只有一個版本（v0.2.0，378 題，sha256 釘死），沒有版本歧義。
        info["version"] = "MbppPlus-v0.2.0" if family == "mbppplus" else None
        info["match"] = "by_task_id_prefix"
        return info
    lcb_ids = {i for i in ids if i.startswith("lcb_")}
    cands = [v for v in ("v1", "v2", "v3")
             if v in banks and lcb_ids <= banks[v]["ids"]]
    info["candidates"] = cands
    if not cands:
        info["match"] = "no_bank_contains_these_ids"
    elif len(cands) == 1:
        info["version"] = cands[0]
        info["match"] = ("exact" if lcb_ids == banks[cands[0]]["ids"]
                         else "subset")
    else:
        # v1 ⊂ v2，所以小庫優先＝最強的可證陳述。題數不足以分辨時照實說。
        info["version"] = cands[0]
        info["match"] = ("exact" if lcb_ids == banks[cands[0]]["ids"]
                         else "ambiguous_subset")
    return info


# ── 裁決檔 ──────────────────────────────────────────────────────────
def _decision_texts() -> list[dict[str, Any]]:
    """掃 repo 根目錄的判準／裁決檔。

    四種前綴都要掃：`DECISION_` 之外，收官結論也可能寫成 `CONCLUSION_`／
    `FINDINGS_`，事前判準寫成 `CRITERION_`。只掃 `DECISION_` 會漏掉整份收官
    （round457 首版就是這樣把 `g_r444_conform_mbpp` 的收官結論漏掉的）。

    每份記三段文字：`title`（第一行）、`opening`（第一個 `##` 之前的前言，
    也就是「這份文件在裁決誰」的宣告）、`text`（全文，只用來做交叉引用）。
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pat in ("DECISION*.md", "CONCLUSION*.md", "CRITERION*.md",
                "FINDINGS*.md"):
        for p in sorted(ROOT.rglob(pat)):
            if ".git" in p.parts or "runs" in p.parts:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            try:
                text = p.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            title = next((ln.lstrip("#").strip()
                          for ln in text.splitlines() if ln.strip()), "")
            opening = _opening_of(text)
            out.append({"rel": rel, "title": title, "opening": opening,
                        "text": text,
                        "is_verdict": bool(
                            (_VERDICT_FILENAME_RE.search(p.name)
                             or p.name.startswith(_VERDICT_PREFIXES))
                            and not _NOT_A_VERDICT_RE.search(p.name)),
                        "runs_in_opening": set(
                            _RUNS_PATH_RE.findall(opening))})
    return sorted(out, key=lambda d: d["rel"])


def _verdict_sort_key(rel: str) -> tuple[str, int]:
    """裁決檔的新舊：先比檔名日期，再比輪次號。"""
    m = _FILENAME_ROUND_RE.search(Path(rel).name)
    return (m.group(1), int(m.group(2))) if m else ("", 0)


def _refs_and_headline(name: str, decisions: list[dict[str, Any]],
                       run_names: set[str]) -> dict[str, Any]:
    """挑出「這個 run 的裁決是哪一份」，並把挑法與落選理由記錄下來。

    **首版的教訓（round457 稽核抓到）**：原本只要求「裁決檔內文提到這個 run」，
    於是 `g_r444_conform_mbpp` 被配到 `..._R440T_E3_WRAPUP.md`——那份是 r443／E3
    的收官，第 84 行只寫了一句「若 CONFORM 實跑顯示…」的前瞻假設。**被順帶提到
    不等於被裁決。** 所以現在有一道硬門檻：

      門檻：run 必須被該檔的**標題或前言**（第一個 `##` 之前）點名——完整目錄名，
            或標題裡的輪次號（`R440X：r445 的獨立稽核` 就是這樣點名 r445 的；
            該檔的完整目錄名落在第一個 `##` 之後一行）。輪次號只在它唯一對應
            一個 run 時才算數（`r441`／`r461` 各對到多個目錄，一律要完整名）。
            這個專題的裁決檔一律在前言寫 `資料：runs/<run>`，那就是它的對象宣告。

    過了門檻之後還要證明「這份文件的對象是**這一個** run」，二選一即可：
      (a) 標題裡就有 run 名（`…殺掉 g_r442_ononly_20260901`）；或
      (b) 宣告區只點名了這一個 run 目錄（唯一對象）。
    兩條都不成立＝那份文件的對象是別人或是併庫後的集合體，**不硬配**：
    headline 標 `—`、`headline_source` 記 `no_settlement_decision`，
    該檔改列進 `related_settlements` 讓讀者自己去看。
    （`g_r444_conform_mbpp` 就落在這裡：唯一過門檻的是 r444+r445 併庫 371 題的
    收官結論，r444 只是其中一個 stratum，沒有專門收官它的檔。）

    合格者之間的排序（由強到弱，全部可複查）：
      標題含 run 名 → 檔名輪次號相符 → 份量（`_verdict_class`：收官 > 獨立稽核
      > 其餘 > 期中）→ 日期／輪次較新。
    headline 一律是該檔標題**逐字**複製，不改寫、不摘要。
    """
    refs = sorted(d["rel"] for d in decisions if name in d["text"])
    verdicts = sorted((d["rel"] for d in decisions
                       if d["is_verdict"] and name in d["text"]),
                      key=_verdict_sort_key)
    by_rel = {d["rel"]: d for d in decisions}

    m = _ROUND_TOKEN_RE.match(name)
    tok = m.group(1).upper() if m else None

    passed = [d for d in decisions if d["is_verdict"] and name in d["opening"]]
    eligible: list[tuple[Any, ...]] = []
    related: list[str] = []
    why: dict[str, str] = {}
    for d in passed:
        in_title = name in d["title"]
        tok_hit = bool(tok and re.search(rf"_{tok}[A-Z]?_", Path(d["rel"]).name))
        # 宣告區點名的目錄裡，真的是 run 的有哪些。`runs/_analysis_r446`
        # 這種是分析工作目錄不是 run（R446 稽核檔就同時點了它與 g_r446_eq5_mbpp），
        # 算進去會讓「唯一對象」誤判成「多重對象」。
        named = {r for r in d["runs_in_opening"] if r in run_names}
        sole = named == {name}
        if in_title or sole:
            eligible.append((in_title, tok_hit,
                             _verdict_class(Path(d["rel"]).name),
                             _verdict_sort_key(d["rel"]), d["rel"]))
            why[d["rel"]] = "named_in_title" if in_title else "sole_subject_of_opening"
        else:
            related.append(d["rel"])

    out: dict[str, Any] = {
        "decision_refs": refs,
        "verdict_decisions": verdicts,
        "related_settlements": sorted(related),
    }
    if not eligible:
        out.update({
            "headline": None,
            "headline_from": None,
            "headline_source": ("no_settlement_decision" if related else "none"),
            "headline_candidates": [],
            "headline_note": (
                "沒有專門收官這個 run 的裁決檔。過了「標題／前言點名」門檻的只有 "
                + "、".join(sorted(related))
                + "，但那份的對象是別的 run 或併庫後的集合體，**不硬配**。"
                if related else
                "沒有任何裁決檔在標題或前言點名這個 run 目錄。"),
        })
        return out
    eligible.sort()
    rel = eligible[-1][-1]
    src = why[rel]
    out.update({
        "headline": by_rel[rel]["title"],
        "headline_from": rel,
        "headline_source": src,
        "headline_candidates": sorted(r[-1] for r in eligible),
        "headline_note": (
            None if len(eligible) == 1 else
            "宣告區點名這個 run 的裁決檔不只一份（見 headline_candidates）；"
            "依「標題點名 → 檔名輪次號相符 → 份量（收官>獨立稽核>其餘>期中）"
            "→ 較新」挑出這一份。"),
    })
    return out

# ── run 分類 ────────────────────────────────────────────────────────
def _classify(d: Path, summary: dict[str, Any] | None,
              n_rows: int) -> tuple[str, str]:
    n = d.name
    if n.startswith("_analysis") or n.startswith("analysis_"):
        return KIND_ANALYSIS, "loop_round_recompute"
    if n == "_replay" or n.startswith("_replay"):
        return KIND_REPLAY, "offline_replay"
    if n.startswith("blayer_"):
        return KIND_OTHER, "blayer_scan"
    if re.match(r"^s\d+[a-z]?(_|$)", n):
        return KIND_OTHER, "exhibit_scan"
    if n.endswith("_snap"):
        return KIND_OTHER, "readonly_snapshot"
    is_g = n.startswith("g_") or (d / "calls.jsonl").exists() \
        or (d / "notes.jsonl").exists()
    if any(tok in n for tok in _SMOKE_TOKENS):
        return KIND_SMOKE, "probe_or_smoke"
    if summary is not None and n_rows > 0:
        return KIND_REAL, "gain_run"
    if summary is not None:
        # 有 summary 沒 rows＝收官寫了但一列都沒產出（例如 n=0 或全 void）。
        return KIND_ABORTED, "summary_without_rows"
    if is_g:
        return KIND_ABORTED, "no_summary"
    return KIND_OTHER, "unclassified"


def _record_spec_state(files: list[dict[str, Any]]) -> dict[str, Any]:
    names = {f["name"] for f in files}
    present = [x for x in RECORD_SPEC_REQUIRED if x in names]
    return {"required_present": present,
            "required_missing": [x for x in RECORD_SPEC_REQUIRED
                                 if x not in names],
            "is_record_spec_pack": len(present) == len(RECORD_SPEC_REQUIRED)}


def build_run_entry(d: Path, banks: dict[str, Any],
                    decisions: list[dict[str, Any]],
                    git_first: dict[str, str],
                    run_names: set[str]) -> dict[str, Any]:
    summary_p = d / "summary.json"
    summary: dict[str, Any] | None = None
    if summary_p.exists():
        try:
            summary = json.loads(summary_p.read_text())
        except ValueError:
            summary = None
    n_rows = _count_lines(d / "rows.jsonl") if (d / "rows.jsonl").exists() else 0
    kind, subkind = _classify(d, summary, n_rows)
    files = _scan_files(d)
    date, date_source = _date_for(d, summary, git_first)
    verdict = _refs_and_headline(d.name, decisions, run_names)

    # rows.jsonl 一列＝一臂上的一題，所以多臂 run 的 n_rows 是各臂相加。
    # 只報總數會讓人以為樣本數比實際大，所以逐臂與去重題數都要出。
    rows_by_arm: dict[str, int] = {}
    task_ids: set[str] = set()
    row_seed: str | None = None
    if (d / "rows.jsonl").exists():
        with (d / "rows.jsonl").open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                a = r.get("arm") or "?"
                rows_by_arm[a] = rows_by_arm.get(a, 0) + 1
                if r.get("task_id"):
                    task_ids.add(r["task_id"])
                if row_seed is None:
                    row_seed = r.get("seed")

    arms: list[str] = []
    infra_void: int | None = None
    terminal: bool | None = None
    complete: bool | None = None
    seed: str | None = None
    if summary:
        seed = summary.get("seed")
        arm_map = summary.get("arms") or {}
        arms = sorted(arm_map)
        if arm_map:
            infra_void = sum(int(a.get("infra_void") or 0)
                             for a in arm_map.values())
        terminal = summary.get("run_terminal")
        complete = summary.get("run_complete")
        # 舊版 runner 沒寫 run_terminal／run_complete。**沒寫就是不知道**，
        # 不要拿 all([]) is True 這種東西當成「跑完了」。
        if terminal is None and arm_map and all(
                "terminal" in a for a in arm_map.values()):
            terminal = all(bool(a.get("terminal")) for a in arm_map.values())
        if complete is None and arm_map and all(
                "complete" in a for a in arm_map.values()):
            complete = all(bool(a.get("complete")) for a in arm_map.values())
    if seed is None:
        seed = row_seed
    if not arms:
        arms = sorted(k for k in rows_by_arm if k != "?")

    runner_git = (summary or {}).get("runner_git") or {}
    return {
        "name": d.name,
        "kind": kind,
        "subkind": subkind,
        "date": date,
        "date_source": date_source,
        "seed": seed,
        "bank": _bank_for_run(d, banks),
        "arms": arms,
        "n_rows": n_rows,
        "n_rows_by_arm": dict(sorted(rows_by_arm.items())),
        "n_distinct_task_ids": len(task_ids),
        "terminal": terminal,
        "complete": complete,
        "infra_void": infra_void,
        "runner_git": {"sha": runner_git.get("sha"),
                       "dirty": runner_git.get("dirty"),
                       "branch": runner_git.get("branch")},
        "n_files": len(files),
        "bytes": sum(f["bytes"] for f in files),
        "files": files,
        "record_spec": _record_spec_state(files),
        **verdict,
    }


# ── banks / logs 區塊 ───────────────────────────────────────────────
def build_banks(banks: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    pins = _codebench_pins()
    kb = _known_bad()
    kb_ids = sorted(set(kb.get("lcb", [])) | set(kb.get("lcb2", [])))

    probe: dict[str, set[str]] = {}
    for fn, key in (("lcb_probe_solutions.json", "v1v2"),
                    ("lcb_v3_probe_solutions.json", "v3")):
        p = ROOT / "ops/gain/data" / fn
        probe[key] = set(json.loads(p.read_text())) if p.exists() else set()

    lcb_out: dict[str, Any] = {}
    for v, b in banks.items():
        p = ROOT / b["path"]
        sha, size, _ = _hash_and_count(p)
        recs = b["records"]
        dates = sorted(r["contest_date"] for r in recs if r.get("contest_date"))
        nums = sorted(int(i.split("_")[1]) for i in b["ids"]
                      if i.split("_")[-1].isdigit())
        diff: dict[str, int] = {}
        for r in recs:
            diff[r.get("difficulty", "?")] = diff.get(r.get("difficulty", "?"), 0) + 1
        pin = pins["lcb"].get(v, {})
        refs = probe["v3"] if v == "v3" else probe["v1v2"]
        used = sorted(r["name"] for r in runs
                      if r["bank"].get("family") == "lcb"
                      and r["bank"].get("version") == v)
        amb = sorted(r["name"] for r in runs
                     if r["bank"].get("family") == "lcb"
                     and v in (r["bank"].get("candidates") or [])
                     and r["bank"].get("version") != v)
        lcb_out[v] = {
            "path": b["path"],
            "sha256": sha,
            "sha256_pin_in_codebench": pin.get("sha256"),
            "sha256_matches_pin": sha == pin.get("sha256"),
            "bytes": size,
            "n_tasks": len(recs),
            "n_tasks_pin_in_codebench": pin.get("count"),
            "task_id_range": [f"lcb_{nums[0]}", f"lcb_{nums[-1]}"] if nums else None,
            "contest_date_window": [dates[0], dates[-1]] if dates else None,
            "n_with_contest_date": len(dates),
            "difficulty": dict(sorted(diff.items())),
            "platform": sorted({r.get("platform", "?") for r in recs}),
            "probe_solutions": {
                "file": ("ops/gain/data/lcb_v3_probe_solutions.json" if v == "v3"
                         else "ops/gain/data/lcb_probe_solutions.json"),
                "n_with_reference_solution": len(refs & b["ids"]),
                "coverage": round(len(refs & b["ids"]) / len(b["ids"]), 4)
                if b["ids"] else None,
            },
            "known_bad_task_ids": sorted(set(kb_ids) & b["ids"]),
            "known_bad_source": "ops/gain/check_bank_precision.py::KNOWN_BAD",
            "used_by_runs": used,
            "also_consistent_with_runs": amb,
        }

    ids = {v: b["ids"] for v, b in banks.items()}
    relations = {}
    if "v1" in ids and "v2" in ids:
        relations["v1_subset_of_v2"] = ids["v1"] <= ids["v2"]
    if "v2" in ids and "v3" in ids:
        relations["v2_v3_overlap"] = len(ids["v2"] & ids["v3"])
        relations["v2_union_v3"] = len(ids["v2"] | ids["v3"])

    return {
        "lcb": lcb_out,
        "lcb_relations": relations,
        "lcb_caveat_v3": (
            "v3 的 contest_date 全部不晚於 2024-08-10，**不能**宣稱晚於訓練截止；"
            "污染風險比 v1/v2 高（R460 C3 判定，vacant/codebench.py 有同一句）。"),
        "mbpp_plus": {
            "path": pins["evalplus_path"],
            "private": True,
            "redistributed": False,
            "gitignored_by": ".gitignore 的 `.vacant-private/`",
            "sha256_pin_in_codebench": pins["evalplus_sha256"],
            "n_tasks_pin_in_codebench": pins["evalplus_count"],
            "verified_against_real_file": "2026-09-07（round457）本機實測 shasum "
                                          "與釘值逐字相同",
            "note": ("官方 EvalPlus MBPP+ v0.2.0 包。索引**只記路徑與 codebench.py "
                     "裡的釘值**，不讀內容、不複製、不進版控。要驗就在本機比對 "
                     "sha256（`vacant/codebench.py::EvalPlusMBPPLoader` 是 fail-closed 的）。"
                     "刻意不記「這個 checkout 有沒有這個檔」——那是環境屬性不是資料屬性，"
                     "寫進去會讓索引在不同 checkout 之間漂掉。"),
        },
        "codebench_builtin_families": {
            "source": "vacant/codebench.py::_FAMILY_BUILDERS",
            "families": pins["builtin_families"],
            "note": ("程序生成的六坑型族，題目**不落盤**——由 seed:family:idx 決定性生成，"
                     "task_id = sha256('codebench:seed:family:idx')[:16]。"
                     "沒有題庫檔可以 hash，重現靠 seed。"),
        },
    }


def build_logs(runs: list[dict[str, Any]], top_files: list[dict[str, Any]]
               ) -> dict[str, Any]:
    launcher = sorted(f["name"] for f in top_files
                      if f["name"].endswith((".launch.log", ".backend.json",
                                             ".log", ".verdict.json")))
    return {
        "kinds": [
            {"kind": "run 資料檔",
             "what": "rows.jsonl / calls.jsonl / notes.jsonl / receipts_*.ndjson"
                     " / receipts_*.pub.json / summary.json",
             "mac_repo": "runs/<run>/",
             "vacant_dev": "~/vacant/Vacant/runs/<run>/",
             "tracked_in_git": True,
             "note": "Mac repo 的 runs/ 全部進版控（HEAD 1043 檔）。"
                     "calls.jsonl 是最大宗（單檔可到 11 MB），但也已在版控內。"},
            {"kind": "launcher log",
             "what": "*.launch.log / *.log / *.backend.json / *.verdict.json",
             "mac_repo": "runs/ 頂層（部分）",
             "vacant_dev": "~/vacant/Vacant/runs/ 頂層（全部）",
             "tracked_in_git": True,
             "note": "**同步不完整**：最新幾個 run 的 launcher log 只在 vacant-dev，"
                     "Mac repo 沒有——見 not_mirrored_to_mac。"},
            {"kind": "迴圈 iteration log",
             "what": "iter-NNNN.log（每輪一支）",
             "mac_repo": "（不存在）",
             "vacant_dev": "~/vacant/logs/iter-*.log",
             "tracked_in_git": False,
             "note": "6352 支，佔 ~/vacant/logs/ 364 MB 的絕大部分。"
                     "只在 vacant-dev，沒有備份，沒有保留政策。"},
            {"kind": "localagent 呼叫側錄",
             "what": "localagent-N.jsonl",
             "mac_repo": "（不存在）",
             "vacant_dev": "~/vacant/logs/localagent-*.jsonl",
             "tracked_in_git": False,
             "note": "104 支。同上：只在 vacant-dev。"},
            {"kind": "發射前探針",
             "what": "*_probe_N.json（conform / eq5_lcb2 / eq5_lcb3 / eq5_seed2 …）",
             "mac_repo": "（不存在）",
             "vacant_dev": "~/vacant/logs/*_probe_*.json",
             "tracked_in_git": False,
             "note": "每次發射前對後端打的三通探針。是「這個 run 發射時後端活著」"
                     "的唯一證據，但沒進版控。"},
            {"kind": "分析工作目錄",
             "what": "_analysis_r*/（CRITERION.md、重算 json/txt、SELFTEST）",
             "mac_repo": "runs/_analysis_r*/",
             "vacant_dev": "~/vacant/Vacant/runs/_analysis_r*/",
             "tracked_in_git": True,
             "note": "衍生物。不是原始資料，不可當證據引用。"},
        ],
        "vacant_dev": {
            "host": "user1@100.124.254.83（vacant-dev）",
            "runs_dir": "~/vacant/Vacant/runs/",
            "runs_entries": 329,
            "runs_bytes_human": "1.7G",
            "logs_dir": "~/vacant/logs/",
            "logs_files": 6514,
            "logs_bytes_human": "364M",
            "logs_time_window": "2026-08-15 → 2026-09-06",
            "listing_method": "ssh 唯讀 `ls`（2026-09-07 本輪實測）",
        },
        "mac_repo": {
            "runs_dir": "runs/",
            "entries": len(runs) + len(top_files),
            "dirs": len(runs),
            "top_level_files": len(top_files),
            "all_tracked_in_git": True,
        },
        "not_mirrored_to_mac": [
            "_analysis_r503/", "_preliminary/", "off_probe_n60_20260902b/",
            "s1_smoke/",
            "g_r448_eq5_mbpp_seed2.launch.log",
            "g_r448_eq5_mbpp_seed2.backend.json",
            "g_r449_eq5_lcb2.launch.log", "g_r449_eq5_lcb2.backend.json",
            "g_r449c_eq5_lcb3.launch.log", "g_r449c_eq5_lcb3.backend.json",
            "g_r461_lcb3_three_arm.launch.log",
            "s13_main.log", "s13_reload.log", "s13_selftest.log",
        ],
        "not_mirrored_note": (
            "vacant-dev 有 329 個項目、Mac repo 有 315 個，差的 14 個列在上面。"
            "**最近四個被稽核過的 run（r448／r449／r449c／r461）的 launcher log "
            "與 backend.json 只存在於 vacant-dev**——那是「發射時用的是哪個後端」"
            "的唯一紀錄，掉了就補不回來。"),
        "retention": (
            "沒有任何自動保留／輪替政策。Mac repo 這一側靠 git 保存（runs/ 全數"
            "進版控，113 MB）；vacant-dev 那一側（~/vacant/logs/ 364 MB、"
            "runs/ 1.7 G）**沒有備份**，機器沒了就沒了。要保留 iteration log 與"
            "發射探針，得另外做一次搬運——本輪只做編目，不動任何檔案。"),
        "launcher_files_in_mac_repo": launcher,
    }


# ── 組裝 ────────────────────────────────────────────────────────────
def build_index() -> dict[str, Any]:
    banks = _load_banks()
    decisions = _decision_texts()
    git_first = _git_first_seen(ROOT)

    dirs = sorted((p for p in RUNS.iterdir() if p.is_dir()),
                  key=lambda p: p.name)
    # 「這份裁決的前言只點名一個 run」要判得準，就得先知道哪些字串真的是 run
    # 目錄——裁決文裡的 `runs/_analysis_r446` 不是 run，不能讓它污染唯一性判定。
    # 「這份裁決的宣告區只點名一個 run」要判得準，就得先知道哪些目錄真的是 run。
    # `_analysis_*`／`_replay` 是衍生工作目錄，裁決檔常常順手引用它們，
    # 算進「對象」會讓唯一性判定失效。
    run_names = {p.name for p in dirs
                 if not p.name.startswith(("_analysis", "analysis_", "_replay"))}
    runs = [build_run_entry(d, banks, decisions, git_first, run_names)
            for d in dirs]

    top_files = []
    for p in sorted(RUNS.iterdir()):
        if not p.is_file() or p.name in ("INDEX.json", "INDEX.md"):
            continue
        sha, size, lines = _hash_and_count(p)
        top_files.append({"name": p.name, "bytes": size,
                          "sha256": sha, "lines": lines})

    by_kind: dict[str, int] = {}
    for r in runs:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1

    return {
        "schema_version": 1,
        "generated_by": "ops/gain/build_runs_index.py",
        "regenerate": "python ops/gain/build_runs_index.py",
        "verify": "python ops/gain/build_runs_index.py --check",
        "record_spec": "docs/RECORD_SPEC.md",
        "sibling_indexers": ["examples/build_archive_index.py（E 系列檔案庫）",
                             "examples/verdicts.py（裁決單一真相來源）"],
        "discipline": [
            "只讀不寫：除了 runs/INDEX.{json,md}，一個資料位元組都不動。",
            "逐檔 sha256，索引本身可被驗。",
            "索引不准比資料樂觀：冒煙／中止／衍生分析都照實標。",
            "輸出無時間戳，同資料重跑必然逐位元組相同。",
            "零網路、零模型呼叫。",
        ],
        "caveat_record_spec": (
            "G 系列 run 目錄（`g_*`）**不是** RECORD_SPEC §1 的證據包——它們沒有 "
            "manifest.json / ledger_events.jsonl / chain_verify.txt / anomalies.md / "
            "SHA256SUMS，用的是 gain_run.py 自己的 summary.json + rows/calls/notes 版面。"
            "符合 RECORD_SPEC 的只有 `blayer_*` 那幾個 B 層掃描。每個目錄的 "
            "`record_spec` 欄位逐項列出缺哪些。"),
        "counts": {
            "entries": len(runs) + len(top_files),
            "dirs": len(runs),
            "top_level_files": len(top_files),
            "dirs_with_summary_json": sum(
                1 for r in runs
                if any(f["name"] == "summary.json" for f in r["files"])),
            "by_kind": dict(sorted(by_kind.items())),
            "total_bytes": (sum(r["bytes"] for r in runs)
                            + sum(f["bytes"] for f in top_files)),
        },
        "runs": runs,
        "top_level_files": top_files,
        "banks": build_banks(banks, runs),
        "logs": build_logs(runs, top_files),
    }


# ── 人讀說明 ────────────────────────────────────────────────────────
_AUDITED = ("g_r441_gemma_only_mbpp_b", "g_r442_ononly_20260901",
            "g_r443_gemma_lcb", "g_r444_conform_mbpp",
            "g_r445_conform_mbpp_ext", "g_r446_eq5_mbpp",
            "g_r447_conform_lcb2", "g_r448_eq5_mbpp_seed2",
            "g_r449_eq5_lcb2", "g_r449c_eq5_lcb3",
            "g_r461_lcb3_three_arm", "g_r461_off_gate_lcb3")


def _bank_label(b: dict[str, Any]) -> str:
    fam = b.get("family")
    if fam == "lcb":
        v = b.get("version") or "?"
        tag = {"exact": "", "subset": "（子集）",
               "ambiguous_subset": "（子集，版本不可分辨）"}.get(b.get("match"), "")
        return f"lcb {v}{tag}"
    if fam == "mbppplus":
        return "MBPP+ v0.2.0"
    return fam or "—"


def _tf(v: bool | None) -> str:
    return "是" if v is True else "否" if v is False else "—"


def _short_headline(h: str | None) -> str:
    if not h:
        return "—"
    return h.replace("|", "／").replace("\n", " ")


def render_md(idx: dict[str, Any]) -> str:
    runs = {r["name"]: r for r in idx["runs"]}
    c = idx["counts"]
    L: list[str] = []
    A = L.append

    A("# runs/ 索引（人讀版）")
    A("")
    A("> 這一份由 `ops/gain/build_runs_index.py` 從 `runs/INDEX.json` **同一次執行**")
    A("> 產生。要改內容改產生器，不要手改本檔——手改會在下一次 `--check` 被抓到。")
    A("")
    A(f"`runs/` 共 **{c['entries']}** 個項目："
      f"{c['dirs']} 個目錄 ＋ {c['top_level_files']} 個頂層檔案，"
      f"合計 {c['total_bytes'] / 1e6:.0f} MB。"
      f"其中 **{c['dirs_with_summary_json']} 個目錄有 `summary.json`**。")
    A("")
    A("分類統計：")
    A("")
    A("| kind | 個數 | 意思 |")
    A("|---|---:|---|")
    meaning = {
        KIND_REAL: "真跑過模型、有 summary.json 與 rows.jsonl——這些才是證據",
        KIND_SMOKE: "冒煙／探針／量具檢查——**不進統計**",
        KIND_ABORTED: "發射過但沒收官（被殺、掛掉、或只有 calls/notes）",
        KIND_ANALYSIS: "迴圈每輪的重算工作目錄——**衍生物，不是證據**",
        KIND_REPLAY: "離線重放產物",
        KIND_OTHER: "B 層掃描、展件抓圖、唯讀快照等",
    }
    for k, n in c["by_kind"].items():
        A(f"| `{k}` | {n} | {meaning.get(k, '')} |")
    A("")
    A("### `INDEX.json` 的形狀（先看這個再寫 parser）")
    A("")
    A("| key | 型別 | 內容 |")
    A("|---|---|---|")
    A("| `counts` | dict | 總數與 `by_kind` |")
    A("| `runs` | **list** | 每個目錄一筆，依 `name` 排序 |")
    A("| `top_level_files` | **list** | `runs/` 頂層的散檔 |")
    A("| `banks` | **dict** | 見 §五；`banks.lcb` 是 dict（key＝`\"v1\"`/`\"v2\"`/`\"v3\"`），**不是 list** |")
    A("| `logs` | dict | `logs.kinds` 是 list，其餘是 dict／str |")
    A("| `caveat_record_spec`、`discipline` | str／list | 讀之前要知道的界線 |")
    A("")

    A("## 一、r441b…r449c、r461 這一段的主 run")
    A("")
    A("這一段是目前**唯一有獨立稽核裁決檔**的那一層。`裁決` 欄逐字抄自該檔標題，")
    A("沒有改寫、沒有摘要。")
    A("")
    A("挑哪一份有兩道關卡（規則全文在 `build_runs_index.py::_refs_and_headline`）：")
    A("")
    A("1. **門檻**：run 目錄名要出現在該檔的**宣告區**——標題、前言、或第一個小節")
    A("   （第二個 `##` 之前），因為裁決檔一律在那裡寫 `資料：runs/<run>`。")
    A("   **被內文順帶提到一句不算。**")
    A("2. **對象**：還要是「標題直接點名」或「宣告區只點名這一個 run」。點名了")
    A("   兩個以上的 run，那份文件的對象就是併庫後的集合體而不是這一個 run。")
    A("")
    A("兩關都過不了就標 `—` 而**不拿別人的裁決來充數**，那份改列進 `INDEX.json` 的")
    A("`related_settlements`。多份都合格時依「標題點名 → 檔名輪次號相符 →")
    A("份量（收官 > 獨立稽核 > 其餘 > 期中）→ 較新」排序，全部候選記在")
    A("`headline_candidates`，選中的理由記在 `headline_source`。")
    A("")
    A("`—` **不是「通過」，是「沒有專門收官它的裁決檔」**——")
    A("`g_r444_conform_mbpp` 就是這樣：唯一點名它的收官是 r444+r445 併庫 371 題那份，")
    A("它在裡面只是兩個 stratum 之一。")
    A("")
    A("| run | 日期 | 題庫 | 臂 | n（列／題） | 跑到底 | 零 void | void | 裁決（逐字抄自 DECISION 標題） |")
    A("|---|---|---|---|---:|---|---|---:|---|")
    for name in _AUDITED:
        r = runs.get(name)
        if not r:
            continue
        src = r["headline_from"]
        if src:
            link = f"[{Path(src).name}](../{src})"
        elif r["related_settlements"]:
            # 沒有專門收官它的檔，但有涵蓋到它的併庫收官——指過去，不冒充。
            link = "（無專屬裁決；相關收官：" + "、".join(
                f"[{Path(x).name}](../{x})" for x in r["related_settlements"]) + "）"
        else:
            link = "—"
        A(f"| `{r['name']}` | {r['date'] or '—'} | {_bank_label(r['bank'])} | "
          f"{'/'.join(r['arms']) or '—'} | "
          f"{r['n_rows']}／{r['n_distinct_task_ids']} | "
          f"{_tf(r['terminal'])} | {_tf(r['complete'])} | "
          f"{r['infra_void'] if r['infra_void'] is not None else '—'} | "
          f"{_short_headline(r['headline'])}<br>{link} |")
    A("")
    A("> `n（列／題）`＝`rows.jsonl` 的列數／去重後的 `task_id` 數。多臂 run 的列數是"
      "**各臂相加**，不是樣本數；配對檢定的 n 要看 `task_id`。逐臂列數在 "
      "`INDEX.json` 的 `n_rows_by_arm`。")
    A("> `跑到底`＝`summary.json` 的 `run_terminal`（每個 task 都被處理過，"
      "**含判成 `infra_void` 的**）；`零 void`＝`run_complete`（`n_void==0` 且"
      "全部處理完）。兩欄不同義：`g_r443_gemma_lcb` 跑到底了但有 4 筆 void，"
      "所以比例類指標的分母要照鐵律 3 扣掉那幾筆。舊版 runner 沒寫 `run_terminal` 的"
      "一律標 `—`——**那是「不知道」，不是「跑完了」**。")
    A("")

    A("## 二、其餘的 run：冒煙／探針／中止／未收官")
    A("")
    A("**這一張表裡的東西都不能當證據。** 列出來是為了讓「為什麼 runs/ 有這麼多目錄」")
    A("有個交代，也讓人一眼看出哪些是半成品。")
    A("")
    A("| run | kind | 日期 | 題庫 | n | 有 summary | 說明 |")
    A("|---|---|---|---|---:|---|---|")
    for r in idx["runs"]:
        if r["kind"] not in (KIND_SMOKE, KIND_ABORTED):
            continue
        has_sum = any(f["name"] == "summary.json" for f in r["files"])
        A(f"| `{r['name']}` | `{r['kind']}` | {r['date'] or '—'} | "
          f"{_bank_label(r['bank'])} | {r['n_rows']} | {_tf(has_sum)} | "
          f"{r['subkind']} |")
    A("")

    real_unaudited = [r for r in idx["runs"] if r["kind"] == KIND_REAL
                      and r["name"] not in _AUDITED]
    if real_unaudited:
        A("## 三、跑完但沒被獨立稽核的 run")
        A("")
        A("有 `summary.json` 也有 `rows.jsonl`，但**不在上面那一段裡**——都是 2026-08 到")
        A("09 初的探索期 run：為了決定下一步怎麼跑而跑的，不是為了得到一個可以拿去講的結論。")
        A("")
        n_unk = sum(1 for r in real_unaudited if r["terminal"] is None)
        n_inc = sum(1 for r in real_unaudited if r["complete"] is False)
        A(f"這 {len(real_unaudited)} 個裡，`跑到底` 有 {n_unk} 個是 `—`"
          "（那個時期的 runner 還沒寫 `run_terminal` 欄位，所以是**不知道**，"
          f"不是跑完了）；`零 void` 是 `否` 的有 {n_inc} 個。")
        A("")
        A("**沒被稽核不等於不成立，也不等於成立——就是沒複核過。** 引用其中任何一個數字，")
        A("都要把這一句一起講出去。")
        A("")
        A("| run | 日期 | 題庫 | 臂 | n（列／題） | 跑到底 | 零 void | void | 提到它的 DECISION | 其中屬裁決檔 |")
        A("|---|---|---|---|---:|---|---|---:|---:|---:|")
        for r in real_unaudited:
            A(f"| `{r['name']}` | {r['date'] or '—'} | {_bank_label(r['bank'])} | "
              f"{'/'.join(r['arms']) or '—'} | "
              f"{r['n_rows']}／{r['n_distinct_task_ids']} | "
              f"{_tf(r['terminal'])} | {_tf(r['complete'])} | "
              f"{r['infra_void'] if r['infra_void'] is not None else '—'} | "
              f"{len(r['decision_refs'])} | {len(r['verdict_decisions'])} |")
        A("")
        A("> `其中屬裁決檔`＝檔名帶 AUDIT／WRAPUP／SETTLEMENT／VERDICT／KILL 的那些"
          "（PREREG／CRITERION 是**量測之前**寫的判準，不算裁決，已排除）。"
          "數字大於 0 只代表「有裁決檔提到它」，不代表那份裁決是在裁決它——"
          "`INDEX.json` 的 `verdict_decisions` 列出是哪幾份，自己打開看。")
        A("")

    n_an = c["by_kind"].get(KIND_ANALYSIS, 0)
    A("## 四、`_analysis_*` 那 %d 個目錄是什麼" % n_an)
    A("")
    A("它們**不是 run，也不是證據**。監控迴圈（`ops/loop.sh` 驅動的每一輪 agent）")
    A("每跑一輪就開一個 `runs/_analysis_r<輪次>/`，把那一輪的重算結果寫進去：")
    A("`off5_vs_off.txt`／`within_run.txt`／`PRIMARY_on_vs_off.txt` 這類配對檢定輸出、")
    A("量測前先 commit 的判準檔 `CRITERION.md`、以及工具自身的 `SELFTEST.txt`。")
    A("算它們的工具在 `ops/gain/replay/`（`paired_ci.py`、`pooled_paired_ci.py`、")
    A("`void_bounds.py`、`token_budget.py` …）。")
    A("")
    A("為什麼要特別講清楚：這些檔的內容**會隨分析工具改版而變**，而且它們的輸入")
    A("就是 `runs/g_*/rows.jsonl`。把 `_analysis_*` 當原始資料引用，等於把自己的")
    A("結論再餵給自己一次。要複核就重跑 `ops/gain/replay/` 的工具、對 `rows.jsonl` 算，")
    A("不要抄 `_analysis_*` 裡的數字。")
    A("")
    A("（`analysis_round455_paired`／`analysis_round522_acurve`／`analysis_round523_audit`／")
    A("`analysis_round525_final_recompute` 是同一類東西，只是命名沒帶底線前綴。）")
    A("")

    A("## 五、題庫")
    A("")
    b = idx["banks"]
    A("> **`INDEX.json` 的 `banks` 是 dict 不是 list。** 下表每一列對應")
    A("> `banks.lcb[\"v1\"|\"v2\"|\"v3\"]`——`banks.lcb` 本身也是 dict，key 是版本字串，")
    A("> 用 `banks.lcb[0]` 會 `KeyError`。同層還有四個非題庫的 key：")
    A("> `banks.lcb_relations`（dict）、`banks.lcb_caveat_v3`（str）、")
    A("> `banks.mbpp_plus`（dict）、`banks.codebench_builtin_families`（dict）。")
    A("> 對照之下 `runs` 與 `top_level_files` 是 **list**，`logs.kinds` 也是 list。")
    A("")
    A("| 題庫 | 檔案 | 題數 | sha256 符合 codebench 釘值 | task_id 範圍 | contest_date 區間 | 難度 | 有參考解 | 已知壞題 | 用過它的 run |")
    A("|---|---|---:|---|---|---|---|---|---|---|")
    for v, e in b["lcb"].items():
        rng = "–".join(e["task_id_range"]) if e["task_id_range"] else "—"
        win = " → ".join(x[:10] for x in e["contest_date_window"]) \
            if e["contest_date_window"] else "—"
        diff = "／".join(f"{k} {n}" for k, n in e["difficulty"].items())
        ps = e["probe_solutions"]
        A(f"| **lcb {v}** | `{e['path']}` | {e['n_tasks']} | "
          f"{_tf(e['sha256_matches_pin'])} | {rng} | {win} | {diff} | "
          f"{ps['n_with_reference_solution']}/{e['n_tasks']}"
          f"（{ps['coverage'] * 100:.1f}%） | "
          f"{'、'.join(e['known_bad_task_ids']) or '無'} | "
          f"{'、'.join(f'`{x}`' for x in e['used_by_runs']) or '—'} |")
    mp = b["mbpp_plus"]
    A(f"| **MBPP+ v0.2.0** | `{mp['path']}`（**私有、不轉散布**） | "
      f"{mp['n_tasks_pin_in_codebench']} | 釘值 `{(mp['sha256_pin_in_codebench'] or '')[:16]}…` | "
      f"`mbppplus_*` | — | — | 官方 GT | — | 見下 |")
    A("")
    r = b["lcb_relations"]
    A(f"- **版本關係**：v1 ⊂ v2（`{r.get('v1_subset_of_v2')}`）；"
      f"v2 ∩ v3 = {r.get('v2_v3_overlap')} 題、聯集 {r.get('v2_union_v3')} 題"
      "——v3 是刻意造出來的**樣本外**複製集，不是 v2 的超集。")
    A(f"- **v3 的警語**：{b['lcb_caveat_v3']}")
    A(f"- **已知壞題**來源：`{b['lcb'].get('v1', {}).get('known_bad_source', '')}`"
      "（白名單不是消音器：冒出新的照樣 FAIL）。")
    A(f"- **MBPP+ 為什麼不在版控**：{mp['note']}"
      f"（`.gitignore:18` 的 `.vacant-private/` 擋住整個目錄。"
      f"釘值 {mp['verified_against_real_file']}。）"
      "**索引裡不含它的任何一個位元組。**")
    fam = b["codebench_builtin_families"]
    A(f"- **程序生成題族**（`{fam['source']}`）：{'、'.join(fam['families'])}。"
      f"{fam['note']}")
    A("")

    A("## 六、log 在哪、哪些進了版控")
    A("")
    lg = idx["logs"]
    A("| 種類 | 檔名 | Mac repo | vacant-dev | 進 git | 備註 |")
    A("|---|---|---|---|---|---|")
    for k in lg["kinds"]:
        A(f"| {k['kind']} | `{k['what']}` | {k['mac_repo']} | "
          f"{k['vacant_dev']} | {_tf(k['tracked_in_git'])} | {k['note']} |")
    A("")
    dev = lg["vacant_dev"]
    A(f"- **vacant-dev**（`{dev['host']}`）："
      f"`{dev['runs_dir']}` {dev['runs_entries']} 個項目／{dev['runs_bytes_human']}；"
      f"`{dev['logs_dir']}` {dev['logs_files']} 個檔／{dev['logs_bytes_human']}，"
      f"時間跨度 {dev['logs_time_window']}。（{dev['listing_method']}）")
    A(f"- **沒有同步回 Mac 的 {len(lg['not_mirrored_to_mac'])} 個項目**："
      + "、".join(f"`{x}`" for x in lg["not_mirrored_to_mac"]))
    A(f"- {lg['not_mirrored_note']}")
    A(f"- **保留政策**：{lg['retention']}")
    A("")

    A("## 七、與 RECORD_SPEC 的落差（不要跳過這一節）")
    A("")
    A(idx["caveat_record_spec"])
    A("")
    packs = [r["name"] for r in idx["runs"] if r["record_spec"]["is_record_spec_pack"]]
    A(f"目前符合 RECORD_SPEC §1 全部必要項的目錄：{'、'.join(f'`{x}`' for x in packs) or '無'}。")
    A("")
    return "\n".join(L) + "\n"


# ── CLI ─────────────────────────────────────────────────────────────
def _dump(idx: dict[str, Any]) -> str:
    return json.dumps(idx, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把 runs/ 掃成索引（只讀，無網路）")
    ap.add_argument("--check", action="store_true",
                    help="重算並與磁碟上的索引比對，不寫檔；不一致 exit 1")
    ap.add_argument("--out", default=None,
                    help="輸出目錄（預設 runs/）")
    args = ap.parse_args(argv)

    idx = build_index()
    js, md = _dump(idx), render_md(idx)
    out = Path(args.out) if args.out else RUNS
    jp, mp = out / "INDEX.json", out / "INDEX.md"

    if args.check:
        bad = False
        for p, new in ((jp, js), (mp, md)):
            old = p.read_text() if p.exists() else ""
            if old != new:
                bad = True
                print(f"DRIFT: {p}", file=sys.stderr)
                for line in list(difflib.unified_diff(
                        old.splitlines(), new.splitlines(),
                        fromfile=f"{p.name} (磁碟)", tofile=f"{p.name} (重算)",
                        lineterm=""))[:60]:
                    print(line, file=sys.stderr)
        if bad:
            print("FAIL：索引與資料不一致。重跑 build_runs_index.py。",
                  file=sys.stderr)
            return 1
        print(f"OK：索引與資料一致（{idx['counts']['dirs']} 個目錄、"
              f"{idx['counts']['dirs_with_summary_json']} 個有 summary.json）")
        return 0

    out.mkdir(parents=True, exist_ok=True)
    jp.write_text(js)
    mp.write_text(md)
    c = idx["counts"]
    print(f"寫入 {jp} 與 {mp}")
    print(f"  {c['entries']} 個項目＝{c['dirs']} 目錄＋{c['top_level_files']} 檔；"
          f"{c['dirs_with_summary_json']} 個有 summary.json")
    print(f"  分類：{c['by_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
