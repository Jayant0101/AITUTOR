/**
 * API service layer — all requests to FastAPI backend.
 * In development, Vite proxies /api → http://localhost:8000
 */

const API_BASE = '/api';

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('socratiq_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function request(method, path, body = null) {
  const options = { method, headers: getHeaders() };
  if (body) options.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, options);
  const data = await res.json();

  if (!res.ok) {
    const errorMsg = data.detail || `Request failed (${res.status})`;
    throw new Error(errorMsg);
  }
  return data;
}

async function uploadRequest(path, file) {
  const token = localStorage.getItem('socratiq_token');
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });

  const data = await res.json();
  if (!res.ok) {
    const errorMsg = data.detail || `Upload failed (${res.status})`;
    throw new Error(errorMsg);
  }
  return data;
}

// ── Auth ──
export const authApi = {
  register: (email, password, displayName = '') =>
    request('POST', '/auth/register', { email, password, display_name: displayName }),

  login: (email, password) =>
    request('POST', '/auth/login', { email, password }),

  me: () => request('GET', '/auth/me'),
};

// ── Chat ──
export const chatApi = {
  send: (query, mode = 'socratic', topK = 3) =>
    request('POST', '/chat', { query, mode, top_k: topK }),
  stream: async (query, mode = 'socratic', topK = 3, onChunk = () => {}) => {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ query, mode, top_k: topK }),
    });

    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      const errorMsg = data.detail || `Stream failed (${res.status})`;
      throw new Error(errorMsg);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let done = false;
    let buffer = '';

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        onChunk(buffer);
      }
    }

    return buffer;
  },
};

// â”€â”€ Files â”€â”€
export const fileApi = {
  upload: (file) => uploadRequest('/files/upload', file),
};

// â”€â”€ YouTube â”€â”€
export const youtubeApi = {
  search: (query) => request('POST', '/search/youtube', { query }),
};

// ── Quiz ──
export const quizApi = {
  submit: (nodeId, question, expectedAnswer, userAnswer, difficulty = 'medium') =>
    request('POST', '/quiz/submit', {
      node_id: nodeId,
      question,
      expected_answer: expectedAnswer,
      user_answer: userAnswer,
      difficulty,
    }),
  generate: (fileIds = []) =>
    request('POST', '/quiz/generate', { file_ids: fileIds }),
};

// ── Learner ──
export const learnerApi = {
  progress: () => request('GET', '/learner/progress'),
};

// ── Health ──
export const healthApi = {
  check: () => request('GET', '/health'),
};

// ── Ingest ──
export const ingestApi = {
  reload: () => request('POST', '/ingest', {}),
};
