import { postForm, applyFragments, fragmentToElement, AjaxError } from "./ajax.js";
import { showToast } from "./toast.js";

// Generic by design: works off whatever content_type_id/object_id are
// already in the DOM (via _comment_form.html's action URL), not
// hardcoded to one page — _thread.html renders identically whether
// included from service_detail.html or term_detail.html.
function initComments() {
  const thread = document.querySelector(".comment-thread");
  if (!thread) return;

  thread.addEventListener("submit", async (event) => {
    const form = event.target;

    if (form.matches(".ajax-add-comment")) {
      event.preventDefault();
      const isReply = Boolean(form.querySelector('input[name="parent_id"]'));
      try {
        const data = await postForm(form.action, new FormData(form));
        const unmatched = applyFragments(data.fragments);
        Object.values(unmatched).forEach((html) => {
          document.getElementById("comment-list-empty")?.remove();
          document.getElementById("comment-list").appendChild(fragmentToElement(html));
        });
        form.reset();
        showToast(isReply ? "Reply posted." : "Comment posted.", "success");
      } catch (err) {
        if (err instanceof AjaxError) applyFragments(err.data.fragments);
        else showToast("Couldn't post that comment — try again.", "danger");
      }
      return;
    }

    if (form.matches(".ajax-toggle-close")) {
      event.preventDefault();
      try {
        const data = await postForm(form.action, new FormData(form));
        applyFragments(data.fragments);
      } catch (err) {
        showToast("Couldn't update that comment — try again.", "danger");
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", initComments);
