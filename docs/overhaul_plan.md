# Precentor: overhaul audit and plan

Written 19 October 2026, after a gap of several months. This is the one place I track the overhaul: I tick items off as they land and record decisions in section 8 as I make them.

## 1. Where things stand

I went back through the live repo (templates, CSS, tokens, models, views, settings, JS) instead of relying on my older notes. Three corrections to what the README and my earlier audits say:

- The bugs from the previous audit are fixed. The `planning` URLs exist, `get_absolute_url` is on `Score` and `Service`, `Service.status` is correct, and `service_confirm_delete.html` is clean.
- Most of the design work I'd listed as unbuilt is built: `TermMarker`, `SiteConfig` with crest upload and crop, hymns/psalm fields, the three-tier suitability tags on `Score`, `occasion_for_date`, the live occasion suggester, toast, theme toggle, AJAX confirm/propose/add-role, and the score combobox. whitenoise is wired.
- What is still unbuilt is the CSV import, `LiturgicalOccasion` seed data (so the occasion dropdown is empty on a fresh install), and deployment.

Section 5 records the baseline test run.

The app is structurally sound. The weak part is the presentation layer: I assembled it from design-system primitives but never made firm decisions about hierarchy, scale or wording. That is why it feels unpolished, and it can be fixed in a focused sweep without a rebuild.

## 2. Typography: why it feels out of proportion

The causes are specific.

1. **The base size is too large and it grows.** `--typography-step-0` is `clamp(1rem … 1.25rem)`, so body text is 16px on a phone and 20px on a desktop. For a dense planning tool, 20px body text belongs in a reading app.
2. **Controls inherit the same size.** `button.css` and `form.css` both set `font-size: var(--typography-step-0)`, so on desktop every button and input is 20px. They should sit a step below body text.
3. **Under 16px, iOS zooms the page on input focus**, so the floor for form controls must be 16px. The current 16px minimum is correct; the fix is to lower the maximum and the ratio, not the floor.
4. **Headings jump too far.** The scale ratio is 1.2 at the small end and 1.25 at the large end, with `h1` at `step-4` (33px to 49px) and `h2` at `step-3` (28px to 39px). An `h2` like "Roles" or a term name inside a card is 39px on desktop, which is bigger than most page titles in comparable apps.
5. **The music list is the worst case.** Each service heading is an `h2` at `step-3` inside an 18rem column (about 288px). "Sunday 4th October 2026 — Sung Eucharist" at 39px wraps to three lines.
6. **`step--1` is not small enough.** It runs 13px to 16px, so on desktop badges, errors and the term summary are the same size as body text at its minimum, and the hierarchy collapses.
7. **Garamond and Inter at the same pixel size don't match.** EB Garamond has a small x-height and looks roughly two pixels smaller than Inter at the same size. Headings can be a touch larger than the numbers imply, which is another reason not to set them as large as they are now.
8. **Print uses the fluid scale.** `clamp()` with `vw` means nothing on paper. The music list needs fixed `pt` sizes in the print block.

### Proposed scale

I'll regenerate the scale in Utopia (utopia.fyi/type/calculator) with these inputs and paste it into `precentor-tokens.JSON`:

| Setting | Value |
|---|---|
| Min viewport / max viewport | 360px / 1280px |
| Base size | 16px / 18px |
| Scale ratio | 1.125 / 1.2 |
| Steps | -2 to 5 |

That gives roughly step-0 16 to 18px, step-1 18 to 22px, step-2 20 to 26px, step-3 23 to 31px, step-4 26 to 37px. Elements are then mapped by role instead of by tag:

| Element | Token | Approx. size |
|---|---|---|
| Page title (`h1`) | step-4 | 26 to 37px |
| Section heading (`h2`) | step-2 | 20 to 26px |
| Card / sub heading (`h3`) | step-1 | 18 to 22px |
| Body, list rows | step-0 | 16 to 18px |
| Buttons, inputs, nav | step--1 | 14 to 15px, with inputs floored at 16px |
| Badges, helper text, timestamps | step--2 | 12.5px |

