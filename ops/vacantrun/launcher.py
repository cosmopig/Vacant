#!/usr/bin/env python3
"""這支在架構裡承重什麼：`vacant run -- <任何 agent 命令>` 的本體（V0 ＋ V1 迴圈）。

## 為什麼是「行程結束」而不是「宣告完成」

要在 wire 上認出「agent 宣告完成了」很難：沒有標準欄位、每個框架的收尾訊息
長得都不一樣、而且那個判斷只有在要把回饋**注入回對話**的時候才真的需要。
如果目的只是**攔下交付**，那就不必認——agent 行程 `wait()` 回來的那一刻
就是交付點。那個訊號 100% 可靠、零協定知識、零 token 成本，
連走文字協定的框架都涵蓋。

所以 V0 做的是五件事，一件都不多：

  1. 起 proxy（ephemeral port），照 `envmap` 的**一份名單**設 base-url 變數，
     並把真上游與真鑰從 agent 的 env 裡拿掉，只留在 proxy 行程；
  2. `wshash.tree_hash(workspace)` 記起點；
  3. spawn agent，等它結束；
  4. 在**凍結的快照**上跑 `acceptance.run_suite(suite="visible")`，簽
     `ws_verdict`，寫收據；
  5. 退出碼反映裁決；沒過 ⇒ 標記拒交。

## V1 ＝ 在 3–4 外面加一圈迴圈（`--retry resample|revise`）

V0 只是**收件口**，不是 Vacant 的機制。R530／R532 量到增益的那個東西是
**閘門＋重抽／重改**。而因為觸發點是行程結束、不在 wire 上，重試**不必碰協定**：
重置或寫一個檔，**再 spawn 一次 agent 就好**——零協定破解、零偽造發言。
兩條臂的政策、回饋模板與重置語意在 `ops/vacantrun/retry.py`（含誠實邊界）；
這一支只負責把它接成迴圈、逐次落盤、逐次簽 `ws_attempt`。

⚠ **R530 踩過的坑，這裡是可執行的防線**：只在 happy path 簽 attempt ⇒
撞預算的格子 0 筆 attempt、1 筆 verdict ⇒ 鏈沒壞，壞的是「鏈說得出這一格
發生過什麼」。所以 `ws_attempt` 在**每一次嘗試結束時**就簽，不是最後補簽；
對帳規則 `attempt 數 ≥ verdict 數` 由 `ops/gain/replay/verify_run_receipts.py`
守著，`tests/test_vacant_run_retry.py` 對每一種收尾都驗一次。

## 開關＝ `VACANT=0|1`

  · `VACANT=0` ——proxy 走純 tee（bytes 原樣轉送、不 parse 不重序列化），
    body 逐位元相同，但**仍然逐字落盤**（鐵律 3 對兩臂都成立）。
    不跑驗收、不簽收據、不拒交，退出碼＝agent 自己的退出碼。
  · `VACANT=1` ——加驗收＋收據＋拒交。

**兩臂在 wire 上必須逐位元相同**，這是整個設計的可比性基礎；可執行證明在
`tests/test_vacant_run.py::test_body_bytes_identical_off_vs_on`。

## 收據用的是既有的那把尺

`ops/gain/r530/receipts.py` 的 `ws_attempt`／`ws_verdict` 一個字都沒改，
所以 `ops/gain/replay/verify_run_receipts.py` 直接驗得過（**不准另寫第二把尺**）。
run 目錄的形狀也照抄：`rows.jsonl` ＋ `receipts_<ARM>.ndjson` ＋ `.pub.json`。

## 誠實邊界（改碼請保留；完整版在 `docs/VACANT_RUN.md`）

1. **proxy 單獨只有 L3。**「agent 一旦被接上就逃不掉」**只有加上出網封鎖
   （`ops/vacantrun/block_egress.sh`，要 root）才是真的**。
   `vacant/controller.py:7-8` 原本就寫著：無法阻止同一 OS 使用者繞過本命令
   直接執行 agent。
2. **中介的是「模型通道」不是「agent 的行為」**：框架自己發起的動作
   （自動 lint、git checkpoint、內建重試）不經過模型通道，看不到也擋不到。
3. **環境變數名單擋不到用設定檔的框架**（pi 的 `models.json`）。
   證據是 proxy 的 `requests_seen`，不是「我設了變數」。
4. **TOCTOU**：驗收跑在凍結快照上，`ws_end_sha256` 綁進收據。凍結前後
   工作區雜湊不一致 ⇒ 判 `infra_void`，**不判拒交也不判通過**。
5. **驗收是單邊保證**（`vacant/suitegauge.py`）：擋得住已知壞解
   ≠ 涵蓋真需求。`accepted=True` 只代表「客戶給的那幾條過了」。
6. **沒有驗收套件 ⇒ fail-closed**：`VACANT=1` 而沒給 `--suite` 一律拒交
   （`no_suite`）。量不到不是通過。要放行得明講 `--allow-no-suite`，
   那一格的 `accepted` 會落成 `null` 而不是 `true`——**「沒量」與「量到過」
   不可以在資料上同形**。
7. **重試不是免費的**：每一次嘗試都燒一整個 agent 行程的 token 與時間。
   `--max-attempts` 是**成本上限**，不是目標值；等預算的定義是
   「上限相同、實際用量落盤」，不是強制用滿（R530 的裁決）。
8. **`revise` 會讓 agent 看到自己的失敗，那是設計**；但它看不到隱藏測資
   （回饋只吃 `suite="visible"` 的結果），這條由 V/GT canary 測試守。
9. **R534 實測：真模型上「沒過→重改」與拒交出現 0 次**（6 格次裡 2 次宣告完成
   都第一輪過、2 次燒光 token、2 次撞脈絡上限）⇒ **V1 讓這條路存在，
   不代表它在你的工作負載上會被觸發。**
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.gain.r530 import acceptance, receipts, wshash          # noqa: E402
from ops.gain.r530.sandbox import make_sandbox                  # noqa: E402
from ops.vacantrun import envmap, retry as retrypolicy          # noqa: E402
from ops.vacantrun.wireproxy import WireProxy                   # noqa: E402
from vacant.crypto import pub_to_hex                            # noqa: E402
from vacant.identity import Identity                            # noqa: E402
from vacant.logbook import Logbook                              # noqa: E402
from vacant.memory import KS1Violation                          # noqa: E402

#: 兩臂的 arm 名。`verify_run_receipts.py` 用 `receipts_<ARM>.ndjson` 認臂，
#: 所以名字裡不能有 `.`。
ARM_ON, ARM_OFF = "RUN-ON", "RUN-OFF"

#: 封閉的裁決集合。多一個就是規格變更——不准在別處臨時造字串。
STOP_REASONS = frozenset({
    "visible_pass",        # 驗收全過 ⇒ 交付
    "visible_fail",        # **單發**驗收沒過 ⇒ 拒交（`max_attempts == 1`）
    "attempts_exhausted",  # 迴圈用完額度仍沒過 ⇒ 拒交（`max_attempts > 1`）
    "no_suite",            # 沒有驗收套件而沒明講放行 ⇒ 拒交（fail-closed）
    "ungated",             # `--allow-no-suite`：沒量，accepted=null
    "ws_moved_during_freeze",   # TOCTOU：凍結期間工作區被動過 ⇒ infra_void
    "ws_reset_failed",     # `resample` 重置之後對不回起點 ⇒ infra_void
    "agent_spawn_failed",  # agent 起不來 ⇒ infra_void
    "ks1_violation",       # 回饋文字帶責任修辭 ⇒ 鐵律 1「run 作廢」⇒ infra_void
})
#: `visible_fail` 與 `attempts_exhausted` **刻意不同名**：後者多燒了 N−1 次
#: 整個 agent 行程的預算。兩者在資料上同形的話，成本就從紀錄裡消失了。
REFUSAL_REASONS = frozenset({"visible_fail", "attempts_exhausted", "no_suite"})

#: 退出碼。**退出碼反映裁決**，不是反映 agent 自己的退出碼。
EXIT_ACCEPTED, EXIT_REFUSED, EXIT_VOID = 0, 20, 22


def _freeze(workspace: pathlib.Path, dest: pathlib.Path) -> tuple[str, str]:
    """把工作區複製成凍結快照。回 `(快照雜湊, 複製後再量一次的活雜湊)`。

    兩個值都回，是因為**只有它們相等才代表快照可信**：不等就表示 agent
    （或別的東西）在我們複製的當下還在寫，那一格的驗收結論不成立。
    這就是邊界 4 的 TOCTOU 那一條，R534 已經這樣做，照抄。
    """
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(workspace, dest, symlinks=True,
                    ignore=shutil.ignore_patterns(*wshash.EXCLUDED_DIRS))
    return wshash.tree_hash(dest), wshash.tree_hash(workspace)


def _sign_attempt(book, ident, *, task_id: str, arm: str, rec: dict,
                  retry_arm: str, n_max: int) -> None:
    """簽一筆 `ws_attempt`。**每一次嘗試都要走這裡，沒有 happy path 例外。**

    `verdict_sha256=None` ＝ 這一輪沒有跑驗收（R530 的語意，逐字沿用）——
    與「跑了但全錯」是兩件事，不可合併。
    """
    receipts.append_attempt(
        book, ident, task_id=task_id, arm=arm, attempt=rec["attempt"],
        gate_round=rec["attempt"], ws_sha256=rec["ws_end_sha256"],
        verdict_sha256=rec.get("verdict_sha256"),
        conversation_sha256=rec["wire_digest"], run="vacant-run",
        conversation_digest_kind="wire_bytes",
        requests_seen=rec["requests_seen"], retry=retry_arm,
        max_attempts=n_max, accepted=rec.get("accepted"),
        ws_start_sha256=rec["ws_start_sha256"],
        agent_rc=rec.get("agent_rc"), stop_reason=rec.get("stop_reason"))


def resolve_max_attempts(retry_arm: str, max_attempts: int | None) -> int:
    """`--retry` ＋ `--max-attempts` → 實際的嘗試上限。**壞組合一律 fail-visible。**

    `--retry none` 配 `--max-attempts 3` 不是「保守的預設」，是**使用者以為
    開了迴圈但沒開**。安靜地當成 1 會讓一次不重試的跑看起來像重試過——
    那種錯要在畫面上死掉，不是在資料裡活著。
    """
    if retry_arm not in retrypolicy.RETRY_ARMS:
        raise SystemExit(f"--retry 只認 {list(retrypolicy.RETRY_ARMS)}，"
                         f"拿到 {retry_arm!r}。停。")
    if max_attempts is None:
        return 1 if retry_arm == "none" else retrypolicy.DEFAULT_MAX_ATTEMPTS
    if max_attempts < 1:
        raise SystemExit(f"--max-attempts 至少是 1，拿到 {max_attempts}。停。")
    if retry_arm == "none" and max_attempts > 1:
        raise SystemExit(
            f"--retry none 不會重試，--max-attempts {max_attempts} 不會發生。"
            "要迴圈就給 --retry resample 或 --retry revise。停。")
    return max_attempts


def run(argv: list[str], *, workspace: pathlib.Path, run_dir: pathlib.Path,
        suite_dir: pathlib.Path | None, vacant_on: bool, task_id: str,
        sandbox_name: str = "auto", allow_no_suite: bool = False,
        port: int = 0, timeout_s: float | None = None,
        test_timeout_s: float = 10.0, inherit_stdin: bool = False,
        retry_arm: str = "none", max_attempts: int | None = None) -> dict:
    """跑一次（V1：最多 `max_attempts` 次嘗試）。回一份可落盤的 summary。

    **預設 `retry_arm="none"` ＝ V0 的行為逐字不變**：一次嘗試、一筆
    `ws_attempt`、一筆 `ws_verdict`、`visible_fail` 還是叫 `visible_fail`。
    """
    workspace, run_dir = workspace.resolve(), run_dir.resolve()
    # 收據落在工作區裡會把自己算進樹雜湊（wire log 每一通都在長大）⇒
    # `ws_end_sha256` 會變成「收據寫了多少」的函數。fail-visible，不要靜靜容忍。
    if run_dir == workspace or workspace in run_dir.parents:
        raise SystemExit(
            f"--run-dir 不可以在工作區底下（{run_dir} ⊂ {workspace}）："
            "收據會把自己算進樹雜湊。換一個工作區外的路徑。停。")
    n_max = resolve_max_attempts(retry_arm, max_attempts)
    if retry_arm != "none" and not vacant_on:
        # OFF＝純 tee，**沒有裁決**可以拿來決定要不要再跑一次。在那裡開迴圈
        # 等於用一個不存在的判準重試。
        raise SystemExit("VACANT=0（OFF 臂）不驗收也不拒交，沒有裁決可以重試。"
                         "要迴圈就要 VACANT=1。停。")
    run_dir.mkdir(parents=True, exist_ok=True)
    arm = ARM_ON if vacant_on else ARM_OFF
    wire_dir = run_dir / f"wire_{arm}"
    sentinel = "vacant-run-" + uuid.uuid4().hex

    proxy = WireProxy(wire_dir=wire_dir,
                      upstreams=envmap.discover_upstreams(),
                      keys=envmap.discover_keys(), sentinel=sentinel,
                      mode=("act" if vacant_on else "tee"), port=port)
    proxy.start()
    child_env, env_meta = envmap.build_child_env(proxy.url, sentinel)

    ws_start = wshash.tree_hash(workspace)
    t0 = time.time()
    summary: dict = {
        "task_id": task_id, "arm": arm, "vacant": int(vacant_on),
        "argv": list(argv), "workspace": str(workspace),
        "proxy_url": proxy.url, "env": env_meta,
        "ws_start_sha256": ws_start, "ws_end_sha256": None,
        "agent_rc": None, "agent_timed_out": False,
        "requests_seen": 0, "wire_by_protocol": {},
        "accepted": None, "refused": None, "stop_reason": None,
        "infra_void": None,
        "visible_passed": None, "visible_total": None,
        "verdict_sha256": None, "verdict_hash": None,
        # ── V1 ────────────────────────────────────────────────────────
        "retry": retry_arm, "max_attempts": n_max, "attempts_used": 0,
        "attempts": [], "retry_constants": retrypolicy.constants_manifest(),
    }
    # 收據鏈在**迴圈之前**開，好讓每一次嘗試結束時就簽得下去（見模組 docstring
    # 的 R530 坑）。OFF 臂沒有收據這回事 ⇒ 兩個都是 None。
    ident, book = ((Identity.generate(), Logbook()) if vacant_on
                   else (None, None))
    has_suite = (suite_dir is not None
                 and any(pathlib.Path(suite_dir).glob("test_*.py")))
    sandbox = None
    origin_dir = None
    try:
        if retry_arm == "resample" and n_max > 1:
            # 起點的**完整**副本（含 `.git`）。理由見 `retry.py`：
            # 排除清單是樹雜湊的清單，不是重置的清單。
            origin_dir = run_dir / "_origin"
            retrypolicy.snapshot_origin(workspace, origin_dir)
            summary["origin_snapshot"] = {"path": str(origin_dir),
                                          "ws_sha256": ws_start}

        for attempt in range(1, n_max + 1):
            rec: dict = {"attempt": attempt, "retry": retry_arm,
                         "reset": None, "feedback": None}
            seen_before = proxy.stats["requests_seen"]

            # ── 2') 這一次嘗試之前：重置（resample）或留著（revise）───
            if attempt > 1 and retry_arm == "resample":
                retrypolicy.restore_origin(origin_dir, workspace)
                back = wshash.tree_hash(workspace)
                rec["reset"] = {"kind": "resample", "ws_sha256": back,
                                "back_to_start": back == ws_start}
                if back != ws_start:
                    rec["stop_reason"] = "ws_reset_failed"
                    summary["attempts"].append(rec)
                    summary.update({
                        "stop_reason": "ws_reset_failed",
                        "infra_void": f"reset={back} start={ws_start}"})
                    break
            rec["ws_start_sha256"] = wshash.tree_hash(workspace)

            # ── 3) spawn agent，等它結束。**那一刻就是交付點。** ──────
            t_a = time.time()
            try:
                proc = subprocess.Popen(
                    argv, cwd=str(workspace), env=child_env,
                    # ⚠ 預設把 stdin 接到 /dev/null：`pi -p` 不給
                    #   `< /dev/null` 會永久卡住（2026-09-18 實測）。
                    #   要互動式 agent 才給 `--stdin inherit`。
                    stdin=(None if inherit_stdin else subprocess.DEVNULL))
            except OSError as exc:
                rec["stop_reason"] = "agent_spawn_failed"
                summary["attempts"].append(rec)
                summary.update({"stop_reason": "agent_spawn_failed",
                                "infra_void": repr(exc)})
                break
            try:
                rec["agent_rc"] = proc.wait(timeout=timeout_s)
                rec["agent_timed_out"] = False
            except subprocess.TimeoutExpired:
                proc.kill()
                rec["agent_rc"] = proc.wait()
                rec["agent_timed_out"] = True
            rec["agent_wall_s"] = round(time.time() - t_a, 3)
            # **等預算＝上限相同、實際用量落盤**（R530 的裁決），不是用滿。
            rec["requests_seen"] = proxy.stats["requests_seen"] - seen_before
            rec["requests_seen_cumulative"] = proxy.stats["requests_seen"]
            rec["wire_digest"] = proxy.wire_digest()

            # ── 4) 凍結 → 驗收 ───────────────────────────────────────
            #  attempt 1 的落點名字**與 V0 逐字相同**（README 印的就是那一行）；
            #  第 2 次以後才加 `_a<n>` 後綴。哪一次是最後一次由 `attempts`
            #  陣列說了算，不要用檔名猜。
            suffix = "" if attempt == 1 else f"_a{attempt}"
            frozen_dir = run_dir / f"_frozen_{arm}{suffix}"
            frozen, live_after = _freeze(workspace, frozen_dir)
            rec["ws_end_sha256"] = frozen
            rec["frozen_path"] = str(frozen_dir)
            if frozen != live_after:
                rec["stop_reason"] = "ws_moved_during_freeze"
                summary["attempts"].append(rec)
                summary.update({
                    "stop_reason": "ws_moved_during_freeze",
                    "ws_end_sha256": frozen,
                    "infra_void": f"frozen={frozen} live={live_after}"})
                break

            if not vacant_on:
                # OFF＝純 tee：不驗收、不簽收據、不拒交。
                # **但 wire 照樣逐字落盤**（鐵律 3 對兩臂都成立）。
                rec.update({"stop_reason": "ungated", "accepted": None})
                summary["attempts"].append(rec)
                break

            if not has_suite:
                # fail-closed：量不到不是通過。這與「有套件但沒過」不同，
                # **重試改變不了它**（套件不會自己長出來）⇒ 不進迴圈。
                # ⚠ 這一次照樣簽一筆 `ws_attempt`，`verdict_sha256=None`
                #   ＝「這一輪沒有跑驗收」（R530 的語意，逐字沿用）。
                #   不簽的話這一格會變成 0 筆 attempt、1 筆 verdict——
                #   正是模組 docstring 講的那個坑。
                rec.update({
                    "stop_reason": "ungated" if allow_no_suite else "no_suite",
                    "accepted": None if allow_no_suite else False,
                    "verdict_sha256": None})
                _sign_attempt(book, ident, task_id=task_id, arm=arm, rec=rec,
                              retry_arm=retry_arm, n_max=n_max)
                summary["attempts"].append(rec)
                break

            if sandbox is None:
                sandbox, backend_meta = make_sandbox(sandbox_name,
                                                     workdir=run_dir)
                summary["sandbox"] = {k: backend_meta.get(k)
                                      for k in ("backend", "sandbox",
                                                "requested")}
            result = acceptance.run_suite(
                sandbox, frozen_dir, suite_dir, suite="visible",
                task_id=task_id, verify_root=run_dir / "_verify",
                timeout_s=test_timeout_s)
            (run_dir / f"visible_{arm}{suffix}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8")
            ok = bool(result.get("all_pass"))
            failures = "" if ok else acceptance.render_failures(result)
            rec.update({
                "visible_passed": result.get("passed"),
                "visible_total": result.get("total"),
                "verdict_sha256": result.get("result_sha256"),
                "visible_path": str(run_dir / f"visible_{arm}{suffix}.json"),
                "accepted": ok, "failures": failures,
                "stop_reason": "visible_pass" if ok else "visible_fail",
            })

            # ── 5) 每一次嘗試都簽一筆 `ws_attempt`，**不是只在 happy path**
            _sign_attempt(book, ident, task_id=task_id, arm=arm, rec=rec,
                          retry_arm=retry_arm, n_max=n_max)
            summary["attempts"].append(rec)
            if ok or attempt == n_max:
                break

            # ── 6) 沒過而且還有額度：照臂的政策準備下一次 ─────────────
            if retry_arm == "revise":
                # **只餵可見驗收的失敗原文**（`result` 來自
                # `run_suite(suite="visible")`）。隱藏測資一律不進這個檔。
                try:
                    text = retrypolicy.render_feedback(
                        failures, attempt=attempt, max_attempts=n_max)
                except KS1Violation as exc:
                    # 鐵律 1：**違反＝run 作廢**。責任修辭有可能不是從模板來，
                    # 而是從客戶測試的訊息裡帶進來的——那一樣不准送出去。
                    # 判 `infra_void` 而不是拒交：這一格沒有量到任何東西。
                    summary.update({"stop_reason": "ks1_violation",
                                    "infra_void": repr(exc)})
                    break
                meta = retrypolicy.write_feedback(workspace, text)
                rec["feedback"] = {**meta, "text": text}
    finally:
        proxy.stop()

    summary["attempts_used"] = len(summary["attempts"])
    summary["requests_seen"] = proxy.stats["requests_seen"]
    summary["wire_by_protocol"] = dict(proxy.stats["by_wire"])
    summary["wire_errors"] = proxy.stats["errors"]
    summary["wire_digest"] = proxy.wire_digest()
    summary["run_wall_s"] = round(time.time() - t0, 3)
    _rollup(summary, n_max)
    assert summary["stop_reason"] in STOP_REASONS, summary["stop_reason"]
    _persist(run_dir, summary, arm if vacant_on else None, ident, book)
    return summary


def _rollup(summary: dict, n_max: int) -> None:
    """把最後一次嘗試的結果攤到 summary 頂層（V0 的欄位形狀逐字不變）。

    ⚠ **`visible_fail` 與 `attempts_exhausted` 的分界就寫在這裡**：
    `max_attempts == 1` ＝ 單發沒過；`> 1` ＝ 迴圈用完額度仍沒過，
    後者多燒了 N−1 次整個 agent 行程。兩者同名的話，成本會從紀錄裡消失。
    """
    if summary.get("infra_void"):
        return                      # 基建事件不是裁決，什麼都不 roll up
    last = summary["attempts"][-1] if summary["attempts"] else None
    if last is None:                # 一次都沒跑成（理論上進不來，防呆）
        summary.update({"stop_reason": "agent_spawn_failed",
                        "infra_void": "no attempt was recorded"})
        return
    for k in ("agent_rc", "agent_timed_out", "ws_end_sha256",
              "visible_passed", "visible_total", "verdict_sha256"):
        if k in last:
            summary[k] = last[k]
    summary["agent_wall_s"] = last.get("agent_wall_s")
    summary["failures"] = last.get("failures", "")
    if last["stop_reason"] in ("no_suite", "ungated"):
        summary.update({
            "stop_reason": last["stop_reason"],
            "accepted": last["accepted"],
            "refused": last["stop_reason"] == "no_suite"})
        return
    ok = bool(last.get("accepted"))
    summary.update({
        "accepted": ok, "refused": not ok,
        "stop_reason": ("visible_pass" if ok else
                        "visible_fail" if n_max == 1 else "attempts_exhausted"),
    })


def _persist(run_dir: pathlib.Path, summary: dict, arm: str | None,
             ident, book) -> None:
    """落盤：`rows.jsonl` ＋（只有 ON 才有的）簽章鏈 ＋ `run_<ARM>.json`。

    收據形狀逐字沿用 R530，所以 `ops/gain/replay/verify_run_receipts.py`
    一個字都不用改就驗得過（**每題每臂一筆 `ws_verdict`**、
    `ws_attempt` ≥ 它——V1 的迴圈讓後者可以是 N 筆，前者仍然只有一筆，
    因為一次 `run()` 只交付一次）。

    ⚠ `infra_void` **整條鏈都不落盤**（V0 的語意：基建事件不是裁決）。
      已經簽過的那幾筆 `ws_attempt` 不會憑空消失——它們的全文在
      `run_<ARM>.json` 的 `attempts` 陣列裡，只是沒有簽章背書。
      理由是對帳規則：`rows.jsonl` 那一列沒有 verdict，鏈只要落盤就會被
      判 `verdict_count_ne_rows`，而那會把「基建壞了」報成「鏈壞了」。
    """
    row = {k: summary[k] for k in
           ("task_id", "arm", "vacant", "ws_start_sha256", "ws_end_sha256",
            "agent_rc", "requests_seen", "accepted", "refused", "stop_reason")}
    row["infra_void"] = summary.get("infra_void")
    row["retry"] = summary.get("retry")
    row["attempts_used"] = summary.get("attempts_used")
    row["max_attempts"] = summary.get("max_attempts")
    with (run_dir / "rows.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (run_dir / f"run_{summary['arm']}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if arm is None or book is None or summary.get("infra_void"):
        return      # infra_void 不簽收據：基建事件不是裁決
    entry = receipts.append_verdict(
        book, ident, task_id=summary["task_id"], arm=arm,
        accepted=bool(summary["accepted"]),
        ws_start_sha256=summary["ws_start_sha256"],
        ws_end_sha256=summary["ws_end_sha256"],
        verdict_sha256=summary["verdict_sha256"],
        conversation_sha256=summary["wire_digest"],
        stop_reason=summary["stop_reason"], run="vacant-run",
        # `accepted_is_null` ＝ `--allow-no-suite` 的那一格。`accepted` 欄位
        # 被 `bool()` 壓成 False，所以「沒量」必須另外有一個欄位說出來，
        # 否則它會和「量到沒過」在資料上同形。
        accepted_is_null=(summary["accepted"] is None),
        conversation_digest_kind="wire_bytes",
        agent_rc=summary["agent_rc"], requests_seen=summary["requests_seen"],
        # 迴圈的成本落在裁決上：這一格總共燒了幾次整個 agent 行程。
        retry=summary["retry"], attempts_used=summary["attempts_used"],
        max_attempts=summary["max_attempts"])
    summary["verdict_hash"] = entry.hash()
    book.save(run_dir / f"receipts_{arm}.ndjson")
    (run_dir / f"receipts_{arm}.pub.json").write_text(json.dumps(
        {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)},
        ensure_ascii=False), encoding="utf-8")
    (run_dir / f"run_{summary['arm']}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def exit_code(summary: dict) -> int:
    """退出碼反映**裁決**，不是 agent 自己的退出碼。

    OFF 臂沒有裁決可反映 ⇒ 透傳 agent 的退出碼（那一臂本來就不 gate）。
    """
    if summary.get("infra_void"):
        return EXIT_VOID
    if not summary.get("vacant"):
        return int(summary.get("agent_rc") or 0)
    return EXIT_REFUSED if summary.get("refused") else EXIT_ACCEPTED


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vacant run", description="把任意 agent 命令包起來：中介模型通道、"
                                       "在行程結束那一刻跑驗收、簽收據、擋交付")
    ap.add_argument("--workspace", default=".", help="交付所在的工作區（預設 .）")
    ap.add_argument("--run-dir", default=None,
                    help="收據與 wire log 的落點（預設 <workspace>/.vacant-run/<ts>）")
    ap.add_argument("--suite", default=None,
                    help="可見驗收目錄（內含 test_*.py）。沒給且沒 --allow-no-suite ⇒ 拒交")
    ap.add_argument("--allow-no-suite", action="store_true",
                    help="明講「這一次不量」：accepted 落成 null，不是 true")
    ap.add_argument("--task-id", default=None, help="收據裡的 task_id（預設自動產生）")
    ap.add_argument("--vacant", choices=["0", "1"], default=None,
                    help="覆寫 VACANT 環境變數（0＝純 tee，1＝驗收＋收據＋拒交）")
    ap.add_argument("--port", type=int, default=0,
                    help="proxy 埠（預設 0＝ephemeral）。用設定檔的框架需要固定埠")
    ap.add_argument("--sandbox", default="auto",
                    help="驗收用的沙箱後端：auto／bwrap／unshare／none")
    ap.add_argument("--timeout", type=float, default=None, help="agent 逾時秒數")
    ap.add_argument("--test-timeout", type=float, default=10.0,
                    help="每個驗收測試檔的逾時秒數（預設 10，同 R530）")
    ap.add_argument("--stdin", choices=["devnull", "inherit"], default="devnull",
                    help="agent 的 stdin（預設 devnull——`pi -p` 不接 /dev/null 會永久卡住）")
    ap.add_argument("--retry", choices=list(retrypolicy.RETRY_ARMS),
                    default="none",
                    help="沒過之後做什麼：none＝不重試（預設，＝V0 的行為）／"
                         "resample＝重置工作區再跑一次（不給失敗原文）／"
                         "revise＝保留工作區、把失敗原文寫進 "
                         f"{retrypolicy.FEEDBACK_FILENAME} 再跑一次")
    ap.add_argument("--max-attempts", type=int, default=None,
                    help="嘗試上限（`--retry none` 恆為 1，其餘預設 "
                         f"{retrypolicy.DEFAULT_MAX_ATTEMPTS}）。"
                         "**這是成本上限不是目標值**：每一次嘗試都燒一整個 "
                         "agent 行程的 token 與時間，實際用量逐次落盤")
    ap.add_argument("--json", action="store_true", help="把 summary 印成 JSON")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="`--` 之後的整條 agent 命令")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else list(args.cmd)
    if not cmd:
        print("要給 `-- <agent 命令>`。停。", file=sys.stderr)
        return 2
    vacant_on = (args.vacant if args.vacant is not None
                 else os.environ.get("VACANT", "1")) not in ("0", "false", "no")
    workspace = pathlib.Path(args.workspace).resolve()
    task_id = args.task_id or f"vr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    # 預設落點在 `~/.vacant-run/`（同 `~/.vacant`／`~/.vacant-mcp` 的慣例），
    # **刻意不在工作區裡**——理由見 `run()` 開頭那條擋門。
    run_dir = pathlib.Path(args.run_dir).resolve() if args.run_dir else \
        pathlib.Path.home() / ".vacant-run" / task_id
    summary = run(cmd, workspace=workspace, run_dir=run_dir,
                  suite_dir=pathlib.Path(args.suite).resolve() if args.suite else None,
                  vacant_on=vacant_on, task_id=task_id,
                  sandbox_name=args.sandbox, allow_no_suite=args.allow_no_suite,
                  port=args.port, timeout_s=args.timeout,
                  test_timeout_s=args.test_timeout,
                  inherit_stdin=(args.stdin == "inherit"),
                  retry_arm=args.retry, max_attempts=args.max_attempts)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        v = summary["stop_reason"]
        mark = ("拒交" if summary.get("refused") else
                "infra_void" if summary.get("infra_void") else
                "未 gate" if summary.get("accepted") is None else "交付")
        # 嘗試次數**一定印**（連 `1/1` 也印）：重試燒的是真的 token 與時間，
        # 只在「有重試過」的時候才提，等於把成本做成一個要去別處查的東西。
        tries = f"{summary['attempts_used']}/{summary['max_attempts']} 次"
        if summary.get("retry") != "none":
            tries += f"（{summary['retry']}）"
        print(f"[vacant run] {summary['arm']}　{mark}（{v}）　{tries}　"
              f"ws {summary['ws_start_sha256'][:12]}→"
              f"{(summary['ws_end_sha256'] or '')[:12]}　"
              f"wire {summary['requests_seen']} 通　收據 {run_dir}",
              file=sys.stderr)
        if summary.get("failures"):
            print(summary["failures"], file=sys.stderr)
    return exit_code(summary)


if __name__ == "__main__":
    raise SystemExit(main())
