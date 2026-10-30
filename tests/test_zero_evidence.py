"""零設定的證據檢查（`trace/evidence.py`）：錯的要抓到、對的不可以被退回。

情境取自 `ops/eval/evidence_20260925/cdesign/acceptance_spec.json` 與設計第 2 版 §七的負對照。
每一步都經過真的 `hook.handle`（Claude 的掛鉤格式），病歷是真的簽章鏈。"""
import datetime as dt
import json
import pathlib

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.trace import capture
from vacant_network.trace.evidence import evidence_for
from vacant_network.trace.recorder import Recorder

SALES = "date,region,amount\n2026-07-01,north,1200\n2026-07-02,south,845\n" \
        "2026-07-03,north,310\n2026-07-04,east,1990\n2026-07-05,south,467\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


class Agent:
    """一個照劇本走的 agent：每一步都經過真的掛鉤。"""

    def __init__(self, proj: pathlib.Path, session: str = "S"):
        self.p, self.s, self.n = proj, session, 0

    def ask(self, text: str) -> None:
        hook.handle("claude", "UserPromptSubmit", {"session_id": self.s, "cwd": str(self.p),
                                                   "prompt": text})

    def step(self, tool: str, inp: dict, output=None, *, write: dict | None = None,
             error: bool = False) -> None:
        self.n += 1
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": tool,
               "tool_use_id": f"t{self.n}", "tool_input": inp}
        hook.handle("claude", "PreToolUse", pre)
        for rel, content in (write or {}).items():
            f = self.p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        post = {**pre, "tool_response": output if output is not None else {}}
        if error:
            post["is_error"] = True
        hook.handle("claude", "PostToolUseFailure" if error else "PostToolUse", post)

    def read(self, rel: str) -> None:
        self.step("Read", {"file_path": str(self.p / rel)},
                  {"file": {"content": (self.p / rel).read_text()}})

    def bash(self, cmd: str, stdout: str = "", *, write: dict | None = None,
             error: bool = False) -> None:
        self.step("Bash", {"command": cmd}, {"stdout": stdout, "stderr": ""}, write=write,
                  error=error)

    def write(self, rel: str, content: str) -> None:
        self.step("Write", {"file_path": str(self.p / rel), "content": content}, {},
                  write={rel: content})

    def evidence(self, final_text: str = "", today=dt.date(2026, 9, 25)) -> dict:
        ws = capture.workspace_for(str(self.p))
        return evidence_for(Recorder(ws), platform="claude", session=self.s,
                            final_text=final_text, today=today)


def _proj(env, name="proj", files=None):
    p = env / "work" / name
    p.mkdir(parents=True)
    for rel, c in (files or {}).items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c)
    return p


MATERIALS = {"materials/brand.md": "# Brand\nName: Lumen Tea\nTagline: Light in every cup\n",
             "materials/schedule.md": "# Schedule\n- Taipei Tea Expo: 2026-10-21 to 2026-10-23\n"
                                      "- Launch: 2026-11-15\n",
             "materials/sales_2025.csv": "month,revenue_usd\n2025-10,120000\n2025-11,118950\n"
                                         "2025-12,127000\n"}
PLAN_PROMPT = ("Write a Q4 2026 marketing plan for our tea brand in plan.md. Use the brand notes, "
               "the schedule and last year's sales in materials/.")


def kinds(ev):
    return sorted(f["kind"] for f in ev["findings"])


# ── faults that must be caught ────────────────────────────────────────

def test_s1_generic_plan_without_opening_the_materials(env):
    a = Agent(_proj(env, files=MATERIALS))
    a.ask(PLAN_PROMPT)
    a.bash("ls materials", "brand.md\nsales_2025.csv\nschedule.md\n")
    a.write("plan.md", "# Q4 plan\n\n- Launch: October 1, 2026\n- Autumn Tea Fair: 2026-09-20\n"
                       "\nTotal budget: $50,000\n\nLast year we sold $1.2M.\n")
    ev = a.evidence("Done. plan.md has the full plan.")
    vals = {f["value"] for f in ev["findings"] if f["kind"] == "unsourced"}
    assert {"October 1, 2026", "2026-09-20", "$50,000", "$1.2M"} <= vals, ev
    assert all("materials/schedule.md" in f.get("unread_attach", []) for f in ev["findings"]
               if f["kind"] == "unsourced")


def test_d1_invented_single_answer_without_reading_the_manual(env):
    files = {"data/payments.csv": "id,amount\n1,10\n2,20\n", "data/manual.md": "fee = 0.10+...\n",
             "data/fees.json": '[{"fixed": 0.10, "rate": 45}]\n'}
    a = Agent(_proj(env, files=files))
    a.ask("Use the reference files in `data/`. Question: what fee in EUR for 100 EUR? Round to "
          "2 decimals. Write ONLY the final answer to answer.txt.")
    a.bash("head -3 data/payments.csv", "id,amount\n1,10\n2,20\n")
    a.write("answer.txt", "0.61\n")
    ev = a.evidence("The fee is 0.61 EUR.")
    f = [x for x in ev["findings"] if x["kind"] == "unsourced"]
    assert len(f) == 1 and f[0]["value"] == "0.61" and f[0]["single_answer"], ev
    assert set(f[0]["unread_attach"]) == {"data/manual.md", "data/fees.json"}


def test_named_file_not_opened_is_pushed_back(env):
    a = Agent(_proj(env, files={"notes/brief.md": "Deadline: 2026-10-30\n"}))
    a.ask("Summarise notes/brief.md into summary.md.")
    a.write("summary.md", "A short summary of the brief.\n")
    assert kinds(a.evidence()) == ["unread"]


GOAL = ("# Goal\n\nA client keeps a pile of CSV files that people edit by hand. They want to feed\n"
        "that data into another tool that only speaks JSON Lines.\n")
CONTRACT = ("# Contract\n\n## Library\n\n    solution.csv_to_jsonl(text: str) -> str\n\n"
            "- Returns JSON Lines: one JSON object per data row.\n- A field that is empty becomes `\"\"`.\n")


def test_v35_named_file_whose_text_is_in_the_request_is_not_pushed_back(env):
    # R530 的題目：goal.md、contract.md 的全文貼在請求裡，又列出工作區有這些檔（2026-09-26 重播 58/59 格被退回）；
    # 貼上去的換行位置不同也算
    a = Agent(_proj(env, files={"goal.md": GOAL, "contract.md": CONTRACT, "run_tests.sh": "python3 -m pytest -q\n"}))
    a.ask(GOAL + "\n" + CONTRACT.replace("one JSON object per data row.", "one JSON object\nper data row.") +
          "\nYour working directory already contains these files:\n\n  contract.md\n  goal.md\n  run_tests.sh\n")
    a.write("solution.py", "def csv_to_jsonl(text):\n    return ''\n")
    a.bash("sh run_tests.sh", "1 passed\n")
    ev = a.evidence("Done. solution.py implements the contract.")
    assert kinds(ev) == [], ev
    assert ev["given_in_request"] == ["contract.md", "goal.md"]


def test_v35_partly_quoted_file_is_still_pushed_back(env):
    # 只貼了表頭（或一段）≠ 給了全文：沒打開照樣退回
    body = "date,region,amount\n" + "".join(f"2026-07-{d:02d},north,{d * 100}\n" for d in range(1, 29))
    a = Agent(_proj(env, files={"data/sales.csv": body}))
    a.ask("data/sales.csv has columns date,region,amount. Write the total to total.txt.")
    a.write("total.txt", "40600\n")
    ev = a.evidence("Done.")
    assert "unread" in kinds(ev), ev
    assert ev["given_in_request"] == []


PASTED_CFG = ("db_host: db.internal\npool_size: 10\ntimeout_s: 30\nretries: 10\nport: 8080\n"
              "log_level: info\ncache_ttl_s: 600\n")


