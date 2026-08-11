import { apiGet, apiJson, errorMessage } from "./api.js";

export function codePointRange(text, selectionStart, selectionEnd) {
  return {
    start: Array.from(text.slice(0, selectionStart)).length,
    end: Array.from(text.slice(0, selectionEnd)).length,
  };
}

export function selectedCodePoints(text, start, end) {
  return Array.from(text).slice(start, end).join("");
}

export function initSynthesis() {
  const textarea = document.querySelector("#synthesis-text");
  const originalCount = document.querySelector("#original-count");
  const synthesisCount = document.querySelector("#synthesis-count");
  const editor = document.querySelector("#pronunciation-editor");
  const surfaceInput = document.querySelector("#selected-surface");
  const readingInput = document.querySelector("#override-reading");
  const addButton = document.querySelector("#override-add");
  const list = document.querySelector("#override-list");
  const previewButton = document.querySelector("#preview-synthesis");
  const previewOriginal = document.querySelector("#preview-original");
  const previewReading = document.querySelector("#preview-reading");
  const disclosure = document.querySelector("#ai-disclosure");
  const generate = document.querySelector("#synthesize");
  const progress = document.querySelector("#synthesis-progress");
  const player = document.querySelector("#synthesis-player");
  const download = document.querySelector("#synthesis-download");
  const errorBox = document.querySelector("#synthesis-error");
  let pronunciationMode = false;
  let selection = null;
  let overrides = [];
  let pollGeneration = 0;

  const activeOverrides = () => pronunciationMode ? overrides : [];
  const showError = (error) => { errorBox.textContent = errorMessage(error); errorBox.hidden = false; };
  const clearOutput = () => { errorBox.hidden = true; player.hidden = true; player.removeAttribute("src"); download.hidden = true; };

  function renderOverrides() {
    list.replaceChildren();
    overrides.forEach((override, index) => {
      const item = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = `${override.surface} → `;
      const input = document.createElement("input");
      input.type = "text";
      input.value = override.reading;
      input.setAttribute("aria-label", `${override.surface}の読み`);
      const save = document.createElement("button");
      save.type = "button";
      save.textContent = "編集を保存";
      save.addEventListener("click", () => { overrides[index] = { ...override, reading: input.value }; renderOverrides(); });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "削除";
      remove.addEventListener("click", () => { overrides.splice(index, 1); renderOverrides(); });
      item.append(label, input, save, remove);
      list.append(item);
    });
  }

  function captureSelection() {
    const range = codePointRange(textarea.value, textarea.selectionStart, textarea.selectionEnd);
    const surface = selectedCodePoints(textarea.value, range.start, range.end);
    selection = range.start < range.end ? { ...range, surface } : null;
    surfaceInput.value = selection?.surface || "";
    addButton.disabled = !selection || !readingInput.value.trim();
  }

  textarea.addEventListener("input", () => {
    originalCount.textContent = Array.from(textarea.value).length;
    synthesisCount.textContent = originalCount.textContent;
    overrides = [];
    renderOverrides();
    captureSelection();
  });
  textarea.addEventListener("select", captureSelection);
  textarea.addEventListener("keyup", captureSelection);
  readingInput.addEventListener("input", () => { addButton.disabled = !selection || !readingInput.value.trim(); });

  addButton.addEventListener("click", () => {
    if (!selection || !readingInput.value.trim()) return;
    overrides.push({ ...selection, reading: readingInput.value.trim() });
    readingInput.value = "";
    selection = null;
    surfaceInput.value = "";
    addButton.disabled = true;
    renderOverrides();
  });

  document.querySelectorAll("[data-synthesis-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      pronunciationMode = button.dataset.synthesisMode === "pronunciation";
      editor.hidden = !pronunciationMode;
      document.querySelectorAll("[data-synthesis-mode]").forEach((item) => item.setAttribute("aria-selected", String(item === button)));
    });
  });

  previewButton.addEventListener("click", async () => {
    clearOutput();
    try {
      const result = await apiJson("POST", "/syntheses/preview", { text: textarea.value, overrides: activeOverrides() });
      previewOriginal.replaceChildren();
      result.original_segments.forEach((segment) => {
        const element = document.createElement(segment.override_index === null ? "span" : "mark");
        element.textContent = segment.text;
        previewOriginal.append(element);
      });
      previewReading.textContent = `読み上げ: ${result.synthesis_text}`;
      synthesisCount.textContent = result.synthesis_text_length;
    } catch (error) { showError(error); }
  });

  disclosure.addEventListener("change", () => { generate.disabled = !disclosure.checked; });

  async function pollJob(jobId) {
    const generation = ++pollGeneration;
    clearOutput();
    progress.hidden = false;
    const poll = async () => {
      if (generation !== pollGeneration) return;
      try {
        const job = await apiGet(`/syntheses/${jobId}`);
        const labels = { queued: "生成待ちです…", running: "あなたの声で生成しています…", succeeded: "音声が完成しました", failed: "音声を生成できませんでした" };
        progress.textContent = labels[job.status] || job.status;
        if (job.status === "succeeded") {
          player.src = `/api/syntheses/${jobId}/audio`;
          player.hidden = false;
          download.href = `/api/syntheses/${jobId}/audio`;
          download.hidden = false;
          return;
        }
        if (job.status === "failed") { showError({ code: job.error_code, message: "音声を生成できませんでした。入力を確認して再度お試しください。", error_id: job.error_id }); return; }
        setTimeout(poll, 1000);
      } catch (error) { progress.hidden = true; showError(error); }
    };
    await poll();
  }

  generate.addEventListener("click", async () => {
    clearOutput();
    generate.disabled = true;
    try {
      const job = await apiJson("POST", "/syntheses", { text: textarea.value, overrides: activeOverrides(), ai_disclosure_acknowledged: disclosure.checked });
      await pollJob(job.id);
    } catch (error) { showError(error); }
    finally { generate.disabled = !disclosure.checked; }
  });

  document.addEventListener("koeclone:synthesis-job", (event) => pollJob(event.detail.id));
}
