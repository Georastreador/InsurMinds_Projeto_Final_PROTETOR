# InsurMinds_PROTETOR — Relatório Técnico

**Plataforma inteligente para análise e comparação de apólices D&O**  
Projeto Final · I2A2 — Instituto de Inteligência Artificial Aplicada · Outubro de 2026  
Grupo **Gp_Protetor** — Ricardo Croce (representante), José Carlos dos Passos, Renato Sant Anna, Tiago Del Rio e Juliano Silva Ignacio  
Repositório: _a preencher_

## 1. Resumo

O InsurMinds_PROTETOR é um MVP que recebe duas apólices ou condições contratuais de seguro D&O (Directors & Officers) em PDF ou imagem, extrai e estrutura seu conteúdo com IA generativa, compara coberturas, exclusões, franquias, limites e cláusulas, e apresenta ao analista uma síntese executiva em que cada diferença aponta a página de origem. O sistema não recomenda qual apólice contratar: descreve diferenças documentais e deixa a decisão ao especialista.

A solução é organizada como uma arquitetura multiagente controlada por um **Harness** (orquestrador com máquina de estados), com seis agentes especializados (A1 a A6) e um agente de consulta sob demanda. Usa a API da OpenAI em cinco pontos: OCR multimodal, extração estruturada, julgamento semântico da comparação, redação da síntese e respostas de consulta.

No conjunto de avaliação principal (condições gerais D&O da Chubb e da Sompo, com anotação humana), a extração acertou 100% dos campos anotados que o schema representa, citou a página anotada em 100% das evidências e atingiu 0,80 de acurácia na comparação (1,00 sobre o gabarito revisado v1.1). Uma análise completa de dois documentos de 50 a 70 páginas leva cerca de 3 minutos.

## 2. Problema e objetivos

Apólices de seguro são documentos longos e jurídicos. Em D&O, cada seguradora organiza coberturas, extensões, exclusões e cláusulas de forma própria, com nomes diferentes para conceitos equivalentes, e muitos valores (limites, franquias, vigência) ficam na Especificação da Apólice, não nas condições gerais. A comparação manual exige horas de leitura especializada.

Objetivos do MVP:

1. Receber documentos em PDF ou imagem e extrair o conteúdo automaticamente.
2. Estruturar a informação num formato comum e armazená-la.
3. Comparar ao menos duas apólices, identificando diferenças materiais.
4. Apresentar as principais diferenças com rastreabilidade Claim → Evidence (página e trecho).
5. Permitir consulta ao acervo de documentos processados.
6. Usar IA generativa de forma controlada: sem inventar fatos e sem emitir veredito.

## 3. Arquitetura da solução

| Camada | Componentes | Papel |
|---|---|---|
| Interface | Streamlit (`app.py`) | Upload, progresso, resultados em 5 abas, consulta, downloads, modo apresentação |
| Orquestração | Harness: `Orchestrator`, `CompleteMVPPipeline`, `scope`, `progress` | Estados, transições, retries, escopo/ramo, trace, persistência |
| Agentes | A1 Intake, A2 Extraction, A3 Análise, A4 Validação, A5 Comparação, A6 Síntese, Consulta | Responsabilidades delimitadas |
| IA generativa | Adaptadores OpenAI (`llm/client.py`, `tools/ocr_tools.py`) | OCR, extração, juiz semântico, síntese, Q&A |
| Contratos | `PolicySchema`, `ComparisonResult`, `InsurMindsState`, taxonomia D&O | Formato comum e validável |
| Dados | SQLite (`storage/database.py`) | Runs, documentos, textos, apólices, comparações, relatórios |
| Qualidade | Golden Dataset, EVAL-01 a 05, runners LIVE, 98 testes | Medição e regressão |

**Princípio central:** o Harness controla o sistema; os agentes executam funções delimitadas. Nenhum agente decide a sequência, repete a si mesmo ou encerra a execução. Isso torna o comportamento previsível, auditável e testável sem API.

## 4. Fluxo completo de processamento

