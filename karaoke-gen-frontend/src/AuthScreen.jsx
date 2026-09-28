import { useState } from 'react';
import { login, register } from './api';

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [fields, setFields] = useState({
    username: '', email: '', password: '', password_confirm: '',
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const update = (event) => {
    setFields((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const session = mode === 'login'
        ? await login({ username: fields.username, password: fields.password })
        : await register(fields);
      onAuthenticated(session);
    } catch (requestError) {
      const firstFieldError = Object.values(requestError.body || {}).flat()[0];
      setError(typeof firstFieldError === 'string' ? firstFieldError : requestError.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand"><span>♫</span> Karaoke<strong>Gen</strong></div>
        <p>{mode === 'login' ? 'Sign in to generate your next karaoke track.' : 'Create an account to start generating tracks.'}</p>
        <label>Username<input name="username" value={fields.username} onChange={update} autoComplete="username" required /></label>
        {mode === 'register' && <label>Email<input name="email" type="email" value={fields.email} onChange={update} autoComplete="email" required /></label>}
        <label>Password<input name="password" type="password" value={fields.password} onChange={update} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 8 : undefined} required /></label>
        {mode === 'register' && <label>Confirm password<input name="password_confirm" type="password" value={fields.password_confirm} onChange={update} autoComplete="new-password" minLength="8" required /></label>}
        {error && <div className="auth-error" role="alert">{error}</div>}
        <button className="auth-submit" disabled={submitting}>{submitting ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Register'}</button>
        <button type="button" className="auth-switch" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>
          {mode === 'login' ? 'Need an account? Register' : 'Already registered? Sign in'}
        </button>
      </form>
    </main>
  );
}
