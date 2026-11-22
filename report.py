import json


def render_report(expenses):
    lines = ['# Expenses']
    lines.extend(f'- {category}: {cents}' for category, cents in sorted(expenses.items()))
    lines.append(f'Total: {sum(expenses.values())} cents')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    with open('expenses.json') as stream:
        expenses = json.load(stream)
    with open('REPORT.md', 'w') as stream:
        stream.write(render_report(expenses))
