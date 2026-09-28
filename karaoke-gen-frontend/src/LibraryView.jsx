import React, { useState } from 'react';

function hasPlayableMedia(song) {
  return song.processing_status === 'ready' && song.instrumental_file && song.vocals_file && song.lyrics_srt_file;
}

function LibrarySongCard({ song, onLoad, onEdit, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState('');
  const [draft, setDraft] = useState({ title: song.title || '', artist: song.artist || '', duration_seconds: song.duration_seconds ?? '', is_public: Boolean(song.is_public) });
  const playable = hasPlayableMedia(song);

  const beginEditing = () => {
    setDraft({ title: song.title || '', artist: song.artist || '', duration_seconds: song.duration_seconds ?? '', is_public: Boolean(song.is_public) });
    setActionError('');
    setEditing(true);
  };

  const save = async (event) => {
    event.preventDefault();
    const changes = {};
    const nextTitle = draft.title.trim();
    const nextArtist = draft.artist.trim();
    const nextDuration = draft.duration_seconds === '' ? null : Number(draft.duration_seconds);
    if (!nextTitle || !nextArtist) { setActionError('Title and artist are required.'); return; }
    if (nextTitle !== song.title) changes.title = nextTitle;
    if (nextArtist !== song.artist) changes.artist = nextArtist;
    if (nextDuration !== (song.duration_seconds ?? null)) changes.duration_seconds = nextDuration;
    if (draft.is_public !== Boolean(song.is_public)) changes.is_public = draft.is_public;
    if (!Object.keys(changes).length) { setEditing(false); return; }
    setSaving(true); setActionError('');
    try { await onEdit(song, changes); setEditing(false); }
    catch (error) { setActionError(error.message || 'Could not update this song.'); }
    finally { setSaving(false); }
  };

  const remove = async () => {
    setActionError('');
    try { await onDelete(song); }
    catch (error) { setActionError(error.message || 'Could not delete this song.'); }
  };

  if (editing) {
    return (
      <article className="library-song-card editing-card">
        <form className="song-edit-form" onSubmit={save}>
          <label>Title<input aria-label={`Title for ${song.title}`} value={draft.title} disabled={saving} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>Artist<input aria-label={`Artist for ${song.title}`} value={draft.artist} disabled={saving} onChange={(event) => setDraft({ ...draft, artist: event.target.value })} /></label>
          <label>Duration (seconds)<input aria-label={`Duration for ${song.title}`} type="number" min="0" step="0.01" value={draft.duration_seconds} disabled={saving} onChange={(event) => setDraft({ ...draft, duration_seconds: event.target.value })} /></label>
          <label className="public-toggle"><input aria-label={`Public ${song.title}`} type="checkbox" checked={draft.is_public} disabled={saving} onChange={(event) => setDraft({ ...draft, is_public: event.target.checked })} /> Public song</label>
          {actionError && <p className="card-error" role="alert">{actionError}</p>}
          <div className="song-card-actions"><button type="submit" className="primary-small" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button><button type="button" disabled={saving} onClick={() => setEditing(false)}>Cancel</button></div>
        </form>
      </article>
    );
  }

  return (
    <article className="library-song-card">
      <div className="song-card-copy">
        <div className="song-card-title-row"><h3>{song.title}</h3>{song.processing_status !== 'ready' && <span className={`status-badge ${song.processing_status}`}>{song.processing_status}</span>}</div>
        <p>{song.artist}</p>
        {Number.isFinite(song.duration_seconds) && <small>{Math.floor(song.duration_seconds / 60)}:{Math.floor(song.duration_seconds % 60).toString().padStart(2, '0')}</small>}
        {actionError && <p className="card-error" role="alert">{actionError}</p>}
      </div>
      <div className="song-card-actions">
        <button type="button" className="primary-small" disabled={!playable} title={playable ? 'Load this song into the player' : 'This song is not ready or is missing media'} onClick={() => onLoad(song)}>Load</button>
        <button type="button" onClick={beginEditing}>Edit</button>
        <button type="button" className="danger-button" onClick={remove}>Delete song</button>
      </div>
    </article>
  );
}

export default function LibraryView({ libraries, loading, error, onRetry, onLoad, onEdit, onDelete }) {
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
          {library.song_entries?.length ? <div className="library-items">{library.song_entries.map(({ id: entryId, song }) => <LibrarySongCard key={entryId} song={song} onLoad={onLoad} onEdit={onEdit} onDelete={onDelete} />)}</div> : <p className="library-group-empty">No standalone songs in this library.</p>}
        </section>
      ))}
    </section>
  );
}
