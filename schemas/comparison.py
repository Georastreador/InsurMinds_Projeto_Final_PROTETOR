from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from .policy import SourceReference


class ComparisonStatus(str, Enum):
    EQUAL = "EQUAL"
    DIFFERENT = "DIFFERENT"
    ONLY_A = "ONLY_A"
    ONLY_B = "ONLY_B"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ComparedValue(BaseModel):
    value: Any = None
    source: Optional[SourceReference] = None


class DifferenceDetail(BaseModel):
    absolute: Optional[float] = None
    percentage: Optional[float] = None
    explanation: Optional[str] = None


class FieldComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    policy_a: ComparedValue
    policy_b: ComparedValue
    status: ComparisonStatus
    difference: Optional[DifferenceDetail] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    review_required: bool = False
    reason: Optional[str] = None


class ComparisonResult(BaseModel):
    run_id: str = Field(min_length=1)
    policy_a_document_id: str = Field(min_length=1)
    policy_b_document_id: str = Field(min_length=1)
    fields: list[FieldComparison] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
