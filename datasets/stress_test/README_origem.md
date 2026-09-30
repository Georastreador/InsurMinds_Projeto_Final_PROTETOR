# Conjunto inicial de documentos de seguros para teste

Pacote preparado em 29/09/2026 para testar o fluxo:

> Documento → Extração → Organização → Armazenamento → Consulta → Comparação → Apresentação

## Conteúdo

| Arquivo | Tipo | Origem | Uso sugerido |
|---|---|---|---|
| `pdfs/01_susep_auto_condicoes_gerais.pdf` | Condições gerais de seguro automóvel | SUSEP, consulta pública | Coberturas, exclusões, assistência, franquia e regras de sinistro |
| `pdfs/02_bb_residencial_condicoes_gerais.pdf` | Condições gerais de seguro residencial | BB Seguros | Limites, coberturas, primeiro risco absoluto, exclusões e obrigações |
| `pdfs/03_porto_viagem_condicoes_gerais.pdf` | Condições gerais de seguro viagem | Porto Seguro | Coberturas médicas, assistência, despesas, exclusões e vigência |
| `pdfs/04_chubb_empresarial_pme_condicoes_gerais.pdf` | Condições gerais de seguro empresarial PME | Chubb | Estrutura extensa, múltiplas coberturas, bens, riscos e cláusulas |
| `pdfs/05_banrisul_vida_digital_condicoes_contratuais.pdf` | Condições contratuais de seguro de vida | Banrisul/ICATU | Capital segurado, beneficiários, eventos cobertos e limitações |
| `pdfs/06_apolice_seguro_garantia_publica.pdf` | Apólice pública de seguro garantia | Governo do Estado do RS | Documento mais próximo de uma apólice emitida, com partes, objeto, vigência e valores |
| `synthetic_apolice_residencial.pdf` | Apólice sintética, sem dados reais | Gerada para este pacote | Teste determinístico com gabarito em JSON |
| `synthetic_apolice_residencial.json` | Gabarito esperado da sintética | Gerado para este pacote | Avaliação de extração e normalização |

## Observações importantes

- Os cinco primeiros documentos são predominantemente **condições gerais/contratuais**, não apólices individualizadas. Eles são úteis para testar extração de cláusulas e comparação de produtos.
- O documento de seguro garantia é uma **apólice pública real** disponibilizada em portal governamental e pode conter dados de empresas, números e valores contratuais. Trate-o como dado externo e verifique a política de privacidade do seu ambiente.
- A apólice sintética usa dados fictícios e foi incluída para testes sem risco de exposição de dados pessoais.
- Os documentos públicos foram baixados de URLs oficiais ou de portais institucionais. A disponibilidade e a versão dos links podem mudar; os checksums em `SHA256SUMS` registram exatamente os arquivos incluídos neste pacote.

## Campos recomendados para o seu modelo

`tipo_documento`, `ramo`, `seguradora`, `produto`, `processo_susep`, `numero_apolice`, `proposta`, `segurado`, `tomador`, `beneficiarios`, `objeto_seguro`, `vigencia_inicio`, `vigencia_fim`, `premio`, `franquia`, `limite_maximo_indenizacao`, `capital_segurado`, `coberturas`, `exclusoes`, `carencias`, `obrigações_segurado`, `obrigações_seguradora`, `procedimento_sinistro`, `moeda`, `fonte`, `data_download`, `hash_sha256`.

Para cada campo, armazene também `evidence`: trecho, página e posição aproximada. Isso permite auditoria da extração e comparação entre versões.

## Sugestão de bateria de testes

1. Extração de texto nativo e contagem de páginas.
2. OCR ou fallback para páginas digitalizadas/imagens.
3. Detecção de idioma, tipo documental e ramo.
4. Captura de datas em formatos diferentes e normalização ISO 8601.
5. Captura de valores monetários e normalização numérica.
6. Reconhecimento de tabelas de coberturas, limites e franquias.
7. Separação entre cobertura, exclusão, condição, obrigação e assistência.
8. Busca por cláusulas e referência cruzada entre documentos.
9. Comparação por cobertura equivalente, mesmo quando os nomes divergem.
10. Detecção de ausência de informação: não inferir `franquia`, `carência` ou `limite` quando o documento não informar.

## Fontes originais

- SUSEP – Automóvel: https://www2.susep.gov.br/safe/menumercado/REP2/Produto.aspx/DownloadConsultaPublica/491537
- BB Seguros – Residencial: https://assets-bbsegurosportal.bbseguros.com.br/2024-08/SEGURO_RESIDENCIAL-V_23.pdf?VersionId=9S_5cAEdqqsZu9kjh4HA2yqsfwuFgRxp
- Porto Seguro – Viagem: https://www.portoseguro.com.br/content/dam/documentos/condicoes_gerais/seguro_viagem/2025/cg.seguroviagem.10.12.2025.pdf
- Chubb – Empresarial PME: https://www.chubb.com/content/dam/chubb-sites/chubb-com/br-pt/condicoes-gerais/empresarial-pme/empresarial-pme-processo-susep-15414-005515-201172-versao-a-partir-de-11-12-2025.pdf
- Banrisul/ICATU – Vida Digital: https://www.banrisulseguros.com.br/bux/link/midias/46376_Condicoes-contratuais-Seguro-Vida-Digital.pdf
- Governo do Estado do RS – Seguro Garantia: https://egr.rs.gov.br/upload/arquivos/202208/03141257-008-2018-seguro-garantia-oi-movel-sa.pdf
