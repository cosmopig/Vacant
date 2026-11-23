from pathlib import Path
import re


SANDBOX = Path(__file__).resolve().parents[1] / 'ops/sandbox'


def prompt(text, heading):
    return re.search('### ' + heading + r'\n\n```text\n(.*?)\n```', text, re.S).group(1)


def test_v4_prompts_preserve_v3_text_and_approved_arm_instructions():
    text = (SANDBOX / 'DEVIN_ARMS.md').read_text()
    plain = prompt(text, 'V3 plain').replace('kit-v3', 'kit-v4').replace('sandbox-v3/', 'sandbox-v4/').replace('/v3/', '/v4/')
    assert prompt(text, 'V4 plain') == prompt(text, 'V4 plain2') == plain
    assert prompt(text, 'V4 calibration') == plain.replace(
        'sandbox-devin/v4/<id>-<arm>-s<k>', 'sandbox-devin-cal4/<id>-plain')
    arm = "Before delivering, write at least one test that reproduces the issue (it must fail on the original code and pass with your fix) inside the `<id>/` test suite, and list its pytest node IDs, one per line, in `<id>/VACANT_TESTS.txt`. Then create the kit-root `.venv` with Vacant as the README says and submit through the gate with the README's `vacant run` command from inside `<id>/` (`--suite ../gates/<id>`, `--run-dir ../receipts/<id>-N`, N = 1, 2, 3, timeout from `../gates/<id>/selection.json`). Exit 0 means accepted. Exit 20 means refused: read its feedback, fix, and submit again, at most 3 submissions. Do not edit `gates/`. Include each submission's raw gate output in your reply."
    assert prompt(text, 'V4 vacant') == plain.replace('Do not open `gates/`.', arm)
    for heading in ('V4 calibration', 'V4 plain', 'V4 plain2', 'V4 vacant'):
        assert 'Do not open a pull request; the pushed branch is the only deliverable.' in prompt(text, heading)


def test_v4_calibration_clearance_defers_to_complete_audits_and_conservative_count():
    dispatch = (SANDBOX / 'DEVIN_ARMS.md').read_text().split('## V4 SWE-bench', 1)[1]
    prereg = (SANDBOX / 'PREREG.md').read_text().split('## v4 bank', 1)[1]
    assert 'Calibration clearance defers to the v4 rule in `PREREG.md`:' in dispatch
    start = 'is only the whole-bank gate; it never enters comparisons. Apply it only when'
    end = 'never salvage a subset or change the threshold.'
    actual = dispatch.split(start, 1)[1].split(end, 1)[0]
    expected = prereg.split(start, 1)[1].split(end, 1)[0]
    assert ' '.join(actual.split()) == ' '.join(expected.split())
