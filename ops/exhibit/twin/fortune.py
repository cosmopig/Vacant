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
4. **命盤卡**（`build_card`）：分身寫 `命盤卡.md`（≤ 6 行）；第一行命盤由這裡決定性寫出（`INFP · 雙魚（水）· O 型`），
   接著至多 3 句「你是 X，所以我 Y」。**Y 必須是這一跑真的發生過的步驟**：每一句提到的地點／動作都要在步驟紀錄裡找得到，
   找不到就從卡上拿掉那一句（這就是 Vacant 的「每一步有沒有根據」用在命盤卡上）；一句都沒有可檢查的字也拿掉
   （量不到不是通過）。

## 誠實邊界（改碼請保留）

* 命盤卡的檢查是**字面的步驟紀錄比對**：句子說「我先去了草稿角」，檢查的是紀錄裡有沒有成功讀過／列過 `地上/草稿角/…`；
  不判斷那一步做得好不好，也不判斷「你是 X」那半句對不對（那是占卜）。
* 動作詞表（`ACTIONS`）是窄名單：句子裡沒有任何表內的字（地點或動作）＝ 無法檢查 ＝ 拿掉。
* 星座與血型沒給就不猜、不寫、不進命盤卡的任何一句（`mentions_ungiven` 擋）。
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

CARD_RULES = (
    "停下之前，一定要先寫好「命盤卡.md」（直接放在你房間最上層）；沒有這個檔，就還沒有做完。"
    "請把「命盤卡.md 已經寫好」也寫進 PLAN.md 的「做完的樣子」。"
    "裡面只寫三句，每句一行，格式固定是「你是X，所以我Y」。"
    "X 只能是他的命盤本身：他的某個字母、他星座的元素，或他的血型，不要改寫成別的形容。"
    "Y 要是這一跑你真的做過的事：要點名你真的去過的一個地點，和你真的打開讀過的地上一件東西（用它在世界裡的名字，不是檔名），"
    "並說你對那件東西做了什麼；有先後的話，照你真的做的先後寫成「先…才…」。"
    "沒做過的、沒打開過的，一個字都不要寫。"
)


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


#: 接在段 2 第一句（user 訊息）後面的提醒：系統提示裡的「停下之前要有命盤卡」gemma 常忘，user 訊息最後一句它比較聽。
CARD_REMINDER = "另外，停下之前要先把命盤卡.md 寫好（三句，格式照說明）。"


def reminder(f: dict[str, Any]) -> str:
    """沒有命盤 ⇒ ''（段 2 第一句與沒有這個功能時逐位元相同）。"""
    return ("\n" + CARD_REMINDER) if way_lines(f) else ""


def way_text(f: dict[str, Any]) -> str:
    """接在段 2 系統提示後面的整段（含命盤卡的規則）。沒有命盤 ⇒ ''。"""
    ls = way_lines(f)
    if not ls:
        return ""
    return "\n\n" + T.WAY_INTRO + "\n" + "\n".join(f"- {x}" for x in ls) + "\n\n" + CARD_RULES


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


#: 命盤卡句子裡的字 → 檢查名。窄名單（誠實邊界）；順序＝長的字在前，避免「先寫計畫」被「計畫」吃掉。
ACTIONS: tuple[tuple[str, str], ...] = (
    ("先寫了計畫", "plan_first"), ("先寫計畫", "plan_first"), ("先寫好計畫", "plan_first"),
    ("先走過地上", "browse_first"), ("先逛了地上", "browse_first"), ("先逛過地上", "browse_first"),
    ("先看過地上", "browse_first"), ("先逛", "browse_first"), ("先走了一圈", "browse_first"),
    ("改了主意", "changed_mind"), ("改主意", "changed_mind"),
    ("兩個版本", "two_versions"), ("兩版", "two_versions"),
    ("再看了一次房間", "recheck"), ("再看一次房間", "recheck"), ("再檢查了一次", "recheck"),
    ("再檢查一次", "recheck"), ("檢查了一遍", "recheck"), ("再讀了一遍", "recheck"),
    ("留給了", "left_for"), ("留給", "left_for"),
    ("收好了", "kept"), ("收在", "kept"), ("收好", "kept"), ("自己保管", "kept"),
    ("寫了計畫", "plan"), ("寫了 PLAN", "plan"),
)
_PLACE_TOKENS = tuple(sorted(list(PLACES) + list(PLACE_ALIASES), key=len, reverse=True))
#: 命盤卡不准自己說閘門給了什麼結果（收據只有閘門給；與 `grounding_gate` 窗 4 同一條精神）。
RECEIPT_CLAIM = re.compile(
    r"(?:獲得|拿到|領到|換到|收到|取得)了?(?:一張)?收據|通過了?(?:閘門|檢查|驗收)|過了閘門|過閘|閘門(?:通過|放行|亮)|亮燈|綠光")
#: ⚠ 「收據」本身是世界裡的東西（帳本鏈上有收據片、投遞口有收據卡），提到它不算；只擋「說閘門給了我結果」的句型。
_SHAPE = re.compile(r"^你.{1,30}?[，,]\s*所以我.{2,}$")