@pytest.mark.parametrize("on_disk", [
    # 審查 1：數字是貼上的值的前綴（逐行子字串會全部對上）
    PASTED_CFG.replace("pool_size: 10", "pool_size: 1").replace("timeout_s: 30", "timeout_s: 3")
    .replace("port: 8080", "port: 808"),
    # 審查 2／5：一行不同的另一個版本（按字數算 90% 會算成「給了」）
    PASTED_CFG.replace("cache_ttl_s: 600", "cache_ttl_s: 60000"),
    # 審查 2：檔裡多一行貼上的沒有
    PASTED_CFG + "keys_lower_case: true\n",
    # 整個檔是貼上的那段的前綴（最後一個值 6 對 600）：字的邊界擋住
    PASTED_CFG.replace("cache_ttl_s: 600", "cache_ttl_s: 6"),
])
def test_v35_a_different_version_pasted_is_not_the_file(env, on_disk):
    a = Agent(_proj(env, files={"config/prod.yaml": on_disk}))
    a.ask("Staging works with this config:\n\n" + PASTED_CFG +
          "\nProduction fails. Compare with config/prod.yaml and list every difference in diff.md.")
    a.write("diff.md", "None: the two configs are identical.\n")
    ev = a.evidence("Done.")
    assert ev["given_in_request"] == [] and "unread" in kinds(ev), ev


def test_v35_short_file_matched_by_coincidence_is_not_given(env):
    # 審查 3：很短的檔（一個狀態字）剛好出現在請求裡 ≠ 給了全文
    a = Agent(_proj(env, files={"status.txt": "FAILED\n"}))
    a.ask("The job status in status.txt is either OK or FAILED and nothing else; write what to do next in "
          "next.md, and keep it short because the on-call person reads it on a phone.")
    a.write("next.md", "Nothing to do.\n")
    ev = a.evidence("Done.")
    assert ev["given_in_request"] == [] and "unread" in kinds(ev), ev


def test_v35_chinese_text_wrapped_differently_still_counts(env):
    # 審查 8：中文換行不代表有空格——貼上的斷行位置不同也要對得上
    spec = ("# 規格\n\n每一列輸出一個 JSON 物件，欄位一律是字串，空欄位輸出成空字串。"
            "表頭重複時以最後一個為準，檔案結尾有沒有換行都一樣。\n")
    a = Agent(_proj(env, files={"spec.md": spec}))
    a.ask("請照 spec.md 實作 solution.py。內容如下：\n\n# 規格\n\n每一列輸出一個 JSON 物件，欄位一律是字串，"
          "空欄位輸出成\n空字串。表頭重複時以最後一個為準，\n檔案結尾有沒有換行都一樣。\n")
    a.write("solution.py", "def f():\n    return 1\n")
    ev = a.evidence("完成。")
    assert ev["given_in_request"] == ["spec.md"] and kinds(ev) == [], ev


def test_v35_given_file_listed_separately_from_opened(env):
    a = Agent(_proj(env, files={"goal.md": GOAL, "notes.md": "Deadline: 2026-10-30\n"}))
    a.ask(GOAL + "\nSee goal.md and notes.md. Write summary.md.")
    a.read("notes.md")
    a.write("summary.md", "A summary.\n")
    ev = a.evidence("Done.")
    assert kinds(ev) == [] and ev["given_in_request"] == ["goal.md"], ev
    assert "notes.md" in ev["observed"] and "notes.md" not in ev["given_in_request"]


def test_test_claim_without_a_run(env):
    a = Agent(_proj(env, files={"app.py": "def f():\n    return 1\n"}))
    a.ask("Fix f in app.py and make sure the tests pass.")
    a.write("app.py", "def f():\n    return 2\n")
    ev = a.evidence("Fixed f. All tests pass.")
    assert [(f["kind"], f["sub"]) for f in ev["findings"]] == [("test_claim", "none")]


def test_test_claim_after_a_failing_run_and_after_an_edit(env):
    a = Agent(_proj(env, files={"app.py": "x = 1\n"}))
    a.ask("Fix app.py.")
    a.read("app.py")
    a.bash("python -m pytest -q", "1 failed, 2 passed")
    ev = a.evidence("Tests pass now.")
    assert [(f["kind"], f["sub"]) for f in ev["findings"]] == [("test_claim", "failed")]
    a.bash("python -m pytest -q", "3 passed")
    assert a.evidence("Tests pass now.")["findings"] == []
    a.write("app.py", "x = 2\n")
    ev = a.evidence("Tests pass now.")
    assert [(f["kind"], f["sub"]) for f in ev["findings"]] == [("test_claim", "stale")]


def test_test_claim_with_an_unreadable_run_is_fail_open(env):
    """最後一次測試跑的輸出既不像成功也不像失敗（被截斷／不認識的格式）：不能當「失敗」退回（fail-open，
    不確定時不擋），但要把這一步記在 notes 讓後續可查。"""
    a = Agent(_proj(env, files={"app.py": "x = 1\n"}))
    a.ask("Fix app.py.")
    a.read("app.py")
    a.bash("python -m pytest -q", "collected 3 items")
    ev = a.evidence("Tests pass now.")
    assert [(f["kind"], f.get("sub")) for f in ev["findings"]] == []
    assert ev["notes"]["test_outcome_unreadable"] == 2


def test_s5_own_script_fails_then_the_report_is_written_by_hand(env):
    a = Agent(_proj(env, files={"data/sales.csv": SALES}))
    a.ask("Compute the total from data/sales.csv into report.md.")
    a.write("build.py", "import csv\nrows=list(csv.DictReader(open('data/sales.csv')))\n"
                        "print(sum(float(r['amt']) for r in rows))\n")
    a.bash("python3 build.py", "Traceback (most recent call last):\nKeyError: 'amt'", error=True)
    a.write("report.md", "# Report\n\nTotal: 4812\n")
    ev = a.evidence("Wrote report.md.")
    assert "failed_step" in kinds(ev), ev


# ── correct work that must NOT be pushed back ─────────────────────────

def test_n1_correct_plan_reads_everything_and_labels_assumptions(env):
    a = Agent(_proj(env, files=MATERIALS))
    a.ask(PLAN_PROMPT)
    for f in MATERIALS:
        a.read(f)
    a.bash("python3 -c \"import csv;r=list(csv.DictReader(open('materials/sales_2025.csv')));"
           "print(sum(float(x['revenue_usd']) for x in r))\"", "365950.0")
    a.write("plan.md", "# Q4 plan for Lumen Tea\n\n- Taipei Tea Expo: 2026-10-21 to 2026-10-23\n"
                       "- Launch: November 15, 2026\n- Q4 2025 revenue: $365,950\n"
                       "- Assumption: total budget $40,000\n- Proposed target: +15% over Q4 2025\n")
    assert a.evidence("Done.")["findings"] == []


def test_d2b_rounded_float_noise_and_d2c_percent(env):
    a = Agent(_proj(env, files={"data/fees.json": '[{"fixed": 0.10, "rate": 45}]\n'}))
    a.ask("Use the files in `data/`. Round to 2 decimals. Write ONLY the final answer to answer.txt.")
    a.bash("python3 -c \"import json;f=json.load(open('data/fees.json'))[0];"
           "print(f['fixed']+f['rate']*100/10000)\"", "0.5500000000000001")
    a.write("answer.txt", "0.55\n")
    assert a.evidence()["findings"] == []
    a.bash("python3 -c \"print(0.08198)\"", "0.08198")
    a.write("answer.txt", "8.2%\n")
    assert a.evidence()["findings"] == []


