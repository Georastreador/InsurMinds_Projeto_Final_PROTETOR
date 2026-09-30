# InsurMinds_PROTETOR — Análise e Comparação de Apólices D&O com IA Generativa

Projeto Final do curso de IA Aplicada do **I2A2 — Instituto de Inteligência Artificial Aplicada (2026)**.

O PROTETOR recebe duas apólices ou condições contratuais de seguro **D&O (Directors & Officers)** em PDF ou imagem, extrai e estrutura seu conteúdo com IA generativa, compara coberturas, exclusões, franquias, limites e cláusulas, e entrega ao analista uma **síntese executiva com evidências por página** — sem recomendar qual apólice contratar. A decisão final é humana.

## O problema

Apólices D&O são longas (50 a 250 páginas), redigidas em linguagem jurídica e estruturadas de forma diferente por cada seguradora. Comparar duas delas exige localizar e alinhar dezenas de coberturas, exclusões e cláusulas, o que leva horas de trabalho especializado. O PROTETOR faz a leitura, o alinhamento e a síntese em cerca de 3 minutos, preservando a página de origem de cada afirmação (Claim → Evidence) para verificação humana.

## Arquitetura

```
Upload A/B ─► Harness (Orchestrator: estados, retries, guardrails, trace, persistência)
               │
               ├─ A1 Intake ........ valida arquivo e metadados
               ├─ A2 Extraction .... texto nativo (PyMuPDF) · OCR com GPT para páginas digitalizadas e imagens
               ├─ A3 Análise D&O ... LLM estrutura o documento no PolicySchema (JSON Schema estrito)
               ├─ A4 Validation .... Pydantic + guardrails; falha → nova tentativa do A3 com os erros
               ├─ A5 Comparison .... pareamento por taxonomia D&O + julgamento semântico por LLM
               └─ A6 Synthesis ..... síntese executiva gerada por IA, limitada ao resultado do A5
                      │
                      ▼
   Interface Streamlit: Resumo · Comparação · Evidências · Apólices · Auditoria da IA · Consulta ao acervo
```

| Componente | Responsabilidade | IA generativa |
|---|---|---|
| **Harness** (`orchestration/`) | Máquina de estados, até 2 retries, escopo/ramo, progresso, persistência, trace | — |
| **A1 Intake** | Formato, tamanho, metadados | — |
| **A2 Extraction** | Texto por página com marcadores `[[PÁGINA n]]`; OCR em lotes para digitalizados | OCR multimodal (GPT) |
| **A3 Análise** | Extração estruturada: coberturas, exclusões, cláusulas, franquias, limites, ramo, evidências | Structured Outputs |
| **A4 Validação** | Schema, datas plausíveis, datas BR→ISO, remove "valores" que são só definições de papel | — |
| **A5 Comparação** | Estados controlados (`EQUAL`, `DIFFERENT`, `ONLY_A/B`, `REVIEW_REQUIRED`…) | Juiz semântico + pareamento de órfãos |
| **A6 Síntese** | Principais diferenças com página; bloqueio de veredito (melhor/pior/recomendada) | Redação da síntese |
| **Consulta** | Busca de temas no acervo e perguntas com resposta citando páginas | Q&A ancorado |

**Guardrails:** não inventar fatos; campos individualizados ausentes ficam `null`; citações só de páginas efetivamente consultadas; nenhuma linguagem de superioridade ou recomendação; documentos fora de D&O são sinalizados como "escopo genérico"; omissões por limite de tamanho são sempre avisadas.

## Tecnologias

- **Python 3.10+**, **Streamlit** (interface), **Pydantic v2** (contratos e validação)
- **OpenAI API** — Responses API com Structured Outputs (extração, julgamento semântico, síntese, consulta) e entrada de imagem (OCR)
- **PyMuPDF** (texto, renderização de páginas, PDF da síntese), **Markdown**
- **SQLite** (armazenamento estruturado de runs, documentos, textos, apólices, comparações e relatórios)
- **pytest** (98 testes automatizados, sem chamadas de API)
- Tesseract (opcional, apenas como OCR offline se estiver instalado)

## Instalação

```bash
git clone <URL-do-repositório>
cd InsurMinds_PROTETOR
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # preencha OPENAI_API_KEY no .env
```

Variáveis do `.env`:

| Variável | Uso | Padrão |
|---|---|---|
| `OPENAI_API_KEY` | Credencial do modo LIVE (nunca versionar) | — |
| `OPENAI_MODEL` | Modelo usado em todas as etapas de IA | `gpt-5.6-luna` |
| `OPENAI_MAX_INPUT_CHARS` | Limite de texto enviado ao A3 por documento | `300000` |
| `OCR_MAX_PAGES` | Limite de páginas digitalizadas lidas por OCR | `40` |

