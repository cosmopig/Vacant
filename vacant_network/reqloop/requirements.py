"""
vacant_network.reqloop.requirements
需求條目（Requirements）模組。

責任：
- 記錄使用者原文那一段 (quote)。
- 作用在哪個交付物 (deliverable)。
- 怎麼觀察成立 (verifier + params)。
- 類型 (kind: explicit / assumption / preference)。
- 不准自己發明好過的條件；沒有可靠檢查的條目就是 UNVERIFIED，不准用模型自評代替。
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
from typing import Any, Literal

from vacant_network.intake.contract import Claim

RequirementKind = Literal["explicit", "assumption", "preference"]
VALID_KINDS: set[RequirementKind] = {"explicit", "assumption", "preference"}


@dataclasses.dataclass(frozen=True)
class RequirementItem:
    """單一需求條目。"""
    id: str
    quote: str
    deliverable: str
    verifier: str
    kind: RequirementKind = "explicit"
    params: dict[str, Any] = dataclasses.field(default_factory=dict)
    description: str = ""
    required: bool = True
    authority: str = "client"
    hidden: bool = False
    unverified: bool = False
    # D2（P20261113_0300-2、11-13 人類裁決第 2 條）：模型原寫的 deliverable 字串。
    # 只提供紀錄、不參與判定；空字串＝舊行為（未走 trusted 路徑）。
    deliverable_claimed: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Requirement id cannot be empty")
        if self.kind not in VALID_KINDS:
            raise ValueError(f"Invalid kind {self.kind!r}; must be one of {VALID_KINDS}")
        if not self.quote.strip():
            raise ValueError(f"Requirement {self.id} must include quote from user request")
        if not self.deliverable.strip():
            raise ValueError(f"Requirement {self.id} must specify target deliverable")

    def to_claim(self) -> Claim:
        """轉換為 Vacant 原生 Claim 物件。"""
        combined_params = dict(self.params)
        combined_params.setdefault("quote", self.quote)
        combined_params.setdefault("deliverable", self.deliverable)
        combined_params.setdefault("kind", self.kind)
        combined_params.setdefault("unverified", self.unverified)
        return Claim(
            id=self.id,
            verifier=self.verifier,
            params=combined_params,
            required=self.required,
            authority=self.authority,
            description=self.description or self.quote,
            hidden=self.hidden,
        )

    def to_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "quote": self.quote,
            "deliverable": self.deliverable,
            "verifier": self.verifier,
            "kind": self.kind,
            "params": dict(self.params),
            "description": self.description,
            "required": self.required,
            "authority": self.authority,
            "hidden": self.hidden,
            "unverified": self.unverified,
        }
        # D2：deliverable_claimed 只留紀錄；空字串＝舊行為，不輸出該欄位——舊需求組
        # 序列化逐位元組不變（phase3 req digest／舊裁決接續不受影響）。
        if self.deliverable_claimed:
            out["deliverable_claimed"] = self.deliverable_claimed
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequirementItem:
        params = dict(data.get("params", {}))
        quote = data.get("quote", params.get("quote", ""))
        deliverable = data.get("deliverable", params.get("deliverable", ""))
        kind = data.get("kind", params.get("kind", "explicit"))
        unverified = bool(data.get("unverified", params.get("unverified", False)))
        return cls(
            id=data["id"],
            quote=quote,
            deliverable=deliverable,
            verifier=data.get("verifier", "unverified"),
            kind=kind,
            params=params,
            description=data.get("description", ""),
            required=data.get("required", True),
            authority=data.get("authority", "client"),
            hidden=data.get("hidden", False),
            unverified=unverified,
            deliverable_claimed=str(data.get("deliverable_claimed", "") or ""),
        )


@dataclasses.dataclass
class RequirementSet:
    """任務需求條目集合。"""
    task_id: str
    items: list[RequirementItem] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequirementSet:
        items = [RequirementItem.from_dict(d) for d in data.get("items", [])]
        return cls(task_id=data.get("task_id", "unnamed_task"), items=items)

    @classmethod
    def load(cls, path: str | pathlib.Path) -> RequirementSet:
        p = pathlib.Path(path)
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return cls.from_dict(raw)

    def save(self, path: str | pathlib.Path) -> None:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
