"""Which benchmark instructions does Vacant's requested-output detector (same regexes as
evidence.requested_outputs / budget.missing_outputs) recognise? Text-only replica (no workspace mapping)."""
import sys, pathlib, re, glob
sys.path.insert(0, '/home/user/Vacant')
from vacant_network.trace.evidence import OUTPUT_VERB, OUTPUT_PREP, OUTPUT_LABEL, FILE_LIKE, CLAIMS, RUNNERS
S = '/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad'
H = S + '/study/src/harbor'
def found(text):
    out = []
    for m in OUTPUT_VERB.finditer(text):
        window = text[m.end(): m.end() + 140].split("\n\n")[0]
        for pm in OUTPUT_PREP.finditer(window):
            tok = pm.group(1).strip("`\"'").rstrip(".,;:!?")
            if FILE_LIKE.match(tok):
                out.append(tok); break
    for m in OUTPUT_LABEL.finditer(text):
        tok = m.group(1).strip("`\"'").rstrip(".,;:!?")
        if FILE_LIKE.match(tok):
            out.append(tok)
    return list(dict.fromkeys(out))
cases = {}
cases['dabstep-23'] = pathlib.Path(S + '/dabstep_pinned/formal/dabstep-23/instruction.md').read_text()
lcb_tail_fn = ('=== YOUR TASK ===\nComplete the Solution class in the starter code to solve the problem.\n'
  'You must use tools to create a file "solution.py" and save your solution class to that file.\n'
  "Test your solution.py iteratively with a program called check_solution.py under the same directory, and iterate until it's correct.\n"
  'There is a time limit on each test case, so be careful about the efficiency of your solution.\n'
  '\n=== STEP GUIDE ===\n1. Understand the problem and the starter code.\n2. Create a file "solution.py" in the current directory.\n'
  "3. Run 'python check_solution.py' to test your solution with sample test cases.\n4. If tests fail, analyze the errors and update your solution.py file.\n5. Repeat steps 3-4 until all sample tests pass.\n")
cases['lcb(functional template tail)'] = lcb_tail_fn
for p in glob.glob('/root/.cache/harbor/tasks/*/*/instruction.md'):
    n = p.split('/')[-2]
    if not n.startswith('dabstep'):
        cases['cached:' + n] = pathlib.Path(p).read_text()
for p in sorted(glob.glob(S + '/study/src/terminal-bench-2-0-sample/sample/*/instruction.md')):
    cases['tb2:' + p.split('/')[-2]] = pathlib.Path(p).read_text()
cases['quixbugs(template, output_name=fixed_x.py)'] = pathlib.Path(H + '/adapters/quixbugs/src/quixbugs/task-template/instruction.md').read_text().replace('{program_name}', 'bitcount').replace('{ext}', 'py').replace('{output_name}', '/app/fixed_bitcount.py')
cases['aider_polyglot(tail, files=two_fer.py)'] = ('Some exercise text.\n\n----\nUse the instructions above to modify the supplied files: two_fer.py\n'
  "Don't change the names of existing functions or classes, as they may be referenced from other code like unit tests.\nOnly use standard libraries; don't install additional packages.")
for k, t in cases.items():
    print(f"{k:55s} -> {found(t)}")
