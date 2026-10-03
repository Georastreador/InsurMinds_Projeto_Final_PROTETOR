from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import os
import tempfile
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from llm.client import DemoHeuristicLLMClient, OpenAIQueryResponder, OpenAIStructuredLLMClient, OpenAIVerdictClassifier
from llm.factory import build_live_components
from guardrails.verdict import VerdictGuard
from agents.query_agent import GROUPS, QueryAgent, catalog, search
from storage.database import Database
from orchestration.mvp_pipeline import CompleteMVPPipeline
from orchestration.state import InsurMindsState
from orchestration.progress import estimate_ocr_seconds, estimate_run_seconds, fmt_chars, fmt_duration, fmt_pages
from tools.pdf_tools import extract_pdf_text
from tools.ocr_tools import IMAGE_EXTENSIONS, TesseractOCR
from tools.report_export import synthesis_markdown, synthesis_pdf
from schemas.labels import STATUS_LABELS, TECHNICAL_WARNING_PREFIX, display_name, human_field
from agents.synthesis_agent import _priority as contractual_priority

load_dotenv()

APP_NAME = "InsurMinds_PROTETOR"
DB_PATH = Path("data") / "insurminds_protetor.db"
RUNS_DIR = Path("data") / "runs"
RECORDED_SOURCES = (RUNS_DIR, Path("evaluation") / "results")


def recorded_runs() -> dict[str, Path]:
    """Saved runs available for replay (presentation mode), newest first."""
    files = [f for d in RECORDED_SOURCES if d.exists() for f in d.glob("*.json")
             if f.name.startswith(("LIVE_", "run_"))]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return {f"{f.stem} · {f.parent.name}": f for f in files}

def compact_value(value: Any, limit: int = 220) -> str:
    if value is None:
        return "Não identificado"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if isinstance(value, dict):
        for key in ("description", "name", "title", "amount"):
            if value.get(key) not in (None, "", [], {}):
                base = str(value[key])
                if key == "amount" and value.get("currency"):
                    base = f"{value.get('currency')} {base}"
                return base if len(base) <= limit else base[: limit - 1] + "…"
        text = json.dumps(value, ensure_ascii=False, default=str)
    elif isinstance(value, list):
        text = "; ".join(compact_value(v, 100) for v in value[:3])
        if len(value) > 3:
            text += f"; +{len(value)-3} item(ns)"
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def source_text(source: Any) -> str:
    if source is None:
        return "Evidência específica não disponível neste item."
    if hasattr(source, "model_dump"):
        source = source.model_dump(mode="json")
    page = source.get("page") if isinstance(source, dict) else None
    section = source.get("section") if isinstance(source, dict) else None
    excerpt = source.get("excerpt") if isinstance(source, dict) else None
    parts = []
    if page:
        parts.append(f"Página {page}")
    if section:
        parts.append(str(section))
    heading = " · ".join(parts) if parts else "Referência documental"
    verified = source.get("verified") if isinstance(source, dict) else None
    if verified is True:
        heading += " · ✅ trecho conferido na página"
    elif verified is False and source.get("verified_page"):
        heading += f" · ⚠️ trecho localizado na página {source['verified_page']}, não na citada"
    elif verified is False:
        heading += " · ⚠️ trecho não localizado no texto da página"
    return f"**{heading}**\n\n{excerpt or 'Trecho não registrado.'}"


def policy_name(policy: Any, fallback: str) -> str:
    return display_name(policy, fallback)


@st.cache_data(show_spinner=False)
def document_profile(name: str, data: bytes) -> dict[str, Any]:
    """Pages and characters of an uploaded PDF, used for the time estimate before running."""
    if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
        return {"pages": 1, "chars": 0, "scanned": 1}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "doc.pdf"
        path.write_bytes(data)
        parsed = extract_pdf_text(path)
    scanned = len(parsed["scanned_pages"])
    return {"pages": parsed["pages"], "chars": parsed["characters_extracted"], "scanned": scanned}


def md_safe(text: str) -> str:
    """Streamlit renders $...$ as LaTeX; escape it so 'R$ 40.000,00' stays currency."""
    return text.replace("$", "\\$")


