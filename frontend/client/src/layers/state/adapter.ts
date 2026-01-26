/**
 * State Layer: Adapter
 * 
 * Fetches data. In real app, hits API.
 * In prototype, returns fixtures.
 */

import { NarrativeVersionDTO } from './contracts';
import { validateVersion } from './validator';

export const StateAdapter = {

    async getLatestVersion(): Promise<NarrativeVersionDTO> {
        try {
            const response = await fetch('http://localhost:8000/api/v1/state/latest');

            if (!response.ok) {
                // Return fixture logic could be fallback, but for now strict failure
                throw new Error(`API Error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();

            // RUNTIME INVARIANT CHECK (The "Microscope")
            return validateVersion(data);
        } catch (e) {
            console.error("CRITICAL FORENSIC FAILURE: Backend connection or contract violation", e);
            throw e;
        }
    }
};

