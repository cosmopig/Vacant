#!/usr/bin/env python3
"""R530 發射器：一塊＝一組題 × 三條臂 × 一顆 seed，全 I/O JSONL 落盤。

規格：`DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md`
＋ Fable 2026-09-13 的建置裁決。

## 這支與 `ops/gain/gain_run.py` 的關係

**不共用執行路徑，共用紀律。** `gain_run` 的處理是「一題一函式」，
R530 的處理是「一個目錄」，兩者的臂、量具、收據形狀都不一樣。
共用的是這幾條，逐條對得上原出處：

  · `infra_void` 規則：作廢的格子 **一列都不寫**（`gain_run.py:1922-1932`）
    ⇒ `len(rows) == processed − infra_void`。完成判定讀 `summary.json`
    不數 `rows.jsonl` 行數（R529 §十一）。
  · retry／退避：由 `ClineBrain` 自己承接（`retries=4`、`backoff_s`），
    用盡才 `InfraVoid`（鐵律 3）。
  · `runner_git_info()`：這一塊跑在哪個 commit、工作區乾不乾淨（round680）。
  · `save_receipts()`：每臂的鏈與公鑰落盤；私鑰不落盤（RECORD_SPEC §7）。
  · 臂在塊內**交錯**（`for task: for arm:`，round278 起的紀律）⇒
    同一題的三條臂一定打同一顆後端、同一段時間；中斷在任何時刻都留下
    三臂格數相等的可分析資料。
  · `reasoning_effort` 預設 `none`，落盤在 `summary.request_policy`
    （DECISION_20260912 §十一：推論模式是**實驗條件**不是實作細節）。

## 發射閘門

  · `--decision`：那份 DECISION 必須存在，而且必須**逐字**含有
    `registration_line()` 這一行（整組比對，不是逐項——理由見
    `schedule_queue.registration_line` 的 docstring）。
  · `--bank-sha`：題庫逐檔 sha256 與釘死的表比對，對不上 `abort_bank_sha_mismatch`。
    **沒給就記 `bank_sha_pinned: false`**，不准讓「沒有釘」看起來像「釘了而且過了」。
  · `--out` 已存在 ⇒ `abort_dir_exists`（同一塊不准跑兩次疊在一起）。
  · `--smoke`：seed 必須以 `smoke-` 開頭、`--out` 必須在 `runs/_smoke/` 底下，
    DECISION 閘門跳過，run 目錄寫一個 `NOT_EVIDENCE` 檔。**冒煙永不進證據。**

用法：
    python3 ops/gain/r530/run_r530.py \\
      --out runs/g_r530_ow_s1_odd --decision DECISION_20260913_R530_….md \\
      --task-set ow_01_csvjson,ow_02_ratelimit --arms A-SOLO,A-CONF,A-GATE \\
      --seed g-r530-s1 --backend bwrap
乾跑（零呼叫、零磁碟）：加 `--plan`。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.brain_cline import (DEFAULT_BACKOFF_S, ClineBrain,  # noqa: E402
                                  InfraVoid, endpoint, load_keys)
from ops.gain.gain_run import runner_git_info, save_receipts  # noqa: E402
from ops.gain.r530 import openwork_arms as oa  # noqa: E402
from ops.gain.r530 import gates, tasks as taskmod  # noqa: E402
from ops.gain.r530.sandbox import make_sandbox  # noqa: E402
from vacant.identity import Identity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_MODEL = "gemma-4-12b-it-qat"
#: 冒煙 seed 的機械標記。**前綴或後綴都算**——預註冊 §三-6 指名的冒煙 seed
#: 是 `g-r530-smoke`（後綴），而本支原本只認前綴 `smoke-`。認一種會讓
#: 預註冊寫死的那顆 seed 發不出去，而那是量具在跟規格吵架，不是規格錯。
SMOKE_SEED_PREFIX = "smoke-"
SMOKE_SEED_SUFFIX = "-smoke"

#: 工作區根的預設值。**刻意不在 `$HOME` 底下**——見 `main()` 裡那段註解。
#: 換機器就換這一行（或用 `--work-root`／`VACANT_R530_WORK`）。
DEFAULT_WORK_ROOT = pathlib.Path("/var/tmp/vacant_r530_work")
SMOKE_OUT_PREFIX = "runs/_smoke/"
#: 冒煙專用預算。**只在 `--smoke --smoke-budget` 下生效。**
#: 為什麼需要它：凍結的 `max_tokens=120_000` 在多輪工具迴圈下 5–8 通就撞滿
#: （每一通都把整段對話當 prompt 重送 ⇒ 累積量隨輪數二次成長），
#: 於是冒煙永遠跑不到閘門輪與拒交那幾條路徑——而那正是冒煙要驗的東西。
#: ⚠ 這**不是**「發現預算不夠就調大」：凍結的那一份一個字都沒動，
#:   `--smoke` 以外拿不到這一份，而且 `summary.budget_profile` 會寫 `smoke`。
#:   正式 run 的預算不夠是一個**要回去重寫 DECISION 的發現**（§三-4 PR-4），
#:   不是一個可以就地轉的旋鈕。
#: ⚠ **只放寬 token 與牆鐘，`max_model_calls` 一個字都不動。**
#:   2026-09-14 試過把它調小到 8 想讓冒煙跑快一點，結果是**冒煙變成測不到東西**：
#:   真後端實測模型要到第 14 通才「宣告完成」（`runs/_smoke` smoke4 的
#:   A-SOLO/ow_01），8 通之下它永遠停在 `budget_calls`，於是
#:   §三-6 的 C2（宣告完成的輪次）與 C3（可見驗收結果）**兩格永遠是空的**——
#:   而那兩格正是冒煙要驗的。調快的代價是量不到，所以不調。
#:   冒煙因此就是慢的（六格約 1.5 小時），那是這個任務形狀的成本不是缺陷。
#: ⚠ 正式 run 一個字都不動凍結的那一份（`budget_profile: "frozen"`）。
SMOKE_BUDGET = {"max_tokens": 2_000_000, "max_wall_s": 1_800}

NOT_EVIDENCE_TEXT = (
    "這個目錄是冒煙，**不是證據**。\n"
    "seed 以 smoke- 開頭、後端可能是 stub、沙箱可能沒有隔離。\n"
    "任何分析、任何收官、任何對外數字都不准引用這裡的東西。\n")


def registration_line(*, out: str, task_set: str, arms: str, seed: str,
                      endpoint_url: str) -> str:
    """這一塊在 DECISION 裡必須逐字出現的那一行。**整組**比對。"""
    return (f"R530_BLOCK: {pathlib.Path(out).name} tasks={task_set} "
            f"arms={arms} seed={seed} endpoint={endpoint_url}")


def _check_decision(decision: str, line: str) -> None:
    p = pathlib.Path(decision)
    if not p.is_file():
        raise SystemExit(f"abort_decision_missing：{p} 不存在。停。")
    if line not in p.read_text(encoding="utf-8"):
        raise SystemExit(
            "abort_not_registered：DECISION 裡找不到這一行（逐字）：\n"
            f"  {line}\n"
            "——沒有註冊的塊不准發射（整組比對，不是逐項）。停。")


def _make_brain(args, calls_path: pathlib.Path):
    """建後端。**協定是實驗條件**，逐格落盤（兩種模式的資料不得混算）。"""
    if args.brain == "stub":
        from ops.gain.r530.stubbrain import StubBrain
        return StubBrain(log_path=calls_path)
    keys = load_keys(args.keys) if args.keys else load_keys()
    key = keys[0] if keys else ""
    if args.tool_protocol == "native":
        from ops.gain.r530.brain_native import NativeToolBrain
        return NativeToolBrain(
            "r530-worker", key=key, log_path=calls_path, model=args.model,
            temperature=args.temperature, retries=args.retries,
            backoff_s=args.retry_backoff_s, timeout_s=args.request_timeout_s,
            reasoning_effort=args.reasoning_effort)
    from ops.gain.r530.brain_native import TextProtocolBrain
    return TextProtocolBrain(ClineBrain(
        "r530-worker", system="", key=key, log_path=calls_path,
        model=args.model, temperature=args.temperature,
        retries=args.retries, backoff_s=args.retry_backoff_s,
        timeout_s=args.request_timeout_s,
        reasoning_effort=args.reasoning_effort))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R530 發射器")
    ap.add_argument("--out", required=True, help="run 目錄（相對 repo 根）")
    ap.add_argument("--decision", default=None,
                    help="這一塊註冊在哪份 DECISION（--smoke 以外必填）")
    ap.add_argument("--task-set", default="all",
                    help="all ／ 逗號分隔的 task_id ／ @<path>.json")
    ap.add_argument("--arms", default=",".join(oa.ARMS))
    ap.add_argument("--seed", required=True)
    ap.add_argument("--backend", default="auto",
                    help="沙箱後端：auto／bwrap／unshare／none")
    ap.add_argument("--sudo-bwrap", action="store_true",
                    help="bwrap 走 sudo -n（Ubuntu 24.04 AppArmor 擋非特權 userns 時唯一可行）")
    ap.add_argument("--sandbox-uid", type=int, default=None,
                    help="unshare 後端降權到哪個 uid。**E-9 需要它**："
                         "降到一個讀不到 $HOME 的 uid（Linux 上 65534＝nobody）"
                         "才會讓 repo_hidden_from_sandbox 為 true。"
                         "不給＝降權回呼叫者自己＝檔案端一格隔離都沒有 ⇒ E-9 紅。")
    ap.add_argument("--sandbox-gid", type=int, default=None)
    ap.add_argument("--work-root", default=None,
                    help="工作區根目錄（預設 ~/vacant/r530_work）")
    ap.add_argument("--brain", default="cline", choices=["cline", "stub"])
    ap.add_argument("--tool-protocol", default="native",
                    choices=["native", "text"],
                    help="native＝OpenAI 原生 tools（2026-09-13 冒煙實測可行，預設）；"
                         "text＝```bash 圍欄（同一次冒煙實測在 gemma-4-12b-it-qat 上不通）。"
                         "兩種模式的資料**不得混算**，逐格落盤。")
    ap.add_argument("--smoke-budget", action="store_true",
                    help="**只准配 --smoke**：把預算換成冒煙專用的一份，好讓閘門輪／"
                         "拒交這些路徑在冒煙裡跑得到。正式 run 一律用凍結的 "
                         "OPENWORK_BUDGET，改它要重寫 DECISION（§三-4 PR-4）。")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--keys", default=None)
    ap.add_argument("--temperature", type=float, default=0.3,
                    help="三臂同值，事前釘死（沿用 ops/localagent.py 的 0.3）")
    ap.add_argument("--retries", type=int, default=4,
                    help="端點重試次數，用盡才記 infra_void（鐵律 3 的 ×4）")
    ap.add_argument("--retry-backoff-s", type=float, default=DEFAULT_BACKOFF_S)
    ap.add_argument("--request-timeout-s", type=int, default=900)
    ap.add_argument("--reasoning-effort", default="none",
                    choices=["none", "default", "low", "medium", "high"])
    ap.add_argument("--gauge-scope", default="none",
                    choices=["bank", "none"],
                    help="bank＝發射前跑一次 `gauge_r530.py --check`（雙向量具："
                         "參考解全過、每個已知壞樁都被擋、anchor 逐字指得回 "
                         "goal/contract），不過就不發射（E-3）。"
                         "none＝不跑（只准冒煙用；正式發射一律 bank）。")
    ap.add_argument("--bank-sha", default=None,
                    help="釘死的題庫 sha256 表（AMEND1）；不給就記 bank_sha_pinned=false")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--plan", action="store_true",
                    help="只印計畫，不發射、不碰後端、不寫 runs/")
    args = ap.parse_args(argv)

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    bad = [a for a in arms if a not in oa.ARMS]
    if bad:
        raise SystemExit(f"unknown arms {bad}（可用 {list(oa.ARMS)}）。停。")
    if args.smoke_budget and not args.smoke:
        raise SystemExit("--smoke-budget 只准配 --smoke。停。")
    ep = endpoint()
    line = registration_line(out=args.out, task_set=args.task_set,
                             arms=args.arms, seed=args.seed, endpoint_url=ep)

    if args.smoke:
        if not (args.seed.startswith(SMOKE_SEED_PREFIX)
                or args.seed.endswith(SMOKE_SEED_SUFFIX)):
            raise SystemExit(
                f"--smoke 的 seed 必須以 {SMOKE_SEED_PREFIX!r} 開頭或以 "
                f"{SMOKE_SEED_SUFFIX!r} 結尾（拿到 {args.seed!r}）——"
                "冒煙的 seed 與正式 run 不同是「冒煙永不進證據」的機械保證。停。")
        if not args.out.startswith(SMOKE_OUT_PREFIX):
            raise SystemExit(
                f"--smoke 的 --out 必須在 {SMOKE_OUT_PREFIX} 底下"
                f"（拿到 {args.out!r}）。停。")
    else:
        if not args.decision:
            raise SystemExit("--decision 是必填的（除非 --smoke）。停。")
        _check_decision(args.decision, line)
        if args.brain == "stub":
            raise SystemExit(
                "--brain stub 只准配 --smoke：替身後端的輸出不是資料。停。")
        if (args.seed.startswith(SMOKE_SEED_PREFIX)
                or args.seed.endswith(SMOKE_SEED_SUFFIX)):
            raise SystemExit(
                "正式 run 的 seed 不准帶冒煙標記（前綴 smoke- 或後綴 -smoke）。停。")

    if args.smoke_budget:
        # 冒煙專用預算：**不是**對凍結常數的修改，是一份只在 `--smoke` 下
        # 生效的替代品，而且它自己也落盤（`summary.budget_profile`）。
        oa.OPENWORK_BUDGET.update(SMOKE_BUDGET)

    # ── E-3（發射閘門）：雙向量具全綠才准發射。────────────────────────
    # ⚠ 它跑的是**整個 bank 的 20 題**不是這一塊的 5 題：題庫是一份共用的正典，
    #   而「這一塊用到的那幾題沒問題」不等於「我們發射時用的題庫沒被動過」。
    #   量不到不是通過（`vacant/suitegauge.py` 的單邊保證）。
    if args.gauge_scope == "bank":
        _g = subprocess.run(
            [sys.executable, str(REPO / "ops/gain/r530/gauge_r530.py"), "--check"],
            cwd=str(REPO), capture_output=True, text=True, timeout=1800)
        if _g.returncode != 0:
            raise SystemExit(
                "abort_gauge_red：`gauge_r530.py --check` 沒過 ⇒ E-3 紅，不准發射。\n"
                + (_g.stdout or "")[-2000:] + (_g.stderr or "")[-800:])

    ts = taskmod.load_tasks(args.task_set)
    bank = taskmod.bank_manifest(ts)
    if args.bank_sha:
        taskmod.assert_bank_matches(ts, args.bank_sha)

    out_dir = (REPO / args.out) if not os.path.isabs(args.out) else pathlib.Path(args.out)
    if args.plan:
        print(f"registration line（要逐字出現在 DECISION 裡）：\n  {line}\n")
        print(f"out          {out_dir}")
        print(f"tasks ({len(ts)})   " + ", ".join(t["task_id"] for t in ts))
        print(f"arms         {arms}")
        print(f"cells        {len(ts) * len(arms)}")
        print(f"endpoint     {ep}")
        print(f"bank root    {bank['_root_sha256']}")
        print(f"budget       {json.dumps(oa.OPENWORK_BUDGET, ensure_ascii=False)}")
        return 0
    if out_dir.exists():
        raise SystemExit(f"abort_dir_exists：{out_dir} 已存在。停。")
    out_dir.mkdir(parents=True)
    if args.smoke:
        (out_dir / "NOT_EVIDENCE").write_text(NOT_EVIDENCE_TEXT, encoding="utf-8")

    # ⚠ **工作區根刻意放在 `$HOME` 之外**（E-9 的前提，Fable 2026-09-14）。
    #   `/home/<user>` 是 `drwxr-x---` ⇒ 降權到 `nobody` 的沙箱連穿越都不行，
    #   工作區放在裡面等於「沙箱寫不進自己的工作區」。放到 `/var/tmp` 之後：
    #   工作區根 0755（我們擁有）⇒ 沙箱**寫不出界**；
    #   單格 0777（`world_writable`）⇒ 沙箱寫得進自己那一格；
    #   而 repo 仍在 `$HOME` 底下 ⇒ 沙箱**看不到** `ops/gain/r530/hidden/`。
    #   三件事合起來就是 E-9 要的結構隔離，而且不需要任何主機政策改動。
    work_root = pathlib.Path(
        args.work_root
        or os.environ.get("VACANT_R530_WORK")
        or DEFAULT_WORK_ROOT)
    work_root.mkdir(parents=True, exist_ok=True)
    os.chmod(work_root, 0o755)
    calls_path = out_dir / "calls.jsonl"
    rows_path = out_dir / "rows.jsonl"
    notes_path = out_dir / "notes.jsonl"
    ws_dir = out_dir / "ws"
    ws_dir.mkdir(exist_ok=True)
    # 驗收的暫存目錄必須是**沙箱 uid 讀得到**的，所以它跟著工作區根走，
    # 不放在 run 目錄裡（run 目錄在 `$HOME` 底下，降權之後讀不到）。
    # 它只在跑一次驗收的那幾秒存在，跑完就刪（`acceptance.run_suite`）。
    verify_root = work_root / "_verify"

    def note(rec: dict) -> None:
        rec["ts_ms"] = int(time.time() * 1000)
        with notes_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    probe_dir = work_root / "_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(probe_dir, 0o777)          # 降權後的沙箱要寫得進探針目錄
    sandbox, backend_meta = make_sandbox(
        args.backend, workdir=str(probe_dir),
        use_sudo_bwrap=args.sudo_bwrap,
        sandbox_uid=args.sandbox_uid, sandbox_gid=args.sandbox_gid)
    (out_dir / "backend_meta.json").write_text(
        json.dumps(backend_meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    # ── E-9（Fable 2026-09-14）：沙箱不夠格就**不准發射**。────────────────
    # 在任何一通模型呼叫之前判。`--smoke` 也一樣——冒煙要驗的正是這個配置，
    # 放它一馬等於讓冒煙證明了一個不會被用的東西。
    e9 = gates.e9_sandbox_gate(backend_meta)
    # ⚠ 唯一不強制的情況：`--brain stub`。那條路徑**沒有模型**——跑進沙箱的
    #   「候選解」是我們自己的 `gauge/*.py`，沒有任何東西可以洩漏給誰。
    #   E-9 擋的是「模型構得到隱藏驗收」，威脅模型在這裡不存在。
    #   ⇒ 照樣量、照樣落盤，但標明 `enforced: false`，不准看起來像過了。
    e9["enforced"] = (args.brain != "stub")
    if not e9["enforced"]:
        e9["not_enforced_reason"] = (
            "--brain stub：沒有模型，跑進沙箱的是我們自己的參考解／壞樁，"
            "沒有可以洩漏的對象。這一格的值是量到的，但它不是一次通過。")
    (out_dir / "gate_e9.json").write_text(
        json.dumps(e9, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if e9["enforced"] and not e9["ok"]:
        raise SystemExit(
            e9["reason"] + f"\n（實測 {json.dumps(e9, ensure_ascii=False)}）"
            "\n沙箱的裝法與回滾見 ops/gain/r530/SANDBOX.md。停。")
    if e9.get("warning"):
        note({"gate": "E-9", "warning": e9["warning"]})
    world_writable = (backend_meta.get("sandbox_uid") is not None
                      and backend_meta.get("sandbox_uid") != os.getuid())

    # ── E-11（Fable 2026-09-14 第六輪）：推論模式必須是登記的那一種。──────
    # **在原生 tools 請求下**量——`reasoning_effort=none` 在不帶 tools 的請求上
    # 生效，不代表它在帶 tools 的請求上生效，而 R530 只走後者。
    # R529 §十一：同一份 gguf 可以在兩台上跑成兩種實驗條件，
    # 而那件事沒有錯誤訊息、只有一批不能併的資料。
    # ⚠ 它燒兩通呼叫（約 20–30 秒），落在 `inference_probe.json`，
    #   **不進任何分析**（`role` 不是實驗臂，V/GT 與 rows 都不會看到它）。
    e11 = {"gate": "E-11", "phase": "preflight", "skipped_reason": None}
    if args.brain == "stub":
        e11["skipped_reason"] = "--brain stub：沒有真的端點可以探"
        e11["ok"] = True
    else:
        from ops.gain.r530.brain_native import probe_inference_mode
        keys = load_keys(args.keys) if args.keys else load_keys()
        probe = probe_inference_mode(ep, args.model,
                                     key=(keys[0] if keys else ""),
                                     reasoning_effort=args.reasoning_effort)
        e11 = gates.e11_preflight_gate({ep: probe})
        # ⚠ `enforced` 要**明說**。真跑時這條閘門確實會擋（下面就 SystemExit），
        #   但先前只有 stub 那條路徑填這個欄位 ⇒ 真跑的 `gate_e11.json` 寫
        #   `enforced: null`，而 `gate_e9.json` 寫 `enforced: true`。
        #   兩個同名欄位不對稱會讓讀的人以為 E-11 沒被強制。
        e11["enforced"] = True
        (out_dir / "inference_probe.json").write_text(
            json.dumps(probe, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        # 結論寫進 backend_meta（Fable 指名）——沙箱與推論條件是同一份「這一塊
        # 是在什麼條件下量的」，分開放會讓引用的人只看到一半。
        backend_meta["inference"] = {
            "reasoning_effort_sent": probe.get("reasoning_effort_sent"),
            "reasoning_tokens": probe.get("reasoning_tokens"),
            "reasoning_tokens_all_zero": probe.get("reasoning_tokens_all_zero"),
            "prefill_ms_per_1k_prompt": probe.get("prefill_ms_per_1k_prompt"),
            "note": probe.get("note"),
        }
        (out_dir / "backend_meta.json").write_text(
            json.dumps(backend_meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    (out_dir / "gate_e11.json").write_text(
        json.dumps(e11, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not e11.get("ok"):
        raise SystemExit(
            e11.get("reason", "E-11 紅") +
            f"\n（實測 {json.dumps(e11, ensure_ascii=False)}）\n停。")

    brain = _make_brain(args, calls_path)
    books = {a: {"book": Logbook(), "ident": Identity.generate()} for a in arms}
    stats = {a: {"processed": 0, "infra_void": 0, "accepted": 0,
                 "deliv": 0, "calls": 0, "tokens": 0, "wall_s": 0.0}
             for a in arms}

    t_start = time.time()
    print(f"── R530 {out_dir.name}　題 {len(ts)} × 臂 {len(arms)} "
          f"＝ {len(ts) * len(arms)} 格　sandbox={backend_meta['backend']}",
          flush=True)
    # 臂在塊內交錯（round278）：同一題三臂連著跑。
    for task in ts:
        for arm in arms:
            cell = work_root / f"{task['task_id']}__{arm}__{args.seed}"
            paths = oa.CellPaths(
                template_dir=task["template_dir"],
                visible_dir=task["visible_dir"],
                hidden_dir=task["hidden_dir"],
                cell_dir=cell,
                verify_root=verify_root,
                ws_archive_dir=ws_dir,
                world_writable=world_writable,
            )
            s = stats[arm]
            s["processed"] += 1
            t0 = time.time()
            # E-9 的附帶條件：沒有檔案隔離時，「這一格有沒有寫到工作區外面」
            # 是一個**只能事後觀察**的事實，而事實沒有被觀察就等於沒發生過。
            outside_before = (gates.snapshot_outside(work_root)
                              if not backend_meta.get("write_confined") else set())
            try:
                row = oa.run_cell(
                    task, brain, arm=arm, seed=args.seed, paths=paths,
                    sandbox=sandbox, calls_path=calls_path,
                    book=books[arm]["book"], ident=books[arm]["ident"])
            except InfraVoid as e:
                # 作廢的格子**一列都不寫**（gain_run 的同一條）。
                s["infra_void"] += 1
                s["wall_s"] += time.time() - t0
                note({"arm": arm, "task_id": task["task_id"],
                      "infra_void": str(e)})
                print(f"   [{arm:7} {task['task_id']:20}] infra_void: {e}",
                      flush=True)
                continue
            if outside_before:
                new_outside = sorted(gates.snapshot_outside(work_root)
                                     - outside_before)
                row["outside_new_files"] = new_outside
                if new_outside:
                    note({"arm": arm, "task_id": task["task_id"],
                          "outside_new_files": new_outside})
            row["endpoint"] = ep
            row["model"] = args.model
            row["backend"] = backend_meta["backend"]
            with rows_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            s["accepted"] += int(row["accepted"])
            s["deliv"] += int(row["deliv"])
            s["calls"] += row["calls"]
            s["tokens"] += row["tokens"]
            s["wall_s"] += row["wall_s"]
            print(f"   [{arm:7} {task['task_id']:20}] "
                  f"accepted={row['accepted']} "
                  f"hidden={row['hidden_passed']}/{row['hidden_total']} "
                  f"calls={row['calls']} stop={row['stop_reason']}", flush=True)

    written = save_receipts(out_dir, books)
    all_rows = ([json.loads(l) for l in rows_path.open(encoding="utf-8") if l.strip()]
                if rows_path.exists() else [])
    # E-10（Fable 2026-09-14）：逐臂的 noop 比例。這支只**算**，不自己判 INVALID
    # ——那是 analyzer 的事；但數字要在 run 的產物裡，不是事後靠人數。
    e10 = gates.e10_noop_gate(all_rows)
    (out_dir / "gate_e10.json").write_text(
        json.dumps(e10, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # E-11 收官：這一塊**實際**燒掉的 reasoning 占比。> 0 ⇒ 該塊 broken。
    all_calls = ([json.loads(l) for l in calls_path.open(encoding="utf-8")
                  if l.strip()] if calls_path.exists() else [])
    e11_close = gates.e11_closeout_gate(all_calls, block=out_dir.name)
    (out_dir / "gate_e11_closeout.json").write_text(
        json.dumps(e11_close, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    if not e11_close["ok"]:
        note({"gate": "E-11", "phase": "closeout",
              "verdict": e11_close["verdict"],
              "reason": e11_close.get("reason")})
    summary = {
        "run": out_dir.name,
        "study": "R530",
        "seed": args.seed,
        "arms": arms,
        "task_set": args.task_set,
        "tasks": [t["task_id"] for t in ts],
        "n_tasks": len(ts),
        "smoke": bool(args.smoke),
        "brain": args.brain,
        "endpoint": ep,
        "model": args.model,
        "registration_line": line,
        "decision": args.decision,
        "gauge_scope": args.gauge_scope,
        "tool_protocol": (args.tool_protocol if args.brain != "stub"
                          else "text"),
        "budget": dict(oa.OPENWORK_BUDGET),
        "budget_profile": "smoke" if args.smoke_budget else "frozen",
        "request_policy": {
            "temperature": args.temperature,
            "retries": args.retries,
            "backoff_s": args.retry_backoff_s,
            "request_timeout_s": args.request_timeout_s,
            "reasoning_effort": args.reasoning_effort,
            "reasoning_effort_applies_to": "chat() (all three arms)",
            "max_tokens_sent": None,
        },
        "backend_meta": backend_meta,
        "gates": {"E9": e9, "E10": e10,
                  "E11_preflight": e11, "E11_closeout": e11_close},
        # 這一塊算不算數的單一真相：E-11 收官紅 ⇒ `broken`，資料不進分析。
        "block_verdict": ("broken" if not e11_close["ok"] else "ok"),
        "work_root": str(work_root),
        "bank": {"root_sha256": bank["_root_sha256"],
                 "pinned": bool(args.bank_sha),
                 "pinned_path": args.bank_sha},
        "runner_git_info": runner_git_info(),
        "receipts_written": written,
        "arms_stats": stats,
        "wall_s": round(time.time() - t_start, 1),
        "run_terminal": True,
        "honest_bounds": [
            "A-SOLO 的 accepted 恆為 True（它沒有拒交語意）——每一次引用 deliv "
            "都要跟著講這句（§六-0、§八-4）。",
            "A-GATE vs A-SOLO 不是等預算比較，而且故意不是；等預算那一刀由 "
            "A-GATE vs A-CONF 負責（§八-4）。",
            "max_wall_s 在呼叫之間檢查，不是每題牆鐘的硬上界（§二-3）。",
            backend_meta.get("honest_bound", ""),
            "token 上限只算 completion（Fable 2026-09-14）；prompt 逐格另外落盤，"
            "因為多輪迴圈的 prompt 隨輪數二次成長，兩個數字混在一起看不出"
            "「是生成太多還是脈絡太長」。",
            e10.get("honest_bound", ""),
        ],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    if verify_root.exists():
        # 暫存驗收目錄跑完就該是空的；留著空殼是為了讓「有沒有殘留」看得見。
        leftovers = sorted(p.name for p in verify_root.iterdir())
        if leftovers:
            note({"verify_root_leftovers": leftovers})
    print(f"── 收工　{summary['wall_s']}s　"
          + "　".join(f"{a}: {stats[a]['deliv']}/{stats[a]['processed']} deliv"
                      for a in arms), flush=True)
    print(f"── {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
