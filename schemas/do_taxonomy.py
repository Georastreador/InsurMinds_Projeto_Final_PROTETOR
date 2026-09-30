"""Canonical D&O concepts used to pair contractual items across insurers.

A3 classifies each coverage/exclusion/clause into one of these categories (the enum
is part of the strict schema sent to the LLM). A5 pairs items by category, so the
comparison no longer depends on the free-text name the LLM chose or its language.
When no category is present (DEMO mode, older runs), `categorize` applies the
keyword rules below as an auditable fallback.
"""
from __future__ import annotations
import re
import unicodedata
from enum import Enum
from typing import Optional


class ExclusionCategory(str, Enum):
    DOLO_FRAUDE = "dolo_fraude"
    VANTAGEM_INDEVIDA = "vantagem_indevida"
    RECLAMACOES_ANTERIORES = "reclamacoes_anteriores"
    DANOS_PUNITIVOS = "danos_punitivos"
    DANOS_MATERIAIS_CORPORAIS = "danos_materiais_corporais"
    POLUICAO_AMBIENTAL = "poluicao_ambiental"
    CIBERNETICO = "cibernetico"
    MULTAS_PENALIDADES = "multas_penalidades"
    RC_PROFISSIONAL = "rc_profissional"
    TRABALHISTAS_PREVIDENCIARIAS = "trabalhistas_previdenciarias"
    TRIBUTOS = "tributos"
    VALORES_MOBILIARIOS = "valores_mobiliarios"
    GARANTIAS_AVAL_FIANCA = "garantias_aval_fianca"
    SEGURADO_CONTRA_SEGURADO = "segurado_contra_segurado"
    SANCOES_EMBARGOS = "sancoes_embargos"
    INSOLVENCIA = "insolvencia"
    MUDANCA_CONTROLE = "mudanca_controle"
    OUTRA = "outra"


class CoverageCategory(str, Enum):
    COBERTURA_A = "cobertura_a"
    COBERTURA_B = "cobertura_b"
    COBERTURA_C = "cobertura_c"
    EXTRADICAO = "extradicao"
    CUSTOS_DEFESA = "custos_defesa"
    MULTAS_PENALIDADES = "multas_penalidades"
    PRATICAS_TRABALHISTAS = "praticas_trabalhistas"
    PENHORA_BLOQUEIO = "penhora_bloqueio"
    INVESTIGACAO = "investigacao"
    CRISE_RELACOES_PUBLICAS = "crise_relacoes_publicas"
    RESPONSABILIDADE_AMBIENTAL = "responsabilidade_ambiental"
    HERDEIROS_CONJUGES = "herdeiros_conjuges"
    SEGURADOS_APOSENTADOS = "segurados_aposentados"
    CONTROLADAS_COLIGADAS = "controladas_coligadas"
    INABILITACAO = "inabilitacao"
    RECLAMACOES_ENTRE_SEGURADOS = "reclamacoes_entre_segurados"
    PROCESSOS_ADMINISTRATIVOS = "processos_administrativos"
    DANOS_MORAIS_MATERIAIS = "danos_morais_materiais"
    OUTRA = "outra"


class ClauseCategory(str, Enum):
    """Standard structure of Brazilian general conditions (SUSEP), common to all lines of business."""
    OBJETIVO_RISCOS_COBERTOS = "objetivo_riscos_cobertos"
    RISCOS_EXCLUIDOS = "riscos_excluidos"
    BASE_RECLAMACOES = "base_reclamacoes"
    AMBITO_TERRITORIAL = "ambito_territorial"
    LIMITES = "limites"
    FRANQUIA = "franquia"
    REINTEGRACAO = "reintegracao"
    PRAZO_COMPLEMENTAR = "prazo_complementar"
    VIGENCIA_RENOVACAO = "vigencia_renovacao"
    ACEITACAO_PROPOSTA = "aceitacao_proposta"
    PAGAMENTO_PREMIO = "pagamento_premio"
    ALTERACAO_RISCO = "alteracao_risco"
    SINISTRO_AVISO_REGULACAO = "sinistro_aviso_regulacao"
    LIQUIDACAO_INDENIZACAO = "liquidacao_indenizacao"
    DEFESA_ACORDOS = "defesa_acordos"
    CONCORRENCIA_APOLICES = "concorrencia_apolices"
    SUB_ROGACAO = "sub_rogacao"
    PERDA_DIREITOS = "perda_direitos"
    CANCELAMENTO_RESCISAO = "cancelamento_rescisao"
    CESSAO_TRANSFERENCIA = "cessao_transferencia"
    MOEDA = "moeda"
    PRESCRICAO = "prescricao"
    FORO_LEI_ARBITRAGEM = "foro_lei_arbitragem"
    OUTRA = "outra"


