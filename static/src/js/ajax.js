const CSRF_COOKIE_NAME = "csrftoken";

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export class AjaxError extends Error {
  constructor(status, data) {
    super(`AJAX request failed with status ${status}`);
    this.status = status;
    this.data = data;
  }
}

// Every fetch() in this project MUST go through postForm() — it's the
// only place X-Requested-With is set (fetch() does not send it by
// default, unlike jQuery's $.ajax), so no call site can forget it and
// silently fall back to a full-page redirect.
export async function postForm(url, formData) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "X-Requested-With": "XMLHttpRequest",
      "X-CSRFToken": getCookie(CSRF_COOKIE_NAME),
    },
    body: formData,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new AjaxError(response.status, data);
  return data;
}

// Swaps each fragment into the DOM by id. IDs with no matching element
// are returned in `unmatched` for the caller to append (feature-specific
// knowledge, kept out of this generic function). If focusId is given,
// re-queries (never the stale pre-swap reference) and focuses it after
// all swaps land — the element must keep the same id across every
// state it can render as for this to find the right node.
export function applyFragments(fragments, focusId) {
  const unmatched = {};
  Object.entries(fragments).forEach(([id, html]) => {
    const el = document.getElementById(id);
    if (el) {
      el.outerHTML = html;
    } else {
      unmatched[id] = html;
    }
  });
  if (focusId) document.getElementById(focusId)?.focus();
  return unmatched;
}

export function fragmentToElement(html) {
  const template = document.createElement("template");
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}
