import { postForm, applyFragments, fragmentToElement, AjaxError } from "./ajax.js";
import { showToast } from "./toast.js";
import { initScorePickers } from "./score-picker.js";
import { confirmAction } from "./confirm-dialog.js";

// The slot list is redrawn whole after a move; its search boxes need
// building again.
function afterSlotsMoved(fragments) {
  applyFragments(fragments);
  initScorePickers(document.getElementById("roles-list"));
}

// Keep focus on the button that was pressed. A slot that reaches the top
// or bottom loses that button (role-block.css hides it), so then focus
// its partner instead.
function focusMoveButton(id) {
  const button = document.getElementById(id);
  const partner = document.getElementById(
    id.startsWith("move-up-") ? id.replace("move-up-", "move-down-") : id.replace("move-down-", "move-up-")
  );
  if (button && button.offsetParent !== null) button.focus();
  else partner?.focus();
}

function slotOrder() {
  return Array.from(document.querySelectorAll("#roles-list > .role-block"))
    .map((block) => block.dataset.rolePk)
    .join(",");
}

// Dragging a slot by its handle. Native drag and drop needs a mouse or
// trackpad, so the Move up and Move down buttons stay for keyboards and
// phones. The listeners sit on <main>, so they keep working after the
// list is redrawn.
function initSlotDragging(main) {
  let dragging = null;
  let orderBefore = "";

  // Only the handle starts a drag, so text in a slot can still be selected.
  main.addEventListener("pointerdown", (event) => {
    const handle = event.target.closest(".role-block__handle");
    if (handle) handle.closest(".role-block").draggable = true;
  });
  main.addEventListener("pointerup", () => {
    if (!dragging) main.querySelectorAll(".role-block[draggable=true]").forEach((b) => (b.draggable = false));
  });
  // The handle sits in the slot's <summary>; a click on it shouldn't fold the slot.
  main.addEventListener("click", (event) => {
    if (event.target.closest(".role-block__handle")) event.preventDefault();
  });

  main.addEventListener("dragstart", (event) => {
    const block = event.target.closest?.(".role-block");
    if (!block || !block.draggable) return;
    dragging = block;
    orderBefore = slotOrder();
    block.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", block.dataset.rolePk);
  });

  main.addEventListener("dragover", (event) => {
    if (!dragging) return;
    const target = event.target.closest?.(".role-block");
    if (!target || target === dragging || target.parentElement !== dragging.parentElement) return;
    event.preventDefault();
    const box = target.getBoundingClientRect();
    const before = event.clientY < box.top + box.height / 2;
    target.parentElement.insertBefore(dragging, before ? target : target.nextElementSibling);
  });

  main.addEventListener("drop", (event) => {
    if (dragging) event.preventDefault();
  });

  // Holding a slot near the top or bottom of the window scrolls the page,
  // faster the nearer the edge, so a slot can be carried past the ones on
  // screen. The browser keeps sending dragover while the mouse is still,
  // so the slot keeps finding its place as the list moves under it. This
  // listens on the whole document, because the header and footer can sit
  // in those edge bands.
  const EDGE = 80;
  const MAX_STEP = 18;
  let pointerY = null;
  let frame = null;

  function scrollStep() {
    frame = null;
    if (!dragging || pointerY === null) return;
    const fromBottom = window.innerHeight - pointerY;
    let step = 0;
    if (pointerY < EDGE) step = -MAX_STEP * (1 - pointerY / EDGE);
    else if (fromBottom < EDGE) step = MAX_STEP * (1 - fromBottom / EDGE);
    if (!step) return;
    window.scrollBy(0, Math.round(step) || Math.sign(step));
    frame = requestAnimationFrame(scrollStep);
  }

  document.addEventListener("dragover", (event) => {
    if (!dragging) return;
    pointerY = event.clientY;
    frame ??= requestAnimationFrame(scrollStep);
  });

  main.addEventListener("dragend", async () => {
    if (!dragging) return;
    const block = dragging;
    dragging = null;
    pointerY = null;
    if (frame) cancelAnimationFrame(frame);
    frame = null;
    block.draggable = false;
    block.classList.remove("is-dragging");
    const order = slotOrder();
    if (order === orderBefore) return;

    const form = document.getElementById("slot-order-form");
    const data = new FormData(form);
    data.set("order", order);
    try {
      afterSlotsMoved((await postForm(form.action, data)).fragments);
      showToast("Slots moved.", "success");
    } catch (err) {
      // The server sends the list as it really is, so the page matches.
      if (err instanceof AjaxError && err.data.fragments) afterSlotsMoved(err.data.fragments);
      showToast("Couldn't move those slots. Try again.", "danger");
    }
  });
}

