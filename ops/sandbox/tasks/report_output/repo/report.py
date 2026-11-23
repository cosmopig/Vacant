import json


def render_report(expenses):
    return '# Expenses\n'


if __name__ == '__main__':
    with open('expenses.json') as stream:
        expenses = json.load(stream)
    with open('REPORT.md', 'w') as stream:
        stream.write(render_report(expenses))
