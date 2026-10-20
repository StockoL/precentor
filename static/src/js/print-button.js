// A Print button only works with JavaScript, so the template leaves it
// hidden and this shows it. Without JavaScript, the browser's own Print
// command still prints the list with the same print styles.
function initPrintButtons() {
  document.querySelectorAll("[data-print]").forEach((button) => {
    button.addEventListener("click", () => window.print());
    button.hidden = false;
  });
}

document.addEventListener("DOMContentLoaded", initPrintButtons);