## Execução

```bash
streamlit run app.py
```

1. Na barra lateral, escolha **LIVE GPT** (requer a chave) ou **DEMO offline** (heurístico, sem IA).
2. Carregue a **Apólice A** e a **Apólice B** (PDF, PNG ou JPG). A tela mostra páginas, tamanho e o **tempo estimado**.
3. Clique em **Analisar e comparar** e acompanhe o progresso por agente.
4. Navegue pelas abas; baixe a síntese em **.md** ou **.pdf** e a comparação em **.csv**.
5. Em **Consultar acervo**, busque temas em todos os documentos processados ou faça perguntas com resposta citando páginas.
6. **Modo apresentação:** reabre runs LIVE gravados sem chamar a API (útil para demonstrações).

## Testes e avaliação

```bash
pytest -q                                       # 98 testes offline
python -m evaluation.run_live_golden --live     # Dataset 1 com gabarito humano (API)
python -m evaluation.run_live_stress            # robustez e OCR (API)
python -m evaluation.make_ocr_fixtures          # gera os documentos digitalizados de teste
```

**Resultados no Dataset 1 (Chubb × Sompo, run LIVE de referência):**

| Métrica | Resultado | Meta |
|---|---|---|
| EVAL-01 Validade do schema | 1,00 / 1,00 | — |
| EVAL-02 Acerto dos campos | 1,00 (12/12) / 1,00 (11/11) | ≥ 0,80 |
| EVAL-03 Evidência na página anotada | 1,00 (6/6) / 1,00 (5/5) | ≥ 0,80 |
| EVAL-04 Comparação (gabarito v1.0 / v1.1) | 0,80 / 1,00 | ≥ 0,90 |
| EVAL-05 Proxy léxico de alucinação | 1,00 / 1,00 | ≥ 0,80 |

EVAL-04 evoluiu de 0,50 para 0,80 (gabarito v1.0) com a taxonomia D&O e o juiz semântico. A revisão v1.1 do gabarito foi confirmada no texto-fonte e as duas versões são reportadas. Robustez: 5 pares LIVE (254 páginas, ramos diferentes, apólice sintética com valores, PDF digitalizado e imagem) passaram em todas as verificações. Detalhes e limitações: `evaluation/golden_dataset/EVALUATION_STATUS_v1.1.json`.

## Datasets

| Dataset | Pasta | Finalidade |
|---|---|---|
| 1 — Golden D&O: Chubb × Sompo | `data/golden_dataset/`, `evaluation/golden_dataset/` | Métricas com anotação humana |
| 2 — Estudo de caso temporal: Invepar 2024×2025, PRODEMGE 2020×2025 | `datasets/case_study/` | Troca de seguradora, limites, OCR, divulgação em demonstrações |
| 3 — Robustez: outros ramos + apólice sintética | `datasets/stress_test/` | Escopo, OCR, tamanho, valores com gabarito |

Fontes e checksums: [`datasets/SOURCES.md`](datasets/SOURCES.md).

## Estrutura do repositório

```
agents/            A1–A6 e agente de Consulta
orchestration/     Harness: orquestrador, estados, pipeline, escopo, progresso
llm/               Adaptadores OpenAI (extração, juiz, síntese, consulta) e schema estrito
schemas/           PolicySchema, ComparisonResult, taxonomia D&O, rótulos
tools/             PDF, OCR, orçamento de texto, exportação da síntese
storage/           SQLite
evaluation/        Golden Dataset, avaliadores EVAL-01..05, runners LIVE, resultados
datasets/          Documentos públicos e sintéticos de teste
tests/             Testes automatizados
Projeto_Final_Artefatos/  Relatório, apresentação, vídeo e artefatos auxiliares
app.py             Interface Streamlit
```

## Segurança

A chave de API é lida apenas do `.env`, que está no `.gitignore`; o repositório contém somente `.env.example`. Documentos enviados no modo LIVE são processados pela API da OpenAI.

## Integrantes

**Grupo: Gp_Protetor**

| Nome | Papel |
|---|---|
| Ricardo Croce | Representante do grupo |
| José Carlos dos Passos | Integrante |
| Renato Sant Anna | Integrante |
| Tiago Del Rio | Integrante |
| Juliano Silva Ignacio | Integrante |

## Licença

Distribuído sob a licença **MIT**. Veja [`LICENSE`](LICENSE).