def show_warnings(warnings: list[str]) -> None:
    if warnings:
        st.warning(md_safe("\n".join(f"- {w}" for w in warnings)))


def comparison_rows(state: Any) -> list[dict[str, Any]]:
    if not state.comparison:
        return []
    rows = []
    for item in state.comparison.fields:
        rows.append(
            {
                "Tema": human_field(item.field),
                "Apólice A": compact_value(item.policy_a.value),
                "Apólice B": compact_value(item.policy_b.value),
                "Situação": STATUS_LABELS.get(item.status.value, item.status.value),
                "Confiança": None if item.confidence is None else round(item.confidence, 2),
                "Revisão": "Sim" if item.review_required else "Não",
                "_item": item,
            }
        )
    return rows


def policy_overview(policy: Any) -> pd.DataFrame:
    values = [
        ("Seguradora", policy.insurer),
        ("Segurado", policy.insured_entity),
        ("Número da apólice", policy.policy_number),
        ("Tipo", policy.policy_type),
        ("Ramo", policy.line_of_business.value if policy.line_of_business else None),
        ("Natureza do documento", policy.document_kind.value if policy.document_kind else None),
        ("Vigência inicial", policy.effective_date),
        ("Vigência final", policy.expiration_date),
        ("Moeda", policy.currency),
        ("Limite de responsabilidade", policy.limit_of_liability),
        ("Limite agregado", policy.aggregate_limit),
        ("Retroatividade", policy.retroactive_date),
        ("Âmbito territorial", policy.territorial_scope),
        ("Jurisdição", policy.jurisdiction),
        ("Confiança da extração", policy.extraction_confidence),
    ]
    return pd.DataFrame(
        [{"Campo": label, "Valor": compact_value(value, 500)} for label, value in values]
    )


def export_comparison_csv(rows: list[dict[str, Any]]) -> bytes:
    public_rows = [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]
    return pd.DataFrame(public_rows).to_csv(index=False).encode("utf-8-sig")


def export_run_json(state: Any) -> bytes:
    return state.model_dump_json(indent=2).encode("utf-8")


st.set_page_config(page_title=APP_NAME, page_icon="🛡️", layout="wide")
st.title(f"🛡️ {APP_NAME}")
st.caption("Análise comparativa de apólices D&O com agentes especializados, Harness e rastreabilidade Claim → Evidence")

with st.sidebar:
    page = st.radio("Navegação", ["Comparar apólices", "Consultar acervo"], horizontal=True)
    st.header("Controle da análise")
    live_available = bool(os.getenv("OPENAI_API_KEY"))
    mode = st.radio("Modo de execução", ["LIVE GPT", "DEMO offline"], index=0 if live_available else 1)
    if mode == "LIVE GPT":
        if live_available:
            st.success(f"LIVE habilitado · {os.getenv('OPENAI_MODEL', 'gpt-5.6-luna')}")
        else:
            st.error("OPENAI_API_KEY não configurada.")
    else:
        st.info("DEMO usa extração heurística e não representa avaliação GenAI.")
    st.divider()
    st.markdown("**Workflow orquestrado**")
    st.caption("A1 Intake → A2 Extraction → A3 D&O Analysis → A4 Validation → A5 Comparison → A6 Synthesis")
    st.caption("O Harness controla estado, transições, retries, persistência e observabilidade.")
    st.divider()
    st.markdown("**Modo apresentação**")
    runs = recorded_runs()
    if runs:
        chosen = st.selectbox("Run gravado", list(runs), label_visibility="collapsed")
        if st.button("Abrir run gravado", use_container_width=True):
            st.session_state["result"] = InsurMindsState.model_validate_json(runs[chosen].read_text(encoding="utf-8"))
            st.session_state["replay"] = chosen
            st.rerun()
        st.caption("Reabre um run LIVE já executado, sem chamadas à API.")
    else:
        st.caption("Nenhum run gravado ainda. Runs LIVE são gravados automaticamente em data/runs.")

