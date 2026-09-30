// Gera o pitch deck InsurMinds_Projeto_Final.pptx.
//
//   npm install pptxgenjs react react-dom react-icons sharp
//   node Projeto_Final_Artefatos/build_pitch_deck.js
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const HERE = __dirname;
const OUT = path.join(HERE, "InsurMinds_Projeto_Final.pptx");

// Palette: deep ink dominates, amber is the single sharp accent, violet marks generative AI
// (same convention as the architecture diagram in the technical report).
const INK = "14213D";
const INK2 = "22335A";
const ICE = "C9D6EA";
const AMBER = "E09F3E";
const VIOLET = "7B5EA7";
const VIOLET_BG = "EFE8F8";
const PANEL = "F2F5F9";
const TEXT = "1F2328";
const MUTED = "5B6573";
const WHITE = "FFFFFF";
const GREEN = "2E7D5B";
const HEAD = "Cambria";
const BODY = "Calibri";

const W = 13.333, H = 7.5, M = 0.6;

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

// Icon inside a filled circle: the deck's visual motif.
async function badge(slide, Comp, x, y, d, circle, glyph) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color: circle }, line: { color: circle } });
  const pad = d * 0.25;
  slide.addImage({ data: await icon(Comp, glyph), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad });
}

function title(slide, text, opts = {}) {
  slide.addText(text, { x: M, y: 0.45, w: W - 2 * M, h: 0.9, fontFace: HEAD, fontSize: 32, bold: true,
                        color: opts.color || INK, margin: 0, valign: "top", isTextBox: true });
}

function footer(slide, n, dark = false) {
  slide.addText(`InsurMinds_PROTETOR · Gp_Protetor · I2A2 2026`, { x: M, y: H - 0.45, w: 6, h: 0.3, fontFace: BODY,
    fontSize: 10, color: dark ? ICE : MUTED, margin: 0, isTextBox: true });
  slide.addText(String(n), { x: W - M - 1, y: H - 0.45, w: 1, h: 0.3, fontFace: BODY, fontSize: 10,
    color: dark ? ICE : MUTED, align: "right", margin: 0, isTextBox: true });
}

function card(slide, x, y, w, h, fill) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill },
    shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 } });
}

