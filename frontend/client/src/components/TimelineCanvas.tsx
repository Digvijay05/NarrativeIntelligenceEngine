/**
 * Presentation Layer: Timeline Canvas
 * 
 * Responsibility:
 * Render the pre-calculated TimelineLayout.
 * PURE COMPONENT - logicless.
 */

import React, { useRef, useEffect } from 'react';
import { RenderableTimeline } from '@/layers/visualization/timeline';
import { useTimeStore } from '@/layers/interaction/store';
import { select } from 'd3-selection';

interface Props {
    layout: RenderableTimeline;
    height: number;
}

export const TimelineCanvas: React.FC<Props> = ({ layout, height }) => {
    const svgRef = useRef<SVGSVGElement>(null);
    const { currentTime } = useTimeStore();

    useEffect(() => {
        if (!svgRef.current) return;

        const svg = select(svgRef.current);

        // Render Tracks
        // Note: In a real heavy app, we'd use Canvas API. For now, SVG is fine.

        // 1. Clear previous (naive re-render for prototype)
        svg.selectAll('*').remove();

        // 2. Groups
        const trackGroup = svg.append('g').attr('class', 'tracks');

        layout.tracks.forEach(track => {
            const g = trackGroup.append('g').attr('transform', `translate(0, ${track.y})`);

            // Track Background
            g.append('rect')
                .attr('width', '100%')
                .attr('height', track.height)
                .attr('fill', '#151A21')
                .attr('opacity', 0.5);

            // Segments
            track.segments.forEach(seg => {
                g.append('rect')
                    .attr('x', seg.x)
                    .attr('y', 0)
                    .attr('width', seg.width)
                    .attr('height', track.height)
                    .attr('fill', seg.color)
                    .attr('opacity', seg.opacity)
                    .attr('rx', 2);

                // Label (if wide enough)
                if (seg.width > 50) {
                    g.append('text')
                        .attr('x', seg.x + 4)
                        .attr('y', track.height / 2 + 4)
                        .attr('fill', '#E6E9EF')
                        .attr('font-size', 10)
                        .text(seg.label);
                }
            });

            // Track Label
            g.append('text')
                .attr('x', 10)
                .attr('y', -4)
                .attr('fill', '#7F8AA3')
                .attr('font-size', 10)
                .text(track.label);
        });

        // 3. Time Cursor (Overlay)
        const cursorX = layout.timeScale(currentTime);
        svg.append('line')
            .attr('x1', cursorX)
            .attr('x2', cursorX)
            .attr('y1', 0)
            .attr('y2', height)
            .attr('stroke', '#4C9AFF')
            .attr('stroke-width', 1);

    }, [layout, height, currentTime]); // Re-render on layout or time change

    return (
        <svg
            ref={svgRef}
            width="100%"
            height={height}
            className="w-full h-full bg-bg-primary border border-border-subtle"
        />
    );
};
