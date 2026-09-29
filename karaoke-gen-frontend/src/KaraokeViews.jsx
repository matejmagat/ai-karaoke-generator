import React from 'react';
import LyricsDisplay, { LyricsSettings } from './LyricsDisplay';

export function GenerationForm({
  title, artist, language, sourceFile, job, error, generating, generationReady,
  onTitleChange, onArtistChange, onLanguageChange, onFileChange, onSubmit,
}) {
  return (
    <section className="panel generator-panel" aria-labelledby="generator-heading">
      <div className="panel-heading">
        <div><span className="eyebrow">Generator</span><h2 id="generator-heading">Source song</h2></div>
        <span className="ready-dot" title={generationReady ? 'Ready' : 'Details required'} />
      </div>
      <label className="field-label">Title<input value={title} onChange={(event) => onTitleChange(event.target.value)} placeholder="Song title" disabled={generating} /></label>
      <label className="field-label">Artist<input value={artist} onChange={(event) => onArtistChange(event.target.value)} placeholder="Artist name" disabled={generating} /></label>
      <label className="field-label">Language<input value={language} onChange={(event) => onLanguageChange(event.target.value)} placeholder="en" pattern="[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?" disabled={generating} /></label>
      <label className="upload-card source-upload"><span className="upload-icon">♪</span><span><strong>Full mix</strong><small>{sourceFile?.name || 'Choose an MP3 or WAV file'}</small></span><input type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" disabled={generating} onChange={(event) => onFileChange(event.target.files?.[0] || null)} /></label>
      <button type="button" className="generate-button" disabled={!generationReady || generating} onClick={onSubmit}>{generating ? `${job.status === 'queued' ? 'Queued' : 'Processing'}…` : 'Generate karaoke track'}</button>
      {job && <div className={`job-status ${job.status}`}><strong>{job.status}</strong><span>Job {job.job_id}</span></div>}
      {error && <div className="generation-error" role="alert">{error}</div>}
      <div className="format-note">MP3 or WAV · language uses a code such as en, hr, or en-US</div>
    </section>
  );
}

export function Mixer({ master, instrumentalVolume, vocalVolume, onMasterChange, onInstrumentalChange, onVocalChange, onReset, lyricsView, onLyricsViewChange, onLyricsViewReset }) {
  return (
    <aside className="panel mixer-panel">
      <div className="mixer">
        <div className="panel-heading compact"><div><span className="eyebrow">Mix</span><h2>Levels</h2></div><button type="button" className="text-button" onClick={onReset}>Reset</button></div>
        <Slider label="Master" icon="◉" value={master} setValue={onMasterChange} />
        <Slider label="Instrumental" icon="◌" value={instrumentalVolume} setValue={onInstrumentalChange} />
        <Slider label="Guide vocals" icon="◍" value={vocalVolume} setValue={onVocalChange} />
      </div>
      {lyricsView && <LyricsSettings settings={lyricsView} onChange={onLyricsViewChange} onReset={onLyricsViewReset} />}
    </aside>
  );
}

export function PlayerView({
  master, instrumentalVolume, vocalVolume, onMasterChange, onInstrumentalChange, onVocalChange, onReset,
  lyricsView, onLyricsViewChange, onLyricsViewReset, currentCueIndex, lyrics, onSeek, status, isPlaying, onTogglePlayback,
  onJumpToCue, currentTime, duration, formatTime,
}) {
  return (
    <>
      <section className="workspace player-workspace">
        <Mixer master={master} instrumentalVolume={instrumentalVolume} vocalVolume={vocalVolume} onMasterChange={onMasterChange} onInstrumentalChange={onInstrumentalChange} onVocalChange={onVocalChange} onReset={onReset} lyricsView={lyricsView} onLyricsViewChange={onLyricsViewChange} onLyricsViewReset={onLyricsViewReset} />
        <section className="stage"><div className="stage-glow glow-one" /><div className="stage-glow glow-two" /><span className="stage-label">Live lyric view</span><LyricsDisplay lyrics={lyrics} currentCueIndex={currentCueIndex} settings={lyricsView} onSeek={onSeek} /><div className="cue-pill"><span className="pulse" /> Cue {currentCueIndex >= 0 ? currentCueIndex + 1 : 0} of {lyrics.length}</div></section>
        <aside className="panel cue-panel"><div className="panel-heading"><div><span className="eyebrow">Navigator</span><h2>Lyric cues</h2></div><span className="cue-count">{lyrics.length}</span></div><div className="cue-list">{lyrics.map((cue, index) => <button type="button" key={`${cue.id}-${index}`} onClick={() => onSeek(cue.start)} className={`cue-row ${index === currentCueIndex ? 'current' : ''} ${index < currentCueIndex ? 'past' : ''}`}><span>{formatTime(cue.start)}</span><strong>{cue.text}</strong></button>)}</div></aside>
      </section>
      <footer className="transport"><div className="transport-info"><span className="status-light" /><span>{status}</span></div><div className="transport-controls"><button type="button" className="transport-button" onClick={() => onJumpToCue(-1)} aria-label="Previous lyric cue">|◀</button><button type="button" className="play-button" onClick={onTogglePlayback} aria-label={isPlaying ? 'Pause' : 'Play'}>{isPlaying ? 'Ⅱ' : '▶'}</button><button type="button" className="transport-button" onClick={() => onJumpToCue(1)} aria-label="Next lyric cue">▶|</button></div><div className="progress-wrap"><span>{formatTime(currentTime)}</span><input aria-label="Track progress" type="range" min="0" max={duration || 1} step="0.01" value={Math.min(currentTime, duration || 0)} onChange={(event) => onSeek(Number(event.target.value))} /><span>{formatTime(duration)}</span></div></footer>
    </>
  );
}

function Slider({ label, icon, value, setValue }) {
  return <label className="level-row"><span className="level-label"><i>{icon}</i>{label}</span><input type="range" min="0" max="100" value={value} onChange={(event) => setValue(Number(event.target.value))} /><output>{value}%</output></label>;
}
