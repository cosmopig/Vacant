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

import copy
import dataclasses
import hashlib
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
    goal_sha256: str = ""
    contract_sha256: str = ""
    # 規格自 hash（整份規格除本欄的 canonical JSON 之 sha256，同 freeze_specs._canon 口徑）。
    # 空字串＝未綁定（舊規格/舊行為）；非空時才進 to_dict，舊序列化逐位元組不變。
    spec_sha256: str = ""
    # from_dict 來源 dict 的深拷貝快照：規格檔案（如 G4 4 題）的 spec_sha256 即對該
    # 快照（除 spec_sha256 欄）而算，載入物件才能直接自校驗；程式內構建＝None（對 to_dict 算）。
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "items": [item.to_dict() for item in self.items],
        }
        if self.goal_sha256:
            d["goal_sha256"] = self.goal_sha256
        if self.contract_sha256:
            d["contract_sha256"] = self.contract_sha256
        if self.spec_sha256:
            d["spec_sha256"] = self.spec_sha256
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequirementSet:
        items = [RequirementItem.from_dict(d) for d in data.get("items", [])]
        return cls(
            task_id=data.get("task_id", "unnamed_task"),
            items=items,
            goal_sha256=str(data.get("goal_sha256", "") or ""),
            contract_sha256=str(data.get("contract_sha256", "") or ""),
            spec_sha256=str(data.get("spec_sha256", "") or ""),
            raw=copy.deepcopy(data),
        )

    def compute_spec_sha256(self) -> str:
        """規格自 hash：整份規格序列化（除 spec_sha256 欄）canonical JSON 之 sha256。

        canonical＝sort_keys＋compact separators＋ensure_ascii=False（同 freeze_specs._canon）。
        依據：from_dict 載入者＝來源 dict 快照 raw；程式內構建者＝to_dict()。
        """
        base = self.raw if self.raw is not None else self.to_dict()
        body = {k: v for k, v in base.items() if k != "spec_sha256"}
        canon = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def verify_self_hash(self) -> tuple[bool, str]:
        """自 hash 自校驗：未綁定→(False,"unbound")；吻合→(True,"OK")；否則 (False,"mismatch: …")。"""
        if not self.spec_sha256:
            return (False, "unbound")
        actual = self.compute_spec_sha256()
        if actual == self.spec_sha256:
            return (True, "OK")
        return (False, f"mismatch: spec_sha256={actual} != recorded={self.spec_sha256}")

    def verify_task_hash(self, task_dir: pathlib.Path) -> tuple[bool, str]:
        """比對 task_dir 下 goal.md／contract.md 的 sha256 與規格記載值。

        未綁定（任一為空字串）→ (False, "unbound")；檔案缺失或 hash 不符 →
        (False, "mismatch: ...")；兩者皆吻合 → (True, "OK")。
        """
        if not self.goal_sha256 or not self.contract_sha256:
            return (False, "unbound")
        base = pathlib.Path(task_dir)
        for name, recorded in (("goal.md", self.goal_sha256),
                               ("contract.md", self.contract_sha256)):
            p = base / name
            if not p.is_file():
                return (False, f"mismatch: {name} missing")
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != recorded:
                return (False, f"mismatch: {name} sha256={actual} != recorded={recorded}")
        return (True, "OK")

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
