import json, os, pathlib, sys, time, random
root = pathlib.Path(sys.argv[1]); M = int(sys.argv[2]); KB = int(sys.argv[3])
os.environ["HOME"] = str(root / "home"); os.environ["VACANT_HOME"] = str(root / "vh")
for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
    os.environ.pop(k, None)
(root / "home").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, "/home/user/Vacant")
from vacant_network.adapters import hook, install as INS
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder
p = INS.state_root() / "install.json"; p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
app = root / "app"; (app / "data").mkdir(parents=True, exist_ok=True)
random.seed(1)
rows = ["psp_reference,merchant,card_scheme,year,hour_of_day,day_of_year,is_credit,eur_amount,ip_country,shopper_interaction,aci,date"]
merch = ["Crossfit_Hanna","Belles_cookbook_store","Golfclub_Baron_Friso","Martinis_Fine_Steakhouse","Rafa_AI"]
while sum(len(r)+1 for r in rows) < KB*1024:
    rows.append(f"{random.randint(10**10,10**11)},{random.choice(merch)},{random.choice(['Visa','GlobalCard','NexPay','TransactPlus'])},2023,{random.randint(0,23)},{random.randint(1,365)},{random.choice(['True','False'])},{random.uniform(1,500):.2f},{random.choice(['NL','BE','SE','IT'])},{random.choice(['Ecommerce','POS'])},{random.choice('ABCDEFG')},2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}")
csvtxt = "\n".join(rows) + "\n"
(app / "data" / "payments.csv").write_text(csvtxt * 3)
def ev(event, sid, **kw):
    out, err, code = hook.handle("pi", event, {"cwd": str(app), "session_id": sid, **kw})
    return json.loads(out) if out else {}
ev("prompt", "S", prompt="Answer using the files in data/. Question: what is the average eur_amount for Rafa_AI? Write the answer to /app/answer.txt.")
for i in range(M):
    inp = {"command": f"head -c {KB*1024} data/payments.csv # {i}"}
    ev("pre_tool", "S", tool="bash", call_id=f"c{i}", input=inp)
    ev("post_tool", "S", tool="bash", call_id=f"c{i}", input=inp, output=csvtxt)
rec = Recorder(app)
t = time.time(); out = zerostop._run_child({"ws": str(app), "platform": "pi", "session": "S", "final_text": None})
print(json.dumps({"steps": M, "kb_per_output": KB, "check_s": round(time.time() - t, 2), "ran": out.get("ran")}))
