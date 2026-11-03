# Merging the work since submission

The live site and `main` are as I submitted them on 23 October 2026.
Everything since is on the `post-submission` branch. This is how I mean
to bring it onto the live site once assessment is over, with the risky
part, the migrations meeting real data, tried on a copy first.

## What the merge does to the data

`post-submission` adds 26 migrations. Three of them move data rather
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

## On the day

1. **Copy the live data.** Take a backup of the Render database and
   restore it into a local Postgres. The database accepts no outside
   connections (`ipAllowList` is empty in `render.yaml`), so the copy
   comes from Render's backups, or from allowing my own address for a
   moment in the dashboard. I haven't yet checked which the plan offers.
2. **Rehearse on the copy.** With `DATABASE_URL` pointing at it:
   `python manage.py migrate`, `python manage.py load_calendar`, then
   `python manage.py check_copied_data`. Stop if it reports a problem.
3. **Decide about hidden hymns.** For any church the check names, tell
   its owner the hymns will now print, or remove those pieces after the
   merge.
4. **Merge and deploy.** Merge `post-submission` into `main` and push.
   Render's build runs `migrate` and `load_calendar` itself.
5. **Check the live site.** Run `check_copied_data` against the live
   database, then the deployment checks in `testing.md` (section 8) and
   a look at the pages added since submission. The free web service has
   no shell, so the check runs from my own computer, with `DATABASE_URL`
   set to the live database's external address while my address is
   allowed in the database's settings, and removed again afterwards.
6. **Drop the old columns.** Only once the check is clean on the live
   data: merge the `drop-old-columns` branch, which removes the four
   columns (`planning/0029`, `core/0015`), the code that still wrote
   them, and the check itself, then deploy again. I rehearsed it on the
   migrated rehearsal database: both migrations applied, the typed
   hymns stayed as pieces in their Hymns slots, and every page opened.
