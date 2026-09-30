from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from schemas.policy import PolicySchema
from schemas.comparison import ComparisonResult


class RunStatus(str, Enum):
    CREATED = "CREATED"
    INGESTING = "INGESTING"
    EXTRACTING = "EXTRACTING"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    READY_TO_COMPARE = "READY_TO_COMPARE"
    COMPARING = "COMPARING"
    SYNTHESIZING = "SYNTHESIZING"
    COMPLETED = "COMPLETED"
    WARNING = "WARNING"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class TraceEvent(BaseModel):
    agent: str
    event: str
    status: str
    duration_ms: Optional[int] = Field(default=None, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)


class InsurMindsState(BaseModel):
    run_id: str
    status: RunStatus = RunStatus.CREATED
    current_agent: Optional[str] = None
    documents: list[dict[str, Any]] = Field(default_factory=list)
    raw_texts: dict[str, str] = Field(default_factory=dict)
    extracted_policies: list[dict[str, Any]] = Field(default_factory=list)
    validated_policies: list[PolicySchema] = Field(default_factory=list)
    comparison: Optional[ComparisonResult] = None
    final_report: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace: list[TraceEvent] = Field(default_factory=list)
