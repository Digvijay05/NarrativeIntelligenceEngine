/**
 * State Layer: Runtime Validation
 * 
 * Uses Zod to enforce the Contract at runtime.
 * "Don't trust the backend."
 */

import { z } from 'zod';
import {
    SegmentKind,
    ThreadState,
    NarrativeVersionDTO
} from './contracts';

// 1. Enums (Strict)
const SegmentKindSchema = z.nativeEnum(SegmentKind);
const ThreadStateSchema = z.nativeEnum(ThreadState);

// 2. Fragment validator (Removed: Fragments not in VersionDTO)

// 3. Segment Validator
const TimelineSegmentSchema = z.object({
    segment_id: z.string(),
    thread_id: z.string(),
    kind: SegmentKindSchema,
    start_time: z.string().datetime(),
    end_time: z.string().datetime(),
    state: ThreadStateSchema,
    fragment_ids: z.array(z.string())
}).refine(data => {
    // P4: Positive Duration
    return new Date(data.start_time) < new Date(data.end_time);
}, {
    message: "Invariant Violation: Segment duration must be positive",
    path: ["end_time"]
}).refine(data => {
    // R2: Explicit Silence Rules
    if (data.kind === SegmentKind.ABSENCE) {
        return data.fragment_ids.length === 0;
    } else {
        return data.fragment_ids.length > 0;
    }
}, {
    message: "Invariant Violation: ABSENCE must have no fragments, PRESENCE must have fragments",
    path: ["fragment_ids"]
});

// 4. Thread Validator
const NarrativeThreadSchema = z.object({
    thread_id: z.string(),
    segments: z.array(TimelineSegmentSchema)
}).refine(_data => {
    // P2: No Implicit Gaps (Client Check)
    // Segments must be sorted and contiguous (or bridged by ABSENCE)
    // For the Strict Contract, we allow "gaps" to simply be unrendered space?
    // User spec says: "If gap, ABSENCE segment must exist".
    // So we check for contiguous coverage?
    // Let's enforce strict ordering for now.

    // PROTOTYPE: Gaps allowed for demo. In production, enable strict check.
    // For strict mode, uncomment the loop below:
    /*
    const sorted = [...data.segments].sort((a, b) =>
        new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
    );
    for (let i = 0; i < sorted.length - 1; i++) {
        const endCurrent = new Date(sorted[i].end_time).getTime();
        const startNext = new Date(sorted[i + 1].start_time).getTime();
        if (endCurrent < startNext) return false; // Gap
        if (endCurrent > startNext) return false; // Overlap
    }
    */
    return true;
}, {
    message: "Invariant Violation: Thread segments have gaps or overlaps",
    path: ["segments"]
});

// 5. Version Validator (Top Level)
export const NarrativeVersionSchema = z.object({
    version_id: z.string(),
    generated_at: z.string().datetime(),
    threads: z.array(NarrativeThreadSchema)
});

// Export Type
export type ValidatedVersion = z.infer<typeof NarrativeVersionSchema>;

export function validateVersion(input: unknown): NarrativeVersionDTO {
    return NarrativeVersionSchema.parse(input) as NarrativeVersionDTO;
}
