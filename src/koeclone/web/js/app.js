const consentKey = "koeclone_usage_consent";
const sections = [...document.querySelectorAll("main > section")];
const steps = [...document.querySelectorAll("[data-section]")];
const consent = document.querySelector("#usage-consent");
const continueButton = document.querySelector("#consent-continue");
const protectedControls = [document.querySelector("#record-start"), document.querySelector("#voice-file")];

export function showSection(name) {
  sections.forEach((section) => { section.hidden = section.id !== name; });
  steps.forEach((step) => {
    if (step.dataset.section === name) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
  history.replaceState(null, "", `#${name}`);
  document.querySelector(`#${name} h1`)?.focus({ preventScroll: true });
  document.dispatchEvent(new CustomEvent("koeclone:section", { detail: { name } }));
}

function setConsent(accepted) {
  consent.checked = accepted;
  continueButton.disabled = !accepted;
  protectedControls.forEach((control) => { control.disabled = !accepted; });
  if (accepted) sessionStorage.setItem(consentKey, "true");
  else sessionStorage.removeItem(consentKey);
}

steps.forEach((step) => step.addEventListener("click", () => showSection(step.dataset.section)));
consent.addEventListener("change", () => setConsent(consent.checked));
continueButton.addEventListener("click", () => showSection("register"));

document.querySelectorAll("[data-register-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    const upload = button.dataset.registerMode === "upload";
    document.querySelector("#record-pane").hidden = upload;
    document.querySelector("#upload-pane").hidden = !upload;
    document.querySelectorAll("[data-register-mode]").forEach((item) => item.setAttribute("aria-selected", String(item === button)));
  });
});

setConsent(sessionStorage.getItem(consentKey) === "true");
const requested = location.hash.slice(1);
showSection(sections.some((section) => section.id === requested) ? requested : "consent");

for (const [path, initializer] of [
  ["./record.js", "initRecording"],
  ["./upload.js", "initUpload"],
  ["./synthesis.js", "initSynthesis"],
  ["./history.js", "initHistory"],
  ["./profile.js", "initProfile"],
]) {
  import(path).then((module) => module[initializer]?.()).catch(() => {});
}
