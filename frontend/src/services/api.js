/**
 * API service layer — all requests to FastAPI backend.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('aitutor_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function request(method, path, body = null) {
  const options = { method, headers: getHeaders() };
  if (body) options.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, options);
  
  let data = {};
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await res.json();
    } catch (e) {
      console.error('Failed to parse JSON:', e);
    }
  } else {
    // Handle non-JSON response (e.g. proxy error, empty body)
    const text = await res.text();
    if (!res.ok) {
      throw new Error(text || `Request failed (${res.status})`);
    }
    data = text ? { text } : {};
  }

  if (!res.ok) {
    const errorMsg = data.detail || `Request failed (${res.status})`;
    throw new Error(errorMsg);
  }
  return data;
}

async function uploadRequest(path, file) {
  const token = localStorage.getItem('aitutor_token');
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });

  let data = {};
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await res.json();
    } catch (e) {
      console.error('Failed to parse JSON:', e);
    }
  } else {
    const text = await res.text();
    if (!res.ok) {
       throw new Error(text || `Upload failed (${res.status})`);
    }
    data = text ? { text } : {};
  }

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
  send: (query, mode = 'socratic', topK = 3, attachments = []) =>
    request('POST', '/chat/query', { query, mode, top_k: topK, attachments }),
  stream: async (query, mode = 'socratic', topK = 3, attachments = [], onChunk = () => {}) => {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ query, mode, top_k: topK, attachments }),
    });

    if (!res.ok || !res.body) {
      const contentType = res.headers.get('content-type') || '';
      const isJson = contentType.includes('application/json');
      const data = isJson ? await res.json().catch(() => ({})) : await res.text().catch(() => '');
      const errorMsg = (isJson && data?.detail) ? data.detail : `Stream failed (${res.status})`;
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
  submitQuiz: (nodeId, question, expectedAnswer, userAnswer, difficulty = 'medium') =>
    request('POST', '/chat/quiz/submit', {
      node_id: nodeId,
      question,
      expected_answer: expectedAnswer,
      user_answer: userAnswer,
      difficulty,
    }),
};

// ── Files ──
export const fileApi = {
  upload: (file) => uploadRequest('/ingest/upload', file),
};

// ── YouTube ──
export const youtubeApi = {
  search: (query) => request('POST', '/search/youtube', { query }),
};

// ── Quiz ──
export const quizApi = {
  submit: (quizId, answers, timeTaken) =>
    request('POST', '/quiz/submit', {
      quiz_id: quizId,
      answers: answers,
      time_taken: timeTaken,
    }),
  generate: (topic, difficulty = 'medium', num_questions = 10) =>
    request('POST', '/quiz/generate', { topic, difficulty, num_questions }),
  history: () => request('GET', '/quiz/history'),
};

// ── Learner ──
export const learnerApi = {
  progress: () => request('GET', '/learner/progress'),
};

// ── Health & Analytics ──
export const healthApi = {
  check: () => request('GET', '/health'),
  analytics: () => request('GET', '/analytics/summary'),
  userAnalytics: (userId) => request('GET', `/analytics/user/${userId}`),
};

// ── Ingest ──
export const ingestApi = {
  reload: () => request('POST', '/ingest', {}),
};

// ── Feedback ──
export const feedbackApi = {
  submit: (feedback, rating = null) =>
    request('POST', '/feedback', { feedback, rating }),
};
