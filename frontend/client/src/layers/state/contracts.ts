/**
 * State Access Layer Contracts
 * Mirrors backend/contracts/spec.py
 * 
 * AUTHORITATIVE MIRROR
 * ====================
 * This file defines the client-side contract for the Narrative Intelligence Engine.
 * It must strictly match the Python dataclasses.
 */

export enum SegmentKind {
    PRESENCE = "presence",
    ABSENCE = "absence"
}

export enum ThreadState {
    ACTIVE = "active",
    DORMANT = "dormant",
    TERMINATED = "terminated",
    DIVERGENT = "divergent"
}

export interface FragmentDTO {
    fragment_id: string;
    source_id: string;
    event_time: string;   // ISO-8601
    ingest_time: string;  // ISO-8601
    payload_ref: string;
}

export interface TimelineSegmentDTO {
    segment_id: string;
    thread_id: string;
    kind: SegmentKind;
    start_time: string;
    end_time: string;
    state: ThreadState;
    fragment_ids: string[];
}

export interface NarrativeThreadDTO {
    thread_id: string;
    segments: TimelineSegmentDTO[];
}

export interface NarrativeVersionDTO {
    version_id: string;
    generated_at: string;
    threads: NarrativeThreadDTO[];
}
