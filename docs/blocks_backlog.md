# Precentor — Blocks Backlog

Blocks identified while applying global styles and Compositions across
every page (deliberately done _before_ any Block is built, so this list
reflects real, observed repetition rather than guessed-at components).
Each entry notes where it was spotted and why it's a Block rather than
a one-off.

## Built

| Block/Utility                       | File                      | Notes                                                                                                                                                                                                |
| ----------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Badge                               | `blocks/badge.css`        | Service status + piece confirmation state. Shares colour vocabulary with the comment card, but as an inline chip rather than a card-level accent. "Not started" uses the `inactive` tokens so it darkens in dark mode. |
| Comment card                        | `blocks/comment-card.css` | Styles the pre-existing `comment`/`comment--{state}` hooks. A closed comment's border uses `inactive-border`.                                                                                       |
| Form                                | `blocks/form.css`         | Styles Django's default `{{ form.as_p }}` output once, applies everywhere. Also styles `.helptext`, and gives single-line inputs the shared control height.                                         |
| Button                              | `blocks/button.css`       | Shares `--layout-control-height` with inputs; the primary hover uses `action-primary-hover`.                                                                                                       |
| Site nav                            | `blocks/nav.css`          | Includes `.nav-count`, the open-comment count beside Inbox. Active-page highlighting still not implemented (Phase 3).                                                                              |
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
| `.visually-hidden`                  | `utilities/utilities.css` | The rest of the original "action link group" utility (`.text-danger`) was superseded by the `.btn-confirm`/`.btn-ghost`/`.btn-danger` variants in `blocks/button.css` — a deliberate button choice reads better than a recoloured link. |

## Not built as separate Blocks (covered by existing work)

- **Filter bar** — `form.css`'s general `input`/`select` styling already covers the filter form's controls; no dedicated Block needed.

## Outstanding

- Nav active-page highlighting (template logic, not CSS). Planned for Phase 3 of [`overhaul_plan.md`](overhaul_plan.md), along with the button hierarchy, a page-header block and empty states.
