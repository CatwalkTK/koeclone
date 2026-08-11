import { apiForm, apiGet, errorMessage } from "./api.js";

export function formatElapsed(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

export function recordingLengthError(seconds) {
  if (seconds < 10) return "録音は10秒以上必要です。もう一度録音してください。";
  if (seconds > 60) return "録音は60秒以内にしてください。もう一度録音してください。";
  return "";
}

export function recordingErrorMessage(error) {
  if (error?.name === "NotAllowedError") {
    return "マイクを利用できません。ブラウザのサイト設定でマイクを許可してから、再度お試しください。";
  }
  return `${errorMessage(error)} 「破棄して録り直す」から再録音できます。`;
}

export async function initRecording() {
  const start = document.querySelector("#record-start");
  const stop = document.querySelector("#record-stop");
  const discard = document.querySelector("#record-discard");
  const confirm = document.querySelector("#record-confirm");
  const playback = document.querySelector("#record-playback");
  const errorBox = document.querySelector("#record-error");
  const status = document.querySelector(".record-status");
  const state = document.querySelector("#record-state");
  const time = document.querySelector("#record-time");
  let challenge = "";
  let recorder;
  let stream;
  let timer;
  let startedAt = 0;
  let blob;
  let draftId;
  let objectUrl;

  function showError(error) {
    errorBox.textContent = typeof error === "string" ? error : recordingErrorMessage(error);
    errorBox.hidden = false;
    discard.hidden = false;
  }

  function reset() {
    clearInterval(timer);
    stream?.getTracks().forEach((track) => track.stop());
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    recorder = undefined;
    stream = undefined;
    blob = undefined;
    draftId = undefined;
    objectUrl = undefined;
    playback.removeAttribute("src");
    playback.hidden = true;
    confirm.hidden = true;
    discard.hidden = true;
    stop.disabled = true;
    state.textContent = "待機中";
    time.textContent = "00:00";
    status.classList.remove("is-recording");
    errorBox.hidden = true;
  }

  try {
    const response = await apiGet("/consent/challenge");
    challenge = response.consent_text;
    document.querySelector("#consent-challenge").textContent = challenge;
  } catch (error) {
    document.querySelector("#consent-challenge").textContent = "同意文を取得できませんでした。";
    showError(error);
  }

  start.addEventListener("click", async () => {
    reset();
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferred = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      recorder = preferred ? new MediaRecorder(stream, { mimeType: preferred }) : new MediaRecorder(stream);
      const chunks = [];
      recorder.addEventListener("dataavailable", (event) => { if (event.data.size) chunks.push(event.data); });
      recorder.addEventListener("stop", async () => {
        clearInterval(timer);
        stream.getTracks().forEach((track) => track.stop());
        status.classList.remove("is-recording");
        const seconds = (performance.now() - startedAt) / 1000;
        const lengthError = recordingLengthError(seconds);
        if (lengthError) { showError(lengthError); state.textContent = "録り直しが必要です"; return; }
        blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        state.textContent = "音声を確認中…";
        const form = new FormData();
        form.set("stage", "validate");
        form.set("source_mode", "direct_recording");
        form.set("consent_accepted", "true");
        form.set("consent_text", challenge);
        form.set("audio", blob, "recording");
        form.set("consent_audio", blob, "consent");
        try {
          const result = await apiForm("/voices", form);
          draftId = result.draft_id;
          playback.src = result.preview_url;
          playback.hidden = false;
          confirm.hidden = false;
          discard.hidden = false;
          state.textContent = "試聴して声を確定してください";
        } catch (error) { state.textContent = "確認できませんでした"; showError(error); }
      });
      recorder.start();
      startedAt = performance.now();
      state.textContent = "録音中";
      status.classList.add("is-recording");
      stop.disabled = false;
      start.disabled = true;
      timer = setInterval(() => { time.textContent = formatElapsed((performance.now() - startedAt) / 1000); }, 250);
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      stream = undefined;
      showError(error);
    }
  });

  stop.addEventListener("click", () => { if (recorder?.state === "recording") recorder.stop(); stop.disabled = true; start.disabled = false; });
  discard.addEventListener("click", () => { reset(); start.disabled = sessionStorage.getItem("koeclone_usage_consent") !== "true"; });
  confirm.addEventListener("click", async () => {
    const form = new FormData();
    form.set("stage", "confirm");
    form.set("draft_id", draftId);
    form.set("consent_accepted", "true");
    form.set("display_name", document.querySelector("#record-display-name").value);
    confirm.disabled = true;
    try {
      const result = await apiForm("/voices", form);
      document.dispatchEvent(new CustomEvent("koeclone:synthesis-job", { detail: { id: result.test_synthesis_id } }));
      document.querySelector('[data-section="synthesis"]').click();
    } catch (error) { showError(error); confirm.disabled = false; }
  });
}
