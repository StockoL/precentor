# Precentor — Score Import Feature: Design Document

A design document for the bulk Score import feature and its
related Compilation cataloguing tools. Reasoning worked out before
code is written — because this feature has grown genuinely complex enough
to need it.

This is the third architecture this feature has gone through.
Earlier approaches are kept below, clearly marked superseded, rather
than deleted — the same "why I didn't do X" discipline as the
README's out-of-scope list. It reflects the feature genuinely being more
complex than it first looked, which is worth being honest about rather than
pretending the design arrived fully-formed.

---

## 1. Problem statement

A conductor or librarian migrating from an existing spreadsheet needs
to bulk-import their score library into Precentor. Real spreadsheets
are inconsistently structured (arbitrary column order/naming, missing
fields, occasional bad data), so the feature must never silently
guess-and-commit — every step must be genuinely correctable by a human
before anything is treated as finished. The feature must save real
time over manual entry, not merely relocate the same amount of effort
into a different shape. Review realistically happens across multiple
sessions, "when the user has time," not necessarily in one sitting.

A related, adjacent problem: real libraries contain **compilations**
(anthologies such as the _Chester Book of Motets_) holding many individual
works. A CSV import will typically list a compilation as a single row
(the physical book), with no breakdown of its contents — that
breakdown is inherently manual work the tool can make faster, but
never fully automate.

---

## 2. Confirmed architecture (current)

### 2.1 Why this needs persisted rows, not an ephemeral review page

Because review happens when the person has time — across sessions,
in any order, one row at a time, sometimes long after the upload — the
list and its status must survive between page loads. This rules out a
single-page, all-rows-at-once review entirely: nothing in that
design outlives one request/response cycle.

### 2.2 The staging model

`Score.title`/`Score.composer` are genuinely required fields, and a
badly-parsed CSV row might have neither. Rather than weakening those
requirements for every hand-entered Score too (a real integrity cost
paid everywhere, just to make imports marginally easier — a trade-off
this project has consistently refused elsewhere), a dedicated,
deliberately lightweight staging model holds whatever was parsed,
however incomplete:

```python
class PendingScoreImport(models.Model):
    STATUS_CHOICES = [
        ("error", "Error"),                 # red — no usable Score yet
        ("needs_review", "Needs review"),   # amber — Score exists, not yet confirmed
        ("complete", "Complete"),           # green — explicitly confirmed
    ]
    raw_data = models.JSONField()
    score = models.OneToOneField(
        Score, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="pending_import",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="error")
    is_compilation = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

**Promotion threshold (red → amber):** a row graduates from
"no Score yet" to "a real Score exists, needs review" only once **both
Title and Composer** are present. Everything else on `Score` may remain
blank at this point.

### 2.3 The list view

A colour-coded list, one row per `PendingScoreImport`, reusing the
existing `badge` colour tokens exactly (no new colour system):
red = `danger` (no `score` yet), amber = `warning` (`score` exists,
`status="needs_review"`), green = `success` (`status="complete"`).

**Default sort: status severity first** — red rows before amber before
green, so what most needs attention surfaces at the top rather than
requiring the person to hunt for it. This also resolves what would
otherwise be a real page-scale concern: since each row is reviewed on
its _own_ page, not all together, the list itself just needs
ordinary list-view scale, not "thousands of form fields on one
request" — the earlier formset design's scale worry doesn't apply to
this architecture at all.

### 2.4 Reusing the existing Score forms — not a parallel form stack

- **Red row** (no `Score` yet) → links to `ScoreCreateView`, pre-filled
  from `raw_data`. Saving it for the first time creates the `Score` and
  promotes the row to amber.
- **Amber row** (a real `Score` already exists) → links to the ordinary
  `ScoreUpdateView` for that `Score`, with one addition: a **"Mark
  complete"** action alongside the normal save, setting
  `PendingScoreImport.status = "complete"` (green).
- Both views stay almost entirely as they already are — a small
  wrapper around existing, working machinery.

### 2.5 The "belongs to a compilation" checkbox

Distinct from "this row _is_ a compilation": this means "this
individual piece lives inside a book the library already owns (or is
also being imported)." Revealed by a checkbox, behaving as a
search-or-create combobox.

Typed text searches existing `Compilation` records and
suggests matches; if nothing matches, offers to create a new
`Compilation` from the typed name on the spot. This ties the checkbox
directly to the same `Compilation` records created via "is a
compilation" flag, rather than being two disconnected mechanisms.

---

## 3. Compilations

- **A compilation piece is a `Score`, not a separate model** — a
  nullable `Score.compilation` FK to a new `Compilation` model (title,
  editor, publisher, `copies_owned`, `filing_location`),
  `on_delete=SET_NULL`. Keeps every piece searchable/filterable through
  the exact same mechanisms as a standalone octavo.
- **Cataloguing a compilation's actual contents is manual, irreducible
  work** — no import can invent a breakdown that doesn't exist in the
  source data. The tool's job is to make this fast, not automatic.
- **Where compilation-flagged rows go:** ticking "this row
  _is_ a compilation" (on a `PendingScoreImport`, during the main
  import review) creates a `Compilation` stub and removes that row
  from the main Score-review list entirely. It instead appears on a
  **separate, persistent "Compilations to catalogue" list, reachable
  from the dashboard** — exactly the person's own description: "stored
  as a simple list... allowing the user to visit it when they have
  time."
- **The Compilation list view mirrors the import review list** — same
  list-view pattern, clicking an entry goes to that compilation's own
  detail page, which offers ways to add its contents: both the
  previously-designed **paste-parse bulk entry** (for transcribing a
  whole table of contents at once) and a **quick single "add a piece"
  link** (the ordinary `ScoreCreateView`, pre-filled with
  `compilation=this`) — not mutually exclusive; the bulk tool serves
  "I have the whole contents list to hand," the single-add link serves
  "I just noticed one more piece."
- **CPDL is at most a convenience link**, never a data source Precentor
  queries or scrapes — reasoning already established: coverage of
  any given physical anthology can't be relied upon; CPDL skews toward
  public-domain works, while a modern anthology usually mixes in
  actively copyrighted content CPDL won't have at all.

---

## 4. Confirmed sub-decisions (summary)

- Row-level validation failures are never all-or-nothing; a row stays
  reviewable/editable indefinitely rather than forcing a re-upload.
- Promotion threshold red→amber: Title **and** Composer both present.
- "Belongs to a compilation": search existing `Compilation`s, offer
  create-new if no match.
- Compilation-flagged rows leave the main list entirely and populate a
  separate dashboard-level "Compilations to catalogue" list.
- List views default-sort by status severity (red, then amber, then
  green).

## 5. Superseded approaches (kept for the record, not in use)

### 5.1 Formset-based single-page review (second architecture)

A `modelformset_factory`-based single page showing every imported row
as an editable form simultaneously, committed together. Superseded
because it can't survive across the multi-session review pattern the
person actually wants ("visit it when they have time") — everything
lived only for the duration of one page/request. Its scale concern
(potentially thousands of form fields on one page) is moot under the
current architecture, since each row now gets its own ordinary page.

### 5.2 Batch `fetch()`-loop progress bar (first architecture)

A JS-driven progress bar processing the import in small batches behind
the scenes. Superseded because the design direction moved to
"everything visible and individually reviewable," not "processed
invisibly with a progress indicator." `score-import.js` and the
`score_import_batch`/`score_import_progress` views built for this
should be removed, not left dormant.

What _does_ carry forward unchanged from both earlier passes:
`ScoreForm` as the single source of validation truth, the
synonym-based column-mapping step, and the staged-upload mechanism for
the initial CSV parse.

---

## 6. Other Considerations

### Data transfer from a raw row to a new Compilation stub

`title`, `copies_owned`, `filing_location` transfer directly when
present in the source row. `editor`/`publisher` — genuine `Compilation`
fields, but a Score-shaped CSV mapping never captures them — start
blank, filled in later. `composer`/`voicing`/`language`/
`duration_minutes`/`lead_time_tag` are silently discarded: not
surprising data loss requiring a warning, just fields that have no
meaningful equivalent on a whole compilation (there is no single
"composer" of an anthology).

### Compilations are a first-class, browsable part of the library

Not just an import-adjacent "to catalogue" queue: a proper
**Compilation list view** (`library:compilation_list`), mirroring
`score_list.html`'s pattern, with its own nav entry alongside the
Score library. Each Compilation's detail page shows its contents as a
**filtered Score list** — `Score.objects.filter(compilation=this)`,
reusing the existing list-row markup rather than inventing new display
logic. A direct payoff of the original "a compilation piece is a
Score, not a separate model" decision — the "mini library list" needs
no new machinery, just the existing one, scoped.

### Duplicate detection: informational, never blocking; multiple genuine entries allowed

Real choir libraries legitimately hold the same nominal piece more than
once — perhaps most commonly the same setting transposed into a different key
for a particular choir's range. Duplicate handling must not prevent this.

- **A new field, `Score.key`** (`CharField(max_length=50, blank=True)`),
  free text — mirroring the voicing decision, not the liturgical-colour
  one: early music repertoire (Byrd, Tallis, Palestrina-era settings —
  exactly the kind of repertoire in this project's own reference music
  list) is often in a church mode, not a conventional major/minor key,
  so a closed choice set would be the wrong fit here.
- **Displayed distinctly wherever a piece's title appears** — e.g.
  "Byrd, Ave verum (in G)" — in `score_list.html`, service role rows,
  and the music list. **Caveat:** this can't be styled (italics) inside
  a native `<select>` `<option>` in the propose-piece dropdown — the
  key still shows there, just as plain parenthetical text, a real,
  accepted limitation of native `<option>` rendering, not a bug to fix.
- **Duplicate check**: `Score.objects.filter(title__iexact=title,
composer__iexact=composer)` (case-insensitive, same reasoning as the
  existing language filter's `__iexact`). A match produces a
  **non-blocking, informational note** (via Django messages) with a
  link to the existing entry/entries — shown _after_ saving, never
  preventing it. The person decides whether it's a genuine accidental
  duplicate worth tidying up, or a legitimately distinct entry (a
  different key being the flagship reason, though a different edition
  or voicing arrangement is equally valid).
- Since the import-review promotion flow (red → amber) reuses
  `ScoreCreateView` directly, this check applies to imported rows
  automatically, at no extra cost — a direct payoff of insisting on one
  real, reused form rather than a parallel import-specific path.
- Note for implementation: this adds a migration to `Score`, and
  `docs/models_plan.md` will need updating to reflect the new field
  when this is actually built.

### Re-running the upload/mapping step

Two complementary, deliberately cheap layers, rather than one clever
mechanism trying to do both jobs:

1. **File-level exact-duplicate check.** `ImportBatch.file_hash` (a
   SHA-256 of the uploaded file's content) is checked against prior
   batches at upload time, _before_ any processing happens. A match
   stops the upload and offers a choice: continue anyway (a new,
   separate batch), or go review the existing matching batch instead.
   Catches the common, lazy case — an accidental double-upload, or
   re-uploading because the first attempt's outcome wasn't clear.
2. **Row-level check (resolved above).** A genuinely edited
   re-upload (some rows fixed, file hash now different) won't be
   caught by the file-hash check — but doesn't need to be: the
   Score-level title+composer duplicate check, surfaced when a row
   promotes from red to amber, independently catches individual
   duplicate rows regardless of whether the whole file matches.

### `PendingScoreImport` batch grouping

```python
class ImportBatch(models.Model):
    original_filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

`PendingScoreImport` gains `batch = models.ForeignKey(ImportBatch,
on_delete=models.CASCADE, related_name="pending_items")`. Worth naming
the structural echo explicitly: **an `ImportBatch` is, to the
dashboard, exactly like a `Term`** — a container with its own
completion summary (red/amber/green counts), shown as a list of
batches rather than one permanently flat list of every pending item
ever uploaded. Same shape as `Term.completion_summary()`, just
counting import statuses instead of service statuses.

### Downloadable template CSV

A static download (columns: Title, Composer, Arranger, Voicing,
Language, Copies Owned, Filing Location, Duration, Rehearsal Lead
Time; one example row), linked from the upload guidance page. No open
design questions remain here — straightforward to build.
