from pathlib import Path
import fitz
import pytest
from agents.intake_agent import IntakeAgent, IntakeError
from agents.extraction_agent import ExtractionAgent
from orchestration.pipeline import DocumentPipeline
from orchestration.state import RunStatus
from storage.database import Database

def make_pdf(path: Path, text='Apólice D&O - Limite de Responsabilidade: R$ 10.000.000'):
    doc=fitz.open(); page=doc.new_page(); page.insert_text((72,72),text); doc.save(path); doc.close()

def test_intake_accepts_pdf(tmp_path):
    p=tmp_path/'policy.pdf'; make_pdf(p); d=IntakeAgent().process(p); assert d['format']=='PDF' and d['status']=='VALID'

def test_intake_rejects_empty(tmp_path):
    p=tmp_path/'empty.pdf'; p.write_bytes(b'')
    with pytest.raises(IntakeError): IntakeAgent().process(p)

def test_extract_text_pdf(tmp_path):
    p=tmp_path/'policy.pdf'; make_pdf(p,'Seguro D&O teste')
    d=IntakeAgent().process(p); e=ExtractionAgent().process(d)
    assert e['method']=='PYMUPDF' and 'Seguro D&O teste' in e['text'] and e['pages']==1

def test_database_roundtrip(tmp_path):
    db=Database(tmp_path/'test.db'); p=tmp_path/'policy.pdf'; make_pdf(p)
    d=IntakeAgent().process(p); e=ExtractionAgent().process(d)
    db.save_document('run-1',d); db.save_raw_text('run-1',e)
    assert 'Limite de Responsabilidade' in db.get_raw_text(d['document_id'])

def test_pipeline_integration(tmp_path):
    p=tmp_path/'policy.pdf'; make_pdf(p,'Apólice D&O integrada')
    pipeline=DocumentPipeline(tmp_path/'pipeline.db'); s=pipeline.process_document(p)
    assert s.status == RunStatus.EXTRACTING
    assert len(s.documents)==1 and len(s.raw_texts)==1
    assert s.metrics['extraction_method']=='PYMUPDF'
    assert not s.errors
