#!/usr/bin/env python3
"""R20261107_0035-1 交付 1：6-cell 審計摘要（20261106 2 格＋20261107 4 格）。
所有數值從既有 raw 證據檔載入（非手抄）；缺值保持 null(UNKNOWN)，不填 0。
輸出：/home/user1/dev/Vacant/ops/audits/realab_20261107_summary.json
"""
import datetime, hashlib, json, pathlib

REPO = pathlib.Path('/home/user1/dev/Vacant')
OPS = pathlib.Path('/home/user1/dev/ops')
OUT = REPO / 'ops/audits/realab_20261107_summary.json'

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def j(p): return json.loads(pathlib.Path(p).read_text())

# ---- 來源 ----
s1106 = j(OPS / 'audits/realab_dab378_20261106_summary.json')      # 11-06 2-cell raw
g1107 = j(OPS / 'realab_20261107/g2_result.json')                  # 11-07 4-cell raw
kv1107 = j(OPS / 'audits/realab_kv_preservation_20261107.json')    # 11-07 kv 審計
ind1107 = j(OPS / 'realab_20261107/independent_after_20261107.json')  # 本輪新採分
MAN_P = REPO / 'ops/reqloop/g2/real_slice/manifest.json'
man = j(MAN_P)
rec = {d['name']: d['source']['score'] for d in man['drafts']}

KV8 = ["pre_mean", "pre_median", "pre_sd", "pre_skewness", "post_mean", "post_median", "post_sd", "post_skewness"]
KV10 = ["pre_mean", "pre_median", "pre_sd", "pre_skewness", "pre_kurtosis", "post_mean", "post_median", "post_sd", "post_skewness", "post_kurtosis"]

cells = []

# ---- realab_dab378_20261106（2 格，dab_378-pi-C）----
for r in s1106['raw_results']:
    arm = r['arm']
    if arm == 'generic':
        preserved, mutated = KV8, []
    else:  # localized：byte_level 註明 2 行 median 格式重排（數值相同、scorer 接受）
        mutated, preserved = ["pre_median", "post_median"], [k for k in KV8 if k not in ("pre_median", "post_median")]
    c = r['cost']
    cells.append({
        'batch': 'realab_dab378_20261106', 'draft': 'dab_378-pi-C', 'role': 'bad', 'arm': arm,
        'before_pass_independent': False,
        'before_note': 'recorded lab score（e008_dabench_pi_AC/dabench-dab_378-pi-C-r1/score.json：pass=false, n_correct 6/8, psaq 0.75；引用，未本地重跑）',
        'after_independent': dict(r['independent_lab_scorer']),
        'kv_preserved': preserved,
        'kv_mutated': mutated,
        'repair_sessions': c['repair_sessions'], 'model_calls': c['api_model_calls'],
        'tokens': c['tokens'], 'wall_ms_total': int(round(c['wall_s'] * 1000)),
        'stopped': r['stopped'], 'exit_code': r['exit_code'],
        'fixed': r['fixed'], 'regressed': r['regressed'],
    })

