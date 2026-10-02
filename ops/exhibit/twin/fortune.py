"""twin/fortune — 命盤（MBTI／星座／血型）：只決定「做事的方式」，不決定題目；命盤卡每一句要有步驟根據。

## 這支在架構裡承重什麼

裁決：`decisions/DECISION_20261002_TWIN_FORTUNE.md`（P10 線 F）。人類原話：「如果我給了你我的人格，但是我最後產出的過程跟結果
無法讓人覺得『啊這就是我』，這樣就沒用。人喜歡迷信，只要能做到類似於通靈出來的過程跟結果都是『啊這就是我』的話，那就很好。」

⚠ **這是占卜遊戲，不是心理學事實。** 畫面與裁決都要這樣寫；這裡的對照表是遊戲規則（為了讓每一跑的劇本不一樣），
不是在說 MBTI／星座／血型真的能預測什麼。

這一支（只用標準函式庫，可以單獨複製進沙箱）做四件事：

1. **資料契約**：卡上的三個枚舉（`mbti`／`mbti_source`／`zodiac`／`blood`）收斂；**星座與血型沒給就不猜**
   （不能從特質推出來，猜了是編）；MBTI 沒給才由分身在段 1 的信裡猜（`mbti_source = "twin"`）。
2. **信的命盤段**：段 1 的分身在信末寫一段「命盤」（`parse_letter`）；`render_section` 把它重寫成確定的格式
   （標頭那幾行由這裡寫、分身只提供每行那一句，且那一句要過 LEAK／時段詞／「沒給的東西不准提」三道防呆）。
3. **做事的方式**（`way_text`）：命盤 → 拼進段 2 系統提示的「你做事的方式」一段。**確定性的對照表**（`fortune_text.py`
   的常數＋這裡的組合規則），措辭由 opencode 起草、領班審；**不給任何任務例子**。命盤只改過程（先去哪、讀的順序、怎麼收尾、
   被退回時怎麼重來），不改題目。
4. **命盤卡**（`build_card`，第二版：**確定性生成，不經模型，段 2 不再要求分身寫任何命盤卡**）：命盤一行（`INFP · 雙魚（水）· O 型`）；
   一句解讀（從信的命盤段挑，優先 J/P、T/F，已過現實詞／LEAK 過濾）；它走過的路（由步驟紀錄生成：去過的地點依序、
   最後寫成品時待的地點、成品標題、被退回幾次）；它做的事（主要成品的標題）。第一版「你是 X，所以我 Y」那套要模型寫、再逐句檢查的做法
   把模型逼成同一套句子，已移除（git 歷史裡有）。

## 誠實邊界（改碼請保留）

* 「它走過的路」每一個字都有步驟紀錄：地點＝成功的 `ws_read`／`ws_list`；「交出」的地點＝最後寫成品之前最近碰到的地點；
  被退回次數＝嘗試數 − 1。它不判斷那一步做得好不好。
* 「解讀」是模型在信裡寫的占卜句，這裡只挑、不改寫（≤40 字截到句讀）；它**不是**步驟根據，是占卜。
* 星座與血型沒給就不猜、不寫、不進命盤卡的解讀與標題（`mentions_ungiven` 擋）。
* 命盤與命盤卡是觀眾資料的衍生物：撤回時跟 run-dir 一起刪（`fortune_in.json`／`fortune_final.json`／`fortune_card.json`），
  進檔案庫的 `twin.fortune` 跟 `decision` 同一條規矩（`twinvault.TWIN_OFF_CHAIN_KEYS`）；鏈上沒有。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

try:                                   # 套件內 import；當腳本跑（`python3 fortune.py way <run>`）時退到同目錄
    from ops.exhibit.twin import fortune_text as T
except ImportError:                    # pragma: no cover - 單檔執行
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import fortune_text as T          # type: ignore[no-redef]

MBTI_TYPES = ("INFP", "INFJ", "INTP", "INTJ", "ISFP", "ISFJ", "ISTP", "ISTJ",
              "ENFP", "ENFJ", "ENTP", "ENTJ", "ESFP", "ESFJ", "ESTP", "ESTJ")
ZODIACS = ("牡羊", "金牛", "雙子", "巨蟹", "獅子", "處女", "天秤", "天蠍", "射手", "摩羯", "水瓶", "雙魚")
ELEMENT_OF = {"牡羊": "火", "獅子": "火", "射手": "火",
              "金牛": "土", "處女": "土", "摩羯": "土",
              "雙子": "風", "天秤": "風", "水瓶": "風",
              "巨蟹": "水", "天蠍": "水", "雙魚": "水"}
BLOODS = ("A", "B", "O", "AB")
#: `mbti_source`：卡片上只有 ai／self；分身自己猜的標 twin（只出現在這一跑的結果裡）。
MBTI_SOURCES = ("ai", "self", "twin")
PLACES = ("投遞口", "捏土處", "長桌廣場", "石頭閘門", "帳本鏈", "草稿角", "紙卡地", "畫架與長椅")
#: 地點的口語寫法 → 正名（命盤卡句子裡可能這樣寫）。
PLACE_ALIASES = {"長桌": "長桌廣場", "廣場": "長桌廣場", "土堆": "長桌廣場", "畫架": "畫架與長椅",
                 "長椅": "畫架與長椅", "閘門": "石頭閘門"}

LETTER_FILE = "信.md"
CARD_FILE = "命盤卡.md"
PLAN_FILE = "PLAN.md"
GROUND_PREFIX = "地上/"
IN_NAME = "fortune_in.json"
FINAL_NAME = "fortune_final.json"
CARD_JSON_NAME = "fortune_card.json"
STEP_LOG_NAME = "twin_steps.ndjson"        # 與 twinagent.STEP_LOG_NAME 同值（測試釘住）
MAX_SENTENCE = 40                           # 信的命盤段每一行那一句的字數上限
MAX_TITLE = 20                              # 命盤卡「它做的事」標題字數上限
MAX_CARD_LINES = 3                          # 命盤卡「你是 X，所以我 Y」最多幾句
MAX_CARD_LINE_CHARS = 60                    # 與雲端 `MAX_FORTUNE_LINE_CHARS` 同值（測試釘住）
LEAK_WINDOW = 8                             # 與 `twin_letter_guard.LEAK_WINDOW` 同值

#: 時段詞（與 `twin_letter_guard.TIME_WORDS` 同值，測試釘住；這支要能單獨執行所以不 import 它）。
TIME_WORDS = ("清晨", "凌晨", "深夜", "半夜", "夜裡", "夜晚", "夜間", "早晨", "早上", "傍晚", "黃昏",
              "中午", "午後", "晚上", "週末", "假日", "星期", "每天", "每週", "每個月", "每年", "年底", "春天",
              "夏天", "秋天", "冬天")


# ---------------------------------------------------------------------------
# 1. 資料契約
# ---------------------------------------------------------------------------

def _enum(v: Any, allowed: tuple[str, ...]) -> str | None:
    return v if isinstance(v, str) and v in allowed else None


def normalize(card: Any) -> dict[str, Any]:
    """卡 → `{mbti, mbti_source, zodiac, blood}`。不認得的值＝None；mbti 為 None 時 mbti_source 也是 None。"""
    c = card if isinstance(card, dict) else {}
    mbti = _enum(c.get("mbti"), MBTI_TYPES)
    src = _enum(c.get("mbti_source"), ("ai", "self"))
    return {"mbti": mbti, "mbti_source": (src or "ai") if mbti else None,
            "zodiac": _enum(c.get("zodiac"), ZODIACS), "blood": _enum(c.get("blood"), BLOODS)}


def element(zodiac: str | None) -> str | None:
    return ELEMENT_OF.get(zodiac) if zodiac else None


def has_any(f: dict[str, Any]) -> bool:
    return bool(f.get("mbti") or f.get("zodiac") or f.get("blood"))


def traits_lines(f: dict[str, Any]) -> list[str]:
    """TRAITS.md 裡的命盤三行（給段 1 的分身讀）。沒給的明講「沒給」並叫它不要猜（MBTI 例外：請它猜）。"""
    if f.get("mbti"):
        who = "觀眾自己選的" if f.get("mbti_source") == "self" else "觀眾的 AI 說的"
        m = f"- MBTI：{f['mbti']}（{who}）"
    else:
        m = "- MBTI：沒有給（請你依特質猜一個 16 型，並在信的命盤段寫一句根據）"
    z = f"- 星座：{f['zodiac']}" if f.get("zodiac") else "- 星座：沒有給（不要猜，也不要在信裡提星座）"
    b = f"- 血型：{f['blood']}" if f.get("blood") else "- 血型：沒有給（不要猜，也不要在信裡提血型）"
    return [m, z, b]


def first_line(f: dict[str, Any]) -> str:
    """命盤卡第一行與拍立得上的那一行：`INFP · 雙魚（水）· O 型`（沒給的就不寫）。"""
    parts: list[str] = []
    if f.get("mbti"):
        parts.append(f["mbti"])
    if f.get("zodiac"):
        parts.append(f"{f['zodiac']}（{element(f['zodiac'])}）")
    if f.get("blood"):
        parts.append(f"{f['blood']} 型")
    return " · ".join(parts).replace("） · ", "）· ")    # 計畫的寫法：`INFP · 雙魚（水）· O 型`


# ---------------------------------------------------------------------------
# 2. 信的命盤段
# ---------------------------------------------------------------------------

_HEAD = re.compile(r"^[\s#>*_\-]*命盤[\s*_:：]*$")
_KEY = re.compile(r"^[\s#>*_\-]*(MBTI|依據|E\s*[/／]\s*I|S\s*[/／]\s*N|T\s*[/／]\s*F|J\s*[/／]\s*P|星座|血型)"
                  r"[\s*_]*[：:]\s*(.*)$", re.I)
_PAIR_KEYS = {"E/I": "EI", "S/N": "SN", "T/F": "TF", "J/P": "JP"}


def _key_of(raw: str) -> str:
    k = re.sub(r"\s+", "", raw).replace("／", "/").upper()
    return {"MBTI": "mbti", "依據": "basis", "星座": "zodiac", "血型": "blood"}.get(k) or _PAIR_KEYS.get(k, k)


def parse_letter(text: str) -> tuple[str, dict[str, str]]:
    """信全文 → （命盤段之前的本文, {鍵: 內容}）。鍵：mbti／basis／EI／SN／TF／JP／zodiac／blood。
    找不到「命盤」標題行 ⇒ 整份都是本文、段是空的。"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if _HEAD.match(ln):
            body = "\n".join(lines[:i]).strip()
            sec: dict[str, str] = {}
            for ln2 in lines[i + 1:]:
                m = _KEY.match(ln2)
                if m:
                    sec.setdefault(_key_of(m.group(1)), m.group(2).strip())
            return body, sec
    return text.strip(), {}


