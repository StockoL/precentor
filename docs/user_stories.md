# Precentor: User Stories

These user stories drive the design and functionality of Precentor.

## Conductor

- As a conductor, I want to see all open terms at a glance, sorted
  chronologically, so I know what needs planning.
  - Met by: The Terms page (`term_list`): current and upcoming terms first, in date order, with past ones folded away.
- As a conductor, I want to see, within a term, which services are
  complete, in progress, or not started, so I know where to focus.
  - Met by: The term page (`term_detail`): each service's status badge and a count for the term.
- As a conductor, I want to filter the score library by voicing,
  language, and liturgical occasion, so I can find pieces my choir can
  actually sing right now.
  - Met by: The Library (`score_list`): Voicing, Language and Suitable-for filters, the last by occasion or season.
- As a conductor, I want to see how long it's been since a piece was
  last sung (with full history available on demand), so I can avoid
  repeating it too often, or repeat it on purpose.
  - Met by: The Library's Last sung column, and the history table on each score's page (`score_detail`).
- As a conductor, I want the scores suggested for a slot to say why
  (tagged for this Sunday, for the season, sung six weeks ago), so I can
  judge the suggestion rather than take it on trust.
  - Met by: The add-piece form on the service page (`service_detail`) and the propose page (`add_piece`): suggestions grouped, each with its reasons.
- As a conductor, I want a pew sheet for each service with the motet's
  words beside a translation, so the congregation can follow what the
  choir sings.
  - Met by: The pew sheet (`service_pew_sheet`), linked from each service.
- As a conductor, I want to choose a hymn by its book and number, with
  a few suggested for the day, so planning hymns is as quick as writing
  the numbers down.
  - Met by: A Hymn slot's book and number boxes on the service page, with the day's hymn suggestions beneath.
- As a conductor, I want to choose the tune a hymn is sung to and have
  the pew sheet give that tune's number, so the congregation can find
  the music.
  - Met by: The tune choice on a hymn's row (`set_tune`); the pew sheet prints "tune NEH 115".
- As a conductor, I want to propose a shortlist of pieces for a slot
  (e.g. two motets for the Offertory), so I can weigh choices before
  deciding.
  - Met by: Proposing more than one piece in a slot (`add_piece`).
- As a conductor, I want to confirm or unconfirm individual pieces
  independently, so I can lock in decisions as they're made without
  being forced to decide everything at once.
  - Met by: Confirm and Unconfirm on each piece (`toggle_confirm`).
- As a conductor, I want to mark a slot as not needed for a specific
  service (e.g. no setting on Good Friday), so the system doesn't treat
  an intended gap as unfinished work.
  - Met by: "Not needed (N/A)" when adding a slot (`add_role`); an N/A slot needs no piece.
- As a conductor, I want to add or remove slots on a specific service,
  so I can handle exceptions (an extra motet, a hymn sung in place of a
  Proper) without fighting a fixed template.
  - Met by: Add a slot (`add_role`) and Remove (`remove_slot`) on the service page.
- As a conductor, I want to type a hymn or psalm into its slot as a
  number from the book, so hymns are planned and confirmed alongside
  everything else without each one being a score in the library.
  - Met by: A typed reference in a Hymn or Psalm slot (`add_piece`), proposed and confirmed like any piece.
- As a conductor, I want to see at a glance which slots are propers,
  which the Ordinary and which hymns, and to change that for a slot
  when we sing something else there, so the plan says what we really do.
  - Met by: The kind badge on each slot and its Change kind control (`change_kind`).
- As a conductor, I want the music list to print the propers beside the
  rest of the music if that's our house style, so the printed list
  matches what the congregation is used to.
  - Met by: The arrangement setting on Settings (`site_config_update`), used by the music list (`term_music_list`).
- As a conductor, I want my templates to remember what each slot is, a
  hymn sung at the Introit for instance, so I set it once rather than on
  every service.
  - Met by: The template form (`slot_template_update`), where each slot has a kind and proper part.
- As a conductor of a choir that sings the 1962 Mass, I want each
  Proper slot to offer that day's chant, so I'm not looking up the
  Introit in the Liber every week, and I can still choose something
  else.
  - Met by: The day's chants offered on Proper slots (`add_piece`), one click to propose, for terms in the Extraordinary Form.
- As a conductor in the Ordinary Form, I want Sundays' Proper slots to
  offer the Graduale's chants for that year of the cycle, so the sung
  propers are as easy to plan as the readings are to find.
  - Met by: The same offer for Ordinary Form Sundays and major feasts, for the year of the cycle.
- As a conductor, I want templates for the services I plan often (Mass,
  Vespers, or my own), so a new service starts with its usual slots in
  one click, and I can still change them afterwards.
  - Met by: The template buttons on the service page (`apply_template`), and the Templates page (`slot_template_list`).
- As a conductor, I want to add a dated notice to a term's music list
  (e.g. "Choir resumes on 22 February"), so the congregation knows
  about breaks without a service being invented to carry the message.
  - Met by: New notice on the term page (`marker_create`); notices print on the music list.
- As a conductor, I want to generate a public-facing music list
  reflecting only confirmed pieces, so I never accidentally publish
  something still under consideration.
  - Met by: The music list (`term_music_list`), public version: confirmed pieces only.
- As a conductor, I want to generate a partial/internal version of the
  list with clearly marked "TBC" placeholders, so my team can see
  progress even before everything's confirmed.
  - Met by: The music list's Draft version, with TBC for slots not yet decided.
- As a conductor, I want to open a comment thread on a service or
  term, so I can discuss a query with my librarian without leaving the
  app.
  - Met by: The comment form on each term and service (`add_comment`).
- As a conductor, I want to set our church's name, crest, colours and
  which form of the Mass we follow, so the music list looks like ours
  and the calendar matches our liturgy.
  - Met by: Settings (`site_config_update`).

