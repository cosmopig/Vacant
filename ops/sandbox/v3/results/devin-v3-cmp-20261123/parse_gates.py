"""Extract reply-reported gate outputs, not independently verified receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import re

UNKNOWN = 'UNKNOWN'
EVENT = re.compile(r'^\[devin\]\s+@\s+\d+\s+\((event-[^)]+)\)\s*\n', re.M)
VERDICT = re.compile(r'^\[vacant run\].*(?:交付（visible_pass）|拒交（visible_fail）).*$', re.M)


def assistant_events(row):
    events = {}
    text = row.get('messages', '')
    matches = list(EVENT.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        events[match[1]] = (text[match.end():end], 'messages')
    final = row.get('final_reply', '')
    if 'contents: ' in final:
        message = json.loads(final.split('contents: ', 1)[1])['message']
        match = re.search(r'--- (event-\S+) ---', final)
        event_id = match[1] if match else 'final_reply'
    else:
        message, event_id = final, 'final_reply'
    if len(message) > len(events.get(event_id, ('', ''))[0]):
        events[event_id] = (message, 'final_reply.contents.message')
    return events


def parse_cell(row):
    events = assistant_events(row)
    outputs = {}
    for event_id, (body, source) in events.items():
        for match in VERDICT.finditer(body):
            ordinals = list(re.finditer(r'\bsubmission\s+(\d+)\b', body[:match.start()], re.I))
            ordinal = int(ordinals[-1][1]) if ordinals else UNKNOWN
            start = body.rfind('\n', 0, ordinals[-1].start()) + 1 if ordinals else match.start()
            end = body.find('\n```', match.end())
            end = end if end >= 0 else match.end()
            excerpt = body[start:end]
            codes = {int(code) for code in re.findall(r'\bexit(?:\s+code)?\s*(?:=|:)?\s*(-?\d+)\b', excerpt, re.I)}
            exit_code = next(iter(codes)) if len(codes) == 1 else UNKNOWN
            item = dict(number=ordinal, exit_code=exit_code,
                        verdict='accepted' if 'visible_pass' in match[0] else 'refused',
                        raw_verdict_line=match[0], event_id=event_id, source=source,
                        source_line=body.count('\n', 0, start) + 1, excerpt=excerpt)
            key = ordinal, match[0]
            if key not in outputs or len(excerpt) > len(outputs[key]['excerpt']):
                outputs[key] = item
    submissions = sorted(outputs.values(), key=lambda x: (x['number'] == UNKNOWN, str(x['number'])))
    numbers = [item['number'] for item in submissions]
    complete_numbering = bool(numbers) and numbers == list(range(1, len(numbers) + 1))
    count = len(submissions) if complete_numbering else UNKNOWN
    body = '\n'.join(text for text, _ in events.values())
    never = bool(re.search(r"(?:never ran|did not run|didn't run) (?:the )?(?:Vacant )?gate", body, re.I))
    return dict(branch=row['branch'], session_id=row['session_id'],
                number_of_submissions=count, submissions=submissions,
                final_gate_verdict=submissions[-1]['verdict'] if complete_numbering else UNKNOWN,
                gate_never_run=False if submissions else True if never else UNKNOWN,
                receipt_verification=UNKNOWN, complete_execution_history=UNKNOWN,
                gate_to_final_handback_binding=UNKNOWN)


def parse_export(path):
    data = Path(path).read_bytes()
    rows = json.loads(data)
    if len({row['branch'] for row in rows}) != len(rows):
        raise ValueError('duplicate session branch')
    return dict(source_sha256=hashlib.sha256(data).hexdigest(),
                measurement='Reply-reported/pasted stdout; not independent receipt verification. '
                            'Repeated messages are deduplicated; 1/1 次 is not a submission count. '
                            'Unknown or unshown execution history remains UNKNOWN.',
                cells=[parse_cell(row) for row in sorted(rows, key=lambda x: x['branch'])])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    print(json.dumps(parse_export(parser.parse_args().export), indent=2, ensure_ascii=False))
