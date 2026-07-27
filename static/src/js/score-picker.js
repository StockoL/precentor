// Pure progressive enhancement over RolePieceForm's existing <select> —
// the form/select itself is never changed. Each role's form already has
// a distinct id (see RolePieceForm(auto_id=...) in planning/views.py),
// so this reads that real id straight from data-target rather than
// generating or rewriting ids itself.
function buildCombobox(container) {
  const targetId = container.dataset.target;
  const select = document.getElementById(targetId);
  if (!select) return;

  const options = Array.from(select.options)
    .filter((option) => option.value)
    .map((option) => ({ value: option.value, label: option.textContent }));

  const listboxId = `${targetId}-listbox`;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "score-combobox__input";
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
    select.value = option.value;
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

  input.addEventListener("focus", () => {
    filtered = options;
    activeIndex = -1;
    renderOptions();
    openList();
  });

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

  const preselected = options.find((option) => option.value === select.value);
  if (preselected) input.value = preselected.label;

  // Only hide the native control's wrapping <p> (label + select) once
  // the enhancement is fully built — if anything above throws, this
  // line never runs and the real <select> stays visible and usable.
  (select.closest("p") || select).classList.add("score-combobox__native-select--hidden");
}

export function initScorePickers(root = document) {
  root.querySelectorAll(".score-combobox").forEach((container) => {
    if (container.dataset.enhanced) return;
    container.dataset.enhanced = "true";
    buildCombobox(container);
  });
}

document.addEventListener("DOMContentLoaded", () => initScorePickers());
