/**
 * Replay Context & State Management (T16-010).
 *
 * Provides synchronized replay playback controls, speed, scrubber state,
 * and current/previous sample tracking that persists across page navigations.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from 'react';
import { useData } from './useData';

export type ReplaySpeed = 1 | 5 | 20;

export interface ReplayContextValue {
  currentIndex: number;
  isPlaying: boolean;
  speed: ReplaySpeed;
  currentSample: Record<string, unknown> | null;
  prevSample: Record<string, unknown> | null;
  setCurrentIndex: (index: number | ((prev: number) => number)) => void;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  setSpeed: (speed: ReplaySpeed) => void;
  stepForward: () => void;
  stepBackward: () => void;
}

const ReplayContext = createContext<ReplayContextValue | undefined>(undefined);

export interface ReplayProviderProps {
  children: React.ReactNode;
  initialSpeed?: ReplaySpeed;
  autoPlay?: boolean;
}

export const ReplayProvider: React.FC<ReplayProviderProps> = ({
  children,
  initialSpeed = 1,
  autoPlay = false,
}) => {
  const { samples } = useData();

  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(autoPlay);
  const [speed, setSpeed] = useState<ReplaySpeed>(initialSpeed);

  // Reset index and playback when the active sample set changes
  useEffect(() => {
    setCurrentIndex(0);
    setIsPlaying(false);
  }, [samples]);

  const play = useCallback(() => {
    if (samples.length > 0) {
      if (currentIndex >= samples.length - 1) {
        // If at the end, wrap to beginning on play
        setCurrentIndex(0);
      }
      setIsPlaying(true);
    }
  }, [samples.length, currentIndex]);

  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }, [isPlaying, pause, play]);

  const stepForward = useCallback(() => {
    setCurrentIndex(prev => {
      if (prev + 1 < samples.length) {
        return prev + 1;
      }
      return prev;
    });
  }, [samples.length]);

  const stepBackward = useCallback(() => {
    setCurrentIndex(prev => {
      if (prev > 0) {
        return prev - 1;
      }
      return 0;
    });
  }, []);

  // Interval playback timer: 1000ms / speed. Re-runs immediately when speed changes.
  useEffect(() => {
    if (!isPlaying || samples.length <= 1) return;

    const intervalMs = Math.round(1000 / speed);
    const timerId = setInterval(() => {
      setCurrentIndex(prev => {
        if (prev + 1 >= samples.length) {
          setIsPlaying(false);
          return Math.max(0, samples.length - 1);
        }
        return prev + 1;
      });
    }, intervalMs);

    return () => clearInterval(timerId);
  }, [isPlaying, speed, samples.length]);

  const currentSample = useMemo(() => {
    if (samples.length === 0 || currentIndex >= samples.length) return null;
    return samples[currentIndex];
  }, [samples, currentIndex]);

  const prevSample = useMemo(() => {
    if (currentIndex <= 0 || currentIndex > samples.length) return null;
    return samples[currentIndex - 1];
  }, [samples, currentIndex]);

  const value: ReplayContextValue = {
    currentIndex,
    isPlaying,
    speed,
    currentSample,
    prevSample,
    setCurrentIndex,
    play,
    pause,
    togglePlay,
    setSpeed,
    stepForward,
    stepBackward,
  };

  return <ReplayContext.Provider value={value}>{children}</ReplayContext.Provider>;
};

export function useReplay(): ReplayContextValue {
  const context = useContext(ReplayContext);
  if (!context) {
    throw new Error('useReplay must be used within a ReplayProvider');
  }
  return context;
}
