"""模擬使用者的驗收（DECISION_20260925_ZERO_CONFIG_DESIGN §七、產品原則 4）：同一個 pi、同一個照劇本回答的
假模型、同一個指令，**沒裝**（A）和**只照 README 裝了 Vacant**（C）各跑一次，看交出來的東西。

    python3 ops/eval/simuser/run_simuser.py --image <題目映像> --wheels <wheel 目錄> \
        --node /opt/node22 --pi-modules <含 @earendil-works/pi-coding-agent 的 node_modules> --out <輸出>

三個情境（DABstep 的題目格式；題目與資料在映像的 /app 裡）：
- `made_up_number`：模型沒讀資料就寫了一個數字 → C 應退回，模型重算之後寫對的值
- `missing_answer`：模型算出答案、卻沒寫答案檔就說做完 → C 應退回，模型寫檔
- `correct`：模型算了再寫 → C **不可以**退回；答案、模型收到的第一個請求都要和 A 一樣

⚠ 這是 L-fake：劇本決定模型「看到退回之後」會怎麼做。它證明的是「只照 README 裝、照常用，
退回真的送得到模型、交件前真的改了檔、對的不會被動到」，**不是**真模型會不會照做（那是評測要量的）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
MOCK = HERE.parent.parent / "intake" / "mock_model.py"

BOILER = ("You are an expert data analyst and you will answer factoid questions by referencing files "
          "in the data directory: `/app/data/`\nDon't forget to reference any documentation in the "
          "data dir before answering a question.\n\nHere is the question you need to answer: {q}\n\n"
          "Here are the guidelines you MUST follow when answering the question above: {g}\n\n"
          "When you have computed the final answer, write ONLY the final answer to `/app/answer.txt` "
          "(e.g. if the answer is 42, the file should contain just `42`).")
AVG_Q = "What is the average transaction amount (eur_amount) across all transactions?"
AVG_G = "Answer must be just a number rounded to 2 decimals."
AVG_CMD = ("python3 -c \"import pandas as pd; "
           "print(round(pd.read_csv('/app/data/payments.csv')['eur_amount'].mean(), 2))\"")
TOP_Q = "Which issuing country has the highest number of transactions?"
TOP_G = "Answer must be just the country code."
TOP_CMD = "cut -d, -f11 /app/data/payments.csv | sort | uniq -c | sort -rn | head -3"


def truth(image: str) -> str:
    p = subprocess.run(["docker", "run", "--rm", "--network", "none", image, "bash", "-c", AVG_CMD],
                       capture_output=True, text=True, timeout=300)
    return p.stdout.strip()


def scenarios(avg: str) -> dict[str, tuple[str, dict]]:
    made_up = "91.85" if avg != "91.85" else "87.12"
    return {
        "made_up_number": (BOILER.format(q=AVG_Q, g=AVG_G), {
            "steps": [{"run": "ls /app/data"}, {"write": ["/app/answer.txt", made_up + "\n"]}],
            "final": f"The average transaction amount is {made_up}.",
            "fix": {"steps": [{"run": AVG_CMD}, {"write": ["/app/answer.txt", avg + "\n"]}],
                    "final": f"Recomputed from payments.csv: {avg}."}}),
        "missing_answer": (BOILER.format(q=TOP_Q, g=TOP_G), {
            "steps": [{"run": TOP_CMD}],
            "final": "The issuing country with the most transactions is NL.",
            "fix": {"steps": [{"write": ["/app/answer.txt", "NL\n"]}],
                    "final": "Wrote NL to /app/answer.txt."}}),
        "correct": (BOILER.format(q=AVG_Q, g=AVG_G), {
            "steps": [{"run": "head -3 /app/data/payments.csv"}, {"run": AVG_CMD},
                      {"write": ["/app/answer.txt", avg + "\n"]}],
            "final": f"The average transaction amount is {avg}."}),
    }


def run(arm: str, name: str, task: str, scn: dict, a: argparse.Namespace,
        out: pathlib.Path) -> dict:
    d = out / f"{name}_{arm}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scenario.json").write_text(json.dumps(scn, indent=1))
    (d / "task.txt").write_text(task)
    cmd = ["docker", "run", "--rm", "--network", "none",
           "-v", f"{a.wheels}:/w:ro", "-v", f"{a.node}:/opt/node22:ro",
           "-v", f"{a.pi_modules}:/opt/pi/node_modules:ro", "-v", f"{MOCK.parent}:/m:ro",
           "-v", f"{HERE}:/sim:ro", "-v", f"{d}:/o", a.image,
           "bash", "/sim/inside.sh", arm, "/o/scenario.json", "/o/task.txt"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    ans = (d / "answer.txt").read_text().strip() if (d / "answer.txt").is_file() else None
    reqs = []
    if (d / "mock.jsonl").is_file():
        reqs = [json.loads(x) for x in (d / "mock.jsonl").read_text().split("\n") if x.strip()]
    events = []
    if (d / "pi_stdout.jsonl").is_file():
        for x in (d / "pi_stdout.jsonl").read_text().split("\n"):
            try:
                events.append(json.loads(x))
            except ValueError:
                pass
    reviews = sum(1 for e in events if "Before delivery: a review" in json.dumps(e))
    return {"scenario": name, "arm": arm, "rc": p.returncode, "answer": ans,
            "pi_exit": (d / "pi_exit").read_text().strip() if (d / "pi_exit").is_file() else None,
            "model_requests": len([r for r in reqs if r.get("path") or r.get("n") is not None]),
            "review_in_stdout": reviews, "delivery_note": (d / "delivery.md").is_file(),
            "install": (d / "install_transcript.txt").read_text()
            if (d / "install_transcript.txt").is_file() else None,
            "stderr": p.stderr[-500:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--wheels", required=True)
    ap.add_argument("--node", required=True)
    ap.add_argument("--pi-modules", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only")
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    avg = truth(a.image)
    rows = []
    for name, (task, scn) in scenarios(avg).items():
        if a.only and name != a.only:
            continue
        for arm in ("A", "C"):
            r = run(arm, name, task, scn, a, out)
            rows.append(r)
            print(json.dumps({k: r[k] for k in ("scenario", "arm", "answer", "pi_exit",
                                                "model_requests", "review_in_stdout",
                                                "delivery_note")}), flush=True)
    (out / "summary.json").write_text(json.dumps({"truth_avg": avg, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
