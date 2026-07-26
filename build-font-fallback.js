/**
 * ============================================================================
 * FONT FALLBACK COMPILER (build-font-fallback.js) — Precentor
 * ============================================================================
 * Reads the actual self-hosted webfont files under static/src/global/fonts/
 * and generates static/src/global/fonts-fallback.css: a metric-adjusted
 * local() @font-face for each webfont, so the browser's fallback (before
 * the webfont finishes loading, or if it never does) is sized and
 * positioned to match it almost exactly — eliminating the layout shift
 * (CLS) that a plain generic fallback (serif / sans-serif) would cause on
 * swap.
 *
 * DO NOT hand-edit fonts-fallback.css — it is regenerated every time this
 * runs. Edit FONT_STACKS below instead (or the font files themselves),
 * then:
 *
 *   node build-font-fallback.js
 *
 * No npm dependencies required — the WOFF2 table directory is parsed by
 * hand and decompressed with Node's built-in zlib.brotliDecompressSync.
 *
 * THE MATHS:
 * This reimplements the metric-override formula Next.js uses for
 * next/font's local font fallback (packages/next/src/server/font-utils.ts,
 * calculateSizeAdjustValues) — verified against its published source
 * rather than guessed:
 *
 *   sizeAdjust      = (webAvgWidth / webUnitsPerEm)
 *                      / (fallbackAvgWidth / fallbackUnitsPerEm)
 *   ascent-override  = |webAscent|  / (webUnitsPerEm * sizeAdjust)
 *   descent-override = |webDescent| / (webUnitsPerEm * sizeAdjust)
 *   line-gap-override= |webLineGap| / (webUnitsPerEm * sizeAdjust)
 *
 * sizeAdjust scales the fallback's glyphs to match the webfont's average
 * character width; the override values then re-express the webfont's own
 * vertical metrics as percentages of the *scaled* fallback, so ascent,
 * descent and line-gap line up too.
 * ============================================================================
 */

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const OUTPUT_PATH = path.join(
  __dirname,
  "static",
  "src",
  "global",
  "fonts-fallback.css",
);

// Which webfont file backs each token, and which local system font
// stands in for it before/without the webfont.
const FONT_STACKS = [
  {
    tokenName: "EB Garamond",
    fallbackName: "EB Garamond Fallback",
    webFontPath: path.join(
      __dirname,
      "static",
      "src",
      "global",
      "fonts",
      "eb-garamond",
      "eb-garamond-variable.woff2",
    ),
    localFont: "Georgia",
  },
  {
    tokenName: "Inter",
    fallbackName: "Inter Fallback",
    webFontPath: path.join(
      __dirname,
      "static",
      "src",
      "global",
      "fonts",
      "inter",
      "inter-variable.woff2",
    ),
    localFont: "Arial",
  },
];

// Hardcoded because these are read from the user's system,
// not the repo — and we can't read them from Node because Node
// doesn't have access to the user's system fonts. These are
// the same values Next.js uses for its local font fallback.
const FALLBACK_METRICS = {
  Georgia: { unitsPerEm: 2048, xAvgCharWidth: 901 },
  Arial: { unitsPerEm: 2048, xAvgCharWidth: 904 },
};

// ---------------------------------------------------------------------------
// sfnt table reading (shared by the plain-TTF and decompressed-WOFF2 paths)
// ---------------------------------------------------------------------------

