/**
 * Replay Player Component (T16-010).
 *
 * Implements:
 * - Play/Pause button
 * - Speed controls (1x, 5x, 20x) with immediate effect
 * - Scrubber slider and previous/next sample stepping
 * - ArrowLeft and ArrowRight keyboard navigation
 * - Responsive layout without text truncation
 */

import React, { useEffect } from 'react';
import { useData } from '../data/useData';
import { useReplay, ReplaySpeed } from '../data/ReplayContext';

export const ReplayPlayer: React.FC = () => {
  const { samples } = useData();
  const {
    currentIndex,
    isPlaying,
    speed,
    currentSample,
    setCurrentIndex,
    togglePlay,
    setSpeed,
    stepForward,
    stepBackward,
  } = useReplay();

  const total = samples.length;
  const currentTs = currentSample?.timestamp ? String(currentSample.timestamp) : null;

  // Keyboard navigation: ArrowLeft, ArrowRight, and Space
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = (document.activeElement?.tagName || '').toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') {
        return;
      }

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        stepBackward();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        stepForward();
      } else if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        togglePlay();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [stepBackward, stepForward, togglePlay]);

  if (total === 0) {
    return null;
  }

  const speeds: ReplaySpeed[] = [1, 5, 20];

  return (
    <section
      aria-label="Replay player"
      data-testid="replay-player"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        padding: '12px 16px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
      }}
    >
      {/* Top Row: Play/Pause, Steppers, Scrubber, and Speed toggles */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap',
        }}
      >
        {/* Play/Pause Button */}
        <button
          onClick={togglePlay}
          aria-label={isPlaying ? 'Pause replay' : 'Play replay'}
          style={{
            padding: '6px 14px',
            borderRadius: '6px',
            border: '1px solid var(--color-border)',
            background: isPlaying ? 'var(--color-primary)' : 'var(--color-surface)',
            color: isPlaying ? '#ffffff' : 'var(--color-text)',
            fontWeight: 600,
            cursor: 'pointer',
            fontSize: '13px',
          }}
        >
          {isPlaying ? '⏸ Pause' : '▶ Play'}
        </button>

        {/* Stepper Buttons */}
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            onClick={stepBackward}
            disabled={currentIndex <= 0}
            aria-label="Previous sample"
            style={{
              padding: '6px 10px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              cursor: currentIndex <= 0 ? 'not-allowed' : 'pointer',
              opacity: currentIndex <= 0 ? 0.5 : 1,
              fontSize: '12px',
            }}
          >
            ⏮ Prev
          </button>
          <button
            onClick={stepForward}
            disabled={currentIndex >= total - 1}
            aria-label="Next sample"
            style={{
              padding: '6px 10px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
              color: 'var(--color-text)',
              cursor: currentIndex >= total - 1 ? 'not-allowed' : 'pointer',
              opacity: currentIndex >= total - 1 ? 0.5 : 1,
              fontSize: '12px',
            }}
          >
            Next ⏭
          </button>
        </div>

        {/* Scrubber Range Input */}
        <div style={{ flex: 1, minWidth: '160px', display: 'flex', alignItems: 'center' }}>
          <input
            type="range"
            min={0}
            max={Math.max(0, total - 1)}
            value={currentIndex}
            onChange={e => setCurrentIndex(Number(e.target.value))}
            aria-label="Replay scrubber"
            style={{ width: '100%', cursor: 'pointer' }}
          />
        </div>

        {/* Speed Controls */}
        <div
          role="group"
          aria-label="Playback speed"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
        >
          <span
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--color-text-muted)',
              marginRight: '2px',
            }}
          >
            Speed:
          </span>
          {speeds.map(s => {
            const isActive = speed === s;
            return (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                aria-pressed={isActive}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: isActive
                    ? '1px solid var(--color-primary)'
                    : '1px solid var(--color-border)',
                  background: isActive ? 'var(--color-primary)' : 'var(--color-bg)',
                  color: isActive ? '#ffffff' : 'var(--color-text)',
                  fontSize: '12px',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                }}
              >
                {s}×
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Info Row: Position & Local Timestamp */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: 'var(--color-text-muted)',
        }}
      >
        <div>
          Sample <strong>{currentIndex + 1}</strong> of <strong>{total}</strong>
        </div>
        {currentTs && (
          <div>
            Timestamp: <code>{currentTs}</code> (device local time)
          </div>
        )}
      </div>
    </section>
  );
};
