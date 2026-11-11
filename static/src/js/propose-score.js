// Proposing a score from its own page. Choosing a service fetches its
// slots in place, rather than opening the second page, and the new
// slot's fields show only once New slot… is chosen. Without JavaScript
// the same steps are two pages, with the new slot's fields always shown.
import { applyFragments, getFragments, whileBusy } from "./ajax.js";

// The second step, whichever way it arrived: hide the new slot's fields
// unless New slot… is the choice.
function initSlotStep() {
  const select = document.getElementById("propose-slot-select");
  const fields = document.getElementById("propose-new-slot");
  if (!select || !fields) return;
  const show = () => {
    fields.hidden = select.value !== "new";
  };
  select.addEventListener("change", show);
  show();
}

const serviceForm = document.getElementById("propose-service-form");

if (serviceForm) {
  const select = serviceForm.querySelector("select");
  const button = serviceForm.querySelector("button[type=submit]");
  select.addEventListener("change", async () => {
    if (!select.value) return;
    const url = `${serviceForm.action}?service=${encodeURIComponent(select.value)}`;
    try {
      const data = await whileBusy(serviceForm, button, () => getFragments(url));
      applyFragments(data.fragments);
      initSlotStep();
    } catch {
      // Anything unexpected: open the second step as a page instead.
      serviceForm.requestSubmit(button);
    }
  });
  initSlotStep();
}
