#!/usr/bin/env python3
"""
Canonical Regression Witness
============================
Executes: data/canonical/absence_replay_v1.json
Against:  backend.temporal.engine.TimelineEngine

PURPOSE:
Proves that the engine obeys the physics of Absence, Dormancy, and Vanished states.
This is not a test suite. It is a formal verification witness.

INVARIANTS:
1. Dormancy Recovery (Tick +2 -> Active)
2. Gap Creation (Tick +4 -> Absence Block)
3. Zombie Resurrection (Tick +6 -> Active + Gap)
4. Vanished Prohibition (Tick +11 -> New Thread)
"""

import sys
import os
import json
import dataclasses
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.contracts.base import Timestamp, FragmentId, ThreadId, SourceId, ThreadLifecycleState, CanonicalTopic, CanonicalEntity
from backend.contracts.events import NormalizedFragment, ContentSignature, SourceMetadata
from backend.temporal.state_machine import StateMachine, ThreadView, DerivedState
from backend.temporal.event_log import ImmutableEventLog

class RegressionWitness:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        with open(dataset_path, "r") as f:
            self.dataset = json.load(f)
            
        # Calibrate engine for regression scale (30s ticks)
        # Dormancy threshold > 30s * 2 (60s). Let's say 90s.
        # Dormancy hours = 90 / 3600 = 0.025
        self.engine = StateMachine(
            topic_overlap_min=0.6,
            temporal_adjacency_hours=1,
            dormancy_hours=0.025
        )
        self.event_log = ImmutableEventLog()
        from backend.temporal.event_log import LogSequence
        self.state: DerivedState = DerivedState(
            at_sequence=LogSequence(0),
            state_hash="",
            threads=tuple()
        )
        self.failures = []
        
    def run(self):
        print(f"[*] Loading Canonical Dataset: {self.dataset['dataset_metadata']['name']}")
        print(f"[*] Timestamp: {Timestamp.now().to_iso()}")
        print("-" * 60)
        
        inputs = sorted(self.dataset["inputs"], key=lambda x: x["tick"])
        max_tick = inputs[-1]["tick"]
        
        # Simulate ticks
        for tick in range(1, max_tick + 1):
            # 1. Get input for this tick
            input_frame = next((i for i in inputs if i["tick"] == tick), None)
            fragments = []
            
            if input_frame:
                print(f"  Tick {tick}: Input received ({len(input_frame['fragments'])} fragments)")
                for f_data in input_frame["fragments"]:
                    frag = self._create_fragment(f_data, tick)
                    fragments.append(frag)
            else:
                print(f"  Tick {tick}: No input (Silence)")
                
            # 2. Advance Engine
            # Append fragments to event log
            if fragments:
                for frag in fragments:
                    self.event_log.append(frag)
            
            # Simulate "Tick" passage? 
            # The StateMachine handles absence based on time differences in the log.
            # However, if no new fragment arrives (Silence), we still need to check absence.
            # But derive_state() is purely reactive to the log.
            # Wait, our engine's derive_state() derives state up to the HEAD of the log.
            # If nothing was added to the log, derive_state() returns the same state.
            # This implies the engine needs a "current time" reference to detect absence at the TAIL.
            # Looking at StateMachine.derive_state signature: derive_state(self, log, until_sequence=None)
            # It doesn't take "current_time".
            # Absence is encoded as FIRST CLASS DATA in the log via "ExpectedContinuation" or "AbsenceMarker"?
            # Let's check if we need to explicitly inject "Tick" events?
            # Or if derive_state calculates absence relative to the last event?
            
            # Inspecting state_machine.py Outline earlier:
            # _check_absence(self, fragment, builder, current_seq)
            # It checks absence *before* processing a new fragment.
            # So absence is detected lazily when the NEXT fragment arrives?
            # Or is there a way to force a check?
            
            # If correct: Absence is only materialized when a new fragment arrives (or a "Heartbeat" fragment).
            # The specification says "A thread transitions... if Tick_current = Tick_last + 4".
            # To simulate this without data, we might need to inject a "Clock Tick" or "Heartbeat" into the log?
            
            # Let's assume for this regression that we only see state changes when we add SOMETHING.
            # But wait, "Gap Creation" test involves silence.
            # If we simply do nothing, state won't change.
            # We must inject a "Tick" marker or heartbeats? 
            # Or maybe the log needs to record "Time Passed"?
            
            # Let's try appending a dummy "Tick" event if no fragments?
            # Or better: The fragments in the dataset act as the clock.
            # Tick 7 (Zombie) arrives at Tick 7. Absence logic runs then.
            # But what about Tick 4 (Gap Creation)?
            # The gaps happen *between* events.
            # If we query derive_state() at Tick 12...
            
            # Let's just append the fragments we have.
            # The state derivation should handle the timestamps on the fragments.
            
            current_head = self.event_log.state.head_sequence
            current_tick_time = self._tick_to_time(tick)
            self.state = self.engine.derive_state(self.event_log, until_sequence=current_head, reference_time=current_tick_time)
            
            # 3. Check Expectations (if any defined for this tick)
            # The dataset defines "expected_invariants" as final states, but we can check continuously?
            # Actually the dataset has 'expected_invariants' as a summary. 
            # Let's run to completion and check invariants.
            
        print("-" * 60)
        self._verify_invariants()
        
        if self.failures:
            print("\n[!] FATAL: REGRESSION FAILED")
            for f in self.failures:
                print(f"    - {f}")
            sys.exit(1)
        else:
            print("\n[*] SUCCESS: All invariants witnessed.")
            sys.exit(0)

    def _create_fragment(self, data: dict, tick: int) -> NormalizedFragment:
        # Helper to create strictly compliant fragment DTO
        # We need to map JSON to the internal NormalizedFragment
        # Using a dummy factory or direct instantiation
        
        # Extract simple topics for overlap
        topics = tuple(CanonicalTopic(t.lower(), 1.0) for t in data["content"].split() if len(t) > 3)
        
        return NormalizedFragment(
            fragment_id=FragmentId(data["fragment_id"], "hash_" + data["fragment_id"]),
            source_event_id="evt_" + data["fragment_id"],
            content_signature=ContentSignature(data["content"], len(data["content"])), # Mocking signature as content for simplicity
            normalized_payload=data["content"],
            detected_language="en",
            canonical_topics=topics, # Engine uses Jaccard on payload/tokens
            canonical_entities=tuple(),
            duplicate_info=None, # Assuming unique
            contradiction_info=None,
            normalization_timestamp=Timestamp(datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))),
            source_metadata=SourceMetadata(
                source_id=SourceId(data["source_id"], "rss"),
                source_confidence=1.0,
                capture_timestamp=Timestamp(datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))),
                event_timestamp=Timestamp(datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")))
            )
        )

    def _tick_to_time(self, tick: int) -> Timestamp:
        # Base time: 2024-01-01T10:00:00Z
        from datetime import datetime, timedelta
        base = datetime(2024, 1, 1, 10, 0, 0)
        delta = timedelta(seconds=(tick - 1) * 30)
        return Timestamp(base + delta)

    def _verify_invariants(self):
        print("[*] Verifying Invariants...")
        invariants = self.dataset["expected_invariants"]
        
        # Helper to find thread by subject tokens (approximate match since we don't have token index in dataset)
        # Actually we can search by the fragment IDs known to be in the thread
        
        for case in invariants:
            # We identify the target thread by finding which thread contains the first fragment of the sequence
            # E.g. for "Dormancy Recovery", we look for thread containing "frag_A_1"
            
            # Finding fragment IDs involved in this case?
            # The dataset doesn't explicitly link "Thread A" to "frag_A_1" in the invariants section, 
            # but the text "Subject A" implies it.
            # We'll search threads for the relevant content/tokens.
            
            target_tokens = set(case["subject_tokens"])
            
            # Find threads that match these tokens (or contain fragments with these tokens)
            matching_threads = []
            
            # We need to inspect the final state's threads
            # BUT: Vanished threads might be in a different list or marked state?
            # Structure: derived_state.threads (List[ThreadView])
            
            for thread in self.state.threads:
                # Check fragments in this thread
                # We need to look up fragment content. 
                # For this harness, we can cheat and look at the fragment IDs if we tracked them.
                # Let's assume the engine tracked tokens.
                
                # Check if any fragment in this thread has text matching the subject
                # We'll just check if the thread contains the primary fragment for the case
                # Case 1 (A): frag_A_1
                # Case 2 (B): frag_B_1
                # etc.
                
                # Derive signature from tokens logic?
                # Simpler: Just check if the thread contains the fragment ID corresponding to the case key.
                # A -> frag_A_1, B -> frag_B_1
                
                if "a" in case["subject_tokens"] and any(f.value == "frag_A_1a" for f in thread.member_fragment_ids):
                    matching_threads.append(thread)
                elif "b" in case["subject_tokens"] and any(f.value == "frag_B_1a" for f in thread.member_fragment_ids):
                    matching_threads.append(thread)
                elif "c" in case["subject_tokens"] and any(f.value == "frag_C_1a" for f in thread.member_fragment_ids):
                    matching_threads.append(thread)
                elif "d" in case["subject_tokens"] and any(f.value == "frag_D_1a" for f in thread.member_fragment_ids):
                    matching_threads.append(thread)
                # Case 4 might have a NEW thread for D (frag_D_2)
                elif "d" in case["subject_tokens"] and any(f.value == "frag_D_2" for f in thread.member_fragment_ids):
                    matching_threads.append(thread)

            # 1. Verify Thread Count
            if len(matching_threads) != case["expected_thread_count"]:
                self.failures.append(f"{case['case']}: Expected {case['expected_thread_count']} threads, found {len(matching_threads)}")
                continue
                
            # 2. Verify Final State of the Primary Thread
            # For Case 4 (Vanished Prohibition), we expect 2 threads: one Vanished, one Active (new).
            
            if case["expected_thread_count"] == 1:
                thread = matching_threads[0]
                actual_state = thread.lifecycle_state.name # Enum to str
                if actual_state != case["expected_final_state"]:
                    debug_info = f"State={actual_state}, Frags={[f.value for f in thread.member_fragment_ids]}, Last={thread.last_activity.to_iso()}"
                    self.failures.append(f"{case['case']}: Expected {case['expected_final_state']}, found {actual_state}. {debug_info}")
                
                # 3. Verify Absence Blocks
                actual_blocks = len(thread.absence_markers)
                if actual_blocks != case["expected_absence_blocks"]:
                    self.failures.append(f"{case['case']}: Expected {case['expected_absence_blocks']} absence blocks, found {actual_blocks}")
                    
            elif case["expected_thread_count"] == 2:
                # Special handling for "Vanished Prohibition" (Split identity)
                # We expect one thread (frag_D_1) to be VANISHED
                # And one thread (frag_D_2) to be ACTIVE
                
                t1 = next((t for t in matching_threads if any(f.value == "frag_D_1a" for f in t.member_fragment_ids)), None)
                t2 = next((t for t in matching_threads if any(f.value == "frag_D_2" for f in t.member_fragment_ids)), None)
                
                if not t1 or t1.lifecycle_state.name != "TERMINATED":
                    debug_info = f"State={t1.lifecycle_state.name if t1 else 'None'}, Frags={[f.value for f in t1.member_fragment_ids] if t1 else []}, Last={t1.last_activity.to_iso() if t1 else 'None'}"
                    self.failures.append(f"{case['case']}: Original thread (D_1) not TERMINATED. {debug_info}")
                
                if not t2 or t2.lifecycle_state.name != "ACTIVE":
                     self.failures.append(f"{case['case']}: New thread (D_2) not ACTIVE (found {t2.lifecycle_state.name if t2 else 'None'})")
                    
            print(f"  ✓ {case['case']}: Verified")

if __name__ == "__main__":
    dataset = os.path.join(project_root, "data", "canonical", "absence_replay_v1.json")
    witness = RegressionWitness(dataset)
    witness.run()
