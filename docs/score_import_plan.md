# Precentor: Score Import

A design document for importing scores in bulk and the related tools
for cataloguing compilations. I worked the reasoning out before
writing any code, because the feature had grown complex enough to
need it.

> **Status, October 2026:** not built. Bulk import is listed as
> future work in the README. This document records the design so it's
> ready when I come back to it. It has been updated for model changes
> made since it was written: the composer is now split into
> `composer_surname` and `composer_other_names`, and the rehearsal
> lead-time tag has been dropped.

This is the third design the feature has been through. I've kept the
earlier ones below, marked as superseded, in the same spirit as the
README's out-of-scope list: it's useful to record why I didn't do
something. The feature turned out more complex than it first looked,
and I'd rather show that than pretend the design arrived finished.

---

## 1. Problem statement

A conductor or librarian moving from a spreadsheet needs to import
their score library into Precentor in bulk. Real spreadsheets are
inconsistent (columns in any order and under any name, missing fields,
the odd bad value), so the feature must never guess and save without
asking. A person has to be able to correct every step before anything
counts as finished. The import has to save real time over entering
scores by hand, not just move the same effort somewhere else. And
review will happen over several sessions, whenever the person has
time, not necessarily in one sitting.

A related problem: real libraries contain **compilations**, anthologies
such as the _Chester Book of Motets_ that hold many individual works. A
CSV will usually list a compilation as one row (the physical book) with
no breakdown of its contents. That breakdown is manual work the tool
can speed up but never fully automate.

---

## 2. Current design

### 2.1 Why the rows have to be saved

Because review happens whenever the person has time (across sessions,
in any order, one row at a time, sometimes long after the upload), the
list and each row's status must survive between page loads. That rules
out reviewing every row at once on a single page: nothing in that
design outlives one request.

### 2.2 The staging model

`Score.title` and `Score.composer_surname` are required, and a badly
parsed CSV row might have neither. I don't want to loosen those
requirements for every hand-entered score just to make imports a
little easier; that would cost integrity everywhere, a trade-off I've
refused elsewhere in the project. Instead, a separate, lightweight
staging model holds whatever was parsed, however incomplete:

