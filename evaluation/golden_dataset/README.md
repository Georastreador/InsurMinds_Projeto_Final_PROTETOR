# Golden Dataset — InsurMinds_PROTETOR

Este diretório contém o contrato e as anotações humanas do Golden Dataset D&O.

Cada caso registra: `document_id` e arquivo; campo esperado; valor esperado; página; trecho de evidência; revisor/notas.

- `GD01_CHUBB_ground_truth.json`, `GD02_SOMPO_ground_truth.json`: anotações de campos (EVAL-02/03).
- `GD01_GD02_expected_comparison.json` (v1.0): status esperados para o EVAL-04, anotados antes dos runs. **É a referência principal.**
- `GD01_GD02_expected_comparison_v1.1.json`: revisa dois itens (exclusões ambiental e cibernética) do critério "presença do tema" para "alcance contratual". A revisão foi feita **depois** de ver a saída do sistema e coincide com os dois erros dele; por isso é reportada sempre ao lado da v1.0, nunca isoladamente.
- `ANNOTATION_PROTOCOL.md` e `GD01_GD02_expected_comparison_v2.0.TEMPLATE.json`: protocolo e modelo para ampliar o gabarito para 37 itens discriminantes, com anotação cega.
- `synthetic_fixture.json`: existe apenas para testar o avaliador e **não** é evidência empírica.

Métricas: use `python -m evaluation.aggregate_runs` (média, pior caso e desvio sobre todos os runs LIVE gravados) e `python -m evaluation.calibration` (calibração do juiz do A5). Não reporte o melhor run isolado.

Os documentos não-D&O usados nos testes técnicos pertencem ao Test/Stress Dataset, não ao Golden Dataset D&O.
