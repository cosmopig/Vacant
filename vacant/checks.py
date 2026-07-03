"""可序列化的 check-spec → Verifier —— 讓「客觀檢查」能跨 MCP / 行程邊界傳遞。

問題（為什麼需要這支）：`Vacant.solve` 的 verifier 是 Python callable，
MCP / 跨行程傳不過去。所以要讓 agent（如 Hermes）能把「怎麼檢查」交給 vacant，
就得把檢查表達成 JSON-able 的 check-spec，vacant 端再 compile 回 Verifier。

支援的 check（由弱到強）：
  {"type":"equals","value":"olleh"}                      # 正規化後相等
  {"type":"contains","value":"foo","ignore_case":true}   # 子字串
  {"type":"regex","pattern":"^\\d{4}$"}                  # 正則命中
  {"type":"json_schema","schema":{...}}                  # 輸出是合法 JSON 且符合 schema
  {"type":"run_python","code":"assert solve('abc')=='cba'"}  # 跑測試（最強：客觀可執行）

防「AI 自產自評」（規格 §10）：最強的 check 是**客觀、可執行**的——跑測試、
驗結構、比對環境真值。這些不是「再問一次 LLM 對不對」，所以擋得住模型自我背書。
run_python 是**受限沙箱**（獨立行程 `python -I` + 逾時 + CPU rlimit + 暫存 cwd +
不繼承使用者環境），對「模型自己寫的測試」夠用；但**不是對抗惡意程式碼的安全邊界**
——要跑不可信程式請改用容器 / gVisor。此處誠實標明邊界。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable

Verifier = Callable[[str], bool]

# 從模型輸出抽出程式碼（優先 ```python fenced；無 fence 則視整段為碼）。
_FENCE = re.compile(r"```(?:python|py)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text: str) -> str:
    """從模型回答抽出 Python 程式碼區塊；沒有 fence 就回整段（去頭尾空白）。"""
    m = _FENCE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


def _normalize(s: str) -> str:
    """寬鬆正規化：去頭尾空白、去包住的引號/反引號。供 equals 比對單一答案 token。"""
    s = (s or "").strip()
    for q in ('"', "'", "`"):
        if len(s) >= 2 and s[0] == q and s[-1] == q:
            s = s[1:-1].strip()
    return s


# --- JSON / schema（最小自帶驗證器，jsonschema 在則優先用）-------------------
def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i, j = text.find(open_c), text.rfind(close_c)
        if 0 <= i < j:
            try:
                return json.loads(text[i : j + 1])
            except Exception:
                continue
    raise ValueError("no JSON found in answer")


_JSON_TYPES = {
    "object": dict, "array": list, "string": str,
    "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
}


def _mini_validate(data: Any, schema: dict) -> bool:
    """type / required / properties / items 的最小遞迴驗證（無第三方依賴）。"""
    t = schema.get("type")
    if t is not None:
        py = _JSON_TYPES.get(t)
        if py is None or not isinstance(data, py):
            return False
        if t == "integer" and isinstance(data, bool):  # bool 是 int 的子類，排除
            return False
    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                return False
        for key, sub in schema.get("properties", {}).items():
            if key in data and not _mini_validate(data[key], sub):
                return False
    if isinstance(data, list) and "items" in schema:
        return all(_mini_validate(x, schema["items"]) for x in data)
    return True


def _json_matches(answer: str, schema: dict) -> bool:
    try:
        data = _extract_json(answer)
    except Exception:
        return False
    try:
        import jsonschema  # 選用：在的話用標準驗證
        jsonschema.validate(data, schema)
        return True
    except ImportError:
        return _mini_validate(data, schema)
    except Exception:
        return False


# --- run_python 受限沙箱 ------------------------------------------------------
def _cpu_limits(seconds: int) -> None:  # pragma: no cover - 在子行程裡跑
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
    except Exception:
        pass


def _run_python(code: str, test: str, timeout: float) -> bool:
    """把 `code + test` 丟進受限子行程跑；exit 0（assert 全過）→ True。"""
    src = (code or "") + "\n\n" + (test or "") + "\n"
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "_cand.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(src)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": d, "TMPDIR": d}
        try:
            r = subprocess.run(
                [sys.executable, "-I", path],
                capture_output=True, text=True, timeout=timeout, cwd=d, env=env,
                preexec_fn=(lambda: _cpu_limits(int(timeout) + 1)) if os.name == "posix" else None,
            )
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False


# --- 公開：compile_check ------------------------------------------------------
def compile_check(spec: dict) -> Verifier:
    """把可序列化的 check-spec 編譯成 Verifier(answer)->bool。spec 無效則 ValueError。"""
    if not isinstance(spec, dict):
        raise ValueError("check spec must be an object")
    t = spec.get("type")

    if t == "equals":
        target = str(spec["value"])
        norm = bool(spec.get("normalize", True))
        if norm:
            target = _normalize(target)
        return lambda a: (_normalize(a) if norm else (a or "")) == target

    if t == "contains":
        sub = str(spec["value"])
        ci = bool(spec.get("ignore_case", False))
        if ci:
            return lambda a: sub.lower() in (a or "").lower()
        return lambda a: sub in (a or "")

    if t == "regex":
        flags = re.DOTALL | (re.IGNORECASE if spec.get("ignore_case") else 0)
        pat = re.compile(str(spec["pattern"]), flags)
        return lambda a: bool(pat.search(a or ""))

    if t == "json_schema":
        schema = spec["schema"]
        return lambda a: _json_matches(a, schema)

    if t == "run_python":
        test = str(spec["code"])
        timeout = float(spec.get("timeout", 8))
        do_extract = bool(spec.get("extract_code", True))
        return lambda a: _run_python(extract_code(a) if do_extract else (a or ""), test, timeout)

    raise ValueError(f"unknown check type: {t!r}")
