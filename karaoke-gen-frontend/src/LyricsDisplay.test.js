import { fireEvent, render, screen } from '@testing-library/react';
import LyricsDisplay, {
  DEFAULT_LYRICS_VIEW, LYRICS_VIEW_STORAGE_KEY, LyricsSettings, getLyricWindow, loadLyricsView, normalizeLyricsView, saveLyricsView,
} from './LyricsDisplay';

const lyrics = Array.from({ length: 10 }, (_, index) => ({ id: index + 1, start: index, end: index + 1, text: `w${index}` }));
const texts = (words) => words.map((word) => word.cue.text);

beforeEach(() => localStorage.clear());

test('defaults to horizontal, centered, 3 ahead and 1 behind', () => {
  expect(DEFAULT_LYRICS_VIEW).toEqual({ scrolling: 'horizontal', static: false, ahead: 3, behind: 1 });
  expect(normalizeLyricsView()).toEqual(DEFAULT_LYRICS_VIEW);
});

test('normalizes invalid settings', () => {
  expect(normalizeLyricsView({ scrolling: 'diagonal', static: 'yes', ahead: -4, behind: '2' })).toEqual({ scrolling: 'horizontal', static: false, ahead: 0, behind: 2 });
  expect(normalizeLyricsView({ ahead: 99, behind: 'abc' })).toMatchObject({ ahead: 12, behind: 1 });
});

test('centered window follows the current word', () => {
  const window = getLyricWindow(lyrics, 4, { ahead: 3, behind: 1 });
  expect(texts(window.before)).toEqual(['w3']);
  expect(window.current.cue.text).toBe('w4');
  expect(texts(window.after)).toEqual(['w5', 'w6', 'w7']);
});

test('centered window is clipped at the edges of the song', () => {
  expect(texts(getLyricWindow(lyrics, 0, { ahead: 2, behind: 3 }).before)).toEqual([]);
  expect(texts(getLyricWindow(lyrics, 9, { ahead: 2, behind: 3 }).after)).toEqual([]);
  expect(texts(getLyricWindow(lyrics, 9, { ahead: 2, behind: 3 }).before)).toEqual(['w6', 'w7', 'w8']);
});

test('static window keeps a fixed page until the current word leaves it', () => {
  const settings = { static: true, ahead: 2, behind: 1 };
  expect(texts(getLyricWindow(lyrics, 0, settings).words)).toEqual(['w0', 'w1', 'w2', 'w3']);
  expect(texts(getLyricWindow(lyrics, 3, settings).words)).toEqual(['w0', 'w1', 'w2', 'w3']);
  expect(texts(getLyricWindow(lyrics, 4, settings).words)).toEqual(['w4', 'w5', 'w6', 'w7']);
  expect(texts(getLyricWindow(lyrics, 9, settings).words)).toEqual(['w8', 'w9']);
});

test('returns an empty window without an active cue', () => {
  expect(getLyricWindow(lyrics, -1)).toEqual({ before: [], current: null, after: [], words: [] });
  expect(getLyricWindow([], 0).current).toBeNull();
});

test('renders the configured layout and seeks when a word is clicked', () => {
  const onSeek = jest.fn();
  const { rerender } = render(<LyricsDisplay lyrics={lyrics} currentCueIndex={5} settings={DEFAULT_LYRICS_VIEW} onSeek={onSeek} />);
  const display = screen.getByTestId('lyrics-display');
  expect(display).toHaveClass('lyrics-horizontal', 'lyrics-centered');
  expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual(['w4', 'w5', 'w6', 'w7', 'w8']);
  expect(screen.getByText('w5')).toHaveAttribute('aria-current', 'true');
  fireEvent.click(screen.getByText('w7')); expect(onSeek).toHaveBeenCalledWith(7);
  rerender(<LyricsDisplay lyrics={lyrics} currentCueIndex={5} settings={{ scrolling: 'vertical', static: true, ahead: 1, behind: 0 }} onSeek={onSeek} />);
  expect(screen.getByTestId('lyrics-display')).toHaveClass('lyrics-vertical', 'lyrics-static');
  expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual(['w4', 'w5']);
});

test('shows a placeholder before lyrics are loaded', () => {
  render(<LyricsDisplay lyrics={[]} currentCueIndex={-1} settings={DEFAULT_LYRICS_VIEW} />);
  expect(screen.getByText('Choose or generate a song to begin')).toBeInTheDocument();
});

test('settings controls emit normalized changes', () => {
  const onChange = jest.fn(); const onReset = jest.fn();
  render(<LyricsSettings settings={DEFAULT_LYRICS_VIEW} onChange={onChange} onReset={onReset} />);
  fireEvent.click(screen.getByRole('radio', { name: 'Vertical' }));
  expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_LYRICS_VIEW, scrolling: 'vertical' });
  fireEvent.click(screen.getByLabelText('Static'));
  expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_LYRICS_VIEW, static: true });
  fireEvent.change(screen.getByLabelText('Words ahead'), { target: { value: '5' } });
  expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_LYRICS_VIEW, ahead: 5 });
  fireEvent.change(screen.getByLabelText('Words behind'), { target: { value: '0' } });
  expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_LYRICS_VIEW, behind: 0 });
  fireEvent.click(screen.getByRole('button', { name: 'Default' })); expect(onReset).toHaveBeenCalled();
});

test('persists settings in localStorage', () => {
  saveLyricsView({ scrolling: 'vertical', static: true, ahead: 4, behind: 2 });
  expect(JSON.parse(localStorage.getItem(LYRICS_VIEW_STORAGE_KEY))).toEqual({ scrolling: 'vertical', static: true, ahead: 4, behind: 2 });
  expect(loadLyricsView()).toEqual({ scrolling: 'vertical', static: true, ahead: 4, behind: 2 });
  localStorage.setItem(LYRICS_VIEW_STORAGE_KEY, '{not json');
  expect(loadLyricsView()).toEqual(DEFAULT_LYRICS_VIEW);
});