Inputs need an explicit `font-size: max(1rem, var(--typography-step--1))` so the iOS floor holds. Music list headings drop to `step-1`; print uses `11pt` body and `14pt` headings.

The space scale moves to the same 16/18 base so padding doesn't outgrow the type.

## 3. Nomenclature

### Wording that is wrong or inconsistent

| Now | Where | Change to |
|---|---|---|
| `not_started`, `in_progress`, `complete` shown raw | every status badge | "Not started", "In progress", "Complete" (mapped in the model or a template filter; the raw value stays for the CSS class) |
| Nav says "Score Library", page says "Scores" | nav, `score_list.html` | "Library" in both |
| Nav says "Inbox", page says "Open comments" | nav, `inbox.html` | "Inbox" in both, with an open count in the nav |
| "Site settings" | nav | "Settings", shown to the conductor only |
| "Dark mode" / "Light mode" text button | nav | Appearance (System / Light / Dark) in the user menu (section 7) |
| `19/10/2026` in lists, `Sunday 4th October 2026` on the music list | list rows vs music list | one format in the app UI ("Sun 4 Oct 2026"), with the long form kept only on the music list |
| "Add a term", "Add a service", "Add a marker", "Add a score" | page actions | "New term", "New service", "New marker", "New score" |
| "View music list", "View draft (internal)", "View public version" | term detail, music list | "Music list" and a Draft / Public toggle |
| "Un-confirm" | piece row | "Unconfirm" |
| "Service form" | page title | "Edit service" / "New service" |
| `LANGUAGE_CODE = "en-us"`, `TIME_ZONE = "UTC"` | settings | `en-gb`, `Europe/London` (dates then default to day-first and BST is handled) |
| Long calendar choice labels | calendar choices | short labels, with the long form as help text |
| Auto-generated labels such as "Soprano parts", "Suited use types" | score form | explicit `verbose_name` and `help_text` per field |
| Page titles `X — Precentor` | all templates | keep, but make every page use it, with the object first |

### Terms still to decide (see section 8)

- **Role.** The user-facing word for "Setting, Anthem, Introit" in a service. "Role" is the model name and reads as jargon in the UI ("Add a role"). "Slot" or "Item" is closer to how choirs talk about a service sheet.
- **Marker.** A dated note in the music list ("Half term", "No choir"). Fine as a model name; in the UI "Note" or "Break" may be clearer.
- **Term.** Correct for a collegiate or cathedral pattern, but a parish choir might say "season" or "period", and "season" collides with liturgical season. "Term" is defensible and matches the rest of my docs.
- **Piece vs score.** The library holds scores; a service holds pieces (a score proposed in a slot). I want to keep that distinction and use each word consistently in the UI.

## 4. Other findings, worst first

### Broken or risky

1. **No viewport meta tag in `base.html`.** On a phone the page renders at desktop width and scales down, so the fluid type and space scales and every `@media` and `clamp()` decision work against the wrong width. One line fixes it: `<meta name="viewport" content="width=device-width, initial-scale=1">`.
2. **Media files on Heroku.** The crest image is saved to `media/`, and Heroku's filesystem is wiped on every restart and deploy, so the crest would vanish. The options were storing it in the database (a `BinaryField`, fine at about 3KB for a single crest), Cloudinary or S3, or committing a default crest as a static file. I've chosen the database (section 8).
3. **Dark mode has holes.** Because `neutral-*` is not overridden:
   - `.badge--not_started` stays a light grey chip on a dark page.
   - `button:hover` goes to `neutral-800` (`#27272a`) on a `#1c1b1f` surface, so the hover is nearly invisible.
   - `--colors-action-primary` (`#8b1a2b`) on the dark surface is about 1.9:1 contrast, so nav hover colour and focus outlines fail WCAG (which needs 3:1 for UI, 4.5:1 for text). It needs a lighter dark-mode value.
