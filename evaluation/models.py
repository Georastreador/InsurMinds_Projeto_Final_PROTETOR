from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

class FieldAnnotation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    field: str
    expected: Any=None
    source_page: int|None=None
    source_excerpt: str|None=None

class GoldenPolicyAnnotation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    document_id: str
    source_file: str
    policy_type: str|None=None
    annotations: list[FieldAnnotation]=Field(default_factory=list)
    reviewer: str|None=None
    notes: list[str]=Field(default_factory=list)

class EvalResult(BaseModel):
    model_config=ConfigDict(extra="forbid")
    eval_id: str
    name: str
    score: float=Field(ge=0,le=1)
    passed: bool
    numerator: int=0
    denominator: int=0
    details: dict=Field(default_factory=dict)
    limitations: list[str]=Field(default_factory=list)
