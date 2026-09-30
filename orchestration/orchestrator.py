from __future__ import annotations
from uuid import uuid4
from .state import InsurMindsState, RunStatus, TraceEvent


ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.CREATED: {RunStatus.INGESTING, RunStatus.FAILED},
    RunStatus.INGESTING: {RunStatus.EXTRACTING, RunStatus.WARNING, RunStatus.FAILED},
    RunStatus.EXTRACTING: {RunStatus.ANALYZING, RunStatus.WARNING, RunStatus.FAILED},
    RunStatus.ANALYZING: {RunStatus.VALIDATING, RunStatus.RETRYING, RunStatus.REVIEW_REQUIRED, RunStatus.FAILED},
    RunStatus.VALIDATING: {RunStatus.READY_TO_COMPARE, RunStatus.RETRYING, RunStatus.REVIEW_REQUIRED, RunStatus.FAILED},
    RunStatus.RETRYING: {RunStatus.ANALYZING, RunStatus.REVIEW_REQUIRED, RunStatus.FAILED},
    RunStatus.READY_TO_COMPARE: {RunStatus.COMPARING, RunStatus.FAILED},
    RunStatus.COMPARING: {RunStatus.SYNTHESIZING, RunStatus.REVIEW_REQUIRED, RunStatus.FAILED},
    RunStatus.SYNTHESIZING: {RunStatus.COMPLETED, RunStatus.WARNING, RunStatus.FAILED},
    RunStatus.WARNING: {RunStatus.EXTRACTING, RunStatus.ANALYZING, RunStatus.VALIDATING, RunStatus.COMPARING, RunStatus.SYNTHESIZING, RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.REVIEW_REQUIRED: {RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}


class InvalidTransitionError(ValueError):
    pass


class Orchestrator:
    def start_run(self) -> InsurMindsState:
        state = InsurMindsState(run_id=str(uuid4()))
        state.trace.append(TraceEvent(agent="ORCHESTRATOR", event="RUN_CREATED", status=state.status.value))
        return state

    def update_state(self, state: InsurMindsState, new_status: RunStatus, current_agent: str | None = None) -> InsurMindsState:
        allowed = ALLOWED_TRANSITIONS[state.status]
        if new_status not in allowed:
            raise InvalidTransitionError(f"Invalid transition: {state.status.value} -> {new_status.value}")
        old = state.status
        state.status = new_status
        state.current_agent = current_agent
        state.trace.append(TraceEvent(
            agent=current_agent or "ORCHESTRATOR",
            event=f"STATE_{old.value}_TO_{new_status.value}",
            status=new_status.value,
        ))
        return state

    def register_error(self, state: InsurMindsState, message: str, fatal: bool = False) -> InsurMindsState:
        state.errors.append(message)
        if fatal and state.status != RunStatus.FAILED:
            if RunStatus.FAILED in ALLOWED_TRANSITIONS[state.status]:
                self.update_state(state, RunStatus.FAILED, "ORCHESTRATOR")
        return state

    def finish_run(self, state: InsurMindsState) -> InsurMindsState:
        return self.update_state(state, RunStatus.COMPLETED, "ORCHESTRATOR")
