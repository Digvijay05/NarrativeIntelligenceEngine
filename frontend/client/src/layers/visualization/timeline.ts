/**
 * Visualization Layer: Timeline Layout
 * 
 * Responsibility:
 * Deterministically transform Narrative State (DTOs) into Renderable Geometry.
 * 
 * Input: NarrativeVersionDTO, Viewport Config
 * Output: RenderableTimeline
 * 
 * CONSTRAINT: Referential Transparency.
 * Same Input -> Same Output.
 */

import {
    NarrativeVersionDTO,
    TimelineSegmentDTO,
    SegmentKind,
    ThreadState
} from '@/layers/state/contracts';
import { ScaleTime, scaleTime } from 'd3-scale';

export interface RenderableSegment {
    uniqueId: string;
    x: number;      // Pixel offset
    width: number;  // Pixel width
    color: string;  // CSS variable var(--state-...)
    label: string;
    opacity: number;
    isInteractive: boolean;
    kind: SegmentKind;
}

export interface RenderableTrack {
    threadId: string;
    label: string;
    y: number;
    height: number;
    segments: RenderableSegment[];
}

export interface RenderableTimeline {
    tracks: RenderableTrack[];
    timeScale: ScaleTime<number, number>;
    viewportStart: Date;
    viewportEnd: Date;
    generatedAt: Date;
}

export interface LayoutConfig {
    width: number;
    trackHeight: number;
    trackGap: number;
    viewStart: Date;
    viewEnd: Date;
}

export class TimelineLayout {

    static calculate(
        version: NarrativeVersionDTO,
        config: LayoutConfig
    ): RenderableTimeline {

        // 1. Create Time Scale
        const timeScale = scaleTime()
            .domain([config.viewStart, config.viewEnd])
            .range([0, config.width]);

        // 2. Map Threads to Tracks
        const tracks: RenderableTrack[] = version.threads.map((thread, index) => {
            const y = index * (config.trackHeight + config.trackGap);

            const renderableSegments = thread.segments.map(seg =>
                this.mapSegment(seg, timeScale)
            );

            // Filter out segments outside viewport if optimization needed (not done here for transparency)

            return {
                threadId: thread.thread_id,
                label: thread.thread_id, // Could use display name if added to contract
                y,
                height: config.trackHeight,
                segments: renderableSegments
            };
        });

        return {
            tracks,
            timeScale,
            viewportStart: config.viewStart,
            viewportEnd: config.viewEnd,
            generatedAt: new Date(version.generated_at)
        };
    }

    private static mapSegment(
        segment: TimelineSegmentDTO,
        scale: ScaleTime<number, number>
    ): RenderableSegment {

        const start = new Date(segment.start_time);
        const end = new Date(segment.end_time);

        const x = scale(start);
        const w = Math.max(2, scale(end) - x);

        // Determine Color Token (Strict Mapping - Forensic Palette Hex)
        // SVG fill attributes don't resolve CSS variables, so we use hex directly
        const COLORS = {
            active: '#4C9AFF',
            dormant: '#8A94A6',
            terminated: '#5A647A',
            divergent: '#C77D3A',
            absence: '#2F3748',
        };

        let color = COLORS.active;
        let opacity = 1.0;

        // R2: Explicit Silence
        if (segment.kind === SegmentKind.ABSENCE) {
            color = COLORS.absence;
            opacity = 0.5;
        } else {
            // Map ThreadState to Visuals
            switch (segment.state) {
                case ThreadState.DORMANT:
                    color = COLORS.dormant;
                    break;
                case ThreadState.TERMINATED:
                    color = COLORS.terminated;
                    break;
                case ThreadState.DIVERGENT:
                    color = COLORS.divergent;
                    break;
                default:
                    color = COLORS.active;
            }
        }

        return {
            uniqueId: segment.segment_id,
            x,
            width: w,
            color,
            label: segment.kind === SegmentKind.ABSENCE ? 'ABSENCE' : `Seg ${segment.segment_id}`,
            opacity,
            isInteractive: segment.kind === SegmentKind.PRESENCE,
            kind: segment.kind
        };
    }
}