def guess_mbti(sec: dict[str, str]) -> str | None:
    """命盤段 `MBTI：` 那一行裡的四個字母（恰好是 16 型之一；前後不能是英文字母）。"""
    v = sec.get("mbti") or ""
    for run in re.findall(r"[A-Za-z]+", v.replace("Ｉ", "I")):
        if len(run) == 4 and run.upper() in MBTI_TYPES:
            return run.upper()
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def shares_window(sentence: str, source: str, window: int = LEAK_WINDOW) -> bool:
    a, b = _norm(sentence), _norm(source)
    if len(a) < window:
        return False
    return any(a[i:i + window] in b for i in range(len(a) - window + 1))


def mentions_ungiven(sentence: str, f: dict[str, Any]) -> bool:
    """句子提到了「沒給」的東西（或與給的不一樣）？——星座血型沒給不准猜，也不准寫。"""
    for z in ZODIACS:
        if z in sentence and z != f.get("zodiac"):
            return True
    if f.get("zodiac") is None and re.search(r"星座|[火土風水]象", sentence):
        return True
    if f.get("blood") is None and re.search(r"血型|(?<![A-Za-z])(AB|A|B|O)\s*型", sentence):
        return True
    if f.get("blood") and re.search(r"(?<![A-Za-z])(AB|A|B|O)\s*型", sentence):
        m = re.search(r"(?<![A-Za-z])(AB|A|B|O)\s*型", sentence)
        if m and m.group(1) != f["blood"]:
            return True
    for run in re.findall(r"(?<![A-Za-z])[A-Za-z]{4}(?![A-Za-z])", sentence):
        if run.upper() in MBTI_TYPES and run.upper() != (f.get("mbti") or ""):
            return True
    return False


