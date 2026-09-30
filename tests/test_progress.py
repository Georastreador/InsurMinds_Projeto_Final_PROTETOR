from pathlib import Path
import pymupdf
from llm.client import DeterministicLLMClient
from orchestration.mvp_pipeline import CompleteMVPPipeline
from orchestration.progress import estimate_analysis_seconds, estimate_run_seconds, fmt_duration


def make_pdf(path: Path, text: str):
    d = pymupdf.open(); d.new_page().insert_text((72, 72), text); d.save(path); d.close()


def response(n):
    return {"policy_number": n, "insurer": "Alpha Seguros", "retentions": [], "insuring_agreements": [], "coverages": [],
            "sublimits": [], "exclusions": [], "clauses": [], "extensions": [], "source_references": [], "warnings": []}


def test_pipeline_reports_monotonic_progress_by_agent(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    make_pdf(a, "A"); make_pdf(b, "B")
    events = []
    llm = DeterministicLLMClient([response("A"), response("B")])
    state = CompleteMVPPipeline(llm, db_path=tmp_path / "p.db", progress=lambda m, f: events.append((m, f))).process(a, b)
    fractions = [f for _, f in events]
    assert fractions == sorted(fractions) and fractions[-1] == 1.0
    text = " ".join(m for m, _ in events)
    for marker in ("Documento A", "Documento B", "A3 ·", "A5 ·", "A6 ·", "Concluído em"):
        assert marker in text
    assert state.metrics["duration_s"] >= 0


def test_estimates_scale_with_size_and_respect_budget():
    assert estimate_analysis_seconds(2_000, 300_000) < estimate_analysis_seconds(200_000, 300_000)
    assert estimate_analysis_seconds(600_000, 300_000) == estimate_analysis_seconds(300_000, 300_000)
    assert estimate_run_seconds([200_000, 120_000], None) < 10
    assert fmt_duration(100) == "1 min 40 s" and fmt_duration(42) == "42 s"