async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.author = "Gp_Protetor";
  pres.title = "InsurMinds_PROTETOR — Projeto Final I2A2";
  let n = 0;

  // 1 — Capa ---------------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    s.background = { color: INK };
    await badge(s, fa.FaShieldAlt, M, 1.0, 1.1, AMBER, INK);
    s.addText("InsurMinds_PROTETOR", { x: M, y: 2.35, w: 11.5, h: 1.0, fontFace: HEAD, fontSize: 48, bold: true,
      color: WHITE, margin: 0, isTextBox: true });
    s.addText("Análise e comparação de apólices D&O com IA generativa", { x: M, y: 3.35, w: 11.5, h: 0.6,
      fontFace: BODY, fontSize: 24, color: ICE, margin: 0, isTextBox: true });
    s.addText("Lê, compara e explica — com a página de cada evidência. A decisão continua humana.", {
      x: M, y: 4.05, w: 11.5, h: 0.5, fontFace: BODY, fontSize: 18, italic: true, color: AMBER, margin: 0, isTextBox: true });
    s.addText([
      { text: "Projeto Final · I2A2 — Instituto de Inteligência Artificial Aplicada · 2026", options: { breakLine: true } },
      { text: "Grupo Gp_Protetor: Ricardo Croce (Chefe), José Carlos dos Passos, Renato Sant Anna, Tiago Del Rio, Juliano Silva Ignacio" },
    ], { x: M, y: 5.6, w: 12, h: 0.8, fontFace: BODY, fontSize: 14, color: ICE, margin: 0, paraSpaceAfter: 4, isTextBox: true });
    s.addNotes("Apresentação do InsurMinds_PROTETOR, plataforma que lê, compara e explica apólices D&O com IA generativa. Mensagem central: o sistema automatiza a leitura e a comparação, mostra a página de cada evidência e deixa a decisão ao especialista.");
  }

  // 2 — Problema -----------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "O problema: comparar apólices D&O leva horas");
    s.addText([
      { text: "Documentos longos, em linguagem jurídica, com estrutura própria de cada seguradora.", options: { bullet: true, breakLine: true } },
      { text: "O mesmo conceito aparece com nomes diferentes — até em idiomas diferentes.", options: { bullet: true, breakLine: true } },
      { text: "Limites, franquias e vigência costumam estar na Especificação, não nas condições gerais.", options: { bullet: true, breakLine: true } },
      { text: "Cada afirmação precisa ser verificável no texto original.", options: { bullet: true } },
    ], { x: M, y: 1.7, w: 6.3, h: 3.6, fontFace: BODY, fontSize: 18, color: TEXT, paraSpaceAfter: 14, valign: "top", isTextBox: true });

    const stats = [
      ["49–254", "páginas nos documentos testados"],
      ["160", "coberturas, exclusões e cláusulas extraídas no par Chubb × Sompo"],
      ["horas", "de leitura especializada por comparação manual"],
    ];
    for (let i = 0; i < stats.length; i++) {
      const y = 1.6 + i * 1.65;
      card(s, 7.4, y, 5.33, 1.4, PANEL);
      s.addText(stats[i][0], { x: 7.65, y: y + 0.15, w: 2.2, h: 1.1, fontFace: HEAD, fontSize: 40, bold: true,
        color: AMBER, margin: 0, valign: "middle", isTextBox: true });
      s.addText(stats[i][1], { x: 9.9, y: y + 0.15, w: 2.65, h: 1.1, fontFace: BODY, fontSize: 15, color: TEXT,
        margin: 0, valign: "middle", isTextBox: true });
    }
    footer(s, n);
    s.addNotes("O desafio não é só ler: é alinhar conceitos entre seguradoras que usam nomes e estruturas diferentes, e manter cada conclusão rastreável. Os números vêm dos documentos usados no projeto: Chubb com 70 páginas, Sompo com 49 e Chubb PME com 254; no run de referência, o sistema extraiu 94 itens da Chubb e 66 da Sompo.");
  }

  // 3 — Solução ------------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "A solução: o PROTETOR lê, compara e explica");
    const cols = [
      [fa.FaFileAlt, "Lê", "PDF nativo, PDF digitalizado ou imagem. OCR com IA onde falta texto. Cada página marcada para citação."],
      [fa.FaBalanceScale, "Compara", "Pareia coberturas, exclusões e cláusulas por conceito D&O, mesmo com nomes e idiomas diferentes. A IA julga o conteúdo de cada par."],
      [fa.FaClipboardCheck, "Explica", "Síntese executiva com as diferenças mais relevantes e a página de cada uma. Sem dizer qual apólice é melhor."],
    ];
    const cw = 3.85, gap = 0.39;
    for (let i = 0; i < 3; i++) {
      const x = M + i * (cw + gap);
      card(s, x, 1.65, cw, 3.55, PANEL);
      await badge(s, cols[i][0], x + 0.35, 1.95, 0.85, INK, WHITE);
      s.addText(cols[i][1], { x: x + 0.35, y: 2.95, w: cw - 0.7, h: 0.55, fontFace: HEAD, fontSize: 24, bold: true,
        color: INK, margin: 0, isTextBox: true });
      s.addText(cols[i][2], { x: x + 0.35, y: 3.5, w: cw - 0.7, h: 1.6, fontFace: BODY, fontSize: 15, color: TEXT,
        margin: 0, valign: "top", isTextBox: true });
    }
    card(s, M, 5.55, W - 2 * M, 1.05, INK);
    s.addText([
      { text: "~3 min ", options: { bold: true, color: AMBER, fontSize: 26, fontFace: HEAD } },
      { text: "para comparar dois documentos de 50–70 páginas, com progresso por agente, downloads (MD, PDF, CSV) e consulta ao acervo.", options: { color: WHITE, fontSize: 16 } },
    ], { x: M + 0.35, y: 5.6, w: W - 2 * M - 0.7, h: 0.95, fontFace: BODY, valign: "middle", margin: 0, isTextBox: true });
    footer(s, n);
    s.addNotes("Três verbos resumem o produto. Ler: inclusive documentos digitalizados. Comparar: por conceito, não por nome. Explicar: síntese com evidência por página. O tempo de cerca de 3 minutos foi medido nos runs LIVE com Chubb × Sompo.");
  }

  // 4 — Arquitetura --------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Arquitetura: o Harness controla, os agentes executam");
    const imgH = 5.35, imgW = imgH * (2500 / 1650);
    s.addImage({ path: path.join(HERE, "arquitetura.png"), x: M, y: 1.45, w: imgW, h: imgH,
      altText: "Diagrama: upload, Harness com agentes A1 a A6, SQLite, OpenAI API e interface Streamlit" });
    const tx = M + imgW + 0.4, tw = W - M - tx;
    const points = [
      ["Máquina de estados", "Transições explícitas; nenhum agente decide a sequência."],
      ["Contratos tipados", "Pydantic entre agentes; adaptadores neutros de provedor."],
      ["IA onde agrega", "OCR, extração, julgamento, síntese e consulta (em lilás)."],
      ["Tudo auditável", "Trace por agente, SQLite e aba Auditoria da IA."],
    ];
    points.forEach(([h, d], i) => {
      s.addText([
        { text: h, options: { bold: true, color: INK, fontSize: 16, breakLine: true } },
        { text: d, options: { color: TEXT, fontSize: 13 } },
      ], { x: tx, y: 1.55 + i * 1.3, w: tw, h: 1.15, fontFace: BODY, margin: 0, valign: "top", isTextBox: true });
    });
    footer(s, n);
    s.addNotes("O princípio central: o Harness controla estados, retries, escopo e persistência; os agentes só executam a sua função. Isso torna o sistema previsível e testável sem API: são 98 testes automatizados. Os blocos em lilás usam IA generativa.");
  }

  // 5 — Agentes ------------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Sete agentes especializados, quatro com IA generativa");
    const agents = [
      [fa.FaInbox, "A1 Intake", "Valida formato, tamanho e metadados.", false],
      [fa.FaFileImage, "A2 Extraction", "Texto por página; OCR multimodal nos digitalizados.", true],
      [fa.FaSitemap, "A3 Análise D&O", "Preenche o PolicySchema com schema estrito e evidências.", true],
      [fa.FaCheckDouble, "A4 Validation", "Pydantic e guardrails; falha gera nova tentativa.", false],
      [fa.FaBalanceScale, "A5 Comparison", "Pareia por conceito D&O; a IA julga os pares.", true],
      [fa.FaFileSignature, "A6 Synthesis", "Síntese só com itens do A5; páginas anexadas.", true],
      [fa.FaSearch, "Consulta", "Busca no acervo e perguntas com citação de página.", true],
      [fa.FaCogs, "Harness", "Estados, retries, escopo, progresso e trace.", false],
    ];
    const cw = 2.85, ch = 2.35, gx = 0.19, gy = 0.3;
    for (let i = 0; i < agents.length; i++) {
      const [ic, name, desc, ai] = agents[i];
      const x = M + (i % 4) * (cw + gx), y = 1.55 + Math.floor(i / 4) * (ch + gy);
      card(s, x, y, cw, ch, ai ? VIOLET_BG : PANEL);
      await badge(s, ic, x + 0.25, y + 0.25, 0.7, ai ? VIOLET : INK, WHITE);
      if (ai) s.addText("IA generativa", { x: x + 1.05, y: y + 0.4, w: 1.6, h: 0.35, fontFace: BODY, fontSize: 11,
        bold: true, color: VIOLET, margin: 0, isTextBox: true });
      s.addText(name, { x: x + 0.25, y: y + 1.05, w: cw - 0.5, h: 0.4, fontFace: HEAD, fontSize: 17, bold: true,
        color: INK, margin: 0, isTextBox: true });
      s.addText(desc, { x: x + 0.25, y: y + 1.45, w: cw - 0.5, h: 0.8, fontFace: BODY, fontSize: 13, color: TEXT,
        margin: 0, valign: "top", isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Cada agente tem entrada e saída tipadas. Quatro etapas do fluxo usam IA generativa (A2 no OCR, A3, A5 e A6), além da Consulta. Todas passam por contratos Pydantic e guardrails no código.");
  }

  // 6 — IA sob controle ----------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "IA generativa sob controle: guardrails no código");
    const rows = [
      [fa.FaLock, "Schema estrito", "O modelo responde no formato do PolicySchema; o A4 valida e é a autoridade final."],
      [fa.FaRedo, "Nova tentativa com os erros", "Se a validação falha, o A3 recebe a lista de erros e tenta de novo (até 2×)."],
      [fa.FaQuoteRight, "Evidência por página", "Cada afirmação cita página e trecho; citações fora das páginas lidas são descartadas."],
      [fa.FaBan, "Sem veredito", "\"Melhor\", \"pior\" e \"recomendada\" são bloqueados em A5, A6 e Consulta."],
      [fa.FaFlag, "Escopo sinalizado", "Fora de D&O, a análise é marcada como genérica; páginas omitidas são sempre avisadas."],
    ];
    for (let i = 0; i < rows.length; i++) {
      const y = 1.55 + i * 1.02;
      await badge(s, rows[i][0], M, y, 0.72, AMBER, INK);
      s.addText([
        { text: rows[i][1], options: { bold: true, color: INK, fontSize: 17, breakLine: true } },
        { text: rows[i][2], options: { color: TEXT, fontSize: 14 } },
      ], { x: M + 0.95, y: y - 0.05, w: 7.2, h: 0.9, fontFace: BODY, margin: 0, valign: "middle", isTextBox: true });
    }
    card(s, 9.05, 1.55, 3.68, 4.95, INK);
    s.addText([
      { text: "Exemplo real", options: { bold: true, color: AMBER, fontSize: 14, breakLine: true } },
      { text: "O modelo escreveu \"5% do LMI\" num campo numérico.", options: { color: WHITE, fontSize: 15, breakLine: true } },
      { text: " ", options: { fontSize: 8, breakLine: true } },
      { text: "O A4 rejeitou, devolveu o erro ao A3 e a segunda tentativa foi aceita — sem intervenção humana e registrado no trace.", options: { color: ICE, fontSize: 15 } },
    ], { x: 9.35, y: 1.8, w: 3.1, h: 4.4, fontFace: BODY, margin: 0, valign: "top", isTextBox: true });
    footer(s, n);
    s.addNotes("A confiança vem do código, não só do prompt. O exemplo à direita aconteceu num run LIVE com a Chubb PME: o ciclo de validação e nova tentativa corrigiu o valor sozinho.");
  }

  // 7 — Experiência ------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "A experiência do analista, do upload à consulta");
    const steps = [
      ["Upload", "PDF ou imagem; a tela mostra páginas, tamanho e tempo estimado."],
      ["Progresso", "Cada agente aparece em tempo real, com estimativa por etapa."],
      ["Resumo", "Síntese executiva com páginas; download em MD e PDF."],
      ["Evidências", "Trecho de A e de B lado a lado, com página, para cada diferença."],
      ["Consulta", "Busca de temas no acervo e perguntas com resposta citada."],
    ];
    const sw = 2.2, gap = 0.33;
    for (let i = 0; i < steps.length; i++) {
      const x = M + i * (sw + gap);
      s.addShape("ellipse", { x: x + sw / 2 - 0.45, y: 1.9, w: 0.9, h: 0.9, fill: { color: i === 2 ? AMBER : INK }, line: { color: i === 2 ? AMBER : INK } });
      s.addText(String(i + 1), { x: x + sw / 2 - 0.45, y: 1.9, w: 0.9, h: 0.9, fontFace: HEAD, fontSize: 26, bold: true,
        color: i === 2 ? INK : WHITE, align: "center", valign: "middle", margin: 0, isTextBox: true });
      if (i < steps.length - 1) s.addShape("line", { x: x + sw / 2 + 0.5, y: 2.35, w: sw + gap - 1.0, h: 0,
        line: { color: MUTED, width: 1.5, endArrowType: "triangle" } });
      s.addText(steps[i][0], { x, y: 3.0, w: sw, h: 0.45, fontFace: HEAD, fontSize: 19, bold: true, color: INK,
        align: "center", margin: 0, isTextBox: true });
      s.addText(steps[i][1], { x, y: 3.5, w: sw, h: 1.3, fontFace: BODY, fontSize: 14, color: TEXT, align: "center",
        margin: 0, valign: "top", isTextBox: true });
    }
    card(s, M, 5.25, W - 2 * M, 1.25, PANEL);
    await badge(s, fa.FaPlayCircle, M + 0.3, 5.47, 0.8, VIOLET, WHITE);
    s.addText([
      { text: "Modo apresentação: ", options: { bold: true, color: INK } },
      { text: "reabre runs LIVE gravados sem chamar a API — a demonstração não depende de rede. Abas separam a experiência do analista da Auditoria da IA (trace, métricas, JSON).", options: { color: TEXT } },
    ], { x: M + 1.35, y: 5.3, w: W - 2 * M - 1.65, h: 1.15, fontFace: BODY, fontSize: 15, valign: "middle", margin: 0, isTextBox: true });
    footer(s, n);
    s.addNotes("Aqui entra a demonstração ao vivo ou o vídeo. Sugestão de roteiro: abrir o run Chubb × Sompo pelo modo apresentação, mostrar a síntese, abrir uma evidência e fazer uma pergunta na Consulta.");
  }

  // 8 — Resultados (Golden) ----------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Resultados no Golden Dataset D&O (Chubb × Sompo)");
    s.addChart(pres.charts.BAR, [{
      name: "Resultado",
      labels: ["Schema válido", "Campos corretos", "Evidência na página", "Comparação (gab. v1.0)", "Comparação (gab. v1.1)", "Proxy de alucinação"],
      values: [1.0, 1.0, 1.0, 0.8, 1.0, 1.0],
    }], {
      x: M, y: 1.45, w: 7.6, h: 5.1, barDir: "bar", chartColors: [INK, INK, INK, AMBER, INK, INK],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", dataLabelFontSize: 12,
      dataLabelColor: TEXT, catAxisLabelColor: TEXT, catAxisLabelFontSize: 12, valAxisHidden: true,
      valAxisMinVal: 0, valAxisMaxVal: 1.15, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showLegend: false, showTitle: true, title: "EVAL-01 a EVAL-05 (1,00 = 100%)", titleFontSize: 14,
      titleColor: INK, catAxisOrientation: "maxMin", barGapWidthPct: 60,
    });
    const facts = [
      ["12/12 · 11/11", "campos anotados extraídos corretamente (Chubb · Sompo)"],
      ["6/6 · 5/5", "evidências citando a página anotada pelo especialista"],
      ["0,80 → 1,00", "comparação: divergências da v1.0 confirmadas no texto e revisadas na v1.1"],
    ];
    facts.forEach(([big, small], i) => {
      const y = 1.55 + i * 1.6;
      card(s, 8.6, y, 4.13, 1.35, PANEL);
      s.addText([
        { text: big, options: { bold: true, color: INK, fontSize: 26, fontFace: HEAD, breakLine: true } },
        { text: small, options: { color: TEXT, fontSize: 13 } },
      ], { x: 8.85, y: y + 0.1, w: 3.7, h: 1.15, fontFace: BODY, margin: 0, valign: "middle", isTextBox: true });
    });
    s.addText("Amostra pequena (2 documentos, 10 itens de comparação); as duas versões do gabarito são reportadas.", {
      x: M, y: 6.6, w: W - 2 * M, h: 0.35, fontFace: BODY, fontSize: 11, italic: true, color: MUTED, margin: 0, isTextBox: true });
    footer(s, n);
    s.addNotes("Os campos que as condições gerais delegam à Especificação ficaram vazios, como no gabarito: o modelo não inventou valores. Na comparação, a v1.0 anotava exclusões pela presença do tema; o sistema apontou diferenças de alcance (ambiental e cibernética), que o grupo conferiu nas páginas 42, 51–55, 65 e 17. O gabarito v1.1 registra isso, e mostramos as duas versões.");
  }

  // 9 — Evolução -----------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Decisões que mudaram o resultado");
    const pairs = [
      ["Extração LIVE", "22 erros", "de schema no 1º teste", "1ª tentativa", "aceita com schema estrito"],
      ["Comparação", "0,50", "pareando pelo nome dado pelo LLM", "0,80", "com taxonomia D&O + juiz semântico"],
      ["Síntese", "87 mil", "caracteres, texto técnico", "~5 mil", "caracteres, gerada por IA com páginas"],
    ];
    for (let i = 0; i < pairs.length; i++) {
      const y = 1.6 + i * 1.65;
      s.addText(pairs[i][0], { x: M, y, w: 2.4, h: 1.35, fontFace: HEAD, fontSize: 20, bold: true, color: INK,
        valign: "middle", margin: 0, isTextBox: true });
      card(s, 3.1, y, 4.1, 1.35, PANEL);
      s.addText([
        { text: pairs[i][1], options: { bold: true, fontSize: 30, color: MUTED, fontFace: HEAD, breakLine: true } },
        { text: pairs[i][2], options: { fontSize: 13, color: MUTED } },
      ], { x: 3.35, y: y + 0.08, w: 3.7, h: 1.2, fontFace: BODY, valign: "middle", margin: 0, isTextBox: true });
      s.addImage({ data: await icon(fa.FaArrowRight, AMBER), x: 7.45, y: y + 0.45, w: 0.45, h: 0.45 });
      card(s, 8.15, y, 4.58, 1.35, INK);
      s.addText([
        { text: pairs[i][3], options: { bold: true, fontSize: 30, color: AMBER, fontFace: HEAD, breakLine: true } },
        { text: pairs[i][4], options: { fontSize: 13, color: WHITE } },
      ], { x: 8.4, y: y + 0.08, w: 4.15, h: 1.2, fontFace: BODY, valign: "middle", margin: 0, isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Cada decisão arquitetural foi motivada por um problema medido. O schema estrito eliminou os erros de formato; a taxonomia resolveu o fato de a Chubb vir em inglês e a Sompo em português; a síntese generativa, limitada aos itens do A5, ficou curta e verificável.");
  }

  // 10 — Robustez e OCR --------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Robustez: outros ramos, 254 páginas e OCR");
    const head = (t) => ({ text: t, options: { bold: true, color: WHITE, fill: { color: INK }, fontSize: 14 } });
    const rows = [
      [head("Cenário LIVE"), head("Verificações"), head("Tempo")],
      ["Empresarial PME (254 págs.) × Residencial — limite de tamanho, ramos diferentes", "8/8", "3 min 05 s"],
      ["Residencial × apólice sintética — limites e franquias em R$ contra gabarito", "19/19", "2 min 17 s"],
      ["Seguro Garantia × Vida — controle negativo de escopo", "7/7", "1 min 43 s"],
      ["PDF só imagem × PDF nativo da mesma apólice — OCR", "33/33", "1 min 40 s"],
      ["Imagem PNG × PDF nativo — OCR de imagem", "aprovado", "57 s"],
    ].map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: { fontSize: 14, color: j === 1 ? GREEN : TEXT,
      bold: j === 1, fill: { color: i % 2 ? WHITE : PANEL } } })));
    s.addTable(rows, { x: M, y: 1.55, w: W - 2 * M, colW: [8.35, 1.9, 1.88], rowH: 0.62, fontFace: BODY,
      border: { type: "solid", pt: 0.75, color: "D0D7DE" }, valign: "middle", margin: 0.1 });
    await badge(s, fa.FaCheckCircle, M, 5.75, 0.7, GREEN, WHITE);
    s.addText("Todos os cenários terminaram sem falha. Fora de D&O, o sistema sinaliza escopo genérico; acima de 300 mil caracteres, declara as páginas omitidas.", {
      x: M + 0.95, y: 5.7, w: W - 2 * M - 0.95, h: 0.8, fontFace: BODY, fontSize: 15, color: TEXT, valign: "middle", margin: 0, isTextBox: true });
    footer(s, n);
    s.addNotes("Os testes de robustez usam documentos de outros ramos e uma apólice sintética com gabarito de valores, porque as condições gerais D&O não têm limites em reais. O OCR foi testado gerando uma versão só imagem da mesma apólice: identificação, vigência, limites e franquias bateram com a versão nativa.");
  }

  // 11 — Estudo de caso ---------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "Estudo de caso: a mesma organização ao longo do tempo");
    const panels = [
      ["PRODEMGE · contratos de D&O", "2020 (digitalizado) × 2025", [
        ["Seguradora", "Ezze → Austral"],
        ["Limite máximo", "R$ 30 mi → R$ 40 mi"],
        ["Valor do contrato", "R$ 74 mil → R$ 35 mil"],
        ["OCR", "15 páginas em 1 min 28 s"],
      ], "Valores conferidos nos documentos originais."],
      ["Invepar · demonstrações financeiras", "DFP 2024 × ITR 2025", [
        ["Seguradora D&O", "Allianz → Berkley"],
        ["Limite", "R$ 100 mi mantido"],
        ["Achado", "tabela × nota divergem na DFP 2024"],
        ["Limitação", "valores em R$ mil não convertidos"],
      ], "Evidência secundária: bom teste de sensibilidade e de limites."],
    ];
    const pw = 5.85;
    for (let i = 0; i < 2; i++) {
      const x = M + i * (pw + 0.43);
      card(s, x, 1.55, pw, 5.0, PANEL);
      await badge(s, i === 0 ? fa.FaFileContract : fa.FaChartLine, x + 0.3, 1.8, 0.75, INK, WHITE);
      s.addText([
        { text: panels[i][0], options: { bold: true, fontSize: 18, color: INK, fontFace: HEAD, breakLine: true } },
        { text: panels[i][1], options: { fontSize: 13, color: MUTED } },
      ], { x: x + 1.25, y: 1.78, w: pw - 1.5, h: 0.85, fontFace: BODY, margin: 0, valign: "middle", isTextBox: true });
      panels[i][2].forEach(([k, v], j) => {
        const y = 2.95 + j * 0.72;
        s.addText(k, { x: x + 0.3, y, w: 1.9, h: 0.55, fontFace: BODY, fontSize: 14, color: MUTED, margin: 0, valign: "middle", isTextBox: true });
        s.addText(v, { x: x + 2.2, y, w: pw - 2.5, h: 0.55, fontFace: BODY, fontSize: 16, bold: true, color: INK, margin: 0, valign: "middle", isTextBox: true });
      });
      s.addText(panels[i][3], { x: x + 0.3, y: 5.9, w: pw - 0.6, h: 0.5, fontFace: BODY, fontSize: 13, italic: true,
        color: MUTED, margin: 0, isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Na PRODEMGE, o sistema leu um contrato de 2020 que era só imagem e identificou a troca de seguradora, o aumento do limite e a mudança de valor. Na Invepar, captou a troca Allianz → Berkley nas demonstrações e expôs uma divergência entre a tabela e a nota de rodapé da própria DFP 2024 — e também as limitações do schema com documentos que listam várias apólices.");
  }

  // 12 — Limitações e próximos passos ------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    title(s, "O que ainda não resolvemos — e para onde evoluir");
    const cols = [
      [fa.FaExclamationTriangle, "Limitações conhecidas", AMBER, [
        "Golden Dataset pequeno: 2 documentos anotados.",
        "O LLM varia entre execuções (quantidade de itens).",
        "Um documento = uma apólice; unidades em R$ mil.",
        "Acima de 300 mil caracteres, há omissão (avisada).",
        "No modo LIVE, os documentos vão para a API.",
      ]],
      [fa.FaRoute, "Próximos passos", VIOLET, [
        "Ampliar o gabarito (Fator, AXA e HDI já catalogados).",
        "Unir condições gerais e Especificação da mesma apólice.",
        "Documentos com várias apólices e normalização de unidades.",
        "Busca semântica no acervo e comparação de N apólices.",
        "Feedback do especialista realimentando o gabarito.",
      ]],
    ];
    const pw = 5.85;
    for (let i = 0; i < 2; i++) {
      const x = M + i * (pw + 0.43);
      card(s, x, 1.55, pw, 5.0, i === 0 ? PANEL : VIOLET_BG);
      await badge(s, cols[i][0], x + 0.3, 1.8, 0.75, cols[i][2], i === 0 ? INK : WHITE);
      s.addText(cols[i][1], { x: x + 1.25, y: 1.8, w: pw - 1.5, h: 0.75, fontFace: HEAD, fontSize: 20, bold: true,
        color: INK, margin: 0, valign: "middle", isTextBox: true });
      s.addText(cols[i][3].map((t, j, a) => ({ text: t, options: { bullet: true, breakLine: j < a.length - 1 } })), {
        x: x + 0.3, y: 2.8, w: pw - 0.6, h: 3.5, fontFace: BODY, fontSize: 15, color: TEXT, paraSpaceAfter: 10,
        valign: "top", isTextBox: true });
    }
    footer(s, n);
    s.addNotes("Transparência sobre limites é parte da proposta: cada limitação aparece em aviso na própria interface. Os próximos passos atacam diretamente essas limitações.");
  }

  // 13 — Encerramento ------------------------------------------------------------------
  {
    const s = pres.addSlide(); n++;
    s.background = { color: INK };
    await badge(s, fa.FaShieldAlt, M, 1.0, 1.0, AMBER, INK);
    s.addText("O PROTETOR lê, compara e explica.", { x: M, y: 2.2, w: 12, h: 0.9, fontFace: HEAD, fontSize: 40,
      bold: true, color: WHITE, margin: 0, isTextBox: true });
    s.addText("A decisão continua humana — agora com as evidências na mão.", { x: M, y: 3.1, w: 12, h: 0.6,
      fontFace: BODY, fontSize: 22, italic: true, color: AMBER, margin: 0, isTextBox: true });
    s.addImage({ data: await icon(fa.FaGithub, ICE), x: M, y: 4.35, w: 0.45, h: 0.45 });
    s.addText("github.com/Georastreador/InsurMinds_Projeto_Final_PROTETOR", { x: M + 0.6, y: 4.35, w: 11, h: 0.45,
      fontFace: BODY, fontSize: 18, color: WHITE, margin: 0, valign: "middle", isTextBox: true,
      hyperlink: { url: "https://github.com/Georastreador/InsurMinds_Projeto_Final_PROTETOR" } });
    s.addText([
      { text: "Gp_Protetor", options: { bold: true, color: WHITE, breakLine: true } },
      { text: "Ricardo Croce · José Carlos dos Passos · Renato Sant Anna · Tiago Del Rio · Juliano Silva Ignacio", options: { color: ICE } },
    ], { x: M, y: 5.4, w: 12, h: 0.8, fontFace: BODY, fontSize: 15, margin: 0, isTextBox: true });
    s.addText("Obrigado!", { x: W - M - 3, y: 6.35, w: 3, h: 0.5, fontFace: HEAD, fontSize: 22, bold: true, color: AMBER,
      align: "right", margin: 0, isTextBox: true });
    s.addNotes("Fechamento: reforçar a mensagem central e o link do repositório, que tem README, relatório técnico, testes e os datasets com fontes.");
  }

  await pres.writeFile({ fileName: OUT });
  console.log(path.relative(path.dirname(HERE), OUT));
}

build();
