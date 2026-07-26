# Precentor — Blocks Backlog

Blocks identified while applying global styles and Compositions across
every page (deliberately done _before_ any Block is built, so this list
reflects real, observed repetition rather than guessed-at components).
Each entry notes where it was spotted and why it's a Block rather than
a one-off.

| Block             | First spotted on      | Notes                                                                                                                                                                                                                                               |
| ----------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nav               | `base.html`           | Currently bare `.cluster` classes only. Needs its own spacing/active-page-highlight treatment once more pages exist to see it against.                                                                                                              |
| Term summary card | `term_list.html`      | "X of Y services complete." Natural candidate to share colour logic with the eventual status badge.                                                                                                                                                 |
| Status label      | `term_detail.html`    | `{{ service.status }}` shown as bare text — needs the status-badge colour treatment discussed early in the design pass.                                                                                                                             |
| Form              | `term_form.html`      | `{{ form.as_p }}`'s internal label/input/error markup is untouched by any Composition — genuinely a component concern, not a layout one. Will recur on every create/edit page across every app.                                                     |
| Action link group | `term_detail.html`    | The Edit/Delete/View-music-list `.cluster` — likely wants a more deliberate visual treatment (e.g. distinguishing a "safe" action from a destructive one) than bare links.                                                                          |
| Filter bar        | `score_list.html`     | Label+select pairs, currently nested `.cluster`s only. A real Block would style the `<select>`s consistently and probably add a "clear filters" affordance.                                                                                         |
| Piece row         | `service_detail.html` | Score description + confirm/un-confirm button, currently a bare `.cluster` with `space-between`. Strong candidate to share visual language with the status label (confirmed/proposed as a small state indicator, similar to the status badge).      |
| Role block        | `service_detail.html` | Heading + pieces list + propose-form, currently a nested `.flow` only. Might benefit from a subtle container (border/background) to visually separate one role from the next, since right now two adjacent roles are distinguished only by spacing. |

Further entries added as the Compositions sweep continues across
`library`, the rest of `planning`, and `comments`.
