import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom';
import { DataProvider } from '../data/DataContext';
import { ReplayProvider, useReplay } from '../data/ReplayContext';
import { ReplayPlayer } from './ReplayPlayer';
import { DemoBundle } from '../types/contracts';

const mockBundle: DemoBundle = {
  bundle_version: 1,
  generated_at: '2024-05-01T12:00:00Z',
  model_version: '1.0.0',
  source: 'sample',
  privacy: {
    cell_ids: 'hashed',
    time: 'device-local, no timezone',
    salt_hash: 'a1b2c3d4e5f60718',
    cell_lookup: {},
  },
  quality: { clean_rows: 5, dropped: 0, total_raw: 5 },
  model_meta: { contamination: 0.05, model_name: 'if_v1' },
  sessions: [
    {
      session_id: 'sess-1',
      device: 'Pixel 7',
      operator: 'Jio',
      start: '2024-05-01 10:00:00',
      end: '2024-05-01 10:00:05',
      n: 5,
    },
  ],
  samples: {
    columns: ['timestamp', 'session_id', 'ss_rsrp'],
    rows: [
      ['2024-05-01 10:00:00', 'sess-1', -85],
      ['2024-05-01 10:00:01', 'sess-1', -86],
      ['2024-05-01 10:00:02', 'sess-1', -87],
      ['2024-05-01 10:00:03', 'sess-1', -88],
      ['2024-05-01 10:00:04', 'sess-1', -89],
    ],
  },
  events: [],
  transitions: [],
};

function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <DataProvider initialBundle={mockBundle}>
      <ReplayProvider>{children}</ReplayProvider>
    </DataProvider>
  );
}

describe('Replay Player Component & Controls (T16-010)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders initial player state, position, and sample count', () => {
    render(
      <TestWrapper>
        <ReplayPlayer />
      </TestWrapper>
    );

    expect(screen.getByTestId('replay-player')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /play replay/i })).toBeInTheDocument();
    expect(screen.getByText(/Sample/i)).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2024-05-01 10:00:00')).toBeInTheDocument();
  });

  it('steps forward and backward using Next and Prev stepper buttons', () => {
    render(
      <TestWrapper>
        <ReplayPlayer />
      </TestWrapper>
    );

    const prevBtn = screen.getByRole('button', { name: /previous sample/i });
    const nextBtn = screen.getByRole('button', { name: /next sample/i });

    // Initially at sample 0, prev should be disabled
    expect(prevBtn).toBeDisabled();
    expect(nextBtn).toBeEnabled();

    // Step forward to sample index 1
    fireEvent.click(nextBtn);
    expect(screen.getByText('2024-05-01 10:00:01')).toBeInTheDocument();
    expect(prevBtn).toBeEnabled();

    // Step forward to index 2
    fireEvent.click(nextBtn);
    expect(screen.getByText('2024-05-01 10:00:02')).toBeInTheDocument();

    // Step backward to index 1
    fireEvent.click(prevBtn);
    expect(screen.getByText('2024-05-01 10:00:01')).toBeInTheDocument();
  });

  it('moves sample with the scrubber range input', () => {
    render(
      <TestWrapper>
        <ReplayPlayer />
      </TestWrapper>
    );

    const scrubber = screen.getByLabelText(/replay scrubber/i);
    expect(scrubber).toHaveValue('0');

    // Drag / change scrubber to sample index 3
    fireEvent.change(scrubber, { target: { value: '3' } });
    expect(scrubber).toHaveValue('3');
    expect(screen.getByText('2024-05-01 10:00:03')).toBeInTheDocument();
  });

  it('supports keyboard navigation: ArrowRight, ArrowLeft, and Space', () => {
    render(
      <TestWrapper>
        <ReplayPlayer />
      </TestWrapper>
    );

    // Press ArrowRight to move forward
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(screen.getByText('2024-05-01 10:00:01')).toBeInTheDocument();

    // Press ArrowLeft to move back
    fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(screen.getByText('2024-05-01 10:00:00')).toBeInTheDocument();

    // Press Space to toggle play
    fireEvent.keyDown(window, { key: ' ' });
    expect(screen.getByRole('button', { name: /pause replay/i })).toBeInTheDocument();

    // Press Space again to pause
    fireEvent.keyDown(window, { key: ' ' });
    expect(screen.getByRole('button', { name: /play replay/i })).toBeInTheDocument();
  });

  it('plays at 1x speed, advances samples, and pauses automatically at the end', () => {
    render(
      <TestWrapper>
        <ReplayPlayer />
      </TestWrapper>
    );

    const playBtn = screen.getByRole('button', { name: /play replay/i });
    fireEvent.click(playBtn);
    expect(screen.getByRole('button', { name: /pause replay/i })).toBeInTheDocument();

    // At 1x speed, interval is 1000ms. Advance 1000ms -> sample index 1
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText('2024-05-01 10:00:01')).toBeInTheDocument();

    // Advance 3 more seconds to reach the end (sample index 4)
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByText('2024-05-01 10:00:04')).toBeInTheDocument();

    // One more tick triggers automatic pause at the end
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByRole('button', { name: /play replay/i })).toBeInTheDocument();
  });

  it('changes speed immediately (1x -> 5x -> 20x)', () => {
    render(
      <TestWrapper>
        <ReplayPlayer />
      </TestWrapper>
    );

    const btn5x = screen.getByRole('button', { name: '5×' });
    const btn20x = screen.getByRole('button', { name: '20×' });

    // Start playback
    fireEvent.click(screen.getByRole('button', { name: /play replay/i }));

    // Switch speed to 5x (interval 200ms)
    fireEvent.click(btn5x);
    expect(btn5x).toHaveAttribute('aria-pressed', 'true');

    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.getByText('2024-05-01 10:00:01')).toBeInTheDocument();

    // Switch speed to 20x (interval 50ms)
    fireEvent.click(btn20x);
    expect(btn20x).toHaveAttribute('aria-pressed', 'true');

    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(screen.getByText('2024-05-01 10:00:02')).toBeInTheDocument();
  });

  it('persists replay state across page navigations', () => {
    function PageA() {
      const { currentIndex } = useReplay();
      return (
        <div>
          <span data-testid="page-a-index">{currentIndex}</span>
          <Link to="/page-b">Go to Page B</Link>
        </div>
      );
    }

    function PageB() {
      const { currentIndex } = useReplay();
      return (
        <div>
          <span data-testid="page-b-index">{currentIndex}</span>
          <Link to="/">Go to Page A</Link>
        </div>
      );
    }

    render(
      <MemoryRouter initialEntries={['/']}>
        <DataProvider initialBundle={mockBundle}>
          <ReplayProvider>
            <ReplayPlayer />
            <Routes>
              <Route path="/" element={<PageA />} />
              <Route path="/page-b" element={<PageB />} />
            </Routes>
          </ReplayProvider>
        </DataProvider>
      </MemoryRouter>
    );

    // Move to sample index 2
    const nextBtn = screen.getByRole('button', { name: /next sample/i });
    fireEvent.click(nextBtn);
    fireEvent.click(nextBtn);

    expect(screen.getByTestId('page-a-index')).toHaveTextContent('2');

    // Navigate to Page B
    fireEvent.click(screen.getByText('Go to Page B'));

    // Replay state survived navigation!
    expect(screen.getByTestId('page-b-index')).toHaveTextContent('2');
  });
});