#: 把觀眾現實關係帶進來的詞（窄名單，不是完備的現實偵測）：命盤段的句子、命盤卡的句子與標題碰到就整句拿掉。
REALITY_WORDS = ("伴侶", "家人", "家庭", "父母", "爸", "媽", "老公", "老婆", "配偶", "男友", "女友", "戀人", "情人",
                 "孩子", "小孩", "兒子", "女兒", "親人", "朋友", "同事", "老闆", "主管", "客戶", "上司",
                 "工作", "職場", "公司", "上班", "下班", "學校", "學生", "老師", "同學", "論文", "考試", "課業",
                 "寵物", "貓", "狗", "手機", "網路")


def mentions_reality(sentence: str) -> bool:
    return any(w in sentence for w in REALITY_WORDS)


def clean_sentence(raw: str, traits: str, f: dict[str, Any]) -> tuple[str | None, str | None]:
    """命盤段每一行那一句 → （乾淨的句子, 被拿掉的理由）。理由：empty／leak／time／ungiven。"""
    s = " ".join(str(raw or "").replace("*", "").split()).strip("　 ")
    if not s:
        return None, "empty"
    if shares_window(s, traits):
        return None, "leak"
    if any(w in s for w in TIME_WORDS):
        return None, "time"
    if mentions_ungiven(s, f):
        return None, "ungiven"
    if mentions_reality(s):
        return None, "reality"
    if len(s) > MAX_SENTENCE:
        cut = max((s.rfind(p, 0, MAX_SENTENCE) for p in "，。；！？,;"), default=-1)
        s = s[:cut] if cut >= 12 else s[:MAX_SENTENCE]
    return s.rstrip("，、；,;"), None


