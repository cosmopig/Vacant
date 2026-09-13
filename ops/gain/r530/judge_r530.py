#!/usr/bin/env python3
"""R530 質化盲評管線——把「一格工作區」變成「四維 1–5 分＋一句理由」，並且落盤到可稽核。

這支在架構裡承重什麼
────────────────────
`DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md` §五-6 寫著
「repo 裡目前不存在，要新建」。它承重的是**收官報告裡「贏在哪一維」那一段**，
而且**只承重那一段**：§六-6 事前寫死「四狀態的四條旗標沒有一條讀 `rubric.*`」，
所以本檔輸出的 JSON 頂層永遠帶著 `"does_not_change_four_state": true`——
那不是註解，是給下游 analyzer 看的擋門（下游若讀了本檔的數字去改裁決，
它會在同一份檔案裡看到這一行）。

四件事決定了這支怎麼寫，每一件都對應一條規格：

1. **盲**（§五-6-1、§五-6-2）。去識別化是**確定性**的：目錄改名
   `sample_<code>`（`code` ＝ salt＋cell_id 的 sha256 前 8 碼，可重算），刪
   `.git/`／`TASK.md`／`examples/`，mtime 歸零，掃洩漏字串。同一題的三臂
   **各自獨立呼叫**、順序由評審自己的 seed 決定——不是把三臂並列在同一個
   prompt 裡請模型比較。理由：並列＝相對比較，錨定效應會把「三臂之間的差」
   放大成一個與內容無關的排序偏好，而我們要的是每一格的絕對分。
2. **洩漏字串命中 ⇒ 整包退出質化**（§五-6-1），不是遮掉。遮掉會改變被評的
   東西，然後那一格的分數就不再是「這份交付有多好」。豁免只有一條路：
   那個字本來就在**題目自己的凍結文字**裡（`ow_07_retrypolicy` 的題目正文
   就有 "retry"），而且豁免要**落盤**（沿用 §五-3 的 `needle_excuse` 紀律）。
   臂名（`A-SOLO`／`A-CONF`／`A-GATE`）與 `.vacant`／`r530` **永不豁免**。
3. **一致性**（Fable 2026-09-13 裁決）：逐維 Cohen's quadratic weighted kappa
   與 Spearman ρ，自己實作、只用標準庫；另外算 Krippendorff α（ordinal），
   因為預註冊 P-W12 指名的仲裁欄位是 `rubric.irr.alpha_<dim>`。
   ⚠ 三個係數在「兩位評審都給同一個分數」時**數學上沒有定義**（期望不一致為 0）。
   本檔在那種情況回 `None` 並附理由，**不回 0.0**——P-W12 事前就預測評審近乎
   常數函數（R438／R516／R440P §三），所以這條路是預期會走到的，不是例外。
4. **全 I/O 落盤、retry×4 退避、infra_void 分得開**（鐵律 3）。模型呼叫走
   `ops/gain/brain_cline.py` 的 `ClineBrain.chat()`：重試表 5／10／20／40、
   牆鐘護欄、逐次落盤。四次都失敗 ⇒ 那一格對那位評審記 `infra_void`，
   **不是 0 分**。回覆解析不出 JSON ⇒ `parse_void`，同樣不是 0 分。

誠實邊界（收官必須原樣帶著）
──────────────────────────
· **盲評不是「評審不知道臂別」，只是「評審沒有被明說」。**（§五-6 逐字）
  去識別化擋得掉字串，擋不掉風格：`A-GATE` 的產出天生更可能帶有「修過好幾輪」
  的痕跡（多餘的防呆、針對某個 case 的特判）。
· **「與目標的貼合度」這一維與隱藏驗收部分重疊**（§一-4），因此它必然與主指標
  相關，不可被引用成「質化獨立佐證了量化」（§八-8）。
· **評審是 12B 本地模型，而本 repo 自己量過模型評審票近乎常數函數**（§八-8-1）。
· **grader 的 `seed` 不讓模型取樣變確定**——它只決定**呈現順序**。LM Studio 端
  沒有被本 run 釘住的取樣種子（沿用 §三-5、§八-6 的同一句）。兩位評審的差異
  是「不同主機 × 不同呈現順序 × 未釘住的取樣」，不是「兩個獨立的評分者母體」。
· **同一顆模型評自己家族的產出**（worker 也是 `gemma-4-12b-it-qat`）。本檔量不掉
  這個偏誤，只能把它寫在這裡並在報告裡印出來。

與預註冊 §五-6 的四處出入（**逐條列出來，不要讓它們變成默認**）
──────────────────────────────────────────────────────────────
1. **評審模型**：預註冊寫 `qwen/qwen3.8-27b`（1004 兩顆 seed）；
   Fable 2026-09-13 裁決改成 `gemma-4-12b-it-qat`，J1 在 1003、J2 在 1004。
   兩台實測都只有這一顆是共通的。實際用了什麼逐次落盤在 `rubric.graders`，
   CLI 的 `--grader` 可以換回去，不必改碼。
2. **一致性係數**：預註冊只指名 Krippendorff α（P-W12 的仲裁欄位）；
   Fable 加了 quadratic weighted kappa 與 Spearman。**三個都算、都印**，
   α 照樣落在 `rubric.irr.alpha_<dim>`。
3. **去識別化目錄名**：預註冊寫 `submission_<sha256[:8]>`、Fable 寫
   `sample_<隨機碼>` ⇒ 取兩者的交集：`sample_<sha256(salt‖cell_id)[:8]>`
   （Fable 的前綴、預註冊的確定性）。
4. ⚠ **豁免機制是本檔新增的，需要 Fable 明文追認。** 預註冊只寫「洩漏字樣
   命中就整包退出」。照字面實作的話，`ow_07_retrypolicy` 的題目正文本身就有
   "retry"，於是那一題的三條臂**全部**會被丟掉——量不到不是通過，但把無辜的
   格全部丟掉也不是量到。本檔的規則是：字樣出現在**題目自己的凍結文字**
   （`task.md`＋`visible.json`＋`rubric.json`）裡時豁免，**且逐筆落盤**
   （`rubric.deident.excused`）；臂名／`.vacant`／`r530` 永不豁免；
   路徑含 `hidden`／`rubric` 永不豁免（結構性擋門，§五-3-1）。

用法
────
    # 開發／稽核：不打後端，只產 prompt（可以直接讀送出去的逐字內容）
    python3 ops/gain/r530/judge_r530.py --cells-jsonl cells.jsonl \\
        --bank ops/gain/data/openwork --out-dir /tmp/r530_rubric --dry-run

    # 正式：兩位評審（J1＝1003、J2＝1004 不同 seed）
    python3 ops/gain/r530/judge_r530.py --run-dir runs/g_r530_ow_s1_odd \\
        --bank ops/gain/data/openwork --out-dir runs/g_r530_ow_s1_odd/rubric

    python3 ops/gain/r530/judge_r530.py --selftest        # 手算對照
    python3 ops/gain/r530/judge_r530.py --mutation-check  # 每一種壞法都要被抓到
    python3 ops/gain/r530/judge_r530.py --make-fake-run /tmp/fakerun  # 假工作區
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import random
import re
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
from dataclasses import asdict, dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.brain_cline import ClineBrain, InfraVoid  # noqa: E402
from vacant.memory import assert_ks1_clean  # noqa: E402

SCHEMA = "r530.rubric.v1"

# ── 評分表：四維 × 1–5（§一-4）────────────────────────────────────────────
#
# **維度鍵在程式裡凍結，級距文字在題庫裡**（資料不是程式，R452 紀律）。
# 題庫的 `rubric.json` 是權威；下面這份英文只有兩個用途：`--make-fake-run`
# 寫給假題庫用，以及讓「本檔預期的四個鍵是哪四個」在原始碼裡看得見。
DIMS = ("readability", "structure", "error_handling", "goal_fit")
DIM_TITLES = {
    "readability": "Readability",
    "structure": "Structure",
    "error_handling": "Error handling",
    "goal_fit": "Fit to the stated goal",
}
SCALE = (1, 2, 3, 4, 5)

DEFAULT_RUBRIC = {
    "readability": {
        "1": "Names carry no meaning; there are no comments and the code cannot "
             "be followed without them; a single function runs past 80 lines.",
        "3": "Names are mostly meaningful and the structure can be followed, "
             "though several passages need a second reading.",
        "5": "Clear on a first reading; names match the wording of the interface "
             "contract; comments appear only where they explain why, not what.",
    },
    "structure": {
        "1": "Everything sits in one function or one file, tangled together.",
        "3": "There is some decomposition, but the boundaries are arbitrary and "
             "duplicated logic appears two or more times.",
        "5": "One responsibility per unit; no duplicated logic; adding one new "
             "rule does not require editing three places.",
    },
    "error_handling": {
        "1": "Exception messages do not say what went wrong, or a bare except "
             "swallows the failure.",
        "3": "Every exception the contract asks for is raised and the messages "
             "are serviceable.",
        "5": "Every exception the contract asks for is raised, the message names "
             "which part of the input was wrong, nothing is swallowed, and the "
             "normal path is not written as an exception.",
    },
    "goal_fit": {
        "1": "What the code does and what the goal statement describes do not "
             "line up.",
        "3": "The interface contract is met, but only part of the trouble "
             "described in the goal statement is handled.",
        "5": "Every trouble named in the goal statement has a visible "
             "counterpart in the code.",
    },
}

# ── 去識別化（§五-6-1）──────────────────────────────────────────────────
#
# 無條件刪除：harness 的鷹架與版本歷史。三條臂的樣板逐位元相同，所以刪掉它們
# 不改變「被評的是誰的工作」，但留著它們會把「這一格跑過幾輪」寫在 git log 裡。
DROP_DIRS = (".git", "examples", "__pycache__", ".pytest_cache", ".mypy_cache")
DROP_FILES = ("TASK.md",)
DROP_SUFFIXES = (".pyc", ".pyo", ".orig", ".rej")
DROP_PREFIXES = (".vacant",)
#: 只有在**與樣板逐位元相同**時才刪（改過就留著，並照樣過洩漏掃描）。
#: 理由：刪掉 worker 改過的檔案＝改變被評的東西；留著鷹架原文＝多一條洩漏面。
DROP_IF_UNCHANGED = ("run_examples.sh", ".gitignore", "README.md")

#: **路徑層的結構性擋門**：工作區裡出現這種路徑 ⇒ 整包退出，**不接受任何豁免**。
#: 理由：`hidden.json` 依設計**從來不會**被複製進工作區（§五-3 第 1 項），
#: 所以它一旦出現在那裡，不管題目正文寫了什麼字，都代表結構性保證破了。
#: 這一條與字樣層的豁免機制分開——否則一題的目標敘述裡出現 "hidden"
#: 就會讓那一題的 `hidden.json` 變成可豁免的。
FORBIDDEN_PATH_PARTS = ("hidden", "rubric")

#: **永不豁免**的字樣：命中就整包退出，題目正文有沒有這個字都一樣。
#: 這些字只可能來自 harness／臂別／收據，不可能是題目要求的詞彙。
NEVER_EXCUSABLE = (
    "a-solo", "a-conf", "a-gate", "a_solo", "a_conf", "a_gate",
    ".vacant", "vacant", "r530", "g-r530",
    "openwork_attempt", "openwork_verdict", "logbook",
)
#: §五-6-1 事前凍結的清單 ＋ Fable 2026-09-13 補的四個（seed／receipt／臂名／`.vacant`）。
#: 這一層**可以**被「題目自己的凍結文字」豁免，豁免逐筆落盤。
FROZEN_LEAK_TOKENS = (
    "acceptance", "gate", "attempt", "retry", "round 2", "the tests said",
    "seed", "receipt", "hidden", "rubric", "persona", "arm",
    "失敗原文", "隱藏", "驗收",
)

_WORDISH = re.compile(r"^[a-z0-9]+$")


def _token_pattern(token: str) -> re.Pattern[str]:
    """字樣 → 比對式。

    純字母數字的字樣用**詞首邊界**（`\\bgate` 命中 "gates"／"a-gate"，不命中
    "aggregate"）；含標點的字樣（`.vacant`、`a-gate`、`round 2`）用純子字串。
    為什麼不全用子字串：`gate` 在 §五-6 的凍結清單裡，而子字串比對會把
    "aggregate"／"investigate"／"delegate" 全部判成洩漏，於是每一格都被丟掉——
    量不到不是通過，但**全部丟掉**也不是量到。
    """
    if _WORDISH.match(token):
        return re.compile(r"\b" + re.escape(token), re.IGNORECASE)
    return re.compile(re.escape(token), re.IGNORECASE)


_PATTERNS = {t: _token_pattern(t) for t in set(NEVER_EXCUSABLE) | set(FROZEN_LEAK_TOKENS)}

# ── prompt（逐字凍結；KS-1 紀律）─────────────────────────────────────────
#
# 措辭紀律（鐵律 1／KS-1）：不出現「你有責任／會被懲罰／有人在看」類措辭。
# 本檔尾端對每一個常數跑 `assert_ks1_clean`，寫錯就 import 不進來。
#
# 這份 prompt 刻意**不提**：臂、嘗試次數、有沒有通過測試、隱藏驗收的存在。
# 評審看得到的只有三樣：題目正文（題庫的權威版本）、評分表、去識別化後的檔案。
JUDGE_SYSTEM = (
    "You read one submission of a small programming task and score it against a "
    "fixed scoring guide. You look only at the files in front of you. You answer "
    "with one JSON object and nothing else."
)

JUDGE_PROMPT_HEADER = """\
Score one submission of a small programming task.

