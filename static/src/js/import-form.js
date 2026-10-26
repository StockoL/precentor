// The import page's form. When a file is chosen it says how big it is,
// and warns before uploading if it's over the limit the server checks.
// While the file uploads the button can't be pressed again, so a double
// click can't make two imports. Without JavaScript the form works as
// before, and the server still checks the size.
const form = document.querySelector("form[data-max-bytes]");

if (form) {
  const maxBytes = Number(form.dataset.maxBytes);
  const input = form.querySelector("input[type=file]");
  const button = form.querySelector("button[type=submit]");
  const status = document.createElement("p");
  status.className = "list-row__meta";
  status.setAttribute("role", "status");
  input.after(status);

  const megabytes = (bytes) => (bytes / (1024 * 1024)).toFixed(1);

  input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) {
      status.textContent = "";
      button.disabled = false;
      return;
    }
    const tooBig = file.size > maxBytes;
    status.textContent = tooBig
      ? `${file.name} is ${megabytes(file.size)} MB, more than the ${megabytes(maxBytes)} MB limit. Split it into smaller files.`
      : `${file.name}, ${Math.max(1, Math.round(file.size / 1024))} KB.`;
    button.disabled = tooBig;
  });

  form.addEventListener("submit", () => {
    button.disabled = true;
    button.textContent = "Importing…";
  });

  // A page restored by Back would otherwise keep the disabled button.
  window.addEventListener("pageshow", () => {
    button.disabled = false;
    button.textContent = "Import";
  });
}
