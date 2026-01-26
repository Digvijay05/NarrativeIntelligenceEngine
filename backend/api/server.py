"""
Narrative Intelligence Engine: Forensic API Server
==================================================

Read-Only API surfacing the Forensic Ledger and Derived State.
Strictly adheres to the "Opaque Read-View" constraint.

Endpoins:
- GET /api/v1/log           -> Linear Event Log
- GET /api/v1/versions      -> Thread Version DAG
- GET /api/v1/state/latest  -> Derived State

Usage:
    uvicorn backend.api.server:app --reload
"""
import os
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..engine import NarrativeIntelligenceBackend, BackendConfig
from ..storage import TemporalStorageConfig
from ..contracts.base import ThreadId
from ..contracts.temporal import LogSequence
from ..temporal.state_machine import DerivedState
from .mapper import map_state_to_dto

# =============================================================================
# INFRASTRUCTURE SETUP
# =============================================================================

# Global Backend Instance
backend_instance: Optional[NarrativeIntelligenceBackend] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize backend interaction on startup."""
    global backend_instance
    
    # Use default data directory or env override
    storage_dir = os.environ.get("NIE_STORAGE_DIR", os.path.join(os.getcwd(), "data", "events"))
    
    print(f"[*] Initializing Forensic Backend at: {storage_dir}")
    
    config = BackendConfig(
        storage=TemporalStorageConfig(
            backend_type="file",
            storage_dir=storage_dir
        ),
        # Read-only configuration could be enforced here if engine supported it explicitly
    )
    
    try:
        backend_instance = NarrativeIntelligenceBackend(config)
        print("[*] Backend initialized successfully.")
    except Exception as e:
        print(f"[!] FAILED to initialize backend: {e}")
        raise e
        
    yield
    
    print("[*] Shutting down backend connection.")
    backend_instance = None

app = FastAPI(
    title="Narrative Intelligence Engine API",
    version="0.1.0",
    description="Forensic Read-Layer for Narrative Intelligence Engine",
    lifespan=lifespan
)

# CORS (Allow Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domian
    allow_credentials=True,
    allow_methods=["GET"], # STRICT READ-ONLY
    allow_headers=["*"],
)


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """System status."""
    if not backend_instance:
        raise HTTPException(status_code=503, detail="Backend not initialized")
    return {"status": "online", "mode": "forensic"}

@app.get("/api/v1/log")
async def get_log(limit: int = 100, offset: int = 0):
    """
    Get linear event log.
    Constraint: Returns strictly ordered events (by sequence).
    """
    # Note: Engine interface needs to expose raw log access for this.
    # Currently engine exposes ingest/query.
    # We'll access the storage component directly via the engine for forensic dump.
    # This is "bypassing" the engine logic but respecting the layered architecture 
    # as this IS the forensic layer.
    
    # Simplified implementation: read fragments/events file via backend storage
    # ideally backend exposes `get_log_entries`.
    
    # Using internal storage access for prototype
    log_entries = []
    # This would need a proper implementation in TemporalStorageEngine to scan log_entries.jsonl
    # For now, we return empty or implement a scanner if critical.
    # Let's focus on STATE visualization first.
    return {"entries": []} # placeholder

@app.get("/api/v1/versions")
async def get_versions():
    """
    Get version DAG.
    Shows branching structure.
    """
    # Uses snapshot history
    if not backend_instance:
        raise HTTPException(503)
        
    # We can inspect snapshots from storage
    # backend_instance._storage.get_all_thread_ids()...
    
    # Placeholder for prototype
    return {"roots": []}

@app.get("/api/v1/state/latest")
async def get_latest_state(thread_id: Optional[str] = None):
    """
    Get currently derived state (HEAD).
    Optional: Filter by single thread.
    """
    if not backend_instance:
        raise HTTPException(503)
        
    # 1. Recompute State from Log (Forensic Proof)
    # in a real system we might cache, but here we derive fresh to prove it works
    # We call internal replayer
    
    try:
        # Access internal replay engine
        replayer = backend_instance._replay_engine
        log = backend_instance._event_log
        
        # HEAD sequence
        head = log.state.head_sequence
        
        # Replay!
        # This returns ReplayResult
        result = replayer.replay_to(head)
        
        if not result.success or not result.state:
             raise HTTPException(500, detail="State derivation failed")
             
        # 2. Map to DTO
        # Need to fetch fragments for payload details (timestamps)
        # We can get them from storage
        all_frags = {f.fragment_id.value: f for f in backend_instance._storage.get_all_fragments()}
        
        dto = map_state_to_dto(result.state, all_frags)
        
        # Filter if thread_id requested
        if thread_id:
            dto["threads"] = [t for t in dto["threads"] if t["thread_id"] == thread_id]
            
        return dto
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))
