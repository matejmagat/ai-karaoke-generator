import React, { useEffect, useMemo, useRef, useState } from 'react';
import './KaraokeApp.css';

const INITIAL_LYRICS = [
  { id: 1, start: 3.142, end: 3.462, text: 'Your' },
  { id: 2, start: 3.762, end: 4.243, text: 'eyes' },
  { id: 3, start: 4.363, end: 5.183, text: 'blue' },
  { id: 4, start: 5.223, end: 5.323, text: 'look' },
  { id: 5, start: 5.523, end: 6.344, text: 'away' },
  { id: 6, start: 6.444, end: 6.644, text: 'But' },
  { id: 7, start: 6.764, end: 8.085, text: 'I knew' },
  { id: 8, start: 8.165, end: 8.485, text: 'if I stared' },
  { id: 9, start: 8.505, end: 9.126, text: 'for too long' },
  { id: 10, start: 9.206, end: 10.647, text: 'I could get lost' },
  { id: 11, start: 10.767, end: 12.928, text: 'I got to have you' },
  { id: 12, start: 13.628, end: 15.47, text: 'At all costs' },
  { id: 13, start: 15.57, end: 17.931, text: 'I miss your hand holding mine' },
  { id: 14, start: 18.752, end: 22.294, text: "I feel like I'm standing in a line" },
  { id: 15, start: 28.075, end: 30.757, text: 'I miss your writing on my spine' },
  { id: 16, start: 31.138, end: 35.461, text: "I feel like I'm the oenophile and you're my favourite wine" },
  { id: 17, start: 35.541, end: 41.006, text: "High on the smoke nine, this is for what I'm designed" },
  { id: 18, start: 41.126, end: 49.833, text: 'To be on the skyline' },
];

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const formatTime = (seconds = 0) => {
  if (!Number.isFinite(seconds)) return '0:00';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

function parseTimestamp(timestamp) {
  const [hours, minutes, rest] = timestamp.trim().split(':');
  const [seconds, milliseconds = '0'] = rest.replace('.', ',').split(',');
  return Number(hours) * 3600 + Number(minutes) * 60 + Number(seconds) + Number(milliseconds.padEnd(3, '0').slice(0, 3)) / 1000;
}

function parseSrt(source) {
  const normalized = source.replace(/^\uFEFF/, '').replace(/\r/g, '').trim();
  if (!normalized) return [];
  return normalized.split(/\n{2,}/).map((block, index) => {
    const lines = block.split('\n').filter(Boolean);
    const timingIndex = lines.findIndex((line) => line.includes('-->'));
    if (timingIndex < 0) return null;
    const [start, end] = lines[timingIndex].split('-->').map(parseTimestamp);
    const text = lines.slice(timingIndex + 1).join(' ').trim();
    return text && Number.isFinite(start) && Number.isFinite(end)
      ? { id: index + 1, start, end, text }
      : null;
  }).filter(Boolean);
}

export default function KaraokeApp() {
  const instrumentalRef = useRef(null);
  const vocalRef = useRef(null);
  const rafRef = useRef(null);
  const objectUrls = useRef([]);

  const [lyrics, setLyrics] = useState(INITIAL_LYRICS);
  const [instrumentalName, setInstrumentalName] = useState('No instrumental selected');
  const [vocalName, setVocalName] = useState('No vocal stem selected');
  const [srtName, setSrtName] = useState('lyrics_aligned.srt');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [master, setMaster] = useState(80);
  const [instrumentalVolume, setInstrumentalVolume] = useState(100);
  const [vocalVolume, setVocalVolume] = useState(65);
  const [status, setStatus] = useState('Load your separated stems to start singing.');

  const currentCueIndex = useMemo(() => {
    const active = lyrics.findIndex((cue) => currentTime >= cue.start && currentTime < cue.end);
    if (active >= 0) return active;
    const next = lyrics.findIndex((cue) => cue.start > currentTime);
    return next > 0 ? next - 1 : next;
  }, [lyrics, currentTime]);

  const currentCue = currentCueIndex >= 0 ? lyrics[currentCueIndex] : null;
  const previousCue = currentCueIndex > 0 ? lyrics[currentCueIndex - 1] : null;
  const nextCue = currentCueIndex >= 0 && currentCueIndex < lyrics.length - 1 ? lyrics[currentCueIndex + 1] : null;

  const applyVolumes = () => {
    if (instrumentalRef.current) instrumentalRef.current.volume = (master / 100) * (instrumentalVolume / 100);
    if (vocalRef.current) vocalRef.current.volume = (master / 100) * (vocalVolume / 100);
  };

  useEffect(() => {
    applyVolumes();
  }, [master, instrumentalVolume, vocalVolume]);

  const syncClock = () => {
    const leader = instrumentalRef.current?.src ? instrumentalRef.current : vocalRef.current;
    if (!leader) return;
    setCurrentTime(leader.currentTime || 0);
    setDuration(Number.isFinite(leader.duration) ? leader.duration : 0);
    if (!leader.paused) rafRef.current = requestAnimationFrame(syncClock);
  };

  const seekAll = (time) => {
    const safeTime = Math.max(0, time);
    [instrumentalRef.current, vocalRef.current].forEach((audio) => {
      if (audio?.src) audio.currentTime = safeTime;
    });
    setCurrentTime(safeTime);
  };

  const handleAudioFile = (event, type) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    objectUrls.current.push(url);
    const audio = type === 'instrumental' ? instrumentalRef.current : vocalRef.current;
    if (audio) {
      audio.src = url;
      audio.load();
    }
    if (type === 'instrumental') setInstrumentalName(file.name);
    else setVocalName(file.name);
    setStatus(`${type === 'instrumental' ? 'Instrumental' : 'Vocal stem'} loaded: ${file.name}`);
  };

  const handleSrtFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const parsed = parseSrt(await file.text());
      if (!parsed.length) throw new Error('No usable SRT cues were found.');
      setLyrics(parsed);
      setSrtName(file.name);
      setStatus(`Imported ${parsed.length} lyric cues from ${file.name}.`);
      seekAll(0);
    } catch (error) {
      setStatus(error.message || 'Unable to parse this subtitle file.');
    }
  };

  const togglePlayback = async () => {
    const sources = [instrumentalRef.current, vocalRef.current].filter((audio) => audio?.src);
    if (!sources.length) {
      setStatus('Choose at least one audio stem before pressing play.');
      return;
    }
    try {
      if (isPlaying) {
        sources.forEach((audio) => audio.pause());
        cancelAnimationFrame(rafRef.current);
        setIsPlaying(false);
      } else {
        const leaderTime = sources[0].currentTime;
        sources.slice(1).forEach((audio) => { audio.currentTime = leaderTime; });
        await Promise.all(sources.map((audio) => audio.play()));
        setIsPlaying(true);
        rafRef.current = requestAnimationFrame(syncClock);
      }
    } catch {
      setStatus('The browser could not start playback. Try loading audio again.');
      setIsPlaying(false);
    }
  };

  const jumpToCue = (direction) => {
    if (!lyrics.length) return;
    const fallbackIndex = lyrics.findIndex((cue) => cue.start > currentTime);
    const base = currentCueIndex >= 0 ? currentCueIndex : Math.max(0, fallbackIndex);
    const target = lyrics[clamp(base + direction, 0, lyrics.length - 1)];
    seekAll(target.start);
  };

  const onLoadedMetadata = () => {
    const tracks = [instrumentalRef.current, vocalRef.current].filter((audio) => audio?.src && Number.isFinite(audio.duration));
    setDuration(tracks.length ? Math.max(...tracks.map((audio) => audio.duration)) : 0);
  };

  useEffect(() => () => {
    cancelAnimationFrame(rafRef.current);
    objectUrls.current.forEach(URL.revokeObjectURL);
  }, []);

  return (
    <main className="karaoke-app">
      <audio ref={instrumentalRef} onLoadedMetadata={onLoadedMetadata} onEnded={() => setIsPlaying(false)} />
      <audio ref={vocalRef} onLoadedMetadata={onLoadedMetadata} />

      <header className="topbar">
        <div className="brand"><span className="brand-mark">♫</span><span>Karaoke<span className="accent">Gen</span></span></div>
        <p>Two stems. One performance.</p>
      </header>

      <section className="workspace">
        <aside className="panel setup-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">Session</span><h2>Source files</h2></div>
            <span className="ready-dot" title="Ready" />
          </div>

          <label className="upload-card">
            <span className="upload-icon">◫</span>
            <span><strong>Instrumental</strong><small>{instrumentalName}</small></span>
            <input type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg,.aac,.flac" onChange={(event) => handleAudioFile(event, 'instrumental')} />
          </label>
          <label className="upload-card">
            <span className="upload-icon">♬</span>
            <span><strong>Guide vocals</strong><small>{vocalName}</small></span>
            <input type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg,.aac,.flac" onChange={(event) => handleAudioFile(event, 'vocal')} />
          </label>
          <label className="upload-card lyric-upload">
            <span className="upload-icon">≡</span>
            <span><strong>Timed lyrics</strong><small>{srtName}</small></span>
            <input type="file" accept=".srt,text/srt,application/x-subrip" onChange={handleSrtFile} />
          </label>

          <div className="format-note">Browser-supported audio only · SRT timestamps drive the lyric display</div>

          <div className="mixer">
            <div className="panel-heading compact"><div><span className="eyebrow">Mix</span><h2>Levels</h2></div><button className="text-button" onClick={() => { setMaster(80); setInstrumentalVolume(100); setVocalVolume(65); }}>Reset</button></div>
            <Slider label="Master" icon="◉" value={master} setValue={setMaster} />
            <Slider label="Instrumental" icon="◌" value={instrumentalVolume} setValue={setInstrumentalVolume} />
            <Slider label="Guide vocals" icon="◍" value={vocalVolume} setValue={setVocalVolume} />
          </div>
        </aside>

        <section className="stage">
          <div className="stage-glow glow-one" /><div className="stage-glow glow-two" />
          <span className="stage-label">Live lyric view</span>
          <div className="lyrics-display" aria-live="polite">
            <p className="nearby previous">{previousCue?.text || ' '}</p>
            <p className="active-lyric">{currentCue?.text || 'Load audio and press play'}</p>
            <p className="nearby next">{nextCue?.text || 'Your lyrics will appear here in time'}</p>
          </div>
          <div className="cue-pill"><span className="pulse" /> Cue {currentCueIndex >= 0 ? currentCueIndex + 1 : 0} of {lyrics.length}</div>
        </section>

        <aside className="panel cue-panel">
          <div className="panel-heading"><div><span className="eyebrow">Navigator</span><h2>Lyric cues</h2></div><span className="cue-count">{lyrics.length}</span></div>
          <div className="cue-list">
            {lyrics.map((cue, index) => (
              <button key={`${cue.id}-${index}`} onClick={() => seekAll(cue.start)} className={`cue-row ${index === currentCueIndex ? 'current' : ''} ${index < currentCueIndex ? 'past' : ''}`}>
                <span>{formatTime(cue.start)}</span><strong>{cue.text}</strong>
              </button>
            ))}
          </div>
        </aside>
      </section>

      <footer className="transport">
        <div className="transport-info"><span className="status-light" /><span>{status}</span></div>
        <div className="transport-controls">
          <button className="transport-button" onClick={() => jumpToCue(-1)} aria-label="Previous lyric cue">|◀</button>
          <button className="play-button" onClick={togglePlayback} aria-label={isPlaying ? 'Pause' : 'Play'}>{isPlaying ? 'Ⅱ' : '▶'}</button>
          <button className="transport-button" onClick={() => jumpToCue(1)} aria-label="Next lyric cue">▶|</button>
        </div>
        <div className="progress-wrap">
          <span>{formatTime(currentTime)}</span>
          <input aria-label="Track progress" type="range" min="0" max={duration || 1} step="0.01" value={Math.min(currentTime, duration || 0)} onChange={(event) => seekAll(Number(event.target.value))} />
          <span>{formatTime(duration)}</span>
        </div>
      </footer>
    </main>
  );
}

function Slider({ label, icon, value, setValue }) {
  return <label className="level-row"><span className="level-label"><i>{icon}</i>{label}</span><input type="range" min="0" max="100" value={value} onChange={(event) => setValue(Number(event.target.value))} /><output>{value}%</output></label>;
}
