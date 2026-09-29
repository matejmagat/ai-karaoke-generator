import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import KaraokeApp from './KaraokeApp';
import { createSong, deleteSong, getLibraries, getProcessingJob, getSong, updateSong } from './api';

jest.mock('./api', () => ({
  createSong: jest.fn(), deleteSong: jest.fn(), getLibraries: jest.fn(), getProcessingJob: jest.fn(), getSong: jest.fn(), updateSong: jest.fn(),
  mediaUrl: (value) => `http://localhost:8000${value}`,
}));

const flushPromises = () => act(async () => { await Promise.resolve(); });
const readySong = { id: 'song-1', title: 'Test Song', artist: 'Test Artist', processing_status: 'ready', duration_seconds: 90, is_public: false, instrumental_file: '/media/instrumental.wav', vocals_file: '/media/vocals.wav', lyrics_srt_file: '/media/lyrics.srt' };
const libraryResponse = () => [{ id: 1, name: 'My Library', song_count: 1, song_entries: [{ id: 10, song: readySong }] }];

beforeEach(() => {
  jest.useFakeTimers(); jest.clearAllMocks(); getLibraries.mockResolvedValue([]); deleteSong.mockResolvedValue(null); updateSong.mockImplementation((id, changes) => Promise.resolve({ ...readySong, ...changes }));
  global.fetch = jest.fn().mockResolvedValue({ ok: true, text: jest.fn().mockResolvedValue('1\n00:00:00,000 --> 00:00:01,000\nHello') });
  jest.spyOn(window.HTMLMediaElement.prototype, 'load').mockImplementation(() => {});
  jest.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
});
afterEach(() => { jest.runOnlyPendingTimers(); jest.useRealTimers(); jest.restoreAllMocks(); });

async function openPopulatedLibrary() {
  getLibraries.mockResolvedValue(libraryResponse());
  render(<KaraokeApp />); await flushPromises();
  fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
}

