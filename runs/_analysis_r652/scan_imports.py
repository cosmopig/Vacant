import json, ast, sys, collections
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
sys.path.insert(0, 'ops/gain')
from gain_run import extract_code, _GAIN_ALLOWED_IMPORTS

WL = set(_GAIN_ALLOWED_IMPORTS)
cands = []
for l in open('runs/g_r443_gemma_lcb/calls.jsonl'):
    d = json.loads(l)
    if d.get('role') not in ('gen', 'revise'):
        continue
    if not d.get('ok') or not d.get('response'):
        continue
    m = d.get('meta') or {}
    code = extract_code(d['response'])
    cands.append({'arm': m.get('arm'), 'task_id': m.get('task_id'),
                  'role': d['role'], 'agent': d.get('agent_id'), 'code': code})

def imports_of(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # third category
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names: mods.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            if n.module and n.level == 0: mods.add(n.module.split('.')[0])
    return mods

outside = collections.Counter()
syntax_err = 0
per_arm = collections.defaultdict(lambda: {'n':0,'blocked':0,'syn':0})
for c in cands:
    mods = imports_of(c['code'])
    a = per_arm[c['arm']]; a['n'] += 1
    if mods is None:
        syntax_err += 1; a['syn'] += 1; c['blocked'] = None; continue
    ext = mods - WL
    c['blocked'] = sorted(ext)
    if ext:
        a['blocked'] += 1
        for m in ext: outside[m] += 1

print('候選碼總數 (gen+revise, ok):', len(cands))
print('語法解析失敗（第三類）:', syntax_err)
print()
print('=== 白名單外的 import，出現次數 ===')
for m, n in outside.most_common(40):
    print('  %-22s %d' % (m, n))
print()
print('=== 分臂 ===')
print('%-6s %6s %9s %6s' % ('arm', 'cands', 'blocked', 'syn'))
for arm, a in sorted(per_arm.items()):
    print('%-6s %6d %9d %6d' % (arm, a['n'], a['blocked'], a['syn']))
json.dump(cands, open('/dev/shm/r652/cands.json', 'w'))
