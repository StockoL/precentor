// The service page sends its scores once, as JSON (Django's json_script),
// already ranked with the ones suited to the service first. Every slot's
// search box reads that one list, so the page doesn't carry a full
// <select> for each slot. Without JavaScript, each slot links to a page
// with the list instead (planning/_add_piece_form.html).
let scoreOptions;

function getScoreOptions() {
  if (scoreOptions === undefined) {
    const source = document.getElementById("score-options");
    scoreOptions = source ? JSON.parse(source.textContent) : null;
  }
  return scoreOptions;
}

function buildCombobox(container) {
  const options = getScoreOptions();
  const form = container.closest("form");
  const valueInput = container.querySelector("input[name='score']");
  if (!options || !form || !valueInput) return;

  const listboxId = `${form.id}-listbox`;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "score-combobox__input";
  input.setAttribute("aria-label", container.dataset.label);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", listboxId);
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-haspopup", "listbox");
  input.setAttribute("autocomplete", "off");
  input.placeholder = "Search scores…";

  const listbox = document.createElement("ul");
  listbox.id = listboxId;
  listbox.className = "score-combobox__listbox";
  listbox.setAttribute("role", "listbox");
  listbox.hidden = true;

  container.append(input, listbox);

  let filtered = [];
  let activeIndex = -1;

  function renderOptions() {
    listbox.innerHTML = "";
    filtered.forEach((option, index) => {
      const li = document.createElement("li");
      li.id = `${listboxId}-option-${index}`;
      li.setAttribute("role", "option");
      li.textContent = option.label;
      li.dataset.value = option.value;
      if (index === activeIndex) li.setAttribute("aria-selected", "true");
      listbox.appendChild(li);
    });
  }

  function openList() {
    listbox.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function closeList() {
    listbox.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
  }

  function choose(option) {
    valueInput.value = option.value;
    input.value = option.label;
    closeList();
  }

  input.addEventListener("input", () => {
    const query = input.value.trim().toLowerCase();
    filtered = query ? options.filter((option) => option.label.toLowerCase().includes(query)) : options;
    activeIndex = -1;
    renderOptions();
    openList();
  });

  function showAllOptions() {
    filtered = options;
    activeIndex = -1;
    renderOptions();
    openList();
  }

  // Both "focus" and "click" are needed: focus doesn't re-fire on a
  // second click while the input is already focused (e.g. right after
  // choosing a result), so a click-only handler is required too for
  // the list to reliably reopen every time a user clicks the input.
  input.addEventListener("focus", showAllOptions);
  input.addEventListener("click", showAllOptions);

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (listbox.hidden) {
        filtered = options;
        renderOptions();
        openList();
      }
      activeIndex = Math.min(activeIndex + 1, filtered.length - 1);
      input.setAttribute("aria-activedescendant", `${listboxId}-option-${activeIndex}`);
      renderOptions();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      input.setAttribute("aria-activedescendant", `${listboxId}-option-${activeIndex}`);
      renderOptions();
    } else if (event.key === "Enter") {
      if (activeIndex >= 0 && filtered[activeIndex]) {
        event.preventDefault();
        choose(filtered[activeIndex]);
      }
    } else if (event.key === "Escape") {
      closeList();
    }
  });

  listbox.addEventListener("mousedown", (event) => {
    const li = event.target.closest("li");
    if (!li) return;
    const option = filtered.find((o) => o.value === li.dataset.value);
    if (option) choose(option);
  });

  document.addEventListener("click", (event) => {
    if (!container.contains(event.target)) closeList();
  });

  // Typing a new search clears the earlier choice, so the form can't
  // submit a score the box no longer shows.
  input.addEventListener("input", () => {
    valueInput.value = "";
  });

  // Swap the link for the form only once the widget is fully built; if
  // anything above throws, the link stays and still works.
  form.hidden = false;
  document.querySelector(`[data-fallback-for="${form.id}"]`)?.setAttribute("hidden", "");
}

export function initScorePickers(root = document) {
  root.querySelectorAll(".score-combobox").forEach((container) => {
    if (container.dataset.enhanced) return;
    container.dataset.enhanced = "true";
    buildCombobox(container);
  });
}

document.addEventListener("DOMContentLoaded", () => initScorePickers());