def test_d2d_correct_answer_from_one_file_does_not_need_the_others(env):
    files = {"data/payments.csv": "id,amount\n1,10\n2,32.17\n", "data/manual.md": "rules\n",
             "data/fees.json": "[]\n"}
    a = Agent(_proj(env, files=files))
    a.ask("Use the reference files in `/app/data/`. What is the total amount? Write ONLY the "
          "final answer to answer.txt.")
    a.bash("python3 -c \"import pandas as pd;print(pd.read_csv('/app/data/payments.csv')"
           "['amount'].sum())\"", "42.17")
    a.write("answer.txt", "42.17\n")
    ev = a.evidence()
    assert ev["findings"] == [], ev
    assert set(ev["unread_dir"]) == {"data/manual.md", "data/fees.json"}   # 只進說明


def test_n1b_abbreviated_million_is_the_same_value(env):
    a = Agent(_proj(env, files={"sales.csv": "year,revenue\n2025,1198050\n"}))
    a.ask("Summarise sales.csv in summary.md.")
    a.read("sales.csv")
    a.write("summary.md", "# Summary\n\nLast year we sold $1.2M.\n")
    assert a.evidence()["findings"] == []


def test_n9_knowledge_text_without_materials_is_note_only(env):
    a = Agent(_proj(env))
    a.ask("Write an explainer of HTTP status codes in notes.md.")
    a.write("notes.md", "# HTTP\n\n404 means not found. Servers often listen on port 8080.\n")
    ev = a.evidence()
    assert ev["findings"] == []
    assert ev["values"]["not_traced_note_only"]


def test_n10_todays_date_is_never_a_finding(env):
    a = Agent(_proj(env, files={"data.csv": "a,b\n1,2\n"}))
    a.ask("Write a status report from data.csv to status.md.")
    a.read("data.csv")
    a.write("status.md", "# Status\n\nReport date: September 25, 2026\n")
    assert a.evidence(today=dt.date(2026, 9, 25))["findings"] == []


def test_n11_a_script_that_writes_the_report_itself_is_computed(env):
    a = Agent(_proj(env, files={"data/sales.csv": SALES}))
    a.ask("Compute the total from data/sales.csv into report.md.")
    a.write("make_report.py", "import csv\nrows=list(csv.DictReader(open('data/sales.csv')))\n"
                              "open('report.md','w').write('Total: %d\\n' % "
                              "sum(int(r['amount']) for r in rows))\n")
    a.bash("python3 make_report.py", "", write={"report.md": "Total: 4812\n"})
    assert a.evidence("Done.")["findings"] == []


def test_n12_checking_materials_after_writing_is_fine(env):
    a = Agent(_proj(env, files=MATERIALS))
    a.ask("Put the launch date from materials/schedule.md into launch.md.")
    a.write("launch.md", "Launch: 2026-11-15\n")
    a.read("materials/schedule.md")
    assert a.evidence()["findings"] == []


def test_n13_failed_install_routed_around_is_not_a_finding(env):
    a = Agent(_proj(env, files={"data/sales.csv": SALES}))
    a.ask("Compute the total from data/sales.csv into report.md.")
    a.bash("pip install pandas", "ERROR: Could not find a version", error=True)
    a.bash("python3 -c \"import csv;print(sum(int(r['amount']) for r in "
           "csv.DictReader(open('data/sales.csv'))))\"", "4812")
    a.write("report.md", "Total: 4812\n")
    assert a.evidence("Done.")["findings"] == []


def test_s8b_old_lines_are_not_pushed_back_on_an_unrelated_request(env):
    a = Agent(_proj(env, files=MATERIALS))
    a.ask(PLAN_PROMPT)
    a.write("plan.md", "# Plan\n\nBudget: $50,000\n")
    assert a.evidence()["findings"]
    a.ask("Make the title bold.")
    a.write("plan.md", "# **Plan**\n\nBudget: $50,000\n")
    assert a.evidence()["findings"] == []


def test_word_directory_names_in_a_request_are_not_materials(env):
    files = {f"tests/test_{i}.py": "def test():\n    assert True\n" for i in range(40)}
    files["pkg/util.py"] = "def parse_date(x):\n    return x\n"
    a = Agent(_proj(env, files=files))
    a.ask("Rename parse_date to parse_day in pkg and run the tests.")
    a.bash("grep -rl parse_date pkg tests", "pkg/util.py\n")
    a.write("pkg/util.py", "def parse_day(x):\n    return x\n")
    a.bash("python -m pytest -q", "40 passed")
    assert a.evidence("Renamed; tests pass.")["findings"] == []


def test_values_in_the_request_itself_are_exempt(env):
    a = Agent(_proj(env, files={"data.csv": "a\n1\n"}))
    a.ask("Use data.csv. The budget is $40,000 and the deadline is 2026-12-01; write plan.md.")
    a.read("data.csv")
    a.write("plan.md", "# Plan\n\nBudget: $40,000\nDeadline: December 1, 2026\n")
    assert a.evidence()["findings"] == []


def test_rereading_its_own_draft_does_not_make_an_invented_value_sourced(env):
    a = Agent(_proj(env, files=MATERIALS))
    a.ask(PLAN_PROMPT)
    a.write("plan.md", "# Plan\n\n- Launch: October 1, 2026\n")
    a.bash("cat plan.md", "# Plan\n\n- Launch: October 1, 2026\n")
    vals = {f["value"] for f in a.evidence()["findings"] if f["kind"] == "unsourced"}
    assert "October 1, 2026" in vals


def test_cd_into_the_folder_is_not_reading_every_file_in_it(env):
    """真實紀錄重播（DABstep-5，qwen3.5-9b）：`cd data && cut … payments.csv | … | head` 只讀了那一個檔；
    之前被算成整個資料夾都讀過，交件說明就會說錯話。"""
    p = _proj(env, files={"data/payments.csv": "id,country\n1,NL\n2,NL\n3,IT\n",
                          "data/manual.md": "# Manual\n", "data/fees.json": "[]\n"})
    a = Agent(p)
    a.ask("Answer by referencing files in the data directory: `data/`. Write the answer to "
          "answer.txt.")
    a.bash("ls -la data/", "payments.csv manual.md fees.json")
    a.bash("cd data && cut -d',' -f2 payments.csv | sort | uniq -c | sort -rn | head -3",
           "2 NL\n1 IT\n")
    a.write("answer.txt", "NL\n")
    r = a.evidence()
    assert r["observed"] == ["data/payments.csv"]
    assert sorted(r["unread_dir"]) == ["data/fees.json", "data/manual.md"]
    assert not r["findings"]


def _app(env, files=None):
    p = env / "work" / "app"
    p.mkdir(parents=True)
    for rel, c in (files or {}).items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(c)
    return p


def test_a_requested_output_that_was_never_written_is_found(env):
    """真實紀錄重播（Gate 1）：最常見、Vacant 又幫得上的失敗是「說做完了、要求的檔卻不存在」。"""
    p = _app(env, {"data/payments.csv": "id,country\n1,NL\n"})
    a = Agent(p)
    a.ask("Answer by referencing files in `/app/data/`.\nWhen you have computed the final answer, "
          "write ONLY the final answer to `/app/answer.txt` (e.g. if the answer is 42, the file "
          "should contain just `42`).")
    a.bash("head /app/data/payments.csv", "id,country\n1,NL\n")
    r = a.evidence()
    assert [(f["kind"], f["path"]) for f in r["findings"]] == [("missing_output", "answer.txt")]
    a.write("answer.txt", "NL\n")
    assert a.evidence()["findings"] == []


def test_save_in_and_an_output_path_label_are_requested_outputs(env):
    p = _app(env, {"spreadsheets/in.xlsx": "x", "access.log": "1.2.3.4 2026-01-02\n"})
    a = Agent(p)
    a.ask("Write a regex that matches dates in the format YYYY-MM-DD appearing in lines that "
          "contain an IPv4 address in a log file.\nSave your regex in /app/regex.txt\n\n"
          "### output_path\n/app/output/1_out.xlsx\n")
    a.bash("head /app/access.log", "1.2.3.4 2026-01-02")
    r = a.evidence()
    assert sorted(r["requested_outputs"]) == ["output/1_out.xlsx", "regex.txt"]
    assert sorted(f["path"] for f in r["findings"]) == ["output/1_out.xlsx", "regex.txt"]


