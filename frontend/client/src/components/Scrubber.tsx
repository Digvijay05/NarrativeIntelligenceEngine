/**
 * Presentation Layer: Scrubber
 * 
 * Responsibility:
 * Control temporal state.
 */

import React from 'react';
import { useTimeStore } from '@/layers/interaction/store';
import { Play, Pause } from 'lucide-react';

export const Scrubber: React.FC = () => {
    const { isPlaying, togglePlay, currentTime } = useTimeStore();

    return (
        <div className="h-16 bg-bg-secondary border-t border-border-subtle flex items-center px-4 gap-4">

            {/* Playback Controls */}
            <button
                onClick={togglePlay}
                className="p-2 rounded hover:bg-bg-tertiary text-text-primary transition-colors"
            >
                {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            </button>

            {/* Time Display */}
            <div className="font-mono text-text-secondary text-sm">
                {currentTime.toISOString()}
            </div>

            {/* Scrubber Bar (Mock) */}
            <div className="flex-1 h-2 bg-bg-tertiary rounded relative group cursor-pointer">
                <div className="absolute top-0 left-0 h-full bg-state-active w-[50%]" />
                {/* Real scrubber would attach mouse events here to call setTime */}
            </div>

        </div>
    );
};