1. **Upload:** o analista envia A e B. A interface mostra páginas, tamanho, páginas digitalizadas e o tempo estimado.
2. **A1 Intake:** valida existência, tamanho e formato (PDF, PNG, JPG) e registra metadados.
3. **A2 Extraction:** extrai o texto nativo por página com PyMuPDF e insere marcadores `[[PÁGINA n]]`. Páginas com imagem e sem camada de texto, e arquivos de imagem, passam por OCR multimodal com GPT, em lotes de 4 páginas, com transcrição literal.
4. **A3 Análise:** o LLM recebe o texto (até 300 mil caracteres; acima disso mantêm-se as primeiras páginas e as de maior densidade contratual, com aviso) e preenche o `PolicySchema` via Structured Outputs com JSON Schema estrito. Classifica ramo, natureza do documento e o conceito D&O de cada item.
5. **A4 Validação:** valida o candidato com Pydantic, normaliza datas brasileiras, rejeita anos implausíveis e remove "valores" que são apenas definições de papel. Se falhar, o Harness pede ao A3 nova tentativa com a lista de erros (até 2 retries).
6. **Escopo:** o Harness confirma o ramo (LLM com reforço determinístico) e marca o run como "D&O validado" ou "genérico".
7. **A5 Comparação:** compara campos simples, limites e Sides A/B/C; pareia coberturas, exclusões e cláusulas pelo conceito da taxonomia; pede ao LLM o pareamento de itens órfãos e o julgamento do conteúdo dos pares (igual, diferente ou revisão humana).
8. **A6 Síntese:** o LLM redige a visão geral e as principais diferenças referindo-se apenas a itens do A5 por identificador; status e páginas são anexados pelo código.
9. **Persistência e apresentação:** tudo é gravado no SQLite e exibido em Resumo, Comparação, Evidências, Apólices e Auditoria, com exportação em MD, PDF, CSV e JSON.

## 5. Agentes desenvolvidos

| Agente | Entrada | Saída | Técnica | Principais salvaguardas |
|---|---|---|---|---|
| A1 Intake | Arquivo | Metadados | Regras | Formato, tamanho, existência |
| A2 Extraction | Metadados | Texto por página | PyMuPDF + OCR GPT (Tesseract opcional) | OCR só onde falta texto; limite de 40 páginas com aviso; transcrição literal |
| A3 Análise D&O | Texto | Candidato `PolicySchema` | LLM com Structured Outputs | Schema estrito; "não inventar"; página em cada evidência |
| A4 Validação | Candidato | `PolicySchema` válido | Pydantic + regras | Retry com feedback; datas plausíveis; papéis ≠ valores |
| A5 Comparação | 2 apólices | `ComparisonResult` | Taxonomia + LLM juiz | Estados controlados; confiança mínima 0,7; veredito vira revisão |
| A6 Síntese | `ComparisonResult` | Relatório | LLM redator | Só itens existentes; sem veredito; alternativa determinística |
| Consulta | Pergunta + acervo | Resposta citada | Recuperação de páginas + LLM | Só páginas enviadas podem ser citadas; sem veredito |

## 6. Tecnologias utilizadas

Python 3.10+, Streamlit, Pydantic v2, OpenAI API (Responses API, Structured Outputs e entrada de imagem), PyMuPDF, Markdown, SQLite e pytest. O modelo é configurável em `OPENAI_MODEL`; os resultados deste relatório foram obtidos com `gpt-5.6-luna`.

## 7. Justificativa das decisões arquiteturais

