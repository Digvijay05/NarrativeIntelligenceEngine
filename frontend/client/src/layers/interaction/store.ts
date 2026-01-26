import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

/**
 * Temporal Control State
 * Purely interaction state, no derived geometry.
 */
interface TemporalState {
    // Current playback time
    currentTime: Date;

    // Playback control
    isPlaying: boolean;
    playbackSpeed: number; // 1.0 = realtime

    // Viewport (Zoom/Pan)
    viewStart: Date;
    viewEnd: Date;

    // Scrubbing logic
    isScrubbing: boolean;

    // Actions
    setTime: (time: Date) => void;
    setPlaying: (isPlaying: boolean) => void;
    togglePlay: () => void;
    setSpeed: (speed: number) => void;
    setViewRange: (start: Date, end: Date) => void;
    startScrubbing: () => void;
    stopScrubbing: () => void;
}

const DEFAULT_VIEW_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours

export const useTimeStore = create<TemporalState>()(
    devtools(
        (set) => ({
            currentTime: new Date(),
            isPlaying: false,
            playbackSpeed: 1.0,

            viewStart: new Date(Date.now() - DEFAULT_VIEW_DURATION_MS),
            viewEnd: new Date(),

            isScrubbing: false,

            setTime: (time) => set({ currentTime: time }),

            setPlaying: (isPlaying) => set({ isPlaying }),

            togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),

            setSpeed: (speed) => set({ playbackSpeed: speed }),

            setViewRange: (start, end) => set({ viewStart: start, viewEnd: end }),

            startScrubbing: () => set({ isScrubbing: true, isPlaying: false }),

            stopScrubbing: () => set({ isScrubbing: false }),
        }),
        { name: 'TemporalControl' }
    )
);
