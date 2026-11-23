from pathlib import Path
from report import render_report

def test_report():
    assert render_report({'z': 0, 'a': -20}) == '# Expenses\n- a: -20\n- z: 0\nTotal: -20 cents\n'
    assert render_report({}) == '# Expenses\nTotal: 0 cents\n'
    assert Path('REPORT.md').read_text() == '# Expenses\n- food: 1250\n- travel: 800\nTotal: 2050 cents\n'
