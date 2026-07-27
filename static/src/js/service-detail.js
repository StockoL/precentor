import { postForm, applyFragments } from "./ajax.js";
import { showToast } from "./toast.js";

function initServiceDetail() {
  const main = document.querySelector("main");
  if (!main.querySelector(".role-block")) return;

  main.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches(".ajax-toggle-confirm")) return;
    event.preventDefault();

    const button = form.querySelector("button[id^='confirm-toggle-']");
    try {
      const data = await postForm(form.action, new FormData(form));
      applyFragments(data.fragments, button.id);
      showToast("Piece updated.", "success");
    } catch (err) {
      showToast("Couldn't update that piece — try again.", "danger");
    }
  });
}

document.addEventListener("DOMContentLoaded", initServiceDetail);
