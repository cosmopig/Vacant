# Does LM Studio's gemma-4-12b chat template accept the message shapes pi produces for Vacant's injections?
import json, sys, urllib.request, time
TOOLS=[{"type":"function","function":{"name":"bash","description":"run a shell command","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}}]
tc={"role":"assistant","content":None,"tool_calls":[{"id":"call_1","type":"function","function":{"name":"bash","arguments":json.dumps({"command":"echo 41"})}}]}
tr={"role":"tool","tool_call_id":"call_1","content":"41\n"}
sysm={"role":"system","content":"You are a helpful coding agent."}
u={"role":"user","content":"Compute 41+1 with bash, then answer."}
inj={"role":"user","content":"[vacant-check] The requested file answer.txt does not exist yet. Write your current answer to it now."}
fu={"role":"user","content":"VACANT-FOLLOWUP: write your current answer to answer.txt now"}
shapes={
 "a_turn_end_inject(tool->user)":[sysm,u,tc,tr,inj],
 "b_continue_after_text(assistant->user)":[sysm,u,{"role":"assistant","content":"The answer is 41."},inj],
 "c_two_users_in_a_row(tool->user->user)":[sysm,u,tc,tr,inj,fu],
}
for base in sys.argv[1:]:
    for name,msgs in shapes.items():
        body={"model":"gemma-4-12b-it-qat","messages":msgs,"tools":TOOLS,"max_tokens":24,"temperature":0,"stream":False}
        req=urllib.request.Request(base.rstrip("/")+"/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"})
        t=time.time()
        try:
            r=json.load(urllib.request.urlopen(req,timeout=120)); ch=r["choices"][0]
            print(base.split("//")[1].split(".")[0], name, "HTTP 200", round(time.time()-t,1),"s", "finish=",ch.get("finish_reason"), "content=",repr((ch["message"].get("content") or "")[:60]), "tool_calls=",bool(ch["message"].get("tool_calls")))
        except urllib.error.HTTPError as e:
            print(base, name, "HTTP", e.code, e.read()[:300])
        except Exception as e:
            print(base, name, "ERR", repr(e)[:200])
