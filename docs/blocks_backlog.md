# Precentor — Blocks Backlog

Blocks identified while applying global styles and Compositions across
every page (deliberately done _before_ any Block is built, so this list
reflects real, observed repetition rather than guessed-at components).
Each entry notes where it was spotted and why it's a Block rather than
a one-off.

| Block             | First spotted on   | Notes                                                                                                                                                                                           |
| ----------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nav               | `base.html`        | Currently bare `.cluster` classes only. Needs its own spacing/active-page-highlight treatment once more pages exist to see it against.                                                          |
| Term summary card | `term_list.html`   | "X of Y services complete." Natural candidate to share colour logic with the eventual status badge.                                                                                             |
| Status label      | `term_detail.html` | `{{ service.status }}` shown as bare text — needs the status-badge colour treatment discussed early in the design pass.                                                                         |
| Form              | `term_form.html`   | `{{ form.as_p }}`'s internal label/input/error markup is untouched by any Composition — genuinely a component concern, not a layout one. Will recur on every create/edit page across every app. |
| Action link group | `term_detail.html` | The Edit/Delete/View-music-list `.cluster` — likely wants a more deliberate visual treatment (e.g. distinguishing a "safe" action from a destructive one) than bare links.                      |

Further entries added as the Compositions sweep continues across
`library`, the rest of `planning`, and `comments`.
