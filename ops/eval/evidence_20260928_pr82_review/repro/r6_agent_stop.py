import pathlib, sys, os
from vacant_network.intake import contract as C, flow
from vacant_network.adapters.hookpolicy import HookEvent, decide_stop
ws = pathlib.Path(sys.argv[1]) / "app"
c = C.load(C.find(ws))
d = decide_stop(HookEvent(agent="pi", kind="stop", session_id="s1", cwd=str(ws)), c,
                check_fn=lambda cc, bd: flow.check(cc, bd, sandbox="none"))
print("uid", os.getuid(), "stop decision:", d.action, d.record.get("not_agent_fixable"), (d.reason or "")[:120])