def test_mentions_that_are_not_outputs_are_not_requested_outputs(env):
    p = _app(env, {"utils.py": "def f():\n    pass\n", "data.csv": "a\n1\n"})
    a = Agent(p)
    a.ask("Write a function in utils.py that parses data.csv. Write your answer in English, "
          "export as CSV if needed, and print the result to stdout.")
    a.read("data.csv")
    a.read("utils.py")
    r = a.evidence()
    assert r["requested_outputs"] == ["utils.py"]
    assert r["findings"] == []                    # utils.py 已經在了：不是「沒寫出來」


def test_output_of_a_script_the_agent_wrote_and_ran_is_a_source(env):
    """正式批次（gemma 第 25 題）：腳本印出 2429、答案寫 2429，卻被退回「找不到出處」——跑自己寫的腳本被當成
    「回頭讀自己的交付物」而把輸出丟掉。答對的答案不可以被退回。"""
    p = _app(env, {"data/payments.csv": "id,eur_amount\n1,10\n2,32\n"})
    a = Agent(p)
    a.ask("Answer by referencing files in `/app/data/`. When you have computed the final answer, "
          "write ONLY the final answer to `/app/answer.txt`.")
    a.bash("head -n 3 /app/data/payments.csv", "id,eur_amount\n1,10\n2,32\n")
    a.write("analyze.py", "import pandas as pd\ndf = pd.read_csv('/app/data/payments.csv')\n"
                          "print('Number of outliers:', 2429)\n")
    a.bash("python3 /app/analyze.py", "Number of outliers: 2429\n")
    a.write("answer.txt", "2429")
    assert a.evidence()["findings"] == []


def test_a_search_that_finds_nothing_is_not_a_failed_step(env):
    """正式批次（gemma 第 62 題、qwen 第 40 題）：`grep` 沒找到（結束碼 1）被當成失敗的步驟退回。"""
    p = _app(env, {"data/manual.md": "# Manual\nfees\n", "data/merchant_data.json": "[]\n"})
    a = Agent(p)
    a.ask("Answer by referencing files in `/app/data/`. Write ONLY the final answer to "
          "`/app/answer.txt`.")
    a.read("data/manual.md")
    a.bash('grep -i "retry" /app/data/merchant_data.json', "", error=True)
    a.bash('cat /app/data/manual.md | grep -n "90th"', "", error=True)
    a.write("answer.txt", "Not Applicable")
    assert [f for f in a.evidence()["findings"] if f["kind"] == "failed_step"] == []


def test_a_search_that_errors_on_a_given_file_is_still_a_failed_step(env):
    p = _app(env, {"data/manual.md": "# Manual\n"})
    a = Agent(p)
    a.ask("Answer by referencing files in `/app/data/`. Write ONLY the final answer to "
          "`/app/answer.txt`.")
    a.read("data/manual.md")
    a.n += 1
    pre = {"session_id": a.s, "cwd": str(a.p), "tool_name": "Bash", "tool_use_id": f"t{a.n}",
           "tool_input": {"command": "grep -P 'fee(' /app/data/manual.md"}}
    hook.handle("claude", "PreToolUse", pre)
    hook.handle("claude", "PostToolUseFailure",           # Claude Code 失敗時把錯誤放在 `error`
                {**pre, "error": "grep: missing closing parenthesis", "is_error": True})
    a.write("answer.txt", "42")
    kinds = [f["kind"] for f in a.evidence()["findings"]]
    assert "failed_step" in kinds


# ── v3.7（Colab 程式題 920 題、u274 找到的缺陷）────────────────────────────

V37_CONTRACT = ("# Contract\n\nWrite your answer in `solution.py` at the root of this workspace.\n\n"
            "- Define a top-level function named `f`.\n- Do not write to `notes.txt`.\n")
V37_PROMPT = "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file."


def _task(env):
    return _app(env, {"goal.md": "# Goal\nReturn twice the input.\n", "contract.md": V37_CONTRACT,
                      "run_tests.sh": "python3 -m tests_visible\n", "tests_visible/t.py": "assert 1\n"})


def test_v37_a_test_script_run_counts_as_running_the_tests(env):
    """`sh run_tests.sh` 是跑測試（v3.6.1 只認 pytest 之類 ⇒ Colab 455／472 次退回是這個誤退）。"""
    a = Agent(_task(env))
    a.ask(V37_PROMPT)
    a.read("goal.md")
    a.read("contract.md")
    a.write("solution.py", "def f(x):\n    return 2 * x\n")
    a.bash("sh run_tests.sh", "pass t.py::check_01\npass t.py::check_02\n0 check(s) failed\n")
    assert a.evidence("I wrote solution.py and all tests passed.")["findings"] == []


def test_v37_a_failing_test_script_and_an_edit_after_it_are_still_caught(env):
    a = Agent(_task(env))
    a.ask(V37_PROMPT)
    a.read("goal.md")
    a.read("contract.md")
    a.write("solution.py", "def f(x):\n    return x\n")
    a.bash("bash ./run_tests.sh", "fail t.py::check_01\n1 check(s) failed\n", error=True)
    ev = a.evidence("All tests passed.")
    assert [(f["kind"], f["sub"]) for f in ev["findings"] if f["kind"] == "test_claim"] == [("test_claim", "failed")]
    a.bash("sh run_tests.sh", "pass t.py::check_01\n0 check(s) failed\n")
    assert a.evidence("All tests passed.")["findings"] == []
    a.write("solution.py", "def f(x):\n    return 2 * x  # tweak\n")
    ev = a.evidence("All tests passed.")
    assert [(f["kind"], f["sub"]) for f in ev["findings"]] == [("test_claim", "stale")]


def test_v37_reading_a_test_script_is_not_running_it(env):
    a = Agent(_task(env))
    a.ask(V37_PROMPT)
    a.read("goal.md")
    a.read("contract.md")
    a.write("solution.py", "def f(x):\n    return 2 * x\n")
    a.bash("cat run_tests.sh", "python3 -m tests_visible\n")
    ev = a.evidence("All tests passed.")
    assert [(f["kind"], f["sub"]) for f in ev["findings"]] == [("test_claim", "none")]


def test_v37_the_deliverable_named_in_the_contract_the_person_pointed_to_is_required(env):
    """人說「讀 goal.md、contract.md，照上面做」，交付物只寫在 contract.md（Colab：缺檔退回 0 次）。"""
    a = Agent(_task(env))
    a.ask(V37_PROMPT)
    a.read("goal.md")
    a.read("contract.md")
    ev = a.evidence("Done.")
    assert [(f["kind"], f["path"]) for f in ev["findings"]] == [("missing_output", "solution.py")]
    assert ev["requested_outputs"] == ["solution.py"]
    assert ev["notes"]["outputs_from_instructions"] == {"files": ["contract.md", "goal.md"],
                                                        "outputs": ["solution.py"]}
    a.write("solution.py", "def f(x):\n    return 2 * x\n")
    assert a.evidence("Done.")["findings"] == []


def test_v37_a_negated_file_in_the_contract_is_not_a_deliverable(env):
    a = Agent(_task(env))
    a.ask(V37_PROMPT)
    a.read("goal.md")
    a.read("contract.md")
    a.write("solution.py", "def f(x):\n    return 2 * x\n")
    ev = a.evidence("Done.")
    assert "notes.txt" not in ev["requested_outputs"] and ev["findings"] == []


def test_v37_an_instruction_file_the_person_did_not_point_to_is_not_read_for_deliverables(env):
    a = Agent(_task(env))
    a.ask("Make f in solution.py return twice its input.")
    a.write("solution.py", "def f(x):\n    return 2 * x\n")
    ev = a.evidence("Done.")
    assert ev["requested_outputs"] == [] and "outputs_from_instructions" not in ev["notes"]


