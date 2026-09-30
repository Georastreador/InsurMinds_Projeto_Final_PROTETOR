from __future__ import annotations
from time import perf_counter
from agents.policy_agent import PolicyAnalysisAgent
from agents.validation_agent import ValidationAgent, PolicyValidationError, feedback_from_errors, retry_warning
from llm.client import StructuredOutputError
from storage.database import Database
from .orchestrator import Orchestrator
from .state import RunStatus, TraceEvent, InsurMindsState

class IntelligencePipeline:
    def __init__(self, llm, db_path='data/insurminds.db', max_retries=2):
        self.orchestrator = Orchestrator()
        self.analysis = PolicyAnalysisAgent(llm)
        self.validation = ValidationAgent()
        self.db = Database(db_path)
        self.max_retries = max_retries

    def process(self, state: InsurMindsState) -> InsurMindsState:
        if state.status != RunStatus.EXTRACTING:
            raise ValueError('M3 expects state at EXTRACTING after M2')
        if not state.documents:
            raise ValueError('No document metadata available')
        doc = state.documents[-1]
        raw_text = state.raw_texts.get(doc['document_id'], '')
        attempt = 0
        feedback = None
        last_error = None
        while attempt <= self.max_retries:
            try:
                self.orchestrator.update_state(state, RunStatus.ANALYZING, self.analysis.name)
                t = perf_counter()
                candidate = self.analysis.process(raw_text=raw_text, document=doc, feedback=feedback)
                state.extracted_policies.append(candidate)
                state.trace.append(TraceEvent(agent=self.analysis.name,event='POLICY_CANDIDATE_EXTRACTED',status='SUCCESS',duration_ms=int((perf_counter()-t)*1000),details={'attempt':attempt+1}))
                self.orchestrator.update_state(state, RunStatus.VALIDATING, self.validation.name)
                t = perf_counter()
                policy = self.validation.process(candidate)
                state.validated_policies.append(policy)
                self.db.save_policy(state.run_id, policy)
                state.trace.append(TraceEvent(agent=self.validation.name,event='POLICY_VALIDATED',status='SUCCESS',duration_ms=int((perf_counter()-t)*1000),details={'attempt':attempt+1}))
                self.orchestrator.update_state(state, RunStatus.READY_TO_COMPARE, self.validation.name)
                state.metrics['intelligence_attempts'] = attempt + 1
                self.db.save_run(state)
                return state
            except (PolicyValidationError, StructuredOutputError) as exc:
                last_error = str(exc)
                state.warnings.append(retry_warning(attempt+1, exc))
                state.trace.append(TraceEvent(agent=self.validation.name,event='POLICY_VALIDATION_FAILED',status='WARNING',details={'attempt':attempt+1,'errors':exc.errors}))
                if attempt >= self.max_retries:
                    self.orchestrator.update_state(state, RunStatus.REVIEW_REQUIRED, self.validation.name)
                    state.metrics['intelligence_attempts'] = attempt + 1
                    self.db.save_run(state)
                    return state
                self.orchestrator.update_state(state, RunStatus.RETRYING, self.validation.name)
                feedback = feedback_from_errors(exc)
                attempt += 1
            except Exception as exc:
                self.orchestrator.register_error(state, str(exc), fatal=True)
                self.db.save_run(state)
                return state
        state.errors.append(last_error or 'Unknown intelligence pipeline error')
        return state