def render_consulta() -> None:
    """Consulta: theme search across stored documents and grounded Q&A (etapa 5 do enunciado)."""
    st.subheader("Consulta ao acervo")
    documents = catalog(Database(DB_PATH))
    if not documents:
        st.info("O acervo está vazio. Processe apólices em **Comparar apólices** para que fiquem disponíveis aqui.")
        return
    st.caption(f"{len(documents)} documento(s) estruturado(s) no acervo (SQLite · {DB_PATH}). "
               "Cada arquivo aparece na versão mais recente processada.")
    with st.expander("Documentos no acervo"):
        st.dataframe(pd.DataFrame([{"Documento": d.policy.source_file, "Seguradora": display_name(d.policy),
                                    "Ramo": d.policy.line_of_business.value if d.policy.line_of_business else "",
                                    "Coberturas": len(d.policy.coverages) + len(d.policy.extensions),
                                    "Exclusões": len(d.policy.exclusions), "Cláusulas": len(d.policy.clauses),
                                    "Processado em": d.created_at[:16].replace("T", " ")} for d in documents]),
                     use_container_width=True, hide_index=True)

    search_tab, ask_tab = st.tabs(["Buscar tema", "Perguntar aos documentos"])
    with search_tab:
        c1, c2 = st.columns([2, 2])
        term = c1.text_input("Tema", placeholder="Ex.: cibernético, franquia, custos de defesa, poluição")
        groups = c2.multiselect("Tipo de item", list(GROUPS.values()), default=list(GROUPS.values()))
        if term.strip():
            chosen = {k for k, v in GROUPS.items() if v in groups}
            rows = search(documents, term, chosen)
            st.write(f"**{len(rows)}** item(ns) encontrado(s) em "
                     f"**{len({r['Documento'] for r in rows})}** documento(s).")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with ask_tab:
        labels = {d.label: d for d in documents}
        selected = st.multiselect("Documentos (até 2)", list(labels), max_selections=2,
                                  default=list(labels)[:2])
        question = st.text_input("Pergunta", placeholder="Ex.: Como cada documento trata a franquia na Cobertura A?")
        live = mode == "LIVE GPT" and live_available
        if not live:
            st.caption("Sem modo LIVE, a consulta mostra apenas as páginas mais relevantes, sem resposta por IA.")
        if st.button("Consultar", type="primary", disabled=not (selected and question.strip())):
            db = Database(DB_PATH)
            docs = [(tag, labels[name], db.get_raw_text(labels[name].document_id) or "") for tag, name in zip("AB", selected)]
            with st.spinner("Selecionando páginas e consultando…"):
                guard = VerdictGuard(OpenAIVerdictClassifier() if live and os.getenv("VERDICT_LLM_CHECK", "true").lower() in {"1", "true", "yes", "sim", "on"} else None)
                result = QueryAgent(OpenAIQueryResponder() if live else None, guard).answer(question, docs)
            for tag, name in zip("AB", selected):
                st.caption(f"**{tag}** = {name}")
            if result["answer"]:
                st.markdown(md_safe(result["answer"]))
                if result["citations"]:
                    st.caption("Citações verificadas: " + ", ".join(f"{c['doc']} p. {c['page']}" for c in result["citations"]))
            if result["note"]:
                st.info(result["note"])
            for tag, pages in result["excerpts"].items():
                if pages:
                    with st.expander(f"Páginas consultadas em {tag}: " + ", ".join(str(p["page"]) for p in pages)):
                        for p in pages:
                            st.markdown(f"**{tag} · página {p['page']}**")
                            st.text(p["text"].strip()[:3000])
            st.caption("A resposta usa somente as páginas acima e não constitui recomendação jurídica ou de contratação.")


if page == "Consultar acervo":
    render_consulta()
    st.stop()

st.subheader("1. Selecione as apólices")
col_a, col_b = st.columns(2)
with col_a:
    a = st.file_uploader("Apólice A", type=["pdf", "png", "jpg", "jpeg"], key="a")
with col_b:
    b = st.file_uploader("Apólice B", type=["pdf", "png", "jpg", "jpeg"], key="b")

