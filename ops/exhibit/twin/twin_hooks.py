"""twin/twin_hooks — 分身那一跑「走 Vacant 0.9.x 產品的掛鉤路徑」的接線（過渡版，2026-10-12）。

## 這支在架構裡承重什麼

計畫 `plans/PLAN_TWIN_ON_091_HOOKS_20261012.md`：數位分身反映的是 Vacant 本身，儀表板也是 Vacant ⇒
分身每一跑的 pi 都要裝上 `vacant install` 對 pi 裝的那一份擴充（把每一步寫進 `VACANT_HOME/trace`
的簽章鏈、說做完時跑零設定檢查），儀表板（`vacant dashboard`）讀同一個 `VACANT_HOME` 就看得到每一跑。

**這支只做接線，不改 0.9.1 產品本身**：擴充檔是 `vacant install --agents pi` 自己寫出來的那一份
（`adapters/agents.PI_EXTENSION`，逐位元相同），`install.json` 的 `mode: evidence` 也是它寫的。

## 開關（預設關；沒設＝分身的行為和這支不存在時逐位元相同）

* `VACANT_TWIN_HOOKS=1` — 開。回滾＝拿掉這一行（再重啟迴圈）。
* `VACANT_HOME` — 儀表板與分身共用的 Vacant 資料夾（例 `/var/lib/vacant-twin/vacant_home`）。
* `VACANT_TWIN_HOOK_PIDIR` — `install` 把擴充裝在這個「pi 設定目錄」底下的 `extensions/vacant.ts`
  （預設 `<VACANT_HOME 的上一層>/pi_vacant`）。每一跑 pi 自己的設定目錄是拋棄式的（run-dir/pi_cfg），
  而且 `--no-extensions` 關了自動探索，所以 `twin_agent.sh` 用 `-e` 明確載入這一份。

## 撤回要刪乾淨（鐵律：觀眾資料）

0.9.1 的 trace 會存步驟（含 `ws_write` 的參數＝分身寫的信）、檔案差異（內容定址的 blob）、交件說明。
`erase()`：刪 `VACANT_HOME/trace/projects/<這一跑>`、只被這一跑引用的 blob、`intake/hooks` 裡以這一跑的
工作階段命名的檔。**即使之後把開關關掉（回滾）也照刪**——只要 `VACANT_HOME` 還設著。

## 誠實邊界（改碼請保留）

1. 共用的 `VACANT_HOME` 是整個**可寫**綁進每一位分身的圍牆（儀表板才看得到）。pi 模型叫得到的只有
   `ws_list/ws_read/ws_write`（只碰得到工作區），但 pi 這個行程本身在圍牆裡讀得到別位觀眾的 trace。
   跟 `twinenclose` 誠實邊界 2 同一級（「收住的是模型叫得到的工具，不是 pi 行程」）。
2. blob 是內容定址：兩位觀眾寫出逐位元相同的檔（例如世界檔 WORLD.md）時那份 blob 是共用的，
   撤回其中一位**不刪**被別的專案引用的 blob（那不是他的資料，也刪了會弄壞別人的重播）。
3. 這一層只在 pi 的擴充事件齊全時才完整：pi 0.85.1 沒有 `agent_before_settle`，擴充的「說做完時查一次並退回」
   不會觸發；`post_check()` 在 pi 結束後補跑同一個零設定檢查、只寫交件說明（不退回——沒有 session 可以退）。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ENV_FLAG = "VACANT_TWIN_HOOKS"
ENV_HOME = "VACANT_HOME"
ENV_PIDIR = "VACANT_TWIN_HOOK_PIDIR"
ENV_EXT = "VACANT_TWIN_HOOK_EXT"
EXT_REL = pathlib.Path("extensions") / "vacant.ts"
_HEX64 = re.compile(rb"[0-9a-f]{64}")


def enabled(env: dict[str, str] | None = None) -> bool:
    return (env if env is not None else os.environ).get(ENV_FLAG, "0").strip() == "1"


def vacant_home(env: dict[str, str] | None = None) -> pathlib.Path | None:
    v = (env if env is not None else os.environ).get(ENV_HOME, "").strip()
    return pathlib.Path(v).expanduser() if v else None


def pidir(env: dict[str, str] | None = None) -> pathlib.Path | None:
    e = env if env is not None else os.environ
    v = e.get(ENV_PIDIR, "").strip()
    if v:
        return pathlib.Path(v).expanduser()
    h = vacant_home(e)
    return (h.parent / "pi_vacant") if h else None


def ext_path(env: dict[str, str] | None = None) -> pathlib.Path | None:
    e = env if env is not None else os.environ
    v = e.get(ENV_EXT, "").strip()
    if v:
        return pathlib.Path(v)
    d = pidir(e)
    return (d / EXT_REL) if d else None


def encl_extras(env: dict[str, str] | None = None) -> dict[str, Any] | None:
    """圍牆要多給的東西；沒開、或缺資料夾／擴充檔 ⇒ `None`（不接，分身照舊跑）。

    回 `{"setenv": {K: V}, "rw": [path], "ro": [path]}`。fail-open：接不上就不接（展場不能因為這一層停掉）。
    """
    e = env if env is not None else os.environ
    if not enabled(e):
        return None
    h, x = vacant_home(e), ext_path(e)
    if h is None or x is None or not x.is_file():
        return None
    for q in (h, x):
        rq = q.resolve()
        if rq == REPO or REPO in rq.parents:    # repo 是唯讀綁進圍牆的，VACANT_HOME 不能在裡面
            return None
    h.mkdir(parents=True, exist_ok=True)
    return {"setenv": {ENV_FLAG: "1", ENV_HOME: str(h), ENV_EXT: str(x)},
            "rw": [str(h)], "ro": [str(x.parent.parent)]}


# ---------------------------------------------------------------------------
# 安裝（部署時跑一次）：呼叫產品自己的 `vacant install --agents pi`
# ---------------------------------------------------------------------------

def install(*, python: str = "/usr/bin/python3", budget_reminder: bool = False,
            env: dict[str, str] | None = None) -> dict[str, Any]:
    """用**產品本身**的安裝指令裝 pi 那一份。擴充檔裡寫死的 python 是 `python`（要在圍牆的 /usr 底下）。"""
    e = dict(env if env is not None else os.environ)
    h, d = vacant_home(e), pidir(e)
    if h is None or d is None:
        raise SystemExit("沒有 VACANT_HOME，不知道要裝到哪裡。")
    h.mkdir(parents=True, exist_ok=True)
    d.mkdir(parents=True, exist_ok=True)
    e.update({"VACANT_HOME": str(h), "PI_CODING_AGENT_DIR": str(d),
              "HOME": str(d / "home"), "PYTHONPATH": str(REPO)})
    (d / "home").mkdir(exist_ok=True)
    cmd = [python, "-m", "vacant_network", "install", "--agents", "pi", "--force"]
    cmd.append("--budget-reminder" if budget_reminder else "--no-budget-reminder")
    r = subprocess.run(cmd, env=e, capture_output=True, text=True, timeout=120, cwd=str(REPO))
    x = d / EXT_REL
    inst = h / "adapters" / "install.json"
    mode = None
    try:
        mode = json.loads(inst.read_text(encoding="utf-8")).get("mode")
    except (OSError, ValueError):
        pass
    return {"rc": r.returncode, "stdout": r.stdout[-600:], "stderr": r.stderr[-600:],
            "ext": str(x), "ext_exists": x.is_file(), "install_json": str(inst), "mode": mode}


# ---------------------------------------------------------------------------
# 撤回：刪 VACANT_HOME 裡這一跑的一切
# ---------------------------------------------------------------------------

def _project_dirs_for(home: pathlib.Path, ws: pathlib.Path) -> list[pathlib.Path]:
    """這個工作區對應的專案資料夾（用 state.json 的 `workspace` 比對，也試雜湊 key）。"""
    from vacant_network.trace.recorder import project_key
    proj = home / "trace" / "projects"
    out: list[pathlib.Path] = []
    cand = {str(ws), str(ws.resolve())}
    keys = {project_key(ws)}
    for k in keys:
        if (proj / k).is_dir():
            out.append(proj / k)
    if proj.is_dir():
        for d in sorted(proj.iterdir()):
            if d in out or not d.is_dir():
                continue
            try:
                st = json.loads((d / "state.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(st, dict) and st.get("workspace") in cand:
                out.append(d)
    return out


def _hexes_in(p: pathlib.Path) -> set[str]:
    out: set[str] = set()
    try:
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
    except OSError:
        return out
    for f in files:
        try:
            out |= {m.decode() for m in _HEX64.findall(f.read_bytes())}
        except OSError:
            pass
    return out


def _blob_closure(objs: pathlib.Path, seeds: set[str], limit: int = 20000) -> set[str]:
    """seeds 加上它們（若是索引 blob）再指到的 sha。只收真的存在於 objects 的。"""
    seen: set[str] = set()
    todo = [s for s in seeds if (objs / s[:2] / s).is_file()]
    while todo and len(seen) < limit:
        s = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        try:
            data = (objs / s[:2] / s).read_bytes()
        except OSError:
            continue
        if len(data) > 5_000_000:
            continue
        for m in _HEX64.findall(data):
            h = m.decode()
            if h not in seen and (objs / h[:2] / h).is_file():
                todo.append(h)
    return seen


def erase(ws: pathlib.Path, home: pathlib.Path | None = None) -> dict[str, Any]:
    """刪掉 `home` 裡屬於工作區 `ws` 的追緝紀錄。回只有類別與計數的報告（會進撤回回報）。"""
    home = home if home is not None else vacant_home()
    rep: dict[str, Any] = {"home_set": home is not None, "projects": 0, "blobs": 0,
                           "blobs_kept_shared": 0, "hook_files": 0, "problems": []}
    if home is None or not home.is_dir():
        return rep
    ws = pathlib.Path(ws)
    dirs = _project_dirs_for(home, ws)
    if not dirs:
        return rep
    objs = home / "trace" / "objects"
    mine: set[str] = set()
    sessions: set[str] = set()
    for d in dirs:
        mine |= _hexes_in(d)
        try:
            st = json.loads((d / "state.json").read_text(encoding="utf-8"))
            # state.json 的鍵是 "pi:<session>"；intake/hooks 底下的檔名只帶 <session>
            sessions |= {str(k).split(":", 1)[-1] for k in (st.get("sessions") or {})}
        except (OSError, ValueError, AttributeError):
            pass
    mine_all = _blob_closure(objs, mine) if objs.is_dir() else set()
    # 別的專案還引用的 blob 不能刪（誠實邊界 2）
    proj_root = home / "trace" / "projects"
    others: set[str] = set()
    if proj_root.is_dir():
        for d in proj_root.iterdir():
            if d.is_dir() and d not in dirs:
                others |= _hexes_in(d)
    others_all = _blob_closure(objs, others) if (objs.is_dir() and others) else set()
    for d in dirs:
        try:
            shutil.rmtree(d)
            rep["projects"] += 1
        except OSError as exc:
            rep["problems"].append(f"project:{type(exc).__name__}")
    for s in sorted(mine_all):
        if s in others_all:
            rep["blobs_kept_shared"] += 1
            continue
        p = objs / s[:2] / s
        try:
            p.unlink()
            rep["blobs"] += 1
        except OSError as exc:
            rep["problems"].append(f"blob:{type(exc).__name__}")
    hooks = home / "intake" / "hooks"
    if hooks.is_dir() and sessions:
        for f in hooks.iterdir():
            if f.is_file() and any(s and s in f.name for s in sessions):
                try:
                    f.unlink()
                    rep["hook_files"] += 1
                except OSError as exc:
                    rep["problems"].append(f"hookfile:{type(exc).__name__}")
    return rep


def erase_all(home: pathlib.Path | None = None) -> dict[str, Any]:
    """閉展用：刪掉 `home` 底下所有追緝紀錄（trace/ 與 intake/hooks/），**留** install.json 與金鑰。
    撤回走的是 `erase()`（只刪那一跑）；這一支補「庫裡沒有、但 VACANT_HOME 裡有」的孤兒專案。"""
    home = home if home is not None else vacant_home()
    rep: dict[str, Any] = {"home_set": home is not None, "removed": [], "problems": []}
    if home is None or not home.is_dir():
        return rep
    for rel in ("trace", "intake/hooks"):
        t = home / rel
        if t.exists():
            try:
                shutil.rmtree(t)
                rep["removed"].append(rel)
            except OSError as exc:
                rep["problems"].append(f"{rel}:{type(exc).__name__}")
    return rep


def present(ws: pathlib.Path, home: pathlib.Path | None = None) -> bool:
    home = home if home is not None else vacant_home()
    if home is None or not home.is_dir():
        return False
    return bool(_project_dirs_for(home, pathlib.Path(ws)))


# ---------------------------------------------------------------------------
# pi 0.85.1 沒有 agent_before_settle：結束後補跑同一個零設定檢查（只寫交件說明）
# ---------------------------------------------------------------------------

def post_check(ws: pathlib.Path, session: str | None, final_text: str | None,
               *, python: str = "/usr/bin/python3", timeout_s: float = 120.0) -> dict[str, Any]:
    """把 pi 擴充在 `session_shutdown` 會送的那份 `session_end` 資料，用「說做完了」的形狀補送一次
    （`final_answer=true`、`aborted=true` ⇒ 0.9.1 的「事後補查」路徑，v3.2/3.3：只寫給人，不退回）。
    失敗一律回報、不丟例外。"""
    payload = {"cwd": str(ws), "session_id": session, "reason": "quit", "turn": 0, "budget": None,
               "aborted": True, "final_answer": True, "final_text": final_text or ""}
    try:
        r = subprocess.run([python, "-m", "vacant_network", "hook", "pi", "session_end"],
                           input=json.dumps(payload), capture_output=True, text=True,
                           timeout=timeout_s, cwd=str(ws))
        return {"rc": r.returncode, "out": r.stdout[-300:], "err": r.stderr[-300:]}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"rc": None, "error": type(exc).__name__}


def post_check_if_needed(ws: pathlib.Path, home: pathlib.Path | None = None, *, python: str = "/usr/bin/python3",
                         timeout_s: float = 100.0) -> dict[str, Any]:
    """pi 結束之後：這一跑有紀錄、卻沒有交件說明（＝擴充沒機會在 session 內查，例如 pi 0.85.1）⇒ 補跑一次。
    已經有 `delivery.json`（pi 0.87.1 的 `agent_before_settle` 查過了）⇒ 不動。沒開、沒紀錄 ⇒ 不動。"""
    home = home if home is not None else vacant_home()
    if home is None or not home.is_dir():
        return {"ran": False, "why": "no_vacant_home"}
    dirs = _project_dirs_for(home, pathlib.Path(ws))
    if not dirs:
        return {"ran": False, "why": "no_project"}
    d = dirs[0]
    if (d / "delivery.json").is_file():
        return {"ran": False, "why": "in_session_check_already_ran"}
    try:
        st = json.loads((d / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ran": False, "why": "no_state"}
    last = str(st.get("last_session") or "").split(":", 1)[-1] or None
    r = post_check(pathlib.Path(ws), last, None, python=python, timeout_s=timeout_s)
    return {"ran": True, "rc": r.get("rc"), "wrote_delivery": (d / "delivery.json").is_file()}


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="分身走 Vacant 0.9.x 掛鉤的接線")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("install", help="用產品自己的 `vacant install --agents pi` 裝（部署時一次）")
    p.add_argument("--python", default="/usr/bin/python3")
    p = sp.add_parser("postcheck", help="pi 結束後補跑零設定檢查（沒有 session 內檢查的 pi 版本）")
    p.add_argument("--ws", required=True)
    p.add_argument("--python", default="/usr/bin/python3")
    p = sp.add_parser("status")
    sp.add_parser("erase-all", help="閉展：刪光 VACANT_HOME 的 trace 與 hook 紀錄（留 install.json、金鑰）")
    p = sp.add_parser("erase")
    p.add_argument("--ws", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "install":
        r = install(python=a.python)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["rc"] == 0 and r["ext_exists"] else 1
    if a.cmd == "erase-all":
        print(json.dumps(erase_all(), ensure_ascii=False))
        return 0
    if a.cmd == "postcheck":
        print(json.dumps(post_check_if_needed(pathlib.Path(a.ws), python=a.python), ensure_ascii=False))
        return 0
    if a.cmd == "status":
        print(json.dumps({"enabled": enabled(), "home": str(vacant_home()),
                          "ext": str(ext_path()), "ext_exists": bool(ext_path() and ext_path().is_file()),
                          "encl_extras": encl_extras()}, ensure_ascii=False, indent=1))
        return 0
    print(json.dumps(erase(pathlib.Path(a.ws)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
