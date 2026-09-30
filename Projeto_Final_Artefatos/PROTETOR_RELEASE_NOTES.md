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