test('shows generation in Library and playback controls in Player', async () => {
  render(<KaraokeApp />); await flushPromises();
  expect(screen.getByRole('tab', { name: 'Player' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.queryByPlaceholderText('Song title')).not.toBeVisible(); expect(screen.getByRole('button', { name: 'Play' })).toBeVisible();
  fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  expect(screen.getByRole('tab', { name: 'Library' })).toHaveAttribute('aria-selected', 'true'); expect(screen.getByPlaceholderText('Song title')).toBeVisible(); expect(screen.getByText('Your library is empty')).toBeInTheDocument();
});

test('shows library loading and retryable error states', async () => {
  getLibraries.mockReturnValueOnce(new Promise(() => {}));
  const { unmount } = render(<KaraokeApp />); fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  expect(screen.getByText('Loading library…')).toBeInTheDocument(); unmount();
  getLibraries.mockRejectedValueOnce(new Error('Library unavailable')).mockResolvedValueOnce([]);
  render(<KaraokeApp />); await flushPromises(); fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Library unavailable'); fireEvent.click(screen.getByRole('button', { name: 'Retry' })); await flushPromises();
  expect(getLibraries).toHaveBeenCalledTimes(3); expect(screen.getByText('Your library is empty')).toBeInTheDocument();
});

test('renders nested songs and loads a ready song into the player', async () => {
  await openPopulatedLibrary();
  expect(screen.getByText('Test Song')).toBeInTheDocument(); expect(screen.getByText('Test Artist')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Load' })); await flushPromises();
  expect(screen.getByRole('tab', { name: 'Player' })).toHaveAttribute('aria-selected', 'true');
  expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/media/lyrics.srt', expect.objectContaining({ signal: expect.any(AbortSignal) }));
  expect(await within(screen.getByTestId('lyrics-display')).findByText('Hello')).toBeInTheDocument();
});

test('disables loading for non-ready and incomplete songs', async () => {
  getLibraries.mockResolvedValue([{ id: 1, name: 'My Library', song_count: 2, song_entries: [
    { id: 10, song: { ...readySong, id: 'processing', title: 'Processing Song', processing_status: 'processing' } },
    { id: 11, song: { ...readySong, id: 'incomplete', title: 'Incomplete Song', lyrics_srt_file: null } },
  ] }]);
  render(<KaraokeApp />); await flushPromises(); fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  expect(screen.getByText('processing')).toBeInTheDocument(); screen.getAllByRole('button', { name: 'Load' }).forEach((button) => expect(button).toBeDisabled());
});

test('edits song metadata and updates the card', async () => {
  await openPopulatedLibrary(); fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  fireEvent.change(screen.getByLabelText('Title for Test Song'), { target: { value: 'Updated Song' } }); fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(updateSong).toHaveBeenCalledWith('song-1', { title: 'Updated Song' })); expect(await screen.findByText('Updated Song')).toBeInTheDocument();
});

test('keeps the edit form and original card data when PATCH fails', async () => {
  updateSong.mockRejectedValueOnce(new Error('Update failed')); await openPopulatedLibrary(); fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  fireEvent.change(screen.getByLabelText('Title for Test Song'), { target: { value: 'Unsaved Song' } }); fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(screen.getAllByRole('alert').some((alert) => alert.textContent.includes('Update failed'))).toBe(true));
  expect(screen.getByLabelText('Title for Test Song')).toHaveValue('Unsaved Song');
});

test('requires confirmation before deleting a song', async () => {
  getLibraries.mockResolvedValueOnce(libraryResponse()).mockResolvedValueOnce([]); jest.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
  render(<KaraokeApp />); await flushPromises(); fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  fireEvent.click(screen.getByRole('button', { name: 'Delete song' })); expect(deleteSong).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Delete song' })); await waitFor(() => expect(deleteSong).toHaveBeenCalledWith('song-1')); await waitFor(() => expect(screen.getByText('Your library is empty')).toBeInTheDocument());
});

test('deleting the active song clears loaded playback state', async () => {
  getLibraries.mockResolvedValueOnce(libraryResponse()).mockResolvedValueOnce([]); jest.spyOn(window, 'confirm').mockReturnValue(true);
  render(<KaraokeApp />); await flushPromises(); fireEvent.click(screen.getByRole('tab', { name: 'Library' })); fireEvent.click(screen.getByRole('button', { name: 'Load' })); await flushPromises(); await within(screen.getByTestId('lyrics-display')).findByText('Hello');
  fireEvent.click(screen.getByRole('tab', { name: 'Library' })); fireEvent.click(screen.getByRole('button', { name: 'Delete song' })); await waitFor(() => expect(deleteSong).toHaveBeenCalledWith('song-1'));
  expect(await screen.findByText('Choose a song from your library.')).toBeInTheDocument(); document.querySelectorAll('audio').forEach((audio) => expect(audio).not.toHaveAttribute('src'));
});

test('keeps polling active jobs, loads completion, and refreshes the library', async () => {
  createSong.mockResolvedValue({ job_id: 'job-1', status: 'queued', updated_at: 'same' });
  getProcessingJob.mockResolvedValueOnce({ job_id: 'job-1', status: 'processing', updated_at: 'same' }).mockResolvedValueOnce({ job_id: 'job-1', status: 'processing', updated_at: 'same' }).mockResolvedValueOnce({ job_id: 'job-1', status: 'completed', song_id: 'song-1', updated_at: 'same' });
  getSong.mockResolvedValue(readySong);
  render(<KaraokeApp />); await flushPromises(); fireEvent.click(screen.getByRole('tab', { name: 'Library' }));
  fireEvent.change(screen.getByPlaceholderText('Song title'), { target: { value: 'Test Song' } }); fireEvent.change(screen.getByPlaceholderText('Artist name'), { target: { value: 'Test Artist' } }); fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [new File(['audio'], 'song.mp3', { type: 'audio/mpeg' })] } }); fireEvent.click(screen.getByRole('button', { name: /generate karaoke track/i })); await flushPromises();
  for (let attempt = 0; attempt < 3; attempt += 1) await act(async () => { jest.advanceTimersByTime(2000); await Promise.resolve(); });
  await flushPromises(); expect(getProcessingJob).toHaveBeenCalledTimes(3); expect(getSong).toHaveBeenCalledWith('song-1', expect.any(AbortSignal)); expect(await within(screen.getByTestId('lyrics-display')).findByText('Hello')).toBeInTheDocument(); expect(screen.getByText(/Test Artist — Test Song is ready to play/)).toBeInTheDocument(); expect(getLibraries).toHaveBeenCalledTimes(2);
});