- **Harness no controle, agentes especializados.** Separar coordenação de execução permite testar cada agente isoladamente, repetir etapas com segurança e registrar um trace completo, em vez de depender de agentes que decidem a própria sequência.
- **Structured Outputs com schema estrito, validação local no A4.** O schema estrito força o formato no provedor; o A4 continua sendo a autoridade de validação, o que permite retries com feedback. No primeiro teste LIVE, sem schema estrito, o modelo devolveu 22 erros de estrutura e o run falhou; com a mudança, os runs passaram a ser aceitos na primeira tentativa, e as poucas rejeições (ex.: "5% do LMI" num campo numérico) foram corrigidas na segunda.
- **Marcadores de página no texto.** São a base do Claim → Evidence: o LLM cita a página que viu, e a interface a exibe ao lado de cada diferença.
- **Taxonomia D&O + juiz semântico.** Comparar pelo nome devolvido pelo LLM falhava entre seguradoras (a Chubb veio em inglês, a Sompo em português): a acurácia da comparação era 0,50. Pareando por conceito e deixando o LLM julgar apenas o conteúdo dos pares, chegou a 0,80.
- **Síntese generativa limitada por identificadores.** A primeira síntese determinística tinha 87 mil caracteres. A versão generativa tem cerca de 5 mil, mas o modelo só pode referir itens existentes, e páginas e status são anexados pelo código.
- **OCR com GPT em vez de Tesseract.** Não exige instalação no sistema, lida melhor com tabelas e usa a mesma credencial; o Tesseract permanece como alternativa offline opcional.
- **Escopo D&O com análise genérica sinalizada.** O enunciado foca D&O; documentos de outros ramos são analisados com os campos gerais e marcados como fora do escopo validado, em vez de serem tratados silenciosamente como D&O.
- **SQLite e Streamlit.** Simples de instalar e suficientes para um MVP demonstrável, conforme a orientação de preferir soluções simples e compreensíveis.

## 8. Avaliação e resultados

### 8.1 Dataset 1 — Golden D&O (Chubb × Sompo)

Dois documentos oficiais de condições gerais D&O (70 e 49 páginas) com anotação humana de campos, páginas e trechos, e uma comparação esperada de 10 itens.

| Métrica | Chubb | Sompo | Meta |
|---|---|---|---|
| EVAL-01 Validade do schema | 1,00 | 1,00 | — |
| EVAL-02 Acerto dos campos anotados | 1,00 (12/12) | 1,00 (11/11) | ≥ 0,80 |
| EVAL-03 Evidência na página anotada | 1,00 (6/6) | 1,00 (5/5) | ≥ 0,80 |
| EVAL-05 Proxy léxico (afirmações presentes no texto) | 1,00 | 1,00 | ≥ 0,80 |
| EVAL-04 Comparação — gabarito v1.0 | 0,80 (8/10) | | ≥ 0,90 |
| EVAL-04 Comparação — gabarito v1.1 | 1,00 (10/10) | | ≥ 0,90 |

A extração respeitou o guardrail central: número da apólice, vigência e limites, que as condições gerais delegam à Especificação, foram mantidos vazios, como no gabarito. Cinco anotações que expressam regras sem campo no schema (ex.: base de reclamações) foram excluídas do denominador e listadas para revisão.

As duas divergências da comparação com a v1.0 foram verificadas no texto-fonte: a exclusão ambiental da Chubb tem recompra por cobertura adicional (p. 42 e 51–55), ausente na Sompo, e a exclusão cibernética da Chubb limita-se à perda de dados (p. 65), enquanto a da Sompo abrange ataques e malware (p. 17). O gabarito foi revisado para v1.1 com justificativa e páginas; a v1.0 foi mantida e os dois resultados são reportados.

### 8.2 Dataset 3 — Robustez e OCR (execuções LIVE)

| Cenário | Verificações | Tempo |
|---|---|---|
| Empresarial PME (254 páginas) × Residencial — limite de tamanho e ramos diferentes | 8/8 | 3 min 05 s |
| Residencial × apólice sintética — limites e franquias em R$ contra gabarito | 19/19 | 2 min 17 s |
| Seguro Garantia × Vida — controle negativo de escopo | 7/7 | 1 min 43 s |
| PDF só imagem × PDF nativo da mesma apólice — OCR | 33/33 | 1 min 40 s |
| Imagem PNG × PDF nativo — OCR de imagem | aprovado | 57 s |

### 8.3 Dataset 2 — Estudo de caso de evolução temporal

- **PRODEMGE 2020 (contrato digitalizado, Ezze) × 2025 (Austral):** o OCR leu as 15 páginas em 1 min 28 s. O sistema identificou a troca de seguradora, o aumento do limite de R$ 30 mi para R$ 40 mi e o valor contratado (R$ 74 mil para R$ 35 mil), conferidos nos documentos.
- **Invepar DFP 2024 × ITR 2025 (demonstrações financeiras):** a síntese captou a mudança de seguradora do D&O (Allianz na tabela de 2024, Berkley em 2025), com páginas. O caso expôs limitações descritas na seção 9: unidade em milhares, várias apólices num mesmo documento e uma nota de rodapé que contradiz a tabela na própria DFP.