function readMetricsFromTables(buf, tables) {
  const head = tables["head"].offset;
  const hhea = tables["hhea"].offset;
  const os2 = tables["OS/2"].offset;

  const unitsPerEm = buf.readUInt16BE(head + 18);
  const hheaLineGap = buf.readInt16BE(hhea + 8);

  const xAvgCharWidth = buf.readInt16BE(os2 + 2);
  const fsSelection = buf.readUInt16BE(os2 + 62);
  const sTypoAscender = buf.readInt16BE(os2 + 68);
  const sTypoDescender = buf.readInt16BE(os2 + 70);
  const sTypoLineGap = buf.readInt16BE(os2 + 72);
  const usWinAscent = buf.readUInt16BE(os2 + 74);
  const usWinDescent = buf.readUInt16BE(os2 + 76);

  // USE_TYPO_METRICS (fsSelection bit 7): when set, the font's own
  // designer-chosen typo metrics are authoritative; otherwise browsers
  // fall back to the Windows-ascent/descent/hhea-lineGap trio. Same
  // resolution rule browsers use for line-height, so matching it here
  // keeps the override values consistent with what actually renders.
  const useTypoMetrics = (fsSelection & 0x80) !== 0;

  return {
    unitsPerEm,
    xAvgCharWidth,
    ascent: useTypoMetrics ? sTypoAscender : usWinAscent,
    descent: useTypoMetrics ? sTypoDescender : -usWinDescent,
    lineGap: useTypoMetrics ? sTypoLineGap : hheaLineGap,
  };
}

// ---------------------------------------------------------------------------
// WOFF2 container: header + table directory + one brotli-compressed blob.
// Only tables relevant to metrics (head/hhea/OS-2) are ever read; glyf/
// loca/hmtx transforms are tracked just enough to compute byte offsets of
// the tables that come after them in the stream.
// ---------------------------------------------------------------------------

const WOFF2_KNOWN_TAGS = [
  "cmap",
  "head",
  "hhea",
  "hmtx",
  "maxp",
  "name",
  "OS/2",
  "post",
  "cvt ",
  "fpgm",
  "glyf",
  "loca",
  "prep",
  "CFF ",
  "VORG",
  "EBDT",
  "EBLC",
  "gasp",
  "hdmx",
  "kern",
  "LTSH",
  "PCLT",
  "VDMX",
  "vhea",
  "vmtx",
  "BASE",
  "GDEF",
  "GPOS",
  "GSUB",
  "EBSC",
  "JSTF",
  "MATH",
  "CBDT",
  "CBLC",
  "COLR",
  "CPAL",
  "SVG ",
  "sbix",
  "acnt",
  "avar",
  "bdat",
  "bloc",
  "bsln",
  "cvar",
  "fdsc",
  "feat",
  "fmtx",
  "fvar",
  "gvar",
  "hsty",
  "just",
  "lcar",
  "mort",
  "morx",
  "opbd",
  "prop",
  "trak",
  "Zapf",
  "Silf",
  "Glat",
  "Gloc",
  "Feat",
  "Sill",
]; // WOFF2 spec §6.1, knownTags — index doubles as the directory-entry tag id

function readUIntBase128(buf, pos) {
  let value = 0;
  let p = pos;
  for (let i = 0; i < 5; i++) {
    const b = buf[p];
    p += 1;
    if (i === 0 && b === 0x80) {
      throw new Error("UIntBase128: leading zero byte");
    }
    if (value & 0xfe000000) {
      throw new Error("UIntBase128: value overflows 32 bits");
    }
    value = (value << 7) | (b & 0x7f);
    if ((b & 0x80) === 0) return [value >>> 0, p];
  }
  throw new Error("UIntBase128: exceeds 5 bytes");
}

