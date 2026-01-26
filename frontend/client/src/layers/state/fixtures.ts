/**
 * State Layer: Fixtures
 * 
 * Adapts the static JSON fixture to the TypeScript contract.
 * Serves as the implementation of I3 (Single JSON Fixture).
 */

import { NarrativeVersionDTO } from './contracts';
import fixtureData from './fixture.json';

// Cast the JSON to the Contract (TS Validated)
export const FIXTURE_VERSION: NarrativeVersionDTO = fixtureData as unknown as NarrativeVersionDTO;
