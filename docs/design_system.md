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

**Type scale:** viewport 360px to 1280px, base 16px to 18px, ratio
1.125 to 1.2, steps -2 to 5. Body text is 16px on a phone and 18px on
a desktop. I revised this in October 2026 from a 16px to 20px base
with a 1.2 to 1.25 ratio: 20px body text suits a reading app more than
a dense planning tool, and the steeper ratio made an `h2` around 39px
on a desktop. 16px is kept as the floor because iOS zooms the page when
a form control's text is smaller than that.

**Space scale:** the same viewport and the same 16px to 18px base,
with Utopia's multipliers (`3xs` 0.25 up to `3xl` 6). Sharing the type
scale's base means padding grows in step with the text instead of
outgrowing it.

**Sizes by role, not by tag:**

| Role | Token | About |
| --- | --- | --- |
| Page title (`h1`) | `step-4` | 26px to 37px |
| Section heading (`h2`) | `step-2` | 20px to 26px |
| Card or sub-heading (`h3`) | `step-1` | 18px to 22px |
| Body text, `h4` | `step-0` | 16px to 18px |
| Buttons, nav | `step--1` | 14px to 15px |
| Inputs | `max(1rem, step--1)` | 16px |
| Badges, help text | `step--2` | 12.5px |

Controls sit a step below body text so they don't compete with the
content around them. Inputs are held at 16px for the iOS reason
above. Error messages stay at `step--1`, because they have to be read
rather than skimmed.

Body text is sized on `body`, never on `html`. Every `rem` is
measured from the root element, so a fluid size there would quietly
rescale every token in the system. I made exactly that mistake once,
and on a desktop every rem became 18px; a browser test now checks the
root stays at the browser's default.

**Control height:** `--layout-control-height` (2.5rem, so 40px) is the
minimum height of buttons, text inputs and selects, with their
vertical padding removed, so a field and the button beside it line
up. It's a minimum rather than a fixed height, so a button whose label
wraps can still grow. Textareas, checkboxes and radios keep their
natural size.

### Colour

- A neutral grayscale ramp, with semantic tokens (`surface-*`,
  `text-*`, `border-*`) aliasing into it.
- A status trio system (`success`/`warning`/`danger`/`info`), each
  shipping a base + `-bg`/`-border`/`-text` variant, used by `badge.css`
  and `comment-card.css`. An `inactive` trio follows the same pattern
  for things with nothing active on them: a service not started, a
  closed comment.
- A `liturgical-*` set (`violet`/`red`/`green`/`white`/`rose`),
  matching `ordo.LiturgicalOccasion.colour`'s `choices` exactly — see
  "Liturgical accent" below.

### Dark mode

`colorsDark` in the token file holds only the tokens whose value
changes. `build-tokens.js` writes them twice: inside
`@media (prefers-color-scheme: dark)` for `:root:not([data-theme])`,
which follows the operating system, and under `:root[data-theme="dark"]`,
which wins whatever the system says.

People choose under Appearance in the user menu: System, Light or
Dark. System removes `data-theme`, so the operating system decides;
Light and Dark set it. `theme-choice.js` stores the choice in
`localStorage`, and a few lines of blocking script in `base.html`'s
`<head>` reapply it before the first paint, so a page never flashes
the wrong theme. The choice needs JavaScript, so the Appearance
fieldset is hidden in the HTML and the script reveals it.

Blocks use semantic tokens, never the raw `neutral-*` ramp, because
only semantic tokens carry dark values. Three blocks broke that rule,
and in October 2026 each one showed up as a light patch on the dark
page: the "Not started" badge, the primary button's hover, and a
closed comment's border. They now use `inactive-*` and
`action-primary-hover`.

`action-primary` has a dark value too. Besides button backgrounds it
colours nav hover text, focus rings and the accent fallback directly
on the page, and the light value, `#8b1a2b`, is only 1.86:1 against
the dark surface. WCAG asks for 4.5:1 for text and 3:1 for focus
indicators. The dark value, `#e8798a`, is 6.14:1. Because it's light,
`text-on-action` switches to the dark surface colour in dark mode, at
the same ratio, so button text stays readable. I checked each pair
with the WCAG contrast formula rather than by eye.

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

