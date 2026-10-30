"""零設定的證據檢查：agent 說做完的那一刻，只看紀錄，找出「幾乎一定是真的問題」。

這支在架構裡承重什麼：產品原則「裝一次、照常用」的核心（`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md`
§二、§五）。沒有契約、不知道正確答案，所以不判對錯；只問**每個決定有沒有根據**：

| 發現 | 條件 |
|---|---|
| `unsourced` 沒有出處的具體值 | 任務有點名資料；值在這一回合新增或改過的行；文件類交付物；值是 agent 自己打出來的；這個任務看過的東西（步驟輸出、讀到的資料、人打的話）裡找不到它——比對時千分位、幣別、四捨五入／截斷、浮點雜訊、科學記號、×100 的百分比、K／M／B、日期的各種寫法都算同一個值；也不是由看過的表格簡單算得出來的；不在豁免裡 |
| `unread` 點名的檔沒打開 | 人打的話裡**單獨**寫了這個檔，這一回合沒有任何一步讀到它，而且人打的話裡沒有**整段**貼著它的全文（v3.5） |
| `test_claim` 說測過但紀錄對不上 | 最後的訊息說測試通過／build 成功，但沒跑過、最後一次失敗、或通過之後程式碼又改過 |
| `failed_step` 失敗的步驟被略過 | 跑 agent 自己寫的腳本或讀給定資料的那一步失敗；之後才寫出交付物；後來沒有再成功跑同一件事；最後的訊息也沒提 |

其他（沒讀的資料夾成員、沒點名資料時沒出處的值）只進交件說明（`notes`）。
Advisory 項（`copy_of_task`／`skeleton`／`stale_output`／`copy_of_input`／`copy_of_inline`／`claimed_run`／`unfetched`）
也只進交件說明、不作為退回理由，由 `zerostop.pushable_for` 明確排除（docs/UNIVERSAL_TASKS.md §2）。
純函式：只讀病歷，所以可以在任何錄好的病歷上離線重播（量誤報）。

誠實邊界：
1. 「讀到了沒」是**下界**：殼層指令執行中讀了哪些檔看不到，只看指令與腳本的文字裡點名的檔
   （路徑、絕對路徑、檔名，或對資料夾做會讀內容的動作）。所以「沒打開」只在人**單獨點名**的檔上退回。
2. 「找不到出處」＝在**有紀錄的東西**裡找不到；模型從系統提示知道的事（例如今天日期）紀錄裡沒有，
   所以今天與工作階段的日期一律豁免，沒點名資料的任務裡的值只進說明。
3. 比對規則寬（四捨五入、縮寫、簡單推算都算同一個值）：寧可放過編出來但剛好湊得上的值，也不把對的退回。
"""
from __future__ import annotations

import ast
import csv
import datetime as _dt
import difflib
import hashlib
import io
import itertools
import json
import math
import os
import pathlib
import re
import tomllib
from typing import Any

from .blame import Step, Trace
from .recorder import Recorder
from .tools import tool_kind

DOC_EXT = {".md", ".txt", ".rst", ".adoc", ".tex", ".html", ".htm", ".csv", ".tsv", ""}
CODE_HINT_EXT = {".py", ".js", ".ts", ".sh", ".go", ".rs", ".java", ".c", ".cc", ".cpp", ".h",
                 ".rb", ".php", ".cs", ".kt", ".swift", ".json", ".yaml", ".yml", ".toml"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache",
             "dist", "build", ".cache", "target", ".vacant"}
MAX_DELIVERABLE_BYTES = 2 * 1024 * 1024
MAX_DIR_MATERIALS = 30
MAX_VALUES_PER_FILE = 60
MAX_CORPUS_NUMBERS = 5000
GIVEN_INLINE_MAX = 64 * 1024     # 貼在請求裡的檔：只看這麼大以內的（見 Evidence.given_inline）
GIVEN_INLINE_MIN = 80            # 壓過空白之後至少這麼多位元組（UTF-8；中文一字 3）才算得上「貼了全文」（R530 最小的一份 297）
COPY_TASK_MIN_PROMPT = 60        # copy_of_task：正規化後提示詞少於這個長度不報（短提示詞的巧合）
COPY_TASK_MIN_RATIO = 0.8        # copy_of_task：len(提示詞)/len(交付檔) 下限；寧可漏抓不可誤傷（docs/UNIVERSAL_TASKS.md §3）
# 方向 A 通用檢查（2026-09-25）：三者都只進交件說明，`zerostop.pushable_for` 明確排除
SKELETON_MIN_LINES = 2           # skeleton：至少這麼多行是未填占位符才報
SKELETON_MIN_RATIO = 0.5         # skeleton：占位行／非空行 比例下限；完整報告裡一個誠實的 TBD 不會觸發
COPY_INPUT_MIN = 80              # copy_of_input：正規化後少於這個長度的素材不比（巧合）
# stale_output：最終訊息要有一個「產出型」動詞才算「声称產出」；「已確認／Done」不觸發
PRODUCE_CLAIM = re.compile(
    r"已(?:寫入|寫好|寫了|整理|更新|生成|產出|建立|創建|撰寫|產)"
    r"|報告已|written (?:to|into)|has been written|I (?:wrote|created|generated|updated)", re.I)
# copy_of_input：提示詞本身就是複製型任務時，交付檔與素材相同是預期，不報
COPY_CUE = re.compile(r"複製|拷貝|備份|copy|duplicate", re.I)
# copy_of_inline（2026-10-25）：交件（正規化後）是 prompt 的逐字子串、且題目要求改寫
# （整理／摘要／分析／重排……）——agent 把貼在題目裡的數據原樣抄回當成果。
# 既有的兩個檢查都漏掉這種交件：copy_of_task 要求連指示句都在交件裡（比例 ≥0.8），
# unsourced 又把 prompt 裡出現過的數字全數豁免（docs/UNIVERSAL_TASKS.md §3 例子）。
INLINE_COPY_MIN = 120           # copy_of_inline：交件正規化後少於這個字數不報（短答案／短摘錄是正常交件）
TRANSFORM_CUE = re.compile(
    r"整理|摘要|總結|分析|重寫|改寫|改成|重組|匯總|排序|清洗|轉換"
    r"|summar|organiz|analy[sz]|rewrit|reformat|transform|distill", re.I)
# copy_of_inline 的反線索：任務要求逐字保留時，逐字寫出正是預期交件（n3 的「原樣寫入」）
VERBATIM_CUE = re.compile(
    r"原樣|照抄|逐字|一字不差|一字不漏|不要增刪|不改動|保持原文|verbatim|word for word|as-is|unchanged", re.I)
# copy_of_inline 的另一個反線索（2026-10-25，n17 負對照）：抽出型任務點名要哪一段
# （「把『處理時限』一節寫入…」「摘出…寫入…」），agent 把該段逐字寫出正是預期交件，
# 不是照抄當成果的 lazy echo。寧可漏抓（這種 lazy echo 可能漏報）不可誤傷。
EXTRACT_CUE = re.compile(r"摘出|抽出|摘錄|擷取|挑出|extract|pull out", re.I)
# copy_of_inline 的反線索（2026-10-26，清單負對照）：題目措辭點名**清單型輸出**
# （動詞在前、編號/清單/列表/列點/numbered list/bullet points 在 12 字內）——這時
# 貼進 prompt 的資料若**已經就是**清單形狀，agent 逐字寫出該清單區塊正是題目要求
# 的交件（reformat 是 no-op），不是照抄當成果的 lazy echo。字集刻意不收「要點」
# （散文要點仍是 lazy echo 形狀，test_lfake_cross_prompt_join_is_caught 要抓）
# 也不收裸 "list"（避免 list.txt 這類檔名誤觸）；方向性（動詞在前）避免內容描述裡
# 的「清單」誤觸。寧可漏抓（這種 lazy echo 可能漏報）不可誤傷。
LIST_REQ_CUE = re.compile(
    r"(?:整理|重組|轉換|改成|改寫|重寫|匯總|排序|輸出|寫成|寫入|列出|列點|organiz\w*|reformat\w*|transform\w*)"
    r"[^。！？!?\n]{0,12}?"
    r"(?:編號|清單|列表|列點|numbered[ -]?list|list items?|bullet[ -]?points?)",
    re.I)
# 清單項行：行首是編號（1. / 1、 / (2)）或符號（- / * / •）標記、後接非空白內容。
LIST_ITEM_LINE = re.compile(r"^(?:[-*+•·]|\d{1,3}\s*[.)、．:：]|[（(]\d{1,3}[)）])\s*\S")
# claimed_run（2026-10-26，第 90 輪）：方向 A「跑過沒」——最終訊息以過去式声称「執行/跑了」
# 某條反引號命令，但整份命令記錄查無。這是 ASSIGNMENT 點名三類裡唯一沒有專屬檢查的
# （failed_step 只抓「跑過且失敗」、test_claim 限測試/建置；「声称跑過但沒跑」兩者都漏）。
# 三層保守濾網（寧可漏抓、不可誤傷）：
#   1) 線索只收過去式（ran/executed/跑了/跑過/跑完/執行…）；「執行緒」不觸發；
#   2) 反引號 span 的第一個字必須是已知 CLI 名稱（RUN_CLAIM_TOOLS）——「I ran the `tests`」
#      這種散文後設不觸發；有參數的命令形（≥2 詞）也走同一份清單；
#   3) 鄰窗有建議/解釋措辭（you can / 可以 / 若… / 請…）＝不是在声称自己跑過 → 不觸發。
# 「跑過沒」的證據搜**整個 workspace 記錄**（含先前回合、子 agent；大小寫不敏感子串：
# pip→pip3、/usr/bin/pandoc 都算跑過）——寧可漏抓跨 session 的造假，不可誤傷跨回合引用。
# 只進交件說明：`zerostop.pushable_for` 明確排除（docs/UNIVERSAL_TASKS.md §2）。
RUN_CLAIM_CUE = re.compile(
    r"\b(?:ran|executed)\b|跑了|跑過|跑完|執行過|執行完|執行(?!緒)|执行(?!绪)", re.I)
RUN_CLAIM_SUGGEST = re.compile(
    r"\b(?:you|one|they|it|this|that)\s+(?:can|could|should|may|might|would|will)\b"
    r"|\b(?:please|help)\s+(?:me\s+)?(?:run|execute)\b"
    r"|\bto\s+(?:run|execute)\b|\bfor\s+running\b|\bhow\s+to\s+run\b"
    r"|\bif\s+(?:you|needed|need)\b"
    r"|建議|試試|試看看|可以|可用|請|請你|請幫我|麻煩|若|如果|假如|倘若", re.I)
# 反引號 span：首詞是 CLI 名稱字元集（2–20 字）＋可選參數；URL（含 ://）匹配不到。
RUN_CLAIM_SPAN = re.compile(r"`([A-Za-z][A-Za-z0-9_.+-]{1,19})(?:\s+[^`]*)?`")
# 單詞 span 的白名單：已知 CLI/工具名。故意不收通用英文詞（tests/file/…）。
RUN_CLAIM_TOOLS = frozenset({
    "pandoc", "wkhtmltopdf", "weasyprint", "prince", "a2ps", "ps2pdf", "qpdf", "pdftk",
    "mutool", "ghostscript", "gs", "ocrmypdf", "tesseract", "convert", "magick",
    "mogrify", "inkscape", "gimp", "libreoffice", "soffice", "blender",
    "ffmpeg", "ffprobe", "sox", "lame", "flac", "wav2vec",
    "curl", "wget", "ssh", "scp", "sftp", "rsync",
    "jq", "zip", "unzip", "tar", "gzip", "gunzip", "xz", "zstd", "lz4", "7z",
    "git", "pip", "pip3", "python", "python3", "node", "npm", "npx", "yarn", "pnpm",
    "cargo", "rustc", "make", "cmake", "gcc", "g++", "clang", "docker", "podman",
    "apt", "apt-get", "yum", "dnf", "brew", "pacman", "snap", "flatpak",
    "awk", "sed", "grep", "rg", "fd", "find", "ls", "cat", "head", "tail", "wc",
    "sort", "uniq", "cut", "tr", "xargs", "file", "stat", "du", "df", "which",
    "mkdir", "touch", "cp", "mv", "rm", "ln", "chmod", "kill", "pkill", "nohup",
    "screen", "tmux", "watch", "top", "htop", "ps", "free", "uname", "whoami",
    "pytest", "tox", "nox", "mypy", "ruff", "flake8", "black", "eslint", "prettier",
    "java", "jar", "mvn", "gradle", "go", "swiftc", "kotlin", "bc", "date", "cal",
    "env", "printenv", "echo", "printf", "basename", "dirname", "readlink", "realpath",
})

# unfetched（2026-10-28，第 100 輪）：方向 A「抓過沒」—— ASSIGNMENT 點名三類（跑過沒／數字追得到／
# 抓過沒）最後一類沒有專屬檢查的缺口。任務點到一個 URL、鄰窗有抓取類線索（fetch/download/retrieve/
# grab/pull/obtain/access/visit/open/scrape/load/read、下載/抓取/獲取/取得/訪問/打開/拉取/讀取），
# 但整份記錄沒有任何一步碰到該 URL（任何步驟的輸入或輸出裡都查無同 key 的 URL），且最終訊息沒有
# 老實說連不上 → advisory 發現。兩層保守濾網（寧可漏抓、不可誤傷，docs/UNIVERSAL_TASKS.md §3）：
#   1) 抓取線索：線索必須在 URL ±60 字元內——參考連結／註腳引用（"see https://…"、polyglot_py
#      goal.md 樣本集裡的維基註腳）不觸發；
#   2) 誠實豁免：最終訊息裡「連不上／404／逾時」線索在該 URL ±80 內，或整段訊息有「fetch 動詞
#      附近說連不上」（URL 不必重提）→ 不報——老實說「連不上」是合規結果，不是缺紀錄。
# 證據面：URL（host＋第一路徑段，小寫、去 www.）出現在**任何一步**的輸入或輸出就算碰到——
# shell curl/wget、fetch 工具呼叫、腳本裡的 URL、甚至把 URL 貼進報告都算（寧漏勿誤）。
# Advisory only：`zerostop.pushable_for` 明確排除（docs/UNIVERSAL_TASKS.md §2）。
URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]{}，。；、（）]+")
FETCH_CUE = re.compile(
    r"\b(?:fetch|download|retriev\w*|grab|pull|obtain|access|visit|open|scrape|load|read)\w*"
    r"|下載|抓取|獲取|取得|訪問|打開|拉取|讀取", re.I)
UNFETCHED_UNAVAILABLE = re.compile(
    r"\bunreachable\b|\bunavailable\b|couldn'?t|could not|failed to|timed? ?out|time-?out"
    r"|\b404\b|no response|not responding|connection (?:error|refused|reset)"
    r"|無法(?:連接|連線|訪問|打開|存取|取得)|連線失敗|逾時|超時|連不上|打不開"
    r"|抓(?:取)?(?:失敗|不到)|下載(?:失敗|不到)|取不到", re.I)

# claimed_write（2026-10-28，第 125 輪）：方向 A「寫過沒」——與 claimed_run／unfetched 同族的
# 「誠實性」檢查。最終訊息以過去式声称「寫入／存成／產生」某個反引號檔名，但整份記錄查無
# 該檔（任何一步的輸入或輸出都碰不到它的 basename），且該檔在最新索引裡也不存在 → advisory 發現。
# 填補缺口：missing_output 只抓「任務點名要的檔」、stale_output 只抓「舊檔當成果」；「沒被要求、
# 卻聲稱已寫、實際不存在」兩邊都漏。四層保守濾網（寧可漏抓、不可誤傷，docs/UNIVERSAL_TASKS.md §3）：
#   1) 線索只收過去式寫檔動詞（wrote/written/saved/created/generated/updated/compiled/exported、
#      寫入/寫了/寫好/存成/產生/生成/更新/建立/創建）；現在式／祈使式（write／請寫／幫我寫）不觸發；
#   2) 反引號 span 必須是「檔名形」（含副檔名，如 report.md）——URL（含 ://）、純詞（tests／file）
#      因字元集／副檔名要求匹配不到；
#   3) 鄰窗有建議／解釋／否定措辭（you can／可以／請／not／未／沒有）＝不是在声称自己寫過 → 不觸發；
#   4) 證據面：檔名 basename 出現在**任何一步**的輸入或輸出、或該檔在最新索引裡存在
#      → 視為已記錄 → 不報（寧可漏抓跨 session／跨回合的造假，不可誤傷真實寫檔）。
# Advisory only：`zerostop.pushable_for` 明確排除（docs/UNIVERSAL_TASKS.md §2）。
WRITE_CLAIM_CUE = re.compile(
    r"\b(?:wrote|written|saved|created|generated|updated|compiled|exported)\b"
    r"|寫入|寫了|寫好|寫進|寫成|寫到|存成|存到|存為|已寫|已存|產生|生成|更新|建立|創建", re.I)
