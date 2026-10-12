"""twin/fortune — 命盤（MBTI／星座／血型）：只決定「做事的方式」，不決定題目；命盤卡每一句要有步驟根據。

## 這支在架構裡承重什麼

裁決：`decisions/DECISION_20261002_TWIN_FORTUNE.md`（P10 線 F）。人類原話：「如果我給了你我的人格，但是我最後產出的過程跟結果
無法讓人覺得『啊這就是我』，這樣就沒用。人喜歡迷信，只要能做到類似於通靈出來的過程跟結果都是『啊這就是我』的話，那就很好。」

**P13（2026-10-07，`decisions/DECISION_20261007_TWIN_DIVINE.md`）**：命盤是 **AI 的判決**（手機上不能改）——`mbti_source`
只剩 `ai`／`twin`；信的命盤段多一行「想試」（他心裡一直想試、卻還沒試的事，已被分身抽象化）；命盤卡改成四行
「你的數位分身其實是…／它心裡一直想試的是…／它試了…／試完它說…」（`compose_card_v3`）。

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

import hashlib
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
MBTI_SOURCES = ("ai", "twin")
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
MAX_WANT_LETTER = 60                        # 信的命盤段「想試」那一句的字數上限（抽象化過的）
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
    # P13：命盤是 AI 的判決，觀眾改不了——沒有「self」這條路；舊卡帶 self 一律當 ai。
    return {"mbti": mbti, "mbti_source": "ai" if mbti else None,
            "zodiac": _enum(c.get("zodiac"), ZODIACS), "blood": _enum(c.get("blood"), BLOODS)}


def element(zodiac: str | None) -> str | None:
    return ELEMENT_OF.get(zodiac) if zodiac else None


def has_any(f: dict[str, Any]) -> bool:
    return bool(f.get("mbti") or f.get("zodiac") or f.get("blood"))


def traits_lines(f: dict[str, Any]) -> list[str]:
    """TRAITS.md 裡的命盤三行（給段 1 的分身讀）。沒給的明講「沒給」並叫它不要猜（MBTI 例外：請它猜）。"""
    if f.get("mbti"):
        who = "觀眾的 AI 替他占卜出來的"
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
_KEY = re.compile(r"^[\s#>*_\-]*(MBTI|依據|E\s*[/／]\s*I|S\s*[/／]\s*N|T\s*[/／]\s*F|J\s*[/／]\s*P|星座|血型|想試)"
                  r"[\s*_]*[：:]\s*(.*)$", re.I)
_PAIR_KEYS = {"E/I": "EI", "S/N": "SN", "T/F": "TF", "J/P": "JP"}


def _key_of(raw: str) -> str:
    k = re.sub(r"\s+", "", raw).replace("／", "/").upper()
    return {"MBTI": "mbti", "依據": "basis", "星座": "zodiac", "血型": "blood", "想試": "want"}.get(k) or _PAIR_KEYS.get(k, k)


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
                 "寵物", "貓", "狗", "手機", "網路",
                 # 第四輪：金錢／債務／職涯／關係事件（真跑 a7：感想「他想面對債務」上了卡）
                 "債務", "欠債", "欠款", "貸款", "房貸", "車貸", "借款", "卡債", "薪水", "薪資", "房租", "學費", "失業",
                 "離職", "辭職", "面試", "履歷", "前任", "前男友", "前女友", "分手", "離婚", "結婚", "求婚", "懷孕",
                 "住院", "醫院", "診所", "病歷", "憂鬱症", "焦慮症")


def mentions_reality(sentence: str) -> bool:
    return any(w in sentence for w in REALITY_WORDS)


def clean_sentence(raw: str, traits: str, f: dict[str, Any],
                   max_len: int = MAX_SENTENCE) -> tuple[str | None, str | None]:
    """命盤段每一行那一句 → （乾淨的句子, 被拿掉的理由）。理由：empty／leak／time／ungiven／reality。"""
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
    if len(s) > max_len:
        cut = max((s.rfind(p, 0, max_len) for p in "，。；！？,;"), default=-1)
        s = s[:cut] if cut >= 12 else s[:max_len]
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


_MBTI_NOTE = {"ai": "你的 AI 這麼說"}


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
    # P13：他心裡一直想試、卻還沒試的事（分身寫信時已抽象化一次；這裡再過一次防呆。沒有「想試」的鍵＝不寫）。
    if sec.get("want"):
        w, why = clean_sentence(sec["want"], traits, f, MAX_WANT_LETTER)
        if why and why != "empty":
            dropped.append({"key": "want", "why": why})
        if w:
            out.append(f"想試：{w}")
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
                r["_n"] = len(rows) + 1               # 「第 N 步」＝這一行在步驟紀錄檔裡的順位（收據頁與手機的過程清單用同一個編號）
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
        # 同一次嘗試裡 PLAN.md 寫了幾次（`seq` 回到 ≤ 前一筆＝下一次嘗試）。被閘門退回後重寫計畫是閘門逼的、不是「改主意」，
        # 所以「改主意」只數同一次嘗試之內的重寫（整合時用 divine 的 30 張真跑量到：不分嘗試會把 9 張裡的 7 張誤判）。
        self.plan_writes_per_attempt = max(self._per_attempt_plan_counts() or [0])

    def _per_attempt_plan_counts(self) -> list[int]:
        counts, cur, last = [], 0, None
        for r in self.rows:
            sq = r.get("seq")
            if isinstance(sq, int) and isinstance(last, int) and sq <= last:
                counts.append(cur)
                cur = 0
            if isinstance(sq, int):
                last = sq
            if r.get("tool") == "ws_write" and r.get("path") == PLAN_FILE and r.get("ok") is True:
                cur += 1
        counts.append(cur)
        return counts

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
                      if self.rows[i].get("path") not in (PLAN_FILE, LETTER_FILE, CARD_FILE, "試的紀錄.md")]
        if not art_writes:
            return False
        last = art_writes[-1]
        return any(r.get("ok") is True and r.get("tool") in ("ws_list", "ws_read")
                   for r in self.rows[last + 1:])

    def a_changed_mind(self) -> bool:                # 同一次嘗試裡 PLAN.md 寫過兩次以上
        return self.plan_writes_per_attempt >= 2

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


def _title_ok(t: str, f: dict[str, Any], traits: str, letter_text: str) -> bool:
    if not t or len(t) > MAX_TITLE or re.fullmatch(r"版本[一二]", t):
        return False
    if t.startswith(("這是我自己", "這是我做", "這是我捏", "這是我造")):      # P13：「這是我自己做的」是標記句，不是名字
        return False
    if len(t) < MIN_TITLE or is_resident_name(t, letter_text):     # P12：太短、或只是居民的稱呼 ⇒ 不當標題（換「一件沒有名字的小事」）
        return False
    if re.search(r"\.(md|txt)\b|[A-Za-z0-9_]+\.[a-z]{2,4}", t) or "/" in t:
        return False
    return not (any(w in t for w in TIME_WORDS) or mentions_reality(t) or mentions_ungiven(t, f)
                or RECEIPT_CLAIM.search(t) or (traits and shares_window(t, traits)))


#: 檔名當標題時不收的泛稱（它們不是「這樣東西的名字」）。
_GENERIC_STEMS = {"成品", "試的紀錄", "PLAN", "紀錄", "過程", "備註", "筆記"}


def title_of(files: dict[str, str], f: dict[str, Any], traits: str = "", letter_text: str = "") -> str | None:
    """這一跑主要成品（最長的頂層 .md／.txt）的標題＝第一個非空行，≤20 字；像檔名、抄觀眾原文、提沒給的東西、現實詞、時段詞 ⇒ 試下一個，都不行 ⇒ None。
    P13：第一行（多半是一整句描述）都不能當標題時，退一步用**檔名**（去掉副檔名；分身被指示用「這樣東西的名字」當檔名）——過同一把尺。"""
    for text in sorted(files.values(), key=len, reverse=True):
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        t = re.sub(r"^[\s#>*\-_\d.、：:【\[（(]+", "", first).strip()
        t = t.strip("「」『』\"'*】]）)").rstrip("。.！!：:，,").strip()
        if _title_ok(t, f, traits, letter_text):
            return t
    for name in sorted(files, key=lambda n: len(files[n]), reverse=True):
        stem = pathlib.PurePath(name).stem.strip()
        if stem not in _GENERIC_STEMS and _title_ok(stem, f, traits, letter_text):
            return stem
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


def route_of(places: list[str], last_place: str | None, title: str, retries: int,
             verb: str = "交出", limit: int = MAX_CARD_LINE_CHARS) -> str:
    """它走過的路（確定性，每一個字都有紀錄）：它先去了A，再到B……，在C交出《標題》；被退回過就加「中途被退回 N 次，改了 N 次」。
    地點取成功讀取／列出的地上地點、依首次出現順序、去重、最多 4 個；整句 ≤ `MAX_CARD_LINE_CHARS`（太長先少一個地點、再截標題）。"""
    ps = list(dict.fromkeys(places))[:4]
    tail = f"；中途被退回 {retries} 次，改了 {retries} 次" if retries > 0 else ""

    def make(pp: list[str], t: str) -> str:
        if not pp:
            head = "它"
        elif len(pp) == 1 and last_place in (None, pp[0]):
            return f"它在{pp[0]}{verb}《{t}》{tail}"          # 只去過一個地方：「它在X交出」，不說「去了X，在X交出」
        elif len(pp) == 1:
            head = f"它去了{pp[0]}"
        else:
            head = f"它先去了{pp[0]}" + "".join(f"，再到{x}" for x in pp[1:])
        where = f"在{last_place}" if last_place else ""
        return f"{head}，{where}{verb}《{t}》{tail}" if pp else f"{head}{where}{verb}《{t}》{tail}"

    t = title
    while len(make(ps, t)) > limit and len(ps) > 1:
        ps = ps[:-1]
    while len(make(ps, t)) > limit and len(t) > 4:
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


# ---------------------------------------------------------------------------
# 5. 像不像你（2026-10-12）：給觀眾的最後產出＝它在這裡**怎麼做事**，不是「你是什麼人」
# ---------------------------------------------------------------------------
# 人類 2026-10-12：「最後的產出如果是『你是什麼人』，這樣不對；而是『如果我在這個世界裡，我也會做這種事』、
# 『這根本是我』。不是 MBTI，是我在這邊做了什麼跟我本人很像。」過程（命盤決定走法、閘門、收據）不動。
#
# 所以命盤解讀句（「追求秩序的同時，內心仍有…」）與路線句（「它先去了投遞口，再到…」）都不再給觀眾看：
# 前者是貼標籤，後者是世界裡的故事。觀眾拿到的每一句都是**這一跑真的做過的一個做事習慣**，
# 用日常語言寫（不帶世界裡的地名、不帶命盤字樣、不帶「你是」），像不像由他自己認。
# 每一句都由 `Evidence` 的判準決定，模板句、不經模型；判準不成立的句子不會出現（不補、不編）。

MIRROR_HEAD = "像不像你？"
MAX_MIRROR_LINES = 3
MIRROR_MANY_READS = 5            # 打開過幾樣地上的東西以上算「翻了很多」
#: 習慣句的挑法見 `mirror_pick`（稀有度固定表＋同組只留一句）；每句尾端「（第 N 步）」指回步驟紀錄。


SYSTEM_FILES = (PLAN_FILE, LETTER_FILE, CARD_FILE, "試的紀錄.md", "TRAITS.md", "WORLD.md", "VACANT_FEEDBACK.md")


def _product_files(files: dict[str, str]) -> dict[str, str]:
    """「做出來的東西」＝工作區最上層扣掉系統檔（試的紀錄／PLAN／信…）。標題與習慣句的證據都只看這一份。"""
    return {n: t for n, t in (files or {}).items() if n not in SYSTEM_FILES}


#: 地點 → 那裡放的是哪一類東西（日常說法；卡上不出現世界裡的地名，只說「那一類東西」）。
PLACE_KIND = {"投遞口": "要寄出去的東西", "帳本鏈": "帳本和記錄", "捏土處": "捏到一半的小東西",
              "長桌廣場": "桌上擺著的雜物", "石頭閘門": "規則和關卡", "草稿角": "沒寫完的草稿",
              "紙卡地": "紙卡", "畫架與長椅": "畫和隨手放的東西"}

#: 每條習慣的稀有度（固定表，不用模型；越大越稀有、越優先）。依 divine 那 30 張真跑的出現率定：
#: 常見的（到處看一圈 14／30、回頭再看 14／30、做出了什麼 28／30）壓低，沒什麼人有的（改主意、寫完又讀自己的計畫…）抬高。
#: 表本身不依賴「這一批」的內容——展場是一張一張出卡，沒有「這一批」可以看；30 張是定表的依據。
RARITY = {
    "start_browse": 1.0, "start_look": 2.4, "start_plan": 1.3, "start_nothing": 4.0,
    "read_before_plan": 2.6, "many_reads": 3.6, "few_reads": 2.8, "first_touch": 1.9,
    "linger": 2.6, "failed_go_on": 2.6, "reread_plan": 4.5, "changed_mind": 6.0, "revise_product": 4.2,
    "several_made": 1.7, "short_made": 2.0, "long_made": 2.4, "plan_vs_made": 3.2,
    "reads_after_plan": 1.1, "many_kinds": 1.2, "recheck": 1.4, "recheck_first": 4.0, "two_versions": 6.0, "left_for": 6.0, "kept": 6.0,
    "retried_open": 2.6, "retried_source": 4.0, "retried": 1.6, "made": 0.35,
    "pace_slow": 3.0, "pace_fast": 1.5, "steps_few": 1.5, "steps_many": 2.8, "q_mark": 3.0, "hedge": 3.4, "digits": 2.4,
}
#: 同一組只留一句（兩句講的是同一件事就只放一句）。
MIRROR_GROUP = {
    "start_browse": "start", "start_look": "start", "start_plan": "start", "start_nothing": "start",
    "first_touch": "start", "read_before_plan": "reads", "many_reads": "reads", "few_reads": "reads",
    "linger": "reads", "failed_go_on": "failed", "reread_plan": "plan", "changed_mind": "plan",
    "revise_product": "revise", "several_made": "made_n", "short_made": "made_n", "long_made": "made_n",
    "plan_vs_made": "plan", "reads_after_plan": "afterplan", "many_kinds": "kinds", "recheck": "end", "recheck_first": "end", "two_versions": "made_n",
    "left_for": "note", "kept": "note", "retried_open": "retry", "retried_source": "retry",
    "retried": "retry", "made": "made",
    "pace_slow": "pace", "pace_fast": "pace", "steps_few": "pace", "steps_many": "pace",
    "q_mark": "voice", "hedge": "voice", "digits": "voice",
}
MIRROR_ORDER = tuple(RARITY)          # 相容舊名：所有習慣鍵
#: 節奏／步數兩類習慣（進來多久才寫計畫、全部用了幾步）反映模型延遲與步數、不是人的做事方式 ⇒ 不進候選（主線 10-13 裁定）；函式留著。
PACE_HABITS = False
PACE_SLOW_S = 40.0                    # 進來到寫下計畫隔這麼久（秒）以上算「想了一下」
PACE_FAST_S = 12.0
STEPS_FEW = 11                        # 全部步驟 ≤ 這個數算「很快就交」
STEPS_MANY = 30
SHORT_MADE_CHARS = 110                # 單一成品全文這個字數以下算「很短」
LONG_MADE_CHARS = 240                 # 這個字數以上算「寫得很細」
STEP_TAG_RE = re.compile(r"\s*（第 (\d+) 步）$")


def step_tag(n: int) -> str:
    return f"（第 {n} 步）"


def strip_step(line: str) -> str:
    """拿掉句尾的「（第 N 步）」（拍立得主字與電視字幕不帶步數）。"""
    return STEP_TAG_RE.sub("", str(line or "")).rstrip()


def step_of(line: str) -> int | None:
    m = STEP_TAG_RE.search(str(line or ""))
    return int(m.group(1)) if m else None


_STEP_TOOL_CODE = {"ws_read": "r", "ws_write": "w", "ws_list": "l"}
_STEP_SYSTEM_KIND = {PLAN_FILE: "計畫", LETTER_FILE: "那封信", "WORLD.md": "世界說明", "TRAITS.md": "特質",
                     "試的紀錄.md": "試的紀錄", CARD_FILE: "命盤卡"}


def public_steps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """收據副本的步驟清單（公開版，**不含檔名與內容**）：`{n, t, k, ok}`——n＝第幾步（步驟紀錄檔的順位，1 起算）、
    t＝r 讀／w 寫／l 列、k＝碰的是哪一類（地上哪一類東西／計畫／那封信／成品…）、ok＝成不成功。
    ⚠ 這份與「（第 N 步）」共用同一個編號；順序＝步驟紀錄檔的順序（不重排）。"""
    out = []
    for i, r in enumerate(rows):
        path = str(r.get("path") or "")
        pl = _place_of(path)
        if pl:
            kind = PLACE_KIND.get(pl, "地上的東西")
        elif path in _STEP_SYSTEM_KIND:
            kind = _STEP_SYSTEM_KIND[path]
        elif path.strip("./") == "":
            kind = "房間"
        else:
            kind = "成品"
        out.append({"n": int(r.get("_n") or (i + 1)), "t": _STEP_TOOL_CODE.get(r.get("tool"), "?"),
                    "k": kind, "ok": bool(r.get("ok"))})
    out.sort(key=lambda x: x["n"])
    return out


def steps_digest(steps: list[dict[str, Any]]) -> str:
    """步驟清單的 sha256（規範化：鍵排序、無空白、不跳脫中文；瀏覽器端用同一個序列化重算）。"""
    blob = json.dumps(steps, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _artifact_writes(ev: "Evidence") -> list[int]:
    return [i for i in ev.writes if ev.rows[i].get("path") not in SYSTEM_FILES]


def _attempt_index(rows: list[dict[str, Any]]) -> list[int]:
    """每一列屬於第幾次嘗試（`seq` 回到 ≤ 前一筆＝下一次嘗試；與 `Evidence._per_attempt_plan_counts` 同一個判準）。"""
    out, cur, last = [], 0, None
    for r in rows:
        sq = r.get("seq")
        if isinstance(sq, int) and isinstance(last, int) and sq <= last:
            cur += 1
        if isinstance(sq, int):
            last = sq
        out.append(cur)
    return out


#: 給觀眾看的句子＝**形容語句**（2026-10-13 人類：不要「前前後後翻了 23 樣東西」那種系統日誌，要像在形容一個人，但不寫「你是…」）。
#: 固定對照表、確定性、不經模型；每條習慣的判準與「（第 N 步）」不變，只換句子。`{k}`＝那一類東西（地上哪一類）。
#: `made`（最後做出來的是《…》）不是形容，只在沒有其他句子時當最後手段（`mirror_pick`）。
ADJ_TEXT: dict[str, str] = {
    "start_browse": "好奇，習慣先四處逛一圈再決定",
    "start_look": "謹慎，先看一眼才動手",
    "start_plan": "有條理，先想清楚再做",
    "start_nothing": "直覺派，想到就做",
    "read_before_plan": "做功課型，動筆前先蒐集很多",
    "first_touch": "對「{k}」特別有感",
    "many_reads": "好奇心重，什麼都想翻翻看",
    "few_reads": "果斷，不用看太多就能開始",
    "linger": "最常被「{k}」吸引",
    "reads_after_plan": "邊做邊找靈感，想到就回去翻",
    "many_kinds": "興趣廣，不會只盯著一處",
    "failed_go_on": "卡住不硬撞，會換條路",
    "reread_plan": "謹慎，寫完會回頭讀自己的計畫",
    "changed_mind": "願意推翻自己，邊做邊調整",
    "revise_product": "反覆琢磨，不滿意就再改一版",
    "two_versions": "拿不定主意時，乾脆兩個都做",
    "several_made": "一做就停不下來",
    "short_made": "簡潔，話不多但說到重點",
    "long_made": "講究細節，一寫就很仔細",
    "left_for": "做東西時心裡想著某個人",
    "kept": "有收拾的習慣，東西會放好",
    "q_mark": "喜歡留白，不把話說死",
    "hedge": "溫和，說話習慣留餘地",
    "digits": "務實，喜歡具體的數字",
    "plan_vs_made": "隨性，計畫歸計畫，做著做著就變了",
    "recheck_first": "念舊，做完還會回到起點看看",
    "recheck": "細心，交出去前會再確認一次",
    "retried_open": "被指出漏看了什麼，會回頭補上",
    "retried_source": "被問到出處，會回頭補上說明",
    "retried": "被指出問題會回頭補上",
}


def mirror_candidates(ev: "Evidence", retries: int, title: str | None, plan_text: str = "",
                      retry_ids: tuple[str, ...] = (), accepted: bool | None = None) -> list[dict[str, Any]]:
    """所有成立的習慣：`{key, text, step}`（`step`＝全部步驟裡的第幾步，1 起算）。判準不成立就不出現。"""
    out: list[dict[str, Any]] = []
    off = len(ev.all) - len(ev.rows)

    def add(key: str, text: str, i: int | None, k: str = "") -> None:
        if i is not None:
            if key in ADJ_TEXT:
                text = ADJ_TEXT[key].format(k=k)               # 形容語句（判準與步數不變，只換句子）
            out.append({"key": key, "text": text, "step": int(ev.rows[i].get("_n") or (off + i + 1))})

    arts = _artifact_writes(ev)
    # 2026-10-13 展前線上驗收：有一跑交了件、卡上卻 0 句（成品寫入沒被 _artifact_writes 認出）。
    # 改成：沒認出成品時，跟成品無關的習慣（怎麼開始、翻了什麼、被退回）照樣出——每句仍綁自己那一步的證據；
    # 跟成品有關的句子各自要 `arts` 才出（不補、不編）。
    if not arts and not ev.ground_reads and not ev.plan_writes:
        return out                            # 什麼都沒做 ⇒ 沒有習慣句可說
    att = _attempt_index(ev.rows)
    first_g = ev.ground_reads[0] if ev.ground_reads else None
    first_kind = PLACE_KIND.get(_place_of(ev.rows[first_g].get("path"))) if first_g is not None else None
    # ── 怎麼開始
    if ev.a_browse_first():
        seen = {p for p, i in ev.place_first.items() if i < ev.plan_writes[0]}
        if len(seen) >= 2:
            add("start_browse", "還沒決定要做什麼，先到處看了一圈", first_g)
        else:
            add("start_look", "先去看了一眼，才決定要做什麼", first_g)
        n_before = sum(1 for g in ev.ground_reads if g < ev.plan_writes[0])
        if n_before >= 4:
            add("read_before_plan", f"動筆寫計畫之前，已經翻過 {n_before} 次東西", ev.plan_writes[0])
    elif ev.a_plan_first():
        add("start_plan", "先把要做的事寫下來，才開始動手", ev.plan_writes[0])
    elif not ev.plan_writes and arts:
        add("start_nothing", "沒寫計畫，直接就動手做了", arts[0])
    if first_kind and first_g is not None:
        add("first_touch", "", first_g, k=first_kind)
    # ── 看東西
    n_read = len(ev.file_first)
    if n_read >= MIRROR_MANY_READS and ev.file_first:
        add("many_reads", f"前前後後翻了 {n_read} 樣東西", max(ev.file_first.values()))
    elif n_read <= 1 and arts:
        add("few_reads", "沒看幾樣東西，就動手了", arts[0])
    per_kind: dict[str, list[int]] = {}
    for g in ev.ground_reads:
        k = PLACE_KIND.get(_place_of(ev.rows[g].get("path")))
        if k:
            per_kind.setdefault(k, []).append(g)
    if per_kind:
        k, idxs = max(per_kind.items(), key=lambda kv: (len(kv[1]), -kv[1][0]))
        if len(idxs) >= 4 and len(idxs) > len(ev.ground_reads) / 3:
            if k != first_kind:                         # 同一類已經由「對 X 特別有感」說過，不重講
                add("linger", "", idxs[0], k=k)
    if ev.plan_writes:
        aft = [g for g in ev.ground_reads if g > ev.plan_writes[0]]
        if len(aft) >= 3:
            add("reads_after_plan", f"寫好計畫之後，還是邊做邊翻，又翻了 {len(aft)} 次東西", aft[0])
    if len(per_kind) >= 3:
        firsts = sorted(v[0] for v in per_kind.values())
        add("many_kinds", f"一共翻過 {len(per_kind)} 類不同的東西，不只盯著一處", firsts[-1])
    for i, r in enumerate(ev.rows):
        if r.get("ok") is False and r.get("tool") == "ws_read" and _place_of(r.get("path")):
            if any(x.get("ok") is True and x.get("tool") in ("ws_read", "ws_list") for x in ev.rows[i + 1:]):
                add("failed_go_on", "碰到一個打不開的東西，沒卡住，換個地方繼續", i)
                break
    # ── 計畫
    for i in ev.plan_writes[:1]:
        again = [j for j, r in enumerate(ev.rows) if j > i and r.get("tool") == "ws_read" and r.get("path") == PLAN_FILE
                 and r.get("ok") is True]
        if again:
            add("reread_plan", "寫好計畫之後，又回頭讀了一遍自己寫的", again[0])
    k = ev.plan_writes_per_attempt
    if k >= 2:
        seenp: dict[int, int] = {}
        step_i = None
        for i in ev.plan_writes:
            seenp[att[i]] = seenp.get(att[i], 0) + 1
            if seenp[att[i]] == 2 and step_i is None:
                step_i = i
        add("changed_mind", "做到一半改了主意，把計畫重寫了一遍" if k == 2 else f"計畫寫了又改，前後改了 {k - 1} 次", step_i)
    # ── 成品
    per_path: dict[tuple[int, str], list[int]] = {}
    for i in arts:
        per_path.setdefault((att[i], str(ev.rows[i].get("path"))), []).append(i)
    rew = [(len(v), v[-1]) for v in per_path.values() if len(v) >= 2]
    if rew:
        n, last_i = max(rew)
        add("revise_product", f"同一件東西寫了又改，前後共 {n} 版", last_i)
    if ev.a_two_versions() and arts:
        add("two_versions", "拿不定主意，乾脆做了兩個版本", arts[-1])
    if len(ev.files) >= 2 and arts and not ev.a_two_versions():
        add("several_made", f"做出來的不只一樣，一共 {len(ev.files)} 樣", arts[-1])
    if arts and ev.files:
        biggest = max(len(t) for t in ev.files.values())
        if len(ev.files) == 1 and biggest <= SHORT_MADE_CHARS:
            add("short_made", "做出來的東西很短，幾句話就收了", arts[-1])
        elif biggest >= LONG_MADE_CHARS:
            add("long_made", f"有一樣東西寫得很細，光那一樣就寫了 {biggest} 個字", arts[-1])
    if ev.a_left_for() and arts:
        add("left_for", "做好的東西，特地寫明了要留給誰", arts[-1])
    if ev.a_kept() and arts:
        add("kept", "做好的東西，寫明了收在哪裡", arts[-1])
    # ── 節奏（只看紀錄的步數與時間）與成品的口氣（只看成品有沒有問號／留餘地的詞／數字）
    t0 = ev.rows[0].get("ts_ms") if ev.rows else None
    if PACE_HABITS and arts and ev.plan_writes and isinstance(t0, int) and isinstance(ev.rows[ev.plan_writes[0]].get("ts_ms"), int):
        dt = (ev.rows[ev.plan_writes[0]]["ts_ms"] - t0) / 1000.0
        if dt >= PACE_SLOW_S:
            add("pace_slow", f"不急著動手，過了 {int(dt // 60)} 分 {int(dt % 60)} 秒才開始寫計畫"
                if dt >= 60 else f"不急著動手，過了 {int(dt)} 秒才開始寫計畫", ev.plan_writes[0])
        elif dt <= PACE_FAST_S:
            add("pace_fast", "一進來很快就開始寫計畫", ev.plan_writes[0])
    n_all = len(ev.all)
    if PACE_HABITS and arts and n_all <= STEPS_FEW:
        add("steps_few", f"從頭到尾只用了 {n_all} 步就交了", arts[-1])
    elif PACE_HABITS and arts and n_all >= STEPS_MANY:
        add("steps_many", f"前前後後用了 {n_all} 步才交", arts[-1])
    prod = "\n".join(ev.files.values())
    if arts and prod:
        if re.search(r"[?？]", prod):
            add("q_mark", "做出來的東西裡，留了一個問號，沒把話說死", arts[-1])
        elif len(re.findall(r"也許|可能|大概|或許|說不定", prod)) >= 2:
            add("hedge", "寫東西習慣留餘地，用了好幾個「也許」「可能」", arts[-1])
        elif re.search(r"\d", prod):
            add("digits", "做出來的東西裡，有具體的數字", arts[-1])
    wish = ""
    m = re.search(r"我想\s*[：:]\s*(.+)", str(plan_text or ""))
    if m:
        wish = re.split(r"[。\n]", m.group(1))[0]
    if wish and title and arts and ev.plan_writes:
        body = (title or "") + " " + " ".join(t[:200] for t in ev.files.values())
        if not (key_bigrams(wish) & key_bigrams(body)):
            add("plan_vs_made", "計畫寫的是一回事，最後做出來的又是另一回事", ev.plan_writes[-1])
    # ── 收尾
    if arts and ev.a_recheck():
        last_art = arts[-1]
        after = [i for i in range(last_art + 1, len(ev.rows))
                 if ev.rows[i].get("ok") is True and ev.rows[i].get("tool") in ("ws_list", "ws_read")]
        first_pl = min(ev.place_first, key=ev.place_first.get) if ev.place_first else None
        back = [i for i in after if first_pl and _place_of(ev.rows[i].get("path")) == first_pl
                and ev.rows[i].get("tool") == "ws_read"]
        if back and len(ev.place_first) >= 2:
            add("recheck_first", "做完之後，又回頭去看了最早翻的那一類東西", back[0])
        elif after:
            add("recheck", "交出去之前，又回頭再看了一遍", after[0])
    # ── 被退回
    if retries > 0:
        nxt = next((i for i, a in enumerate(att) if a >= 1), None)
        if nxt is None and ev.rows:          # 紀錄裡看不出重來的那一步（嘗試進行中、seq 沒回頭）⇒ 指到最後一步，不編
            nxt = len(ev.rows) - 1
        if nxt is not None:
            ids = set(retry_ids)
            if "G1" in ids:
                add("retried_open", 
                    "被退回過，因為計畫裡點名要看的東西還沒打開，補開之後才過" if accepted is True      # 「才過」只在這一跑最終通過時才說
                    else "被退回過，因為計畫裡點名要看的東西還沒打開，回去補開了", nxt)
            elif ids & {"G2", "G3"}:
                add("retried_source", "被退回過，因為有個數字說不出出處，回去補上了", nxt)
            else:
                add("retried", f"被退回 {retries} 次，每一次都回去改", nxt)
    if title and arts:
        add("made", f"最後做出來的是《{title}》", arts[-1])
    return out


def _jitter(seed: str, key: str) -> float:
    h = hashlib.sha256(f"{seed}|{key}".encode("utf-8")).digest()
    return 0.8 + 0.4 * (h[0] / 255.0)           # 0.8..1.2：只在稀有度接近時決勝負，不改變「稀有的優先」


def _fits(c: dict[str, Any]) -> bool:
    # 句尾還要放「（第 N 步）」；收據副本的步驟清單最多 500 步，超過的指不到就不用
    return len(c["text"]) + len(step_tag(c["step"])) <= MAX_CARD_LINE_CHARS and c["step"] <= 500


def mirror_pick(cands: list[dict[str, Any]], seed: str = "") -> list[dict[str, Any]]:
    """從成立的習慣挑至多 3 句：稀有度（固定表）×確定性微擾優先；同組只留一句；
    至少一句不是「怎麼開始」或「最後做出來的是」；依步驟先後排（讀起來像在說這一跑的經過），「做出了什麼」放最後。"""
    fit = [c for c in cands if _fits(c)]
    if any(c["key"] != "made" for c in fit):
        fit = [c for c in fit if c["key"] != "made"]        # 「最後做出來的是《…》」不是形容：沒有別的句子時才用
    ranked = sorted(fit, key=lambda c: -RARITY[c["key"]] * _jitter(seed, c["key"]))
    chosen: list[dict[str, Any]] = []
    groups: set[str] = set()
    for c in ranked:
        g = MIRROR_GROUP[c["key"]]
        if g in groups:
            continue
        chosen.append(c)
        groups.add(g)
        if len(chosen) >= MAX_MIRROR_LINES:
            break
    if chosen and all(MIRROR_GROUP[c["key"]] in ("start", "made") for c in chosen):
        extra = next((c for c in ranked if MIRROR_GROUP[c["key"]] not in ("start", "made")), None)
        if extra:
            drop = next((c for c in reversed(chosen) if MIRROR_GROUP[c["key"]] == "made"), chosen[-1])
            chosen[chosen.index(drop)] = extra
    chosen.sort(key=lambda c: (c["key"] == "made", c["step"]))
    return chosen


def mirror_picks(rows: list[dict[str, Any]], files: dict[str, str], retries: int,
                 title: str | None, plan_text: str = "", retry_ids: tuple[str, ...] = (),
                 seed: str = "", accepted: bool | None = None) -> list[dict[str, Any]]:
    ev = Evidence(rows, None)
    ev.files = dict(files or {})
    return mirror_pick(mirror_candidates(ev, retries, title, plan_text, retry_ids, accepted), seed or (title or ""))


def mirror_lines(rows: list[dict[str, Any]], files: dict[str, str], retries: int,
                 title: str | None, plan_text: str = "", retry_ids: tuple[str, ...] = (),
                 seed: str = "", accepted: bool | None = None) -> list[str]:
    """最多 3 句，每句尾端是「（第 N 步）」＝步驟紀錄裡的第 N 步（收據頁的步驟清單用同一個編號）。"""
    return [c["text"] + step_tag(c["step"])
            for c in mirror_picks(rows, files, retries, title, plan_text, retry_ids, seed, accepted)]


MAX_WANT_PUBLIC = 60        # 給觀眾／雲端／電視的 `want` 字數上限（`wish_of` 本身 ≤ 44）


def plan_write_step(rows: list[dict[str, Any]]) -> int | None:
    """PLAN.md 最後一次成功寫入的那一步（「第 N 步」，與習慣句、收據頁同一套編號＝步驟紀錄檔的順位）；沒有或超過 500 ⇒ None。"""
    n = None
    for i, r in enumerate(rows):
        if r.get("tool") == "ws_write" and r.get("path") == PLAN_FILE and r.get("ok") is True:
            n = int(r.get("_n") or (i + 1))
    return n if n is not None and n <= 500 else None


def want_with_step(plan_text: str, rows: list[dict[str, Any]], traits: str, f: dict[str, Any]) -> tuple[str | None, int | None]:
    """(想做的那一句, 它寫進 PLAN 的那一步)。句子取不到 ⇒ (None, None)；步數對不到寫入紀錄 ⇒ (句子, None)。"""
    w = wish_of(plan_text, traits, f) if str(plan_text or "").strip() else None
    if not w or len(w) > MAX_WANT_PUBLIC:
        return None, None
    return w, plan_write_step(rows)


def compose_card(f: dict[str, Any], *, letter_text: str, rows: list[dict[str, Any]], files: dict[str, str],
                 retries: int, traits: str = "", plan_text: str = "", retry_ids: tuple[str, ...] = (),
                 seed: str = "", accepted: bool | None = None) -> dict[str, Any]:
    """命盤卡（確定性，不經模型）。給觀眾的 `lines`＝「像不像你」的做事習慣（`mirror_lines`，第 5 節）——
    **有沒有命盤都做**：習慣句只看步驟紀錄。解讀句與路線句只留在 `reading`／`route` 當紀錄，不進 `lines`。"""
    res: dict[str, Any] = {"first_line": first_line(f), "head": MIRROR_HEAD, "lines": [], "dropped": [],
                           "present": False, "card_file": False}
    title = title_of(files, f, traits, letter_text)
    res["title"] = title
    places = visited_places(rows)
    res["places"] = places
    if has_any(f):
        res["reading"] = reading_of(letter_text, f, traits)
        if places:
            res["route"] = route_of(places, last_place_before_delivery(rows), title or NO_NAME_TITLE, retries)
    res["lines"] = mirror_lines(rows, files, retries, title, plan_text, retry_ids, seed, accepted)
    # 2026-10-13「它想做的是…」：分身這一跑想做的那件事＝PLAN「我想：」之後那一句（同一套 `wish_of` 防呆；取不到就 None，不編）。
    res["want"], res["want_step"] = want_with_step(plan_text, rows, traits, f)
    res["present"] = bool(res["lines"])
    return res


# ---------------------------------------------------------------------------
# 4b. P13 命盤卡第三版：「你的數位分身其實是…」四行
# ---------------------------------------------------------------------------

RECORD_FILE = "試的紀錄.md"                      # 分身交的「試的紀錄」（檔名固定，才讀得到最後那句感想）
VERDICT_PREFIX = "你的數位分身其實是："
WANT_PREFIX = "它心裡想："
TRIED_PREFIX = "它試了："
SAID_PREFIX = "試完它說："
MAX_WANT_CARD = 44          # 指令要求「我想：」之後 30 字內、一句完整的話；卡上容忍到 44（再長取完整子句，子句不完整就換下一個候選，再不行才不上卡）
MAX_TRIED_CARD = 56         # 卡第 3 行（做了什麼＋世界留下的改變）的句子上限（前綴 4 字 ⇒ 60 ≤ 60）
MAX_SAID_CARD = 55          # 前綴 5 字 ⇒ 60 ≤ 60
LOOK_NAME = "look_in.json"  # run-dir：外形三項＋氣質詞（觀眾 AI 的判決；撤回時跟 run-dir 一起刪）
SHAPES = ("圓潤", "修長", "厚實", "小巧", "粗獷", "方正")
TEXTURES = ("光滑", "指紋", "斑駁", "絨面")
COLORS = ("暖土", "赭紅", "奶油", "灰藍", "苔綠", "沙金")
MAX_VIBE_WORD = 6
_SAID_KEY = re.compile(r"^[\s#>*_\-]*(?:感想|試完(?:我|它)?說)[\s*_]*[：:]\s*(.+)$")
_PLAN_LABEL = re.compile(r"^(?:第一行|我決定|決定|我要試|它要試|想試)\s*[：:]\s*")
_FILENAME_LIKE = re.compile(r"\.(md|txt)\b|[A-Za-z0-9_]+\.[a-z]{2,4}\b|/")


_HEADING_ONLY = re.compile(r"^(?:PLAN(?:\.md)?|計畫|試的計畫|我的計畫)\s*[：:]?$", re.I)


def _first_line_of(text: str) -> str:
    """PLAN.md 第一個「有內容」的行（只是標題字樣「PLAN」「計畫」的行不算）；拿掉 markdown 記號與「第一行：」之類的標籤。"""
    for ln in str(text or "").splitlines():
        if ln.strip():
            s = re.sub(r"^[\s#>*\-_]+", "", ln).strip()
            s = _PLAN_LABEL.sub("", s).strip().strip("「」『』\"'*")
            if not s or _HEADING_ONLY.match(s):
                continue
            return s
    return ""


ABSTRACT_WORDS = ("渴望", "靜默", "虛無", "細碎", "共振", "壓抑", "沉默", "溫潤", "圓潤")      # 與 `twinagent.ABSTRACT_WORDS` 同值（測試釘住）


def _card_sentence(raw: str, traits: str, f: dict[str, Any], max_len: int) -> str | None:
    """卡上一句話的共同防呆：LEAK／時段詞／沒給的東西／現實詞（`clean_sentence`）＋不像檔名＋不自己說閘門給了結果。"""
    s, _why = clean_sentence(raw, traits, f, max_len)
    if not s or _FILENAME_LIKE.search(s) or RECEIPT_CLAIM.search(s):
        return None
    if sum(1 for w in ABSTRACT_WORDS if w in s) >= 2:           # 卡上一句話裡堆兩個以上被用爛的抽象詞 ⇒ 不上卡（寧缺）
        return None
    return re.sub(r"(?<=[一-鿿」])[ \t]+(?=[一-鿿「])", "", s).rstrip("。.！!")          # 拿掉路徑清成物件名後留下的空白（「音樂盒 從…」）


_WISH_LABEL = re.compile(r"^[\s#>*\-_]*(?:\d+[.、]\s*)?\**我想\**\s*[：:]\s*(.+)$")
_CHANGE_LABEL = re.compile(r"^[\s#>*\-_]*\**(?:改變|世界(?:的)?改變|留下的改變|這個改變是)\**\s*[：:]\s*(.*)$")
_SENT_END = "。！？!?"
#: 願望句的開頭（去掉「想／想要」之後）：動詞在前。不在這張表裡 ⇒ 多半是名詞片語（「一張填滿了圓圈的紙卡」），不上卡。
_WISH_VERBS = "讓|看|弄清楚|搞清楚|知道|聽|找|等|確認|證明|試|摸|見|記|被|留|吃|睡|送|還|說|唱|畫|跳|學|收|守|陪|求|聞|有人|有東西|能|可以"
_WISH_START = re.compile(rf"^(?:{_WISH_VERBS})")
_ACTION_START = re.compile(r"^(?:把|用|去|在|拿|走|先|從|到|將|替|幫|再|跟|對|往)")


def wish_of(plan_text: str, traits: str, f: dict[str, Any]) -> str | None:
    """卡第 2 行：PLAN.md 第一個「我想：」開頭的行，取冒號之後的願望句（想要，不是動作）。
    候選依序：「我想：」那一句 → PLAN「為什麼是他」段與試的紀錄裡以「我想＋願望動詞」開頭的完整句；每個候選都要**是完整的一句**
    （`frag_reason`）且過卡上共同防呆，過不了就換下一個，全部不行才沒有這一行（寧缺；不退回拿動作句充數）。"""
    cands: list[tuple[str, bool]] = []
    lines = str(plan_text or "").splitlines()
    for ln in lines[:12]:
        m = _WISH_LABEL.match(ln.strip())
        if m:
            cands += _sentences_of(m.group(1).strip().strip("「」『』\"'*"))[:1]
            break
    else:
        return None                    # 沒有「我想：」標籤＝第二輪的動作句，不充數
    for ln in lines[1:]:
        for s, term in _sentences_of(ln):
            m = re.match(rf"^(?:\d+[.、]\s*)?我想要?(?=(?:{_WISH_VERBS}))(.+)$", s)
            if m:
                cands.append((m.group(1), term))
    for raw, term in cands:
        w = re.sub(rf"^想要?(?=(?:{_WISH_VERBS}))", "", _clean_paths(raw)).lstrip("：: ，,")
        if not w or _ACTION_START.match(w) or not _WISH_START.match(w):    # 以動作開頭＝計畫句；不是「動詞在前的願望」＝名詞片語
            continue
        got = _first_ok([(w, term)], MAX_WANT_CARD, traits, f, wish=True)
        if got:
            return got
    return None


want_of = wish_of          # 舊名字（第二輪的呼叫端）


def said_of(record_text: str, traits: str, f: dict[str, Any]) -> str | None:
    """卡第 4 行的句子：「試的紀錄」裡**最後一個**「感想：…」；取第一個「完整的句子」（到 。！？ 為止、≤ `MAX_SAID_CARD`），
    太長取完整子句，再不行換下一句，都不行＝None（不補罐頭句）。"""
    hit = None
    for ln in str(record_text or "").splitlines():
        m = _SAID_KEY.match(ln)
        if m:
            hit = m.group(1)
    if not hit:
        return None
    return _first_ok([(_SELF_MADE.sub("", s).strip(), term) for s, term in _sentences_of(_clean_paths(hit))[:3]],
                     MAX_SAID_CARD, traits, f)


def _first_sentence(text: str) -> str:
    t = " ".join(str(text or "").split())
    for i, ch in enumerate(t):
        if ch in _SENT_END:
            return t[:i]
    return t


_QUOTED_PATH = re.compile(r"「([^」]*(?:/|\.txt|\.md)[^」]*)」")
_BARE_SLASH = re.compile(r"[一-鿿A-Za-z0-9_]+(?:/[一-鿿A-Za-z0-9_ ]+)+(?:\.(?:txt|md))?")
_EXT = re.compile(r"\.(?:txt|md)\b")
_SEQ_PREFIX = re.compile(r"桌[一二三四五六七八九十0-9]+_(?=[一-鿿])")


def _obj_name(path: str) -> str:
    """`地上/長桌廣場/桌五_音樂盒.txt` → `音樂盒`（資料夾、副檔名、前綴的「桌五_」都拿掉）。"""
    last = next((x for x in reversed(path.split("/")) if x.strip()), "")
    last = re.sub(r"\.(?:txt|md)$", "", last)
    return last.split("_")[-1] if "_" in last else last


def _clean_paths(t: str) -> str:
    """模型愛把地上的檔案路徑或檔名放進句子：卡上只留物件的名字（不帶資料夾、副檔名）。"""
    t = _QUOTED_PATH.sub(lambda m: "「" + _obj_name(m.group(1)) + "」", t)
    t = _BARE_SLASH.sub(lambda m: _obj_name(m.group(0)), t)
    return _SEQ_PREFIX.sub("", _EXT.sub("", t))               # 「桌五_音樂盒.txt」→「音樂盒」


_HANGING_END = tuple("的之和與及或但而並把用在被讓對從向往跟像如")
_LABEL_LEAD = re.compile(r"^\s*(?:試了什麼|怎麼試的?|最後怎麼收場|中間出了什麼事|改變|這個改變是)\s*[：:]\s*")
_SELF_MADE = re.compile(r"[，,]?\s*這是我(?:自己)?做的[，,。]?")


#: 一句像樣的「做了什麼／變成什麼」會有的動詞字（確定性字面檢查，不是語意判斷）；沒有任何一個 ⇒ 多半是名詞片語或被截斷的殘句。
_PRED = set("放變成多少填蓋掛立斷接亮響擺貼留拆摺捏種推拉裂補綁埋圍搭刻畫寫挖移擠壓抱捲揉串排插抬翻點釘縫裝敲吹拿帶遞送做建修"
            "能會有出開活動完到起回醒說唱長發飛漂流轉停走住著了斜靠繫移載穿折疊鋪蹲坐站躺擁握撥拍對合連齊現呈入進滿空找見聽")
_TAIL_BAD = tuple("的之和與及或但而並把用在被讓對從向往跟像如地")
_TAIL_PHRASES = ("情況下", "狀態下", "之下", "的時候", "之際", "之前", "之後", "以前", "以後", "為止", "而且", "然後", "但是",
                 "所以", "因為", "如果", "假如", "雖然", "即使", "只要", "一邊", "同時")      # 掛在尾巴的從屬連接：這一段還沒說完
_PREDICATIVE_DE = re.compile(r"(?:是|很|都|變得|變成|還是).{0,8}的$")      # 「現在長椅中間是空的」的「的」是句尾，不是修飾語


def _complete(c: str, wish: bool = False) -> bool:
    """這一段像不像完整的一句：結尾不掛著「的／和／把／地…」，而且有動詞字（願望句的開頭動詞不算）。"""
    c = c.rstrip("，、；,; ")
    if not c or (c.endswith(_TAIL_BAD) and not (c.endswith("的") and _PREDICATIVE_DE.search(c))) or c.endswith(_TAIL_PHRASES):
        return False
    if wish and not c.startswith(("讓", "有人", "有東西", "能", "可以")):     # 「聽見…」「看…會不會」：開頭的動詞自己就是謂語
        return True
    body = re.sub("|".join(PLACES) + "|「[^」]*」|角落|沒有", "", c[1:] if wish else c)     # 地名與物件名裡的字（長桌廣場的「長」…）、「沒有」不算動詞
    return any(ch in _PRED for ch in body)


def _fit(sent: str, limit: int, wish: bool = False) -> str | None:
    """挑出 ≤ limit 字、像完整一句的片段：整句夠短又完整就用整句；太長就從開頭起取最長的「整段子句」（在，；處）且那一段是完整的；
    不行就取「現在…」那一半；都不行 ⇒ None（寧缺，不硬切半個詞）。不在「、」截。"""
    sent = sent.strip()
    if len(sent) <= limit:
        return sent.rstrip("，、；,; ") if _complete(sent, wish) else None
    i = sent.rfind("現在")                       # 長句裡「現在…」那一半就是改變本身，優先
    if i > 0 and len(sent) - i <= limit and _complete(sent[i:], wish):
        return sent[i:].rstrip("，、；,; ")
    clauses = re.findall(r"[^，；,;]+[，；,;]?", sent)
    best = None
    for k in range(1, len(clauses) + 1):
        cand = "".join(clauses[:k]).rstrip("，、；,; ")
        if len(cand) > limit:
            break
        if len(cand) >= 8 and _complete(cand, wish):
            best = cand
    return best


# ---------------------------------------------------------------------------
# P13 第四輪：殘句不上卡。取**完整句**（到 。！？ 為止）且 ≤ 上限；太長退到「完整子句」且該子句自己語意完整；
# 都不行換下一個候選句；全部不行才沒有那一行。判斷是結構規則（不只字表）：結尾掛著、從屬沒有主句、「但看到…」的時間殘片、
# 以接續詞開頭、結尾是名詞（「…的反應」）卻沒有主要動詞、標題式結尾。規則只用於挑句，不改任何一個字。
# 誠實邊界：確定性字面／結構啟發式，擋不住所有殘句（負控制集 `tests/test_twin_cardsentence_20261008.py` 釘住已知的），也會誤丟。
# ---------------------------------------------------------------------------

_SUBORD_HEAD = ("雖然", "儘管", "即使", "就算", "如果", "假如", "要是", "因為", "由於", "既然", "只要", "一旦", "無論", "不管",
                "每當", "等到", "隨著", "當")
_CONN_LEAD = re.compile(r"^(?:但是|但|可是|不過|然而|而且|而|並且|並|所以|因此|於是|然後|接著|還有|以及)")
_TEMPORAL_FRAG = re.compile(r"^(?:看到|看著|看見|聽到|聽見|想到|發現|當|等到|每當|隨著|一邊|一面)")
_CONT_START = ("是", "讓", "使", "令", "才", "就", "也", "並", "而", "且", "則", "還", "卻", "所以", "因此", "於是", "然後", "接著",
               "從而", "導致", "以及", "或者", "或是")
_TAIL_MORE = ("或者", "還是", "以及", "而是", "並且", "想要", "打算", "試圖", "需要", "應該", "可以", "能夠", "開始", "繼續", "準備",
              "正在", "嘗試")
_LOCATIVE_PP = re.compile(r"^(?:我|它|他)?(?:在|從|向|往|朝|於)[^，；,;]*(?:上|下|裡|中|內|旁|邊|前|後|外|處|旁邊|附近)$")
_TITLE_END = ("紀錄", "記錄", "實驗", "嘗試", "計畫", "計劃", "過程", "筆記", "清單", "報告", "結果")
#: 句尾名詞檢查時要遮掉的「含動詞字的名詞」（「動作」的「動」不是謂語）
_NOUN_MASK = ("動作", "活動", "運動", "種子", "空位", "長椅", "長桌", "出口", "入口", "開口", "開始", "對稱", "連結", "完整性")
#: 這一子句有主要動詞的證據（句尾是「…的N」時用）：有／是／把／將／成為／變成／了／過／動詞＋方向補語／「著＋這個」
_EVID = re.compile(r"[有是把將]|成為|變成|變為|成了|[了過]|著(?:這|那|一|某)"
                   r"|[放擺掛貼綁繫塞裝帶移挪壓蓋插疊堆丟送交遞做捏拿找看聽寫畫留](?:進|入|在|到|上|向|往|給|回|出|下|走|開|掉|起)")
_EVID_NOISE = re.compile(r"所有|擁有|但是|於是|或是|總是|還是|而是|經過|通過|超過|把握|了解")


def _clauses_of(s: str) -> list[str]:
    return [c.strip() for c in re.split(r"[，,；;]", s) if c.strip()]


def _mask(s: str) -> str:
    s = re.sub("|".join(PLACES) + r"|「[^」]*」", "", s)
    for w in _NOUN_MASK:
        s = s.replace(w, "")
    return s


def _has_verb(s: str) -> bool:
    return any(ch in _PRED for ch in _mask(s))


def frag_reason(s: str, *, terminated: bool = False, wish: bool = False) -> str | None:
    """這一段像不像**完整的一句**？回 None＝像；回字串＝殘句的理由。
    `terminated`＝這一句在原文有 。！？ 收尾（模型自己寫完的整句，不再套「結尾是名詞」那組嚴格規則）；
    `wish`＝願望句（開頭的動詞自己就是謂語）。切出來的子句、沒有句號的行一律用嚴格規則（terminated=False）。"""
    c = str(s or "").strip().rstrip("，、；,; ")
    if len(c) < 5:
        return "short"
    if c.endswith(_TAIL_BAD) and not (c.endswith("的") and re.search(r"是.{0,8}的$", c)) and not c.endswith("的地"):
        return "hanging_end"                                  # 「兩道光交界的地」的「地」是名詞（地方），前面一定是「的」；副詞的「地」不會接在「的」後面
    if c.endswith(_TAIL_PHRASES) or c.endswith(_TAIL_MORE):
        return "hanging_tail"
    cl = _clauses_of(c)
    if not cl:
        return "short"
    if cl[-1].startswith(_SUBORD_HEAD) or (cl[0].startswith(_SUBORD_HEAD) and len(cl) < 2):
        return "subordinate_without_main"                      # 「雖然…」沒有主句，或句子最後掛著一個「雖然很小聲」
    last = cl[-1]
    core = _CONN_LEAD.sub("", last, count=1)
    if (core != last and _TEMPORAL_FRAG.match(core)) or last.startswith(("等到", "每當", "隨著")):
        return "temporal_fragment"
    if terminated:
        return None
    if any(c.endswith(w) for w in _TITLE_END) and not _EVID.search(_EVID_NOISE.sub("", c)):
        return "title_like"
    if not wish and cl[0].startswith(_CONT_START):
        return "continuation_start"
    if _LOCATIVE_PP.match(last):
        return "locative_phrase"                              # 「（我）在…的石壁上」：只交代地點，動作在下一個子句
    if wish and _WISH_START.match(cl[0]) and not cl[0].startswith(("讓", "有人", "有東西", "能", "可以")):
        return None                                       # 「看…」「聽見…的第十二個音」：開頭的動詞自己就是謂語，後面的名詞是它的受詞
    body = last[1:] if (wish and len(cl) == 1) else last
    if not _has_verb(body):
        return "no_verb"
    de = last.rfind("的")
    if 0 <= de < len(last) - 1:
        tail = last[de + 1:]
        if len(tail) <= 8 and not _has_verb(tail) and not _EVID.search(_EVID_NOISE.sub("", last)):
            return "nominal_end"                          # 「…被撥動後的反應」「…沒說出口的情感」：句尾是名詞、前面沒有主要動詞
    return None


def _sentences_of(text: str) -> list[tuple[str, bool]]:
    """文字 → [(句子, 有沒有 。！？ 收尾)]；沒有收尾的只可能是最後一句。"""
    t = " ".join(str(text or "").split())
    out: list[tuple[str, bool]] = []
    buf = ""
    for ch in t:
        if ch in _SENT_END:
            if buf.strip():
                out.append((buf.strip(), True))
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append((buf.strip(), False))
    return out


def _fit_options(sent: str, terminated: bool, limit: int, wish: bool = False) -> list[str]:
    """這一句放上卡的可能寫法（優先序）：整句（完整且 ≤ limit）→「現在…」那一半 → 越長越好的完整子句前綴。"""
    s = sent.strip().rstrip("，、；,; ")
    out: list[str] = []
    if len(s) <= limit and frag_reason(s, terminated=terminated, wish=wish) is None:
        out.append(s)
    if len(s) > limit and not wish:
        i = s.rfind("現在")
        if i > 0 and len(s) - i <= limit and frag_reason(s[i:], terminated=False) is None:
            out.append(s[i:])
    clauses = re.findall(r"[^，；,;]+[，；,;]?", s)
    pre: list[str] = []
    for k in range(1, len(clauses)):                     # 不含整句（整句在上面處理過）
        cand = "".join(clauses[:k]).rstrip("，、；,; ")
        if len(cand) > limit:
            break
        if len(cand) >= 8 and frag_reason(cand, terminated=False, wish=wish) is None:
            pre.append(cand)
    out += sorted(pre, key=len, reverse=True)
    return out


def _first_ok(cands: list[tuple[str, bool]], limit: int, traits: str, f: dict[str, Any], wish: bool = False) -> str | None:
    """依序試每個候選句的每個寫法，第一個既完整又過卡上共同防呆（現實詞／LEAK／沒給的東西…）的就是答案。"""
    for s, term in cands:
        for opt in _fit_options(s, term, limit, wish):
            got = _card_sentence(opt, traits, f, limit)
            if got:
                return got
    return None


def changed_candidates(record_text: str) -> list[tuple[str, bool]]:
    """「試的紀錄」裡世界留下的改變（原文選句、不改字）：以「改變：」開頭那一段的前兩句；沒有就取「感想：」前面最近一段的前兩句。
    **標題行不當候選**（名詞片語不是做了什麼）。"""
    lines = str(record_text or "").splitlines()
    body = None
    for i, ln in enumerate(lines):
        m = _CHANGE_LABEL.match(ln.strip())
        if m:
            body = m.group(1).strip() or next((x.strip() for x in lines[i + 1:] if x.strip()), "")
            break
    if body is None:
        said = next((i for i in range(len(lines) - 1, -1, -1) if _SAID_KEY.match(lines[i])), None)
        if said is None:
            return []
        for ln in reversed(lines[:said]):
            t = ln.strip()
            if t and "這是我自己做的" not in t[:8] and not t.startswith("#"):
                body = t
                break
    if not body:
        return []
    return [(_SELF_MADE.sub("", _LABEL_LEAD.sub("", s)).strip(), term) for s, term in _sentences_of(_clean_paths(body))[:2]]


def changed_of(record_text: str) -> str | None:
    """（舊介面）改變那一句的第一個像樣寫法；沒有＝None。"""
    for s, term in changed_candidates(record_text):
        opts = _fit_options(s, term, MAX_TRIED_CARD)
        if opts:
            return opts[0]
    return None


def title_line_of(record_text: str) -> str | None:
    """「試的紀錄」第一個有內容的行（指令要求它是這次試的標題）。第四輪起不再上卡（標題是名詞片語），只留給檔案庫。"""
    for ln in str(record_text or "").splitlines():
        t = re.sub(r"^[\s#>*\-_]+", "", ln).strip().strip("「」『』\"'*")
        if t:
            if t in _GENERIC_STEMS or t.startswith("試的紀錄"):
                return None
            t = _LABEL_LEAD.sub("", t).rstrip("。.")
            return t if 0 < len(t) <= MAX_TRIED_CARD else None
    return None


#: 兩張卡的行共用「這個詞」不算數的泛用詞（沒有指到世界上的哪個東西）
_GENERIC_BIGRAMS = frozenset("位置 重新 回到 一半 一個 一張 一些 一點 原本 沒有 自己 現在 世界 東西 地方 想要 可以 這個 那個 那張 這張 "
                             "出現 變成 看見 發現 開始 結果 上面 裡面 旁邊 中間 之後 之前 然後 因為 所以 如果 或是 還是 已經 能夠 "
                             "沉重 情感 感覺 感到 壓迫 心裡 真實 內心 一點 完整".split())
_BIGRAM_STOP = set("的了在把讓它他她我們你是有被和與及或但而並也就都很不這那一個張些點上下裡中之後前並將從向往跟像如地得著過")
_CJK_RUN = re.compile(r"[一-鿿]+")


def key_bigrams(text: str) -> set[str]:
    """一句話裡的**關鍵名詞字串**（確定性、字面）：連續漢字取相鄰兩字，含虛詞字（的了在把…）或在泛用詞表裡的不算。
    第 2 行（願望）與第 3 行（做了什麼）共用任何一個 ⇒ 兩行講的是同一個東西（紙卡、缺口、薄泥…）。"""
    out: set[str] = set()
    for run in _CJK_RUN.findall(str(text or "")):
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg[0] in _BIGRAM_STOP or bg[1] in _BIGRAM_STOP or bg in _GENERIC_BIGRAMS or bg in ABSTRACT_WORDS:
                continue
            out.add(bg)
    return out


def shared_with_wish(sentence: str, wish: str | None) -> int:
    """這一句與第 2 行（願望句）共用的關鍵名詞字串個數（沒有願望＝0）。"""
    if not wish:
        return 0
    return len(key_bigrams(sentence) & key_bigrams(wish))


_CHANGE_MARK = re.compile(r"[了過]|現在|變成|成為|留下|放在|蓋住|堆在|擺在|落在|填")
_RECORD_NOISE = re.compile(r"^(?:#|試的紀錄|這次試的標題|(?:改變|感想|最後怎麼收場|中間出了什麼事|試了什麼|怎麼試的?)\s*[：:])")


def body_candidates(record_text: str) -> list[tuple[str, bool]]:
    """「試的紀錄」正文裡的每一個句子（原文、不改字）：略過標題行、「感想：」、「改變：」（那一段由 `changed_candidates` 管）。"""
    out: list[tuple[str, bool]] = []
    lines = str(record_text or "").splitlines()
    for i, ln in enumerate(lines):
        t = ln.strip()
        if not t or _RECORD_NOISE.match(t) or t.endswith(".md") or _SAID_KEY.match(t):
            continue
        if len(t) < 16 and not re.search(r"[。！？]", t) and i <= 2:         # 標題行（名詞片語）不當候選
            continue
        for sn, term in _sentences_of(_clean_paths(t)):
            sn = _SELF_MADE.sub("", _LABEL_LEAD.sub("", sn)).strip()
            if sn:
                out.append((sn, term))
    return out


#: 「結果句」記號：世界現在怎樣了（比 `_CHANGE_MARK` 嚴格；只用來決定正文句能不能插隊）
_RESULT_MARK = re.compile(r"現在|變成|多了|多出|不再|終於|留下")


def rank_tried(change: list[tuple[str, bool]], body: list[tuple[str, bool]], wish: str | None) -> list[tuple[str, bool]]:
    """第 3 行的候選排序（確定性）：① 「改變」那段裡與第 2 行共用關鍵名詞的句子 → ② 正文其他句子裡共用、且帶『做了／留下什麼』字樣的（共用越多越前面；改變段第一句已是結果句〔`_RESULT_MARK`〕時不插隊）
    → ③ 其餘「改變」句，照原本的順序。沒有願望或沒有任何共用 ⇒ 完全等於原本的順序（只有 ③）。"""
    seen = {c[0] for c in change}
    t0 = [c for c in change if shared_with_wish(c[0], wish) > 0]                 # 改變段裡本來就共用的：維持原本的先後
    t1 = [c for c in body if c[0] not in seen and shared_with_wish(c[0], wish) > 0 and _CHANGE_MARK.search(c[0])]   # 正文裡「做了／留下什麼」且共用的
    t1.sort(key=lambda c: -shared_with_wish(c[0], wish))
    t2 = [c for c in change if shared_with_wish(c[0], wish) <= 0]
    # 主線 2026-10-08（round5 盲評）：評審偏好結果句（真卡 2/6 票偏正文動作句）⇒ 改變段第一句已是結果句時，正文句不插隊
    if change and _RESULT_MARK.search(change[0][0]):
        t1 = []        # 改變段第一句本身就是「世界現在怎樣了」的結果句：不讓正文動作句插隊（round5 盲評 v1）
    return t0 + t1 + t2


def tried_of(record_text: str, traits: str, f: dict[str, Any], wish: str | None = None) -> str | None:
    """卡第 3 行：`它試了：<做了什麼＋世界留下的改變>`——前綴**永遠**是「它試了：」（手機與電視都靠它拆前綴）。
    候選＝「試的紀錄」的改變那一段，**優先和第 2 行（願望）共用世界物件名／關鍵名詞的完整句**（`rank_tried`），沒有共用的才退回現行順序；
    完整句、太長取完整子句、不行換下一句，過卡上一句話的共同防呆；**不放路線、不放標題**。每個字仍出自紀錄。"""
    change = changed_candidates(record_text)
    cands = rank_tried(change, body_candidates(record_text), wish) if wish else change
    s = _first_ok(cands, MAX_TRIED_CARD, traits, f)
    if not s:
        return None
    s = s.replace("我們", "它們").replace("我", "它")           # 卡是第三人稱：「我」→「它」
    return TRIED_PREFIX + (s[1:] if s.startswith("它") and len(s) > 6 else s)       # 「它試了：它…」→「它試了：…」


# --- 第 1 行：AI 的判決（形狀質感色系居民＋氣質詞＋命盤代號），程式組句、不經模型 ---

def normalize_look(card: Any) -> dict[str, Any]:
    """卡 → `{shape, texture, color, vibe:[詞…]}`（枚舉不合法 ＝ None；氣質切成詞，過現實詞／時段詞，每詞 ≤ `MAX_VIBE_WORD` 字，最多 3 個）。"""
    c = card if isinstance(card, dict) else {}
    out: dict[str, Any] = {"shape": _enum(c.get("shape"), SHAPES), "texture": _enum(c.get("texture"), TEXTURES),
                           "color": _enum(c.get("color"), COLORS), "vibe": []}
    words: list[str] = []
    for w in re.split(r"[、，,；;/／\s和與及]+", str(c.get("vibe") or "")):
        w = w.strip("。.！!「」『』\"'*·")
        if 1 <= len(w) <= MAX_VIBE_WORD and re.search(r"[一-鿿]", w) and not mentions_reality(w) and not any(t in w for t in TIME_WORDS) \
                and w not in words:
            words.append(w)
    out["vibe"] = words[:3]
    return out


def code_of(f: dict[str, Any]) -> str:
    """`ENFP · 雙子 · AB`（括號裡那一串；沒給的就不寫）。"""
    return " · ".join(x for x in (f.get("mbti"), f.get("zodiac"), f.get("blood")) if x)


def verdict_of(f: dict[str, Any], look: dict[str, Any] | None, seed: str = "") -> str:
    """卡第 1 行：`你的數位分身其實是：<形狀><質感>的<色系>居民，<氣質三詞擇二>（ENFP · 雙子 · AB）`。
    全部來自觀眾 AI 的判決欄位；氣質三詞擇二由 `seed`（run-dir 名）確定性決定；外形與氣質都沒有時退回舊寫法（只有命盤）。
    總長 ≤ `MAX_CARD_LINE_CHARS`（超過就從氣質詞開始減）。"""
    lk = look if isinstance(look, dict) else {}
    body = "".join(x for x in (lk.get("shape"), lk.get("texture")) if x)
    color = lk.get("color")
    if color:
        color = color if color.endswith("色") else color + "色"
    noun = (f"{body}的" if body else "") + (color or "") + "居民" if (body or color) else ""
    words = [w for w in (lk.get("vibe") or []) if isinstance(w, str)][:3]
    if len(words) == 3:                                      # 三詞擇二：拿掉哪一個由 seed 決定
        drop = int(hashlib.sha256(("vibe\n" + seed).encode("utf-8")).hexdigest(), 16) % 3
        words = [w for i, w in enumerate(words) if i != drop]
    code = code_of(f)
    if not noun and not words:
        return VERDICT_PREFIX + first_line(f)
    while True:
        head = noun + ("，" if noun and words else "") + "、".join(words)
        line = VERDICT_PREFIX + head + (f"（{code}）" if code else "")
        if len(line) <= MAX_CARD_LINE_CHARS or not words:
            return line
        words = words[:-1]


def compose_card_v3(f: dict[str, Any], *, plan_text: str, record_text: str, rows: list[dict[str, Any]],
                    files: dict[str, str], retries: int, traits: str = "", letter_text: str = "",
                    look: dict[str, Any] | None = None, seed: str = "") -> dict[str, Any]:
    """命盤卡第三版（P13，確定性、不經模型）。
    第 1 行 `verdict`：AI 的判決（外形＋氣質詞＋命盤，`verdict_of`）；第 2 行 `want_line`：PLAN「我想：」之後的願望句；
    第 3 行 `tried_line`：「試的紀錄」裡的改變那一句（做了什麼＋世界留下什麼，原文選句、不是路線）；
    第 4 行 `said_line`：分身在「試的紀錄」最後寫的感想（過濾後）。2、3、4 任何一行找不到根據／過不了防呆就**沒有那一行**。
    `lines`＝第 1 行＋存在的 2、3、4 行（≤4，進檔案庫與手機）；`tv_lines`＝電視字幕兩行（2、3）。"""
    res: dict[str, Any] = {"first_line": first_line(f), "verdict": "", "lines": [], "tv_lines": [], "dropped": [],
                           "present": False, "card_file": False, "want_line": None, "tried_line": None,
                           "said_line": None}
    if not has_any(f):
        return res
    res["verdict"] = verdict_of(f, look, seed)
    others = {n: tx for n, tx in files.items() if n != RECORD_FILE}
    title = title_of(others, f, traits, letter_text)
    res["title"] = title
    res["places"] = visited_places(rows)             # 路線留在檔案庫（不上卡）
    w = want_of(plan_text, traits, f)
    s = said_of(record_text, traits, f)
    # 「試的紀錄」缺或空 ＝ 沒做完：第 3、4 行都不出（第 2 行是 PLAN 的，照出）
    has_record = len(record_text.strip()) >= 30
    td = tried_of(record_text, traits, f, w) if has_record else None
    res["want_line"] = (WANT_PREFIX + w) if w else None
    res["tried_line"] = td
    res["said_line"] = (SAID_PREFIX + s) if s else None
    if plan_text.strip() and not w:
        res["dropped"].append({"key": "want", "why": "no_wish_label_or_filtered"})
    if has_record and not td:
        res["dropped"].append({"key": "tried", "why": "missing_or_filtered"})
    if record_text.strip() and not s:
        res["dropped"].append({"key": "said", "why": "missing_or_filtered"})
    # 雲端命盤卡上限 4 行、第一行＝判決（線 C 約定）：lines[0] 是 verdict，其後是存在的 2、3、4 行
    res["lines"] = [res["verdict"]] + [x for x in (res["want_line"], res["tried_line"], res["said_line"]) if x]
    res["tv_lines"] = [x for x in (res["want_line"], res["tried_line"]) if x]
    res["present"] = len(res["lines"]) > 1
    return res


def polaroid_pick(fz: dict[str, Any] | None) -> str:
    """拍立得印哪一句：第 4 行（試完它說）優先，沒有就第 2 行（它心裡一直想試的是）；兩個都沒有 ⇒ 舊版 `lines[0]`；
    拿掉句尾標點。"""
    d = fz if isinstance(fz, dict) else {}
    for k in ("said_line", "want_line"):
        if d.get(k):
            return polaroid_sentence(str(d[k]))
    ls = [x for x in (d.get("lines") or []) if not str(x).startswith(VERDICT_PREFIX)]
    return polaroid_sentence(str(next(iter(ls), "")))


def retry_ids_of(rd: pathlib.Path) -> tuple[str, ...]:
    """被退回的原因類別（閘門的格號，如 G1＝點名的東西沒打開、G2／G3＝數字的出處）：讀每一次嘗試的逐格結果，只收沒過的格。
    讀不到 ⇒ 空（習慣句退回通用說法，不編原因）。"""
    ids: list[str] = []
    try:
        runj = json.loads((pathlib.Path(rd) / "run_RUN-ON.json").read_text(encoding="utf-8"))
        try:
            from ops.exhibit.twin import grounding_gate as gg
        except ImportError:            # pragma: no cover - 單檔執行
            import grounding_gate as gg   # type: ignore[no-redef]
        for a in runj.get("attempts", []):
            if a.get("accepted") is True or not a.get("visible_path"):
                continue
            vis = json.loads(pathlib.Path(a["visible_path"]).read_text(encoding="utf-8"))
            for fl in vis.get("files", []):
                for c in fl.get("cases", []):
                    if not c.get("ok"):
                        cid, _label = gg.describe(c.get("case"), False, c.get("message") or "")
                        if cid and cid not in ids:
                            ids.append(str(cid))
    except Exception:                                  # noqa: BLE001
        return tuple(ids)
    return tuple(ids)


def accepted_of(rd: pathlib.Path) -> bool | None:
    """這一跑最後一次嘗試有沒有通過（`run_RUN-ON.json`）。讀不到／嘗試還在進行中 ⇒ None（句子不說「過」）。"""
    try:
        runj = json.loads((pathlib.Path(rd) / "run_RUN-ON.json").read_text(encoding="utf-8"))
        at = runj.get("attempts", [])
        if at and isinstance(at[-1].get("accepted"), bool):
            return at[-1]["accepted"]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def attempts_retries(rd: pathlib.Path) -> int:
    """這一跑被閘門退回、重改過幾次＝嘗試數 − 1（`run_RUN-ON.json`）。讀不到 ⇒ 0。"""
    n = 0
    try:
        runj = json.loads((pathlib.Path(rd) / "run_RUN-ON.json").read_text(encoding="utf-8"))
        n = max(0, len(runj.get("attempts", [])) - 1)
    except (OSError, ValueError, TypeError):
        pass
    # 嘗試進行中（twin_agent.sh 每一次嘗試結束時發電視那張卡）run_RUN-ON.json 還沒寫進這一次——
    # 改從事件流學「現在是第幾次嘗試」，退回數＝它 − 1；否則被退回過的跑，電視的卡會少「被退回 N 次」那一句、和手機對不上（整合 e2e M7）。
    try:
        try:
            from ops.exhibit.twin import grounding_gate as gg
        except ImportError:            # pragma: no cover - 單檔執行
            import grounding_gate as gg   # type: ignore[no-redef]
        meta = json.loads((pathlib.Path(rd) / gg.GATE_META_NAME).read_text(encoding="utf-8"))
        _rid, attempt = gg._learn_run(meta["events_path"], meta["task_id"])
        if isinstance(attempt, int) and attempt >= 1:
            n = max(n, attempt - 1)
    except Exception:                                  # noqa: BLE001
        pass
    return n


def build_card(rd: pathlib.Path, ws: pathlib.Path | None, f: dict[str, Any], traits: str = "") -> dict[str, Any]:
    """從 run-dir（步驟紀錄、`letter_final.md`、`run_RUN-ON.json`）與最後的工作區（PLAN.md、成品、「試的紀錄」）生成命盤卡（第三版）。
    **不讀分身寫的任何命盤卡**；PLAN 第一行與「試的紀錄」最後的感想過同一套防呆才上卡。"""
    rd = pathlib.Path(rd)
    try:
        letter = (rd / "letter_final.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        letter = ""
    plan = record = ""
    if ws:
        for name, which in ((PLAN_FILE, "plan"), (RECORD_FILE, "record")):
            try:
                tx = (pathlib.Path(ws) / name).read_text(encoding="utf-8", errors="replace")
            except OSError:
                tx = ""
            if which == "plan":
                plan = tx
            else:
                record = tx
    try:
        look = json.loads((rd / LOOK_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        look = {}
    rows = read_steps(rd)
    files = _top_files(pathlib.Path(ws)) if ws else {}
    retries = attempts_retries(rd)
    # 過程（P13 divine）：四行卡照算、照存 `fortune_card.json`（verdict／want_line／tried_line／said_line，當紀錄）。
    res = compose_card_v3(f, plan_text=plan, record_text=record, rows=rows, files=files,
                          retries=retries, traits=traits, letter_text=letter,
                          look=look if isinstance(look, dict) else {}, seed=rd.name)
    # 產出（2026-10-12 mirror）：給觀眾的 `head`／`lines` 只來自 `mirror_lines`——「像不像你？」＋至多 3 句做事習慣。
    # 系統檔（試的紀錄／PLAN／信…）不算「做出來的東西」，所以標題與證據都不看它們。
    mir = compose_card(f, letter_text=letter, rows=rows, files=_product_files(files), retries=retries, traits=traits,
                       plan_text=plan, retry_ids=retry_ids_of(rd), seed=rd.name, accepted=accepted_of(rd))
    res["lines_v3"] = list(res.get("lines") or [])           # 舊的四行（verdict＋想＋試＋說）：只留紀錄
    res["title"] = mir.get("title")
    res["places"] = mir.get("places") or res.get("places") or []
    res["head"] = MIRROR_HEAD
    res["lines"] = list(mir["lines"])
    res["tv_lines"] = [strip_step(x) for x in mir["lines"]]  # 電視字幕＝同一組句子、不帶步數（≤3 句）
    res["present"] = bool(res["lines"])
    res["want"], res["want_step"] = mir.get("want"), mir.get("want_step")
    if "reading" in mir:
        res["reading"] = mir["reading"]
    if "route" in mir:
        res["route"] = mir["route"]
    try:
        (rd / CARD_JSON_NAME).write_text(json.dumps(res, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
    return res


def polaroid_sentence(line: str) -> str:
    """拍立得主字那一行＝第一句習慣（`lines[0]`）；拿掉句尾的「（第 N 步）」與標點（拍立得不帶步數）。"""
    return strip_step(line).rstrip("。.！!")


def card_md(card: dict[str, Any]) -> str:
    """卡的全文：「像不像你？」＋至多 3 句做事習慣。不放命盤那一行與四行卡（那些是過程／紀錄，不是給觀眾的產出）。"""
    ls = list(card.get("lines") or [])
    return "\n".join([card.get("head") or MIRROR_HEAD] + ls) + "\n" if ls else ""


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
            "verdict": card.get("verdict"), "want_line": card.get("want_line"),
            "tried_line": card.get("tried_line"), "said_line": card.get("said_line"),
            "want": card.get("want"), "want_step": card.get("want_step"),
            "lines": list(card.get("lines") or [])}


def emit(rd: pathlib.Path, phase: str, f: dict[str, Any], lines: list[str] | None = None,
         want: str | None = None) -> bool:
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
        if want and phase == "card":
            row["want"] = want
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
                emit(rd, "card", f, card.get("tv_lines") if "tv_lines" in card else card["lines"], want=card.get("want"))
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
