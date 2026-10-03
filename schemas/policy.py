from __future__ import annotations
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .do_taxonomy import ClauseCategory, CoverageCategory, DocumentKind, ExclusionCategory, LineOfBusiness


class IdentificationStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"


class InsuringSide(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    OTHER = "OTHER"


class SourceReference(BaseModel):
    page: Optional[int] = Field(default=None, ge=1)
    section: Optional[str] = None
    excerpt: Optional[str] = None
    # Filled by the Harness (tools/evidence_check.py), never requested from the LLM.
    verified: Optional[bool] = None
    verified_page: Optional[int] = Field(default=None, ge=1)


class Money(BaseModel):
    amount: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper().strip() if value else value


class Retention(BaseModel):
    applies_to: Optional[str] = None
    amount: Optional[Money] = None
    conditions: Optional[str] = None
    source_reference: Optional[SourceReference] = None


class InsuringAgreement(BaseModel):
    side: InsuringSide
    present: bool
    title: Optional[str] = None
    description: Optional[str] = None
    limit: Optional[Money] = None
    retention: Optional[Money] = None
    source_reference: Optional[SourceReference] = None


class Coverage(BaseModel):
    coverage_id: Optional[str] = None
    name: str
    normalized_name: Optional[str] = None
    category: Optional[CoverageCategory] = None
    present: bool = True
    description: Optional[str] = None
    limit: Optional[Money] = None
    sublimit: Optional[Money] = None
    retention: Optional[Money] = None
    conditions: list[str] = Field(default_factory=list)
    source_reference: Optional[SourceReference] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class Exclusion(BaseModel):
    exclusion_id: Optional[str] = None
    name: str
    normalized_name: Optional[str] = None
    category: Optional[ExclusionCategory] = None
    description: Optional[str] = None
    exceptions: list[str] = Field(default_factory=list)
    source_reference: Optional[SourceReference] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class Clause(BaseModel):
    name: str
    category: Optional[ClauseCategory] = None
    description: Optional[str] = None
    source_reference: Optional[SourceReference] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class Extension(Clause):
    # Extensions extend coverage, so they share the coverage taxonomy.
    category: Optional[CoverageCategory] = None


class ReportingPeriod(BaseModel):
    duration_days: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None
    source_reference: Optional[SourceReference] = None


class PolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    policy_number: Optional[str] = None
    insurer: Optional[str] = None
    insured_entity: Optional[str] = None
    policy_type: Optional[str] = None
    line_of_business: Optional[LineOfBusiness] = None
    document_kind: Optional[DocumentKind] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    currency: Optional[str] = None
    limit_of_liability: Optional[Money] = None
    aggregate_limit: Optional[Money] = None
    retentions: list[Retention] = Field(default_factory=list)
    insuring_agreements: list[InsuringAgreement] = Field(default_factory=list)
    coverages: list[Coverage] = Field(default_factory=list)
    sublimits: list[Money] = Field(default_factory=list)
    exclusions: list[Exclusion] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    extensions: list[Extension] = Field(default_factory=list)
    retroactive_date: Optional[date] = None
    reporting_period: Optional[ReportingPeriod] = None
    territorial_scope: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_references: list[SourceReference] = Field(default_factory=list)
    extraction_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper().strip() if value else value

    @field_validator("effective_date", "expiration_date", "retroactive_date")
    @classmethod
    def plausible_year(cls, value: Optional[date]) -> Optional[date]:
        # Guardrail against garbled LLM dates (e.g. 0110-01-10); fails A4 and triggers retry.
        if value is not None and not 1900 <= value.year <= 2100:
            raise ValueError(f"implausible policy date {value.isoformat()}")
        return value
