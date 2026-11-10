/**
 * ============================================================================
 * FONT FALLBACK COMPILER (build-font-fallback.js) for Precentor
 * ============================================================================
 * Reads the actual self-hosted webfont files under static/src/global/fonts/
 * and generates static/src/global/fonts-fallback.css: a metric-adjusted
 * local() @font-face for each webfont, so the browser's fallback (before
 * the webfont finishes loading, or if it never does) is sized and
 * positioned to match it almost exactly, eliminating the layout shift
 * (CLS) that a plain generic fallback (serif / sans-serif) would cause on
 * swap.
 *
 * DO NOT hand-edit fonts-fallback.css: it is regenerated every time this
 * runs. Edit FONT_STACKS below instead (or the font files themselves),
 * then:
 *
 *   node build-font-fallback.js
 *
 * No npm dependencies required: the WOFF2 table directory is parsed by
 * hand and decompressed with Node's built-in zlib.brotliDecompressSync.
 *
 * THE MATHS:
 * This reimplements the metric-override formula Next.js uses for
 * next/font's local font fallback (packages/next/src/server/font-utils.ts,
 * calculateSizeAdjustValues), checked against its published source
 * rather than guessed:
 *
 *   sizeAdjust      = (webAvgWidth / webUnitsPerEm)
 *                      / (fallbackAvgWidth / fallbackUnitsPerEm)
 *
 * Both average widths must be measured the same way. Each is the mean
 * advance width of the characters in SAMPLE_TEXT, ordinary English, so
 * letters count as often as they're read. (The OS/2 table's
 * xAvgCharWidth won't do: in modern fonts it averages every glyph,
 * ligatures and symbols included, which made both fallbacks about a
 * third wider than the fonts they stand in for.)
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

// The system fonts aren't in the repository, so their average widths
// are written here. They were measured with this script from Windows
// 11's own files, by the same SAMPLE_TEXT as the webfonts:
//   node build-font-fallback.js --measure C:\Windows\Fonts\georgia.ttf
const FALLBACK_METRICS = {
  Georgia: { unitsPerEm: 2048, averageWidth: 897.1 },
  Arial: { unitsPerEm: 2048, averageWidth: 900.1 },
};

// Ordinary English with a few capitals and figures, for averaging
// character widths as they're met in reading.
const SAMPLE_TEXT =
  "The choir sings at the Sunday Mass and at Vespers in the evening. " +
  "Each term the conductor plans the music for every service, and the " +
  "librarian finds the copies, counts them and files them again after " +
  "use. A motet by Byrd or Victoria, a hymn from the book, and a psalm " +
  "with its antiphon: the list for 29 November is printed by Friday.";

// ---------------------------------------------------------------------------
// sfnt table reading (shared by the plain-TTF and decompressed-WOFF2 paths)
// ---------------------------------------------------------------------------

function readMetricsFromTables(buf, tables) {
  const head = tables["head"].offset;
  const hhea = tables["hhea"].offset;
  const os2 = tables["OS/2"].offset;

  const unitsPerEm = buf.readUInt16BE(head + 18);
  const hheaLineGap = buf.readInt16BE(hhea + 8);

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
    averageWidth: averageWidth(buf, tables),
    ascent: useTypoMetrics ? sTypoAscender : usWinAscent,
    descent: useTypoMetrics ? sTypoDescender : -usWinDescent,
    lineGap: useTypoMetrics ? sTypoLineGap : hheaLineGap,
  };
}

// The glyph a character is drawn with, from the cmap table's Windows
// Unicode subtable: format 12 (full Unicode) if the font has one, else
// format 4 (the Basic Multilingual Plane). 0 means the font lacks it.
function glyphLookup(buf, tables) {
  const cmap = tables["cmap"].offset;
  const subtables = {};
  for (let i = 0; i < buf.readUInt16BE(cmap + 2); i++) {
    const record = cmap + 4 + i * 8;
    const key = `${buf.readUInt16BE(record)}.${buf.readUInt16BE(record + 2)}`;
    subtables[key] = cmap + buf.readUInt32BE(record + 4);
  }
  const format12 = subtables["3.10"];
  if (format12 !== undefined && buf.readUInt16BE(format12) === 12) {
    const groups = buf.readUInt32BE(format12 + 12);
    return (code) => {
      for (let i = 0; i < groups; i++) {
        const group = format12 + 16 + i * 12;
        const start = buf.readUInt32BE(group);
        if (code >= start && code <= buf.readUInt32BE(group + 4)) {
          return buf.readUInt32BE(group + 8) + (code - start);
        }
      }
      return 0;
    };
  }
  const table = subtables["3.1"];
  const segments = buf.readUInt16BE(table + 6) / 2;
  const ends = table + 14;
  const starts = ends + segments * 2 + 2;
  const deltas = starts + segments * 2;
  const rangeOffsets = deltas + segments * 2;
  return (code) => {
    for (let i = 0; i < segments; i++) {
      if (code > buf.readUInt16BE(ends + i * 2)) continue;
      const start = buf.readUInt16BE(starts + i * 2);
      if (code < start) return 0;
      const delta = buf.readInt16BE(deltas + i * 2);
      const rangeOffset = buf.readUInt16BE(rangeOffsets + i * 2);
      if (rangeOffset === 0) return (code + delta) & 0xffff;
      const glyph = buf.readUInt16BE(rangeOffsets + i * 2 + rangeOffset + (code - start) * 2);
      return glyph === 0 ? 0 : (glyph + delta) & 0xffff;
    }
    return 0;
  };
}

// The mean advance width of SAMPLE_TEXT's characters, in font units, from
// the hmtx table (glyphs past numberOfHMetrics share the last width).
function averageWidth(buf, tables) {
  const glyphFor = glyphLookup(buf, tables);
  const hmtx = tables["hmtx"].offset;
  const metricsCount = buf.readUInt16BE(tables["hhea"].offset + 34);
  let total = 0;
  for (const character of SAMPLE_TEXT) {
    const glyph = Math.min(glyphFor(character.codePointAt(0)), metricsCount - 1);
    total += buf.readUInt16BE(hmtx + glyph * 4);
  }
  return total / [...SAMPLE_TEXT].length;
}

// A plain TrueType file's table directory, for --measure.
function readTtfMetrics(fontPath) {
  const buf = fs.readFileSync(fontPath);
  const tables = {};
  for (let i = 0; i < buf.readUInt16BE(4); i++) {
    const record = 12 + i * 16;
    tables[buf.toString("ascii", record, record + 4)] = {
      offset: buf.readUInt32BE(record + 8),
      length: buf.readUInt32BE(record + 12),
    };
  }
  return readMetricsFromTables(buf, tables);
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
]; // WOFF2 spec §6.1, knownTags; the index doubles as the directory-entry tag id

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
  const webAvgWidth = webMetrics.averageWidth / webMetrics.unitsPerEm;
  const fallbackAvgWidth =
    fallbackMetrics.averageWidth / fallbackMetrics.unitsPerEm;
  const sizeAdjust = webAvgWidth / fallbackAvgWidth;

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
    ` * static/src/global/fonts/. Do not edit this file directly; your\n` +
    ` * changes will be overwritten.\n` +
    ` */\n\n` +
    `@layer global {\n${blocks.join("\n\n")}\n}\n`;

  fs.writeFileSync(OUTPUT_PATH, output, "utf8");
  console.log(
    `[build-font-fallback] wrote ${path.relative(__dirname, OUTPUT_PATH)}`,
  );
}

if (process.argv[2] === "--measure") {
  const metrics = readTtfMetrics(process.argv[3]);
  console.log(
    `unitsPerEm: ${metrics.unitsPerEm}, averageWidth: ${metrics.averageWidth.toFixed(1)}`,
  );
} else {
  build();
}
