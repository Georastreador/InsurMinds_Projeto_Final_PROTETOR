# Golden Dataset — InsurMinds_PROTETOR

Este diretório contém o contrato e as anotações humanas do Golden Dataset D&O.

Cada caso registra:
- `document_id` e arquivo;
- campo esperado;
- valor esperado;
- página;
- trecho de evidência;
- revisor/notas.

Arquivos GD01/GD02 representam as anotações de referência produzidas para os documentos públicos Chubb e Sompo selecionados no projeto. O arquivo `synthetic_fixture.json` existe apenas para testar o avaliador e **não** deve ser incluído como evidência empírica do desempenho do sistema.

`GD01_GD02_expected_comparison.json` (v1.0) registra os status esperados para EVAL-04. `GD01_GD02_expected_comparison_v1.1.json` revisa dois itens (exclusões ambiental e cibernética) do critério "presença do tema" para "alcance contratual", com justificativa e páginas; a v1.0 é mantida e as duas versões são reportadas juntas. O resultado EVAL-04 incluído no pacote corresponde à avaliação anteriormente executada sobre representações manualmente curadas e não deve ser confundido com uma futura medição end-to-end do run LIVE.

Os documentos não-D&O usados nos testes técnicos pertencem ao Test/Stress Dataset, não ao Golden Dataset D&O.

Status atual da avaliação: `EVALUATION_STATUS_v1.1.json` (runs LIVE end-to-end executados em 30/09/2026).
