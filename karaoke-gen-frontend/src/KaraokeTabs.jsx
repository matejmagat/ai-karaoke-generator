import React from 'react';
import './KaraokeTabs.css';

export default function KaraokeTabs({ activeTab, onSelect }) {
  return (
    <nav className="app-tabs" role="tablist" aria-label="Karaoke sections">
      <button
        id="player-tab"
        type="button"
        role="tab"
        aria-selected={activeTab === 'player'}
        aria-controls="player-panel"
        tabIndex={activeTab === 'player' ? 0 : -1}
        onClick={() => onSelect('player')}
      >
        Player
      </button>
      <button
        id="library-tab"
        type="button"
        role="tab"
        aria-selected={activeTab === 'library'}
        aria-controls="library-panel"
        tabIndex={activeTab === 'library' ? 0 : -1}
        onClick={() => onSelect('library')}
      >
        Library
      </button>
    </nav>
  );
}
