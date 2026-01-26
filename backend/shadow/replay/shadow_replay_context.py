from typing import List, Optional
from backend.shadow.contract import RawShadowEvent
from backend.shadow.replay.shadow_replay_adapter import adapt_shadow_event
from backend.temporal.state_machine import StateMachine, DerivedState
from backend.temporal.event_log import ImmutableEventLog
from backend.normalization import NormalizationEngine, NormalizationConfig
from backend.contracts.events import RawIngestionEvent, NormalizedFragment

class ShadowReplayContext:
    def __init__(self):
        # ISOLATED UNIVERSE
        # We instantiate fresh engines for providing the physics
        
        # 1. Normalization (Stateless)
        # Use default config, but we could customize for shadow if needed
        self.normalization_engine = NormalizationEngine()
        
        # 2. State Machine (The Physics)
        # Calibration from Verification Phase
        # We should match the regression harness or production defaults?
        # User said "Same physics". Production defaults are 168h dormancy.
        # But we want to see effects in 24h.
        # However, "Constitution: tune thresholds... Forbidden".
        # So we use defaults.
        self.state_machine = StateMachine() 
        
        self.shadow_state: Optional[DerivedState] = None
        self.event_log = ImmutableEventLog()

    def replay(self, shadow_events: List[RawShadowEvent]) -> DerivedState:
        """
        Replay shadow events in an isolated context.
        """
        # 1. Sort by Tick (Deterministic)
        sorted_events = sorted(shadow_events, key=lambda e: e.poll_tick_id)
        
        # 2. Clear Log (Optional: if we want fresh replay every time)
        # Or we can append? 
        # "Replay is deterministic... Same log at same sequence = same derived state."
        # If we reuse the context, we should probably rebuild the log or append new events.
        # For simplicity and isolation, we rebuild the log from the input batch 
        # if the input batch represents "All History".
        # But `run_shadow.py` might feed incremental?
        # The User said: "shadow_events = sorted(log.all_events())"
        # So inputs are ALL events. So we start fresh.
        
        self.event_log = ImmutableEventLog()
        
        # 3. Adapt & Normalize
        for shadow_event in sorted_events:
            # A. Adapt RawShadow -> RawIngestion
            raw_ingest = adapt_shadow_event(shadow_event)
            
            # B. Normalize RawIngestion -> NormalizedFragment
            norm_result = self.normalization_engine.normalize(raw_ingest)
            
            if norm_result.success and norm_result.fragment:
                # C. Append to Log
                self.event_log.append(norm_result.fragment)
            else:
                # Log normalize failure? (In shadow mode we observe silence)
                pass
        
        # 4. Derive State
        self.shadow_state = self.state_machine.derive_state(self.event_log)
        
        return self.shadow_state