4. **N+1 queries.** `TermListView` calls `completion_summary()` per term, which calls `Service.status` per service, which runs two queries per role. Ten terms of fifteen services with five roles each is well over a thousand queries per page load. The fix is to prefetch `services__roles__pieces` and compute status from the prefetched objects.
5. **Service detail renders every score in every role's `<select>`.** The combobox sits over a full `<select>` per role, so the page HTML grows as roles times scores. Fine at 20 scores, painful at 500. A single shared `<datalist>` or a lazy fetch fixes it.
6. **Production settings are incomplete.** `ALLOWED_HOSTS = []`, no `CSRF_TRUSTED_ORIGINS`, no `SECURE_*` or cookie settings, no `Procfile`, and `SECRET_KEY` has no failure message if the environment variable is missing.

### Design and hierarchy

7. **`li` and `p` are capped at 60ch globally**, so `.list-row` (a flex row that should span the content width with the badge or buttons at the far right) is squeezed to 60ch and looks oddly narrow on wide screens. The cap should come off `li` inside `.list-row`, or the measure should apply to prose only.
8. **Every bare `<button>` is a primary burgundy button.** "Log out", "Dark mode", "Filter", "Close", "Confirm" and "Print" all look equally important. The default button should be neutral, with an explicit `.btn-primary` for the one primary action per view.
9. **Links that act as buttons are unstyled.** "Add a term", "Add a service" and "View music list" are plain inline links next to styled ghost and danger buttons. Page-level actions need a consistent header block (title left, actions right).
10. **Nav.** The brand has the same weight as the links, there's no current-page state (`aria-current="page"`), no `aria-label` on the `<nav>`, no skip link, and the full nav, including Settings, shows to logged-out visitors.
11. **Detail pages are label-value paragraphs.** `score_detail.html` and `service_detail.html` use `<p>Label: value</p>`. A `<dl>` with a grid, or a small summary block, reads better and is the correct semantics.
12. **The score list is a list of titles.** It shows no composer, voicing or language, and the "Add" link sits above the filter. A librarian scanning the library needs a table (or card rows) with title, composer, voicing, language and copies.
13. **Empty states are bare** ("No terms yet.", "No roles yet."). Each should say what to do next and offer the primary action.
14. **Delete confirmations don't say what goes with the item.** Deleting a term cascades to its services, roles, pieces and markers, and the confirm page should say how many.
15. **Inline styles.** `style="--flow-space: …"` is the accepted CUBE way to vary a composition, but `onclick="window.print()"` on the music list is an inline handler and belongs in a JS file.
16. **Every script loads on every page** (six module scripts). Each one guards itself, but a `{% block extra_js %}` would let each page load only what it uses.
17. **`music_list.html` and `_music_list_service_entry.html` start with a stray HTML comment** before `{% extends %}`/content. Harmless, but it should go.
18. **`house_accent_colour` is interpolated into a `style` attribute.** Django escapes it, but the form should validate a 6-digit hex so a malformed value can't break the attribute.

### Housekeeping

19. **LICENSE says "Louis Mannix".** It should carry my legal name, Louis Stockton; the business name Mannix Music is unaffected. Line 3 changes to "Louis Stockton".
20. **The README status banner** is nearly right but out of date: the remaining work is the import feature, seed data, deployment and wrap-up, not only "deployment and documentation".
21. **Docs naming drifted.** The repo has `ordo_plan.md` and `score_import_plan.md`, but `music_list_redesign_design.md` isn't in `docs/` at all even though the feature is built. I'll restore it (or fold it into `design_system.md`) so the docs match the code.
22. **No `LiturgicalOccasion` data.** `ordo/migrations/0004` seeds use types and seasons only. A fresh clone has an empty occasion dropdown and a suggester with nothing to suggest. This is the biggest risk for the demo.
23. **Locale and time zone** (see section 3) affect date display and the "today" boundary.

