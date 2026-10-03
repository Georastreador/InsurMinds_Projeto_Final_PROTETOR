"""Verification layer 4: LIVE robustness over the Test/Stress Dataset (non-D&O lines).

Usage:
    python -m evaluation.run_live_stress            # all pairs
    python -m evaluation.run_live_stress --pair 2   # one pair (0-based)

Each pair is checked against invariants (never FAILED, scope flagged, D&O structure
not applicable, no verdict language, disclosed page omissions). The synthetic
residential policy is also checked against its JSON answer key: identification,
term dates, and per-coverage limits and deductibles in BRL.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from schemas.do_taxonomy import fold
from guardrails.verdict import has_verdict

ROOT = Path(__file__).resolve().parents[1]
STRESS = ROOT / "datasets" / "stress_test"
PDFS = STRESS / "pdfs"
SYNTHETIC = STRESS / "synthetic_apolice_residencial.pdf"
RESULTS_DIR = ROOT / "evaluation" / "results"
OCR_DIR = ROOT / "data" / "ocr_test"  # built by: python -m evaluation.make_ocr_fixtures
SCANNED = OCR_DIR / "synthetic_apolice_residencial_digitalizada.pdf"
PAGE_PNG = OCR_DIR / "synthetic_apolice_residencial_p1.png"

PAIRS = [
    # (A, B, expected lines, purpose)
    (PDFS / "04_chubb_empresarial_pme_condicoes_gerais.pdf", PDFS / "02_bb_residencial_condicoes_gerais.pdf",
     ("empresarial", "residencial"), "Documento de 254 páginas (orçamento de entrada) e ramos diferentes"),
    (PDFS / "02_bb_residencial_condicoes_gerais.pdf", SYNTHETIC,
     ("residencial", "residencial"), "Mesmo ramo, condições gerais × apólice emitida com valores (gabarito)"),
    (PDFS / "06_apolice_seguro_garantia_publica.pdf", PDFS / "05_banrisul_vida_digital_condicoes_contratuais.pdf",
     ("garantia", "vida"), "Apólice emitida real × condições de vida (controle negativo D&O)"),
    (SCANNED, SYNTHETIC, ("residencial", "residencial"),
     "OCR: PDF digitalizado (só imagem) × mesmo documento em PDF nativo (gabarito)"),
    (PAGE_PNG, SYNTHETIC, ("residencial", "residencial"),
     "OCR: imagem PNG da página 1 × PDF nativo (gabarito de identificação e vigência)"),
]


def check(name: str, ok: bool, detail: str = "") -> dict:
    return {"check": name, "ok": bool(ok), "detail": detail}


def synthetic_checks(policy, identification_only: bool = False) -> list[dict]:
    gold = json.loads((STRESS / "synthetic_apolice_residencial.json").read_text(encoding="utf-8"))
    out = [
        check("sintética: seguradora", fold(gold["seguradora"]) in fold(policy.insurer), str(policy.insurer)),
        check("sintética: número da apólice", gold["numero_apolice"] in (policy.policy_number or ""), str(policy.policy_number)),
        check("sintética: segurado", fold(gold["segurado"]["nome"]) in fold(policy.insured_entity), str(policy.insured_entity)),
        check("sintética: início de vigência", str(policy.effective_date) == gold["vigencia"]["inicio"][:10], str(policy.effective_date)),
        check("sintética: fim de vigência", str(policy.expiration_date) == gold["vigencia"]["fim"][:10], str(policy.expiration_date)),
    ]
    if identification_only:
        return out
    coverages = {fold(c.name): c for c in policy.coverages}
    def find(name):
        key = fold(name)
        return next((c for k, c in coverages.items() if key in k or k in key), None)
    for g in gold["coberturas"]:
        c = find(g["nome"])
        if isinstance(g.get("limite"), (int, float)):
            got = c.limit.amount if c and c.limit else None
            out.append(check(f"sintética: limite '{g['nome']}'", got is not None and Decimal(str(got)) == Decimal(str(g["limite"])), str(got)))
        elif g.get("limite") is not None:  # non-monetary limit (e.g. "4 eventos por vigência"): no amount may be invented
            got = c.limit.amount if c and c.limit else None
            out.append(check(f"sintética: limite não monetário '{g['nome']}' sem valor inventado", got is None, str(got)))
        if g.get("franquia") is not None:
            money = (c.retention or c.sublimit) if c else None
            got = money.amount if money else None
            if got is None:  # deductible may be recorded in retentions
                got = next((r.amount.amount for r in policy.retentions if r.amount and fold(g["nome"])[:12] in fold(r.applies_to)), None)
            out.append(check(f"sintética: franquia '{g['nome']}'", got is not None and Decimal(str(got)) == Decimal(str(g["franquia"])), str(got)))
    return out


def run_pair(index: int) -> dict:
    import os
    from dotenv import load_dotenv
    from llm.factory import build_live_components
    from orchestration.mvp_pipeline import CompleteMVPPipeline
    load_dotenv(ROOT / ".env")
    a, b, lines, purpose = PAIRS[index]
    started = datetime.now()
    c = build_live_components()
    state = CompleteMVPPipeline(c.llm, semantic=c.semantic, writer=c.writer, ocr=c.ocr, guard=c.guard,
                                db_path=str(ROOT / "data" / "insurminds_protetor.db")).process(a, b)
    seconds = (datetime.now() - started).total_seconds()
    checks = [check("run não termina em FAILED", state.status.value in ("COMPLETED", "REVIEW_REQUIRED"), state.status.value)]
    if len(state.validated_policies) == 2:
        pa, pb = state.validated_policies
        got = tuple(p.line_of_business.value if p.line_of_business else None for p in (pa, pb))
        checks += [
            check("ramo identificado", got == lines, f"{got}"),
            check("escopo sinalizado como genérico", state.metrics.get("scope", "").startswith("Genérico"), state.metrics.get("scope", "")),
            check("aviso de ramo fora do escopo", any("validada apenas para D&O" in w for w in state.warnings)),
            check("Side A/B/C não aplicável", all(x.status.value == "NOT_APPLICABLE" for x in state.comparison.fields if x.field.startswith("insuring_side_"))),
            check("síntese sem linguagem de veredito", not has_verdict("\n".join(l for l in state.final_report.splitlines() if not l.startswith(">")))),
            check("evidências conferidas na página (≥ 90%)", all((v.get("verified_rate") or 0) >= 0.9 for v in state.metrics.get("evidence_check", {}).values()),
                  str({k: v.get("verified_rate") for k, v in state.metrics.get("evidence_check", {}).items()})),
            check("síntese gerada por IA", str(state.metrics.get("synthesis_method", "")).startswith("generative"), str(state.metrics.get("synthesis_method"))),
        ]
        for p in (pa, pb):
            if len(state.raw_texts.get(p.document_id, "")) > int(os.getenv("OPENAI_MAX_INPUT_CHARS", 300_000)):
                checks.append(check(f"omissão de páginas declarada ({p.source_file[:30]})", any("omitida" in w for w in p.warnings)))
            if Path(p.source_file).name.startswith("synthetic_apolice_residencial"):
                label = Path(p.source_file).name
                checks += [dict(c, check=f"{c['check']} [{label[:40]}]") for c in synthetic_checks(p, identification_only=label.endswith(".png"))]
        methods = {e.details.get("document_id"): e.details.get("method") for e in state.trace if e.event == "TEXT_EXTRACTED"}
        for p in (pa, pb):
            if p.source_file in (SCANNED.name, PAGE_PNG.name):
                checks.append(check(f"extração por OCR ({p.source_file[:40]})", "OCR" in str(methods.get(p.document_id)), str(methods.get(p.document_id))))
        if a == SCANNED:
            same = [x for x in state.comparison.fields if x.field in ("policy_number", "insurer", "insured_entity", "effective_date", "expiration_date")]
            checks.append(check("OCR × nativo: identificação e vigência iguais", all(x.status.value == "EQUAL" for x in same),
                                str({x.field: x.status.value for x in same})))
    return {"pair": index, "purpose": purpose, "a": a.name, "b": b.name, "run_id": state.run_id,
            "status": state.status.value, "seconds": round(seconds, 1), "errors": state.errors,
            "comparison_fields": len(state.comparison.fields) if state.comparison else 0,
            "checks": checks, "passed": all(c["ok"] for c in checks)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", type=int, choices=range(len(PAIRS)))
    args = parser.parse_args()
    indices = [args.pair] if args.pair is not None else list(range(len(PAIRS)))
    results = []
    for i in indices:
        r = run_pair(i); results.append(r)
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] par {i} · {r['a'][:32]} × {r['b'][:32]} · {r['status']} · {r['seconds']}s")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"    ✗ {c['check']}: {c['detail']}")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"STRESS_LIVE_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
