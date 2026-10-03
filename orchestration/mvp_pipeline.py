from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Optional

from agents.comparison_agent import ComparisonAgent
from agents.extraction_agent import ExtractionAgent
from agents.intake_agent import IntakeAgent
from agents.policy_agent import PolicyAnalysisAgent
from agents.synthesis_agent import SynthesisAgent
from agents.validation_agent import PolicyValidationError, ValidationAgent, feedback_from_errors, retry_warning
from guardrails.injection import detect_injection
from guardrails.verdict import VerdictGuard
from llm.client import StructuredOutputError
from llm.provider import is_transient
from llm.usage import UsageLedger
from schemas.labels import display_name
from schemas.policy import PolicySchema
from storage.database import Database
from tools.evidence_check import summary_warning, verify_policy
from tools.privacy import maybe_redact
from .orchestrator import Orchestrator
from .progress import ProgressCallback, estimate_analysis_seconds, fmt_chars, fmt_duration, fmt_pages
from .scope import assess_scope, reconcile_line_of_business
from .state import RunStatus, TraceEvent


class TransientProviderError(RuntimeError):
    """Wraps a provider error that persisted after the SDK retries; one more A3 attempt is allowed."""
    def __init__(self, exc: BaseException):
        super().__init__(f"{type(exc).__name__}: {exc}"); self.errors = [{"loc": ("provider",), "msg": str(exc)[:200]}]


