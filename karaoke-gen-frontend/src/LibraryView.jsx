import React from 'react';

function hasPlayableMedia(song) {
  return song.processing_status === 'ready' && song.instrumental_file && song.vocals_file && song.lyrics_srt_file;
}

function LibrarySongCard({ song, onLoad }) {
  const playable = hasPlayableMedia(song);
  return (
    <article className="library-song-card">
      <div className="song-card-copy">
        <div className="song-card-title-row">
          <h3>{song.title}</h3>
          {song.processing_status !== 'ready' && <span className={`status-badge ${song.processing_status}`}>{song.processing_status}</span>}
        </div>
        <p>{song.artist}</p>
        {Number.isFinite(song.duration_seconds) && <small>{Math.floor(song.duration_seconds / 60)}:{Math.floor(song.duration_seconds % 60).toString().padStart(2, '0')}</small>}
      </div>
      <div className="song-card-actions">
        <button type="button" className="primary-small" disabled={!playable} title={playable ? 'Load this song into the player' : 'This song is not ready or is missing media'} onClick={() => onLoad(song)}>Load</button>
      </div>
    </article>
  );
}

export default function LibraryView({ libraries, loading, error, onRetry, onLoad }) {
  const songCount = libraries.reduce((total, library) => total + (library.song_entries?.length || 0), 0);

  if (loading && !libraries.length) return <div className="library-state" role="status">Loading library…</div>;
  if (error && !libraries.length) return <div className="library-state error-state" role="alert"><p>{error}</p><button type="button" onClick={onRetry}>Retry</button></div>;
  if (!songCount) return <div className="library-state"><span className="eyebrow">Library</span><h1>Your library is empty</h1><p>Generate your first karaoke track with the form.</p>{error && <p className="inline-error" role="alert">{error}</p>}<button type="button" className="text-button" onClick={onRetry}>Refresh</button></div>;

  return (
    <section className="library-content" aria-label="Song libraries">
      <div className="library-content-heading"><div><span className="eyebrow">Library</span><h1>Your karaoke songs</h1></div><button type="button" className="text-button" disabled={loading} onClick={onRetry}>{loading ? 'Refreshing…' : 'Refresh'}</button></div>
      {error && <div className="library-inline-error" role="alert">{error}</div>}
      {libraries.map((library) => (
        <section key={library.id} className="library-group">
          <header><div><h2>{library.name}</h2>{library.description && <p>{library.description}</p>}</div><span>{library.song_count ?? library.song_entries?.length ?? 0} songs</span></header>
          {library.song_entries?.length ? <div className="library-items">{library.song_entries.map(({ id: entryId, song }) => <LibrarySongCard key={entryId} song={song} onLoad={onLoad} />)}</div> : <p className="library-group-empty">No standalone songs in this library.</p>}
        </section>
      ))}
    </section>
  );
}