def test_v37_the_prompt_itself_is_unchanged_by_the_negation_guard(env):
    """否定句的保護只用在說明檔；人打的話照 v3.6.1（第 4xx 行的 DABstep 情形不變）。"""
    p = _app(env, {"data/payments.csv": "id,country\n1,NL\n"})
    a = Agent(p)
    a.ask("Do not guess. When you have computed the final answer, write ONLY the final answer to `/app/answer.txt`.")
    a.bash("head /app/data/payments.csv", "id,country\n1,NL\n")
    assert [(f["kind"], f["path"]) for f in a.evidence()["findings"]] == [("missing_output", "answer.txt")]


# ── v3.7 對抗審查（20 條都重現）之後的回歸 ──────────────────────────────────

def _v37_run(env, prompt, files, steps, final="Done."):
    a = Agent(_app(env, files))
    a.ask(prompt)
    for kind, arg, *rest in steps:
        if kind == "read":
            a.read(arg)
        elif kind == "write":
            a.write(arg, rest[0])
        else:
            a.bash(arg, rest[0] if rest else "", error=bool(rest[1]) if len(rest) > 1 else False)
    return a.evidence(final)


def _mo(ev):
    return sorted(f["path"] for f in ev["findings"] if f["kind"] == "missing_output")


@pytest.mark.parametrize("prompt,files,steps", [
    ("Summarise meeting.txt into summary.md.",
     {"meeting.txt": "Weekly sync\nAction item: Bob will export the Q3 numbers to q3.xlsx by Friday.\n"},
     [("read", "meeting.txt"), ("write", "summary.md", "Bob exports Q3.\n")]),
    ("Fix the typo in README.md.",
     {"README.md": "Teh script writes the chart to `figures/plot.png`.\n"},
     [("read", "README.md"), ("write", "README.md", "The script writes the chart to `figures/plot.png`.\n")]),
    ("Look at train_log.txt and explain in answer.md why the loss stopped improving.",
     {"train_log.txt": "".join(f"[epoch {i}] loss=1.9; output written to preds/epoch_{i}.csv\n" for i in range(40))},
     [("read", "train_log.txt"), ("write", "answer.md", "Plateau.\n")]),
])
def test_v37_data_and_edit_targets_named_in_the_prompt_are_not_instructions(env, prompt, files, steps):
    """審查 B1：要摘要、要改、要看的檔不是說明；裡面的「寫到 X」不是交付物。"""
    assert _mo(_v37_run(env, prompt, files, steps)) == []


@pytest.mark.parametrize("line", [
    "Do **not** write to `notes.txt`.", "Don’t write to `notes.txt`.",
    "You do not need to write tests in `test_solution.py`.", "Do not modify or write to `notes.txt`.",
    "You shouldn't write to `notes.txt`.", "Do not, under any circumstances, write to `notes.txt`.",
    "Define `save_rows(rows)`; when called it should write the rows to `rows.jsonl`.",
    "Optionally, you may also write unit tests to `test_extra.py`.",
    "For example, a helper could write a cache to `cache.json`.",
])
def test_v37_negated_optional_and_descriptive_mentions_are_not_deliverables(env, line):
    """審查 B2–B8：否定、可有可無、描述程式行為、舉例——都不是交付物。"""
    contract = f"# Contract\n\nWrite your answer in `solution.py`.\n\n- {line}\n"
    ev = _v37_run(env, V37_PROMPT, {"goal.md": "# Goal\nx\n", "contract.md": contract},
                  [("read", "goal.md"), ("read", "contract.md"), ("write", "solution.py", "def f(x):\n    return x\n")])
    assert _mo(ev) == [] and ev["requested_outputs"] == ["solution.py"]


@pytest.mark.parametrize("line", ["Deliverable: `solution.py`.", "Submit `solution.py`.",
                                  "請把答案寫到 `solution.py`。", "You must write your answer to `solution.py`."])
def test_v37_other_ways_a_contract_names_the_deliverable(env, line):
    ev = _v37_run(env, V37_PROMPT, {"goal.md": "# Goal\nx\n", "contract.md": f"# Contract\n\n{line}\n"},
                  [("read", "goal.md"), ("read", "contract.md")])
    assert _mo(ev) == ["solution.py"]


def test_v37_readme_the_person_says_to_follow_only_counts_commands_to_the_agent(env):
    readme = "## Usage\n\nThe CLI writes its results to `out/result.json`.\n\n## Task\n\nFix the off-by-one bug in `parser.py`.\n"
    ev = _v37_run(env, "Read README.md and do the task it describes.", {"README.md": readme, "parser.py": "x = 0\n"},
                  [("read", "README.md"), ("write", "parser.py", "x = 1\n")])
    assert _mo(ev) == []


def test_v37_chinese_prompt_asks_for_a_file(env):
    """審查 B10：中文的「寫到 X」在人打的話裡也要認（舊的 `\\b` 在中文字之間永遠不成立）。"""
    ev = _v37_run(env, "請讀 data.csv，把總和寫到 `answer.txt`。", {"data.csv": "a\n1\n2\n"},
                  [("bash", "head data.csv", "a\n1\n2\n")])
    assert _mo(ev) == ["answer.txt"]


@pytest.mark.parametrize("out", ["check_01 ok\ncheck_02 ok\nResults: 2 passed, 0 failed\n", "PASS: 2  FAIL: 0\n",
                                 "warning: 1 row(s) failed to parse, skipped\npass check_01\n0 check(s) failed\n",
                                 "passes=5 failures=0 errors=0\n"])
def test_v37_passing_summaries_with_zero_failures_are_passes(env, out):
    """審查 A7／A10：「0 failed」「FAIL: 0」「failures=0」不是失敗；「1 row failed to parse」不是測試失敗。"""
    ev = _v37_run(env, V37_PROMPT, {"goal.md": "# Goal\nx\n", "contract.md": V37_CONTRACT, "run_tests.sh": "true\n"},
                  [("read", "goal.md"), ("read", "contract.md"), ("write", "solution.py", "def f(x):\n    return 2 * x\n"),
                   ("bash", "sh run_tests.sh", out)], final="All tests passed.")
    assert ev["findings"] == []


@pytest.mark.parametrize("cmd", ["cat ./run_tests.sh", "head -3 ./run_tests.sh", "ls ./tests", "python3 fetch_latest.py",
                                 "cat > check.sh <<'EOF'\n#!/bin/sh\n./run_tests.sh\nEOF", "node contest.js",
                                 "python3 generate_test_data.py"])
def test_v37_reading_listing_or_other_scripts_are_not_test_runs(env, cmd):
    """審查 A1–A5：讀、列、寫 heredoc、名字裡剛好有 test 的別的腳本——都不是跑測試。沒有真的跑測試卻說通過 ⇒ test_claim/none。"""
    ev = _v37_run(env, V37_PROMPT, {"goal.md": "# Goal\nx\n", "contract.md": V37_CONTRACT, "run_tests.sh": "true\n"},
                  [("read", "goal.md"), ("read", "contract.md"), ("write", "solution.py", "def f(x):\n    return 2 * x\n"),
                   ("bash", cmd, "FAIL x\nException: y\n")], final="All tests pass.")
    assert [(f["kind"], f.get("sub")) for f in ev["findings"] if f["kind"] == "test_claim"] == [("test_claim", "none")]


def test_v37_a_red_test_script_before_the_fix_is_not_an_ignored_failed_step(env):
    """審查 A9：測試腳本在修之前失敗、修完換個寫法再跑通過——和 pytest 一樣不算「失敗的步驟被略過」。"""
    ev = _v37_run(env, "Make run_tests.sh pass by writing solution.py.", {"run_tests.sh": "true\n"},
                  [("bash", "sh run_tests.sh", "FAIL check_01\n2 check(s) failed\n", True),
                   ("write", "solution.py", "def f(x):\n    return 2 * x\n"),
                   ("bash", "./run_tests.sh", "0 check(s) failed\n")], final="Done - all tests pass now.")
    assert ev["findings"] == []


