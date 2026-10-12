import json, lzma, re, collections
from scorer import question_scorer

ROWS = json.load(lzma.open('/tmp/claude-0/review_effect/mechanism/runs_turns.json.xz', 'rt'))
NUM = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
WRITE_RE = re.compile(r"answer\.txt")

def outcome(r):
    if r['reward'] == 1:
        return 'right'
    return 'missing' if r['answer_file'] is False else 'wrong'

def ans_kind(exp):
    e = (exp or '').strip()
    if e.lower() in ('yes', 'no', 'not applicable', ''):
        return 'trivial'
    if ',' in e or ';' in e:
        return 'list'
    if re.fullmatch(r"-?[\d.,]+%?", e):
        # distinctive if >=3 significant digits
        digits = re.sub(r"[^\d]", "", e).lstrip('0')
        return 'num' if len(digits) >= 3 else 'smallnum'
    return 'str'

def contains_correct(text, exp, kind=None):
    """Does text contain a token the scorer accepts as exp? Only for distinctive kinds."""
    kind = kind or ans_kind(exp)
    if not text:
        return False
    if kind in ('num',):
        for m in NUM.finditer(text):
            tok = m.group(0)
            try:
                if question_scorer(tok, exp):
                    return True
            except Exception:
                pass
        return False
    if kind == 'str':
        return re.search(r"(?<!\w)" + re.escape(exp.strip().lower()) + r"(?!\w)", text.lower()) is not None
    if kind == 'list':
        items = [x.strip().lower() for x in re.split(r"[,;]", exp) if x.strip()]
        tl = text.lower()
        return bool(items) and all(re.search(r"(?<!\w)" + re.escape(i) + r"(?!\w)", tl) for i in items)
    return False

def write_turns(r):
    """turns in which answer.txt was written (write tool or bash redirect)."""
    out = []
    for t in r['turns'] or []:
        for c in t['calls']:
            a = c.get('args') or {}
            if c['name'] in ('write', 'edit') and str(a.get('path') or a.get('file_path') or '').endswith('answer.txt'):
                out.append(t['i'])
            elif c['name'] == 'bash' and re.search(r"(>>?|tee( -a)?)\s*['\"]?(/app/)?answer\.txt|answer\.txt['\"]?\s*,\s*['\"][wa]", str(a.get('command') or '')):
                out.append(t['i'])
    return out

def nudge_turns(r):
    return [t['i'] for t in r['turns'] or [] if any(e['type'] == 'vacant-budget' for e in t['entries'])]

def real_turns(r):
    ts = r['turns'] or []
    # drop synthetic error turn after abort (no calls, no text, stop == error) at the end
    n = len(ts)
    if n and ts[-1]['stop'] in ('error', 'aborted') and not ts[-1]['calls'] and not ts[-1]['text'].strip():
        n -= 1
    return n

def _decs(s):
    s = s.replace(',', '').rstrip('%')
    return len(s.split('.')[1]) if '.' in s else 0

def contains_correct_strict(text, exp, kind=None):
    kind = kind or ans_kind(exp)
    if not text:
        return False
    if kind == 'num':
        ed = _decs(exp.strip())
        for m in NUM.finditer(text):
            tok = m.group(0)
            try:
                if _decs(tok) >= ed and question_scorer(tok, exp):
                    return True
            except Exception:
                pass
        return False
    return contains_correct(text, exp, kind)
