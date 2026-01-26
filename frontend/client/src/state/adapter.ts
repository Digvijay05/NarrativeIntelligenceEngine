/**
 * State Adapter
 * ==============
 * Connects frontend state to backend API.
 * 
 * CONSTRAINT: This is the ONLY module that makes HTTP calls.
 * All data flows through here. No mocks in production.
 */

import { GraphSnapshotDTO, NarrativeThreadDTO, EvidenceFragmentDTO } from './contracts';

const API_BASE = '/api/v1';

// =============================================================================
// TYPE DEFINITIONS (Backend Response Shape)
// =============================================================================

interface BackendThreadDTO {
    thread_id: string;
    segments: {
        segment_id: string;
        thread_id: string;
        kind: 'presence' | 'absence';
        start_time: string;
        end_time: string;
        state: string;
        fragment_ids: string[];
    }[];
}

interface BackendSnapshotResponse {
    version_id: string;
    generated_at: string;
    timestamp?: string;
    sequence?: number;
    threads: BackendThreadDTO[];
}

// =============================================================================
// ADAPTER FUNCTIONS
// =============================================================================

/**
 * Transform backend response to frontend DTO.
 * This is a pure function (no side effects).
 */
function transformToFrontendDTO(backend: BackendSnapshotResponse): GraphSnapshotDTO {
    const threads: NarrativeThreadDTO[] = backend.threads.map(bt => {
        // Extract fragments from all presence segments
        const fragments: EvidenceFragmentDTO[] = [];
        let startTime = '';
        let endTime = '';

        for (const seg of bt.segments) {
            if (seg.kind === 'presence') {
                if (!startTime || seg.start_time < startTime) startTime = seg.start_time;
                if (!endTime || seg.end_time > endTime) endTime = seg.end_time;

                // Create minimal fragment DTOs
                for (const fid of seg.fragment_ids) {
                    fragments.push({
                        fragment_id: fid,
                        source_id: 'unknown', // Backend should provide this
                        event_time: seg.start_time,
                        ingest_time: seg.end_time,
                        content: {
                            title: '', // Not available in segment
                            description_hash: ''
                        }
                    });
                }
            }
        }

        // Determine lifecycle state
        const hasAbsence = bt.segments.some(s => s.kind === 'absence');
        let state: 'emergent' | 'active' | 'dormant' | 'diverged' | 'vanished' = 'active';
        if (hasAbsence) {
            state = 'dormant';
        }
        const lastSeg = bt.segments[bt.segments.length - 1];
        if (lastSeg?.state === 'diverged') {
            state = 'diverged';
        }

        return {
            thread_id: bt.thread_id,
            fragments: fragments,
            state: state,
            start_time: startTime || new Date().toISOString(),
            end_time: endTime || new Date().toISOString(),
        };
    });

    return {
        timestamp: backend.timestamp || backend.generated_at,
        threads: threads
    };
}

/**
 * Fetch latest state from backend.
 */
export async function fetchLatestSnapshot(): Promise<GraphSnapshotDTO> {
    const response = await fetch(`${API_BASE}/state/latest`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch state: ${response.status}`);
    }

    const data: BackendSnapshotResponse = await response.json();
    return transformToFrontendDTO(data);
}

/**
 * Fetch snapshot at a specific timestamp.
 */
export async function fetchSnapshotAt(timestamp: string): Promise<GraphSnapshotDTO> {
    const encoded = encodeURIComponent(timestamp);
    const response = await fetch(`${API_BASE}/snapshot/${encoded}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch snapshot: ${response.status}`);
    }

    const data: BackendSnapshotResponse = await response.json();
    return transformToFrontendDTO(data);
}

/**
 * Subscribe to live state updates via SSE.
 * Returns a function to unsubscribe.
 */
export function subscribeToStream(
    onUpdate: (snapshot: GraphSnapshotDTO) => void,
    onError?: (error: Error) => void
): () => void {
    const eventSource = new EventSource(`${API_BASE}/stream`);

    eventSource.onmessage = (event) => {
        try {
            const data: BackendSnapshotResponse = JSON.parse(event.data);
            const snapshot = transformToFrontendDTO(data);
            onUpdate(snapshot);
        } catch (e) {
            onError?.(e instanceof Error ? e : new Error(String(e)));
        }
    };

    eventSource.onerror = () => {
        onError?.(new Error('SSE connection lost'));
    };

    // Return unsubscribe function
    return () => {
        eventSource.close();
    };
}
