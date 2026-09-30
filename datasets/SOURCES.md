# Fontes dos documentos

Todos os documentos usados são públicos ou sintéticos. Os checksums SHA-256 registram exatamente as versões utilizadas.

## Dataset 1 — Golden D&O (Chubb × Sompo) · `data/golden_dataset/`

| Documento | Emissor | Versão | Processo SUSEP | Fonte | SHA-256 |
|---|---|---|---|---|---|
| Condições Contratuais D&O Capital Fechado | Chubb | 12/2025 | 15414.900832/2017-90 | https://www.chubb.com/content/dam/chubb-sites/chubb-com/br-pt/condicoes-gerais/diretores-e-administradores/capital-fechado-processo-susep-15414-900832-2017-90-versao-a-partir-de-16-12-2025.pdf | `5db507e3…9e85b` |
| Condições Gerais RC D&O (v1.5) | Sompo Seguros | 11/2025 | 15414.652408/2023-71 | https://sompo.com.br/produto/sompo-responsabilidade-civil-do | `605cc300…874b6` |

Anotação humana: `evaluation/golden_dataset/` (GD01, GD02; comparação esperada v1.0 e v1.1).

## Dataset 2 — Estudo de caso: evolução temporal · `datasets/case_study/`

| Documento | Organização | Uso | SHA-256 |
|---|---|---|---|
| DFP 4T24 — Demonstrações contábeis 31/12/2024 | Invepar | Divulgação do seguro D&O (nota 21, p. 80) | `a402f979…270c` |
| ITR 4T25 — Demonstrações contábeis 31/12/2025 | Invepar | Divulgação do seguro D&O (nota 21, p. 75) | `77e1ced6…2d7` |
| Contrato PS 907/2020 (digitalizado) | PRODEMGE × Ezze Seguros | Contratação de D&O, LMI R$ 30 mi | `a78ae190…8ad1` |
| Contrato PS 1037/2025 | PRODEMGE × Austral Seguradora | Contratação de D&O, LMI R$ 40 mi | `a4bc7ca9…6105` |

Fontes: relações com investidores da Invepar (demonstrações contábeis) e Sistema Eletrônico de Informações do Governo de Minas Gerais (contratos PRODEMGE). _URLs exatas a registrar pelo grupo._

## Dataset 3 — Robustez (outros ramos) · `datasets/stress_test/`

Condições gerais de Automóvel (SUSEP), Residencial (BB Seguros), Viagem (Porto Seguro), Empresarial PME (Chubb), Vida (Banrisul/Icatu), apólice pública de Seguro Garantia (Governo do RS) e uma apólice residencial **sintética** com gabarito JSON. URLs e checksums em `datasets/stress_test/README_origem.md` e `SHA256SUMS`.

Os documentos de outros ramos e o estudo de caso **não** entram nas métricas D&O (EVAL-02 a 04); servem para robustez, OCR e sensibilidade.
