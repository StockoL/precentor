# Testing Precentor

This covers the automated tests, the checks I ran on the code, the
manual tests, and the bugs found along the way. Each check says what I
used, what it found and whether that's resolved.

Everything here was run again on 10 November 2026 on the code that
became the live site, between commits `61f3790` and `b500e3f`, on a
local copy of the site with the invented demo church. The manual tests
were carried out in Google Chrome 157 on Windows 11, driven by
Playwright and checked by me row by row, or by the automated test
named. Playwright's own Chromium 149 hangs on cross-document page
transitions, which real Chrome and Edge don't, so it was used only for
the automated browser tests, where every page is opened by its address.

## 1. Checks run, findings and how each was resolved

| Check | What I used | What it found on 10 November | Resolved? |
| ----- | ----------- | ---------------------------- | --------- |
| Automated tests | `python manage.py test` (Django's test runner, with Playwright driving Chromium for the browser tests) | 895 tests, all passing, at `b500e3f` (section 4) | Nothing to resolve. There were 553 at submission |
| Deployment settings | `python manage.py check --deploy` with `DEBUG` off | No issues. One warning is silenced on purpose: joining the browsers' HSTS preload list, which is for a domain's owner to apply for | Nothing to resolve |
| Migrations | `python manage.py makemigrations --check --dry-run`, and a rehearsal of the merge on a copy of the live database ([`after_assessment.md`](after_assessment.md)) | No missing migrations. On the copy, all 28 new migrations ran, `check_copied_data` found everything copied, and all 177 pages opened for every church | Nothing to resolve |
| Python style | flake8 7.4.1 with the settings in `.flake8` (line length 120, `venv` and migrations left out) | No findings | At submission: two unused imports, a blank line and an escape, fixed in `1f2e618`; more in `722ffc4`; the 16 long lines, the variable `l` and the lambda left then were cleared in `86ad9e8` |
| Leftover debugging | `git grep` for `print(`, `breakpoint(`, `TODO`, `FIXME` and commented-out code, outside `venv` and migrations | None in the app. The scripts in `tools/` print what they've done, on purpose | Nothing to resolve |
| Files that shouldn't be tracked | `git ls-files`, searched for `.env`, database files, keys, `venv` and uploaded media; `git grep` for literal secret keys and passwords | None tracked. The only passwords in the code are test values and the demo church's, used for screenshots | `*.sqlite3` added to `.gitignore` in `442ef09` |
| HTML validation | The W3C's Nu HTML Checker 26.11.9 through [`tools/validate_html.py`](../tools/validate_html.py), every page (section 2) | 74 pages, no errors. 30 warnings, all `role="list"` | The `role="list"` is deliberate (README §16). Errors fixed earlier: the Settings colour picker (`7abd14c`) and a form inside a `<span>` on the service page (`5866886`) |
| CSS validation | [W3C CSS Validator](https://jigsaw.w3.org/css-validator/), CSS level 3 profile, each of the 47 source files in `static/src/` | 42 files with no errors. 8 errors in 5 files, all CSS the validator doesn't know yet: `@container` and `container-type` (music list), `@view-transition` and its pseudo-elements (global styles and the sign-in pages' stylesheet), `view-transition-name` (navigation), and `pointer-events`, which is outside the CSS3 profile | Nothing to fix: each is supported by current browsers |
| JavaScript | [ESLint](https://eslint.org/) 8.57 with its recommended rules, for browser ES modules, over all 14 files in `static/src/js/` | No errors and no warnings | Nothing to resolve. The JavaScript is also exercised by the browser tests |
| Lighthouse | Lighthouse 12.2.1 in Chrome 157, nine pages, desktop and mobile (section 3) | Accessibility, best practices and SEO 100 on every page; performance 100 on desktop, 95 to 99 on mobile | At submission a missing favicon and meta description cost points: fixed in `0b642e4` and `7b6fab4`. Mobile speed improved in `49ec234`, `e55fd08`, `094f805` and `791158d` |
| Widths and browsers | [`tools/check_viewports.py`](../tools/check_viewports.py): 25 pages at 320, 375, 768, 1024 and 1280 pixels in Chromium, Firefox and WebKit (section 6) | 375 page loads, nothing wider than the window, no console errors | At submission the score form was 3 pixels too wide at 320, fixed in `6bf1062` |
| Text contrast | Every visible piece of text on the 25 pages, measured against its background in light and dark (row R05) | All 1,403 meet WCAG AA in both; the lowest ratios are 4.83 in light and 5.7 in dark | Nothing to resolve |

## 2. HTML validation by page

Checked on 10 November 2026 at `b500e3f`, with
[`tools/validate_html.py`](../tools/validate_html.py). It renders every
page the project's routes give, signed in as a church's owner (or signed
out, for the pages before signing in), with `DEBUG` off as on the live
site, and 13 pages that only appear after an action, such as a form with
mistakes or a deleted account. Each page went to the Nu HTML Checker
26.11.9, the W3C's own checker, run on my computer from its published
download: the [online copy](https://validator.w3.org/nu/) sits behind
Cloudflare, which kept turning the script away even at one request every
ten minutes. A new page is checked without being added to a list.

74 pages, **no errors**. The 30 warnings are all the same: "the list role
is unnecessary", on lists that keep `role="list"` on purpose (Safari stops
announcing a list as a list once its bullets are removed; README §16).
Routes that aren't HTML pages weren't sent: the crest image, three CSV
downloads, and six actions that only accept a form being posted.

Errors found by earlier runs, all fixed: the Settings colour picker's
`maxlength` and `required` (`7abd14c`), and a `<span>` holding a form in a
hymn's row on the service page (`5866886`).

| Page | Errors | Warnings | Notes |
| ---- | ------ | -------- | ----- |
| Inbox (`comments:inbox`) | 0 | 1 | `role="list"` |
| Settings (`core:site_config_update`) | 0 | 0 |  |
| Delete your account (`delete_account`) | 0 | 0 |  |
| Delete the church (`delete_church`) | 0 | 0 |  |
| Join by invitation (`join`) | 0 | 0 |  |
| Library completeness (`library:completeness`) | 0 | 2 | `role="list"` |
| A hymn (`library:hymn_detail`) | 0 | 1 | `role="list"` |
| A hymn's tune in a book (`library:hymn_entry_update`) | 0 | 0 |  |
| Import a hymnal's list (`library:hymn_import`) | 0 | 0 |  |
| A hymnal import's result (`library:hymn_import_detail`) | 0 | 0 |  |
| Edit a hymn (`library:hymn_update`) | 0 | 0 |  |
| New hymnal (`library:hymnal_create`) | 0 | 0 |  |
| Delete a hymnal (`library:hymnal_delete`) | 0 | 0 |  |
| A hymnal (`library:hymnal_detail`) | 0 | 1 | `role="list"` |
| Hymnals (`library:hymnal_list`) | 0 | 1 | `role="list"` |
| Edit a hymnal (`library:hymnal_update`) | 0 | 0 |  |
| Remove a hymnal import (`library:remove_hymn_import`) | 0 | 0 |  |
| Remove an import (`library:remove_import`) | 0 | 0 |  |
| Add a score (`library:score_create`) | 0 | 0 |  |
| Delete a score (`library:score_delete`) | 0 | 0 |  |
| A score (`library:score_detail`) | 0 | 0 |  |
| Import (`library:score_import`) | 0 | 0 |  |
| An import's result (`library:score_import_detail`) | 0 | 0 |  |
| Imports (`library:score_import_list`) | 0 | 1 | `role="list"` |
| Library (`library:score_list`) | 0 | 0 |  |
| Edit a score (`library:score_update`) | 0 | 0 |  |
| New tune (`library:tune_create`) | 0 | 0 |  |
| Tunes (`library:tune_list`) | 0 | 1 | `role="list"` |
| Edit a tune (`library:tune_update`) | 0 | 0 |  |
| Sign in (`login`) | 0 | 0 |  |
| Cancel an invitation (`members:invitation_cancel`) | 0 | 0 |  |
| An invitation's link (`members:invitation_link`) | 0 | 0 |  |
| Invite someone (`members:invite`) | 0 | 0 |  |
| Make someone the owner (`members:make_owner`) | 0 | 0 |  |
| Members (`members:member_list`) | 0 | 3 | `role="list"` |
| Remove a member (`members:remove`) | 0 | 0 |  |
| Change password (`password_change`) | 0 | 0 |  |
| Password changed (`password_change_done`) | 0 | 0 |  |
| Password saved (`password_reset_complete`) | 0 | 0 |  |
| Choose a new password (reset link) (`password_reset_confirm`) | 0 | 0 |  |
| Propose a piece (without JavaScript) (`planning:add_piece`) | 0 | 0 |  |
| New notice (`planning:marker_create`) | 0 | 0 |  |
| Delete a notice (`planning:marker_delete`) | 0 | 0 |  |
| Edit a notice (`planning:marker_update`) | 0 | 0 |  |
| New service (`planning:service_create`) | 0 | 0 |  |
| Delete a service (`planning:service_delete`) | 0 | 0 |  |
| A service (`planning:service_detail`) | 0 | 13 | `role="list"` |
| Pew sheet (`planning:service_pew_sheet`) | 0 | 0 |  |
| Edit a service (`planning:service_update`) | 0 | 0 |  |
| New template (`planning:slot_template_create`) | 0 | 1 | `role="list"` |
| Delete a template (`planning:slot_template_delete`) | 0 | 0 |  |
| Templates (`planning:slot_template_list`) | 0 | 1 | `role="list"` |
| Edit a template (`planning:slot_template_update`) | 0 | 1 | `role="list"` |
| New term (`planning:term_create`) | 0 | 0 |  |
| Delete a term (`planning:term_delete`) | 0 | 0 |  |
| A term (`planning:term_detail`) | 0 | 2 | `role="list"` |
| Terms (`planning:term_list`) | 0 | 1 | `role="list"` |
| Music list (`planning:term_music_list`) | 0 | 0 |  |
| Edit a term (`planning:term_update`) | 0 | 0 |  |
| Privacy (`privacy`) | 0 | 0 |  |
| Register (`signup`) | 0 | 0 |  |
| 404 page | 0 | 0 |  |
| 500 page | 0 | 0 |  |
| 403 page (a Viewer adding a term) | 0 | 0 |  |
| Log in, wrong password | 0 | 0 |  |
| Score form with mistakes | 0 | 0 |  |
| Join, link no longer valid | 0 | 0 |  |
| Join, already signed in | 0 | 0 |  |
| Delete my account, as a member | 0 | 0 |  |
| Reset link for a member | 0 | 0 |  |
| Use another template, asked first | 0 | 0 |  |
| Terms, a new church's first steps | 0 | 0 |  |
| Account deleted | 0 | 0 |  |
| Church deleted | 0 | 0 |  |

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

On 1 November I found why the service page scored lowest on a phone:
its layout shifted by 0.34 as it loaded, against 0 on the hymnal page.
The fallback fonts shown until the web fonts arrive were about a third
too wide, so the service's title wrapped onto two lines and then jumped
back to one, moving everything below it. With the fallbacks corrected
(`49ec234`), the mobile scores, measured twice each from a cold start,
are:

| Page      | Mobile performance, before / after | Layout shift after |
| --------- | ---------------------------------- | ------------------ |
| A service | 69 / 85 and 86                     | 0.008 (was 0.338)  |
| Library   | 75 / 89                            | 0.001              |
| Terms     | 92 / 91                            | 0                  |

That left about three seconds before anything appeared, as each of the
46 stylesheets was a request of its own. With them joined into one
(`e55fd08`), a service page makes 13 requests instead of 58, and the
same measurements give:

| Page      | Mobile performance | First contentful paint |
| --------- | ------------------ | ---------------------- |
| A service | 92 and 93          | 2.5 to 2.6 s (was 3.3) |
| Library   | 95                 | 2.4 s (was 2.9)        |
| Terms     | 96                 | 2.3 s (was 2.7)        |

Two smaller steps followed, each measured with and without (three
Lighthouse runs a page, or five timed loads) and kept only because it
helped. Preloading the two main fonts (`094f805`), which a browser
otherwise only finds once it has read the stylesheet, brought the first
paint forward by about half a second on each page. Preloading the
modules that the term and service pages' scripts import (`791158d`)
brought the term page's last script forward from 831 to 648 ms; the
service page gained only 32 ms. With both:

| Page      | Mobile performance (three runs) | First contentful paint | Layout shift |
| --------- | ------------------------------- | ---------------------- | ------------ |
| A service | 93, 95, 95                      | 2.1 s                  | 0            |
| Library   | 98, 99, 98                      | 1.7 s                  | 0            |
| Terms     | 99, 99, 99                      | 1.5 s                  | 0            |

These were measured on the development server, which doesn't compress
files; the live site sends the compressed copy whitenoise makes.

Measured again on 10 November 2026 at `b500e3f`, with Lighthouse 12.2.1
in Google Chrome 157, on the nine pages above and signed in where the page
needs it, one run each on desktop and on mobile:

| Page                 | Performance (desktop / mobile) | Accessibility | Best practices | SEO | First paint (mobile) | Layout shift |
| -------------------- | ------------------------------ | ------------- | -------------- | --- | -------------------- | ------------ |
| Sign in              | 100 / 99                       | 100           | 100            | 100 | 1.5 s                | 0            |
| Terms                | 100 / 99                       | 100           | 100            | 100 | 1.5 s                | 0            |
| A service            | 100 / 95                       | 100           | 100            | 100 | 2.0 s                | 0            |
| Library              | 100 / 99                       | 100           | 100            | 100 | 1.5 s                | 0            |
| Music list           | 100 / 96                       | 100           | 100            | 100 | 1.8 s                | 0            |
| Pew sheet            | 100 / 98                       | 100           | 100            | 100 | 1.7 s                | 0            |
| Library completeness | 100 / 99                       | 100           | 100            | 100 | 1.5 s                | 0            |
| A hymnal             | 100 / 99                       | 100           | 100            | 100 | 1.5 s                | 0            |
| Import               | 100 / 99                       | 100           | 100            | 100 | 1.5 s                | 0            |

Accessibility, best practices and SEO are 100 on every page, on both.
The service page and the music list are the longest pages, which is why
they're the slowest to fill a simulated phone's screen.

## 4. Automated tests

The suite has 895 tests, run on 10 November 2026 at commit `b500e3f`;
all passed. The browser tests start a real server and use Playwright to
drive Chromium, so they cover the JavaScript as well as the Python.

| File                                      | Tests | What it covers                                                                                                     |
| ----------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| `accounts/tests.py`                       | 141   | Users, the database rules on accounts, the roles table, sign-in, sign-up, invitations, the members page, roles, removing and restoring people, ownership, reset links, changing your own password, the limits on wrong passwords and on registering, deleting your own account and deleting the church |
| `accounts/test_browser.py`                | 2     | The Copy link button, and what happens when the browser refuses the clipboard |
| `comments/tests.py`                       | 34    | Adding, replying to, closing and deleting comments; the Inbox; each church's own comments, and comments kept as "A former member" |
| `comments/test_browser.py`                | 3     | Comment threads, deleting a comment, and closed threads as a Viewer sees them, in the browser |
| `core/tests.py`                           | 34    | Settings, the crest upload and processing, the crest's address, the music list arrangement and the repeat window, each church's own settings |
| `library/tests.py`                        | 123   | Scores, the library's search, filters and sorting, the ranking the piece picker uses, "last sung", texts, the completeness page, returning after an edit, hymnals, hymns and their pages, joining the same hymn, hymn last sung, tunes and a tune's number in a book, each church's own library, the Suitable-for filters and their menus, and a score planned for a service being kept when deleted |
| `library/test_metre.py`                   | 5     | Writing a metre one way: short names, doubled verses, lines of ten or more, anything else kept as typed |
| `library/test_browser.py`                 | 11    | The score form's tag input, the library as a Viewer sees it, and the import page's file size check and disabled button, in the browser |
| `library/test_importing.py`               | 52    | Importing from a Google Sheets link, or refusing neither or both; reading a spreadsheet (encodings, separators, headers, limits), checking each row, saving an import all at once, keeping and removing it, who may remove it, the Imports list, the export and its round trip |
| `library/test_sheets.py`                  | 8     | A Google Sheets link: the export address built from its ID and tab, every other address refused, and with Google's answer faked, CSV kept, the size limit, a sign-in page, a refusal and no connection |
| `library/test_hymn_import.py`             | 17    | A hymnal's list: reading it (a number needed, a repeated number skipped), new numbers added with their details, only blanks filled for known ones, tunes matched or added, a list that changes nothing; removing an import (sung entries and hymns in other books kept, blanks emptied unless changed since, unused tunes gone); the import, result, keep and remove pages |
| `ordo/tests.py`                           | 19    | Easter, the seeded data, occasion lookup by date and its endpoint, occasion keys, colours and each church's use types |
| `ordo/test_calendar.py`                   | 18    | Working out the Ordinary Form calendar, with precedence and transfers |
| `ordo/test_calendar_1962.py`              | 23    | Working out the 1962 calendar |
| `ordo/test_calendar_data.py`              | 22    | Loading the calendar files with `load_calendar` |
| `ordo/test_dates.py`                      | 29    | Easter and the other date rules, and the Sunday cycle |
| `ordo/test_reference.py`                  | 3     | Every day from 2020 to 2040 against the reference data |
| `ordo/test_propers.py`                    | 21    | The chants of both forms: one per part, season and year, several of a part in the order sung, loading them with the calendar, every one belonging to a day of its form, the 1962 seasons' edges and a saint's form by date, and an Ordinary Form Sunday's chant for its year, each year's own Lent Communion and each of the four Christmas Masses; the Sunday an Ordinary Form weekday borrows from, and none in Lent, late Advent, Christmas or the Easter octave |
| `planning/tests.py`                       | 81    | Terms, services, notices, slots, pieces, status, the music list, each church's own planning |
| `planning/test_templates.py`              | 26    | Slot templates as rows with kinds, editing them as a formset (order, remove, each name once), splitting old templates into rows, and applying them |
| `planning/test_slot_order.py`             | 8     | Moving slots and reordering them |
| `planning/test_remove_slot.py`            | 6     | Removing slots, asking first when they have pieces |
| `planning/test_service_form.py`           | 3     | The service form's calendar choice |
| `planning/test_browser.py`                | 27    | The service page in the browser: the score picker and its suggestion groups, a hymn by book and number, a suggested hymn filling them in, the day's chant proposed in one click, a typed reference, confirming, dragging slots, changing a slot's kind, dialogs |
| `planning/test_slot_kinds.py`             | 23    | Classifying slot names, kinds on save and from templates, the migrations that classified existing slots (and later Sequences and Responsories), the badge, choosing and changing a kind, and a slot named Canticle |
| `planning/test_reference_pieces.py`       | 34    | A piece as a score, a hymn or a reference and the rule between them, proposing each, showing them everywhere, copying hymns and the psalm into slots, the music list arrangement, a hymn's tune and its choices, the pew sheet's tune number, the first-line prompt |
| `planning/test_suggestions.py`            | 20    | What each suggestion rests on, in a fixed number of queries; groups, strength and reasons; a slot's use type; the propose page's groups; the service page's data; the voicing prompt; suggested hymns and their book |
| `planning/test_propers.py`                | 15    | The day's chants on a slot: which part, Alleluia or Tract by date, not once proposed, not for other slots; several in order, each going once proposed in a slot of the same kind; Sequence slots; Palm Sunday's antiphons, the Vigil's Alleluia and Tracts in each form's order, and an Ember Saturday's graduals from the loaded data; an Ordinary Form weekday offered the Sunday before's chants, a 1962 one with no occasion nothing; the propose page's own form, and an Alleluia or Tract slot on a weekday with no occasion |
| `planning/test_pew_sheet.py`              | 6     | Which slots a pew sheet prints, its texts and composers and the options to leave them off, and each church's own |
| `planning/test_check_copied_data.py`     | 5     | The check run after the merge: it passes when hymns, the psalm and template slots were copied, fails on a missing hymn or psalm or a template whose rows differ, names churches that had hidden hymns, and changes nothing |
| `precentor_project/tests.py`              | 28    | The base template, the navigation and its wording, the Inbox count, the user menu, the 403 page, never storing signed-in pages, the 500 page, the privacy page and footer, and the check on return addresses |
| `precentor_project/test_scripts.py`       | 2     | Every module a page's scripts import is on the page or preloaded |
| `precentor_project/test_css.py`           | 6     | The one stylesheet: built from every CSS source as it is now, the layers declared first, and the only one pages link, and printing hiding the navigation, the controls and the footer |
| `precentor_project/test_browser.py`       | 15    | Signing in, type and control sizes, checkboxes, Settings, the user menu, page transitions and the skip link, in the browser |
| `precentor_project/test_delete_pages.py`  | 5     | Going Back to a delete page after deleting |
| `precentor_project/test_isolation.py`     | 7     | Two complete churches: every address with an id tried as the other church, every page checked for the other church's text, and every model and route covered |
| `precentor_project/test_settings.py`      | 11    | Production settings: the secret key check, hosts, HTTPS, the cookies and the cache |
| `precentor_project/test_testing.py`       | 2     | The shared test helpers |

To run them, see "Running it locally" in the README.

## 5. Manual tests

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| M01  | Register a church          | Choose Register, fill in the church's name, your name, email and password twice, submit                       | Signed in on the Terms page, which shows the Getting started panel                              | Pass: registered a church and landed on Terms with the Getting started panel |
| M02  | Sign in and out            | Log out from the user menu; sign in with the same email in different capitals                                 | Signed out and back at the sign-in page; then signed in again                                   | Pass: Log out led to the sign-in page; signing in again with the address in capitals worked |
| M03  | Password reset by link     | As the owner, Members, Reset link for a member; open the link in another browser and choose a new password    | "Password saved"; the member signs in with the new password; the link no longer works           | Pass: the link opened in a second browser; "Password saved"; the member signed in with the new password; the link then said "This reset link no longer works" |
| M04  | Add a score                | Library, Add score; submit empty, then fill in and save                                                       | Errors beside the required fields; then the score's page                                        | Pass: the browser's own check stops an empty form first ("Please fill in this field"); sent without it, the server marks the title and composer as required beside each (Test figure 1); filled in, the score's page |
| M05  | Edit a score               | On a score's page, Edit, change the title, save                                                               | The new title on the score's page and in the library                                            | Pass: the new title on the score's page, and found by the Library's search |
| M06  | Delete a score             | On a score's page, Delete, confirm                                                                            | A confirmation page first; then the library without the score                                   | Pass: a confirmation page first (Test figure 2); then the Library without the score |
| M07  | Search the library         | Type part of a title or composer in the search box                                                            | Only matching scores listed                                                                     | Pass: "byrd" listed only Byrd's three scores; "ave" the three whose titles begin Ave |
| M08  | Filter the library         | Choose a language, a voicing and a season                                                                     | Only scores matching all three; the counts update                                               | Fail, then fixed (`89073e1`, `f15b70c`): there was no season control on the Library. Now Latin, SATB and Advent chosen from the menus list only Canite tuba, the one Advent score that is both, and the menus keep the choices |
| M09  | Create a term              | Terms, New term, fill in, save                                                                                | The term's page                                                                                 | Pass: the new term's page (the calendar has to be chosen; nothing is assumed) |
| M10  | Edit and delete a term     | Edit the term's name; then Delete term and confirm                                                            | The new name; then the Terms page without it                                                    | Pass: the new name; after Delete term and confirming, the Terms page without it |
| M11  | Add a service              | On a term, New service, pick a date                                                                           | The day's occasion is suggested from the date; saving shows the service                         | Pass: for 6 December the form offered "Second Sunday of Advent" with Set as occasion; one click set it, and the saved service shows it |
| M12  | Edit a service             | Edit service, change the type, save                                                                           | The new type on the service page                                                                | Pass: the heading changed from Sung Mass to Solemn Mass, with the date |
| M13  | Slots from a template      | On an empty service, press Mass                                                                               | The Mass slots in order                                                                         | Pass: the Mass template's ten slots, in order |
| M14  | Reorder a slot             | Move a slot down; then drag one to a new place                                                                | The new order, kept after reloading                                                             | Pass: Move down put the Introit below the Kyrie, kept after reloading. Dragging: by the browser test `test_dragging_a_slot_by_its_handle`, and by me by hand in Chrome (Playwright can't start a native drag in Chrome) |
| M15  | Propose a piece            | Type in a slot's search box, choose a score                                                                   | The piece listed as Proposed; suitable scores listed first                                      | Pass: typing "Ave" listed the matching scores; choosing one listed it as Proposed with no reload. Suitable scores first: see M41 |
| M16  | Confirm and unconfirm      | Confirm a proposed piece; then Unconfirm                                                                      | The badge changes each time, and the service's status follows                                   | Pass: Not started; on Confirm the badge read Confirmed and the service In progress; on Unconfirm the badge read Proposed, and the service stayed In progress as a piece is still proposed |
| M17  | Mark a slot N/A            | Add a slot with "Not needed (N/A)" ticked                                                                     | The slot shows (N/A) and doesn't count against the service's status                             | Pass: the slot read "Extra motet (N/A)" and didn't count against the status |
| M18  | The music list             | On a term, Music list; switch between Public and Draft                                                        | Public shows confirmed pieces; Draft marks undecided slots TBC                                  | Pass: the public list showed no TBC, and services with nothing decided "Nothing to display yet"; the draft had its banner and marked 31 slots TBC |
| M19  | Print the music list       | Press Print                                                                                                   | A clean page without the navigation or buttons                                                  | Fail, then fixed (`61f3790`): the footer's Privacy link printed at the end. Since the fix, Chrome's printed PDF has no navigation, controls or footer (Test figure 3) |
| M20  | Comment, close, delete     | Comment on a service; reply; Close; as a Conductor, delete the closed thread                                  | The thread appears in the Inbox until closed; then it's deleted                                 | Pass: the reply showed under the comment; the thread was in the Inbox while open and gone once closed; then deleted |
| M21  | Invite and join            | As the owner, Members, Invite someone as a Librarian; open the link in another browser and join              | The link is shown once; the new person is signed in as a Librarian                              | Pass: the link was shown once (reloading its page doesn't show it again); in another browser the new person joined as a Librarian, offered Add score but refused New term |
| M22  | Change a role              | As the owner, change a member's role on the Members page                                                      | A message confirming it; the member's controls change                                           | Pass: "Lina Librarian is now a Viewer."; that member was no longer offered Add score |
| M23  | Remove a member            | As the owner, Remove a member and confirm; that member tries to sign in                                       | They're under Former members and can't sign in                                                  | Pass: listed under Former members; signing in refused; brought back with Restore |
| M24  | Settings and crest         | Settings, change the church's name, upload a crest as a logo, save                                            | The name and crest on the music list                                                            | Pass: the new name and the uploaded crest on the music list |
| M25  | A Viewer refused           | As a Viewer, open `/terms/add/`                                                                               | The "Not available to you" page (403)                                                           | Pass: "Not available to you", status 403 (Test figure 4) |
| M26  | Another church's record    | As one church, open the address of another church's score or service                                          | "Page not found" (404)                                                                          | Pass: status 404 for another church's score (the local server runs with `DEBUG` on, so the page itself is checked in M27) |
| M27  | Error pages                | Open an address that doesn't exist                                                                            | Precentor's own 404 page                                                                        | Pass: Precentor's own 404 page with `DEBUG` off (Test figure 5) |
| M28  | Too many wrong passwords   | Sign in to one address with a wrong password six times                                                        | The sixth is refused with "Too many wrong passwords", even with the right password, for 15 minutes | Pass: the sixth wrong try said "Too many wrong passwords for this address. Wait 15 minutes…", and the right password was refused too |
| M29  | Too many registrations     | Register six churches from one network within an hour                                                         | The sixth is refused with "try again in an hour" and nothing is created | Pass: the sixth registration from one network within the hour was refused: "Please try again in an hour" |
| M30  | Delete your own account    | As a member, Change password, Delete your account, give the password                                          | Signed out, the account gone, their comments shown as "A former member"; the owner is told to hand over first | Pass: "Your account has been deleted"; their comment now reads "A former member"; signing in refused; the owner opening the page is told to hand over ownership first |
| M31  | Delete the church          | As the owner, Settings, Delete this church, type its name                                                     | The page lists what will go; a wrong name is refused; the right one deletes everything and signs out | Pass: the page listed what goes; a wrong name was refused; the right name deleted the church, and Terms then led to the sign-in page |
| M32  | Privacy page               | Follow Privacy in the footer, signed in and out                                                                | The page explains what's kept and how to leave                       | Pass: the Privacy link in the footer, signed in and signed out |
| M33  | Import a spreadsheet       | Library, Import; download the template, fill in a few rows, choose the file, Import                           | The chosen file's name and size shown; then the result page with the count, any skipped rows and why, how many have no voicing, and a list of the scores imported with their composer, voicing and language; a notice on the Library | Fail, then fixed (`f4e842b`): the result page asked "Happy with these?" without listing the scores. Since: the file's name and size shown on choosing it; the result page counts what was imported and skipped and how many have no voicing, then lists each score imported with its composer, voicing and language, "(unspecified)" where empty (Test figure 6); a notice on the Library |
| M34  | Keep or remove an import   | From the notice, Review it; Keep these scores. Import again; Remove this import and confirm                    | Keeping closes the import; removing deletes its scores, keeping any already planned into a service | Pass: Keep closed the import and the notice went; Remove asked first and took its scores away. A score already planned being kept: by `test_a_score_already_planned_is_kept_and_the_page_says_so` |
| M35  | A file that's too big      | Choose a file over 2 MB                                                                                       | Said at once, with the Import button disabled; without JavaScript the server refuses it        | Pass: with JavaScript, "big.csv is 2.0 MB, more than the 2.0 MB limit" and Import disabled; without, the server refused it: "The file is larger than 2 MB" |
| M36  | Export the library         | Library, Export                                                                                               | A CSV named with the date, in the import's columns; it imports into an empty church unchanged  | Pass: `precentor-library-2026-11-10.csv` in the import's columns; imported into a new, empty church and exported again, the two files were identical |
| M37  | A slot's kind              | Add slots called Introit, Communion hymn and Procession; then change the Introit's kind to Hymn               | Badges read Proper, Hymn and Other (a procession is no kind of its own); after the change the badge reads Hymn with no reload, and the page keeps its place | Pass: badges Proper, Hymn and Other; Change kind made the Introit's badge Hymn with no reload |
| M38  | Type a hymn number         | In a Hymn slot, type NEH 123 in the reference box and propose it                                             | The book and number, then the reference box, come before the score search; the piece is listed as NEH 123, with no reload                  | Pass: the book and number, then the reference box, then the score search; "NEH 123" proposed and listed with no reload |
| M39  | Propose without JavaScript | With JavaScript off, follow Propose a piece on a Hymn slot; submit with nothing chosen, then with a reference  | Book and number, then the reference, then the score list; one message for an empty form; then the service page with the piece | Pass: book, number, reference, then the score list; an empty form said "Choose one: a score, a hymn number or a reference."; Psalm 150 was proposed and the service shown |
| M40  | Music list arrangement     | Settings, Music list arrangement: Propers beside the rest; open a term's music list, then print it             | Each service's propers in one list and the rest in another, side by side when wide, stacked on paper | Pass: in the single-column layout the propers and the rest sit side by side on screen and stack when printed at A4 width; in newspaper columns, which are narrow, they stack |
| M41  | Suggestions with reasons   | On an Advent service, open a Communion slot's search box; then the propose page for the same slot with JavaScript off | Groups Suggested, Suggested sung recently, Other scores; each score with its reasons; the same on the propose page | Pass: Suggested (each with its reasons, such as "For Advent; Already planned this term"), Other scores, and Other scores, sung recently; the same groups on the propose page |
| M42  | Repeat window              | Settings, set Sung recently means within to 1 week; reopen a slot's list                                    | A score sung two weeks ago is no longer in a "sung recently" group                              | Pass: at 8 weeks the scores sung 4 weeks ago were in the "sung recently" group; at 1 week, none were |
| M43  | A score's text             | Edit a score, fill in Text, Translation and Translation credit, save                                         | The score's page shows the text beside the translation, with the credit beneath                 | Pass: the score's page showed the text beside the translation, with the credit beneath |
| M44  | The pew sheet              | From a service, Pew sheet; untick Composers and Update; Print                                                | Confirmed music in order, the motet's text beside its translation; composers gone after Update; prints white without the controls | Pass: the confirmed music in order, with the Ave Maria's Latin beside its English (Test figure 7); composers gone after unticking and Update, with the choices in the address; printing as in M19 |
| M45  | The voicing prompt         | Plan a score that has no voicing; follow Add it and save a voicing                                           | A quiet line on the piece's row; after saving, back on the service with the line gone           | Pass: "No voicing recorded yet. Add it" on the row; after saving a voicing, back on the service with the line gone |
| M46  | Library completeness       | Library, Completeness; follow the voicing count                                                              | Counts of scores with no voicing and no language, and the motets with no text listed; the count matches the filtered Library | Pass: "2 scores with no voicing", and the Library that link opens lists 2 scores |
| M47  | Hymnals                    | Library, Hymnals; add one, edit it, archive it; try to delete one with hymns sung from it | Listed with copies; archived ones apart; the delete refused with a note to archive instead | Pass: added, edited and archived (then listed under Archived); deleting the hymnal sung from was refused with "Archive it instead" (Test figure 8) |
| M48  | A hymn by book and number  | In a Hymn slot, choose the book, type a number, propose; then open the hymn from its hymnal's page and add a first line | NEH 53 on the row, a quiet line asking for its first line until it has one; the hymnal lists it by number | Pass: SAH 99 on the row with "No first line recorded yet" until one was added; the hymnal's page lists 99 with its line |
| M49  | The same hymn in two books | Give two hymns the same first line; on one's page answer the question both ways | Yes joins them and keeps both numbers; no isn't asked again | Pass: the question was asked; after No it wasn't asked again on either hymn; after Yes the hymn's page lists both SAH 14 and SAH 16 |
| M50  | Tunes                      | Add tunes; set a hymn's tune in its book; on a hymn in a service choose another tune; open the pew sheet | The row offers the book's tune, then same-metre tunes from the book, then the rest; the sheet prints "NEH 53, tune NEH 115" | Pass: the row offered Its usual tune, Same metre in SAH, then Other tunes, and "8.7.8.7" matched "87 87"; the pew sheet printed "SAH 12, tune SAH 11" |
| M51  | Suggested hymns            | Tag a hymn for the season; open a Hymn slot on a service in that season; click the suggestion | The hymn listed with its reason; clicking fills in the book and number | Pass: with SAH 16 tagged for Advent, an Advent Vespers' Hymn slot suggested it; clicking filled in SAH and 16 |
| M52  | Template slots             | Edit Vespers: set Hymn's kind to Motet, swap two numbers, tick Remove on one, add a slot in a blank row, save; apply it to a service | The template lists the new order; the service's slots arrive in it, Hymn as a Motet | Pass: the template listed Hymn (as a Motet), Psalms, Magnificat, Te Deum; a service given it got those slots and kinds |
| M53  | The day's chant (1962)     | On a 1962 service for the Second Sunday of Advent with the Mass template, look at the Gradual; click the chant; then open the Communion's propose page with JavaScript off | "For this day: Ex Sion species decoris ejus" under the search box; one click proposes it and it goes; the propose page offers "Propose Jerusalem, surge et sta" | Pass: "Ex Sion species decoris ejus" under the Gradual; one click proposed it and it was no longer offered; the Communion's propose page offered "Propose Jerusalem, surge et sta" |
| M54  | Import from Google Sheets  | Library, Import; paste the link of Google's public example sheet and Import; then a link to a sheet that doesn't exist | The first comes back from Google and is refused for having no Title column; the second says the sheet isn't shared or the link is wrong | Pass: Google's example sheet: "The file has no Title or Composer surname column…"; a sheet that doesn't exist: "Google didn't send the sheet, so either it isn't shared or the link is wrong…" |
| M55  | Import a hymnal's list     | On a hymnal's page, Import a list; import a file of made-up rows with one row missing its number and an extra column | The result page counts what was added and the new tune, names the skipped row and the column left out; the hymnal page shows the new numbers and a notice to review the import | Pass: 2 hymns added and 1 new tune; row 3 skipped for having no number; the Notes column left out; the hymnal's page lists 20 and 21 with a notice to review the import |
| M56  | The day's chant, Ordinary Form | On the demo church's Sung Mass for the First Sunday of Advent 2026, look at each slot | The Introit, Gradual, Alleluia, Offertory and Communion offer Ad te levavi, Universi, Ostende nobis, Ad te Domine levavi and Dominus dabit benignitatem; the Ordinary's slots offer nothing | Pass: Ad te levavi, Universi, qui te exspectant, Ostende nobis, Ad te Domine levavi and Dominus dabit benignitatem; nothing on the Ordinary's slots |
| M57  | Days with more to sing     | On 1962 services for Palm Sunday, Good Friday, the Easter Vigil, the Ember Saturday of Lent, Candlemas and All Souls, and an Ordinary Form Good Friday, add Antiphon, Hymn, Responsory, Canticle and Proper slots | Each slot offers the day's chants of its kind in the order sung: Palm Sunday's ten antiphons, the Vigil's Alleluia before its Tract in 1962, the Ember Saturday's four graduals, then Benedictus es and the Tract; no Introit on Good Friday; Dies irae on All Souls | Fail, then fixed (`c5a8833`): a slot named Canticle became Other and missed the Ember Saturday's Benedictus es. Since: Palm Sunday's ten antiphons in order, the Vigil's Confitemini Domino before Laudate Dominum, the four graduals, Benedictus es and the Tract, no Introit on Good Friday in either form, Dies irae on All Souls |
| M58  | A weekday, Ordinary Form   | Services with no occasion on Wednesday 9 December 2026, Friday 18 December 2026, Tuesday 9 February 2027, Tuesday 2 March 2027 and Tuesday 6 April 2027; look at the Introit and Communion | The Sunday before's chants (Populus Sion; Venite, adoremus; Quasi modo), and nothing on 18 December or in Lent | Fail, then fixed (`945b43f`): the services on 9 December, 9 February and 6 April were server errors. Since: Populus Sion; Venite, adoremus; Quasi modo; and nothing on 18 December or 2 March |

### Screenshots for the manual tests

Taken on 10 November 2026 at `b500e3f` by
[`tools/take_test_screenshots.py`](../tools/take_test_screenshots.py),
in Chromium at 1280 pixels, from the invented demo church.

![The Add score form sent empty, with This field is required under Title and under Composer surname](screenshots/testing/m04-score-form-errors.png)

_Test figure 1. M04: an empty score form as the server answers it, each required field marked. The browser's own check, which comes first, was turned off for the picture._

![The page asking whether to delete Parsons' Ave Maria, with Delete and Cancel buttons](screenshots/testing/m06-delete-confirmation.png)

_Test figure 2. M06: deleting asks first._

![The Advent music list as printed: the church's crest and name, the services in three columns, and no navigation, buttons or footer](screenshots/testing/m19-music-list-print.png)

_Test figure 3. M19: the music list with the print styles, after the fix. Chrome's own printout is the [PDF](screenshots/testing/m19-music-list.pdf), four A4 pages._

![The Not available to you page shown to a Viewer who opens New term, with a Go to Terms button](screenshots/testing/m25-forbidden.png)

_Test figure 4. M25: a Viewer refused, with the reason._

![Precentor's Page not found page, with a Go to Terms button](screenshots/testing/m27-not-found.png)

_Test figure 5. M27: the 404 page, with DEBUG off as on the live site._

![An import's result page: 1 score imported, one row skipped for having no title, 1 with no voicing yet, a table listing Christus factus est by Anerio with no voicing, and buttons to keep or remove the import](screenshots/testing/m33-import-result.png)

_Test figure 6. M33: what an import brought in, listed, and what it skipped._

![The pew sheet for the First Sunday of Advent, with the Ave Maria's Latin text beside its English translation](screenshots/testing/m44-pew-sheet.png)

_Test figure 7. M44: the pew sheet, with a motet's text beside its translation._

![The Hymnals page listing St Aelred's Hymn Book with its copies and filing location](screenshots/testing/m47-hymnals.png)

_Test figure 8. M47: the Hymnals page._

## 6. Responsiveness, usability and the keyboard

Run on 10 November 2026 between `f15b70c` and `b500e3f`. R01 to R03 by
[`tools/check_viewports.py`](../tools/check_viewports.py), the rest in
Google Chrome 157.

| ID   | Check | Steps | Expected | Result |
| ---- | ----- | ----- | -------- | ------ |
| R01  | Phones: 320 and 375 pixels | Every main page at each width, in Chromium, Firefox and WebKit | Nothing wider than the screen except the library table, which scrolls in its own box; no console errors | Pass: all 25 pages at both widths in all three engines (Test figures 9 to 12). At submission the score form was 3 pixels too wide at 320, fixed in `6bf1062` |
| R02  | Tablets: 768 and 1024 pixels | The same pages at each width | The layout fills the width without gaps or overlaps; no console errors | Pass: all 25 pages in all three engines (Test figure 13) |
| R03  | Laptop: 1280 pixels | The same pages | The layout as in the README's screenshots; no console errors | Pass: all 25 pages in all three engines (Test figure 14); the README's figures were taken again on the same code |
| R04  | Keyboard alone | Sign in, open a service, propose and confirm a piece, using only the keyboard | Every step reachable with Tab, Enter and the arrow keys, with a visible outline on each control | Pass: signed in, opened Advent 2026 and its Midnight Mass, chose Mozart's Ave verum corpus with the arrow keys, proposed and confirmed it, using only Tab, typing, the arrow keys and Enter. Every control showed an outline (a term's card is outlined as a whole), and after Confirm the focus stayed on the button, now reading Unconfirm (Test figure 15) |
| R05  | Dark mode | Switch the device to dark, then choose Dark in the user menu | Every page readable, with the same contrast as in light | Pass: every visible piece of text on the 25 pages measured against its background, 1,403 in each theme: all meet WCAG AA, the lowest ratio 4.83 in light and 5.7 in dark. Dark chosen in the user menu on a light device applied at once and carried to the next page (Test figures 16 to 18) |
| R06  | Without JavaScript | Turn JavaScript off; propose a piece, confirm it, remove a slot | Each works through ordinary pages | Pass: Sicut cervus proposed from the propose page; after Confirm and a fresh load it read Confirmed; Remove asked first on a page of its own, and the slot went |

### Widths and browsers

[`tools/check_viewports.py`](../tools/check_viewports.py) opened each of
the 25 main pages at five widths in each of Playwright's three browser
engines, 375 loads in all, and looked for anything that made the page
scroll sideways and for errors in the console. The 404 page was rendered
with `DEBUG` off, as on the live site.

| Engine   | Version       | Stands in for                    |
| -------- | ------------- | -------------------------------- |
| Chromium | 149.0.7827.55 | Chrome, Edge, Samsung Internet   |
| Firefox  | 151.0         | Firefox                          |
| WebKit   | 26.5          | Safari on a Mac, iPhone and iPad |

Every page passed at every width in all three engines:

| Page | 320 px | 375 px | 768 px | 1024 px | 1280 px |
| ---- | ------ | ------ | ------ | ------- | ------- |
| Sign in | Pass | Pass | Pass | Pass | Pass |
| Register | Pass | Pass | Pass | Pass | Pass |
| Privacy | Pass | Pass | Pass | Pass | Pass |
| Terms | Pass | Pass | Pass | Pass | Pass |
| A term | Pass | Pass | Pass | Pass | Pass |
| A service | Pass | Pass | Pass | Pass | Pass |
| Propose a piece | Pass | Pass | Pass | Pass | Pass |
| Pew sheet | Pass | Pass | Pass | Pass | Pass |
| Music list | Pass | Pass | Pass | Pass | Pass |
| Library | Pass | Pass | Pass | Pass | Pass |
| A score | Pass | Pass | Pass | Pass | Pass |
| Add a score | Pass | Pass | Pass | Pass | Pass |
| Completeness | Pass | Pass | Pass | Pass | Pass |
| Import | Pass | Pass | Pass | Pass | Pass |
| Imports | Pass | Pass | Pass | Pass | Pass |
| Hymnals | Pass | Pass | Pass | Pass | Pass |
| A hymnal | Pass | Pass | Pass | Pass | Pass |
| A hymn | Pass | Pass | Pass | Pass | Pass |
| Tunes | Pass | Pass | Pass | Pass | Pass |
| Templates | Pass | Pass | Pass | Pass | Pass |
| Edit a template | Pass | Pass | Pass | Pass | Pass |
| Inbox | Pass | Pass | Pass | Pass | Pass |
| Settings | Pass | Pass | Pass | Pass | Pass |
| Members | Pass | Pass | Pass | Pass | Pass |
| Not found (404) | Pass | Pass | Pass | Pass | Pass |

Playwright's WebKit is the engine Safari is built on, run on Windows,
not Safari itself. The manual tests used Google Chrome 157.

![A service page at 320 pixels in Chromium: the heading, its buttons and the first slot fitting the width](screenshots/testing/r01-320-service-chromium.png)

_Test figure 9. R01: a service at 320 pixels in Chromium._

![The same service page at 320 pixels in Firefox](screenshots/testing/r01-320-service-firefox.png)

_Test figure 10. R01: the same in Firefox._

![The same service page at 320 pixels in WebKit](screenshots/testing/r01-320-service-webkit.png)

_Test figure 11. R01: the same in WebKit, the engine Safari uses._

![The library at 320 pixels, its filters stacked and the table scrolling inside its own box](screenshots/testing/r01-320-library-chromium.png)

_Test figure 12. R01: the library at 320 pixels; only the table scrolls sideways._

![A service page at 768 pixels](screenshots/testing/r02-768-service-chromium.png)

_Test figure 13. R02: a service at 768 pixels._

![The library at 1280 pixels, with the search box and the Language, Voicing, Season and Use menus in one row above the table](screenshots/testing/r03-1280-library-chromium.png)

_Test figure 14. R03: the library at 1280 pixels._

![The Terms page after pressing Tab three times, with an outline round the Terms link and round the first term's card](screenshots/testing/r04-keyboard-focus.png)

_Test figure 15. R04: keyboard focus, shown round the link and the card it's in._

![A service page in dark colours](screenshots/testing/r05-dark-service.png)

_Test figure 16. R05: a service in dark mode._

![The music list in dark colours, with the liturgical colours lightened](screenshots/testing/r05-dark-music-list.png)

_Test figure 17. R05: the music list in dark mode._

![The Settings page in dark colours](screenshots/testing/r05-dark-settings.png)

_Test figure 18. R05: Settings in dark mode._

### Real devices

These are checked by me on the live site after the deploy, on my own
phone and tablet: signing in, Terms, a service, the library, the music
list and the pew sheet.

| Device | Browser | Width | What was checked | Result | Screenshot |
| ------ | ------- | ----- | ---------------- | ------ | ---------- |
|        |         |       |                  |        |            |
|        |         |       |                  |        |            |

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
| `a8194bf` | A site superuser opening an invitation link was told their account "belongs to no church" |
| `49ec234` | The fallback fonts were about a third too wide, so the page jumped as the web fonts loaded |
| `e55fd08` | Each page made 46 requests for its CSS before it could be drawn; now one stylesheet |
| `5c8e834` | Deleting a church that had sung any hymns failed with a server error, as each hymn's entry protected its hymnal |
| `8ba3c31` | Good Friday and the Easter Vigil were offered Palm Sunday's chants, Palm Sunday's Tract was missing, and All Souls had no Dies irae |
| `af995ac` | The sign-in pages each showed an HTML validation error, from a `<style>` block the checker couldn't read |
| `2fda28f` | A server error showed Django's bare "Server Error (500)", with no stylesheet and no way back |
| `5866886` | On the service page a hymn's tune form sat inside a `<span>`, which the HTML validator refused |
| `61f3790` | The footer's Privacy link printed at the end of the music list and the pew sheet (row M19) |
| `945b43f` | An Ordinary Form weekday service with no occasion, borrowing the Sunday before's chants, was a server error when it had an Alleluia or Tract slot (row M58) |
| `c5a8833` | A slot named Canticle was given the kind Other, so it was never offered the day's canticle (row M57) |
| `89073e1`, `f15b70c` | The Library had no season, use or occasion filter, though the README and row M08 said it had; a season in its address only reordered the list |
| `f4e842b` | An import's result page asked "Happy with these?" without listing the scores it had brought in (row M33); tests in `0398cc3` |

The flake8 findings left at submission (16 long lines, a variable named
`l` and a lambda) were cleared in `86ad9e8`. No fault found in the app is left unfixed;
the two known issues below are in a test and in the testing browser.

### Known bugs

| Bug                                                                                                                                            | Effect                                                                                                         | Why it's not fixed yet                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| The browser test for confirming a piece failed once in a full run of the planning tests on 30 October | None for people using the site; a test can fail without a real fault | Not reproduced: on 1 November it passed 20 runs on its own and 6 runs of all the planning browser tests, as it has in every full run since. It passed again in the full run of 10 November. If it fails again, the traceback names the line |
| Playwright's own Chromium (149) stops drawing after any cross-document page transition, so a click from one page to the next leaves the old page on screen | None for people using the site: Chrome 157 and Edge 157 cross-fade and draw normally | A fault in the testing browser, not the site, so the manual tests were run in Google Chrome. The automated browser tests, which mostly work within one page, pass in it |

## 8. Deployment check

On the [live site](https://precentor.onrender.com), after each deploy.
The merge of the work since submission is rehearsed in
[`after_assessment.md`](after_assessment.md); its last column is filled
in once that deploy is done.

| ID | Check | Expected | At the first deploy, 23 October | After the merge |
| -- | ----- | -------- | ------------------------------- | --------------- |
| D01 | The site loads | The sign-in page, after up to a minute if the site was asleep | Pass: the sign-in page loaded on the live site on 23 October |  |
| D02 | `http://` goes to `https://` | Typing `http://precentor.onrender.com` ends on the `https://` address | Pass: `http://precentor.onrender.com/` answered 301, to `https://precentor.onrender.com/` |  |
| D03 | `DEBUG` is off | A made-up address shows Precentor's 404 page, not Django's debug page | Pass: a made-up address answered 404 with Precentor's own page |  |
| D04 | Static files and the crest | Styles, fonts and an uploaded crest all load | Pass: stylesheets and the favicon answered 200 from their hashed static addresses; the crest was uploaded and shown on the live site on 22 October |  |
| D05 | Register and plan | Register a test church, add a score, a term and a service, propose and confirm a piece, open the music list | Pass on the live site on 23 October: registered a test church, added a score, a term and a service, applied the Mass template, proposed and confirmed a piece, and saw it on the music list |  |
| D06 | The build | Render's build log shows the 28 new migrations applied, `load_calendar` loading the chants, then "Your service is live" | Not part of the first deploy |  |
| D07 | The copied data | `python manage.py check_copied_data`, run from my computer against the live database, ends "Everything was copied" | Not part of the first deploy |  |
| D08 | The pages added since | Hymnals, a hymnal, the pew sheet, the completeness page, the template editor, the Library's Season and Use menus, and a Proper slot offering the day's chant all open and work | Not part of the first deploy |  |
| D09 | Real devices | The checks in the table at the end of section 6, on my phone and tablet | Not part of the first deploy |  |