def resolve(given: dict[str, Any], sec: dict[str, str]) -> dict[str, Any]:
    """觀眾給的（`fortune_in.json`）＋信裡猜的 MBTI → 這一跑用的命盤。**給了就以給的為準**；沒給才收分身猜的。"""
    f = {"mbti": given.get("mbti"), "mbti_source": given.get("mbti_source"),
         "zodiac": given.get("zodiac"), "blood": given.get("blood"), "mbti_guessed": False}
    if not f["mbti"]:
        g = guess_mbti(sec)
        if g:
            f["mbti"], f["mbti_source"], f["mbti_guessed"] = g, "twin", True
    f["element"] = element(f["zodiac"])
    return f


_MBTI_NOTE = {"ai": "你的 AI 這麼說", "self": "你自己選的"}


def render_section(f: dict[str, Any], sec: dict[str, str], traits: str) -> tuple[str, dict[str, Any]]:
    """確定性地重寫命盤段。標頭行（MBTI／星座／血型）由這裡寫；分身只提供每行那一句，過防呆。
    回（段落全文, 計數＋被拿掉的理由）。沒有任何可寫的行 ⇒ 空字串。"""
    dropped: list[dict[str, str]] = []
    out: list[str] = []

    def sent(key: str) -> str | None:
        s, why = clean_sentence(sec.get(key, ""), traits, f)
        if why and why != "empty":
            dropped.append({"key": key, "why": why})
        return s

    if f.get("mbti"):
        if f.get("mbti_guessed"):
            basis = sent("basis")
            out.append(f"MBTI：我猜你是 {f['mbti']}" + (f"。依據：{basis}" if basis else ""))
        else:
            out.append(f"MBTI：你是 {f['mbti']}（{_MBTI_NOTE.get(f.get('mbti_source') or 'ai', '你的 AI 這麼說')}）")
        for k, label in (("EI", "E/I"), ("SN", "S/N"), ("TF", "T/F"), ("JP", "J/P")):
            s = sent(k)
            if s:
                out.append(f"{label}：{s}")
    if f.get("zodiac"):
        s = sent("zodiac")
        out.append(f"星座：{f['zodiac']}（{f['element']}象）" + (f"。{s}" if s else ""))
    if f.get("blood"):
        s = sent("blood")
        out.append(f"血型：{f['blood']} 型" + (f"。{s}" if s else ""))
    text = ("命盤\n" + "\n".join(out)) if out else ""
    return text, {"lines": len(out), "dropped": dropped}


# ---------------------------------------------------------------------------
# 3. 做事的方式（拼進段 2 的系統提示）
# ---------------------------------------------------------------------------

def way_lines(f: dict[str, Any]) -> list[str]:
    """命盤 → 「做事的方式」的條目（確定性）。沒有任何命盤 ⇒ 空 list（段 2 的系統提示與沒有命盤時逐位元相同）。"""
    out: list[str] = []
    m = f.get("mbti")
    if m:
        out.append(T.WAY_EI[m[0]])
        out.append(T.FIRST_STOPS[m[0] + m[1]])
        out.append(T.WAY_SN[m[1]])
        out.append(T.WAY_TF[m[2]])
        out.append(T.WAY_JP[m[3]])
    if f.get("zodiac"):
        out.append(T.WAY_ELEMENT[element(f["zodiac"])])
    if f.get("blood"):
        out.append(T.WAY_BLOOD[f["blood"]])
    if m:
        out.append(T.RETRY_JP[m[3]])
    return out


def reminder(f: dict[str, Any]) -> str:
    """（第二版起命盤卡由程式生成，段 2 不再有任何關於命盤卡的要求。）恆為空字串；保留給舊呼叫端。"""
    return ""


def way_text(f: dict[str, Any]) -> str:
    """接在段 2 系統提示後面的整段。沒有命盤 ⇒ ''。"""
    ls = way_lines(f)
    if not ls:
        return ""
    return "\n\n" + T.WAY_INTRO + "\n" + "\n".join(f"- {x}" for x in ls)


# ---------------------------------------------------------------------------
# 4. 命盤卡：每一句要有步驟根據
# ---------------------------------------------------------------------------

def read_steps(rd: pathlib.Path) -> list[dict[str, Any]]:
    p = pathlib.Path(rd) / STEP_LOG_NAME
    rows: list[dict[str, Any]] = []
    try:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                break
            if isinstance(r, dict):
                rows.append(r)
    except OSError:
        return []
    rows.sort(key=lambda r: (r.get("ts_ms") or 0, r.get("seq") or 0))
    return rows


def stage2_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """段 2 的步驟（第一次成功讀 信.md 之後）。段 1 讀的是 TRAITS.md、寫的是信，不算在世界裡做的事。"""
    for i, r in enumerate(rows):
        if r.get("tool") == "ws_read" and r.get("path") == LETTER_FILE:
            return rows[i:]
    return rows


def _place_of(path: Any) -> str | None:
    p = str(path or "").lstrip("./")
    if not p.startswith(GROUND_PREFIX):
        return None
    head = p[len(GROUND_PREFIX):].split("/", 1)[0]
    return head if head in PLACES else None


