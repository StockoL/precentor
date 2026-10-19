# Precentor — Blocks Backlog

Blocks identified while applying global styles and Compositions across
every page (deliberately done _before_ any Block is built, so this list
reflects real, observed repetition rather than guessed-at components).
Each entry notes where it was spotted and why it's a Block rather than
a one-off.

## Built

| Block/Utility                       | File                      | Notes                                                                                                                                                                                                |
| ----------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Badge                               | `blocks/badge.css`        | Service status + piece confirmation state. Shares colour vocabulary with the comment card, but as an inline chip rather than a card-level accent. "Not started" uses the `inactive` tokens so it darkens in dark mode. Also Sung (success) and Scheduled (warning) for a score's service history. |
| Comment card                        | `blocks/comment-card.css` | Styles the pre-existing `comment`/`comment--{state}` hooks. A closed comment's border uses `inactive-border`.                                                                                       |
| Form                                | `blocks/form.css`         | Styles Django's default `{{ form.as_p }}` output once, applies everywhere. Also styles `.helptext`, fieldsets and legends, keeps checkboxes at their natural size, gives single-line inputs the shared control height, and borders fields Django marks `aria-invalid`. |
| Button                              | `blocks/button.css`       | A hierarchy: neutral default, `.btn-primary` for the one main action in a view, `.btn-ghost`, `.btn-danger`; each works on `<a>` too. Shares `--layout-control-height` with inputs. |
| Site nav                            | `blocks/nav.css`          | Includes `.nav-count`, the open-comment count beside Inbox, and styles the link marked `aria-current` with an underline. Has its own `view-transition-name`, so it stays put between pages. |
| User menu                           | `blocks/user-menu.css`    | A `<details>` disclosure in the nav with Appearance (System / Light / Dark), Settings and Log out.                                                                                                  |
| Page header                         | `blocks/page-header.css`  | Page title on the left, the page's actions on the right, wrapping beneath on a phone.                                                                                                              |
| Detail list                         | `blocks/detail-list.css`  | A `<dl>` of label-value facts on detail pages, in two aligned columns.                                                                                                                             |
| Toolbar                             | `blocks/toolbar.css`      | A row of labelled filter controls lined up along the bottom edge (the Library's search and filters).                                                                                               |
| Data table                          | `blocks/data-table.css`   | The Library's dense, sortable table: sticky header, tabular figures, sideways scrolling on a phone.                                                                                                |
| Tag input                           | `blocks/tag-input.css`    | Chips and a search box over a `<select multiple>` (the score form's suitability fields; `tag-input.js`).                                                                                          |
| Empty state                         | `blocks/empty-state.css`  | A dashed box where a list is empty, saying what belongs there and offering the action that adds the first one.                                                                                     |
| Skip link                           | `blocks/skip-link.css`    | Added in October 2026: hidden above the viewport until keyboard focus, then jumps to `<main>`.                                                                                                     |
| List row                            | `blocks/list-row.css`     | Row-per-item lists (services, notices, pieces, inbox). Lifts the global 60ch measure so a row spans the content width.                                                                            |
| Card                                | `blocks/card.css`         | Bordered panel used for terms and slots.                                                                                                                                                           |
| Toast                               | `blocks/toast.css`        | Success and error messages after AJAX actions, and server messages after a reload.                                                                                                                |
| Role block                          | `blocks/role-block.css`   | One slot on the service page (the CSS keeps the model's name).                                                                                                                                     |
| Term summary                        | `blocks/term-summary.css` |                                                                                                                                                                                                      |
| Liturgical accent                   | `blocks/liturgical-accent.css` | Occasion eyebrow, accent rule and dot, reading `--accent`; see `design_system.md`.                                                                                                            |
| Music list                          | `blocks/music-list.css`   | The printable list, including the Public / Draft toggle and the unlayered print rules.                                                                                                            |
| Score combobox                      | `blocks/score-combobox.css` | The type-to-search score picker over a native `<select>`.                                                                                                                                       |
| Crest crop                          | `blocks/crest-crop.css`   | The crop frame for the crest upload on Settings.                                                                                                                                                   |
| `[hidden]`                          | `utilities/utilities.css` | Makes the `hidden` attribute win over any block that sets `display`.                                                                                                                               |
| `.visually-hidden`                  | `utilities/utilities.css` | The rest of the original "action link group" utility (`.text-danger`) was superseded by the `.btn-primary`/`.btn-ghost`/`.btn-danger` variants in `blocks/button.css` — a deliberate button choice reads better than a recoloured link. |

## Not built as separate Blocks (covered by existing work)

- **Filter bar** — `form.css`'s general `input`/`select` styling already covers the filter form's controls; no dedicated Block needed.

## Outstanding

Nothing at the moment. The page-by-page pass in Phase 4 of [`overhaul_plan.md`](overhaul_plan.md) may turn up more.
