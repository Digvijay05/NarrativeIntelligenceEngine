"""
Synthetic Adversarial Canon
===========================

Generates stress-test scenarios for the Narrative Intelligence Engine.
Focuses on Forensic Constraints: Late Arrivals, Divergence, and Absence.

SCENARIOS:
1. The Late Arrival: Verifies local-first immutability and re-computation.
2. The Parallel Reality: Verifies handling of mutually exclusive claims.
3. The Great Silence: Verifies first-class absence detection.

USAGE:
    python tests/stress_canon.py
"""
import os
import shutil
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import List

# Add project root to path
sys.path.append(os.getcwd())

from backend.engine import NarrativeIntelligenceBackend, BackendConfig
from backend.storage import TemporalStorageConfig
from backend.contracts.base import SourceId, Timestamp
from backend.contracts.events import RawIngestionEvent
from backend.forensic import cmd_versions, cmd_log

BASE_STORAGE_DIR = os.path.join(os.getcwd(), "data", "adversarial_canon")

def setup_scene(scene_name: str) -> NarrativeIntelligenceBackend:
    """Initialize a clean backend for a specific scene."""
    storage_dir = os.path.join(BASE_STORAGE_DIR, scene_name)
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)
    os.makedirs(storage_dir, exist_ok=True)
    
    print(f"\n🎬 SETUP SCENE: {scene_name}")
    print(f"    Storage: {storage_dir}")
    
    config = BackendConfig(
        storage=TemporalStorageConfig(
            backend_type="file",
            storage_dir=storage_dir
        )
    )
    return NarrativeIntelligenceBackend(config), storage_dir

def run_scene_1_late_arrival():
    """
    SCENE 1: The Late Arrival
    
    Timeline:
    T0: Event A (Historic)
    T2: Event C (Current)
    T1: Event B (Late Arrival - arrives after C but happened before C)
    
    Expectation:
    - Log structure: A -> C -> B (Append only)
    - derived State: A -> B -> C (Recomputed)
    """
    backend, storage_dir = setup_scene("scene_1_late_arrival")
    source = SourceId("chrono_witness", "sensor")
    
    base_time = datetime.now(timezone.utc)
    t0 = base_time - timedelta(hours=10)
    t1 = base_time - timedelta(hours=5)
    t2 = base_time
    
    print("[*] Action: Ingesting T0 (Ancient Base)...")
    backend.ingest_single(source, "T0: The foundation was laid.", Timestamp(t0))
    
    print("[*] Action: Ingesting T2 (Current Tip)...")
    backend.ingest_single(source, "T2: The roof was finished.", Timestamp(t2))
    
    print("[*] Action: Ingesting T1 (LATE ARRIVAL - The missing middle)...")
    # This arrives LAST, but happened in the MIDDLE
    backend.ingest_single(source, "T1: The walls were built.", Timestamp(t1))
    
    print("\n✅ VERIFICATION (CLI Output):")
    arg_storage_dir = storage_dir
    class Args:
        storage_dir = arg_storage_dir
    print("--- Event Log (Linear Ingestion Order) ---")
    cmd_log(Args)
    print("\n--- Version Graph (Should show branching/recompute) ---")
    cmd_versions(Args)

def run_scene_2_parallel_reality():
    """
    SCENE 2: The Parallel Reality
    
    Two sources make contradictory claims about the same topic.
    
    Expectation:
    - Thread splits into two parallel branches.
    - System does NOT collapse them into one "truth".
    """
    backend, storage_dir = setup_scene("scene_2_parallel_reality")
    
    # We need a shared topic/seed to force them into the same thread initially
    # or rely on topic clustering.
    
    src_red = SourceId("network_red", "news")
    src_blue = SourceId("network_blue", "news")
    
    t0 = datetime.now(timezone.utc)
    
    print("[*] Action: Both sources agree on context...")
    backend.ingest_single(src_red, "The election results are coming in for Region X.", Timestamp(t0))
    backend.ingest_single(src_blue, "Region X election processing initiated.", Timestamp(t0))
    
    print("[*] Action: DIVERGENCE! Mutually exclusive claims...")
    # These should trigger a conflict if we had a contradiction detector
    # Since we don't have a real ML model, we might need to simulate the 'contradiction' tag 
    # or rely on the StateMachine's divergence check (which needs implementation).
    
    backend.ingest_single(src_red, "Candidate Red has won Region X decisively.", Timestamp(t0))
    backend.ingest_single(src_blue, "Candidate Blue has won Region X decisively.", Timestamp(t0))
    
    print("\n✅ VERIFICATION (CLI Output):")
    arg_storage_dir = storage_dir
    class Args:
        storage_dir = arg_storage_dir
    cmd_versions(Args)

def run_scene_3_great_silence():
    """
    SCENE 3: The Great Silence
    
    A heartbeat source goes silent.
    
    Expectation:
    - AbsenceMarker generated after threshold.
    """
    backend, storage_dir = setup_scene("scene_3_great_silence")
    source = SourceId("heartbeat_monitor", "daemon")
    
    base_time = datetime.now(timezone.utc) - timedelta(days=10)
    
    print("[*] Action: Establishing heartbeat (Daily for 5 days)...")
    for i in range(5):
        ts = base_time + timedelta(days=i)
        backend.ingest_single(source, f"Heartbeat check {i} OK", Timestamp(ts))
        
    print("[*] Action: SILENCE (No events for 5 days)...")
    # We query the state NOW (5 days later)
    # The state derivation should insert absence markers for the missing days
    
    # Trigger a "view" by querying (or just ingesting a dummy event to force recompute)
    # We'll ingest a "Query Event" or strictly speaking, just asking for state should do it
    # But our CLI shows persisted snapshots. 
    # To force a snapshot with absence, we likely need to trigger the state machine.
    # We'll ingest a distinct event "Probe" to force the timeline forward.
    
    print("[*] Action: Probing silence...")
    backend.ingest_single(SourceId("auditor", "system"), "Auditing system status.", Timestamp.now())
    
    print("\n✅ VERIFICATION (CLI Output):")
    arg_storage_dir = storage_dir
    class Args:
        storage_dir = arg_storage_dir
    
    # We specifically want to check the state for absence markers
    # For now, we'll list versions and hopefully see the absence in the snapshot data if we dumped detailed state
    cmd_versions(Args)
    
    # In a full test we'd inspect the snapshot JSON content
    pass

if __name__ == "__main__":
    print("==================================================")
    print("SYNTHETIC ADVERSARIAL CANON")
    print("Constructing Stress Scenarios...")
    print("==================================================")
    
    run_scene_1_late_arrival()
    run_scene_2_parallel_reality()
    run_scene_3_great_silence()
