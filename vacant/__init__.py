"""Vacant — 站在 AI agent『之間那條線』上的信任層（Phase 1 實作）。

對應《Vacant 架構總規格（單一文件）v1》。本套件是「A 層機制模擬」：純 CPU、零
GPU、零 API，把信任 + 持久/復活整條迴圈跑起來、驗得了（G2–G7）。上機（3090 +
vLLM + Hermes）只需把 EchoSubstrate 換成 HermesACPSubstrate。

分層對照：
  L0 substrate.py   可換的腦（EchoSubstrate / HermesACPSubstrate）
  L1 identity/logbook/reputation/body  vacant 身體（信任庫 + 能力庫綁定）
  L2 envelope/gateway                  邊界信任（簽/驗/把關/記帳）
  L3 waker                             喚醒對的 HOME + resume + 寫回（復活）
  L4 registry                          halo 發現 + 信譽路由索引
     verifier/tasks                    可檢查任務的非循環真值錨
     host                              一台機器的常駐組裝
"""

from .agent import SolveResult, Vacant, checkable_cases
from .attest import make_attestation, verify_attestation
from .body import CapabilityCard, VacantBody
from .brains import Brain, HermesBrain, LMStudioBrain, OpenAIBrain
from .checks import compile_check, extract_code
from .codebench import code_cases
from .composer import ComposeResult, Composer
from .gateway import BadSignature, CallOutcome, Gateway, ReputationRejected
from .host import Host
from .identity import Identity, PublicIdentity
from .logbook import ChainError, Logbook
from .envelope import ChannelGuard, Envelope, ReplayError
from .registry import Registry
from .reputation import Reputation
from .substrate import EchoSubstrate, HermesACPSubstrate, Substrate
from .waker import Waker, WakeResult

__version__ = "0.1.0"

__all__ = [
    "Vacant",
    "SolveResult",
    "checkable_cases",
    "code_cases",
    "compile_check",
    "extract_code",
    "make_attestation",
    "verify_attestation",
    "Brain",
    "LMStudioBrain",
    "OpenAIBrain",
    "HermesBrain",
    "Composer",
    "ComposeResult",
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
    "EchoSubstrate",
    "HermesACPSubstrate",
    "Waker",
    "WakeResult",
]
