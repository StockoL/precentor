# Precentor — Blocks Backlog

Blocks identified while applying global styles and Compositions across
every page (deliberately done _before_ any Block is built, so this list
reflects real, observed repetition rather than guessed-at components).
Each entry notes where it was spotted and why it's a Block rather than
a one-off.

## Built

| Block/Utility                       | File                      | Notes                                                                                                                                                                                                |
| ----------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Badge                               | `blocks/badge.css`        | Service status + piece confirmation state. Shares colour vocabulary with the comment card, but as an inline chip rather than a card-level accent.                                                    |
| Comment card                        | `blocks/comment-card.css` | Styles the pre-existing `comment`/`comment--{state}` hooks.                                                                                                                                          |
| Form                                | `blocks/form.css`         | Styles Django's default `{{ form.as_p }}` output once, applies everywhere.                                                                                                                           |
| Button                              | `blocks/button.css`       |                                                                                                                                                                                                      |
| Site nav                            | `blocks/nav.css`          | Active-page highlighting still not implemented — needs `request.resolver_match`, a template-logic addition, not pure CSS.                                                                            |
| Role block                          | `blocks/role-block.css`   |                                                                                                                                                                                                      |
| Term summary                        | `blocks/term-summary.css` |                                                                                                                                                                                                      |
| `.text-danger` / `.visually-hidden` | `utilities/utilities.css` | "Action link group" (originally logged as a Block) turned out to be a Utility concern — grouping was already handled by `.cluster`; only the Delete link's colour needed a single-property override. |

## Not built as separate Blocks (covered by existing work)

- **Filter bar** — `form.css`'s general `input`/`select` styling already covers the filter form's controls; no dedicated Block needed.

## Outstanding

- Nav active-page highlighting (template logic, not CSS)
