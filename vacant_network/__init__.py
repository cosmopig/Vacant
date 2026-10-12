"""Vacant — 接在任何 AI agent 外面的可究責層（accountability layer）。

產品入口 `VacantFirstController` 直接 delegate、驗 receipt/trust card、重跑 objective
check，全部通過後才啟動 Hermes 或任意 CLI agent。底層同時保留研究需要的信譽路由、
持久記憶、hash-chain、互審、稽核、實驗 runner 與可替換 substrate。

分層對照：
  L0 substrate.py   可換的腦（EchoSubstrate / HermesACPSubstrate）
  L1 identity/logbook/reputation/body  vacant 身體（信任庫 + 能力庫綁定）
  L2 envelope/gateway                  邊界把關（簽/驗/把關/記帳）
   L3 waker                             喚醒對的 HOME + resume + 寫回（復活）
   L4 registry                          halo 發現 + 信譽路由索引
   Product controller/receipt           強制順序 + 完整 task/answer 簽章 gate
      verifier/tasks                    可檢查任務的非循環真值錨
      host                              一台機器的常駐組裝
"""

# PEP 562 惰性匯入：hook 熱路徑（`python -m vacant_network hook`，每個工具呼叫兩次）
# 只需要 adapters／trace，不該為了套件 __init__ 連帶載入 brains（urllib.request）、
# controller、gateway、host 等。對外名字與 __all__ 不變，`from vacant_network import X`
# 照舊可用，首次取用才載入對應子模組。
# 誠實邊界：以前「匯入套件」會順帶把這些子模組掛成套件屬性；現在要用到才有。
_LAZY = {
    "SolveResult": ".agent",
    "Vacant": ".agent",
    "checkable_cases": ".agent",
    "make_attestation": ".attest",
    "verify_attestation": ".attest",
    "CapabilityCard": ".body",
    "VacantBody": ".body",
    "Brain": ".brains",
    "HermesBrain": ".brains",
    "LMStudioBrain": ".brains",
    "OpenAIBrain": ".brains",
    "compile_check": ".checks",
    "extract_code": ".checks",
    "project_checked_answer": ".checks",
    "code_cases": ".codebench",
    "ComposeResult": ".composer",
    "Composer": ".composer",
    "AgentEvidenceError": ".controller",
    "AgentRunFailed": ".controller",
    "ArgvTemplate": ".controller",
    "ControllerResult": ".controller",
    "GatePolicy": ".controller",
    "GateRejected": ".controller",
    "VacantFirstController": ".controller",
    "hermes_argv": ".controller",
    "verify_delivery": ".controller",
    "BadSignature": ".gateway",
    "CallOutcome": ".gateway",
    "Gateway": ".gateway",
    "ReputationRejected": ".gateway",
    "Host": ".host",
    "Identity": ".identity",
    "PublicIdentity": ".identity",
    "ChainError": ".logbook",
    "Logbook": ".logbook",
    "ChannelGuard": ".envelope",
    "Envelope": ".envelope",
    "ReplayError": ".envelope",
    "Registry": ".registry",
    "ReceiptError": ".receipt",
    "VerifiedReceipt": ".receipt",
    "verify_delegation_receipt": ".receipt",
    "Reputation": ".reputation",
    "EchoSubstrate": ".substrate",
    "HermesACPSubstrate": ".substrate",
    "LMStudioSubstrate": ".substrate",
    "Substrate": ".substrate",
    "SubstrateResult": ".substrate",
    "Waker": ".waker",
    "WakeResult": ".waker",
}


def __getattr__(name):
    mod = _LAZY.get(name)
    if mod is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    val = getattr(importlib.import_module(mod, __name__), name)
    globals()[name] = val
    return val


def __dir__():
    return sorted(set(globals()) | set(_LAZY))


__version__ = "0.9.1"

__all__ = [
    "Vacant",
    "SolveResult",
    "checkable_cases",
    "code_cases",
    "compile_check",
    "extract_code",
    "project_checked_answer",
    "make_attestation",
    "verify_attestation",
    "Brain",
    "LMStudioBrain",
    "OpenAIBrain",
    "HermesBrain",
    "Composer",
    "ComposeResult",
    "VacantFirstController",
    "GatePolicy",
    "GateRejected",
    "AgentRunFailed",
    "AgentEvidenceError",
    "ArgvTemplate",
    "ControllerResult",
    "hermes_argv",
    "verify_delivery",
    "ReceiptError",
    "VerifiedReceipt",
    "verify_delegation_receipt",
    "Host",
    "VacantBody",
    "CapabilityCard",
    "Gateway",
    "CallOutcome",
    "BadSignature",
    "ReputationRejected",
    "Identity",
    "PublicIdentity",
    "Logbook",
    "ChainError",
    "Envelope",
    "ChannelGuard",
    "ReplayError",
    "Registry",
    "Reputation",
    "Substrate",
    "SubstrateResult",
    "EchoSubstrate",
    "HermesACPSubstrate",
    "LMStudioSubstrate",
    "Waker",
    "WakeResult",
]