def visited_places(rows: list[dict[str, Any]]) -> list[str]:
    """段 2 去過的地點（依第一次成功 ws_read／ws_list 地上/<地點>/… 的順序，不重複）。"""
    seen: list[str] = []
    for r in stage2_rows(rows):
        if r.get("ok") is True and r.get("tool") in ("ws_read", "ws_list"):
            pl = _place_of(r.get("path"))
            if pl and pl not in seen:
                seen.append(pl)
    return seen


def _top_files(ws: pathlib.Path) -> dict[str, str]:
    """工作區最上層的檔（不含 PLAN／信／命盤卡／TRAITS／WORLD）→ 全文。"""
    out: dict[str, str] = {}
    skip = {PLAN_FILE, LETTER_FILE, CARD_FILE, "TRAITS.md", "WORLD.md", "VACANT_FEEDBACK.md"}
    try:
        for p in sorted(pathlib.Path(ws).iterdir()):
            if p.is_file() and not p.is_symlink() and p.name not in skip and p.suffix.lower() in (".md", ".txt"):
                try:
                    out[p.name] = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
    except OSError:
        pass
    return out


class Evidence:
    """一跑的步驟證據（只看紀錄與最後的工作區，不看句子寫得好不好）。"""

    def __init__(self, rows: list[dict[str, Any]], ws: pathlib.Path | None,
                 ground_files: list[str] | None = None) -> None:
        self.all = rows
        self.rows = stage2_rows(rows)
        # 先後證據：地點＝第一次成功 ws_read／ws_list 地上/<地點>/…；東西＝第一次成功 ws_read 那個檔
        self.place_first: dict[str, int] = {}
        self.file_first: dict[str, int] = {}
        for i, r in enumerate(self.rows):
            if r.get("ok") is not True or r.get("tool") not in ("ws_read", "ws_list"):
                continue
            pl = _place_of(r.get("path"))
            if pl:
                self.place_first.setdefault(pl, i)
            if r.get("tool") == "ws_read" and str(r.get("path") or "").startswith(GROUND_PREFIX):
                self.file_first.setdefault(str(r["path"]), i)
        self.ground_files = sorted(set(ground_files or []) | set(self.file_first))
        self.places = set(visited_places(rows))
        self.files = _top_files(ws) if ws else {}
        ok = [r for r in self.rows if r.get("ok") is True]
        self.plan_writes = [i for i, r in enumerate(self.rows)
                            if r.get("tool") == "ws_write" and r.get("path") == PLAN_FILE and r.get("ok") is True]
        self.ground_reads = [i for i, r in enumerate(self.rows)
                             if r.get("tool") == "ws_read" and r.get("ok") is True and _place_of(r.get("path"))]
        self.writes = [i for i, r in enumerate(self.rows) if r.get("tool") == "ws_write" and r.get("ok") is True]
        self.n_ok = len(ok)

    # 動作詞的判準（每個回 (有沒有, 說明)）
    def a_plan(self) -> bool:
        return bool(self.plan_writes)

    def a_browse_first(self) -> bool:                # 先走過地上、之後才寫計畫
        return bool(self.plan_writes and self.ground_reads and self.ground_reads[0] < self.plan_writes[0])

    def a_plan_first(self) -> bool:                  # 先寫計畫、之後才打開地上的東西
        return bool(self.plan_writes and (not self.ground_reads or self.plan_writes[0] < self.ground_reads[0])
                    and self.ground_reads)

    def a_recheck(self) -> bool:                     # 最後一次寫成品之後，又列過房間或讀過檔
        art_writes = [i for i in self.writes
                      if self.rows[i].get("path") not in (PLAN_FILE, LETTER_FILE, CARD_FILE)]
        if not art_writes:
            return False
        last = art_writes[-1]
        return any(r.get("ok") is True and r.get("tool") in ("ws_list", "ws_read")
                   for r in self.rows[last + 1:])

    def a_changed_mind(self) -> bool:                # PLAN.md 寫過兩次以上
        return len(self.plan_writes) >= 2

    def a_two_versions(self) -> bool:                # 兩個檔，內文各有「版本一」「版本二」
        has1 = any("版本一" in t for t in self.files.values())
        has2 = any("版本二" in t for t in self.files.values())
        return has1 and has2 and len(self.files) >= 2

    def a_left_for(self) -> bool:                    # 成品裡寫明留給誰（內文有「留給」，或檔名就是「給…」）
        return any(("留給" in t) or n.startswith("給") for n, t in self.files.items())

    def a_kept(self) -> bool:                        # 成品裡寫明收在哪裡
        return any(("收在" in t or "收好" in t or "保管" in t) for t in self.files.values())

    def a_small_note(self) -> bool:                  # 多寫了一個很短的檔
        return len(self.files) >= 3 or any(len(t) <= 120 and "留給" in t for t in self.files.values())

    def has(self, kind: str, token: str) -> bool:
        if kind == "place":
            return token in self.places
        return getattr(self, "a_" + token)()


