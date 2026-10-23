# Testing Precentor

This covers the automated tests, the checks I ran on the code, the
manual tests, and the bugs found along the way. Each check says what I
used, what it found and whether that's resolved. The manual tests were
carried out on 23 October 2026, in Chromium through Playwright on a
local copy of the site with an invented demo church, or by the
automated test named; anything not yet carried out says "To check".

## 1. Checks run, findings and how each was resolved

| Check                       | What I used                                                                                     | What it found                                                                                                               | Resolved?                                                                                                                                         |
| --------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automated tests             | `python manage.py test` (Django's test runner, with Playwright driving Chromium for the browser tests) | 553 tests, all passing (23 October 2026, at `7b6fab4`)                                                                | Nothing to resolve                                                                                                                                |
| Deployment settings         | `python manage.py check --deploy` with `DEBUG` off                                              | No issues. One warning is silenced on purpose: joining the browsers' HSTS preload list, which is for a domain's owner to apply for | Nothing to resolve                                                                                                                                |
| Python style                | `flake8` with a line length of 120, excluding `venv` and migrations                             | 22 findings: two unused imports, one extra blank line, one invalid escape (`\W` in a test string), 16 long lines, a variable named `l`, a lambda assigned to a name | Resolved the unused imports, the blank line and the escape in `1f2e618`. Left the 16 long lines (121 to 139 characters, mostly test data), the `l` in `ordo/utils.py` and the lambda in a test, as they don't affect behaviour |
| Leftover debugging          | `git grep` for `print(`, `breakpoint(`, `TODO`, `FIXME` and commented-out code, outside `venv` and migrations | None in the app. The two scripts in `tools/` print what they've done, on purpose                                     | Nothing to resolve                                                                                                                                |
| Files that shouldn't be tracked | `git ls-files`, searched for `.env`, database files, keys, `venv` and uploaded media; `git grep` for literal secret keys and passwords | None tracked. The only passwords in the code are test values and the demo church's password in `tools/`, used only for the screenshots | `*.sqlite3` added to `.gitignore` in `442ef09`, so the screenshots database can't be committed                                                    |
| HTML validation             | [W3C Nu HTML Checker](https://validator.w3.org/nu/), sent the rendered HTML of 13 pages (section 2) | 4 errors on 3 pages and 18 warnings. Two errors on Settings were real: `maxlength` and `required` on the colour picker. Two were `@view-transition`, a CSS rule the checker doesn't know yet. The warnings are all "the list role is unnecessary" | Fixed the colour picker in `7abd14c`. `@view-transition` is valid CSS, newer than the checker. The `role="list"` is deliberate: Safari stops announcing a list as a list when its bullets are removed, so the role puts that back |
| CSS validation              | [W3C CSS Validator](https://jigsaw.w3.org/css-validator/), every one of the 41 files in `static/src/`, CSS level 3 profile | 38 files with no errors. 6 errors in 3 files, all newer CSS the validator doesn't recognise yet: `@container` and `container-type` (music list), `view-transition-name` (navigation) and `@view-transition` (global styles) | Nothing to fix: each is supported by current browsers; the validator lags behind them |
| JavaScript                  | [ESLint](https://eslint.org/) 8.57 with its recommended rules, for browser ES modules, over all 12 files in `static/src/js/` | No errors and no warnings                                                                                                    | Nothing to resolve. The JavaScript is also exercised by the 46 browser tests                                                                      |
| Lighthouse                  | [Lighthouse](https://developer.chrome.com/docs/lighthouse/) 12.2 in Chromium, five pages, desktop and mobile (section 3) | Accessibility 100 on every page. Best practices 96: a console error for the missing `/favicon.ico`. SEO 90: no meta description | Added a favicon in `0b642e4` and a meta description in `7b6fab4`. Performance on mobile (69 to 92) is measured on a slowed-down simulated phone; the lower scores are the longer pages, the service page and the library |

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

## 4. Automated tests

The suite has 553 tests, run on 23 October 2026 at commit `7b6fab4`;
all passed. The browser tests start a real server and use Playwright to
drive Chromium, so they cover the JavaScript as well as the Python.

| File                                      | Tests | What it covers                                                                                                     |
| ----------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| `accounts/tests.py`                       | 115   | Users, the database rules on accounts, the roles table, sign-in, sign-up, invitations, the members page, roles, removing and restoring people, ownership, reset links |
| `comments/tests.py`                       | 30    | Adding, replying to, closing and deleting comments; the Inbox; each church's own comments                          |
| `comments/test_browser.py`                | 3     | Comment threads, deleting a comment, and closed threads as a Viewer sees them, in the browser                     |
| `core/tests.py`                           | 32    | Settings, the crest upload and processing, the crest's address, each church's own settings                         |
| `library/tests.py`                        | 61    | Scores, the library's search, filters and sorting, suitability ranking, "last sung", each church's own library     |
| `library/test_browser.py`                 | 8     | The score form's tag input, and the library as a Viewer sees it, in the browser                                   |
| `ordo/tests.py`                           | 19    | Easter, the seeded data, occasion lookup by date and its endpoint, occasion keys, colours and each church's use types |
| `ordo/test_calendar.py`                   | 18    | Working out the Ordinary Form calendar, with precedence and transfers                                              |
| `ordo/test_calendar_1962.py`              | 23    | Working out the 1962 calendar                                                                                      |
| `ordo/test_calendar_data.py`              | 22    | Loading the calendar files with `load_calendar`                                                                    |
| `ordo/test_dates.py`                      | 28    | Easter and the other date rules                                                                                    |
| `ordo/test_reference.py`                  | 3     | Every day from 2020 to 2040 against the reference data                                                             |
| `planning/tests.py`                       | 81    | Terms, services, notices, slots, pieces, status, the music list, each church's own planning                        |
| `planning/test_templates.py`              | 23    | Slot templates and applying them                                                                                   |
| `planning/test_slot_order.py`             | 8     | Moving slots and reordering them                                                                                   |
| `planning/test_remove_slot.py`            | 6     | Removing slots, asking first when they have pieces                                                                 |
| `planning/test_service_form.py`           | 3     | The service form's calendar choice                                                                                 |
| `planning/test_browser.py`                | 21    | The service page in the browser: the score picker, confirming, dragging slots, dialogs                             |
| `precentor_project/tests.py`              | 20    | The base template, the navigation and its wording, the Inbox count, the user menu and the 403 page                |
| `precentor_project/test_browser.py`       | 14    | Signing in, type and control sizes, checkboxes, Settings, the user menu, page transitions and the skip link, in the browser |
| `precentor_project/test_delete_pages.py`  | 5     | Going Back to a delete page after deleting                                                                         |
| `precentor_project/test_settings.py`      | 8     | Production settings: the secret key check, hosts, HTTPS                                                            |
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
| M11  | Add a service              | On a term, New service, pick a date                                                                           | The day's occasion is suggested from the date; saving shows the service                         | Pass: the occasion lookup by date by automated tests (`ordo/tests.py`); the suggestion in the browser To check |
| M12  | Edit a service             | Edit service, change the type, save                                                                           | The new type on the service page                                                                | Pass: automated tests (`planning/tests.py`) |
| M13  | Slots from a template      | On an empty service, press Mass                                                                               | The Mass slots in order                                                                         | Pass: automated tests (`planning/test_templates.py`) |
| M14  | Reorder a slot             | Move a slot down; then drag one to a new place                                                                | The new order, kept after reloading                                                             | Pass: moving and dragging by browser tests (`planning/test_browser.py`) |
| M15  | Propose a piece            | Type in a slot's search box, choose a score                                                                   | The piece listed as Proposed; suitable scores listed first                                      | Pass: browser tests and Figure 11 |
| M16  | Confirm and unconfirm      | Confirm a proposed piece; then Unconfirm                                                                      | The badge changes each time, and the service's status follows                                   | Pass: browser tests (`planning/test_browser.py`) |
| M17  | Mark a slot N/A            | Add a slot with "Not needed (N/A)" ticked                                                                     | The slot shows (N/A) and doesn't count against the service's status                             | Pass: slots marked N/A shown and not counted (Figures 9 and 10) |
| M18  | The music list             | On a term, Music list; switch between Public and Draft                                                        | Public shows confirmed pieces; Draft marks undecided slots TBC                                  | Pass: public view in the browser (Figure 12); draft view To check |
| M19  | Print the music list       | Press Print                                                                                                   | A clean page without the navigation or buttons                                                  | To check |
| M20  | Comment, close, delete     | Comment on a service; reply; Close; as a Conductor, delete the closed thread                                  | The thread appears in the Inbox until closed; then it's deleted                                 | Pass: browser tests (`comments/test_browser.py`) and automated tests |
| M21  | Invite and join            | As the owner, Members, Invite someone as a Librarian; open the link in another browser and join              | The link is shown once; the new person is signed in as a Librarian                              | Pass: invited and joined in two browsers |
| M22  | Change a role              | As the owner, change a member's role on the Members page                                                      | A message confirming it; the member's controls change                                           | Pass: automated tests (`accounts/tests.py`) |
| M23  | Remove a member            | As the owner, Remove a member and confirm; that member tries to sign in                                       | They're under Former members and can't sign in                                                  | Pass: removed in the browser, then listed under Former members; signing in refused by an automated test |
| M24  | Settings and crest         | Settings, change the church's name, upload a crest as a logo, save                                            | The name and crest on the music list                                                            | Pass: crest upload and processing by automated tests; uploaded on the live site on 22 October |
| M25  | A Viewer refused           | As a Viewer, open `/terms/add/`                                                                               | The "Not available to you" page (403)                                                           | Pass: in the browser (Figure 16) |
| M26  | Another church's record    | As one church, open the address of another church's score or service                                          | "Page not found" (404)                                                                          | Pass: in the browser (Figure 17) |
| M27  | Error pages                | Open an address that doesn't exist                                                                            | Precentor's own 404 page                                                                        | Pass: in the browser with `DEBUG` off (Figure 17) |

## 6. Responsiveness, usability and the keyboard

| ID   | Check                         | Steps                                                                       | Expected                                                             | Result   |
| ---- | ----------------------------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------- | -------- |
| R01  | 320 pixels wide               | Terms, a service, the library and the music list at 320 pixels              | Nothing wider than the screen except the library table, which scrolls in its own box | To check |
| R02  | 768 pixels wide               | The same pages at 768 pixels                                                | The layout fills the width without gaps or overlaps                  | To check |
| R03  | 1280 pixels wide              | The same pages at 1280 pixels                                               | The layout as in the README's screenshots                            | Pass: every page in the README's figures at 1280 pixels |
| R04  | Keyboard alone                | Sign in, open a service, propose and confirm a piece, using only the keyboard | Every step reachable with Tab, Enter and the arrow keys, with a visible outline on each control | Pass for focus outlines (Figure 23); the whole journey To check |
| R05  | Dark mode                     | Switch the device to dark, then choose Dark in the user menu                | Every page readable, with the same contrast as in light              | Pass for the service page (Figure 22) and by browser tests; other pages To check |
| R06  | Without JavaScript            | Turn JavaScript off; propose a piece, confirm it, remove a slot             | Each works through ordinary pages                                    | Pass: each is an ordinary form post, covered by automated tests without JavaScript |

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

**Left unfixed:** the 16 long lines, the variable `l` and the lambda
found by flake8 (see section 1). None affects how the app works.

### Known bugs

| Bug                                                                                                                                            | Effect                                                                                                         | Why it's not fixed yet                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| The "change your password" pages (`/accounts/password_change/`) still have Django admin's look, and nothing in the app links to them           | Someone who wants a new password asks the owner for a reset link, which works, rather than changing it themselves | Restyling them and adding a menu link is new work, left until after submission          |
| A signed-in site superuser who opens an invitation link is told their account "belongs to no church"                                           | Only affects the site's administrator, who has no church by design                                             | Cosmetic; the link is still refused, which is correct                                   |
| Mobile performance on the longest pages is lower: 69 for a service with ten slots and 75 for the library (section 3)                           | Those pages take longer to become usable on a slow phone                                                       | Would need the pages split or loaded in parts; not attempted before submission          |

## 8. Deployment check

On the live site, https://precentor.onrender.com, after each deploy.

| ID   | Check                         | Expected                                                                 | Result   |
| ---- | ----------------------------- | ------------------------------------------------------------------------ | -------- |
| D01  | The site loads                | The sign-in page, after up to a minute if the site was asleep            | To check |
| D02  | `http://` goes to `https://`  | Typing `http://precentor.onrender.com` ends on the `https://` address    | To check |
| D03  | `DEBUG` is off                | A made-up address shows Precentor's 404 page, not Django's debug page    | To check |
| D04  | Static files and the crest    | Styles, fonts and an uploaded crest all load                             | To check |
| D05  | Register and plan             | Register a test church, add a score, a term and a service, propose and confirm a piece, open the music list | To check |
