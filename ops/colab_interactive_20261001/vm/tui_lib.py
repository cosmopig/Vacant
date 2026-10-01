#!/usr/bin/env python3
"""tui_lib — i1001 互動式批次的「純函式」那一半：不碰 tmux、不碰使用者、不碰檔案系統以外的東西，所以能在
錄好的 pi session 檔上離線重播測試（tests/test_colab_interactive_20261001.py）。

這支在架構裡承重什麼：互動式 pi 沒有「行程結束＝跑完」這個訊號（`pi --print` 有），所以「這一段 session 跑完了沒」
全靠讀 pi 寫在磁碟上的 session jsonl 判斷。判錯的後果不對稱：太早（把 Vacant 還要送回去的那 0.4 秒當成結束）會讓 C 組
看起來沒作用；太晚只是多花時間。所以這裡把規則寫成**可重播**的狀態機（`tail_state`＋`DoneDetector`），並用
pi 0.87.1 實測錄下的 6 種結尾（plain／claim／error／errorfinal／length／abort）當測試資料。

量到的事實（`PI_INTERACTIVE_NOTES.md`；pi 0.87.1、tmux 3.4、stub 模型，不是真模型）：
- session 檔在第一則 assistant 訊息寫完之前**不存在**；沒有 `agent_end` 條目。
- 結尾：assistant `stop`／`length`／`aborted`＝最終；`error` 後面接 `context_edit`＝pi 會重試（退避 2／4／8 秒，三次），
  `error` 後面什麼都沒有＝重試用完；`toolUse`／`toolResult`／`user`／`custom_message`＝還在跑。
- Vacant 的送回是同一個 run 裡的 `custom_message`（`vacant-check`），在最終 `stop` 之後 0.37–0.48 秒（n=7）。
⚠ 沒量過的（不要當成已知）：真 vLLM 下的延遲分布；超長工作區上的 Vacant 檢查（上限 330 秒，期間 session 檔不寫東西，
  所以 C 組另外看 `vacant_network hook` 行程）；自動壓縮（compaction）的呼叫在最終 `stop` 之後會不會出現。

誠實邊界：`IDLE_S` 是實測最大間隔的 30 倍左右，不是證明；`late_write_after_done` 與 `max_gap_after_final_s`
逐段記進 meta.json，整批跑完用它們回頭檢查這個數字。
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Iterable

MODEL_DEFAULT = "gemma-4-12b-it-qat"
PROVIDER = "harbor-endpoint"
INSTR_SENTENCE = ("Read goal.md and contract.md in this directory and do what they say. "
                  "Use your tools to write the file.")
PANE_EXIT_RE = re.compile(r"__PANE_EXIT_(\d+)__")
IDLE_S_DEFAULT = 15.0

# ── 名字 ────────────────────────────────────────────────────────────────────────────────────────


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def cell_name(prefix: str, arm: str, bank: str, task_id: str, sample: int, attempt: int = 1) -> str:
    """`<前綴>-<組>-<題庫>-<題>-s<第幾次>`；void 重跑那一次尾巴多 `v2`（分析讀 meta.json 的欄位，不讀名字）。"""
    return safe(f"{prefix}-{arm}-{bank}-{task_id}-s{sample}" + ("" if attempt == 1 else f"v{attempt}"))


def session_tag(cell: str, n: int) -> str:
    """代理的標籤＝一段 session 一個（帳本才分得開 K／R 的第 2、3 段）：`<格子>.n<第幾段>`。"""
    return f"{cell}.n{n}"


def sessions_dir_name(n: int) -> str:
    return "sessions" if n == 1 else f"sessions-{n}"


# ── pi session jsonl：增量讀 ＋ 結尾判讀 ─────────────────────────────────────────────────────────


def iso(s: str) -> float:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def summarize(e: dict) -> dict:
    """條目縮成判讀要用的欄位（長工作階段的 jsonl 可到數 MB，輪詢時只留摘要）。"""
    m = e.get("message") or {}
    out: dict[str, Any] = {"type": e.get("type"), "timestamp": e.get("timestamp")}
    if m:
        out["message"] = {"role": m.get("role"), "stopReason": m.get("stopReason")}
        if m.get("errorMessage"):
            out["message"]["errorMessage"] = str(m["errorMessage"])[:400]
    if e.get("customType"):
        out["customType"] = e["customType"]
    return out


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join((p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type", "text") == "text")
    return ""


class SessionTail:
    """增量讀一個 `--session-dir` 底下的所有 *.jsonl（只吃寫完的整行；半行等下一輪）。

    屬性：`summ`（每條的摘要）、`bytes`（已讀位元組總數）、`first_user_text`（第一則 user 訊息全文，
    用來核對「打進去的字」是不是就是那一句）、`n_files`。"""

    def __init__(self, sess_dir: str | os.PathLike):
        self.dir = str(sess_dir)
        self.pos: dict[str, int] = {}
        self.summ: list[dict] = []
        self.bytes = 0
        self.first_user_text: str | None = None
        self.n_files = 0

    def poll(self) -> int:
        new = 0
        files = sorted(glob.glob(os.path.join(self.dir, "**", "*.jsonl"), recursive=True))
        self.n_files = len(files)
        for f in files:
            try:
                size = os.stat(f).st_size
            except OSError:
                continue
            pos = self.pos.get(f, 0)
            if size <= pos:
                continue
            try:
                with open(f, "rb") as fh:
                    fh.seek(pos)
                    data = fh.read(size - pos)
            except OSError:
                continue
            cut = data.rfind(b"\n")
            if cut < 0:
                continue
            self.pos[f] = pos + cut + 1
            self.bytes += cut + 1
            for line in data[:cut + 1].splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                self.summ.append(summarize(e))
                new += 1
                m = e.get("message") or {}
                if self.first_user_text is None and e.get("type") == "message" and m.get("role") == "user":
                    self.first_user_text = _text_of(m.get("content"))
        return new

    @property
    def state(self) -> str:
        return tail_state(self.summ)


def read_entries(sess_dir: str | os.PathLike) -> list[dict]:
    """整個讀完（結束時存檔／測試用；輪詢請用 SessionTail）。"""
    out: list[dict] = []
    for f in sorted(glob.glob(os.path.join(str(sess_dir), "**", "*.jsonl"), recursive=True)):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def tail_state(entries: list[dict]) -> str:
    """running | final | retrying | error_final | empty（pi 0.87.1 的結尾判讀；見模組 docstring）。

    對完整條目與 `summarize` 的摘要都成立。"""
    i = len(entries) - 1
    while i >= 0 and entries[i].get("type") not in ("message", "custom_message"):
        i -= 1
    if i < 0:
        return "empty"
    e = entries[i]
    m = e.get("message") or {}
    if e.get("type") == "custom_message" or m.get("role") != "assistant":
        return "running"
    sr = m.get("stopReason")
    if sr in ("stop", "aborted", "length"):
        return "final"
    if sr == "error":
        after = [x.get("type") for x in entries[i + 1:]]
        return "retrying" if "context_edit" in after else "error_final"
    return "running"            # toolUse、pending、deferred


def last_assistant(entries: list[dict]) -> dict | None:
    for e in reversed(entries):
        m = e.get("message") or {}
        if e.get("type") == "message" and m.get("role") == "assistant":
            return m
    return None


def max_gap_after_final(entries: list[dict]) -> float | None:
    """「最終 stop 的 assistant 條目 → 下一個條目」的最大間隔（秒）：IDLE_S 的稽核數字。
    只算後面真的還有條目的 stop（Vacant 送回、使用者追問）；沒有後續就沒有間隔。"""
    gaps = []
    for i, e in enumerate(entries[:-1]):
        m = e.get("message") or {}
        if e.get("type") == "message" and m.get("role") == "assistant" and m.get("stopReason") == "stop":
            a, b = e.get("timestamp"), entries[i + 1].get("timestamp")
            if a and b:
                try:
                    gaps.append(iso(b) - iso(a))
                except ValueError:
                    pass
    return round(max(gaps), 3) if gaps else None


# ── 「跑完了」的狀態機 ───────────────────────────────────────────────────────────────────────────


class DoneDetector:
    """done ＝ 同時成立：
      1. `tail_state` 是 final 或 error_final（`retrying`／`running`／`empty` 都不算）；
      2. 沒有活著的 `vacant_network hook` 行程（C 組；A 組永遠 0）；
      3. 安靜 ≥ idle_s：session 位元組、代理帳本的通數與最後一通時間、（C）hook 事件檔大小、tail_state、hook 行程數
         全都沒動。
    `sig` 由呼叫端組（任何會動的東西都放進去）；這裡只管「sig 或狀態一變就重新計時」。"""

    def __init__(self, idle_s: float = IDLE_S_DEFAULT):
        self.idle_s = float(idle_s)
        self._sig: Any = object()
        self._state: Any = None
        self._hook: Any = None
        self.last_change: float | None = None
        self.done_at: float | None = None

    def update(self, now: float, state: str, sig: Any, hook_procs: int = 0) -> bool:
        if self.last_change is None or sig != self._sig or state != self._state or hook_procs != self._hook:
            self._sig, self._state, self._hook, self.last_change = sig, state, hook_procs, now
        if state in ("final", "error_final") and hook_procs == 0 and now - self.last_change >= self.idle_s:
            self.done_at = now
            return True
        return False

    def quiet_s(self, now: float) -> float:
        return 0.0 if self.last_change is None else now - self.last_change


# ── 錯誤分類：哪些是基礎設施（void）、哪些是 agent 的結果 ────────────────────────────────────────

_CODE_RE = re.compile(r"^\s*(\d{3})\b")


def error_code(message: str | None) -> int | None:
    m = _CODE_RE.match(message or "")
    return int(m.group(1)) if m else None


def error_is_infra(message: str | None) -> bool:
    """pi 的 `errorMessage` 開頭是 HTTP 狀態（`500: {...}`）。5xx／429／408／402（記帳代理的預算閘）＝基礎設施；
    其他 4xx（例如 400 上下文太長）是這一跑自己的結果；沒有狀態碼的（連線被重設、串流中斷、fetch failed…）
    一律當基礎設施——寧可重跑一次，也不把斷線算成 agent 失敗。"""
    code = error_code(message)
    if code is None:
        return True
    return code >= 500 or code in (402, 408, 429)


# ── 代理帳本（共用一份、增量讀、按標籤加總）──────────────────────────────────────────────────────


class LedgerTail:
    """`/srv/eval/proxy/ledger.jsonl` 的增量讀（所有格子共用；一個執行緒更新、多個格子查）。
    `stats(tag)`：{calls, non200, stream_errors, prompt_tokens, completion_tokens, last_ts, last_end_ts}。"""

    def __init__(self, path: str | os.PathLike, min_interval_s: float = 1.0):
        self.path = str(path)
        self.pos = 0
        self.rows: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def refresh(self, force: bool = False) -> None:
        now = time.time()
        with self.lock:
            if not force and now - self._last < self.min_interval_s:
                return
            self._last = now
            try:
                size = os.stat(self.path).st_size
            except OSError:
                return
            if size < self.pos:                       # 被輪替／截短：從頭
                self.pos, self.rows = 0, {}
            if size == self.pos:
                return
            with open(self.path, "rb") as fh:
                fh.seek(self.pos)
                data = fh.read(size - self.pos)
            cut = data.rfind(b"\n")
            if cut < 0:
                return
            self.pos += cut + 1
            for line in data[:cut + 1].splitlines():
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                self._add(x)

    def _add(self, x: dict) -> None:
        tag = x.get("tag") or "untagged"
        r = self.rows.setdefault(tag, {"calls": 0, "non200": 0, "stream_errors": 0, "prompt_tokens": 0,
                                       "completion_tokens": 0, "cached_tokens": 0, "last_ts": 0.0, "last_end_ts": 0.0,
                                       "statuses": {}})
        r["calls"] += 1
        st = x.get("status")
        r["statuses"][str(st)] = r["statuses"].get(str(st), 0) + 1
        if st != 200:
            r["non200"] += 1
        if x.get("stream_error"):
            r["stream_errors"] += 1
        u = x.get("usage") or {}
        r["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        r["completion_tokens"] += int(u.get("completion_tokens") or 0)
        r["cached_tokens"] += int(u.get("cached_tokens") or 0)
        ts = float(x.get("ts") or 0.0)
        r["last_ts"] = max(r["last_ts"], ts)
        r["last_end_ts"] = max(r["last_end_ts"], ts + float(x.get("latency_s") or 0.0))

    def stats(self, tag: str) -> dict:
        self.refresh()
        with self.lock:
            return dict(self.rows.get(tag) or {"calls": 0, "non200": 0, "stream_errors": 0, "prompt_tokens": 0,
                                               "completion_tokens": 0, "cached_tokens": 0, "last_ts": 0.0,
                                               "last_end_ts": 0.0, "statuses": {}})

    def final_stats(self, tag: str) -> dict:
        self.refresh(force=True)
        return self.stats(tag)


# ── 畫面（pane）判讀 ─────────────────────────────────────────────────────────────────────────────


def footer_ready(pane_text: str, model: str = MODEL_DEFAULT, provider: str = PROVIDER) -> bool:
    """TUI 收得到鍵了：頁腳 `(<provider>) <model>` 已畫出。更早打的字會被丟掉（pi 進 raw mode 時清 stdin）。
    `pi v0.87.1` 的橫幅不是準備好的訊號。"""
    return f"({provider}) {model}" in pane_text


def trust_dialog_present(pane_text: str) -> bool:
    return "Trust project folder?" in pane_text


#: 互動模式遇到這些路徑會停在「信任專案資料夾？」選單（`pi --print` 靜默略過）。實測於 PI_INTERACTIVE_NOTES §5.1。
TRUST_TRIGGERS = (".pi/settings.json", ".pi/extensions", ".pi/skills", ".pi/prompts", ".pi/themes",
                  ".pi/SYSTEM.md", ".pi/APPEND_SYSTEM.md", ".agents/skills")


def trust_triggers(workspace: str | os.PathLike, ancestors: tuple[str, ...] = ("/",)) -> list[str]:
    """工作區（以及沙箱裡看得到的上層：`/app` 的上一層就是 `/`）裡會觸發信任對話框的路徑。回傳實際存在的那幾條。
    注意是**沙箱裡**的祖先，不是主機上 `/srv/runs/<格子>/` 那一串（沙箱把 app 綁到 /app）。"""
    out = []
    for d in (Path(workspace), *(Path(x) for x in ancestors)):
        for t in TRUST_TRIGGERS:
            if (d / t).exists():
                out.append(str(d / t))
    return out


def pane_exit_rc(pane_text: str) -> int | None:
    m = PANE_EXIT_RE.search(pane_text)
    return int(m.group(1)) if m else None


# ── 打字 ─────────────────────────────────────────────────────────────────────────────────────────


def typing_plan(text: str) -> tuple[str, str]:
    """(模式, 實際要送的字)：單行、沒有 tab ⇒ `send-keys -l`；否則 `paste-buffer -p`（括號貼上），tab 換成 4 個空白
    （send-keys 會把 tab 吃掉當補全鍵；貼上時 pi 把 tab 轉成 4 個空白——兩邊一致）。
    第一個字元不可以是 `/` 或 `!`（會被當成指令）。"""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    if t[:1] in ("/", "!"):
        raise ValueError("typed text must not start with / or ! (pi treats it as a command)")
    t = t.replace("\t", "    ")
    return ("line" if "\n" not in t else "paste"), t


def typed_matches(first_user_text: str | None, typed: str) -> bool | None:
    """pi 記下的第一則 user 訊息就是我們打的字嗎（逐字，只容許行尾空白）。None＝session 檔還沒有 user 訊息。"""
    if first_user_text is None:
        return None
    norm = lambda s: "\n".join(x.rstrip() for x in s.replace("\r\n", "\n").split("\n")).strip()   # noqa: E731
    return norm(first_user_text) == norm(typed)


# ── 交付物與重試條件 ──────────────────────────────────────────────────────────────────────────────


def deliverable_name(bank: str, task_dir: str | os.PathLike | None = None) -> str:
    """這一題要 agent 交的那個檔：LCB＝solution.py、dabench／databench＝answer.txt、polyglot＝hidden/expected.json 的 solution_file。"""
    if bank.startswith("lcb"):
        return "solution.py"
    if bank in ("dabench", "databench"):
        return "answer.txt"
    if bank == "polyglot_py" and task_dir is not None:
        try:
            return json.loads((Path(task_dir) / "hidden" / "expected.json").read_text())["solution_file"]
        except (OSError, ValueError, KeyError):
            pass
    return "solution.py"


def has_deliverable(workspace: str | os.PathLike, name: str) -> bool:
    p = Path(workspace) / name
    try:
        return p.is_file() and not p.is_symlink() and p.stat().st_size > 0
    except OSError:
        return False


def needs_retry(prev_session: dict, workspace: str | os.PathLike, deliverable: str) -> tuple[bool, str | None]:
    """R 組的條件（規格：「逾時或沒有交件」才開新一段）。回傳 (要不要重試, 原因)。"""
    if prev_session.get("timeout"):
        return True, "timeout"
    if not has_deliverable(workspace, deliverable):
        return True, "no_deliverable"
    return False, None


# ── K 組：給 agent 看的失敗文字（KS-1：不寫責任／懲罰／究責措辭）─────────────────────────────────

KS1_PHRASES = ("你有責任", "你會被懲罰", "你將被懲罰", "你要負責", "後果自負", "you are responsible",
               "you will be punished", "you will be held accountable", "your fault", "blame", "punish",
               "penalt", "accountab", "careless", "you failed", "you did not follow", "you were wrong")


def ks1_clean(text: str) -> str:
    low = text.lower()
    for p in KS1_PHRASES:
        if p in low:
            raise ValueError(f"KS-1: forbidden wording {p!r} in a prompt text")
    return text


K_PREFACE = ("The visible checks for this task were run on the file you wrote. "
             "These are the results they reported:")
K_CLOSING = "Please correct the file so the checks pass, and write it again."


def failure_text(judge: dict, limit: int = 2400) -> str:
    """從 bridge `judge` 的 JSON 取「可見檢查」回報的細節（`results[].detail` 與 `reasons`），原文、不加評語。
    沒有可用細節時給一句中性的話（不編造內容）。"""
    lines: list[str] = []
    for r in judge.get("results") or []:
        if r.get("status") in ("PASS", None):
            continue
        d = str(r.get("detail") or "").strip()
        if d:
            lines.append(d)
    if not lines:
        lines = [str(x).strip() for x in (judge.get("reasons") or []) if str(x).strip()]
    if not lines:
        lines = ["(the checks did not report any detail)"]
    body = "\n".join(lines)
    if len(body) > limit:
        body = body[:limit // 2] + "\n...[cut]...\n" + body[-(limit // 2):]
    return body


def k_instruction(instr: str, judge: dict) -> str:
    """K 組第 2、3 段的字：同一句任務＋空行＋可見檢查的回報。第一個字元仍是任務那句的字母。"""
    text = f"{instr}\n\n{K_PREFACE}\n\n{failure_text(judge)}\n\n{K_CLOSING}"
    return ks1_clean(text)


# ── 單段 session 的 void 判斷 ────────────────────────────────────────────────────────────────────


def classify_session(*, ready: bool, trust_unhandled: bool, typed_ok: bool | None, final_state: str,
                     last_error: str | None, ledger: dict, session_file: bool, timeout: bool,
                     pane_rc_early: int | None, exited_before_done: bool) -> tuple[bool, str | None]:
    """(是不是 void, 原因)。順序就是優先序；全部是「基礎設施，不是 agent 的表現」（規格的 infra_void 規則）：
    - 頁腳一直沒出現／信任對話框沒處理掉／行程在第一通請求前就死了；
    - 打進去的字不等於那一句（輸入壞了＝這一組沒收到固定的變因）；
    - 最終 assistant 條目是基礎設施型錯誤（5xx／429／408／402／串流中斷）；
    - 這一段的任何一通代理帳本不是 200 或帶 stream_error（照 C5 analyze.py 的規則）；
    - 完全沒有模型呼叫；逾時但沒有任何一通完成（模型端卡死）。"""
    if not ready:
        return True, "footer_timeout" if not trust_unhandled else "trust_dialog_unhandled"
    if typed_ok is False:
        return True, "input_mismatch"
    if final_state == "error_final" and error_is_infra(last_error):
        return True, f"model_error_final: {(last_error or '')[:120]}"
    if ledger.get("non200") or ledger.get("stream_errors"):
        return True, f"proxy_non200: {ledger.get('non200', 0)} call(s), {ledger.get('stream_errors', 0)} stream error(s)"
    if ledger.get("calls", 0) == 0 and not session_file:
        return True, "pi_died_before_first_request" if exited_before_done else "no_model_call"
    if timeout and ledger.get("calls", 0) == 0:
        return True, "timeout_without_any_model_reply"
    if exited_before_done and pane_rc_early not in (None, 0) and ledger.get("calls", 0) == 0:
        return True, f"pi_crash_before_first_request rc={pane_rc_early}"
    return False, None


# ── 位置（同時在跑的 pi 對話數）──────────────────────────────────────────────────────────────────


class SlotPool:
    """固定的全域並行：同時在跑的 pi 對話數 ≤ n。
    - `acquire(k)` 一次拿 k 個（單位的 A、C 兩條線一起開，確保同一時段）；
    - `acquire(1, priority=True)` 給「已經在跑的單位」的接續段（K／R 的第 2、3 段）：有人在等接續時新單位不准插隊，
      這樣池子不會被新單位塞滿而讓老單位拖長。"""

    def __init__(self, n: int):
        self.n = max(1, int(n))
        self.used = 0
        self.cont_waiting = 0
        self.cv = threading.Condition()
        self.peak = 0

    def acquire(self, k: int = 1, *, priority: bool = False) -> int:
        k = max(1, min(int(k), self.n))
        with self.cv:
            if priority:
                self.cont_waiting += 1
            try:
                while not (self.n - self.used >= k and (priority or self.cont_waiting == 0)):
                    self.cv.wait()
                self.used += k
                self.peak = max(self.peak, self.used)
            finally:
                if priority:
                    self.cont_waiting -= 1
        return k

    def release(self, k: int = 1) -> None:
        with self.cv:
            self.used = max(0, self.used - k)
            self.cv.notify_all()

    class _Ctx:
        def __init__(self, pool: "SlotPool", k: int, priority: bool):
            self.pool, self.k, self.priority = pool, k, priority

        def __enter__(self):
            self.k = self.pool.acquire(self.k, priority=self.priority)
            return self

        def __exit__(self, *a):
            self.pool.release(self.k)

    def slot(self, k: int = 1, *, priority: bool = False) -> "SlotPool._Ctx":
        return SlotPool._Ctx(self, k, priority)


def pgrep_hook_count(pids_text: str) -> int:
    return len([x for x in pids_text.split() if x.strip().isdigit()])


def jsonl_rows(path: str | os.PathLike) -> Iterable[dict]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return
