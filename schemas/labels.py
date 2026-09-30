"""User-facing Portuguese labels shared by the Streamlit UI and A6 synthesis."""
from __future__ import annotations
import re
from typing import Any

STATUS_LABELS = {
    "EQUAL": "Igual",
    "DIFFERENT": "Diferente",
    "ONLY_A": "Somente A",
    "ONLY_B": "Somente B",
    "NOT_IDENTIFIED": "Não identificado",
    "NOT_APPLICABLE": "Não aplicável",
    "REVIEW_REQUIRED": "Revisão humana",
}

FIELD_LABELS = {
    "policy_number": "Número da apólice",
    "insurer": "Seguradora",
    "insured_entity": "Segurado",
    "policy_type": "Tipo de apólice",
    "effective_date": "Início de vigência",
    "expiration_date": "Fim de vigência",
    "currency": "Moeda",
    "retroactive_date": "Data de retroatividade",
    "territorial_scope": "Âmbito territorial",
    "jurisdiction": "Jurisdição",
    "limit_of_liability": "Limite de responsabilidade",
    "aggregate_limit": "Limite agregado",
    "insuring_side_A": "Cobertura Side A",
    "insuring_side_B": "Cobertura Side B",
    "insuring_side_C": "Cobertura Side C",
    "retentions": "Franquias / retenções",
    "reporting_period": "Prazo complementar / adicional",
}

GROUP_LABELS = {"coverages": "Cobertura", "exclusions": "Exclusão", "clauses": "Cláusula", "extensions": "Extensão"}

CONCEPT_LABELS = {
    # exclusions
    "dolo_fraude": "Dolo / fraude", "vantagem_indevida": "Vantagem indevida",
    "reclamacoes_anteriores": "Reclamações anteriores", "danos_punitivos": "Danos punitivos / exemplares",
    "danos_materiais_corporais": "Danos materiais, corporais e morais", "poluicao_ambiental": "Poluição / danos ambientais",
    "cibernetico": "Riscos cibernéticos", "multas_penalidades": "Multas e penalidades",
    "rc_profissional": "RC profissional", "trabalhistas_previdenciarias": "Verbas trabalhistas e previdenciárias",
    "tributos": "Tributos", "valores_mobiliarios": "Valores mobiliários", "garantias_aval_fianca": "Garantias, aval e fiança",
    "segurado_contra_segurado": "Segurado contra segurado", "sancoes_embargos": "Sanções e embargos",
    "insolvencia": "Insolvência", "mudanca_controle": "Mudança de controle",
    # coverages / extensions
    "cobertura_a": "Cobertura A (pessoas seguradas)", "cobertura_b": "Cobertura B (reembolso à sociedade)",
    "cobertura_c": "Cobertura C (entidade)", "extradicao": "Custos de extradição", "custos_defesa": "Custos de defesa",
    "praticas_trabalhistas": "Práticas trabalhistas", "penhora_bloqueio": "Penhora online e bloqueio de bens",
    "investigacao": "Custos de investigação", "crise_relacoes_publicas": "Gerenciamento de crise / relações públicas",
    "responsabilidade_ambiental": "Responsabilidade ambiental", "herdeiros_conjuges": "Herdeiros e cônjuges",
    "segurados_aposentados": "Segurados aposentados", "controladas_coligadas": "Controladas e coligadas",
    "inabilitacao": "Inabilitação", "reclamacoes_entre_segurados": "Reclamações entre segurados",
    "processos_administrativos": "Processos administrativos e arbitrais", "danos_morais_materiais": "Danos morais e materiais",
    # clauses
    "objetivo_riscos_cobertos": "Objetivo e riscos cobertos", "riscos_excluidos": "Riscos excluídos",
    "base_reclamacoes": "Base de reclamações e notificação", "ambito_territorial": "Âmbito territorial",
    "limites": "Limites", "franquia": "Franquia / participação obrigatória", "reintegracao": "Reintegração",
    "prazo_complementar": "Prazo complementar / adicional", "vigencia_renovacao": "Vigência e renovação",
    "aceitacao_proposta": "Aceitação da proposta", "pagamento_premio": "Pagamento do prêmio",
    "alteracao_risco": "Alteração / agravamento do risco", "sinistro_aviso_regulacao": "Aviso e regulação de sinistro",
    "liquidacao_indenizacao": "Liquidação e indenização", "defesa_acordos": "Defesa e acordos",
    "concorrencia_apolices": "Concorrência de apólices", "sub_rogacao": "Sub-rogação", "perda_direitos": "Perda de direitos",
    "cancelamento_rescisao": "Cancelamento e rescisão", "cessao_transferencia": "Cessão e transferência",
    "moeda": "Moeda e atualização", "prescricao": "Prescrição", "foro_lei_arbitragem": "Foro, lei aplicável e arbitragem",
}


def _pretty(key: str) -> str:
    """Concept label, or the item's own name for items without a canonical concept."""
    if key in CONCEPT_LABELS:
        return CONCEPT_LABELS[key]
    text = " ".join(re.split(r"[_\s]+", key.strip()))
    return text[:1].upper() + text[1:]


def human_field(field: str) -> str:
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    if ":" in field:
        group, item = field.split(":", 1)
        return f"{GROUP_LABELS.get(group, group.title())}: {_pretty(item)}"
    return field.replace("_", " ").title()


def short_value(value: Any, limit: int = 160) -> str:
    """One-line human summary of a compared value (item, list of items, money or scalar)."""
    if value is None:
        return "não identificado"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, list):
        parts = [short_value(v, 60) for v in value[:3]]
        text = "; ".join(parts) + (f"; +{len(value) - 3}" if len(value) > 3 else "")
    elif isinstance(value, dict):
        if value.get("amount") is not None and "name" not in value:
            text = f"{value.get('currency') or ''} {value['amount']}".strip()
        else:
            text = next((str(value[k]) for k in ("name", "title", "applies_to", "description", "conditions")
                         if value.get(k) not in (None, "", [], {})), "item sem descrição")
    else:
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def display_name(policy: Any, fallback: str = "Documento") -> str:
    """Insurer name, or a readable form of the file name when the insurer was not identified."""
    if getattr(policy, "insurer", None):
        return policy.insurer
    stem = re.sub(r"^\d+[_\s-]*", "", str(getattr(policy, "source_file", "") or "").rsplit(".", 1)[0])
    text = " ".join(stem.replace("_", " ").replace("-", " ").split())
    return text[:1].upper() + text[1:] if text else fallback


TECHNICAL_WARNING_PREFIX = "A4:"
