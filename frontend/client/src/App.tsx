import { useEffect, useState, useMemo } from 'react';
import { StateAdapter } from '@/layers/state/adapter';
import { NarrativeVersionDTO } from '@/layers/state/contracts';
import { TimelineLayout, RenderableTimeline } from '@/layers/visualization/timeline';
import { TimelineCanvas } from '@/components/TimelineCanvas';
import { Scrubber } from '@/components/Scrubber';
// import { useTimeStore } from '@/layers/interaction/store'; // Disabled for prototype

// Layout Configuration (Forensic Standards)
const CONFIG = {
    width: 1200,
    trackHeight: 40,
    trackGap: 10,
    viewStart: new Date('2024-01-01T12:00:00Z'),
    viewEnd: new Date('2024-01-02T12:00:00Z')
};

function App() {
    const [version, setVersion] = useState<NarrativeVersionDTO | null>(null);
    // const { viewStart, viewEnd } = useTimeStore(); // Disabled for prototype

    // 1. Fetch Data (State Layer)
    useEffect(() => {
        async function load() {
            const v = await StateAdapter.getLatestVersion();
            setVersion(v);
        }
        load();
    }, []);

    // 2. Calculate Layout (Visualization Layer)
    // Note: Using CONFIG values for prototype. In production, these would come from store.
    const layout: RenderableTimeline | null = useMemo(() => {
        if (!version) return null;
        return TimelineLayout.calculate(version, CONFIG);
    }, [version]);

    // 3. Render (Presentation Layer)
    return (
        <div className="flex flex-col h-screen bg-bg-primary text-text-primary overflow-hidden">

            {/* Header */}
            <header className="h-12 border-b border-border-subtle flex items-center px-4 bg-bg-secondary">
                <h1 className="font-mono text-sm tracking-widest text-text-muted uppercase">
                    Narrative Intelligence Engine <span className="text-state-active">v0.1.0</span>
                </h1>
                <div className="ml-auto flex gap-4 text-xs text-text-disabled font-mono">
                    {version && <span>VER: {version.version_id}</span>}
                    <span>FORENSIC MODE: ACTIVE</span>
                </div>
            </header>

            {/* Main Visualization */}
            <main className="flex-1 relative overflow-hidden flex items-center justify-center p-8">
                <div className="w-full max-w-[1200px] aspect-[16/9] border border-border-strong bg-bg-secondary relative shadow-2xl">
                    {layout ? (
                        <TimelineCanvas layout={layout} height={600} />
                    ) : (
                        <div className="flex items-center justify-center h-full text-text-muted">Loading Evidence...</div>
                    )}
                </div>
            </main>

            {/* Controls */}
            <Scrubber />

        </div>
    );
}

export default App;
