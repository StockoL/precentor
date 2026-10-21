// Progressive enhancement over the occasion and additional occasions
// <select>s that ServiceForm renders, which work the same without it. When
// the date changes, this fetches the occasions kept that day, in the
// church's national calendar, and offers them for the conductor to
// choose: the day's celebration first, then anything also kept. It never
// fills a field in without a click. It also hides the occasions of the
// other form of the calendar, so the lists are shorter to search.
function initOccasionSuggest() {
  const dateField = document.getElementById("id_date");
  const container = document.getElementById("occasion-suggestions");
  if (!dateField || !container) return;

  const calendarUseField = document.getElementById("id_calendar_use");
  const occasionField = document.getElementById("id_occasion");
  const additionalField = document.getElementById("id_additional_occasions");

  function effectiveCalendarUse() {
    return calendarUseField?.value || container.dataset.termCalendarUse || "";
  }

  // Each option says which form it belongs to (ordo/fields.py). One
  // already chosen stays in sight whatever the calendar, so nothing is
  // dropped without the conductor seeing it.
  function showOnlyThisCalendar() {
    const calendarUse = effectiveCalendarUse();
    [occasionField, additionalField].forEach((field) => {
      field?.querySelectorAll("option[data-calendar-use]").forEach((option) => {
        const other = Boolean(calendarUse) && option.dataset.calendarUse !== calendarUse && !option.selected;
        option.hidden = other;
        option.disabled = other;
      });
    });
  }

  // Keep the boxes in step with the field, which its chip input
  // (tag-input.js) can change too.
  additionalField?.addEventListener("change", () => {
    container.querySelectorAll("input[data-occasion-id]").forEach((box) => {
      box.checked = Array.from(additionalField.selectedOptions).some(
        (opt) => opt.value === box.dataset.occasionId
      );
    });
  });

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
        ? "Kept on this date:"
        : "Kept on this date, the day’s celebration first:";
    container.appendChild(heading);

    occasions.forEach((occasion, index) => {
      const row = document.createElement("div");
      row.className = "cluster";

      const label = document.createElement("span");
      label.textContent = index === 0 ? occasion.name : `${occasion.name} (also kept)`;
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
        checkbox.dataset.occasionId = String(occasion.id);
        checkbox.checked = Array.from(additionalField.selectedOptions).some(
          (opt) => opt.value === String(occasion.id)
        );
        checkbox.addEventListener("change", () => {
          const option = Array.from(additionalField.options).find(
            (opt) => opt.value === String(occasion.id)
          );
          if (option) option.selected = checkbox.checked;
          // Lets the chip input over this select (tag-input.js) redraw.
          additionalField.dispatchEvent(new Event("change"));
        });
        checkboxLabel.append(checkbox, " Add to other occasions");
        row.appendChild(checkboxLabel);
      }

      container.appendChild(row);
    });
  }

  async function suggest() {
    const dateValue = dateField.value;
    const calendarUse = effectiveCalendarUse();
    if (!dateValue || !calendarUse) {
      clear();
      return;
    }

    const params = new URLSearchParams({
      date: dateValue,
      calendar_use: calendarUse,
      national_calendar: container.dataset.nationalCalendar || "",
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
  calendarUseField?.addEventListener("change", () => {
    showOnlyThisCalendar();
    suggest();
  });
  showOnlyThisCalendar();
}

document.addEventListener("DOMContentLoaded", initOccasionSuggest);
