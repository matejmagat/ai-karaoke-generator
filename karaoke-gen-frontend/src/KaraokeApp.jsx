import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createSong, getProcessingJob } from './api';
import './KaraokeApp.css';

const INITIAL_LYRICS = [];
const ACTIVE_JOB_STATES = ['queued', 'processing'];
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

function errorMessage(error) {
  if (error.status === 400 && error.body) {
    return Object.entries(error.body)
      .map(([field, messages]) => `${field.replaceAll('_', ' ')}: ${[].concat(messages).join(' ')}`)
      .join(' ');
  }
  if (error.status === 404) return 'This processing job is no longer available.';
  if (error.status === 502) return 'The audio processing service is unavailable. Please retry.';
  return error.message || 'Generation failed. Please retry.';
}

export default function KaraokeApp() {
  const instrumentalRef = useRef(null);
  const vocalRef = useRef(null);
  const rafRef = useRef(null);

  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('');
  const [language, setLanguage] = useState('en');
  const [sourceFile, setSourceFile] = useState(null);
  const [job, setJob] = useState(null);
  const [generationError, setGenerationError] = useState('');
  const [lyrics, setLyrics] = useState(INITIAL_LYRICS);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [master, setMaster] = useState(80);
  const [instrumentalVolume, setInstrumentalVolume] = useState(100);
  const [vocalVolume, setVocalVolume] = useState(65);
  const [status, setStatus] = useState('Enter song details and choose a full mix.');

  const currentCueIndex = useMemo(() => {
    const active = lyrics.findIndex((cue) => currentTime >= cue.start && currentTime < cue.end);
    if (active >= 0) return active;
    const next = lyrics.findIndex((cue) => cue.start > currentTime);
    return next > 0 ? next - 1 : next;
  }, [lyrics, currentTime]);

  const currentCue = currentCueIndex >= 0 ? lyrics[currentCueIndex] : null;
  const previousCue = currentCueIndex > 0 ? lyrics[currentCueIndex - 1] : null;
  const nextCue = currentCueIndex >= 0 && currentCueIndex < lyrics.length - 1 ? lyrics[currentCueIndex + 1] : null;

  useEffect(() => {
    if (instrumentalRef.current) instrumentalRef.current.volume = (master / 100) * (instrumentalVolume / 100);
    if (vocalRef.current) vocalRef.current.volume = (master / 100) * (vocalVolume / 100);
  }, [master, instrumentalVolume, vocalVolume]);

  useEffect(() => {
    if (!job?.job_id || !ACTIVE_JOB_STATES.includes(job.status)) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const next = await getProcessingJob(job.job_id, controller.signal);
        setJob(next);
        if (next.status === 'failed') {
          setGenerationError(next.error || 'Song processing failed.');
          setStatus('Generation failed.');
        } else if (next.status === 'completed') {
          setStatus('Processing complete. Loading generated song…');
        } else {
          setStatus(next.status === 'queued' ? 'Generation queued…' : 'Separating stems and aligning lyrics…');
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          setGenerationError(errorMessage(error));
          setStatus('Could not check generation status.');
        }
      }
    }, 2000);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [job?.job_id, job?.status, job?.updated_at]);

  const submitGeneration = async () => {
    setGenerationError('');
    setJob(null);
    setLyrics([]);
    setStatus('Uploading full mix…');
    try {
      const created = await createSong({
        title: title.trim(), artist: artist.trim(), language: language.trim(), file: sourceFile,
      });
      setJob(created);
      setStatus(created.status === 'processing' ? 'Processing song…' : 'Generation queued…');
    } catch (error) {
      setGenerationError(errorMessage(error));
      setStatus('Could not start generation.');
    }
  };

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

  const togglePlayback = async () => {
    const sources = [instrumentalRef.current, vocalRef.current].filter((audio) => audio?.src);
    if (!sources.length) { setStatus('Generate a song before pressing play.'); return; }
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
      setStatus('The browser could not start playback. Reload the generated audio.');
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

  const generationReady = title.trim() && artist.trim() && language.trim() && sourceFile;
  const generating = ACTIVE_JOB_STATES.includes(job?.status);
  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  return (
    <main className="karaoke-app">
      <audio ref={instrumentalRef} onLoadedMetadata={onLoadedMetadata} onEnded={() => setIsPlaying(false)} />
      <audio ref={vocalRef} onLoadedMetadata={onLoadedMetadata} />
      <header className="topbar"><div className="brand"><span className="brand-mark">♫</span><span>Karaoke<span className="accent">Gen</span></span></div><p>One song in. Your karaoke mix out.</p></header>
      <section className="workspace">
        <aside className="panel setup-panel">
          <div className="panel-heading"><div><span className="eyebrow">Generator</span><h2>Source song</h2></div><span className="ready-dot" title={generationReady ? 'Ready' : 'Details required'} /></div>
          <label className="field-label">Title<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Song title" disabled={generating} /></label>
          <label className="field-label">Artist<input value={artist} onChange={(event) => setArtist(event.target.value)} placeholder="Artist name" disabled={generating} /></label>
          <label className="field-label">Language<input value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="en" pattern="[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?" disabled={generating} /></label>
          <label className="upload-card source-upload"><span className="upload-icon">♪</span><span><strong>Full mix</strong><small>{sourceFile?.name || 'Choose an MP3 or WAV file'}</small></span><input type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" disabled={generating} onChange={(event) => setSourceFile(event.target.files?.[0] || null)} /></label>
          <button className="generate-button" disabled={!generationReady || generating} onClick={submitGeneration}>{generating ? `${job.status === 'queued' ? 'Queued' : 'Processing'}…` : 'Generate karaoke track'}</button>
          {job && <div className={`job-status ${job.status}`}><strong>{job.status}</strong><span>Job {job.job_id}</span></div>}
          {generationError && <div className="generation-error" role="alert">{generationError}</div>}
          <div className="format-note">MP3 or WAV · language uses a code such as en, hr, or en-US</div>
          <div className="mixer">
            <div className="panel-heading compact"><div><span className="eyebrow">Mix</span><h2>Levels</h2></div><button className="text-button" onClick={() => { setMaster(80); setInstrumentalVolume(100); setVocalVolume(65); }}>Reset</button></div>
            <Slider label="Master" icon="◉" value={master} setValue={setMaster} /><Slider label="Instrumental" icon="◌" value={instrumentalVolume} setValue={setInstrumentalVolume} /><Slider label="Guide vocals" icon="◍" value={vocalVolume} setValue={setVocalVolume} />
          </div>
        </aside>
        <section className="stage"><div className="stage-glow glow-one" /><div className="stage-glow glow-two" /><span className="stage-label">Live lyric view</span><div className="lyrics-display" aria-live="polite"><p className="nearby previous">{previousCue?.text || ' '}</p><p className="active-lyric">{currentCue?.text || (generating ? 'Creating your karaoke track…' : 'Generate a song to begin')}</p><p className="nearby next">{nextCue?.text || 'Synchronized lyrics will appear here'}</p></div><div className="cue-pill"><span className="pulse" /> Cue {currentCueIndex >= 0 ? currentCueIndex + 1 : 0} of {lyrics.length}</div></section>
        <aside className="panel cue-panel"><div className="panel-heading"><div><span className="eyebrow">Navigator</span><h2>Lyric cues</h2></div><span className="cue-count">{lyrics.length}</span></div><div className="cue-list">{lyrics.map((cue, index) => <button key={`${cue.id}-${index}`} onClick={() => seekAll(cue.start)} className={`cue-row ${index === currentCueIndex ? 'current' : ''} ${index < currentCueIndex ? 'past' : ''}`}><span>{formatTime(cue.start)}</span><strong>{cue.text}</strong></button>)}</div></aside>
      </section>
      <footer className="transport"><div className="transport-info"><span className="status-light" /><span>{status}</span></div><div className="transport-controls"><button className="transport-button" onClick={() => jumpToCue(-1)} aria-label="Previous lyric cue">|◀</button><button className="play-button" onClick={togglePlayback} aria-label={isPlaying ? 'Pause' : 'Play'}>{isPlaying ? 'Ⅱ' : '▶'}</button><button className="transport-button" onClick={() => jumpToCue(1)} aria-label="Next lyric cue">▶|</button></div><div className="progress-wrap"><span>{formatTime(currentTime)}</span><input aria-label="Track progress" type="range" min="0" max={duration || 1} step="0.01" value={Math.min(currentTime, duration || 0)} onChange={(event) => seekAll(Number(event.target.value))} /><span>{formatTime(duration)}</span></div></footer>
    </main>
  );
}

function Slider({ label, icon, value, setValue }) {
  return <label className="level-row"><span className="level-label"><i>{icon}</i>{label}</span><input type="range" min="0" max="100" value={value} onChange={(event) => setValue(Number(event.target.value))} /><output>{value}%</output></label>;
}