WRITE_CLAIM_SUGGEST = re.compile(
    r"\b(?:you|one|they|it|this|that)\s+(?:can|could|should|may|might|would|will)\b"
    r"|\b(?:please|help)\s+(?:me\s+)?(?:write|save|create|generate|update)\b"
    r"|\bto\s+(?:write|save|create|generate)\b|\bfor\s+(?:writing|saving|creating|generating)\b"
    r"|\bhow\s+to\s+(?:write|save|create)\b"
    r"|\bif\s+(?:you|needed|need)\b"
    r"|建議|試試|試看看|可以|可用|請|請你|請幫我|麻煩|若|如果|假如|倘若", re.I)
WRITE_CLAIM_NEGATION = re.compile(
    r"\b(?:not|never|no|neither|nor|without|did\s+not|didn't|have\s+not|haven't|has\s+not|hasn't|was\s+not|wasn't|were\s+not|weren't)\b"
    r"|沒有|沒寫|未寫|未存|未產生|未生成|未建立|未創建|未更新|並未|不寫|不產生|不生成|無需產生|無須產生", re.I)
# 反引號 span：檔名形（字母／數字／._/-/／＋ 點＋ 1–8 字副檔名）。URL（含 ://）因 ':' 不在字元集而匹配不到。
WRITE_CLAIM_SPAN = re.compile(r"`([A-Za-z0-9_./-]+?\.[A-Za-z0-9]{1,8})`")


def _url_key(u: str) -> str:
    """URL 比對 key：host（小寫、去 `www.`）＋第一路徑段（小寫）。
    query/fragment 差異不影響比對（抓 `/v1/rates?d=1` 就算碰到 `/v1/rates`）。"""
    m = re.match(r"https?://([^/]+)(?:/([^/?#]*))?", u.strip())
    if not m:
        return u.strip().lower()
    host = m.group(1).lower().split("@")[-1].removeprefix("www.")
    return f"{host}/{(m.group(2) or '').lower()}"


def _is_placeholder_line(line: str) -> bool:
    """單獨一行就是未填占位符（先去掉行首的清單／標題／編號標記）。
    只認整行完全匹配的嚴格形狀：`TBD`/`TODO`、`[待填]` 這類短括號、`{{…}}`、`___`、`待補`；
    「上線日期：TBD（待供應商確認）」這種一行裡有其它內容的不算。
    括號占位符只認**雙**括號 `{{…}}`：單括號 `{…}` 是 JSONL 行／字典／集合字面量等
    資料值形狀，當占位符會誤報（volumes.jsonl 回歸）；寧可漏抓不可誤傷。"""
    s = re.sub(r"^(?:[-*+]|#{1,6}|\d+[.)、])\s*", "", line.strip())
    if not s:
        return False
    return bool(
        re.fullmatch(r"TBD|TODO|FIXME", s, re.IGNORECASE)
        or re.fullmatch(r"\[[^\[\]]{1,20}\]", s)
        or re.fullmatch(r"\{\{[^{}]{1,30}\}\}", s)
        or re.fullmatch(r"_{3,}", s)
        or re.fullmatch(r"待(?:填|補|定|確認|續|完成)", s)
    )
_CJK = r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
_CJK_GAP = re.compile(rf"(?<={_CJK})\s+(?={_CJK})")


def _collapse(text: str) -> str:
    """把所有空白壓成一個空格；兩個中日韓字之間的換行／空白直接拿掉（中文換行不代表有空格）。"""
    return " ".join(_CJK_GAP.sub("", text).split())


def _edge(a: str, b: str) -> bool:
    """a|b 之間是不是一個字的邊界：空白，或兩邊都是中日韓字（`_collapse` 拿掉了它們之間的換行）。"""
    return a == " " or b == " " or bool(re.match(_CJK, a) and re.match(_CJK, b))


def _contains_whole(haystack: str, needle: str) -> bool:
    """needle 整段出現在 haystack 裡、前後是字的邊界或頭尾（兩邊都已經 `_collapse` 過）。"""
    i = haystack.find(needle)
    while i >= 0:
        j = i + len(needle)
        if (i == 0 or _edge(haystack[i - 1], needle[0])) and \
                (j == len(haystack) or _edge(needle[-1], haystack[j])):
            return True
        i = haystack.find(needle, i + 1)
    return False


def _is_list_block(text: str) -> bool:
    """交件是不是清單區塊：每行非空行都以清單項標記開頭（編號 1./1、/(2) 或符號 -/*），
    或首行是短標籤（≤ 30 字、無句末標點）其餘皆清單項（「重點工作清單：\n1. …」形狀）。
    只給 `LIST_REQ_CUE`（題目點名清單型輸出）配合用：題目要求清單形狀、交件就是清單
    形狀時，逐字是預期交件（2026-10-26 清單負對照）。散文（甲：…）不是清單區塊。"""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    if all(LIST_ITEM_LINE.match(ln) for ln in lines):
        return True
    return (len(lines) >= 2 and len(lines[0]) <= 30
            and not re.search(r"[。！？!?]$", lines[0])
            and all(LIST_ITEM_LINE.match(ln) for ln in lines[1:]))


def _union_candidate(raws: list[str], prompts: list[str], joined: str) -> str | None:
    """N 元 union（2–3 元；≥4 元仍是註冊漏，寧漏勿誤）：N 份逐字文本按任一順序拼接、
    collapse 後是 prompt（或整場對話）的逐字連續子串、且 ≥ `INLINE_COPY_MIN`。
    命中回 detail（與 round 83 成對版同文），否則 None。拼接從原文重組後再 collapse
    （各自 collapse 後直接拼會在 CJK-ASCII 交界丟空格，見樣本自檢）。"""
    for perm in itertools.permutations(raws):
        cc = _collapse("\n".join(perm)).lower()
        if len(cc) < INLINE_COPY_MIN:
            continue
        if any(c and cc != c and cc in c for c in prompts):
            return ("verbatim block split across the named files; "
                    "the task asked for a reworking")
        if joined and cc != joined and cc in joined \
                and all(cc != pt for pt in prompts if pt):
            return ("verbatim block spanning the whole conversation, "
                    "split across the named files; "
                    "the task asked for a reworking")
    return None


ASSUMPTION_WORDS = re.compile(
    r"\b(assum\w*|estimat\w*|approx\w*|placeholder|tbd|tbc|e\.g\.|for example|example|sample|"
    r"hypothetical|rough|ballpark|forecast\w*|project(ed|ion)|scenario|target\w*|goal|propos\w*|"
    r"plan(ned)? to|aim\w*|objective|kpi)\b|假設|估計|範例|待定|預估|暫定|目標|建議", re.I)
EXEMPT_HEADINGS = re.compile(r"^\s{0,3}#{1,6}\s*(unverified|assumptions?|open questions|tbd|"
                             r"未驗證|假設|待確認)\b", re.I)
READ_VERBS = re.compile(r"\b(python3?|node|awk|grep|rg|cat|head|tail|sed|jq|less|more|read_csv|"
                        r"read_json|open|load|json\.load|pd\.|pandas|csv\.|readFile|fs\.)", re.I)
# 純顯示指令（從命令開頭）：只把內容印出來、不含查詢/轉換。用於「已消費資料上的重覆 probe」判定。
DISPLAY_ONLY_PROBE = re.compile(
    r"^\s*(head|tail|cat|less|more|wc|od|xxd|strings|stat)(\s|$)", re.I)
# 查詢/轉換動詞：出現即不視為純顯示（grep 失敗是未滿足的查詢，不是重覆 probe）。
QUERY_IN_CMD = re.compile(
    r"\b(grep|egrep|fgrep|awk|sed|jq|xargs|perl|ruby|python3?|node|cut|sort|uniq|tr|tee)\b", re.I)
PROBE_CMD = re.compile(r"^\s*(pip3?|python3? -m pip|uv|npm|pnpm|yarn|npx|apt(-get)?|brew|which|"
                       r"command|type|ls|find|tree|stat|file|wc|du|df|curl|wget|git|echo|pwd|"
                       r"env|printenv|test|\[)\b")
IMPORT_PROBE = re.compile(r"python3?\s+-c\s+['\"]\s*import\s+[\w., ]+['\"]\s*$")
RUNNERS = re.compile(r"\b(pytest|python3? -m (unittest|pytest)|unittest|tox|nox|"
                     r"(npm|pnpm|yarn)( run)? (test|build|lint|typecheck)|jest|vitest|mocha|"
                     r"go test|cargo (test|build|check)|make (test|check|lint)|mvn|gradle|"
                     r"dotnet test|rspec|phpunit|ctest|bazel test)\b")
CLAIMS = re.compile(r"((all )?tests? (now )?(pass|passed|passing|are green|succeed\w*)|test suite "
                    r"(passes|is green)|(build|lint|typecheck)s? (pass\w*|clean|succeed\w*)|"
                    r"tested and (works|passes)|測試(全部)?通過|測試都過)", re.I)
#: v3.7：任意的測試腳本（`sh run_tests.sh`、`bash test.sh`、`./run_tests.sh`、`python tests/test_x.py`、`node test.js`）也是跑測試——
#: 腳本的檔名以 test 開頭或結尾、是一個字（run_tests.sh、test_x.py、x_test.js、tests.sh；不是 latest、contest、generate_test_data），而且在**指令的位置**被執行
#: （直譯器或 `./`、`/…`），不是被讀、被列、被寫（`cat ./run_tests.sh`、`ls ./tests`、heredoc 裡的字）。見 `is_test_script_run`。
#: Colab 程式題 920 題：455／472 次退回是不認這種指令的誤退
TEST_BASENAME = re.compile(r"^(?:(?:run|all)[_-]?)?tests?(?:[_.-][\w.-]+)?$|^[\w.-]+[_.-]tests?$", re.I)
SCRIPT_INTERP = re.compile(r"^(?:(?:ba|z|da)?sh|python3?(?:\.\d+)?|node|nodejs|bun|deno|ruby|perl)$")
SCRIPT_EXT = {".sh", ".bash", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl"}
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b", re.S)
_SEGMENT = re.compile(r"&&|\|\||;|\||\n|\$\(|`|\(")
_PREFIX = re.compile(r"^(?:(?:cd\s+\S+|timeout\s+\S+|time|sudo|nice|env|command|exec|\w+=\S*)\s+)*")
#: 測試的總結行：失敗要有**非零**的數字（「0 failed」「FAIL: 0」「failures=0」不是失敗）；名詞只收測試的（不收「1 row failed to parse」）
FAIL_OUT = re.compile(r"(FAILED|failures=[1-9]|errors=[1-9]|Traceback \(most recent call last\)|\bFAIL\b(?!:?\s*0\b)|"
                      r"\b[1-9]\d* failed\b|npm ERR!|error\[E\d+|test result: FAILED|BUILD FAILED|"
                      r"Tests:.*\b[1-9]\d* failed|\bError:|Exception:|command not found|No such file)")
PASS_OUT = re.compile(r"(\bOK\b\s*$|\b\d+ passed\b|test result: ok|BUILD SUCCESS|\bPASS\b)", re.M)
_TEST_NOUN = r"(?:tests?|checks?|cases?|specs?|assertions?|examples?)(?:\(s\))?"
PASS_OUT_2 = re.compile(r"(\b0 " + _TEST_NOUN + r" failed\b|\ball (?:\d+ )?" + _TEST_NOUN + r" (?:have )?passed\b|"
                        r"\bfail(?:ed|ures?)?:?\s*0\b)", re.I)
FAIL_OUT_2 = re.compile(r"\b[1-9]\d* " + _TEST_NOUN + r" failed\b", re.I)


def is_test_script_run(cmd: str) -> bool:
    """v3.7：這個殼層指令有沒有**執行**一支測試腳本（見 `TEST_BASENAME`）。heredoc 的內容不算指令；
    每一段（`&&`、`;`、`|`、換行、`$(`）去掉 `cd X`／`timeout N`／`env`／`VAR=…` 之後，開頭要是直譯器＋腳本、或 `./`、`/` 開頭的可執行檔。"""
    body = _HEREDOC.sub(" ", cmd or "")
    for seg in _SEGMENT.split(body):
        seg = _PREFIX.sub("", seg.strip())
        words = seg.split()
        if not words:
            continue
        target = None
        if SCRIPT_INTERP.match(words[0]):
            rest = [w for w in words[1:] if not w.startswith("-")]
            if rest and _ext(rest[0].strip("'\"")) in SCRIPT_EXT:
                target = rest[0]
        elif words[0].startswith(("./", "/")):
            target = words[0]
        if target:
            base = target.strip("'\"").rsplit("/", 1)[-1]
            stem = base.rsplit(".", 1)[0] if _ext(base) in SCRIPT_EXT else base
            if TEST_BASENAME.match(stem):
                return True
    return False


MENTIONS_FAILURE = re.compile(r"\b(fail\w*|error\w*|crash\w*|could not|couldn't|did not run|"
                              r"not run|broke|broken)\b|失敗|錯誤", re.I)
#: 人要求寫出的檔：「寫／存／輸出 … 到 PATH」，或 `output path` 這類標籤下一行的路徑
OUTPUT_VERB = re.compile(r"\b(write|writes|save|store|put|output|export|generate|create|produce|"
                         r"place|dump|record|list|寫入|寫到|存到|存成|輸出到|產生)\b", re.I)
OUTPUT_PREP = re.compile(r"(?:\b(?:to|in|into|as|at)\b|到|至|成)\s*(`[^`\n]+`|\"[^\"\n]+\"|'[^'\n]+'|[^\s,;()]+)")
OUTPUT_LABEL = re.compile(r"output[ _-]?(?:path|file)\b[^\n]*\n(?:[ \t]*\n)*[ \t]*(`[^`\n]+`|[^\s]+)",
                          re.I)
#: v3.7：說明檔裡的交付物（`asked_outputs`）。只讀人**要 agent 照著做**的說明檔：檔名本身是說明（contract、spec、task…），
#: 或人的那一句話裡有「照著做／依照／as described in」這類字；要摘要、要修改、要看的檔不讀（那是資料或要改的東西）
INSTRUCTION_EXT = {".md", ".txt", ".rst"}
INSTRUCTION_STEM = re.compile(r"^(?:contract|spec|specification|task|tasks|instructions?|requirements?|goal|assignment|"
                              r"brief|todo|deliverables?)$", re.I)
INSTRUCTION_CUE = re.compile(r"(\bfollow\w*|\bdo what\b|\bwhat (?:it|they) says?\b|\bas (?:described|specified|instructed|stated|written) in\b|"
                             r"\baccording to\b|\bper\b|\binstructions?\b|\bthe task (?:it|they|that it|described)\b|"
                             r"\bcomplete the task\b|\bcarry out\b|照著?做|照上面|依照|按照|依說明)", re.I)
INSTRUCTION_MAX_BYTES = 64 * 1024
INSTRUCTION_MAX_OUTPUTS = 3                  # 一份說明檔寫出超過這麼多個「寫到 X」＝它是資料（紀錄、日誌），全部不算
#: 說明檔裡的一句話要是**對 agent 的命令**：動詞在句首／項目開頭，或是「you must／should／need to …」；
#: 否定、可有可無、舉例的都不算（「Do not write to X」「Optionally write tests to X」「e.g. write to X」）
DOC_IMPERATIVE_PRE = re.compile(r"^(?:[-*+]|\d+[.)])?\s*(?:please\s+)?(?:(?:you|u)\s+(?:must|should|need to|have to|are to|will)\s+"
                                r"(?:also\s+)?|make sure (?:to|you)\s+|be sure to\s+|remember to\s+)?$", re.I)
DOC_NOT_REQUIRED = re.compile(r"(\bnot\b|n't\b|\bnever\b|\bavoid\b|\boptional\w*|\bmay\b|\bmight\b|\bcan\b|\bcould\b|"
                              r"\bif you (?:like|want|wish)\b|\be\.g\.|\bfor example\b|\bexample\b|\bsuch as\b|"
                              r"不要|不用|不必|勿|別|可以|例如|比如)", re.I)
DOC_LABEL = re.compile(r"(?:^|\n)[ \t]*(?:[-*+][ \t]*)?(?:\*\*)?(?:deliverables?|submission|submit|answer file|output file)(?:\*\*)?"
                       r"[ \t]*[:：]?[ \t]*(`[^`\n]+`|\"[^\"\n]+\"|[^\s,;()]+)", re.I)
#: 中文的「寫到／存成／放在 X」：動詞本身已經帶了介系詞，路徑緊接在後（v3.7；舊的 `\b` 在中文字之間永遠不成立）
CJK_OUTPUT = re.compile(r"(?:寫入|寫到|寫在|存到|存成|存在|輸出到|輸出成|放到|放在)\s*(`[^`\n]+`|「[^」\n]+」|\"[^\"\n]+\"|[^\s,;()，。；、]+)")
FILE_LIKE = re.compile(r"^(?!.*://)[\w./~-]*[\w-]\.[A-Za-z0-9]{1,10}$")
DIR_CUE_RE = re.compile(r"\b(?:in|from|under|inside)\s+(?:the\s+)?([A-Za-z0-9_.-]+)\s+"
                        r"(?:directory|folder|dir)\b", re.I)
AT_TAG_REQ_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)\[")
AT_TAG_VAL_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)\[([^\[\]\n]+)\]")
REQ_FUNC_RE = re.compile(
    r"(?:(?:define|write|implement|create)\s+(?:a\s+)?(?:top-level\s+)?(?:async\s+)?(?:function|class)\s+"
    r"(?:(?:named|called)\s+)?`(?:(?:async\s+)?def\s+|class\s+)?([A-Za-z_]\w*)`|"
    r"`(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(|"
    r"\bsolution\.([A-Za-z_]\w*)\s*\()",
    re.I,
)
REFUSAL_FILE_RE = re.compile(
    r"^\s*(?:I\s+(?:cannot|can't|could\s+not|couldn't|am\s+unable\s+to)\s+"
    r"(?:determine|find|compute|answer|calculate|access|read)|"
    r"Sorry,\s+I\s+(?:cannot|can't|could\s+not|am\s+unable))\b",
    re.I,
)
PROSE_ANSWER_RE = re.compile(
    r"^\s*(?:#{1,6}\s+\S|The\s+(?:final\s+)?answer\s+is\b|Based\s+on\s+the\b|Here\s+is\s+the\b)",
    re.I,
)
CONFLICT_MARKER_RE = re.compile(r"^<<<<<<< .*\n(?:.*\n)*?^=======\r?$\n(?:.*\n)*?^>>>>>>> ", re.M)
#: 執行程式的指令開頭（輸出是計算結果，不是回頭讀檔）
INTERPRETER = re.compile(r"^\s*(?:cd\s+\S+\s*&&\s*)?(python[0-9.]*|node|nodejs|deno|bun|bash|sh|zsh|ruby|"
                         r"perl|Rscript|julia|php|go\s+run)\b")
