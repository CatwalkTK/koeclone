function apiPath(path) {
  return path.startsWith("/api/") ? path : `/api${path.startsWith("/") ? path : `/${path}`}`;
}

async function request(path, options = {}) {
  const response = await fetch(apiPath(path), options);
  if (!response.ok) {
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    const detail = payload.error || {};
    const error = new Error(detail.message || `通信に失敗しました（${response.status}）`);
    error.code = detail.code || "ERR_NETWORK";
    error.error_id = detail.error_id || null;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

export function apiGet(path) {
  return request(path);
}

export function apiJson(method, path, body) {
  return request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiForm(path, formData) {
  return request(path, { method: "POST", body: formData });
}

const guidance = {
  ERR_AUDIO_TOO_SHORT: "10秒以上になるよう、もう一度録音してください。",
  ERR_AUDIO_TOO_LONG: "音声を短くして、もう一度お試しください。",
  ERR_AUDIO_MOSTLY_SILENT: "声が小さいか無音です。マイクを近づけて録り直してください。",
  ERR_AUDIO_CLIPPING: "音が大きすぎます。マイクから少し離れて録り直してください。",
  ERR_FILE_UNSUPPORTED_FORMAT: "WAVまたはMP3ファイルを選んでください。",
  ERR_FILE_TOO_LARGE: "50MB以下のファイルを選んでください。",
  ERR_AI_DISCLOSURE_REQUIRED: "AI生成音声として利用する確認が必要です。",
};

export function errorMessage(error) {
  const message = guidance[error?.code] || error?.message || "処理に失敗しました。もう一度お試しください。";
  return error?.error_id ? `${message}（エラーID: ${error.error_id}）` : message;
}