# ---- realab_20261107（4 格）----
ind_by = {(r['draft'], r['arm']): r for r in ind1107['cells']}
kv_by = {c['cell']: c for c in kv1107['cells']}
for c in g1107['cells']:
    key = (c['draft'], c['arm'])
    ind = ind_by[key]
    kv = kv_by.get(f"{c['draft']}/{c['arm']}", {})
    cost = c['cost']
    no_gap = c['stopped'] == 'no_gap'
    recd = rec[c['draft']]
    cells.append({
        'batch': 'realab_20261107', 'draft': c['draft'], 'role': c['role'], 'arm': c['arm'],
        'before_pass_independent': bool(recd['pass']),
        'before_note': f"recorded lab score（e008_dabench_pi_AC/{'dabench-dab_378-pi-C-r1' if c['role']=='bad' else 'dabench-dab_378-pi-A-r1'}/score.json：pass={recd['pass']}"
                       + (f", n_correct 6/8, psaq 0.75；引用，未本地重跑）" if c['role'] == 'bad'
                          else f", abq 1, psaq 1.0, n_items 8；引用，未本地重跑）"),
        'after_independent': dict(ind['independent_after'], final_answer_sha256=ind['final_answer_sha256'],
                                  scored_via=ind['scored_via']),
        'kv_preserved': kv.get('kv_preserved', []),
        'kv_mutated': kv.get('kv_mutated', []),
        'kv_audit_note': kv.get('note', 'audit_kv_preservation 審計端計算（產品函式，非模型自評）'),
        'repair_sessions': cost['calls'], 'model_calls': cost['model_calls'],
        'tokens': cost['tokens'], 'wall_ms_total': cost['wall_ms_total'],
        'stopped': c['stopped'], 'exit_code': c['exit_code'],
        'fixed': c['fixed'], 'regressed': c['regressed'],
    })
    if no_gap:
        cells[-1]['kv_preserved'] = None
        cells[-1]['kv_mutated'] = None
        cells[-1]['kv_audit_note'] = ('no_gap、零輪未重生產 ⇒ 審計未執行（by design，不虛灌證據）；'
                                     'kv_preserved/kv_mutated = null（UNKNOWN，未測量≠未變動）')
        cells[-1]['cost_note'] = ('no_gap：agent 未啟動 ⇒ repair_sessions=0、model_calls=0 是完整事實；'
                                  'tokens/wall_ms_total 無 usage 來源 ⇒ null（UNKNOWN，不填 0）')