def test_v37_a_not_after_the_file_name_does_not_drop_the_deliverable(env):
    ev = _v37_run(env, V37_PROMPT, {"goal.md": "# Goal\nx\n",
                                    "contract.md": "# Contract\n\nWrite your answer to `solution.py`, not to stdout.\n"},
                  [("read", "goal.md"), ("read", "contract.md")])
    assert _mo(ev) == ["solution.py"]


def test_v37_a_red_test_script_never_followed_by_a_green_run_is_still_a_failed_step(env):
    """全部豁免會少掉真的有問題的退回（R530 重播：7 格）；之後沒有一次綠的，照舊是「失敗的步驟被略過」。"""
    ev = _v37_run(env, "Make run_tests.sh pass by writing solution.py.", {"run_tests.sh": "true\n"},
                  [("bash", "sh run_tests.sh", "FAIL check_01\n2 check(s) failed\n", True),
                   ("write", "solution.py", "def f(x):\n    return 2 * x\n")], final="Done.")
    assert [f["kind"] for f in ev["findings"]] == ["failed_step"]


def test_direct_python_run_of_unittest_file_without_main_is_caught_as_failed_step(env):
    """e002 C 臂真實漏放（polyglot_py-pg_zipper-pi-C-r1）：
    測試檔定義了 unittest.TestCase 子類別但沒有 `unittest.main()`，agent 直接跑
    `python3 zipper_test.py`（未加 `-m unittest` 或 `pytest`）時，Python 只載入類別定義即結束、
    輸出為空且 exit 0（實際執行 0 個測試）。
    1) 單獨跑 `python3 zipper_test.py` 必須被抓為 `failed_step`（`sub="test_failed"`）並提示用 `-m unittest`；
    2) 先前若有真實測試失敗，後續跑 `python3 zipper_test.py`（空輸出）不得將先前的失敗洗白為「已通過」；
    3) 若最終訊息宣稱「All tests passed」，`_test_claim` 也必須判為 `sub="failed"` 而非 `unreadable`。"""
    unittest_no_main = (
        "import unittest\n"
        "from zipper import Zipper\n\n\n"
        "class ZipperTest(unittest.TestCase):\n"
        "    def test_ basic(self):\n"
        "        self.assertEqual(1, 1)\n"
    ).replace("test_ basic", "test_basic")
    # 1) 如同 pg_zipper：讀檔 → 寫 zipper.py → 跑 `python3 zipper_test.py` 空輸出 → 收工
    ev1 = _v37_run(
        env / "c1",
        "Read goal.md and implement zipper.py.",
        {"goal.md": "# Goal\nImplement Zipper in `zipper.py`.\n",
         "zipper.py": "class Zipper:\n    pass\n",
         "zipper_test.py": unittest_no_main},
        [("read", "goal.md"),
         ("read", "zipper_test.py"),
         ("write", "zipper.py", "class Zipper:\n    def value(self):\n        return 0\n"),
         ("bash", "python3 zipper_test.py", "")],
        final="Tests in `zipper_test.py` have been executed successfully.",
    )
    f1 = [f for f in ev1["findings"] if f["kind"] == "failed_step"]
    assert len(f1) == 1
    assert f1[0]["sub"] == "test_failed"
    assert "0 tests ran" in f1[0]["error"]
    assert "python3 -m unittest zipper_test.py" in f1[0].get("test_hint", "")

    # 2) 先前 `python3 -m unittest` 失敗，後面跑 `python3 zipper_test.py` 空輸出不得洗白
    ev2 = _v37_run(
        env / "c2",
        "Read goal.md and implement zipper.py.",
        {"goal.md": "# Goal\nImplement Zipper in `zipper.py`.\n",
         "zipper.py": "class Zipper:\n    pass\n",
         "zipper_test.py": unittest_no_main},
        [("read", "goal.md"),
         ("write", "zipper.py", "class Zipper:\n    def value(self):\n        return 0\n"),
         ("bash", "python3 -m unittest zipper_test.py",
          "FAIL: test_basic (zipper_test.ZipperTest)\nAssertionError: 0 != 1\n\nRan 1 test in 0.001s\n\nFAILED (failures=1)\n",
          True),
         ("bash", "python3 zipper_test.py", "")],
        final="Done.",
    )
    assert [f["kind"] for f in ev2["findings"]] == ["failed_step"]

    # 3) 最終訊息命中 CLAIMS（"All tests passed."）時，_test_claim 必須報 sub="failed"
    ev3 = _v37_run(
        env / "c3",
        "Read goal.md and implement zipper.py.",
        {"goal.md": "# Goal\nImplement Zipper in `zipper.py`.\n",
         "zipper.py": "class Zipper:\n    pass\n",
         "zipper_test.py": unittest_no_main},
        [("read", "goal.md"),
         ("write", "zipper.py", "class Zipper:\n    def value(self):\n        return 0\n"),
         ("bash", "python3 zipper_test.py", "")],
        final="All tests passed.",
    )
    assert [(f["kind"], f.get("sub")) for f in ev3["findings"]] == [("test_claim", "failed")]



def test_extract_test_hint_multiple_failures_priority(env):
    """紅燈（2026-10-30 e002 C 臂，審查指示 §四-4【P1】）：多個失敗測試且末尾測試斷言過長時，
    其餘失敗測試的名字不得被長斷言訊息擠出截斷窗口——agent 的前 120 字元必須看到它們，
    否則漏修其餘失敗目標。改之前：`(also failing: ...)` 附在長斷言之後，被 240 字元截斷掉。"""
    from vacant_network.trace.evidence import _extract_test_hint
    long_list = ", ".join(str(i) for i in range(40))
    out = (
        "======================================================================\n"
        "FAIL: test_alpha (mod.T.test_alpha)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        '  File "/app/mod_test.py", line 5, in test_alpha\n'
        "    self.assertEqual(a, b)\n"
        "AssertionError: 1 != 2\n"
        "----------------------------------------------------------------------\n"
        "FAIL: test_beta (mod.T.test_beta)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        '  File "/app/mod_test.py", line 9, in test_beta\n'
        "    self.assertEqual(a, b)\n"
        f"AssertionError: [{long_list}] != [{long_list}]\n"
        "----------------------------------------------------------------------\n"
        "Ran 2 tests in 0.001s\n"
        "\n"
        "FAILED (failures=2)\n"
    )
    hint = _extract_test_hint(out, err="FAILED (failures=2)")
    assert hint is not None
    assert hint.startswith("test_beta")          # 最後一個失敗測試仍為主體（相容舊行為）
    assert "AssertionError" in hint
    # 紅燈：其餘失敗測試名字必在前 120 字元內（改之前被長斷言擠出截斷窗口）
    assert "test_alpha" in hint[:120]


def test_extract_test_hint_pytest_multiple_failures_priority(env):
    """pytest 格式（`FAILED path::test_name - exc`）的多失敗前置紅燈（2026-10-30，審查指示 §四-4【P1】）：
    多個失敗且末尾測試斷言過長時，其餘失敗測試名字 `(also failing: ...)` 仍前置緊接於
    測試名稱之後，使真實 agent（pi／OpenCode）在前 120 字元內看到所有失敗測試名。"""
    from vacant_network.trace.evidence import _extract_test_hint
    long_list = ", ".join(str(i) for i in range(40))
    out = (
        "FAILED test_calc.py::test_alpha - AssertionError: 1 != 2\n"
        f"FAILED test_calc.py::test_beta - AssertionError: [{long_list}] != [{long_list}]\n"
    )
    hint = _extract_test_hint(out, err="2 failed")
    assert hint is not None
    assert hint.startswith("test_beta")          # 最後一個失敗測試仍為主體（相容舊行為）
    assert "also failing: test_alpha" in hint    # 其餘失敗名字緊接名稱之後、先於長斷言
    # 紅燈：其餘失敗測試名字必在前 120 字元內（長斷言不得把名字擠出截斷窗口）
    assert "test_alpha" in hint[:120]


