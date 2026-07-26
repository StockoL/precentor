# Precentor — Design System

This document covers the visual design system: how it's structured,
why it follows CUBE CSS, and the reasoning behind each layer. See the
main [README](../README.md) for domain/data decisions, and
[`docs/blocks_backlog.md`](blocks_backlog.md) for how each Block was
identified from real, observed repetition rather than guessed at.

## Methodology: CUBE CSS

CUBE CSS (Composition, Utility, Block, Exception — championed by Andy
Bell) organises styles into layers of increasing specificity and
decreasing reuse:

1. **Global** — tokens and base element styles (typography, reset).
2. **Composition** — aesthetics-agnostic layout primitives (spacing,
   wrapping, alignment). No colour or typographic opinions.
3. **Block** — genuine, repeated components with their own visual
   identity (badges, forms, the comment card).
4. **Utility** — small, single-purpose overrides.

Blocks were deliberately **not** built until every page had been swept
with Compositions first — this meant the eventual Block list (see
`blocks_backlog.md`) reflects real, repeated patterns actually observed
across the app, rather than components guessed at in the abstract
before any page existed.

## Cascade layers, not `@import`

`static/src/01-global/layers.css` (well — `src/global/layers.css` in
the actual folder naming used) declares:

```css
@layer reset, global, compositions, blocks, utilities;
```

Every other CSS file wraps its own rules in the matching `@layer { }`
block. Cascade priority is therefore determined by this declared order,
**not** by which order files happen to load in — which matters,
because every file is linked individually via a plain `<link>` tag in
`base.html`, not chained together with `@import`.

**Why not `@import`:** an early prototype (adapted from a toolkit
called `looseleaf-ui`) used `@import "..." layer(name);` to both import
and assign a layer in one line. This was dropped: `@import` chains are
sequential, render-blocking network requests — the browser can't
request the second file until the first has been fetched and parsed.
Plain `<link>` tags, in contrast, can all be requested in parallel
(especially efficiently under HTTP/2). The `@layer` mechanism gives the
same cascade guarantees without the performance cost.

**Why no JS bundler either:** a bundler (minification, single-file
output) was prototyped but deliberately not adopted for Precentor —
introducing Node/npm into an otherwise pure-Python Django project, for
a handful of small CSS files at this project's scale, was judged
unnecessary complexity for negligible real benefit. `variables.css`
(see below) is the one generated CSS artifact in the project, produced
by a small dependency-free Node script and committed like any other
build output.

## Design tokens

