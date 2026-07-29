// Progressive enhancement over the plain occasion / additional_occasions
// <select> fields that ServiceForm already renders — those selects work
// exactly as before with this script absent. On date change, this fetches
// candidate occasions and offers them as choices the conductor confirms;
// it never fills a selection in without a click.
function initOccasionSuggest() {
  const dateField = document.getElementById("id_date");
  const container = document.getElementById("occasion-suggestions");
  if (!dateField || !container) return;

  const traditionField = document.getElementById("id_tradition");
  const calendarUseField = document.getElementById("id_calendar_use");
  const occasionField = document.getElementById("id_occasion");
  const additionalField = document.getElementById("id_additional_occasions");

  function effectiveTradition() {
    return traditionField?.value || container.dataset.termTradition || "";
  }

  function effectiveCalendarUse() {
    return calendarUseField?.value || container.dataset.termCalendarUse || "";
  }

  function clear() {
    container.hidden = true;
    container.innerHTML = "";
  }

  function render(occasions) {
    container.innerHTML = "";
    if (!occasions.length) {
      container.hidden = true;
      return;
    }
    container.hidden = false;

    const heading = document.createElement("p");
    heading.textContent =
      occasions.length === 1
        ? "This date matches a known occasion:"
        : "This date matches more than one known occasion:";
    container.appendChild(heading);

    occasions.forEach((occasion) => {
      const row = document.createElement("div");
      row.className = "cluster";

      const label = document.createElement("span");
      label.textContent = occasion.name;
      row.appendChild(label);

      const setPrimary = document.createElement("button");
      setPrimary.type = "button";
      setPrimary.className = "btn-ghost";
      setPrimary.textContent = "Set as occasion";
      setPrimary.addEventListener("click", () => {
        if (occasionField) occasionField.value = String(occasion.id);
      });
      row.appendChild(setPrimary);

      if (additionalField && occasions.length > 1) {
        const checkboxLabel = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.addEventListener("change", () => {
          const option = Array.from(additionalField.options).find(
            (opt) => opt.value === String(occasion.id)
          );
          if (option) option.selected = checkbox.checked;
        });
        checkboxLabel.append(checkbox, " Also relevant");
        row.appendChild(checkboxLabel);
      }

      container.appendChild(row);
    });
  }

  async function suggest() {
    const dateValue = dateField.value;
    const tradition = effectiveTradition();
    const calendarUse = effectiveCalendarUse();
    if (!dateValue || !tradition || !calendarUse) {
      clear();
      return;
    }

    const params = new URLSearchParams({
      date: dateValue,
      tradition,
      calendar_use: calendarUse,
    });

    let data;
    try {
      const response = await fetch(`/ordo/occasion-lookup/?${params}`);
      if (!response.ok) throw new Error("occasion lookup failed");
      data = await response.json();
    } catch (err) {
      clear();
      return;
    }

    render(data.occasions);
  }

  dateField.addEventListener("change", suggest);
}

document.addEventListener("DOMContentLoaded", initOccasionSuggest);