## 5. Step 0: the baseline

With the venv active:

```powershell
python manage.py test
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
```

Then a branch and tag, so the overhaul can be reverted cleanly:

```powershell
git switch -c overhaul
git tag pre-overhaul
```

Done 19 October 2026: `pre-overhaul` tags `94a7781`, and the work continues on `overhaul`. With the Phase 0 code changes in place, all 70 tests pass (the Playwright browser tests run as part of `manage.py test`) and `makemigrations --check` is clean. `check --deploy` is still to run; its warnings belong to Phase 7.

Phase 1 doesn't start until the tests are green; otherwise I can't tell a regression from an old failure.

## 6. The plan

Each phase is a set of small commits (one concern each, imperative summary, body explaining why).

### Phase 0: Catholic-only scope (about half a day, first)

Decision (19 Oct): Precentor is Catholic-only for now. Doing this before the visual work means every later form, test and page is built against the final shape instead of being rebuilt.

The CofE footprint, found by searching the repo:

| Area | What goes |
|---|---|
| `ordo/models.py` | `TRADITION_CHOICES`; the `tradition` field on `LiturgicalSeason` and `LiturgicalOccasion`; the `tradition` ordering and `__str__` suffix; the `tradition` argument of `occasion_for_date()` |
| `planning/models.py` | `Term.tradition`, `Service.tradition`, `Service.effective_tradition()` |
| `planning/forms.py`, `planning/admin.py`, `ordo/admin.py` | `tradition` in field lists, filters and list displays |
| `ordo/views.py` | the `tradition` query parameter and its validation |
| `service_form.html`, `occasion-suggest.js` | `data-term-tradition`, the tradition lookup and the tradition check before fetching |
| `ordo/migrations/0004` | the whole `"cofe"` season list, and the "Harvest" use type |
| Tests | about 40 references across `ordo/tests.py`, `planning/tests.py`, `planning/test_browser.py`, `library/tests.py`, `comments/tests.py` and `comments/test_browser.py`, all using `tradition="cofe"` |
| Docs | `ordo_plan.md` (13 mentions), `models_plan.md` (17), `README.md` (7) |

Steps:

1. [x] Migrations that delete the CofE rows (`LiturgicalSeason` and `LiturgicalOccasion` where `tradition="cofe"`), then remove the `tradition` fields from all four models. Delete first (`ordo/0005`, data only), then `RemoveField` (`ordo/0006`, `planning/0005`, schema only). Data and schema operations are in separate migrations because on PostgreSQL, deleting rows that have FK links and then altering the same table inside one transaction can fail with "cannot ALTER TABLE because it has pending trigger events". Migrations 0001 to 0004 stay untouched; they are history and still run correctly on a fresh database.
2. [x] Remove `tradition` from models, forms, admin, the lookup view, the template and the JS. `occasion_for_date(date, calendar_use)` loses a parameter.
3. [x] Rewrite the tests to match. The "wrong tradition excluded" test goes; the "invalid tradition" test becomes an "invalid calendar use" test; the other `calendar_use` tests stay.
4. [x] Relabel `calendar_use` as the Catholic choice it now is: "Ordinary Form (Novus Ordo)" and "Extraordinary Form (1962)". It stays, because a choir that sings both rites needs it. The stored values `current` and `historic` are unchanged; only the labels move, so the migrations (`ordo/0007`, `planning/0006`) are SQL no-ops.
5. [x] Revise the seeded seasons to the Catholic set (Advent, Christmas, Ordinary Time, Lent, Easter Triduum, Easter; Pentecost is a feast, not a season) and drop "Harvest" from the use types. `ordo/0008` renames Holy Week to Easter Triduum (keeping existing score tags) and removes Pentecost; `ordo/0009` removes Harvest, and the score form's help text no longer suggests it. Both are reversible.
6. [x] Docs: README scope and out-of-scope list (the dual-tradition Ordo moves to "future work", with the reasoning kept), `ordo_plan.md`, `models_plan.md`, and the ERD's occasion attributes.