#: 材料名裡太籠統、不能當「點名東西」的字。
_GENERIC_PARTS = frozenset({"另一張", "現貼", "第四列", "完成", "進度", "紀錄"})


def object_names(rel: str) -> list[str]:
    """`地上/帳本鏈/尾段_418到447片.txt` → 世界裡的名字：檔名去副檔名（整個）＋以「_」切開、沒有數字、≥2 字的各段。不是檔名本身。"""
    stem = pathlib.PurePosixPath(rel).stem
    names = {stem}
    for part in stem.split("_"):
        if len(part) >= 2 and not re.search(r"\d", part) and part not in _GENERIC_PARTS:
            names.add(part)
    return sorted(names, key=len, reverse=True)


def objects_in(sentence: str, ground_files: list[str]) -> list[tuple[str, str]]:
    """句子點名了哪些地上的東西 → [(字面, 名字所屬的檔們用 '|' 連起來)]。長名字先配、配過就挖掉。"""
    table: dict[str, list[str]] = {}
    for rel in ground_files:
        for n in object_names(rel):
            table.setdefault(n, []).append(rel)
    out: list[tuple[str, str]] = []
    s = sentence
    for n in sorted(table, key=len, reverse=True):
        if n in s:
            out.append((n, "|".join(table[n])))
            s = s.replace(n, "〇" * len(n))
    return out


def tokens_in(sentence: str) -> list[tuple[str, str, str]]:
    """句子裡可檢查的**動作詞**（只當額外的順序／動作判準，不能單獨讓一句過關）。"""
    out: list[tuple[str, str, str]] = []
    s = sentence
    for w, kind in ACTIONS:
        if w in s:
            out.append(("action", w, kind))
            s = s.replace(w, "〇" * len(w))
    return out


