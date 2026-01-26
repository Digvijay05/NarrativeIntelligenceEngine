"""
Verify Forensic API
===================

Integration test for backend/api/server.py.
Spins up the server and hits endpoints.

Requires:
- uvicorn
- requests
"""
import os
import sys
import time
import requests
import subprocess
import shutil
import signal
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

from backend.engine import NarrativeIntelligenceBackend, BackendConfig
from backend.storage import TemporalStorageConfig
from backend.contracts.base import SourceId, Timestamp

TEST_STORAGE_DIR = os.path.join(os.getcwd(), "data", "test_api_env")

def setup_test_data():
    """Ingest some data so the API has something to show."""
    if os.path.exists(TEST_STORAGE_DIR):
        shutil.rmtree(TEST_STORAGE_DIR)
    os.makedirs(TEST_STORAGE_DIR, exist_ok=True)
    
    print(f"[*] Seeding test data in {TEST_STORAGE_DIR}...")
    
    config = BackendConfig(
        storage=TemporalStorageConfig(
            backend_type="file",
            storage_dir=TEST_STORAGE_DIR
        )
    )
    backend = NarrativeIntelligenceBackend(config)
    
    # Ingest baseline
    backend.ingest_single(SourceId("test", "test"), "Event 1", Timestamp.now())
    backend.ingest_single(SourceId("test", "test"), "Event 2", Timestamp.now())
    
    print("[+] Seed complete.")

def run_tests():
    """Run API verification."""
    BASE_URL = "http://localhost:8000"
    
    # 1. Health
    print(">>> Testing /health...")
    try:
        r = requests.get(f"{BASE_URL}/health")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        assert r.status_code == 200
    except Exception as e:
        print(f"[FAIL] Health check failed: {e}")
        return

    # 2. Log
    print("\n>>> Testing /api/v1/log...")
    r = requests.get(f"{BASE_URL}/api/v1/log")
    print(f"Response: {r.json()}")
    
    # 3. State
    print("\n>>> Testing /api/v1/state/latest...")
    r = requests.get(f"{BASE_URL}/api/v1/state/latest")
    data = r.json()
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(f"Error Response: {r.text}")
    data = r.json()
    # print(f"Response: {data}")
    if "threads" in data:
        print(f"[PASS] Structure Valid. Found {len(data['threads'])} threads.")
        if len(data['threads']) > 0:
            segments = data['threads'][0]['segments']
            print(f"       First thread has {len(segments)} segments.")
            print(f"       Segment 0 Kind: {segments[0]['kind']}")
    else:
        print("[FAIL] Invalid State Structure")

def main():
    setup_test_data()
    
    # Set env var for server to pick up
    os.environ["NIE_STORAGE_DIR"] = TEST_STORAGE_DIR
    
    # Start Server in Subprocess
    print("[*] Launching Server...")
    proc = subprocess.Popen(
        [sys.executable, "run_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy()
    )
    
    try:
        # Wait for boot with retry
        print("[*] Waiting for server boot...")
        booted = False
        for i in range(10):
            # Check if process died
            if proc.poll() is not None:
                print(f"[!] Server process died early. Exit code: {proc.returncode}")
                break
                
            try:
                requests.get("http://localhost:8000/health")
                booted = True
                print("[*] Server is online.")
                break
            except:
                time.sleep(1)
        
        if not booted:
            print("[!] Server failed to boot.")
            # Ensure process is dead so we can read output
            if proc.poll() is None:
                print("[*] Terminating server to read output...")
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            
            # Print stderr
            outs, errs = proc.communicate(timeout=1)
            print(f"STDOUT: {outs.decode() if outs else ''}")
            print(f"STDERR: {errs.decode() if errs else ''}")
            return

        # Run Tests
        run_tests()
        
    finally:
        if proc.poll() is None:
            print("[*] Killing Server...")
            proc.terminate()

if __name__ == "__main__":
    main()
        # Clean up
        # shutil.rmtree(TEST_STORAGE_DIR)
