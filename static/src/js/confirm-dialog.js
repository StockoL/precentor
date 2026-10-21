// A confirmation dialog in the house style, in place of window.confirm(),
// whose look the browser decides. It's a native <dialog> opened with
// showModal(), so focus stays inside it, Escape cancels, and screen
// readers announce it as a dialog; the heading names it and the message
// describes it.
//
//   if (!(await confirmAction({ title: "Delete this comment?", ... }))) return;
//
// Resolves true for the confirm button, false for Cancel, Escape or a
// click outside. Focus starts on Cancel, the safe choice, and returns to
// wherever it was when the dialog closes.

let instance = 0;

export function confirmAction({ title, message, confirmLabel, cancelLabel = "Cancel" }) {
  instance += 1;
  const id = `confirm-dialog-${instance}`;
  const previousFocus = document.activeElement;

  const dialog = document.createElement("dialog");
  dialog.className = "confirm-dialog card flow";
  dialog.setAttribute("aria-labelledby", `${id}-title`);
  dialog.setAttribute("aria-describedby", `${id}-message`);

  const heading = document.createElement("h2");
  heading.id = `${id}-title`;
  heading.textContent = title;

  const text = document.createElement("p");
  text.id = `${id}-message`;
  text.textContent = message;

  const actions = document.createElement("div");
  actions.className = "cluster confirm-dialog__actions";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn-ghost";
  cancel.textContent = cancelLabel;
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "btn-danger";
  confirm.textContent = confirmLabel;
  actions.append(cancel, confirm);

  dialog.append(heading, text, actions);
  document.body.append(dialog);

  return new Promise((resolve) => {
    let answer = false;
    cancel.addEventListener("click", () => dialog.close());
    confirm.addEventListener("click", () => {
      answer = true;
      dialog.close();
    });
    // A click on the backdrop lands on the dialog itself, outside its box.
    dialog.addEventListener("click", (event) => {
      const box = dialog.getBoundingClientRect();
      const outside =
        event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
      if (event.target === dialog && outside) dialog.close();
    });
    dialog.addEventListener("close", () => {
      dialog.remove();
      if (previousFocus && document.contains(previousFocus)) previousFocus.focus();
      resolve(answer);
    });

    dialog.showModal();
    cancel.focus();
  });
}
