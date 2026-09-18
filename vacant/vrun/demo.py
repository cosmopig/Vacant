#!/usr/bin/env python3
"""這支在架構裡承重什麼：`vacant demo gate` ——裝完之後看到的**第一幕**。

## 為什麼要有這一支

README 原本的 30 秒 quickstart 是**函式庫示範**（`run_python_check` 回 True／False、
`verify_chain` 回 True）。那個畫面回答不了使用者真正的問題：
**「我的 agent 接上 Vacant 之後，有什麼不一樣？」**

V0 實測（vacant-dev，pi 0.85.1 打 gemma-4-12b）已經跑出那一幕：

    pi: "Done. I have created solution.py…"      ← agent 宣告完成
    → 閘門跑 → ImportError: cannot import name 'mul'
    → exit 20，收據 accepted=false

**agent 說它做完了，客戶的驗收說沒有。** 這一支把那一幕做成零設定、零模型、
零網路、30 秒跑得完的版本，讓任何人在自己的機器上當場看到它發生。

## 不准是假演出

畫面上每一個數字都是**當場真的跑出來的**：

  · 假 agent 是一支真的子行程（`AGENT_SRC`），真的寫出一份 `solution.py`，
    真的以退出碼 0 結束（它自己認為成功了）；
  · 閘門是 `vacant/vrun/acceptance.py` 那一支（R530 實驗用的也是它，
    `ops/gain/r530/acceptance.py` 現在 re-export 到這裡），不是另寫的第二把尺；
  · `ImportError: cannot import name 'mul'` 是驗收 driver 真的抓到的例外原文，
    不是字串常數（本檔沒有任何地方寫著那句話）；
  · 退出碼 20 是 `vacant run` 這個**真的子行程**的 `returncode`；
  · 收據是真的 Ed25519 簽章鏈，當場用**既有的**驗章器驗一次給你看
    （`vacant/vrun/verify_receipts.py`；`ops/gain/replay/verify_run_receipts.py`
    是同一支的 re-export，R460R／R529 的鏈用的就是它）。

`_assert_not_a_performance()` 是這一條的可執行防呆：任何一項不成立就整個
喊停並回非 0，**寧可 demo 壞掉，也不要 demo 說謊**。

## 兩跑對照的分母是「沒有 Vacant」

第一跑是**裸 agent**（不經過 `vacant run`，也不經過 proxy），因為使用者要比的
分母就是「我現在的日常」。不用 `VACANT=0` 當分母：那一臂是 Vacant 的觀測模式
（tee 落盤、不 gate），拿它當「沒有 Vacant」會把兩件事混在一起。

## 這隻假 agent 一通模型呼叫都沒有

所以 `requests_seen` 會是 0，畫面上照實印。這不是缺陷而是**離線可跑**的代價，
而且它正好帶出誠實邊界那一條：**`requests_seen` 才是「被中介了」的證據**，
「我設了環境變數」不是（`envmap` docstring 邊界 1）。

誠實邊界完整版在 `docs/VACANT_RUN.md` §4，畫面上只印與這一幕相關的三條。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap

#: `vacant` 套件安裝位置的**上一層**：repo checkout 底下＝repo 根，
#: `pip install` 之後＝site-packages。子行程的 `PYTHONPATH` 前綴用它。
#:
#: 為什麼要這一行：這一幕的全部價值是「畫面上的數字是**這份**程式碼當場跑出來的」。
#: 同一台機器上常常有第二份（worktree、editable 裝在別處、PATH 上的舊 console
#: script），子行程若去載到另一份，畫面會安靜地變成別人的結果。把本模組自己所屬的
#: 那個 `vacant` 套件的位置明寫進子行程的 `PYTHONPATH`，就沒有這個歧義。
PKG_PARENT = pathlib.Path(__file__).resolve().parents[2]

#: `vacant run` 的拒交退出碼。**從 launcher 讀**，不在這裡寫死第二份——
#: demo 的防呆拿它當判準，寫死就等於防呆在對照自己的假設。
from .launcher import EXIT_REFUSED

#: 假 agent。**它自己認為它成功了**——寫了檔、印了完成宣告、退出碼 0。
#: 錯法刻意挑「看起來對但名字不對」：`multiply` 不是客戶要的 `mul`。
#: 這正是 V0 真跑時 pi 犯的那一種錯，而且它是外行一眼看得懂的錯
#: （不是「演算法錯了」，是「交出來的東西根本接不上」）。
AGENT_SRC = '''\
"""一隻假 agent：不呼叫模型、不連網，30 行寫完就宣告完成。"""
import pathlib

pathlib.Path("solution.py").write_text(
    "def add(a, b):\\n"
    "    return a + b\\n"
    "\\n"
    "def multiply(a, b):\\n"
    "    return a * b\\n",
    encoding="utf-8")

print("Done. I have created solution.py with add() and multiply().")
print("All requirements are implemented and the code is ready to use.")
raise SystemExit(0)
'''

#: 客戶的可見驗收。**兩條，字面值，看得懂。** 這就是 README 前提句裡
#: 「需求被編譯成可執行的驗收測資」最小的樣子。
SUITE_SRC = '''\
def check_add():
    from solution import add
    assert add(2, 3) == 5


def check_mul():
    from solution import mul
    assert mul(3, 4) == 12
'''

#: 客戶交給 agent 的需求原文。放進工作區，讓「要什麼」與「驗什麼」同時看得到。
TASK_SRC = '''\
# 需求

`solution.py` 要提供兩個函式：

  · `add(a, b)`  → a + b
  · `mul(a, b)`  → a * b

驗收在 `tests_visible/`，你可以自己先跑。
'''

#: 畫面寬度。終端機窄一點也還讀得下去。
RULE = "─" * 68


def _tilde(p: pathlib.Path | str) -> str:
    """把 $HOME 收成 `~`，讓畫面上的命令短到可以直接複製。"""
    s = str(p)
    home = str(pathlib.Path.home())
    return "~" + s[len(home):] if s.startswith(home + os.sep) else s


def _shown(argv: list[str]) -> str:
    """把 argv 印成**使用者可以直接複製貼上**的一行。

    只做兩件事，都是路徑寫法的等價替換，**不改任何一個引數的語意**：
    家目錄底下的絕對路徑 → `~/…`；跑這支的直譯器 → `python3`。

    ⚠ 刻意**不**縮寫成 repo 相對路徑。搬進套件之後這一幕在兩種環境都要跑
    （repo checkout ／ `pip install` 之後的任何目錄），而「repo 相對」那種寫法
    只有在 repo 根底下貼上才跑得動——在別的地方它是一行看起來能跑的死字串。
    """
    out = []
    for a in argv:
        if a == sys.executable:
            out.append("python3")
            continue
        out.append(_tilde(a) if os.sep in a else a)
    return " ".join(out)


def _child_env() -> dict[str, str]:
    """子行程的環境：把**本套件**的位置放在 `PYTHONPATH` 最前面。"""
    env = dict(os.environ)
    old = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (str(PKG_PARENT) + (os.pathsep + old if old else ""))
    return env


def scaffold(root: pathlib.Path) -> dict[str, pathlib.Path]:
    """把這一幕需要的四樣東西寫到 `root` 底下。整個目錄我們自己擁有，先清空。"""
    if root.exists():
        shutil.rmtree(root)
    paths = {
        "root": root,
        "agent": root / "demo_agent.py",
        "suite": root / "tests_visible",
        "ws_plain": root / "ws_plain",
        "ws_vacant": root / "ws_vacant",
        # run 目錄**不可以在工作區底下**（launcher 會擋）：收據自己在長大，
        # 放在工作區裡會讓 ws_end_sha256 變成「收據寫了多少」的函數。
        "run": root / "receipts",
    }
    paths["suite"].mkdir(parents=True)
    (paths["suite"] / "test_visible.py").write_text(SUITE_SRC, encoding="utf-8")
    paths["agent"].write_text(AGENT_SRC, encoding="utf-8")
    for key in ("ws_plain", "ws_vacant"):
        paths[key].mkdir(parents=True)
        (paths[key] / "TASK.md").write_text(TASK_SRC, encoding="utf-8")
        shutil.copytree(paths["suite"], paths[key] / "tests_visible")
    return paths


def _vacant_cmd() -> list[str]:
    """**刻意用模組形式而不是 PATH 上的 `vacant`。**

    兩者是同一支（`pyproject` 的 `vacant = "vacant.cli:main"`），但 PATH 上那個
    console script 綁的是「安裝時」的那個 checkout。同一台機器上有第二份
    checkout（worktree、editable 裝在別處）時，它會安靜地跑到另一份程式碼去，
    而 demo 的全部價值就是**畫面上的數字是這份程式碼當場跑出來的**。
    `-m` ＋ `PYTHONPATH=PKG_PARENT`（`_child_env`）讓子行程載到的就是本模組
    所屬的那個 `vacant`，沒有這個歧義。
    畫面上會另外註明它等同使用者會打的 `vacant run`。
    """
    return [sys.executable, "-m", "vacant.cli"]


def _assert_not_a_performance(plain: subprocess.CompletedProcess,
                              gated: subprocess.CompletedProcess,
                              summary: dict, chain: list[dict],
                              verified: dict,
                              selftest: subprocess.CompletedProcess,
                              verify: subprocess.CompletedProcess) -> None:
    """可執行防呆：這一幕的每一個宣稱都必須是當場跑出來的。

    任何一條不成立 ⇒ `SystemExit`。**寧可 demo 壞掉，也不要 demo 說謊**
    （鐵律 5 的展場版本：demo 只能說看得到的，不能演）。
    """
    bad: list[str] = []
    if plain.returncode != 0:
        bad.append(f"裸 agent 應該自認成功（rc=0），實際 rc={plain.returncode}")
    if "Done." not in plain.stdout:
        bad.append("裸 agent 沒有印出完成宣告")
    if gated.returncode != EXIT_REFUSED:
        bad.append(f"閘門應該判拒交（rc={EXIT_REFUSED}），實際 rc={gated.returncode}")
    if summary.get("stop_reason") != "visible_fail":
        bad.append(f"stop_reason 應該是 visible_fail，實際 {summary.get('stop_reason')!r}")
    if summary.get("accepted") is not False or summary.get("refused") is not True:
        bad.append(f"accepted/refused 不對：{summary.get('accepted')!r}/"
                   f"{summary.get('refused')!r}")
    if not summary.get("failures"):
        bad.append("沒有失敗原文——那句 ImportError 必須是真的抓到的")
    if summary.get("visible_passed") == summary.get("visible_total"):
        bad.append("驗收應該有一條沒過")
    if not chain or chain[-1].get("type") != "ws_verdict":
        bad.append("收據鏈的最後一筆應該是 ws_verdict")
    if chain and chain[-1].get("payload", {}).get("accepted") is not False:
        bad.append("收據裡的 accepted 應該是 false")
    if verified.get("verdict") != "OK" or verified.get("failed_total"):
        bad.append(f"收據驗不過：{verified.get('verdict')!r} "
                   f"failed={verified.get('failed_total')}")
    # 負控制先過才算數：驗章器自己要抓得到壞鏈，不然「驗過了」沒有內容。
    if selftest.returncode != 0 or "PASS" not in selftest.stdout:
        bad.append(f"驗章器的負控制沒過（rc={selftest.returncode}）")
    if verify.returncode != 0:
        bad.append(f"驗章器對這張收據回非 0（rc={verify.returncode}）")
    if bad:
        raise SystemExit("demo 的前提沒成立，不演：\n  · " + "\n  · ".join(bad))


def run_demo(root: pathlib.Path, *, sandbox: str = "auto",
             quiet: bool = False) -> dict:
    """跑完整幕。回一份 summary（同時已經印在畫面上）。"""
    def say(*a):
        if not quiet:
            print(*a)

    paths = scaffold(root)
    say()
    say("vacant demo gate — 零設定、零模型端點、零 API key、零網路。")
    say("               一隻假 agent，一道真閘門，一張真收據。")
    say()
    say(f"客戶的需求　：{_tilde(paths['ws_vacant'] / 'TASK.md')}")
    say("　　　　　　　  solution.py 要有 add(a, b) 與 mul(a, b)")
    say(f"客戶的驗收　：{_tilde(paths['suite'] / 'test_visible.py')}（2 條）")
    say("　　　　　　　  check_add: add(2, 3) == 5")
    say("　　　　　　　  check_mul: mul(3, 4) == 12")
    say()

    # ── 第一跑：裸 agent。沒有 Vacant，就是使用者現在的日常。────────────
    say(RULE)
    say("[1/2] 沒有 Vacant：agent 說完成，就是完成")
    say(RULE)
    plain_argv = [sys.executable, str(paths["agent"])]
    say(f"$ cd {_tilde(paths['ws_plain'])} && python3 demo_agent.py")
    plain = subprocess.run(plain_argv, cwd=str(paths["ws_plain"]),
                           capture_output=True, text=True, timeout=120,
                           env=_child_env())
    for line in plain.stdout.splitlines():
        say("  " + line)
    say()
    say(f"  agent 退出碼　　　　：{plain.returncode}")
    say(f"  交付　　　　　　　　：出去了（{_tilde(paths['ws_plain'] / 'solution.py')}）")
    say("  誰量過　　　　　　　：沒有人")
    say("  收據　　　　　　　　：沒有")
    say()

    # ── 第二跑：同一隻 agent，包在 vacant run 裡。────────────────────────
    say(RULE)
    say("[2/2] 加上 Vacant：同一隻 agent、同一份交付，這次有人收件")
    say(RULE)
    gated_argv = _vacant_cmd() + [
        "run", "--workspace", str(paths["ws_vacant"]),
        "--suite", str(paths["suite"]), "--run-dir", str(paths["run"]),
        "--task-id", "demo-gate", "--sandbox", sandbox, "--vacant", "1",
        "--", sys.executable, str(paths["agent"])]
    say(f"$ {_shown(gated_argv)}")
    say("  （`python3 -m vacant.cli` ＝ 你會打的 `vacant`；這裡用模組形式＋"
        "明寫 PYTHONPATH，確保跑的是這一份安裝的 vacant）")
    say("  ── 以下到空行為止，是 `vacant run` 原樣印出來的 ──")
    gated = subprocess.run(gated_argv, capture_output=True, text=True,
                           timeout=600, cwd=str(paths["root"]),
                           env=_child_env())
    # stdout＝agent 自己印的；stderr＝`vacant run` 自己那一行裁決摘要。
    # 兩邊都照原樣印出來，**畫面上不重寫工具的輸出**。
    for line in gated.stdout.splitlines():
        say("  " + line)
    for line in gated.stderr.splitlines():
        say("  " + line)
    say()

    summary = json.loads((paths["run"] / "run_RUN-ON.json")
                         .read_text(encoding="utf-8"))
    chain_p = paths["run"] / "receipts_RUN-ON.ndjson"
    chain = [json.loads(l) for l in
             chain_p.read_text(encoding="utf-8").splitlines() if l.strip()]

    say(f"  agent 退出碼　　　　：{summary['agent_rc']}"
        "　　← agent 自己說它成功了")
    say(f"  客戶的驗收　　　　　：{summary['visible_passed']}/"
        f"{summary['visible_total']} 通過")
    say("  沒過的那一條（讀自 run_RUN-ON.json，與上面同一份原文）：")
    for line in str(summary["failures"]).splitlines():
        say("      " + line)
    say(f"  裁決　　　　　　　　：拒交（{summary['stop_reason']}）")
    say(f"  vacant run 退出碼　 ：{gated.returncode}"
        "　　← 退出碼反映裁決，不反映 agent 的說法")
    say()
    say(f"  工作區雜湊　　　　　：{summary['ws_start_sha256'][:12]}… → "
        f"{summary['ws_end_sha256'][:12]}…（agent 真的動過東西）")
    say(f"  模型通道　　　　　　：requests_seen = {summary['requests_seen']}"
        "（這隻假 agent 不呼叫模型，所以離線也跑得完）")
    say("  　　　換成你真的 agent 就看這個數字："
        "「我設了環境變數」不是被中介的證據，requests_seen 才是。")
    say(f"  收據　　　　　　　　：{len(chain)} 筆 Ed25519 簽章鏈　"
        f"{_tilde(chain_p)}")
    say(f"  　　鏈頭　　　　　　：{summary['verdict_hash'][:32]}…")
    say()

    # ── 收據當場驗一次：用**既有的**那把尺，不另寫第二把。──────────────
    say(RULE)
    say("這張收據任何人都能重算——包括先證明驗章器抓得到壞鏈")
    say(RULE)
    # `-m` 形式：`ops/gain/replay/verify_run_receipts.py` 是**同一支**的
    # re-export（那個路徑照樣能直接跑），但它只存在於 repo checkout 裡，
    # 而這一行要在 `pip install` 之後的任何目錄都複製得動。
    ruler = ["-m", "vacant.vrun.verify_receipts"]
    st_argv = [sys.executable, *ruler, "--selftest"]
    say(f"$ {_shown(st_argv)}")
    st = subprocess.run(st_argv, capture_output=True, text=True, timeout=300,
                        cwd=str(paths["root"]), env=_child_env())
    say("  " + (st.stdout.strip().splitlines() or ["(no output)"])[-1])
    vf_argv = [sys.executable, *ruler, "--glob", str(paths["run"]),
               "--json", str(paths["root"] / "verify.json")]
    say(f"$ {_shown(vf_argv)}")
    vf = subprocess.run(vf_argv, capture_output=True, text=True, timeout=300,
                        cwd=str(paths["root"]), env=_child_env())
    for line in vf.stdout.splitlines()[:6]:
        say("  " + line)
    verified = json.loads((paths["root"] / "verify.json")
                          .read_text(encoding="utf-8"))
    say()

    _assert_not_a_performance(plain, gated, summary, chain, verified, st, vf)

    say(RULE)
    say("一句話：**agent 說它做完了，客戶的驗收說沒有。**")
    say("　　　　沒有 Vacant，上面那份 solution.py 已經交出去了。")
    say(RULE)
    say()
    say("接你自己的 agent（`--` 後面照你平常怎麼打就怎麼打）：")
    say()
    say("    vacant run --suite <你自己的驗收目錄> -- <你的 agent 命令>")
    say()
    say("自檢：你的 agent 真的被中介到了嗎？（環境變數名單擋不到用設定檔的框架）")
    say()
    say("    vacant run --allow-no-suite --run-dir /tmp/vr -- <你的 agent 命令>")
    say("    python3 -c \"import json;print(json.load("
        "open('/tmp/vr/run_RUN-ON.json'))['requests_seen'])\"")
    say("    # 非 0 ⇒ 模型通道真的經過 Vacant。0 ⇒ 沒被中介到")
    say("    #        （框架把 base url 寫在設定檔裡，或那一跑根本沒呼叫模型）。")
    say()
    say("誠實邊界（三條，不准淡化；完整版 docs/VACANT_RUN.md §4）：")
    say("  1. proxy 單獨只有 L3。要「agent 逃不掉」得再加出網封鎖")
    say("     （ops/vacantrun/block_egress.sh，需要 root 一次；**那支只在 repo")
    say("     checkout 裡**，pip 裝的版本沒有它——見 README「還需要 clone 的部分」）。")
    say("  2. 中介的是**模型通道**不是 agent 的行為：框架自己的 lint、")
    say("     git checkpoint、內建重試不經過模型通道，看不到也擋不到。")
    say("  3. 驗收是**單邊保證**：擋得住已知壞解 ≠ 涵蓋真需求。")
    say("     accepted=true 只代表「客戶寫下來的那幾條過了」。")
    say()
    say(f"這一跑的全部證據都在：{_tilde(paths['root'])}")
    say()

    return {"root": str(paths["root"]), "plain_rc": plain.returncode,
            "gated_rc": gated.returncode,
            "stop_reason": summary["stop_reason"],
            "accepted": summary["accepted"],
            "visible_passed": summary["visible_passed"],
            "visible_total": summary["visible_total"],
            "failures": summary["failures"],
            "requests_seen": summary["requests_seen"],
            "receipt_entries": len(chain),
            "verdict_hash": summary["verdict_hash"],
            "receipts_verdict": verified["verdict"],
            "receipts_failed_total": verified["failed_total"]}


def default_root() -> pathlib.Path:
    return pathlib.Path.home() / ".vacant-run" / "demo-gate"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="vacant demo gate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            零設定、零模型、零網路的 30 秒示範：一隻假 agent 宣告完成，
            客戶的驗收說沒有，交付被擋下來，並留下一張任何人都能重算的收據。"""))
    ap.add_argument("--root", default=None,
                    help=f"落點（預設 {_tilde(default_root())}；每次執行會先清空）")
    ap.add_argument("--sandbox", default="auto",
                    help="驗收用的沙箱後端：auto／bwrap／unshare／none")
    ap.add_argument("--json", action="store_true", help="只印 JSON summary")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = pathlib.Path(args.root).resolve() if args.root else default_root()
    out = run_demo(root, sandbox=args.sandbox, quiet=args.json)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
