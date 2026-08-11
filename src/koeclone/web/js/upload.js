import { apiForm, errorMessage } from "./api.js";

const maxBytes = 50 * 1024 * 1024;

export function uploadFileError(file) {
  if (!file) return "WAVまたはMP3ファイルを選んでください。";
  if (file.size > maxBytes) return "50MB以下のファイルを選んでください。";
  if (!/\.(wav|mp3)$/i.test(file.name)) return "拡張子が.wavまたは.mp3のファイルを選んでください。";
  return "";
}

export function uploadErrorMessage(error) {
  return `${errorMessage(error)} 別のファイルを選んで、もう一度お試しください。`;
}

export function initUpload() {
  const input = document.querySelector("#voice-file");
  const firstRights = document.querySelector("#upload-rights-first");
  const validate = document.querySelector("#upload-validate");
  const playback = document.querySelector("#upload-playback");
  const finalRights = document.querySelector("#upload-rights-final");
  const finalLabel = finalRights.closest("label");
  const confirm = document.querySelector("#upload-confirm");
  const discard = document.querySelector("#upload-discard");
  const errorBox = document.querySelector("#upload-error");
  let draftId;

  function showError(value) {
    errorBox.textContent = typeof value === "string" ? value : uploadErrorMessage(value);
    errorBox.hidden = false;
    discard.hidden = false;
  }

  function updateValidate() {
    validate.disabled = !input.files?.[0] || !firstRights.checked;
  }

  function clearDraft() {
    finalRights.checked = false;
    draftId = undefined;
    playback.removeAttribute("src");
    playback.hidden = true;
    finalLabel.hidden = true;
    confirm.hidden = true;
    confirm.disabled = true;
    discard.hidden = true;
  }

  function reset() {
    input.value = "";
    firstRights.checked = false;
    validate.disabled = true;
    errorBox.hidden = true;
    clearDraft();
  }

  input.addEventListener("change", () => {
    errorBox.hidden = true;
    clearDraft();
    const problem = uploadFileError(input.files?.[0]);
    if (problem) showError(problem);
    updateValidate();
  });
  firstRights.addEventListener("change", updateValidate);
  finalRights.addEventListener("change", () => { confirm.disabled = !finalRights.checked; });
  discard.addEventListener("click", reset);

  validate.addEventListener("click", async () => {
    const file = input.files?.[0];
    const problem = uploadFileError(file);
    if (problem || !firstRights.checked) { showError(problem || "音声の権利確認が必要です。"); return; }
    validate.disabled = true;
    const form = new FormData();
    form.set("stage", "validate");
    form.set("source_mode", "file_upload");
    form.set("consent_accepted", "true");
    form.set("consent_text", "自分の声であり、登録と利用の権利を持つ音声です。");
    form.set("audio", file, file.name);
    try {
      const result = await apiForm("/voices", form);
      draftId = result.draft_id;
      playback.src = result.preview_url;
      playback.hidden = false;
      finalLabel.hidden = false;
      confirm.hidden = false;
      discard.hidden = false;
    } catch (error) { showError(error); validate.disabled = false; }
  });

  confirm.addEventListener("click", async () => {
    if (!finalRights.checked || !draftId) { showError("登録確定前の権利確認が必要です。"); return; }
    confirm.disabled = true;
    const form = new FormData();
    form.set("stage", "confirm");
    form.set("draft_id", draftId);
    form.set("consent_accepted", "true");
    form.set("display_name", document.querySelector("#upload-display-name").value);
    try {
      const result = await apiForm("/voices", form);
      document.dispatchEvent(new CustomEvent("koeclone:synthesis-job", { detail: { id: result.test_synthesis_id } }));
      document.querySelector('[data-section="synthesis"]').click();
    } catch (error) { showError(error); confirm.disabled = false; }
  });
}
