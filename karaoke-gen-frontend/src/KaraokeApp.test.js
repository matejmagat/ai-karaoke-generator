import { act, fireEvent, render, screen } from '@testing-library/react';
import KaraokeApp from './KaraokeApp';
import { createSong, getLibraries, getProcessingJob, getSong } from './api';

jest.mock('./api', () => ({
  createSong: jest.fn(),
  getLibraries: jest.fn(),
  getProcessingJob: jest.fn(),
  getSong: jest.fn(),
  mediaUrl: (value) => `http://localhost:8000${value}`,
}));

const flushPromises = () => act(async () => { await Promise.resolve(); });

beforeEach(() => {
  jest.useFakeTimers(); jest.clearAllMocks(); getLibraries.mockResolvedValue([]);
  global.fetch = jest.fn().mockResolvedValue({ ok: true, text: jest.fn().mockResolvedValue('1\n00:00:00,000 --> 00:00:01,000\nHello') });
  jest.spyOn(window.HTMLMediaElement.prototype, 'load').mockImplementation(() => {});
});
afterEach(() => { jest.runOnlyPendingTimers(); jest.useRealTimers(); jest.restoreAllMocks(); });

test('shows generation in Library and playback controls in Player', async () => {
  render(<KaraokeApp />); await flushPromises();
  expect(screen.getByRole('tab', { name: 'Player' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.queryByPlaceholderText('Song title')).not.toBeVisible();
  expect(screen.getByRole('button', { name: 'Play' })).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  expect(screen.getByRole('tab', { name: 'Library' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByPlaceholderText('Song title')).toBeVisible();
  expect(screen.getByText('Your library is empty')).toBeInTheDocument();
});

test('renders nested songs returned by the library API', async () => {
  getLibraries.mockResolvedValue([{ id: 1, name: 'My Library', song_count: 1, song_entries: [{ id: 10, song: { id: 'song-1', title: 'Test Song', artist: 'Test Artist', processing_status: 'ready', instrumental_file: '/i.wav', vocals_file: '/v.wav', lyrics_srt_file: '/l.srt' } }] }]);
  render(<KaraokeApp />); await flushPromises();
  fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  expect(screen.getByText('Test Song')).toBeInTheDocument();
  expect(screen.getByText('Test Artist')).toBeInTheDocument();
});

test('keeps polling unchanged active jobs and loads the completed song', async () => {
  createSong.mockResolvedValue({ job_id: 'job-1', status: 'queued', updated_at: 'same' });
  getProcessingJob.mockResolvedValueOnce({ job_id: 'job-1', status: 'processing', updated_at: 'same' }).mockResolvedValueOnce({ job_id: 'job-1', status: 'processing', updated_at: 'same' }).mockResolvedValueOnce({ job_id: 'job-1', status: 'completed', song_id: 'song-1', updated_at: 'same' });
  getSong.mockResolvedValue({ id: 'song-1', title: 'Test Song', artist: 'Test Artist', instrumental_file: '/media/instrumental.wav', vocals_file: '/media/vocals.wav', lyrics_srt_file: '/media/lyrics.srt' });
  render(<KaraokeApp />); await flushPromises(); fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  fireEvent.change(screen.getByPlaceholderText('Song title'), { target: { value: 'Test Song' } });
  fireEvent.change(screen.getByPlaceholderText('Artist name'), { target: { value: 'Test Artist' } });
  fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [new File(['audio'], 'song.mp3', { type: 'audio/mpeg' })] } });
  fireEvent.click(screen.getByRole('button', { name: /generate karaoke track/i })); await flushPromises();
  for (let attempt = 0; attempt < 3; attempt += 1) await act(async () => { jest.advanceTimersByTime(2000); await Promise.resolve(); });
  await flushPromises();
  expect(getProcessingJob).toHaveBeenCalledTimes(3); expect(getSong).toHaveBeenCalledWith('song-1', expect.any(AbortSignal));
  expect(await screen.findByText('Hello')).toBeInTheDocument(); expect(screen.getByText(/Test Artist — Test Song is ready to play/)).toBeInTheDocument();
  expect(getLibraries).toHaveBeenCalledTimes(2);
});