if a and b:
    budget = int(os.getenv("OPENAI_MAX_INPUT_CHARS", OpenAIStructuredLLMClient.DEFAULT_MAX_INPUT_CHARS))
    profiles = [document_profile(f.name, f.getvalue()) for f in (a, b)]
    lines = []
    for label, f, prof in (("A", a, profiles[0]), ("B", b, profiles[1])):
        line = f"**{label}** · {f.name}: {fmt_pages(prof['pages'])}, {fmt_chars(prof['chars'])}"
        if prof["scanned"]:
            line += f" — {prof['scanned']} página(s) digitalizada(s): leitura por OCR"
            if mode != "LIVE GPT" and not TesseractOCR.available():
                line += " (**requer modo LIVE**: Tesseract não instalado)"
        if mode == "LIVE GPT" and prof["chars"] > budget:
            line += f" — acima do limite de {fmt_chars(budget)}; as páginas com menos termos contratuais serão omitidas"
        lines.append(line)
    if mode == "LIVE GPT":
        # Scanned pages have no native text yet: assume ~2.000 characters per page for A3.
        estimate = estimate_run_seconds([p["chars"] + 2000 * p["scanned"] for p in profiles], budget)
        estimate += sum(estimate_ocr_seconds(p["scanned"]) for p in profiles)
        lines.append(f"Tempo estimado da análise LIVE: **~{fmt_duration(estimate)}** (A3 é a etapa mais longa, proporcional ao tamanho).")
    else:
        lines.append("Modo DEMO: processamento local em poucos segundos.")
    st.info("  \n".join(lines))

run_col, clear_col = st.columns([3, 1])
with run_col:
    process = st.button("Analisar e comparar", type="primary", disabled=not (a and b), use_container_width=True)
with clear_col:
    if st.button("Limpar resultado", use_container_width=True):
        st.session_state.pop("result", None)
        st.session_state.pop("replay", None)
        st.rerun()

if process:
    with tempfile.TemporaryDirectory() as td:
        pa = Path(td) / a.name
        pb = Path(td) / b.name
        pa.write_bytes(a.getvalue())
        pb.write_bytes(b.getvalue())
        if mode == "LIVE GPT":
            if not live_available:
                st.error("Configure OPENAI_API_KEY antes de executar LIVE GPT.")
                st.stop()
            live_parts = build_live_components()
            llm, semantic, writer, ocr, guard = (live_parts.llm, live_parts.semantic, live_parts.writer,
                                                 live_parts.ocr, live_parts.guard)
        else:
            llm = DemoHeuristicLLMClient()
            semantic = writer = None  # A5/A6 use their deterministic fallbacks
            ocr = None  # Tesseract if installed; otherwise scanned documents require LIVE
            guard = VerdictGuard()
        with st.status("Executando Harness e agentes A1 → A6…", expanded=True) as run_status:
            bar = st.progress(0.0, text="Iniciando…")

            def report_progress(message: str, fraction: float) -> None:
                bar.progress(fraction, text=message)
                st.write(md_safe(message))

            pipeline = CompleteMVPPipeline(llm, semantic=semantic, writer=writer, db_path=str(DB_PATH),
                                           progress=report_progress, ocr=ocr, guard=guard)
            state = pipeline.process(pa, pb)
            done = state.status.value in {"COMPLETED", "REVIEW_REQUIRED"}
            run_status.update(label=f"{'Concluído' if done else 'Interrompido'} em {fmt_duration(state.metrics.get('duration_s', 0))}",
                              state="complete" if done else "error", expanded=False)
        st.session_state["result"] = state
        st.session_state.pop("replay", None)
        if mode == "LIVE GPT":
            RUNS_DIR.mkdir(parents=True, exist_ok=True)
            (RUNS_DIR / f"run_{state.run_id}.json").write_text(state.model_dump_json(), encoding="utf-8")

state = st.session_state.get("result")
if not state:
    st.info("Carregue duas apólices e selecione **Analisar e comparar**. O resultado executivo aparecerá aqui.")
    st.stop()

if state.status.value not in {"COMPLETED", "REVIEW_REQUIRED"}:
    st.error(f"Run {state.run_id} encerrado com status {state.status.value}.")
    if state.errors:
        st.write(state.errors)
    st.stop()

policies = state.validated_policies
name_a = policy_name(policies[0], "Apólice A") if len(policies) > 0 else "Apólice A"
name_b = policy_name(policies[1], "Apólice B") if len(policies) > 1 else "Apólice B"
rows = comparison_rows(state)
counts = Counter(item.status.value for item in state.comparison.fields) if state.comparison else Counter()
attention = counts.get("DIFFERENT", 0) + counts.get("ONLY_A", 0) + counts.get("ONLY_B", 0) + counts.get("REVIEW_REQUIRED", 0)

