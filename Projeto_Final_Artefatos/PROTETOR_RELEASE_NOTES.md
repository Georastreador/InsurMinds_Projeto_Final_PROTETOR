# InsurMinds_PROTETOR — Release v1.3 (01/10/2026)

Revisão técnica crítica da v1.2 aplicada ao código. Foco: métricas honestas, Claim → Evidence verificado, guardrail anti-veredito robusto, correção de um erro de extração encontrado no run de referência, operação e LGPD.

## Avaliação
- `evaluation/aggregate_runs.py`: reavalia offline todos os runs LIVE gravados e reporta média, pior caso e desvio; separa itens discriminantes dos que só esperam "não identificado" e mostra o baseline de um extrator que devolve apenas nulos.
- `evaluation/calibration.py`: distribuição da confiança do juiz do A5 e acurácia por faixa.
- Números principais passam a ser o gabarito v1.0 (média 0,77; pior 0,70); o v1.1 é sempre reportado ao lado.
- `ANNOTATION_PROTOCOL.md` + modelo v2.0 com 37 itens para anotação cega.
- Removidos `EVAL04_result.json` (obsoleto, 9/9) e a cópia duplicada `real_v1/`.

## Claim → Evidence
- `tools/evidence_check.py`: cada trecho citado é conferido no texto da página (segmentos separados por "…", tolerância a 10%). Marca `verified` / `verified_page` em cada referência; A5 reduz a confiança (máx. 0,6) e sinaliza; A6 e a interface mostram "trecho não confirmado" ou "localizado na p. N". Nos runs gravados: 98,5% a 100% conferidos.

## Guardrails
- `guardrails/verdict.py`: padrões ampliados (recomendação, preferência, vantagem, superioridade, PT/EN) que preservam comparações factuais, mais um classificador LLM opcional (camada 2) na síntese e na Consulta. Suíte adversarial com 20 frases bloqueadas e 12 factuais preservadas; zero falso positivo em 490 textos gerados nos runs gravados.
- `guardrails/injection.py`: documento delimitado em `<documento>` no prompt, com instrução explícita; trechos com formato de instrução a uma IA são sinalizados no trace.
- `tools/privacy.py`: CPF, e-mail e telefone mascarados antes do envio (A3 e Consulta).

## Extração e comparação
- A4: `reporting_period` com retroatividade é esvaziado e preenchido a partir da extensão/cláusula de prazo complementar/adicional (erro do run de referência v1.2, Sompo).
- Prompt do A3: definição explícita de `reporting_period`.
- `llm/sectioned.py`: extração por janelas de páginas com fusão determinística (opt-in `OPENAI_EXTRACTION_MODE=sectioned`; ainda não medida LIVE).
- A5: pares formados por pareamento de órfãos vão sempre à revisão humana; corte de confiança configurável (`A5_MIN_CONFIDENCE`).

## Operação e código
- `llm/provider.py`: cliente único com timeout e retries explícitos; erro transitório persistente vira mais uma tentativa do A3, não falha do run.
- `llm/usage.py`: tokens por etapa e custo estimado (com preços configurados) em `metrics.llm_usage` e na aba Auditoria.
- Harness: documentos A e B percorrem A1→A4 em paralelo quando o adaptador é stateless; todas as transições passam pelo `Orchestrator` (fim da atribuição direta de status).
- `llm/factory.py`: componentes LIVE montados num único lugar (app e runners).
- Removidos os pipelines legados (`pipeline.py`, `intelligence_pipeline.py`, `comparison_pipeline.py`); os testes foram migrados para o pipeline principal.
- 145 testes offline (eram 98).

## Pendências
- Rodar `run_live_golden --live` ≥ 3 vezes com a v1.3 e atualizar as métricas com `aggregate_runs`.
- Anotar o gabarito v2.0 seguindo o protocolo.
- Medir `OPENAI_EXTRACTION_MODE=sectioned` antes de torná-lo padrão.
- Atualizar slides e vídeo, que ainda mostram os números da v1.2.

# InsurMinds_PROTETOR — Release v1.2 (30/09/2026)

## Integração GenAI em produção (LIVE executado)
- A3 com Structured Outputs e JSON Schema estrito; A4 como autoridade de validação, com retry e feedback de erros.
- Marcadores de página no texto (Claim → Evidence), orçamento de entrada com omissão declarada, normalização de datas brasileiras.
- A5 com taxonomia D&O (coberturas, exclusões e estrutura SUSEP de cláusulas), juiz semântico por LLM e pareamento de órfãos.
- A6 com síntese generativa limitada aos itens do A5; bloqueio de linguagem de veredito em A5, A6 e Consulta.
- A2 com OCR multimodal (GPT) para PDFs digitalizados, páginas digitalizadas e imagens; Tesseract opcional.
- Escopo por ramo (D&O validado × análise genérica), Consulta ao acervo, modo apresentação, estimativa e progresso por agente, download da síntese em MD e PDF.

## Avaliação
- Golden Chubb × Sompo: EVAL-01/02/03/05 = 1,00; EVAL-04 = 0,80 (gabarito v1.0) e 1,00 (v1.1).
- Robustez e OCR: 5 pares LIVE aprovados; estudo de caso Invepar e PRODEMGE.
- 98 testes automatizados.

# InsurMinds_PROTETOR — Release v1.1

## Objetivo da atualização
Transformar a saída técnica do MVP em uma interface de decisão clara para o analista, sem criar novos agentes nem alterar as responsabilidades A1–A6.

## Alterações principais
- novo nome de aplicação: **InsurMinds_PROTETOR**;
- interface reorganizada em Resumo Executivo, Comparação, Evidências, Apólices e Auditoria da IA;
- cards com campos comparados, diferenças/exclusivos, iguais e revisão humana;
- filtro “somente diferenças e pontos de atenção” e busca por tema;
- Claim → Evidence lado a lado;
- visão resumida de cada apólice, mantendo JSON completo sob expansão;
- exportação da comparação em CSV e do run em JSON;
- observabilidade deslocada para aba própria, preservando valor técnico sem dominar a experiência;
- banco padrão persistente em `data/insurminds_protetor.db`;
- `.env` carregado automaticamente com `python-dotenv`;
- adapter LIVE mantido atrás do mesmo contrato, com JSON do provedor + validação local pelo `PolicySchema`;
- agentes A1–A6 e Harness preservados.

## Compatibilidade
Classes internas como `InsurMindsState` foram mantidas para evitar regressões desnecessárias. O rebranding é aplicado à aplicação, documentação, exports e persistência padrão.