#: 命盤卡的標題不准自己說閘門給了什麼結果（收據只有閘門給；與 `grounding_gate` 窗 4 同一條精神）。
RECEIPT_CLAIM = re.compile(
    r"(?:獲得|拿到|領到|換到|收到|取得)了?(?:一張)?收據|通過了?(?:閘門|檢查|驗收)|過了閘門|過閘|閘門(?:通過|放行|亮)|亮燈|綠光")
#: ⚠ 「收據」本身是世界裡的東西（帳本鏈上有收據片、投遞口有收據卡），提到它不算；只擋「說閘門給了我結果」的句型。


NO_NAME_TITLE = "一件沒有名字的小事"
READING_ORDER = ("JP", "TF", "EI", "SN")        # 解讀優先挑 J/P、T/F 那一行；沒有就挑第一個存在的行


MIN_TITLE = 3
#: 居民的外形名（世界裡居民互相這樣叫：顏色＋形狀，如「苔綠細長」「赭紅方」「奶油圓」）。
_RESIDENT_NAME = re.compile(r"^(?:暖土|赭紅|沙金|苔綠|奶油|灰藍)色?(?:圓|方|小|細長|厚實|粗獷|大)?(?:的?居民|的?人)?$")
_ADDRESS = re.compile(r"^[ \t]*([^\s：:，,。#>*\-]{2,8})[：:]", re.M)
_NOT_ADDRESS = {"命盤", "MBTI", "星座", "血型", "開頭", "E/I", "S/N", "T/F", "J/P", "依據"}


def is_resident_name(t: str, letter_text: str = "") -> bool:
    """標題是不是居民的稱呼：外形名（顏色＋形狀）、或信裡拿來稱呼對方的那個詞（行首「X：」）。"""
    t = (t or "").strip()
    if _RESIDENT_NAME.match(t):
        return True
    return bool(t) and t in {m for m in _ADDRESS.findall(letter_text or "")} - _NOT_ADDRESS


def title_of(files: dict[str, str], f: dict[str, Any], traits: str = "", letter_text: str = "") -> str | None:
    """這一跑主要成品（最長的頂層 .md／.txt）的標題＝第一個非空行，≤20 字；像檔名、抄觀眾原文、提沒給的東西、現實詞、時段詞 ⇒ 試下一個，都不行 ⇒ None。"""
    for text in sorted(files.values(), key=len, reverse=True):
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        t = re.sub(r"^[\s#>*\-_\d.、：:【\[（(]+", "", first).strip()
        t = t.strip("「」『』\"'*】]）)").rstrip("。.！!：:，,").strip()
        if not t or len(t) > MAX_TITLE or re.fullmatch(r"版本[一二]", t):
            continue
        if len(t) < MIN_TITLE or is_resident_name(t, letter_text):     # P12：太短、或只是居民的稱呼 ⇒ 不當標題（換「一件沒有名字的小事」）
            continue
        if re.search(r"\.(md|txt)\b|[A-Za-z0-9_]+\.[a-z]{2,4}", t) or "/" in t:
            continue
        if (any(w in t for w in TIME_WORDS) or mentions_reality(t) or mentions_ungiven(t, f)
                or RECEIPT_CLAIM.search(t) or (traits and shares_window(t, traits))):
            continue
        return t
    return None


def main_title(ws: pathlib.Path | None, f: dict[str, Any], traits: str = "") -> str | None:
    return title_of(_top_files(ws) if ws else {}, f, traits)


def reading_of(letter_text: str, f: dict[str, Any], traits: str = "") -> str | None:
    """一句解讀：從信的命盤段挑一句（優先 J/P、T/F，其次 E/I、S/N；都沒有就挑第一個存在的行）。
    重新過一次現實詞／LEAK／時段詞／沒給的東西（`clean_sentence`，≤40 字截到句讀）。**不經模型**。"""
    _body, sec = parse_letter(letter_text or "")
    keys = [k for k in READING_ORDER if sec.get(k)] + [k for k in sec if k not in READING_ORDER and k not in ("mbti", "basis", "zodiac", "blood") and sec.get(k)]
    for k in keys:
        sent, _why = clean_sentence(sec[k], traits, f)
        if sent:
            return sent
    return None


