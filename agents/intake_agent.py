from __future__ import annotations
from pathlib import Path
from uuid import uuid4
from typing import Any

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}

class IntakeError(ValueError): pass

class IntakeAgent:
    name = 'A1_INTAKE'
    def process(self, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists() or not path.is_file(): raise IntakeError('Arquivo não encontrado.')
        if path.stat().st_size == 0: raise IntakeError('Arquivo vazio.')
        ext = path.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS: raise IntakeError(f'Formato não suportado: {ext or "sem extensão"}')
        return {'document_id': str(uuid4()), 'filename': path.name, 'source_path': str(path.resolve()),
                'format': 'JPEG' if ext in {'.jpg','.jpeg'} else ext[1:].upper(),
                'size_bytes': path.stat().st_size, 'status': 'VALID'}