function readWoff2Metrics(fontPath) {
  const buf = fs.readFileSync(fontPath);
  if (buf.readUInt32BE(0) !== 0x774f4632) {
    throw new Error(`${fontPath} is not a WOFF2 file`);
  }
  const numTables = buf.readUInt16BE(12);
  const totalCompressedSize = buf.readUInt32BE(20);

  let p = 48; // fixed WOFF2 header is 48 bytes
  const entries = [];
  for (let i = 0; i < numTables; i++) {
    const flags = buf[p];
    p += 1;

    const tagIndex = flags & 0x3f;
    let tag;
    if (tagIndex === 0x3f) {
      tag = buf.toString("ascii", p, p + 4);
      p += 4;
    } else {
      tag = WOFF2_KNOWN_TAGS[tagIndex];
    }
    const transformVersion = (flags >> 6) & 0x3;

    let origLength;
    [origLength, p] = readUIntBase128(buf, p);

    // Only glyf/loca (version !== 3) and hmtx (version === 1) carry a
    // transform, and therefore a separate transformLength field.
    const hasTransform =
      tag === "glyf" || tag === "loca"
        ? transformVersion !== 3
        : tag === "hmtx" && transformVersion === 1;

    let streamLength = origLength;
    if (hasTransform) {
      [streamLength, p] = readUIntBase128(buf, p);
    }

    entries.push({ tag, origLength, streamLength });
  }

  // Table data is a single brotli stream starting right after the
  // directory, tables concatenated in directory order (WOFF2 spec §5.3).
  const compressed = buf.subarray(p, p + totalCompressedSize);
  const decompressed = zlib.brotliDecompressSync(compressed);

  const tables = {};
  let offset = 0;
  for (const entry of entries) {
    tables[entry.tag] = { offset, length: entry.origLength };
    offset += entry.streamLength;
  }

  return readMetricsFromTables(decompressed, tables);
}

// ---------------------------------------------------------------------------
// Metric-override maths (see module doc comment for the formula)
// ---------------------------------------------------------------------------

function formatPercent(value) {
  return `${Math.abs(value * 100).toFixed(2)}%`;
}

function calculateOverrides(webMetrics, fallbackMetrics) {
  const webAvgWidth = webMetrics.xAvgCharWidth / webMetrics.unitsPerEm;
  const fallbackAvgWidth =
    fallbackMetrics.xAvgCharWidth / fallbackMetrics.unitsPerEm;
  const sizeAdjust = webMetrics.xAvgCharWidth
    ? webAvgWidth / fallbackAvgWidth
    : 1;

  return {
    sizeAdjust: formatPercent(sizeAdjust),
    ascentOverride: formatPercent(
      webMetrics.ascent / (webMetrics.unitsPerEm * sizeAdjust),
    ),
    descentOverride: formatPercent(
      webMetrics.descent / (webMetrics.unitsPerEm * sizeAdjust),
    ),
    lineGapOverride: formatPercent(
      webMetrics.lineGap / (webMetrics.unitsPerEm * sizeAdjust),
    ),
  };
}

function build() {
  const blocks = FONT_STACKS.map((stack) => {
    const webMetrics = readWoff2Metrics(stack.webFontPath);
    const fallbackMetrics = FALLBACK_METRICS[stack.localFont];
    if (!fallbackMetrics) {
      throw new Error(
        `No hardcoded metrics for fallback font "${stack.localFont}"`,
      );
    }
    const overrides = calculateOverrides(webMetrics, fallbackMetrics);

    return (
      `  @font-face {\n` +
      `    font-family: "${stack.fallbackName}";\n` +
      `    src: local("${stack.localFont}");\n` +
      `    ascent-override: ${overrides.ascentOverride};\n` +
      `    descent-override: ${overrides.descentOverride};\n` +
      `    line-gap-override: ${overrides.lineGapOverride};\n` +
      `    size-adjust: ${overrides.sizeAdjust};\n` +
      `  }`
    );
  });

  const output =
    `/**\n` +
    ` * AUTO-GENERATED by build-font-fallback.js from the webfont files under\n` +
    ` * static/src/global/fonts/. Do not edit this file directly — your\n` +
    ` * changes will be overwritten.\n` +
    ` */\n\n` +
    `@layer global {\n${blocks.join("\n\n")}\n}\n`;

  fs.writeFileSync(OUTPUT_PATH, output, "utf8");
  console.log(
    `[build-font-fallback] wrote ${path.relative(__dirname, OUTPUT_PATH)}`,
  );
}

build();
