# Precentor: Design System

This document covers the visual design system: how it's structured,
why it follows CUBE CSS, and the reasoning behind each layer. See the
main [README](../README.md) for domain and data decisions, and
[`docs/blocks_backlog.md`](blocks_backlog.md) for how each Block was
picked out from repetition I'd actually seen, not guessed at.

## Methodology: CUBE CSS

CUBE CSS (Composition, Utility, Block, Exception, championed by Andy
Bell) organises styles into layers of increasing specificity and
decreasing reuse:

1. **Global:** tokens and base element styles (typography, reset).
2. **Composition:** layout primitives with no aesthetic opinions
   (spacing, wrapping, alignment). No colour or typography.
3. **Block:** repeated components with their own visual identity
   (badges, forms, the comment card).
4. **Utility:** small, single-purpose overrides.

I didn't build any Blocks until every page had been laid out with
Compositions first. That way the Block list (see `blocks_backlog.md`)
reflects patterns that really did repeat across the app, not
components imagined before any page existed.

## Cascade layers, not `@import`

`static/src/global/layers.css` declares:

```css
@layer reset, global, compositions, blocks, utilities;
```

Every other CSS file wraps its rules in the matching `@layer { }`
block. Cascade priority therefore comes from this declared order, not
from the order the files load in. That matters because every file is
linked individually with a plain `<link>` tag in `base.html`, not
chained together with `@import`.

**Why not `@import`:** an early prototype (adapted from a toolkit
called `looseleaf-ui`) used `@import "..." layer(name);` to import a
file and assign its layer in one line. I dropped it because `@import`
chains are sequential, render-blocking requests: the browser can't
request the second file until it has fetched and parsed the first.
Plain `<link>` tags can all be requested in parallel, especially under
HTTP/2, and `@layer` gives the same cascade guarantees without the
cost.

**Why no bundler either:** I prototyped a bundler (minification,
single-file output) but didn't adopt it. Bringing Node and npm into an
otherwise pure-Python Django project, for a handful of small CSS files,
was more complexity than the benefit justified at this scale.
`variables.css` (see below) is the one generated CSS file in the
project, produced by a small dependency-free Node script and committed
like any other build output.

## Design tokens

`precentor-tokens.JSON` (project root) is the single source of truth
for colour, the type and space scales, layout constants, fonts and
transition timings. `build-tokens.js` (also in the project root) compiles
it into `static/src/global/variables.css`. It runs with
`node build-tokens.js` and needs no `npm install`, since it only uses
Node's built-in `fs` and `path` modules.

**Don't hand-edit `variables.css`.** The script regenerates it from the
JSON every time it runs. It's treated like a Django migration:
generated, committed, never edited by hand.

### Scales

