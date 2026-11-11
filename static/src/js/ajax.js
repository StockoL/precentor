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

// Every fetch() in this project MUST go through postForm() or
// getFragments(): they're the only places X-Requested-With is set (fetch() does not send it by
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

// The GET counterpart, for fragments a page asks for without changing
// anything (the slots of the service chosen when proposing a score).
// The same header, so the view answers in JSON rather than a page.
export async function getFragments(url) {
  const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new AjaxError(response.status, data);
  return data;
}

// Runs one AJAX submit with its button disabled and marked busy, so a
// quick double-click can't send it twice. Both are put back in finally,
// whatever happens, so an error never leaves a form that can't be sent.
// This runs before the caller applies the response, so a button the
// response then replaces is replaced by a fresh one, enabled as served.
// A form sent without a button (a chant's, by
// requestSubmit) uses its first submit button. A disabled button loses
// focus, so a button that had it gets it back, before the caller moves
// focus anywhere else.
export async function whileBusy(form, submitter, work) {
  const button = submitter ?? form.querySelector("button[type=submit], button:not([type])");
  if (!button) return work();
  const hadFocus = document.activeElement === button;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  try {
    return await work();
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    if (hadFocus) button.focus();
  }
}

// Swaps each fragment into the DOM by id. IDs with no matching element
// are returned in `unmatched` for the caller to append (feature-specific
// knowledge, kept out of this generic function). If focusId is given,
// re-queries (never the stale pre-swap reference) and focuses it after
// all swaps land. The element must keep the same id across every
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