# Ordered: the first matching rule wins, so specific concepts precede generic ones.
_RULES: dict[type[Enum], list[tuple[Enum, str]]] = {
    ExclusionCategory: [
        # Dolo/fraude first: combined wordings ("conduta dolosa, fraude ... vantagem indevida") are primarily dolo.
        (ExclusionCategory.DOLO_FRAUDE, r"dolo|fraud|intencional|intentional|ma-?fe"),
        (ExclusionCategory.VANTAGEM_INDEVIDA, r"vantagem indevida|ganho pessoal|personal profit"),
        (ExclusionCategory.RECLAMACOES_ANTERIORES, r"anterior|prior|pendente|preexist|known|conhecid"),
        (ExclusionCategory.DANOS_PUNITIVOS, r"punitiv|exemplar"),
        (ExclusionCategory.POLUICAO_AMBIENTAL, r"polui|ambient|environmental|pollution"),
        (ExclusionCategory.CIBERNETICO, r"ciber|cyber|malware"),
        (ExclusionCategory.MULTAS_PENALIDADES, r"multa|penalidade|fines|penalt"),
        (ExclusionCategory.DANOS_MATERIAIS_CORPORAIS, r"corpora|materia|bodily|property|mora(l|is)"),
        (ExclusionCategory.RC_PROFISSIONAL, r"profissional|professional"),
        (ExclusionCategory.TRABALHISTAS_PREVIDENCIARIAS, r"trabalhist|previdenci|employment"),
        (ExclusionCategory.TRIBUTOS, r"tribut|\btax|fiscal"),
        (ExclusionCategory.VALORES_MOBILIARIOS, r"valores mobiliarios|securities|prospect|oferta publica"),
        (ExclusionCategory.GARANTIAS_AVAL_FIANCA, r"\baval|fianca|guarantee|garantia"),
        (ExclusionCategory.SEGURADO_CONTRA_SEGURADO, r"segurado contra|insured v"),
        (ExclusionCategory.SANCOES_EMBARGOS, r"sanc|embargo"),
        (ExclusionCategory.INSOLVENCIA, r"insolv|falencia|recuperacao judicial"),
        (ExclusionCategory.MUDANCA_CONTROLE, r"controle|aquisicao|acquisition|change of control"),
    ],
    CoverageCategory: [
        (CoverageCategory.COBERTURA_A, r"\bside a\b|\bcobertura a\b"),
        (CoverageCategory.COBERTURA_B, r"\bside b\b|\bcobertura b\b"),
        (CoverageCategory.COBERTURA_C, r"\bside c\b|\bcobertura c\b"),
        (CoverageCategory.EXTRADICAO, r"extradi"),
        (CoverageCategory.CUSTOS_DEFESA, r"custos? de defesa|defen[cs]e cost"),
        (CoverageCategory.MULTAS_PENALIDADES, r"multa|penalidade|fines|penalt"),
        (CoverageCategory.PRATICAS_TRABALHISTAS, r"trabalhist|employment"),
        (CoverageCategory.PENHORA_BLOQUEIO, r"penhora|bloqueio|seizure|freeze"),
        (CoverageCategory.INVESTIGACAO, r"investiga"),
        (CoverageCategory.CRISE_RELACOES_PUBLICAS, r"crise|crisis|relacoes publicas|public relations"),
        (CoverageCategory.RESPONSABILIDADE_AMBIENTAL, r"ambient|environmental"),
        (CoverageCategory.HERDEIROS_CONJUGES, r"herdeir|conjug|spous|heirs|espolio|estate"),
        (CoverageCategory.SEGURADOS_APOSENTADOS, r"aposentad|retired"),
        (CoverageCategory.CONTROLADAS_COLIGADAS, r"controlad|coligad|subsidiar|affiliat"),
        (CoverageCategory.INABILITACAO, r"inabilita|disqualif"),
        (CoverageCategory.RECLAMACOES_ENTRE_SEGURADOS, r"segurado contra|insured v|tomador contra|entity claims"),
        (CoverageCategory.PROCESSOS_ADMINISTRATIVOS, r"administrativ|arbitra"),
        (CoverageCategory.DANOS_MORAIS_MATERIAIS, r"danos? (morais|materiais)|corporais"),
    ],
    ClauseCategory: [
        (ClauseCategory.RISCOS_EXCLUIDOS, r"riscos? excluid|exclus"),
        (ClauseCategory.OBJETIVO_RISCOS_COBERTOS, r"objetivo|objeto do seguro|riscos? cobert"),
        (ClauseCategory.BASE_RECLAMACOES, r"base de reclama|reclamac\w* com notifica|claims.made|reclamacao continua|notificac"),
        (ClauseCategory.AMBITO_TERRITORIAL, r"geograf|territor|mundo"),
        (ClauseCategory.FRANQUIA, r"franquia|participacao obrigatoria|retenc"),
        (ClauseCategory.REINTEGRACAO, r"reintegra"),
        (ClauseCategory.PRAZO_COMPLEMENTAR, r"prazo (complementar|adicional|suplementar)|reporting period"),
        (ClauseCategory.VIGENCIA_RENOVACAO, r"vigencia|renova|prorroga"),
        (ClauseCategory.ACEITACAO_PROPOSTA, r"aceita|proposta"),
        (ClauseCategory.PAGAMENTO_PREMIO, r"pagamento do premio|\bpremio"),
        (ClauseCategory.ALTERACAO_RISCO, r"altera\w* (no|do) risco|agravamento"),
        (ClauseCategory.LIQUIDACAO_INDENIZACAO, r"liquidac|indeniza"),
        (ClauseCategory.SINISTRO_AVISO_REGULACAO, r"sinistro|regulac"),
        (ClauseCategory.CONCORRENCIA_APOLICES, r"concorrencia|outros seguros"),
        (ClauseCategory.SUB_ROGACAO, r"sub-?rogac"),
        (ClauseCategory.PERDA_DIREITOS, r"perda de direito"),
        (ClauseCategory.CANCELAMENTO_RESCISAO, r"cancelamento|rescis"),
        (ClauseCategory.CESSAO_TRANSFERENCIA, r"cessao|transferencia"),
        (ClauseCategory.PRESCRICAO, r"prescri"),
        (ClauseCategory.FORO_LEI_ARBITRAGEM, r"\bforo\b|arbitra|lei aplicavel|jurisdi"),
        (ClauseCategory.MOEDA, r"\bmoeda\b|atualizacao de valores"),
        (ClauseCategory.LIMITES, r"limite"),
        (ClauseCategory.DEFESA_ACORDOS, r"defesa|acordo"),
    ],
}