Type and space scales are fluid (via `clamp()`), generated with
[Utopia](https://utopia.fyi), so sizes interpolate smoothly between a
minimum and maximum viewport instead of jumping at fixed breakpoints.

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
above. Error messages stay at `step--1`, because they have to be read,
not skimmed.

Body text is sized on `body`, never on `html`. Every `rem` is
measured from the root element, so a fluid size there would quietly
rescale every token in the system. I made exactly that mistake once,
and on a desktop every rem became 18px; a browser test now checks the
root stays at the browser's default.

**Control height:** `--layout-control-height` (2.5rem, so 40px) is the
minimum height of buttons, text inputs and selects, with their
vertical padding removed, so a field and the button beside it line
up. It's a minimum, not a fixed height, so a button whose label
wraps can still grow. Textareas, checkboxes and radios keep their
natural size.

### Colour

- A neutral grey ramp, with semantic tokens (`surface-*`, `text-*`,
  `border-*`) pointing into it.
- Status colours (`success`, `warning`, `danger`, `info`), each with a
  base value and `-bg`, `-border` and `-text` variants, used by
  `badge.css` and `comment-card.css`. An `inactive` set follows the
  same pattern for things with nothing active on them: a service not
  started, a closed comment.
- A `liturgical-*` set (`violet`, `red`, `green`, `white`, `rose`),
  matching the `choices` on `ordo.LiturgicalOccasion.colour` exactly.
  See "Liturgical accent" below.

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
with the WCAG contrast formula, not by eye.

## Fonts

Headings use **EB Garamond** and body text uses **Inter**. Both are
self-hosted instead of loaded from the Google Fonts CDN. That saves a
third-party DNS lookup and render-blocking request, and it means no
visitor's IP address goes to Google on every page load. Both are
variable fonts, so one file each covers the full weight range.

I chose EB Garamond over an earlier candidate, Fraunces. Fraunces has
a soft, editorial character that's very much of the moment, which
seemed a poor fit for a project rooted in centuries-old liturgical
tradition. EB Garamond is a faithful revival of Claude Garamond's
16th-century type, which is contemporary with the Reformation and
early Anglican liturgy.

I chose it while Precentor still supported the Church of England
calendar. Now that it's Catholic only, I've kept it: Garamond's type is
just as much a contemporary of Palestrina and the Council of Trent, and
it still suits a tool built around the liturgical year.

`build-font-fallback.js` generates a metric-matched fallback
`@font-face`, which sits between the real font and the generic system
font in the stack (for example `"EB Garamond", "EB Garamond Fallback",
system-ui, serif`). Because the fallback has the same metrics, the
page barely shifts when the real typeface finishes loading and swaps
in. `font-display: swap` on both real `@font-face` declarations keeps
text visible while the fonts load, so there's no flash of invisible
text.

## Liturgical accent

`badge.css` is the project's status indicator. `Service.status` and
`RolePiece` confirmation share the same colour vocabulary (`success`,
`warning`, `info`, and `inactive` for a service not started), shown as
small inline chips. The chip shows the readable label ("Not started");
the raw value only names the CSS class. `comment-card.css` uses the
same tokens for `Comment.state`, but as a border and background on the
whole card instead of a chip, because a comment is a bigger piece of
content than a one-word status.

`liturgical-accent.css` provides `.occasion-eyebrow` (the occasion's
name above a service's title), `.accent-rule` (a short coloured line
under it) and `.occasion-dot` (a dot beside an occasion in a list). All
three read a `--accent` custom property and fall back to
`--colors-action-primary`. Templates set `--accent` inline to
`var(--colors-liturgical-{{ service.occasion.colour }})`. No separate
colour-mapping code is needed, because I chose the values in
`LiturgicalOccasion`'s `COLOUR_CHOICES` to match the `liturgical-*`
token names exactly. The public music list's left border on each entry
(`.music-list-entry--accent`, in `music-list.css`) uses the same
mechanism; see "`music_list.html`" below.

**This is a contextual accent, not a theme for today's date.** It's a
scaled-down version of a bigger idea, where the whole app's background
would reflect the current liturgical season on any given day. That
would need season date ranges in `ordo`, not just named occasions on
single dates, which is a substantial addition to a model layer I
otherwise consider finished. The contextual version reuses data
already in `Service.occasion` and cost nothing extra to build; the
README notes it as the scope I chose.

## Folder structure

```
static/src/
├── global/
│   ├── layers.css          # @layer declaration order; link first
│   ├── variables.css       # generated by build-tokens.js
│   ├── fonts.css           # @font-face declarations
│   ├── fonts-fallback.css  # generated by build-font-fallback.js
│   ├── reset.css
│   ├── global-styles.css
│   └── fonts/
│       ├── eb-garamond/
│       └── inter/
├── compositions/
│   ├── center.css / cluster.css / flow.css / grid.css
│   ├── reel.css / sidebar.css / switcher.css / wrapper.css
│   └── cover.css           # added later; see below
├── blocks/
│   ├── badge.css / button.css / card.css / comment-card.css
│   ├── form.css / list-row.css / nav.css / role-block.css
│   ├── music-list.css / liturgical-accent.css / term-summary.css
│   ├── score-combobox.css / crest-crop.css / toast.css
│   ├── skip-link.css / page-header.css / user-menu.css
│   ├── detail-list.css / empty-state.css
│   └── toolbar.css / data-table.css / tag-input.css / term-card.css
├── utilities/
│   └── utilities.css
└── js/
    ├── ajax.js / toast.js / user-menu.js / theme-choice.js
    ├── comments.js / service-detail.js / score-picker.js
    └── occasion-suggest.js / tag-input.js / crest-crop.js
```

**`cover.css`** isn't part of the original `looseleaf-ui` Composition
set. I added it during the design pass to centre `login.html`'s form
vertically within the full page height. That's a different axis from
`.center`, which only caps the width and centres horizontally, so the
two are used together, not as alternatives.

## `music_list.html`: a different visual mode

The music list is meant to be read and printed, not navigated, so it
has its own treatment instead of inheriting the app's nav and Block
styling wholesale:

- `@media print` and `@page` are declared **outside** every `@layer`.
  Unlayered CSS always beats layered CSS, whatever the order or
  selector specificity, so the site nav and the music list controls
  are always hidden in print; a mistake in layer order can't let them
  through. The project doesn't use `!important` anywhere, because
  cascade layers already give the guarantee it's usually reached for.
- On screen, `.music-list` gives the page a document-like look
  (heading rules, a warning-coloured draft banner) distinct from the
  rest of the UI, so it reads as a document even before printing.
- The public layout uses real newspaper columns,
  `.music-list-columns { columns: 18rem; }`, instead of a grid made to
  look like them. The `columns` shorthand here sets a column width,
  not a fixed count, so the browser decides how many columns fit, and
  a short half-term list isn't stretched thinly across four columns.
  `break-inside: avoid` on each entry is essential: without it the
  browser will slice a service or notice in half at a column
  boundary. The print rules needed no change for this, since they
  only touch the nav, the controls, the type and the colours, so the
  printed sheet stays in columns too. Draft mode always uses the
  older single-column `dl` grid (slot and pieces) instead, because
  draft is for scanning what's still TBC, not previewing the final
  layout.
- Each entry's left border reuses `--accent`, the same custom property
  `service_detail.html`'s `.occasion-eyebrow` and `.accent-rule` set
  from `service.occasion.colour` (see "Liturgical accent" above), via
  a `.music-list-entry--accent` class. One colour mechanism serves
  both pages.
- The Public / Draft toggle is a small labelled `<nav>`. The version
  being viewed carries `aria-current="page"`, which screen readers
  announce and the stylesheet shows in bold, so one attribute does
  both jobs.
- Service headings use `step-1` on screen; at the app's usual `h2`
  size they wrapped onto four lines in an 18rem column.
- Each entry is a size container (`container-type: inline-size`).
  Below 26rem the occasion, hymns and psalm go under the pieces
  instead of beside them, which on screen means inside a newspaper
  column. It's a container query, not a media query, because what
  matters is the column's width, not the window's; wide entries,
  print included, keep them side by side.
- Print uses fixed sizes (11pt body, 14pt headings, 18pt title), since
  the fluid screen scale is worked out from the window width and
  means nothing on paper. It keeps Garamond throughout and resets the
  colour tokens the list uses to print-safe values, so the paper
  looks the same whichever theme the person printing has chosen. I
  checked it by printing to PDF in both themes.
- The page uses plain `.center`, not `.center[data-intrinsic]` as
  `login.html` does. A document should stay left-aligned inside and
  be centred only as a whole block, whereas in a small centred form
  every child should line up on the middle.

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
  hidden " open", so it's read as "Inbox 2 open", not a bare
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
  stretched to the full width like text inputs. A paragraph holding a
  checkbox is found with `:has()` and laid out as a row, with the box
  given `order: -1`, so it sits before its label on the same line
  whichever order the HTML has. (A first attempt used `row-reverse`,
  which only worked for Django's label-first `as_p`; the hand-written
  Settings form showed it up.) Colour pickers are swatch-sized.
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
  phone it scrolls sideways inside a focusable region instead of
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

## `crest-crop.js`: a hand-built image crop tool

This is progressive enhancement over a plain `crest_image` file input,
in the same spirit as the score combobox in `score-picker.js`: a real,
working control underneath (the file input still submits normally),
improved with my own JavaScript instead of a third-party cropping
library, since building this kind of widget is part of what the
project's brief assesses. When a file is chosen, it builds a frame
with a fixed aspect ratio and lets the image be panned and zoomed
inside it. It then draws the chosen crop onto an off-screen `<canvas>`
and puts the result back on the real file input through the
`DataTransfer` API, so neither the form nor its Django view needs to
know cropping happened. `core/imaging.py` validates and normalises
whatever arrives on the server regardless, since the client alone is
never trusted.
