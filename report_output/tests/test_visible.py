from report import render_report

def test_heading():
    assert render_report({}).startswith('# Expenses\n')