#: 找不到就回 1 的搜尋指令
SEARCH_CMD = re.compile(r"^\s*(grep|egrep|fgrep|zgrep|rg|ag)\b")
SEARCH_ERR = re.compile(r"No such file|Permission denied|Is a directory|(?:^|\n)\s*(grep|rg|ag): |"
                        r"invalid|unrecognized option", re.I)
#: 只換目錄或列出檔名的指令（連同它的參數）：不算讀了資料夾裡的內容
_NOT_A_DIR_READ = re.compile(r"(?<![\w.-])(cd|pushd|ls|tree|du|stat)\b[^;&|\n]*")
ONLY_ANSWER = re.compile(r"\b(only|just) (the )?(final )?answer\b|write only\b|\bONLY\b", re.I)

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], 1)}
MONTHS.update({m[:3].lower(): i for m, i in list(MONTHS.items())})
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_RES = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(" + _MON + r")\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b", re.I), "mdy"),
    (re.compile(r"\b(\d{1,2}) (" + _MON + r")\.?,? (\d{4})\b", re.I), "dmy"),
    (re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"), "ymd"),
]
NUM_RE = re.compile(
    r"(?<![\w.#/-])(?P<cur>US\$|NT\$|\$|€|£|¥|USD ?|EUR ?|TWD ?)?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
    r"(?P<suf>\s?%|\s?(?:[KMB]|bn|mn|million|billion|thousand)\b)?(?![\w.]*\d)", re.I)
VERSION_RE = re.compile(r"\bv?\d+\.\d+\.\d+|\b[vV]\d+(\.\d+)*\b|\bpython ?\d\.\d+", re.I)
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")


# ── small helpers ───────────────────────────────────────────────────────

def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def _skipped(path: str) -> bool:
    return any(part in SKIP_DIRS for part in path.split("/")[:-1])


