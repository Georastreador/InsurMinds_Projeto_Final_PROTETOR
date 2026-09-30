"""Entry point for M6 quality evaluation. No new agent is created here."""
import json
from pathlib import Path
from .models import GoldenPolicyAnnotation
from .evaluator import QualityEvaluator
from observability.quality_report import ObservabilityReport

def load_gold(path):
    return GoldenPolicyAnnotation.model_validate_json(Path(path).read_text(encoding="utf-8"))

def save_report(results,path):
    report=ObservabilityReport().build_quality_report(results)
    Path(path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report