You are given three things: the task the author was working from, a scoring
guide, and the files the author left behind. Read all three, then score the
submission on four dimensions.

Each dimension is an integer from 1 to 5. The scoring guide describes levels 1,
3 and 5; use 2 and 4 for submissions that sit between two described levels.
Score each dimension on its own -- a submission can be strong on one dimension
and weak on another.
"""

JUDGE_PROMPT_FOOTER = """\
## Output format

Reply with one JSON object inside a fenced block, and nothing outside it:

```json
{"readability": 3, "structure": 3, "error_handling": 3, "goal_fit": 3,
 "reason": "one sentence naming the single thing that most affected these scores"}
```

All four scores are integers from 1 to 5. `reason` is one sentence.
"""


def rubric_block(rubric: dict) -> str:
    """評分表 → prompt 區塊。級距文字逐字來自題庫的 `rubric.json`。"""
    out = ["## Scoring guide", ""]
    for dim in DIMS:
        levels = rubric[dim]
        out.append(f"### {DIM_TITLES[dim]} (`{dim}`)")
        for lvl in ("1", "3", "5"):
            out.append(f"- **{lvl}** -- {levels[lvl]}")
        out.append("")
    return "\n".join(out)


def submission_block(files: list[tuple[str, str]], sample_id: str,
                     omitted: list[tuple[str, int]]) -> str:
    """去識別化後的檔案 → prompt 區塊（先目錄樹、再逐檔全文）。"""
    out = [f"## Submission `{sample_id}/`", "", "```", f"{sample_id}/"]
    for path, _ in files:
        out.append(f"  {path}")
    for path, size in omitted:
        out.append(f"  {path}   (not shown, {size} bytes)")
    out.append("```")
    out.append("")
    for path, text in files:
        lang = "python" if path.endswith(".py") else ""
        out.append(f"### `{sample_id}/{path}`")
        out.append(f"```{lang}")
        out.append(text)
        out.append("```")
        out.append("")
    if not files:
        out.append("(The submission contains no readable files.)")
        out.append("")
    return "\n".join(out)


def build_prompt(task_md: str, rubric: dict, sample_id: str,
                 files: list[tuple[str, str]],
                 omitted: list[tuple[str, int]]) -> str:
    """組出送給評審的**逐字** user 訊息。"""
    return "\n".join([
        JUDGE_PROMPT_HEADER,
        "## The task the author was working from",
        "",
        task_md.strip(),
        "",
        rubric_block(rubric),
        submission_block(files, sample_id, omitted),
        JUDGE_PROMPT_FOOTER,
    ])


# ── 後端（§五-6-3；Fable 2026-09-13 裁決：J1＝1003、J2＝1004 不同 seed）──────
ENDPOINT_1003 = "http://100.119.113.56:1234/v1/chat/completions"
ENDPOINT_1004 = "http://100.86.226.21:1234/v1/chat/completions"
JUDGE_MODEL = "gemma-4-12b-it-qat"
#: `"none"` ＝ 對齊兩台（1003 是 thinking 後端、1004 不是；DECISION_20260912 §十一）。
#: 想讓 thinking 當第二視角時把 J2 改成 `effort=default`，實際送了什麼落盤在
#: `rubric.graders[].reasoning_effort`。
DEFAULT_REASONING_EFFORT = "none"
#: 評審的取樣溫度。與 worker 的 0.3 無關——評分要的是穩定不是多樣。
#: ⚠ 溫度 0 不等於確定性：LM Studio 端沒有被本 run 釘住的取樣種子。
JUDGE_TEMPERATURE = 0.0

DEFAULT_GRADERS = (
    {"id": "J1", "api": ENDPOINT_1003, "model": JUDGE_MODEL,
     "seed": "j1-1003", "effort": DEFAULT_REASONING_EFFORT},
    {"id": "J2", "api": ENDPOINT_1004, "model": JUDGE_MODEL,
     "seed": "j2-1004", "effort": DEFAULT_REASONING_EFFORT},
)


@dataclass
class Grader:
    gid: str
    api: str
    model: str
    seed: str
    effort: str | None = DEFAULT_REASONING_EFFORT
    kind: str = "backend"          # "backend" | "stub"
    temperature: float = JUDGE_TEMPERATURE
    timeout_s: int = 300
    retries: int = 4

    def to_json(self) -> dict:
        d = asdict(self)
        d["reasoning_effort"] = d.pop("effort")
        d["id"] = d.pop("gid")
        return d


def parse_grader(spec: str) -> Grader:
    """`id=J1;api=http://…;model=…;seed=…;effort=none;kind=backend`。"""
    kv = {}
    for part in re.split(r"[;,]", spec):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"grader 規格看不懂（要 key=value）：{part!r}")
        k, v = part.split("=", 1)
        kv[k.strip()] = v.strip()
    unknown = set(kv) - {"id", "api", "model", "seed", "effort", "kind",
                         "temperature", "timeout_s", "retries"}
    if unknown:
        raise ValueError(f"grader 規格有不認得的欄位：{sorted(unknown)}")
    if "id" not in kv:
        raise ValueError("grader 規格缺 id=")
    effort = kv.get("effort", DEFAULT_REASONING_EFFORT)
    return Grader(
        gid=kv["id"], api=kv.get("api", ENDPOINT_1003),
        model=kv.get("model", JUDGE_MODEL), seed=kv.get("seed", kv["id"]),
        effort=None if effort in ("", "none-field") else effort,
        kind=kv.get("kind", "backend"),
        temperature=float(kv.get("temperature", JUDGE_TEMPERATURE)),
        timeout_s=int(kv.get("timeout_s", 300)),
        retries=int(kv.get("retries", 4)),
    )


# ── 格（cell）──────────────────────────────────────────────────────────
@dataclass
class Cell:
    cell_id: str
    task_id: str
    arm: str
    seed: str
    ws_path: pathlib.Path            # tar.gz 或目錄
    attempt: int | None = None
    delivered: bool | None = None

    def to_json(self) -> dict:
        d = asdict(self)
        d["ws_path"] = str(self.ws_path)
        return d


@dataclass
class Deident:
    """一格去識別化的結果——**包含被丟掉的那些格**，丟掉本身就是要落盤的資料。"""
    cell: Cell
    sample_id: str
    files: list[tuple[str, str]] = field(default_factory=list)
    omitted: list[tuple[str, int]] = field(default_factory=list)
    dropped_files: list[str] = field(default_factory=list)
    leak_hits: list[dict] = field(default_factory=list)
    excused: list[dict] = field(default_factory=list)
    ok: bool = True
    reason: str = ""
    tree_sha256: str = ""

    def to_json(self) -> dict:
        return {
            "cell": self.cell.to_json(), "sample_id": self.sample_id,
            "ok": self.ok, "reason": self.reason,
            "files": [p for p, _ in self.files],
            "files_n": len(self.files),
            "chars": sum(len(t) for _, t in self.files),
            "omitted": [{"path": p, "bytes": n} for p, n in self.omitted],
            "dropped_files": self.dropped_files,
            "leak_hits": self.leak_hits, "excused": self.excused,
            "tree_sha256": self.tree_sha256,
        }


# ── 題庫 ───────────────────────────────────────────────────────────────
def load_bank(bank_dir: pathlib.Path) -> dict[str, dict]:
    """`<bank>/<task_id>/{task.md,rubric.json,visible.json,template/}` → dict。

    **fail-closed**：`task.md` 或四個維度的級距文字缺一個就丟例外。少一個維度
    而靜靜地用預設值＝評分表在不同題目之間偷偷不一樣，而那會直接改掉
    `rubric.<seed>.<dim>.<ARM>` 的意思。
    """
    bank: dict[str, dict] = {}
    shared_rubric = None
    shared = bank_dir / "rubric.json"
    if shared.exists():
        shared_rubric = _normalise_rubric(json.loads(shared.read_text("utf-8")),
                                          str(shared))
    for d in sorted(p for p in bank_dir.iterdir() if p.is_dir()):
        if d.name.startswith("_"):
            continue
        task_md = d / "task.md"
        if not task_md.exists():
            continue
        rjson = d / "rubric.json"
        if rjson.exists():
            rubric = _normalise_rubric(json.loads(rjson.read_text("utf-8")),
                                       str(rjson))
        elif shared_rubric is not None:
            rubric = shared_rubric
        else:
            raise SystemExit(f"[bank] {d.name} 沒有 rubric.json，"
                             f"{bank_dir}/rubric.json 也不存在——拒跑（fail-closed）")
        vocab_src = [task_md.read_text("utf-8")]
        for extra in ("visible.json",):
            p = d / extra
            if p.exists():
                vocab_src.append(p.read_text("utf-8"))
        vocab_src.append(json.dumps(rubric, ensure_ascii=False))
        bank[d.name] = {
            "task_md": task_md.read_text("utf-8"),
            "rubric": rubric,
            "rubric_sha256": hashlib.sha256(
                json.dumps(rubric, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
            "vocab": "\n".join(vocab_src),
            "template": d / "template" if (d / "template").is_dir() else None,
        }
    if not bank:
        raise SystemExit(f"[bank] {bank_dir} 裡沒有任何 <task>/task.md——拒跑")
    return bank


def _normalise_rubric(raw: dict, where: str) -> dict:
    """吃兩種形狀：`{"dims":[{"key":…,"levels":{…}}]}` 或 `{"<dim>":{"1":…}}`。"""
    if "dims" in raw and isinstance(raw["dims"], list):
        raw = {d["key"]: d.get("levels", {}) for d in raw["dims"]}
    out = {}
    for dim in DIMS:
        levels = raw.get(dim)
        if not isinstance(levels, dict):
            raise SystemExit(f"[bank] {where} 缺維度 {dim!r}——拒跑（fail-closed）")
        norm = {str(k): str(v) for k, v in levels.items()}
        missing = [lvl for lvl in ("1", "3", "5") if not norm.get(lvl)]
        if missing:
            raise SystemExit(f"[bank] {where} 的 {dim!r} 缺級距 {missing}——拒跑")
        out[dim] = {lvl: norm[lvl] for lvl in ("1", "3", "5")}
    return out


# ── 去識別化 ───────────────────────────────────────────────────────────
MAX_FILE_BYTES = 40_000
MAX_FILES = 200
MAX_PROMPT_CHARS = 120_000
MAX_TAR_BYTES = 64 * 1024 * 1024


def sample_id_for(salt: str, cell_id: str) -> str:
    """`sample_<8 碼>`。**確定性**（salt＋cell_id 的 sha256），所以重跑可重算，
    但從 sample_id 反推不出題目／臂／seed（除非拿得到 salt 與 cell 清單）。"""
    h = hashlib.sha256(f"{salt}\x00{cell_id}".encode()).hexdigest()
    return f"sample_{h[:8]}"


def _safe_members(tf: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """只收一般檔案，路徑不得絕對／不得含 `..`／不得是連結或裝置。"""
    out = []
    total = 0
    for m in tf.getmembers():
        if not m.isfile():
            continue
        name = m.name.replace("\\", "/")
        if name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts:
            continue
        total += m.size
        if total > MAX_TAR_BYTES:
            break
        out.append(m)
    return out


def read_workspace(ws_path: pathlib.Path) -> dict[str, bytes]:
    """工作區（tar.gz 或目錄）→ `{relpath: bytes}`，路徑已去掉最外層目錄。"""
    raw: dict[str, bytes] = {}
    if ws_path.is_dir():
        for p in sorted(ws_path.rglob("*")):
            if p.is_file() and not p.is_symlink():
                raw[p.relative_to(ws_path).as_posix()] = p.read_bytes()
        return raw
    with tarfile.open(ws_path, "r:*") as tf:
        members = _safe_members(tf)
        names = [m.name.replace("\\", "/").lstrip("./") for m in members]
        prefix = ""
        tops = {n.split("/", 1)[0] for n in names if "/" in n}
        if len(tops) == 1 and all("/" in n for n in names):
            prefix = tops.pop() + "/"
        for m, name in zip(members, names):
            f = tf.extractfile(m)
            if f is None:
                continue
            raw[name[len(prefix):]] = f.read()
    return raw


def _is_dropped(relpath: str) -> str | None:
    parts = relpath.split("/")
    for d in DROP_DIRS:
        if d in parts[:-1] or parts[0] == d:
            return f"drop_dir:{d}"
    base = parts[-1]
    if base in DROP_FILES:
        return f"drop_file:{base}"
    if any(base.endswith(s) for s in DROP_SUFFIXES):
        return "drop_suffix"
    if any(base.startswith(p) or relpath.startswith(p) for p in DROP_PREFIXES):
        return "drop_prefix"
    return None


def _template_bytes(template: pathlib.Path | None) -> dict[str, bytes]:
    if template is None:
        return {}
    return {p.relative_to(template).as_posix(): p.read_bytes()
            for p in sorted(template.rglob("*")) if p.is_file()}


def _leak_hits(text: str, vocab: str) -> tuple[list[dict], list[dict]]:
    """回 `(命中, 豁免)`。

    豁免只有一條路：那個字樣在**題目自己的凍結文字**（`vocab`）裡出現過，
    而且它不在 `NEVER_EXCUSABLE`。豁免**落盤**，不是靜靜地放過
    （沿用 §五-3 的 `needle_excuse` 紀律：豁免要看得見）。
    """
    hits: list[dict] = []
    excused: list[dict] = []
    for token, pat in _PATTERNS.items():
        found = pat.findall(text)
        if not found:
            continue
        rec = {"token": token, "n": len(found)}
        if token in NEVER_EXCUSABLE:
            hits.append(rec)
            continue
        if pat.search(vocab):
            rec["excuse"] = "token appears in the task's own frozen text"
            excused.append(rec)
        else:
            hits.append(rec)
    hits.sort(key=lambda r: r["token"])
    excused.sort(key=lambda r: r["token"])
    return hits, excused


def deidentify(cell: Cell, bank_entry: dict, salt: str, *,
               max_file_bytes: int = MAX_FILE_BYTES,
               max_files: int = MAX_FILES,
               max_prompt_chars: int = MAX_PROMPT_CHARS) -> Deident:
    """一格工作區 → 可以送出去的檔案清單，或者「整包退出」的理由。"""
    sid = sample_id_for(salt, cell.cell_id)
    out = Deident(cell=cell, sample_id=sid)
    try:
        raw = read_workspace(cell.ws_path)
    except Exception as e:                                   # noqa: BLE001
        out.ok = False
        out.reason = f"workspace_unreadable: {type(e).__name__}: {e}"
        return out

    tmpl = _template_bytes(bank_entry.get("template"))
    kept: dict[str, bytes] = {}
    for relpath in sorted(raw):
        why = _is_dropped(relpath)
        if why:
            out.dropped_files.append(f"{relpath} [{why}]")
            continue
        base = relpath.split("/")[-1]
        if base in DROP_IF_UNCHANGED and tmpl.get(relpath) == raw[relpath]:
            out.dropped_files.append(f"{relpath} [drop_scaffold_unchanged]")
            continue
        kept[relpath] = raw[relpath]

    if len(kept) > max_files:
        out.ok = False
        out.reason = f"too_many_files: {len(kept)} > {max_files}"
        return out

    bad_paths = [p for p in sorted(kept)
                 if any(x in p.lower() for x in FORBIDDEN_PATH_PARTS)]
    if bad_paths:
        # §五-3 第 1 項的結構性保證破了：隱藏驗收不該出現在工作區裡。
        # 這不是「評分被汙染」，是「這一格的實驗條件本身要被人看過」。
        out.ok = False
        out.reason = "forbidden_path: " + ",".join(bad_paths[:5])
        out.leak_hits.append({"token": "<path>", "n": len(bad_paths),
                              "paths": bad_paths[:20]})
        return out

    files: list[tuple[str, str]] = []
    omitted: list[tuple[str, int]] = []
    budget = max_prompt_chars
    for relpath in sorted(kept):
        blob = kept[relpath]
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            omitted.append((relpath, len(blob)))
            continue
        if len(blob) > max_file_bytes:
            head = text[: max_file_bytes // 2]
            tail = text[-(max_file_bytes // 2):]
            text = f"{head}\n...[{len(blob)} bytes, middle not shown]...\n{tail}"
        if len(text) + len(relpath) > budget:
            omitted.append((relpath, len(blob)))
            continue
        budget -= len(text) + len(relpath)
        files.append((relpath, text))

    scan_src = "\n".join([p for p, _ in files] + [t for _, t in files]
                         + [p for p, _ in omitted])
    hits, excused = _leak_hits(scan_src, bank_entry.get("vocab", ""))
    out.files, out.omitted = files, omitted
    out.leak_hits, out.excused = hits, excused
    out.tree_sha256 = hashlib.sha256(
        json.dumps([[p, hashlib.sha256(kept[p]).hexdigest()] for p in sorted(kept)],
                   ensure_ascii=False).encode()).hexdigest()
    if hits:
        out.ok = False
        out.reason = "leak_tokens: " + ",".join(f"{h['token']}x{h['n']}" for h in hits)
    elif not files:
        out.ok = False
        out.reason = "no_readable_files"
    return out


def materialise(deid: Deident, root: pathlib.Path) -> pathlib.Path:
    """把去識別化後的內容寫成 `<root>/sample_xxxx/`，mtime 一律歸零（§五-6-1）。

    只有 `--keep-deident-dir` 會用到。送進 prompt 的是 `deid.files`，不是這個目錄
    ——這個目錄的用途是給人（Fable）去翻「評審到底看到了什麼」。
    """
    base = root / deid.sample_id
    if base.exists():
        shutil.rmtree(base)
    for relpath, text in deid.files:
        p = base / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        os.utime(p, (0, 0))
    for p in sorted(base.rglob("*"), reverse=True):
        os.utime(p, (0, 0))
    os.utime(base, (0, 0))
    return base


# ── 呼叫與解析 ─────────────────────────────────────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_scores(text: str) -> tuple[dict[str, int], str] | None:
    """回覆 → `({dim: 1..5}, reason)`，解析不出來回 `None`（**不是 0 分**）。

    寬鬆在「JSON 藏在哪裡」，嚴格在「值長什麼樣」：四個鍵都要在、都要是
    1–5 的整數。少一個鍵就當作沒評到——把缺的鍵補成 3 分，會讓「評審沒回答」
    與「評審給了中間分」在事後分不開。
    """
    candidates = [m.group(1) for m in _FENCE.finditer(text or "")]
    depth, start = 0, None
    for i, ch in enumerate(text or ""):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start:i + 1])
    for blob in reversed(candidates):
        try:
            obj = json.loads(blob)
        except Exception:                                    # noqa: BLE001
            continue
        if not isinstance(obj, dict):
            continue
        scores = {}
        ok = True
        for dim in DIMS:
            v = obj.get(dim)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                ok = False
                break
            if float(v) != int(v) or int(v) not in SCALE:
                ok = False
                break
            scores[dim] = int(v)
        if ok:
            reason = str(obj.get("reason") or "").strip()
            return scores, reason
    return None


def stub_score(grader: Grader, prompt: str) -> tuple[dict[str, int], str]:
    """離線替身評審——**不是模型**，只是一組寫死的啟發式。

    存在的理由只有兩個：(a) 測試要在沒有後端的機器上跑完整條管線；
    (b) `--mutation-check` 要有一份確定性的分數矩陣可以驗統計。
    它的輸出在 JSONL 與 summary 裡都帶 `"stub": true`，
    **任何帶 stub 的資料都不准進收官報告**。
    """
    body = prompt.split("## Submission", 1)[-1]
    lines = [ln for ln in body.splitlines() if ln.strip()]
    n_def = body.count("def ")
    longest = max((len(b.splitlines()) for b in body.split("def ")[1:]), default=0)
    scores = {
        "readability": 5 if longest < 25 else (3 if longest < 60 else 1),
        "structure": 5 if n_def >= 4 else (3 if n_def >= 2 else 1),
        "error_handling": (1 if "except:" in body or "except Exception" in body
                           else (5 if "raise ValueError" in body else 2)),
        "goal_fit": 4 if len(lines) > 20 else 2,
    }
    # 兩位替身評審要有一點（確定性的）不一致，否則 kappa 永遠是 1.0，
    # 而「kappa 在完全一致時沒有定義」那條路就永遠測不到。
    jitter = int(hashlib.sha256(f"{grader.seed}{prompt}".encode()).hexdigest(), 16) % 3
    dim = DIMS[jitter % len(DIMS)]
    if jitter == 2:
        scores[dim] = max(1, min(5, scores[dim] + (1 if jitter % 2 else -1)))
    return scores, f"stub grader {grader.gid}: {n_def} defs, longest block {longest} lines"


def score_one(grader: Grader, brain: ClineBrain | None, prompt: str, *,
              parse_retries: int = 2) -> dict:
    """一格一位評審一次評分。回一筆可以直接落盤的 dict。

    三種收場，**互相分得開**（鐵律 3）：
      · `ok`         —— 解析出四個分數；
      · `parse_void` —— 後端回了，但 `parse_retries+1` 次都解析不出 JSON；
      · `infra_void` —— 後端重試用盡（`InfraVoid`）。**不是 0 分**。
    """
    if grader.kind == "stub":
        scores, reason = stub_score(grader, prompt)
        return {"status": "ok", "scores": scores, "reason": reason,
                "stub": True, "parse_attempt": 1, "response": json.dumps(
                    {**scores, "reason": reason}, ensure_ascii=False)}
    assert brain is not None
    last_text = ""
    for attempt in range(1, parse_retries + 2):
        try:
            text, info = brain.chat(
                [{"role": "user", "content": prompt}],
                role="r530_judge", turn=attempt,
                meta={"grader": grader.gid, "parse_attempt": attempt})
        except InfraVoid as e:
            return {"status": "infra_void", "scores": None, "reason": "",
                    "error": str(e), "parse_attempt": attempt, "response": ""}
        last_text = text
        parsed = parse_scores(text)
        if parsed is not None:
            scores, reason = parsed
            return {"status": "ok", "scores": scores, "reason": reason,
                    "parse_attempt": attempt, "response": text,
                    "latency_ms": info.get("latency_ms"),
                    "usage": info.get("usage"), "server_model": info.get("server_model"),
                    "finish_reason": info.get("finish_reason")}
    return {"status": "parse_void", "scores": None, "reason": "",
            "parse_attempt": parse_retries + 1, "response": last_text,
            "error": "四個分數解析不出來"}


def blind_order(cells: list[Deident], grader: Grader, run_id: str) -> list[Deident]:
    """每位評審自己的呈現順序（§五-6-2）。

    ⚠ 這是**呈現順序**的亂數，不是模型取樣的亂數。同一份 prompt 送兩次不保證
    同一個答案，而本 run 沒有釘住 LM Studio 的取樣種子（§三-5 同一句）。
    """
    order = list(cells)
    random.Random(f"{grader.seed}:{run_id}").shuffle(order)
    return order


# ── 統計：三個係數，全部自己實作（Fable 裁決）────────────────────────────
def quadratic_weighted_kappa(a: list[int], b: list[int],
                             categories: tuple[int, ...] = SCALE) -> dict:
    """Cohen's kappa，二次權重 `w=(i-j)^2/(k-1)^2`。

    ⚠ **類別集合是固定的 1–5，不是「觀測到的類別」**。用觀測類別會讓權重的分母
    隨資料浮動：兩位評審只給過 3 和 4 時 `(k-1)^2` 會變成 1，於是同樣的一分之差
    被當成滿分之差。固定 1–5 之後，不同維度／不同 run 的 kappa 才可以並排看。

    `kappa=None` ＝ **沒有定義**（期望不一致為 0，兩位評審都是常數）。
    P-W12 事前就預測評審近乎常數函數，所以這條路是預期會走到的。回 0.0 會被
    讀成「一致性等於零」，那是另一件事。
    """
    n = len(a)
    if n != len(b):
        raise ValueError("兩位評審的長度不一樣")
    if n == 0:
        return {"kappa": None, "n": 0, "reason": "no paired observations"}
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1.0
    rows = [sum(r) for r in obs]
    cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    denom = (k - 1) ** 2
    num_o = num_e = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / denom
            num_o += w * obs[i][j] / n
            num_e += w * rows[i] * cols[j] / (n * n)
    if num_e == 0:
        return {"kappa": None, "n": n, "observed_disagreement": num_o,
                "expected_disagreement": 0.0,
                "reason": "expected disagreement is zero (at least one grader is "
                          "constant and the other agrees with it exactly); "
                          "kappa is undefined, not zero"}
    return {"kappa": 1.0 - num_o / num_e, "n": n,
            "observed_disagreement": num_o, "expected_disagreement": num_e,
            "reason": ""}


def _ranks(xs: list[float]) -> list[float]:
    """平均秩（tie → 平均）。不處理 tie 的秩會讓「兩位都給 3」變成一個假的順序。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks


