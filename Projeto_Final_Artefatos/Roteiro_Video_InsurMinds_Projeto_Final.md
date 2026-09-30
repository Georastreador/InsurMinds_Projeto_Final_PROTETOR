# Roteiro do vídeo — InsurMinds_Projeto_Final.mp4

Duração total: **4 min 47 s** (limite do I2A2: 5 min). Narração gerada por voz sintética pt-BR (macOS, Luciana); o grupo pode regravar com voz própria seguindo este roteiro e os tempos abaixo.

Cobertura dos itens exigidos: problema (00:00–01:08) · arquitetura (01:08–01:54) · funcionamento da aplicação (01:54–03:24) · resultados (03:24–04:20) · encerramento.


## 1. O problema e a solução

**00:00 · Slide 1** — Olá! Nós somos o grupo Gp_Protetor, e este é o InsurMinds_PROTETOR: uma plataforma que lê, compara e explica apólices de seguro D&O, usando inteligência artificial generativa.

**00:13 · Slide 2** — O problema. Apólices D&O são documentos longos, de 49 a 254 páginas nos nossos testes, escritos em linguagem jurídica. Cada seguradora organiza coberturas, exclusões e cláusulas do seu jeito, com nomes diferentes, às vezes até em outro idioma. Comparar duas apólices exige horas de leitura especializada, e cada conclusão precisa ser verificável no texto original.

**00:43 · Slide 3** — A nossa solução faz três coisas. Lê o documento, inclusive PDF digitalizado ou imagem. Compara coberturas, exclusões e cláusulas pelo conceito, e não pelo nome. E explica, numa síntese executiva que aponta a página de cada diferença. Tudo em cerca de três minutos, sem dizer qual apólice é melhor: a decisão continua humana.


## 2. Arquitetura da solução

**01:08 · Slide 4** — Na arquitetura, um orquestrador, que chamamos de Harness, controla a máquina de estados, as novas tentativas e o registro de cada etapa. Seis agentes especializados executam o fluxo: recepção, extração com OCR, análise estruturada, validação, comparação e síntese. Os blocos em lilás usam IA generativa, sempre com contratos tipados e registro completo para auditoria.

**01:37 · Slide 6** — A IA trabalha sob controle. O modelo responde num esquema estrito, validado pelo código. Se errar, recebe os erros e tenta de novo. Cada afirmação cita a página de origem, e palavras como melhor, pior ou recomendada são bloqueadas.


## 3. Funcionamento da aplicação

**01:54 · Aplicação — upload e estimativa** — Vamos à aplicação. Carregamos as condições gerais da Chubb e da Sompo. Antes de processar, a tela já mostra o número de páginas, o tamanho de cada documento e o tempo estimado da análise.

**02:08 · Aplicação — resumo executivo (modo apresentação)** — Para esta demonstração, abrimos pelo modo apresentação um processamento real já gravado. O resumo executivo, gerado por IA, destaca as principais diferenças, como franquias, prazo complementar e exclusões, cada uma com a página nos dois documentos. A síntese pode ser baixada em Markdown ou PDF.

**02:31 · Aplicação — aba Comparação** — Na aba Comparação, a matriz completa pode ser filtrada para mostrar apenas as diferenças e os pontos de atenção.

**02:39 · Aplicação — aba Evidências** — Em Evidências, vemos lado a lado o trecho de cada apólice que sustenta a diferença.

**02:46 · Aplicação — aba Auditoria da IA** — E a Auditoria da IA registra o rastreamento de todos os agentes, as métricas e os avisos.

**02:53 · Aplicação — Consulta — buscar tema** — A página de Consulta pesquisa todo o acervo processado. Buscando por cibernético, encontramos as exclusões correspondentes em vários documentos, com a página de cada uma.

**03:05 · Aplicação — Consulta — pergunta com IA (LIVE)** — Também podemos perguntar em linguagem natural. Aqui, sobre dois contratos de D&O da mesma empresa, de 2020 e de 2025, a resposta traz o limite de cada contrato e os valores de pagamento, citando as páginas conferidas.


## 4. Principais resultados

**03:24 · Slide 8** — Nos resultados, avaliamos o sistema contra um gabarito anotado por especialista, com as apólices da Chubb e da Sompo. A extração acertou todos os campos anotados e citou a página correta em todas as evidências. A comparação atingiu 80% no gabarito original, e 100% no gabarito revisado, depois que confirmamos no texto duas diferenças apontadas pelo sistema.

**03:51 · Slide 10** — Também testamos a robustez: documentos de outros ramos, um arquivo de 254 páginas, e documentos digitalizados lidos por OCR. Todos os cenários passaram em todas as verificações.

**04:06 · Slide 11** — Em um estudo de caso real, o sistema acompanhou a mesma organização ao longo do tempo, identificando troca de seguradora, aumento de limite e mudança de valor, inclusive num contrato digitalizado.


## 5. Encerramento

**04:20 · Slide 12** — Ainda há limitações, como um gabarito pequeno e a variação entre execuções do modelo. Elas estão documentadas no relatório, junto com os próximos passos.

**04:32 · Slide 13** — O InsurMinds_PROTETOR lê, compara e explica. A decisão continua humana, agora com as evidências na mão. O código, o relatório e os dados estão no nosso repositório no GitHub. Obrigado!
