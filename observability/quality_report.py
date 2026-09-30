from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from evaluation.models import EvalResult

class ObservabilityReport:
    """Cross-cutting Harness report; not an agent."""
    def build_run_summary(self,state):
        agents=Counter(x.agent for x in state.trace)
        durations={}
        for x in state.trace:
            if x.duration_ms is not None:
                durations[x.agent]=durations.get(x.agent,0)+x.duration_ms
        return {
            "run_id":state.run_id,
            "status":state.status.value,
            "documents":len(state.documents),
            "validated_policies":len(state.validated_policies),
            "trace_events":len(state.trace),
            "agents_seen":dict(agents),
            "duration_ms_by_agent":durations,
            "warnings":list(state.warnings),
            "errors":list(state.errors),
            "metrics":dict(state.metrics),
        }

    def build_quality_report(self,results:list[EvalResult]):
        return {
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "evaluations":[r.model_dump(mode="json") for r in results],
            "all_passed":all(r.passed for r in results) if results else False,
            "mean_score":sum(r.score for r in results)/len(results) if results else 0.0,
            "methodological_note":"Scores are meaningful only for manually annotated Golden Dataset cases; EVAL-05 is a lexical proxy."
        }
