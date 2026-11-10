# Merging the work since submission

After I submitted on 23 October 2026, everything new went on the
`post-submission` branch, and `main` and the live site stayed as
submitted. On 10 November I brought the branch onto `main` and the live
site. This is how I planned it, with the risky part, the migrations
meeting real data, tried on a copy first, and what happened on the day.

## What the merge does to the data

`post-submission` adds 28 migrations. Three of them move data rather
than only adding columns:

- `planning/0020` gives every existing slot a kind and proper part,
  worked out from its name.
- `planning/0023` copies each service's Hymns and Psalm text into slots
  as confirmed pieces: the hymns, in the order typed, into a Hymns slot,
  the psalm into a Psalm slot.
- `planning/0027` splits each template's slots, kept as lines of text,
  into rows with a kind each.

None of them deletes anything. The old columns (`Service.hymns` and
`psalm`, `SiteConfig.show_hymns_psalm` and `SlotTemplate.slot_names`)
stay until a later migration drops them, once the copies are checked.

One behaviour changes. On the submitted site a church could keep hymns
and the psalm off its music list (`show_hymns_psalm`). Nothing reads
that setting now, so a church that had it off would start to see its
copied hymns printed. The check below names any such church.

## The check

`python manage.py check_copied_data` reads every service with hymns or
a psalm and every template, compares the old text with what was copied,
and lists churches that had hidden hymns. It changes nothing. It ends
with "Everything was copied" or, if anything differs, with an error and
each difference, so it can't pass unnoticed.

## Rehearsed on 2 November 2026

I checked out `main` as submitted into a separate folder, built a
database with its own demo seed, and added old-style data the seed
doesn't have: three services with hymns and psalms typed in (one with
extra spaces), a template whose text repeated a slot in different
capitals and had a blank line, and a second church with hymns hidden on
its music list. Then `post-submission` migrated the same database:

- all 26 migrations ran;
- `load_calendar` loaded 4,143 chants for 1962 and 440 for the Ordinary
  Form;
- `check_copied_data` reported everything copied, and named the church
  that had hidden hymns;
- every main page, term, music list, service, pew sheet and template
  page opened without an error, 42 in all.

That was SQLite with made-up data; the live site is Postgres with real
data, which is why the first step below is a copy.

## Rehearsed on the live data, 10 November 2026

I exported the live database from the Render dashboard (the plan offers
an export, a `pg_dump` in directory format) and restored it into a
local PostgreSQL 17.11, the same version Render runs. The copy held 13
churches, 13 people, 8 scores, 3 terms, 2 services, 10 slots, 1 piece
and 26 templates. No service had hymns or a psalm typed in, and no
church had hidden them.

- **As submitted.** `main` at `50aa979`, checked out separately, opened
  the copy with nothing to migrate, and all 123 of its pages answered
  without an error for every church.
- **The merge.** On `post-submission` at `a2ccdf1`, all 28 migrations
  ran (two more than on 2 November: the chants' order within a part,
  and Sequence and Responsory slots). Then `load_calendar` loaded 4,210
  chants for 1962 and 494 for the Ordinary Form, and
  `check_copied_data` said "Checked 0 services with hymns or a psalm,
  and 26 templates. Everything was copied."
- **What the data migrations did.** Every one of the 10 slots was given
  a kind (five Ordinary, five Propers with their parts), and the 26
  templates became 182 rows, one for each line of their old text.
- **The pages.** All 177 pages, now including the pew sheets, hymnals,
  tunes and completeness, opened for every church in Chromium with no
  error in the page or the console.
- **Time and memory**, measured on a fresh copy on my own computer:
  `migrate` 1.5 seconds and 87 MB at most, `load_calendar` 1.8 seconds
  and 68 MB, `check_copied_data` 0.5 seconds and 58 MB. Render's free
  web service allows 512 MB.

Nothing failed, so the merge went ahead.

## On the day, 10 November 2026

The plan had six steps. Here is each, with what happened.

1. **Copy the live data.** Take a backup of the Render database and
   restore it into a local Postgres. The database accepts no outside
   connections (`ipAllowList` is empty in `render.yaml`), so the copy
   comes from Render's backups, or from allowing my own address for a
   moment in the dashboard. *Done:* I used the dashboard's export, as
   described above.
2. **Rehearse on the copy.** With `DATABASE_URL` pointing at it:
   `python manage.py migrate`, `python manage.py load_calendar`, then
   `python manage.py check_copied_data`. Stop if it reports a problem.
   *Done:* no problems, as above.
3. **Decide about hidden hymns.** For any church the check names, tell
   its owner the hymns will now print, or remove those pieces after the
   merge. *Nothing to decide:* no church had hidden them.
4. **Merge and deploy.** Merge `post-submission` into `main` and push.
   Render's build runs `migrate` and `load_calendar` itself. *Done:*
   `main` had nothing of its own since submission, so the merge was a
   fast-forward to `dbc70a7`. I pushed it, and Render reported the
   deploy successful. Later the same day `main` moved on to `5daa862`
   and was pushed again.
5. **Check the live site.** Run `check_copied_data` against the live
   database, then the deployment checks in `testing.md` (section 8) and
   a look at the pages added since submission. The free web service has
   no shell, so the check runs from my own computer, with `DATABASE_URL`
   set to the live database's external address while my address is
   allowed in the database's settings, and removed again afterwards.
   *Done:* the check reported no difference, and checks D01 to D09
   passed, D09 on my own iPhone, iPad and PC.
6. **Drop the old columns.** Only once the check is clean on the live
   data: a migration removing the four old columns, and the code that
   still reads them (the template's text and the settings admin), as a
   commit and deploy of its own. It's ready, and rehearsed, on the
   `drop-old-columns` branch. *Not done yet:* the check was clean, so
   this is the next step. The four columns are still in the live
   database.
