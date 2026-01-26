/**
 * Forensic Data Contracts
 * =======================
 * READ-ONLY interfaces mirroring backend truth.
 * NO computed fields. NO optional fields (unless backend allows).
 */

export interface EvidenceFragmentDTO {
    fragment_id: string;
    source_id: string;
    // ISO Strings from backend
    event_time: string;
    ingest_time: string;
    content: {
        title: string;
        // We do NOT store full text here if not needed for visualization bandwidth
        description_hash: string;
    };
}

export interface NarrativeThreadDTO {
    thread_id: string;
    fragments: EvidenceFragmentDTO[];
    state: "emergent" | "active" | "dormant" | "diverged" | "vanished";
    divergence_reason?: string;
    start_time: string;
    end_time: string;
}

export interface GraphSnapshotDTO {
    timestamp: string;
    threads: NarrativeThreadDTO[];
}