Steps 1 to 3 go in one commit, because the migrations, models and tests only pass together.

For seed data, romcal and missalemeum both cover the Roman calendar; romcal also has a national calendar for England and Wales.

### Phase 1: foundations (about half a day)

1. [x] Add the viewport meta tag and a skip link.
2. [x] Set `LANGUAGE_CODE = "en-gb"` and `TIME_ZONE = "Europe/London"`. This needed a `NativeDateInput` widget first: under `en-gb`, Django renders dates as DD/MM/YYYY, which `<input type="date">` rejects, so every edit form's dates would have opened blank.
3. [x] Regenerate the type and space scales (section 2) in `precentor-tokens.JSON`, run `node build-tokens.js`, and remap headings by role in `global-styles.css`. Also: body text sized on `body` (it had no size, and must not go on `html`, where it would rescale every rem); buttons, inputs and nav at step--1 with inputs floored at 16px; badges and help text at step--2; a shared `--layout-control-height` of 2.5rem.
4. [x] Fix dark mode: dark values for `action-primary` and the colours used by badges and hover states. Instead of overriding the raw `neutral-*` ramp, the blocks now use semantic tokens with their own dark values (`action-primary-hover`, and an `inactive-*` trio).
5. [x] Fix the 60ch measure so it doesn't constrain `.list-row` items.

Done when every page is readable at 360px and 1280px, headings step down visibly from `h1` to `h3`, and dark mode has no light patches.

### Phase 2: nomenclature (about two hours)

1. [x] Settle the glossary in section 8 (slot, notice, term).
2. [x] Status labels via a model property or filter, keeping raw values for CSS classes. Done as `Service.STATUS_LABELS` and a `status_label` property; status is derived, so there is no `get_status_display()`.
3. [x] Nav, page titles, headings and button wording per section 3. The nav's Settings link shows to the conductor only and Inbox carries an open count, both from a `nav` context processor in `precentor_project`.
4. [x] Date format and `verbose_name` / `help_text` on the model fields. One format module (`precentor_project/formats/en_GB/formats.py`, via `FORMAT_MODULE_PATH`) sets "Sun 4 Oct 2026". The calendar choice labels were kept, since Phase 0 had just settled them; the help text now explains the term default and the service override instead.

Done when no underscore or raw choice value is visible anywhere in the UI.

### Phase 3: components (about a day)

1. [x] Button hierarchy: neutral default, `.btn-primary`, `.btn-ghost`, `.btn-danger`, and an anchor style that matches. `.btn-confirm`, which nothing used, became `.btn-primary`; a test keeps each page to one primary action.
2. [x] A `.page-header` block (title and actions), used on the list and detail pages. Form pages have only a title and their own Save, so they don't need it.
3. [x] Nav: current-page state, auth gating, user menu with Appearance, open-comment count. Plus cross-document view transitions (see the Phase 3 log entry).
4. [x] Detail pages as `<dl>` blocks. The score list as a table moves to Phase 4, where the Library page spec covers it in full.
5. [x] Empty states and cascade-aware delete confirmations.
6. [x] Form layout: grouped fields, help text, visible error styling. The service form is grouped; the score form's fieldsets are part of Phase 4.

### Phase 4: page-by-page pass (about half a day)

