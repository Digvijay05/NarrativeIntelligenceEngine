/**
 * Forensic Narrative Store
 * =========================
 * Zustand store implementing the "Tape" model for time-travel.
 * 
 * ARCHITECTURE:
 * - `tape`: Array of GraphSnapshotDTO ordered by time.
 * - `cursor`: Current frame index.
 * - `activeFrame`: Computed getter.
 * 
 * CONSTRAINTS:
 * - Read-only with respect to narrative data.
 * - No mutations of DTO objects.
 * - Deterministic: same tape + cursor = same output.
 */

import { create } from 'zustand';
import { GraphSnapshotDTO, NarrativeThreadDTO } from './contracts';

interface ForensicState {
    // === TAPE (Immutable History) ===
    tape: GraphSnapshotDTO[];

    // === CURSOR (Current Position) ===
    cursor: number;

    // === PLAYBACK STATE ===
    isPlaying: boolean;
    playIntervalMs: number;

    // === CONNECTION STATE ===
    connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
    lastError: string | null;

    // === COMPUTED (derived, not stored) ===
    // Accessed via getters below

    // === ACTIONS ===
    appendSnapshot: (snapshot: GraphSnapshotDTO) => void;
    setTape: (tape: GraphSnapshotDTO[]) => void;
    scrub: (frame: number) => void;
    play: () => void;
    pause: () => void;
    stepForward: () => void;
    stepBackward: () => void;
    setConnectionStatus: (status: 'disconnected' | 'connecting' | 'connected' | 'error', error?: string) => void;
}

export const useForensicStore = create<ForensicState>((set) => ({
    // Initial State
    tape: [],
    cursor: 0,
    isPlaying: false,
    playIntervalMs: 1000,
    connectionStatus: 'disconnected',
    lastError: null,

    // === ACTIONS ===

    appendSnapshot: (snapshot) => set((state) => {
        // Append to tape (new frame)
        const newTape = [...state.tape, snapshot];
        return {
            tape: newTape,
            // Auto-advance cursor to latest if at end
            cursor: state.cursor === state.tape.length - 1 ? newTape.length - 1 : state.cursor
        };
    }),

    setTape: (tape) => set({ tape, cursor: tape.length > 0 ? tape.length - 1 : 0 }),

    scrub: (frame) => set((state) => ({
        cursor: Math.max(0, Math.min(frame, state.tape.length - 1))
    })),

    play: () => set({ isPlaying: true }),

    pause: () => set({ isPlaying: false }),

    stepForward: () => set((state) => ({
        cursor: Math.min(state.cursor + 1, state.tape.length - 1)
    })),

    stepBackward: () => set((state) => ({
        cursor: Math.max(state.cursor - 1, 0)
    })),

    setConnectionStatus: (status, error) => set({
        connectionStatus: status,
        lastError: error || null
    })
}));

// === SELECTORS (Pure Functions) ===

/**
 * Get the current active frame.
 * Returns null if tape is empty.
 */
export function selectActiveFrame(state: ForensicState): GraphSnapshotDTO | null {
    if (state.tape.length === 0) return null;
    const idx = Math.max(0, Math.min(state.cursor, state.tape.length - 1));
    return state.tape[idx] ?? null;
}

/**
 * Get threads from the active frame.
 */
export function selectActiveThreads(state: ForensicState): NarrativeThreadDTO[] {
    const frame = selectActiveFrame(state);
    return frame?.threads ?? [];
}

/**
 * Get time range of the tape.
 */
export function selectTapeTimeRange(state: ForensicState): { start: Date | null, end: Date | null } {
    if (state.tape.length === 0) {
        return { start: null, end: null };
    }
    const first = state.tape[0];
    const last = state.tape[state.tape.length - 1];
    return {
        start: new Date(first.timestamp),
        end: new Date(last.timestamp)
    };
}