I chose it while Precentor still supported the Church of England
calendar. Now that it's Catholic only, I've kept it: Garamond's type is
just as much a contemporary of Palestrina and the Council of Trent, and
it still suits a tool built around the liturgical year.

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
colour vocabulary (`success`/`warning`/`info`, and `inactive` for a
service not started), applied as small inline chips. The chip shows
the readable label ("Not started"); the raw value only names the
CSS class. `comment-card.css` uses the same tokens for `Comment.state`, but
as a card-level border/background accent rather than a chip — a
deliberate distinction, since a comment is a bigger unit of content
than a one-word status, even though both draw from the same palette.

`liturgical-accent.css` provides `.accent-bar` and `.occasion-dot`,
both reading a `--accent` custom property with a fallback to
`--colors-action-primary`. `service_detail.html` sets `--accent`
inline, directly from `service.occasion.colour` — this works with no
separate colour-mapping code at all, because `LiturgicalOccasion`'s
`COLOUR_CHOICES` values were deliberately chosen to match the
`liturgical-*` token names exactly. The public music list's per-entry
left border (`.music-list-entry--accent`, in `music-list.css`) reuses
this exact mechanism rather than a new one — see "`music_list.html`" below.

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
│   │   ├── badge.css / button.css / card.css / comment-card.css
│   │   ├── form.css / list-row.css / nav.css / role-block.css
│   │   ├── music-list.css / liturgical-accent.css / term-summary.css
│   │   ├── score-combobox.css / crest-crop.css / toast.css
│   │   ├── skip-link.css / page-header.css / user-menu.css
│   │   ├── detail-list.css / empty-state.css
│   │   └── toolbar.css / data-table.css / tag-input.css / term-card.css
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
  rules, a warning-styled draft banner) distinct from the rest of the
  UI, so it reads as a real document even before printing.
- The public layout is genuine newspaper columns —
  `.music-list-columns { columns: 18rem; }` — rather than a hand-built
  grid simulation. It's `column-width`-driven (via the `columns`
  shorthand) rather than a fixed `column-count`, so the browser decides
  how many columns fit; a short half-term list doesn't end up sparsely
  stretched across four columns it doesn't need. `break-inside: avoid`
  on each entry is essential, not optional — without it the browser
  will happily slice a service or marker in half at a column boundary.
  The unlayered print rules above needed no change to make this work:
  they only ever touched the nav/controls and body colour, never the
  column layout, so the printed sheet stays columnar automatically.
  Draft mode always renders the older single-column `dl` grid
  (role→pieces) instead, regardless of this layout — draft is for
  quickly scanning what's still TBC, not previewing the final shape.
- Each entry's left border reuses `--accent` — the same custom
  property `service_detail.html`'s `.occasion-eyebrow`/`.accent-rule`
  already set from `service.occasion.colour` (see "Liturgical accent"
  below) — via a new `.music-list-entry--accent` class, rather than
  inventing a second colour mechanism for the same underlying fact.
- The Public / Draft toggle is a small labelled `<nav>`. The version
  being viewed carries `aria-current="page"`, which screen readers
  announce and the stylesheet shows in bold, so one attribute does
  both jobs.
- The page uses plain `.center` (not `.center[data-intrinsic]`, unlike
  `login.html`) — a document should stay left-aligned internally, only
  centred as a whole block on the page, unlike a small centred form
  where every child should align to the middle.

## Accessibility basics

- **Viewport:** `base.html` sets `width=device-width`. Without it,
  phones lay the page out at about 980px and zoom out, so none of the
  fluid sizing or media queries respond to the real screen.
- **Skip link:** the first focusable element on every page is
  "Skip to main content" (`skip-link.css`), which jumps to
  `<main id="main">`. It sits above the viewport until it receives
  focus, and it's moved with `transform`, not `display: none`, so
  screen readers still find it.
- **Reading measure:** the global layer caps `p` and `li` at 60ch for
  comfortable reading. `.list-row` lifts the cap, because a row
  should span the content width with its badge or buttons at the far
  end. The blocks layer comes after global, so `max-width: none`
  wins without any extra specificity.
- **Help text:** Django links each field's help text to its input with
  `aria-describedby`; `form.css` styles `.helptext` small and muted on
  its own line.
- **Inbox count:** the number beside Inbox is followed by a visually
  hidden " open", so it's read as "Inbox 2 open" rather than a bare
  number.