```python
class PendingScoreImport(models.Model):
    STATUS_CHOICES = [
        ("error", "Error"),                 # red: no usable Score yet
        ("needs_review", "Needs review"),   # amber: Score exists, not yet confirmed
        ("complete", "Complete"),           # green: explicitly confirmed
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

**From red to amber:** a row moves from "no score yet" to "a real
score exists and needs review" only once it has **both a title and a
composer's surname**. Every other field on `Score` can still be blank
at that point.

### 2.3 The list view

A colour-coded list, one row per `PendingScoreImport`, using the
existing `badge` colour tokens with no new colour system: red is
`danger` (no `score` yet), amber is `warning` (`score` exists,
`status="needs_review"`) and green is `success`
(`status="complete"`).

**Sorted by status first:** red rows before amber before green, so what
most needs attention is at the top and nobody has to hunt for it. This
also removes a worry about page size. Each row is reviewed on its
_own_ page, so the list only needs to cope with ordinary list sizes,
not thousands of form fields in one request, which was the problem
with the earlier formset design.

### 2.4 Reusing the existing score forms

- **A red row** (no `Score` yet) links to `ScoreCreateView`, filled in
  from `raw_data`. Saving it creates the `Score` and turns the row
  amber.
- **An amber row** (a real `Score` exists) links to the ordinary
  `ScoreUpdateView` for that score, with one addition: a **Mark
  complete** action beside the normal save, which sets
  `PendingScoreImport.status = "complete"` (green).
- Both views stay almost exactly as they are, with a small wrapper
  around code that already works.

### 2.5 The "belongs to a compilation" checkbox

This is different from "this row _is_ a compilation". It means "this
piece is in a book the library already owns, or that's also being
imported". Ticking the checkbox reveals a combobox that searches or
creates.

Typing searches existing `Compilation` records and suggests matches.
If nothing matches, it offers to create a new `Compilation` with the
typed name there and then. That ties the checkbox to the same
`Compilation` records the "is a compilation" flag creates, so the two
aren't separate mechanisms.

---

## 3. Compilations

- **A piece in a compilation is a `Score`, not a separate model.** A
  nullable `Score.compilation` foreign key points to a new
  `Compilation` model (title, editor, publisher, `copies_owned`,
  `filing_location`), with `on_delete=SET_NULL`. Every piece can then
  be searched and filtered exactly like a standalone octavo.
- **Cataloguing a compilation's contents is manual work that can't be
  avoided.** No import can invent a breakdown that isn't in the source
  data. The tool's job is to make it quick, not automatic.
- **Where compilation rows go:** ticking "this row _is_ a compilation"
  on a `PendingScoreImport` during review creates a `Compilation` stub
  and takes the row off the main review list. It appears instead on a
  separate, lasting **Compilations to catalogue** list, reachable from
  the Terms page. That matches what I wanted in my own words: "stored
  as a simple list... allowing the user to visit it when they have
  time."
- **The compilation list works like the import list.** Clicking an
  entry opens that compilation's page, which offers two ways to add
  its contents: **paste and parse** for transcribing a whole table of
  contents at once, and a single **Add a piece** link (the ordinary
  `ScoreCreateView`, with `compilation` already set). They work
  together: the first is for when the whole contents list is to hand,
  the second for when I notice one more piece.
- **CPDL is at most a convenience link,** never a source Precentor
  queries or scrapes. Its coverage of any particular anthology can't
  be relied on: CPDL leans towards public-domain works, while a modern
  anthology usually includes music still in copyright that CPDL won't
  have.

---

## 4. Decisions in brief

- A row that fails validation never fails the whole import. It stays
  open for review and editing indefinitely, with no need to upload
  again.
- A row turns from red to amber once it has a title **and** a
  composer's surname.
- "Belongs to a compilation" searches existing `Compilation`s and
  offers to create a new one if nothing matches.
- Compilation rows leave the main list and go on a separate
  Compilations to catalogue list.
- Lists sort by status first: red, then amber, then green.

## 5. Superseded designs (kept for the record)

### 5.1 Reviewing every row on one page with a formset (second design)

A single page built with `modelformset_factory`, showing every
imported row as an editable form at once and saving them together. I
dropped it because it couldn't support review over several sessions:
everything lived only as long as one page. Its size problem (possibly
thousands of form fields on one page) doesn't arise in the current
design, since each row gets its own page.

### 5.2 A progress bar driven by a `fetch()` loop (first design)

A JavaScript progress bar that processed the import in small batches
behind the scenes. I dropped it once the design moved to "everything
visible and reviewable one by one" instead of "processed out of sight
with a progress bar". The prototype's `score-import.js` and its
`score_import_batch` and `score_import_progress` views are no longer
in the codebase.

What carries forward from both earlier designs: `ScoreForm` as the one
place validation happens, the column-mapping step based on synonyms,
and staging the upload for the first CSV parse.

---

## 6. Other considerations

### What a raw row passes to a new compilation stub

`title`, `copies_owned` and `filing_location` carry over directly when
the row has them. `editor` and `publisher` are real `Compilation`
fields, but a CSV laid out for scores never has them, so they start
blank and are filled in later. The composer, `voicing`, `language` and
`duration_minutes` are dropped without a warning. That isn't a loss
anyone needs telling about: those fields mean nothing for a whole
compilation, which has no single composer.

### Compilations are part of the library, with their own pages

They're not just a queue of things to catalogue after an import. A
**compilation list** (`library:compilation_list`) follows the pattern
of the Library page and has its own nav entry beside it. Each
compilation's page lists its contents as a **filtered score list**,
`Score.objects.filter(compilation=this)`, using the existing list
markup. This pays off the decision that a piece in a compilation is a
`Score`: the small library list for a compilation needs nothing new,
just the existing list narrowed down.

### Duplicates: a note, never a block, and real duplicates allowed

Choir libraries often hold the same piece more than once, most
commonly the same setting in a different key to suit a choir's range.
Handling duplicates mustn't prevent that.

- **A new field, `Score.key`** (`CharField(max_length=50, blank=True)`),
  free text. It follows the voicing decision, not the liturgical
  colour one: early repertoire (Byrd, Tallis, Palestrina, exactly what
  my own sample music list contains) is often in a church mode, not a
  major or minor key, so a fixed list of choices would be wrong here.
- **Shown wherever a piece's title appears,** for example "Byrd, Ave
  verum (in G)", on the Library page, in service slots and on the
  music list. One limitation: it can't be styled (in italics, say)
  inside a native `<option>` in the propose-piece dropdown. The key
  still shows there as plain text in brackets, which I accept as a
  limit of native `<option>` rendering.
- **The check:** `Score.objects.filter(title__iexact=title,
  composer_surname__iexact=surname)`, case-insensitive like the
  existing language filter. A match produces an **informational
  note** (through Django messages) linking to the existing entries,
  shown _after_ saving and never preventing it. The person decides
  whether it's an accidental duplicate to tidy up or a separate entry
  (a different key being the main reason, though a different edition
  or arrangement counts too).
- Because a row turning from red to amber goes through
  `ScoreCreateView`, imported rows get this check automatically. That
  comes from insisting on one shared form, with no separate path for
  imports.
- When this is built, it adds a migration to `Score`, and
  `docs/models_plan.md` needs the new field.

### Uploading the same file again

Two simple layers, each doing one job, instead of one clever mechanism
trying to do both:

1. **A check for the exact same file.** `ImportBatch.file_hash` (a
   SHA-256 of the file's contents) is compared with earlier batches at
   upload time, _before_ any processing. A match stops the upload and
   offers a choice: continue anyway as a new batch, or go to the
   matching batch instead. That catches the common case: uploading
   twice by accident, or again because the first attempt's outcome
   wasn't clear.
2. **A check on each row (above).** An edited file (some rows fixed,
   so a different hash) gets past the file check, and doesn't need to
   be caught there: the title and surname check, run when a row turns
   from red to amber, catches each duplicate row whether or not the
   whole file matches.

### Grouping rows into batches

```python
class ImportBatch(models.Model):
    original_filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

`PendingScoreImport` gains `batch = models.ForeignKey(ImportBatch,
on_delete=models.CASCADE, related_name="pending_items")`. The shape is
worth pointing out: **an `ImportBatch` works like a `Term`**, a
container with its own completion summary (red, amber and green
counts), listed as batches instead of one flat list of every row ever
uploaded. It's the same shape as `Term.completion_summary()`, counting
import statuses instead of service statuses.

### A template CSV to download

A static file (columns: Title, Composer Surname, Composer Other Names,
Arranger, Editor, Voicing, Language, Copies Owned, Filing Location,
Duration; one example row), linked from the upload instructions. No
design questions remain here.
