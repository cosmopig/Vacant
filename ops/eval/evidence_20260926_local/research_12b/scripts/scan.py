import json, re, pathlib, collections, sys
D = pathlib.Path('/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/analysis_runs')
idx = {r['file']: r for r in json.load(open(D/'index.json'))}

def parse(path):
    turns = []  # list of (turn, [(call, result)])
    cur = None
    lines = path.read_text().splitlines()
    i = 0
    mode = None
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^## Turn (\d+) ', ln)
        if m:
            cur = {'turn': int(m.group(1)), 'calls': []}
            turns.append(cur); i += 1; continue
        if ln.startswith('## Verifier'):
            break
        if cur is not None and ln.startswith('call '):
            call = ln
            res = []
            j = i + 1
            if j < len(lines) and lines[j].startswith('result: '):
                res.append(lines[j][8:])
                j += 1
                while j < len(lines) and (lines[j].startswith('        ') or lines[j] == ''):
                    if lines[j] == '' and j+1 < len(lines) and not lines[j+1].startswith('        '):
                        break
                    res.append(lines[j].strip()); j += 1
            cur['calls'].append((call, '\n'.join(res).strip()))
            i = j; continue
        i += 1
    return turns

def strip_comments(call):
    # remove bash comment lines inside the JSON command string
    try:
        name, js = call.split(': ', 1)
        a = json.loads(js)
        if 'command' in a:
            cmd = '\n'.join(l for l in a['command'].split('\n') if not l.strip().startswith('#')).strip()
            return name + ':' + cmd
    except Exception:
        pass
    return call

def empty(res):
    r = res.strip()
    return r == '' or r.startswith('[ERROR] (no output)') or r == '(no output)' or r.startswith('No matches') or r == '0'

rows = []
for f in sorted(idx):
    r = idx[f]
    turns = parse(D/f)
    seen = collections.Counter()
    seen_nc = collections.Counter()
    first_rep2 = first_rep3 = None
    first_rep2_nc = None
    empties = 0; max_consec_empty = 0; consec = 0; first_empty3 = None
    for t in turns:
        for call, res in t['calls']:
            key = (call, res)
            seen[key] += 1
            if seen[key] == 2 and first_rep2 is None: first_rep2 = t['turn']
            if seen[key] == 3 and first_rep3 is None: first_rep3 = t['turn']
            k2 = (strip_comments(call), res)
            seen_nc[k2] += 1
            if seen_nc[k2] == 2 and first_rep2_nc is None: first_rep2_nc = t['turn']
            if empty(res):
                consec += 1; empties += 1
                if consec >= 3 and first_empty3 is None: first_empty3 = t['turn']
            else:
                consec = 0
            max_consec_empty = max(max_consec_empty, consec)
    rows.append((f, r['arm'], int(r['reward']), r['answer_file'], r['turns'], first_rep2, first_rep2_nc, first_rep3, first_empty3, max_consec_empty))

print('file'.ljust(24), 'arm rew file turns rep2 rep2nc rep3 empty3 maxEmptyRun')
for row in rows:
    print(row[0].ljust(24), row[1].ljust(3), row[2], 'F' if row[3] else '-', str(row[4]).rjust(3), *(str(x).rjust(5) for x in row[5:]))
json.dump(rows, open('/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/loopscan/rows.json','w'))
