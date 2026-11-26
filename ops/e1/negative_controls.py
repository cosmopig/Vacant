#!/usr/bin/env python3
"""ops.e1.negative_controls — 沙箱隔離負控制：從 worker 沙箱內實測五類禁止路徑皆不可讀，且評分沙箱斷網。

這支在架構裡承重什麼
====================
在任何實驗 run 啟動前，以與真實 worker 完全相同的 `build_worker_bwrap_argv` 啟動探針，從沙箱內部嘗試讀取：
1. 鏈的隱藏測資（`hidden_tests.json` / `hidden_truth.json`）
2. 評分器輸出目錄（evaluator / run root）
3. 上一回合別臂的工作區（other arm workspace）
4. 教材目錄（materials dir）
5. `~/dev/ops`（含參考題庫與原始 pi 設定）

**只要任何一項讀得到，立即回傳非零退出碼**；`run_e1.py` 啟動前必須跑完且全數通過才准開跑。
另同時驗證：
- 評分沙箱（`--unshare-net`）確實無法連上宿主正在監聽的本機 TCP port。
- Worker 沙箱內的去敏 `models.json` 不含外部 API 金鑰（`sk-`）。

誠實邊界（改碼請保留）
----------------------
- 負控制驗的是「以本套件的 `bwrap` 參數啟動時，上述五類宿主路徑在沙箱內無法開啟或列舉」。
- 若呼叫端自行繞過 `sandbox.py` 另起行程，負控制無法察覺；且 worker 沙箱因須連本機模型而共用網路，
  故本腳本不宣稱「worker 斷網」（斷網只驗評分沙箱）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import socket
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1 import DEFAULT_PI_CFG_DIR
from ops.e1.sandbox import (
    build_eval_bwrap_argv,
    build_worker_bwrap_argv,
    prepare_sanitized_pi_cfg,
    run_sandboxed,
)

_WORKER_PROBE_PY = r"""
import json, os, pathlib, sys

targets = json.loads(sys.stdin.read())
results = []
for item in targets:
    name = item["name"]
    path = item["path"]
    readable = False
    detail = ""
    try:
        p = pathlib.Path(path)
        if p.is_dir():
            entries = os.listdir(path)
            readable = True
            detail = f"listed {len(entries)} entries"
        elif p.exists():
            data = p.read_bytes()[:64]
            readable = True
            detail = f"read {len(data)} bytes"
        else:
            detail = "not_found"
    except OSError as exc:
        detail = f"oserror:{type(exc).__name__}"
    results.append({"name": name, "path": path, "readable": readable, "detail": detail})

# 正向健全檢查：/work 可讀寫，HOME 是 /sandbox_home，且去敏設定無 sk- 金鑰
sanity = {}
try:
    w = pathlib.Path("/work/.nc_probe_write")
    w.write_text("ok", encoding="utf-8")
    sanity["work_rw"] = (w.read_text(encoding="utf-8") == "ok")
    w.unlink()
except OSError as exc:
    sanity["work_rw"] = False
    sanity["work_rw_err"] = str(exc)

sanity["home_isolated"] = (os.environ.get("HOME") == "/sandbox_home")
cfg_p = pathlib.Path(os.environ.get("PI_CODING_AGENT_DIR", "")) / "models.json"
if cfg_p.is_file():
    txt = cfg_p.read_text(encoding="utf-8", errors="replace")
    sanity["cfg_no_secret_key"] = ("sk-" not in txt)
    sanity["cfg_readonly"] = False
    try:
        (cfg_p.parent / ".try_write").write_text("x", encoding="utf-8")
    except OSError:
        sanity["cfg_readonly"] = True
else:
    sanity["cfg_no_secret_key"] = True
    sanity["cfg_readonly"] = True

print(json.dumps({"targets": results, "sanity": sanity}))
"""

_EVAL_NET_PROBE_PY = r"""
import json, socket, sys

