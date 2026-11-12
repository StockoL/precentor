# Testing Precentor

This covers the automated tests, the checks I ran on the code, the
manual tests, and the bugs found along the way. Each check says what I
used, what it found and whether that's resolved.

Everything here was run on a local copy of the site with the invented
demo church. The manual tests were run on 10 and 11 November 2026: on
10 November between commits `61f3790` and `b500e3f`, with rows [M59](#m59) and
[M60](#m60) added later that day at `4746a58`, M61 to M64 at `59e3469` and M65
at `b0fafbf`; on 11 November M66 at `823ebe2`, M67 and M68 at `89d33a9`
and M69 at `3ed02e7`. M70 and M71 were run on my iPhone on 12 November.
The checks in [sections 1 to 3](#1-checks-run-findings-and-how-each-was-resolved), the widths and browsers, and the
contrast were all run at `8908668` on 10 November, with the checkers'
own screenshots. The code has changed since (adding several services,
proposing from the library, the iPhone fixes and a command for
handing on ownership), so I ran the checks again on 12 November: the
HTML checker on every page, the CSS validator and ESLint at `04fd132`,
and the tests, flake8 and the deployment, migration, debugging and
tracked-file checks at `46dbe45`, which added the command and changed
no page, stylesheet or script; [section 1](#1-checks-run-findings-and-how-each-was-resolved) gives both results where they
differ. Lighthouse, the widths and the contrast weren't run again. The
manual tests were carried out in Google Chrome 157 on Windows 11, driven by
Playwright and checked by me row by row, or by the automated test
named. Playwright's own Chromium 149 hangs on cross-document page
transitions, which real Chrome and Edge don't, so it was used only for
the automated browser tests, where every page is opened by its address.

## Contents

- [1. Checks run, findings and how each was resolved](#1-checks-run-findings-and-how-each-was-resolved)
- [2. HTML and CSS validation](#2-html-and-css-validation)
  - [HTML, every page](#html-every-page)
  - [HTML on the W3C's online checker](#html-on-the-w3cs-online-checker)
  - [CSS](#css)
- [3. Lighthouse scores](#3-lighthouse-scores)
- [4. Automated tests](#4-automated-tests)
- [5. Manual tests](#5-manual-tests)
  - [5.1 Accounts and members](#51-accounts-and-members)
  - [5.2 The library](#52-the-library)
  - [5.3 Importing and exporting](#53-importing-and-exporting)
  - [5.4 Terms and services](#54-terms-and-services)
  - [5.5 Slots and pieces](#55-slots-and-pieces)
  - [5.6 Suggestions and the day's chants](#56-suggestions-and-the-days-chants)
  - [5.7 Hymns](#57-hymns)
  - [5.8 The music list, the pew sheet and Settings](#58-the-music-list-the-pew-sheet-and-settings)
  - [5.9 Comments](#59-comments)
  - [5.10 Roles, other churches and errors](#510-roles-other-churches-and-errors)
- [6. Responsiveness, usability and the keyboard](#6-responsiveness-usability-and-the-keyboard)
  - [Widths and browsers](#widths-and-browsers)
  - [Real devices](#real-devices)
- [7. Bugs found and fixed](#7-bugs-found-and-fixed)
  - [Known bugs](#known-bugs)
- [8. Deployment check](#8-deployment-check)
  - [After v2.0.0 (11 November 2026)](#after-v200-11-november-2026)

## 1. Checks run, findings and how each was resolved

| Check | What I used | What it found on 10 November, and on 12 November | Resolved? |
| ----- | ----------- | ---------------------------- | --------- |
| Automated tests | `python manage.py test` (Django's test runner, with Playwright driving Chromium for the browser tests) | 1,020 tests, all passing, at `46dbe45`, the last change to the code; 944 at `7fd2e74`, after the ten that tested copying the old columns went with them ([section 4](#4-automated-tests)); 954 at `8908668`, the run in my own terminal ([Check figure 1](#check-figure-1)) | Nothing to resolve. There were 553 at submission |
| Deployment settings | `python manage.py check --deploy` with `DEBUG` off and the host name Render sets | No issues. One warning is silenced on purpose: joining the browsers' HSTS preload list, which is for a domain's owner to apply for ([Check figure 2](#check-figure-2)). The same on 12 November | Nothing to resolve |
| Migrations | `python manage.py makemigrations --check --dry-run`, and a rehearsal of the merge on a copy of the live database ([`merge_record.md`](merge_record.md)) | No missing migrations ([Check figure 2](#check-figure-2)), and none on 12 November. On the copy, all 28 new migrations ran, `check_copied_data` found everything copied, and all 177 pages opened for every church | Nothing to resolve |
| Python style | flake8 7.4.1 with the settings in `.flake8` (line length 120, `venv` and migrations left out) | No findings ([Check figure 2](#check-figure-2)), and none on 12 November | At submission: two unused imports, a blank line and an escape, fixed in `1f2e618`; more in `722ffc4`; the 16 long lines, the variable `l` and the lambda left then were cleared in `86ad9e8` |
| Leftover debugging | `git grep` for `print(`, `breakpoint(`, `TODO`, `FIXME` and commented-out code, outside `venv` and migrations | None in the app, on both dates. The scripts in `tools/` and the three Node build scripts print what they've done, on purpose | Nothing to resolve |
| Files that shouldn't be tracked | `git ls-files`, searched for `.env`, database files, keys, `venv` and uploaded media; `git grep` for literal secret keys and passwords | None tracked, on both dates. The only passwords in the code are test values and the demo church's, used for screenshots | `*.sqlite3` added to `.gitignore` in `442ef09` |
| HTML validation | The W3C's Nu HTML Checker 26.11.9 on my computer through [`tools/validate_html.py`](../tools/validate_html.py), every page; then the 25 main pages on the W3C's online checker, 26.11.10 ([section 2](#2-html-and-css-validation)) | 75 pages, no errors. 30 warnings, all `role="list"`. Online, no errors on any of the 25, and 27 warnings, all `role="list"`. On 12 November, on my computer: 77 pages, still no errors, and the same 30 warnings | The `role="list"` is deliberate ([README §16](../README.md#16-design-decisions-that-depart-from-convention)). Errors fixed earlier: the Settings colour picker (`7abd14c`) and a form inside a `<span>` on the service page (`5866886`) |
| CSS validation | [W3C CSS Validator](https://jigsaw.w3.org/css-validator/), CSS level 3 profile, on the two stylesheets the site serves, which hold all 47 source files in `static/src/` ([section 2](#2-html-and-css-validation)) | 8 errors, all CSS the validator doesn't know yet: `@container` and `container-type` (music list), `@view-transition` and its pseudo-elements (global styles and the sign-in pages' stylesheet), `view-transition-name` (navigation), and `pointer-events`, which is outside the CSS3 profile. 13 warnings, on vendor prefixes, custom properties it doesn't check, and `clip`. On 12 November `precentor.css` again: the same 7 errors, and 14 warnings, the new one the date fields' `::-webkit-date-and-time-value` | Nothing to fix: each is supported by current browsers, and the warnings are explained in [section 2](#2-html-and-css-validation) |
| JavaScript | [ESLint](https://eslint.org/) 8.57 with its recommended rules, for browser ES modules (the settings in `.eslintrc.json`), over all the files in `static/src/js/` | No errors and no warnings in the 14 files ([Check figure 2](#check-figure-2)), nor in the 16 on 12 November | Nothing to resolve. The JavaScript is also exercised by the browser tests |
| Lighthouse | Lighthouse 12.2.1 in Chrome 157, nine pages, desktop and mobile ([section 3](#3-lighthouse-scores)) | Accessibility, best practices and SEO 100 on every page; performance 100 on desktop, 94 to 99 on mobile | At submission a missing favicon and meta description cost points: fixed in `0b642e4` and `7b6fab4`. Mobile speed improved in `49ec234`, `e55fd08`, `094f805` and `791158d` |
| Widths and browsers | [`tools/check_viewports.py`](../tools/check_viewports.py): 25 pages at 320, 375, 768, 1024 and 1280 pixels in Chromium, Firefox and WebKit ([section 6](#6-responsiveness-usability-and-the-keyboard)) | 375 page loads, nothing wider than the window, no console errors | At submission the score form was 3 pixels too wide at 320, fixed in `6bf1062` |
| Text contrast | Every visible piece of text on the 25 pages, measured against its background in light and dark ([row R05](#r05)) | All 1,424 meet WCAG AA in both; the lowest ratios are 4.83 in light and 5.7 in dark | Nothing to resolve |

Every check above was run again on 10 November 2026 at `8908668`. The
checks that print to a terminal I ran once more in my own terminal in
VS Code, and the screenshots are of that. flake8 and ESLint print
nothing when they find nothing, so each command adds a line saying so.
The last command sets `DEBUG` off and the host name as Render does,
then clears both.

<a id="check-figure-1"></a>

![The VS Code terminal: python manage.py test found 954 tests, the system check found no issues, then a row of dots, Ran 954 tests in 510.070s, and OK](screenshots/testing/checks/terminal-tests.png)

_Check figure 1. The whole suite in my terminal: 954 tests, all passing._

<a id="check-figure-2"></a>

![The VS Code terminal: flake8: no findings; ESLint: no findings; makemigrations --check --dry-run: No changes detected; check --deploy: System check identified no issues (1 silenced)](screenshots/testing/checks/terminal-linters-and-deploy.png)

_Check figure 2. flake8, ESLint, the migrations check and the deployment check, one after another._

[↑ Back to contents](#contents)

## 2. HTML and CSS validation

### HTML, every page

Checked on 10 November 2026 at `8908668`, with
[`tools/validate_html.py`](../tools/validate_html.py). It renders every
page the project's routes give, signed in as a church's owner (or signed
out, for the pages before signing in), with `DEBUG` off as on the live
site, and 13 pages that only appear after an action, such as a form with
mistakes or a deleted account. Each page went to the Nu HTML Checker
26.11.9, the W3C's own checker, run on my computer from its published
download: the [online copy](https://validator.w3.org/nu/) sits behind
Cloudflare, which kept turning the script away even at one request every
ten minutes. A new page is checked without being added to a list.

75 pages, **no errors**. The 30 warnings are all the same: "the list role
is unnecessary", on lists that keep `role="list"` on purpose (Safari stops
announcing a list as a list once its bullets are removed; [README §16](../README.md#16-design-decisions-that-depart-from-convention)).
On 12 November, at `04fd132`, I ran it again with the same checker after
the pages added since: 77 pages, still no errors, and the same 30
warnings on the same pages. Add several services and proposing a score
from its page have none.
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
| Add several services (`planning:service_batch`) | 0 | 0 | Added since the full run; checked on its own, the first step and its preview, as it was built |
| Propose a score from its page (`planning:propose_score`) | 0 | 0 | Added since the full run; checked on its own, both steps and the refused states, as it was built |
| Remove a piece (without JavaScript) (`planning:remove_piece`) | 0 | 0 |  |
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

### HTML on the W3C's online checker

So that the result isn't only my own copy's word, the 25 main pages
went to the [online checker](https://validator.w3.org/nu/) as well, on
10 November 2026 at `8908668`, by
[`tools/take_validation_screenshots.py`](../tools/take_validation_screenshots.py)
in Google Chrome. The online checker can't sign in to fetch a page
itself, so each page's HTML, as the server sends it for the demo
church, went in through its text box. Each screenshot shows the
checker's own result, with the page's heading outline turned on, so
the page it checked is named by its own headings.

The online checker was 26.11.10, one release newer than my copy, and
agreed with it: **no errors on any page**, and 27 warnings, every one
"the list role is unnecessary" on the same deliberate lists.

<a id="check-figure-3"></a>

![The Nu HTML Checker online, checking the sign-in page by text input: Document checking completed. No errors or warnings to show, with the page's outline below](screenshots/testing/checks/html-sign-in.png)

_Check figure 3. The sign-in page on the W3C's online checker: no errors or warnings._

<a id="check-figure-4"></a>

![The Nu HTML Checker online, checking a service page: eleven warnings, each The list role is unnecessary for element ul, then Document checking completed, and the outline headed Sung Mass, Sun 29 Nov 2026](screenshots/testing/checks/html-a-service.png)

_Check figure 4. A service, the longest page: no errors, and only the deliberate `role="list"` warnings._

<details>
<summary>All 25 pages on the online checker</summary>

| Page | Errors | Warnings, all `role="list"` | The checker's result |
| ---- | ------ | ---------------------------- | -------------------- |
| Sign in | 0 | 0 | [Screenshot](screenshots/testing/checks/html-sign-in.png) |
| Register | 0 | 0 | [Screenshot](screenshots/testing/checks/html-register.png) |
| Privacy | 0 | 0 | [Screenshot](screenshots/testing/checks/html-privacy.png) |
| Terms | 0 | 1 | [Screenshot](screenshots/testing/checks/html-terms.png) |
| A term | 0 | 3 | [Screenshot](screenshots/testing/checks/html-a-term.png) |
| A service | 0 | 11 | [Screenshot](screenshots/testing/checks/html-a-service.png) |
| Propose a piece | 0 | 0 | [Screenshot](screenshots/testing/checks/html-propose-a-piece.png) |
| Pew sheet | 0 | 0 | [Screenshot](screenshots/testing/checks/html-pew-sheet.png) |
| Music list | 0 | 0 | [Screenshot](screenshots/testing/checks/html-music-list.png) |
| Library | 0 | 0 | [Screenshot](screenshots/testing/checks/html-library.png) |
| A score | 0 | 0 | [Screenshot](screenshots/testing/checks/html-a-score.png) |
| Add a score | 0 | 0 | [Screenshot](screenshots/testing/checks/html-add-a-score.png) |
| Completeness | 0 | 2 | [Screenshot](screenshots/testing/checks/html-completeness.png) |
| Import | 0 | 0 | [Screenshot](screenshots/testing/checks/html-import.png) |
| Imports | 0 | 1 | [Screenshot](screenshots/testing/checks/html-imports.png) |
| Hymnals | 0 | 1 | [Screenshot](screenshots/testing/checks/html-hymnals.png) |
| A hymnal | 0 | 1 | [Screenshot](screenshots/testing/checks/html-a-hymnal.png) |
| A hymn | 0 | 1 | [Screenshot](screenshots/testing/checks/html-a-hymn.png) |
| Tunes | 0 | 1 | [Screenshot](screenshots/testing/checks/html-tunes.png) |
| Templates | 0 | 1 | [Screenshot](screenshots/testing/checks/html-templates.png) |
| Edit a template | 0 | 1 | [Screenshot](screenshots/testing/checks/html-edit-a-template.png) |
| Inbox | 0 | 1 | [Screenshot](screenshots/testing/checks/html-inbox.png) |
| Settings | 0 | 0 | [Screenshot](screenshots/testing/checks/html-settings.png) |
| Members | 0 | 2 | [Screenshot](screenshots/testing/checks/html-members.png) |
| Not found (404) | 0 | 0 | [Screenshot](screenshots/testing/checks/html-not-found--404.png) |

</details>

### CSS

The site serves two stylesheets: `precentor.css`, built from 46 of the
source files by `build-css.js`, and `no-page-transition.css`, which only
the sign-in pages add ([README §16](../README.md#16-design-decisions-that-depart-from-convention)). On 10 November 2026 I sent both to
the [W3C CSS Validator](https://jigsaw.w3.org/css-validator/) as files,
with the CSS level 3 profile, and the screenshots are its own results.

The 8 errors are all CSS that browsers support and the validator
doesn't know yet: `@view-transition` and its two pseudo-elements, which
it can't parse, `view-transition-name`, `@container` and
`container-type`, and `pointer-events`, which is outside the level 3
profile. Seven are in `precentor.css`, one in `no-page-transition.css`.
On 12 November, after the rule for date fields, I sent `precentor.css`
again: the same seven errors, and one more warning, for
`::-webkit-date-and-time-value`, which starts a date at the left in
Safari like the text in the fields around it.

The 13 warnings are about choices made on purpose. Two are the
`text-size-adjust` prefixes that stop a phone enlarging text on its own,
and two the `::-webkit-details-marker` that hides the disclosure arrow
in Safari. Eight say the validator can't check custom properties, which
hold every colour and size in the design system. The last is `clip`,
deprecated in favour of `clip-path` but still honoured by every
browser, in the usual pattern for text that only screen readers read.

<a id="check-figure-5"></a>

![The W3C CSS Validator's results for precentor.css at CSS level 3: seven errors listed by line, then thirteen warnings](screenshots/testing/checks/css-precentor.png)

_Check figure 5. The main stylesheet: seven errors, all newer CSS the validator doesn't know, and the warnings above._

<a id="check-figure-6"></a>

![The W3C CSS Validator's results for no-page-transition.css: one error, Unrecognized at-rule @view-transition](screenshots/testing/checks/css-no-page-transition.png)

_Check figure 6. The sign-in pages' stylesheet: its one rule, `@view-transition`. As that's all it holds, the validator then says it found no style sheet._

[↑ Back to contents](#contents)

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

Measured again on 10 November 2026 at `8908668`, with Lighthouse 12.2.1
in Google Chrome 157, on the nine pages above and signed in where the page
needs it, one run each on desktop and on mobile, by
[`tools/take_validation_screenshots.py`](../tools/take_validation_screenshots.py).
Each screenshot is the top of Lighthouse's own report, with the address
it measured, and the report's note of when, the device it emulated and
its version.

| Page | Performance (desktop / mobile) | Accessibility | Best practices | SEO | Lighthouse's report |
| ---- | ------------------------------ | ------------- | -------------- | --- | ------------------- |
| Sign in | 100 / 98 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-sign-in-desktop.png), [mobile](screenshots/testing/checks/lighthouse-sign-in-mobile.png) |
| Terms | 100 / 99 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-terms-desktop.png), [mobile](screenshots/testing/checks/lighthouse-terms-mobile.png) |
| A service | 100 / 94 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-a-service-desktop.png), [mobile](screenshots/testing/checks/lighthouse-a-service-mobile.png) |
| Library | 100 / 98 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-library-desktop.png), [mobile](screenshots/testing/checks/lighthouse-library-mobile.png) |
| Music list | 100 / 95 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-music-list-desktop.png), [mobile](screenshots/testing/checks/lighthouse-music-list-mobile.png) |
| Pew sheet | 100 / 97 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-pew-sheet-desktop.png), [mobile](screenshots/testing/checks/lighthouse-pew-sheet-mobile.png) |
| Completeness | 100 / 99 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-completeness-desktop.png), [mobile](screenshots/testing/checks/lighthouse-completeness-mobile.png) |
| A hymnal | 100 / 99 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-a-hymnal-desktop.png), [mobile](screenshots/testing/checks/lighthouse-a-hymnal-mobile.png) |
| Import | 100 / 98 | 100 | 100 | 100 | [Desktop](screenshots/testing/checks/lighthouse-import-desktop.png), [mobile](screenshots/testing/checks/lighthouse-import-mobile.png) |

Accessibility, best practices and SEO are 100 on every page, on both.
The service page and the music list are the longest pages, which is why
they're the slowest to fill a simulated phone's screen. A run measured
a moment earlier gave the service 95 on mobile; one run can differ from
the next by a point or two, so the table keeps the run the screenshots
show.

<a id="check-figure-7"></a>

![Lighthouse's report for the service page on mobile: Performance 94, Accessibility, Best Practices and SEO 100, emulating a Moto G Power on slow 4G with Lighthouse 12.2.1](screenshots/testing/checks/lighthouse-a-service-mobile.png)

_Check figure 7. The lowest score: a service on a simulated phone._

[↑ Back to contents](#contents)

## 4. Automated tests

The suite has 1,020 tests, run on 12 November 2026 at `46dbe45`;
all passed. The browser tests start a real server and use Playwright to
drive Chromium, so they cover the JavaScript as well as the Python.

| File                                      | Tests | What it covers                                                                                                     |
| ----------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| `accounts/tests.py`                       | 141   | Users, the database rules on accounts, the roles table, sign-in, sign-up, invitations, the members page, roles, removing and restoring people, ownership, reset links, changing your own password, the limits on wrong passwords and on registering, deleting your own account and deleting the church |
| `accounts/test_browser.py`                | 2     | The Copy link button, and what happens when the browser refuses the clipboard |
| `accounts/test_transfer_ownership.py`     | 5     | The command that hands on ownership when the owner can't: the swap, a switched-off owner, a church with no owner, and each refusal |
| `comments/tests.py`                       | 34    | Adding, replying to, closing and deleting comments; the Inbox; each church's own comments, and comments kept as "A former member" |
| `comments/test_browser.py`                | 3     | Comment threads, deleting a comment, and closed threads as a Viewer sees them, in the browser |
| `core/tests.py`                           | 34    | Settings, the crest upload and processing, the crest's address, the music list arrangement and the repeat window, each church's own settings |
| `library/tests.py`                        | 123   | Scores, the library's search, filters and sorting, the ranking the piece picker uses, "last sung", texts, the completeness page, returning after an edit, hymnals, hymns and their pages, joining the same hymn, hymn last sung, tunes and a tune's number in a book, each church's own library, the Suitable-for filters and their menus, and a score planned for a service being kept when deleted |
| `library/test_service_bar.py`             | 9     | A score opened from a service: its slots in that service with the day, occasion and state, and the way back; another church's service, or one that doesn't exist or isn't a number, ignored; Confirm and Remove on the bar coming back to the score page, a confirmed piece asking first, and another site's address as next going to the service instead |
| `library/test_metre.py`                   | 5     | Writing a metre one way: short names, doubled verses, lines of ten or more, anything else kept as typed |
| `library/test_browser.py`                 | 11    | The score form's tag input, the library as a Viewer sees it, and the import page's file size check and disabled button, in the browser |
| `library/test_importing.py`               | 58    | Importing from a Google Sheets link, or refusing neither or both; reading a spreadsheet (encodings, separators, headers, limits), checking each row, saving an import all at once, keeping and removing it, who may remove it, keeping or removing it a second time, the Imports list, the export and its round trip |
| `library/test_sheets.py`                  | 8     | A Google Sheets link: the export address built from its ID and tab, every other address refused, and with Google's answer faked, CSV kept, the size limit, a sign-in page, a refusal and no connection |
| `library/test_hymn_import.py`             | 22    | A hymnal's list: reading it (a number needed, a repeated number skipped), new numbers added with their details, only blanks filled for known ones, tunes matched or added, a list that changes nothing; removing an import (sung entries and hymns in other books kept, blanks emptied unless changed since, unused tunes gone); the import, result, keep and remove pages, a second keep or remove, and who may remove it |
| `ordo/tests.py`                           | 19    | Easter, the seeded data, occasion lookup by date and its endpoint, occasion keys, colours and each church's use types |
| `ordo/test_calendar.py`                   | 18    | Working out the Ordinary Form calendar, with precedence and transfers |
| `ordo/test_calendar_1962.py`              | 23    | Working out the 1962 calendar |
| `ordo/test_calendar_data.py`              | 22    | Loading the calendar files with `load_calendar` |
| `ordo/test_dates.py`                      | 29    | Easter and the other date rules, and the Sunday cycle |
| `ordo/test_reference.py`                  | 3     | Every day from 2020 to 2040 against the reference data |
| `ordo/test_propers.py`                    | 21    | The chants of both forms: one per part, season and year, several of a part in the order sung, loading them with the calendar, every one belonging to a day of its form, the 1962 seasons' edges and a saint's form by date, and an Ordinary Form Sunday's chant for its year, each year's own Lent Communion and each of the four Christmas Masses; the Sunday an Ordinary Form weekday borrows from, and none in Lent, late Advent, Christmas or the Easter octave |
| `planning/tests.py`                       | 85    | Terms, services, notices, slots, pieces, proposing and confirming at once, confirming twice, status, the music list, each church's own planning |
| `planning/test_templates.py`              | 24    | Slot templates as rows with kinds, editing them as a formset (order, remove, each name once), and applying them |
| `planning/test_slot_order.py`             | 8     | Moving slots and reordering them |
| `planning/test_batch.py`                  | 6     | The dates a batch offers, from the real calendar: every Sunday of a term, both ends of the range, a weekday solemnity under the second pattern only and not the Vigil Mass's weekday, 1962's first-class days, every date to pick, each date's celebration, and the calendar read once however long the range |
| `planning/test_service_batch.py`          | 24    | Adding several services: the button and who may use it, another church's term, the term's dates to start with and both its ends allowed, dates outside it refused, the type from the template; the preview ticked or not, its count, dates already holding the service, and a fixed number of queries; creating with occasion, type, template and slots, leaving out unticked and outside dates, no duplicates when run twice, the cap of 60, nothing ticked, a rollback leaving nothing, both steps without JavaScript, and, in the browser, Select all, Select none and the count |
| `planning/test_remove_slot.py`            | 6     | Removing slots, asking first when they have pieces |
| `planning/test_piece_links.py`            | 8     | A piece's title linking to its score or hymn with its service, on the service page and the music list, and a typed reference linking nowhere; the music list's words unchanged, with no query per piece; the pew sheet unlinked; and, in the browser, a printed title looking like the words around it |
| `planning/test_propose_score.py`          | 22    | Proposing a score from its page: the button for those who plan, coming services with their status and those already holding it disabled, at a fixed number of queries; the slots with what each holds and the one chosen and why; proposing, proposing and confirming, a new slot with its kind, the same score twice refused, another church's service or slot, a Viewer, both routes without JavaScript, and, in the browser, the slots arriving in place |
| `planning/test_remove_piece.py`           | 13    | Removing one piece: at once when it's proposed with no comments, asking first when it's confirmed or has comments, what the page is sent back, a removed chant offered again, without JavaScript, a second removal, another church's piece, Viewers, and no extra query per piece |
| `planning/test_service_form.py`           | 3     | The service form's calendar choice |
| `planning/test_date_checks.py`            | 10    | A term ending before it starts, a service outside its term, and new term dates that would leave services outside it, at both ends, with a rename still allowed |
| `planning/test_browser.py`                | 38    | The service page in the browser: the score picker and its suggestion groups, a search that finds nothing used as typed, a hymn by book and number, a suggested hymn filling them in, the day's chant proposed in one click, a typed reference, a refused proposal, a second piece after a score, proposing and confirming at once, confirming, dragging slots, changing a slot's kind, dialogs, a button kept busy during its request and usable after an error, taking a piece out from the keyboard, the reference box at 320 pixels, the list stopping at the bottom of what can be seen |
| `planning/test_slot_kinds.py`             | 23    | Classifying slot names, kinds on save and from templates, the migrations that classified existing slots (and later Sequences and Responsories), the badge, choosing and changing a kind, and a slot named Canticle |
| `planning/test_reference_pieces.py`       | 34    | A piece as a score, a hymn or a reference and the rule between them, proposing each, showing them everywhere, the music list arrangement, a hymn's tune and its choices, the pew sheet's tune number, the first-line prompt, the same piece twice in a slot |
| `planning/test_outside_library.py`        | 5     | A typed piece in a slot for scores marked as not in the library, with a link to add it for those who may, the score form filled in from it and coming back, and the propose page without JavaScript |
| `planning/test_suggestions.py`            | 20    | What each suggestion rests on, in a fixed number of queries; groups, strength and reasons; a slot's use type; the propose page's groups; the service page's data; the voicing prompt; suggested hymns and their book |
| `planning/test_propers.py`                | 15    | The day's chants on a slot: which part, Alleluia or Tract by date, not once proposed, not for other slots; several in order, each going once proposed in a slot of the same kind; Sequence slots; Palm Sunday's antiphons, the Vigil's Alleluia and Tracts in each form's order, and an Ember Saturday's graduals from the loaded data; an Ordinary Form weekday offered the Sunday before's chants, a 1962 one with no occasion nothing; the propose page's own form, and an Alleluia or Tract slot on a weekday with no occasion |
| `planning/test_viewers.py`                | 3     | Viewers see the draft music list, the pew sheet and proposed pieces; signed-out visitors go to sign in; another church's members get "not found" |
| `planning/test_pew_sheet.py`              | 6     | Which slots a pew sheet prints, its texts and composers and the options to leave them off, and each church's own |
| `precentor_project/tests.py`              | 28    | The base template, the navigation and its wording, the Inbox count, the user menu, the 403 page, never storing signed-in pages, the 500 page, the privacy page and footer, and the check on return addresses |
| `precentor_project/test_scripts.py`       | 2     | Every module a page's scripts import is on the page or preloaded |
| `precentor_project/test_css.py`           | 6     | The one stylesheet: built from every CSS source as it is now, the layers declared first, and the only one pages link, and printing hiding the navigation, the controls and the footer |
| `precentor_project/test_browser.py`       | 16    | Signing in, type and control sizes, checkboxes, Settings, the user menu, page transitions, the skip link, and date fields lining up with the other fields, in the browser |
| `precentor_project/test_delete_pages.py`  | 5     | Going Back to a delete page after deleting |
| `precentor_project/test_isolation.py`     | 7     | Two complete churches: every address with an id tried as the other church, every page checked for the other church's text, and every model and route covered |
| `precentor_project/test_settings.py`      | 11    | Production settings: the secret key check, hosts, HTTPS, the cookies and the cache |
| `precentor_project/test_testing.py`       | 2     | The shared test helpers |

To run them, see [Running it locally](../README.md#18-running-it-locally) in the README.

[↑ Back to contents](#contents)

## 5. Manual tests

Grouped by feature, in the order someone meets them; each row keeps its
number. The screenshots follow the table they belong to. Most were taken
on 10 November 2026 at `b500e3f` by
[`tools/take_test_screenshots.py`](../tools/take_test_screenshots.py),
in Chromium at 1280 pixels, from the invented demo church; [row M65](#m65)'s
were taken in Google Chrome 157 while I ran it, at `b0fafbf`.

### 5.1 Accounts and members

Registering, signing in, passwords, invitations, members, and leaving.

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m01"></a>M01  | Register a church          | Choose Register, fill in the church's name, your name, email and password twice, submit                       | Signed in on the Terms page, which shows the Getting started panel                              | Pass: registered a church and landed on Terms with the Getting started panel |
| <a id="m02"></a>M02  | Sign in and out            | Log out from the user menu; sign in with the same email in different capitals                                 | Signed out and back at the sign-in page; then signed in again                                   | Pass: Log out led to the sign-in page; signing in again with the address in capitals worked |
| <a id="m03"></a>M03  | Password reset by link     | As the owner, Members, Reset link for a member; open the link in another browser and choose a new password    | "Password saved"; the member signs in with the new password; the link no longer works           | Pass: the link opened in a second browser; "Password saved"; the member signed in with the new password; the link then said "This reset link no longer works" |
| <a id="m21"></a>M21  | Invite and join            | As the owner, Members, Invite someone as a Librarian; open the link in another browser and join              | The link is shown once; the new person is signed in as a Librarian                              | Pass: the link was shown once (reloading its page doesn't show it again); in another browser the new person joined as a Librarian, offered Add score but refused New term |
| <a id="m22"></a>M22  | Change a role              | As the owner, change a member's role on the Members page                                                      | A message confirming it; the member's controls change                                           | Pass: "Lina Librarian is now a Viewer."; that member was no longer offered Add score |
| <a id="m23"></a>M23  | Remove a member            | As the owner, Remove a member and confirm; that member tries to sign in                                       | They're under Former members and can't sign in                                                  | Pass: listed under Former members; signing in refused; brought back with Restore |
| <a id="m28"></a>M28  | Too many wrong passwords   | Sign in to one address with a wrong password six times                                                        | The sixth is refused with "Too many wrong passwords", even with the right password, for 15 minutes | Pass: the sixth wrong try said "Too many wrong passwords for this address. Wait 15 minutes…", and the right password was refused too |
| <a id="m29"></a>M29  | Too many registrations     | Register six churches from one network within an hour                                                         | The sixth is refused with "try again in an hour" and nothing is created | Pass: the sixth registration from one network within the hour was refused: "Please try again in an hour" |
| <a id="m30"></a>M30  | Delete your own account    | As a member, Change password, Delete your account, give the password                                          | Signed out, the account gone, their comments shown as "A former member"; the owner is told to hand over first | Pass: "Your account has been deleted"; their comment now reads "A former member"; signing in refused; the owner opening the page is told to hand over ownership first |
| <a id="m31"></a>M31  | Delete the church          | As the owner, Settings, Delete this church, type its name                                                     | The page lists what will go; a wrong name is refused; the right one deletes everything and signs out | Pass: the page listed what goes; a wrong name was refused; the right name deleted the church, and Terms then led to the sign-in page |
| <a id="m32"></a>M32  | Privacy page               | Follow Privacy in the footer, signed in and out                                                                | The page explains what's kept and how to leave                       | Pass: the Privacy link in the footer, signed in and signed out |

### 5.2 The library

Scores: adding, editing, deleting, finding them, and what's missing from them.

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m04"></a>M04  | Add a score                | Library, Add score; submit empty, then fill in and save                                                       | Errors beside the required fields; then the score's page                                        | Pass: the browser's own check stops an empty form first ("Please fill in this field"); sent without it, the server marks the title and composer as required beside each ([Test figure 1](#test-figure-1)); filled in, the score's page |
| <a id="m05"></a>M05  | Edit a score               | On a score's page, Edit, change the title, save                                                               | The new title on the score's page and in the library                                            | Pass: the new title on the score's page, and found by the Library's search |
| <a id="m06"></a>M06  | Delete a score             | On a score's page, Delete, confirm                                                                            | A confirmation page first; then the library without the score                                   | Pass: a confirmation page first ([Test figure 2](#test-figure-2)); then the Library without the score |
| <a id="m07"></a>M07  | Search the library         | Type part of a title or composer in the search box                                                            | Only matching scores listed                                                                     | Pass: "byrd" listed only Byrd's three scores; "ave" the three whose titles begin Ave |
| <a id="m08"></a>M08  | Filter the library         | Choose a language, a voicing and a season                                                                     | Only scores matching all three; the counts update                                               | Fail, then fixed (`89073e1`, `f15b70c`): there was no season control on the Library. Now Latin, SATB and Advent chosen from the menus list only Canite tuba, the one Advent score that is both, and the menus keep the choices |
| <a id="m43"></a>M43  | A score's text             | Edit a score, fill in Text, Translation and Translation credit, save                                         | The score's page shows the text beside the translation, with the credit beneath                 | Pass: the score's page showed the text beside the translation, with the credit beneath |
| <a id="m45"></a>M45  | The voicing prompt         | Plan a score that has no voicing; follow Add it and save a voicing                                           | A quiet line on the piece's row; after saving, back on the service with the line gone           | Pass: "No voicing recorded yet. Add it" on the row; after saving a voicing, back on the service with the line gone |
| <a id="m46"></a>M46  | Library completeness       | Library, Completeness; follow the voicing count                                                              | Counts of scores with no voicing and no language, and the motets with no text listed; the count matches the filtered Library | Pass: "2 scores with no voicing", and the Library that link opens lists 2 scores |

<a id="test-figure-1"></a>

![The Add score form sent empty, with This field is required under Title and under Composer surname](screenshots/testing/m04-score-form-errors.png)

_Test figure 1. M04: an empty score form as the server answers it, each required field marked. The browser's own check, which comes first, was turned off for the picture._

<a id="test-figure-2"></a>

![The page asking whether to delete Parsons' Ave Maria, with Delete and Cancel buttons](screenshots/testing/m06-delete-confirmation.png)

_Test figure 2. M06: deleting asks first._

### 5.3 Importing and exporting

A spreadsheet or a Google Sheets link in, the library out.

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m33"></a>M33  | Import a spreadsheet       | Library, Import; download the template, fill in a few rows, choose the file, Import                           | The chosen file's name and size shown; then the result page with the count, any skipped rows and why, how many have no voicing, and a list of the scores imported with their composer, voicing and language; a notice on the Library | Fail, then fixed (`f4e842b`): the result page asked "Happy with these?" without listing the scores. Since: the file's name and size shown on choosing it; the result page counts what was imported and skipped and how many have no voicing, then lists each score imported with its composer, voicing and language, "(unspecified)" where empty ([Test figure 3](#test-figure-3)); a notice on the Library |
| <a id="m34"></a>M34  | Keep or remove an import   | From the notice, Review it; Keep these scores. Import again; Remove this import and confirm                    | Keeping closes the import; removing deletes its scores, keeping any already planned into a service | Pass: Keep closed the import and the notice went; Remove asked first and took its scores away. A score already planned being kept: by `test_a_score_already_planned_is_kept_and_the_page_says_so` |
| <a id="m35"></a>M35  | A file that's too big      | Choose a file over 2 MB                                                                                       | Said at once, with the Import button disabled; without JavaScript the server refuses it        | Pass: with JavaScript, "big.csv is 2.0 MB, more than the 2.0 MB limit" and Import disabled; without, the server refused it: "The file is larger than 2 MB" |
| <a id="m36"></a>M36  | Export the library         | Library, Export                                                                                               | A CSV named with the date, in the import's columns; it imports into an empty church unchanged  | Pass: `precentor-library-2026-11-10.csv` in the import's columns; imported into a new, empty church and exported again, the two files were identical |
| <a id="m54"></a>M54  | Import from Google Sheets  | Library, Import; paste the link of Google's public example sheet and Import; then a link to a sheet that doesn't exist | The first comes back from Google and is refused for having no Title column; the second says the sheet isn't shared or the link is wrong | Pass: Google's example sheet: "The file has no Title or Composer surname column…"; a sheet that doesn't exist: "Google didn't send the sheet, so either it isn't shared or the link is wrong…" |
| <a id="m62"></a>M62  | Keeping an import twice    | Import a one-row file and open its result page in two tabs; Keep in the first, then in the second; import another, open its Remove page as a Viewer, then remove it as the Conductor | The first keeps it; the second goes to the Library saying it has already gone; the Viewer is refused; the Conductor removes it | Pass, since `65a4a2a`: "Kept 1 score from m62.csv."; the second tab went to the Library with "That import has already been removed or kept."; the Viewer got "Not available to you" (403); "Removed 1 score imported from m62b.csv." |

<a id="test-figure-3"></a>

![An import's result page: 1 score imported, one row skipped for having no title, 1 with no voicing yet, a table listing Christus factus est by Anerio with no voicing, and buttons to keep or remove the import](screenshots/testing/m33-import-result.png)

_Test figure 3. M33: what an import brought in, listed, and what it skipped._

### 5.4 Terms and services

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m09"></a>M09  | Create a term              | Terms, New term, fill in, save                                                                                | The term's page                                                                                 | Pass: the new term's page (the calendar has to be chosen; nothing is assumed) |
| <a id="m10"></a>M10  | Edit and delete a term     | Edit the term's name; then Delete term and confirm                                                            | The new name; then the Terms page without it                                                    | Pass: the new name; after Delete term and confirming, the Terms page without it |
| <a id="m11"></a>M11  | Add a service              | On a term, New service, pick a date                                                                           | The day's occasion is suggested from the date; saving shows the service                         | Pass: for 6 December the form offered "Second Sunday of Advent" with Set as occasion; one click set it, and the saved service shows it |
| <a id="m12"></a>M12  | Edit a service             | Edit service, change the type, save                                                                           | The new type on the service page                                                                | Pass: the heading changed from Sung Mass to Solemn Mass, with the date |
| <a id="m63"></a>M63  | Term and service dates     | New term ending the day before it starts; a service on 25 December in Advent 2026 (29 November to 24 December); Advent to end on 23 December; then, with a service already dated 27 December, rename Advent and leave its dates | Each refused with a plain message beside the date; the rename saved | Pass, since `128c3a0`, `c56b704`, `a00e7b7` and `68721ad`: "A term can't end before it starts."; "Advent 2026 runs from Sun 29 Nov 2026 to Thu 24 Dec 2026, so the service needs a date in between."; "2 services would fall outside these dates, the first on Thu 24 Dec 2026. Move or delete them first."; the renamed term saved |
| <a id="m69"></a>M69  | Several services at once | On Advent 2026, Add several services; try From 28 November; then Vespers, Solemn Vespers, Sundays and solemnities; in the preview untick 20 December, Select none, Select all, untick it again and create; send a second tab opened on the same preview; open one of the services made; on the 1962 term, look at the patterns and pick; without JavaScript, pick one date and create; as the Viewer, open the term and the page; both steps at 320 pixels | The range starts as the term's and is refused outside it; the preview lists the Sundays and the Immaculate Conception, ticked, with their names and the count; the count follows the ticks; each service made has its occasion and the template's slots; dates already made are skipped and said; 1962 names its second pattern for first-class days; picking ticks nothing; it works without JavaScript; the Viewer is refused; nothing wider than the screen | Pass, since `684e6ef` to `3ed02e7`: the range started 29 Nov to 24 Dec, and 28 November gave "Advent 2026 runs from Sun 29 Nov 2026 to Thu 24 Dec 2026, so the dates need to be in between."; five dates ticked, from "Sun 29 Nov: First Sunday of Advent" to "Tue 8 Dec: The Immaculate Conception of the Blessed Virgin Mary", "Create 5 services" ([Test figures 4 to 7](#test-figure-4)); the count went to 4, 0, 5 and 4; "Created 4 services."; the second tab gave "Created 1 service; skipped 4 that already exist."; the 29 November service had the occasion First Sunday of Advent and the slots Psalms, Hymn, Magnificat and Marian antiphon; the 1962 term offered "Sundays and first-class days", and picking listed 22 dates under November and December, none ticked; without JavaScript there was no Select all, and one date ticked gave "Created 1 service." (the button's count stays as served); the Viewer had no button and got 403; both steps fitted at 320. What the test made was deleted afterwards |
| <a id="m70"></a>M70  | Date fields on an iPhone | On an iPhone in Safari, open Add several services, New term, Edit service, New notice and a score's Edit page | Each date field (From and To; the term's start and end; the service's and the notice's date; Last sung) as wide as the fields around it, inside its column, with its date at the left | Fail, accepted as cosmetic, on my iPhone on 12 November: From and To still ran past the right edge of the fields above them after `5bfe255`, though every date was readable, nothing was cut off and the date picker worked ([Test figure 40](#test-figure-40), [Known bugs](#known-bugs)). In WebKit emulating an iPhone at 320 and 393 pixels, every date field lined up with the others, and the browser test `test_a_date_lines_up_with_the_other_fields_on_a_phone_and_a_laptop` checks that at 320 and 1280 |
| <a id="m71"></a>M71  | The score search on an iPhone | On an iPhone in Safari, open a service with a slot that takes a score, scroll until its search box is in the lower half of the screen, tap it and type a letter | No AutoFill bar above the keyboard; the list ends above the keyboard and scrolls inside itself, however many scores match; choosing a score fills the box and closes the list | Pass on my iPhone on 12 November, after `7cbd632` and `54f2288`: no AutoFill bar, only Safari's form bar, and the list stopped above the keyboard, showing four scores at a time and scrolling inside itself ([Test figure 34](#test-figure-34)). Before them, the keyboard hid about half the list. The browser test `test_the_list_stops_at_the_bottom_of_what_can_be_seen` checks the list ends inside a short window and grows when the window does. If the box sits less than about two scores' height above the keyboard, the list keeps that height and still runs under it |

<a id="test-figure-4"></a>

![Add several services to Advent 2026: the Vespers template, Solemn Vespers as the type, From 29/11/2026 To 24/12/2026, and Sundays and solemnities chosen](screenshots/testing/m69-batch-choices-1280.png)

_Test figure 4. M69: the first step, at 1280 pixels._

<a id="test-figure-5"></a>

![The second step: the choices summed up, Select all and Select none, then November and December with the four Sundays of Advent and Tuesday 8 December, the Immaculate Conception, all ticked, and Create 5 services](screenshots/testing/m69-batch-dates-1280.png)

_Test figure 5. M69: the dates, each with its celebration, before anything is made._

<a id="test-figure-6"></a>

![The first step at 320 pixels, its fields one under another](screenshots/testing/m69-batch-choices-320.png)

_Test figure 6. M69: the first step at 320 pixels._

<a id="test-figure-7"></a>

![The second step at 320 pixels, each date's name wrapping beside its box](screenshots/testing/m69-batch-dates-320.png)

_Test figure 7. M69: the dates at 320 pixels._

### 5.5 Slots and pieces

Planning a service: its slots, and proposing, confirming and removing pieces.

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m13"></a>M13  | Slots from a template      | On an empty service, press Mass                                                                               | The Mass slots in order                                                                         | Pass: the Mass template's ten slots, in order |
| <a id="m14"></a>M14  | Reorder a slot             | Move a slot down; then drag one to a new place                                                                | The new order, kept after reloading                                                             | Pass: Move down put the Introit below the Kyrie, kept after reloading. Dragging: by the browser test `test_dragging_a_slot_by_its_handle`, and by me by hand in Chrome (Playwright can't start a native drag in Chrome) |
| <a id="m15"></a>M15  | Propose a piece            | Type in a slot's search box, choose a score                                                                   | The piece listed as Proposed; suitable scores listed first                                      | Pass: typing "Ave" listed the matching scores; choosing one listed it as Proposed with no reload. Suitable scores first: see M41 |
| <a id="m16"></a>M16  | Confirm and unconfirm      | Confirm a proposed piece; then Unconfirm                                                                      | The badge changes each time, and the service's status follows                                   | Pass: Not started; on Confirm the badge read Confirmed and the service In progress; on Unconfirm the badge read Proposed, and the service stayed In progress as a piece is still proposed |
| <a id="m17"></a>M17  | Mark a slot N/A            | Add a slot with "Not needed (N/A)" ticked                                                                     | The slot shows (N/A) and doesn't count against the service's status                             | Pass: the slot read "Extra motet (N/A)" and didn't count against the status |
| <a id="m37"></a>M37  | A slot's kind              | Add slots called Introit, Communion hymn and Procession; then change the Introit's kind to Hymn               | Badges read Proper, Hymn and Other (a procession is no kind of its own); after the change the badge reads Hymn with no reload, and the page keeps its place | Pass: badges Proper, Hymn and Other; Change kind made the Introit's badge Hymn with no reload |
| <a id="m38"></a>M38  | Type a hymn number         | In a Hymn slot, type NEH 123 in the reference box and propose it                                             | The book and number, then the reference box, come before the score search; the piece is listed as NEH 123, with no reload                  | Pass: the book and number, then the reference box, then the score search; "NEH 123" proposed and listed with no reload |
| <a id="m39"></a>M39  | Propose without JavaScript | With JavaScript off, follow Propose a piece on a Hymn slot; submit with nothing chosen, then with a reference  | Book and number, then the reference, then the score list; one message for an empty form; then the service page with the piece | Pass: book, number, reference, then the score list; an empty form said "Choose one: a score, a hymn number or a reference."; Psalm 150 was proposed and the service shown |
| <a id="m52"></a>M52  | Template slots             | Edit Vespers: set Hymn's kind to Motet, swap two numbers, tick Remove on one, add a slot in a blank row, save; apply it to a service | The template lists the new order; the service's slots arrive in it, Hymn as a Motet | Pass: the template listed Hymn (as a Motet), Psalms, Magnificat, Te Deum; a service given it got those slots and kinds |
| <a id="m59"></a>M59  | A piece not in the library | In a Kyrie slot, type Messe solennelle in the search box, choose what it offers and propose it; follow Add to library and save the score with a composer; type Psalm 150 into a Hymn slot; open the service as a Viewer; with JavaScript off, open the Kyrie's propose page | The list offers the text as typed, which goes into the reference box; the row says "Not in the library." with an Add to library link; the score form has the title filled in and goes back to the service; no note on the Hymn slot; the Viewer sees the note but no link; the propose page says anything not in the library can be typed in the reference box | Pass: the only option was `Use "Messe solennelle" as typed (not in the library)`; the arrow key and Enter put the text in the reference box and emptied the search box; the row read "Messe solennelle, Proposed, Not in the library. Add to library"; the form's Title was Messe solennelle, and saving went back to the piece's row on the service, where the piece still says Not in the library, as it stays a reference; nothing under Psalm 150; the Viewer saw the note and no link; the propose page said "Anything not in the library can be typed here" |
| <a id="m60"></a>M60  | Propose and confirm        | On a service In progress, type Mass in G minor in the Kyrie's reference box and press Propose and confirm; type another and press Enter; with JavaScript off, propose a third from the Kyrie's propose page with Propose and confirm | The first listed as Confirmed, the service's status changing with it, and "Piece proposed and confirmed."; Enter only proposes; without JavaScript the same, back on the service page | Pass: Mass in G minor listed as Confirmed, the status went from In progress to Complete as the Kyrie was the last slot unsettled, and the message read "Piece proposed and confirmed."; Enter listed Missa Aeterna Christi munera as Proposed; the propose page had Propose piece then Propose and confirm, and Missa de Angelis came back on the service page as Confirmed |
| <a id="m61"></a>M61  | Double clicks and repeats  | On a Sung Mass with nothing planned, type Mass in G minor in the Kyrie's reference box and double-click Propose piece; double-click its Confirm; then type mass in g minor and propose it again | One request and one piece; one request and the piece Confirmed; the repeat refused with "That's already proposed for this slot." | Pass, since `eda6561`, `99e2b3a` and `8dfa229`: each double-click sent one request; one row, then Confirmed with Unconfirm on its button; the repeat was refused with that message and the slot still had one row |
| <a id="m65"></a>M65  | Removing a piece           | On the Sung Mass of 13 December, Tab to Remove on the Kyrie's proposed Missa brevis and press Enter; Remove the Gradual's Ave Maria, which has a comment, first with Cancel; Remove the confirmed Agnus Dei; with the service open in two tabs, remove the Credo's piece in each; open the service as the Viewer; with JavaScript off, Remove the confirmed Offertory and the proposed Communion; at 320 pixels, Remove the Introit's | Each button named with its piece and slot; a proposed piece with no comments goes at once, focus moving to its slot's form, with a message; the others ask first, saying what goes with them; the second tab says it has already gone; no Remove for the Viewer; without JavaScript a confirmation page, then back on the service with a message; the button fits at 320 | Pass, since `f3353c6`, `954347d` and `606aaf0`: buttons named like "Remove Vigilate (William Byrd) from the Communion"; the Kyrie's row went without a reload, focus in the Kyrie's form, and "Removed Missa brevis (Giovanni Pierluigi da Palestrina) from the Kyrie."; the Gradual's dialog read "Its comment goes with it. This can't be undone." with focus on Cancel, which kept it (Test figures [8](#test-figure-8) and [9](#test-figure-9)); the Agnus Dei's read "It's confirmed, so it will leave the music list.", and the slot then showed "No pieces proposed yet." above its form; the second tab reloaded with "That piece has already been removed."; the Viewer saw 5 pieces and no Remove button; without JavaScript the Offertory's page said the same as the dialog ([Test figure 10](#test-figure-10)), and both came back to the service with "Removed Alma Redemptoris Mater (Plainchant) from the Offertory." and "Removed Vigilate (William Byrd) from the Communion."; at 320 the page was no wider than the window and the button sat between 172 and 261 pixels |
| <a id="m66"></a>M66  | A piece's page from the service | On the Sung Mass of 13 December follow the Introit's Rorate caeli; then Back to the service; on Vespers of 6 December follow the hymn SAH 12; propose a typed reference in an empty Kyrie; open the Advent music list, then print it; open the pew sheet; open the score with `?service=999999` and `?service=abc`; repeat the first at 320 pixels | A score and a hymn link to their pages and a reference doesn't; the score's page says which slots it has in that service and their state, and leads back; the list's titles link on screen and print as plain words; the pew sheet has no links; a bad service is ignored; nothing wider than the screen | Pass, since `29ef886`, `24572bf` and `823ebe2`: the link was `/library/320/?service=164`, and the bar read "Confirmed for the Introit, Sunday 13 December (Third Sunday of Advent)" and "Proposed for the Sanctus, Sunday 13 December (Third Sunday of Advent)" ([Test figures 11 to 12](#test-figure-11)); Back to the service went to `/services/164/`; SAH 12 opened "O come, O come, Emmanuel"; the reference Missa de Angelis had no link, and was removed again; the music list had 40 links, which in print had no underline and the text's colour; the pew sheet had none; both bad values showed the score with no bar; at 320 the page was no wider than the window |
| <a id="m67"></a>M67  | Propose from the library | With Ave Maria (Parsons) marked for Offertory for the test, open its page and Propose; choose the Sung Mass of 20 December; Propose; with a second tab left on the second step without JavaScript, Propose there too; propose it again into a new slot of Midnight Mass, Motet after Communion of kind Motet, with Propose and confirm; without JavaScript, propose Vigilate by the two pages; as the Viewer, open the score and the propose page; repeat the second step at 320 pixels | Coming services listed with term and status, those that already have it disabled; the slots arrive in place, the one it's marked for chosen with the reason, the new slot's fields hidden; back on the service with a message; the second tab refused; the new slot made with its kind; two pages without JavaScript; no button and 403 for the Viewer; nothing wider than the screen | Pass, since `a32478a` to `85fb3c8`: 11 services offered, the 7 that already had it disabled and ending "already proposed", the Mass labelled "Sun 20 Dec 2026, Sung Mass: Advent 2026 (Not started)"; its slots came without a reload, with Offertory chosen and "Chosen because this score is marked for Offertory.", the new slot's fields hidden ([Test figures 13 to 14](#test-figure-13)); "Proposed Ave Maria (Robert Parsons) for the Offertory." on the service; the second tab said "That's already proposed for this slot."; "Proposed and confirmed Ave Maria (Robert Parsons) for the Motet after Communion.", its badge Motet; without JavaScript the second step was a page with the new slot's fields shown, and "Proposed Vigilate (William Byrd) for the Communion."; the Viewer had no Propose and got 403; at 320 the page fitted. What the test added was deleted afterwards |
| <a id="m68"></a>M68  | The score page's service bar | From the Sung Mass of 20 December, follow Ave Maria; Confirm on the bar; then Remove, Cancel, and Remove again; look at the bar at 320 pixels | Confirm and Remove on the bar, each coming back to the score page; Remove asks first for a confirmed piece, and Cancel comes back too | Pass, since `89d33a9`: the bar read "Proposed for the Offertory, Sunday 20 December (Fourth Sunday of Advent)" with Confirm and Remove ([Test figures 15 to 16](#test-figure-15)); Confirm came back to `/library/321/?service=166` reading "Confirmed for the Offertory"; Remove asked "Remove Ave Maria (Robert Parsons)?", whose Cancel led back to the same address; Remove then came back with "Removed Ave Maria (Robert Parsons) from the Offertory." and no line left on the bar; at 320 the page fitted |

<a id="test-figure-8"></a>

![The Gradual's slot on a service page: Ave Maria by Robert Parsons marked Proposed, with Confirm and Remove buttons beside it, and the slot's own Remove at the top right](screenshots/testing/m65-remove-button.png)

_Test figure 8. M65: each piece has its own Remove, beside Confirm._

<a id="test-figure-9"></a>

![A dialog over the service page asking "Remove Ave Maria (Robert Parsons)?" with "Its comment goes with it. This can't be undone.", and Cancel outlined as focused beside Remove](screenshots/testing/m65-remove-dialog.png)

_Test figure 9. M65: a piece with a comment asks first, with focus on Cancel. The message in the corner is from the Kyrie's piece, removed just before._

<a id="test-figure-10"></a>

![A page headed "Remove Alma Redemptoris Mater (Plainchant)?", saying it is from the Offertory at Sung Mass on Sun 13 Dec 2026, that it's confirmed so will leave the music list, and that this can't be undone, with Remove and Cancel](screenshots/testing/m65-remove-page.png)

_Test figure 10. M65: without JavaScript the same question is a page of its own._

<a id="test-figure-11"></a>

![A score's page opened from a service: above the title, a slim bar reading Confirmed for the Introit, Sunday 13 December (Third Sunday of Advent) and Proposed for the Sanctus, the same day, with Back to the service on the right](screenshots/testing/m66-score-from-service-1280.png)

_Test figure 11. M66: a score opened from a service says where it sits in it, at 1280 pixels._

<a id="test-figure-12"></a>

![The same page at 320 pixels, the bar's two lines wrapped above Back to the service, then the title](screenshots/testing/m66-score-from-service-320.png)

_Test figure 12. M66: the same at 320 pixels._

<a id="test-figure-13"></a>

![Propose Ave Maria (Robert Parsons): the Service select set to Sun 20 Dec 2026, Sung Mass, then the Slot select on Offertory: empty with Chosen because this score is marked for Offertory, and the buttons Propose and Propose and confirm](screenshots/testing/m67-propose-1280.png)

_Test figure 13. M67: proposing a score from its page, the slot chosen for the use it's marked for, at 1280 pixels._

<a id="test-figure-14"></a>

![The same two steps at 320 pixels, one above the other](screenshots/testing/m67-propose-320.png)

_Test figure 14. M67: the same at 320 pixels._

<a id="test-figure-15"></a>

![A score's page opened from a service: the bar's two lines, Confirmed for the Introit with Unconfirm and Remove, and Proposed for the Sanctus with Confirm and Remove](screenshots/testing/m68-bar-1280.png)

_Test figure 15. M68: the service bar's own Confirm and Remove, at 1280 pixels._

<a id="test-figure-16"></a>

![The same bar at 320 pixels, each line's buttons wrapped beneath it](screenshots/testing/m68-bar-320.png)

_Test figure 16. M68: the same at 320 pixels._

### 5.6 Suggestions and the day's chants

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m41"></a>M41  | Suggestions with reasons   | On an Advent service, open a Communion slot's search box; then the propose page for the same slot with JavaScript off | Groups Suggested, Suggested sung recently, Other scores; each score with its reasons; the same on the propose page | Pass: Suggested (each with its reasons, such as "For Advent; Already planned this term"), Other scores, and Other scores, sung recently; the same groups on the propose page |
| <a id="m42"></a>M42  | Repeat window              | Settings, set Sung recently means within to 1 week; reopen a slot's list                                    | A score sung two weeks ago is no longer in a "sung recently" group                              | Pass: at 8 weeks the scores sung 4 weeks ago were in the "sung recently" group; at 1 week, none were |
| <a id="m53"></a>M53  | The day's chant (1962)     | On a 1962 service for the Second Sunday of Advent with the Mass template, look at the Gradual; click the chant; then open the Communion's propose page with JavaScript off | "For this day: Ex Sion species decoris ejus" under the search box; one click proposes it and it goes; the propose page offers "Propose Jerusalem, surge et sta" | Pass: "Ex Sion species decoris ejus" under the Gradual; one click proposed it and it was no longer offered; the Communion's propose page offered "Propose Jerusalem, surge et sta" |
| <a id="m56"></a>M56  | The day's chant, Ordinary Form | On the demo church's Sung Mass for the First Sunday of Advent 2026, look at each slot | The Introit, Gradual, Alleluia, Offertory and Communion offer Ad te levavi, Universi, Ostende nobis, Ad te Domine levavi and Dominus dabit benignitatem; the Ordinary's slots offer nothing | Pass: Ad te levavi, Universi, qui te exspectant, Ostende nobis, Ad te Domine levavi and Dominus dabit benignitatem; nothing on the Ordinary's slots |
| <a id="m57"></a>M57  | Days with more to sing     | On 1962 services for Palm Sunday, Good Friday, the Easter Vigil, the Ember Saturday of Lent, Candlemas and All Souls, and an Ordinary Form Good Friday, add Antiphon, Hymn, Responsory, Canticle and Proper slots | Each slot offers the day's chants of its kind in the order sung: Palm Sunday's ten antiphons, the Vigil's Alleluia before its Tract in 1962, the Ember Saturday's four graduals, then Benedictus es and the Tract; no Introit on Good Friday; Dies irae on All Souls | Fail, then fixed (`c5a8833`): a slot named Canticle became Other and missed the Ember Saturday's Benedictus es. Since: Palm Sunday's ten antiphons in order, the Vigil's Confitemini Domino before Laudate Dominum, the four graduals, Benedictus es and the Tract, no Introit on Good Friday in either form, Dies irae on All Souls |
| <a id="m58"></a>M58  | A weekday, Ordinary Form   | Services with no occasion on Wednesday 9 December 2026, Friday 18 December 2026, Tuesday 9 February 2027, Tuesday 2 March 2027 and Tuesday 6 April 2027; look at the Introit and Communion | The Sunday before's chants (Populus Sion; Venite, adoremus; Quasi modo), and nothing on 18 December or in Lent | Fail, then fixed (`945b43f`): the services on 9 December, 9 February and 6 April were server errors. Since: Populus Sion; Venite, adoremus; Quasi modo; and nothing on 18 December or 2 March |

### 5.7 Hymns

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m47"></a>M47  | Hymnals                    | Library, Hymnals; add one, edit it, archive it; try to delete one with hymns sung from it | Listed with copies; archived ones apart; the delete refused with a note to archive instead | Pass: added, edited and archived (then listed under Archived); deleting the hymnal sung from was refused with "Archive it instead" ([Test figure 17](#test-figure-17)) |
| <a id="m48"></a>M48  | A hymn by book and number  | In a Hymn slot, choose the book, type a number, propose; then open the hymn from its hymnal's page and add a first line | NEH 53 on the row, a quiet line asking for its first line until it has one; the hymnal lists it by number | Pass: SAH 99 on the row with "No first line recorded yet" until one was added; the hymnal's page lists 99 with its line |
| <a id="m49"></a>M49  | The same hymn in two books | Give two hymns the same first line; on one's page answer the question both ways | Yes joins them and keeps both numbers; no isn't asked again | Pass: the question was asked; after No it wasn't asked again on either hymn; after Yes the hymn's page lists both SAH 14 and SAH 16 |
| <a id="m50"></a>M50  | Tunes                      | Add tunes; set a hymn's tune in its book; on a hymn in a service choose another tune; open the pew sheet | The row offers the book's tune, then same-metre tunes from the book, then the rest; the sheet prints "NEH 53, tune NEH 115" | Pass: the row offered Its usual tune, Same metre in SAH, then Other tunes, and "8.7.8.7" matched "87 87"; the pew sheet printed "SAH 12, tune SAH 11" |
| <a id="m51"></a>M51  | Suggested hymns            | Tag a hymn for the season; open a Hymn slot on a service in that season; click the suggestion | The hymn listed with its reason; clicking fills in the book and number | Pass: with SAH 16 tagged for Advent, an Advent Vespers' Hymn slot suggested it; clicking filled in SAH and 16 |
| <a id="m55"></a>M55  | Import a hymnal's list     | On a hymnal's page, Import a list; import a file of made-up rows with one row missing its number and an extra column | The result page counts what was added and the new tune, names the skipped row and the column left out, and lists each number added or filled in with what happened to it; the hymnal page shows the new numbers and a notice to review the import | Fail, then fixed (`a79ddab`): the result page asked "Happy with it?" without listing what had changed. Before the fix: 2 hymns added and 1 new tune; row 3 skipped for having no number; the Notes column left out; the hymnal's page lists 20 and 21 with a notice to review the import. Since: the page lists SAH 18 "Filled in: first line", SAH 20 and SAH 21 "Added", in number order with their first lines, and "New tune: Stuttgart" |

<a id="test-figure-17"></a>

![The Hymnals page listing St Aelred's Hymn Book with its copies and filing location](screenshots/testing/m47-hymnals.png)

_Test figure 17. M47: the Hymnals page._

### 5.8 The music list, the pew sheet and Settings

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m18"></a>M18  | The music list             | On a term, Music list; switch between Public and Draft                                                        | Public shows confirmed pieces; Draft marks undecided slots TBC                                  | Pass: the public list showed no TBC, and services with nothing decided "Nothing to display yet"; the draft had its banner and marked 31 slots TBC |
| <a id="m19"></a>M19  | Print the music list       | Press Print                                                                                                   | A clean page without the navigation or buttons                                                  | Fail, then fixed (`61f3790`): the footer's Privacy link printed at the end. Since the fix, Chrome's printed PDF has no navigation, controls or footer ([Test figure 18](#test-figure-18)). Run again at `823ebe2`, after the titles became links on screen: Chrome's PDF had the same four pages, word for word, with no underline, link colour or address on any title |
| <a id="m24"></a>M24  | Settings and crest         | Settings, change the church's name, upload a crest as a logo, save                                            | The name and crest on the music list                                                            | Pass: the new name and the uploaded crest on the music list |
| <a id="m40"></a>M40  | Music list arrangement     | Settings, Music list arrangement: Propers beside the rest; open a term's music list, then print it             | Each service's propers in one list and the rest in another, side by side when wide, stacked on paper | Pass: in the single-column layout the propers and the rest sit side by side on screen and stack when printed at A4 width; in newspaper columns, which are narrow, they stack |
| <a id="m44"></a>M44  | The pew sheet              | From a service, Pew sheet; untick Composers and Update; Print                                                | Confirmed music in order, the motet's text beside its translation; composers gone after Update; prints white without the controls | Pass: the confirmed music in order, with the Ave Maria's Latin beside its English ([Test figure 19](#test-figure-19)); composers gone after unticking and Update, with the choices in the address; printing as in M19 |

<a id="test-figure-18"></a>

![The Advent music list as printed: the church's crest and name, the services in three columns, and no navigation, buttons or footer](screenshots/testing/m19-music-list-print.png)

_Test figure 18. M19: the music list with the print styles, after the fix. Chrome's own printout is the [PDF](screenshots/testing/m19-music-list.pdf), four A4 pages._

<a id="test-figure-19"></a>

![The pew sheet for the First Sunday of Advent, with the Ave Maria's Latin text beside its English translation](screenshots/testing/m44-pew-sheet.png)

_Test figure 19. M44: the pew sheet, with a motet's text beside its translation._

### 5.9 Comments

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m20"></a>M20  | Comment, close, delete     | Comment on a service; reply; Close; as a Conductor, delete the closed thread                                  | The thread appears in the Inbox until closed; then it's deleted                                 | Pass: the reply showed under the comment; the thread was in the Inbox while open and gone once closed; then deleted |

### 5.10 Roles, other churches and errors

| ID   | Feature                    | Steps                                                                                                         | Expected                                                                                        | Result   |
| ---- | -------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------- |
| <a id="m25"></a>M25  | A Viewer refused           | As a Viewer, open `/terms/add/`                                                                               | The "Not available to you" page (403)                                                           | Pass: "Not available to you", status 403 ([Test figure 20](#test-figure-20)) |
| <a id="m26"></a>M26  | Another church's record    | As one church, open the address of another church's score or service                                          | "Page not found" (404)                                                                          | Pass: status 404 for another church's score (the local server runs with `DEBUG` on, so the page itself is checked in M27) |
| <a id="m27"></a>M27  | Error pages                | Open an address that doesn't exist                                                                            | Precentor's own 404 page                                                                        | Pass: Precentor's own 404 page with `DEBUG` off ([Test figure 21](#test-figure-21)) |
| <a id="m64"></a>M64  | A Viewer sees drafts       | As the Viewer, open Advent 2026; Music list, then Draft; the Sung Mass of 13 December; its Pew sheet | Each service's status on the term; the draft with TBC for slots not yet settled; the proposed pieces marked Proposed with no Confirm buttons; the pew sheet | Pass: In progress and Not started on the term page; the draft's "DRAFT" banner with 30 TBC; 5 pieces marked Proposed and no Confirm button; the pew sheet for Sung Mass, Sun 13 Dec 2026 |

<a id="test-figure-20"></a>

![The Not available to you page shown to a Viewer who opens New term, with a Go to Terms button](screenshots/testing/m25-forbidden.png)

_Test figure 20. M25: a Viewer refused, with the reason._

<a id="test-figure-21"></a>

![Precentor's Page not found page, with a Go to Terms button](screenshots/testing/m27-not-found.png)

_Test figure 21. M27: the 404 page, with DEBUG off as on the live site._

[↑ Back to contents](#contents)

## 6. Responsiveness, usability and the keyboard

Run on 10 November 2026 between `f15b70c` and `b500e3f`. R01 to R03 by
[`tools/check_viewports.py`](../tools/check_viewports.py), the rest in
Google Chrome 157. R01 to R03 and R05's measurements were run again at
`8908668`, with the same results apart from R05's count of text.

| ID   | Check | Steps | Expected | Result |
| ---- | ----- | ----- | -------- | ------ |
| <a id="r01"></a>R01  | Phones: 320 and 375 pixels | Every main page at each width, in Chromium, Firefox and WebKit | Nothing wider than the screen except the library table, which scrolls in its own box; no console errors | Pass: all 25 pages at both widths in all three engines ([Test figures 22 to 25](#test-figure-22)). At submission the score form was 3 pixels too wide at 320, fixed in `6bf1062` |
| <a id="r02"></a>R02  | Tablets: 768 and 1024 pixels | The same pages at each width | The layout fills the width without gaps or overlaps; no console errors | Pass: all 25 pages in all three engines ([Test figure 26](#test-figure-26)) |
| <a id="r03"></a>R03  | Laptop: 1280 pixels | The same pages | The layout as in the README's screenshots; no console errors | Pass: all 25 pages in all three engines ([Test figure 27](#test-figure-27)); the README's figures were taken again on the same code |
| <a id="r04"></a>R04  | Keyboard alone | Sign in, open a service, propose and confirm a piece, using only the keyboard | Every step reachable with Tab, Enter and the arrow keys, with a visible outline on each control | Pass: signed in, opened Advent 2026 and its Midnight Mass, chose Mozart's Ave verum corpus with the arrow keys, proposed and confirmed it, using only Tab, typing, the arrow keys and Enter. Every control showed an outline (a term's card is outlined as a whole), and after Confirm the focus stayed on the button, now reading Unconfirm ([Test figure 28](#test-figure-28)) |
| <a id="r05"></a>R05  | Dark mode | Switch the device to dark, then choose Dark in the user menu | Every page readable, with the same contrast as in light | Pass: every visible piece of text on the 25 pages measured against its background, 1,424 in each theme: all meet WCAG AA, the lowest ratio 4.83 in light and 5.7 in dark. Dark chosen in the user menu on a light device applied at once and carried to the next page ([Test figures 29 to 31](#test-figure-29)) |
| <a id="r06"></a>R06  | Without JavaScript | Turn JavaScript off; propose a piece, confirm it, remove a slot | Each works through ordinary pages | Pass: Sicut cervus proposed from the propose page; after Confirm and a fresh load it read Confirmed; Remove asked first on a page of its own, and the slot went |
| <a id="r07"></a>R07  | Links to other sites | Look for any link that leaves Precentor: in the templates with `git grep 'href="http' -- '*.html'`, and in every page as it's sent, rendered from the list [`tools/validate_html.py`](../tools/validate_html.py) uses | Any link to another site opens in a new tab, with `rel="noopener noreferrer"` | Pass, with nothing to change, on 12 November at `04fd132`: no template has one, nothing turns text people type into links, and none of the 77 pages links off the site. Every link stays within Precentor, so none needs a new tab |

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

<a id="test-figure-22"></a>

![A service page at 320 pixels in Chromium: the heading, its buttons and the first slot fitting the width](screenshots/testing/r01-320-service-chromium.png)

_Test figure 22. R01: a service at 320 pixels in Chromium._

<a id="test-figure-23"></a>

![The same service page at 320 pixels in Firefox](screenshots/testing/r01-320-service-firefox.png)

_Test figure 23. R01: the same in Firefox._

<a id="test-figure-24"></a>

![The same service page at 320 pixels in WebKit](screenshots/testing/r01-320-service-webkit.png)

_Test figure 24. R01: the same in WebKit, the engine Safari uses._

<a id="test-figure-25"></a>

![The library at 320 pixels, its filters stacked and the table scrolling inside its own box](screenshots/testing/r01-320-library-chromium.png)

_Test figure 25. R01: the library at 320 pixels; only the table scrolls sideways._

<a id="test-figure-26"></a>

![A service page at 768 pixels](screenshots/testing/r02-768-service-chromium.png)

_Test figure 26. R02: a service at 768 pixels._

<a id="test-figure-27"></a>

![The library at 1280 pixels, with the search box and the Language, Voicing, Season and Use menus in one row above the table](screenshots/testing/r03-1280-library-chromium.png)

_Test figure 27. R03: the library at 1280 pixels._

<a id="test-figure-28"></a>

![The Terms page after pressing Tab three times, with an outline round the Terms link and round the first term's card](screenshots/testing/r04-keyboard-focus.png)

_Test figure 28. R04: keyboard focus, shown round the link and the card it's in._

<a id="test-figure-29"></a>

![A service page in dark colours](screenshots/testing/r05-dark-service.png)

_Test figure 29. R05: a service in dark mode._

<a id="test-figure-30"></a>

![The music list in dark colours, with the liturgical colours lightened](screenshots/testing/r05-dark-music-list.png)

_Test figure 30. R05: the music list in dark mode._

<a id="test-figure-31"></a>

![The Settings page in dark colours](screenshots/testing/r05-dark-settings.png)

_Test figure 31. R05: Settings in dark mode._

### Real devices

I checked these on the live site on 12 November 2026, on my own phone
and tablet and on the PC I built Precentor on, after the deploy of
`c785009`. The screenshots are from the devices themselves; names and
email addresses are blurred. The iPhone and iPad were in dark mode, as
the PC was for Members and Invite someone.

| Device | Browser | Width | What was checked | Result | Screenshots |
| ------ | ------- | ----- | ---------------- | ------ | ----------- |
| iPhone 14 Pro, iOS 27.0.1 | Safari | 393 points | Terms, a service, the score search with the keyboard up, the library, the music list, the pew sheet, removing a slot, proposing from the library, adding several services | Pass on 12 November, with the two iPhone issues under [Known bugs](#known-bugs) | Test figures [32](#test-figure-32), [33](#test-figure-33), [34](#test-figure-34), [35](#test-figure-35), [36](#test-figure-36), [37](#test-figure-37), [38](#test-figure-38), [39](#test-figure-39), [40](#test-figure-40) |
| 12.9-inch iPad Pro (3rd generation), iPadOS 26.7.2 | Safari | 1024 points | Signing in, Terms, a term, a service, adding several services and its dates | Pass on 12 November | Test figures [41](#test-figure-41), [42](#test-figure-42), [43](#test-figure-43), [44](#test-figure-44), [45](#test-figure-45), [46](#test-figure-46) |
| PC, Windows 11 Home 26H2 | Chrome | 1920 pixels | Signing in, Terms, a term before and after adding several services, a service, the pew sheet, the library, a score, proposing from the library, Members, inviting someone | Pass on 12 November | Test figures [47](#test-figure-47), [48](#test-figure-48), [49](#test-figure-49), [50](#test-figure-50), [51](#test-figure-51), [52](#test-figure-52), [53](#test-figure-53), [54](#test-figure-54), [55](#test-figure-55), [56](#test-figure-56), [57](#test-figure-57) |

<a id="test-figure-32"></a>

![Terms in dark colours on an iPhone: Michaelmas 2026, starting in 3 days, with its progress bar and next service, and Lent with no services yet](screenshots/testing/d09-iphone-14-pro-terms.png)

_Test figure 32. D09: Terms. iPhone 14 Pro, iOS 27.0.1, Safari, dark mode._

<a id="test-figure-33"></a>

![A service's Introit slot on an iPhone: its kind, Move down, the kind menu and Change kind, the confirmed Adorate Deum, and the search box, reference box and two Propose buttons one under another](screenshots/testing/d09-iphone-14-pro-service.png)

_Test figure 33. D09: a service's first slot. iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-34"></a>

![The score search open on an iPhone with the keyboard up: four scores under Other scores, the list ending above the keyboard and Safari's form bar](screenshots/testing/d09-iphone-14-pro-propose-search-keyboard.png)

_Test figure 34. D09: the score search with the keyboard up: the list stops above the keyboard and scrolls inside itself ([row M71](#m71)). iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-35"></a>

![The library on an iPhone: 21 scores, the table scrolled sideways inside its own frame to show the Title column](screenshots/testing/d09-iphone-14-pro-library.png)

_Test figure 35. D09: the library, its table scrolled sideways inside its frame. iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-36"></a>

![Michaelmas 2026's music list on an iPhone, under the church's crest: the Mass of Sunday 15th November, slot by slot](screenshots/testing/d09-iphone-14-pro-music-list.png)

_Test figure 36. D09: the music list. iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-37"></a>

![The pew sheet for Mass on Sunday 15 November on an iPhone: the crest, the celebration, and each slot's music under its heading](screenshots/testing/d09-iphone-14-pro-pew-sheet.png)

_Test figure 37. D09: the pew sheet. iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-38"></a>

![The dialog for removing the Introit on an iPhone, saying its proposed piece and comments go with it, with Cancel focused](screenshots/testing/d09-iphone-14-pro-remove-dialog.png)

_Test figure 38. D09: removing a slot: the confirmation dialog. iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-39"></a>

![Proposing Missa Pour ung plaisir from its own page on an iPhone: the Service menu, Show its slots and a link back to the score](screenshots/testing/d09-iphone-14-pro-propose-from-library.png)

_Test figure 39. D09: proposing a score from its own page. iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-40"></a>

![Add several services to Lent on an iPhone: Template, Service type, From and To, the From and To boxes running further right than the two above, and the three date choices](screenshots/testing/d09-iphone-14-pro-add-several-services.png)

_Test figure 40. D09: Add several services. From and To run past the right edge of the fields above them ([Known bugs](#known-bugs)). iPhone 14 Pro, iOS 27.0.1, Safari._

<a id="test-figure-41"></a>

![The sign-in page on an iPad with the keyboard up and Safari offering Passwords above it](screenshots/testing/d09-ipad-login.png)

_Test figure 41. D09: signing in. 12.9-inch iPad Pro, iPadOS 26.7.2, Safari, dark mode._

<a id="test-figure-42"></a>

![Terms on an iPad: Michaelmas 2026 and Lent as cards, New term at the right](screenshots/testing/d09-ipad-terms.png)

_Test figure 42. D09: Terms. 12.9-inch iPad Pro, iPadOS 26.7.2, Safari._

<a id="test-figure-43"></a>

![Michaelmas 2026 on an iPad: its six buttons on one line, two services with their status, the empty notices and the comment box](screenshots/testing/d09-ipad-term.png)

_Test figure 43. D09: a term. 12.9-inch iPad Pro, iPadOS 26.7.2, Safari._

<a id="test-figure-44"></a>

![Mass on Sunday 22 November on an iPad: the Mass Setting, Introit and Gradual slots, each with its confirmed piece and the search box, reference box and Propose buttons on one line](screenshots/testing/d09-ipad-service.png)

_Test figure 44. D09: a service. 12.9-inch iPad Pro, iPadOS 26.7.2, Safari._

<a id="test-figure-45"></a>

![Add several services to Lent on an iPad: Template, Service type, From and To, and Every Sunday chosen](screenshots/testing/d09-ipad-add-several-services.png)

_Test figure 45. D09: Add several services. 12.9-inch iPad Pro, iPadOS 26.7.2, Safari._

<a id="test-figure-46"></a>

![The dates for Lent on an iPad, January to April 2027, each ticked with its celebration, under Select all and Select none, and Create 24 services](screenshots/testing/d09-ipad-add-several-services-dates.png)

_Test figure 46. D09: the dates to create, all ticked. 12.9-inch iPad Pro, iPadOS 26.7.2, Safari._

<a id="test-figure-47"></a>

![The sign-in page in Chrome on a 1920-pixel screen, the email address blurred](screenshots/testing/d09-desktop-login.png)

_Test figure 47. D09: signing in. PC, Windows 11 Home 26H2, Chrome, 1920 pixels wide._

<a id="test-figure-48"></a>

![Terms in Chrome: Michaelmas 2026 and Lent as cards](screenshots/testing/d09-desktop-terms.png)

_Test figure 48. D09: Terms. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-49"></a>

![Lent in Chrome before any services: its buttons, including Add several services, and the empty Services and Notices boxes](screenshots/testing/d09-desktop-term-empty.png)

_Test figure 49. D09: a term with no services yet. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-50"></a>

![Lent in Chrome after adding several services: 0 of 24 services complete, the first seven Sundays listed as Not started, and the message Created 24 services](screenshots/testing/d09-desktop-term-batch-created.png)

_Test figure 50. D09: the same term once 24 services were created. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-51"></a>

![Mass for the Baptism of the Lord in Chrome: the Mass Setting, Introit and Gradual slots, with Chrome's own list of earlier entries open under a reference box](screenshots/testing/d09-desktop-service-search.png)

_Test figure 51. D09: a service. The list under the reference box is Chrome's own, of what had been typed there before. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-52"></a>

![The pew sheet for Mass on Sunday 10 January 2027 in Chrome, with nothing confirmed yet, its two options, Update and Print](screenshots/testing/d09-desktop-pew-sheet.png)

_Test figure 52. D09: the pew sheet of a service with nothing confirmed yet. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-53"></a>

![The library in Chrome: Search, Language and Voicing, 21 scores in a table with their voicing, language, copies and last sung](screenshots/testing/d09-desktop-library.png)

_Test figure 53. D09: the library. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-54"></a>

![Missa L'hora passa in Chrome: Propose, Edit and Delete, its details and an empty service history](screenshots/testing/d09-desktop-score-detail.png)

_Test figure 54. D09: a score. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-55"></a>

![Proposing Missa L'hora passa in Chrome, the Service menu open on the coming services, each with its term and status](screenshots/testing/d09-desktop-propose-from-library.png)

_Test figure 55. D09: proposing a score from its own page, the service menu open. PC, Windows 11 Home 26H2, Chrome._

<a id="test-figure-56"></a>

![Members in Chrome in dark colours: the owner, a Conductor, with the role menu and Change role, the name blurred, and no invitations waiting](screenshots/testing/d09-desktop-members.png)

_Test figure 56. D09: Members. PC, Windows 11 Home 26H2, Chrome, dark mode._

<a id="test-figure-57"></a>

![Invite someone in Chrome in dark colours: three roles with Viewer chosen, Who it's for and Make the link](screenshots/testing/d09-desktop-invite.png)

_Test figure 57. D09: inviting someone. PC, Windows 11 Home 26H2, Chrome, dark mode._

[↑ Back to contents](#contents)

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
| `61f3790` | The footer's Privacy link printed at the end of the music list and the pew sheet ([row M19](#m19)) |
| `945b43f` | An Ordinary Form weekday service with no occasion, borrowing the Sunday before's chants, was a server error when it had an Alleluia or Tract slot ([row M58](#m58)) |
| `c5a8833` | A slot named Canticle was given the kind Other, so it was never offered the day's canticle ([row M57](#m57)) |
| `89073e1`, `f15b70c` | The Library had no season, use or occasion filter, though the README and [row M08](#m08) said it had; a season in its address only reordered the list |
| `f4e842b` | An import's result page asked "Happy with these?" without listing the scores it had brought in ([row M33](#m33)); tests in `0398cc3` |
| `a79ddab` | A hymnal import's result page had the same gap: it counted the hymns added and filled without listing them ([row M55](#m55)); tests in `60f7d08` |
| `5398c9e` | Each time a proposal was refused on the service page, another "Propose a piece" link appeared under the slot, as the form sent back carried the link with it, and only the first was hidden |
| `511ea00` | After a score was proposed from a slot's search box, a hymn number or reference typed next in the same slot was refused with "Choose one", as the reset form kept the score in its hidden field |
| `eda6561` | Nothing disabled a button while its request ran, so a quick double-click proposed a piece twice or turned Confirm on and off ([row M61](#m61)); tests in `104e125` |
| `8dfa229` | The same score, hymn or reference could be proposed twice in one slot ([row M61](#m61)); tests in `ffd14e3` |
| `99e2b3a` | Confirm toggled whatever the piece's state, so the same request twice undid itself ([row M61](#m61)); tests in `8fcd514` |
| `65a4a2a` | Keeping an import that had already been kept or removed gave "Page not found", where removing it again gave a message; Remove was guarded only by signing in, not by the library role ([row M62](#m62)); tests in `0beae19` |
| `128c3a0` | A term could end before it started ([row M63](#m63)); tests in `4875a87` |
| `c56b704` | A service could be dated outside its term ([row M63](#m63)); tests in `f494aed` |
| `a00e7b7`, `68721ad` | Changing a term's dates could leave its services outside it ([row M63](#m63)); tests in `ed0e69f` |
| `f3353c6`, `954347d`, `606aaf0` | A piece could only go with its whole slot, so a wrong or replaced proposal stayed listed until the slot was removed and rebuilt. Each piece now has its own Remove ([row M65](#m65)); tests in `68961ec`, `7d5638b` and `b0fafbf` |
| `c5e13b1` | At 320 pixels a slot's "Or type a reference" box was 18 pixels wider than its card and ran over the card's edge. The page itself was no wider than the screen, so [row R01](#r01)'s check didn't catch it; tests in `a410aaa` |
| `29ef886`, `24572bf`, `823ebe2` | A piece's title on the service page and the music list led nowhere, so checking a score meant finding it again in the library. Each title now links to its score or hymn, and a score opened that way says where it sits in the service, with a way back; printed, a title stays plain words ([row M66](#m66)); the tests are in the same commits |
| `a32478a`, `311edad`, `ae8ab69`, `12624d1`, `85fb3c8`, `89d33a9` | Planning started only from a service, so a conductor looking at a score had to find the service first, and the score page's service bar could only send them back there. A score can now be proposed from its own page into a coming service's slot or a new one, and the bar confirms or removes it (rows [M67](#m67) and [M68](#m68)); the tests are in the same commits |
| `684e6ef`, `829cfc4`, `0038ea7`, `f02d0d3`, `3ed02e7` | A term's services were added one at a time, so a term of Sundays meant the same form a dozen times. Several can now be added at once, each with its celebration and the template's slots, after a preview of the dates ([row M69](#m69)); the tests are in the same commits |
| `fc87a4e` | A test, a note in the stylesheet and one of my own tests used Choral Evensong, an Anglican service, in a Catholic app; Solemn Vespers and Vespers take its place |
| `5bfe255` | On an iPhone the date fields ran wider than the fields around them and centred their dates, as iOS draws its own date control; I saw it on From and To in Add several services ([row M70](#m70)). Its layout test is in the same commit. On the phone the fields are still wider, kept as a known bug ([Known bugs](#known-bugs)) |
| `7cbd632`, `54f2288` | On an iPhone the keyboard hid about half the score search's list, as the keyboard covers the page without making the window smaller, and iOS can put its AutoFill bar above the keyboard for a text field. The box is now a search field, which keeps Escape from clearing it, and the list stops at the room left above the keyboard ([row M71](#m71)); the tests are in the same commits |

The flake8 findings left at submission (16 long lines, a variable named
`l` and a lambda) were cleared in `86ad9e8`. Five known issues are listed below:
three are in a test and in the testing tools, and two are cosmetic limits on an iPhone.

### Known bugs

| Bug                                                                                                                                            | Effect                                                                                                         | Why it's not fixed yet                                                                  |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| The browser test for confirming a piece failed once in a full run of the planning tests on 30 October | None for people using the site; a test can fail without a real fault | Not reproduced: on 1 November it passed 20 runs on its own and 6 runs of all the planning browser tests, as it has in every full run since. It passed again in the full run of 10 November. If it fails again, the traceback names the line |
| Playwright's own Chromium (149) stops drawing after any cross-document page transition, so a click from one page to the next leaves the old page on screen | None for people using the site: Chrome 157 and Edge 157 cross-fade and draw normally | A fault in the testing browser, not the site, so the manual tests were run in Google Chrome. The automated browser tests, which mostly work within one page, pass in it |
| With JavaScript turned off in Playwright, its check before each click says any page reached by a click can't be clicked, as if the whole page were covering the button | None for people using the site: on the same pages a real mouse click works in Chrome 157, with or without a window | A fault in the testing tool, not the site, so [row M65](#m65)'s steps without JavaScript used real mouse clicks after the page had settled |
| On an iPhone in Safari, date fields (From and To on Add several services) run past the right edge of the fields around them ([Test figure 40](#test-figure-40)) | Cosmetic: the layout stays usable, nothing is cut off, and the date picker works | WebKit on iOS draws `type="date"` as its own control. `5bfe255` let it shrink, capped it at its column and started its text at the left; on the phone the dates now sit at the left, but the fields are still wider. Accepted as it is |
| On an iPhone, the keyboard takes the lower half of the screen, so the score search's list has only the room above it ([Test figure 34](#test-figure-34)) | The list shows about four scores at a time; it scrolls inside itself, and the page can still be scrolled | A limit of a search box with a list under it on a small screen. Since `54f2288` the list stops above the keyboard instead of running under it |

[↑ Back to contents](#contents)

## 8. Deployment check

On the [live site](https://precentor.onrender.com), after each deploy.
The merge of the work since submission was rehearsed and carried out
as set down in [`merge_record.md`](merge_record.md); the middle column is
the checks after that deploy, on 10 November 2026, and the last those
after the old columns were dropped, in a deploy of its own on 11 November.

| ID | Check | Expected | At the first deploy, 23 October | After the merge | After dropping the old columns, 11 November |
| -- | ----- | -------- | ------------------------------- | --------------- | ------------------------------------------- |
| <a id="d01"></a>D01 | The site loads | The sign-in page, after up to a minute if the site was asleep | Pass: the sign-in page loaded on the live site on 23 October | Pass on 10 November: the sign-in page answered 200 | Pass: the sign-in page answered 200, and `/` sent a signed-out visitor to it |
| <a id="d02"></a>D02 | `http://` goes to `https://` | Typing `http://precentor.onrender.com` ends on the `https://` address | Pass: `http://precentor.onrender.com/` answered 301, to `https://precentor.onrender.com/` | Pass: `http://precentor.onrender.com/` answered 301, to the `https://` address | Pass: 301, to the `https://` address |
| <a id="d03"></a>D03 | `DEBUG` is off | A made-up address shows Precentor's 404 page, not Django's debug page | Pass: a made-up address answered 404 with Precentor's own page | Pass: a made-up address answered 404 with Precentor's own page | Pass: 404 with Precentor's own page, and no debug page |
| <a id="d04"></a>D04 | Static files and the crest | Styles, fonts and an uploaded crest all load | Pass: stylesheets and the favicon answered 200 from their hashed static addresses; the crest was uploaded and shown on the live site on 22 October | Pass: both stylesheets and the preloaded font answered 200 from their hashed addresses; a crest uploaded to a test church showed, from `/settings/crest/<church>/<version>/` | Pass: both stylesheets, both preloaded fonts and the sign-in page's scripts answered 200 from their hashed addresses; a crest uploaded to a test church showed on Settings |
| <a id="d05"></a>D05 | Register and plan | Register a test church, add a score, a term and a service, propose and confirm a piece, open the music list | Pass on the live site on 23 October: registered a test church, added a score, a term and a service, applied the Mass template, proposed and confirmed a piece, and saw it on the music list | Pass: registered a test church, added a score, a term and a service (its occasion set from the date), applied the Mass template, proposed and confirmed a piece, and saw it on the music list; the church was then deleted | Pass: registered a test church, added a score, a term and a service (the First Sunday of Advent, set from the date), applied the Mass template (10 slots, each with its kind), proposed and confirmed Missa de Angelis in the Kyrie, and saw it on the music list; the church was then deleted |
| <a id="d06"></a>D06 | The build | Render's build log shows the 28 new migrations applied, `load_calendar` loading the chants, then "Your service is live" | Not part of the first deploy | Pass: Render reported the deploy successful, and the pages that need the new migrations work ([D08](#d08)) | Pass: Render showed the deploy of `7fd2e74` live. Its two migrations ran: the dropped columns couldn't be left empty, so the new church's settings and its service, saved without them, would have been refused had the columns still been there |
| <a id="d07"></a>D07 | The copied data | `python manage.py check_copied_data`, run from my computer against the live database, ends "Everything was copied" | Not part of the first deploy | Pass: run from my computer against the live database, with no difference reported | Not repeated: it was the evidence that the columns could go, and the check went with them |
| <a id="d08"></a>D08 | The pages added since | Hymnals, a hymnal, the pew sheet, the completeness page, the template editor, the Library's Season and Use menus, and a Proper slot offering the day's chant all open and work | Not part of the first deploy | Pass: the Introit offered Ad te levavi; the pew sheet listed the piece; a hymnal was created and its page opened; the completeness page and the template editor opened; the Library's Season and Use menus listed Advent (1) and Mass (1), and Advent filtered it to 1 score | Pass: a new church's template editor showed its slots as rows with their kinds; the Introit offered Ad te levavi, which was proposed and then taken out with Remove ("Removed Ad te levavi from the Introit."); the pew sheet listed the confirmed piece; a hymnal was created; the completeness page opened; Advent (1) filtered the Library to 1 score |
| <a id="d09"></a>D09 | Real devices | The checks in the table at the end of [section 6](#6-responsiveness-usability-and-the-keyboard), on my phone and tablet | Not part of the first deploy | Pass: on an iPhone 14 Pro and a 12.9-inch iPad Pro in Safari, and on my PC in Chrome ([section 6, Real devices](#real-devices)) | Not repeated: nothing a page shows changed with this deploy |

### After v2.0.0 (11 November 2026)

`main` and the tag `v2.0.0` were pushed at `08cd1ec`, after the full
suite (1,013 tests), the migrations check, flake8 and ESLint had all
passed on that commit. The deploy had no migrations. It was live at
23:30, when the new page for adding several services began to answer.
The checks below were run from my computer against the live site, on
a test church deleted afterwards.

| ID | Result |
| -- | ------ |
| [D01](#d01) | Pass: the sign-in page answered 200, and `/` sent a signed-out visitor to it |
| [D02](#d02) | Pass: 301, to the `https://` address |
| [D03](#d03) | Pass: 404 with Precentor's own page, and no debug page |
| [D04](#d04) | Pass: both stylesheets (the main one under its new hashed name), both preloaded fonts and the sign-in page's scripts answered 200; a crest uploaded to the test church showed on Settings |
| [D05](#d05) | Pass: registered, added a score, a term and a service (the First Sunday of Advent, from the date), applied the Mass template (10 slots with their kinds), proposed and confirmed Missa de Angelis, and saw it on the music list |
| [D06](#d06) | Build log not read; the new page answering from 23:30 shows the build finished, and this deploy had no migrations to apply |
| [D07](#d07) | Not needed: nothing in this deploy touched the data's shape |
| [D08](#d08) | Pass: the template editor with its slot rows and kinds, the Advent filter, the day's chant offered on the Introit, the pew sheet, a new hymnal and the completeness page |
| [D09](#d09) | Pass on 12 November, after `c785009`: on my iPhone, iPad and PC, with the two iPhone issues under [Known bugs](#known-bugs) ([Real devices](#real-devices)) |
| New | Pass: adding several services offered the term's four Sundays, "Create 4 services", and made them ("Created 4 services."); Rorate caeli proposed from its own page went into the first empty slot ("Proposed Rorate caeli (Plainchant) for the Introit."); its link on the service led to the score's page, whose bar read "Proposed for the Introit, Sunday 29 November (First Sunday of Advent)", and Confirm there came back reading "Confirmed" |

[↑ Back to contents](#contents)
