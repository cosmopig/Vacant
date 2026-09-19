"""`vacant run` V0 的**維運側**：實作已搬進 `vacant_network/vrun/`（2026-09-18）。

這一包在架構裡承重什麼：兩件事，**只有兩件**。

1. **維持 `ops.vacantrun.*` 這個 import 路徑**。`launcher`／`wireproxy`／`demo`／
   `retry` 在這裡是 re-export（`sys.modules[__name__] = vacant_network.vrun.<同名>`），所以
   既有的 `from ops.vacantrun import launcher`、
   `python3 ops/vacantrun/launcher.py …` 照樣可用，而且**沒有第二份**。
   ⚠ `envmap` **沒有**留 re-export：它現在只住在 `vacant_network/vrun/envmap.py`。
     那份名單漏一格的後果是「那條路沒被中介，而且不會有錯誤訊息」，
     再放一個看起來也是名單的檔案在這裡，就是給未來的人一個改錯地方的機會。

2. **放真的只能住在 repo 裡的東西**：`block_egress.sh`（V3 出網封鎖，要 root
   一次）、`verify_egress_block.py`（封鎖有沒有生效的實測）、`selftest.py`
   （端到端自檢，要用到 repo 的 `runs/`）、`wrap_agent.sh`（pi／Codex／OpenCode
   三個吃設定檔的框架那幾段接線，見 `docs/AGENT_COMPAT.md`）。這幾樣進不了 wheel 也不該進——
   它們是維運動作不是產品功能。README 的「還需要 clone 的部分」逐條列了它們。

為什麼搬：`ops/` 不進 wheel，判斷層留在這裡就等於
`pip install vacant-network` 的人拿不到閘門。完整理由見 `vacant_network/vrun/__init__.py`。
"""