def _parse_date(m: re.Match, kind: str) -> _dt.date | None:
    try:
        if kind == "ymd":
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if kind == "mdy":
            return _dt.date(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
        return _dt.date(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
    except (ValueError, KeyError):
        return None


def dates_in(text: str) -> list[tuple[str, _dt.date, int, int]]:
    out = []
    for rx, kind in DATE_RES:
        for m in rx.finditer(text):
            d = _parse_date(m, kind)
            if d is not None:
                out.append((m.group(0), d, m.start(), m.end()))
    return out


class Num:
    """寫出來的一個數：值、小數位數、是不是百分比、縮寫的倍數。"""

    def __init__(self, raw: str, value: float, decimals: int, pct: bool, scale: float):
        self.raw, self.value, self.decimals, self.pct, self.scale = raw, value, decimals, pct, scale

    def candidates(self) -> list[tuple[float, float]]:
        """(要比對的值, 容許差)：四捨五入到寫出的位數、截斷、百分比與縮寫都換算回原單位。"""
        tol = 0.5 * 10 ** (-self.decimals) + 1e-9
        out = [(self.value * self.scale, tol * self.scale)]
        if self.pct:
            out.append((self.value / 100.0, tol / 100.0))
        elif 0 < abs(self.value) <= 100:
            # 支援未標註 % 但題目要求比例／百分比的同源數值換算（例如 49.67 對應 0.4967）
            out.append((self.value / 100.0, tol / 100.0))
        return out


def numbers_in(text: str) -> list[tuple[Num, int, int]]:
    out = []
    bad = [(m.start(), m.end()) for m in VERSION_RE.finditer(text)] + \
          [(m.start(), m.end()) for m in TIME_RE.finditer(text)] + \
          [(s, e) for _, _, s, e in dates_in(text)]
    for m in NUM_RE.finditer(text):
        if any(s <= m.start() < e for s, e in bad):
            continue
        raw_num = m.group("num")
        try:
            v = float(raw_num.replace(",", ""))
        except ValueError:
            continue
        dec = len(raw_num.split(".")[1]) if "." in raw_num and "e" not in raw_num.lower() else 0
        suf = (m.group("suf") or "").strip().lower()
        pct = suf == "%"
        scale = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "b": 1e9,
                 "bn": 1e9, "billion": 1e9}.get(suf, 1.0)
        out.append((Num(m.group(0).strip(), v, dec, pct, scale), m.start(), m.end()))
    return out


def _significant(n: Num) -> bool:
    """值得查的數：有幣別／百分比／縮寫，或至少兩位有效數字；不查 0–10 的整數、單獨的年份。"""
    affix = n.pct or n.scale != 1.0 or bool(re.match(r"\D", n.raw))
    if affix:
        return True
    if n.decimals == 0 and float(n.value).is_integer():
        iv = int(n.value)
        if 0 <= iv <= 10 or 1900 <= iv <= 2100:
            return False
    digits = re.sub(r"\D", "", n.raw.split("e")[0].split("E")[0]).lstrip("0")
    return len(digits) >= 2


def _extract_test_hint(outp: str, err: str = "") -> str | None:
    """從測試輸出提取最後一個失敗測試名稱與斷言／例外摘要（最多 240 字元）。

    - 以「最後一個失敗測試」為主體（相容舊行為）；多個測試失敗時附註其餘名字
      （>4 個只給計數），避免 agent 只看到一個失敗而忽略其餘（2026-10-29 e002 C-arm）。
    - 多行斷言訊息（如 set diff 的缺失項目、list diff 的差異元素）附帶其後細節行。
    - 隱去敏感本機路徑與重複總結行。
    """
    if not outp:
        return None
    err_clean = (err or "").strip()
    lines = [ln.strip() for ln in outp.splitlines() if ln.strip()]
    # 結構行＝區塊邊界／traceback／總結行：不是斷言訊息的細節行
    STRUCT = re.compile(
        r"^(?:=+$|-+$|\?\s|Traceback|During handling|The above exception|"
        r"Ran\s+\d+|FAILED\b|FAIL:|ERROR:|E\s|File\s|>\s"
        r"|\S+\.py:\d+:|Command exited with code)")
    blocks: list[dict[str, Any]] = []  # 每個失敗區塊 {name, exc, detail[]}
    cur: dict[str, Any] | None = None
    for ln in lines:
        if ln == err_clean or ln.startswith("Command exited with code"):
            continue
        if re.match(r"^(?:FAILED\s*\(|=+\s*\d+|\d+\s+failed\b)", ln, re.I):
            continue
        m_u = re.match(r"^(?:FAIL|ERROR):\s+([A-Za-z0-9_]+)", ln)
        if m_u:
            cur = {"name": m_u.group(1), "exc": None, "detail": []}
            blocks.append(cur)
            continue
        m_p = re.match(r"^FAILED\s+\S+?::([A-Za-z0-9_]+)(?:\s+-\s+(.*))?$", ln)
        if m_p:
            cur = {"name": m_p.group(1),
                   "exc": m_p.group(2).strip() if m_p.group(2) else None, "detail": []}
            blocks.append(cur)
            continue
        clean_ln = re.sub(r"^E\s+", "", ln)
        if re.search(r"^(?:[A-Za-z_]\w*(?:Error|Exception)\b|assert\s+|Expected\b)", clean_ln):
            if cur is None:
                cur = {"name": None, "exc": None, "detail": []}
                blocks.append(cur)
            cur["exc"] = clean_ln
            cur["detail"] = []
            continue
        if cur is not None and cur["exc"] is not None and not STRUCT.match(ln):
            cur["detail"].append(ln)
    if not blocks:
        return None
    last = blocks[-1]
    if last["name"] and last["exc"]:
        raw = last["exc"] if last["name"] in last["exc"] else f"{last['name']}: {last['exc']}"
    else:
        raw = last["exc"] or last["name"]
    if not raw or raw == err_clean:
        return None
    # 多個測試失敗：附註其餘失敗測試名字（>4 個只給計數），讓 agent 知道「不止一個」
    others = [b["name"] for b in blocks if b["name"] and b["name"] != last["name"]]
    if others:
        suffix = ("also failing: " + ", ".join(others)) if len(others) <= 4 \
            else f"+{len(others)} other failing tests"
        raw = f"{raw}; {suffix}"
    # 斷言的後續細節行（set/list diff 等）附在摘要後
    if last["detail"]:
        detail_str = "; ".join(last["detail"][:3])
        raw = f"{raw} | {detail_str}"
    # 移除常見絕對路徑前綴避免干擾 KS1 判定
    sanitized = re.sub(r"/(?:[a-zA-Z0-9_.-]+/)+", "", raw)
    sanitized = " ".join(sanitized.split())
    if len(sanitized) > 240:
        sanitized = sanitized[:237] + "..."
    return sanitized


# ── the pass ────────────────────────────────────────────────────────────

class Evidence:
    def __init__(self, rec: Recorder, *, platform: str, session: str,
                 final_text: str | None = None, today: _dt.date | None = None):
        self.rec = rec
        self.tr = Trace(rec)
        self.platform, self.session = platform, session
        self.final_text = final_text or ""
        self.today = today or _dt.date.today()
        self.notes: dict[str, Any] = {}

    # window ──────────────────────────────────────────────────────────
    def _mine(self, actor: dict[str, Any]) -> bool:
        return str(actor.get("platform")) == self.platform and \
            str(actor.get("session")) == self.session

    def _is_test_step_cmd(self, s: Step) -> bool:
        if tool_kind(s.tool) != "shell":
            return False
        clean_cmd = _strip_shell_comments(_command_of(self.tr, s))
        return bool(clean_cmd and (RUNNERS.search(clean_cmd) or is_test_script_run(clean_cmd)))

    def _step_test_output(self, s: Step) -> str:
        outp = self.tr.output_text(s)
        if not outp:
            raw_out = self.tr.blob_text(s.output_blob) or ""
            try:
                j_out = json.loads(raw_out)
                if isinstance(j_out, dict):
                    outp = str(j_out.get("stdout") or j_out.get("output") or raw_out)
                else:
                    outp = raw_out
            except Exception:
                outp = raw_out
        if s.error:
            outp = f"{outp}\n{s.error}" if outp else str(s.error)
        return outp

    def best_test_checkpoint(self, steps: list[Step] | None = None) -> tuple[str | None, tuple[int, int], int | None]:
        """尋找目前要求視窗內通過最多測試的步驟檢查點。回傳 `(pre_index, (passed, failed), step_n)`。
        同分時取較晚的步驟（`>=`），避免平手時把較晚狀態覆寫回較早狀態。"""
        if steps is None:
            _start, _texts, win_steps = self.window()
            steps = win_steps if win_steps else self.tr.steps
        best_idx: str | None = None
        best_score: tuple[int, int] = (-1, 999999)
        best_step_n: int | None = None
        for s in steps:
            if not self._is_test_step_cmd(s):
                continue
            score = parse_test_score(self._step_test_output(s))
            if score is not None:
                passed, failed = score
                key = (passed, -failed)
                if key >= (best_score[0], -best_score[1]):
                    idx = s.pre_index
                    if idx:
                        best_score = (passed, failed)
                        best_idx = idx
                        best_step_n = s.n
        if best_idx is not None and best_score[0] > 0:
            return best_idx, best_score, best_step_n
        return None, (0, 0), None

    def maybe_restore_best_checkpoint(self, steps: list[Step] | None = None) -> bool:
        """若最後一次測試比同回合先前的測試檢查點退步（且最後一次測試後未再改寫檔案），
        將工作區還原至最高分檢查點並記錄 `checkpoint_restore` 事件。"""
        if steps is None:
            _start, _texts, steps = self.window()
        if not steps:
            return False
        best_idx, best_score, best_n = self.best_test_checkpoint(steps)
        if not best_idx or best_score[0] <= 0:
            return False
        last_test_pos: int | None = None
        cur_score: tuple[int, int] = (0, 999999)
        for i in range(len(steps) - 1, -1, -1):
            s = steps[i]
            if not self._is_test_step_cmd(s):
                continue
            last_test_pos = i
            parsed = parse_test_score(self._step_test_output(s))
            if parsed is not None:
                cur_score = parsed
            break
        if last_test_pos is None:
            return False
        if any(t.writes for t in steps[last_test_pos + 1:]):
            return False
        if (best_score[0], -best_score[1]) <= (cur_score[0], -cur_score[1]):
            return False
        if best_idx == self.tr.latest_index():
            return False
        return restore_best_checkpoint(self.rec, best_idx, best_n or 0)

    def window(self) -> tuple[int, list[str], list[Step]]:
        """回 (起點 seq, 人的要求原文, 這一回合的步驟)。起點＝這個工作階段最後一則人打的要求
        （含 `vacant do` 交給這一跑的任務）；沒有就從這個工作階段的第一步開始。"""
        start, texts = -1, []
        do_runs = {run for run, sess in self.tr.do_sessions.items()
                   if f"{self.platform}:{self.session}" in sess}
        for p in self.tr.prompts:
            src = str(p.get("source") or "user")
            ps = str(p.get("session") or "")
            person = (src == "user" and ps == self.session) or \
                     (src == "vacant do" and (ps in ("*",) or ps.removeprefix("do:") in do_runs))
            if person:
                start = int(p["seq"])
                texts = [self.tr.prompt_text(p)]
        steps = [s for s in self.tr.steps if s.seq > start and self._mine(s.actor)]
        if start < 0:
            self.notes["window_basis"] = "session_start"
        return start, texts, steps

    # deliverables and changed lines ─────────────────────────────────
    def deliverables(self, steps: list[Step]) -> tuple[dict[str, tuple[str, str]], str | None]:
        """路徑 → (這一回合開始時的內容, 現在的內容)。只收這一回合的步驟寫過、現在還在的文字檔。"""
        latest = self.tr.latest_index()
        start_idx = steps[0].pre_index if steps and steps[0].pre_index else self.tr.initial
        written: dict[str, Step] = {}
        for s in steps:
            for w in s.writes:
                written[str(w["path"])] = s
        out = {}
        idx = self.tr.index(latest)
        for path in written:
            e = idx.get(path)
            if e is None or _skipped(path) or getattr(e, "size", 0) > MAX_DELIVERABLE_BYTES:
                continue
            now = self.tr.file_text(latest, path)
            if now is None or "\x00" in now:
                continue
            out[path] = (self.tr.file_text(start_idx, path) or "", now)
        return out, start_idx

    # materials ───────────────────────────────────────────────────────
    def _materials_from_texts(self, texts: list[str], start_idx: str | None
                              ) -> tuple[list[str], list[str]]:
        files = sorted(self.tr.index(start_idx))
        root = str(self.rec.workspace)
        named, in_dirs = [], []
        for text in texts:
            cued_dirs = {m.group(1).strip("/").removeprefix("./")
                         for m in DIR_CUE_RE.finditer(text)}
            for d_cue in sorted(cued_dirs):
                under = [f for f in files if f.startswith(d_cue + "/")]
                if under and len(under) <= MAX_DIR_MATERIALS:
                    in_dirs.extend(under)
            for tok in re.findall(r"`[^`]+`|\"[^\"]+\"|'[^']+'|\S+", text):
                quoted = tok[:1] in "`\"'"
                t = tok.strip("`\"'()[]<>{}").rstrip(".,;:!?")
                if not t or " " in t.strip():
                    continue
                if t.startswith(root + "/"):
                    t = t[len(root) + 1:]
                elif t.startswith("/"):
                    t = t.lstrip("/")
                t = t.removeprefix("./")
                if re.search(r"\.[A-Za-z0-9]{1,10}$", t) and not t.endswith("/"):
                    hits = [f for f in files if f == t or f.endswith("/" + t)]
                    if not hits and "/" not in t:
                        hits = [f for f in files if f.rsplit("/", 1)[-1] == t]
                    if len(hits) == 1:
                        named.append(hits[0])
                    continue
                d = t.rstrip("/")
                if not d or not ("/" in t or quoted):
                    continue
                parts = d.split("/")                  # 專案根以外的絕對路徑：逐層去掉前面再比
                for k in range(len(parts)):
                    cand = "/".join(parts[k:])
                    if any(f.startswith(cand + "/") for f in files):
                        d = cand
                        break
                under = [f for f in files if f.startswith(d + "/")]
                if under and len(under) <= MAX_DIR_MATERIALS:
                    in_dirs.extend(under)
        named = sorted(dict.fromkeys(named))
        return named, sorted(set(in_dirs) - set(named))

    def _instruction_docs(self, prompt_texts: list[str], start_idx: str | None,
                          base_named: list[str] | None = None) -> list[tuple[str, str]]:
        """人點名要 agent 照著做的未修改說明檔 `[(路徑, 內容)]`。"""
        if base_named is None:
            base_named, _ = self._materials_from_texts(prompt_texts, start_idx)
        docs = [f for f in base_named if _ext(f) in INSTRUCTION_EXT and self._is_instruction(f, prompt_texts)]
        if not docs:
            return []
        latest = self.tr.latest_index()
        idx = self.tr.index(start_idx)
        out: list[tuple[str, str]] = []
        for f in docs:
            e = idx.get(f)
            if e is None or getattr(e, "size", 0) > INSTRUCTION_MAX_BYTES:
                continue
            text = self.tr.file_text(start_idx, f)
            if not text or "\x00" in text or (self.tr.file_text(latest, f) or "") != text:
                continue                              # 這一回合改過它＝它是要改的東西，不是說明
            out.append((f, text))
        return out

    def materials(self, prompt_texts: list[str], start_idx: str | None
                  ) -> tuple[list[str], list[str]]:
        """人打的話裡點名的資料（含人要 agent 照著做的說明檔裡點名的輸入資料）：
        `(單獨點名的檔, 點名的資料夾裡的檔)`。只認路徑形式：有副檔名的檔名（≤10 字元，含 `.parquet`）、
        含 `/` 的路徑、用反引號／引號包起來的資料夾名，或明確的 `in the <dir> directory/folder`。"""
        named, in_dirs = self._materials_from_texts(prompt_texts, start_idx)
        inst_docs = self._instruction_docs(prompt_texts, start_idx, named)
        if inst_docs:
            doc_paths = {f for f, _ in inst_docs}
            req_outs = {r for r, _ in self.requested_outputs(prompt_texts)}
            for _f, text in inst_docs:
                got_outs = [r for r, _ in self._resolve(self._doc_output_tokens(text))
                            if r not in doc_paths]
                if len(got_outs) > INSTRUCTION_MAX_OUTPUTS:
                    continue
                req_outs.update(got_outs)
                extra_n, extra_d = self._materials_from_texts([text], start_idx)
                for ef in extra_n:
                    stem = os.path.splitext(ef.rsplit("/", 1)[-1])[0]
                    if (ef not in doc_paths and ef not in req_outs
                            and not TEST_BASENAME.match(stem)
                            and not any(p.startswith("tests") for p in ef.split("/"))):
                        named.append(ef)
                for ed in extra_d:
                    stem = os.path.splitext(ed.rsplit("/", 1)[-1])[0]
                    if (ed not in doc_paths and ed not in req_outs
                            and not TEST_BASENAME.match(stem)
                            and not any(p.startswith("tests") for p in ed.split("/"))):
                        in_dirs.append(ed)
        named = sorted(dict.fromkeys(named))
        return named, sorted(set(in_dirs) - set(named))

    def asked_outputs(self, prompt_texts: list[str], start_idx: str | None) -> list[tuple[str, str]]:
        """人要求寫出的檔（v3.7）：人打的話裡寫的，加上人**要 agent 照著做**的說明檔（`.md`／`.txt`／`.rst`）裡對 agent 下的命令。
        說明檔＝人點名、而且檔名是說明（contract.md、TASK.md…）或那一句話裡有「照著做／依照」；這一回合 agent 自己改過的、
        大於 64 KB 的不讀；一份說明檔裡超過 3 個就全部不算（那是資料）。說明檔用這一回合開始時的內容。
        Colab 程式題：交付物只寫在 `contract.md`，v3.6.1 一次都沒認出來（沒交檔 34 格、缺檔退回 0 次）。"""
        outs = self.requested_outputs(prompt_texts)
        inst_docs = self._instruction_docs(prompt_texts, start_idx)
        if not inst_docs:
            return outs
        doc_paths = {f for f, _ in inst_docs}
        have = {r for r, _ in outs}
        extra: list[tuple[str, str]] = []
        used: list[str] = []
        for f, text in inst_docs:
            got = [(r, raw) for r, raw in self._resolve(self._doc_output_tokens(text))
                   if r not in have and r not in doc_paths]
            if len(got) > INSTRUCTION_MAX_OUTPUTS:
                continue
            used.append(f)
            for r, raw in got:
                if r not in {x for x, _ in extra}:
                    extra.append((r, raw))
        if extra:
            self.notes["outputs_from_instructions"] = {"files": used, "outputs": [r for r, _ in extra]}
        return outs + extra

    @staticmethod
    def _is_instruction(path: str, prompt_texts: list[str]) -> bool:
        base = path.rsplit("/", 1)[-1]
        if INSTRUCTION_STEM.match(os.path.splitext(base)[0]):
            return True
        for text in prompt_texts:
            for sent in re.split(r"(?<=[.!?。！？])\s+|\n", text):
                if base in sent and INSTRUCTION_CUE.search(sent):
                    return True
        return False

    @staticmethod
    def _doc_output_tokens(text: str) -> list[str]:
        """說明檔裡對 agent 下的「寫到 X」命令（見 `DOC_IMPERATIVE_PRE`／`DOC_NOT_REQUIRED`）＋「Deliverable: X」這類標籤。"""
        found: list[str] = []
        norm = text.replace("\u2019", "'").replace("\u2018", "'")
        for m in OUTPUT_VERB.finditer(norm):
            cut = max(norm.rfind(c, 0, m.start()) for c in (".", "\n", ";", ":", "!", "?"))
            pre = re.sub(r"[*_~`]+", "", norm[cut + 1: m.start()]).strip()
            if not DOC_IMPERATIVE_PRE.match(pre + (" " if pre else "")):
                continue
            window = norm[m.end(): m.end() + 140].split("\n\n")[0]
            for pm in OUTPUT_PREP.finditer(window):
                tok = pm.group(1).strip("`\"'").rstrip(".,;:!?")
                if FILE_LIKE.match(tok):
                    # 否定／可有可無／舉例只看句首到這個檔名（「寫到 solution.py，不要印出來」的 not 管的是後面）
                    if not DOC_NOT_REQUIRED.search(re.sub(r"[*_~]+", "", norm[cut + 1: m.end() + pm.end()])):
                        found.append(tok)
                    break
        for rx in (DOC_LABEL, CJK_OUTPUT):
            for m in rx.finditer(norm):
                cut = max(norm.rfind(c, 0, m.start()) for c in ("。", "\n", "；"))
                if DOC_NOT_REQUIRED.search(norm[cut + 1: m.end()]):
                    continue
                tok = m.group(1).strip("`\"'「」").rstrip(".,;:!?。")
                if FILE_LIKE.match(tok):
                    found.append(tok)
        return found

    def requested_outputs(self, prompt_texts: list[str]) -> list[tuple[str, str]]:
        """人要求寫出的檔：(工作區裡的相對路徑, 人寫的樣子)。只收有副檔名的路徑；專案根以外、
        對不到專案裡任何資料夾的絕對路徑不收（看不到它在不在）。v3.7：中文的「寫到／存成 X」也認（舊的 `\b` 在中文字之間永遠不成立）。"""
        found: list[str] = []
        for text in prompt_texts:
            for m in CJK_OUTPUT.finditer(text):
                tok = m.group(1).strip("`\"'「」").rstrip(".,;:!?。")
                if FILE_LIKE.match(tok):
                    found.append(tok)
            for m in OUTPUT_VERB.finditer(text):
                window = text[m.end(): m.end() + 140].split("\n\n")[0]
                for pm in OUTPUT_PREP.finditer(window):
                    tok = pm.group(1).strip("`\"'").rstrip(".,;:!?")
                    if FILE_LIKE.match(tok):
                        found.append(tok)
                        break
            for m in OUTPUT_LABEL.finditer(text):
                tok = m.group(1).strip("`\"'").rstrip(".,;:!?")
                if FILE_LIKE.match(tok):
                    found.append(tok)
        return self._resolve(found)

    def _resolve(self, found: list[str]) -> list[tuple[str, str]]:
        """人寫的路徑 → 工作區裡的相對路徑（專案根以外、對不到專案資料夾的絕對路徑不收）。"""
        root = str(self.rec.workspace)
        files = self.tr.index(self.tr.latest_index())
        dirs = {f.rsplit("/", 1)[0] for f in files if "/" in f}
        out: list[tuple[str, str]] = []
        for raw in dict.fromkeys(found):
            t = raw.removeprefix("./")
            if t.startswith("~"):
                continue
            if t.startswith(root + "/"):
                rel: str | None = t[len(root) + 1:]
            elif t.startswith("/"):
                parts = t.lstrip("/").split("/")
                rel = None
                # 專案根以外的絕對路徑（評測容器裡的 /app/…）：資料夾對得上專案裡的資料夾、
                # 或上一層就是專案根的名字，才換成相對路徑
                for k in range(len(parts) - 1):
                    cand = "/".join(parts[k:-1])
                    if cand in dirs:
                        rel = cand + "/" + parts[-1]
                        break
                if rel is None and self.rec.workspace.name in parts[:-1]:
                    rel = "/".join(parts[parts.index(self.rec.workspace.name) + 1:])
                if rel is None and len(parts) >= 2 and parts[0] in ("app", "workspace", "work", "src"):
                    if len(parts) == 2:
                        rel = parts[1]
                    else:
                        rel = "/".join(parts[1:])
            else:
                rel = t
            if rel and not _skipped(rel):
                out.append((rel, raw))
        return out

    def _material_consumed_before(self, steps: list[Step], i: int, mats: list[str],
                                  cmd: str) -> bool:
        """純顯示 probe（head/tail/cat…）在資料已**成功消費過**之後失敗＝重覆動作，不是略過。
        （2026-10-25，C37 dabstep-14-s2：讀過 payments.csv 後 `head -n 1` 失敗被誤退）

        刻意不收窄到「任何失敗指令」：`grep -P 'fee('` 這類**查詢**失敗，即使檔案讀過，
        該查詢本身仍未被滿足（test_zero_evidence::test_a_search_that_errors…）——查詢/轉換
        動詞（grep/awk/sed/jq/…）在命令裡就不豁免。

        「已消費」只認兩種證據：read/search 工具成功且路徑對得上；shell 成功、命令是讀類動詞、
        且輸出非空。`rm X`（空輸出）、`echo X`（非讀類動詞）都不算。"""
        clean = _strip_shell_comments(cmd)
        if not DISPLAY_ONLY_PROBE.match(clean) or QUERY_IN_CMD.search(clean):
            return False
        bases = {m.rsplit("/", 1)[-1] for m in mats}
        for t in steps[:i]:
            if t.error:
                continue
            kind = tool_kind(t.tool)
            inp = self.tr.input_text(t)
            if not any(b in inp for b in bases):
                continue
            if kind in ("read", "search"):
                return True
            if kind == "shell":
                if not (self.tr.output_text(t) or "").strip():
                    continue
                if READ_VERBS.search(_strip_shell_comments(inp)):
                    return True
        return False

    def observed(self, steps: list[Step], candidates: list[str], deliverables: set[str]) -> set[str]:
        root = str(self.rec.workspace)
        seen: set[str] = set()
        scripts: dict[str, str] = {}            # 這一回合寫的腳本 → 內容
        for s in steps:
            for w in s.writes:
                p = str(w["path"])
                if _ext(p) in {".py", ".js", ".ts", ".sh", ".mjs", ".r", ".jl"}:
                    scripts[p] = self.tr.file_text(s.post_index, p) or ""
        texts = []
        for s in steps:
            kind = tool_kind(s.tool)
            t = self.tr.input_text(s)
            if kind in ("read", "search", "shell", "fetch", "agent", "other"):
                texts.append(t)
            if kind == "shell":
                for sp, body in scripts.items():
                    if re.search(r"(?<![\w.-])" + re.escape(sp.rsplit("/", 1)[-1]) + r"\b", t):
                        texts.append(body)
        for f in candidates:
            base = f.rsplit("/", 1)[-1]
            d = f.rsplit("/", 1)[0] if "/" in f else ""
            pats = [re.escape(root + "/" + f), r"(?<![\w.-])" + re.escape(f),
                    r"(?:^|[\s\"'`/{(+=,:])" + re.escape(base) + r"(?![\w-])"]
            if _ext(f) == ".py":
                stem = os.path.splitext(base)[0]
                pats.append(r"(?:\b(?:-m|unittest|pytest|import|from)\s+(?:[\w.]+\s+)*)"
                            + re.escape(stem) + r"\b")
                if "/" in f:
                    mod = os.path.splitext(f)[0].replace("/", ".")
                    pats.append(r"(?<![\w.-])" + re.escape(mod) + r"\b")
            for t in texts:
                if any(re.search(p, t) for p in pats):
                    seen.add(f)
                    break
                # 對整個資料夾做會讀內容的動作（`grep -r x data`、`cat data/*`、`os.listdir('data')`）：
                # 資料夾名後面不接檔名才算——`head data/payments.csv` 只讀了那一個檔。
                # `cd data && … payments.csv`、`ls data` 不是讀整個資料夾（2026-09-25 真實紀錄重播）
                td = _NOT_A_DIR_READ.sub(" ", t)
                if d and READ_VERBS.search(td) and re.search(
                        r"(?<![\w.-])" + re.escape(d) + r"/?(\*[^\s\"'`]*)?(?=[\s\"'`),;\]]|$)", td):
                    seen.add(f)
                    break
        return seen

    def given_inline(self, candidates: list[str], prompt_texts: list[str],
                     start_idx: str | None) -> set[str]:
        """人打的話裡已經貼了全文的檔：內容已經給了＝已經讀到（v3.5，2026-09-26）。

        R530 的題目把 `goal.md`、`contract.md` 整段貼在請求裡，又列出「工作區裡有這幾個檔」；agent 不必再打開，
        v3.4 卻退回「點名的檔沒打開」——R530 SOLO 的紀錄重播 59 格裡 58 格被退回，大部分是這種
        （`ops/eval/evidence_20260926_local/v35_given_inline/`）。

        判準（對抗審查之後收緊，`ops/eval/evidence_20260926_local/v35_given_inline/review/`）：這一回合開始時檔的**全文**，壓過空白之後**整段、連續地**出現在
        人打的話裡（也壓過空白，前後是空白或頭尾）。貼的是舊版、差一行、數字是前綴（`pool_size: 1` 對貼上的
        `pool_size: 10`）、只貼了一部分——都**不算**，照樣退回。至少 `GIVEN_INLINE_MIN` 位元組（太短的檔會被巧合對上）；
        只看 ≤ `GIVEN_INLINE_MAX` 位元組、讀得出文字的檔。換行位置不同也對得上（空白都壓成一個；中日韓字之間的換行拿掉）。
        只會讓退回變少，不會變多。"""
        joined = _collapse("\n".join(prompt_texts))
        if len(joined.encode()) < GIVEN_INLINE_MIN:
            return set()
        out: set[str] = set()
        idx = self.tr.index(start_idx)
        for f in candidates:
            e = idx.get(f)
            if e is None or e.size > GIVEN_INLINE_MAX:
                continue
            text = self.tr.file_text(start_idx, f)
            if not text or "\x00" in text:
                continue
            whole = _collapse(text)
            if len(whole.encode()) >= GIVEN_INLINE_MIN and _contains_whole(joined, whole):
                out.add(f)
        return out

    # the corpus of what this task observed ─────────────────────────
    def corpus(self, steps: list[Step], deliverables: set[str], observed_files: set[str],
               start_idx: str | None, prompt_texts: list[str]) -> str:
        parts = list(prompt_texts)
        for s in steps:
            kind = tool_kind(s.tool)
            if kind == "write":
                continue
            out = self.tr.output_text(s)
            if not out:
                continue
            inp = self.tr.input_text(s)
            refs = set(re.findall(r"[\w./-]+\.[A-Za-z0-9]{1,10}", inp))
            # 跑自己寫的腳本是**計算**，不是回頭讀交付物（2026-09-25 正式批次：`python3 /app/analyze.py` 印出的
            # 2429 被當成「讀自己的交付物」丟掉，答對的答案被退回——6 次誤報的根因）
            runs_code = bool(INTERPRETER.match(inp)) or any(_ext(r) in CODE_HINT_EXT for r in refs)
            if refs and not runs_code and all(any(r.endswith(d) or d.endswith(r)
                                                   for d in deliverables) for r in refs):
                continue                          # 只是回頭讀自己寫的交付物：不算出處
            parts.append(out)
        for f in observed_files:
            t = self.tr.file_text(start_idx, f)
            if t:
                parts.append(t[:2_000_000])
        return "\n".join(parts)

    # derived numbers from observed tables ───────────────────────────
    def derived(self, corpus_tables: list[str]) -> list[float]:
        out: list[float] = []
        for text in corpus_tables:
            try:
                rows = list(csv.reader(io.StringIO(text)))
            except csv.Error:
                continue
            if len(rows) < 2 or len(rows[0]) < 2 or len(rows) > 200_000:
                continue
            head, body = rows[0], rows[1:]
            cols = list(zip(*[r for r in body if len(r) == len(head)]))
            numeric: dict[int, list[float]] = {}
            for i, col in enumerate(cols):
                vals = []
                for v in col:
                    try:
                        vals.append(float(v.replace(",", "").replace("$", "").strip()))
                    except ValueError:
                        break
                else:
                    if vals:
                        numeric[i] = vals
            for vals in numeric.values():
                out += [sum(vals), sum(vals) / len(vals), float(len(vals)), min(vals), max(vals)]
            for gi, gcol in enumerate(cols):
                if gi in numeric:
                    continue
                keys: dict[str, list[int]] = {}
                for r_i, g in enumerate(gcol):
                    key_forms = {g}
                    for _, d, _, _ in dates_in(g):
                        key_forms |= {f"y{d.year}", f"m{d.year}-{d.month}",
                                      f"q{d.year}-{(d.month - 1) // 3}"}
                    for k in key_forms:
                        keys.setdefault(k, []).append(r_i)
                if len(keys) > 500:
                    continue
                for vi, vals in numeric.items():
                    for idxs in keys.values():
                        out.append(sum(vals[i] for i in idxs if i < len(vals)))
            if len(out) > MAX_CORPUS_NUMBERS:
                break
        return out[:MAX_CORPUS_NUMBERS]

    # the checks ──────────────────────────────────────────────────────
    def run(self) -> dict[str, Any]:
        start, prompt_texts, steps = self.window()
        delivs, start_idx = self.deliverables(steps)
        named, dir_members = self.materials(prompt_texts, start_idx)
        inst_docs = self._instruction_docs(prompt_texts, start_idx)
        task_texts = list(prompt_texts) + [t for _, t in inst_docs]
        deliv_set = set(delivs)
        observed = self.observed(steps, named + dir_members, deliv_set)
        given = self.given_inline(named + dir_members, prompt_texts, start_idx) - observed
        observed |= given
        findings: list[dict[str, Any]] = []
        unread_named = [f for f in named if f not in observed and f not in deliv_set]
        unread_dir = [f for f in dir_members if f not in observed and f not in deliv_set]
        for f in unread_named:
            findings.append({"kind": "unread", "path": f})

        # Task E Rule 1: 資料夾內有業務說明文件（*.md / *.txt），且題目要求參考說明文件（或提到 documentation/rules/manual），但文件全未讀取
        has_doc_cue = bool(re.search(r"\b(?:documentation|documents?|docs?|manual|readme|rules?|guides?|policies|policy)\b", "\n".join(task_texts), re.I))
        dir_docs = [f for f in dir_members if (f.lower().endswith((".md", ".txt"))
                                               or any(k in f.lower() for k in ("manual", "readme", "guide", "rule")))
                    and not f.endswith("answer.txt") and not f.endswith("out.txt")]
        data_observed = any(f in observed for f in dir_members if f not in dir_docs)
        if has_doc_cue and dir_docs and (data_observed or delivs):
            unread_docs = [d for d in dir_docs if d not in observed]
            if len(unread_docs) == len(dir_docs):
                findings.append({
                    "kind": "unread",
                    "path": unread_docs[0],
                    "sub": "unread_doc",
                    "doc_paths": unread_docs,
                    "target": list(delivs.keys())[0] if delivs else "the requested output"
                })
        materials_named = bool(named or dir_members)
        corpus = self.corpus(steps, deliv_set, observed, start_idx, prompt_texts)
        values, value_notes = self._values(steps, delivs, corpus, task_texts, materials_named)
        only_answer = any(ONLY_ANSWER.search(t) for t in task_texts)
        for v in values:
            v["single_answer"] = only_answer or v.pop("_short")
            if unread_dir or unread_named:
                v["unread_attach"] = (unread_named + unread_dir)[:6]
            findings.append(v)
        findings += self._test_claim(steps, delivs)
        findings += self._failed_steps(steps, delivs, named + dir_members)
        findings += self._claimed_runs()
        findings += self._unfetched_sources(task_texts)
        findings += self._claimed_writes()
        outs = self.asked_outputs(prompt_texts, start_idx)
        latest_idx = self.tr.latest_index()
        latest = self.tr.index(latest_idx)
        for rel, raw in outs:
            # 相對路徑：agent 在專案的子資料夾裡寫了同一個相對路徑也算在（專案根＝git 根；v3.1）
            if rel not in latest and rel not in named + dir_members \
                    and not any(f.endswith("/" + rel) for f in latest):
                findings.append({"kind": "missing_output", "path": rel, "asked": raw})
        findings += self._invalid_outputs(delivs, outs, task_texts, corpus, start_idx, latest_idx,
                                          only_answer=only_answer)
        findings += self._copy_of_task(delivs, outs, task_texts, start_idx, latest_idx)
        findings += self._skeleton(delivs, outs, start_idx, latest_idx)
        findings += self._stale_outputs(outs, delivs, start_idx)
        findings += self._copy_of_input(delivs, outs, named, task_texts, start_idx, latest_idx)
        findings += self._copy_of_inline(delivs, outs, task_texts, latest_idx)
        scope = self.rec.dir.name
        for fd in findings:
            fd["finding_id"] = finding_id(fd, scope)
        return {"window_start": start, "steps": len(steps), "deliverables": sorted(delivs),
                "materials_named": named, "materials_in_dirs": dir_members,
                "requested_outputs": [r for r, _ in outs],
                "observed": sorted(observed), "given_in_request": sorted(given), "unread_dir": unread_dir,
                "values": value_notes, "findings": findings, "notes": self.notes,
                "final_text_seen": bool(self.final_text)}

    def _values(self, steps: list[Step], delivs: dict[str, tuple[str, str]], corpus: str,
                prompt_texts: list[str], materials_named: bool
                ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        notes: dict[str, Any] = {"checked": 0, "traced": 0, "derived": 0, "exempt": 0,
                                 "not_typed": 0, "not_traced_note_only": []}
        step_calc_nums = [n.value * n.scale for s in steps if tool_kind(s.tool) != "read"
                          for n, _, _ in numbers_in(self.tr.output_text(s))]
        corpus_nums = step_calc_nums + [n.value * n.scale for n, _, _ in numbers_in(corpus)][:MAX_CORPUS_NUMBERS]
        corpus_nums += [n.value for n, _, _ in numbers_in(corpus) if n.pct][:500]
        tables = [corpus]
        for s in steps:
            tables.append(self.tr.output_text(s))
        derived = self.derived(tables)
        pool = corpus_nums + derived
        pool_small = pool[:300]
        pairs = []
        for i, a in enumerate(pool_small):
            for b in pool_small[i + 1:]:
                pairs += [a + b, abs(a - b)]
                if b:
                    pairs += [a / b, 100 * a / b]
                if a:
                    pairs += [b / a, 100 * b / a]
        corpus_dates = {d for _, d, _, _ in dates_in(corpus)}
        prompt = "\n".join(prompt_texts)
        prompt_dates = {d for _, d, _, _ in dates_in(prompt)}
        prompt_nums = [n for n, _, _ in numbers_in(prompt)]
        today = {self.today, self.today - _dt.timedelta(days=1)}
        step_inputs = [(s, self.tr.input_text(s)) for s in steps]
        out = []
        for path, (old, new) in sorted(delivs.items()):
            ext = _ext(path)
            if ext in CODE_HINT_EXT or ext not in DOC_EXT:
                continue
            lines = new.splitlines()
            changed = _changed_lines(old, new)
            exempt_block = _exempt_lines(lines)
            nonempty = [ln for ln in lines if ln.strip()]
            # 只有一行短短的答案（例如題目要的答案檔）：退回時請它只寫重算的值；多一個標題就是報告
            short = len(nonempty) == 1 and len(nonempty[0].strip()) <= 40
            count = 0
            for ln_no in changed:
                line = lines[ln_no - 1]
                if ln_no in exempt_block:
                    continue
                labelled = (not short) and ASSUMPTION_WORDS.search(line)
                items: list[tuple[str, Any]] = []
                for raw, d, _, _ in dates_in(line):
                    items.append((raw, d))
                for n, s_, e_ in numbers_in(_strip_code(line)):
                    if _significant(n):
                        items.append((n.raw, n))
                for raw, obj in items:
                    count += 1
                    if count > MAX_VALUES_PER_FILE:
                        break
                    notes["checked"] += 1
                    if labelled:
                        notes["exempt"] += 1
                        continue
                    if isinstance(obj, _dt.date):
                        if obj in today or obj in prompt_dates:
                            notes["exempt"] += 1
                            continue
                        if obj in corpus_dates:
                            notes["traced"] += 1
                            continue
                    else:
                        if any(_num_match(obj, p.value * p.scale) for p in prompt_nums):
                            notes["exempt"] += 1
                            continue
                        if any(_num_match(obj, c) for c in corpus_nums):
                            notes["traced"] += 1
                            continue
                        if any(_num_match(obj, c) for c in derived) or \
                                any(_num_match(obj, c) for c in pairs):
                            notes["derived"] += 1
                            continue
                    if not _typed(raw, obj, path, step_inputs):
                        notes["not_typed"] += 1       # 由它跑的程式算出來寫進去的：算在這個任務裡
                        continue
                    if not materials_named:
                        notes["not_traced_note_only"].append(f"{path} line {ln_no} {raw}")
                        continue
                    out.append({"kind": "unsourced", "path": path, "line": ln_no, "value": raw,
                                "_short": short})
        return out, notes

    def _copy_of_task(self, delivs: dict[str, tuple[str, str]], outs: list[tuple[str, str]],
                      task_texts: list[str], start_idx: str | None,
                      latest_idx: str | None) -> list[dict[str, Any]]:
        """要求的交付檔 ≈ 任務提示詞原文（連指令句一起照抄）＝把題目當答案交出去。

        通用任務（方向 A）：域無關、只看紀錄。三重保守條件（docs/UNIVERSAL_TASKS.md §3）：
        `_collapse` 正規化後提示詞**包含於**交付檔、比例 ≥ COPY_TASK_MIN_RATIO、
        提示詞 ≥ COPY_TASK_MIN_PROMPT 字。只照抄引用內容（不含指令句）的轉述任務不觸發。
        預設只進交件說明：`zerostop.pushable_for` 明確排除，不退回給 agent。"""
        out: list[dict[str, Any]] = []
        texts = [_collapse(t).lower() for t in task_texts
                 if t and len(_collapse(t)) >= COPY_TASK_MIN_PROMPT]
        if not texts:
            return out
        latest = self.tr.index(latest_idx)
        cands: list[tuple[str, str]] = []
        for path, (old, new) in sorted(delivs.items()):
            cands.append((path, new))
        for rel, _raw in outs:
            actual = rel if rel in latest else next(
                (f for f in sorted(latest) if f.endswith("/" + rel)), None)
            if actual and actual not in delivs:
                new_t = self.tr.file_text(latest_idx, actual)
                if new_t is not None and "\x00" not in new_t:
                    cands.append((actual, new_t))
        for path, new in cands:
            if not new or not new.strip():
                continue                      # 空檔已由 invalid_output/empty 報過
            n_d = _collapse(new).lower()
            if len(n_d) < COPY_TASK_MIN_PROMPT:
                continue
            for n_t in texts:
                if n_t in n_d and len(n_t) / len(n_d) >= COPY_TASK_MIN_RATIO:
                    out.append({"kind": "copy_of_task", "path": path,
                                "detail": f"nearly identical to the task prompt "
                                          f"(ratio {len(n_t) / len(n_d):.2f})"})
                    break
        return out

    # ── 方向 A 通用檢查（只進交件說明；zerostop.pushable_for 明確排除）──────
    def _skeleton(self, delivs: dict[str, tuple[str, str]], outs: list[tuple[str, str]],
                  start_idx: str | None, latest_idx: str | None) -> list[dict[str, Any]]:
        """要求的交付檔是模板骨架：多數非空行是未填占位符（TBD／TODO／[待填]／{{…}}／___…）。

        通用任務（方向 A）：領域無關、只看寫出的檔內容。保守：占位行 ≥ SKELETON_MIN_LINES
        且占位行／非空行 ≥ SKELETON_MIN_RATIO；完整報告裡一個誠實的「日期：TBD」不觸發
        （那一行不是獨立占位行）。
        預設只進交件說明：`zerostop.pushable_for` 明確排除。"""
        latest = self.tr.index(latest_idx)
        cands: list[tuple[str, str]] = []
        for path, (old, new) in sorted(delivs.items()):
            cands.append((path, new))
        for rel, _raw in outs:
            actual = rel if rel in latest else next(
                (f for f in sorted(latest) if f.endswith("/" + rel)), None)
            if actual and actual not in delivs:
                new_t = self.tr.file_text(latest_idx, actual)
                if new_t is not None and "\x00" not in new_t:
                    cands.append((actual, new_t))
        out = []
        for path, new in cands:
            if not new or not new.strip():
                continue                      # 空檔已由 invalid_output/empty 報過
            lines = [l for l in new.splitlines() if l.strip()]
            ph = sum(1 for l in lines if _is_placeholder_line(l))
            if ph >= SKELETON_MIN_LINES and ph / len(lines) >= SKELETON_MIN_RATIO:
                out.append({"kind": "skeleton", "path": path,
                            "detail": f"{ph}/{len(lines)} non-empty lines are unfilled placeholder markers"})
        return out

    def _stale_outputs(self, outs: list[tuple[str, str]], delivs: dict[str, tuple[str, str]],
                       start_idx: str | None) -> list[dict[str, Any]]:
        """要求的交付檔在本回合前已存在、agent 沒改過，最終訊息卻稱「已寫好／已更新」
        → 疑似把舊檔當成果交出去。

        通用任務（方向 A）：領域無關、只看紀錄（該檔在回合開始時存不存在 × 有沒有寫步驟 × 最終訊息）。
        保守：最終訊息要有「產出型」動詞（寫入/整理/更新/生成/…）；
        只說「Done／已確認」不觸發；「確認有錯才改」的任務真的不需改也不觸發（沒有產出型動詞）。
        預設只進交件說明：`zerostop.pushable_for` 明確排除。"""
        if not self.final_text or not PRODUCE_CLAIM.search(self.final_text):
            return []
        start = self.tr.index(start_idx)
        if not start:
            return []
        out = []
        for rel, raw in outs:
            if rel in delivs:
                continue                      # 這一回合寫過，不是舊檔
            actual = rel if rel in start else next(
                (f for f in sorted(start) if f.endswith("/" + rel)), None)
            if not actual:
                continue                      # 回合開始時不存在（missing_output 管那個）
            out.append({"kind": "stale_output", "path": rel, "asked": raw,
                        "detail": "existed before this session, was never modified, "
                                  "yet the final message claims it was produced"})
        return out

    def _copy_of_input(self, delivs: dict[str, tuple[str, str]], outs: list[tuple[str, str]],
                       named: list[str], task_texts: list[str], start_idx: str | None,
                       latest_idx: str | None) -> list[dict[str, Any]]:
        """要求的交付檔內容與一份點名輸入素材逐字相同（`_collapse` 正規化後）
        → 疑似把輸入原封不動當成果交出去，而不是做要求的整理／摘要。

        通用任務（方向 A）：領域無關、只看紀錄。保守：素材須是人點名的、回合開始時在的、
        正規化後 ≥ COPY_INPUT_MIN；內容逐字相同（不是「相似」——合法重排任務的產出與輸入
        相似但不同，不誤觸）；提示詞本身就是複製型任務（複製/備份/copy…）則相同是預期，不報。
        預設只進交件說明：`zerostop.pushable_for` 明確排除。"""
        if any(COPY_CUE.search(t) for t in task_texts):
            return []
        start = self.tr.index(start_idx)
        if not start:
            return []
        inputs: list[tuple[str, str]] = []
        for f in sorted(set(named)):
            if f not in start:
                continue
            t = self.tr.file_text(start_idx, f)
            if t is None or "\x00" in t:
                continue
            c = _collapse(t).lower()
            if len(c) >= COPY_INPUT_MIN:
                inputs.append((f, c))
        if not inputs:
            return []
        latest = self.tr.index(latest_idx)
        cands: list[tuple[str, str]] = []
        for path, (old, new) in sorted(delivs.items()):
            cands.append((path, new))
        for rel, _raw in outs:
            actual = rel if rel in latest else next(
                (f for f in sorted(latest) if f.endswith("/" + rel)), None)
            if actual and actual not in delivs:
                new_t = self.tr.file_text(latest_idx, actual)
                if new_t is not None and "\x00" not in new_t:
                    cands.append((actual, new_t))
        out = []
        for path, new in cands:
            if not new or not new.strip():
                continue
            n_d = _collapse(new).lower()
            if len(n_d) < COPY_INPUT_MIN:
                continue
            for f, c in inputs:
                if n_d == c:
                    out.append({"kind": "copy_of_input", "path": path, "input": f,
                                "detail": f"verbatim identical to the input material {f}"})
                    break
        return out

    def _session_prompt_texts(self) -> list[str]:
        """本 session 的人類要求全文（seq 升序；含 `vacant do` 的重跑 prompt）。

        `window()` 只取**最後一則**人類 prompt 當 task text；跨輪拼接判定
        （2026-10-29 已知漏→ round 45 修復，方向 A §2.5：交件是兩輪以上 inline
        數據拼接的逐字子串）需要整場對話。person 判定與 `window()` 同一套。
        """
        out: list[str] = []
        do_runs = {run for run, sess in self.tr.do_sessions.items()
                   if f"{self.platform}:{self.session}" in sess}
        for p in self.tr.prompts:
            src = str(p.get("source") or "user")
            ps = str(p.get("session") or "")
            person = (src == "user" and ps == self.session) or \
                     (src == "vacant do" and (ps == "*" or ps.removeprefix("do:") in do_runs))
            if person:
                out.append(self.tr.prompt_text(p))
        return out

    def _copy_of_inline(self, delivs: dict[str, tuple[str, str]], outs: list[tuple[str, str]],
                        task_texts: list[str], latest_idx: str | None) -> list[dict[str, Any]]:
        """要求交出的內容（正規化後）是任務提示詞的逐字子串、且題目要求改寫
        （整理／摘要／分析／重排……）——疑似把貼在題目裡的數據原樣抄回當成果，
        沒有做題目要求的改寫。

        通用任務（方向 A）：領域中立、只看紀錄。守則（寧可漏抓、不可誤傷）：
        - 題目要有改寫線索（`TRANSFORM_CUE`）才查——「照原文寫入」這類抄錄任務裡
          逐字寫出正是預期交件；`COPY_CUE`／`VERBATIM_CUE`（原樣／照抄／verbatim…）／
          `EXTRACT_CUE`（摘出／抽出／extract…，點名要哪一段）出現也直接豁免。
          線索判定用**整場對話**（所有 session prompt，round 45）：任何一輪的豁免線索
          （例如跨輪合併任務的「條目保持原文」）豁免整個任務——只看最後一輪會讓
          正當的跨輪逐字交件在豁免外被 join 語料誤傷；
        - **清單型輸出豁免**（2026-10-26 清單負對照）：題目點名清單型輸出
          （`LIST_REQ_CUE`：動詞＋編號/清單/列表/列點/numbered list/bullet points）
          且交件本身就是清單區塊（`_is_list_block`）時，逐字寫出該清單正是預期交件
          （reformat 是 no-op）——見 test_clean_list_reformat_verbatim_not_caught；
          豁免是合取：清單形狀但題目要求散文輸出（無 `LIST_REQ_CUE`）仍被抓——見
          test_lfake_list_block_without_list_cue_is_caught（2026-10-26 round 64 邊界 pin）；
          `_is_list_block` 的兩個分支各有專屬 pin（round 65）：全行清單項分支由上述兩樣本
          固定；短標題行分支（首行 ≤30 字＋其餘皆清單項）由
          test_clean_list_label_verbatim_not_caught（豁免側）＋
          test_lfake_list_label_without_list_cue_is_caught（合取側）固定；
        - 交件（正規化後）要 ≥ `INLINE_COPY_MIN` 且是 prompt 的**逐字**子串
          （報告引用一段原文不會命中：交件比引文長，不是 prompt 的子串）；
        - **多文件切分**（2026-10-28 註冊已知漏 → round 83 union 檢查；round 120 升為 2–3 元）：
          逐檔都低於 `INLINE_COPY_MIN`、但 2–3 份按任一順序拼接是 prompt（或整場對話）的
          逐字連續子串且合計 ≥ `INLINE_COPY_MIN` 時，該組合的每個檔各報一個發現（同一檔
          只報一次）。同三门＋清單豁免；≥4 檔切分仍是註冊漏（寧漏勿誤）——見
          test_lfake_multifile_split_is_caught（兩檔，抓）＋
          test_lfake_multifile_split_not_pushed_back（advisory）＋
          test_lfake_trifile_split_is_caught（三檔，round 89 曾 pin 為註冊漏、round 120 抓到）＋
          test_clean_multifile_split_keep_verbatim_not_caught／
          test_clean_trifile_split_keep_verbatim_not_caught（verbatim 豁免負對照）；
        - **跨輪拼接**（round 45，2026-10-29 §2.5）：交件是整場對話（≥2 輪）拼接
          的逐字連續子串、且不等於任何單輪 prompt 時也命中。拼接語料**先拼接、
          再 `_collapse`**（先各自 collapse 再拼接會丟掉邊界空白，
          見 test_clean_multifile_split_keep_verbatim_not_caught 的自檢）；
        - 交件＝整段 prompt 的情形由 `copy_of_task` 報（比例 1.0），這裡不重複。
        預設 advisory only：`zerostop.pushable_for` 明確排除（單輪、跨輪同）。"""
        texts = [t for t in task_texts if t]
        all_texts = list(dict.fromkeys(texts + [t for t in self._session_prompt_texts() if t]))
        if any(COPY_CUE.search(t) or VERBATIM_CUE.search(t) or EXTRACT_CUE.search(t) for t in all_texts):
            return []
        if not any(TRANSFORM_CUE.search(t) for t in all_texts):
            return []
        prompts = [_collapse(t).lower() for t in texts]
        # 跨輪拼接語料：只取人類 prompt（不含 instruction docs），≥2 輪才有語料。
        sess = [t for t in self._session_prompt_texts() if t]
        joined = _collapse("\n".join(sess)).lower() if len(sess) >= 2 else ""
        latest = self.tr.index(latest_idx)
        cands: list[tuple[str, str]] = []
        for path, (old, new) in sorted(delivs.items()):
            cands.append((path, new))
        for rel, _raw in outs:
            actual = rel if rel in latest else next(
                (f for f in sorted(latest) if f.endswith("/" + rel)), None)
            if actual and actual not in delivs:
                new_t = self.tr.file_text(latest_idx, actual)
                if new_t is not None and "\x00" not in new_t:
                    cands.append((actual, new_t))
        out: list[dict[str, Any]] = []
        for path, new in cands:
            if not new or not new.strip():
                continue
            n_d = _collapse(new).lower()
            if len(n_d) < INLINE_COPY_MIN:
                continue
            # 清單型輸出豁免：題目點名清單形狀、交件就是清單形狀 → 逐字是預期交件
            # （reformat no-op），不是 lazy echo（2026-10-26 清單負對照）。
            if any(LIST_REQ_CUE.search(t) for t in all_texts) and _is_list_block(new):
                continue
            hit = False
            for n_t in prompts:
                if n_d != n_t and n_d in n_t:
                    out.append({"kind": "copy_of_inline", "path": path,
                                "detail": "verbatim block from the task text; the task asked for a reworking"})
                    hit = True
                    break
            if not hit and joined and n_d != joined and n_d in joined \
                    and all(n_d != pt for pt in prompts):
                out.append({"kind": "copy_of_inline", "path": path,
                            "detail": "verbatim block spanning the whole conversation; "
                                     "the task asked for a reworking"})
        # 多文件切分（2026-10-28 註冊已知漏 → round 83 union 檢查；round 120 升為 2–3 元，
        # docs/UNIVERSAL_TASKS.md §2.4）：逐檔都低於 INLINE_COPY_MIN（逐檔檢查跳過），但 2–3 份
        # 的逐字拼接（按任一順序）是語料的逐字連續子串且 ≥ INLINE_COPY_MIN——把內聯資料
        # 原樣切成多檔的 lazy 切分回顯。三门與逐檔相同（上方 early return 已保證：
        # 改寫線索在＋無 COPY／VERBATIM／EXTRACT 豁免）；清單形狀豁免同用
        # （組合中任一檔是清單區塊＋題目點名清單 → 豁免，寧漏勿誤）；≥4 檔切分仍是註冊漏
        # （寧漏勿誤）；拼接從原文重組後再 collapse
        #（各自 collapse 後直接拼會在 CJK-ASCII 交界丟空格，見樣本自檢）。
        small: list[tuple[str, str]] = []
        for path, new in cands:
            if not new or not new.strip():
                continue
            if 0 < len(_collapse(new)) < INLINE_COPY_MIN:
                small.append((path, new))
        if len(small) >= 2:
            list_exempt = any(LIST_REQ_CUE.search(t) for t in all_texts)
            reported: set[str] = set()
            for size in (2, 3):
                for combo in itertools.combinations(small, size):
                    if list_exempt and any(_is_list_block(raw) for _p, raw in combo):
                        continue
                    detail = _union_candidate([raw for _p, raw in combo], prompts, joined)
                    if not detail:
                        continue
                    for path, _raw in combo:
                        if path in reported:
                            continue
                        reported.add(path)
                        out.append({"kind": "copy_of_inline", "path": path, "detail": detail})
        return out

    def _test_claim(self, steps: list[Step], delivs: dict[str, tuple[str, str]]
                    ) -> list[dict[str, Any]]:
        m = CLAIMS.search(self.final_text or "")
        if not m:
            return []
        quote = _sentence_around(self.final_text, m.start(), m.end())
        runs = []
        for s in steps:
            if tool_kind(s.tool) != "shell":
                continue
            cmd = _command_of(self.tr, s)
            if not (RUNNERS.search(cmd) or is_test_script_run(cmd)):
                continue
            out = self.tr.output_text(s)
            if s.error or FAIL_OUT.search(out) or FAIL_OUT_2.search(out):
                runs.append((s, "failed", cmd))
            elif PASS_OUT.search(out) or PASS_OUT_2.search(out):
                runs.append((s, "passed", cmd))
            else:
                runs.append((s, "unreadable", cmd))
        if not runs:
            return [{"kind": "test_claim", "sub": "none", "quote": quote}]
        last, outcome, cmd = runs[-1]
        if outcome == "failed":
            return [{"kind": "test_claim", "sub": "failed", "quote": quote, "step": last.n,
                     "cmd": cmd}]
        if outcome == "unreadable":
            self.notes["test_outcome_unreadable"] = last.n
            return []
        code_changes = [s for s in steps if s.seq > last.seq and any(
            _ext(str(w["path"])) in CODE_HINT_EXT - {".json", ".yaml", ".yml", ".toml"}
            for w in s.writes)]
        if code_changes:
            s = code_changes[-1]
            p = next(str(w["path"]) for w in s.writes
                     if _ext(str(w["path"])) in CODE_HINT_EXT)
            return [{"kind": "test_claim", "sub": "stale", "quote": quote, "step": s.n,
                     "last_pass": last.n, "path": p}]
        return []

    def _claimed_runs(self) -> list[dict[str, Any]]:
        """方向 A「跑過沒」（2026-10-26，第 90 輪）：最終訊息以過去式声称「執行/跑了」某條
        反引號命令（首詞必須是已知 CLI 名稱、鄰窗無建議措辭），但整份命令記錄查無。
        三層保守濾網見 `RUN_CLAIM_CUE` 旁的註解。Advisory only：`zerostop.pushable_for`
        明確排除，只進交件說明（docs/UNIVERSAL_TASKS.md §2）。"""
        text = self.final_text or ""
        if not text:
            return []
        cmds: list[str] = []
        for s in self.tr.steps:
            if tool_kind(s.tool) != "shell":
                continue
            c = _command_of(self.tr, s)
            if c:
                cmds.append(c.lower())
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RUN_CLAIM_SPAN.finditer(text):
            token = m.group(1).lower()
            if token in seen or token not in RUN_CLAIM_TOOLS:
                continue
            seen.add(token)
            start, end = m.span()
            if any(token in c for c in cmds):     # 記錄裡有＝跑過（pip→pip3 也算）
                continue
            near = text[max(0, start - 20):min(len(text), end + 20)]
            if not RUN_CLAIM_CUE.search(near):
                continue
            wide = text[max(0, start - 60):min(len(text), end + 60)]
            if RUN_CLAIM_SUGGEST.search(wide):
                continue
            out.append({"kind": "claimed_run", "sub": "none", "cmd_token": token,
                        "quote": _sentence_around(text, start, end)})
        return out

    def _unfetched_sources(self, task_texts: list[str]) -> list[dict[str, Any]]:
        """方向 A「抓過沒」（2026-10-28，第 100 輪）：任務點到 URL＋鄰窗有抓取線索，但整份記錄
        沒有任何一步碰到該 URL，且最終訊息沒有老實說連不上。濾網與證據面見 `URL_RE` 旁註解。
        Advisory only：`zerostop.pushable_for` 明確排除，只進交件說明（docs/UNIVERSAL_TASKS.md §2）。"""
        task = "\n".join(task_texts)
        cand: list[tuple[str, str]] = []          # (url, 任務文字裡的線索句)
        for m in URL_RE.finditer(task):
            url = m.group(0).rstrip(".,;:!?。，；：、")
            key = _url_key(url)
            if any(key == _url_key(u) for u, _ in cand):
                continue
            start, end = m.span()
            if FETCH_CUE.search(task[max(0, start - 60):min(len(task), end + 60)]):
                cand.append((url, _sentence_around(task, start, end)))
        if not cand:
            return []
        # 證據面：任何一步的輸入／輸出碰到該 URL 就算抓過（curl、fetch 工具、腳本、引用皆算——寧漏勿誤）。
        touched: set[str] = set()
        for s in self.tr.steps:
            for txt in (self.tr.input_text(s), self.tr.output_text(s)):
                if txt:
                    touched.update(_url_key(u) for u in URL_RE.findall(txt))
        final = self.final_text or ""
        # 整段誠實豁免：最終訊息在 fetch 動詞附近老實說連不上（URL 不必重提）→ 一律不報。
        if final and any(
                UNFETCHED_UNAVAILABLE.search(final[max(0, mm.start() - 100):min(len(final), mm.end() + 100)])
                for mm in FETCH_CUE.finditer(final)):
            return []
        out: list[dict[str, Any]] = []
        for url, quote in cand:
            key = _url_key(url)
            if key in touched:
                continue
            if final and any(
                    UNFETCHED_UNAVAILABLE.search(final[max(0, mm.start() - 80):min(len(final), mm.end() + 80)])
                    for mm in URL_RE.finditer(final)
                    if _url_key(mm.group(0).rstrip(".,;:!?。，；：、")) == key):
                continue
            out.append({"kind": "unfetched", "sub": "none", "url": url,
                        "host": key.split("/", 1)[0], "quote": quote})
        return out

    def _claimed_writes(self) -> list[dict[str, Any]]:
        """方向 A「寫過沒」（2026-10-28，第 125 輪）：最終訊息以過去式聲稱「寫入/存成/產生」某個
        反引號檔名，但整份記錄查無該檔（任何一步的輸入或輸出都碰不到它的 basename），且該檔在最新
        索引裡也不存在。濾網與證據面見 `WRITE_CLAIM_CUE` 旁註解。Advisory only：
        `zerostop.pushable_for` 明確排除，只進交件說明（docs/UNIVERSAL_TASKS.md §2）。"""
        text = self.final_text or ""
        if not text:
            return []
        latest = self.tr.index(self.tr.latest_index())
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in WRITE_CLAIM_SPAN.finditer(text):
            path = m.group(1)
            base = path.rsplit("/", 1)[-1]
            key = base.lower()
            if key in seen:
                continue
            seen.add(key)
            # 證據面①：basename 出現在任何一步的輸入或輸出 → 視為已記錄（寧漏勿誤）。
            recorded = False
            for s in self.tr.steps:
                for t in (self.tr.input_text(s), self.tr.output_text(s)):
                    if t and base.lower() in t.lower():
                        recorded = True
                        break
                if recorded:
                    break
            if recorded:
                continue
            # 證據面②：該檔在最新索引裡存在（絕對／相對路徑皆算）→ 聲稱與現實一致 → 不報。
            if any(f == path or f.endswith("/" + path) or f.rsplit("/", 1)[-1].lower() == key
                   for f in latest):
                continue
            start, end = m.span()
            near = text[max(0, start - 80):min(len(text), end + 80)]
            if not WRITE_CLAIM_CUE.search(near):
                continue
            if WRITE_CLAIM_NEGATION.search(near):
                continue
            wide = text[max(0, start - 100):min(len(text), end + 100)]
            if WRITE_CLAIM_SUGGEST.search(wide):
                continue
            out.append({"kind": "claimed_write", "sub": "none", "path": path,
                        "quote": _sentence_around(text, start, end)})
        return out

    def _failed_steps(self, steps: list[Step], delivs: dict[str, tuple[str, str]],
                      materials: list[str]) -> list[dict[str, Any]]:
        out = []
        has_test_claim = bool(CLAIMS.search(self.final_text or ""))
        written_scripts = {str(w["path"]).rsplit("/", 1)[-1] for s in steps for w in s.writes
                           if _ext(str(w["path"])) in {".py", ".js", ".ts", ".sh", ".mjs"}}
        deliv_scripts = {d.rsplit("/", 1)[-1] for d in delivs
                         if _ext(d) in {".py", ".js", ".ts", ".sh", ".mjs"}}
        has_code_deliv = any(_ext(d) in CODE_HINT_EXT for d in delivs)
        for i, s in enumerate(steps):
            if tool_kind(s.tool) != "shell":
                continue
            cmd = _command_of(self.tr, s)
            clean_cmd = _strip_shell_comments(cmd)
            outp = self.tr.output_text(s)
            is_runner = bool(RUNNERS.search(clean_cmd))
            is_test_script = is_test_script_run(clean_cmd)
            is_test_cmd = is_runner or is_test_script
            failed = bool(s.error) or bool(re.search(r"Traceback \(most recent call last\)|"
                                                     r"\bError:|Exception:", outp))
            if is_test_cmd and (FAIL_OUT.search(outp) or FAIL_OUT_2.search(outp)):
                failed = True
            if failed and _no_match_only(clean_cmd, outp + "\n" + str(s.error or "")):
                failed = False                    # grep／rg 找不到＝結束碼 1，不是失敗（正式批次 2 次誤報）
            if not failed or not clean_cmd or PROBE_CMD.match(clean_cmd) or IMPORT_PROBE.search(clean_cmd):
                continue
            later = steps[i + 1:]
            # v3.7+：測試（腳本或 runner）紅了、之後又有一次跑測試是綠的＝修好了，不算略過；
            # 若最後訊息宣稱通過，交給 `_test_claim` 處理，不重複報。
            if is_test_cmd:
                if has_test_claim:
                    continue
                if any(tool_kind(t.tool) == "shell"
                       and (RUNNERS.search(_strip_shell_comments(_command_of(self.tr, t)))
                            or is_test_script_run(_strip_shell_comments(_command_of(self.tr, t))))
                       and not t.error and not FAIL_OUT.search(self.tr.output_text(t))
                       and not FAIL_OUT_2.search(self.tr.output_text(t)) for t in later):
                    continue
                # 若後面還有另一次失敗的測試執行，只報最後一次失敗的測試執行
                if any(tool_kind(t.tool) == "shell"
                       and (RUNNERS.search(_strip_shell_comments(_command_of(self.tr, t)))
                            or is_test_script_run(_strip_shell_comments(_command_of(self.tr, t))))
                       and (t.error or FAIL_OUT.search(self.tr.output_text(t))
                            or FAIL_OUT_2.search(self.tr.output_text(t))) for t in later):
                    continue
            runs_own = any(re.search(r"(?<![\w.-])" + re.escape(b) + r"\b", clean_cmd)
                           for b in written_scripts)
            runs_deliv = any(re.search(r"(?<![\w.-])" + re.escape(b) + r"\b", clean_cmd)
                             for b in deliv_scripts)
            cued_mats = [m for m in materials if m in clean_cmd or m.rsplit("/", 1)[-1] in clean_cmd]
            reads_given = bool(cued_mats)
            if not (runs_own or reads_given or (is_test_cmd and has_code_deliv)):
                continue
            wrote_after = any(w for t in later for w in t.writes if str(w["path"]) in delivs)
            # 先寫交付物、再跑測試或跑交付物本身失敗，之後沒改也沒重跑通過就直接收工
            unfixed_after_deliv = bool(delivs) and not wrote_after and (
                (is_test_cmd and has_code_deliv) or runs_deliv
            )
            if not (wrote_after or unfixed_after_deliv):
                continue
            norm = _norm_cmd(cmd)
            if any(tool_kind(t.tool) == "shell" and _norm_cmd(_command_of(self.tr, t)) == norm
                   and not t.error and not re.search(r"Traceback|\bError:",
                                                     self.tr.output_text(t)) for t in later):
                continue
            # 讀給定資料／跑自寫腳本失敗（非測試），但後續已有成功的替代（另一支自寫腳本跑成、
            # 或讀到題目點名的資料）＝失敗是放棄的嘗試，不是略過。
            # 2026-10-25：runs_own 也適用——calc.py 跑失敗、改用 awk 或另一支自寫腳本算出
            # 正確值並交付，不應 failed_step 退回。無後續成功取代（test_s5：build.py 失敗後
            # 直接手寫報告）仍照退；is_test_cmd 照舊走上面的測試分支，不受此豁免影響。
            if (reads_given or runs_own) and not is_test_cmd:
                # 該資料在此步驟**之前**已有一次成功讀取＝已消費；這次是重覆 probe 失敗，不是略過。
                # C37 dabstep-14-s2（2026-10-02 正式批次）：agent 讀過 payments.csv 後再跑
                # `head -n 1 payments.csv` 失敗，改用別的方法算對並交付，仍被 failed_step 退回。
                if reads_given and self._material_consumed_before(steps, i, cued_mats, clean_cmd):
                    continue
                recovery_mats = cued_mats if reads_given else materials
                if any(tool_kind(t.tool) == "shell"
                       and not t.error
                       and not re.search(r"Traceback|\bError:", self.tr.output_text(t))
                       and (any(re.search(r"(?<![\w.-])" + re.escape(b) + r"\b",
                                          _strip_shell_comments(_command_of(self.tr, t)))
                                for b in written_scripts)
                            or any(m in _command_of(self.tr, t) or m.rsplit("/", 1)[-1] in _command_of(self.tr, t)
                                   for m in recovery_mats))
                       for t in later):
                    continue
            # 若此失敗指令操作了交付檔 d（如 sed -i、awk、patch 修改 d 失敗），
            # 但後續步驟中 d 已被 write/edit 工具覆寫，且最後的測試執行已通過（或後續無測試失敗），
            # 代表該次殼層修改失敗已被後續的直接寫檔覆寫並驗證通過，不應視為未處理的失敗步驟。
            target_delivs_in_cmd = [d for d in delivs if d in clean_cmd or d.rsplit("/", 1)[-1] in clean_cmd]
            if target_delivs_in_cmd and not is_test_cmd:
                overwritten = any(
                    str(w["path"]) in target_delivs_in_cmd or str(w["path"]).rsplit("/", 1)[-1] in target_delivs_in_cmd
                    for t in later for w in t.writes
                )
                has_subsequent_test_pass = any(
                    tool_kind(t.tool) == "shell"
                    and (RUNNERS.search(_strip_shell_comments(_command_of(self.tr, t)))
                         or is_test_script_run(_strip_shell_comments(_command_of(self.tr, t))))
                    and not t.error and not FAIL_OUT.search(self.tr.output_text(t))
                    and not FAIL_OUT_2.search(self.tr.output_text(t))
                    for t in later
                )
                if overwritten and has_subsequent_test_pass:
                    continue
            if self.final_text and MENTIONS_FAILURE.search(self.final_text) and not (is_test_cmd and has_code_deliv):
                continue
            err = next((ln for ln in reversed(outp.strip().splitlines()) if ln.strip()),
                       str(s.error or "failed"))
            item: dict[str, Any] = {"kind": "failed_step", "step": s.n, "cmd": cmd, "error": err}
            if is_test_cmd and has_code_deliv:
                item["sub"] = "test_failed"
                hint = _extract_test_hint(outp + "\n" + str(s.error or ""), err=err)
                if hint:
                    item["test_hint"] = hint
            out.append(item)
        return out

    def _invalid_outputs(self, delivs: dict[str, tuple[str, str]],
                         outs: list[tuple[str, str]], task_texts: list[str], corpus: str,
                         start_idx: str | None, latest_idx: str | None, *,
                         only_answer: bool = False) -> list[dict[str, Any]]:
        """檢查交付物的結構與基本有效性（`empty`、`syntax`、`stub`、`contract_shape`）。"""
        out: list[dict[str, Any]] = []
        latest = self.tr.index(latest_idx)
        req_paths = {r for r, _ in outs}
        candidates: list[tuple[str, str, str, bool]] = [
            (path, old, new, True) for path, (old, new) in sorted(delivs.items())
        ]
        for rel, _raw in outs:
            actual = rel if rel in latest else next(
                (f for f in sorted(latest) if f.endswith("/" + rel)), None
            )
            if actual and actual not in delivs:
                old_t = self.tr.file_text(start_idx, actual) or ""
                new_t = self.tr.file_text(latest_idx, actual)
                if new_t is not None and "\x00" not in new_t:
                    candidates.append((actual, old_t, new_t, False))

        joined_task = "\n".join(task_texts)
        req_at_tags = list(dict.fromkeys(AT_TAG_REQ_RE.findall(joined_task)))
        req_funcs = list(dict.fromkeys(
            next((g for g in m.groups() if g), "")
            for m in REQ_FUNC_RE.finditer(joined_task)
            if any(m.groups())
        ))

        for path, old, new, was_written in candidates:
            ext = _ext(path)
            base = path.rsplit("/", 1)[-1]
            is_req = path in req_paths or any(path.endswith("/" + r) for r in req_paths)
            # 若任務已明確點名交付物（如 answer.txt），中間產生的其它探索暫存檔不作格式／空檔攔截
            if req_paths and not is_req:
                continue

            # 1) empty：要求的交付物或本回合寫出的主要檔案為空（排除 __init__.py 等合法空檔）
            if not new.strip():
                if is_req or (was_written and base not in {"__init__.py", "py.typed", ".gitkeep", ".keep"}):
                    out.append({"kind": "invalid_output", "sub": "empty", "path": path,
                                "detail": "file is empty"})
                continue

            # 2) syntax：本回合寫出的檔案有語法錯誤、未解衝突標記、或誤包了 Markdown 程式碼圍欄
            tree: ast.Module | None = None
            if was_written:
                first_ln = next((ln.strip() for ln in new.splitlines() if ln.strip()), "")
                old_first = next((ln.strip() for ln in old.splitlines() if ln.strip()), "")
                if (ext not in {".md", ".rst", ".adoc", ".tex", ".html", ".htm"}
                        and first_ln.startswith("```") and not old_first.startswith("```")):
                    out.append({"kind": "invalid_output", "sub": "syntax", "path": path,
                                "line": 1, "detail": "starts with a Markdown code fence"})
                    continue
                if CONFLICT_MARKER_RE.search(new) and not CONFLICT_MARKER_RE.search(old):
                    out.append({"kind": "invalid_output", "sub": "syntax", "path": path,
                                "detail": "contains unresolved merge conflict markers"})
                    continue
                if ext == ".py":
                    try:
                        tree = ast.parse(new, filename=path)
                    except SyntaxError as e:
                        out.append({"kind": "invalid_output", "sub": "syntax", "path": path,
                                    "line": e.lineno or 1,
                                    "detail": f"Python SyntaxError: {e.msg}"})
                        continue
                elif ext == ".json":
                    try:
                        json.loads(new)
                    except json.JSONDecodeError as e:
                        out.append({"kind": "invalid_output", "sub": "syntax", "path": path,
                                    "line": e.lineno, "detail": f"invalid JSON: {e.msg}"})
                        continue
                elif ext == ".jsonl":
                    bad_jsonl = None
                    for ln_i, ln_s in enumerate(new.splitlines(), 1):
                        if not ln_s.strip():
                            continue
                        try:
                            json.loads(ln_s)
                        except json.JSONDecodeError as e:
                            bad_jsonl = (ln_i, e.msg)
                            break
                    if bad_jsonl is not None:
                        out.append({"kind": "invalid_output", "sub": "syntax", "path": path,
                                    "line": bad_jsonl[0],
                                    "detail": f"invalid JSON Lines: {bad_jsonl[1]}"})
                        continue
                elif ext == ".toml":
                    try:
                        tomllib.loads(new)
                    except Exception as e:  # noqa: BLE001
                        out.append({"kind": "invalid_output", "sub": "syntax", "path": path,
                                    "detail": f"invalid TOML: {e}"})
                        continue
            elif ext == ".py":
                try:
                    tree = ast.parse(new, filename=path)
                except SyntaxError:
                    tree = None

            # 3) stub：未實作的 NotImplementedError／todo!()、或把 Traceback／NaN／拒絕訊息寫進答案檔
            if ext == ".py" and tree is not None and (was_written or is_req):
                stub_fn = _python_stub_function(tree, check_pass=was_written and is_req)
                if stub_fn is not None:
                    fn_name, fn_line, fn_why = stub_fn
                    out.append({"kind": "invalid_output", "sub": "stub", "path": path,
                                "line": fn_line, "detail": f"function {fn_name} {fn_why}"})
                    continue
            elif ext in {".rs", ".js", ".ts", ".go", ".java", ".cpp", ".c", ".cs", ".kt", ".swift"} \
                    and (was_written or is_req):
                if re.search(r"\b(?:todo!\s*\(|unimplemented!\s*\(|NotImplementedException|"
                             r"UnsupportedOperationException)\b", new):
                    out.append({"kind": "invalid_output", "sub": "stub", "path": path,
                                "detail": "contains unimplemented stub"})
                    continue

            if was_written and ext in DOC_EXT:
                if ("Traceback (most recent call last):" in new
                        and "Traceback (most recent call last):" not in old
                        and "```" not in new):
                    out.append({"kind": "invalid_output", "sub": "stub", "path": path,
                                "detail": "contains a Python traceback instead of a result"})
                    continue
                # Task 3: 未展開的 Python 物件 repr() 殘留
                if (is_req or only_answer) and re.search(r"<(?:function|generator object|cell at|built-in function)\b|\b(?:DataFrame\(|Series\(\[\])", new):
                    out.append({"kind": "invalid_output", "sub": "stub", "path": path,
                                "detail": "contains un-evaluated Python object representation"})
                    continue
                nonempty = [ln.strip() for ln in new.splitlines() if ln.strip()]
                if len(nonempty) == 1:
                    vlow = nonempty[0].lower()
                    if vlow in {"nan", "-nan", "inf", "-inf", "<na>", "nat", "tbd", "todo", "placeholder"} \
                            or (vlow in {"none", "null", "undefined"}
                                and not re.search(r"\b" + re.escape(vlow) + r"\b",
                                                  corpus + "\n" + joined_task, re.I)):
                        out.append({"kind": "invalid_output", "sub": "stub", "path": path,
                                    "detail": f"contains placeholder value {nonempty[0]!r}"})
                        continue
                    # Task 3: 空集合交付攔截（問句要求具體項目／名單，但寫出空集合）
                    if vlow in {"[]", "{}", "set()", "list()"} and (is_req or only_answer):
                        if re.search(r"\b(?:which|list|what are|find all|identify)\b", joined_task, re.I):
                            out.append({"kind": "invalid_output", "sub": "empty", "path": path,
                                        "detail": "empty collection []"})
                            continue

                    # Task E Rule 2: 單一腳本無驗算與空篩選攔截（輸出 0 / 0.0 / Not Applicable / []）
                    if vlow in {"not applicable", "n/a", "0", "0.0", "0.00", "0.000"} and (is_req or only_answer):
                        if re.search(r"\b(?:what is|what are|which|how many|total|fee|amount|count|sum|find|calculate|list)\b", joined_task, re.I):
                            last_calc = None
                            for s in reversed(self.tr.steps):
                                raw_in = self.tr.blob_text(s.input_blob) or ""
                                if any(k in raw_in for k in ("python", "python3", "df", ".py")):
                                    last_calc = s
                                    break
                            if last_calc:
                                raw_out = self.tr.blob_text(last_calc.output_blob) or ""
                                outp = raw_out
                                try:
                                    j_out = json.loads(raw_out)
                                    if isinstance(j_out, dict):
                                        outp = str(j_out.get("stdout") or j_out.get("output") or j_out.get("text") or raw_out)
                                except Exception:
                                    pass
                                raw_in = self.tr.blob_text(last_calc.input_blob) or ""
                                cmd = raw_in
                                try:
                                    j_in = json.loads(raw_in)
                                    if isinstance(j_in, dict):
                                        cmd = str(j_in.get("command") or j_in.get("cmd") or raw_in)
                                except Exception:
                                    pass
                                has_inspect = any(kw in outp.lower() or kw in cmd.lower()
                                                  for kw in ("unique", "value_counts", "head(", "groupby", "dtypes", "info("))
                                if not has_inspect and (
                                    "empty dataframe" in outp.lower()
                                    or "series([], " in outp.lower()
                                    or outp.strip() in {"0", "0.0", "0.00", "[]", "set()", ""}
                                ):
                                    out.append({
                                        "kind": "invalid_output",
                                        "sub": "empty_filter",
                                        "path": path,
                                        "detail": f"filter produced zero rows/empty result ({vlow}) without checking column values"
                                    })
                                    continue
                if (is_req or only_answer) and REFUSAL_FILE_RE.search(new):
                    out.append({"kind": "invalid_output", "sub": "stub", "path": path,
                                "detail": "contains a refusal message instead of the answer"})
                    continue

            # 4) contract_shape：明確要求的 @key[value] 標籤、單一答案無多餘標題、要求的頂層函式、CSV 資料列
            if (was_written or is_req) and req_at_tags and ext in {".txt", ".md", ""} \
                    and (is_req or len(delivs) == 1):
                found_tags = {k: v.strip() for k, v in AT_TAG_VAL_RE.findall(new) if v.strip()}
                generic = {"name", "tag", "field", "item", "var", "id", "metric",
                           "value", "val", "answer", "ans", "number", "num", "key", "label",
                           "result", "x"}
                specific = [k for k in req_at_tags if k.lower() not in generic]
                if not found_tags:
                    out.append({"kind": "invalid_output", "sub": "contract_shape", "path": path,
                                "detail": "missing required @key[value] format"})
                    continue
                missing_k = [k for k in specific if k not in found_tags]
                if missing_k:
                    tags_s = ", ".join(f"@{k}[...]" for k in missing_k[:3])
                    out.append({"kind": "invalid_output", "sub": "contract_shape", "path": path,
                                "detail": f"missing required tag(s): {tags_s}"})
                    continue

            if was_written and only_answer and ext == ".txt" and not req_at_tags:
                if PROSE_ANSWER_RE.search(new) and not PROSE_ANSWER_RE.search(joined_task):
                    out.append({"kind": "invalid_output", "sub": "contract_shape", "path": path,
                                "detail": "the task asks for ONLY the final answer without headings or prose"})
                    continue

            if ext == ".py" and tree is not None and req_funcs \
                    and (base == "solution.py" or is_req):
                defs, has_star = _python_top_level_names(tree)
                if not has_star:
                    missing_fn = [fn for fn in req_funcs if fn not in defs]
                    if missing_fn:
                        out.append({"kind": "invalid_output", "sub": "contract_shape", "path": path,
                                    "detail": f"missing required top-level definition `{missing_fn[0]}`"})
                        continue

            if was_written and is_req and ext in {".csv", ".tsv"} and not old.strip():
                csv_lns = [ln for ln in new.splitlines() if ln.strip()]
                if len(csv_lns) == 1:
                    out.append({"kind": "invalid_output", "sub": "contract_shape", "path": path,
                                "detail": "CSV output has only a header row and no data rows"})
                    continue
        return out


# ── module-level helpers ────────────────────────────────────────────────

def _is_abstractmethod(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and "abstract" in dec.id:
            return True
        if isinstance(dec, ast.Attribute) and "abstract" in dec.attr:
            return True
    return False


def _python_stub_function(tree: ast.Module, *, check_pass: bool = False
                          ) -> tuple[str, int, str] | None:
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _is_abstractmethod(n)]
    for fn in funcs:
        body = list(fn.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Raise) and stmt.exc is not None:
                exc = stmt.exc.func if isinstance(stmt.exc, ast.Call) else stmt.exc
                if isinstance(exc, ast.Name) and exc.id in ("NotImplementedError", "NotImplemented"):
                    return (fn.name, fn.lineno, "still raises NotImplementedError")
            if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Name) \
                    and stmt.value.id == "NotImplemented":
                return (fn.name, fn.lineno, "returns NotImplemented")
    if check_pass:
        cand_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _is_abstractmethod(node):
                cand_funcs.append(node)
            elif isinstance(node, ast.ClassDef):
                is_exc = any(
                    (isinstance(b, ast.Name) and b.id.endswith(("Exception", "Error")))
                    or (isinstance(b, ast.Attribute) and b.attr.endswith(("Exception", "Error")))
                    for b in node.bases
                )
                if is_exc:
                    continue
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _is_abstractmethod(sub):
                        if not (sub.name.startswith("__") and sub.name.endswith("__") and sub.name != "__init__"):
                            cand_funcs.append(sub)
        non_init = [f for f in cand_funcs if f.name != "__init__"] or cand_funcs
        if non_init:
            all_pass = True
            for fn in non_init:
                body = list(fn.body)
                if body and isinstance(body[0], ast.Expr) \
                        and isinstance(body[0].value, ast.Constant) \
                        and isinstance(body[0].value.value, str):
                    body = body[1:]
                if not (len(body) == 1 and (
                    isinstance(body[0], ast.Pass)
                    or (isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and body[0].value.value is Ellipsis)
                )):
                    all_pass = False
                    break
            if all_pass:
                return (non_init[0].name, non_init[0].lineno, "is an unimplemented stub (pass)")
    return None


def _python_top_level_names(tree: ast.Module) -> tuple[set[str], bool]:
    names: set[str] = set()
    has_star = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    has_star = True
                else:
                    names.add(alias.asname or alias.name)
    return names, has_star


def finding_id(f: dict[str, Any], scope: str) -> str:
    key = {"unsourced": (f.get("path"), f.get("value")), "unread": (f.get("path"),),
           "missing_output": (f.get("path"),),
           "invalid_output": (f.get("path"), f.get("sub"), f.get("detail")),
           "test_claim": (f.get("sub"),), "failed_step": (_norm_cmd(f.get("cmd") or ""),),
           "claimed_run": (f.get("cmd_token"),),
           "claimed_write": (f.get("path"),),
           "skeleton": (f.get("path"),), "stale_output": (f.get("path"),),
           "copy_of_input": (f.get("path"), f.get("input")),
           "copy_of_inline": (f.get("path"),)}
    raw = repr((scope, f["kind"], key.get(f["kind"], ())))
    return "z_" + hashlib.sha256(raw.encode()).hexdigest()[:10]


def _num_match(n: Num, observed: float) -> bool:
    if observed is None or (isinstance(observed, float) and math.isnan(observed)):
        return False
    for target, tol in n.candidates():
        if abs(observed - target) <= tol:
            return True
        # 截斷：寫出的位數以下直接捨去
        if target >= 0 and 0 <= observed - target < 2 * tol:
            return True
    return False


def _typed(raw: str, obj: Any, path: str, step_inputs: list[tuple[Step, str]]) -> bool:
    """這個值是 agent 自己打出來的：寫這個交付物的步驟的輸入（寫檔工具的內容、殼層的 echo／heredoc、
    內嵌程式碼裡的字面值）裡就有它。由程式算出來寫進去的（輸入裡沒有這個字面值）不算。"""
    forms = {raw, raw.replace(",", "")}
    if isinstance(obj, Num):
        forms.add(re.sub(r"[^\d.]", "", raw))
    for s, text in step_inputs:
        if not any(str(w["path"]) == path for w in s.writes):
            continue
        if any(f and f in text for f in forms):
            return True
    return False


def _strip_shell_comments(cmd: str) -> str:
    body = _HEREDOC.sub(" ", cmd or "")
    lines = [ln.strip() for ln in body.splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    return "\n".join(lines)


def _no_match_only(cmd: str, outp: str) -> bool:
    """這一步的「失敗」只是搜尋沒找到：指令（或管線的最後一段）是 grep／rg 類，輸出裡沒有真的錯誤。
    2026-10-25：也認 `cd dir && grep …` 這類鏈頭（INTERPRETER 早已認 `cd … &&` 前綴）——
    逐段去掉 `cd …` 前綴後照舊判斷；`grep: No such file` 這類真錯誤仍算失敗。"""
    clean = _strip_shell_comments(cmd)
    while (m := re.match(r"^\s*cd\s+\S+\s*(?:&&|\|\||;)\s*", clean)) is not None:
        clean = clean[m.end() :]
    lines = [ln for ln in clean.splitlines() if ln.strip()]
    if lines and all(
        SEARCH_CMD.match(ln) or SEARCH_CMD.match([x for x in re.split(r"(?<!\|)\|(?!\|)", ln) if x.strip()][-1])
        for ln in lines
    ):
        return not SEARCH_ERR.search(outp or "")
    stages = [x for x in re.split(r"(?<!\|)\|(?!\|)", clean) if x.strip()]
    last = stages[-1] if stages else ""
    if not (SEARCH_CMD.match(clean) or SEARCH_CMD.match(last)):
        return False
    return not SEARCH_ERR.search(outp or "")


def _changed_lines(old: str, new: str) -> list[int]:
    a, b = old.splitlines(), new.splitlines()
    out: list[int] = []
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out.extend(range(j1 + 1, j2 + 1))
    return out


def _exempt_lines(lines: list[str]) -> set[int]:
    out, level = set(), None
    in_code = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_code = not in_code
            out.add(i)
            continue
        if in_code:
            out.add(i)
            continue
        h = re.match(r"^\s{0,3}(#{1,6})\s", ln)
        if h:
            lv = len(h.group(1))
            if level is not None and lv <= level:
                level = None
            if EXEMPT_HEADINGS.match(ln):
                level = lv
                out.add(i)
                continue
        if level is not None:
            out.add(i)
        if i < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i]) and "|" in ln:
            out.add(i)                            # 表格的標題列
        if re.match(r"^\s*\d+[.)]\s", ln):
            pass
    return out


