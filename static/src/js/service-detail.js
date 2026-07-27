import { postForm, applyFragments, fragmentToElement, AjaxError } from "./ajax.js";
import { showToast } from "./toast.js";

function initServiceDetail() {
  const main = document.querySelector("main");
  // #roles-list is always rendered on service_detail.html, even with zero
  // roles yet — unlike .role-block, which only exists once a role does.
  if (!document.getElementById("roles-list")) return;

  main.addEventListener("submit", async (event) => {
    const form = event.target;

    if (form.matches(".ajax-toggle-confirm")) {
      event.preventDefault();
      const button = form.querySelector("button[id^='confirm-toggle-']");
      try {
        const data = await postForm(form.action, new FormData(form));
        applyFragments(data.fragments, button.id);
        showToast("Piece updated.", "success");
      } catch (err) {
        showToast("Couldn't update that piece — try again.", "danger");
      }
      return;
    }

    if (form.matches(".ajax-propose-piece")) {
      event.preventDefault();
      const rolePk = form.dataset.rolePk;
      try {
        const data = await postForm(form.action, new FormData(form));
        const unmatched = applyFragments(data.fragments);
        const ul = document.getElementById(`role-${rolePk}-pieces`);
        Object.values(unmatched).forEach((html) => {
          document.getElementById(`role-${rolePk}-pieces-empty`)?.remove();
          ul.appendChild(fragmentToElement(html));
        });
        form.reset();
        showToast("Piece proposed.", "success");
      } catch (err) {
        if (err instanceof AjaxError) applyFragments(err.data.fragments);
        else showToast("Couldn't add that piece — try again.", "danger");
      }
      return;
    }

    if (form.matches(".ajax-add-role")) {
      event.preventDefault();
      try {
        const data = await postForm(form.action, new FormData(form));
        const unmatched = applyFragments(data.fragments);
        const list = document.getElementById("roles-list");
        Object.values(unmatched).forEach((html) => {
          document.getElementById("roles-list-empty")?.remove();
          list.appendChild(fragmentToElement(html));
        });
        form.reset();
        showToast("Role added.", "success");
      } catch (err) {
        if (err instanceof AjaxError) applyFragments(err.data.fragments);
        else showToast("Couldn't add that role — try again.", "danger");
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", initServiceDetail);
