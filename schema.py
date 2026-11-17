"""Typed routing decision shape for the A-to-z refund claim router.

Only billing, shipping, and stock are valid specialists. A claim may need
more than one (e.g. a claim can be both a billing and a stock issue), so
`specialists` is a non-empty list rather than a single value.
"""
from typing import List, Literal

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
