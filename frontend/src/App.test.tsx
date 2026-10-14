import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { HashRouter } from 'react-router-dom';
import App from './App';
import { PAGES } from './constants/pages';

describe('App Shell & Navigation (T16-006 / T16-007)', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('renders unified brand header with mode label and no deploy chrome', () => {
    render(
      <HashRouter>
        <App />
      </HashRouter>
    );
    expect(screen.getByText('5G-NADS')).toBeInTheDocument();
    expect(screen.getByText('Static Demo (Mode 1)')).toBeInTheDocument();
    expect(screen.queryByText(/deploy/i)).not.toBeInTheDocument();
  });

  it('renders all page navigation links', () => {
    render(
      <HashRouter>
        <App />
      </HashRouter>
    );
    const nav = screen.getByRole('navigation', { name: /primary navigation/i });
    PAGES.forEach(page => {
      expect(within(nav).getByText(page.label)).toBeInTheDocument();
    });
  });

  it('renders research prototype notice in footer per G31', () => {
    render(
      <HashRouter>
        <App />
      </HashRouter>
    );
    expect(screen.getByText(/Academic research prototype/i)).toBeInTheDocument();
    expect(screen.getByText(/App: v2.1.0/i)).toBeInTheDocument();
  });

  it('toggles and persists theme in localStorage', () => {
    render(
      <HashRouter>
        <App />
      </HashRouter>
    );
    const themeBtn = screen.getByLabelText(/Toggle light and dark theme/i);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    fireEvent.click(themeBtn);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('nads_theme')).toBe('dark');

    fireEvent.click(themeBtn);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('nads_theme')).toBe('light');
  });
});
