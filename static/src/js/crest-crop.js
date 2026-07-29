// Progressive enhancement over a plain <input type="file"> — the input
// stays the real, submitted form field throughout. If cropping isn't
// possible (no DataTransfer/canvas support) this simply never builds the
// crop UI, and the raw file the user picked submits as-is; the server-side
// Pillow centre-crop in core/imaging.py is the fallback for that case.
const DEFAULT_TARGET_WIDTH = 1600;
const DEFAULT_TARGET_HEIGHT = 400;
const MIN_WIDTH = 800;
const MIN_HEIGHT = 200;
const MAX_ZOOM_FACTOR = 4;

function supportsCropping() {
  return typeof DataTransfer !== "undefined" && typeof HTMLCanvasElement !== "undefined";
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function buildCropper(container) {
  if (!supportsCropping()) return;

  const targetId = container.dataset.target;
  const input = document.getElementById(targetId);
  if (!input) return;

  const targetWidth = parseInt(container.dataset.targetWidth, 10) || DEFAULT_TARGET_WIDTH;
  const targetHeight = parseInt(container.dataset.targetHeight, 10) || DEFAULT_TARGET_HEIGHT;

  let ui = null;

  function teardownUi() {
    if (ui) {
      ui.wrapper.remove();
      ui = null;
    }
  }

  function buildUiForImage(img) {
    teardownUi();

    const wrapper = document.createElement("div");

    const warning = document.createElement("p");
    warning.className = "crest-crop__warning";
    warning.hidden = true;
    if (img.naturalWidth < MIN_WIDTH || img.naturalHeight < MIN_HEIGHT) {
      warning.hidden = false;
      warning.textContent = `This image is quite small (${img.naturalWidth}×${img.naturalHeight}px) — it may look blurry once cropped.`;
    }

    const frame = document.createElement("div");
    frame.className = "crest-crop__frame";

    const image = document.createElement("img");
    image.className = "crest-crop__image";
    image.src = img.src;
    image.alt = "";
    image.width = img.naturalWidth;
    image.height = img.naturalHeight;
    frame.appendChild(image);

    const controls = document.createElement("div");
    controls.className = "crest-crop__controls";

    const zoom = document.createElement("input");
    zoom.type = "range";
    zoom.className = "crest-crop__zoom";
    zoom.min = "0";
    zoom.max = "100";
    zoom.value = "0";

    const confirmButton = document.createElement("button");
    confirmButton.type = "button";
    confirmButton.textContent = "Use this crop";

    controls.append(zoom, confirmButton);

    const preview = document.createElement("img");
    preview.className = "crest-crop__preview";
    preview.hidden = true;
    preview.alt = "Crop preview";

    wrapper.append(warning, frame, controls, preview);
    container.appendChild(wrapper);
    ui = { wrapper, frame, image, zoom, confirmButton, preview };

    let scale = 1;
    let minScale = 1;
    let maxScale = 1;
    let tx = 0;
    let ty = 0;

    function applyTransform() {
      image.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    }

    function clampPosition() {
      const frameRect = frame.getBoundingClientRect();
      const displayedWidth = img.naturalWidth * scale;
      const displayedHeight = img.naturalHeight * scale;
      tx = clamp(tx, frameRect.width - displayedWidth, 0);
      ty = clamp(ty, frameRect.height - displayedHeight, 0);
    }

    function resetForFrameSize() {
      const frameRect = frame.getBoundingClientRect();
      minScale = Math.max(frameRect.width / img.naturalWidth, frameRect.height / img.naturalHeight);
      maxScale = minScale * MAX_ZOOM_FACTOR;
      scale = minScale;
      tx = (frameRect.width - img.naturalWidth * scale) / 2;
      ty = (frameRect.height - img.naturalHeight * scale) / 2;
      clampPosition();
      applyTransform();
    }

    // Deferred so the frame has been laid out (and has real dimensions)
    // before anything measures it.
    requestAnimationFrame(resetForFrameSize);

    zoom.addEventListener("input", () => {
      scale = minScale + (maxScale - minScale) * (Number(zoom.value) / 100);
      clampPosition();
      applyTransform();
    });

    let dragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartTx = 0;
    let dragStartTy = 0;

    image.addEventListener("pointerdown", (event) => {
      dragging = true;
      dragStartX = event.clientX;
      dragStartY = event.clientY;
      dragStartTx = tx;
      dragStartTy = ty;
      image.setPointerCapture(event.pointerId);
    });

    image.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      tx = dragStartTx + (event.clientX - dragStartX);
      ty = dragStartTy + (event.clientY - dragStartY);
      clampPosition();
      applyTransform();
    });

    function stopDragging() {
      dragging = false;
    }
    image.addEventListener("pointerup", stopDragging);
    image.addEventListener("pointercancel", stopDragging);

    confirmButton.addEventListener("click", () => {
      const frameRect = frame.getBoundingClientRect();
      const sourceX = -tx / scale;
      const sourceY = -ty / scale;
      const sourceWidth = frameRect.width / scale;
      const sourceHeight = frameRect.height / scale;

      const canvas = document.createElement("canvas");
      canvas.width = targetWidth;
      canvas.height = targetHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(
        img,
        sourceX, sourceY, sourceWidth, sourceHeight,
        0, 0, targetWidth, targetHeight,
      );

      canvas.toBlob((blob) => {
        if (!blob) return;
        const file = new File([blob], "crest.png", { type: "image/png" });
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        input.files = dataTransfer.files;

        preview.hidden = false;
        preview.src = URL.createObjectURL(blob);
      }, "image/png");
    });
  }

  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (!file) {
      teardownUi();
      return;
    }

    const img = new Image();
    img.onload = () => buildUiForImage(img);
    img.src = URL.createObjectURL(file);
  });
}

export function initCrestCrop(root = document) {
  root.querySelectorAll(".crest-crop").forEach((container) => {
    if (container.dataset.enhanced) return;
    container.dataset.enhanced = "true";
    buildCropper(container);
  });
}

document.addEventListener("DOMContentLoaded", () => initCrestCrop());