def spearman(a: list[float], b: list[float]) -> dict:
    """Spearman ρ ＝ 秩上的 Pearson（tie 走平均秩）。

    `rho=None` ＝ 沒有定義（某一邊完全沒有變異）。
    """
    n = len(a)
    if n != len(b):
        raise ValueError("兩位評審的長度不一樣")
    if n < 2:
        return {"rho": None, "n": n, "reason": "n < 2"}
    ra, rb = _ranks(list(map(float, a))), _ranks(list(map(float, b)))
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    if va == 0 or vb == 0:
        return {"rho": None, "n": n,
                "reason": "one grader gave the same score to every submission; "
                          "rank correlation is undefined, not zero"}
    return {"rho": cov / (va * vb), "n": n, "reason": ""}


def krippendorff_alpha_ordinal(pairs: list[tuple[int, int]],
                               categories: tuple[int, ...] = SCALE) -> dict:
    """Krippendorff α（ordinal metric），兩位評審版。預註冊 P-W12 指名的欄位。

    δ²(c,k) ＝ ( Σ_{g=c..k} n_g − (n_c+n_k)/2 )²，n_g ＝ 該值在**係數矩陣**上的邊際。
    ordinal metric 的重點是：類別之間的距離由資料的分佈決定，不是由標籤的數值決定。
    """
    if not pairs:
        return {"alpha": None, "n_units": 0, "reason": "no units"}
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    o = [[0.0] * k for _ in range(k)]
    for x, y in pairs:
        o[idx[x]][idx[y]] += 1.0
        o[idx[y]][idx[x]] += 1.0
    nc = [sum(row) for row in o]
    n = sum(nc)
    if n < 2:
        return {"alpha": None, "n_units": len(pairs), "reason": "n < 2"}

    def delta2(i: int, j: int) -> float:
        lo, hi = (i, j) if i <= j else (j, i)
        s = sum(nc[g] for g in range(lo, hi + 1)) - (nc[lo] + nc[hi]) / 2.0
        return s * s

    do = sum(o[i][j] * delta2(i, j) for i in range(k) for j in range(k)) / n
    de = sum(nc[i] * nc[j] * delta2(i, j)
             for i in range(k) for j in range(k)) / (n * (n - 1))
    if de == 0:
        return {"alpha": None, "n_units": len(pairs), "observed": do, "expected": 0.0,
                "reason": "expected disagreement is zero (every score is identical); "
                          "alpha is undefined, not zero"}
    return {"alpha": 1.0 - do / de, "n_units": len(pairs),
            "observed": do, "expected": de, "reason": ""}


