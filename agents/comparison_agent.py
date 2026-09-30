from __future__ import annotations
from decimal import Decimal
from enum import Enum
from typing import Protocol, Optional, Any, Callable
from schemas.policy import InsuringAgreement, PolicySchema
from schemas.comparison import ComparisonResult, FieldComparison, ComparedValue, DifferenceDetail, ComparisonStatus
from orchestration.scope import is_do
from schemas.do_taxonomy import (ClauseCategory, CoverageCategory, ExclusionCategory, canonical_policy_type,
                                 canonical_territorial_scope, categorize, fold)

PROHIBITED_VERDICTS = {"best","worst","better","worse","recommended","melhor","pior","recomendado","recomendada"}
SEMANTIC_STATUSES = {"EQUAL", "DIFFERENT", "REVIEW_REQUIRED"}
MIN_SEMANTIC_CONFIDENCE = 0.7

class SemanticComparator(Protocol):
    """Judges whether paired contractual content is equivalent.

    Implementations may also expose `compare_many(requests)` taking a list of
    (field, item_a, item_b) tuples; A5 uses it to judge all pairs in one call, and
    `match_orphans(orphans_a, orphans_b)` returning [{"a": i, "b": j, "confidence": c}]
    to pair items that the taxonomy left unmatched.
    """
    def compare(self, field: str, item_a: Any, item_b: Any) -> dict: ...

class ConservativeSemanticComparator:
    """Safe default: exact normalized names are equal; unmatched/ambiguous content requires review."""
    def compare(self, field: str, item_a: Any, item_b: Any) -> dict:
        def norm(x):
            if x is None or x == []: return None
            if isinstance(x, list):
                return tuple(sorted(filter(None, (norm(v) for v in x)))) or None
            if isinstance(x, dict):
                x = x.get("normalized_name") or x.get("name") or x.get("description") or x.get("conditions")
            return " ".join(str(x).lower().split()) if x is not None else None
        a,b=norm(item_a),norm(item_b)
        if a is None and b is None: return {"status":"NOT_IDENTIFIED","confidence":1.0,"reason":"No value identified in either policy."}
        if a is None: return {"status":"ONLY_B","confidence":1.0,"reason":"Identified only in policy B."}
        if b is None: return {"status":"ONLY_A","confidence":1.0,"reason":"Identified only in policy A."}
        if a == b: return {"status":"EQUAL","confidence":1.0,"reason":"Normalized semantic labels match exactly."}
        return {"status":"REVIEW_REQUIRED","confidence":0.5,"reason":"Semantic equivalence is not established by the deterministic fallback."}