@dataclass
class DocumentOutcome:
    """Everything one document produced in A1→A4. Built by a worker without touching the shared state."""
    label: str
    doc: Optional[dict[str, Any]] = None
    extraction: Optional[dict[str, Any]] = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    policy: Optional[PolicySchema] = None
    events: list[TraceEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    attempts: int = 0
    evidence: Optional[dict[str, Any]] = None
    review_required: bool = False
    error: Optional[BaseException] = None


class CompleteMVPPipeline:
    """Runs two documents under one run_id through A1 -> A6.

    v1.3: documents A and B go through A1→A4 concurrently when the extraction adapter is
    stateless (`supports_parallel`); every state change goes through the Orchestrator; the
    evidence of each validated policy is verified against the page text; prompt-injection
    attempts are flagged; provider token usage is recorded per stage.
    """
    _DOC_SPAN = 0.84  # documents share [0, .84); A5 and A6 take the rest

    def __init__(self, llm, semantic=None, db_path="data/insurminds_protetor.db", max_retries=2, writer=None,
                 progress: ProgressCallback | None = None, ocr=None, guard: Optional[VerdictGuard] = None,
                 parallel: Optional[bool] = None):
        self.orchestrator = Orchestrator()
        self.intake = IntakeAgent()
        self.extraction = ExtractionAgent(ocr)
        self.analysis = PolicyAnalysisAgent(llm)
        self.validation = ValidationAgent()
        self.comparison = ComparisonAgent(semantic)
        self.guard = guard or VerdictGuard()
        self.synthesis = SynthesisAgent(writer, self.guard)
        self.db = Database(db_path)
        self.max_retries = max_retries
        self.progress = progress
        self.parallel = getattr(llm, "supports_parallel", False) if parallel is None else parallel
        # Input budget of the LIVE adapter; None for offline extractors (no LLM latency).
        self.input_budget = getattr(llm, "max_input_chars", None)
        self.ledger = UsageLedger()
        for component in (llm, semantic, writer, ocr, getattr(self.guard, "classifier", None)):
            if component is not None and hasattr(component, "ledger"):
                component.ledger = self.ledger
        self._last_fraction = 0.0
        self._doc_fraction: dict[str, float] = {}

    # --- progress -----------------------------------------------------------------
    def _emit(self, message, fraction):
        fraction = max(self._last_fraction, min(max(fraction, 0.0), 1.0))  # monotonic, also with parallel docs
        self._last_fraction = fraction
        if self.progress:
            self.progress(message, fraction)

    def _doc_progress(self, label: str, local: float, message: str):
        self._doc_fraction[label] = max(self._doc_fraction.get(label, 0.0), local)
        overall = self._DOC_SPAN * sum(self._doc_fraction.values()) / 2
        self._emit(message, overall)

    # --- A1 → A4 for one document (no shared state) --------------------------------
    def _process_document(self, file_path, label: str, notify) -> DocumentOutcome:
        out = DocumentOutcome(label=label)
        try:
            notify(label, 0.0, f"A1/A2 · {label}: validando e extraindo o texto (páginas digitalizadas passam por OCR)…")
            t = perf_counter()
            doc = out.doc = self.intake.process(file_path)
            out.events.append(TraceEvent(agent=self.intake.name, event="DOCUMENT_VALIDATED", status="SUCCESS",
                                         duration_ms=int((perf_counter() - t) * 1000), details={"document_id": doc["document_id"]}))
            ext = out.extraction = self.extraction.process(doc)
            out.events.append(TraceEvent(agent=self.extraction.name, event="TEXT_EXTRACTED", status="SUCCESS",
                                         duration_ms=ext["duration_ms"], details={"document_id": doc["document_id"], "method": ext["method"],
                                                                                   "pages": ext["pages"], "warnings": ext.get("warnings", [])}))
            out.warnings += [f"{label}: {w}" for w in ext.get("warnings", [])]
            injection = detect_injection(ext["text"])
            if injection:
                out.warnings.append(f"{label}: trechos com formato de instrução a um modelo de IA foram encontrados no documento "
                                    "e tratados como conteúdo (possível tentativa de prompt injection). Conferir o original.")
                out.events.append(TraceEvent(agent="ORCHESTRATOR", event="PROMPT_INJECTION_SUSPECTED", status="WARNING",
                                             details={"document_id": doc["document_id"], "snippets": injection}))
            chars = len(ext["text"])
            size = f"{label} ({doc['filename']}): {fmt_pages(ext['pages'])}, {fmt_chars(chars)}."
            if "OCR" in ext["method"]:
                size += f" Texto obtido por OCR ({ext['method']}) em {fmt_duration(ext['duration_ms'] / 1000)}."
            if self.input_budget and chars > self.input_budget:
                size += f" Acima do limite de {fmt_chars(self.input_budget)}: as páginas com menos termos contratuais serão omitidas (com aviso)."
            notify(label, 0.08, size)

            estimate = estimate_analysis_seconds(chars, self.input_budget)
            feedback = None
            while True:
                attempt = out.attempts
                out.attempts += 1
                tentativa = "" if attempt == 0 else f" (nova tentativa {attempt + 1})"
                if self.input_budget is None:
                    notify(label, 0.12, f"A3 · estruturando {label} (extrator heurístico DEMO){tentativa}")
                else:
                    notify(label, 0.12, f"A3 · estruturando {label} com IA{tentativa} — estimativa ~{fmt_duration(estimate)}")
                try:
                    t = perf_counter()
                    try:
                        candidate = self.analysis.process(raw_text=ext["text"], document=doc, feedback=feedback)
                    except Exception as exc:
                        if is_transient(exc):
                            raise TransientProviderError(exc) from exc
                        raise
                    out.candidates.append(candidate)
                    out.events.append(TraceEvent(agent=self.analysis.name, event="POLICY_CANDIDATE_EXTRACTED", status="SUCCESS",
                                                 duration_ms=int((perf_counter() - t) * 1000),
                                                 details={"attempt": attempt + 1, "document_id": doc["document_id"]}))
                    t = perf_counter()
                    policy = self.validation.process(candidate)
                    out.events.append(TraceEvent(agent=self.validation.name, event="POLICY_VALIDATED", status="SUCCESS",
                                                 duration_ms=int((perf_counter() - t) * 1000),
                                                 details={"attempt": attempt + 1, "document_id": doc["document_id"]}))
                except (PolicyValidationError, StructuredOutputError, TransientProviderError) as exc:
                    out.warnings.append(retry_warning(attempt + 1, exc))
                    out.events.append(TraceEvent(agent=self.validation.name, event="POLICY_VALIDATION_FAILED", status="WARNING",
                                                 details={"attempt": attempt + 1, "document_id": doc["document_id"], "errors": exc.errors}))
                    if attempt >= self.max_retries:
                        out.review_required = True; out.error = exc
                        return out
                    notify(label, 0.4, f"A4 · {label}: resposta rejeitada pela validação; o A3 fará nova tentativa com os erros apontados")
                    feedback = feedback_from_errors(exc)
                    continue
                break

            # Claim -> Evidence verification against the page text (A3 saw the PII-masked text).
            masked = [{"page": p["page"], "text": maybe_redact(p["text"])[0]} for p in ext["page_texts"]]
            out.evidence = verify_policy(policy, ext["page_texts"], masked)
            note = summary_warning(label, out.evidence)
            if note:
                out.warnings.append(note); policy.warnings.append(note)
            out.events.append(TraceEvent(agent="ORCHESTRATOR", event="EVIDENCE_VERIFIED", status="WARNING" if note else "SUCCESS",
                                         details={"document_id": doc["document_id"], **out.evidence}))
            out.policy = policy
            elapsed = sum(e.duration_ms or 0 for e in out.events if e.event == "POLICY_CANDIDATE_EXTRACTED") / 1000
            notify(label, 1.0, f"✓ {label} estruturado e validado em {fmt_duration(elapsed)}")
            return out
        except Exception as exc:  # intake/extraction/non-retryable provider errors
            out.error = exc
            return out

    def _run_documents(self, files: list[tuple[Any, str]]) -> list[DocumentOutcome]:
        if not self.parallel:
            outcomes = []
            for f, label in files:
                outcomes.append(self._process_document(f, label, self._doc_progress))
                if outcomes[-1].error is not None:  # sequential: do not spend effort on B when A already failed
                    break
            return outcomes
        messages: queue.Queue = queue.Queue()
        notify = lambda label, local, msg: messages.put((label, local, msg))  # noqa: E731 — workers never touch the UI
        with ThreadPoolExecutor(max_workers=len(files)) as pool:
            futures = [pool.submit(self._process_document, f, label, notify) for f, label in files]
            while not all(f.done() for f in futures) or not messages.empty():
                try:
                    self._doc_progress(*messages.get(timeout=0.2))
                except queue.Empty:
                    pass
            return [f.result() for f in futures]

    def _merge(self, state, outcomes: list[DocumentOutcome]) -> None:
        """Bring the per-document results into the run state, in A/B order, through the Orchestrator."""
        for o in outcomes:
            if o.doc:
                state.documents.append(o.doc); self.db.save_document(state.run_id, o.doc)
            if o.extraction:
                state.raw_texts[o.doc["document_id"]] = o.extraction["text"]; self.db.save_raw_text(state.run_id, o.extraction)
            state.extracted_policies += o.candidates
            state.trace += o.events
            state.warnings += o.warnings
            if o.evidence is not None:
                state.metrics.setdefault("evidence_check", {})[o.label] = {k: v for k, v in o.evidence.items() if k != "wrong_page_examples"}
        state.metrics["documents_in_parallel"] = self.parallel
        state.metrics["a3_attempts"] = {o.label: o.attempts for o in outcomes}

        failed = next((o for o in outcomes if o.error is not None and not o.review_required), None)
        if failed is not None:
            raise failed.error
        self.orchestrator.update_state(state, RunStatus.EXTRACTING, self.extraction.name)
        self.orchestrator.update_state(state, RunStatus.ANALYZING, self.analysis.name)
        for _ in range(max(o.attempts for o in outcomes) - 1):
            self.orchestrator.update_state(state, RunStatus.VALIDATING, self.validation.name)
            self.orchestrator.update_state(state, RunStatus.RETRYING, self.validation.name)
            self.orchestrator.update_state(state, RunStatus.ANALYZING, self.analysis.name)
        self.orchestrator.update_state(state, RunStatus.VALIDATING, self.validation.name)
        review = next((o for o in outcomes if o.review_required), None)
        if review is not None:
            self.orchestrator.update_state(state, RunStatus.REVIEW_REQUIRED, self.validation.name)
            raise review.error
        for o in outcomes:
            state.validated_policies.append(o.policy); self.db.save_policy(state.run_id, o.policy)
        self.orchestrator.update_state(state, RunStatus.READY_TO_COMPARE, self.validation.name)

    # --- run ----------------------------------------------------------------------
    def process(self, file_a, file_b):
        state = self.orchestrator.start_run(); self.db.save_run(state)
        started = perf_counter()
        self._last_fraction, self._doc_fraction = 0.0, {}
        try:
            self.orchestrator.update_state(state, RunStatus.INGESTING, self.intake.name)
            outcomes = self._run_documents([(file_a, "Documento A"), (file_b, "Documento B")])
            self._merge(state, outcomes)

            for pol in state.validated_policies:
                note = reconcile_line_of_business(pol, state.raw_texts.get(pol.document_id, ""))
                if note:
                    state.trace.append(TraceEvent(agent="ORCHESTRATOR", event="LINE_OF_BUSINESS_RECONCILED", status="WARNING",
                                                  details={"document_id": pol.document_id, "note": note}))
            scope, scope_warnings = assess_scope(state.validated_policies)
            state.metrics.update(scope); state.warnings.extend(scope_warnings)
            state.trace.append(TraceEvent(agent="ORCHESTRATOR", event="SCOPE_ASSESSED", status=scope["scope"], details=scope))

            self.orchestrator.update_state(state, RunStatus.COMPARING, self.comparison.name)
            live = self.input_budget is not None
            self._emit("A5 · comparando coberturas, exclusões, franquias e cláusulas" + (" — estimativa ~30 s" if live else ""), 0.85)
            t = perf_counter()
            result = self.comparison.compare(state.run_id, state.validated_policies[0], state.validated_policies[1])
            state.comparison = result; self.db.save_comparison(state.run_id, result)
            review_count = sum(1 for x in result.fields if x.review_required)
            state.trace.append(TraceEvent(agent=self.comparison.name, event="POLICIES_COMPARED", status="SUCCESS",
                                          duration_ms=int((perf_counter() - t) * 1000),
                                          details={"fields": len(result.fields), "review_required": review_count}))
            state.metrics["comparison_fields"] = len(result.fields)
            state.metrics["comparison_review_required"] = review_count
            state.warnings.extend(result.warnings)

            self.orchestrator.update_state(state, RunStatus.SYNTHESIZING, self.synthesis.name)
            self._emit("A6 · redigindo a síntese executiva" + (" — estimativa ~15 s" if live else ""), 0.94)
            t = perf_counter()
            pa, pb = state.validated_policies
            context = {"name_a": display_name(pa, "Documento A"), "name_b": display_name(pb, "Documento B"),
                       **{k: state.metrics.get(k) for k in ("scope", "lines_of_business", "general_conditions_only")}}
            report = self.synthesis.process(result, context)
            state.metrics["synthesis_method"] = self.synthesis.last_method
            if self.synthesis.last_guard:
                state.metrics["verdict_guard"] = self.synthesis.last_guard
            if self.synthesis.last_warning:
                state.warnings.append(self.synthesis.last_warning)
            state.final_report = report; self.db.save_report(state.run_id, report)
            state.trace.append(TraceEvent(agent=self.synthesis.name, event="REPORT_SYNTHESIZED", status="SUCCESS",
                                          duration_ms=int((perf_counter() - t) * 1000),
                                          details={"characters": len(report), "method": self.synthesis.last_method}))
            self.orchestrator.finish_run(state)
            return self._close(state, started, f"Concluído em {{}}")
        except Exception as exc:
            if state.status not in {RunStatus.FAILED, RunStatus.REVIEW_REQUIRED}:
                self.orchestrator.register_error(state, str(exc), fatal=True)
            elif str(exc) and str(exc) not in state.errors:
                state.errors.append(str(exc))
            return self._close(state, started, f"Execução interrompida ({state.status.value}) após {{}}")

    def _close(self, state, started, template: str):
        state.metrics["duration_s"] = round(perf_counter() - started, 1)
        state.metrics["llm_usage"] = self.ledger.summary()
        self._emit(template.format(fmt_duration(state.metrics["duration_s"])), 1.0)
        self.db.save_run(state)
        return state