- **Current section:** the nav link for the section you're in carries
  `aria-current`: `page` on the section's own page, `true` elsewhere
  in it, so a service page marks Terms without claiming to be the
  Terms page. It's shown with an underline as well as colour.
- **Facts on detail pages** are `<dl>` lists, so each label and its
  value are announced as a pair (`detail-list.css`).

## Buttons

There's one filled button per view at most, for the main action:
Save on a form, New term on the terms page, Print on the music list.
Everything else is quieter, so the main action is easy to find.

| Class | Look | Used for |
| --- | --- | --- |
| `button` / `.btn` | Neutral, bordered | Ordinary actions: Confirm, Filter, Add comment |
| `.btn-primary` | Filled with the action colour | The one main action in a view |
| `.btn-ghost` | Transparent, bordered | Secondary actions: Edit, Cancel |
| `.btn-danger` | Red text | Destructive actions: Delete |

Every class works on `<a>` too, so a link that acts as a button looks
like one. Each variant has its own `:hover` rule, because
`button:hover` (an element plus a pseudo-class) outranks a plain class
and would otherwise turn a primary button grey. The small lift on
hover is switched off for people who ask for reduced motion.

## Forms

`form.css` styles Django's standard form output once, so every form
looks the same without per-page styling. Most forms render with
`{{ form.as_p }}`, which wraps each field in a `<p>`.

Longer forms group related fields in a `<fieldset>` with a `<legend>`
(the service form has When, Liturgy and Music list). Screen readers
announce the legend with each field inside it, so the grouping isn't
only visual. Each field in a fieldset is rendered with Django's
`{{ field.as_field_group }}`, which outputs the field's label, help
text, errors and input together.

One Django 6 detail caught me out here. `as_field_group` doesn't wrap
those parts in an element of their own: the label, help text and input
come out as loose siblings. A fieldset with the `.flow` composition
spaces its direct children apart, so it treated the label and its own
input as separate items and put a full gap between them, as wide as
the gap between two fields. Wrapping each field in a plain `<div>`
fixes it. The `<div>` becomes the thing `.flow` spaces, and the label,
help text and input stay together inside it:

```html
<fieldset class="flow">
    <legend>When</legend>
    <div>{{ form.date.as_field_group }}</div>
    <div>{{ form.service_type.as_field_group }}</div>
</fieldset>
```

Other form details:

- A row of small fields side by side (the score's part counts and
  vocal ranges) uses the `grid` composition. `form.css` caps it at
  the reading measure, so the form keeps one right-hand edge, and
  lines it up along the bottom, so a field whose help text wraps
  doesn't push its input below its neighbours'.
- The voicing field suggests the voicings already in the library
  through a native `<datalist>`, with no JavaScript.
- Groups get more space after them than the fields inside them get,
  so each group reads as separate.
- Checkboxes and radios keep their natural size, instead of being
  stretched to the full width like text inputs. A checkbox in Django's
  `as_p` output comes after its label on a line of its own; `form.css`
  finds those paragraphs with `:has()` and lays them out as a reversed
  row, so the box sits before its label on the same line.
- Django marks a field with errors `aria-invalid="true"`, which screen
  readers announce; `form.css` gives the same fields a red border.
- Help text and the shared control height are described under
  "Accessibility basics" and "Scales" above.

## The Library table

The Library is a dense, spreadsheet-style table (`data-table.css`)
under a row of filters (`toolbar.css`).

- **Toolbar:** each control has its label above it, and the row lines
  up along the bottom edge, so labelled controls and the buttons
  beside them sit level. The form is marked `role="search"`.
- **Sorting:** clicking a heading sorts by it, and clicking again
  reverses it. The sorted heading carries `aria-sort`, which screen
  readers announce, plus a small arrow that's hidden from them. The
  view works out each heading's state, since a template can't do
  that logic cleanly. Links use Django's `{% querystring %}` tag, so
  sorting and paging keep the current search and filters.
- **Narrow screens:** the table never goes below 64rem wide, so on a
  phone it scrolls sideways inside a focusable region rather than
  squeezing every title onto several lines. The minimum is written
  as `inline-size: max(100%, 64rem)`, because `min-width` on a table
  is undefined in CSS and browsers ignore it.
- **Sticky header:** a sticky element only sticks inside its nearest
  scrolling box. Once the table's region scrolls sideways it is that
  box, so the region also caps its height (75vh) and scrolls
  vertically, and the header sticks inside it.
