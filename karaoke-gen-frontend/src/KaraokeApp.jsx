import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createSong, deleteSong, getLibraries, getProcessingJob, getSong, mediaUrl, updateSong } from './api';
import KaraokeTabs from './KaraokeTabs';
import { GenerationForm, PlayerView } from './KaraokeViews';
import LibraryView from './LibraryView';
import { DEFAULT_LYRICS_VIEW, loadLyricsView, saveLyricsView } from './LyricsDisplay';
import './KaraokeApp.css';

const ACTIVE_JOB_STATES = ['queued', 'processing'];
const POLL_INTERVAL_MS = 2000;
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
export function parseSrt(source) {
  const normalized = source.replace(/^\uFEFF/, '').replace(/\r/g, '').trim();
  if (!normalized) return [];
  return normalized.split(/\n{2,}/).map((block, index) => {
    const lines = block.split('\n').filter(Boolean);
    const timingIndex = lines.findIndex((line) => line.includes('-->'));
    if (timingIndex < 0) return null;
    const [start, end] = lines[timingIndex].split('-->').map(parseTimestamp);
    const text = lines.slice(timingIndex + 1).join(' ').trim();
    return text && Number.isFinite(start) && Number.isFinite(end) ? { id: index + 1, start, end, text } : null;
  }).filter(Boolean);
}
export function errorMessage(error) {
  if (error.status === 400 && error.body) return Object.entries(error.body).map(([field, messages]) => `${field.replaceAll('_', ' ')}: ${[].concat(messages).join(' ')}`).join(' ');
  if (error.status === 404) return 'This processing job is no longer available.';
  if (error.status === 502) return 'The audio processing service is unavailable. Please retry.';
  return error.message || 'Generation failed. Please retry.';
}

