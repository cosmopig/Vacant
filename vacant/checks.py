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

NW-2a：沙箱本體對外也直接曝露成 `run_python_check(candidate_code, test_code,
*, timeout=8) -> bool`，供 Auditor（稽核＝重跑 hidden_check）與 codebench 的
MBPP+ 任務族共用同一顆沙箱，不必每處各自兜一份 subprocess 邏輯。
"""

from __future__ import annotations

import ast
import builtins
import json
import os
import re
import secrets
import signal
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
        if not all(_mini_validate(x, schema["items"]) for x in data):
            return False
    if isinstance(data, (str, list)):
        if "minLength" in schema and isinstance(data, str) and len(data) < int(schema["minLength"]):
            return False
        if "maxLength" in schema and isinstance(data, str) and len(data) > int(schema["maxLength"]):
            return False
        if "minItems" in schema and isinstance(data, list) and len(data) < int(schema["minItems"]):
            return False
        if "maxItems" in schema and isinstance(data, list) and len(data) > int(schema["maxItems"]):
            return False
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


def project_checked_answer(answer: str, spec: dict) -> str:
    """只保留 verifier 實際判定的 artifact，避免把未檢查尾文交給下游 agent。"""
    check_type = spec.get("type") if isinstance(spec, dict) else None
    if check_type == "run_python" and spec.get("extract_code", True):
        return extract_code(answer)
    if check_type == "json_schema":
        return json.dumps(
            _extract_json(answer), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"), allow_nan=False)
    if check_type == "equals" and spec.get("normalize", True):
        return _normalize(answer)
    return (answer or "").strip()


# --- run_python 受限沙箱 ------------------------------------------------------
def _cpu_limits(seconds: int) -> None:  # pragma: no cover - 在子行程裡跑
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
    except Exception:
        pass


_BASE_IMPORTS = {"__future__"}
_FORBIDDEN_CALLS = {
    "breakpoint", "compile", "delattr", "dir", "eval", "exec", "exit", "getattr",
    "globals", "help", "input", "locals", "open", "quit", "setattr", "vars",
}
_FORBIDDEN_NAMES = {"__builtins__", "__import__", "builtins", *_FORBIDDEN_CALLS}
_FORBIDDEN_ATTRS = {
    "__builtins__", "__class__", "__dict__", "__globals__", "__mro__", "__subclasses__",
    "ag_frame", "cr_frame", "f_builtins", "f_globals", "f_locals", "gi_frame", "tb_frame",
    "_exit", "execv", "execve", "fork", "kill", "popen", "remove", "rmdir",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp",
    "spawnvpe", "system", "unlink",
}


def _candidate_functions(
    candidate_code: str, *, allowed_imports: tuple[str, ...] = (),
) -> list[str] | None:
    """擋明顯 process/file 旁路並回傳可由 verifier proxy 呼叫的頂層函式。"""
    try:
        tree = ast.parse(candidate_code or "")
    except SyntaxError:
        return None
    functions: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(value, ast.Lambda):
                functions.extend(t.id for t in targets if isinstance(t, ast.Name))
    import_roots = _BASE_IMPORTS | set(allowed_imports)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            return None
        if isinstance(node, ast.Attribute) \
                and (node.attr.startswith("__") or node.attr in _FORBIDDEN_ATTRS):
            return None
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] not in import_roots for alias in node.names):
                return None
        elif isinstance(node, ast.ImportFrom):
            if not node.module or node.module.split(".", 1)[0] not in import_roots:
                return None
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                return None
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                return None
    reserved = set(dir(builtins)) | {
        "ast", "builtins", "json", "os", "selectors", "subprocess", "sys", "time",
        "_protocol", "_selector", "_vacant_call", "_worker",
    }
    return list(dict.fromkeys(
        name for name in functions if name.isidentifier() and name not in reserved
    )) or None


def _worker_source() -> str:
    return r'''import ast
import json
import os
import sys

candidate_path, protocol_fd, nonce = sys.argv[1], int(sys.argv[2]), sys.argv[3]
protocol = os.fdopen(protocol_fd, "w", encoding="utf-8", buffering=1) if protocol_fd >= 0 else sys.stdout
safe_open = open
safe_compile = compile
safe_exec = exec
safe_repr = repr
safe_type = type
literal_eval = ast.literal_eval
scalar_types = (type(None), bool, int, float, str, bytes)
container_types = (list, tuple, set, frozenset)

def literal_repr(value):
    value_type = safe_type(value)
    if value_type in scalar_types:
        rendered = safe_repr(value)
        literal_eval(rendered)
        return rendered
    if value_type in container_types:
        for item in value:
            literal_repr(item)
        rendered = safe_repr(value)
        literal_eval(rendered)
        return rendered
    if value_type is dict:
        for key, item in value.items():
            literal_repr(key); literal_repr(item)
        rendered = safe_repr(value)
        literal_eval(rendered)
        return rendered
    raise TypeError("candidate values must use exact Python literal types")

def emit(payload):
    protocol.write(nonce + json.dumps(payload) + "\n")
    protocol.flush()

try:
    with safe_open(candidate_path, "r", encoding="utf-8") as fh:
        source = fh.read()
    namespace = {"__name__": "__vacant_candidate__", "__file__": candidate_path}
    safe_exec(safe_compile(source, candidate_path, "exec"), namespace, namespace)
except BaseException as exc:
    emit({"ok": False, "error": safe_type(exc).__name__})
    raise SystemExit(1)

emit({"ready": True})

for line in sys.stdin:
    try:
        request = json.loads(line)
        args, kwargs = ast.literal_eval(request["call"])
        function = namespace[request["function"]]
        if not callable(function):
            raise TypeError("candidate entry point is not callable")
        value = function(*args, **kwargs)
        payload = {
            "ok": True,
            "value": literal_repr(value),
            "args": literal_repr(args),
            "kwargs": literal_repr(kwargs),
        }
    except BaseException as exc:
        payload = {"ok": False, "error": safe_type(exc).__name__, "message": str(exc)[:500]}
    emit(payload)
'''


def _test_runner_source(
    *, worker_path: str, candidate_path: str, worker_cwd: str,
    nonce: str, call_timeout: float, test_code: str, function_names: list[str],
) -> str:
    proxies = "\n".join(
        f"def {name}(*args, **kwargs):\n"
        f"    return _vacant_call({name!r}, *args, **kwargs)"
        for name in function_names
    )
    return f'''import ast
import builtins
import json
import os
import selectors
import subprocess
import sys
import time

_nonce = {nonce!r}
_worker_env = {{"PATH": os.environ.get("PATH", ""), "HOME": {worker_cwd!r}, "TMPDIR": {worker_cwd!r}}}
if os.name == "posix":
    _read_fd, _write_fd = os.pipe()
    _worker = subprocess.Popen(
        [sys.executable, "-I", {worker_path!r}, {candidate_path!r}, str(_write_fd), _nonce],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        text=True, bufsize=1, cwd={worker_cwd!r}, env=_worker_env,
        pass_fds=(_write_fd,),
    )
    os.close(_write_fd)
    _protocol = os.fdopen(_read_fd, "r", encoding="utf-8")
else:
    _worker = subprocess.Popen(
        [sys.executable, "-I", {worker_path!r}, {candidate_path!r}, "-1", _nonce],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1, cwd={worker_cwd!r}, env=_worker_env,
    )
    _protocol = _worker.stdout
_selector = selectors.DefaultSelector()
_selector.register(_protocol, selectors.EVENT_READ)

_ready_deadline = time.monotonic() + {call_timeout!r}
while True:
    if _worker.poll() is not None:
        raise RuntimeError("candidate worker failed to initialize")
    ready = _selector.select(max(0.0, _ready_deadline - time.monotonic()))
    if not ready:
        _worker.kill()
        raise TimeoutError("candidate worker initialization timed out")
    line = _protocol.readline()
    if line.startswith(_nonce):
        response = json.loads(line[len(_nonce):])
        if response.get("ready"):
            break

def _vacant_call(function, *args, **kwargs):
    if _worker.poll() is not None:
        raise RuntimeError("candidate worker exited")
    try:
        call_repr = repr((args, kwargs))
        ast.literal_eval(call_repr)
    except Exception as exc:
        raise TypeError("solve arguments must be Python literals") from exc
    _worker.stdin.write(json.dumps({{"function": function, "call": call_repr}}) + "\\n")
    _worker.stdin.flush()
    deadline = time.monotonic() + {call_timeout!r}
    while time.monotonic() < deadline:
        if _worker.poll() is not None:
            raise RuntimeError("candidate worker exited")
        ready = _selector.select(max(0.0, deadline - time.monotonic()))
        if not ready:
            continue
        line = _protocol.readline()
        if not line:
            raise RuntimeError("candidate worker closed stdout")
        if not line.startswith(_nonce):
            continue
        response = json.loads(line[len(_nonce):])
        if not response.get("ok"):
            error_type = getattr(builtins, response.get("error", ""), RuntimeError)
            if not isinstance(error_type, type) or not issubclass(error_type, Exception):
                error_type = RuntimeError
            raise error_type(response.get("message", "candidate solve failed"))
        try:
            value = ast.literal_eval(response["value"])
            changed_args = ast.literal_eval(response["args"])
            changed_kwargs = ast.literal_eval(response["kwargs"])
        except Exception as exc:
            raise TypeError("solve result must be a Python literal") from exc
        for original, changed in zip(args, changed_args):
            if isinstance(original, list) and isinstance(changed, list):
                original[:] = changed
            elif isinstance(original, dict) and isinstance(changed, dict):
                original.clear(); original.update(changed)
            elif isinstance(original, set) and isinstance(changed, set):
                original.clear(); original.update(changed)
        for key, original in kwargs.items():
            changed = changed_kwargs.get(key)
            if isinstance(original, list) and isinstance(changed, list):
                original[:] = changed
            elif isinstance(original, dict) and isinstance(changed, dict):
                original.clear(); original.update(changed)
            elif isinstance(original, set) and isinstance(changed, set):
                original.clear(); original.update(changed)
        return value
    _worker.kill()
    raise TimeoutError("candidate solve timed out")

{proxies}

try:
{chr(10).join("    " + line for line in (test_code or "").splitlines())}
finally:
    if _worker.poll() is None:
        _worker.terminate()
        try:
            _worker.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            _worker.kill()
'''


def run_python_check(
    candidate_code: str,
    test_code: str,
    *,
    timeout: float = 8,
    allowed_imports: tuple[str, ...] = (),
) -> bool:
    """NW-2a：hidden tests 與候選碼分行程，透過 literal-only function proxy 驗證。

    verifier runner 持有 hidden tests；candidate worker 只持有候選碼。測試裡的 entry-point
    呼叫經 stdin/stdout RPC 送到 worker，回值必須可由 `ast.literal_eval` 還原。這會擋住
    `os._exit(0)` 提前把 verifier 偽裝成成功、候選碼直接讀同檔 hidden tests，以及常見
    process/file API。整個 process group 受 `python -I`、乾淨 env/cwd、CPU limit 與 wall
    timeout 約束；任何初始化、RPC、assert、例外或逾時失敗一律回 False。

    誠實邊界：AST allowlist 與 process separation 是應用層 hardening，不是惡意程式碼的
    完整 OS sandbox。高風險第三方碼仍應使用 container、gVisor 或獨立 VM。
    """
    if any(not isinstance(name, str) or not name.isidentifier() for name in allowed_imports):
        return False
    function_names = _candidate_functions(candidate_code, allowed_imports=allowed_imports)
    if timeout <= 0 or not function_names:
        return False
    with tempfile.TemporaryDirectory() as test_dir, tempfile.TemporaryDirectory() as worker_dir:
        candidate_path = os.path.join(worker_dir, "candidate.py")
        worker_path = os.path.join(worker_dir, "worker.py")
        runner_path = os.path.join(test_dir, "runner.py")
        nonce = "VACANT_RESULT_" + secrets.token_hex(16) + ":"
        call_timeout = max(0.1, timeout * 0.9)
        with open(candidate_path, "w", encoding="utf-8") as fh:
            fh.write(candidate_code or "")
        with open(worker_path, "w", encoding="utf-8") as fh:
            fh.write(_worker_source())
        with open(runner_path, "w", encoding="utf-8") as fh:
            fh.write(_test_runner_source(
                worker_path=worker_path,
                candidate_path=candidate_path,
                worker_cwd=worker_dir,
                nonce=nonce,
                call_timeout=call_timeout,
                test_code=test_code,
                function_names=function_names,
            ))
        env = {"PATH": os.environ.get("PATH", ""), "HOME": test_dir, "TMPDIR": test_dir}
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, "-I", runner_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=test_dir, env=env,
                preexec_fn=(lambda: _cpu_limits(int(timeout) + 1)) if os.name == "posix" else None,
                start_new_session=(os.name == "posix"),
            )
            proc.communicate(timeout=timeout)
            return proc.returncode == 0
        except subprocess.TimeoutExpired:
            if proc is not None:
                if os.name == "posix":
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:  # pragma: no cover - Windows
                    proc.kill()
                proc.communicate()
            return False
        except Exception:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.communicate()
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
        imports = spec.get("allowed_imports", [])
        if not isinstance(imports, list) or any(not isinstance(x, str) for x in imports):
            raise ValueError("run_python allowed_imports must be a list of module names")
        return lambda a: run_python_check(
            extract_code(a) if do_extract else (a or ""), test,
            timeout=timeout, allowed_imports=tuple(imports),
        )

    raise ValueError(f"unknown check type: {t!r}")
