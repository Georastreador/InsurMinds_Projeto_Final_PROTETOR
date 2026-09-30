from __future__ import annotations
from time import perf_counter
from agents.intake_agent import IntakeAgent
from agents.extraction_agent import ExtractionAgent
from storage.database import Database
from .orchestrator import Orchestrator
from .state import RunStatus, TraceEvent

class DocumentPipeline:
    def __init__(self, db_path='data/insurminds.db'):
        self.orchestrator=Orchestrator(); self.intake=IntakeAgent(); self.extraction=ExtractionAgent(); self.db=Database(db_path)
    def process_document(self,file_path):
        s=self.orchestrator.start_run(); self.db.save_run(s)
        try:
            self.orchestrator.update_state(s,RunStatus.INGESTING,self.intake.name)
            t=perf_counter(); d=self.intake.process(file_path); s.documents.append(d); self.db.save_document(s.run_id,d)
            s.trace.append(TraceEvent(agent=self.intake.name,event='DOCUMENT_VALIDATED',status='SUCCESS',duration_ms=int((perf_counter()-t)*1000),details={'document_id':d['document_id']}))
            self.orchestrator.update_state(s,RunStatus.EXTRACTING,self.extraction.name)
            e=self.extraction.process(d); s.raw_texts[d['document_id']]=e['text']; self.db.save_raw_text(s.run_id,e)
            s.metrics.update({'pages':e['pages'],'characters_extracted':e['characters_extracted'],'extraction_method':e['method'],'extraction_duration_ms':e['duration_ms']})
            s.trace.append(TraceEvent(agent=self.extraction.name,event='TEXT_EXTRACTED',status='SUCCESS',duration_ms=e['duration_ms'],details={'document_id':d['document_id'],'method':e['method']}))
            self.db.save_run(s); return s
        except Exception as exc:
            self.orchestrator.register_error(s,str(exc),fatal=True); self.db.save_run(s); return s