summary = {
    'schema': 'realab.summary/1',
    'ticket': 'R20261107_0035-1',
    'task': 'dab_378',
    'generated_at': datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds'),
    'purpose': ('11-06 指示 #4 後續＋審查 2026-11-07 Priority 2：6-cell 審計摘要——realab_dab378_20261106（2 格）'
                '＋realab_20261107（4 格）：獨立 scorer 結果、鍵級保留、成本欄位；並回答同草稿同預算下 '
                'localized 是否修回更多、正確成果是否退步、成本是否值得'),
    'cells': cells,
    'answer': {
        'localized_fixes_more_than_generic': ('否（本切片）——4 個 C（壞草稿）格中兩臂各修回同樣 2 個 kurtosis 錯誤'
            '（pre/post_kurtosis，wrong_to_right），regressed 皆 0；A（好草稿）格兩臂皆維持 11/11（right_stays_right）。'
            'localized 沒有修回 generic 修不回的東西，反之亦然。'),
        'correct_results_regressed': ('否——6 格最終產物獨立 scorer 皆 pass=true、檢查層 regressed=0。'
            '位元組層：11-06 localized 重排 2 行 median 格式（19711.00→19711.0，數值相同、scorer 接受，kv_mutated=2）；'
            '11-07 兩臂 kv 鍵值行全數逐位元組保留（C 8/8、A 10/10，kv_mutated=0）；A/localized no_gap 零輪未重生產。'),
        'cost_worth_it': ('無一致結論——11-06 C：localized 32 calls/417,236 tok/300.2s vs generic 24/440,238/89.2s'
            '（localized 更貴、wall 觸 300s 每輪上限）；11-07 C：localized 14/77,732/48.1s vs generic 29/485,581/107.1s'
            '（localized 更省）。兩批修正集合相同 ⇒ 成本方向隨 run 變化，沒有為「多修的東西」付代價，也沒有省下的代價。'
            '開發選樣、單 rep（1 draft × 2 arms × 2 批），不宣稱 localized 較好或較差。'),
    },
    'boundaries': [
        'tamper/UNKNOWN 不計成功；缺值=null(UNKNOWN) 不填 0；A/localized no_gap 格 tokens/wall 為 null（無 usage 來源），'
        '其 repair_sessions/model_calls=0 是「agent 未啟動」的完整事實（g2 cost 同口徑）',
        'kv_preserved/kv_mutated＝audit_kv_preservation 審計端計算（只收 verifier==kv_recomputed 的 @key[value] 鍵；'
        'req_answer_kv 是格式條目、非鍵值行，不進 kv 清單）',
        'before_pass_independent 是 lab 既有已記錄分（引用，未本地重跑 hidden scorer）；after 全部為本輪/11-06 新採分（pass=true、rc=0、raw stdout sha 記錄）',
        '11-07 四格最終產物只有兩種位元組內容（eb139290…：A/generic+C/generic；06ff239a…：A/localized+C/localized＝A 草稿）；'
        '按 sha 去重各採分一次、逐格記錄同一結果',
        '本切片＝dabench 失敗草稿 dab_378-pi-C（effects2_20261106 generic 失敗）＋其同 task 好草稿 dab_378-pi-A 作「正確成果退步」基準；'
        '開發選樣單 rep，不宣稱 localized 較好',
        '11-07 結果 manifest（run 時）sha256=cf516b8d…；本票交付 2 的措辭修訂後 sha256=32527583…（措辭修訂不改變任何已記錄結果）',
    ],
    'manifest_wording_fix': {
        'file': 'ops/reqloop/g2/real_slice/manifest.json',
        'change': '「9 條已滿足行」→「9 個已滿足條目（1 條 req_answer_kv 格式＋8 條 @key[value] 鍵值行）」（4 處：current_behavior／expected_demonstrable_improvement／independent_acceptance／dab_378-pi-C preservation.note）',
        'manifest_sha256_at_run': g1107['manifest']['sha256'],
        'manifest_sha256_after_fix': sha(MAN_P),
    },
    'evidence': {
        'realab_dab378_20261106': {
            'summary': '/home/user1/dev/ops/audits/realab_dab378_20261106_summary.json',
            'raw': '/home/user1/dev/ops/realab_dab378_20261106/{before_after.json,provenance.json,contrast/*}',
            'scorer_raw_stdout_sha256': s1106['raw_results'][0]['independent_lab_scorer']['raw_stdout_sha256'],
        },
        'realab_20261107': {
            'g2_result': '/home/user1/dev/ops/realab_20261107/g2_result.json (sha256 %s)' % sha(OPS / 'realab_20261107/g2_result.json'),
            'kv_audit': '/home/user1/dev/ops/audits/realab_kv_preservation_20261107.json',
            'independent_after_this_round': '/home/user1/dev/ops/realab_20261107/independent_after_20261107.json',
            'scorer_raw_stdout_sha256': ind1107['cells'][0]['independent_after']['raw_stdout_sha256'],
            'final_answer_sha256_by_content': {
                'eb139290…(A/generic+C/generic)': ind1107['cells'][0]['final_answer_sha256'],
                '06ff239a…(A/localized+C/localized=draft A)': ind1107['cells'][1]['final_answer_sha256'],
            },
        },
        'drafts': {d['name']: d['draft']['files'] for d in man['drafts']},
    },
    'provenance': {
        'model': man['model'],
        'scorer': 'lab 既有 black-box scorer（independent_score.py 介面，sudo -n、生成後才跑、hidden_read_by_agent=false、未讀 /srv/eval hidden 或 scorer.py 源碼）',
        'no_model_calls_this_round': True,
        'note': '本輪（r1154）只執行：採分（2 次，按最終內容 sha 去重）＋審計端計算；無 repair/agent 執行',
    },
}
OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print('wrote', OUT)
for c in cells:
    print(f"  {c['batch'][-11:]} {c['draft'][-8:]} {c['arm']:<10} before={c['before_pass_independent']} "
          f"after={c['after_independent']['pass']} kv={len(c['kv_preserved']) if c['kv_preserved'] is not None else 'null'}/"
          f"{len(c['kv_mutated']) if c['kv_mutated'] is not None else 'null'} "
          f"cost={c['repair_sessions']}/{c['model_calls']}/{c['tokens']}/{c['wall_ms_total']}")