st.divider()
st.subheader(f"2. Resultado — {name_a} × {name_b}")
duration = f" · Tempo de processamento {fmt_duration(state.metrics['duration_s'])}" if "duration_s" in state.metrics else ""
st.caption(f"Run {state.run_id} · Status {state.status.value}{duration}")
if st.session_state.get("replay"):
    st.info(f"Modo apresentação: exibindo o run gravado **{st.session_state['replay']}** (nenhuma chamada à API).")
scope = state.metrics.get("scope")
if scope:
    lines = " × ".join(state.metrics.get("lines_of_business", []))
    if scope.startswith("D&O"):
        st.success(f"Escopo: {scope} · Ramos: {lines}")
    else:
        st.warning(f"Escopo: {scope} · Ramos: {lines}. Coberturas, exclusões, franquias e limites são comparados de forma genérica; a qualidade foi validada apenas para D&O.")
if state.metrics.get("general_conditions_only"):
    st.info("Os documentos são condições gerais: número, vigência, limites e valores normalmente constam da Especificação da Apólice e aparecem como não identificados.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Campos comparados", len(rows))
m2.metric("Diferenças / exclusivos", attention)
m3.metric("Itens iguais", counts.get("EQUAL", 0))
m4.metric("Revisão humana", sum(1 for x in state.comparison.fields if x.review_required) if state.comparison else 0)

tabs = st.tabs(["Resumo executivo", "Comparação", "Evidências", "Apólices", "Auditoria da IA"])

with tabs[0]:
    st.markdown("### Síntese executiva")
    st.markdown(md_safe(state.final_report or "Síntese não disponível."))
    if state.final_report:
        export_meta = {"run_id": state.run_id, "status": state.status.value,
                       "duration": fmt_duration(state.metrics["duration_s"]) if "duration_s" in state.metrics else None}
        d1, d2, _ = st.columns([1, 1, 2])
        d1.download_button("Baixar síntese (.md)", data=synthesis_markdown(state.final_report, export_meta).encode("utf-8"),
                           file_name=f"{APP_NAME}_sintese_{state.run_id}.md", mime="text/markdown", use_container_width=True)
        try:
            pdf_bytes = synthesis_pdf(state.final_report, export_meta)
            d2.download_button("Baixar síntese (.pdf)", data=pdf_bytes, file_name=f"{APP_NAME}_sintese_{state.run_id}.pdf",
                               mime="application/pdf", use_container_width=True)
        except Exception as exc:  # the Markdown export remains available
            d2.caption(f"PDF indisponível ({type(exc).__name__}).")
    st.markdown("### Leitura rápida")
    if attention:
        st.write(
            f"O sistema identificou **{attention} ponto(s) de diferença, exclusividade ou revisão** "
            f"entre **{name_a}** e **{name_b}**. Use a aba **Comparação** para filtrar os itens e "
            "a aba **Evidências** para verificar a origem documental."
        )
    else:
        st.write("Não foram identificadas diferenças nos campos efetivamente comparados.")
    show_warnings([w for w in state.warnings if not w.startswith(TECHNICAL_WARNING_PREFIX)])
    st.caption("A análise descreve diferenças documentais e não constitui recomendação jurídica ou de contratação.")

with tabs[1]:
    st.markdown("### Matriz comparativa")
    c1, c2 = st.columns([1, 2])
    with c1:
        only_attention = st.toggle("Mostrar somente diferenças e pontos de atenção", value=True)
    with c2:
        query = st.text_input("Filtrar por tema", placeholder="Ex.: franquia, exclusão, territorialidade")
    visible = rows
    if only_attention:
        visible = [r for r in visible if r["_item"].status.value in {"DIFFERENT", "ONLY_A", "ONLY_B", "REVIEW_REQUIRED"}]
    if query.strip():
        q = query.lower().strip()
        visible = [r for r in visible if q in r["Tema"].lower() or q in r["Apólice A"].lower() or q in r["Apólice B"].lower()]
    display = [{k: v for k, v in r.items() if not k.startswith("_")} for r in visible]
    st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
    st.download_button("Baixar comparação (.csv)", data=export_comparison_csv(rows), file_name=f"{APP_NAME}_comparacao_{state.run_id}.csv", mime="text/csv")

