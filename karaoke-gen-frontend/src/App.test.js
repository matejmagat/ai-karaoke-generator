import { render, screen } from '@testing-library/react';
import App from './App';
import { parseSrt } from './KaraokeApp';

beforeEach(() => localStorage.clear());

test('shows authentication before the generator', () => {
  render(<App />);
  expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  expect(screen.getByText(/sign in to generate/i)).toBeInTheDocument();
});

test('parses generated SRT cues for the existing player', () => {
  const cues = parseSrt('1\n00:00:01,250 --> 00:00:02,500\nHello world\n\n2\n00:00:03.000 --> 00:00:04.100\nNext line');
  expect(cues).toEqual([
    { id: 1, start: 1.25, end: 2.5, text: 'Hello world' },
    { id: 2, start: 3, end: 4.1, text: 'Next line' },
  ]);
});
