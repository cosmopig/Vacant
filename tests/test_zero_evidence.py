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
