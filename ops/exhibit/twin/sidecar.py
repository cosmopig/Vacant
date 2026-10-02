"""twin/sidecar — 分身**自己**記的旁註串流（`twin.sidecar/1`）。不是 Vacant 的事件。

## 這支在架構裡承重什麼

2026-09-24 人類裁決兩次：

1. 「刪事後推導，留錄影重播」——電視事件只剩 `vacant.lifecycle/1` 一條路。
   副作用：OFF 臂的事後稽核（`postaudit`）與整批累計（`counters`）從電視上消失。
2. 「**分身側自己記一份補回**」——這兩樣**不是 Vacant 當場做的事**，所以
   **不准進 Vacant 的 lifecycle 契約**（`vacant_network/vrun/*` 一個字都不動）。

這一支就是第 2 條的那「一份」：分身（`run_twin.py`）在**它自己做的事**發生的當下
寫一筆旁註。現在只有一種——`postaudit`：OFF 那一跑結束之後，分身用同一把尺
（`tests_visible`）在 OFF 的凍結快照上補量一次（`run_twin.postaudit_off`）。

```
 vacant run ──lifecycle.jsonl──────────┐   Vacant 當場觀察到的（契約：lifecycle.py）
 run_twin.postaudit_off ──X.sidecar.jsonl ┴─▶ live_events.Folder ──▶ 電視 postaudit
                          分身自己事後做的（契約：這一支）
```

`counters` **不在旁註裡**：它不是任何人「做」的一件事，是 `serve_twin` 依
**已經播過的格子**當場數出來的（`live_events.Tally`）。旁註只記發生過的事。

## 放哪裡：旁邊一個同名 `X.sidecar.jsonl`（**不**混進 lifecycle 同一個檔）

選了分檔，理由依重要性排：

1. **lifecycle 檔要維持「純 Vacant」。** `lifecycle.validate_stream` 見到不認得的
   schema 會判整份不合格，而 `serve_twin.load_recordings` 的規則是「一行壞就整份不收」。
   混在同一個檔 ⇒ 要嘛改 Vacant 的 validate（不准動 `vrun/*`），要嘛每一個讀
   lifecycle 的人都得先學會「跳過分身的行」——第一個沒學會的讀者會把整份錄影判死，
   或者更糟：學會「跳過不認得的行」，之後 Vacant 真的換版時也安靜地跳過。
2. **兩個作者、兩份來歷，在檔案層就分得開。** 「這一行是 Vacant 當場觀察到的」
   與「這一行是分身事後補量的」是展場最不能混的兩句話（鐵律 5 的展場版本）。
   分檔之後，連 `grep` 都不會把它們混成一句。
3. **寫的人本來就不同。** lifecycle 是 `launcher` 裡的 `Emitter` 開檔追加；
   旁註是 `run_twin` 在 `launcher.run` 回來之後追加。同一個檔兩個寫者，
   要靠行寫入的原子性撐著；分檔就沒有這個問題。

分檔的代價與補法：

- **錄影的 sha256 綁定原本只涵蓋 lifecycle 那一個檔。** ⇒ `pair_receipts` 另外綁
  旁註的 sha256（`pack["recording"]["sidecar"]`），規則對稱：資料包綁了旁註而旁註
  不在、旁註在而資料包沒綁、sha256 對不上，三種都不收（`pair_receipts.check_sidecar`）。
- **`recordings/*.jsonl` 的 glob 會掃到 `X.sidecar.jsonl`。** ⇒
  `serve_twin.default_recordings` 用 `is_sidecar` 排掉；就算有人硬塞
  `--recording X.sidecar.jsonl`，它過不了 `lifecycle.validate_stream`，照樣整份不收。
- **現場真跑要 tail 兩個檔。** ⇒ `serve_twin --live L.jsonl` 自動 tail
  `sidecar_path(L)`，兩者都用 `live_events.Tail`。

## 契約（`twin.sidecar/1`）

每一行一個 JSON 物件。共同欄位 `COMMON`，各型別專屬欄位 `FIELDS`（**key 一定要在**，
值可以是 `None`——「沒量到」要看得見）。`validate()` 是可執行版本。

`postaudit`：

| 欄位 | 意思 |
|---|---|
| `cell_id` | 哪一格（＝ lifecycle `run_started.caller.cell_id`） |
| `run_id` | **被量的那一跑**（OFF 臂）的 lifecycle `run_id` |
| `ws_end_sha256` | 那一跑 `run_ended.ws_end_sha256`：量的就是這棵凍結的樹 |
| `arm` | 恆 `"OFF"` |
| `when` | 恆 `"after_the_run"` |
| `is_verdict` | 恆 `false` |
| `signed` | 恆 `false` |
| `all_pass`／`passed`／`total` | 同一份 `tests_visible` 的結果 |
| `failed_case` | 第一個沒過的案例**名字**（不帶訊息全文），全過＝`null` |
| `ruler`／`note` | 用哪一把尺、以及「這不是裁決」那一句 |

`twin_step`（2026-09-28，契約 `plans/CONTRACT_PROCESS_20260928.md` §A）：

| 欄位 | 意思 |
|---|---|
| `cell_id` | 哪一格（＝ `twin_id`） |
| `run_id` | 這一跑（**ON** 臂，分身只有一臂）的 lifecycle `run_id` |
| `seq` | 原始記錄檔裡的序號（同一跑內單調遞增，從 1 開始） |
| `step` | `read`／`write`／`list`（`ws_read`／`ws_write`／`ws_list` 的動詞形） |
| `path_kind` | `traits`／`plan`／`artifact`／`other`（`ws_list` 恆 `other`） |
| `bytes` | 讀到或寫入的位元組數；`ws_list` 恆 `null` |
| `ok` | 這次呼叫有沒有被 `confine()` 擋下 |

**不帶檔名。** 原始記錄檔（`twinagent.STEP_LOG_NAME`，住在 run-dir，工作區外）
才有檔名，那一份只給手機用（見 `twinagent.read_step_log`），撤回時跟 run-dir
一起刪。

## 綁定（`validate(rows, lifecycle_events=…)`）

每一筆 `postaudit` 都要綁得上**同一份錄影裡**的一跑：`run_id` 存在、是 `RUN-OFF`、
有 `run_ended`、不是 `infra_void`、`ws_end_sha256` 相等、`cell_id` 相等、
`ts_ms` 不早於那一跑的 `run_ended`（「事後」要在資料上成立）、一跑最多一筆。
綁不上 ⇒ 整份旁註不收（**不是**整份錄影不收：lifecycle 是 Vacant 的紀錄，
它本身沒壞；壞的是分身的註，那就不演分身的註）。

每一筆 `twin_step` 要綁得上**同一份錄影裡**的一跑：`run_id` 存在、是 `RUN-ON`、
`cell_id` 相等、`ts_ms` 不早於那一跑的 `run_started`（一跑可以有很多筆，
不像 `postaudit` 一跑最多一筆）。**不要求 `run_ended` 已經出現**——這一種
旁註本來就發生在那一跑**進行中**。

## 誠實邊界（改碼時保留）

1. **旁註不是證據，也不是裁決。** 沒有簽章、沒有進收據鏈；三個旗標
   （`when`／`is_verdict`／`signed`）缺一不可，`validate` 與電視契約各擋一次。
2. **旁註不准改變一跑的任何東西。** 它在 `launcher.run` 回來**之後**才寫，
   寫不進去只印一行警告（`append` 回錯誤字串，不丟例外）。
3. **不帶內容。** 不寫案例訊息全文、不寫程式碼、不寫 prompt（`CONTENT_KEYS`）。
4. **不准拿舊 run 目錄補寫旁註。** 旁註只在 `postaudit_off` 完成的當下寫；
   事後替沒有旁註的舊錄影補一份＝事後推導從後門回來（與 `pair_receipts`
   誠實邊界 3 同一條）。舊錄影沒有旁註，電視上就沒有 postaudit。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
from typing import Any, Iterable

SCHEMA = "twin.sidecar/1"

#: 檔名後綴：`X.jsonl` 的旁註是 `X.sidecar.jsonl`。
SUFFIX = ".sidecar.jsonl"

#: `twin_step`：分身工作區三個工具（`ws_list`／`ws_read`／`ws_write`）被呼叫的旁註
#: （契約 `plans/CONTRACT_PROCESS_20260928.md` §A，2026-09-28）。**不是** Vacant
#: 當場觀察到的事——它來自分身側自己寫的原始記錄檔（`twinagent.STEP_LOG_NAME`），
#: 由分身迴圈（`twinagent.StepForwarder`）轉寫成這裡的一行，理由與 `postaudit`
#: 同一條（見模組 docstring）：不准進 lifecycle 契約，`vacant_network/vrun/*` 不動。
#:
#: `twin_say`（契約補充 `plans/CONTRACT_PROCESS_20261001_ADDENDUM.md` §E，2026-10-01）：
#: 分身的 pi 以 `--mode json` 跑，`agent_stdout.log` 裡每一回合 assistant 的**文字**
#: （不含思考區塊、不含工具呼叫的參數）→ 一筆旁註。來源同樣是分身側自己的記錄
#: （pi 的 stdout），不是 Vacant 當場觀察到的事，理由與上面兩種同一條。
#:
#: `twin_fortune`（P10，2026-10-02，`decisions/DECISION_20261002_TWIN_FORTUNE.md`）：分身這一跑用的**命盤**。
#: 兩拍：`way`（段 1 結束、命盤定下來，電視演「它照著你的命盤……」）、`card`（每次嘗試結束、命盤卡檢查完，
#: 電視收尾那一拍）。欄位全是**枚舉**（MBTI 16 型、mbti_source、元素、血型）；`lines` 只在 `card` 拍有，
#: ≤ 3 句、每句 ≤ 60 字，是分身依這一跑的步驟寫、且已逐句對過步驟紀錄的「你是 X，所以我 Y」（不帶檔名）。
TYPES = ("postaudit", "twin_step", "twin_say", "twin_gate", "twin_fortune")

COMMON = ("schema", "type", "ts_ms", "cell_id", "run_id")

FIELDS: dict[str, tuple[str, ...]] = {
    "postaudit": ("arm", "ws_end_sha256", "when", "is_verdict", "signed",
                  "all_pass", "passed", "total", "failed_case", "ruler", "note"),
    "twin_step": ("seq", "step", "path_kind", "bytes", "ok"),
    "twin_say": ("seq", "turn", "text", "truncated"),
    # 根據閘門（`grounding_gate.prepare`，2026-10-01）：這一次嘗試的四格窗逐格結果。
    # 寫在 `gate_ran` 之前（pi 結束、凍結之前），電視才拿得到逐格結果；權威的結果仍是
    # launcher 落的 `visible_*.json`（測試比對兩者相等）。
    "twin_gate": ("attempt", "passed", "checks"),
    "twin_fortune": ("phase", "attempt", "mbti", "mbti_source", "zodiac", "element", "blood", "lines"),
}
#: `twin_fortune` 的枚舉（與 `tv_contract.FORTUNE_*` 同值，測試釘住；`fortune.py` 是來源）。
FORTUNE_PHASES = ("way", "card")
FORTUNE_MBTI = ("INFP", "INFJ", "INTP", "INTJ", "ISFP", "ISFJ", "ISTP", "ISTJ",
                "ENFP", "ENFJ", "ENTP", "ENTJ", "ESFP", "ESFJ", "ESTP", "ESTJ")
FORTUNE_SOURCES = ("ai", "self", "twin")
FORTUNE_ZODIACS = ("牡羊", "金牛", "雙子", "巨蟹", "獅子", "處女", "天秤", "天蠍", "射手", "摩羯", "水瓶", "雙魚")
FORTUNE_ELEMENTS = ("火", "土", "風", "水")
FORTUNE_BLOODS = ("A", "B", "O", "AB")
FORTUNE_MAX_LINES = 3
FORTUNE_LINE_MAX = 60
#: `twin_gate.checks[]` 每條准出現的欄位（與 `tv_contract.GATE_CHECK_KEYS` 同值，測試釘住）。
GATE_CHECK_KEYS = ("id", "ok", "label", "file", "line")

#: `twin_say.text` 的字數上限（契約補充 §E）。超過就截斷並 `truncated: true`。
SAY_MAX = 80

WHEN_AFTER = "after_the_run"

#: 旁註裡不准出現的內容欄位（誠實邊界 3）。`path`／`name`／`file`／`text` 是
#: `twin_step` 那一份加的：原始記錄檔（給手機用）含檔名，但轉進這裡的這一份
#: **不帶檔名**（電視事件流的規則，契約 §A）。
CONTENT_KEYS = ("cases", "message", "body", "request", "response", "messages",
                "prompt", "code", "source", "path", "name", "file", "text")

#: lifecycle 那一側 OFF／ON 臂的名字（launcher 的 `arm`）。
LC_ARM_OFF = "RUN-OFF"
LC_ARM_ON = "RUN-ON"

#: `twin_step.step` 的白名單（`ws_read`／`ws_write`／`ws_list` 的動詞形）。
STEP_KINDS = ("read", "write", "list")
#: 原始記錄檔的 `tool` → `twin_step.step`。
_TOOL_TO_STEP = {"ws_read": "read", "ws_write": "write", "ws_list": "list"}

#: `twin_step.path_kind` 的白名單（契約 §A）。
#: 地上的八個地點（`world/materials/<地點>/`）→ 固定代號。**列舉**：路徑裡的地點名
#: 只用來查這張表，查不到就歸 `other`；代號以外的東西（檔名、內容）不外流。
GROUND_PLACES = {
    "投遞口": "drop", "捏土處": "clay", "長桌廣場": "longtable", "石頭閘門": "gate",
    "帳本鏈": "chain", "草稿角": "draft", "紙卡地": "cards", "畫架與長椅": "easel",
}
GROUND_KINDS = tuple("ground:" + c for c in GROUND_PLACES.values())
PATH_KINDS = ("traits", "plan", "artifact", "other") + GROUND_KINDS


def sidecar_path(lifecycle_path: str | os.PathLike) -> pathlib.Path:
    """`X.jsonl` → `X.sidecar.jsonl`（同目錄）。"""
    p = pathlib.Path(lifecycle_path)
    return p.with_name(p.stem + SUFFIX)


def is_sidecar(path: str | os.PathLike) -> bool:
    return pathlib.Path(path).name.endswith(SUFFIX)


def _first_failed(result: dict) -> str | None:
    """第一個沒過的可見測試名。**走訪順序與 ON 臂 `gate_ran.failed_case` 相同**
    （`launcher._first_failed_case`：`files[*].cases[*]`），兩臂同一把尺、同一種讀法。"""
    for f in result.get("files") or []:
        for c in f.get("cases") or []:
            if not c.get("ok"):
                return c.get("case")
    return None


def postaudit_row(pa: dict, *, cell_id: str, run_id: str,
                  ws_end_sha256: str | None, ts_ms: int | None = None) -> dict:
    """`run_twin.postaudit_off` 的回傳 → 一筆旁註。三個旗標**寫死**，不從 `pa` 抄。

    ⚠ 寫死的理由：`pa` 是 `run_twin` 自己組的 dict，改碼的人手滑把 `is_verdict`
      改成 `True` 也不會有任何東西攔他；旁註這一層再寫死一次，資料上就不可能出現
      「事後稽核自稱裁決」。
    """
    return {
        "schema": SCHEMA, "type": "postaudit",
        "ts_ms": int(ts_ms if ts_ms is not None else time.time() * 1000),
        "cell_id": cell_id, "run_id": run_id, "arm": "OFF",
        "ws_end_sha256": ws_end_sha256,
        "when": WHEN_AFTER, "is_verdict": False, "signed": False,
        "all_pass": bool(pa.get("all_pass")),
        "passed": pa.get("passed"), "total": pa.get("total"),
        "failed_case": _first_failed(pa),
        "ruler": pa.get("ruler"), "note": pa.get("note"),
    }


def classify_path_kind(tool: Any, path: Any) -> str:
    """原始記錄的 `(tool, path)` → `twin_step.path_kind`（契約 §A 的三類＋`other`）。

    `ws_list` 沒有單一檔案可指 ⇒ 恆 `other`；`TRAITS.md`／`PLAN.md` 認**檔名**
    （不管在哪一層目錄——分身的工作區目前是扁平的，但這裡不假設它永遠扁平）。
    """
    if tool != "ws_read" and tool != "ws_write":
        return "other"
    if not isinstance(path, str) or not path:
        return "other"
    parts = [x for x in path.replace("\\", "/").split("/") if x not in ("", ".")]
    if ".." in parts:                # 路徑穿越：不認、不猜
        return "other"
    if parts and parts[0] == "地上":      # 地上/<地點>/<檔>：只取地點代號
        code = GROUND_PLACES.get(parts[1]) if len(parts) >= 2 else None
        return "ground:" + code if code else "other"
    name = parts[-1] if parts else ""
    if name == "TRAITS.md":
        return "traits"
    if name == "PLAN.md":
        return "plan"
    if name == "WORLD.md":          # 世界設定：不是成品、也不是觀眾特質；契約白名單不加新值
        return "other"
    return "artifact"


def twin_step_row(raw: dict, *, cell_id: str, run_id: str) -> dict | None:
    """原始記錄檔（`twinagent.STEP_LOG_NAME`）一行 → 一筆 `twin_step` 旁註。

    形狀不對（不是我們自己寫的那個格式）回 `None`，呼叫端只計數不轉發
    ——這一份會進電視事件流，寧可少轉一行也不要轉一行形狀不對的。
    **不帶檔名**：`raw["path"]` 只用來分類 `path_kind`，不放進回傳值
    （契約 §A：「這一份會進電視事件流」的那一份不帶檔名）。
    """
    if not isinstance(raw, dict):
        return None
    step = _TOOL_TO_STEP.get(raw.get("tool"))
    if step is None:
        return None
    seq = raw.get("seq")
    ok = raw.get("ok")
    if not _is_nat(seq) or not isinstance(ok, bool):
        return None
    b = raw.get("bytes")
    if b is not None and not _is_nat(b):
        return None
    ts_ms = raw.get("ts_ms")
    if not _is_nat(ts_ms):
        ts_ms = int(time.time() * 1000)
    return {
        "schema": SCHEMA, "type": "twin_step", "ts_ms": ts_ms,
        "cell_id": cell_id, "run_id": run_id,
        "seq": seq, "step": step,
        "path_kind": classify_path_kind(raw.get("tool"), raw.get("path")),
        "bytes": b, "ok": ok,
    }


#: gemma 的思考通道記號：`<|channel>thought … <channel|>`（真 pi 實測會漏進 text 區塊）。
#: 通道裡面是**思考**，整段丟（沒關上就丟到結尾）；契約補充：思考不發。
_THOUGHT_CHANNEL_RE = re.compile(r"<\|channel>.*?(?:<channel\|>|$)", re.S)
_SPECIAL_TOKEN_RE = re.compile(r"<\|[^>\n]{0,40}>|<[^<>\n]{0,40}\|>")
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_FENCE_RE = re.compile(r"```.*?```", re.S)
_MD_LEAD_RE = re.compile(r"(?m)^\s*(?:#{1,6}\s+|>\s+|[-*+]\s+|\d+[.)]\s+)")


def clean_say(text: Any) -> str:
    """pi 的 assistant 文字 → 旁註的 `text`：去 markdown 標記、去模型殘留的特殊記號
    （真 pi 實測：`<|channel>thought\n<channel|>` 會漏進 text 區塊）、合併空白。

    **不改寫**：只刪標記與空白，字都是 agent 自己生的。程式碼區塊整段丟掉
    （契約補充：code 格不出，也不把程式碼當成「它在想」）。
    """
    if not isinstance(text, str):
        return ""
    t = _MD_FENCE_RE.sub(" ", text)
    t = _THOUGHT_CHANNEL_RE.sub(" ", t)
    t = _SPECIAL_TOKEN_RE.sub(" ", t)
    t = _MD_LINK_RE.sub(r"\1", t)
    t = _MD_LEAD_RE.sub("", t)
    t = re.sub(r"[`*~#>]+|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", t)   # 檔名裡的 _ 不動
    return re.sub(r"\s+", " ", t).strip()


#: 看起來像檔名的字串（電視不顯示檔名，契約 §D 的公開／私人界線）。
_FILENAME_RE = re.compile(r"[\w\-\u4e00-\u9fff]+\.(?:md|txt|json|csv|html?|py|js|ts|pdf|png|jpe?g|docx?|xlsx?)\b",
                          re.I)


def looks_like_filename(text: str, known_names: Iterable[str] = ()) -> bool:
    """這句話裡有沒有檔名：副檔名樣式，或這一跑 agent 自己寫過的檔（全名、或主檔名 ≥4 字）。

    電視事件流不帶檔名（契約 §A／§D），而 agent 的話（尤其收尾那句「我交出了 X.md」）
    常會自己講出檔名——**整句不發**（不改寫、不補罐頭句，與 LEAK 規則同一條紀律）。
    """
    if _FILENAME_RE.search(text):
        return True
    for n in known_names:
        if not isinstance(n, str) or not n:
            continue
        stem = n.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if n in text or (len(stem) >= 4 and stem in text):
            return True
    return False


def say_row(text: str, *, turn: int, seq: int, cell_id: str, run_id: str,
            ts_ms: int | None = None) -> dict | None:
    """一句已過防呆的話 → 一筆 `twin_say`。`text` 先 `clean_say`；清完空了回 `None`
    （空白、純標記、純程式碼區塊不發）。超過 `SAY_MAX` 截斷並 `truncated: true`。"""
    t = clean_say(text)
    if not t:
        return None
    trunc = len(t) > SAY_MAX
    if trunc:
        t = t[:SAY_MAX]
    return {
        "schema": SCHEMA, "type": "twin_say",
        "ts_ms": int(ts_ms if ts_ms is not None else time.time() * 1000),
        "cell_id": cell_id, "run_id": run_id, "seq": int(seq), "turn": int(turn),
        "text": t, "truncated": trunc,
    }


def append(path: str | os.PathLike, row: dict) -> str | None:
    """追加一行。回 `None`＝寫進去了；否則回錯誤字串（**不丟例外**，誠實邊界 2）。"""
    try:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
        return None
    except (OSError, TypeError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"


def read(path: str | os.PathLike) -> list[dict]:
    """讀整個檔；不存在＝空清單。最後一行寫到一半不算（`lifecycle.read` 同一條規則）。"""
    p = pathlib.Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return out


def _is_nat(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _runs(lifecycle_events: Iterable[dict]) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for e in lifecycle_events:
        rid = e.get("run_id")
        if e.get("type") == "run_started":
            caller = e.get("caller") or {}
            runs[rid] = {"arm": e.get("arm"), "ended": False,
                         "started_ms": e.get("ts_ms"),
                         "cell_id": caller.get("cell_id") or e.get("task_id")}
        elif e.get("type") == "run_ended" and rid in runs:
            runs[rid].update(ended=True, ended_ms=e.get("ts_ms"),
                             ws_end=e.get("ws_end_sha256"),
                             infra_void=e.get("infra_void"))
    return runs


def _fortune_problems(r: dict, i: int) -> list[str]:
    """`twin_fortune` 的形狀：全是枚舉；`lines` 只在 card 拍、≤3 句、每句 ≤60 字、不是檔名。"""
    bad: list[str] = []
    if r.get("phase") not in FORTUNE_PHASES:
        bad.append(f"旁註第 {i} 筆：twin_fortune 的 phase 不在白名單：{r.get('phase')!r}")
    if not (_is_nat(r.get("attempt")) and r["attempt"] >= 1):
        bad.append(f"旁註第 {i} 筆：twin_fortune 的 attempt 要是 ≥ 1 的整數")
    for key, allowed in (("mbti", FORTUNE_MBTI), ("mbti_source", FORTUNE_SOURCES), ("zodiac", FORTUNE_ZODIACS),
                         ("element", FORTUNE_ELEMENTS), ("blood", FORTUNE_BLOODS)):
        v = r.get(key)
        if v is not None and v not in allowed:
            bad.append(f"旁註第 {i} 筆：twin_fortune 的 {key} 不在白名單：{v!r}")
    if (r.get("zodiac") is None) != (r.get("element") is None):
        bad.append(f"旁註第 {i} 筆：twin_fortune 的 zodiac 與 element 要同時有或同時沒有")
    if (r.get("mbti") is None) != (r.get("mbti_source") is None):
        bad.append(f"旁註第 {i} 筆：twin_fortune 的 mbti 與 mbti_source 要同時有或同時沒有")
    ls = r.get("lines")
    if not isinstance(ls, list) or len(ls) > FORTUNE_MAX_LINES:
        bad.append(f"旁註第 {i} 筆：twin_fortune 的 lines 要是 ≤ {FORTUNE_MAX_LINES} 句的清單")
    else:
        if r.get("phase") == "way" and ls:
            bad.append(f"旁註第 {i} 筆：twin_fortune 的 way 拍不帶 lines")
        for s in ls:
            if not isinstance(s, str) or not s.strip() or len(s) > FORTUNE_LINE_MAX:
                bad.append(f"旁註第 {i} 筆：twin_fortune 的 lines 每句要是非空字串、≤ {FORTUNE_LINE_MAX} 字")
            elif looks_like_filename(s):
                bad.append(f"旁註第 {i} 筆：twin_fortune 的 lines 帶了像檔名的字")
    return bad


def validate(rows: Iterable[dict], *,
             lifecycle_events: Iterable[dict] | None = None) -> list[str]:
    """旁註契約自檢（＋給了 lifecycle 就一併驗綁定）。回問題清單（空＝合格）。"""
    bad: list[str] = []
    runs = _runs(lifecycle_events) if lifecycle_events is not None else None
    seen: set[str] = set()
    for i, r in enumerate(rows, 1):
        for k in COMMON:
            if k not in r:
                bad.append(f"旁註第 {i} 筆缺共同欄位 {k}")
        if r.get("schema") != SCHEMA:
            bad.append(f"旁註第 {i} 筆 schema 是 {r.get('schema')!r}，不是 {SCHEMA}")
        t = r.get("type")
        if t not in FIELDS:
            bad.append(f"旁註第 {i} 筆 type 不在契約裡：{t!r}")
            continue
        for k in FIELDS[t]:
            if k not in r:
                bad.append(f"旁註第 {i} 筆（{t}）缺欄位 {k}")
        for k in CONTENT_KEYS:
            # `twin_say` 的 `text` 是**agent 自己生成、已過逐字抄錄防呆**的那句話
            # （契約補充 §E）——這一個欄位是它的本體，其餘內容欄位照擋。
            if k in r and not (t == "twin_say" and k == "text"):
                bad.append(f"旁註第 {i} 筆夾帶了內容欄位 {k}")
        if not _is_nat(r.get("ts_ms")):
            bad.append(f"旁註第 {i} 筆 ts_ms 不是非負整數")
        if t == "postaudit":
            # ── 事後稽核不准長得像裁決：三個旗標缺一不可 ──────────────
            if r.get("is_verdict") is not False:
                bad.append(f"旁註第 {i} 筆：postaudit 的 is_verdict 必須是 false")
            if r.get("signed") is not False:
                bad.append(f"旁註第 {i} 筆：postaudit 的 signed 必須是 false")
            if r.get("when") != WHEN_AFTER:
                bad.append(f"旁註第 {i} 筆：postaudit 沒說它是事後量的"
                           f"（when 必須是 {WHEN_AFTER!r}）")
            if r.get("arm") != "OFF":
                bad.append(f"旁註第 {i} 筆：postaudit 只量 OFF 臂（ON 臂有自己的閘門）")
            if not isinstance(r.get("all_pass"), bool):
                bad.append(f"旁註第 {i} 筆：all_pass 只能是 true／false")
            p, n = r.get("passed"), r.get("total")
            if not (_is_nat(p) and _is_nat(n) and p <= n):
                bad.append(f"旁註第 {i} 筆：passed／total 要是 0 ≤ passed ≤ total 的整數")
            elif r.get("all_pass") is True and p != n:
                bad.append(f"旁註第 {i} 筆：all_pass=true 卻只過了 {p}/{n}")
            rid = r.get("run_id")
            if rid in seen:
                bad.append(f"旁註第 {i} 筆：同一跑 {rid} 有兩筆 postaudit")
            seen.add(rid)
            if runs is None:
                continue
            # ── 綁定：這一筆量的是錄影裡的哪一跑 ─────────────────────
            run = runs.get(rid)
            if run is None:
                bad.append(f"旁註第 {i} 筆：run_id {rid} 不在這份錄影裡")
                continue
            if run["arm"] != LC_ARM_OFF:
                bad.append(f"旁註第 {i} 筆：run_id {rid} 是 {run['arm']}，不是 OFF 臂")
            if not run["ended"]:
                bad.append(f"旁註第 {i} 筆：那一跑在錄影裡沒有 run_ended")
                continue
            if run.get("infra_void"):
                bad.append(f"旁註第 {i} 筆：那一跑 infra_void（沒跑成），不該有事後稽核")
            if r.get("ws_end_sha256") != run.get("ws_end"):
                bad.append(f"旁註第 {i} 筆：ws_end_sha256 與那一跑的 run_ended 不同"
                           "（量的不是那一棵樹）")
            if r.get("cell_id") != run["cell_id"]:
                bad.append(f"旁註第 {i} 筆：cell_id {r.get('cell_id')!r} 與那一跑的格子"
                           f" {run['cell_id']!r} 不同")
            if _is_nat(r.get("ts_ms")) and _is_nat(run.get("ended_ms")) \
                    and r["ts_ms"] < run["ended_ms"]:
                bad.append(f"旁註第 {i} 筆：ts_ms 早於那一跑的 run_ended——"
                           "「事後」在資料上不成立")
        elif t == "twin_fortune":
            bad.extend(_fortune_problems(r, i))
            if runs is None:
                continue
            run = runs.get(r.get("run_id"))
            if run is None:
                bad.append(f"旁註第 {i} 筆：run_id {r.get('run_id')!r} 不在這份錄影裡")
                continue
            if run["arm"] != LC_ARM_ON:
                bad.append(f"旁註第 {i} 筆：run_id {r.get('run_id')} 是 {run['arm']}，不是 ON 臂")
            if r.get("cell_id") != run["cell_id"]:
                bad.append(f"旁註第 {i} 筆：cell_id {r.get('cell_id')!r} 與那一跑的格子"
                           f" {run['cell_id']!r} 不同")
        elif t == "twin_gate":
            if not (_is_nat(r.get("attempt")) and r["attempt"] >= 1):
                bad.append(f"旁註第 {i} 筆：twin_gate 的 attempt 要是 ≥ 1 的整數")
            if not isinstance(r.get("passed"), bool):
                bad.append(f"旁註第 {i} 筆：twin_gate 的 passed 只能是 true／false")
            if "cut" in r and r["cut"] is not True:
                bad.append(f"旁註第 {i} 筆：twin_gate 的 cut 只能是 true（沒被切掉就不要帶）")
            ck = r.get("checks")
            if not isinstance(ck, list) or not ck:
                bad.append(f"旁註第 {i} 筆：twin_gate 的 checks 要是非空清單")
            else:
                for j, c in enumerate(ck, 1):
                    if not isinstance(c, dict) or set(c) - set(GATE_CHECK_KEYS):
                        bad.append(f"旁註第 {i} 筆：twin_gate.checks 第 {j} 條有不准的欄位")
                        continue
                    if not (isinstance(c.get("id"), str) and c["id"]
                            and isinstance(c.get("ok"), bool)
                            and isinstance(c.get("label"), str) and c["label"].strip()):
                        bad.append(f"旁註第 {i} 筆：twin_gate.checks 第 {j} 條的 id／ok／label 形狀不對")
                if (all(isinstance(c, dict) and isinstance(c.get("ok"), bool) for c in ck)
                        and isinstance(r.get("passed"), bool)
                        and r["passed"] != all(c["ok"] for c in ck)):
                    bad.append(f"旁註第 {i} 筆：twin_gate.passed 與 checks 的逐條結果對不上")
            if runs is None:
                continue
            run = runs.get(r.get("run_id"))
            if run is None:
                bad.append(f"旁註第 {i} 筆：run_id {r.get('run_id')!r} 不在這份錄影裡")
                continue
            if run["arm"] != LC_ARM_ON:
                bad.append(f"旁註第 {i} 筆：run_id {r.get('run_id')} 是 {run['arm']}，"
                           "不是 ON 臂——分身的閘門只在 ON 臂")
            if r.get("cell_id") != run["cell_id"]:
                bad.append(f"旁註第 {i} 筆：cell_id {r.get('cell_id')!r} 與那一跑的格子"
                           f" {run['cell_id']!r} 不同")
        elif t in ("twin_step", "twin_say"):
            if t == "twin_step":
                # ── 分身工作區三個工具被呼叫的旁註：形狀＋白名單 ─────────────
                if r.get("step") not in STEP_KINDS:
                    bad.append(f"旁註第 {i} 筆：twin_step 的 step 不在白名單："
                               f"{r.get('step')!r}")
                if r.get("path_kind") not in PATH_KINDS:
                    bad.append(f"旁註第 {i} 筆：twin_step 的 path_kind 不在白名單："
                               f"{r.get('path_kind')!r}")
                if not isinstance(r.get("ok"), bool):
                    bad.append(f"旁註第 {i} 筆：twin_step 的 ok 只能是 true／false")
                bv = r.get("bytes")
                if bv is not None and not _is_nat(bv):
                    bad.append(f"旁註第 {i} 筆：twin_step 的 bytes 要是非負整數或 null")
            else:
                # ── 分身自己說的話：80 字上限、截斷旗標要誠實 ────────────────
                tx = r.get("text")
                if not isinstance(tx, str) or not tx.strip():
                    bad.append(f"旁註第 {i} 筆：twin_say 的 text 要是非空字串")
                elif len(tx) > SAY_MAX:
                    bad.append(f"旁註第 {i} 筆：twin_say 的 text 超過 {SAY_MAX} 字")
                if not isinstance(r.get("truncated"), bool):
                    bad.append(f"旁註第 {i} 筆：twin_say 的 truncated 只能是 true／false")
                elif r["truncated"] and isinstance(tx, str) and len(tx) != SAY_MAX:
                    bad.append(f"旁註第 {i} 筆：twin_say 說被截斷了，長度卻不是 {SAY_MAX}")
                if not _is_nat(r.get("turn")):
                    bad.append(f"旁註第 {i} 筆：twin_say 的 turn 要是非負整數")
            if not _is_nat(r.get("seq")):
                bad.append(f"旁註第 {i} 筆：{t} 的 seq 要是非負整數")
            if runs is None:
                continue
            # ── 綁定：這一步是這一跑（ON 臂）做的 ─────────────────────
            run = runs.get(r.get("run_id"))
            if run is None:
                bad.append(f"旁註第 {i} 筆：run_id {r.get('run_id')!r} 不在這份錄影裡")
                continue
            if run["arm"] != LC_ARM_ON:
                bad.append(f"旁註第 {i} 筆：run_id {r.get('run_id')} 是 {run['arm']}，"
                           "不是 ON 臂——分身的步驟只在 ON 臂發生")
            if r.get("cell_id") != run["cell_id"]:
                bad.append(f"旁註第 {i} 筆：cell_id {r.get('cell_id')!r} 與那一跑的格子"
                           f" {run['cell_id']!r} 不同")
            if _is_nat(r.get("ts_ms")) and _is_nat(run.get("started_ms")) \
                    and r["ts_ms"] < run["started_ms"]:
                bad.append(f"旁註第 {i} 筆：ts_ms 早於那一跑的 run_started——"
                           "這一步不可能發生在那一跑開始之前")
    return bad


def merge(lifecycle_events: list[dict], rows: list[dict]) -> list[dict]:
    """lifecycle ＋ 旁註 → 一條給 `Folder` 吃的串流。

    兩種旁註兩種插法（**只加不改**：`postaudit` 的插法逐位元組不動）：

    · `postaudit` 插在**它綁的那一跑的 `run_ended` 之後**（不是照 `ts_ms` 重排：
      重排可能動到 lifecycle 自己的順序；`postaudit` 的 `ts_ms` 本來就恆晚於
      `run_ended`，見 `validate` 的綁定規則）。
    · `twin_step` 發生在那一跑**進行中**（`ts_ms` 介於 `run_started`／`run_ended`
      之間），所以插在同一跑**依 `ts_ms` 排序後、第一個 `ts_ms` 不早於它的
      lifecycle 事件之前**——這樣重播時「讀了特質」「寫了計畫」會出現在
      `working`／`verdict` 之間，不是像 `postaudit` 那樣全部堆在收尾之後。
      理論上這一跑最晚也會在 `run_ended` 那一步之前把剩下的全部沖掉（同一跑
      的 lifecycle 事件用完了）。

    綁不上的旁註接在最後——`Folder` 會因為找不到那一跑而不發事件（不猜）。
    呼叫端應該先 `validate`。
    """
    after_end: dict[str, list[dict]] = {}
    live: dict[str, list[dict]] = {}
    for r in rows:
        bucket = live if r.get("type") in ("twin_step", "twin_say", "twin_gate", "twin_fortune") else after_end
        bucket.setdefault(r.get("run_id"), []).append(r)
    for lst in live.values():
        lst.sort(key=lambda r: r.get("ts_ms", 0))
    out: list[dict] = []
    for e in lifecycle_events:
        rid = e.get("run_id")
        pending = live.get(rid)
        if pending:
            ets = e.get("ts_ms", 0)
            while pending and pending[0].get("ts_ms", 0) <= ets:
                out.append(pending.pop(0))
        out.append(e)
        if e.get("type") == "run_ended":
            out.extend(live.pop(rid, []))          # 保底：理論上不會剩東西
            out.extend(after_end.pop(rid, []))      # 舊行為：postaudit 接在後面
    for rest in list(live.values()) + list(after_end.values()):
        out.extend(rest)
    return out