def median_quartiles(xs: list[float]) -> dict:
    """中位數與四分位（`statistics.quantiles(n=4, method="inclusive")`＝線性內插）。

    ⚠ 平均數**也**一起印，因為預註冊 P-W11 指名的仲裁欄位是
    `rubric.<seed>.<dim>.<ARM>.mean`。四分位是 Fable 要的形狀，
    平均是預註冊釘死的欄位——兩個都落盤，收官引哪一個由預註冊決定。
    """
    if not xs:
        return {"n": 0, "median": None, "q1": None, "q3": None, "mean": None,
                "min": None, "max": None}
    if len(xs) == 1:
        v = float(xs[0])
        return {"n": 1, "median": v, "q1": v, "q3": v, "mean": v, "min": v, "max": v}
    q1, med, q3 = statistics.quantiles(xs, n=4, method="inclusive")
    return {"n": len(xs), "median": float(med), "q1": float(q1), "q3": float(q3),
            "mean": float(statistics.fmean(xs)),
            "min": float(min(xs)), "max": float(max(xs))}


# ── 彙整 ───────────────────────────────────────────────────────────────
def aggregate(records: list[dict], deidents: list[Deident], graders: list[Grader],
              *, run_id: str, salt: str, disagree_threshold: int = 2) -> dict:
    """所有評分紀錄 → 收官要引的那一份 JSON。

    **`does_not_change_four_state` 永遠寫死 `True`**（§六-6）：四狀態的四條旗標
    沒有一條讀 `rubric.*`。這一行在這裡不是註解，是給下游 analyzer 的擋門。
    """
    ok = [r for r in records if r["status"] == "ok"]
    by_cell: dict[str, dict[str, dict]] = {}
    for r in ok:
        by_cell.setdefault(r["cell"]["cell_id"], {})[r["grader_id"]] = r

    # (a) 逐評審：每 (seed, dim, arm) 的中位數／四分位／平均
    per_grader: dict[str, dict] = {}
    for g in graders:
        buckets: dict[tuple[str, str, str], list[float]] = {}
        for r in ok:
            if r["grader_id"] != g.gid:
                continue
            c = r["cell"]
            for dim in DIMS:
                buckets.setdefault((c["seed"], dim, c["arm"]), []).append(
                    float(r["scores"][dim]))
        tree: dict = {}
        for (seed, dim, arm), xs in sorted(buckets.items()):
            tree.setdefault(seed, {}).setdefault(dim, {})[arm] = median_quartiles(xs)
        per_grader[g.gid] = tree

    # (b) 兩位評審在同一格的平均（預註冊 `rubric.<seed>.<dim>.<ARM>` 走這一份）
    #     ⚠ 只有兩位都評到的格才進來——一位 void 一位 ok 就平均掉，等於讓
    #     「評審 A 的分數」冒充「兩位的共識」。
    pair_buckets: dict[tuple[str, str, str], list[float]] = {}
    per_seed_cells: dict[str, set[str]] = {}
    for cell_id, per in by_cell.items():
        if len(per) < 2:
            continue
        any_r = next(iter(per.values()))
        c = any_r["cell"]
        per_seed_cells.setdefault(c["seed"], set()).add(cell_id)
        for dim in DIMS:
            vals = [float(r["scores"][dim]) for r in per.values()]
            pair_buckets.setdefault((c["seed"], dim, c["arm"]), []).append(
                sum(vals) / len(vals))
    rubric_tree: dict = {}
    for (seed, dim, arm), xs in sorted(pair_buckets.items()):
        rubric_tree.setdefault(seed, {}).setdefault(dim, {})[arm] = median_quartiles(xs)

    # (c) 評審間一致性：逐維三個係數
    gids = [g.gid for g in graders]
    irr: dict = {}
    disagreements: list[dict] = []
    if len(gids) >= 2:
        g1, g2 = gids[0], gids[1]
        for dim in DIMS:
            a, b, cells = [], [], []
            for cell_id, per in sorted(by_cell.items()):
                if g1 in per and g2 in per:
                    a.append(per[g1]["scores"][dim])
                    b.append(per[g2]["scores"][dim])
                    cells.append(cell_id)
            kap = quadratic_weighted_kappa(a, b)
            spe = spearman(a, b)
            alp = krippendorff_alpha_ordinal(list(zip(a, b)))
            irr[dim] = {
                "pair": [g1, g2], "n_pairs": len(a),
                "kappa_quadratic": kap["kappa"], "kappa_note": kap.get("reason", ""),
                "spearman_rho": spe["rho"], "spearman_note": spe.get("reason", ""),
                "alpha_ordinal": alp["alpha"], "alpha_note": alp.get("reason", ""),
                "exact_agreement": (sum(1 for x, y in zip(a, b) if x == y) / len(a)
                                    if a else None),
                "mean_abs_diff": (sum(abs(x - y) for x, y in zip(a, b)) / len(a)
                                  if a else None),
            }
            for cell_id, x, y in zip(cells, a, b):
                if abs(x - y) >= disagree_threshold:
                    per = by_cell[cell_id]
                    disagreements.append({
                        "cell_id": cell_id, "sample_id": per[g1]["sample_id"],
                        "task_id": per[g1]["cell"]["task_id"],
                        "arm": per[g1]["cell"]["arm"], "seed": per[g1]["cell"]["seed"],
                        "dim": dim, g1: x, g2: y, "diff": abs(x - y),
                        f"reason_{g1}": per[g1]["reason"],
                        f"reason_{g2}": per[g2]["reason"],
                    })
    disagreements.sort(key=lambda d: (-d["diff"], d["cell_id"], d["dim"]))

    # (d) 長度綁架的可量化版本：字數與分數的 Spearman。
    #     「可讀性會不會被字數綁架」不是靠猜的，是靠這一欄看的。
    chars = {d.sample_id: sum(len(t) for _, t in d.files) for d in deidents}
    length_confound = {}
    for dim in DIMS:
        xs = [float(chars.get(r["sample_id"], 0)) for r in ok]
        ys = [float(r["scores"][dim]) for r in ok]
        length_confound[dim] = spearman(xs, ys) if len(xs) >= 2 else {
            "rho": None, "n": len(xs), "reason": "n < 2"}

    dropped = [d.to_json() for d in deidents if not d.ok]
    excused = [{"sample_id": d.sample_id, "task_id": d.cell.task_id,
                "excused": d.excused} for d in deidents if d.excused]
    used_stub = any(r.get("stub") for r in records)
    return {
        "schema": SCHEMA,
        # §六-6：四狀態的四條旗標沒有一條讀 rubric.*。這一行是擋門不是註解。
        "does_not_change_four_state": True,
        "generated_ts_ms": int(time.time() * 1000),
        "run_id": run_id,
        "blind_salt_sha256": hashlib.sha256(salt.encode()).hexdigest(),
        "contains_stub_grader": used_stub,
        "graders": [g.to_json() for g in graders],
        "runner_git": git_info(),
        "counts": {
            "cells_in": len(deidents),
            "cells_scored": len(by_cell),
            "cells_scored_by_all_graders": sum(
                1 for per in by_cell.values() if len(per) == len(gids)),
            "calls": len(records),
            "ok": len(ok),
            "infra_void_n": sum(1 for r in records if r["status"] == "infra_void"),
            "parse_void_n": sum(1 for r in records if r["status"] == "parse_void"),
        },
        # 預註冊指名的仲裁欄位就長這個樣子：`rubric.<seed>.<dim>.<ARM>.mean`、
        # `rubric.irr.alpha_<dim>`、`rubric.deident_dropped_n`、`rubric.graders`。
        "rubric": {
            **rubric_tree,
            "irr": {f"alpha_{dim}": irr.get(dim, {}).get("alpha_ordinal")
                    for dim in DIMS},
            "deident_dropped_n": len(dropped),
            "graders": [g.gid for g in graders],
        },
        "irr_detail": irr,
        "per_grader": per_grader,
        "disagreements": disagreements,
        "disagree_threshold": disagree_threshold,
        "length_confound": length_confound,
        "deident": {"dropped": dropped, "excused": excused},
        "honest_bounds": HONEST_BOUNDS,
    }


