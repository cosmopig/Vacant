"""單人內配對摘要（20260925 評測邊界）：描述小樣本，不把相關當成效裁決。"""

import argparse
import json
import math
import re
from pathlib import Path


def manifest():
    raw = (Path(__file__).parent / 'app/cases.js').read_text()
    return json.loads(raw.removeprefix('window.RELIANCE_CASES = ').removesuffix(';\n'))


def sign_test(diffs):
    """雙尾 exact sign test；同分不進二項分母，不需額外套件。"""
    nonzero = [d for d in diffs if abs(d) > 1e-12]
    n = len(nonzero)
    if not n:
        return 1.0, 0
    k = min(sum(d > 0 for d in nonzero), sum(d < 0 for d in nonzero))
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n), n


def validate(export, bank):
    if not isinstance(export, dict):
        raise ValueError('export must be a JSON object')
    if export.get('schema_version') != 1 or export.get('case_version') != bank['version']:
        raise ValueError('unsupported schema/case version')
    pid = export.get('participant_id', '')
    if not re.fullmatch(r'[\w-]{1,100}', pid):
        raise ValueError('invalid participant_id')
    if not isinstance(export.get('seed'), int) or isinstance(export['seed'], bool):
        raise ValueError('missing integer participant seed')
    responses = export.get('responses', [])
    if not isinstance(responses, list) or any(not isinstance(r, dict) or 'case_id' not in r for r in responses):
        raise ValueError('responses must be objects with case_id')
    if len(responses) != 8 or len({r['case_id'] for r in responses}) != 8:
        raise ValueError('need 8 distinct completed responses')
    cases = {c['id']: c for c in bank['cases']}
    stats = {}
    for condition in ('record', 'plain'):
        rows = [r for r in responses if r.get('condition') == condition]
        if len(rows) != 4:
            raise ValueError('need 4 responses in each condition')
        for r in rows:
            if r['case_id'] not in cases or r.get('reward') != cases[r['case_id']]['reward']:
                raise ValueError('case/reward does not match archive-derived manifest')
            if r.get('decision') not in ('accept', 'reject'):
                raise ValueError('invalid decision')
            if not isinstance(r.get('confidence'), (int, float)) or not 50 <= r['confidence'] <= 100:
                raise ValueError('confidence outside 50–100')
            time = r.get('time_ms')
            if not isinstance(time, (int, float)) or not math.isfinite(time) or time < 0:
                raise ValueError('invalid decision time')
        wrong = [r for r in rows if r['reward'] == 0]
        if len(wrong) != 2:
            raise ValueError('need 2 wrong and 2 right per condition')
        stats[condition] = dict(
            accuracy=sum((r['decision'] == 'accept') == bool(r['reward']) for r in rows) / 4,
            accepted_wrong=sum(r['decision'] == 'accept' for r in wrong) / len(wrong))
    return dict(id=pid, synthetic=export.get('synthetic') is True, **stats)


def aggregate(exports):
    bank = manifest()
    rows = [validate(e, bank) for e in exports]
    if not rows:
        raise ValueError('no exported JSON files')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate participant_id; refusing to double-count')
    if len({r['synthetic'] for r in rows}) != 1:
        raise ValueError('do not mix synthetic and participant exports')
    label = '合成測試資料（非真人結果）' if rows[0]['synthetic'] else '探索性真人匯出（未驗證參與者身分）'
    lines = ['# 可究責性小實驗：單人內配對', '', label,
             '', '| participant | 紀錄正確率 | 無紀錄正確率 | 差（百分點） | 紀錄收下錯答率 | 無紀錄收下錯答率 | 差（百分點） |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        a, b = r['record'], r['plain']
        lines.append(f'| {r["id"]} | {a["accuracy"]:.0%} | {b["accuracy"]:.0%} | '
                     f'{100*(a["accuracy"]-b["accuracy"]):+.1f} | {a["accepted_wrong"]:.0%} | '
                     f'{b["accepted_wrong"]:.0%} | {100*(a["accepted_wrong"]-b["accepted_wrong"]):+.1f} |')
    lines += ['', f'參與者數 n={len(rows)}；差值一律為「加看紀錄 − 只看說法」。',
              '正確率分母各 4；收下錯答率分母各 2 份錯誤交件（越低越好）。', '']
    for metric, name in [('accuracy', '正確率'), ('accepted_wrong', '收下錯答率')]:
        diffs = [r['record'][metric] - r['plain'][metric] for r in rows]
        p, n = sign_test(diffs)
        lines.append(f'- {name}：平均配對差 {100*sum(diffs)/len(diffs):+.1f} 百分點；'
                     f'雙尾 exact sign test p={p:.6g}，非同分 n={n}，同分 {len(rows)-n}。')
    lines += ['', '小樣本、固定挑選題庫、回合揭曉造成學習效應；未校正案例／模型差異或多重比較。',
              '每人隨機分派但看的不是同一批案例；僅作探索，不推廣到一般任務。重複身分以 participant_id 擋，不保證同一人未重做。']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        result = aggregate([json.loads(p.read_text()) for p in sorted(args.folder.glob('*.json'))])
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    if args.out:
        args.out.write_text(result)
    else:
        print(result, end='')
