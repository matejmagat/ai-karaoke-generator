import React from 'react';

export const LYRICS_VIEW_STORAGE_KEY = 'karaoke.lyricsView';
export const MAX_CONTEXT_WORDS = 12;
export const DEFAULT_LYRICS_VIEW = Object.freeze({
  scrolling: 'horizontal',
  static: false,
  ahead: 3,
  behind: 1,
});

const SCROLLING_MODES = ['horizontal', 'vertical'];
const toWordCount = (value, fallback) => {
  const number = Math.floor(Number(value));
  if (!Number.isFinite(number)) return fallback;
  return Math.min(MAX_CONTEXT_WORDS, Math.max(0, number));
};

// Coerces any partial/untrusted settings object into a valid lyric view configuration.
export function normalizeLyricsView(settings = {}) {
  const source = settings && typeof settings === 'object' ? settings : {};
  return {
    scrolling: SCROLLING_MODES.includes(source.scrolling) ? source.scrolling : DEFAULT_LYRICS_VIEW.scrolling,
    static: typeof source.static === 'boolean' ? source.static : DEFAULT_LYRICS_VIEW.static,
    ahead: toWordCount(source.ahead, DEFAULT_LYRICS_VIEW.ahead),
    behind: toWordCount(source.behind, DEFAULT_LYRICS_VIEW.behind),
  };
}

export function loadLyricsView(storage = window.localStorage) {
  try {
    const stored = storage?.getItem(LYRICS_VIEW_STORAGE_KEY);
    return normalizeLyricsView(stored ? JSON.parse(stored) : {});
  } catch {
    return { ...DEFAULT_LYRICS_VIEW };
  }
}

export function saveLyricsView(settings, storage = window.localStorage) {
  try { storage?.setItem(LYRICS_VIEW_STORAGE_KEY, JSON.stringify(normalizeLyricsView(settings))); } catch { /* storage unavailable */ }
}

/**
 * Selects the cues visible around the current cue.
 *
 * - Centered (static = false): a window that slides with every word, keeping the current
 *   word in the middle with `behind` words before it and `ahead` words after it.
 * - Static (static = true): the lyrics are split into fixed pages of `behind + 1 + ahead`
 *   words. The page stays put while the highlight moves across it and flips once the
 *   current word leaves the page.
 */
export function getLyricWindow(lyrics, currentIndex, settings = DEFAULT_LYRICS_VIEW) {
  const { behind, ahead, static: isStatic } = normalizeLyricsView(settings);
  if (!lyrics.length || currentIndex < 0) return { before: [], current: null, after: [], words: [] };
  const index = Math.min(currentIndex, lyrics.length - 1);
  const withIndex = (start, end) => lyrics.slice(start, end).map((cue, offset) => ({ cue, index: start + offset }));
  let start;
  let end;
  if (isStatic) {
    const pageSize = behind + 1 + ahead;
    start = Math.floor(index / pageSize) * pageSize;
    end = Math.min(lyrics.length, start + pageSize);
  } else {
    start = Math.max(0, index - behind);
    end = Math.min(lyrics.length, index + ahead + 1);
  }
  const words = withIndex(start, end);
  return {
    before: words.filter((word) => word.index < index),
    current: { cue: lyrics[index], index },
    after: words.filter((word) => word.index > index),
    words,
  };
}

function Word({ word, currentIndex, onSeek }) {
  const state = word.index === currentIndex ? 'current' : word.index < currentIndex ? 'past' : 'upcoming';
  return (
    <button
      type="button"
      className={`lyric-word ${state}`}
      aria-current={state === 'current' ? 'true' : undefined}
      style={{ '--distance': Math.abs(word.index - currentIndex) }}
      onClick={() => onSeek?.(word.cue.start)}
      tabIndex={-1}
    >
      {word.cue.text}
    </button>
  );
}

export default function LyricsDisplay({ lyrics, currentCueIndex, settings, onSeek }) {
  const view = normalizeLyricsView(settings);
  const { before, current, after, words } = getLyricWindow(lyrics, currentCueIndex, view);
  const layoutClass = `lyrics-display lyrics-${view.scrolling} ${view.static ? 'lyrics-static' : 'lyrics-centered'}`;

  if (!current) {
    return (
      <div className={layoutClass} aria-live="polite" data-testid="lyrics-display">
        <p className="lyrics-placeholder active-lyric">Choose or generate a song to begin</p>
        <p className="lyrics-placeholder nearby">Synchronized lyrics will appear here</p>
      </div>
    );
  }

  if (view.static) {
    return (
      <div className={layoutClass} aria-live="polite" data-testid="lyrics-display">
        <div className="lyric-page">
          {words.map((word) => <Word key={`${word.cue.id}-${word.index}`} word={word} currentIndex={current.index} onSeek={onSeek} />)}
        </div>
      </div>
    );
  }

  return (
    <div className={layoutClass} aria-live="polite" data-testid="lyrics-display">
      <div className="lyric-context lyric-behind">
        {before.map((word) => <Word key={`${word.cue.id}-${word.index}`} word={word} currentIndex={current.index} onSeek={onSeek} />)}
      </div>
      <Word word={current} currentIndex={current.index} onSeek={onSeek} />
      <div className="lyric-context lyric-ahead">
        {after.map((word) => <Word key={`${word.cue.id}-${word.index}`} word={word} currentIndex={current.index} onSeek={onSeek} />)}
      </div>
    </div>
  );
}

export function LyricsSettings({ settings, onChange, onReset }) {
  const view = normalizeLyricsView(settings);
  const update = (changes) => onChange(normalizeLyricsView({ ...view, ...changes }));
  return (
    <div className="lyrics-settings">
      <div className="panel-heading compact"><div><span className="eyebrow">Display</span><h2>Lyrics view</h2></div><button type="button" className="text-button" onClick={onReset}>Default</button></div>
      <div className="setting-row">
        <span className="level-label">Scrolling</span>
        <div className="segmented" role="radiogroup" aria-label="Lyric scrolling">
          {SCROLLING_MODES.map((mode) => (
            <button key={mode} type="button" role="radio" aria-checked={view.scrolling === mode} className={view.scrolling === mode ? 'selected' : ''} onClick={() => update({ scrolling: mode })}>
              {mode === 'horizontal' ? 'Horizontal' : 'Vertical'}
            </button>
          ))}
        </div>
      </div>
      <label className="setting-row">
        <span className="level-label">Static</span>
        <input type="checkbox" className="toggle" checked={view.static} onChange={(event) => update({ static: event.target.checked })} />
      </label>
      <label className="setting-row">
        <span className="level-label">Words ahead</span>
        <input type="number" className="word-count" min="0" max={MAX_CONTEXT_WORDS} value={view.ahead} onChange={(event) => update({ ahead: event.target.value })} />
      </label>
      <label className="setting-row">
        <span className="level-label">Words behind</span>
        <input type="number" className="word-count" min="0" max={MAX_CONTEXT_WORDS} value={view.behind} onChange={(event) => update({ behind: event.target.value })} />
      </label>
    </div>
  );
}