with tabs[2]:
    st.markdown("### Claim → Evidence")
    evidence_rows = sorted((r for r in rows if r["_item"].status.value in {"DIFFERENT", "ONLY_A", "ONLY_B", "REVIEW_REQUIRED"}),
                           key=lambda r: contractual_priority(r["_item"].field))
    if not evidence_rows:
        st.info("Não há diferenças com evidências para exibir.")
    for row in evidence_rows:
        item = row["_item"]
        with st.expander(f"{row['Tema']} · {row['Situação']}"):
            ea, eb = st.columns(2)
            with ea:
                st.markdown(md_safe(f"**{name_a}**"))
                st.markdown(md_safe(compact_value(item.policy_a.value, 1200)))
                st.markdown(md_safe(source_text(item.policy_a.source)))
            with eb:
                st.markdown(md_safe(f"**{name_b}**"))
                st.markdown(md_safe(compact_value(item.policy_b.value, 1200)))
                st.markdown(md_safe(source_text(item.policy_b.source)))
            if item.reason:
                st.caption(md_safe(f"Critério de comparação: {item.reason}"))

with tabs[3]:
    if not policies:
        st.info("Nenhuma apólice validada disponível.")
    for idx, policy in enumerate(policies):
        title = name_a if idx == 0 else name_b
        st.markdown(f"### {title}")
        st.dataframe(policy_overview(policy), use_container_width=True, hide_index=True)
        x1, x2, x3, x4 = st.columns(4)
        x1.metric("Coberturas", len(policy.coverages))
        x2.metric("Exclusões", len(policy.exclusions))
        x3.metric("Cláusulas", len(policy.clauses))
        x4.metric("Extensões", len(policy.extensions))
        with st.expander("Ver estrutura completa da apólice"):
            st.json(policy.model_dump(mode="json"))
        if policy.warnings:
            st.warning("\n".join(policy.warnings))

with tabs[4]:
    st.markdown("### Auditoria da IA e do Harness")
    st.write("Esta área expõe a execução técnica sem ocupar a experiência principal do analista.")
    a1, a2, a3 = st.columns(3)
    a1.metric("Status", state.status.value)
    a2.metric("Eventos de trace", len(state.trace))
    a3.metric("Warnings", len(state.warnings))
    evidence = state.metrics.get("evidence_check") or {}
    if evidence:
        st.markdown("**Verificação de evidências (Claim → Evidence)**")
        st.dataframe(pd.DataFrame([{"Documento": k, "Referências": v.get("references"), "Conferidas na página": v.get("verified"),
                                    "Em outra página": v.get("wrong_page"), "Não localizadas": v.get("not_found"),
                                    "Taxa": v.get("verified_rate")} for k, v in evidence.items()]),
                     use_container_width=True, hide_index=True)
    usage = state.metrics.get("llm_usage") or {}
    if usage.get("by_stage"):
        st.markdown("**Consumo do provedor (tokens)**")
        st.dataframe(pd.DataFrame([{"Etapa": k, **v} for k, v in usage["by_stage"].items()]), use_container_width=True, hide_index=True)
        cost = usage.get("estimated_cost_usd")
        st.caption(f"Total: {usage['total']['input_tokens']:,} tokens de entrada · {usage['total']['output_tokens']:,} de saída"
                   + (f" · custo estimado US$ {cost:.4f}" if cost is not None else f" · {usage.get('cost_note')}"))
    if state.metrics:
        st.markdown("**Métricas do run**")
        st.json(state.metrics)
    if state.errors:
        st.error("\n".join(state.errors))
    show_warnings(state.warnings)
    trace_rows = [x.model_dump(mode="json") for x in state.trace]
    if trace_rows:
        st.markdown("**Trace A1 → A6**")
        st.dataframe(pd.DataFrame(trace_rows), use_container_width=True, hide_index=True)
    st.download_button("Baixar run completo (.json)", data=export_run_json(state), file_name=f"{APP_NAME}_run_{state.run_id}.json", mime="application/json")
