import { apiGet, apiJson, errorMessage } from "./api.js";

export function formatDuration(durationMs) {
  if (durationMs === null || durationMs === undefined) return "—";
  const seconds = Math.round(durationMs / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function initHistory() {
  const container = document.querySelector("#history-list");
  const deleteAll = document.querySelector("#history-delete-all");
  const errorBox = document.querySelector("#history-error");

  function showError(error) {
    errorBox.textContent = errorMessage(error);
    errorBox.hidden = false;
  }

  async function loadHistory() {
    errorBox.hidden = true;
    try {
      const result = await apiGet("/syntheses");
      deleteAll.disabled = result.items.length === 0;
      container.replaceChildren();
      if (result.items.length === 0) {
        const empty = document.createElement("p");
        empty.className = "empty";
        empty.textContent = "まだ生成した音声はありません。";
        container.append(empty);
        return;
      }
      result.items.forEach((job) => container.append(historyItem(job)));
    } catch (error) { showError(error); }
  }

  function historyItem(job) {
    const article = document.createElement("article");
    article.className = "history-item";
    const header = document.createElement("header");
    const preview = document.createElement("strong");
    preview.textContent = job.text_preview;
    const date = document.createElement("time");
    date.dateTime = job.created_at;
    date.textContent = new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" }).format(new Date(job.created_at));
    header.append(preview, date);
    const metadata = document.createElement("p");
    metadata.textContent = `状態: ${job.status}　長さ: ${formatDuration(job.duration_ms)}　読み修正: ${job.override_count}件`;
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const play = document.createElement("button");
    play.type = "button";
    play.textContent = "再生";
    play.disabled = !job.audio_available;
    const download = document.createElement("button");
    download.type = "button";
    download.textContent = "ダウンロード";
    download.disabled = !job.audio_available;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "削除";
    remove.className = "danger";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.hidden = true;
    play.addEventListener("click", () => {
      if (!audio.src) audio.src = `/api/syntheses/${job.id}/audio`;
      audio.hidden = !audio.hidden;
      if (!audio.hidden) audio.play().catch(showError);
      else audio.pause();
    });
    download.addEventListener("click", () => { window.location.assign(`/api/syntheses/${job.id}/audio`); });
    remove.addEventListener("click", async () => {
      try { await apiJson("DELETE", `/syntheses/${job.id}`); await loadHistory(); }
      catch (error) { showError(error); }
    });
    actions.append(play, download, remove);
    article.append(header, metadata, actions, audio);
    return article;
  }

  deleteAll.addEventListener("click", async () => {
    if (!window.confirm("生成した音声をすべて削除します。元に戻せません。よろしいですか？")) return;
    try { await apiJson("DELETE", "/syntheses"); await loadHistory(); }
    catch (error) { showError(error); }
  });
  document.addEventListener("koeclone:section", (event) => { if (event.detail.name === "history") loadHistory(); });
  document.addEventListener("koeclone:profile-deleted", loadHistory);
  loadHistory();
}
