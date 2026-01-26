import React, { useRef, useEffect, useMemo } from 'react';
import * as d3 from 'd3';
import { NarrativeThreadDTO } from '../state/contracts';

interface TimelineCanvasProps {
    threads: NarrativeThreadDTO[];
    width: number;
    height: number;
    // Viewport time range
    domainStart: Date;
    domainEnd: Date;
}

/**
 * TimelineCanvas
 * ==============
 * Pure Visualization Layer.
 * Renders backend truth as SVG.
 * 
 * Rules:
 * 1. No data mutation.
 * 2. x-axis is linear time.
 * 3. y-axis is thread ID (categorical).
 * 4. Silence is empty space.
 */
export const TimelineCanvas: React.FC<TimelineCanvasProps> = ({
    threads,
    width,
    height,
    domainStart,
    domainEnd
}) => {
    const svgRef = useRef<SVGSVGElement>(null);

    // D3 Layout Calculation (Pure)
    const layout = useMemo(() => {
        // X Scale
        const xScale = d3.scaleTime()
            .domain([domainStart, domainEnd])
            .range([0, width]);

        // Y Scale (Bands)
        const threadIds = threads.map(t => t.thread_id);
        const yScale = d3.scaleBand()
            .domain(threadIds)
            .range([50, height - 20]) // Top padding for axis
            .padding(0.2);

        return { xScale, yScale };
    }, [width, height, domainStart, domainEnd, threads]);

    // Rendering Effect
    useEffect(() => {
        if (!svgRef.current) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll("*").remove(); // Clear previous render

        const { xScale, yScale } = layout;

        // 1. Grid / Axis
        const xAxis = d3.axisTop(xScale)
            .ticks(5)
            .tickSizeOuter(0)
            .tickFormat(d3.timeFormat("%H:%M") as any);

        const gridGroup = svg.append("g")
            .attr("class", "grid")
            .attr("transform", "translate(0, 40)")
            .call(xAxis);

        gridGroup.selectAll("path, line")
            .attr("stroke", "#3A455C") // border-strong
            .attr("stroke-dasharray", "2,2");

        gridGroup.selectAll("text")
            .attr("fill", "#7F8AA3") // text-muted
            .attr("font-family", "JetBrains Mono, monospace")
            .attr("font-size", "10px");

        // 2. Threads
        const threadsGroup = svg.append("g")
            .attr("class", "threads");

        threads.forEach(thread => {
            const y = yScale(thread.thread_id);
            const bandwidth = yScale.bandwidth();

            if (y === undefined) return;

            const group = threadsGroup.append("g")
                .attr("class", `thread-${thread.state}`);

            // Draw Fragments (Points)
            thread.fragments.forEach(frag => {
                const x = xScale(new Date(frag.event_time));

                // Dot
                group.append("circle")
                    .attr("cx", x)
                    .attr("cy", y + bandwidth / 2)
                    .attr("r", 3)
                    .attr("fill", getColorForState(thread.state));
            });

            // Draw Label
            group.append("text")
                .attr("x", 10)
                .attr("y", y + bandwidth / 2 + 4)
                .text(thread.thread_id.substring(0, 8))
                .attr("fill", "#56607A") // text-disabled
                .attr("font-family", "JetBrains Mono")
                .attr("font-size", "10px");
        });

    }, [layout, threads]);

    return (
        <svg
            ref={svgRef}
            width={width}
            height={height}
            className="w-full h-full bg-bg-primary"
        />
    );
};

// Stateless Color Helper
function getColorForState(state: string): string {
    switch (state) {
        case 'active': return '#4C9AFF';
        case 'emergent': return '#6B85B7';
        case 'diverged': return '#C77D3A';
        case 'terminated': return '#5A647A';
        default: return '#8A94A6';
    }
}
