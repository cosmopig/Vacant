import sys, hashlib, importlib
exe = sys.argv[1]
sys.executable = exe
from vacant_network.adapters import agents
print(hashlib.sha256(agents.pi_extension_text().encode()).hexdigest())
