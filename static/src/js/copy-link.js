// A Copy link button beside each link that's passed on by hand (an
// invitation or a reset link). The button is made here, so without
// JavaScript there's no button that does nothing; the read-only box is
// still there to select and copy by hand.
import { showToast } from "./toast.js";

function addCopyButton(container) {
  const input = container.querySelector("input[readonly]");
  if (!input) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn";
  button.textContent = "Copy link";
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(input.value);
      showToast("Link copied.", "success");
    } catch {
      // The clipboard can be refused (an old browser, or permission
      // denied), so fall back to selecting the text for the person.
      input.select();
      showToast("Couldn't copy it automatically. The link is selected; copy it with Ctrl+C or Cmd+C.", "warning");
    }
  });
  input.after(button);
}

document.querySelectorAll(".copy-link").forEach(addCopyButton);
