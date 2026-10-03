# InsurMinds_PROTETOR — Análise e Comparação de Apólices D&O com IA Generativa

Projeto Final do curso de IA Aplicada do **I2A2 — Instituto de Inteligência Artificial Aplicada (2026)**.

O PROTETOR recebe duas apólices ou condições contratuais de seguro **D&O (Directors & Officers)** em PDF ou imagem, extrai e estrutura seu conteúdo com IA generativa, compara coberturas, exclusões, franquias, limites e cláusulas, e entrega ao analista uma **síntese executiva com evidências por página** — sem recomendar qual apólice contratar. A decisão final é humana.

## O problema

Apólices D&O são longas (50 a 250 páginas), redigidas em linguagem jurídica e estruturadas de forma diferente por cada seguradora. Comparar duas delas exige localizar e alinhar dezenas de coberturas, exclusões e cláusulas, o que leva horas de trabalho especializado. O PROTETOR faz a leitura, o alinhamento e a síntese em cerca de 3 minutos, preservando a página de origem de cada afirmação (Claim → Evidence) e **conferindo cada trecho citado contra o texto da página** antes de mostrá-lo ao analista.

## Arquitetura

O PROTETOR é um **workflow orquestrado**: um Harness determinístico decide a sequência, os retries e o encerramento; as etapas A1–A6 executam funções delimitadas, quatro delas com IA generativa. Não há agentes autônomos escolhendo o próximo passo — escolha deliberada para um domínio em que previsibilidade e auditabilidade valem mais que autonomia.