`precentor-tokens.json` (project root) is the single source of truth
for colour, typographic scale, spacing scale, layout constants, fonts,
and transition timings. `build-tokens.js` (also project root, run
locally via `node build-tokens.js`, no `npm install` required — only
Node's built-in `fs`/`path` modules) compiles it into
`static/src/global/variables.css`.

**Do not hand-edit `variables.css`** — it's fully regenerated from the
JSON every time the script runs, the same "generated artifact,
committed, never hand-edited" convention already used for Django
migrations.

### Scales

Type and space scales are fluid (via `clamp()`), generated with
[Utopia](https://utopia.fyi) — sized to smoothly interpolate between a
minimum and maximum viewport rather than jumping at fixed breakpoints.

### Colour

- A neutral grayscale ramp, with semantic tokens (`surface-*`,
  `text-*`, `border-*`) aliasing into it.
- A status trio system (`success`/`warning`/`danger`/`info`), each
  shipping a base + `-bg`/`-border`/`-text` variant, used by `badge.css`
  and `comment-card.css`.
- A `liturgical-*` set (`violet`/`red`/`green`/`white`/`rose`),
  matching `ordo.LiturgicalOccasion.colour`'s `choices` exactly — see
  "Liturgical accent" below.

## Fonts

Headings use **EB Garamond**, body text uses **Inter** — both
self-hosted (not the Google Fonts CDN), for performance (no
third-party DNS lookup/render-blocking request) and privacy (no
visitor IP sent to Google on every page load). Both are variable
fonts, so one file each covers their full weight range.

EB Garamond was chosen over an earlier candidate (Fraunces) — Fraunces
has a distinctive, quite trend-forward "warm/soft editorial"
character, judged a poor fit for a project rooted in centuries-old
liturgical tradition. EB Garamond is a faithful revival of Claude
Garamond's 16th-century type, genuinely contemporary with the
Reformation and early Anglican liturgy — a meaningful historical
resonance rather than a fashion-of-the-moment choice.

`build-font-fallback.js` generates a metric-matched fallback
`@font-face`, inserted between the real font and the generic system
fallback in the font stack (e.g. `"EB Garamond", "EB Garamond
Fallback", system-ui, serif`), mitigating the layout shift that occurs
when a fallback font swaps to the real typeface once it finishes
loading. `font-display: swap` on both real `@font-face` declarations
ensures text stays visible throughout, rather than the "flash of
invisible text."

## Liturgical accent

`badge.css` implements this project's status-indicator system:
`Service.status` and `RolePiece` confirmation state share the same
colour vocabulary (`success`/`warning`/`info`), applied as small inline
chips. `comment-card.css` uses the same tokens for `Comment.state`, but
as a card-level border/background accent rather than a chip — a
deliberate distinction, since a comment is a bigger unit of content
than a one-word status, even though both draw from the same palette.

`liturgical-accent.css` provides `.accent-bar` and `.occasion-dot`,
both reading a `--accent` custom property with a fallback to
`--colors-action-primary`. `service_detail.html` sets `--accent`
inline, directly from `service.occasion.colour` — this works with no
separate colour-mapping code at all, because `LiturgicalOccasion`'s
`COLOUR_CHOICES` values were deliberately chosen to match the
`liturgical-*` token names exactly.

**This is a contextual accent, not a global "today's date" theme** — a
deliberate, scoped-down version of an earlier, bigger idea. The full
version (the whole app's background reflecting the current liturgical
season on any given day) would require modelling season date-_ranges_
in `ordo`, not just point-in-time named occasions — a real, non-trivial
addition to a model layer otherwise considered finished. The contextual
version reuses data already in `Service.occasion`, costing nothing
extra to build, and is noted in the README as the deliberately chosen
scope.

## Folder structure

```
static/
├── src/
│   ├── global/
│   │   ├── layers.css        # @layer declaration order — link first
│   │   ├── variables.css     # generated by build-tokens.js
│   │   ├── fonts.css         # @font-face declarations
│   │   ├── fonts-fallback.css  # generated by build-font-fallback.js
│   │   ├── reset.css
│   │   └── global-styles.css
│   ├── compositions/
│   │   ├── center.css / cluster.css / flow.css / grid.css
│   │   ├── reel.css / sidebar.css / switcher.css / wrapper.css
│   │   └── cover.css          # added mid-project, not in the original
│   │                           # looseleaf-ui set — see below
│   ├── blocks/
│   │   ├── badge.css / comment-card.css / form.css / button.css
│   │   ├── nav.css / role-block.css / term-summary.css
│   │   ├── music-list.css / liturgical-accent.css
│   └── utilities/
│       └── utilities.css
└── fonts/
    ├── EBGaramond-Variable.woff2
    └── Inter-Variable.woff2
```

**`cover.css`** was added during the design pass, not part of the
original `looseleaf-ui` Composition set — needed to vertically centre
`login.html`'s form within the full page height, a genuinely different
axis of positioning than `.center` (which only handles the horizontal
width cap and centring). The two Compositions are meant to be used
together, not as alternatives.

## `music_list.html` — a deliberately different visual mode

The music list is meant to be read and printed, not navigated, so it
was given its own treatment rather than inheriting the app's nav/
Block styling wholesale:

- `@media print` and `@page` are declared **outside** every `@layer` —
  unlayered CSS always wins over any layered rule regardless of order
  or selector specificity, guaranteeing the site nav and the draft/
  public/print controls are hidden at print time with no risk of a
  layer-ordering mistake ever letting them through. No `!important`
  needed anywhere in the project — cascade layer order already
  provides the guarantee `!important` is usually reached for.
- On-screen, `.music-list` gives the page a document-like look (heading
  rules, a two-column `dl` grid for role→pieces, a warning-styled
  draft banner) distinct from the rest of the UI, so it reads as a
  real document even before printing.
- The page uses plain `.center` (not `.center[data-intrinsic]`, unlike
  `login.html`) — a document should stay left-aligned internally, only
  centred as a whole block on the page, unlike a small centred form
  where every child should align to the middle.