HONEST_BOUNDS = [
    "盲評不是「評審不知道臂別」，只是「評審沒有被明說」。去識別化擋得掉字串，"
    "擋不掉風格：A-GATE 的產出天生更可能帶有修過好幾輪的痕跡。（預註冊 §五-6）",
    "「與目標的貼合度」是四維裡唯一與隱藏驗收有部分重疊的一維，因此它必然與"
    "主指標相關，不可被引用成「質化獨立佐證了量化」。（§一-4、§八-8）",
    "評審是 12B 本地模型，而本 repo 自己量過模型評審票近乎常數函數"
    "（R438／R516／R440P §三）。低一致性是事前預測（P-W12），不是資料壞掉；"
    "高一致性也不等於這把尺準。（§八-8）",
    "評審與 worker 是同一顆模型（gemma-4-12b-it-qat）。同族自評的偏誤本管線"
    "量不掉，只能記在這裡。",
    "grader 的 seed 只決定呈現順序，不讓模型取樣變確定——LM Studio 端沒有被"
    "本 run 釘住的取樣種子。（§三-5、§八-6 同一句）",
    "質化不進任何一格裁決：四狀態的四條旗標沒有一條讀 rubric.*。（§六-6）",
]


def git_info() -> dict:
    root = pathlib.Path(__file__).resolve().parents[3]
    def _run(args):
        try:
            r = subprocess.run(args, cwd=root, capture_output=True, text=True,
                               timeout=15)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:                                    # noqa: BLE001
            return None
    return {"commit": _run(["git", "rev-parse", "HEAD"]),
            "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
            "dirty": bool(_run(["git", "status", "--porcelain"]))}


# ── 輸入：格從哪裡來 ────────────────────────────────────────────────────
_WS_NAME = re.compile(r"^(?P<task>.+)_(?P<arm>A-[A-Z]+)_(?P<attempt>\d+)\.tar\.gz$")