## Librarian / Music Administrator

- As a librarian, I want to see the full repertoire plan (proposed and
  confirmed) for any open term, so I know what to prepare.
  - Met by: The term and service pages, which every role can read.
- As a librarian, I want to record and update how many copies of a
  score we own and where they're filed, so the physical library stays
  organised.
  - Met by: Copies owned and filing location on the score form (`score_update`).
- As a librarian, I want to raise a comment about a specific piece in
  its service's thread (e.g. "do we have enough copies?"), so I can flag
  a concern directly to the conductor.
  - Met by: The thread on the piece's service page (`add_comment`).
- As a librarian, I want to see a simple inbox of all open comments, so
  I know at a glance what still needs attention.
  - Met by: The Inbox (`inbox`), with its count in the menu.
- As a librarian, I want to bring our existing library in from the
  spreadsheet we already keep, so I don't have to type hundreds of
  scores in again.
  - Met by: Import on the Library (`score_import`), from a CSV file in the template's columns (`import_template`).
- As a librarian whose library lives in Google Sheets, I want to paste
  the sheet's link rather than download it first, so bringing it in is
  one step fewer.
  - Met by: The Google Sheets link box on the same page.
- As a librarian, I want to see which rows of my file were skipped and
  why, and to undo the whole import if it went wrong, so a messy
  spreadsheet can't leave a mess in the library.
  - Met by: The import's result page (`score_import_detail`) and Remove (`remove_import`).
- As a librarian, I want to download the whole library as a
  spreadsheet, so I have a copy of my own and can tidy it in bulk.
  - Met by: Export on the Library (`export_library`), in the import's own columns.
- As a librarian, I want the church's hymn books in the library with
  their copies, and each hymn's first line and words added as we learn
  them, so the hymns we sing build into a record of our own.
  - Met by: Hymnals (`hymnal_list`), each hymnal's page, and Edit on each hymn (`hymn_update`).
- As a librarian who already keeps a hymn book's numbers in a
  spreadsheet, I want to import that list into the book without losing
  anything we've corrected by hand, so the record is complete from the
  start.
  - Met by: Import a list on a hymnal's page (`hymn_import`), which fills blanks and never overwrites.
- As a librarian, I want one page that shows what the library's details
  are missing, so I can fill the gaps when I have a spare half hour
  without being nagged about them.
  - Met by: The completeness page (`completeness`), linked from the Library.
- As a librarian, I want to record a motet's text and its translation
  with who made it, so the pew sheet can print them and the credit is
  kept.
  - Met by: The Text fieldset on the score form: text, translation and translation credit.

## Viewer (a singer, a clergy colleague, an assistant)

- As a viewer, I want to see each term's services, their slots and the
  pieces proposed or confirmed, so I know what's coming without asking.
  - Met by: The Terms, term and service pages.
- As a viewer, I want to browse and search the library, so I can look
  up a piece's voicing, language or notes before a rehearsal.
  - Met by: The Library (`score_list`) and each score's page.
- As a viewer, I want to comment on a service or term, and close or
  reopen a thread, so I can raise a question and say when it's settled.
  - Met by: The comment form (`add_comment`) and Close or Re-open (`toggle_close`).
- As a viewer, I want the pages to show me only what I can use, so I'm
  not offered buttons that would refuse me.
  - Met by: Buttons are hidden by role through `can`; a refused page says why (403).

## Owner (whoever registered the church, or was handed it)

- As someone running a church's music, I want to register my church
  and start planning straight away, so I don't have to ask anyone to
  set it up for me.
  - Met by: Register (`signup`), then the first steps on an empty Terms page.
- As an owner, I want to start with working Mass and Vespers templates,
  so a new church isn't faced with a blank page.
  - Met by: The Mass, Vespers and Mass with hymns templates every new church is given.
- As an owner, I want to invite people with a link that gives them a
  role and expires, so I can bring in my librarian and singers without
  the site sending email.
  - Met by: Invite someone on the Members page (`invite`), with a link that works once within seven days.
- As an owner, I want to change someone's role or remove them, so the
  list of people who can see our plans stays right as people come and
  go.
  - Met by: Change role (`change_role`) and Remove (`remove`) on the Members page.
- As an owner, I want to make a reset link for someone who has
  forgotten their password, so they can get back in without email.
  - Met by: Reset link on the Members page (`reset_link`).
- As an owner, I want to hand ownership to someone else, so the church
  isn't stuck when I step down.
  - Met by: Make owner on the Members page (`make_owner`).
- As an owner, I want to delete the church and everything in it, after
  being told what will go, so our data doesn't stay behind when we
  stop using it.
  - Met by: Delete the church (`delete_church`), after typing its name, from a page listing what goes.
- As a member, I want to delete my own account, so I can leave without
  asking the owner.
  - Met by: Delete my account (`delete_account`).
- As a member of any church, I want to be sure no other church can see
  or change our data, so I can trust the site with our plans.
  - Met by: Every page is limited to the person's own church; another church's address gives 404. The isolation test checks every route.

## Site owner's goals (the church)

- The church wants an accurate, professionally formatted music list
  produced for the congregation each term, without manual re-typing.
  - Met by: The music list (`term_music_list`), printed from the browser.
- The church wants a clear, auditable record of what was actually
  performed, useful for licensing/reporting purposes (see "nice to
  have" CCLI export in the README).
  - Met by: Partly: each score's page lists every service it was proposed for or sung at. The CCLI export isn't built.
- The church wants the conductor's and librarian's responsibilities
  kept appropriately separate, so physical library management and
  musical decision-making don't conflict.
  - Met by: The Conductor and Librarian roles (README §2), enforced in `accounts/permissions.py`.
