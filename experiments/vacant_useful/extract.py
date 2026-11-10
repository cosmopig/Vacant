"""Twin-2K-500 rows.jsonl (cache, outside repo) -> compact.pkl (cache). No data enters the repo."""
import json,sys,pickle
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from vacant_network.personal.twin2k import convert_participant
out={}
with open(str(Path.home()/'.cache/vacant/twin2k500')+'/rows.jsonl') as f:
    for i,line in enumerate(f):
        row=json.loads(line)
        p=convert_participant(row,seed=20261109)
        calib={c['question_id']:(c['choice_text'],c['demographic'],c['stem'],c['block'],[o['text'] for o in c['options']]) for c in p['calibration']}
        w4={c['question_id']:(l['choice_option_id'],c['stem'],[o['text'] for o in c['options']],c['family']) for c,l in zip(p['holdout_cases'],p['labels'])}
        out[p['pid']]={'calib':calib,'w4':w4,'retest':p['test_retest']['rate']}
pickle.dump(out,open(str(Path.home()/'.cache/vacant/twin2k500')+'/compact.pkl','wb'))
print(len(out))
