"""Typed routing decision shape for the A-to-z refund claim router.

Only billing, shipping, and stock are valid specialists. A claim may need
more than one (e.g. a claim can be both a billing and a stock issue), so
`specialists` is a non-empty list rather than a single value.
"""
from typing import Dict, List, Literal

from pydantic import BaseModel, Field, field_validator

Specialist = Literal["billing", "shipping", "stock"]


class RoutingDecision(BaseModel):
    specialists: List[Specialist] = Field(
        ...,
        min_length=1,
        description="One or more of: billing, shipping, stock.",
    )
    reason: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("specialists")
    @classmethod
    def no_duplicate_specialists(cls, value: List[str]) -> List[str]:
        if len(set(value)) != len(value):
            raise ValueError("specialists must not contain duplicates")
        return value


class SpecialistFinding(BaseModel):
    specialist: Specialist
    found: bool
    rows: List[dict]
    note: str


class EscalationFlags(BaseModel):
    missing_record: bool = False
    low_confidence: bool = False
    contradicts_billing: bool = False
    contradicts_shipping: bool = False
    contradicts_stock: bool = False


class ClaimResolution(BaseModel):
    claim_id: str
    order_id: str
    specialists_consulted: List[Specialist]
    findings: Dict[str, SpecialistFinding]
    router_confidence: float
    escalation: EscalationFlags
    escalate_to_human: bool
    human_review_reason: str