def _strip_code(line: str) -> str:
    line = re.sub(r"`[^`]*`", " ", line)
    line = re.sub(r"^\s*\d+[.)]\s", " ", line)      # 清單編號
    return re.sub(r"#[0-9a-fA-F]{3,8}\b", " ", line)  # 色碼


def _sentence_around(text: str, s: int, e: int) -> str:
    a = max(text.rfind(".", 0, s), text.rfind("\n", 0, s)) + 1
    b_candidates = [x for x in (text.find(".", e), text.find("\n", e)) if x >= 0]
    b = min(b_candidates) if b_candidates else len(text)
    return text[a:b].strip()[:120]


def _command_of(tr: Trace, s: Step) -> str:
    obj = tr.input_obj(s)
    if isinstance(obj, dict):
        for k in ("command", "cmd", "script"):
            v = obj.get(k)
            if isinstance(v, list):
                v = " ".join(map(str, v))
            if isinstance(v, str) and v.strip():
                return v.strip()
    return tr.input_text(s).strip()[:500]


def _norm_cmd(cmd: str) -> str:
    clean = _strip_shell_comments(cmd)
    lines = [ln for ln in clean.splitlines() if ln.strip()]
    target = lines[-1] if lines and INTERPRETER.match(lines[-1]) else clean
    words = re.findall(r"[^\s\"']+", target or cmd or "")
    first_file = next((w for w in words[1:] if re.search(r"\.\w{1,10}$", w)), "")
    return f"{words[0] if words else ''} {first_file}".strip()


