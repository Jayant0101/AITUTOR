/**
 * API service layer — all requests to FastAPI backend.
 * Updated for Next.js and Supabase Auth.
 */

import { createClient } from '@/lib/supabase/client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function getHeaders() {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  
  // Use Supabase client to get the current session token
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  
  return headers;
}

async function request<T>(method: string, path: string, body: unknown = null): Promise<T> {
  const headers = await getHeaders();
  const options: RequestInit = { method, headers };
  if (body) options.body = JSON.stringify(body);

  const res = await fetch(`${API_BASE}${path}`, options);
  
  let data: Record<string, unknown> = {};
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await res.json() as Record<string, unknown>;
    } catch (e) {
      console.error('Failed to parse JSON:', e);
    }
  } else {
    const text = await res.text();
    if (!res.ok) {
      throw new Error(text || `Request failed (${res.status})`);
    }
    data = text ? { text } : {};
  }

  if (!res.ok) {
    const errorMsg = (data.detail as string) || `Request failed (${res.status})`;
    throw new Error(errorMsg);
  }
  return data as T;
}

async function uploadRequest<T>(path: string, file: File): Promise<T> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
    body: form,
  });

  let data: Record<string, unknown> = {};
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await res.json() as Record<string, unknown>;
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
    const errorMsg = (data.detail as string) || `Upload failed (${res.status})`;
    throw new Error(errorMsg);
  }
  return data as T;
}

// ── Chat ──
export const chatApi = {
  send: (query: string, mode = 'socratic', topK = 3, attachments = [], history = []) =>
    request('POST', '/chat/query', { query, mode, top_k: topK, attachments, history }),
  stream: async (query: string, mode = 'socratic', topK = 3, attachments = [], history = [], onChunk = (text: string) => {}) => {
    const headers = await getHeaders();
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ query, mode, top_k: topK, attachments, history }),
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
  submitQuiz: (nodeId: string, question: string, expectedAnswer: string, userAnswer: string, difficulty = 'medium') =>
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
  upload: (file: File) => uploadRequest('/ingest/upload', file),
};

// ── YouTube ──
export const youtubeApi = {
  search: (query: string) => request('POST', '/search/youtube', { query }),
};

// ── Quiz ──
export const quizApi = {
  submit: (quizId: string, answers: any[], timeTaken: number) =>
    request('POST', '/quiz/submit', {
      quiz_id: quizId,
      answers: answers,
      time_taken: timeTaken,
    }),
  generate: (topic: string, difficulty = 'medium', num_questions = 10) =>
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
  userAnalytics: (userId: string) => request('GET', `/analytics/user/${userId}`),
};

// ── Ingest ──
export const ingestApi = {
  reload: () => request('POST', '/ingest', {}),
};

// ── Feedback ──
export const feedbackApi = {
  submit: (feedback: string, rating: number | null = null) =>
    request('POST', '/feedback', { feedback, rating }),
};
