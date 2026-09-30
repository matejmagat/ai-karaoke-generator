import { render, screen, within } from '@testing-library/react';
import { PlayerView } from './KaraokeViews';
import { DEFAULT_LYRICS_VIEW } from './LyricsDisplay';

const lyrics = Array.from({ length: 30 }, (_, index) => ({ id: index + 1, start: index, end: index + 1, text: `word${index}` }));
const noop = () => {};
const renderPlayer = (props = {}) => render(
  <PlayerView master={80} instrumentalVolume={100} vocalVolume={65} onMasterChange={noop} onInstrumentalChange={noop} onVocalChange={noop} onReset={noop}
    lyricsView={DEFAULT_LYRICS_VIEW} onLyricsViewChange={noop} onLyricsViewReset={noop} currentCueIndex={0} lyrics={lyrics} onSeek={noop}
    status="ready" isPlaying={false} onTogglePlayback={noop} onJumpToCue={noop} currentTime={0} duration={120} formatTime={(value) => String(value)} {...props} />,
);

test('navigator scrolls to keep the current cue in view', () => {
  const scrollTo = jest.fn();
  window.HTMLElement.prototype.scrollTo = scrollTo;
  const heights = [
    jest.spyOn(window.HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function height() { return this.dataset.testid === 'cue-list' ? 200 : 20; }),
    jest.spyOn(window.HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(function height() { return this.dataset.testid === 'cue-list' ? 1200 : 20; }),
    jest.spyOn(window.HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(40),
    jest.spyOn(window.HTMLElement.prototype, 'offsetTop', 'get').mockImplementation(function top() { return this.classList.contains('cue-row') ? Number(this.textContent.match(/\d+$/)[0]) * 40 : 0; }),
  ];
  const { rerender } = renderPlayer();
  expect(within(screen.getByTestId('cue-list')).getByRole('button', { name: /word0$/ })).toHaveAttribute('aria-current', 'true');
  rerender(<PlayerView master={80} instrumentalVolume={100} vocalVolume={65} onMasterChange={noop} onInstrumentalChange={noop} onVocalChange={noop} onReset={noop}
    lyricsView={DEFAULT_LYRICS_VIEW} onLyricsViewChange={noop} onLyricsViewReset={noop} currentCueIndex={10} lyrics={lyrics} onSeek={noop}
    status="ready" isPlaying={false} onTogglePlayback={noop} onJumpToCue={noop} currentTime={10} duration={120} formatTime={(value) => String(value)} />);
  expect(scrollTo).toHaveBeenLastCalledWith({ top: 320, behavior: 'smooth' });
  heights.forEach((spy) => spy.mockRestore()); delete window.HTMLElement.prototype.scrollTo;
});

test('timeline and level sliders fill up to their current value', () => {
  renderPlayer({ currentTime: 30, duration: 120 });
  expect(screen.getByLabelText('Track progress').style.getPropertyValue('--fill')).toBe('25%');
  expect(screen.getByLabelText(/Master/).style.getPropertyValue('--fill')).toBe('80%');
  expect(screen.getByLabelText(/Guide vocals/).style.getPropertyValue('--fill')).toBe('65%');
});

test('timeline comes before the transport buttons', () => {
  renderPlayer();
  const position = screen.getByLabelText('Track progress').compareDocumentPosition(screen.getByRole('button', { name: 'Play' }));
  expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
