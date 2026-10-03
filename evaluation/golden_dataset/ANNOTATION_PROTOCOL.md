# Protocolo de anotação do Golden Dataset v2.0 (comparação D&O)

**Objetivo:** levar o EVAL-04 de 10 itens (5 discriminantes) para 30–40 itens discriminantes, anotados **antes** de rodar o sistema, para medir também o que hoje não é medido: em 30/09/2026 o run de referência gerou 102 itens comparados e apenas 10 tinham gabarito.

## Regras

1. **Anotação cega.** O anotador não consulta saídas do PROTETOR (runs, sínteses, tabelas) antes de fechar a anotação. Registrar data e nome no campo `annotator`.
2. **Dois anotadores por item, quando possível.** Divergências são resolvidas por um terceiro e registradas em `adjudication`. Reportar a concordância (proporção de itens iguais) junto com o EVAL-04.
3. **Critério único:** o status descreve o **alcance contratual** (o mesmo critério do A5), não a presença do tema.
   - `EQUAL`: mesmo alcance e condições, ainda que com redação diferente.
   - `DIFFERENT`: diferença material de alcance, condição, exceção, prazo ou valor.
   - `ONLY_A` / `ONLY_B`: o tema existe em um documento e não no outro (conferido por leitura, não por busca de palavra).
   - `REVIEW_REQUIRED`: a equivalência depende de informação ausente dos dois textos (ex.: Especificação).
4. **Evidência obrigatória:** página e trecho literal de cada lado (`page_a`, `excerpt_a`, `page_b`, `excerpt_b`).
5. **Congelamento:** depois de rodar o sistema, o gabarito não muda. Correções viram uma nova versão (`v2.1`), e as duas versões são reportadas, como foi feito com v1.0 e v1.1.
6. **Itens triviais à parte:** campos que as condições gerais delegam à Especificação (`NOT_IDENTIFIED`) ficam em lista separada e não entram no escore discriminante.

## Itens sugeridos para Chubb (GD01) × Sompo (GD02)

Escolhidos por peso contratual; o status **não** está preenchido de propósito.

| Grupo | Item (campo A5) |
|---|---|
| Estrutura | `insuring_side_A`, `insuring_side_B`, `insuring_side_C` |
| Prazos | `reporting_period` (prazo complementar/adicional), `clauses:base_reclamacoes`, `clauses:vigencia_renovacao` |
| Franquias | `retentions`, `clauses:franquia` |
| Coberturas | `coverages:custos_defesa`, `coverages:investigacao`, `coverages:crise_relacoes_publicas`, `coverages:responsabilidade_ambiental`, `coverages:penhora_bloqueio`, `coverages:extradicao`, `coverages:herdeiros_conjuges`, `coverages:segurados_aposentados`, `coverages:praticas_trabalhistas`, `coverages:multas_penalidades`, `coverages:processos_administrativos` |
| Exclusões | `exclusions:dolo_fraude`, `exclusions:vantagem_indevida`, `exclusions:reclamacoes_anteriores`, `exclusions:danos_materiais_corporais`, `exclusions:poluicao_ambiental`, `exclusions:cibernetico`, `exclusions:multas_penalidades`, `exclusions:rc_profissional`, `exclusions:trabalhistas_previdenciarias`, `exclusions:tributos`, `exclusions:valores_mobiliarios`, `exclusions:segurado_contra_segurado`, `exclusions:sancoes_embargos` |
| Cláusulas | `clauses:defesa_acordos`, `clauses:sinistro_aviso_regulacao`, `clauses:sub_rogacao`, `clauses:cancelamento_rescisao`, `clauses:ambito_territorial` |

Modelo de arquivo: `GD01_GD02_expected_comparison_v2.0.TEMPLATE.json`. Depois de preenchido, renomeie para `..._v2.0.json`, inclua-o em `EXPECTED_COMPARISON` (`evaluation/run_live_golden.py`) e rode `python -m evaluation.aggregate_runs`.

## Próximos documentos

Os candidatos já catalogados (Fator, AXA, HDI) entram como novos pares, com o mesmo protocolo. Meta mínima para uma conclusão defensável: 3 pares e cerca de 100 itens discriminantes.
