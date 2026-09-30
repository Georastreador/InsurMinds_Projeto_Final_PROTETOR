from __future__ import annotations
import re
from typing import Any
from schemas.policy import PolicySchema
from schemas.comparison import ComparisonResult, ComparisonStatus
from .models import GoldenPolicyAnnotation, EvalResult

def _get(obj: Any, path: str):
    cur=obj
    for part in path.split("."):
        if cur is None: return None
        if hasattr(cur, part): cur=getattr(cur,part)
        elif isinstance(cur,dict): cur=cur.get(part)
        else: return None
    if hasattr(cur,"model_dump"): return cur.model_dump(mode="json")
    return cur

# ISO codes are normalizations; Brazilian documents write the currency this way.
CURRENCY_SURFACE_FORMS={"BRL":{"r$","reais","real brasileiro","moeda corrente nacional"},"USD":{"us$","dólar","dolar"}}

def _norm(v):
    if v is None: return None
    if isinstance(v,(dict,list)): return v
    return " ".join(str(v).lower().split())

class QualityEvaluator:
    """M6 evaluation layer. It measures existing agents; it is not an agent."""

    def eval_01_schema_validity(self, policy: PolicySchema) -> EvalResult:
        ok=True
        try: PolicySchema.model_validate(policy.model_dump())
        except Exception: ok=False
        return EvalResult(eval_id="EVAL-01",name="Schema validity",score=float(ok),
                          passed=ok,numerator=int(ok),denominator=1)

    def eval_02_field_extraction(self, policy: PolicySchema, gold: GoldenPolicyAnnotation) -> EvalResult:
        checked=0; correct=0; mismatches=[]
        for ann in gold.annotations:
            checked+=1
            actual=_get(policy,ann.field)
            if _norm(actual)==_norm(ann.expected): correct+=1
            else: mismatches.append({"field":ann.field,"expected":ann.expected,"actual":actual})
        score=correct/checked if checked else 0.0
        return EvalResult(eval_id="EVAL-02",name="Field extraction accuracy",score=score,
                          passed=bool(checked and score>=0.80),numerator=correct,denominator=checked,
                          details={"mismatches":mismatches},
                          limitations=[] if checked else ["No manually annotated fields were available."])

    def eval_03_evidence_grounding(self, policy: PolicySchema, gold: GoldenPolicyAnnotation) -> EvalResult:
        # Strong criterion: an expected non-null fact needs a source excerpt in the gold annotation
        # AND the extracted policy must expose at least one source reference containing that excerpt.
        relevant=[a for a in gold.annotations if a.expected not in (None,"",[],{})]
        supported=0; missing=[]
        refs=" ".join((r.excerpt or "") for r in policy.source_references).lower()
        for ann in relevant:
            excerpt=(ann.source_excerpt or "").strip().lower()
            if excerpt and excerpt in refs: supported+=1
            else: missing.append(ann.field)
        score=supported/len(relevant) if relevant else 0.0
        return EvalResult(eval_id="EVAL-03",name="Evidence grounding",score=score,
                          passed=bool(relevant and score>=0.80),numerator=supported,denominator=len(relevant),
                          details={"missing_evidence_fields":missing},
                          limitations=["Requires manual Claim→Evidence annotations in the Golden Dataset."])

    def eval_04_comparison_accuracy(self, result: ComparisonResult, expected: dict[str,str]) -> EvalResult:
        actual={x.field:x.status.value for x in result.fields}
        checked=len(expected); correct=sum(actual.get(k)==v for k,v in expected.items())
        errors={k:{"expected":v,"actual":actual.get(k)} for k,v in expected.items() if actual.get(k)!=v}
        score=correct/checked if checked else 0.0
        return EvalResult(eval_id="EVAL-04",name="Comparison accuracy",score=score,
                          passed=bool(checked and score>=0.90),numerator=correct,denominator=checked,
                          details={"errors":errors},
                          limitations=[] if checked else ["No manually labelled comparison was available."])

    def eval_05_unsupported_claim_proxy(self, policy: PolicySchema, raw_text: str) -> EvalResult:
        # Lexical proxy only: tests whether selected extracted scalar claims occur in source text.
        # It is intentionally NOT labelled as a semantic hallucination detector.
        claims=[]
        for field in ("policy_number","insurer","insured_entity","currency"):
            v=getattr(policy,field,None)
            if v: claims.append((field,str(v)))
        if policy.limit_of_liability and policy.limit_of_liability.amount is not None:
            claims.append(("limit_of_liability",str(policy.limit_of_liability.amount)))
        normalized=re.sub(r"\s+"," ",raw_text.lower())
        supported=0; unsupported=[]
        for field,value in claims:
            variants={value.lower(), value.lower().replace(".0","")}
            if field=="currency":
                variants|=CURRENCY_SURFACE_FORMS.get(value.upper(),set())
            if any(v in normalized for v in variants): supported+=1
            else: unsupported.append({"field":field,"value":value})
        score=supported/len(claims) if claims else 1.0
        return EvalResult(eval_id="EVAL-05",name="Unsupported-claim lexical proxy",score=score,
                          passed=score>=0.80,numerator=supported,denominator=len(claims),
                          details={"unsupported_proxy_claims":unsupported},
                          limitations=[
                            "Lexical proxy only; it is not proof of semantic grounding or absence of hallucination.",
                            "Formatting and normalization differences can produce false negatives."
                          ])
