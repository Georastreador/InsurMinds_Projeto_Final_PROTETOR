// Gera o relatório técnico em DOCX a partir do mesmo Markdown usado no PDF.
//
//   npm install docx@9
//   node Projeto_Final_Artefatos/build_relatorio_docx.js
//
// Suporta o subconjunto de Markdown do relatório: títulos (#, ##, ###), parágrafos com
// **negrito**, *itálico*, `código` e URLs, listas numeradas e com marcadores, tabelas e imagens.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, ImageRun, AlignmentType, LevelFormat, Footer, PageNumber,
  ExternalHyperlink,
} = require("docx");

const HERE = __dirname;
const SOURCE = path.join(HERE, "Relatorio_Tecnico_InsurMinds_PROTETOR.md");
const TARGET = path.join(HERE, "Relatorio_Tecnico_InsurMinds_PROTETOR.docx");

// A4 with 2 cm margins: content width 11906 - 2 * 1134 = 9638 DXA.
const PAGE = { width: 11906, height: 16838 };
const MARGIN = 1134;
const CONTENT_DXA = PAGE.width - 2 * MARGIN;
const BLUE = "0B3D62";
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "C9D1D9" };

// ---- inline formatting --------------------------------------------------------------
const TOKEN = /(\*\*[^*]+\*\*|`[^`]+`|(?<![\w*])\*[^*\s][^*]*\*(?![\w*])|(?<![\w])_[^_\s][^_]*_(?![\w])|https?:\/\/[^\s)|]+)/g;

function inline(text, base = {}) {
  const runs = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) runs.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) runs.push(new TextRun({ text: t.slice(1, -1), font: "Courier New", size: 18, ...base }));
    else if (t.startsWith("http")) runs.push(new ExternalHyperlink({ link: t, children: [new TextRun({ text: t, style: "Hyperlink", ...base })] }));
    else runs.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...base }));
  return runs;
}

// Paragraph lines joined by Markdown hard breaks ("  " at line end) become separate lines.
function paragraphFrom(lines, opts = {}) {
  const children = [];
  lines.forEach((line, i) => {
    const hard = /\s{2}$/.test(line);
    children.push(...inline(line.trim()));
    if (i < lines.length - 1) children.push(hard ? new TextRun({ break: 1 }) : new TextRun(" "));
  });
  return new Paragraph({ children, spacing: { after: 120 }, ...opts });
}

// ---- tables ---------------------------------------------------------------------------
function cellsOf(row) {
  return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

function tableFrom(rows) {
  const header = cellsOf(rows[0]);
  const body = rows.slice(2).map(cellsOf);
  const n = header.length;
  // Column widths proportional to content length, with a floor so short columns stay readable.
  const weights = header.map((h, i) => Math.max(8, ...[h, ...body.map((r) => r[i] || "")].map((c) => Math.min(c.length, 60))));
  const total = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map((w) => Math.floor((w / total) * CONTENT_DXA));
  widths[n - 1] += CONTENT_DXA - widths.reduce((a, b) => a + b, 0);

  const makeRow = (cells, isHeader) => new TableRow({
    tableHeader: isHeader,
    children: widths.map((w, i) => new TableCell({
      width: { size: w, type: WidthType.DXA },
      borders: { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER },
      shading: isHeader ? { fill: "E8EEF4", type: ShadingType.CLEAR, color: "auto" } : undefined,
      margins: { top: 60, bottom: 60, left: 90, right: 90 },
      children: [new Paragraph({ children: inline(cells[i] || "", { size: 18, bold: isHeader || undefined }) })],
    })),
  });
  return new Table({
    width: { size: CONTENT_DXA, type: WidthType.DXA },
    columnWidths: widths,
    rows: [makeRow(header, true), ...body.map((r) => makeRow(r, false))],
  });
}

// ---- document -------------------------------------------------------------------------
const lines = fs.readFileSync(SOURCE, "utf8").split("\n");
const children = [];
const numbering = [];
let listCounter = 0;
let i = 0;

while (i < lines.length) {
  const line = lines[i];
  if (!line.trim()) { i++; continue; }

  const heading = line.match(/^(#{1,3}) (.*)$/);
  if (heading) {
    const level = [HeadingLevel.TITLE, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2][heading[1].length - 1];
    children.push(new Paragraph({ heading: level, children: inline(heading[2]) }));
    i++; continue;
  }

  const image = line.match(/^!\[([^\]]*)\]\(([^)]+)\)/);
  if (image) {
    const data = fs.readFileSync(path.join(HERE, image[2]));
    const widthPx = Math.round((CONTENT_DXA / 1440) * 96);
    const heightPx = Math.round(widthPx * (data.readUInt32BE(20) / data.readUInt32BE(16))); // PNG IHDR
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: "png", data, transformation: { width: widthPx, height: heightPx },
                                altText: { title: image[1], description: image[1], name: image[1] } })],
    }));
    i++; continue;
  }

  if (line.startsWith("|")) {
    const rows = [];
    while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
    children.push(tableFrom(rows));
    children.push(new Paragraph({ children: [], spacing: { after: 60 } }));
    continue;
  }

  if (/^\d+\. /.test(line) || /^- /.test(line)) {
    const ordered = /^\d+\. /.test(line);
    const ref = `list-${listCounter++}`;
    numbering.push({
      reference: ref,
      levels: [{ level: 0, format: ordered ? LevelFormat.DECIMAL : LevelFormat.BULLET, text: ordered ? "%1." : "•",
                 alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }],
    });
    const pattern = ordered ? /^\d+\. / : /^- /;
    while (i < lines.length && pattern.test(lines[i])) {
      children.push(new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60 },
                                    children: inline(lines[i].replace(pattern, "")) }));
      i++;
    }
    continue;
  }

  const block = [];
  while (i < lines.length && lines[i].trim() && !/^(#{1,3} |!\[|\||\d+\. |- )/.test(lines[i])) block.push(lines[i++]);
  children.push(paragraphFrom(block));
}

const doc = new Document({
  creator: "Gp_Protetor",
  title: "InsurMinds_PROTETOR — Relatório Técnico",
  styles: {
    default: { document: { run: { font: "Arial", size: 21 } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal",
        run: { size: 36, bold: true, color: BLUE, font: "Arial" }, paragraph: { spacing: { after: 160 } } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, color: BLUE, font: "Arial" }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, color: BLUE, font: "Arial" }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: numbering },
  sections: [{
    properties: { page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new TextRun({ text: "InsurMinds_PROTETOR · Gp_Protetor · Página ", size: 16, color: "57606A" }),
        new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "57606A" }),
        new TextRun({ text: " de ", size: 16, color: "57606A" }),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "57606A" }),
      ] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(TARGET, buf);
  console.log(path.relative(path.dirname(HERE), TARGET));
});
