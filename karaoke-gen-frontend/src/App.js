import { useState } from 'react';
import KaraokeApp from './KaraokeApp';
import AuthScreen from './AuthScreen';
import { clearSession, loadSession } from './api';
import './App.css';

function App() {
  const [session, setSession] = useState(loadSession);

  if (!session) return <AuthScreen onAuthenticated={setSession} />;

  const logout = () => {
    clearSession();
    setSession(null);
  };

  return (
    <div className="App session-shell">
      <div className="session-user">
        <span>{session.username || 'Signed in'}</span>
        <button onClick={logout}>Log out</button>
      </div>
      <KaraokeApp />
    </div>
  );
}

export default App;
