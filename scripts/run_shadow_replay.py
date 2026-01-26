import sys
import os

# Ensure project root in path
sys.path.append(os.getcwd())

from backend.shadow.storage.shadow_event_log import ShadowEventLog
from backend.shadow.replay.shadow_replay_context import ShadowReplayContext

def run_shadow_replay():
    print("[*] Loading Shadow Event Log...")
    log = ShadowEventLog()
    events = log.all_events()
    
    if not events:
        print("[!] No events found in shadow log. Run ingestion first.")
        return

    print(f"[*] Replaying {len(events)} events deterministicly...")
    
    context = ShadowReplayContext()
    final_state = context.replay(events)
    
    print("\n" + "="*60)
    print("FORENSIC OBSERVATION LEDGER (SHADOW MODE)")
    print("="*60)
    
    if not final_state or not final_state.threads:
        print("No threads emerged.")
    else:
        print(f"Total Threads: {len(final_state.threads)}")
        print("\n| Thread ID | Lifecycle | Absences | Last Activity |")
        print("| :--- | :--- | :--- | :--- |")
        
        for thread in final_state.threads:
            absences = len(thread.absence_markers)
            last_act = thread.last_activity.to_iso() if thread.last_activity else "N/A"
            print(f"| `{thread.thread_id.value}` | `{thread.lifecycle_state.name}` | {absences} | `{last_act}` |")

    # Anomaly Detection (Simple Heuristics)
    print("\n[!] Anomalies & Signals")
    # Check for Vanished threads that received late updates (requires deeper inspection of log vs state)
    # For now, just listing Vanished threads
    vanished = [t for t in final_state.threads if t.lifecycle_state.name == "TERMINATED"]
    if vanished:
        print(f"- Vanished Threads: {len(vanished)}")
        for t in vanished:
            print(f"  - {t.thread_id.value} (TERMINATED)")
    
    # Check for Resurrected threads (more than 1 absence block)
    resurrected = [t for t in final_state.threads if len(t.absence_markers) > 0]
    if resurrected:
        print(f"- Resurrected Threads (Scarred): {len(resurrected)}")
        for t in resurrected:
             print(f"  - {t.thread_id.value}: {len(t.absence_markers)} scars")

if __name__ == "__main__":
    run_shadow_replay()
