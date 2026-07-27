const STORAGE_KEY = "precentor-theme";

function effectiveTheme() {
  const manual = document.documentElement.getAttribute("data-theme");
  if (manual) return manual;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function updateToggleLabel(button) {
  const isDark = effectiveTheme() === "dark";
  button.textContent = isDark ? "Light mode" : "Dark mode";
  button.setAttribute("aria-pressed", String(isDark));
}

function initThemeToggle() {
  const button = document.getElementById("theme-toggle");
  if (!button) return;
  updateToggleLabel(button);
  button.addEventListener("click", () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
    updateToggleLabel(button);
  });
}

document.addEventListener("DOMContentLoaded", initThemeToggle);
