import { apiGet, apiJson, errorMessage } from "./api.js";

export function initProfile() {
  const card = document.querySelector("#profile-card");
  const summary = document.querySelector("#profile-summary");
  const deleteButton = document.querySelector("#profile-delete");
  const status = document.querySelector("#profile-status");
  const errorBox = document.querySelector("#profile-error");
  let profile;

  async function loadProfile() {
    try {
      profile = await apiGet("/voices/current");
      summary.textContent = `${profile.display_name}（登録日時: ${new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" }).format(new Date(profile.created_at))}）`;
      card.hidden = false;
      deleteButton.disabled = false;
      errorBox.hidden = true;
      status.textContent = "";
    } catch (error) {
      card.hidden = true;
      if (error.code === "ERR_PROFILE_NOT_FOUND") {
        profile = undefined;
        errorBox.hidden = true;
        return;
      }
      errorBox.textContent = errorMessage(error);
      errorBox.hidden = false;
    }
  }

  function complete(message) {
    document.dispatchEvent(new CustomEvent("koeclone:profile-deleted"));
    profile = undefined;
    card.hidden = true;
    errorBox.hidden = true;
    document.querySelector('[data-section="register"]').click();
    status.textContent = message;
    status.focus();
  }

  deleteButton.addEventListener("click", async () => {
    if (!profile) return;
    const confirmed = window.confirm(
      `音声プロフィール「${profile.display_name}」を削除します。\n` +
      "参照音声・同意録音・生成した音声とサイドカー・生成履歴がすべて削除され、元に戻せません。\n" +
      "削除しますか？",
    );
    if (!confirmed) return;
    deleteButton.disabled = true;
    try {
      await apiJson("DELETE", "/voices/current");
      complete("音声プロフィールを削除しました。参照音声・生成した音声・履歴もすべて削除されています。");
    } catch (error) {
      if (error.code === "ERR_PROFILE_NOT_FOUND") {
        complete("音声プロフィールは既に削除されています。");
        return;
      }
      errorBox.textContent = errorMessage(error);
      errorBox.hidden = false;
      deleteButton.disabled = false;
    }
  });

  document.addEventListener("koeclone:section", (event) => {
    if (event.detail.name === "register") loadProfile();
  });
  loadProfile();
}