def route_of(places: list[str], last_place: str | None, title: str, retries: int) -> str:
    """它走過的路（確定性，每一個字都有紀錄）：它先去了A，再到B……，在C交出《標題》；被退回過就加「中途被退回 N 次，改了 N 次」。
    地點取成功讀取／列出的地上地點、依首次出現順序、去重、最多 4 個；整句 ≤ `MAX_CARD_LINE_CHARS`（太長先少一個地點、再截標題）。"""
    ps = list(dict.fromkeys(places))[:4]
    tail = f"；中途被退回 {retries} 次，改了 {retries} 次" if retries > 0 else ""

    def make(pp: list[str], t: str) -> str:
        if not pp:
            head = "它"
        elif len(pp) == 1 and last_place in (None, pp[0]):
            return f"它在{pp[0]}交出《{t}》{tail}"          # 只去過一個地方：「它在X交出」，不說「去了X，在X交出」
        elif len(pp) == 1:
            head = f"它去了{pp[0]}"
        else:
            head = f"它先去了{pp[0]}" + "".join(f"，再到{x}" for x in pp[1:])
        where = f"在{last_place}" if last_place else ""
        return f"{head}，{where}交出《{t}》{tail}" if pp else f"{head}{where}交出《{t}》{tail}"

    t = title
    while len(make(ps, t)) > MAX_CARD_LINE_CHARS and len(ps) > 1:
        ps = ps[:-1]
    while len(make(ps, t)) > MAX_CARD_LINE_CHARS and len(t) > 4:
        t = t[:-2] + "…" if not t.endswith("…") else t[:-2] + "…"
    return make(ps, t)


def last_place_before_delivery(rows: list[dict[str, Any]]) -> str | None:
    """交件前最後寫成品時待的地點：最後一次寫頂層成品（不是 PLAN／信／TRAITS）之前，最近一次成功碰到的地上地點。"""
    rows = stage2_rows(rows)
    lw = None
    for i, r in enumerate(rows):
        if (r.get("tool") == "ws_write" and r.get("ok") is True and not _place_of(r.get("path"))
                and r.get("path") not in (PLAN_FILE, LETTER_FILE, CARD_FILE)):
            lw = i
    if lw is None:
        return None
    for r in reversed(rows[:lw]):
        if r.get("ok") is True and r.get("tool") in ("ws_read", "ws_list") and _place_of(r.get("path")):
            return _place_of(r.get("path"))
    return None


def compose_card(f: dict[str, Any], *, letter_text: str, rows: list[dict[str, Any]], files: dict[str, str],
                 retries: int, traits: str = "") -> dict[str, Any]:
    """命盤卡第二版（確定性，不經模型）：命盤一行＋一句解讀＋它走過的路＋它做的事。`lines`＝[解讀, 路線]（缺解讀就只有路線）。"""
    res: dict[str, Any] = {"first_line": first_line(f), "lines": [], "dropped": [], "present": False, "card_file": False}
    if not has_any(f):
        return res
    title = title_of(files, f, traits, letter_text)
    res["title"] = title
    reading = reading_of(letter_text, f, traits)
    places = visited_places(rows)
    last = last_place_before_delivery(rows)
    res["places"] = places
    res["reading"] = reading
    if places:
        res["route"] = route_of(places, last, title or NO_NAME_TITLE, retries)
    res["lines"] = [x for x in (reading, res.get("route")) if x]
    res["present"] = bool(res["lines"])
    return res


def attempts_retries(rd: pathlib.Path) -> int:
    """這一跑被閘門退回、重改過幾次＝嘗試數 − 1（`run_RUN-ON.json`）。讀不到 ⇒ 0。"""
    try:
        runj = json.loads((pathlib.Path(rd) / "run_RUN-ON.json").read_text(encoding="utf-8"))
        return max(0, len(runj.get("attempts", [])) - 1)
    except (OSError, ValueError, TypeError):
        return 0


