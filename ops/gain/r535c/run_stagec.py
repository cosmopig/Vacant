"""這支在架構裡承重什麼：**Stage C 的驅動——「檔案從不被讀」是不是 pi 專屬的**。

預註冊 `decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md` **L-6** 逐字：

    Stage C（第二基質 10 題、只跑 RF／RP，看「file 從不被讀」是不是 pi 專屬）
    ＝選配、不進預註冊。S1／S2 歸檔後才准動；接不上就丟，不補。

⚠⚠ **L-6 寫死「不進預註冊」⇒ 本檔跑出來的數字不可以拿來做假說檢定。**
它能說的只有描述性的那一句：「在這 10 題上，agent X 的 `M7_file` 是 a/b」。
**禁止**拿它跟 S1／S2 合併、做任何統計檢定、或說「效果複製了／沒複製」。
收官句只能是描述。這一條同時寫在 `README.md` 與逐格落盤的 `stagec_meta.json`。

## 設計（照 L-6，沒有自己加東西）

- **10 題**：`ops/gain/r535/bank/` 的 S1 前 10 題（`s1_01…s1_10`）。**不另外挑**
  ——挑題本身就是一個選擇點。
- **只跑 RF／RP 兩臂**（旗標從 `run_r535.ARMS` **原樣引用**，不在這裡重打字串）。
- **兩個第二基質**：OpenCode 1.18.31（設定路線）＋ Claude Code 2.1.278（零接線），
  接線都照 `docs/AGENT_COMPAT.md` §8／§9，走 `ops/vacantrun/wrap_agent.sh`。
- 同一顆模型、同一個端點、`reasoning_effort: "none"`
  （**後者靠 `effort_shim.py`**——兩個 agent 的設定路線裡沒有那個欄位，
  而不補就是換了推論模式；實測 5 ⇒ 0，理由寫在那支的 docstring）。
- ⇒ **10 題 × 2 臂 × 2 agent ＝ 40 格。**

## 量什麼（主軸是 M7 三層，不是效果量）

`M7_name`（檔名有沒有進 wire）／`M7_file`（回饋**內容**有沒有進 wire）／
`M7_ws`（有沒有看工作區）／`M7_ws_solution`（有沒有讀自己上一份錯碼），
外加 `requests_seen`、`upstreams_defaulted`、最終 `accepted`。
**三個 M7 的量具從 `run_r535.py` 原樣引用**，只有一處擴充：

⚠ **`M7_ws` 的解析器要多認一種形狀。** `run_r535._tool_calls_from_body` 只認
OpenAI 的 `messages[].tool_calls[].function`；Claude Code 走的是 Anthropic
Messages（`content` 裡的 `tool_use` block）。**不擴充的話 Claude Code 那 20 格
會全部落 `unparsable_tool_shape`（＝ null）**——那不是「沒看工作區」，是量具不認得。
擴充寫在本檔的 `_tool_calls_any` / `_tool_calls_from_anthropic_response`，
**分類函式（`classify_call`／`reads_own_solution`）仍然是 r535 那一份**，
而且 `--selftest` 兩種形狀各一條負控制：認不出來就紅，不准安靜地回 0。

## 紀律

- `requests_seen == 0` ⇒ **`infra_void`，不是 0 分**（§4.5 的現場版本）。
- 四臂旗標、prompt、工作區樣板**全部從 `run_r535` 引用**，本檔不重打。
- 本檔**不動** `ops/gain/r535/` 與 `vacant_network/` 的任何一個位元組。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


#: **R535 的量具與凍結常數從這裡來，不在本檔重打。**
R5 = _load("r535_run_r535", HERE.parent / "r535" / "run_r535.py")
SHIM = _load("r535c_effort_shim", HERE / "effort_shim.py")

WRAP = REPO / "ops" / "vacantrun" / "wrap_agent.sh"

#: Stage C 的兩臂。**順序與旗標都引用 `run_r535.ARMS`。**
STAGEC_ARMS = ("RF", "RP")

#: L-6 的 10 題：**S1 的前 10 題**，照 manifest 的順序取，不另外挑。
STAGEC_N_TASKS = 10

#: 兩個第二基質。`wrap` ＝ `wrap_agent.sh` 的第一個參數。
AGENTS: dict[str, dict] = {
    "opencode": {
        "wrap": "opencode", "version_cmd": ["opencode", "--version"],
        "expect_version": "1.18.31",
        "route": "設定路線（OPENCODE_CONFIG_CONTENT）",
        "compat": "docs/AGENT_COMPAT.md §8",
    },
    "claude": {
        "wrap": "claude", "version_cmd": ["claude", "--version"],
        "expect_version": "2.1.278",
        "route": "零接線（ANTHROPIC_BASE_URL 在 envmap.REDIRECT_VARS）",
        "compat": "docs/AGENT_COMPAT.md §9",
    },
}

#: ⚠ **這一句不可以拿掉**：它跟著每一份產物走。
NOT_A_TEST = (
    "Stage C 照預註冊 L-6 是**選配、不進預註冊** ⇒ 本檔的數字**只能描述**："
    "「在這 10 題上，agent X 的 M7_file 是 a/b」。"
    "不准做假說檢定、不准與 S1／S2 合併、不准說「效果複製了／沒複製」。"
)

#: ⚠ **`by_agent` 是兩臂合併的，單獨引用它一定會被讀錯。**
#:
#: 2026-09-19 實際發生過一次：有人看 `by_agent` 讀到「OpenCode 的 `M7_name`
#: 是 0% 但 `M7_file` 是 50%」，以為那是「檔名沒進 wire、內容卻讀到了」的矛盾，
#: 懷疑量具在 OpenCode 上有盲點。**不是。** 兩個數字各由一個臂主導：
#:
#:   · `RP` 的 `M7_file = 100%` 是**設計如此**——回饋接在 argv 尾端（正控制）。
#:   · `RP` 的 `M7_name = 0%` 也是**設計如此**——`--feedback-into prompt`
#:     不把 `VACANT_FEEDBACK.md` 寫進工作區，那個檔根本不存在
#:     （凍結快照逐格可查：RF 的 `_frozen_*_a2/` 有那個檔，RP 的沒有）。
#:
#: ⇒ **要判讀就看 `by_agent_arm`。** `by_agent` 只拿來看 n 與健康檢查。
BY_AGENT_IS_ARM_MERGED = (
    "⚠ by_agent 是 RF＋RP **合併**的，不可單獨引用："
    "RP 的 M7_file 必為 1（回饋走 argv ＝正控制）、"
    "RP 的 M7_name 必為 0（那條管道不把檔案寫進工作區）。"
    "判讀一律看 by_agent_arm。"
)


# ── M7_ws：多一種工具呼叫形狀 ────────────────────────────────────────────

def _tool_calls_from_anthropic_body(blob: bytes) -> tuple[list[dict] | None,
                                                          dict]:
    """從一通 **Anthropic Messages** request body 撈這一段對話的所有工具呼叫。

    形狀（2026-09-19 vacant-dev 實測，Claude Code 2.1.278 × LM Studio）：
    `messages[].content[] = {"type": "tool_use", "id", "name", "input": {…}}`，
    工具結果是 `{"type": "tool_result", "tool_use_id", "content"}`。

    ⚠ 回傳的 `args` 是把 `input` **序列化成字串**——因為下游的
    `classify_call`／`reads_own_solution`（**r535 那一份，本檔不改**）吃的是字串。
    """
    ev = {"tool_use_blocks": 0, "tool_result_blocks": 0, "unparsable": False}
    try:
        body = json.loads(blob.decode("utf-8"))
    except Exception:                        # noqa: BLE001
        return None, ev
    if not isinstance(body, dict):
        return None, ev
    calls: list[dict] = []
    for m in body.get("messages") or []:
        if not isinstance(m, dict):
            continue
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            t = str(blk.get("type", ""))
            if t == "tool_result":
                ev["tool_result_blocks"] += 1
            elif t == "tool_use":
                ev["tool_use_blocks"] += 1
                calls.append({
                    "name": blk.get("name"),
                    "args": json.dumps(blk.get("input") or {},
                                       ensure_ascii=False)[:400],
                    "tool_call_id": blk.get("id")})
    if not calls and ev["tool_result_blocks"]:
        ev["unparsable"] = True
    return calls, ev


def _tool_calls_from_anthropic_response(blob: bytes) -> list[dict]:
    """最後一通 **Anthropic SSE** 回應裡新開的工具呼叫。

    同 `run_r535._tool_calls_from_response` 的理由：一次嘗試的最後一通回應如果
    是工具呼叫，那一筆**不會**出現在任何後續 request 的 history 裡。
    Anthropic 的形狀是 `content_block_start`（帶 `tool_use`）＋
    `content_block_delta`（`input_json_delta.partial_json` 逐段拼）。
    """
    parts: dict[int, dict] = {}
    for line in blob.split(b"\n"):
        s = line.strip()
        if not s.startswith(b"data:"):
            continue
        payload = s[5:].strip()
        if payload == b"[DONE]":
            continue
        try:
            d = json.loads(payload.decode("utf-8"))
        except Exception:                    # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        i = d.get("index", 0)
        if d.get("type") == "content_block_start":
            cb = d.get("content_block") or {}
            if cb.get("type") == "tool_use":
                parts[i] = {"name": cb.get("name"), "args": "",
                            "tool_call_id": cb.get("id")}
        elif d.get("type") == "content_block_delta" and i in parts:
            delta = d.get("delta") or {}
            if delta.get("type") == "input_json_delta":
                parts[i]["args"] += str(delta.get("partial_json") or "")
    return [{**v, "args": v["args"][:400]} for _, v in sorted(parts.items())
            if v["name"]]


def _tool_calls_any(blob: bytes) -> tuple[list[dict] | None, dict]:
    """兩種形狀都試。回 `(calls, evidence)`，`evidence["shape"]` 說是哪一種。

    順序：先 OpenAI（r535 原件），撈到就用；撈不到再試 Anthropic。
    **兩邊都撈不到、但看得見工具痕跡 ⇒ `unparsable`**（照 r535 的紀律：
    量具壞了不是機制沒被觸發，`M7_ws` 落 `null` 不落 `false`）。
    """
    oa_calls, oa_ev = R5._tool_calls_from_body(blob)
    if oa_calls:
        return oa_calls, {"shape": "openai", **oa_ev}
    an_calls, an_ev = _tool_calls_from_anthropic_body(blob)
    if an_calls:
        return an_calls, {"shape": "anthropic", **an_ev}
    if oa_calls is None and an_calls is None:
        return None, {"shape": None, "unparsable": False,
                      "reason": "body_not_json"}
    ev = {"shape": None, "unparsable": bool(oa_ev.get("unparsable")
                                            or an_ev.get("unparsable")),
          "openai": oa_ev, "anthropic": an_ev}
    return [], ev


def _tool_calls_from_response_any(blob: bytes) -> list[dict]:
    out = R5._tool_calls_from_response(blob)
    return out if out else _tool_calls_from_anthropic_response(blob)


def measure_m7_ws_any(run_dir: pathlib.Path, summary: dict,
                      slices: dict[int, list[str]], slice_meta: dict,
                      *, tools_path: pathlib.Path | None = None) -> dict:
    """`M7_ws` ＋ `M7_ws_solution`，**兩種 wire 形狀都認**。

    除了 `_tool_calls_any` 這一處，其餘邏輯與 `run_r535.measure_m7_ws`
    **逐條相同**：三種 `null` 的理由分開記、一種都不寫成 `false`、
    分類用 r535 的 `classify_call`／`reads_own_solution`、工具序列一律落盤。
    """
    arm = summary["arm"]
    attempts = summary.get("attempts") or []
    res: dict = {"m7_ws": None, "m7_ws_reason": None, "m7_ws_ratio": None,
                 "m7_ws_counts": {}, "m7_ws_calls": [],
                 "m7_ws_solution": None, "m7_ws_solution_reason": None,
                 "m7_ws_solution_ratio": None, "m7_ws_solution_n": 0,
                 "m7_ws_source": "last_request_per_attempt+last_response",
                 "m7_ws_shapes": [], "m7_ws_unparsable_evidence": None}
    if len(attempts) < 2:
        res["m7_ws_reason"] = res["m7_ws_solution_reason"] = "no_second_attempt"
        return res
    if not slice_meta.get("ok"):
        why = f"wire_unmappable: {slice_meta.get('reason')}"
        res["m7_ws_reason"] = res["m7_ws_solution_reason"] = why
        return res
    counts: dict[str, int] = {}
    total, sol_n, parsed_any = 0, 0, False
    unparsable: list[dict] = []
    seq = 0
    rows: list[dict] = []
    for rec in attempts:
        n = rec["attempt"]
        if n < 2:
            continue
        ids = slices.get(n, [])
        if not ids:
            continue
        blob = R5._req_blobs(run_dir, arm, ids[-1:])
        if not blob:
            continue
        calls, ev = _tool_calls_any(blob[0])
        if calls is None:
            continue
        if ev.get("shape"):
            res["m7_ws_shapes"].append({"attempt": n, "shape": ev["shape"]})
        if ev.get("unparsable"):
            unparsable.append({"attempt": n, "call_id": ids[-1], **ev})
        tail = run_dir / f"wire_{arm}" / f"{ids[-1]}.resp.bin"
        extra = _tool_calls_from_response_any(tail.read_bytes()) \
            if tail.exists() else []
        parsed_any = True
        for c, src in ([(c, "request_history") for c in calls]
                       + [(c, "last_response") for c in extra]):
            kind = R5.classify_call(c["name"], c["args"])
            is_sol = R5.reads_own_solution(c["name"], c["args"])
            counts[kind] = counts.get(kind, 0) + 1
            total += 1
            sol_n += 1 if is_sol else 0
            seq += 1
            rows.append({"attempt": n, "seq": seq, "call_id": ids[-1],
                         "tool_call_id": c.get("tool_call_id"),
                         "tool": c["name"], "kind": kind,
                         "reads_own_solution": is_sol, "source": src,
                         "args_head": c["args"][:80]})
            res["m7_ws_calls"].append(
                {"attempt": n, "name": c["name"], "kind": kind,
                 "reads_own_solution": is_sol, "args": c["args"][:200]})
    if tools_path is not None:
        tools_path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8")
    if unparsable:
        res["m7_ws_unparsable_evidence"] = unparsable
        res["m7_ws_reason"] = res["m7_ws_solution_reason"] = \
            "unparsable_tool_shape"
        return res
    if not parsed_any:
        res["m7_ws_reason"] = res["m7_ws_solution_reason"] = \
            "no_parsable_request_body"
        return res
    other = total - counts.get("read_task", 0) - counts.get(
        "write_solution", 0)
    res["m7_ws_counts"] = {**counts, "total": total, "other_total": other,
                           "reads_own_solution": sol_n}
    res["m7_ws_solution_n"] = sol_n
    if total == 0:
        res["m7_ws_reason"] = res["m7_ws_solution_reason"] = \
            "no_tool_calls_in_attempt_ge2"
        return res
    res["m7_ws_ratio"] = other / total
    res["m7_ws_solution_ratio"] = sol_n / total
    res["m7_ws"] = bool(other > 0)
    res["m7_ws_solution"] = bool(sol_n > 0)
    return res


# ── 推論模式：兩半分開記（F3 的 Stage C 版本）──────────────────────────

def measure_effort(run_dir: pathlib.Path, arm: str, shim_log: pathlib.Path,
                   t0: float, t1: float, *, value: str = "none") -> dict:
    """**推論模式的兩半，兩半都記，而且分開記。**

    ① `effort_in_agent_request`：**agent 自己**有沒有送 `reasoning_effort`
       （預期 `False`——兩個 agent 的設定路線裡沒有那個欄位。這正是 shim 存在的理由）。
    ② `effort_injected_all`：這一格期間 shim 有沒有對**每一通帶 `model` 的**請求
       補上它（`shim.jsonl` 逐通）。
    ③ `reasoning_tokens`：回應裡實際是幾。

    ⚠ **`/v1/messages` 那條路的 `usage` 不報 `reasoning_tokens`**
    （2026-09-19 實測）⇒ Claude Code 那 20 格的 ③ 是 `unmeasured`，
    **不准當成 0**。這是本輪一條真的殘餘，寫在 README 的「不能被讀成什麼」。
    """
    res: dict = {"effort_expect": value, "effort_calls": 0,
                 "effort_in_agent_request": 0,
                 "reasoning_tokens_values": [], "rt_zero": 0, "rt_nonzero": 0,
                 "rt_unmeasured": 0, "effort_verdict": None,
                 "shim_model_calls": 0, "shim_injected": 0,
                 "shim_already_correct": 0, "shim_errors": 0}
    idx = run_dir / f"wire_{arm}" / "index.jsonl"
    if idx.exists():
        wdir = run_dir / f"wire_{arm}"
        for s in idx.read_text(encoding="utf-8").splitlines():
            if not s.strip():
                continue
            rec = json.loads(s)
            cid = rec.get("call_id")
            req, resp = wdir / f"{cid}.req.bin", wdir / f"{cid}.resp.bin"
            if not req.exists():
                continue
            res["effort_calls"] += 1
            try:
                body = json.loads(req.read_bytes().decode("utf-8"))
                if isinstance(body, dict) and body.get("reasoning_effort"):
                    res["effort_in_agent_request"] += 1
            except Exception:                # noqa: BLE001
                pass
            rt = R5.reasoning_tokens_of(
                R5.sse_usage(resp.read_bytes()) if resp.exists() else None)
            if rt is None:
                res["rt_unmeasured"] += 1
            elif rt == 0:
                res["rt_zero"] += 1
            else:
                res["rt_nonzero"] += 1
            if rt is not None and len(res["reasoning_tokens_values"]) < 32:
                res["reasoning_tokens_values"].append(rt)
    if shim_log.exists():
        for s in shim_log.read_text(encoding="utf-8").splitlines():
            if not s.strip():
                continue
            try:
                rec = json.loads(s)
            except Exception:                # noqa: BLE001
                continue
            if not (t0 <= rec.get("ts", 0) <= t1):
                continue
            if rec.get("reason") in ("no_model_field", "not_json",
                                     "empty_body", "not_object"):
                continue
            res["shim_model_calls"] += 1
            if rec.get("reason") == "injected":
                res["shim_injected"] += 1
            elif rec.get("reason") == "already_correct":
                res["shim_already_correct"] += 1
            if rec.get("error"):
                res["shim_errors"] += 1
    covered = res["shim_injected"] + res["shim_already_correct"]
    if res["effort_calls"] == 0:
        res["effort_verdict"] = "unmeasured"
    elif res["rt_nonzero"]:
        res["effort_verdict"] = "thinking_on"      # ⇒ 該格 INVALID
    elif covered < res["shim_model_calls"] or res["shim_model_calls"] == 0:
        res["effort_verdict"] = "shim_incomplete"  # ⇒ 該格 INVALID
    elif res["rt_unmeasured"] and not res["rt_zero"]:
        # 量不到就是量不到（Anthropic wire）。**不報 ok。**
        res["effort_verdict"] = "unmeasured_rt"
    else:
        res["effort_verdict"] = "ok"
    return res


# ── 計畫 ────────────────────────────────────────────────────────────────

def plan_rows(manifest: dict) -> list[dict]:
    """40 格。**確定性**：題照 manifest 的順序取前 10，臂輪轉，agent 外層。

    輪轉的理由與 `run_r535.plan_rows` 相同（裁決 R278）：兩臂固定同一個先後
    就把「第幾個跑」黏在臂上；輪轉讓它跨題抵銷。
    """
    tasks = manifest["strata"]["S1"]["task_ids"][:STAGEC_N_TASKS]
    if len(tasks) != STAGEC_N_TASKS:
        raise SystemExit(f"S1 題數不足 {STAGEC_N_TASKS}：{len(tasks)}")
    rows: list[dict] = []
    for agent in AGENTS:
        for idx, task_id in enumerate(tasks):
            r = idx % len(STAGEC_ARMS)
            order = STAGEC_ARMS[r:] + STAGEC_ARMS[:r]
            for pos, arm in enumerate(order):
                rows.append({"agent": agent, "task_id": task_id, "arm": arm,
                             "stratum": "S1", "task_index": idx,
                             "arm_pos": pos,
                             "cell": f"{agent}__{task_id}__{arm}"})
    for i, r in enumerate(rows):
        r["plan_index"] = i
    return rows


# ── 一格 ────────────────────────────────────────────────────────────────

class StageCDriver:
    def __init__(self, args, manifest: dict, manifest_sha: str):
        self.a = args
        self.manifest = manifest
        self.manifest_sha = manifest_sha
        self.out = pathlib.Path(args.out).resolve()
        self.bank = R5.bank_dir(pathlib.Path(args.bank_manifest), manifest)
        self.cells_dir = self.out / "cells"
        self.log = self.out / f"driver_{args.stream}.jsonl"
        self.upstream = R5.upstream_base(args.endpoint)
        self.shim_log = self.out / f"shim_{args.stream}.jsonl"
        self.shim: SHIM.EffortShim | None = None

    def ev(self, kind: str, **kw) -> None:
        R5.jsonl_append(self.log, {"ts": R5.now_iso(), "stream": self.a.stream,
                                   "event": kind, **kw})

    # -- 接線 -------------------------------------------------------------
    def cell_argv(self, cell: pathlib.Path, task_id: str, arm: str,
                  agent: str) -> list[str]:
        """**旗標與 prompt 都從 `run_r535` 引用**，本檔只換 `--` 之後那一段。"""
        spec = R5.ARMS[arm]
        suite = self.bank / task_id / "tests_visible"
        prompt = R5.PI_PROMPT + (R5.FEEDBACK_PLACEHOLDER
                                 if spec["placeholder"] else "")
        return [sys.executable, "-m", "vacant_network.vrun.launcher",
                "--workspace", str(cell / "ws"),
                "--run-dir", str(cell / "run"),
                "--suite", str(suite),
                "--task-id", f"r535c_{agent}_{task_id}_{arm}",
                "--vacant", "1",
                "--sandbox", self.a.sandbox,
                "--test-timeout", str(self.a.test_timeout),
                "--timeout", str(self.a.agent_timeout),
                "--json", *spec["flags"],
                "--", str(WRAP), AGENTS[agent]["wrap"], prompt]

    def cell_env(self, agent: str) -> dict:
        env = dict(os.environ)
        env["VACANT"] = "1"
        assert self.shim is not None
        # **兩條路由都釘到本地。** openai 那條不是多餘的：Claude Code 啟動時探
        # `$ANTHROPIC_BASE_URL/api/hello`，而 `wireproxy.route()` 把它判給 openai
        # ⇒ 不釘的話那一通真的出網（`envmap` 誠實邊界，AGENT_COMPAT §9.4）。
        env["VACANT_RUN_UPSTREAM_OPENAI"] = self.shim.url + "/v1"
        env["VACANT_RUN_UPSTREAM_ANTHROPIC"] = self.shim.url
        env["OPENAI_API_KEY"] = "lmstudio"
        env["VACANT_AGENT_MODEL"] = self.a.model
        env["PYTHONPATH"] = (str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
                             ).rstrip(os.pathsep)
        if self.a.node_bin:
            env["PATH"] = self.a.node_bin + os.pathsep + env.get("PATH", "")
        # agent 之間不要互吃狀態（wrap_agent.sh 自己也清一輪，這裡多一道）。
        for k in ("OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR",
                  "CLAUDE_CONFIG_DIR", "ANTHROPIC_MODEL"):
            env.pop(k, None)
        return env

    # -- 跑 ---------------------------------------------------------------
    def run_cell(self, row: dict) -> dict | None:
        task_id, arm, agent = row["task_id"], row["arm"], row["agent"]
        cell = self.cells_dir / row["cell"]
        try:
            cell.mkdir(parents=True)
        except FileExistsError:
            done = self.cell_done(cell)
            self.ev("skip", cell=row["cell"],
                    reason="run_complete" if done else "dir_exists_not_complete")
            return None
        io = cell / "io.jsonl"
        started = time.time()
        R5.jsonl_append(io, {"ts": R5.now_iso(), "event": "cell_start", **row,
                             "bank_manifest_sha256": self.manifest_sha,
                             "arm_flags": R5.ARMS[arm]["flags"],
                             "upstream": self.upstream,
                             "shim": self.shim.url if self.shim else None})
        state: dict = {
            "cell": row["cell"], "task_id": task_id, "arm": arm,
            "agent": agent, "agent_version": self.a.versions.get(agent),
            "stratum": row["stratum"], "run_complete": False,
            "cell_status": None, "started": R5.now_iso(),
            "bank_manifest_sha256": self.manifest_sha,
            "arm_flags": R5.ARMS[arm]["flags"], "prompt": R5.PI_PROMPT,
            "prompt_has_placeholder": R5.ARMS[arm]["placeholder"],
            "stream": self.a.stream, "reasoning_effort": self.a.effort,
            "agent_timeout_s": self.a.agent_timeout,
            "task_index": row.get("task_index"), "arm_pos": row.get("arm_pos"),
            "plan_index": row.get("plan_index"),
            "not_a_test": NOT_A_TEST,
        }
        self.write_cell(cell, state)

        landed = R5.materialise_ws(cell / "ws", self.bank / task_id, arm,
                                   self.manifest)
        state["workspace_files"] = landed
        argv = self.cell_argv(cell, task_id, arm, agent)
        state["launcher_argv"] = argv
        R5.jsonl_append(io, {"ts": R5.now_iso(), "event": "materialised",
                             "files": landed, "argv": argv})
        if self.a.dry_run:
            state.update({"cell_status": "dry_run", "run_complete": False})
            self.write_cell(cell, state)
            return state

        rc, tries, void_reason = None, [], None
        t_lo = time.time()
        for i in range(1, R5.INFRA_RETRIES + 1):
            if i > 1:
                for name in ("run", "ws"):
                    src = cell / name
                    if src.exists():
                        src.rename(cell / f"{name}_void_{i - 1}")
                R5.materialise_ws(cell / "ws", self.bank / task_id, arm,
                                  self.manifest)
            t0 = time.time()
            proc = subprocess.run(argv, cwd=str(REPO), env=self.cell_env(agent),
                                  capture_output=True, text=True)
            rc = proc.returncode
            (cell / f"launcher_stdout_{i}.json").write_text(
                proc.stdout or "", encoding="utf-8")
            (cell / f"launcher_stderr_{i}.log").write_text(
                proc.stderr or "", encoding="utf-8")
            tries.append({"try": i, "rc": rc,
                          "wall_s": round(time.time() - t0, 3)})
            R5.jsonl_append(io, {"ts": R5.now_iso(), "event": "launcher_done",
                                 "try": i, "rc": rc,
                                 "wall_s": round(time.time() - t0, 3),
                                 "stderr_tail": (proc.stderr or "")[-600:]})
            if rc in (R5.EXIT_ACCEPTED, R5.EXIT_REFUSED):
                # `requests_seen == 0` ＝ **agent 沒被中介到**，不是量測。
                sp = cell / "run" / "run_RUN-ON.json"
                seen = None
                if sp.exists():
                    try:
                        seen = json.loads(sp.read_text(encoding="utf-8")
                                          ).get("requests_seen")
                    except Exception:        # noqa: BLE001
                        seen = None
                if seen:
                    break
                void_reason = (f"requests_seen={seen!r}：agent 沒被中介到"
                               f"（{agent} 的接線？），第 {i} 次")
                R5.jsonl_append(io, {"ts": R5.now_iso(),
                                     "event": "not_mediated",
                                     "try": i, "requests_seen": seen})
                rc = None
                continue
            if rc == 2:
                void_reason = f"launcher 拒收參數（rc=2）：{(proc.stderr or '')[-400:]}"
                state.update({"cell_status": "driver_bug",
                              "infra_void": void_reason, "run_complete": True,
                              "launcher_tries": tries})
                self.write_cell(cell, state)
                raise SystemExit(void_reason)
            void_reason = f"rc={rc}（infra_void 或未知），第 {i} 次"
        t_hi = time.time()
        state["launcher_tries"] = tries
        state["launcher_rc"] = rc

        summary_path = cell / "run" / "run_RUN-ON.json"
        if rc not in (R5.EXIT_ACCEPTED, R5.EXIT_REFUSED) \
                or not summary_path.exists():
            # **沒量到 ≠ 量到 0**：accepted 落 null，不落 False。
            state.update({
                "cell_status": "infra_void", "accepted": None,
                "infra_void": void_reason or "run_RUN-ON.json 不存在",
                "m7_file": None, "m7_file_reason": "infra_void",
                "m7_name": None, "m7_name_reason": "infra_void",
                "m7_ws": None, "m7_ws_reason": "infra_void",
                "m7_ws_solution": None,
                "wall_s": round(time.time() - started, 3),
                "run_complete": True, "finished": R5.now_iso()})
            self.write_cell(cell, state)
            R5.jsonl_append(self.out / "cells.jsonl", self.row_of(state))
            self.ev("cell_void", cell=row["cell"], reason=state["infra_void"])
            return state

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        state.update(self.harvest(cell, summary, arm, t_lo, t_hi))
        status = "measured"
        if state.get("effort_verdict") in ("thinking_on", "shim_incomplete"):
            status = "invalid_effort"
        state.update({"wall_s": round(time.time() - started, 3),
                      "cell_status": status, "finished": R5.now_iso(),
                      "run_complete": True})
        self.write_cell(cell, state)
        R5.jsonl_append(self.out / "cells.jsonl", self.row_of(state))
        self.ev("cell_done", cell=row["cell"], accepted=state.get("accepted"),
                stop_reason=state.get("stop_reason"),
                attempts=state.get("attempts_used"),
                requests_seen=state.get("requests_seen"),
                m7_name=state.get("m7_name"), m7_file=state.get("m7_file"),
                m7_ws=state.get("m7_ws"), wall_s=state["wall_s"])
        return state

    def harvest(self, cell: pathlib.Path, summary: dict, arm_name: str,
                t_lo: float, t_hi: float) -> dict:
        run_dir, arm = cell / "run", summary["arm"]
        attempts = summary.get("attempts") or []
        slices, slice_meta = R5.wire_slices(run_dir, arm, attempts)
        out: dict = {
            "accepted": summary.get("accepted"),
            "refused": summary.get("refused"),
            "stop_reason": summary.get("stop_reason"),
            "infra_void": summary.get("infra_void"),
            "attempts_used": summary.get("attempts_used"),
            "max_attempts": summary.get("max_attempts"),
            "requests_seen": summary.get("requests_seen"),
            "wire_by_protocol": summary.get("wire_by_protocol"),
            "wire_errors": summary.get("wire_errors"),
            "upstreams": summary.get("upstreams"),
            "upstreams_defaulted": summary.get("upstreams_defaulted"),
            "agent_wall_s": summary.get("agent_wall_s"),
            "visible_passed": summary.get("visible_passed"),
            "visible_total": summary.get("visible_total"),
            "ws_start_sha256": summary.get("ws_start_sha256"),
            "ws_end_sha256": summary.get("ws_end_sha256"),
            "verdict_sha256": summary.get("verdict_sha256"),
            "wire_digest": summary.get("wire_digest"),
            "wire_slice_meta": slice_meta,
            "attempts": [{
                "attempt": a["attempt"], "accepted": a.get("accepted"),
                "stop_reason": a.get("stop_reason"),
                "visible_passed": a.get("visible_passed"),
                "visible_total": a.get("visible_total"),
                "requests_seen": a.get("requests_seen"),
                "agent_rc": a.get("agent_rc"),
                "agent_timed_out": a.get("agent_timed_out"),
                "agent_wall_s": a.get("agent_wall_s"),
                "feedback_delivery": a.get("feedback_delivery"),
                "feedback_in_prompt_bytes": a.get("feedback_in_prompt_bytes"),
                "feedback_sha256": (a.get("feedback") or {}).get("sha256"),
                "ws_end_sha256": a.get("ws_end_sha256"),
            } for a in attempts],
        }
        idx = run_dir / f"wire_{arm}" / "index.jsonl"
        out["wire_upstreams"] = sorted({
            json.loads(s)["upstream"].rsplit("/v1", 1)[0]
            for s in idx.read_text(encoding="utf-8").splitlines() if s.strip()
        }) if idx.exists() else []
        # **M7_file／M7_name 是 r535 的原件**（位元組比對，與 wire 協定無關）。
        out.update(R5.measure_m7_file(run_dir, arm_name, summary, slices,
                                      slice_meta))
        out.update(R5.measure_m7_name(run_dir, arm_name, summary, slices,
                                      slice_meta))
        # **M7_ws 是本檔的擴充版**（多認 Anthropic 形狀），分類仍是 r535 的。
        out.update(measure_m7_ws_any(run_dir, summary, slices, slice_meta,
                                     tools_path=cell / "tools.jsonl"))
        out.update(measure_effort(run_dir, arm, self.shim_log, t_lo, t_hi,
                                  value=self.a.effort))
        out.update(R5.measure_suspect_timeout(run_dir, arm))
        out["agent_timed_out_n"] = sum(
            1 for a in attempts if a.get("agent_timed_out"))
        if not out.get("requests_seen"):
            out["not_mediated"] = True
        return out

    @staticmethod
    def row_of(state: dict) -> dict:
        keys = ("cell", "agent", "task_id", "arm", "cell_status", "accepted",
                "stop_reason", "attempts_used", "requests_seen",
                "upstreams_defaulted",
                "m7_name", "m7_name_reason", "m7_file", "m7_file_reason",
                "m7_ws", "m7_ws_ratio", "m7_ws_reason",
                "m7_ws_solution", "m7_ws_solution_ratio",
                "effort_verdict", "rt_nonzero", "rt_zero", "rt_unmeasured",
                "shim_model_calls", "shim_injected",
                "agent_timed_out_n", "suspect_timeout", "infra_void",
                "wall_s", "run_complete")
        return {"ts": R5.now_iso(), **{k: state.get(k) for k in keys}}

    @staticmethod
    def write_cell(cell: pathlib.Path, state: dict) -> None:
        tmp = cell / "cell.json.tmp"
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(cell / "cell.json")

    @staticmethod
    def cell_done(cell: pathlib.Path) -> bool:
        p = cell / "cell.json"
        if not p.exists():
            return False
        try:
            return bool(json.loads(p.read_text(encoding="utf-8")
                                   ).get("run_complete"))
        except Exception:                    # noqa: BLE001
            return False

    # -- 整條流 -----------------------------------------------------------
    def run(self, rows: list[dict]) -> int:
        self.out.mkdir(parents=True, exist_ok=True)
        self.cells_dir.mkdir(parents=True, exist_ok=True)
        self.shim = SHIM.EffortShim(upstream=self.upstream,
                                    log_path=self.shim_log,
                                    value=self.a.effort).start()
        self.ev("stream_start", n=len(rows), shim=self.shim.url,
                upstream=self.upstream, not_a_test=NOT_A_TEST)
        try:
            for row in rows:
                self.run_cell(row)
        finally:
            self.ev("stream_end", shim_stats=self.shim.stats)
            self.shim.stop()
        return 0


# ── 量具自檢（負控制在前）────────────────────────────────────────────────

_SELFTEST_ANTHROPIC_REQ = json.dumps({
    "model": "gemma-4-12b-it-qat",
    "messages": [
        {"role": "user", "content": [{"type": "text", "text": "do it"}]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_1", "name": "Bash",
             "input": {"command": "ls -la"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": "solution.py\nTASK.md\nVACANT_FEEDBACK.md"}]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_2", "name": "Read",
             "input": {"file_path": "/ws/solution.py"}}]},
    ]}, ensure_ascii=False).encode("utf-8")

_SELFTEST_ANTHROPIC_RESP = (
    b'event: content_block_start\n'
    b'data: {"type":"content_block_start","index":0,'
    b'"content_block":{"type":"tool_use","id":"tu_3","name":"Write",'
    b'"input":{}}}\n\n'
    b'event: content_block_delta\n'
    b'data: {"type":"content_block_delta","index":0,'
    b'"delta":{"type":"input_json_delta",'
    b'"partial_json":"{\\"file_path\\":\\"solution.py\\"}"}}\n\n'
)

_SELFTEST_ANTHROPIC_UNPARSABLE = json.dumps({
    "model": "m",
    "messages": [{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "…"}]}],
}, ensure_ascii=False).encode("utf-8")


def selftest(verbose: bool = True) -> dict:
    """**認不出來就要紅。** 兩種 wire 形狀各驗一輪，外加兩條負控制。

    為什麼要有這一支：`M7_ws = 0` 有兩個成因——agent 真的只 read／write，
    或者**解析器不認得這個框架的形狀**。兩者在輸出上同形（都是空陣列），
    而後者會把「量具壞了」報成「機制沒被觸發」。Stage C 多了一個
    Anthropic wire 的 agent，所以這一條在本輪是承重的。
    """
    rows: list[dict] = []

    def chk(name: str, ok: bool, got=None) -> None:
        rows.append({"case": name, "pass": bool(ok), "got": got})
        if verbose:
            print(f"  [{'OK ' if ok else 'RED'}] {name}"
                  + (f"  got={got}" if got is not None else ""))

    # ① r535 的 OpenAI 形狀仍然認得（本檔沒有把它弄壞）
    oa = R5._selftest_wire_openai()
    calls, ev = _tool_calls_any(oa)
    names = [c["name"] for c in (calls or [])]
    chk("openai 形狀撈得到工具呼叫", bool(calls) and ev.get("shape") == "openai",
        names)

    # ② Anthropic 形狀撈得到，而且 `reads_own_solution` 認得出來
    calls, ev = _tool_calls_any(_SELFTEST_ANTHROPIC_REQ)
    names = [c["name"] for c in (calls or [])]
    chk("anthropic 形狀撈得到工具呼叫",
        bool(calls) and ev.get("shape") == "anthropic" and len(calls) == 2,
        names)
    sol = [c for c in (calls or [])
           if R5.reads_own_solution(c["name"], c["args"])]
    chk("anthropic：讀自己的 solution.py 認得出來", len(sol) == 1,
        [c["name"] for c in sol])
    kinds = sorted({R5.classify_call(c["name"], c["args"])
                    for c in (calls or [])})
    chk("anthropic：分類用的是 r535 那一份（ls ⇒ other）", "other" in kinds,
        kinds)

    # ③ Anthropic SSE 的最後一通工具呼叫撈得到
    extra = _tool_calls_from_response_any(_SELFTEST_ANTHROPIC_RESP)
    chk("anthropic SSE 撈得到最後一通工具呼叫",
        len(extra) == 1 and extra[0]["name"] == "Write",
        [e["name"] for e in extra])

    # ④ 負控制：看得見工具痕跡卻撈不到呼叫 ⇒ unparsable（不是 0）
    calls, ev = _tool_calls_any(_SELFTEST_ANTHROPIC_UNPARSABLE)
    chk("負控制：有痕跡撈不到 ⇒ unparsable 不是空陣列",
        calls == [] and ev.get("unparsable") is True, ev.get("unparsable"))

    # ⑤ 負控制：body 不是 JSON ⇒ None（不是空陣列）
    calls, ev = _tool_calls_any(b"<<not json>>")
    chk("負控制：body 不是 JSON ⇒ None", calls is None, calls)

    # ⑥ 沒有工具痕跡的 body ⇒ 空陣列且不是 unparsable
    calls, ev = _tool_calls_any(R5._selftest_wire_no_tools())
    chk("沒有工具痕跡 ⇒ 空陣列、不是 unparsable",
        calls == [] and not ev.get("unparsable"), ev.get("unparsable"))

    # ⑦ shim 的五條
    sh = SHIM.selftest(verbose=False)
    chk("effort_shim selftest 五條全綠", sh["ok"],
        [r["case"] for r in sh["rows"] if not r["pass"]])

    ok = all(r["pass"] for r in rows)
    return {"ok": ok, "rows": rows}


# ── 報表 ────────────────────────────────────────────────────────────────

def _frac(sel: list[dict], key: str) -> dict:
    t = sum(1 for r in sel if r.get(key) is True)
    f = sum(1 for r in sel if r.get(key) is False)
    n = sum(1 for r in sel if r.get(key) is None)
    return {"true": t, "false": f, "null": n, "denom": t + f,
            "pct": (round(100.0 * t / (t + f), 1) if (t + f) else None)}


def report(out: pathlib.Path) -> dict:
    cells = []
    for p in sorted((out / "cells").glob("*/cell.json")):
        try:
            cells.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:                    # noqa: BLE001
            continue

    done = [c for c in cells if c.get("run_complete")]
    doc: dict = {"not_a_test": NOT_A_TEST,
                 "by_agent_is_arm_merged": BY_AGENT_IS_ARM_MERGED,
                 "generated": R5.now_iso(),
                 "n_cells_seen": len(cells), "n_run_complete": len(done),
                 "by_agent": {}, "by_agent_arm": {}, "cells": []}
    for agent in AGENTS:
        sel = [c for c in done if c.get("agent") == agent]
        measured = [c for c in sel if c.get("cell_status") == "measured"]
        doc["by_agent"][agent] = {
            "n": len(sel), "n_measured": len(measured),
            "n_infra_void": sum(1 for c in sel
                                if c.get("cell_status") == "infra_void"),
            "n_invalid_effort": sum(1 for c in sel
                                    if c.get("cell_status") == "invalid_effort"),
            "M7_name": _frac(measured, "m7_name"),
            "M7_file": _frac(measured, "m7_file"),
            "M7_ws": _frac(measured, "m7_ws"),
            "M7_ws_solution": _frac(measured, "m7_ws_solution"),
            "accepted": _frac(measured, "accepted"),
            "requests_seen_zero": sum(1 for c in sel
                                      if not c.get("requests_seen")),
            "upstreams_defaulted_nonempty": sum(
                1 for c in sel if c.get("upstreams_defaulted")),
            "rt_nonzero_cells": sum(1 for c in sel if c.get("rt_nonzero")),
            "rt_unmeasured_cells": sum(1 for c in sel
                                       if c.get("rt_unmeasured")),
        }
        for arm in STAGEC_ARMS:
            s2 = [c for c in measured if c.get("arm") == arm]
            doc["by_agent_arm"][f"{agent}/{arm}"] = {
                "n": len(s2),
                "M7_name": _frac(s2, "m7_name"),
                "M7_file": _frac(s2, "m7_file"),
                "M7_ws": _frac(s2, "m7_ws"),
                "M7_ws_solution": _frac(s2, "m7_ws_solution"),
                "accepted": _frac(s2, "accepted"),
                "attempts_used": sorted(
                    {c.get("attempts_used") for c in s2}),
            }
    for c in sorted(done, key=lambda r: (r.get("agent") or "",
                                         r.get("task_id") or "",
                                         r.get("arm") or "")):
        doc["cells"].append(StageCDriver.row_of(c))
    return doc


def rescan(out: pathlib.Path) -> dict:
    """**從落盤的 wire 重算 M7 三層，跟 `cell.json` 記的那一份逐格比。**

    這一支存在的理由是「可被外部驗證」：拿到歸檔的人不必相信 `cell.json` 裡的
    布林值，可以自己從 `wire_RUN-ON/*.req.bin` 重算一次。**對不上就是紅的**
    ——不管是我們當初寫錯，還是事後有人動過檔案。

    ⚠ 它**驗不動**模型那一端：同一顆模型再跑一次不會逐字相同。
    它驗的是「這一份 wire 支不支持這一份數字」。
    """
    res: dict = {"generated": R5.now_iso(), "n": 0, "ok": 0,
                 "mismatch": [], "unreadable": []}
    for p in sorted((out / "cells").glob("*/cell.json")):
        cell = p.parent
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:             # noqa: BLE001
            res["unreadable"].append({"cell": cell.name, "why": repr(exc)})
            continue
        sp = cell / "run" / "run_RUN-ON.json"
        if not sp.exists():
            res["unreadable"].append({"cell": cell.name,
                                      "why": "run_RUN-ON.json 不存在"})
            continue
        summary = json.loads(sp.read_text(encoding="utf-8"))
        attempts = summary.get("attempts") or []
        slices, meta = R5.wire_slices(cell / "run", summary["arm"], attempts)
        got: dict = {}
        got.update(R5.measure_m7_file(cell / "run", rec["arm"], summary,
                                      slices, meta))
        got.update(R5.measure_m7_name(cell / "run", rec["arm"], summary,
                                      slices, meta))
        got.update(measure_m7_ws_any(cell / "run", summary, slices, meta))
        res["n"] += 1
        diff = {k: {"recorded": rec.get(k), "rescan": got.get(k)}
                for k in ("m7_name", "m7_file", "m7_ws", "m7_ws_solution")
                if rec.get(k) != got.get(k)}
        if diff:
            res["mismatch"].append({"cell": cell.name, **diff})
        else:
            res["ok"] += 1
    res["verdict"] = ("OK" if res["n"] and not res["mismatch"]
                      and not res["unreadable"] else "MISMATCH")
    return res


def print_report(doc: dict) -> None:
    print("=" * 74)
    print("Stage C（R535 L-6）——「檔案從不被讀」是不是 pi 專屬")
    print("⚠ " + NOT_A_TEST)
    print("=" * 74)
    print(f"run_complete {doc['n_run_complete']} / 見到 {doc['n_cells_seen']} 格")
    print("-" * 74)
    print("以下這張 by_agent 表 " + BY_AGENT_IS_ARM_MERGED)
    print("-" * 74)
    hdr = f"{'agent':<10}{'n':>4}{'meas':>6}{'void':>6}" \
          f"{'M7_name':>12}{'M7_file':>12}{'M7_ws':>12}{'M7_ws_sol':>12}"
    print(hdr)
    for agent, d in doc["by_agent"].items():
        def cell(k):
            v = d[k]
            return f"{v['true']}/{v['denom']}" + (
                f"({v['pct']}%)" if v["pct"] is not None else "")
        print(f"{agent:<10}{d['n']:>4}{d['n_measured']:>6}"
              f"{d['n_infra_void']:>6}"
              f"{cell('M7_name'):>12}{cell('M7_file'):>12}"
              f"{cell('M7_ws'):>12}{cell('M7_ws_solution'):>12}")
    print("-" * 74)
    print("↓ **判讀看這一張**（逐臂）。RP 的 M7_file 必為 1、M7_name 必為 0。")
    for key, d in doc["by_agent_arm"].items():
        def cell(k):
            v = d[k]
            return f"{v['true']}/{v['denom']}"
        print(f"{key:<18} n={d['n']:<3} "
              f"M7_name={cell('M7_name'):<7} M7_file={cell('M7_file'):<7} "
              f"M7_ws={cell('M7_ws'):<7} M7_ws_sol={cell('M7_ws_solution'):<7} "
              f"accepted={cell('accepted')}")
    print("=" * 74)


# ── CLI ─────────────────────────────────────────────────────────────────

def agent_versions(node_bin: str) -> dict:
    env = dict(os.environ)
    if node_bin:
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    out = {}
    for name, spec in AGENTS.items():
        try:
            p = subprocess.run(spec["version_cmd"], capture_output=True,
                               text=True, timeout=60, env=env)
            out[name] = (p.stdout or p.stderr or "").strip().splitlines()[-1] \
                if (p.stdout or p.stderr).strip() else ""
        except Exception as exc:             # noqa: BLE001
            out[name] = f"<{exc!r}>"
    return out


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Stage C（R535 L-6，選配、不進預註冊）驅動。")
    ap.add_argument("--out", default=None, help="落盤目錄")
    ap.add_argument("--bank-manifest",
                    default=str(HERE.parent / "r535" / "bank_manifest.json"))
    ap.add_argument("--expect-manifest-sha256",
                    default=R5.EXPECTED_MANIFEST_SHA256)
    ap.add_argument("--endpoint", default=os.environ.get("VACANT_GAIN_API", ""),
                    help="完整的 /v1/chat/completions（同 R535）")
    ap.add_argument("--model", default="gemma-4-12b-it-qat")
    ap.add_argument("--effort", default="none",
                    help="要注入的 reasoning_effort（Stage C ＝ none）")
    ap.add_argument("--sandbox", default="none")
    ap.add_argument("--test-timeout", type=float, default=30.0)
    ap.add_argument("--agent-timeout", type=float, default=600.0)
    ap.add_argument("--node-bin",
                    default="/home/user1/.local/opt/node-v22.23.2-linux-x64/bin",
                    help="node／opencode／claude 的 bin 目錄（要進 PATH）")
    ap.add_argument("--stream", default="c0")
    ap.add_argument("--shard", default=None, help="i:n")
    ap.add_argument("--agents", default=",".join(AGENTS))
    ap.add_argument("--arms", default=",".join(STAGEC_ARMS))
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="只跑量具自檢（負控制在前），不碰端點")
    ap.add_argument("--write-plan", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--rescan", action="store_true",
                    help="從落盤的 wire 重算 M7 三層，跟 cell.json 逐格比")
    return ap


def select(rows: list[dict], args) -> list[dict]:
    agents = {s.strip() for s in args.agents.split(",") if s.strip()}
    arms = {s.strip() for s in args.arms.split(",") if s.strip()}
    bad = arms - set(STAGEC_ARMS)
    if bad:
        raise SystemExit(f"Stage C 只有 {list(STAGEC_ARMS)}，收到 {sorted(bad)}")
    bad = agents - set(AGENTS)
    if bad:
        raise SystemExit(f"不認識的 agent {sorted(bad)}，只有 {list(AGENTS)}")
    sel = [r for r in rows if r["agent"] in agents and r["arm"] in arms]
    if args.tasks:
        want = {s.strip() for s in args.tasks.split(",") if s.strip()}
        sel = [r for r in sel if r["task_id"] in want]
    if args.shard:
        i, n = (int(x) for x in args.shard.split(":"))
        sel = [r for r in sel if r["plan_index"] % n == i]
    if args.limit:
        sel = sel[: args.limit]
    return sel


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.selftest:
        r = selftest()
        print("selftest:", "OK" if r["ok"] else "RED")
        return 0 if r["ok"] else 1
    if not args.out:
        raise SystemExit("--out 是必填")
    out = pathlib.Path(args.out).resolve()
    if args.rescan:
        doc = rescan(out)
        (out / "rescan.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in doc.items() if k != "mismatch"},
                         ensure_ascii=False, indent=2))
        if doc["mismatch"]:
            print(json.dumps(doc["mismatch"][:10], ensure_ascii=False,
                             indent=2))
        return 0 if doc["verdict"] == "OK" else 1
    if args.report:
        doc = report(out)
        (out / "report.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print_report(doc)
        return 0

    manifest, msha = R5.load_manifest(pathlib.Path(args.bank_manifest),
                                      expect_sha=args.expect_manifest_sha256)
    rows = plan_rows(manifest)
    if args.write_plan:
        out.mkdir(parents=True, exist_ok=True)
        doc = {"generated": R5.now_iso(), "not_a_test": NOT_A_TEST,
               "bank_manifest_sha256": msha, "n_cells": len(rows),
               "agents": {k: v for k, v in AGENTS.items()},
               "arms": {a: R5.ARMS[a]["flags"] for a in STAGEC_ARMS},
               "prompt": R5.PI_PROMPT, "rows": rows}
        doc["plan_sha256"] = R5.sha256_bytes(
            json.dumps(rows, ensure_ascii=False, sort_keys=True).encode())
        (out / "plan.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"n_cells": doc["n_cells"],
                          "plan_sha256": doc["plan_sha256"],
                          "bank_manifest_sha256": msha},
                         ensure_ascii=False, indent=2))
        return 0

    st = selftest(verbose=False)
    if not st["ok"]:
        raise SystemExit("量具自檢紅了，不准發射："
                         + json.dumps([r for r in st["rows"]
                                       if not r["pass"]], ensure_ascii=False))
    if not args.endpoint:
        raise SystemExit("--endpoint（或 VACANT_GAIN_API）是必填")
    args.versions = agent_versions(args.node_bin)
    for name, spec in AGENTS.items():
        got = args.versions.get(name, "")
        if spec["expect_version"] not in got:
            raise SystemExit(
                f"{name} 版本對不上：期望含 {spec['expect_version']}，"
                f"實際 {got!r}。停（版本是這一節結論的一部分）。")
    sel = select(rows, args)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stagec_meta.json").write_text(json.dumps({
        "generated": R5.now_iso(), "not_a_test": NOT_A_TEST,
        "prereg": "decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md L-6",
        "bank_manifest_sha256": msha, "model": args.model,
        "endpoint": args.endpoint, "effort_injected": args.effort,
        "agents": args.versions, "arms": {a: R5.ARMS[a]["flags"]
                                          for a in STAGEC_ARMS},
        "prompt": R5.PI_PROMPT,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    drv = StageCDriver(args, manifest, msha)
    return drv.run(sel)


if __name__ == "__main__":
    raise SystemExit(main())
