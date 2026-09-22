"""agentwrap —— 在 `vacant run` **裡面**把 agent 接到中介上（產品路徑）。

這支在架構裡承重什麼：`vacant run -- pi` **單獨不會生效**。pi 不吃
`OPENAI_BASE_URL`（2026-09-18 實測：假上游 0 通，它跑去 `api.openai.com`
拿了一個 401），要把 base url 寫進它自己的設定檔才行。那段接線一直只活在
`ops/vacantrun/wrap_agent.sh`——一支**凍結的實驗腳本**，而且只做 `pi -p`。

本檔把同一段接線搬進產品，並補上**互動模式**（使用者真的「打開 pi」那一幕）。

    vacant on                    ← 使用者敲這個
      └─ vacant run --stdin inherit -- python -m …agentwrap pi
           └─（proxy 起來了，VACANT_RUN_PROXY 有值）
              ├─ 建一個**這一跑自己的**設定目錄
              ├─ 寫 models.json：baseUrl → proxy
              └─ exec pi --provider vacantproxy --model m   （互動 TUI）

## 為什麼設定寫在暫存目錄而不是 `~/.pi/`

**不碰使用者的檔案。** `~/.pi/agent/` 底下有 `auth.json`；而且
`possess.wire_pi` 的 docstring 自己記著：同目錄還有一份 `models-store.json`，
**哪一份才是 pi 0.85.1 真正讀的那一份沒有量過**。relocate 那條路
（`PI_CODING_AGENT_DIR`）是**量到過的**那一條（600 格 abpi ＋ pi_tty 兩批），
所以產品走它。

⚠ 這也是 `vacant on`（本檔）與 `vacant install`（`possess.py`）的分野：
  前者只在這一跑之內生效、關掉就沒了；後者改使用者的常駐設定。
  兩者的證據等級**不一樣**，不要混講。

## 互動模式的三個條件（缺一就安靜落回 print）

`DECISION_20260920_PI_TTY_VS_PRINT_MODE.md` 量出來的：

1. stdin 是 tty  ⇒ launcher 要 `--stdin inherit`
2. stdout 是 tty ⇒ **不可以給 `--json`**
3. 真的有一張 pty

三個條件缺一，pi 就落回 print **而且不會報錯**。所以 `vacant on` 這條路
在 `cli` 那一端把 1、2 釘死，3 靠使用者本來就在終端機裡。

## 誠實邊界（改碼請保留）

1. **`VACANT_RUN_PROXY` 沒有值就拒跑**，不要「那就直連吧」——那會變成
   一個看起來有 Vacant、實際沒中介的 session，正是本專案最忌的失敗方式。
2. 本檔**不宣稱**中介成立。成立與否看 `run_*.json` 的 `requests_seen`
   與 wire index，那是 launcher 的事。這裡只負責把線接上。
3. `pi` 這一格的**常駐**通道（`vacant install`）至今沒有被 `requests_seen`
   證實過；本檔走的是 relocate 那條**量過**的路。兩件事不要互相背書。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile
from typing import Any

#: 我們寫進 agent 設定裡的 provider 名字。**要看得出是誰接的**——
#: pi 的 TUI 狀態列會把它顯示出來（`(vacantproxy) <model>`），
#: 那一行是現場唯一「肉眼看得到自己被中介」的訊號。
PROVIDER_ID = "vacantproxy"

#: 預設模型。展場與實驗都用這個；`VACANT_AGENT_MODEL` 蓋得過。
DEFAULT_MODEL = "gemma-4-12b-it-qat"

#: 本檔接得動的 agent。與 `envmap.CONFIG_ROUTE` 同一份名單——
#: 那裡記著每一個的 relocate 變數、設定檔名與**實測日期**。
SUPPORTED: tuple[str, ...] = ("pi", "codex", "opencode", "claude")


class WireError(RuntimeError):
    """接線失敗。**往上丟，不要吞**——吞掉就變成沒中介的 session。"""


def _proxy_base() -> str:
    """這一跑的 proxy 位址。**沒有就拒跑。**"""
    base = (os.environ.get("VACANT_RUN_PROXY") or "").strip().rstrip("/")
    if not base:
        raise WireError(
            "VACANT_RUN_PROXY 沒有值 ⇒ 拒跑。\n"
            "  本檔只在 `vacant run` 裡面有意義（proxy 由它起）。\n"
            "  🔴 **刻意不退回直連**：那會給你一個看起來有 Vacant、\n"
            "     實際上每一通都沒被中介的 session。")
    return base


def wire_pi(cfg: pathlib.Path, base: str, model: str) -> list[str]:
    """寫 `models.json`，回互動模式的 argv。

    形狀與 `possess.wire_pi` 一致（同一個 provider id、同一組 compat 旗標），
    差別只在寫到**這一跑自己的目錄**而不是 `~/.pi/agent/`。
    """
    doc = {"providers": {PROVIDER_ID: {
        "baseUrl": f"{base}/v1",
        "api": "openai-completions",
        # 上游若要金鑰，`sentinel=""` 讓 Authorization 原樣穿透，
        # proxyd 永不持有它（`wireproxy.py` 的規格，改碼要保住）。
        "apiKey": os.environ.get("OPENAI_API_KEY", "sk-vacant-run"),
        "compat": {"supportsDeveloperRole": False,
                   "supportsReasoningEffort": False},
        "models": [{"id": model, "name": "m",
                    "contextWindow": 262144, "maxTokens": 16384}],
    }}}
    (cfg / "models.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", "utf-8")
    os.environ["PI_CODING_AGENT_DIR"] = str(cfg)
    # 離線／不要在展場連外查版本／不要送遙測。
    os.environ.setdefault("PI_OFFLINE", "1")
    os.environ.setdefault("PI_SKIP_VERSION_CHECK", "1")
    os.environ.setdefault("PI_TELEMETRY", "0")
    # ⚠ **沒有 `-p`**：那正是互動與 print 的唯一差別（讀碼確認）。
    return ["pi", "--provider", PROVIDER_ID, "--model", "m"]


def wire_codex(cfg: pathlib.Path, base: str, model: str) -> list[str]:
    """`CODEX_HOME/config.toml`。

    ⚠ `wire_api` 必須是 `"responses"`——0.147.0 **不收 `"chat"`**；
      而且內建 id `openai` **不准覆寫**（會 fail-closed 報錯），所以用新 id。
    """
    (cfg / "config.toml").write_text(
        f'model = "{model}"\n'
        f'model_provider = "{PROVIDER_ID}"\n\n'
        f'[model_providers.{PROVIDER_ID}]\n'
        f'name = "{PROVIDER_ID}"\n'
        f'base_url = "{base}/v1"\n'
        f'wire_api = "responses"\n', "utf-8")
    os.environ["CODEX_HOME"] = str(cfg)
    return ["codex"]


def wire_opencode(cfg: pathlib.Path, base: str, model: str) -> list[str]:
    """OpenCode 走 `OPENCODE_CONFIG_CONTENT`（**沒有檔案**，整份塞環境變數）。

    ⚠ 2026-09-18 的教訓：它的 binary 裡 grep 不到 `OPENAI_BASE_URL`，
      照字串判會寫「不吃環境變數」——**實測它吃**（讀變數的是 runtime 才
      載入的 `@ai-sdk/openai`）。**掃 binary 不算量。**
    """
    os.environ["OPENCODE_CONFIG_CONTENT"] = json.dumps({
        "provider": {PROVIDER_ID: {
            "npm": "@ai-sdk/openai-compatible",
            "options": {"baseURL": f"{base}/v1",
                        "apiKey": os.environ.get("OPENAI_API_KEY",
                                                 "sk-vacant-run")},
            "models": {model: {"name": model}},
        }},
        # 🔴 **這裡跟 `possess.wire_opencode` 刻意不一樣。**
        #    那一支不動頂層 `model`，理由是「那是使用者選的模型，
        #    換掉它等於替人做決定」——對**常駐**附身而言是對的。
        #    但 `vacant on` 是使用者**這一次明確要求**在 Vacant 底下開，
        #    不指定的話 opencode 會用它自己存的預設（實測落到
        #    `gpt-5.6-terra-pro`，然後 `Error: Required`）
        #    ⇒ 那條路沒有被我們改道，等於白開一次。
        "model": f"{PROVIDER_ID}/{model}",
    }, ensure_ascii=False)
    return ["opencode"]


def wire_claude(cfg: pathlib.Path, base: str, model: str) -> list[str]:
    """Claude Code 走 `ANTHROPIC_BASE_URL`（**環境變數，不必寫檔**）。

    ⚠ **這一格未驗證。** `possess.wire_claude` 是把它寫進
      `~/.claude/settings.json` 的 `env` 區塊；本檔改成直接設環境變數，
      而「claude 認不認環境變數」**沒有量過**。
      ⇒ 判準一樣：跑完看 `run_*.json` 的 `requests_seen`。是 0 就是沒接上，
        不要因為「我設了變數」就當它成立——pi 那一格就是這樣被打臉的
        （設了 `OPENAI_BASE_URL`，假上游 0 通）。
    ⚠ **不碰 `ANTHROPIC_API_KEY`**（憑證紅線）。
    """
    os.environ["ANTHROPIC_BASE_URL"] = base
    return ["claude"]


_WIRE = {"pi": wire_pi, "codex": wire_codex, "opencode": wire_opencode,
         "claude": wire_claude}

#: 這一格的通道**被 `requests_seen` 證實過**沒有。`None` ＝沒量過，不是壞掉。
#: 選單會把它顯示出來——使用者有權知道自己選的那一條驗到什麼程度。
CHANNEL_MEASURED: dict[str, str | None] = {
    "pi": "2026-09-18 假上游 ＋ 600 格 abpi ＋ pi_tty（print 與互動都量過）",
    "codex": "2026-09-19 真模型 0.147.0（假上游 0.153.2）",
    "opencode": "2026-09-19 真模型（假上游 2026-09-18）",
    "claude": None,
}


#: 一次性叫法。⚠ **實測出來的，不要照直覺改**——每一家的形狀都不同，
#: 而猜錯的失敗方式是「agent 把 prompt 當成路徑」這種看起來像別的問題的錯。
_ONESHOT: dict[str, Any] = {
    "pi": lambda q: ["-p", q],
    "opencode": lambda q: ["run", q],
    "codex": lambda q: ["exec", q],
    "claude": lambda q: ["-p", q],
}


def build(agent: str, cfg: pathlib.Path, *, model: str | None = None,
          prompt: str | None = None) -> list[str]:
    """接線 ＋ 回要 exec 的 argv。`prompt` 有值 ⇒ 一次性模式。"""
    if agent not in _WIRE:
        raise WireError(f"不認得的 agent：{agent!r}（接得動的：{', '.join(SUPPORTED)}）")
    if shutil.which(agent) is None:
        raise WireError(
            f"{agent} 不在 PATH 上。\n"
            f"  ⚠ 「設定目錄在、PATH 上沒有」是實測過的形狀"
            f"（possess 為此誤判過兩次）——先確認 `command -v {agent}`。")
    cfg.mkdir(parents=True, exist_ok=True)
    argv = _WIRE[agent](cfg, _proxy_base(), model or
                        os.environ.get("VACANT_AGENT_MODEL", DEFAULT_MODEL))
    if prompt is not None:
        # 一次性模式的叫法**每一家都不一樣**，猜會出事：
        #   · pi        `-p <prompt>`（不給 `< /dev/null` 會永久卡住，V0 已知；
        #               那是 launcher 的 `--stdin devnull` 在管，不是這裡）
        #   · opencode  `run <message>` —— **裸參數會被當成專案目錄**
        #               （實測：`Failed to change directory to …說一句話就好`）
        #   · codex     `exec <prompt>`（非互動子命令）
        #   · claude    `-p <prompt>`
        argv += _ONESHOT[agent](prompt)
    return argv


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    agent, rest = a[0], a[1:]
    prompt = rest[0] if rest else None
    cfg = pathlib.Path(os.environ.get("VACANT_AGENT_CFG")
                       or tempfile.mkdtemp(prefix=f"vacant-{agent}-"))
    try:
        cmd = build(agent, cfg, prompt=prompt)
    except WireError as e:
        sys.stderr.write(f"🔴 {e}\n")
        return 2
    sys.stderr.write(f"[vacant] {agent} → {os.environ['VACANT_RUN_PROXY']}"
                     f"（設定在 {cfg}，不碰你的 ~/.{agent}）\n")
    os.execvp(cmd[0], cmd)   # noqa: S606 —— 取代本行程，退出碼直接是 agent 的


if __name__ == "__main__":   # pragma: no cover
    raise SystemExit(main())
