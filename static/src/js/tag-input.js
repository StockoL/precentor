// Chip input over a <select multiple> (the score form's three "suitable
// for" fields, and the service form's other occasions). Progressive enhancement: the native select stays the
// source of truth, so adding a chip selects its option and removing one
// deselects it, and the form submits exactly as it would without
// JavaScript. The select is only hidden once everything here is built;
// if anything throws first, the plain select stays usable.
//
// A container with data-new-into="<input id>" also accepts names that
// aren't in the list (use types). They go into that text field as a
// comma-separated list, and the server creates them on save.

let instance = 0;

function buildTagInput(container) {
  const select = container.querySelector("select[multiple]");
  if (!select) return;
  const newField = container.dataset.newInto
    ? document.getElementById(container.dataset.newInto)
    : null;

  instance += 1;
  const baseId = `${select.id || `tag-input-${instance}`}-tags`;
  const listboxId = `${baseId}-listbox`;

  const wrapper = document.createElement("div");
  wrapper.className = "tag-input";

  const chips = document.createElement("ul");
  chips.className = "tag-input__chips cluster";
  chips.setAttribute("role", "list");

  const input = document.createElement("input");
  input.type = "text";
  input.id = `${baseId}-search`;
  input.className = "tag-input__search";
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-controls", listboxId);
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("autocomplete", "off");
  input.placeholder = newField ? "Type to find or add…" : "Type to find…";
  // Keep the field's help text attached to the control people now use.
  const describedBy = select.getAttribute("aria-describedby");
  if (describedBy) input.setAttribute("aria-describedby", describedBy);

  const listbox = document.createElement("ul");
  listbox.id = listboxId;
  listbox.className = "tag-input__listbox";
  listbox.setAttribute("role", "listbox");
  listbox.hidden = true;

  // Announces each change, since a chip appearing isn't otherwise spoken.
  const status = document.createElement("p");
  status.className = "visually-hidden";
  status.setAttribute("aria-live", "polite");

  wrapper.append(chips, input, listbox, status);
  select.after(wrapper);

  const options = Array.from(select.options).filter((option) => option.value);
  let matches = [];
  let activeIndex = -1;

  function newNames() {
    if (!newField) return [];
    return newField.value.split(",").map((name) => name.trim()).filter(Boolean);
  }

  function setNewNames(names) {
    newField.value = names.join(", ");
  }

  function announce(message) {
    status.textContent = message;
  }

  function makeChip(label, onRemove) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tag-input__chip";
    button.setAttribute("aria-label", `Remove ${label}`);
    button.textContent = label;
    button.addEventListener("click", () => {
      onRemove();
      announce(`Removed ${label}`);
      input.focus();
    });
    li.append(button);
    return li;
  }

  // Tell anything watching the select (and this widget, which redraws)
  // that its options changed, as a change made by hand would.
  function changed() {
    select.dispatchEvent(new Event("change"));
  }

  function renderChips() {
    chips.replaceChildren();
    options
      .filter((option) => option.selected)
      .forEach((option) => {
        chips.append(
          makeChip(option.textContent, () => {
            option.selected = false;
            changed();
          }),
        );
      });
    newNames().forEach((name) => {
      chips.append(
        makeChip(name, () => {
          setNewNames(newNames().filter((other) => other !== name));
          renderChips();
        }),
      );
    });
    chips.hidden = !chips.children.length;
  }

  // The options the typed text could mean: unchosen ones containing it,
  // plus "Add …" for a new name when that's allowed and nothing matches
  // it exactly.
  function findMatches() {
    const query = input.value.trim();
    const lower = query.toLowerCase();
    const found = options
      .filter((option) => !option.selected)
      .filter((option) => !lower || option.textContent.toLowerCase().includes(lower))
      .map((option) => ({ label: option.textContent, option }));
    const exact = options.some((option) => option.textContent.toLowerCase() === lower)
      || newNames().some((name) => name.toLowerCase() === lower);
    if (newField && query && !exact) {
      found.push({ label: `Add "${query}"`, newName: query });
    }
    return found;
  }

  function renderListbox() {
    listbox.replaceChildren();
    matches.forEach((match, index) => {
      const li = document.createElement("li");
      li.id = `${listboxId}-option-${index}`;
      li.setAttribute("role", "option");
      li.textContent = match.label;
      if (index === activeIndex) li.setAttribute("aria-selected", "true");
      li.addEventListener("mousedown", (event) => {
        event.preventDefault(); // keep focus in the search box
        choose(match);
      });
      listbox.append(li);
    });
    if (activeIndex >= 0) {
      input.setAttribute("aria-activedescendant", `${listboxId}-option-${activeIndex}`);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  }

  function openList() {
    matches = findMatches();
    activeIndex = -1;
    renderListbox();
    listbox.hidden = !matches.length;
    input.setAttribute("aria-expanded", String(!listbox.hidden));
  }

  function closeList() {
    listbox.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    activeIndex = -1;
  }

  function choose(match) {
    if (match.option) {
      match.option.selected = true;
      changed();
      announce(`Added ${match.option.textContent}`);
    } else {
      setNewNames([...newNames(), match.newName]);
      announce(`Added ${match.newName}, to be created when you save`);
    }
    input.value = "";
    renderChips();
    openList();
  }

  input.addEventListener("input", openList);
  input.addEventListener("focus", openList);

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (listbox.hidden) openList();
      activeIndex = Math.min(activeIndex + 1, matches.length - 1);
      renderListbox();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      renderListbox();
    } else if (event.key === "Enter") {
      // Enter adds the highlighted option, or the only one left; it
      // never submits the form from here.
      event.preventDefault();
      const match = matches[activeIndex] || (matches.length === 1 ? matches[0] : null);
      if (match) choose(match);
    } else if (event.key === "Escape") {
      closeList();
    } else if (event.key === "Backspace" && !input.value) {
      // An empty box: Backspace removes the last chip.
      const last = chips.querySelector("li:last-child button");
      if (last) last.click();
    }
  });

  document.addEventListener("click", (event) => {
    if (!wrapper.contains(event.target)) closeList();
  });

  // Also close when focus leaves, by Tab for instance; a click elsewhere
  // isn't the only way out.
  wrapper.addEventListener("focusout", (event) => {
    if (!wrapper.contains(event.relatedTarget)) closeList();
  });

  // Something else may select an option, such as the service form's
  // suggestions; it fires "change", and the chips are redrawn.
  select.addEventListener("change", renderChips);

  renderChips();

  // Everything is built, so the native controls can go. The label now
  // points at the search box, so clicking it still lands somewhere.
  const label = container.querySelector(`label[for="${select.id}"]`);
  if (label) label.htmlFor = input.id;
  select.hidden = true;
  if (newField) newField.closest("[data-new-field]").hidden = true;
}

export function initTagInputs(root = document) {
  root.querySelectorAll("[data-tag-input]").forEach((container) => {
    if (container.dataset.enhanced) return;
    container.dataset.enhanced = "true";
    buildTagInput(container);
  });
}

initTagInputs();