class ComparisonAgent:
    """A5: pairs contractual items by canonical D&O concept, then judges paired content.

    Pairing is deterministic (taxonomy category declared by A3 or keyword fallback);
    only the judgment of paired content is delegated to the SemanticComparator.
    """
    name = "A5_COMPARISON"
    SIMPLE_FIELDS=("policy_number","insurer","insured_entity","effective_date","expiration_date","currency","retroactive_date","jurisdiction")

    def __init__(self, semantic: Optional[SemanticComparator]=None):
        self.semantic=semantic or ConservativeSemanticComparator()

    @staticmethod
    def _src(obj): return getattr(obj,"source_reference",None) if obj is not None else None
    @staticmethod
    def _cv(value, source=None): return ComparedValue(value=value,source=source)
    @staticmethod
    def _plain(value): return value.isoformat() if hasattr(value,"isoformat") else value

    def _simple(self, field, a, b, source_a=None, source_b=None):
        if a is None and b is None: status=ComparisonStatus.NOT_IDENTIFIED
        elif a is None: status=ComparisonStatus.ONLY_B
        elif b is None: status=ComparisonStatus.ONLY_A
        elif a == b: status=ComparisonStatus.EQUAL
        else: status=ComparisonStatus.DIFFERENT
        return FieldComparison(field=field,policy_a=self._cv(a,source_a),policy_b=self._cv(b,source_b),status=status,confidence=1.0)

    def _concept(self, field, a, b, canon: Callable[[Optional[str]], Optional[str]]):
        """Compare free-text values by canonical concept while displaying the original text."""
        item=self._simple(field,a,b)
        if a is not None and b is not None:
            ca,cb=canon(a),canon(b)
            item.status=ComparisonStatus.EQUAL if ca==cb else ComparisonStatus.DIFFERENT
            item.reason=f"Comparado por conceito normalizado: A={ca}; B={cb}."
        return item

    def _money(self, field, a, b):
        av = a.amount if a else None; bv = b.amount if b else None
        ac = a.currency if a else None; bc = b.currency if b else None
        item=self._simple(field, None if av is None else {"amount":str(av),"currency":ac}, None if bv is None else {"amount":str(bv),"currency":bc})
        if av is not None and bv is not None and ac == bc:
            diff=Decimal(bv)-Decimal(av)
            pct=None if Decimal(av)==0 else float((diff/Decimal(av))*100)
            item.difference=DifferenceDetail(absolute=float(diff),percentage=pct,explanation=f"B - A in {ac or 'same currency'}")
        return item

    SIDE_CATEGORIES={"cobertura_a":"A","cobertura_b":"B","cobertura_c":"C"}

    @classmethod
    def _side_map(cls, policy):
        """Side presence from insuring agreements, completed by coverages classified as Cobertura A/B/C."""
        sides={x.side.value:x for x in policy.insuring_agreements}
        for x in policy.coverages+policy.extensions:
            side=cls.SIDE_CATEGORIES.get(getattr(categorize(CoverageCategory,x),"value",None))
            if side and side not in sides:
                sides[side]=InsuringAgreement(side=side,present=True,title=x.name,source_reference=x.source_reference)
        return sides

    @classmethod
    def _without_sides(cls, items):
        # Side A/B/C are compared in insuring_side_*; keeping them here would duplicate them as orphans.
        return [x for x in items if getattr(categorize(CoverageCategory,x),"value",None) not in cls.SIDE_CATEGORIES]

    @staticmethod
    def _group(items, kind: type[Enum]) -> dict[str, list]:
        """Group items by canonical category; uncategorized items keep their own name.

        Uncategorized items are matched on the accent-free form but keyed by the first
        item's readable name, so the UI shows "cláusula específica", not "clausula especifica".
        """
        groups: dict[str, list] = {}; display: dict[str, str] = {}
        for x in items:
            cat=categorize(kind,x)
            if cat is not None and cat.value!="outra":
                match=key=cat.value
            else:
                raw=getattr(x,"normalized_name",None) or x.name
                match=fold(raw); key=display.setdefault(match," ".join(str(raw).replace("_"," ").lower().split()))
            if match: groups.setdefault(key,[]).append(x)
        return groups

    @staticmethod
    def _dump(items):
        dumped=[x.model_dump(mode="json") for x in items]
        return None if not dumped else dumped[0] if len(dumped)==1 else dumped

    def _pair(self, field, items_a, items_b, pending):
        """Presence is decided here; content of items present in both goes to the semantic judge."""
        va,vb=self._dump(items_a),self._dump(items_b)
        sa=self._src(items_a[0]) if items_a else None; sb=self._src(items_b[0]) if items_b else None
        if va is None and vb is None:
            status=ComparisonStatus.NOT_IDENTIFIED
        elif va is None: status=ComparisonStatus.ONLY_B
        elif vb is None: status=ComparisonStatus.ONLY_A
        else: status=ComparisonStatus.REVIEW_REQUIRED
        item=FieldComparison(field=field,policy_a=self._cv(va,sa),policy_b=self._cv(vb,sb),status=status,confidence=1.0)
        if va is not None and vb is not None:
            pending.append((item,field,va,vb))
        return item

    def _categorized(self, field, items_a, items_b, kind, pending):
        ga,gb=self._group(items_a,kind),self._group(items_b,kind)
        return [self._pair(f"{field}:{k}",ga.get(k,[]),gb.get(k,[]),pending) for k in sorted(set(ga)|set(gb))]

    MIN_MATCH_CONFIDENCE = 0.75
    # Exclusions only pair with exclusions; coverages and clauses may pair with each other because
    # extraction sometimes records the same provision as a coverage extension or as a clause.
    _MATCH_FAMILY = {"exclusions": "exclusions", "coverages": "grants", "clauses": "grants"}

    def _match_orphans(self, fields, pending):
        """Pair ONLY_A/ONLY_B items the taxonomy could not align, using the semantic matcher."""
        if not hasattr(self.semantic, "match_orphans"):
            return fields
        def orphans(status):
            return [x for x in fields if x.status==status and x.field.split(":")[0] in self._MATCH_FAMILY]
        oa,ob=orphans(ComparisonStatus.ONLY_A),orphans(ComparisonStatus.ONLY_B)
        if not oa or not ob:
            return fields
        def view(x, value):
            from schemas.labels import human_field, short_value
            return {"label": human_field(x.field), "family": self._MATCH_FAMILY[x.field.split(":")[0]], "text": short_value(value, 300)}
        matches=self.semantic.match_orphans([view(x,x.policy_a.value) for x in oa],[view(x,x.policy_b.value) for x in ob])
        used_a,used_b,merged=set(),set(),{}
        for m in sorted(matches,key=lambda m:-(m.get("confidence") or 0)):
            i,j,conf=m.get("a"),m.get("b"),m.get("confidence") or 0
            if not (isinstance(i,int) and isinstance(j,int) and 0<=i<len(oa) and 0<=j<len(ob)): continue
            if i in used_a or j in used_b or conf<self.MIN_MATCH_CONFIDENCE: continue
            a,b=oa[i],ob[j]
            if self._MATCH_FAMILY[a.field.split(":")[0]]!=self._MATCH_FAMILY[b.field.split(":")[0]]: continue
            used_a.add(i); used_b.add(j)
            item=FieldComparison(field=a.field,policy_a=a.policy_a,policy_b=b.policy_b,status=ComparisonStatus.REVIEW_REQUIRED,
                                 confidence=conf,reason=f"Pareado por similaridade semântica com '{b.field}' (confiança {conf:.2f}).")
            pending.append((item,item.field,a.policy_a.value,b.policy_b.value))
            merged[id(a)]=item; merged[id(b)]=None
        return [merged.get(id(x),x) for x in fields if merged.get(id(x),x) is not None]

    def _judge(self, pending):
        from agents.synthesis_agent import has_verdict  # local import: synthesis imports labels only
        if not pending: return
        requests=[(field,va,vb) for _,field,va,vb in pending]
        if hasattr(self.semantic,"compare_many"):
            results=self.semantic.compare_many(requests)
        else:
            results=[self.semantic.compare(*r) for r in requests]
        for (item,*_),r in zip(pending,results):
            status=str(r.get("status","REVIEW_REQUIRED")); conf=r.get("confidence"); reason=r.get("reason")
            # Guardrails: controlled states only, low confidence and verdict language escalate to human review.
            if status not in SEMANTIC_STATUSES: status="REVIEW_REQUIRED"
            if conf is not None and conf < MIN_SEMANTIC_CONFIDENCE and status!="REVIEW_REQUIRED":
                status="REVIEW_REQUIRED"; reason=f"Confiança {conf:.2f} abaixo do mínimo; {reason or ''}".strip()
            if reason and has_verdict(reason):
                status="REVIEW_REQUIRED"; reason="Justificativa semântica descartada por conter linguagem de veredito."
            if item.reason and item.reason.startswith("Pareado por similaridade"):
                reason=f"{item.reason} {reason or ''}".strip()
            item.status=ComparisonStatus(status); item.confidence=conf; item.reason=reason
            item.review_required=item.status==ComparisonStatus.REVIEW_REQUIRED

    def compare(self, run_id: str, a: PolicySchema, b: PolicySchema) -> ComparisonResult:
        fields=[]; pending=[]
        for name in self.SIMPLE_FIELDS:
            fields.append(self._simple(name,self._plain(getattr(a,name)),self._plain(getattr(b,name))))
        fields.append(self._concept("policy_type",a.policy_type,b.policy_type,canonical_policy_type))
        fields.append(self._concept("territorial_scope",a.territorial_scope,b.territorial_scope,canonical_territorial_scope))
        fields.append(self._money("limit_of_liability",a.limit_of_liability,b.limit_of_liability))
        fields.append(self._money("aggregate_limit",a.aggregate_limit,b.aggregate_limit))
        sa,sb=self._side_map(a),self._side_map(b)
        do_scope=is_do(a) and is_do(b)
        for side in ("A","B","C"):
            ia,ib=sa.get(side),sb.get(side)
            av=ia.present if ia else None; bv=ib.present if ib else None
            item=self._simple(f"insuring_side_{side}",av,bv,self._src(ia),self._src(ib))
            if not do_scope:
                item.status=ComparisonStatus.NOT_APPLICABLE; item.reason="Estrutura Side A/B/C é específica de D&O."
            fields.append(item)
        fields.append(self._pair("retentions",a.retentions,b.retentions,pending))
        fields.append(self._pair("reporting_period",[x for x in [a.reporting_period] if x],[x for x in [b.reporting_period] if x],pending))
        fields.extend(self._categorized("coverages",self._without_sides(a.coverages+a.extensions),
                                        self._without_sides(b.coverages+b.extensions),CoverageCategory,pending))
        fields.extend(self._categorized("exclusions",a.exclusions,b.exclusions,ExclusionCategory,pending))
        fields.extend(self._categorized("clauses",a.clauses,b.clauses,ClauseCategory,pending))
        fields=self._match_orphans(fields,pending)
        self._judge(pending)
        warnings=[]
        if any(x.review_required for x in fields): warnings.append("One or more semantic comparisons require human review.")
        return ComparisonResult(run_id=run_id,policy_a_document_id=a.document_id,policy_b_document_id=b.document_id,fields=fields,warnings=warnings)