def evidence_for(rec: Recorder, *, platform: str, session: str, final_text: str | None = None,
                 today: _dt.date | None = None) -> dict[str, Any]:
    return Evidence(rec, platform=platform, session=session, final_text=final_text,
                    today=today).run()


def parse_test_score(text: str) -> tuple[int, int] | None:
    """從測試輸出解析 (passed, failed)。"""
    m_ran = re.search(r"Ran\s+(\d+)\s+tests?", text)
    if m_ran:
        total = int(m_ran.group(1))
        if "\nOK" in text or text.strip().endswith("OK"):
            return total, 0
        m_fail = re.search(r"failures=(\d+)", text)
        m_err = re.search(r"errors=(\d+)", text)
        failed = (int(m_fail.group(1)) if m_fail else 0) + (int(m_err.group(1)) if m_err else 0)
        return max(0, total - failed), failed

    m_pass = re.search(r"(\d+)\s+passed\b", text)
    m_fail = re.search(r"(\d+)\s+failed\b", text)
    if m_pass or m_fail:
        p_cnt = int(m_pass.group(1)) if m_pass else 0
        f_cnt = int(m_fail.group(1)) if m_fail else 0
        return p_cnt, f_cnt

    m_cargo = re.search(r"test result: (?:ok|FAILED)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed", text)
    if m_cargo:
        return int(m_cargo.group(1)), int(m_cargo.group(2))

    return None