def load_cells(args) -> tuple[list[Cell], str]:
    """`--cells-jsonl` 是正典；`--run-dir` 是便利的自動探索。回 `(cells, run_id)`。"""
    cells: list[Cell] = []
    if args.cells_jsonl:
        p = pathlib.Path(args.cells_jsonl)
        base = p.parent
        for line in p.read_text("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            d = json.loads(line)
            ws = d.get("ws_tar") or d.get("ws_dir") or d.get("ws_path")
            if not ws:
                raise SystemExit(f"[cells] 這一列沒有 ws_tar／ws_dir：{line[:120]}")
            wsp = pathlib.Path(ws)
            if not wsp.is_absolute():
                wsp = base / wsp
            cells.append(Cell(
                cell_id=d.get("cell_id") or f'{d["task_id"]}|{d["arm"]}|{d["seed"]}',
                task_id=d["task_id"], arm=d["arm"], seed=d["seed"], ws_path=wsp,
                attempt=d.get("attempt"), delivered=d.get("delivered")))
        return cells, args.run_id or p.parent.name

    run_dir = pathlib.Path(args.run_dir)
    run_id = args.run_id or run_dir.name
    rows = run_dir / "rows.jsonl"
    seen: dict[str, Cell] = {}
    if rows.exists():
        for line in rows.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            ws = (d.get("ws_tar") or d.get("ws_path") or d.get("workspace_tar"))
            if not (ws and d.get("task_id") and d.get("arm")):
                continue
            wsp = pathlib.Path(ws)
            if not wsp.is_absolute():
                wsp = run_dir / wsp
            seed = d.get("seed") or run_id
            cid = d.get("cell_id") or f'{d["task_id"]}|{d["arm"]}|{seed}'
            att = int(d.get("attempt") or 0)
            prev = seen.get(cid)
            # 質化評的是**最終交付**（§二-1：宣告完成的那一刻就是最終交付），
            # 所以同一格有多個 attempt 時取 attempt 最大的那一份。
            if prev is None or (prev.attempt or 0) <= att:
                seen[cid] = Cell(cell_id=cid, task_id=d["task_id"], arm=d["arm"],
                                 seed=seed, ws_path=wsp, attempt=att,
                                 delivered=d.get("delivered"))
    if not seen:
        for p in sorted((run_dir / "ws").glob("*.tar.gz")):
            m = _WS_NAME.match(p.name)
            if not m:
                continue
            task, arm, att = m["task"], m["arm"], int(m["attempt"])
            seed = args.seed_label or run_id
            cid = f"{task}|{arm}|{seed}"
            prev = seen.get(cid)
            if prev is None or (prev.attempt or 0) <= att:
                seen[cid] = Cell(cell_id=cid, task_id=task, arm=arm, seed=seed,
                                 ws_path=p, attempt=att)
    if not seen:
        raise SystemExit(f"[cells] {run_dir} 裡找不到任何格"
                         f"（rows.jsonl 沒有 ws_tar 欄，ws/*.tar.gz 也沒有）")
    return sorted(seen.values(), key=lambda c: c.cell_id), run_id


# ── 主流程 ─────────────────────────────────────────────────────────────
def run_judging(cells: list[Cell], bank: dict, graders: list[Grader], *,
                run_id: str, salt: str, out_dir: pathlib.Path, dry_run: bool,
                parse_retries: int = 2, keep_deident: bool = False,
                backoff_s: float = 5.0,
                max_file_bytes: int = MAX_FILE_BYTES,
                max_prompt_chars: int = MAX_PROMPT_CHARS,
                disagree_threshold: int = 2) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    deidents: list[Deident] = []
    for c in cells:
        entry = bank.get(c.task_id)
        if entry is None:
            d = Deident(cell=c, sample_id=sample_id_for(salt, c.cell_id), ok=False,
                        reason=f"task_not_in_bank: {c.task_id}")
        else:
            d = deidentify(c, entry, salt, max_file_bytes=max_file_bytes,
                           max_prompt_chars=max_prompt_chars)
        deidents.append(d)

    with (out_dir / "deident.jsonl").open("w", encoding="utf-8") as f:
        for d in deidents:
            f.write(json.dumps(d.to_json(), ensure_ascii=False) + "\n")
    if keep_deident:
        root = out_dir / "deident"
        root.mkdir(parents=True, exist_ok=True)
        for d in deidents:
            if d.ok:
                materialise(d, root)

    usable = [d for d in deidents if d.ok]
    prompts = {}
    for d in usable:
        entry = bank[d.cell.task_id]
        prompts[d.sample_id] = build_prompt(
            entry["task_md"], entry["rubric"], d.sample_id, d.files, d.omitted)

    records: list[dict] = []
    prompts_f = (out_dir / "judge_prompts.jsonl").open("w", encoding="utf-8")
    calls_f = (out_dir / "judge_calls.jsonl").open("w", encoding="utf-8")
    try:
        for g in graders:
            brain = None
            if not dry_run and g.kind != "stub":
                brain = ClineBrain(
                    agent_id=f"r530-judge-{g.gid}", system=JUDGE_SYSTEM, key="",
                    log_path=out_dir / f"judge_backend_{g.gid}.jsonl",
                    model=g.model, temperature=g.temperature, retries=g.retries,
                    backoff_s=backoff_s, timeout_s=g.timeout_s,
                    reasoning_effort=g.effort)
                # `ClineBrain.__init__` 從環境變數 `VACANT_GAIN_API` 取端點，
                # 而本管線要**同時**打兩台（J1＝1003、J2＝1004）⇒ 逐位評審覆寫。
                # 覆寫的值逐次落盤在 backend 的 `api` 欄，稽核看得見。
                brain.api = g.api
            for order_index, d in enumerate(blind_order(usable, g, run_id)):
                prompt = prompts[d.sample_id]
                base = {
                    "ts_ms": int(time.time() * 1000),
                    "grader_id": g.gid, "grader_seed": g.seed, "api": g.api,
                    "model": g.model, "reasoning_effort": g.effort,
                    "temperature": g.temperature,
                    "sample_id": d.sample_id, "order_index": order_index,
                    "cell": d.cell.to_json(),
                    "submission_files_n": len(d.files),
                    "submission_chars": sum(len(t) for _, t in d.files),
                    "system": JUDGE_SYSTEM, "prompt": prompt,
                }
                prompts_f.write(json.dumps(base, ensure_ascii=False) + "\n")
                prompts_f.flush()
                if dry_run:
                    continue
                res = score_one(g, brain, prompt, parse_retries=parse_retries)
                rec = {**base, **res}
                records.append(rec)
                calls_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                calls_f.flush()
                os.fsync(calls_f.fileno())
    finally:
        prompts_f.close()
        calls_f.close()

    summary = aggregate(records, deidents, graders, run_id=run_id, salt=salt,
                        disagree_threshold=disagree_threshold)
    summary["dry_run"] = dry_run
    (out_dir / "rubric_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def print_report(summary: dict) -> None:
    p = print
    p("=" * 78)
    p("R530 質化盲評（§五-6）")
    p(f"  run_id={summary['run_id']}  dry_run={summary.get('dry_run')}")
    p(f"  does_not_change_four_state={summary['does_not_change_four_state']}"
      "   ← 質化不進任何一格裁決（§六-6）")
    if summary.get("contains_stub_grader"):
        p("  ⚠⚠ 這份結果含 **替身評審（stub）**，不是模型評分——不准進收官報告。")
    c = summary["counts"]
    p(f"  格：{c['cells_in']} 進來／{c['cells_scored']} 有分數／"
      f"{c['cells_scored_by_all_graders']} 兩位都評到")
    p(f"  呼叫：{c['calls']}（ok {c['ok']}／infra_void {c['infra_void_n']}／"
      f"parse_void {c['parse_void_n']}）")
    p(f"  去識別化丟掉：{summary['rubric']['deident_dropped_n']} 格")
    for d in summary["deident"]["dropped"]:
        p(f"    - {d['cell']['cell_id']}  {d['reason']}")
    for e in summary["deident"]["excused"]:
        if e["excused"]:
            toks = ",".join(f"{x['token']}x{x['n']}" for x in e["excused"])
            p(f"    豁免 {e['task_id']} {e['sample_id']}: {toks}")

    p("-" * 78)
    p("逐 seed × 臂 × 維（兩位評審在同一格的平均；**不跨 seed 平均**）")
    reserved = ("irr", "deident_dropped_n", "graders")
    for seed in sorted(k for k in summary["rubric"] if k not in reserved):
        tree = summary["rubric"][seed]
        if not isinstance(tree, dict):
            continue
        p(f"  seed={seed}")
        for dim in DIMS:
            arms = tree.get(dim, {})
            cells = "  ".join(
                f"{arm}: med={_f(v['median'])} q1={_f(v['q1'])} q3={_f(v['q3'])} "
                f"mean={_f(v['mean'])} n={v['n']}"
                for arm, v in sorted(arms.items()))
            p(f"    {dim:<16} {cells}")
    p("-" * 78)
    p("評審間一致性（逐維；None ＝ 沒有定義，不是 0）")
    for dim in DIMS:
        d = summary["irr_detail"].get(dim)
        if not d:
            continue
        p(f"  {dim:<16} n={d['n_pairs']:<4} kappa_w={_f(d['kappa_quadratic'])}  "
          f"spearman={_f(d['spearman_rho'])}  alpha_ord={_f(d['alpha_ordinal'])}  "
          f"exact={_f(d['exact_agreement'])}  |Δ|={_f(d['mean_abs_diff'])}")
        for note in (d["kappa_note"], d["spearman_note"], d["alpha_note"]):
            if note:
                p(f"      ↳ {note}")
    p("-" * 78)
    thr = summary["disagree_threshold"]
    p(f"兩位評審差 ≥{thr} 分的格（給人抽讀，不進統計）：{len(summary['disagreements'])} 筆")
    for d in summary["disagreements"][:40]:
        gids = summary["rubric"]["graders"]
        p(f"  {d['sample_id']}  {d['task_id']} {d['arm']} {d['seed']}  {d['dim']}: "
          f"{gids[0]}={d[gids[0]]} {gids[1]}={d[gids[1]]}")
        p(f"      {gids[0]}: {d['reason_' + gids[0]][:100]}")
        p(f"      {gids[1]}: {d['reason_' + gids[1]][:100]}")
    p("-" * 78)
    p("長度與分數的 Spearman（「可讀性會不會被字數綁架」的可量化版本）")
    for dim in DIMS:
        lc = summary["length_confound"].get(dim, {})
        p(f"  {dim:<16} rho={_f(lc.get('rho'))}  n={lc.get('n')}"
          + (f"  ({lc['reason']})" if lc.get("reason") else ""))
    p("-" * 78)
    p("誠實邊界（收官必須原樣帶著）")
    for line in summary["honest_bounds"]:
        p(f"  · {line}")
    p("=" * 78)


def _f(x) -> str:
    return "None" if x is None else f"{x:+.3f}" if isinstance(x, float) else str(x)


# ── 假工作區（開發與測試用；正控／負控就住在這裡）──────────────────────────
FAKE_TASK_MD = """\
# Goal

A client keeps a pile of records that people edit by hand, and every week
somebody pastes a broken one into the pipeline. They want the bad records named
-- with the line number and what is wrong with it -- instead of a stack trace,
and they want the good records to keep flowing.

# Contract

`normalise(rows: list[str]) -> list[dict]`

- Each row is `name,amount`. `amount` is an integer number of cents.
- On a row that does not have exactly two fields, raise `ValueError` whose
  message is `line <N>: expected 2 fields`, where `<N>` is 1-based.
- On a row whose amount is not an integer, raise `ValueError` whose message is
  `line <N>: amount is not an integer`.
- Leading and trailing spaces around each field are removed.
- The returned list keeps the input order.
"""

FAKE_GOOD = '''\
"""Turn hand-edited rows into records, naming the row that is wrong."""


def _split_row(row, lineno):
    fields = [f.strip() for f in row.split(",")]
    if len(fields) != 2:
        raise ValueError("line %d: expected 2 fields" % lineno)
    return fields


def _parse_amount(text, lineno):
    try:
        return int(text)
    except ValueError:
        raise ValueError("line %d: amount is not an integer" % lineno) from None


def normalise(rows):
    out = []
    for lineno, row in enumerate(rows, start=1):
        name, amount = _split_row(row, lineno)
        out.append({"name": name, "amount": _parse_amount(amount, lineno)})
    return out
'''

FAKE_BAD = '''\
def normalise(r):
    x = []
    for i in range(len(r)):
        try:
            a = r[i].split(",")
            b = a[0]
            c = a[1]
            d = int(c)
            e = {}
            e["name"] = b.strip()
            e["amount"] = d
            x.append(e)
        except:
            raise ValueError("bad")
    return x
'''

FAKE_MID = '''\
def normalise(rows):
    out = []
    n = 0
    for row in rows:
        n = n + 1
        parts = row.split(",")
        if len(parts) != 2:
            raise ValueError("line %d: expected 2 fields" % n)
        try:
            amount = int(parts[1].strip())
        except ValueError:
            raise ValueError("line %d: amount is not an integer" % n)
        out.append({"name": parts[0].strip(), "amount": amount})
    return out
'''

#: 負控：一份**刻意帶洩漏字串**的工作區。它必須被去識別化整包擋下來；
#: 擋不下來 ⇒ 那條紅線其實不存在。
FAKE_LEAKY = FAKE_MID + '''

# NOTE: A-GATE round 2 -- the acceptance run said case 3 failed, retry with seed
# 4242; receipt written to .vacant/logbook.
'''


def make_fake_run(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """造一個假的 run＋假的題庫，用來開發與測試（**不含任何真資料**）。

    形狀：3 題 × 3 臂 × 2 seed ＝ 18 格，其中
      · `fw_03_leak` 的 `A-GATE` 兩顆 seed ＝ **負控**（帶臂名／收據字樣，要被擋）；
      · `fw_02_ctrl` 的 `A-SOLO` ＝ **負控的另一半**：刻意寫壞（單一巨函式、裸
        except、無意義命名）；`A-GATE` ＝ 參考解 ⇒ 分數方向要對。
    """
    bank = root / "bank"
    run = root / "run"
    (run / "ws").mkdir(parents=True, exist_ok=True)
    tasks = {"fw_01_records": FAKE_TASK_MD,
             "fw_02_ctrl": FAKE_TASK_MD,
             "fw_03_leak": FAKE_TASK_MD}
    for tid, md in tasks.items():
        d = bank / tid
        (d / "template").mkdir(parents=True, exist_ok=True)
        (d / "task.md").write_text(md, encoding="utf-8")
        (d / "rubric.json").write_text(
            json.dumps(DEFAULT_RUBRIC, ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "visible.json").write_text(json.dumps(
            [{"kind": "call", "target": "normalise",
              "args": [["a,1"]], "expected": [{"name": "a", "amount": 1}]}],
            ensure_ascii=False), encoding="utf-8")
        (d / "template" / "TASK.md").write_text(md, encoding="utf-8")
        (d / "template" / "run_examples.sh").write_text(
            "#!/bin/sh\npython3 -c 'import solution'\n", encoding="utf-8")
        (d / "template" / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")

    bodies = {
        ("fw_01_records", "A-SOLO"): FAKE_MID,
        ("fw_01_records", "A-CONF"): FAKE_GOOD,
        ("fw_01_records", "A-GATE"): FAKE_GOOD,
        ("fw_02_ctrl", "A-SOLO"): FAKE_BAD,          # 負控：刻意寫壞
        ("fw_02_ctrl", "A-CONF"): FAKE_MID,
        ("fw_02_ctrl", "A-GATE"): FAKE_GOOD,         # 正控：參考解
        ("fw_03_leak", "A-SOLO"): FAKE_MID,
        ("fw_03_leak", "A-CONF"): FAKE_MID,
        ("fw_03_leak", "A-GATE"): FAKE_LEAKY,        # 負控：洩漏字串
    }
    rows = []
    for seed in ("fake-s1", "fake-s2"):
        for (tid, arm), body in bodies.items():
            att = 1 if arm == "A-SOLO" else 3
            ws = run / "ws" / f"{tid}_{arm}_{att}.tar.gz"
            stage = root / "_stage" / f"{tid}_{arm}_{seed}"
            if stage.exists():
                shutil.rmtree(stage)
            (stage / ".git").mkdir(parents=True, exist_ok=True)
            (stage / ".git" / "COMMIT_EDITMSG").write_text(
                f"attempt {att} on arm {arm}\n", encoding="utf-8")
            (stage / "TASK.md").write_text(tasks[tid], encoding="utf-8")
            (stage / "run_examples.sh").write_text(
                "#!/bin/sh\npython3 -c 'import solution'\n", encoding="utf-8")
            (stage / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
            (stage / "examples").mkdir(exist_ok=True)
            (stage / "examples" / "case_1.py").write_text(
                "assert normalise(['a,1'])\n", encoding="utf-8")
            # ⚠ 這一行本來寫成 `# seed-neutral filler`，結果 18 格全部被
            #   `seed` 這個凍結字樣擋掉——留著當紀錄：凍結清單裡的通用字
            #   （seed／gate／attempt）會把完全無辜的檔案整包丟掉。
            (stage / "solution.py").write_text(
                body + f"\n\n# padding {len(seed)}\n", encoding="utf-8")
            tar_name = f"{tid}_{arm}_{att}_{seed}"
            ws = run / "ws" / f"{tar_name}.tar.gz"
            with tarfile.open(ws, "w:gz") as tf:
                tf.add(stage, arcname=f"{tid}_{arm}")
            rows.append({"task_id": tid, "arm": arm, "seed": seed, "attempt": att,
                         "ws_tar": f"ws/{tar_name}.tar.gz",
                         "cell_id": f"{tid}|{arm}|{seed}",
                         "delivered": True})
    (run / "rows.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8")
    shutil.rmtree(root / "_stage", ignore_errors=True)
    return bank, run


# ── 量具探針：正控／負控（PR-3 的雙向紀律，§三-4）────────────────────────
def run_controls(graders: list[Grader], out_dir: pathlib.Path, *,
                 dry_run: bool = False, parse_retries: int = 2,
                 backoff_s: float = 5.0) -> dict:
    """把這把尺自己量一次：參考解、刻意寫壞的、帶洩漏字串的，各一份。

    三條判準（沿用 `vacant/suitegauge.py` 的雙向紀律——參考解要過、已知壞樁
    要被擋）：

      1. **正控**：參考解的四維總分 **>** 刻意寫壞那一份（單一巨函式、裸
         `except`、無意義命名）。
      2. **正控（分維）**：`structure` 與 `error_handling` 兩維各自 **≥**。
         這兩維是壞樁被做壞的地方；其他兩維不設判準（壞樁的 `goal_fit`
         其實沒被做壞，硬要求方向會變成要求評審亂給分）。
      3. **負控**：帶 `A-GATE`／`receipt`／`.vacant` 字樣那一份**必須整包被擋**。

    ⚠ 單邊保證（逐字沿用 `vacant/suitegauge.py`）：擋得住已知壞解 ≠ 涵蓋真需求。
      這個探針綠了只代表「這把尺分得出我們刻意做出來的好壞差」，
      **不代表**它分得出 A-GATE 與 A-SOLO 之間的差。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stage = out_dir / "_controls_ws"
    if stage.exists():
        shutil.rmtree(stage)
    bank_dir = stage / "bank" / "ctrl_task"
    (bank_dir / "template").mkdir(parents=True, exist_ok=True)
    (bank_dir / "task.md").write_text(FAKE_TASK_MD, encoding="utf-8")
    (bank_dir / "rubric.json").write_text(
        json.dumps(DEFAULT_RUBRIC, ensure_ascii=False, indent=2), encoding="utf-8")
    cells = []
    for label, body in (("good", FAKE_GOOD), ("bad", FAKE_BAD), ("leaky", FAKE_LEAKY)):
        ws = stage / "ws" / label
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "solution.py").write_text(body, encoding="utf-8")
        cells.append(Cell(cell_id=f"ctrl_task|CTRL-{label.upper()}|ctrl",
                          task_id="ctrl_task", arm=f"CTRL-{label.upper()}",
                          seed="ctrl", ws_path=ws))
    bank = load_bank(stage / "bank")
    summary = run_judging(cells, bank, graders, run_id="r530-controls",
                          salt="r530-controls", out_dir=out_dir / "controls",
                          dry_run=dry_run, parse_retries=parse_retries,
                          backoff_s=backoff_s)
    calls = [json.loads(l) for l in
             (out_dir / "controls" / "judge_calls.jsonl").read_text("utf-8").splitlines()
             if l.strip()]
    dropped = {d["cell"]["arm"] for d in summary["deident"]["dropped"]}
    res = {
        "schema": "r530.rubric.controls.v1",
        "negative_control_leaky_dropped": "CTRL-LEAKY" in dropped,
        "graders": [g.to_json() for g in graders],
        "by_grader": {}, "direction_ok": None, "notes": [
            "單邊保證：擋得住已知壞解 ≠ 涵蓋真需求（vacant/suitegauge.py 逐字）。",
            "正控綠 ≠ 這把尺分得出 A-GATE 與 A-SOLO 的差。",
        ],
    }
    all_ok = res["negative_control_leaky_dropped"]
    for g in graders:
        s = {r["cell"]["arm"]: r for r in calls
             if r["grader_id"] == g.gid and r["status"] == "ok"}
        good, bad = s.get("CTRL-GOOD"), s.get("CTRL-BAD")
        if not (good and bad):
            res["by_grader"][g.gid] = {"ok": False, "reason": "控制格沒有評到"}
            all_ok = False
            continue
        deltas = {d: good["scores"][d] - bad["scores"][d] for d in DIMS}
        total = sum(good["scores"].values()) - sum(bad["scores"].values())
        ok = total > 0 and deltas["structure"] >= 0 and deltas["error_handling"] >= 0
        res["by_grader"][g.gid] = {
            "ok": ok, "total_delta": total, "deltas": deltas,
            "good": good["scores"], "bad": bad["scores"],
            "reason_good": good["reason"], "reason_bad": bad["reason"]}
        all_ok = all_ok and ok
    res["direction_ok"] = all_ok
    (out_dir / "controls.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def print_controls(res: dict) -> None:
    print("=" * 78)
    print("R530 質化量具探針（正控／負控）")
    print(f"  負控（帶洩漏字樣那一份被整包擋下）：{res['negative_control_leaky_dropped']}")
    for gid, d in res["by_grader"].items():
        if not d.get("deltas"):
            print(f"  {gid}: {d.get('reason')}")
            continue
        print(f"  {gid}: 總分差 {d['total_delta']:+d}  "
              + "  ".join(f"{k}={v:+d}" for k, v in d["deltas"].items())
              + f"   方向{'對' if d['ok'] else '**錯**'}")
        print(f"      參考解 {d['good']}  「{d['reason_good'][:80]}」")
        print(f"      壞樁   {d['bad']}  「{d['reason_bad'][:80]}」")
    print(f"  direction_ok = {res['direction_ok']}")
    for n in res["notes"]:
        print(f"  · {n}")
    print("=" * 78)


# ── selftest／mutation-check ────────────────────────────────────────────
class _Fail(AssertionError):
    pass


def _close(a, b, tol=1e-9, what=""):
    if a is None or abs(a - b) > tol:
        raise _Fail(f"{what}: 期望 {b}，拿到 {a}")


def selftest(verbose: bool = True) -> int:
    """手算對照。每一條都寫得出算式，不是拿實作自己驗自己。"""
    checks: list[tuple[str, callable]] = []

    def check(name):
        def deco(fn):
            checks.append((name, fn))
            return fn
        return deco

    @check("QWK 手算：J1=[1,2,3,1] J2=[1,2,3,3] 類別(1,2,3) ⇒ 0.3846153846")
    def _():
        # 觀測加權不一致 = (1,3) 那一格 w=1 ⇒ 1/4 = 0.25
        # 期望加權不一致 = 0.25+0.03125+0.015625+0.03125+0.0625+0.015625 = 0.40625
        # kappa = 1 - 0.25/0.40625
        r = quadratic_weighted_kappa([1, 2, 3, 1], [1, 2, 3, 3], categories=(1, 2, 3))
        _close(r["observed_disagreement"], 0.25, what="QWK 觀測")
        _close(r["expected_disagreement"], 0.40625, what="QWK 期望")
        _close(r["kappa"], 1 - 0.25 / 0.40625, what="QWK")

    @check("QWK 類別集合固定 1–5：只觀測到 3/4 時分母仍是 (5-1)^2")
    def _():
        r = quadratic_weighted_kappa([3, 4, 3, 4], [4, 3, 4, 3])
        # w(3,4) = 1/16；觀測全在 (3,4)/(4,3) ⇒ 0.0625
        _close(r["observed_disagreement"], 0.0625, what="固定類別的觀測")

    @check("QWK 完全一致但常數 ⇒ kappa 沒有定義（None，不是 0）")
    def _():
        r = quadratic_weighted_kappa([3, 3, 3], [3, 3, 3])
        if r["kappa"] is not None:
            raise _Fail(f"常數評審的 kappa 應該是 None，拿到 {r['kappa']}")
        if "undefined" not in r["reason"]:
            raise _Fail("常數評審要附「沒有定義」的理由")

    @check("QWK 完全一致且有變異 ⇒ 1.0")
    def _():
        _close(quadratic_weighted_kappa([1, 3, 5], [1, 3, 5])["kappa"], 1.0,
               what="完全一致")

    @check("Spearman 手算：[1,2,3,4] vs [2,1,4,3] ⇒ 0.6")
    def _():
        _close(spearman([1, 2, 3, 4], [2, 1, 4, 3])["rho"], 0.6, what="Spearman 無 tie")

    @check("Spearman 手算（有 tie）：[1,1,2] vs [1,2,3] ⇒ 1.5/sqrt(3)")
    def _():
        _close(spearman([1, 1, 2], [1, 2, 3])["rho"], 1.5 / math.sqrt(3.0),
               what="Spearman 有 tie")

    @check("Spearman 手算（兩組不同大小的 tie）："
           "[1,1,2,3,3,3] vs [1..6] ⇒ sqrt(6/7)")
    def _():
        # 這一條才分得開「平均秩」與「取第一個位置當秩」：只有一組 tie 時，
        # 兩種秩互為仿射變換 ⇒ Pearson 一樣 ⇒ 測不出差別。
        # 平均秩 ra=[1.5,1.5,3,5,5,5]；cov=15、var_a=15、var_b=17.5
        # ⇒ rho = 15/sqrt(15*17.5) = sqrt(6/7) = 0.9258200998
        _close(spearman([1, 1, 2, 3, 3, 3], [1, 2, 3, 4, 5, 6])["rho"],
               math.sqrt(6.0 / 7.0), what="Spearman 兩組 tie")

    @check("Spearman 常數 ⇒ None")
    def _():
        if spearman([3, 3, 3], [1, 2, 3])["rho"] is not None:
            raise _Fail("常數評審的 rho 應該是 None")

    @check("Krippendorff ordinal 手算：[(1,2),(2,1)] ⇒ -0.5")
    def _():
        # o_12=o_21=2；n_1=n_2=2；δ²(1,2) = (2+2 - (2+2)/2)² = 4
        # Do = (2*4+2*4)/4 = 4；De = (2*2*4 + 2*2*4)/(4*3) = 32/12
        # alpha = 1 - 4/(32/12) = 1 - 1.5 = -0.5
        r = krippendorff_alpha_ordinal([(1, 2), (2, 1)], categories=(1, 2))
        _close(r["observed"], 4.0, what="alpha 觀測")
        _close(r["expected"], 32 / 12, what="alpha 期望")
        _close(r["alpha"], -0.5, what="alpha")

    @check("Krippendorff 完全一致且有變異 ⇒ 1.0；全常數 ⇒ None")
    def _():
        _close(krippendorff_alpha_ordinal([(1, 1), (5, 5), (3, 3)])["alpha"], 1.0,
               what="alpha 完全一致")
        if krippendorff_alpha_ordinal([(3, 3), (3, 3)])["alpha"] is not None:
            raise _Fail("全常數的 alpha 應該是 None")

    @check("中位數與四分位：[1,2,3,4,5] ⇒ med=3 q1=2 q3=4 mean=3")
    def _():
        r = median_quartiles([1, 2, 3, 4, 5])
        _close(r["median"], 3.0, what="med")
        _close(r["q1"], 2.0, what="q1")
        _close(r["q3"], 4.0, what="q3")
        _close(r["mean"], 3.0, what="mean")

    @check("解析：四個鍵齊全才算數；缺一個鍵回 None（不補 3 分）")
    def _():
        good = '```json\n{"readability":4,"structure":3,"error_handling":5,' \
               '"goal_fit":2,"reason":"x"}\n```'
        s, why = parse_scores(good)
        if s != {"readability": 4, "structure": 3, "error_handling": 5, "goal_fit": 2}:
            raise _Fail(f"解析錯：{s}")
        if why != "x":
            raise _Fail("reason 沒帶出來")
        if parse_scores('{"readability":4,"structure":3,"error_handling":5}') is not None:
            raise _Fail("缺鍵應該回 None")
        if parse_scores('{"readability":7,"structure":3,"error_handling":5,'
                        '"goal_fit":2}') is not None:
            raise _Fail("超出 1–5 應該回 None")

    @check("洩漏掃描：臂名／收據永不豁免；題目自己的字（retry）才豁免")
    def _():
        vocab = "the client wants a retry policy with exponential backoff"
        hits, exc = _leak_hits("we retry three times", vocab)
        if hits:
            raise _Fail(f"題目正文有 retry，不該命中：{hits}")
        if not any(e["token"] == "retry" for e in exc):
            raise _Fail("豁免要落盤")
        hits2, _ = _leak_hits("# A-GATE round 2", vocab)
        if not any(h["token"] in ("a-gate", "round 2") for h in hits2):
            raise _Fail("臂名必須命中")
        hits3, exc3 = _leak_hits("receipt written", "the receipt printer client")
        if hits3:
            raise _Fail("receipt 在題目正文裡時應該被豁免")
        hits4, _ = _leak_hits("aggregate the delegated investigation", vocab)
        if hits4:
            raise _Fail(f"aggregate/delegate 不該被 `gate` 命中：{hits4}")
        hits5, _ = _leak_hits("gates opened", vocab)
        if not hits5:
            raise _Fail("`gates` 應該被 `gate` 命中")

    @check("盲：兩位評審的呈現順序不同，且 sample_id 不含題目／臂／seed")
    def _():
        cells = [Deident(cell=Cell(f"t{i}|A-GATE|s1", f"t{i}", "A-GATE", "s1",
                                   pathlib.Path(".")),
                         sample_id=sample_id_for("salt", f"t{i}|A-GATE|s1"))
                 for i in range(12)]
        g1 = Grader("J1", "x", "m", "j1")
        g2 = Grader("J2", "x", "m", "j2")
        o1 = [d.sample_id for d in blind_order(cells, g1, "run")]
        o2 = [d.sample_id for d in blind_order(cells, g2, "run")]
        if o1 == o2:
            raise _Fail("兩位評審的順序一樣＝順序隨機沒生效")
        if sorted(o1) != sorted(o2):
            raise _Fail("兩位評審看到的集合必須相同")
        again = [d.sample_id for d in blind_order(cells, g1, "run")]
        if again != o1:
            raise _Fail("同一位評審同一個 run 的順序必須可重算")
        for d in cells:
            for bad in ("A-GATE", "t0", "s1"):
                if bad.lower() in d.sample_id.lower():
                    raise _Fail(f"sample_id 洩漏 {bad}")

    @check("彙整：does_not_change_four_state 永遠是 True")
    def _():
        s = aggregate([], [], [Grader("J1", "x", "m", "a"), Grader("J2", "x", "m", "b")],
                      run_id="r", salt="s")
        if s["does_not_change_four_state"] is not True:
            raise _Fail("§六-6 的擋門不見了")
        if "irr" not in s["rubric"] or "deident_dropped_n" not in s["rubric"]:
            raise _Fail("預註冊指名的欄位不見了")

    @check("彙整：中位數逐 seed 分開算，不跨 seed 平均")
    def _():
        recs = []
        for seed, vals in (("s1", [5, 5, 5]), ("s2", [1, 1, 1])):
            for i, v in enumerate(vals):
                for gid in ("J1", "J2"):
                    recs.append({
                        "status": "ok", "grader_id": gid, "sample_id": f"x{seed}{i}",
                        "reason": "", "scores": {d: v for d in DIMS},
                        "cell": {"cell_id": f"t{i}|A-GATE|{seed}", "task_id": f"t{i}",
                                 "arm": "A-GATE", "seed": seed}})
        s = aggregate(recs, [], [Grader("J1", "x", "m", "a"), Grader("J2", "x", "m", "b")],
                      run_id="r", salt="s")
        _close(s["rubric"]["s1"]["readability"]["A-GATE"]["median"], 5.0, what="s1")
        _close(s["rubric"]["s2"]["readability"]["A-GATE"]["median"], 1.0, what="s2")
        if "s1s2" in s["rubric"] or len(s["rubric"]["s1"]["readability"]) != 1:
            raise _Fail("seed 被混在一起了")

    @check("差 ≥2 分的格要進清單")
    def _():
        recs = []
        for gid, v in (("J1", 5), ("J2", 2)):
            recs.append({"status": "ok", "grader_id": gid, "sample_id": "s",
                         "reason": f"{gid} said so",
                         "scores": {d: v for d in DIMS},
                         "cell": {"cell_id": "t|A-GATE|s1", "task_id": "t",
                                  "arm": "A-GATE", "seed": "s1"}})
        s = aggregate(recs, [], [Grader("J1", "x", "m", "a"), Grader("J2", "x", "m", "b")],
                      run_id="r", salt="s")
        if len(s["disagreements"]) != len(DIMS):
            raise _Fail(f"四維都差 3 分，應該有 {len(DIMS)} 筆，"
                        f"拿到 {len(s['disagreements'])}")

    failed = 0
    for name, fn in checks:
        try:
            fn()
            if verbose:
                print(f"  ok   {name}")
        except Exception as e:                               # noqa: BLE001
            failed += 1
            print(f"  FAIL {name}\n       {e}")
    if verbose:
        print(f"selftest: {len(checks) - failed}/{len(checks)} 通過")
    return 1 if failed else 0


def mutation_check(verbose: bool = True) -> int:
    """每一種壞法都要被 `selftest` 抓到。抓不到的突變＝那條紅線其實不存在。"""
    g = globals()
    muts: list[tuple[str, str, callable]] = []

    def _linear_kappa(a, b, categories=SCALE):
        n = len(a)
        if not n:
            return {"kappa": None, "n": 0, "reason": ""}
        k = len(categories)
        idx = {c: i for i, c in enumerate(categories)}
        obs = [[0.0] * k for _ in range(k)]
        for x, y in zip(a, b):
            obs[idx[x]][idx[y]] += 1.0
        rows = [sum(r) for r in obs]
        cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]
        no = ne = 0.0
        for i in range(k):
            for j in range(k):
                w = abs(i - j) / (k - 1)          # ← 線性權重（錯）
                no += w * obs[i][j] / n
                ne += w * rows[i] * cols[j] / (n * n)
        if ne == 0:
            return {"kappa": None, "n": n, "observed_disagreement": no,
                    "expected_disagreement": 0.0, "reason": "undefined"}
        return {"kappa": 1 - no / ne, "n": n, "observed_disagreement": no,
                "expected_disagreement": ne, "reason": ""}
    muts.append(("QWK 權重改成線性", "quadratic_weighted_kappa", _linear_kappa))

    # ⚠ 突變版**不可以**經由 globals 回頭呼叫被換掉的那一支（那是無限遞迴）。
    #   原實作用預設引數在定義時就綁進來。
    def _zero_kappa(a, b, categories=SCALE, _orig=quadratic_weighted_kappa):
        r = _orig(a, b, categories)
        if r["kappa"] is None:
            r = {**r, "kappa": 0.0, "reason": ""}      # ← 把「沒有定義」塌成 0
        return r
    muts.append(("kappa 把 None 塌成 0.0", "quadratic_weighted_kappa", _zero_kappa))

    def _naive_spearman(a, b):
        n = len(a)
        if n < 2:
            return {"rho": None, "n": n, "reason": "n < 2"}
        ra = [sorted(a).index(x) + 1 for x in a]       # ← tie 不取平均秩
        rb = [sorted(b).index(y) + 1 for y in b]
        ma, mb = sum(ra) / n, sum(rb) / n
        cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
        va = math.sqrt(sum((x - ma) ** 2 for x in ra))
        vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
        if va == 0 or vb == 0:
            return {"rho": None, "n": n, "reason": "undefined"}
        return {"rho": cov / (va * vb), "n": n, "reason": ""}
    muts.append(("Spearman 不處理 tie", "spearman", _naive_spearman))

    def _nominal_alpha(pairs, categories=SCALE):
        if not pairs:
            return {"alpha": None, "n_units": 0, "reason": ""}
        k = len(categories)
        idx = {c: i for i, c in enumerate(categories)}
        o = [[0.0] * k for _ in range(k)]
        for x, y in pairs:
            o[idx[x]][idx[y]] += 1.0
            o[idx[y]][idx[x]] += 1.0
        nc = [sum(r) for r in o]
        n = sum(nc)
        if n < 2:
            return {"alpha": None, "n_units": len(pairs), "reason": ""}
        d2 = lambda i, j: (0.0 if i == j else 1.0)     # ← nominal metric（錯）
        do = sum(o[i][j] * d2(i, j) for i in range(k) for j in range(k)) / n
        de = sum(nc[i] * nc[j] * d2(i, j)
                 for i in range(k) for j in range(k)) / (n * (n - 1))
        if de == 0:
            return {"alpha": None, "n_units": len(pairs), "observed": do,
                    "expected": 0.0, "reason": "undefined"}
        return {"alpha": 1 - do / de, "n_units": len(pairs), "observed": do,
                "expected": de, "reason": ""}
    muts.append(("Krippendorff 用 nominal metric", "krippendorff_alpha_ordinal",
                 _nominal_alpha))

    def _mean_only(xs):
        if not xs:
            return {"n": 0, "median": None, "q1": None, "q3": None, "mean": None,
                    "min": None, "max": None}
        m = float(statistics.fmean(xs))
        return {"n": len(xs), "median": m, "q1": m, "q3": m, "mean": m,
                "min": float(min(xs)), "max": float(max(xs))}
    muts.append(("中位數改成平均數", "median_quartiles", _mean_only))

    def _blind_noop(cells, grader, run_id):
        return list(cells)                               # ← 兩位評審同一個順序
    muts.append(("順序隨機被拿掉", "blind_order", _blind_noop))

    def _no_leak(text, vocab):
        return [], []                                    # ← 洩漏掃描整個失效
    muts.append(("洩漏掃描回空", "_leak_hits", _no_leak))

    def _lenient_parse(text, _orig=parse_scores):
        r = _orig(text)
        if r is None:
            return {d: 3 for d in DIMS}, ""               # ← 解析不出來就給 3 分
        return r
    muts.append(("解析失敗補 3 分", "parse_scores", _lenient_parse))

    def _wide_pattern(token):
        return re.compile(re.escape(token), re.IGNORECASE)   # ← 全用子字串
    muts.append(("字樣比對全用子字串（aggregate 會被 gate 命中）",
                 "_token_pattern", _wide_pattern))

    failed = 0
    for name, target, impl in muts:
        orig = g[target]
        orig_patterns = dict(_PATTERNS)
        g[target] = impl
        if target == "_token_pattern":
            _PATTERNS.clear()
            _PATTERNS.update({t: impl(t) for t in orig_patterns})
        try:
            rc = selftest(verbose=False)
        finally:
            g[target] = orig
            _PATTERNS.clear()
            _PATTERNS.update(orig_patterns)
        if rc == 0:
            failed += 1
            print(f"  NOT CAUGHT  {name}   ← 這條紅線其實不存在")
        elif verbose:
            print(f"  caught      {name}")
    if verbose:
        print(f"mutation-check: {len(muts) - failed}/{len(muts)} 被抓到")
    return 1 if failed else 0


# ── CLI ────────────────────────────────────────────────────────────────
def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="R530 質化盲評管線（預註冊 §五-6）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_argument_group("輸入")
    src.add_argument("--cells-jsonl", help="每列一格："
                     '{"cell_id","task_id","arm","seed","ws_tar"|"ws_dir"}')
    src.add_argument("--run-dir", help="從 runs/<name>/rows.jsonl 或 ws/*.tar.gz 探索")
    src.add_argument("--bank", default="ops/gain/data/openwork",
                     help="題庫根目錄（<task>/task.md、rubric.json、template/）")
    src.add_argument("--run-id", default=None)
    src.add_argument("--seed-label", default=None,
                     help="用 ws/*.tar.gz 探索時，這一塊的 seed 標籤")
    src.add_argument("--tasks", default=None, help="逗號分隔，只跑這些題")
    src.add_argument("--arms", default=None, help="逗號分隔，只跑這些臂")
    src.add_argument("--limit", type=int, default=0)

    out = ap.add_argument_group("輸出")
    out.add_argument("--out-dir", default=None)
    out.add_argument("--keep-deident-dir", action="store_true",
                     help="把去識別化後的檔案樹寫出來給人翻")
    out.add_argument("--json", default=None, help="另存一份 summary JSON")

    jd = ap.add_argument_group("評審")
    jd.add_argument("--grader", action="append", default=[],
                    help="id=J1;api=…;model=…;seed=…;effort=none;kind=backend|stub")
    jd.add_argument("--stub-graders", action="store_true",
                    help="離線替身評審（**不是模型**，不准進收官）")
    jd.add_argument("--blind-salt", default=None,
                    help="sample_id 的 salt（預設＝run_id）")
    jd.add_argument("--parse-retries", type=int, default=2)
    jd.add_argument("--backoff-s", type=float, default=5.0)
    jd.add_argument("--disagree-threshold", type=int, default=2)
    jd.add_argument("--max-file-bytes", type=int, default=MAX_FILE_BYTES)
    jd.add_argument("--max-prompt-chars", type=int, default=MAX_PROMPT_CHARS)
    jd.add_argument("--dry-run", action="store_true", help="不打後端，只產 prompt")

    dev = ap.add_argument_group("開發")
    dev.add_argument("--selftest", action="store_true")
    dev.add_argument("--mutation-check", action="store_true")
    dev.add_argument("--make-fake-run", default=None, help="造假工作區到這個目錄")
    dev.add_argument("--controls", action="store_true",
                     help="量具探針：參考解 vs 刻意寫壞的（方向要對）＋洩漏負控")
    return ap


def resolve_graders(args) -> list[Grader]:
    if args.stub_graders:
        return [Grader("J1", "stub://1", "stub", "j1-stub", kind="stub"),
                Grader("J2", "stub://2", "stub", "j2-stub", kind="stub")]
    if args.grader:
        graders = [parse_grader(s) for s in args.grader]
    else:
        graders = [parse_grader(";".join(f"{k}={v}" for k, v in g.items()))
                   for g in DEFAULT_GRADERS]
    if len({g.gid for g in graders}) != len(graders):
        raise SystemExit("[graders] id 重複")
    return graders


def main(argv=None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.mutation_check:
        return mutation_check()
    if args.make_fake_run:
        bank, run = make_fake_run(pathlib.Path(args.make_fake_run))
        print(f"假題庫 {bank}\n假 run  {run}")
        return 0

    graders = resolve_graders(args)
    if args.controls:
        out_dir = pathlib.Path(args.out_dir or "./r530_controls")
        res = run_controls(graders, out_dir, dry_run=args.dry_run,
                           parse_retries=args.parse_retries, backoff_s=args.backoff_s)
        print_controls(res)
        return 0 if res["direction_ok"] else 1

    if not (args.cells_jsonl or args.run_dir):
        ap.error("要 --cells-jsonl 或 --run-dir（或 --selftest／--make-fake-run）")

    cells, run_id = load_cells(args)
    if args.tasks:
        keep = set(args.tasks.split(","))
        cells = [c for c in cells if c.task_id in keep]
    if args.arms:
        keep = set(args.arms.split(","))
        cells = [c for c in cells if c.arm in keep]
    if args.limit:
        cells = cells[: args.limit]
    if not cells:
        raise SystemExit("[cells] 篩完之後一格都不剩")

    bank = load_bank(pathlib.Path(args.bank))
    salt = args.blind_salt or run_id
    out_dir = pathlib.Path(args.out_dir or (pathlib.Path(args.run_dir or ".") / "rubric"))
    summary = run_judging(
        cells, bank, graders, run_id=run_id, salt=salt, out_dir=out_dir,
        dry_run=args.dry_run, parse_retries=args.parse_retries,
        keep_deident=args.keep_deident_dir, backoff_s=args.backoff_s,
        max_file_bytes=args.max_file_bytes, max_prompt_chars=args.max_prompt_chars,
        disagree_threshold=args.disagree_threshold)
    print_report(summary)
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n落盤：{out_dir}/"
          "{deident.jsonl,judge_prompts.jsonl,judge_calls.jsonl,rubric_summary.json}")
    return 0


# KS-1 防呆（鐵律 1）：import 時就跑，繞不過去。送給評審的每一段文字都要過。
for _txt in (JUDGE_SYSTEM, JUDGE_PROMPT_HEADER, JUDGE_PROMPT_FOOTER,
             *(lvl for dim in DEFAULT_RUBRIC.values() for lvl in dim.values())):
    assert_ks1_clean(_txt)
del _txt


if __name__ == "__main__":
    raise SystemExit(main())
