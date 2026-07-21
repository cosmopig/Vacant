import asyncio, os, sys, traceback
import acp
from acp import spawn_agent_process, Client
from acp.client.connection import TextContentBlock
from acp.schema import RequestPermissionResponse, SelectedPermissionOutcome

PROMPT = ('You have a delegation tool a2a_call(capability, input) that routes a task to a trusted expert agent. '
          'Reverse the string cvve2f by calling a2a_call with capability="reverse" and input="cvve2f". '
          'Then report the exact answer it returns.')

class Drv(Client):
    def __init__(self): self.updates = []
    async def session_update(self, params, **k):
        self.updates.append(repr(params)[:400]); return None
    async def request_permission(self, params, **k):
        opts = getattr(params, "options", None) or []
        pick = None
        for o in opts:
            if "allow" in str(getattr(o, "kind", "")).lower(): pick = o; break
        pick = pick or (opts[0] if opts else None)
        oid = getattr(pick, "option_id", None) or getattr(pick, "id", None)
        return RequestPermissionResponse(outcome=SelectedPermissionOutcome(option_id=oid))
    async def read_text_file(self, params, **k): raise RuntimeError("nofs")
    async def write_text_file(self, params, **k): raise RuntimeError("nofs")
    async def create_terminal(self, params, **k): raise RuntimeError("noterm")
    async def terminal_output(self, params, **k): raise RuntimeError("noterm")
    async def kill_terminal(self, params, **k): raise RuntimeError("noterm")
    async def release_terminal(self, params, **k): raise RuntimeError("noterm")
    async def wait_for_terminal_exit(self, params, **k): raise RuntimeError("noterm")
    async def ext_method(self, *a, **k): return {}
    async def ext_notification(self, *a, **k): return None
    async def on_connect(self, *a, **k): return None

async def main():
    drv = Drv()
    env = dict(os.environ); env["HERMES_HOME"] = os.path.expanduser("~/.hermes")
    # 端點不寫死（G10）：VACANT_ENDPOINT 指定，預設本機 LM Studio
    env["CUSTOM_BASE_URL"] = os.environ.get("VACANT_ENDPOINT", "http://localhost:1234").rstrip("/") + "/v1"
    pv = getattr(acp, "PROTOCOL_VERSION", 1)
    async with spawn_agent_process(lambda agent: drv, os.path.expanduser("~/hermes-agent/venv/bin/hermes-acp"),
                                   env=env, cwd=os.path.expanduser("~/hermes-agent"), use_unstable_protocol=True) as (conn, proc):
        init = await conn.initialize(protocol_version=pv)
        print("INIT ok; auth_methods=", getattr(init,"auth_methods",None), "pv=", getattr(init,"protocol_version",None))
        sess = await conn.new_session(cwd=os.path.expanduser("~/hermes-agent"), mcp_servers=[])
        sid = sess.session_id
        print("SESSION", sid)
        resp = await conn.prompt(prompt=[TextContentBlock(type="text", text=PROMPT)], session_id=sid)
        print("PROMPT stop_reason=", getattr(resp,"stop_reason",None))
        print("=== UPDATES (", len(drv.updates), ") ===")
        for u in drv.updates: print(u)

try:
    asyncio.run(asyncio.wait_for(main(), timeout=240))
except Exception:
    traceback.print_exc()