port = int(sys.argv[1])
connected = False
err = None
try:
    s = socket.create_connection(("127.0.0.1", port), timeout=1.5)
    connected = True
    s.close()
except OSError as exc:
    err = f"{type(exc).__name__}:{exc.errno}"
print(json.dumps({"connected": connected, "error": err}))
"""


def _ensure_canary(directory: pathlib.Path, filename: str, token: str) -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / filename
    if not p.exists():
        p.write_text(token, encoding="utf-8")
    return p


def run_negative_controls(
    *,
    hidden_tests_path: pathlib.Path | None = None,
    eval_dir: pathlib.Path | None = None,
    other_arm_ws: pathlib.Path | None = None,
    materials_dir: pathlib.Path | None = None,
    dev_ops_dir: pathlib.Path | None = None,
    pi_cfg_dir: pathlib.Path | None = None,
    extra_worker_binds: list[tuple[pathlib.Path, str]] | None = None,
) -> dict:
    """在真實 bwrap 沙箱內執行全套隔離負控制。

    任何未由呼叫端指定的路徑，會在獨立暫存目錄建立真實金絲雀檔作為目標，確保五類檢查每次都真的跑過。
    `extra_worker_binds` 僅供單元測試做「正向破壞控制」（證明若誤掛路徑，本函式一定抓得出來）。
    """
    dev_ops = (dev_ops_dir or pathlib.Path("~/dev/ops").expanduser()).resolve()
    with tempfile.TemporaryDirectory(prefix="e1_nc_") as tmp:
        tmp_p = pathlib.Path(tmp)
        ws = tmp_p / "worker_ws"
        ws.mkdir()
        sanitized_cfg = tmp_p / "pi_cfg"
        src_cfg = pi_cfg_dir if pi_cfg_dir is not None else DEFAULT_PI_CFG_DIR
        if src_cfg.is_dir():
            prepare_sanitized_pi_cfg(src_cfg, sanitized_cfg)
        else:
            sanitized_cfg.mkdir()

        # 準備五類禁止讀取目標（實檔或金絲雀檔）
        targets: list[dict[str, str]] = []

        if hidden_tests_path is not None and hidden_tests_path.exists():
            ht = hidden_tests_path.resolve()
        else:
            ht = _ensure_canary(tmp_p / "chain_secret", "hidden_tests.json", '{"canary":"hidden"}')
        targets.append({"name": "hidden_tests", "path": str(ht)})

        if eval_dir is not None and eval_dir.exists():
            ev_target = eval_dir.resolve()
        else:
            ev_target = _ensure_canary(tmp_p / "eval_out", "eval_canary.json", '{"canary":"eval"}')
        targets.append({"name": "evaluator_out", "path": str(ev_target)})

        if other_arm_ws is not None and other_arm_ws.exists():
            oa_target = other_arm_ws.resolve()
        else:
            oa_target = _ensure_canary(tmp_p / "other_arm_prev_round", "solution.py", "# other arm canary\n")
        targets.append({"name": "other_arm_prev_ws", "path": str(oa_target)})

        if materials_dir is not None and materials_dir.exists():
            mat_target = (materials_dir / "manifest.json").resolve()
            if not mat_target.exists():
                mat_target = materials_dir.resolve()
        else:
            mat_target = _ensure_canary(tmp_p / "materials", "manifest.json", '{"canary":"materials"}')
        targets.append({"name": "materials_dir", "path": str(mat_target)})

        targets.append({"name": "dev_ops_dir", "path": str(dev_ops)})
        evalplus_p = dev_ops / "ref" / "evalplus"
        if evalplus_p.exists():
            targets.append({"name": "dev_ops_evalplus", "path": str(evalplus_p)})
        d2_models = dev_ops / "agentcfg" / "d2v52" / "models.json"
        if d2_models.exists():
            targets.append({"name": "dev_ops_models_json", "path": str(d2_models)})

        argv = build_worker_bwrap_argv(
            ["python3", "-c", _WORKER_PROBE_PY],
            workspace_dir=ws,
            pi_cfg_dir=sanitized_cfg,
            extra_ro_binds=extra_worker_binds,
        )
        res = run_sandboxed(argv, timeout_s=30, stdin_bytes=json.dumps(targets).encode("utf-8"))
        if res["rc"] != 0:
            return {
                "passed": False,
                "error": f"worker probe exited {res['rc']}: {res['stderr'][:300]}",
                "targets": [],
                "sanity": {},
                "eval_net_isolated": False,
            }
        try:
            payload = json.loads(res["stdout"])
        except ValueError as exc:
            return {
                "passed": False,
                "error": f"worker probe bad json: {exc}; stdout={res['stdout'][:200]}",
                "targets": [],
                "sanity": {},
                "eval_net_isolated": False,
            }

        # 評分沙箱 --unshare-net 驗證：宿主開一個臨時監聽 socket，評分沙箱內連線必須失敗
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            eval_argv = build_eval_bwrap_argv(
                ["python3", "-c", _EVAL_NET_PROBE_PY, str(port)],
                mem_limit_mb=512,
            )
            eres = run_sandboxed(eval_argv, timeout_s=20)
        finally:
            srv.close()

        eval_net_isolated = False
        eval_net_detail = ""
        if eres["rc"] == 0:
            try:
                ep = json.loads(eres["stdout"])
                eval_net_isolated = (ep.get("connected") is False)
                eval_net_detail = str(ep.get("error") or "")
            except ValueError:
                eval_net_detail = f"bad_json:{eres['stdout'][:120]}"
        else:
            eval_net_detail = f"rc={eres['rc']}:{eres['stderr'][:120]}"

        t_list = payload.get("targets") or []
        sanity = payload.get("sanity") or {}
        leaks = [t for t in t_list if t.get("readable")]
        sanity_ok = all(bool(sanity.get(k)) for k in ("work_rw", "home_isolated", "cfg_no_secret_key"))
        passed = (not leaks) and sanity_ok and eval_net_isolated
        return {
            "passed": passed,
            "leaks": leaks,
            "targets": t_list,
            "sanity": sanity,
            "eval_net_isolated": eval_net_isolated,
            "eval_net_detail": eval_net_detail,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="E1′ 隔離負控制：從 worker 沙箱內實測禁止路徑不可讀")
    ap.add_argument("--hidden-tests", type=pathlib.Path, help="鏈的隱藏測資檔路徑")
    ap.add_argument("--eval-dir", type=pathlib.Path, help="評分器輸出目錄")
    ap.add_argument("--other-arm-ws", type=pathlib.Path, help="別臂上一回合的工作區路徑")
    ap.add_argument("--materials-dir", type=pathlib.Path, help="文件教材目錄")
    ap.add_argument("--dev-ops", type=pathlib.Path, default=pathlib.Path("~/dev/ops").expanduser(), help="~/dev/ops 路徑")
    ap.add_argument("--pi-cfg", type=pathlib.Path, default=DEFAULT_PI_CFG_DIR, help="pi 設定來源目錄")
    ap.add_argument("--json", action="store_true", help="以 JSON 輸出完整報告")
    args = ap.parse_args()

    rep = run_negative_controls(
        hidden_tests_path=args.hidden_tests,
        eval_dir=args.eval_dir,
        other_arm_ws=args.other_arm_ws,
        materials_dir=args.materials_dir,
        dev_ops_dir=args.dev_ops,
        pi_cfg_dir=args.pi_cfg,
    )
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if rep["passed"] else "FAIL"
        print(f"[negative_controls] {status}")
        for t in rep.get("targets") or []:
            mark = "LEAK!" if t["readable"] else "blocked"
            print(f"  {mark:7s} {t['name']}: {t['path']} ({t['detail']})")
        print(f"  sanity: {rep.get('sanity')}")
        print(f"  eval_net_isolated: {rep.get('eval_net_isolated')} ({rep.get('eval_net_detail')})")
        if rep.get("error"):
            print(f"  error: {rep['error']}")
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
