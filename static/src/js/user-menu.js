// The user menu is a native <details> element, so it opens and closes
// with mouse and keyboard without any script. This adds the two things
// a dropdown menu is expected to do that <details> doesn't: close on
// Escape (returning focus to the toggle) and close on a click outside.

function initUserMenu() {
  const menu = document.querySelector(".user-menu");
  if (!menu) return;
  const summary = menu.querySelector("summary");

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.open) {
      menu.open = false;
      summary.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });
}

initUserMenu();