function initServiceDetail() {
  const main = document.querySelector("main");
  // #roles-list is always rendered on service_detail.html, even with zero
  // roles yet — unlike .role-block, which only exists once a role does.
  if (!document.getElementById("roles-list")) return;
  initSlotDragging(main);

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
        if (err instanceof AjaxError) {
          // The swapped-in form fragment carries a brand-new .score-combobox
          // wrapper (previously enhanced one was just destroyed by the
          // outerHTML swap) — re-init scoped to just this form.
          applyFragments(err.data.fragments);
          initScorePickers(document.getElementById(`add-piece-form-${rolePk}`));
        } else {
          showToast("Couldn't add that piece — try again.", "danger");
        }
      }
      return;
    }

    if (form.matches(".ajax-move-slot")) {
      event.preventDefault();
      const { slotName, direction } = form.dataset;
      const buttonId = form.querySelector("button").id;
      try {
        const data = await postForm(form.action, new FormData(form));
        afterSlotsMoved(data.fragments);
        focusMoveButton(buttonId);
        showToast(`Moved ${slotName} ${direction}.`, "success");
      } catch (err) {
        showToast("Couldn't move that slot. Try again.", "danger");
      }
      return;
    }

    // A slot with pieces asks first, with the wording the page put on the
    // form. Focus then moves to the slot that took its place, or the one
    // before, or the Add a slot box when none are left.
    if (form.matches(".ajax-remove-slot")) {
      event.preventDefault();
      const { slotName, confirmTitle } = form.dataset;
      if (confirmTitle) {
        const confirmed = await confirmAction({
          title: confirmTitle,
          message: form.dataset.confirmMessage,
          confirmLabel: form.dataset.confirmLabel,
        });
        if (!confirmed) return;
      }
      const block = form.closest(".role-block");
      const neighbour = block.nextElementSibling ?? block.previousElementSibling;
      const neighbourId = neighbour?.matches(".role-block") ? neighbour.id : null;
      const data = new FormData(form);
      data.set("confirm", "1");
      try {
        afterSlotsMoved((await postForm(form.action, data)).fragments);
        const next = neighbourId && document.querySelector(`#${neighbourId} summary`);
        (next || document.getElementById("id_role_name"))?.focus();
        showToast(`Removed ${slotName}.`, "success");
      } catch (err) {
        showToast("Couldn't remove that slot. Try again.", "danger");
      }
      return;
    }

    // Using another template replaces the slots, so ask first. The page
    // marks those buttons with the dialog's wording; on yes, the form goes
    // ahead as normal, with replace=1, and the page reloads.
    if (form.matches(".apply-template[data-confirm-title]")) {
      event.preventDefault();
      const confirmed = await confirmAction({
        title: form.dataset.confirmTitle,
        message: form.dataset.confirmMessage,
        confirmLabel: form.dataset.confirmLabel,
      });
      if (!confirmed) return;
      const replace = document.createElement("input");
      replace.type = "hidden";
      replace.name = "replace";
      replace.value = "1";
      form.append(replace);
      form.submit();
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
        // The new slot needs its search box built; .dataset.enhanced
        // stops the slots already there being built twice.
        initScorePickers(list);
        form.reset();
        showToast("Slot added.", "success");
      } catch (err) {
        if (err instanceof AjaxError) applyFragments(err.data.fragments);
        else showToast("Couldn't add that slot — try again.", "danger");
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", initServiceDetail);
