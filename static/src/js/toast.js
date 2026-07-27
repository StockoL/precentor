const AUTO_DISMISS_MS = 6000;

function region() {
  return document.getElementById("toast-region");
}

export function showToast(message, tag = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast--${tag}`;
  toast.setAttribute("role", tag === "danger" ? "alert" : "status");

  const text = document.createElement("span");
  text.textContent = message; // never innerHTML — message may originate from user-editable data (e.g. a Score title)

  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.className = "toast-dismiss";
  dismiss.setAttribute("aria-label", "Dismiss");
  dismiss.textContent = "×";
  dismiss.addEventListener("click", () => toast.remove());

  toast.append(text, dismiss);
  region().appendChild(toast);
  setTimeout(() => toast.remove(), AUTO_DISMISS_MS);
}

function promoteServerMessages() {
  const list = document.getElementById("server-messages");
  if (!list) return;
  list.querySelectorAll("li").forEach((li) => {
    showToast(li.textContent, li.dataset.tag || "info");
  });
  list.remove();
}

document.addEventListener("DOMContentLoaded", promoteServerMessages);