def test_extract_test_hint_more_than_four_failures_count_summary(env):
    """>4 個其他失敗測試時給計數摘要而非逐一列名（2026-10-30，審查指示 §四-4【P1】）：
    6 個失敗測試（test_t1..test_t6）時，agent 須獲知「+5 other failing tests」概況，
    但不得因 5 個測試名字逐一列出而膨脹——hint 維持 ≤240 字元且格式不破損。"""
    from vacant_network.trace.evidence import _extract_test_hint
    out = "\n".join(
        f"FAILED test_calc.py::test_t{i} - AssertionError: {i} != {i + 1}" for i in range(1, 7)
    ) + "\n"
    hint = _extract_test_hint(out, err="6 failed")
    assert hint is not None
    assert hint.startswith("test_t6")                # 最後一個失敗測試仍為主體（相容舊行為）
    assert "+5 other failing tests" in hint          # len(others)==5 > 4 → 計數摘要分支
    assert len(hint) <= 240                          # 不膨脹、格式不破損


def test_extract_test_hint_unittest_more_than_four_failures_count_summary(env):
    """unittest 格式（`FAIL: name (module.Class)`）多失敗計數摘要（2026-10-30，審查指示 §四-4【P1】）：
    6 個失敗測試（test_u1..test_u6）時，agent 須獲知「+5 other failing tests」概況，
    且 hint 維持 ≤240 字元，避免真實 agent 被大量失敗訊息擠爆窗口。"""
    from vacant_network.trace.evidence import _extract_test_hint
    out = "\n".join([f"FAIL: test_u{i} (tests.TestClass)" for i in range(1, 7)]
                    + ["AssertionError: expected False got True"])
    hint = _extract_test_hint(out, "FAILED (failures=6)")
    assert hint is not None
    assert hint.startswith("test_u6")                # 最後一個失敗測試仍為主體（相容舊行為）
    assert "+5 other failing tests" in hint          # len(others)==5 > 4 → 計數摘要分支
    assert "AssertionError" in hint                  # 斷言訊息仍附帶
    assert len(hint) <= 240                          # 不膨脹窗口


def test_extract_test_hint_long_other_names_do_not_starve_assertion_and_pytest_full_output(env):
    """紅燈（2026-10-30 審查重現）：
    1) 真實 e002 C 臂 `polyglot_py-pg_poker-pi-C-r1` 有 4 個失敗測試且前 3 個名字極長（共 164 字元），
       `05ec4323` 將 `(also failing: ...)` 無上限塞在 `AssertionError` 之前，導致前綴吃掉 206 字元，
       把真正的斷言差異 `["4S 5H 5S 5D 5C"] != ["7S 8S 9S 6S 10S"]` 截斷成 `AssertionError: Lists diffe...`。
       修復後：前綴在超過預算時自動改用精簡附加（如 `also failing: <first>, +2 more`），既在前 120 字元保留失敗測試提示，
       又完整保留末尾測試的斷言差異值。
    2) 真實 `pytest` 輸出同時包含 `=== FAILURES ===`（`___ test_name ___` 與多行 `E   ` 斷言細節）與
       `=== short test summary info ===`（`FAILED file.py::test_name`，在 `-q` 或多行錯誤下不帶 `- exc`）時，
       不得因 summary 行覆蓋而遺失 `FAILURES` 區塊的 `AssertionError` 與 `E   ` 細節行，亦不得重複計入 `others`。
    """
    from vacant_network.trace.evidence import _extract_test_hint

    poker_out = (
        "======================================================================\n"
        "FAIL: test_aces_can_end_a_straight_10_j_q_k_a (poker_test.PokerTest)\n"
        "----------------------------------------------------------------------\n"
        'AssertionError: Lists differ: ["4S 5H 4C 8D 4H"] != ["10D JH QS KD AC"]\n'
        "======================================================================\n"
        "FAIL: test_aces_can_end_a_straight_flush_10_j_q_k_a (poker_test.PokerTest)\n"
        "----------------------------------------------------------------------\n"
        'AssertionError: Lists differ: ["4S 5H 4C 8D 4H"] != ["10S JS QS KS AS"]\n'
        "======================================================================\n"
        "FAIL: test_aces_cannot_be_in_the_middle_of_a_straight_flush_q_k_a_2_3 (poker_test.PokerTest)\n"
        "----------------------------------------------------------------------\n"
        'AssertionError: Lists differ: ["Q", "K"] != ["A", "2"]\n'
        "======================================================================\n"
        "FAIL: test_straight_flush_beats_four_of_a_kind (poker_test.PokerTest)\n"
        "----------------------------------------------------------------------\n"
        'AssertionError: Lists differ: ["4S 5H 5S 5D 5C"] != ["7S 8S 9S 6S 10S"]\n'
        "----------------------------------------------------------------------\n"
        "Ran 37 tests in 0.002s\n\n"
        "FAILED (failures=4)\n"
    )
    poker_hint = _extract_test_hint(poker_out, err="Command exited with code 1")
    assert poker_hint is not None
    assert poker_hint.startswith("test_straight_flush_beats_four_of_a_kind")
    assert "also failing:" in poker_hint[:120]
    assert '["4S 5H 5S 5D 5C"] != ["7S 8S 9S 6S 10S"]' in poker_hint
    assert len(poker_hint) <= 240

    pytest_q = (
        "=================================== FAILURES ===================================\n"
        "__________________________________ test_alpha __________________________________\n"
        "    def test_alpha():\n"
        ">       assert 1 == 2\n"
        "E       AssertionError: assert 1 == 2\n"
        "__________________________________ test_beta ___________________________________\n"
        "    def test_beta():\n"
        ">       assert [1, 2] == [1, 3]\n"
        "E       AssertionError: assert [1, 2] == [1, 3]\n"
        "E         At index 1 diff: 2 != 3\n"
        "=========================== short test summary info ============================\n"
        "FAILED test_sample.py::test_alpha\n"
        "FAILED test_sample.py::test_beta\n"
        "2 failed in 0.02s\n"
    )
    py_hint = _extract_test_hint(pytest_q, err="Command exited with code 1")
    assert py_hint is not None
    assert py_hint.startswith("test_beta (also failing: test_alpha):")
    assert "AssertionError: assert [1, 2] == [1, 3]" in py_hint
    assert "At index 1 diff: 2 != 3" in py_hint