- **Numbers** use tabular figures and line up on the right, headings
  included.

## Term cards

The Terms page shows each term as a card (`term-card.css`): name
and phase badge, how far through it is, a status bar, the next
service with what's still to settle, open comments, and "Ready to
publish" once everything is complete.

- **Stretched link:** the term's name is the card's link, and its
  `::after` is stretched over the whole card, so the card is one big
  target. Wrapping the card in an `<a>` instead would put the
  next-service link inside another link, which isn't valid HTML.
  Links inside the card sit above the stretched one, and keyboard
  focus on the name rings the whole card through `:has()`.
- **Status bar:** three segments grow in proportion to the counts of
  complete, in progress and not started services. The counts reach
  the CSS as custom properties on the bar (`style="--complete: 3"`),
  which carry data, not styling choices. The bar is hidden from
  screen readers because the sentence beside it says the same.
- **Hover** gives an accent border, a small lift and a shadow; the
  lift is off for anyone who asks for reduced motion.

**A stacking lesson:** the nav's `view-transition-name` makes it a
stacking context, so the user menu's `z-index` only counted inside
the nav, and the term cards, positioned for their stretched links,
painted over the open menu on a phone. The nav itself now has
`position: relative` and a `z-index`, and a browser test checks the
menu is the topmost thing over a card.

## Chip inputs

The score form's three "suitable for" fields are multi-selects,
which are awkward to use: a long list and Ctrl-click to choose
several. `tag-input.js` turns each into chips over a search box:
type to see the options not yet chosen, Enter or a click to add one,
click a chip (or Backspace in an empty box) to remove one.

- **The select stays the source of truth.** A chip selects or
  deselects its option, so the form submits exactly as it would
  without JavaScript. The select is only hidden once the widget is
  fully built; if anything fails first, the plain select still works.
- **Accessibility:** the search box is an ARIA combobox with arrow
  keys, each chip is a button labelled "Remove Advent", and a live
  region announces every change. The field's `<label>` moves to the
  search box and its help text stays linked through
  `aria-describedby`. The list closes on Escape, on a click elsewhere
  and when focus leaves by Tab.
- **New use types:** uses can also take a name that isn't in the
  list, offered as Add "…". It goes into the form's Other uses field,
  which the script hides, and the server creates it on save. Seasons
  and occasions are pick-only, because an occasion carries a date
  rule that a typed name wouldn't have.

Building this showed up a cascade problem worth recording. The
`hidden` attribute hides an element through the browser's own
`display: none`, and any author style outranks the browser's, so
`form.css`, which gives every select `display: block`, quietly undid
it. A `[hidden] { display: none; }` rule in the utilities layer, the
last layer, now makes `hidden` mean hidden everywhere.

## Page transitions

Moving between pages fades the content in about 180ms, using
cross-document view transitions: an `@view-transition` rule at the
end of `global-styles.css`. The nav has its own
`view-transition-name`, so it stays still while the content changes.
The rule sits inside `@media (prefers-reduced-motion:
no-preference)`, so anyone who asks for less motion gets plain page
loads, and browsers without support load pages as they always did.
It's outside the cascade layers because `@view-transition` is a
document setting, not a style rule competing in the cascade.

The login page opts out. In automated testing, Chromium sometimes
froze the page for three or four seconds before abandoning a
transition, most reliably right after logging in. A transition needs
both pages to opt in, so a `@view-transition { navigation: none; }`
rule on the login page makes logging in a plain page load. I
checked the rest by hand in Chrome, where page-to-page transitions
run smoothly.

## `crest-crop.js` — a hand-rolled image crop tool

Progressive enhancement over a plain `crest_image` file input, in the
same spirit as `score-picker.js`'s combobox: a
real, working control underneath (the file input still submits
normally), enhanced with genuine JS engineering rather than a
third-party cropping library, since hand-building this kind of widget
is exactly the sort of thing this project's brief is assessing. On
file selection it builds a fixed-aspect-ratio frame, lets the image be
panned/zoomed, then renders the chosen crop onto an off-screen
`<canvas>` and swaps the result onto the real file input via the
`DataTransfer` API — so nothing about the surrounding form or its
Django view needs to know cropping happened at all. `core/imaging.py`
re-validates and re-normalises whatever actually arrives server-side
regardless, the same "never trust the client alone" principle applied
elsewhere in the project.
