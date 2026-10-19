// Appearance choice in the user menu: System, Light or Dark.
//
// "System" means no data-theme attribute, so the prefers-color-scheme
// media query in variables.css decides. Light and Dark set data-theme,
// which wins over the system setting, and are remembered in
// localStorage. The blocking script in base.html's <head> reapplies a
// saved choice before first paint, so there's no flash of the wrong
// theme; this module only handles the radios.

const STORAGE_KEY = "precentor-theme";

function applyTheme(choice) {
  if (choice === "system") {
    document.documentElement.removeAttribute("data-theme");
    localStorage.removeItem(STORAGE_KEY);
  } else {
    document.documentElement.setAttribute("data-theme", choice);
    localStorage.setItem(STORAGE_KEY, choice);
  }
}

function initThemeChoice() {
  const fieldset = document.getElementById("theme-choice");
  if (!fieldset) return;

  // The choice needs JavaScript to work, so the fieldset ships hidden
  // and appears only once this has run.
  fieldset.hidden = false;

  const saved = localStorage.getItem(STORAGE_KEY) || "system";
  const current = fieldset.querySelector(`input[value="${saved}"]`);
  if (current) current.checked = true;

  fieldset.addEventListener("change", (event) => {
    if (event.target.name === "theme") applyTheme(event.target.value);
  });
}

initThemeChoice();
