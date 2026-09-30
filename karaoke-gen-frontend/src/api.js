const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const SESSION_KEY = 'karaoke-gen-session';

// An explicitly empty REACT_APP_API_BASE_URL means "same origin": the Docker
// image serves the app behind nginx, which proxies /api/ and /media/.
const configuredApiBaseUrl = process.env.REACT_APP_API_BASE_URL;
export const API_BASE_URL = (configuredApiBaseUrl ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');

export function loadSession() {
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_KEY));
    return session?.access && session?.refresh ? session : null;
  } catch {
    return null;
  }
}

export function clearSession() { localStorage.removeItem(SESSION_KEY); }

function saveSession(tokens, username) {
  const previous = loadSession();
  const session = {
    access: tokens.access,
    refresh: tokens.refresh || previous?.refresh,
    username: username || previous?.username || '',
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

async function responseError(response) {
  const body = await response.json().catch(() => ({}));
  const message = body.detail || body.non_field_errors?.[0] || `Request failed (${response.status}).`;
  return Object.assign(new Error(message), { status: response.status, body });
}

async function publicJson(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!response.ok) throw await responseError(response);
  return response.json();
}

export async function login(credentials) {
  const tokens = await publicJson('/api/auth/login/', { method: 'POST', body: JSON.stringify(credentials) });
  return saveSession(tokens, credentials.username);
}

export async function register(details) {
  const result = await publicJson('/api/auth/register/', { method: 'POST', body: JSON.stringify(details) });
  return saveSession(result, result.user?.username || details.username);
}

async function refreshAccessToken() {
  const session = loadSession();
  if (!session?.refresh) throw new Error('Your session has expired. Please sign in again.');
  try {
    const tokens = await publicJson('/api/auth/token/refresh/', {
      method: 'POST', body: JSON.stringify({ refresh: session.refresh }),
    });
    return saveSession(tokens, session.username).access;
  } catch (error) {
    clearSession();
    throw error;
  }
}

export async function authenticatedRequest(path, options = {}, retry = true) {
  const session = loadSession();
  if (!session?.access) throw new Error('Sign in to continue.');
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${session.access}` },
  });
  if (response.status === 401 && retry) {
    await refreshAccessToken();
    return authenticatedRequest(path, options, false);
  }
  if (!response.ok) throw await responseError(response);
  if (response.status === 204) return null;
  return response.json();
}

export function createSong({ title, artist, language, file }) {
  const form = new FormData();
  form.append('title', title);
  form.append('artist', artist);
  form.append('language', language);
  form.append('full_mix_file', file);
  return authenticatedRequest('/api/songs/', { method: 'POST', body: form });
}

export function getProcessingJob(jobId, signal) {
  return authenticatedRequest(`/api/songs/processing-status/${encodeURIComponent(jobId)}/`, { signal });
}

export function getSong(songId, signal) {
  return authenticatedRequest(`/api/songs/${encodeURIComponent(songId)}/`, { signal });
}

export function getLibraries(signal) {
  return authenticatedRequest('/api/libraries/', { signal });
}

export function updateSong(songId, changes) {
  return authenticatedRequest(`/api/songs/${encodeURIComponent(songId)}/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  });
}

export function deleteSong(songId) {
  return authenticatedRequest(`/api/songs/${encodeURIComponent(songId)}/`, { method: 'DELETE' });
}

export function mediaUrl(value) {
  return value ? new URL(value, `${API_BASE_URL || window.location.origin}/`).toString() : '';
}
