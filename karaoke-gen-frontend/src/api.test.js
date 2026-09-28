import { authenticatedRequest, clearSession, createSong, login } from './api';

beforeEach(() => {
  localStorage.clear();
  global.fetch = jest.fn();
});

afterEach(() => jest.restoreAllMocks());

function response(status, body) {
  return { ok: status >= 200 && status < 300, status, json: jest.fn().mockResolvedValue(body) };
}

test('stores login tokens for authenticated requests', async () => {
  fetch.mockResolvedValueOnce(response(200, { access: 'access-token', refresh: 'refresh-token' }));
  await login({ username: 'singer', password: 'password123' });
  const session = JSON.parse(localStorage.getItem('karaoke-gen-session'));
  expect(session).toMatchObject({ username: 'singer', access: 'access-token', refresh: 'refresh-token' });
});

test('refreshes once after a protected request returns 401', async () => {
  localStorage.setItem('karaoke-gen-session', JSON.stringify({ username: 'singer', access: 'old', refresh: 'refresh' }));
  fetch
    .mockResolvedValueOnce(response(401, { detail: 'expired' }))
    .mockResolvedValueOnce(response(200, { access: 'new' }))
    .mockResolvedValueOnce(response(200, { value: 'ok' }));

  await expect(authenticatedRequest('/api/protected/')).resolves.toEqual({ value: 'ok' });
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer new');
});

test('submits song creation as multipart form data', async () => {
  localStorage.setItem('karaoke-gen-session', JSON.stringify({ username: 'singer', access: 'access', refresh: 'refresh' }));
  fetch.mockResolvedValueOnce(response(202, { job_id: 'job-1', status: 'queued' }));
  const file = new File(['audio'], 'mix.mp3', { type: 'audio/mpeg' });

  await createSong({ title: 'Title', artist: 'Artist', language: 'en', file });
  const options = fetch.mock.calls[0][1];
  expect(options.body).toBeInstanceOf(FormData);
  expect(options.body.get('full_mix_file')).toBe(file);
  expect(options.headers['Content-Type']).toBeUndefined();
});

test('clears persisted tokens on logout', () => {
  localStorage.setItem('karaoke-gen-session', '{}');
  clearSession();
  expect(localStorage.getItem('karaoke-gen-session')).toBeNull();
});