def places_in(sentence: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    s = sentence
    for p in _PLACE_TOKENS:
        if p in s:
            out.append((p, PLACE_ALIASES.get(p, p)))
            s = s.replace(p, "〇" * len(p))
    return out


_X_PIECE_SPLIT = re.compile(r"[、,，和及＋+/／的\s]|又|也|而且")


def x_valid(x: str, f: dict[str, Any]) -> bool:
    """X 半句必須是命盤本身：他的字母（單個或四個）、星座的元素（或星座名）、血型。每一段都要是，且是「給了的」那些。"""
    for w in ("的人", "星座", "元素", "血型", "型", "座", "血", "象"):       # 「雙子星座」「B型血」「水象元素」都是命盤本身的說法
        x = x.replace(w, "")
    pieces = [p for p in _X_PIECE_SPLIT.split(x.strip()) if p]
    if not pieces:
        return False
    m = f.get("mbti") or ""
    for p in pieces:
        p2 = p.strip()
        ok = False
        if m and (p2.upper() == m or (len(p2) == 1 and p2.upper() in m)):
            ok = True
        elif p2.upper() in ("E", "I", "S", "N", "T", "F", "J", "P") and not m:
            ok = False
        elif f.get("zodiac") and (p2.rstrip("象") == element(f["zodiac"]) or p2 == f["zodiac"]):
            ok = True
        elif f.get("blood") and p2.upper() == f["blood"]:
            ok = True
        if not ok:
            return False
    return True


_ORDER = re.compile(r"先(.+?)(?:才|再|然後|之後才|後才)(.+)")
_SHAPE2 = re.compile(r"^你是(.{1,24}?)[，,]\s*所以我(.+)$")


def check_sentence(sentence: str, ev: Evidence, f: dict[str, Any], traits: str = "") -> tuple[bool, str]:
    """一句命盤卡「你是X，所以我Y」→ （保留嗎, 理由）。

    X 必須是命盤本身（`x_valid`）。Y 至少點名一個地點或一件地上的東西，點名的地點要有成功讀取／列出、東西要這一跑真的被 ws_read 過；
    「先…才…」的先後要與步驟紀錄一致。另擋：自稱收據／通過、逐字抄觀眾原文、提到沒給的星座血型、現實關係詞、時段詞。
    理由：ok／shape／filename／x_not_chart／too_long／time／ungiven／reality／receipt_claim／leak／no_checkable／ungrounded:<字>／order_mismatch。
    """
    s = " ".join(str(sentence or "").replace("*", "").split())
    s = re.sub(r"^[\-\d.、\s]+", "", s)
    m = _SHAPE2.match(s)
    if not m:
        return False, "shape"
    if len(s) > MAX_CARD_LINE_CHARS:
        return False, "too_long"
    if any(w in s for w in TIME_WORDS):
        return False, "time"
    if mentions_ungiven(s.replace(f.get("mbti") or "~~", ""), f):
        return False, "ungiven"
    if re.search(r"\.(?:md|txt)\b|[A-Za-z0-9]_|_[A-Za-z0-9\u4e00-\u9fff]|/", s):
        return False, "filename"                      # 世界內的名字，不是檔名
    if mentions_reality(s):
        return False, "reality"
    if RECEIPT_CLAIM.search(s):
        return False, "receipt_claim"
    if traits and shares_window(s, traits):
        return False, "leak"
    if not x_valid(m.group(1), f):
        return False, "x_not_chart"
    y = m.group(2)
    objs, plcs = objects_in(y, ev.ground_files), places_in(y)
    if not objs and not plcs:
        return False, "no_checkable"
    for lit, name in plcs:
        if name not in ev.place_first:
            return False, f"ungrounded:{lit}"
    for lit, files in objs:
        if not any(fl in ev.file_first for fl in files.split("|")):
            return False, f"ungrounded:{lit}"
    for kind, lit, name in tokens_in(y):
        if not ev.has(kind, name):
            return False, f"ungrounded:{lit}"

    def first_of(part: str) -> int | None:
        idx = [ev.place_first[n] for _l, n in places_in(part) if n in ev.place_first]
        for _l, files in objects_in(part, ev.ground_files):
            idx += [ev.file_first[fl] for fl in files.split("|") if fl in ev.file_first]
        return min(idx) if idx else None

    om = _ORDER.search(y)
    if om:
        a, b = first_of(om.group(1)), first_of(om.group(2))
        if a is not None and b is not None and a >= b:
            return False, "order_mismatch"
    return True, "ok"


def main_title(ws: pathlib.Path | None, f: dict[str, Any], traits: str = "") -> str | None:
    """這一跑主要成品（最長的那個頂層 .md／.txt）的標題＝第一個非空行，≤20 字；像檔名、抄觀眾原文、提沒給的東西、現實詞、時段詞 ⇒ None。"""
    files = _top_files(ws) if ws else {}
    for text in sorted(files.values(), key=len, reverse=True):          # 最長的成品先試；標題不合格就試下一個
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        t = re.sub(r"^[\s#>*\-_\d.、：:【\[（(]+", "", first).strip()
        t = t.strip("「」『』\"'*】]）)").rstrip("。.！!：:，,").strip()
        if not t or len(t) > MAX_TITLE or re.fullmatch(r"版本[一二]", t):
            continue
        if re.search(r"\.(md|txt)\b|[A-Za-z0-9_]+\.[a-z]{2,4}", t) or "/" in t:
            continue
        if (any(w in t for w in TIME_WORDS) or mentions_reality(t) or mentions_ungiven(t, f)
                or RECEIPT_CLAIM.search(t) or (traits and shares_window(t, traits))):
            continue
        return t
    return None


def build_card(rd: pathlib.Path, ws: pathlib.Path | None, f: dict[str, Any],
               traits: str = "") -> dict[str, Any]:
    """讀工作區的 `命盤卡.md`、逐句對步驟紀錄 → `{first_line, lines, kept, dropped[{text,why}], present}`。

    第一行（命盤）永遠由 `first_line(f)` 決定性寫出，不信分身寫的那一行。沒有任何命盤 ⇒ 不出卡（`present:False`）。
    `lines` 是通過檢查的「你是 X，所以我 Y」（至多 `MAX_CARD_LINES`）。
    """
    res: dict[str, Any] = {"first_line": first_line(f), "lines": [], "dropped": [], "present": False,
                           "card_file": False}
    if not has_any(f):
        return res
    gdir = pathlib.Path(rd) / "stage2_in" / "地上"
    gfiles = ([GROUND_PREFIX + p.relative_to(gdir).as_posix() for p in sorted(gdir.rglob("*")) if p.is_file()]
              if gdir.is_dir() else [])
    ev = Evidence(read_steps(rd), pathlib.Path(ws) if ws else None, gfiles)
    res["title"] = main_title(pathlib.Path(ws) if ws else None, f, traits)
    raw = ""
    if ws and (pathlib.Path(ws) / CARD_FILE).is_file():
        try:
            raw = (pathlib.Path(ws) / CARD_FILE).read_text(encoding="utf-8", errors="replace")
            res["card_file"] = True
        except OSError:
            raw = ""
    cand = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for ln in cand:
        if "所以我" not in ln:
            continue                             # 第一行（命盤）與別的雜行不是句子
        ok, why = check_sentence(ln, ev, f, traits)
        if ok and len(res["lines"]) < MAX_CARD_LINES:
            res["lines"].append(" ".join(ln.replace("*", "").split()))
        elif ok:
            res["dropped"].append({"text": ln, "why": "over_limit"})
        else:
            res["dropped"].append({"text": ln, "why": why})
    res["present"] = bool(res["lines"])
    res["places"] = visited_places(ev.all)
    try:
        (pathlib.Path(rd) / CARD_JSON_NAME).write_text(json.dumps(res, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
    return res


def polaroid_sentence(line: str) -> str:
    """命盤卡一句「你是X，所以我Y」→ 拍立得那一行用的短句「我Y」（窄帶放不下整句）。不是那個形狀就原樣回。"""
    s = str(line or "")
    return ("我" + s.split("所以我", 1)[1]).rstrip("。") if "所以我" in s else s


def card_md(card: dict[str, Any]) -> str:
    """通過檢查的命盤卡全文（≤ 6 行）。"""
    ls = [card.get("first_line") or ""]
    if card.get("title"):
        ls.append("它做的事：" + card["title"])
    ls += list(card.get("lines") or [])
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