def build_card(rd: pathlib.Path, ws: pathlib.Path | None, f: dict[str, Any], traits: str = "") -> dict[str, Any]:
    """從 run-dir（步驟紀錄、`letter_final.md`、`run_RUN-ON.json`）與最後的工作區（成品標題）生成命盤卡。**不讀分身寫的任何命盤卡。**"""
    rd = pathlib.Path(rd)
    try:
        letter = (rd / "letter_final.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        letter = ""
    res = compose_card(f, letter_text=letter, rows=read_steps(rd), files=_top_files(pathlib.Path(ws)) if ws else {},
                       retries=attempts_retries(rd), traits=traits)
    if has_any(f):
        try:
            (rd / CARD_JSON_NAME).write_text(json.dumps(res, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass
    return res


def polaroid_sentence(line: str) -> str:
    """拍立得那一行用的短句＝命盤卡的「解讀」那一句（`lines[0]`）；拿掉句尾標點。"""
    return str(line or "").rstrip("。.！!")


def card_md(card: dict[str, Any]) -> str:
    """命盤卡全文：命盤一行、解讀、它走過的路、它做的事（≤ 6 行）。"""
    ls = [card.get("first_line") or ""] + list(card.get("lines") or [])
    ls.append("它做的事：" + (card.get("title") or NO_NAME_TITLE))
    return "\n".join(x for x in ls if x) + "\n"


# ---------------------------------------------------------------------------
# 進出口（run-dir 檔案；撤回時跟 run-dir 一起刪）
# ---------------------------------------------------------------------------

def load_final(rd: pathlib.Path) -> dict[str, Any] | None:
    try:
        d = json.loads((pathlib.Path(rd) / FINAL_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return d if isinstance(d, dict) else None


def twin_view(f: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    """進 `twin.fortune` 的東西（檔案庫、撤回會刪）＋ publish 給雲端用的欄位。"""
    # ⚠ 不放 element（單字「水」「火」…）：進檔案庫的字串會被收成「不准上鏈的祕密」，單字會誤中別的字；
    #   元素由 zodiac 推得出來（`element()`）。
    return {"mbti": f.get("mbti"), "mbti_source": f.get("mbti_source"), "zodiac": f.get("zodiac"),
            "blood": f.get("blood"), "first_line": card.get("first_line"), "title": card.get("title"),
            "lines": list(card.get("lines") or [])}


def emit(rd: pathlib.Path, phase: str, f: dict[str, Any], lines: list[str] | None = None) -> bool:
    """寫一筆旁註 `twin_fortune`（`twin.sidecar/1`；全是枚舉）。旁註位置與 run_id 從 `gate_meta.json` 與事件檔學來
    （與 `grounding_gate.prepare` 寫 `twin_gate` 同一條路）。任何一步缺了就不寫、不丟例外（旁註不准改變一跑）。"""
    import time
    try:
        try:
            from ops.exhibit.twin import grounding_gate as gg
        except ImportError:            # pragma: no cover - 單檔執行
            import grounding_gate as gg   # type: ignore[no-redef]
        meta = json.loads((pathlib.Path(rd) / gg.GATE_META_NAME).read_text(encoding="utf-8"))
        if not (meta.get("events_path") and meta.get("sidecar_path")):
            return False
        rid, attempt = gg._learn_run(meta["events_path"], meta["task_id"])
        if not rid or attempt < 1:
            return False
        row = {"schema": "twin.sidecar/1", "type": "twin_fortune", "ts_ms": int(time.time() * 1000),
               "cell_id": meta["cell_id"], "run_id": rid, "phase": phase, "attempt": attempt,
               "mbti": f.get("mbti"), "mbti_source": f.get("mbti_source"),
               "zodiac": f.get("zodiac"), "element": element(f.get("zodiac")), "blood": f.get("blood"),
               "lines": list(lines or [])}
        sp = pathlib.Path(meta["sidecar_path"])
        sp.parent.mkdir(parents=True, exist_ok=True)
        with sp.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception:                                  # noqa: BLE001
        return False


def _cli(argv: list[str]) -> int:
    """`way <run_dir>`：印段 2 系統提示尾端那一段（沒有命盤＝空）。`msg <run_dir>`：印段 2 第一句尾端的提醒（沒有命盤＝空）。`announce <run_dir>`：段 1 結束、命盤定下來時發 way 旁註。
    `card <工作區> <run_dir>`：每次嘗試結束時對步驟紀錄檢查命盤卡、發 card 旁註（pi 已死、凍結還沒開始）。"""
    if len(argv) == 3 and argv[1] == "way":
        f = load_final(pathlib.Path(argv[2]))
        sys.stdout.write(way_text(f) if f else "")
        return 0
    if len(argv) == 3 and argv[1] == "msg":
        f = load_final(pathlib.Path(argv[2]))
        sys.stdout.write(reminder(f) if f else "")
        return 0
    if len(argv) == 3 and argv[1] == "announce":
        f = load_final(pathlib.Path(argv[2]))
        if f and has_any(f):
            emit(pathlib.Path(argv[2]), "way", f)
        return 0
    if len(argv) == 4 and argv[1] == "card":
        rd, ws = pathlib.Path(argv[3]), pathlib.Path(argv[2])
        f = load_final(rd)
        if f and has_any(f):
            try:
                card = build_card(rd, ws, f, traits_hint(rd))
                emit(rd, "card", f, card["lines"])
            except Exception as exc:                   # noqa: BLE001
                print(f"fortune card 失敗：{type(exc).__name__}", file=sys.stderr)
        return 0
    print("用法：fortune.py way|announce <run_dir>｜card <工作區> <run_dir>", file=sys.stderr)
    return 2


def traits_hint(rd: pathlib.Path) -> str:
    """命盤卡的逐字抄錄（LEAK）比對要用的觀眾特質全文：段 1 結束後 TRAITS.md 已移出房間，
    `twin_letter_guard` 在 run-dir（工作區外）留一份 `traits_ref.txt`（撤回時跟 run-dir 一起刪）。
    ⚠ 比對的是**觀眾原文**，不是信：卡句的 X 本來就是從信讀來的性情，不算抄錄。"""
    try:
        return (pathlib.Path(rd) / "traits_ref.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