```
Upload A/B ─► Harness (Orchestrator: estados, retries, guardrails, trace, custo, persistência)
               │   A e B percorrem A1→A4 em paralelo
               │
               ├─ A1 Intake ........ valida arquivo e metadados
               ├─ A2 Extraction .... texto nativo (PyMuPDF) · OCR com GPT para páginas digitalizadas e imagens
               ├─ A3 Análise D&O ... LLM estrutura o documento no PolicySchema (JSON Schema estrito)
               ├─ A4 Validation .... Pydantic + guardrails; falha → nova tentativa do A3 com os erros
               ├─ Verificação ...... cada trecho de evidência conferido no texto da página citada
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
| **A4 Validação** | Schema, datas plausíveis, datas BR→ISO, remove "valores" que são só definições de papel, separa prazo complementar de retroatividade | — |
| **Verificação de evidência** | Confere cada trecho citado no texto da página (aceita "…" e diferenças mínimas); sinaliza página errada ou trecho não localizado e reduz a confiança do item | — |
| **A5 Comparação** | Estados controlados (`EQUAL`, `DIFFERENT`, `ONLY_A/B`, `REVIEW_REQUIRED`…); pares formados fora da taxonomia vão sempre à revisão humana | Juiz semântico + pareamento de órfãos |
| **A6 Síntese** | Principais diferenças com página e status da evidência; bloqueio de veredito em duas camadas | Redação da síntese |
| **Consulta** | Busca de temas no acervo e perguntas com resposta citando páginas | Q&A ancorado |

**Guardrails:**
- não inventar fatos; campos individualizados ausentes ficam `null`;
- evidência conferida no texto da página citada (`tools/evidence_check.py`); citações da Consulta só de páginas efetivamente enviadas;
- nenhuma linguagem de superioridade ou recomendação: padrões determinísticos + classificador LLM (`guardrails/verdict.py`), com suíte adversarial em `tests/test_verdict_guard.py`;
- o documento é delimitado no prompt como conteúdo, e trechos com formato de instrução a uma IA são sinalizados (`guardrails/injection.py`);
- CPF, e-mail e telefone são mascarados antes do envio ao provedor (`tools/privacy.py`, LGPD);
- documentos fora de D&O são sinalizados como "escopo genérico"; omissões por limite de tamanho são sempre avisadas.

## Tecnologias

- **Python 3.10+**, **Streamlit** (interface), **Pydantic v2** (contratos e validação)
- **OpenAI API** — Responses API com Structured Outputs (extração, julgamento semântico, síntese, consulta) e entrada de imagem (OCR)
- **PyMuPDF** (texto, renderização de páginas, PDF da síntese), **Markdown**
- **SQLite** (armazenamento estruturado de runs, documentos, textos, apólices, comparações e relatórios)
- **pytest** (145 testes automatizados, sem chamadas de API)
- Tesseract (opcional, apenas como OCR offline se estiver instalado)

## Instalação

```bash
git clone https://github.com/Georastreador/InsurMinds_Projeto_Final_PROTETOR.git
cd InsurMinds_Projeto_Final_PROTETOR
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
| `OPENAI_MAX_INPUT_CHARS` | Limite de texto enviado ao A3 por chamada | `300000` |
| `OPENAI_TIMEOUT_S` / `OPENAI_MAX_RETRIES` | Timeout e tentativas com espera crescente (429, 5xx, conexão) | `300` / `4` |
| `OPENAI_EXTRACTION_MODE` | `single` ou `sectioned` (janelas de páginas + fusão; experimental, ainda não medido LIVE) | `single` |
| `VERDICT_LLM_CHECK` | Camada 2 do guardrail anti-veredito (classificador LLM) | `true` |
| `A5_MIN_CONFIDENCE` | Corte de confiança do juiz do A5 | `0.7` |
| `REDACT_PII` | Mascarar CPF, e-mail e telefone antes do envio | `true` |
| `OPENAI_PRICE_INPUT_PER_MTOK` / `..._OUTPUT_...` | Preço para estimar custo na Auditoria | vazio |
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
pytest -q                                       # 145 testes offline
python -m evaluation.run_live_golden --live     # Dataset 1 com gabarito humano (API)
python -m evaluation.aggregate_runs             # média, pior caso e desvio sobre todos os runs gravados (offline)
python -m evaluation.calibration                # calibração do juiz semântico do A5 (offline)
python -m evaluation.run_live_stress            # robustez e OCR (API)
python -m evaluation.make_ocr_fixtures          # gera os documentos digitalizados de teste
```

**Resultados no Dataset 1 (Chubb × Sompo) — 3 runs LIVE com o A5 atual, reavaliados offline** (`evaluation/results/AGGREGATE_*.md`):

| Métrica | Média | Pior caso | Observação |
|---|---|---|---|
| EVAL-01 Validade do schema | 1,00 | 1,00 | — |
| EVAL-02 Campos (todos) — Chubb / Sompo | 0,97 / 1,00 | 0,92 / 1,00 | Um extrator que só devolvesse nulos teria 0,50 / 0,55 |
| EVAL-02 Campos discriminantes — Chubb / Sompo | 1,00 / 1,00 | 1,00 / 1,00 | 6 e 5 campos com valor esperado |
| EVAL-03 Página da evidência | 1,00 | 1,00 | Trecho idêntico ao do gabarito: 0,61 / 0,27 |
| Evidência conferida na página (todas as referências) | 0,99 – 1,00 | 0,98 | Verificação em runtime introduzida na v1.3 |
| **EVAL-04 Comparação, gabarito v1.0 (10 itens)** | **0,77** | **0,70** | Meta ≥ 0,90 não atingida |
| EVAL-04 v1.0, só itens discriminantes (5) | 0,53 | 0,40 | Os outros 5 esperam "não identificado" |
| EVAL-04 gabarito v1.1 (10 itens) | 0,97 | 0,90 | v1.1 revisada após ver a saída: reportar sempre com a v1.0 |
| EVAL-05 Proxy léxico | 1,00 | 0,00 | 1 ou 2 afirmações por documento; um run falhou antes do guardrail de papéis do A4 |

Calibração do A5: nos 79 itens julgados, a confiança mínima foi 0,78 e a mediana 0,98. Os 15 itens com gabarito tinham confiança ≥ 0,95 e acerto de 0,53 (v1.0). A confiança autodeclarada não separa acertos de erros, então pares formados fora da taxonomia passaram a exigir revisão humana. O próximo passo é ampliar o gabarito (`evaluation/golden_dataset/ANNOTATION_PROTOCOL.md`).

Os runs gravados foram produzidos pela v1.2. As correções da v1.3 (prazo complementar × retroatividade, verificação de evidência, revisão de pares órfãos) ainda precisam de novos runs LIVE para serem medidas: rode `run_live_golden --live` pelo menos 3 vezes e depois `aggregate_runs`.

Robustez: 5 pares LIVE (254 páginas, ramos diferentes, apólice sintética com valores, PDF digitalizado e imagem) passaram em todas as verificações da v1.2.

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
guardrails/        Veredito (2 camadas) e prompt injection
orchestration/     Harness: orquestrador, estados, pipeline, escopo, progresso
llm/               Adaptadores OpenAI, cliente único (timeout/retries), custo, extração seccionada, schema estrito
schemas/           PolicySchema, ComparisonResult, taxonomia D&O, rótulos
tools/             PDF, OCR, orçamento de texto, verificação de evidência, LGPD, exportação
storage/           SQLite
evaluation/        Golden Dataset, avaliadores EVAL-01..05, runners LIVE, resultados
datasets/          Documentos públicos e sintéticos de teste
tests/             Testes automatizados
Projeto_Final_Artefatos/  Relatório, apresentação, vídeo e artefatos auxiliares
app.py             Interface Streamlit
```

## Segurança

A chave de API é lida apenas do `.env`, que está no `.gitignore`; o repositório contém somente `.env.example`. Documentos enviados no modo LIVE são processados pela API da OpenAI: CPF, e-mail e telefone são mascarados antes do envio (`REDACT_PII`), mas **imagens enviadas ao OCR não podem ser mascaradas**. O SQLite local guarda o texto integral sem criptografia; para documentos reais de clientes, use disco criptografado e defina a política de retenção. O texto do documento é delimitado no prompt e tratado como conteúdo; tentativas de instrução embutida são sinalizadas na Auditoria.

## Integrantes

**Grupo: Gp_Protetor**

| Nome | Papel |
|---|---|
| Ricardo Croce | Chefe do grupo |
| José Carlos dos Passos | Integrante |
| Renato Sant Anna | Integrante |
| Tiago Del Rio | Integrante |
| Juliano Silva Ignacio | Integrante |

## Licença

Distribuído sob a licença **MIT**. Veja [`LICENSE`](LICENSE).