def restore_best_checkpoint(rec: Recorder, target_index: str, step_n: int) -> bool:
    """將工作區還原至最高分步驟的狀態，更新 state.last_index 並記錄 checkpoint_restore 事件。"""
    try:
        idx = rec.load_index(target_index)
        if not idx:
            return False
        from . import workspace as W
        with rec._lock():
            st = rec._state()
            before_index = st.get("last_index")
            cur_idx: W.Index = {}
            if isinstance(before_index, str) and before_index:
                try:
                    cur_idx = rec.load_index(before_index)
                except Exception:
                    cur_idx = {}
            if not cur_idx and rec.workspace.is_dir():
                cur_idx = W.scan(rec.workspace, None, skip=rec.skip, blobs=rec.blobs)
            changes = W.diff(cur_idx, idx) if cur_idx else []
            # 先確認所有目標檔案皆可完整還原（在庫裡或工作區原位 sha 相符），避免半途失敗污染工作區
            for rel, e in sorted(idx.items()):
                if ".." in pathlib.PurePosixPath(rel).parts or e.sha256.startswith(("big:", "secret:")):
                    return False
                if e.sha256.startswith("link:"):
                    continue
                if rec.blobs.has(e.sha256):
                    continue
                src = rec.workspace / rel
                if not (src.is_file() and not src.is_symlink() and W._sha_file(src) == e.sha256):
                    return False
            # 移除 target_index 之後才新增的檔案
            for c in changes:
                if c.after is None:
                    gone = rec.workspace / c.path
                    if ".." not in pathlib.PurePosixPath(c.path).parts and (gone.is_file() or gone.is_symlink()):
                        gone.unlink(missing_ok=True)
            missing = W.materialize(idx, rec.blobs, rec.workspace, workspace=rec.workspace)
            if missing:
                return False
            restored = [c.path for c in changes] if changes else sorted(idx.keys())
            st["last_index"] = target_index
            rec._save(st)
            rec._append("checkpoint_restore", {
                "before_index": before_index,
                "target_index": target_index,
                "step": step_n,
                "restored_files": restored,
                "changes": [c.to_json() for c in changes],
            })
        return True
    except Exception:
        return False
