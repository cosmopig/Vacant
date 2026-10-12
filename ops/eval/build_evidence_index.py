"""零設定評估（2026-09-25／26）的證據索引產生器：把這一輪的每一份紀錄、程式、裁決列成一張表，附大小與 sha256。

    python3 ops/eval/build_evidence_index.py            # 產生 ops/eval/evidence_20260925/INDEX.md
    python3 ops/eval/build_evidence_index.py --check    # 檢查索引和現在的檔案一致（被改過、少了、多了都會失敗）

為什麼要產生器、不手寫：索引要能被查——之後有人問「那一份檔當時長什麼樣」，對 sha256 就知道有沒有被動過。
手寫的索引會漂；`--check` 讓漂移在第一時間被看到（同 `ops/gain/build_runs_index.py` 的做法）。

分組與說明寫在 `GROUPS`；每一組列出的檔案是**當下樹上實際存在的**（glob），不是寫死的清單。
提交紀錄取 `FIRST_COMMIT^..HEAD`（這一輪第一個 commit 的前一個 → HEAD），只列觸及 `PATHS` 的 commit。
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "ops/eval/evidence_20260925/INDEX.md"
FIRST_COMMIT = "a80a295a"          # 零設定評測計畫第 2 版＋研議證據：這一輪的起點
# 提交清單只列觸及這一輪東西的提交（同一段時間裡別的工作——hookpolicy、contract quick 的修正——不列）
PATHS = ["ops/eval", "decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md",
         "decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md", "decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md",
         "decisions/conclusions/CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md",
         "docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md",
         "vacant_network/adapters/mode.py", "vacant_network/adapters/hook.py", "vacant_network/adapters/cli.py",
         "vacant_network/trace/evidence.py", "vacant_network/trace/review.py", "vacant_network/trace/zerostop.py",
         "vacant_network/trace/recorder.py", "tests/test_zero_mode.py", "tests/test_zero_evidence.py",
         "tests/test_zero_stop.py", "tests/test_eval_orproxy.py", "README.md", "CLAUDE.md"]

GROUPS: list[tuple[str, str, list[str]]] = [
    ("總報告", "這一輪的完整報告：為什麼是這個結果、和過去的架構比、Vacant 要不要變成 agent",
     ["docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md"]),
    ("裁決、預註冊、結論", "設計、評估計畫（含人類裁決）、簽過字的預註冊、結論與更正",
     ["decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md",
      "decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md",
      "decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md",
      "decisions/conclusions/CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md"]),
    ("產品程式（C 組本身）", "裝了就有作用的零設定 Stop 檢查；正式批次跑的是 8b22c7cc 這一版，之後 efda0d1f 修了兩個誤報",
     ["vacant_network/adapters/mode.py", "vacant_network/adapters/hook.py",
      "vacant_network/adapters/agents.py", "vacant_network/adapters/cli.py",
      "vacant_network/trace/evidence.py", "vacant_network/trace/review.py",
      "vacant_network/trace/zerostop.py", "vacant_network/trace/recorder.py",
      "vacant_network/trace/feedback.py"]),
    ("測試", "零設定的單元與掛鉤測試（含正式批次暴露的誤報回歸）",
     ["tests/test_zero_mode.py", "tests/test_zero_evidence.py", "tests/test_zero_stop.py",
      "tests/test_eval_orproxy.py"]),
    ("評估工具", "記帳代理、Harbor 的 C 組包裝、釘死的 DABstep、試點／正式驅動、分析、重播、模擬使用者、閘門 2",
     ["ops/eval/orproxy.py", "ops/eval/harbor_vacant.py", "ops/eval/dabstep_pin.py",
      "ops/eval/dabstep_formal.py", "ops/eval/pilot/run_one.sh", "ops/eval/pilot/collect.py",
      "ops/eval/pilot/tasks.json", "ops/eval/formal/run_formal.py", "ops/eval/formal/analyze.py",
      "ops/eval/formal/explore_two_runs.py",
      "ops/eval/replay_pi_session.py", "ops/eval/replay_gate.py",
      "ops/eval/simuser/inside.sh", "ops/eval/simuser/run_simuser.py",
      "ops/eval/gate2/run_gate2.sh", "ops/eval/build_evidence_index.py"]),
    ("證據：研究與閘門 1、整輪的帳", "題庫研究筆記、閘門 1（選模型的冒煙測試）、記帳代理設定；`ledger.jsonl` 是研究階段的 41 通，`ledger_all.jsonl.xz`／`summary_all.json` 是整輪 3,324 通、3.4026 美元",
     ["ops/eval/evidence_20260925/README.md", "ops/eval/evidence_20260925/notes/*",
      "ops/eval/evidence_20260925/gate1/*", "ops/eval/evidence_20260925/proxy_config.json",
      "ops/eval/evidence_20260925/ledger.jsonl", "ops/eval/evidence_20260925/summary.json",
      "ops/eval/evidence_20260925/study_result.json",
      "ops/eval/evidence_20260925/ledger_all.jsonl.xz", "ops/eval/evidence_20260925/summary_all.json"]),
    ("證據：C 組設計第 1 版與審查", "第 1 版設計、字句、批評（4 blocker、15 major）、驗收規格、安裝稽核",
     ["ops/eval/evidence_20260925/cdesign/*"]),
    ("證據：真實紀錄重播（誤報門檻）", "閘門 1 的 9 個真實 pi 工作階段在題目容器裡重播",
     ["ops/eval/evidence_20260925/replay/*/*"]),
    ("證據：模擬使用者（L-fake）", "乾淨 Ubuntu、只照 README 裝、照常用 pi；A/C 三個情境；請求逐位元組比對",
     ["ops/eval/evidence_20260925/simuser/SIMUSER.md", "ops/eval/evidence_20260925/simuser/*/*"]),
    ("證據：閘門 2（Harbor 裡，L-fake）", "Harbor 裡 A=0.0、C=1.0（沒寫答案檔被退回、補寫）",
     ["ops/eval/evidence_20260925/gate2/*", "ops/eval/evidence_20260925/gate2/*/*"]),
    ("證據：校準與題目清單", "校準（困難題 1716）、釘死環境與正式 79 題的清單",
     ["ops/eval/evidence_20260925/pilot/*", "ops/eval/evidence_20260925/pilot/calibration/*"]),
    ("證據：正式批次", "執行紀錄、逐通帳、分析輸出、全部請求／回應本文與 318 跑 Harbor 目錄的壓縮檔",
     ["ops/eval/evidence_20260925/formal/*"]),
    ("證據：調查（2026-09-26）", "為什麼沒有差別：過去實驗對照、失敗分類、文獻、兩跑的探索性估計；先讀 README",
     ["ops/eval/evidence_20260925/investigation/README.md", "ops/eval/evidence_20260925/investigation/*",
      "ops/eval/evidence_20260925/investigation/helpers/*"]),
]


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return str(n)


def files_of(patterns: list[str]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for pat in patterns:
        hits = sorted(p for p in REPO.glob(pat) if p.is_file() and "__pycache__" not in p.parts)
        out += [p for p in hits if p not in out and p != OUT]
    return out


def commits() -> list[str]:
    try:
        log = subprocess.run(["git", "log", "--reverse", "--format=%h|%ad|%s",
                              "--date=format:%Y-%m-%d %H:%M", f"{FIRST_COMMIT}^..HEAD", "--", *PATHS],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [ln for ln in log.splitlines() if ln.strip()]


def render() -> str:
    lines = ["# 零設定評估（2026-09-25／26）證據索引", "",
             "> 由 `ops/eval/build_evidence_index.py` 產生；`--check` 驗證索引和檔案一致。**不要手改**。", "",
             "讀的順序：先看總報告（第一組），要查數字再看結論與正式批次的原始紀錄。",
             "原始紀錄（全部請求／回應、每一跑的 Harbor 目錄）在「證據：正式批次」那一組的兩個 `.xz` 壓縮檔裡；",
             "解壓：`xz -dc formal_io.jsonl.xz > io.jsonl`、`xz -dc formal_jobs.tar.xz | tar -x`。", ""]
    for title, desc, pats in GROUPS:
        fs = files_of(pats)
        lines += [f"## {title}", "", desc, ""]
        if not fs:
            lines += ["（目前沒有檔案）", ""]
            continue
        lines += ["| 檔案 | 大小 | sha256（前 16 碼） |", "|---|---:|---|"]
        for p in fs:
            rel = p.relative_to(REPO).as_posix()
            depth = OUT.parent.relative_to(REPO).as_posix().count("/") + 1
            link = "../" * depth + rel
            lines.append(f"| [`{rel}`]({link}) | {human(p.stat().st_size)} | `{sha(p)[:16]}` |")
        lines.append("")
    cs = commits()
    lines += ["## 這一輪的提交（依時間）", "",
              f"從 `{FIRST_COMMIT}`（評測計畫第 2 版）到索引產生時的 HEAD，只列觸及這一輪程式、測試、評估工具、裁決、文件的提交。", ""]
    if cs:
        lines += ["| commit | 時間（UTC） | 說明 |", "|---|---|---|"]
        for c in cs:
            h, d, s = c.split("|", 2)
            lines.append(f"| `{h}` | {d} | {s.replace('|', '／')} |")
    lines += ["", "## 不在 git 裡的東西", "",
              "- OpenRouter 金鑰：只在記帳代理的行程裡讀，從未寫進任何檔（所有證據檔都掃過 `sk-or-v1`）。",
              "- 題目容器映像 `vacant-eval/dabstep-env:1`（ID 在 `pilot/PIN_MANIFEST.json`）：可用 `ops/eval/dabstep_pin.py` 從官方 Dockerfile＋釘死的資料重建。",
              "- 這台雲端機器的暫存區（scratchpad）：原始工作目錄在評估結束後不保證存在；需要的都已壓縮進 `formal/`。", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = render()
    if a.check:
        old = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        # 提交清單會隨新提交變長：只比對檔案表
        strip = lambda t: t.split("## 這一輪的提交")[0]  # noqa: E731
        if strip(old) != strip(text):
            print("FAIL：索引和檔案不一致，重跑 build_evidence_index.py", file=sys.stderr)
            return 1
        print("OK：索引和檔案一致")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