def fold(text: object) -> str:
    """Lowercase, accent-free, whitespace-normalized text for matching."""
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(text.replace("_", " ").lower().split())


def categorize(kind: type[Enum], item: object) -> Optional[Enum]:
    """Category declared by A3, or the first keyword rule matching the item's name."""
    declared = getattr(item, "category", None)
    if declared is not None:
        return declared
    label = fold(f"{getattr(item, 'normalized_name', None) or ''} {getattr(item, 'name', '')}")
    for category, pattern in _RULES[kind]:
        if re.search(pattern, label):
            return category
    return None


def canonical_policy_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    folded = fold(value)
    if "d&o" in folded or "diretores" in folded or "directors and officers" in folded:
        return "D&O"
    return folded


def canonical_territorial_scope(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    folded = fold(value)
    if re.search(r"mundo|mundial|worldwide", folded):
        return "WORLDWIDE_UNLESS_SPECIFIED" if re.search(r"salvo|especificacao|unless|divers", folded) else "WORLDWIDE"
    return folded


# --- Line of business (scope) -------------------------------------------------------
# D&O is the validated specialization; other lines are analyzed with the generic
# schema fields (coverages, exclusions, retentions, limits) and flagged as such.

class LineOfBusiness(str, Enum):
    DO = "d_o"
    RC_GERAL = "rc_geral"
    AUTO = "auto"
    RESIDENCIAL = "residencial"
    EMPRESARIAL = "empresarial"
    VIDA = "vida"
    VIAGEM = "viagem"
    GARANTIA = "garantia"
    OUTRO = "outro"


class DocumentKind(str, Enum):
    CONDICOES_GERAIS = "condicoes_gerais"
    APOLICE_EMITIDA = "apolice_emitida"
    OUTRO = "outro"


LINE_LABELS = {
    LineOfBusiness.DO: "D&O", LineOfBusiness.RC_GERAL: "RC Geral", LineOfBusiness.AUTO: "Automóvel",
    LineOfBusiness.RESIDENCIAL: "Residencial", LineOfBusiness.EMPRESARIAL: "Empresarial",
    LineOfBusiness.VIDA: "Vida", LineOfBusiness.VIAGEM: "Viagem", LineOfBusiness.GARANTIA: "Garantia",
    LineOfBusiness.OUTRO: "Outro",
}

# Ordered keyword rules for the offline fallback (DEMO). Scores count occurrences.
_LINE_RULES: list[tuple[LineOfBusiness, str]] = [
    (LineOfBusiness.DO, r"d&o|diretores e administradores|directors and officers|conselheiros, diretores"),
    (LineOfBusiness.GARANTIA, r"seguro garantia|tomador.{0,40}segurado.{0,40}garantia"),
    (LineOfBusiness.AUTO, r"automove|veiculo|casco"),
    (LineOfBusiness.VIAGEM, r"viagem|bagagem|traslado"),
    (LineOfBusiness.VIDA, r"morte|invalidez|capital segurado|beneficiario"),
    (LineOfBusiness.RESIDENCIAL, r"residencia|moradia|imovel residencial"),
    (LineOfBusiness.EMPRESARIAL, r"empresarial|estabelecimento|lucros cessantes"),
]


def detect_line_of_business(text: str) -> LineOfBusiness:
    folded = fold(text[:200_000])
    scores = {line: len(re.findall(pattern, folded)) for line, pattern in _LINE_RULES}
    # D&O conditions also mention death, beneficiaries etc.; the specialization wins when clearly present.
    if scores[LineOfBusiness.DO] >= 3:
        return LineOfBusiness.DO
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else LineOfBusiness.OUTRO
