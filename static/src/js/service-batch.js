// Adding several services: the dates' checkboxes get Select all and
// Select none, and the button's count follows the ticks. Without
// JavaScript the server counts them, so this only saves clicks; a date
// that already has the service stays as it is, disabled.

const form = document.getElementById("batch-form");

if (form) {
  const button = document.getElementById("batch-create");
  const boxes = [...form.querySelectorAll('input[name="dates"]')].filter((box) => !box.disabled);

  const count = () => {
    const ticked = boxes.filter((box) => box.checked).length;
    button.textContent = `Create ${ticked} service${ticked === 1 ? "" : "s"}`;
  };

  const choose = (label, ticked) => {
    const choice = document.createElement("button");
    choice.type = "button";
    choice.className = "btn-ghost";
    choice.textContent = label;
    choice.addEventListener("click", () => {
      boxes.forEach((box) => {
        box.checked = ticked;
      });
      count();
    });
    return choice;
  };

  const choices = document.createElement("div");
  choices.className = "cluster";
  choices.append(choose("Select all", true), choose("Select none", false));
  form.querySelector("fieldset").before(choices);
  form.addEventListener("change", count);
}
