from __future__ import annotations
from time import perf_counter
from agents.comparison_agent import ComparisonAgent
from storage.database import Database
from .orchestrator import Orchestrator
from .state import InsurMindsState, RunStatus, TraceEvent

class ComparisonPipeline:
    def __init__(self, semantic=None, db_path='data/insurminds.db'):
        self.orchestrator=Orchestrator(); self.agent=ComparisonAgent(semantic); self.db=Database(db_path)

    def process(self,state:InsurMindsState)->InsurMindsState:
        if state.status != RunStatus.READY_TO_COMPARE: raise ValueError('M4 expects READY_TO_COMPARE')
        if len(state.validated_policies) < 2: raise ValueError('M4 requires at least two validated policies')
        self.orchestrator.update_state(state,RunStatus.COMPARING,self.agent.name)
        t=perf_counter()
        result=self.agent.compare(state.run_id,state.validated_policies[-2],state.validated_policies[-1])
        state.comparison=result
        state.trace.append(TraceEvent(agent=self.agent.name,event='POLICIES_COMPARED',status='SUCCESS',duration_ms=int((perf_counter()-t)*1000),details={'fields':len(result.fields),'review_required':sum(1 for x in result.fields if x.review_required)}))
        self.db.save_comparison(state.run_id,result)
        state.metrics['comparison_fields']=len(result.fields)
        state.metrics['comparison_review_required']=sum(1 for x in result.fields if x.review_required)
        if state.metrics['comparison_review_required']:
            state.warnings.extend(result.warnings)
        self.orchestrator.update_state(state,RunStatus.SYNTHESIZING,self.agent.name)
        self.db.save_run(state)
        return state
