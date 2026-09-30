from __future__ import annotations
from time import perf_counter
from agents.intake_agent import IntakeAgent
from agents.extraction_agent import ExtractionAgent
from agents.policy_agent import PolicyAnalysisAgent
from agents.validation_agent import ValidationAgent, PolicyValidationError, feedback_from_errors, retry_warning
from llm.client import StructuredOutputError
from agents.comparison_agent import ComparisonAgent
from agents.synthesis_agent import SynthesisAgent
from storage.database import Database
from .orchestrator import Orchestrator
from .scope import assess_scope, reconcile_line_of_business
from schemas.labels import display_name
from .state import RunStatus, TraceEvent
from .progress import ProgressCallback, estimate_analysis_seconds, fmt_chars, fmt_duration, fmt_pages

class CompleteMVPPipeline:
    """Runs two documents under one run_id through A1 -> A6."""
    def __init__(self, llm, semantic=None, db_path="data/insurminds_protetor.db", max_retries=2, writer=None,
                 progress: ProgressCallback | None = None, ocr=None):
        self.orchestrator=Orchestrator()
        self.intake=IntakeAgent()
        self.extraction=ExtractionAgent(ocr)
        self.analysis=PolicyAnalysisAgent(llm)
        self.validation=ValidationAgent()
        self.comparison=ComparisonAgent(semantic)
        self.synthesis=SynthesisAgent(writer)
        self.db=Database(db_path)
        self.max_retries=max_retries
        self.progress=progress
        # Input budget of the LIVE adapter; None for offline extractors (no LLM latency).
        self.input_budget=getattr(llm,"max_input_chars",None)

    # Share of the progress bar: document A in [0, .42), document B in [.42, .84), A5, A6, done.
    _DOC_SPAN=0.42

    def _emit(self, message, fraction):
        if self.progress:
            self.progress(message, min(max(fraction,0.0),1.0))

    def _ingest_extract_analyze_validate(self, state, file_path, label="Documento", index=0):
        base=index*self._DOC_SPAN
        # For the second document, continue the same run by returning to INGESTING
        # from READY_TO_COMPARE through an explicit local cycle represented in trace.
        if state.status == RunStatus.CREATED:
            self.orchestrator.update_state(state, RunStatus.INGESTING, self.intake.name)
        elif state.status == RunStatus.READY_TO_COMPARE:
            state.status = RunStatus.INGESTING
            state.current_agent = self.intake.name
            state.trace.append(TraceEvent(agent="ORCHESTRATOR",event="NEXT_DOCUMENT_CYCLE",status="INGESTING"))

        self._emit(f"A1/A2 · {label}: validando e extraindo o texto (páginas digitalizadas passam por OCR)…",base)
        t=perf_counter()
        doc=self.intake.process(file_path)
        state.documents.append(doc); self.db.save_document(state.run_id,doc)
        state.trace.append(TraceEvent(agent=self.intake.name,event="DOCUMENT_VALIDATED",status="SUCCESS",
                                      duration_ms=int((perf_counter()-t)*1000),details={"document_id":doc["document_id"]}))

        self.orchestrator.update_state(state,RunStatus.EXTRACTING,self.extraction.name)
        ext=self.extraction.process(doc)
        state.raw_texts[doc["document_id"]]=ext["text"]; self.db.save_raw_text(state.run_id,ext)
        state.trace.append(TraceEvent(agent=self.extraction.name,event="TEXT_EXTRACTED",status="SUCCESS",
                                      duration_ms=ext["duration_ms"],details={"document_id":doc["document_id"],"method":ext["method"],
                                                                              "pages":ext["pages"],"warnings":ext.get("warnings",[])}))
        state.warnings.extend(f"{label}: {w}" for w in ext.get("warnings",[]))
        chars=len(ext["text"]); estimate=estimate_analysis_seconds(chars,self.input_budget)
        size=f"{label} ({doc['filename']}): {fmt_pages(ext['pages'])}, {fmt_chars(chars)}."
        if "OCR" in ext["method"]:
            size+=f" Texto obtido por OCR ({ext['method']}) em {fmt_duration(ext['duration_ms']/1000)}."
        if self.input_budget and chars>self.input_budget:
            size+=f" Acima do limite de {fmt_chars(self.input_budget)}: as páginas com menos termos contratuais serão omitidas (com aviso)."
        self._emit(size,base+0.03)

        attempt=0; feedback=None
        while attempt <= self.max_retries:
            try:
                self.orchestrator.update_state(state,RunStatus.ANALYZING,self.analysis.name)
                tentativa="" if attempt==0 else f" (nova tentativa {attempt+1})"
                if self.input_budget is None:
                    self._emit(f"A3 · estruturando {label} (extrator heurístico DEMO){tentativa}",base+0.05)
                else:
                    self._emit(f"A3 · estruturando {label} com IA{tentativa} — estimativa ~{fmt_duration(estimate)}",base+0.05)
                t=perf_counter()
                candidate=self.analysis.process(raw_text=ext["text"],document=doc,feedback=feedback)
                state.extracted_policies.append(candidate)
                state.trace.append(TraceEvent(agent=self.analysis.name,event="POLICY_CANDIDATE_EXTRACTED",status="SUCCESS",
                                              duration_ms=int((perf_counter()-t)*1000),details={"attempt":attempt+1,"document_id":doc["document_id"]}))
                self.orchestrator.update_state(state,RunStatus.VALIDATING,self.validation.name)
                t=perf_counter()
                policy=self.validation.process(candidate)
                state.validated_policies.append(policy); self.db.save_policy(state.run_id,policy)
                state.trace.append(TraceEvent(agent=self.validation.name,event="POLICY_VALIDATED",status="SUCCESS",
                                              duration_ms=int((perf_counter()-t)*1000),details={"attempt":attempt+1,"document_id":doc["document_id"]}))
                self.orchestrator.update_state(state,RunStatus.READY_TO_COMPARE,self.validation.name)
                elapsed=sum(e.duration_ms or 0 for e in state.trace if e.event=="POLICY_CANDIDATE_EXTRACTED"
                            and e.details.get("document_id")==doc["document_id"])/1000
                self._emit(f"✓ {label} estruturado e validado em {fmt_duration(elapsed)}",base+self._DOC_SPAN)
                return
            except (PolicyValidationError, StructuredOutputError) as exc:
                state.warnings.append(retry_warning(attempt+1, exc))
                state.trace.append(TraceEvent(agent=self.validation.name,event="POLICY_VALIDATION_FAILED",status="WARNING",
                                              details={"attempt":attempt+1,"errors":exc.errors}))
                if attempt >= self.max_retries:
                    self.orchestrator.update_state(state,RunStatus.REVIEW_REQUIRED,self.validation.name)
                    raise
                self._emit(f"A4 · {label}: resposta rejeitada pela validação; o A3 fará nova tentativa com os erros apontados",base+0.2)
                self.orchestrator.update_state(state,RunStatus.RETRYING,self.validation.name)
                feedback=feedback_from_errors(exc)
                attempt += 1

    def process(self, file_a, file_b):
        state=self.orchestrator.start_run(); self.db.save_run(state)
        started=perf_counter()
        try:
            self._ingest_extract_analyze_validate(state,file_a,"Documento A",0)
            self._ingest_extract_analyze_validate(state,file_b,"Documento B",1)

            for pol in state.validated_policies:
                note=reconcile_line_of_business(pol,state.raw_texts.get(pol.document_id,""))
                if note: state.trace.append(TraceEvent(agent="ORCHESTRATOR",event="LINE_OF_BUSINESS_RECONCILED",status="WARNING",
                                                       details={"document_id":pol.document_id,"note":note}))
            scope,scope_warnings=assess_scope(state.validated_policies)
            state.metrics.update(scope); state.warnings.extend(scope_warnings)
            state.trace.append(TraceEvent(agent="ORCHESTRATOR",event="SCOPE_ASSESSED",status=scope["scope"],details=scope))

            self.orchestrator.update_state(state,RunStatus.COMPARING,self.comparison.name)
            live=self.input_budget is not None
            self._emit("A5 · comparando coberturas, exclusões, franquias e cláusulas"+(" — estimativa ~30 s" if live else ""),0.85)
            t=perf_counter()
            result=self.comparison.compare(state.run_id,state.validated_policies[0],state.validated_policies[1])
            state.comparison=result; self.db.save_comparison(state.run_id,result)
            state.trace.append(TraceEvent(agent=self.comparison.name,event="POLICIES_COMPARED",status="SUCCESS",
                                          duration_ms=int((perf_counter()-t)*1000),
                                          details={"fields":len(result.fields),"review_required":sum(1 for x in result.fields if x.review_required)}))
            state.metrics["comparison_fields"]=len(result.fields)
            state.metrics["comparison_review_required"]=sum(1 for x in result.fields if x.review_required)
            state.warnings.extend(result.warnings)

            self.orchestrator.update_state(state,RunStatus.SYNTHESIZING,self.synthesis.name)
            self._emit("A6 · redigindo a síntese executiva"+(" — estimativa ~15 s" if live else ""),0.94)
            t=perf_counter()
            pa,pb=state.validated_policies
            context={"name_a":display_name(pa,"Documento A"),"name_b":display_name(pb,"Documento B"),
                     **{k:state.metrics.get(k) for k in ("scope","lines_of_business","general_conditions_only")}}
            report=self.synthesis.process(result,context)
            state.metrics["synthesis_method"]=self.synthesis.last_method
            if self.synthesis.last_warning: state.warnings.append(self.synthesis.last_warning)
            state.final_report=report; self.db.save_report(state.run_id,report)
            state.trace.append(TraceEvent(agent=self.synthesis.name,event="REPORT_SYNTHESIZED",status="SUCCESS",
                                          duration_ms=int((perf_counter()-t)*1000),details={"characters":len(report),"method":self.synthesis.last_method}))
            self.orchestrator.finish_run(state)
            state.metrics["duration_s"]=round(perf_counter()-started,1)
            self._emit(f"Concluído em {fmt_duration(state.metrics['duration_s'])}",1.0)
            self.db.save_run(state)
            return state
        except Exception as exc:
            if state.status not in {RunStatus.FAILED,RunStatus.REVIEW_REQUIRED}:
                self.orchestrator.register_error(state,str(exc),fatal=True)
            state.metrics["duration_s"]=round(perf_counter()-started,1)
            self._emit(f"Execução interrompida ({state.status.value}) após {fmt_duration(state.metrics['duration_s'])}",1.0)
            self.db.save_run(state)
            return state