Terms, Term detail, Service detail (the screen I'll use most), Library, Score detail and form, Inbox, Music list (screen and print), Settings and Login, each in both themes at 360px and 1280px, with screenshots before and after. The music list gets fixed `pt` print sizes and a real print check (Save as PDF).

Progress:

- [x] **Library** (`909a90f` to `eec04d9`), built to the spec in section 7: `editor` and `last_sung_manual` fields; last sung derived by `with_last_sung()`; catalogue names and ordering; search, Language and Voicing filters (the old Voice part filter dropped, as decided); a sortable table with `aria-sort`; fifty to a page with the filters kept in the links. Found and fixed on the way: suitability ranking listed a score once per tag (it also affected the propose-piece picker), and a score with no language blanked the Language menu.
- [x] **Score page** (`85fd49f` to `a191936`): `background`, `notes` and four vocal ranges, the ranges checked by a validator and stored in one tidy form; a history state for each proposed piece (Sung, Scheduled or Proposed); and the page rebuilt as a summary, background, notes, ranges and a service history table.
- [x] **Score form** (`f7a1396` to `7455901`): five fieldsets, a datalist of existing voicings, freehand use types created on save, and chip inputs over the three suitability selects. Found on the way: `hidden` didn't hide a select inside a form, because `form.css` sets its `display`; a `[hidden]` utility now fixes that everywhere.
- [x] **Terms** (`e48afba` to `a7106c6`): full-width status cards built to the spec in section 7, current and upcoming first, past folded away. The view loads everything in a fixed number of queries, which also does Phase 5's first item for this page; a test checks the count doesn't grow with more terms. Found on the way: the open user menu was drawn behind the cards on a phone (a stacking context from the nav's view-transition-name).
- [ ] The remaining pages: Term detail, Service detail, Inbox, Music list (screen and print), Settings, Login.

### Phase 5: performance and robustness (about half a day)

1. Prefetch status data for the term list, with `assertNumQueries` tests so it stays fixed.
2. One shared score list for the comboboxes instead of one `<select>` per role.
3. Per-page scripts via `{% block extra_js %}`; move the print handler out of the template.
4. Validate `house_accent_colour` as hex.

### Phase 6: seed data and features

1. **Ordo seed data (first).** Generate occasions from romcal (MIT) or missalemeum (MIT) as a one-off, load them through a data migration or fixture, and register `LiturgicalOccasion` in the admin. The demo needs this whatever else happens.
2. **CSV import.** Built per `docs/score_import_plan.md` (the persisted-row architecture; nothing superseded remains in the repo). It is a "should have"; see the decision in section 8.
3. Any JS follow-ups from the existing JS audit.

### Phase 7: deployment (about half a day)

1. `Procfile`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` from the environment, `SECURE_*` and secure cookie settings, `DEBUG` off.
2. Crest stored in the database (section 4, item 2).
3. Heroku Postgres, `collectstatic`, migrations and seed data on deploy, and `check --deploy` clean.
4. A fresh deploy from scratch, with the steps written down.

### Phase 8: submission readiness (about a day)

1. README: accurate status, install and run steps, deployment steps, screenshots, credits (including font licences and the data sources).
2. A testing document: manual test table (feature, steps, expected, result), automated test summary, browser and device matrix.
3. Validation evidence: W3C HTML and CSS validators, a JS linter, pycodestyle/flake8, Lighthouse (performance, accessibility, best practices).
4. Reconcile `user_stories.md` against what's built, and mark anything descoped.
5. LICENSE name; docs naming (section 4, item 21).

Total: about six focused days, including Phase 0, the library table and the tag inputs; most of it is Phases 0 to 4.

## 7. Page specs

### Global

- A shared control height (`--control-height`, about 2.5rem) on inputs, selects and buttons so a toolbar row lines up. Labels sit above their controls and the row aligns to the bottom edge.
- Theme choice moves out of the nav into a user menu (name, Appearance: System / Light / Dark, Settings for the conductor, Log out). Settings stays for church-wide config only.
- A subtle site-wide crossfade between pages using cross-document View Transitions, with the nav pinned and reduced motion respected.

### Terms page

- Full-width vertical cards. Current and upcoming terms first in date order, past terms collapsed below.
- "New term" as a filled primary button at the right of the page heading, in a shared `.page-header`.
- Each card shows: a Current / Upcoming / Past badge with "Week 4 of 12" or "starts in 3 weeks"; the date range; a complete / in progress / not started bar; the next service with what is outstanding (warning-coloured within about two weeks); an open-comments count; "ready to publish" when everything is complete.
- Hover and focus: accent border, a small lift and shadow, a visible focus ring, all off under reduced motion. Secondary links inside a card use the stretched-link pattern so anchors are not nested.
- The status data is computed once in the view with prefetching (the same fix as the N+1 item).

### Library page

Toolbar, left to right: a search box (`type="search"`), Language, Voicing, Filter, and a Clear link if any filter is active. "New score" is a primary button at the right of the heading.

- **Search.** One box, split on whitespace; every word must match somewhere in title, composer surname, other names, arranger or editor (an AND of ORs). Works without JS as a plain GET. A later enhancement can filter as the user types.
- **Voicing replaces Voice part.** A select built from the distinct voicings actually in the library, with counts ("SATB (84)", "SSATB (12)"), plus one grouped option, "Any four-part mixed", that matches scores with all four part counts above zero. The old per-voice-part filter can move under "More filters" if I still find I need it. To stop "SATB" and "S.A.T.B." splitting into two entries, the Voicing field on the score form gets a `<datalist>` of existing values.
- **Table, spreadsheet style.** Columns: Composer, Title, Voicing, Language, Duration, Copies, Filing location, Last sung. Dense rows, 1px borders, tabular numerals, a sticky header and row hover. The Composer column reads `Palestrina, Giovanni Pierluigi da (ed. Stockton)`, with `(arr. …)` shown the same way when there is an arranger.
- **Sorting and size.** Server-side sort by clicking headers (`?sort=composer&dir=asc`, with `aria-sort`), default composer surname then title, paginated at 50 with filters preserved in the links. On narrow screens the table sits in a scrollable, focusable region, and the least important columns (Duration, Copies, Filing) hide below a container width.
- **Last sung.** Derived, never stored, like `Service.status`: the latest service date among confirmed pieces whose date has passed. A confirmed piece in a future service is "scheduled", not "sung". For history that predates Precentor, an optional `last_sung_manual` date; the table shows the later of the two. Shown as a date with a relative hint ("4 Oct 2026, 3 weeks ago"), "Never" when blank, and sortable through an annotation.
- **Model changes.** A new `editor` field (separate from `arranger`, because they are different roles); ordering becomes composer surname then title.

### Score detail page (repurposed)

The table now carries the metadata, so this page holds what doesn't fit in a row:

- Background and history (`background`, long text).
- Interpretation and rehearsal notes (`notes`, long text).
- Vocal range per part: four optional fields (`range_soprano` and so on), validated as note names such as `A3–E5`.
- Performance history: a small table of every service the piece has been proposed or confirmed in (date, service, slot, state). "Last sung" is computed from the same data, so the two always agree.
- A compact summary of the library metadata at the top, and Edit / Delete as before.

### Score form

- **Tags.** The three "suited" fields become empty chip inputs: nothing preloaded, type to see matching options, Enter or click to add, click a chip to remove. The help text ("e.g. …") stays. They're built the same way as the score combobox, as vanilla JS over the existing `<select multiple>`, which remains the no-JS fallback.
- **What can be created freehand.** Use types are plain labels, so typing a new one creates it on save (trimmed, matched case-insensitively against existing ones). Seasons and occasions are calendar data: an occasion carries a date rule and a colour that drive the suggester and the liturgical accent, so a made-up one would have no date. Those two fields allow searching and picking, not inventing. The empty seed data is also why the occasions field looks uneditable at the moment: `LiturgicalOccasion` has no rows, so there is nothing to pick. Seeding it (Phase 6, step 1) fixes that.
- **Layout.** Grouped fields: Identity (title, composer surname, other names, arranger, editor), Forces (voicing, four part counts), Library (language, copies, filing location, duration), Liturgical use (the three tag fields), Notes (background, notes, ranges).

## 8. Decisions

### Made

| Question | Decision |
|---|---|
| Keep `calendar_use` (Ordinary / Extraordinary Form) after dropping CofE | Yes |
| Delete the CofE rows in the dev database | Yes; nothing in it matters yet |
| Separate `editor` field alongside `arranger` | Yes |
| "Last sung" counts only confirmed pieces whose date has passed, with an optional manual date for older history | Yes |
| Use types can be created freehand; seasons and occasions are pick-only | Yes |
| Repurpose the score detail page for background, ranges and history | Yes |
| Theme choice | User menu (System / Light / Dark); Settings stays for church-wide config, conductor only |
| Page transitions | Cross-document View Transitions crossfade, nav pinned, reduced motion respected |
| Crest storage on Heroku | In the database (single small image, no extra service) |
| Base type size | 16px to 18px, ratio 1.125 to 1.2 (decided 19 Oct 2026) |
| UI word for `ServiceRole` | "Slot": it reads as a place that holds pieces ("Offertory slot: 2 pieces proposed"). "Moment" (the liturgical documents' word) reads oddly in "Add a moment"; "Item" blurs with "piece"; "Part" clashes with voice parts. |
| UI word for `TermMarker` | "Notice": these are public announcements on the music list, as parish notices are. "Note" risked confusion with musical notes and the planned score notes field; "Rubric" is too obscure. |
| Keep "Term" | Yes: cathedral and choir-school usage, and it matches term names like "Michaelmas 2026". "Season" clashes with liturgical seasons. |

Model names stay as they are (`ServiceRole`, `TermMarker`); only the words shown in the UI change, in Phase 2.

### Open

| Question | Leaning |
|---|---|
| CSV import in or out of this submission | Out of the first deploy; build it after Phases 1 to 5 if time allows, since the overhaul and seed data matter more to the assessment |

## 9. Progress log

One line per phase as it completes, with the commit range.

- Step 0 (19 Oct 2026): baseline tagged `pre-overhaul` at `94a7781`; branch `overhaul`.
- Phase 0 (19 Oct 2026): `13548ef` to `ad6fb3e`. Beyond the six planned steps, it also renamed the use types to Mass and Vespers, switched test fixtures and the add-role placeholder to Catholic service and slot names, and corrected the README and ERD, which claimed role templates were seeded (none exist). 73 tests pass.
- Phase 1 (19 Oct 2026): `031c217` to `54e3a7d`. Browser tests now cover the skip link, the root font size, the shared control height and list row width. A screenshot pass of eleven pages in light and dark at 360px and 1280px found no overflow and no light patches; it also caught Anglican examples left in the score form's help text, fixed in `54e3a7d`. Left for later phases: music list headings too large for their columns (Phase 4), every nav button styled as primary (Phase 3), the "Is not applicable" checkbox stretched to full width (Phase 3 form layout). 81 tests pass.
- Phase 2 (19 Oct 2026): `bc395b1` to `e683bdd`. A scan of the visible text of fifteen pages found no underscores, raw values or retired words, except the crest's storage path ("Currently: site_config/crest.png") from Django's file widget on Settings; that widget goes when the crest moves into the database (Phase 7). Also found: the `core` app had no tests at all; `core/tests.py` now exists, but the settings singleton, crest processing and conductor-only access still need tests (Phase 5). The term page now calls `Service.status` three times per row; Phase 5's prefetching rewrite should make that cheap. 99 tests pass.
- Phase 3 (19 Oct 2026): `d1e8d42` to `785ab63`. The view transitions needed care. In Playwright's Chromium, some navigations froze for three to four seconds before the browser abandoned the transition, so the work waited on a branch until I'd checked it by hand in Chrome, where page-to-page transitions run smoothly. The login page opts out, and the browser tests check the configuration from the parsed CSS rather than waiting for a transition. The screenshot pass also caught two problems my own earlier changes had caused: the toast's x button had grown to the 40px control height, and bulletless lists kept a 40px indent. Both are fixed. 121 tests pass.
