import { useEffect, useMemo, useRef } from 'react';
import { TimelineCanvas } from './visualization/TimelineCanvas';
import { ForensicScrubber } from './components/Scrubber';
import { useForensicStore, selectActiveFrame, selectActiveThreads } from './state/store';
import { fetchLatestSnapshot, subscribeToStream } from './state/adapter';

/**
 * Narrative Oscilloscope App
 * ==========================
 * 
 * ARCHITECTURE:
 * - State: ForensicStore (Zustand)
 * - Data: Backend API via adapter.ts
 * - Viz: D3 TimelineCanvas
 * - Control: ForensicScrubber
 */
function App() {
    const appendSnapshot = useForensicStore(s => s.appendSnapshot);
    const setConnectionStatus = useForensicStore(s => s.setConnectionStatus);
    const connectionStatus = useForensicStore(s => s.connectionStatus);
    const activeFrame = useForensicStore(selectActiveFrame);
    const activeThreads = useForensicStore(selectActiveThreads);

    const unsubRef = useRef<(() => void) | null>(null);

    // === INITIAL FETCH ===
    useEffect(() => {
        setConnectionStatus('connecting');

        fetchLatestSnapshot()
            .then(snapshot => {
                appendSnapshot(snapshot);
                setConnectionStatus('connected');
            })
            .catch(err => {
                console.error('[App] Initial fetch failed:', err);
                setConnectionStatus('error', err.message);
            });

        // Cleanup
        return () => {
            if (unsubRef.current) {
                unsubRef.current();
            }
        };
    }, [appendSnapshot, setConnectionStatus]);

    // === SSE SUBSCRIPTION (after initial connection) ===
    useEffect(() => {
        if (connectionStatus !== 'connected') return;

        unsubRef.current = subscribeToStream(
            (snapshot) => {
                appendSnapshot(snapshot);
            },
            (err) => {
                console.error('[App] SSE error:', err);
                setConnectionStatus('error', err.message);
            }
        );

        return () => {
            if (unsubRef.current) {
                unsubRef.current();
                unsubRef.current = null;
            }
        };
    }, [connectionStatus, appendSnapshot, setConnectionStatus]);

    // === DERIVED TIME DOMAIN ===
    const { domainStart, domainEnd } = useMemo(() => {
        if (!activeFrame || activeThreads.length === 0) {
            return {
                domainStart: new Date(),
                domainEnd: new Date(Date.now() + 3600000)
            };
        }

        let min = Infinity;
        let max = -Infinity;

        for (const thread of activeThreads) {
            const start = new Date(thread.start_time).getTime();
            const end = new Date(thread.end_time).getTime();
            if (start < min) min = start;
            if (end > max) max = end;
        }

        // Add 10% padding
        const range = max - min;
        const padding = range * 0.1;

        return {
            domainStart: new Date(min - padding),
            domainEnd: new Date(max + padding)
        };
    }, [activeFrame, activeThreads]);

    return (
        <div className="flex flex-col h-screen bg-bg-primary text-text-primary overflow-hidden">
            {/* Header */}
            <header className="h-12 border-b border-border-subtle flex items-center justify-between px-4 bg-bg-secondary">
                <h1 className="font-mono text-sm tracking-widest text-text-muted uppercase">
                    Narrative Oscilloscope <span className="text-state-active">v0.2.0</span>
                </h1>

                {/* Connection Status */}
                <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' :
                        connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                            connectionStatus === 'error' ? 'bg-red-500' :
                                'bg-gray-500'
                        }`} />
                    <span className="font-mono text-xs text-text-muted uppercase">
                        {connectionStatus}
                    </span>
                </div>
            </header>

            {/* Visualization */}
            <main className="flex-1 w-full h-full relative overflow-hidden">
                {activeThreads.length > 0 ? (
                    <TimelineCanvas
                        threads={activeThreads}
                        width={1200}
                        height={600}
                        domainStart={domainStart}
                        domainEnd={domainEnd}
                    />
                ) : (
                    <div className="flex items-center justify-center h-full text-text-muted font-mono text-sm">
                        {connectionStatus === 'connecting' ? 'Connecting to backend...' :
                            connectionStatus === 'error' ? 'Connection failed. Check backend.' :
                                'No data available.'}
                    </div>
                )}
            </main>

            {/* Scrubber */}
            <ForensicScrubber />
        </div>
    );
}

export default App;