export default function KaraokeApp() {
  const instrumentalRef = useRef(null);
  const vocalRef = useRef(null);
  const rafRef = useRef(null);
  const loadedSongRef = useRef(null);
  const [activeTab, setActiveTab] = useState('player');
  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('');
  const [language, setLanguage] = useState('en');
  const [sourceFile, setSourceFile] = useState(null);
  const [job, setJob] = useState(null);
  const [song, setSong] = useState(null);
  const [generationError, setGenerationError] = useState('');
  const [libraries, setLibraries] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState('');
  const [lyrics, setLyrics] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [master, setMaster] = useState(80);
  const [instrumentalVolume, setInstrumentalVolume] = useState(100);
  const [vocalVolume, setVocalVolume] = useState(65);
  const [status, setStatus] = useState('Choose a song from your library.');
  const [lyricsView, setLyricsView] = useState(() => loadLyricsView());
  useEffect(() => { saveLyricsView(lyricsView); }, [lyricsView]);

  const refreshLibraries = useCallback(async (signal) => {
    setLibraryLoading(true); setLibraryError('');
    try {
      const result = await getLibraries(signal);
      setLibraries(Array.isArray(result) ? result : result.results || []);
    } catch (error) {
      if (error.name !== 'AbortError') setLibraryError(errorMessage(error));
    } finally {
      if (!signal?.aborted) setLibraryLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController(); refreshLibraries(controller.signal);
    return () => controller.abort();
  }, [refreshLibraries]);

  const currentCueIndex = useMemo(() => {
    const active = lyrics.findIndex((cue) => currentTime >= cue.start && currentTime < cue.end);
    if (active >= 0) return active;
    const next = lyrics.findIndex((cue) => cue.start > currentTime);
    return next > 0 ? next - 1 : next;
  }, [lyrics, currentTime]);

  useEffect(() => {
    if (instrumentalRef.current) instrumentalRef.current.volume = (master / 100) * (instrumentalVolume / 100);
    if (vocalRef.current) vocalRef.current.volume = (master / 100) * (vocalVolume / 100);
  }, [master, instrumentalVolume, vocalVolume]);

  useEffect(() => {
    const jobId = job?.job_id;
    if (!jobId) return undefined;
    const controller = new AbortController(); let timer; let stopped = false;
    const poll = async () => {
      try {
        const next = await getProcessingJob(jobId, controller.signal);
        if (stopped) return;
        setJob(next);
        if (next.status === 'failed') { setGenerationError(next.error || 'Song processing failed.'); setStatus('Generation failed.'); }
        else if (next.status === 'completed') setStatus('Processing complete. Loading generated song…');
        else { setStatus(next.status === 'queued' ? 'Generation queued…' : 'Separating stems and aligning lyrics…'); timer = setTimeout(poll, POLL_INTERVAL_MS); }
      } catch (error) {
        if (!stopped && error.name !== 'AbortError') { setGenerationError(errorMessage(error)); setStatus('Could not check generation status.'); }
      }
    };
    timer = setTimeout(poll, POLL_INTERVAL_MS);
    return () => { stopped = true; clearTimeout(timer); controller.abort(); };
  }, [job?.job_id]);

  useEffect(() => {
    if (job?.status !== 'completed' || !job.song_id || song?.id === job.song_id) return undefined;
    const controller = new AbortController();
    getSong(job.song_id, controller.signal).then(async (completedSong) => {
      setSong(completedSong); await refreshLibraries(); setActiveTab('player');
    }).catch((error) => {
      if (error.name !== 'AbortError') { setGenerationError(errorMessage(error)); setStatus('Could not load the completed song.'); }
    });
    return () => controller.abort();
  }, [job?.status, job?.song_id, song?.id, refreshLibraries]);

  const seekAll = (time) => {
    const safeTime = Math.max(0, time);
    [instrumentalRef.current, vocalRef.current].forEach((audio) => { if (audio?.src) audio.currentTime = safeTime; });
    setCurrentTime(safeTime);
  };
  useEffect(() => {
    if (!song?.id || loadedSongRef.current === song.id) return undefined;
    const controller = new AbortController();
    const loadGeneratedSong = async () => {
      try {
        if (!song.instrumental_file || !song.vocals_file || !song.lyrics_srt_file) throw new Error('The generated song is missing one or more output files.');
        instrumentalRef.current.src = mediaUrl(song.instrumental_file); vocalRef.current.src = mediaUrl(song.vocals_file);
        instrumentalRef.current.load(); vocalRef.current.load();
        const response = await fetch(mediaUrl(song.lyrics_srt_file), { signal: controller.signal });
        if (!response.ok) throw new Error('Could not load generated lyrics.');
        const parsed = parseSrt(await response.text());
        if (!parsed.length) throw new Error('Generated SRT has no usable lyric cues.');
        setLyrics(parsed); seekAll(0); loadedSongRef.current = song.id; setStatus(`${song.artist} — ${song.title} is ready to play.`);
      } catch (error) {
        if (error.name !== 'AbortError') { setGenerationError(error.message || 'Could not load generated files.'); setStatus('Generated media is unavailable.'); }
      }
    };
    loadGeneratedSong();
    return () => controller.abort();
  }, [song]);

  const submitGeneration = async () => {
    setGenerationError(''); setJob(null); setSong(null); setLyrics([]); loadedSongRef.current = null; setStatus('Uploading full mix…');
    try {
      const created = await createSong({ title: title.trim(), artist: artist.trim(), language: language.trim(), file: sourceFile });
      setJob(created); setStatus(created.status === 'processing' ? 'Processing song…' : 'Generation queued…');
    } catch (error) { setGenerationError(errorMessage(error)); setStatus('Could not start generation.'); }
  };
  const syncClock = () => {
    const leader = instrumentalRef.current?.src ? instrumentalRef.current : vocalRef.current;
    if (!leader) return;
    setCurrentTime(leader.currentTime || 0); setDuration(Number.isFinite(leader.duration) ? leader.duration : 0);
    if (!leader.paused) rafRef.current = requestAnimationFrame(syncClock);
  };
  const togglePlayback = async () => {
    const sources = [instrumentalRef.current, vocalRef.current].filter((audio) => audio?.src);
    if (!sources.length) { setStatus('Choose or generate a song before pressing play.'); return; }
    try {
      if (isPlaying) { sources.forEach((audio) => audio.pause()); cancelAnimationFrame(rafRef.current); setIsPlaying(false); }
      else { const leaderTime = sources[0].currentTime; sources.slice(1).forEach((audio) => { audio.currentTime = leaderTime; }); await Promise.all(sources.map((audio) => audio.play())); setIsPlaying(true); rafRef.current = requestAnimationFrame(syncClock); }
    } catch { setStatus('The browser could not start playback. Reload the generated audio.'); setIsPlaying(false); }
  };
  const jumpToCue = (direction) => {
    if (!lyrics.length) return;
    const fallbackIndex = lyrics.findIndex((cue) => cue.start > currentTime);
    const base = currentCueIndex >= 0 ? currentCueIndex : Math.max(0, fallbackIndex);
    seekAll(lyrics[clamp(base + direction, 0, lyrics.length - 1)].start);
  };
  const onLoadedMetadata = () => {
    const tracks = [instrumentalRef.current, vocalRef.current].filter((audio) => audio?.src && Number.isFinite(audio.duration));
    setDuration(tracks.length ? Math.max(...tracks.map((audio) => audio.duration)) : 0);
  };
  const loadSongIntoPlayer = (selectedSong) => {
    if (selectedSong.processing_status !== 'ready') { setLibraryError('This song is not ready to play.'); return; }
    if (!selectedSong.instrumental_file || !selectedSong.vocals_file || !selectedSong.lyrics_srt_file) { setLibraryError('This song is missing one or more media files.'); return; }
    [instrumentalRef.current, vocalRef.current].forEach((audio) => audio?.pause());
    cancelAnimationFrame(rafRef.current); setIsPlaying(false); loadedSongRef.current = null; setLyrics([]); setCurrentTime(0); setDuration(0); setGenerationError(''); setLibraryError(''); setSong(selectedSong); setActiveTab('player');
  };
  const editLibrarySong = async (selectedSong, changes) => {
    setLibraryError('');
    try {
      const savedSong = await updateSong(selectedSong.id, changes);
      setLibraries((current) => current.map((library) => ({ ...library, song_entries: (library.song_entries || []).map((entry) => entry.song.id === savedSong.id ? { ...entry, song: savedSong } : entry) })));
      if (song?.id === savedSong.id) { setSong(savedSong); setStatus(`${savedSong.artist} — ${savedSong.title} is ready to play.`); }
      return savedSong;
    } catch (error) { setLibraryError(errorMessage(error)); throw error; }
  };
  const clearPlayer = () => {
    [instrumentalRef.current, vocalRef.current].forEach((audio) => { audio?.pause(); audio?.removeAttribute('src'); audio?.load(); });
    cancelAnimationFrame(rafRef.current); loadedSongRef.current = null; setSong(null); setLyrics([]); setCurrentTime(0); setDuration(0); setIsPlaying(false); setStatus('Choose a song from your library.');
  };
  const removeLibrarySong = async (selectedSong) => {
    if (!window.confirm(`Delete "${selectedSong.title}" from your songs?`)) return;
    setLibraryError('');
    try {
      await deleteSong(selectedSong.id);
      const wasActive = song?.id === selectedSong.id || loadedSongRef.current === selectedSong.id;
      await refreshLibraries();
      if (wasActive) clearPlayer();
    } catch (error) { setLibraryError(errorMessage(error)); throw error; }
  };
  const generationReady = title.trim() && artist.trim() && language.trim() && sourceFile;
  const generating = ACTIVE_JOB_STATES.includes(job?.status);
  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  return (
    <main className="karaoke-app">
      <audio ref={instrumentalRef} onLoadedMetadata={onLoadedMetadata} onEnded={() => setIsPlaying(false)} /><audio ref={vocalRef} onLoadedMetadata={onLoadedMetadata} />
      <header className="topbar"><div className="brand"><span className="brand-mark">♫</span><span>Karaoke<span className="accent">Gen</span></span></div><p>One song in. Your karaoke mix out.</p></header>
      <KaraokeTabs activeTab={activeTab} onSelect={setActiveTab} />
      <section id="player-panel" className="tab-panel player-panel" role="tabpanel" aria-labelledby="player-tab" hidden={activeTab !== 'player'}><PlayerView master={master} instrumentalVolume={instrumentalVolume} vocalVolume={vocalVolume} onMasterChange={setMaster} onInstrumentalChange={setInstrumentalVolume} onVocalChange={setVocalVolume} onReset={() => { setMaster(80); setInstrumentalVolume(100); setVocalVolume(65); }} lyricsView={lyricsView} onLyricsViewChange={setLyricsView} onLyricsViewReset={() => setLyricsView({ ...DEFAULT_LYRICS_VIEW })} currentCueIndex={currentCueIndex} lyrics={lyrics} onSeek={seekAll} status={status} isPlaying={isPlaying} onTogglePlayback={togglePlayback} onJumpToCue={jumpToCue} currentTime={currentTime} duration={duration} formatTime={formatTime} /></section>
      <section id="library-panel" className="tab-panel library-panel" role="tabpanel" aria-labelledby="library-tab" hidden={activeTab !== 'library'}><div className="library-grid"><GenerationForm title={title} artist={artist} language={language} sourceFile={sourceFile} job={job} error={generationError} generating={generating} generationReady={generationReady} onTitleChange={setTitle} onArtistChange={setArtist} onLanguageChange={setLanguage} onFileChange={setSourceFile} onSubmit={submitGeneration} /><LibraryView libraries={libraries} loading={libraryLoading} error={libraryError} onRetry={() => refreshLibraries()} onLoad={loadSongIntoPlayer} onEdit={editLibrarySong} onDelete={removeLibrarySong} /></div></section>
    </main>
  );
}
