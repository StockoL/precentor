# Testing Precentor

This covers the automated tests, the checks I ran on the code, the
manual tests, and the bugs found along the way. Each check says what I
used, what it found and whether that's resolved. The manual tests were
carried out on 23 October 2026, in Chromium through Playwright on a
local copy of the site with an invented demo church, or by the
automated test named. Anything I didn't get to before submission says so.

## 1. Checks run, findings and how each was resolved

| Check                       | What I used                                                                                     | What it found                                                                                                               | Resolved?                                                                                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automated tests             | `python manage.py test` (Django's test runner, with Playwright driving Chromium for the browser tests) | 801 tests, all passing (31 October 2026, at `6bf1062`)                                                                | Nothing to resolve                                                                                                                                |
| Deployment settings         | `python manage.py check --deploy` with `DEBUG` off                                              | No issues. One warning is silenced on purpose: joining the browsers' HSTS preload list, which is for a domain's owner to apply for | Nothing to resolve                                                                                                                                |
| Python style                | `flake8` with a line length of 120, excluding `venv` and migrations                             | 22 findings: two unused imports, one extra blank line, one invalid escape (`\W` in a test string), 16 long lines, a variable named `l`, a lambda assigned to a name | Resolved the unused imports, the blank line and the escape in `1f2e618`. Left the 16 long lines (121 to 139 characters, mostly test data), the `l` in `ordo/utils.py` and the lambda in a test, as they don't affect behaviour. Rerun on 31 October with flake8 7.5: two files in `accounts` ended in a blank line and one import there had grown too long, all fixed in `722ffc4`; the rest as before |
| Leftover debugging          | `git grep` for `print(`, `breakpoint(`, `TODO`, `FIXME` and commented-out code, outside `venv` and migrations | None in the app. The two scripts in `tools/` print what they've done, on purpose                                     | Nothing to resolve                                                                                                                                |
| Files that shouldn't be tracked | `git ls-files`, searched for `.env`, database files, keys, `venv` and uploaded media; `git grep` for literal secret keys and passwords | None tracked. The only passwords in the code are test values and the demo church's password in `tools/`, used only for the screenshots | `*.sqlite3` added to `.gitignore` in `442ef09`, so the screenshots database can't be committed                                                    |
| HTML validation             | [W3C Nu HTML Checker](https://validator.w3.org/nu/), sent the rendered HTML of 13 pages (section 2) | 4 errors on 3 pages and 18 warnings. Two errors on Settings were real: `maxlength` and `required` on the colour picker. Two were `@view-transition`, a CSS rule the checker doesn't know yet. The warnings are all "the list role is unnecessary" | Fixed the colour picker in `7abd14c`. `@view-transition` is valid CSS, newer than the checker. The `role="list"` is deliberate: Safari stops announcing a list as a list when its bullets are removed, so the role puts that back. Rerun on 31 October over 26 pages, the 13 above and 13 added since: no new errors, and only more of the same `role="list"` warning |
| CSS validation              | [W3C CSS Validator](https://jigsaw.w3.org/css-validator/), every one of the 41 files in `static/src/`, CSS level 3 profile | 38 files with no errors. 6 errors in 3 files, all newer CSS the validator doesn't recognise yet: `@container` and `container-type` (music list), `view-transition-name` (navigation) and `@view-transition` (global styles) | Nothing to fix: each is supported by current browsers; the validator lags behind them. Rerun on 31 October for the 11 files changed or added since: no errors apart from the same two in the music list |
| JavaScript                  | [ESLint](https://eslint.org/) 8.57 with its recommended rules, for browser ES modules, over all 14 files in `static/src/js/` | No errors and no warnings                                                                                                    | Nothing to resolve. Rerun on 31 October over the same 14 files, four of them changed since: still none. The JavaScript is also exercised by the browser tests                                                                      |
| Lighthouse                  | [Lighthouse](https://developer.chrome.com/docs/lighthouse/) 12.2 in Chromium, five pages, desktop and mobile (section 3) | Accessibility 100 on every page. Best practices 96: a console error for the missing `/favicon.ico`. SEO 90: no meta description | Added a favicon in `0b642e4` and a meta description in `7b6fab4`. Performance on mobile (69 to 92) is measured on a slowed-down simulated phone; the lower scores are the longer pages, the service page and the library. Rerun on 31 October on five new or changed pages: 100 for accessibility, best practices and SEO on all of them |

## 2. HTML validation by page

| Page                    | Errors | Warnings | Notes                                                        |
| ----------------------- | ------ | -------- | ------------------------------------------------------------ |
| Sign in                 | 1      | 0        | `@view-transition` (see section 1)                           |
| Register                | 1      | 0        | `@view-transition`                                           |
| Terms                   | 0      | 1        | `role="list"`                                                |
| A term                  | 0      | 3        | `role="list"`                                                |
| A service               | 0      | 11       | `role="list"`                                                |
| Library                 | 0      | 0        |                                                              |
| A score                 | 0      | 0        |                                                              |
| Add a score             | 0      | 0        |                                                              |
| Music list              | 0      | 0        |                                                              |
| Inbox                   | 0      | 1        | `role="list"`                                                |
| Settings                | 2      | 0        | The colour picker's `maxlength` and `required`; fixed in `7abd14c` |
| Members                 | 0      | 2        | `role="list"`                                                |
| Page not found          | 0      | 0        |                                                              |
| Privacy                 | 0      | 0        | Checked 31 October, like every row below                     |
| Import                  | 0      | 0        |                                                              |
| Imports                 | 0      | 1        | `role="list"`                                                |
| Library completeness    | 0      | 2        | `role="list"`                                                |
| Hymnals                 | 0      | 2        | `role="list"`                                                |
| A hymnal                | 0      | 1        | `role="list"`                                                |
| A hymn                  | 0      | 1        | `role="list"`                                                |
| Edit a hymn             | 0      | 0        |                                                              |
| Tunes                   | 0      | 1        | `role="list"`                                                |
| Pew sheet               | 0      | 0        |                                                              |
| Templates               | 0      | 1        | `role="list"`                                                |
| Edit a template         | 0      | 1        | `role="list"` on its `<ol>`                                  |
| Propose a piece         | 0      | 0        |                                                              |

## 3. Lighthouse scores

Measured before the favicon and meta description were added, which
were the only things keeping Best practices and SEO below 100.

| Page       | Performance (desktop / mobile) | Accessibility | Best practices | SEO |
| ---------- | ------------------------------ | ------------- | -------------- | --- |
| Sign in    | 100 / 82                       | 100           | 96             | 90  |
| Terms      | 100 / 92                       | 100           | 96             | 90  |
| A service  | 99 / 69                        | 100           | 96             | 90  |
| Library    | 88 / 75                        | 100           | 96             | 90  |
| Music list | 99 / 78                        | 100           | 96             | 91  |

Measured again on 31 October, with the favicon and meta description in
place, on the pages added since and the service page, which changed
most.

| Page                 | Performance (desktop / mobile) | Accessibility | Best practices | SEO |
| -------------------- | ------------------------------ | ------------- | -------------- | --- |
| A service            | 99 / 69                        | 100           | 100            | 100 |
| Pew sheet            | 99 / 81                        | 100           | 100            | 100 |
| Library completeness | 99 / 83                        | 100           | 100            | 100 |
| A hymnal             | 99 / 91                        | 100           | 100            | 100 |
| Import               | 99 / 90                        | 100           | 100            | 100 |

## 4. Automated tests

The suite has 801 tests, run on 31 October 2026 at commit `6bf1062`;
all passed. The browser tests start a real server and use Playwright to
drive Chromium, so they cover the JavaScript as well as the Python.

| File                                      | Tests | What it covers                                                                                                     |
| ----------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| `accounts/tests.py`                       | 139   | Users, the database rules on accounts, the roles table, sign-in, sign-up, invitations, the members page, roles, removing and restoring people, ownership, reset links, changing your own password, the limits on wrong passwords and on registering, deleting your own account and deleting the church |
| `accounts/test_browser.py`                | 2     | The Copy link button, and what happens when the browser refuses the clipboard                                    |
| `comments/tests.py`                       | 33    | Adding, replying to, closing and deleting comments; the Inbox; each church's own comments, and comments kept as "A former member"                          |
| `comments/test_browser.py`                | 3     | Comment threads, deleting a comment, and closed threads as a Viewer sees them, in the browser                     |
| `core/tests.py`                           | 34    | Settings, the crest upload and processing, the crest's address, the music list arrangement and the repeat window, each church's own settings |
| `library/tests.py`                        | 116   | Scores, the library's search, filters and sorting, suitability ranking, "last sung", texts, the completeness page, returning after an edit, hymnals, hymns and their pages, joining the same hymn, hymn last sung, tunes and a tune's number in a book, each church's own library |
| `library/test_metre.py`                   | 5     | Writing a metre one way: short names, doubled verses, lines of ten or more, anything else kept as typed |
| `library/test_browser.py`                 | 11    | The score form's tag input, the library as a Viewer sees it, and the import page's file size check and disabled button, in the browser |
| `library/test_importing.py`               | 49    | Reading a spreadsheet (encodings, separators, headers, limits), checking each row, saving an import all at once, keeping and removing it, who may remove it, the Imports list, the export and its round trip |
| `ordo/tests.py`                           | 19    | Easter, the seeded data, occasion lookup by date and its endpoint, occasion keys, colours and each church's use types |
| `ordo/test_calendar.py`                   | 18    | Working out the Ordinary Form calendar, with precedence and transfers                                              |
| `ordo/test_calendar_1962.py`              | 23    | Working out the 1962 calendar                                                                                      |
| `ordo/test_calendar_data.py`              | 22    | Loading the calendar files with `load_calendar`                                                                    |
| `ordo/test_dates.py`                      | 28    | Easter and the other date rules                                                                                    |
| `ordo/test_reference.py`                  | 3     | Every day from 2020 to 2040 against the reference data                                                             |
| `planning/tests.py`                       | 81    | Terms, services, notices, slots, pieces, status, the music list, each church's own planning                        |
| `planning/test_templates.py`              | 26    | Slot templates as rows with kinds, editing them as a formset (order, remove, each name once), splitting old templates into rows, and applying them |
| `planning/test_slot_order.py`             | 8     | Moving slots and reordering them                                                                                   |
| `planning/test_remove_slot.py`            | 6     | Removing slots, asking first when they have pieces                                                                 |
| `planning/test_service_form.py`           | 3     | The service form's calendar choice                                                                                 |
| `planning/test_browser.py`                | 26    | The service page in the browser: the score picker and its suggestion groups, a hymn by book and number, a suggested hymn filling them in, a typed reference, confirming, dragging slots, changing a slot's kind, dialogs |
| `planning/test_slot_kinds.py`             | 20    | Classifying slot names, kinds on save and from templates, the migration that classified existing slots, the badge, choosing and changing a kind |
| `planning/test_reference_pieces.py`       | 33    | A piece as a score, a hymn or a reference and the rule between them, proposing each, showing them everywhere, copying hymns and the psalm into slots, the music list arrangement, a hymn's tune and its choices, the pew sheet's tune number, the first-line prompt |
| `planning/test_suggestions.py`            | 20    | What each suggestion rests on, in a fixed number of queries; groups, strength and reasons; a slot's use type; the propose page's groups; the service page's data; the voicing prompt; suggested hymns and their book |
| `planning/test_pew_sheet.py`              | 6     | Which slots a pew sheet prints, its texts and composers and the options to leave them off, and each church's own |
| `precentor_project/tests.py`              | 27    | The base template, the navigation and its wording, the Inbox count, the user menu, the 403 page, never storing signed-in pages,, the privacy page and footer, and the check on return addresses                |
| `precentor_project/test_browser.py`       | 15    | Signing in, type and control sizes, checkboxes, Settings, the user menu, page transitions and the skip link, in the browser |
| `precentor_project/test_delete_pages.py`  | 5     | Going Back to a delete page after deleting                                                                         |
| `precentor_project/test_isolation.py`     | 7     | Two complete churches: every address with an id tried as the other church, every page checked for the other church's text, and every model and route covered |
| `precentor_project/test_settings.py`      | 11    | Production settings: the secret key check, hosts, HTTPS, the cookies and the cache                                                            |
| `precentor_project/test_testing.py`       | 2     | The shared test helpers                                                                                            |

To run them, see "Running it locally" in the README.

## 5. Manual tests

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| M01  | Register a church          | Choose Register, fill in the church's name, your name, email and password twice, submit                       | Signed in on the Terms page, which shows the Getting started panel                              | Pass: registered in the browser (README Figures 2 and 3) |
| M02  | Sign in and out            | Log out from the user menu; sign in with the same email in different capitals                                 | Signed out and back at the sign-in page; then signed in again                                   | Pass: signed in by email in the browser; logging out and capitals by automated tests |
| M03  | Password reset by link     | As the owner, Members, Reset link for a member; open the link in another browser and choose a new password    | "Password saved"; the member signs in with the new password; the link no longer works           | Pass: link opened in a second browser; the full round trip by an automated test |
| M04  | Add a score                | Library, Add score; submit empty, then fill in and save                                                       | Errors beside the required fields; then the score's page                                        | Pass: errors shown in the browser (Figure 6); saving by automated tests |
| M05  | Edit a score               | On a score's page, Edit, change the title, save                                                               | The new title on the score's page and in the library                                            | Pass: automated tests (`library/tests.py`) |
| M06  | Delete a score             | On a score's page, Delete, confirm                                                                            | A confirmation page first; then the library without the score                                   | Pass: confirmation shown in the browser (Figure 7); deleting by automated tests |
| M07  | Search the library         | Type part of a title or composer in the search box                                                            | Only matching scores listed                                                                     | Pass: automated tests (`library/tests.py`) |
| M08  | Filter the library         | Choose a language, a voicing and a season                                                                     | Only scores matching all three; the counts update                                               | Pass: filtered by season in the browser (Figure 4); combined filters by automated tests |
| M09  | Create a term              | Terms, New term, fill in, save                                                                                | The term's page                                                                                 | Pass: automated tests (`planning/tests.py`) |
| M10  | Edit and delete a term     | Edit the term's name; then Delete term and confirm                                                            | The new name; then the Terms page without it                                                    | Pass: automated tests (`planning/tests.py`) |
| M11  | Add a service              | On a term, New service, pick a date                                                                           | The day's occasion is suggested from the date; saving shows the service                         | Pass: on the live site, 6 December 2026 suggested the Second Sunday of Advent |
| M12  | Edit a service             | Edit service, change the type, save                                                                           | The new type on the service page                                                                | Pass: automated tests (`planning/tests.py`) |
| M13  | Slots from a template      | On an empty service, press Mass                                                                               | The Mass slots in order                                                                         | Pass: automated tests (`planning/test_templates.py`) |
| M14  | Reorder a slot             | Move a slot down; then drag one to a new place                                                                | The new order, kept after reloading                                                             | Pass: moving and dragging by browser tests (`planning/test_browser.py`) |
| M15  | Propose a piece            | Type in a slot's search box, choose a score                                                                   | The piece listed as Proposed; suitable scores listed first                                      | Pass: browser tests and Figure 13 |
| M16  | Confirm and unconfirm      | Confirm a proposed piece; then Unconfirm                                                                      | The badge changes each time, and the service's status follows                                   | Pass: browser tests (`planning/test_browser.py`) |
| M17  | Mark a slot N/A            | Add a slot with "Not needed (N/A)" ticked                                                                     | The slot shows (N/A) and doesn't count against the service's status                             | Pass: slots marked N/A shown and not counted (Figures 11 and 12) |
| M18  | The music list             | On a term, Music list; switch between Public and Draft                                                        | Public shows confirmed pieces; Draft marks undecided slots TBC                                  | Pass: public view (Figure 14) and, on the live site, the draft view with its banner and TBC slots |
| M19  | Print the music list       | Press Print                                                                                                   | A clean page without the navigation or buttons                                                  | Not carried out before submission |
| M20  | Comment, close, delete     | Comment on a service; reply; Close; as a Conductor, delete the closed thread                                  | The thread appears in the Inbox until closed; then it's deleted                                 | Pass: browser tests (`comments/test_browser.py`) and automated tests |
| M21  | Invite and join            | As the owner, Members, Invite someone as a Librarian; open the link in another browser and join              | The link is shown once; the new person is signed in as a Librarian                              | Pass: invited and joined in two browsers |
| M22  | Change a role              | As the owner, change a member's role on the Members page                                                      | A message confirming it; the member's controls change                                           | Pass: automated tests (`accounts/tests.py`) |
| M23  | Remove a member            | As the owner, Remove a member and confirm; that member tries to sign in                                       | They're under Former members and can't sign in                                                  | Pass: removed in the browser, then listed under Former members; signing in refused by an automated test |
| M24  | Settings and crest         | Settings, change the church's name, upload a crest as a logo, save                                            | The name and crest on the music list                                                            | Pass: crest upload and processing by automated tests; uploaded on the live site on 22 October |
| M25  | A Viewer refused           | As a Viewer, open `/terms/add/`                                                                               | The "Not available to you" page (403)                                                           | Pass: in the browser (Figure 18) |
| M26  | Another church's record    | As one church, open the address of another church's score or service                                          | "Page not found" (404)                                                                          | Pass: in the browser (Figure 19) |
| M27  | Error pages                | Open an address that doesn't exist                                                                            | Precentor's own 404 page                                                                        | Pass: in the browser with `DEBUG` off (Figure 19) |
| M28  | Too many wrong passwords   | Sign in to one address with a wrong password six times                                                        | The sixth is refused with "Too many wrong passwords", even with the right password, for 15 minutes | Pass: in the browser on 26 October, and by automated tests |
| M29  | Too many registrations     | Register six churches from one network within an hour                                                         | The sixth is refused with "try again in an hour" and nothing is created | Pass: in the browser on 26 October, and by automated tests |
| M30  | Delete your own account    | As a member, Change password, Delete your account, give the password                                          | Signed out, the account gone, their comments shown as "A former member"; the owner is told to hand over first | Pass: by automated tests; the pages checked in the browser on 26 October |
| M31  | Delete the church          | As the owner, Settings, Delete this church, type its name                                                     | The page lists what will go; a wrong name is refused; the right one deletes everything and signs out | Pass: by automated tests; the page and a wrong name checked in the browser on 26 October |
| M32  | Privacy page               | Follow Privacy in the footer, signed in and out                                                                | The page explains what's kept and how to leave                       | Pass: in the browser on 26 October |
| M33  | Import a spreadsheet       | Library, Import; download the template, fill in a few rows, choose the file, Import                           | The chosen file's name and size shown; then the result page with the count, any skipped rows and why, and how many have no voicing; a notice on the Library | Pass: in the browser on 26 October (Figures 8 and 9), and by automated tests (`library/test_importing.py`) |
| M34  | Keep or remove an import   | From the notice, Review it; Keep these scores. Import again; Remove this import and confirm                    | Keeping closes the import; removing deletes its scores, keeping any already planned into a service | Pass: both pages in the browser on 26 October; a 200-row file imported and removed on the demo church, leaving the library exactly as before |
| M35  | A file that's too big      | Choose a file over 2 MB                                                                                       | Said at once, with the Import button disabled; without JavaScript the server refuses it        | Pass: in the browser on 26 October, and by browser and automated tests |
| M36  | Export the library         | Library, Export                                                                                               | A CSV named with the date, in the import's columns; it imports into an empty church unchanged  | Pass: downloaded in the browser on 26 October; the round trip by an automated test |
| M37  | A slot's kind              | Add slots called Introit, Communion hymn and Procession; then change the Introit's kind to Hymn               | Badges read Proper, Hymn and Other; after the change the badge reads Hymn with no reload, and the page keeps its place | Pass: in the browser on 30 October, and by browser and automated tests |
| M38  | Type a hymn number         | In a Hymn slot, type NEH 123 in the reference box and propose it                                             | The reference box comes first; the piece is listed as NEH 123, with no reload                  | Pass: by a browser test; the form checked in the browser at both widths on 30 October |
| M39  | Propose without JavaScript | With JavaScript off, follow Propose a piece on a Hymn slot; submit with nothing chosen, then with a reference  | Reference first, then the score list; one message for an empty form; then the service page with the piece | Pass: the page checked in the browser on 30 October; submitting by automated tests |
| M40  | Music list arrangement     | Settings, Music list arrangement: Propers beside the rest; open a term's music list, then print it             | Each service's propers in one list and the rest in another, side by side when wide, stacked on paper | Pass: in the browser on 30 October at 1280px and in a narrow column; print checked by emulating print media at A4 width, not on paper |
| M41  | Suggestions with reasons   | On an Advent service, open a Communion slot's search box; then the propose page for the same slot with JavaScript off | Groups Suggested, Suggested sung recently, Other scores; each score with its reasons; the same on the propose page | Pass: in the browser on 30 October, and by browser and automated tests |
| M42  | Repeat window              | Settings, set Sung recently means within to 1 week; reopen a slot's list                                    | A score sung two weeks ago is no longer in a "sung recently" group                              | Pass: by automated tests; the setting checked in the browser on 30 October |
| M43  | A score's text             | Edit a score, fill in Text, Translation and Translation credit, save                                         | The score's page shows the text beside the translation, with the credit beneath                 | Pass: in the browser at both widths on 30 October, and by automated tests |
| M44  | The pew sheet              | From a service, Pew sheet; untick Composers and Update; Print                                                | Confirmed music in order, the motet's text beside its translation; composers gone after Update; prints white without the controls | Pass: in the browser on 30 October; print checked by emulating print media, not on paper |
| M45  | The voicing prompt         | Plan a score that has no voicing; follow Add it and save a voicing                                           | A quiet line on the piece's row; after saving, back on the service with the line gone           | Pass: the line checked in the browser on 30 October; the return by automated tests |
| M46  | Library completeness       | Library, Completeness; follow the voicing count                                                              | Counts of scores with no voicing and no language, and the motets with no text listed; the count matches the filtered Library | Pass: in the browser on 30 October, and by automated tests |
| M47  | Hymnals                    | Library, Hymnals; add one, edit it, archive it; try to delete one with hymns sung from it | Listed with copies; archived ones apart; the delete refused with a note to archive instead | Pass: the list and form in the browser on 30 and 31 October; archiving and the refused delete by automated tests |
| M48  | A hymn by book and number  | In a Hymn slot, choose the book, type a number, propose; then open the hymn from its hymnal's page and add a first line | NEH 53 on the row, a quiet line asking for its first line until it has one; the hymnal lists it by number | Pass: proposing by a browser test; the pages in the browser on 31 October |
| M49  | The same hymn in two books | Give two hymns the same first line; on one's page answer the question both ways | Yes joins them and keeps both numbers; no isn't asked again | Pass: the question in the browser on 31 October; joining and remembering by automated tests |
| M50  | Tunes                      | Add tunes; set a hymn's tune in its book; on a hymn in a service choose another tune; open the pew sheet | The row offers the book's tune, then same-metre tunes from the book, then the rest; the sheet prints "NEH 53, tune NEH 115" | Pass: the tune row in the browser at both widths on 31 October; the sheet's wording by automated tests |
| M51  | Suggested hymns            | Tag a hymn for the season; open a Hymn slot on a service in that season; click the suggestion | The hymn listed with its reason; clicking fills in the book and number | Pass: in the browser on 31 October, and by a browser test |
| M52  | Template slots             | Edit Vespers: set Hymn's kind to Motet, swap two numbers, tick Remove on one, add a slot in a blank row, save; apply it to a service | The template lists the new order; the service's slots arrive in it, Hymn as a Motet | Pass: the form in the browser at both widths on 31 October; saving and applying by automated tests |

## 6. Responsiveness, usability and the keyboard

| ID   | Check                         | Steps                                                                       | Expected                                                             | Result   |
| ---- | ----------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------- | -------- |
| R01  | 320 pixels wide               | Every main page at 320 pixels                                               | Nothing wider than the screen except the library table, which scrolls in its own box | Fail, then fixed: the score form was 3 pixels too wide (`6bf1062`). After the fix, all 19 pages passed in Chromium, Firefox and WebKit on 31 October |
| R02  | 768 pixels wide               | The same pages at 768 pixels                                                | The layout fills the width without gaps or overlaps                  | Pass: all 19 pages in all three engines on 31 October, with no console errors |
| R03  | 1280 pixels wide              | The same pages at 1280 pixels                                               | The layout as in the README's screenshots                            | Pass: every page in the README's figures at 1280 pixels |
| R04  | Keyboard alone                | Sign in, open a service, propose and confirm a piece, using only the keyboard | Every step reachable with Tab, Enter and the arrow keys, with a visible outline on each control | Pass on 31 October, in Chromium: every step done with Tab, typing, the arrow keys and Enter. Each control had a focus outline; a term's link rings its whole card instead (Figure 25 shows the outline) |
| R05  | Dark mode                     | Switch the device to dark, then choose Dark in the user menu                | Every page readable, with the same contrast as in light              | Pass: the service page (Figure 24) and by browser tests; every other page checked by hand on 23 October |
| R06  | Without JavaScript            | Turn JavaScript off; propose a piece, confirm it, remove a slot             | Each works through ordinary pages                                    | Pass: each is an ordinary form post, covered by automated tests without JavaScript |

### Browsers and devices

On 31 October I loaded the 19 main pages (signing in, registering,
terms, a term, a service, the library, the score form, the music list,
the pew sheet, the inbox, Settings, Members, completeness, hymnals, a
hymnal, tunes, templates, import and privacy) in each browser engine
Playwright provides, at 320, 768 and 1280 pixels wide. A script looked
for anything wider than the window and for errors in the console.

| Engine   | Version tested | Stands in for                        | 320 px | 768 px | 1280 px |
| -------- | -------------- | ------------------------------------ | ------ | ------ | ------- |
| Chromium | 149            | Chrome, Edge, Samsung Internet       | Pass after `6bf1062` | Pass | Pass |
| Firefox  | 151            | Firefox                              | Pass after `6bf1062` | Pass | Pass |
| WebKit   | 26.5           | Safari on a Mac, iPhone and iPad     | Pass after `6bf1062` | Pass | Pass |

Playwright's WebKit is the engine Safari is built on, run on Windows,
not Safari itself, and none of this was on a real phone. I haven't
tested on an iPhone or an Android phone, so those rows say what the
engine does, not what a particular device does.

## 7. Bugs found and fixed

Taken from the commit history. Each was found while building or
testing, fixed, and covered by a test where it could be.

| Commit    | What was wrong and fixed                                                                  |
| --------- | ----------------------------------------------------------------------------------------- |
| `dc5550c` | A service's status treated an unconfirmed piece as not started                            |
| `47a4126` | Suitability ranking listed a score once for each of its tags                              |
| `cf60999` | The term's list of services didn't link to each service                                   |
| `3474c45` | The service delete page referred to the term instead of the service                       |
| `1bfe045` | Comment reply forms on one page shared element ids                                        |
| `c5637c1` | The score search box didn't reopen when clicked while already focused                     |
| `2599d09` | The service page's script didn't start on a service with no slots                         |
| `ce41b43` | The Not started badge was light in dark mode                                              |
| `b2c58b1` | Checkboxes were stretched full width, and fields with errors weren't marked               |
| `2412544` | The checkboxes on Settings were in the wrong order and the colour picker was too wide     |
| `a7106c6` | The open user menu was drawn behind the page                                              |
| `5b2f8ff` | Going Back after a delete reopened the delete page, which then showed "Page not found"    |
| `afe7ee3` | The planning actions could reach another church's slots and pieces by their address       |
| `f4ec027` | A comment could be added to another church's term, service or piece                       |
| `6b65a6c` | The change-password pages still had the admin's look, and nothing linked to them (fixed with `5ca663b`) |
| `e9ee61f` | On a phone, with a longer name, the user menu's panel opened off the left of the screen    |
| `6bf1062` | At 320 pixels the score form was a few pixels wider than the screen, as a fieldset won't shrink below its widest row |

**Left unfixed:** the 16 long lines, the variable `l` and the lambda
found by flake8 (see section 1). None affects how the app works.

### Known bugs

| Bug                                                                                                                                            | Effect                                                                                                         | Why it's not fixed yet                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| A signed-in site superuser who opens an invitation link is told their account "belongs to no church"                                           | Only affects the site's administrator, who has no church by design                                             | Cosmetic; the link is still refused, which is correct                                   |
| Mobile performance on the longest pages is lower: 69 for a service with ten slots and 75 for the library (section 3)                           | Those pages take longer to become usable on a slow phone                                                       | Would need the pages split or loaded in parts; not attempted before submission          |
| The browser test for confirming a piece failed once in a full run of the planning tests on 30 October, then passed in every rerun | None for people using the site; a test can fail without a real fault | Not reproduced, and which check failed wasn't captured, so there's nothing yet to fix with confidence |

## 8. Deployment check

On the live site, https://precentor.onrender.com, after each deploy.

| ID   | Check                         | Expected                                                                 | Result   |
| ---- | ----------------------------- | ------------------------------------------------------------------------ | -------- |
| D01  | The site loads                | The sign-in page, after up to a minute if the site was asleep            | Pass: the sign-in page loaded on the live site on 23 October |
| D02  | `http://` goes to `https://`  | Typing `http://precentor.onrender.com` ends on the `https://` address    | Pass: `http://precentor.onrender.com/` answered 301, to `https://precentor.onrender.com/` |
| D03  | `DEBUG` is off                | A made-up address shows Precentor's 404 page, not Django's debug page    | Pass: a made-up address answered 404 with Precentor's own page |
| D04  | Static files and the crest    | Styles, fonts and an uploaded crest all load                             | Pass: stylesheets and the favicon answered 200 from their hashed static addresses; the crest was uploaded and shown on the live site on 22 October |
| D05  | Register and plan             | Register a test church, add a score, a term and a service, propose and confirm a piece, open the music list | Pass on the live site on 23 October: registered a test church, added a score, a term and a service, applied the Mass template, proposed and confirmed a piece, and saw it on the music list |
