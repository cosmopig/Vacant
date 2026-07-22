"""Vacant — AI agent 前面的強制信任、客觀驗證與可究責交付層。

產品入口 `VacantFirstController` 直接 delegate、驗 receipt/trust card、重跑 objective
check，全部通過後才啟動 Hermes 或任意 CLI agent。底層同時保留研究需要的信譽路由、
持久記憶、hash-chain、互審、稽核、實驗 runner 與可替換 substrate。

分層對照：
  L0 substrate.py   可換的腦（EchoSubstrate / HermesACPSubstrate）
  L1 identity/logbook/reputation/body  vacant 身體（信任庫 + 能力庫綁定）
  L2 envelope/gateway                  邊界信任（簽/驗/把關/記帳）
   L3 waker                             喚醒對的 HOME + resume + 寫回（復活）
   L4 registry                          halo 發現 + 信譽路由索引
   Product controller/receipt           強制順序 + 完整 task/answer 簽章 gate
      verifier/tasks                    可檢查任務的非循環真值錨
      host                              一台機器的常駐組裝
"""

from .agent import SolveResult, Vacant, checkable_cases
from .attest import make_attestation, verify_attestation
from .body import CapabilityCard, VacantBody
from .brains import Brain, HermesBrain, LMStudioBrain, OpenAIBrain
from .checks import compile_check, extract_code, project_checked_answer
from .codebench import code_cases
from .composer import ComposeResult, Composer
from .controller import (
    AgentEvidenceError,
    AgentRunFailed,
    ArgvTemplate,
    ControllerResult,
    GatePolicy,
    GateRejected,
    VacantFirstController,
    hermes_argv,
    verify_delivery,
)
from .gateway import BadSignature, CallOutcome, Gateway, ReputationRejected
from .host import Host
from .identity import Identity, PublicIdentity
from .logbook import ChainError, Logbook
from .envelope import ChannelGuard, Envelope, ReplayError
from .registry import Registry
from .receipt import ReceiptError, VerifiedReceipt, verify_delegation_receipt
from .reputation import Reputation
from .substrate import EchoSubstrate, HermesACPSubstrate, LMStudioSubstrate, Substrate, SubstrateResult
from .waker import Waker, WakeResult

__version__ = "0.1.0"

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
