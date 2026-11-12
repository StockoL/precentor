// The service page sends its scores once, as JSON (Django's json_script),
// each with what a suggestion rests on: its occasion and season tags, its
// use types, when it was last sung. Every slot's search box reads that one
// list, so the page doesn't carry a full <select> for each slot, and
// groups it for its own slot. Without JavaScript, each slot links to a
// page with the list instead (planning/_add_piece_form.html).
let scoreOptions;
let useTypes;

function readJson(id, fallback) {
  const source = document.getElementById(id);
  return source ? JSON.parse(source.textContent) : fallback;
}

function getScoreOptions() {
  if (scoreOptions === undefined) scoreOptions = readJson("score-options", null);
  return scoreOptions;
}

function getUseTypes() {
  if (useTypes === undefined) useTypes = readJson("use-types", []);
  return useTypes;
}

const GROUPS = [
  ["suggested", "Suggested"],
  ["suggested_recent", "Suggested, sung recently"],
  ["other", "Other scores"],
  ["other_recent", "Other scores, sung recently"],
];
const GROUP_KEYS = GROUPS.map(([key]) => key);
const GROUP_LABELS = Object.fromEntries(GROUPS);

// The slot's use type: the church's one named like the slot, or else like
// its kind, read from the slot's badge so a kind just changed counts. The
// same rule as slot_use_type() in planning/suggestions.py.
function slotUseType(container) {
  const badge = document.getElementById(`kind-badge-${container.dataset.rolePk}`);
  const kind = badge ? badge.textContent.trim() : "";
  for (const name of [container.dataset.slotName || "", kind]) {
    const found = getUseTypes().find((useType) => useType.name.toLowerCase() === name.toLowerCase());
    if (found) return found;
  }
  return null;
}

// Each score's group and reasons for this slot, as placed() in
// planning/suggestions.py: an occasion counts more than a season, a season
// more than a use type. The sort is stable, so the server's title order
// holds within each group.
function arrange(options, useType) {
  const placed = options.map((option) => {
    const forUse = useType !== null && option.useTypes.includes(useType.id);
    const strength = [Boolean(option.occasion), Boolean(option.season), forUse];
    const reasons = [option.occasion, option.season].filter(Boolean).map((name) => `For ${name}`);
    if (forUse) reasons.push(`For ${useType.name}`);
    if (option.sung) reasons.push(option.sung);
    if (option.inTerm) reasons.push("Already planned this term");
    const group = (strength.some(Boolean) ? "suggested" : "other") + (option.recent ? "_recent" : "");
    const rank = [GROUP_KEYS.indexOf(group), ...strength.map((part) => (part ? 0 : 1))];
    return { ...option, group, rank, reasons };
  });
  return placed.sort((a, b) => {
    const difference = a.rank.findIndex((part, index) => part !== b.rank[index]);
    return difference === -1 ? 0 : a.rank[difference] - b.rank[difference];
  });
}

function buildCombobox(container) {
  if (!getScoreOptions()) return;
  const form = container.closest("form");
  const valueInput = container.querySelector("input[name='score']");
  if (!form || !valueInput) return;
  // Worked out again each time the list opens, as the slot's kind may
  // have changed since the page loaded.
  let options = [];

  const listboxId = `${form.id}-listbox`;

  const input = document.createElement("input");
  input.type = "search";
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

  // A heading starts each group. It's for the eye only; each option names
  // its group through aria-describedby, and its reasons are in its text.
  function renderOptions() {
    listbox.innerHTML = "";
    let group = null;
    filtered.forEach((option, index) => {
      if (option.group !== group && GROUP_LABELS[option.group]) {
        group = option.group;
        const heading = document.createElement("li");
        heading.id = `${listboxId}-${group}`;
        heading.className = "score-combobox__group";
        heading.setAttribute("role", "presentation");
        heading.setAttribute("aria-hidden", "true");
        heading.textContent = GROUP_LABELS[group];
        listbox.appendChild(heading);
      }
      const li = document.createElement("li");
      li.id = `${listboxId}-option-${index}`;
      li.setAttribute("role", "option");
      if (!option.typed) li.setAttribute("aria-describedby", `${listboxId}-${group}`);
      li.textContent = option.label;
      if (option.reasons.length) {
        const reasons = document.createElement("span");
        reasons.className = "score-combobox__reasons";
        reasons.textContent = option.reasons.join("; ");
        li.append(" ", reasons);
      }
      li.dataset.index = index;
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

  // The "as typed" option moves the text to the reference box, where it
  // would have gone without the search, and leaves no score chosen.
  function choose(option) {
    if (option.typed) {
      valueInput.value = "";
      input.value = "";
      closeList();
      const reference = form.querySelector("input[name='reference']");
      reference.value = option.text;
      reference.focus();
      return;
    }
    valueInput.value = option.value;
    input.value = option.label;
    closeList();
  }

  input.addEventListener("input", () => {
    options = arrange(getScoreOptions(), slotUseType(container));
    const text = input.value.trim();
    const query = text.toLowerCase();
    filtered = query ? options.filter((option) => option.label.toLowerCase().includes(query)) : options;
    // Nothing matches: offer the text as a reference instead, as an option
    // like the others, so the arrow keys, Enter and a screen reader reach it.
    if (query && !filtered.length) {
      filtered = [{ typed: true, text, group: "typed", reasons: [], label: `Use "${text}" as typed (not in the library)` }];
    }
    activeIndex = -1;
    renderOptions();
    openList();
  });

  function showAllOptions() {
    options = arrange(getScoreOptions(), slotUseType(container));
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
        options = arrange(getScoreOptions(), slotUseType(container));
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
      // A search box clears its text on Escape by default, which would
      // empty the chosen score and open the list again; here Escape only
      // closes the list.
      event.preventDefault();
      closeList();
    }
  });

  listbox.addEventListener("mousedown", (event) => {
    const li = event.target.closest("li[role=option]");
    if (!li) return;
    const option = filtered[Number(li.dataset.index)];
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
