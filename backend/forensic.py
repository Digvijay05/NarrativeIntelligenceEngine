"""
Forensic Reporter CLI
=====================

Tool for forensic verification of the Narrative Intelligence Engine.
Bypasses API to inspect disk state directly.

COMMANDS:
- verify:  Check hash chain integrity
- log:     Dump linear event log (Git-style)
- versions: Visualize version DAG
- state:   Dump point-in-time state

USAGE:
    python -m backend.forensic [COMMAND] [ARGS]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Optional

from .temporal.event_log import ImmutableEventLog
from .temporal.replay import ReplayEngine
from .temporal.state_machine import StateMachine
from .temporal.versioning import VersionTracker
from .contracts.temporal import LogEntry, LogSequence
from .contracts.base import Timestamp, FragmentId
from .contracts.events import NormalizedFragment
# Import necessary helpers to reconstruct objects if needed
# For simplicity, we assume we can reconstruct NormalizedFragment from JSON

def load_fragments(storage_dir: str) -> Dict[str, Dict]:
    """Load raw normalized fragments from storage into dict."""
    fragments = {}
    path = os.path.join(storage_dir, "fragments.jsonl")
    if not os.path.exists(path):
        return fragments
        
    with open(path, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                fid = data.get('fragment_id', {}).get('value')
                if fid:
                    fragments[fid] = data
            except:
                pass
    return fragments

def reconstruct_fragment(data: Dict) -> NormalizedFragment:
    """
    Reconstruct NormalizedFragment object from JSON data.
    Note: specialized reconstruction for verification purposes.
    We need to match the structure expected by LogEntry for hash computation.
    """
    # This is a bit hacky - ideally we use a proper serializer
    # But for forensic verification, we need to ensure we match what was used for hashing.
    # The LogEntry hash uses: sequence|fragment_id|timestamp|prev_hash
    # So we mainly need a NormalizedFragment object that has the correct fragment_id.
    
    from .contracts.base import FragmentId, ContentSignature, SourceMetadata
    from .contracts.events import NormalizedFragment, DuplicateInfo, ContradictionInfo, DuplicateStatus, ContradictionStatus
    
    fid_val = data['fragment_id']['value']
    
    # We create a minimal proxy or try to populate fully?
    # LogEntry.create uses fragment.fragment_id.value.
    # So we just need fragment_id to be correct.
    
    # Mocking the rest for now as they aren't used in LogEntry hash
    # In a real impl, we'd fully deserialized.
    return NormalizedFragment(
        fragment_id=FragmentId(value=fid_val, content_hash=""), 
        source_event_id="",
        content_signature=ContentSignature(payload_hash="", payload_length=0),
        normalized_payload="",
        detected_language=None,
        canonical_topics=(),
        canonical_entities=(),
        duplicate_info=DuplicateInfo(status=DuplicateStatus.UNIQUE),
        contradiction_info=ContradictionInfo(status=ContradictionStatus.NO_CONTRADICTION),
        normalization_timestamp=Timestamp.now(),
        source_metadata=SourceMetadata(source_id=None, source_confidence=1.0, capture_timestamp=Timestamp.now(), event_timestamp=None)
    )

def cmd_verify(args):
    """Verify hash chain integrity."""
    print(f"[*] Verifying storage at: {args.storage_dir}")
    print("[*] Loading fragments...")
    fragment_data = load_fragments(args.storage_dir)
    print(f"    Loaded {len(fragment_data)} fragments.")
    
    log_path = os.path.join(args.storage_dir, "log_entries.jsonl")
    if not os.path.exists(log_path):
        print("[!] No log entries found (empty storage?).")
        return
    
    event_log = ImmutableEventLog()
    count = 0
    errors = 0
    
    print("[*] Verifying hash chain...")
    with open(log_path, 'r') as f:
        for line in f:
            try:
                row = json.loads(line)
                seq_val = row['sequence']
                fid_val = row['fragment_id']
                ts_iso = row['ingestion_timestamp']
                prev_hash = row['previous_hash']
                entry_hash = row['entry_hash']
                
                # Check fragment existence
                if fid_val not in fragment_data:
                    print(f"[FAIL] Seq {seq_val}: Fragment {fid_val} missing from storage")
                    errors += 1
                    continue
                
                # Reconstruct objects
                seq = LogSequence(seq_val)
                ts = Timestamp(datetime.fromisoformat(ts_iso))
                frag = reconstruct_fragment(fragment_data[fid_val])
                
                entry = LogEntry(
                    sequence=seq,
                    fragment=frag,
                    ingestion_timestamp=ts,
                    previous_hash=prev_hash,
                    entry_hash=entry_hash
                )
                
                # Verify
                event_log.load_verified_entry(entry)
                count += 1
                
            except ValueError as ve:
                print(f"[FAIL] Integrity Error: {str(ve)}")
                errors += 1
                return # Stop on broken chain
            except Exception as e:
                print(f"[FAIL] Parse Error: {str(e)}")
                errors += 1
    
    if errors == 0:
        print(f"[PASS] Verified {count} entries. Integrity intact.")
        print(f"[INFO] HEAD Hash: {event_log.state.head_hash}")
    else:
        print(f"[FAIL] Found {errors} errors.")

def cmd_log(args):
    """Dump linear log."""
    log_path = os.path.join(args.storage_dir, "log_entries.jsonl")
    if not os.path.exists(log_path):
        print("No log.")
        return
        
    print("SEQ | TIME | TYPE | HASH | FRAGMENT")
    print("-" * 80)
    with open(log_path, 'r') as f:
        for line in f:
            row = json.loads(line)
            ts = row['ingestion_timestamp']
            print(f"{row['sequence']:<4} | {ts[:19]} | EVENT | {row['entry_hash'][:8]}... | {row['fragment_id'][:12]}...")

def load_snapshots(storage_dir: str) -> List[Dict]:
    """Load snapshots for version graph."""
    snapshots = []
    path = os.path.join(storage_dir, "snapshots.jsonl")
    if not os.path.exists(path):
        return snapshots
        
    with open(path, 'r') as f:
        for line in f:
            try:
                snapshots.append(json.loads(line))
            except:
                pass
    return snapshots

def render_ascii_dag(snapshots: List[Dict]):
    """Render ASCII DAG of versions."""
    # Build adjacency list: parent -> children
    # And map version_id -> data
    
    version_map = {}
    children = {}
    roots = []
    
    for s in snapshots:
        vid = s['version_id']['value']
        p_vid = s.get('previous_version_id')
        timestamp = s['created_at'][:19]
        thread_id = s.get('thread_id', {}).get('value', 'unknown')
        
        version_map[vid] = {
            'timestamp': timestamp,
            'thread': thread_id,
            'snapshot': s
        }
        
        if not p_vid:
            roots.append(vid)
        else:
            if p_vid not in children:
                children[p_vid] = []
            children[p_vid].append(vid)
            
    if not roots:
        print("[!] No version roots found.")
        return

    # DFS to print
    def print_tree(vid, prefix="", is_last=True):
        entry = version_map.get(vid, {'timestamp': '?', 'thread': '?', 'snapshot': {}})
        snap = entry.get('snapshot', {})
        
        # Status Tags
        tags = []
        if snap.get('absence_detected'):
            tags.append("[ABSENCE]")
        if snap.get('lifecycle_state') == "diverged":
            tags.append("[DIVERGED]")
        
        tag_str = " " + " ".join(tags) if tags else ""
        
        connector = "`-- " if is_last else "|-- "
        branch_prefix = "    " if is_last else "|   "
        
        print(f"{prefix}{connector}v: {vid[:8]}... [{entry['timestamp']}] Thread: {entry['thread'][:8]}...{tag_str}")
        
        kids = children.get(vid, [])
        for i, kid in enumerate(kids):
            print_tree(kid, prefix + branch_prefix, i == len(kids) - 1)

    print("\nVERSION LINEAGE DAG")
    print("===================")
    for root in roots:
        print_tree(root)

def cmd_versions(args):
    """Visualize version DAG."""
    print(f"[*] Loading snapshot history from: {args.storage_dir}")
    snapshots = load_snapshots(args.storage_dir)
    print(f"    Loaded {len(snapshots)} snapshots.")
    render_ascii_dag(snapshots)

def cmd_check_ui_safety(args):
    """Scan frontend code for forbidden patterns."""
    import re
    
    target_dir = args.target_dir
    print(f"[*] Scanning {target_dir} for UI Safety violations...")
    
    FORBIDDEN_PATTERNS = [
        (r"d3\.curve", "INTERPOLATION: No curve smoothing allowed."),
        (r"\.curve\(", "INTERPOLATION: No curve smoothing allowed."),
        # (r"interpolate", "INTERPOLATION: No data interpolation allowed."), # Too broad?
    ]
    
    violations = 0
    for root, _, files in os.walk(target_dir):
        for file in files:
            if not file.endswith(('.ts', '.tsx', '.js', '.jsx')):
                continue
                
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern, msg in FORBIDDEN_PATTERNS:
                    if re.search(pattern, content):
                        print(f"[VIOLATION] {path}: {msg}")
                        violations += 1
            except Exception as e:
                print(f"[WARN] Failed to read {path}: {e}")
                    
    if violations == 0:
        print("[PASS] No UI safety violations found.")
    else:
        print(f"[FAIL] Found {violations} violations.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Forensic Reporter")
    parser.add_argument("--storage-dir", default="./data/storage", help="Path to storage directory")
    
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("verify", help="Verify integrity")
    subparsers.add_parser("log", help="Dump log")
    subparsers.add_parser("versions", help="Show version DAG")
    
    safety_parser = subparsers.add_parser("check_ui_safety", help="Check UI constraints")
    safety_parser.add_argument("target_dir", help="Directory to scan")
    
    args = parser.parse_args()
    
    if args.command == "verify":
        cmd_verify(args)
    elif args.command == "log":
        cmd_log(args)
    elif args.command == "versions":
        cmd_versions(args)
    elif args.command == "check_ui_safety":
        cmd_check_ui_safety(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
