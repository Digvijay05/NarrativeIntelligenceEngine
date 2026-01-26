import os
import shutil
import sys
import argparse
from datetime import datetime, timezone, timedelta

# Add project root to path
# Assuming we run from project root
sys.path.append(os.getcwd())

from backend.engine import NarrativeIntelligenceBackend, BackendConfig
from backend.storage import TemporalStorageConfig
from backend.contracts.base import SourceId, Timestamp
from backend.forensic import cmd_verify, cmd_log, cmd_versions

def run_test():
    # Use absolute path for storage to avoid confusion
    base_dir = os.getcwd()
    storage_dir = os.path.join(base_dir, "data", "test_forensic_storage")
    
    # Clean up previous run
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)
    
    print(f"[*] Initializing Backend with File Storage at {storage_dir}")
    config = BackendConfig(
        storage=TemporalStorageConfig(
            backend_type="file",
            storage_dir=storage_dir
        )
    )
    backend = NarrativeIntelligenceBackend(config)
    
    # Ingest some events
    source_id = SourceId(value="cli_test_source", source_type="test")
    
    events = [
        "Event A: The beginning",
        "Event B: The middle",
        "Event C: The end"
    ]
    
    print("[*] Ingesting events...")
    for payload in events:
        backend.ingest_single(
            source_id=source_id,
            payload=payload,
            event_timestamp=Timestamp.now()
        )
        print(f"    Ingested: {payload}")
        
    # Simulate a late arrival to create version branching (for cmd_versions)
    print("[*] Ingesting Late Arrival...")
    late_time = datetime.now(timezone.utc) - timedelta(hours=1)
    backend.ingest_single(
        source_id=source_id,
        payload="Event A.5: The forgotten middle",
        event_timestamp=Timestamp(value=late_time)
    )
    
    # Run CLI commands
    print("\n" + "="*50)
    print("RUNNING FORENSIC CLI VERIFICATION")
    print("="*50 + "\n")
    
    class Args:
        storage_dir = os.path.join(base_dir, "data", "test_forensic_storage")
    
    args = Args()
    
    print("\n>>> COMMAND: verify")
    cmd_verify(args)
    
    print("\n>>> COMMAND: log")
    cmd_log(args)
    
    print("\n>>> COMMAND: versions")
    cmd_versions(args)

if __name__ == "__main__":
    run_test()