### 8.4 Testes automatizados

98 testes cobrem agentes, Harness, retries, guardrails, taxonomia, OCR (com motor simulado), exportação, consulta e avaliação, sem chamadas de API. A instalação limpa a partir do `requirements.txt` foi verificada.

## 9. Limitações conhecidas

- **Amostra de avaliação pequena:** 2 documentos anotados e 10 itens de comparação. A revisão v1.1 do gabarito foi motivada por divergências apontadas pelo próprio sistema; por isso v1.0 e v1.1 são reportadas juntas.
- **Variação entre execuções:** o LLM não é determinístico; a quantidade e a granularidade dos itens extraídos variam entre runs, o que afeta a contagem de itens exclusivos.
- **Condições gerais × apólice emitida:** o Golden Dataset não tem valores individualizados; limites e franquias em R$ foram verificados na apólice sintética e nos contratos do estudo de caso.
- **Um documento, uma apólice:** o schema representa uma apólice por documento. Demonstrações financeiras que listam várias apólices geram campos inconsistentes entre documentos.
- **Unidades:** valores em "R$ mil" são reconhecidos em aviso, mas não convertidos automaticamente.
- **Datas deduzidas:** quando o documento diz apenas "12 meses a partir da assinatura", o modelo pode calcular a vigência a partir da assinatura eletrônica; isso é sinalizado em aviso.
- **Normalização de texto:** diferenças de pontuação (hífen × travessão) podem marcar como "diferente" um mesmo nome.
- **Limites de tamanho:** acima de 300 mil caracteres, páginas de menor densidade contratual são omitidas (com aviso); o OCR lê até 40 páginas por documento.
- **OCR generativo:** pode repetir ou, em tese, completar trechos; a transcrição é instruída a ser literal e o método fica registrado no trace.
- **Modo DEMO:** o extrator heurístico serve apenas para demonstração offline.
- **Privacidade:** no modo LIVE, os documentos são enviados à API da OpenAI.

## 10. Possibilidades de evolução

1. Ampliar o Golden Dataset com os candidatos já catalogados (Fator, AXA, HDI) e medir a variação em execuções repetidas.
2. Unir condições gerais e Especificação da mesma apólice numa única análise.
3. Suportar documentos com várias apólices (divulgações financeiras) e normalização de unidades.
4. Busca semântica com embeddings no acervo e comparação de mais de dois documentos.
5. Ciclo de feedback do especialista: correções humanas alimentando o gabarito e ajustes da taxonomia.
6. Modelos locais ou OCR dedicado (Azure Document Intelligence, Textract) para cenários com restrição de dados.
7. Integração contínua executando testes e avaliações a cada mudança.

## 11. Fontes dos documentos

- Chubb — Condições Contratuais D&O Capital Fechado, processo SUSEP 15414.900832/2017-90, versão 12/2025: https://www.chubb.com/content/dam/chubb-sites/chubb-com/br-pt/condicoes-gerais/diretores-e-administradores/capital-fechado-processo-susep-15414-900832-2017-90-versao-a-partir-de-16-12-2025.pdf
- Sompo — Condições Gerais RC D&O v1.5, processo SUSEP 15414.652408/2023-71, 11/2025: https://sompo.com.br/produto/sompo-responsabilidade-civil-do
- Invepar — Demonstrações contábeis de 31/12/2024 (DFP) e 31/12/2025, publicadas no site de relações com investidores.
- PRODEMGE — Contratos PS 907/2020 (Ezze Seguros) e PS 1037/2025 (Austral Seguradora), Sistema Eletrônico de Informações de Minas Gerais.
- Robustez: SUSEP (Automóvel), BB Seguros (Residencial), Porto Seguro (Viagem), Chubb (Empresarial PME), Banrisul/Icatu (Vida), Governo do RS (Seguro Garantia) e apólice sintética criada para o projeto.

Checksums SHA-256 e URLs completas: `datasets/SOURCES.md` e `datasets/stress_test/README_origem.md`.
