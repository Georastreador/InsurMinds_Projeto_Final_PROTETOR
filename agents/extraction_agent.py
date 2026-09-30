from __future__ import annotations
from pathlib import Path
from time import perf_counter
from typing import Optional
from tools.pdf_tools import extract_pdf_text
from tools.ocr_tools import extract_with_ocr, OCRNotConfiguredError, OCREngine
from tools.text_budget import join_pages

class ExtractionError(RuntimeError): pass

class ExtractionAgent:
    """A2: native PDF text first; OCR only for images and pages without a text layer."""
    name='A2_EXTRACTION'

    def __init__(self, ocr: Optional[OCREngine] = None):
        self.ocr=ocr

    def process(self, document: dict) -> dict:
        start=perf_counter(); path=Path(document['source_path']); fmt=document['format']
        warnings=[]
        try:
            if fmt == 'PDF':
                parsed=extract_pdf_text(path)
                pages=parsed['page_texts']
                scanned=parsed['scanned_pages']
                if not scanned:
                    method='PYMUPDF'
                else:
                    ocr=extract_with_ocr(path, pages=scanned, ocr=self.ocr)
                    by_page={p['page']:p['text'] for p in ocr['page_texts']}
                    pages=[{'page':p['page'],'text':by_page.get(p['page'],p['text'])} for p in pages]
                    method=ocr['method'] if len(scanned)==len(pages) else f"PYMUPDF+{ocr['method']}"
                    warnings+=ocr['warnings']
                    warnings.append(f"{len(ocr['ocr_pages'])} página(s) sem camada de texto lida(s) por OCR ({ocr['method']}).")
            else:
                ocr=extract_with_ocr(path, ocr=self.ocr)
                pages=ocr['page_texts']; method=ocr['method']; warnings+=ocr['warnings']
        except OCRNotConfiguredError as e:
            raise ExtractionError(str(e)) from e
        except Exception as e:
            raise ExtractionError(f'Falha na extração: {e}') from e
        text=join_pages(pages) if any(p['text'].strip() for p in pages) else ''
        if not text:
            raise ExtractionError('Nenhum texto foi extraído do documento.')
        return {'document_id':document['document_id'],'pages':len(pages),'method':method,'text':text,
                'page_texts':pages,'characters_extracted':len(text),'warnings':warnings,
                'duration_ms':int((perf_counter()-start)*1000),'status':'SUCCESS'}
