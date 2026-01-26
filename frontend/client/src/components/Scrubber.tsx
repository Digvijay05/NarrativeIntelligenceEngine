/**
 * Presentation Layer: Scrubber
 * =============================
 * Time-travel control component.
 * 
 * CONSTRAINTS:
 * - No data interpretation.
 * - Purely controls cursor position.
 * - Displays raw time values.
 */

import React, { useCallback } from 'react';
import { useForensicStore, selectActiveFrame } from '../state/store';

export const ForensicScrubber: React.FC = () => {
    const tape = useForensicStore(s => s.tape);
    const cursor = useForensicStore(s => s.cursor);
    const isPlaying = useForensicStore(s => s.isPlaying);
    const scrub = useForensicStore(s => s.scrub);
    const play = useForensicStore(s => s.play);
    const pause = useForensicStore(s => s.pause);
    const stepForward = useForensicStore(s => s.stepForward);
    const stepBackward = useForensicStore(s => s.stepBackward);

    const activeFrame = useForensicStore(selectActiveFrame);

    const handleScrub = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        scrub(parseInt(e.target.value, 10));
    }, [scrub]);

    const togglePlay = useCallback(() => {
        if (isPlaying) {
            pause();
        } else {
            play();
        }
    }, [isPlaying, play, pause]);

    const isEmpty = tape.length === 0;

    return (
        <div className="h-16 bg-bg-secondary border-t border-border-subtle flex items-center px-4 gap-4">

            {/* Step Back */}
            <button
                onClick={stepBackward}
                disabled={isEmpty || cursor === 0}
                className="p-2 rounded hover:bg-bg-tertiary text-text-primary transition-colors disabled:opacity-30"
                title="Step Back"
            >
                ⏮
            </button>

            {/* Play/Pause */}
            <button
                onClick={togglePlay}
                disabled={isEmpty}
                className="p-2 rounded hover:bg-bg-tertiary text-text-primary transition-colors disabled:opacity-30"
                title={isPlaying ? "Pause" : "Play"}
            >
                {isPlaying ? '⏸' : '▶'}
            </button>

            {/* Step Forward */}
            <button
                onClick={stepForward}
                disabled={isEmpty || cursor === tape.length - 1}
                className="p-2 rounded hover:bg-bg-tertiary text-text-primary transition-colors disabled:opacity-30"
                title="Step Forward"
            >
                ⏭
            </button>

            {/* Frame Counter */}
            <div className="font-mono text-text-secondary text-sm min-w-[80px]">
                {isEmpty ? '--/--' : `${cursor + 1}/${tape.length}`}
            </div>

            {/* Scrubber Range */}
            <input
                type="range"
                min={0}
                max={Math.max(0, tape.length - 1)}
                value={cursor}
                onChange={handleScrub}
                disabled={isEmpty}
                className="flex-1 h-2 bg-bg-tertiary rounded cursor-pointer disabled:cursor-not-allowed"
            />

            {/* Current Timestamp */}
            <div className="font-mono text-text-muted text-xs min-w-[180px] text-right">
                {activeFrame?.timestamp ? new Date(activeFrame.timestamp).toISOString() : '----'}
            </div>
        </div>
    );
};

export default ForensicScrubber;