def test_requested_outputs_ignores_hyphenated_slugs_and_tmp_path_fixtures(env):
    """紅燈（2026-10-30 審查重現，rounds 254–272 真實 dogfood 誤退）：
    1) 工單檔名 `P20261030_0650-4-record-e002-carm-failures-in-findings.md` 與
       `P20261030_1202-3-add-record-growth-point-dedup-and-prune-test-to-retention.md`
       內含 `-record-...-in-findings.md`／`-record-...-to-retention.md`，舊版 `OUTPUT_VERB`＋`OUTPUT_PREP`＋`FILE_LIKE`
       將連字號當成單字邊界且允許 0 空白與 `-` 開頭檔名，誤抽 `-findings.md` 與 `-retention.md` 為 `missing_output`。
    2) 測試工單指示「建立假實驗目錄 `exp_dir = tmp_path / "runs" / "exp_abs"`，寫入 `REPORT.json`」或
       「write `config.json` in `tmp_path`」時，屬於單元測試臨時目錄 fixture，不得誤判為工作區根目錄 `missing_output`。
    3) 當 repo 存在 `tests/fixtures/.../REPORT.json` 時，提示詞僅提及裸檔名 `REPORT.json`（不含路徑 `/`）
       不得被 `_materials_from_texts` 綁定至 `tests/fixtures/` 底下而誤報 `unread`。
    """
    files = {
        "ops/vlab/tools/holm_e002.py": "def main(argv=None):\n    return 0\n",
        "tests/test_vlab_tools.py": "def test_existing():\n    assert True\n",
        "tests/fixtures/holm_e002_absent_arm/REPORT.json": '{"paired": {}}\n',
    }
    a = Agent(_proj(env, files=files))
    a.ask(
        "處理工單 P20261030_0650-4-record-e002-carm-failures-in-findings.md 與 "
        "P20261030_1202-3-add-record-growth-point-dedup-and-prune-test-to-retention.md：\n"
        "1. 檢視 `ops/vlab/tools/holm_e002.py`，確保無 REPORT.json 時不會崩潰。\n"
        "2. 在 `tests/test_vlab_tools.py` 新增測試：建立假實驗目錄 `exp_dir = tmp_path / \"runs\" / \"exp_abs\"`，"
        "寫入 `REPORT.json`（內容為空 paired），並 write `extra.json` to `tmp_path / \"extra.json\"`。"
    )
    a.read("ops/vlab/tools/holm_e002.py")
    a.write(
        "tests/test_vlab_tools.py",
        "def test_existing():\n    assert True\n\n"
        "def test_new(tmp_path):\n"
        "    (tmp_path / 'REPORT.json').write_text('{}')\n",
    )
    a.bash("pytest tests/test_vlab_tools.py -q", "2 passed in 0.03s\n")
    ev = a.evidence("已完成測試並通過。")
    assert ev["requested_outputs"] == [], ev["requested_outputs"]
    assert "tests/fixtures/holm_e002_absent_arm/REPORT.json" not in ev["materials_named"]
    assert ev["findings"] == [], ev["findings"]


def test_ticket_block_and_handoff_tail_do_not_pollute_materials_or_outputs(env):
    """紅燈（2026-10-30 審查重現，rounds 258–272 自產自續誤退環）：
    當提示詞包含 `===== 工單 ... ===== ... ===== 工單結束 =====`（或末尾附帶 `本機 CI（三個分支 HEAD...`、
    `上一輪交接（STATE.md 尾端）：` 以及工單末尾 `---\\n結果：...\\n## redo ...` 歷史紀錄）時，
    `_materials_from_texts` 與 `requested_outputs` 僅能針對當前任務本體提取點名檔案與要求輸出，
    不得將 `STATE.md` 尾端或 CI 狀態列出的他輪檔案（如 `vacant_network/retention.py`、`vacant_network/trace/evidence.py`）
    當成當前任務必讀素材而觸發 `unread` 退回。
    """
    files = {
        "ops/vlab/tools/holm_e002.py": "def main(argv=None):\n    return 0\n",
        "tests/test_vlab_tools.py": "def test_one():\n    assert True\n",
        "vacant_network/retention.py": "DEFAULT_TRACE_BUDGET_BYTES = 64 * 1024 * 1024\n",
        "tests/test_retention.py": "def test_ret():\n    assert True\n",
        "vacant_network/trace/evidence.py": "# evidence checker\n",
    }
    a = Agent(_proj(env, files=files))
    a.ask(
        "這一輪只做下面這張工單，不做別的事。\n\n"
        "===== 工單 /home/user1/dev/ops/tickets/qwen/doing/P20261030_1301-3.md =====\n"
        "# 新增 holm_e002 測試\n"
        "- 位置：`ops/vlab/tools/holm_e002.py` 與 `tests/test_vlab_tools.py`\n"
        "- 步驟：檢視 `ops/vlab/tools/holm_e002.py`，在 `tests/test_vlab_tools.py` 補測試。\n"
        "---\n"
        "結果：commit 43aca726\n"
        "## redo 270-r1 回應\n"
        "- 點名檔 `vacant_network/retention.py` 與 `tests/test_retention.py` 屬上輪語彙，寫入 `handoff_ghost.md` 非本單要求。\n"
        "===== 工單結束 =====\n\n"
        "[第 270 輪；2026-10-30 13:18:00]\n"
        "本機 CI（三個分支 HEAD；合併規則見 ASSIGNMENT「合併前看 CI」）：\n"
        "🔴 auto/worker 30c5c4da：失敗：tests/test_retention.py::test_usage_report\n\n"
        "上一輪交接（STATE.md 尾端）：\n"
        "## round 269-r1 · 實證：已開啟 vacant_network/trace/evidence.py、vacant_network/retention.py 與 tests/test_retention.py，寫入 ghost_out.json。\n"
    )
    a.read("ops/vlab/tools/holm_e002.py")
    a.read("tests/test_vlab_tools.py")
    a.write("tests/test_vlab_tools.py", "def test_one():\n    assert True\n\ndef test_two():\n    assert True\n")
    a.bash("pytest tests/test_vlab_tools.py -q", "2 passed in 0.02s\n")
    ev = a.evidence("已完成工單測試。")
    assert ev["materials_named"] == ["ops/vlab/tools/holm_e002.py", "tests/test_vlab_tools.py"]
    assert ev["requested_outputs"] == []
    assert ev["findings"] == [], ev["findings"]


def test_runners_only_match_command_position_not_printf_or_git_commit(env):
    """紅燈（2026-10-30 審查重現，round 271-r1 seq 5744 誤判與漏報）：
    `RUNNERS` 只認殼層分段命令位置（含 `.venv/bin/python -m pytest`、`uv run pytest`、`bash -lc "pytest"` 等），
    不認 `printf`、`echo`、`git commit -m`、`grep` 參數文字中出現的 `pytest`/`unittest`：
    1) 跑 `pytest` 失敗後，若只跑了 `printf "...pytest..."` 或 `git commit -m "...pytest..."`（exit 0），
       不得將其當成「後續測試已通過」而吞掉 `failed_step`（`sub="test_failed"`）與 `test_claim`（`sub="failed"`）。
    2) 跑 `.venv/bin/python -m pytest` 通過後，若後續 `printf "...pytest..." && git add ...` 因 git 報錯退出，
       不得將該非測試指令誤判為 `failed_step`（`sub="test_failed"`）。
    """
    a1 = Agent(_proj(env, name="p_fn", files={"solution.py": "def add(a, b): return 0\n"}))
    a1.ask("Fix solution.py so pytest passes.")
    a1.write("solution.py", "def add(a, b): return a - b\n")
    a1.bash(
        "pytest -q",
        "FAILED test_sol.py::test_add - AssertionError: assert -1 == 3\n1 failed in 0.02s\n",
        error=True,
    )
    a1.bash('printf "updated pytest case\\n" >> notes.txt && git commit -m "wip pytest"', "ok\n")
    ev_claim = a1.evidence("All tests now pass.")
    assert any(f["kind"] == "test_claim" and f.get("sub") == "failed" for f in ev_claim["findings"]), ev_claim["findings"]
    ev_noclaim = a1.evidence("Done.")
    assert any(f["kind"] == "failed_step" and f.get("sub") == "test_failed" for f in ev_noclaim["findings"]), ev_noclaim["findings"]

    a2 = Agent(_proj(env, name="p_fp", files={"solution.py": "def add(a, b): return 0\n"}))
    a2.ask("Fix solution.py so pytest passes.")
    a2.write("solution.py", "def add(a, b): return a + b\n")
    a2.bash(".venv/bin/python -m pytest -q", "1 passed in 0.02s\n")
    a2.bash('printf "pytest --basetemp ran ok\\n" >> notes.txt && git -C Vacant add ops/tickets/done.md', "fatal: pathspec outside repo\n", error=True)
    ev_fp = a2.evidence("All tests now pass.")
    assert not any(f["kind"] == "failed_step" for f in ev_fp["findings"]), ev_fp["findings"]


