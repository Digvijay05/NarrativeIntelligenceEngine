import argparse
import sys
from backend.shadow.rss.source_config import SHADOW_RSS_SOURCES
from backend.shadow.rss.poller import shadow_tick_generator, get_next_tick_from_log
from backend.shadow.rss.fetch import fetch_rss_bytes
from backend.shadow.rss.emit import emit_raw_shadow_event
from backend.shadow.storage.shadow_event_log import ShadowEventLog

def run_shadow_rss_ingestion(single_tick_mode: bool = False):
    log = ShadowEventLog()
    
    if single_tick_mode:
        # State-aware single run
        # Derive next tick from persistent log
        events = log.all_events()
        next_tick = get_next_tick_from_log(events)
        print(f"[*] Single Tick Mode. Next Tick: {next_tick}")
        
        # Process each source exactly once for this tick
        count = 0
        for source in SHADOW_RSS_SOURCES:
            try:
                raw_bytes = fetch_rss_bytes(source.feed_url)
                event = emit_raw_shadow_event(
                    source_id=source.source_id,
                    raw_payload=raw_bytes,
                    published_timestamp=None,
                    poll_tick_id=next_tick,
                )
                log.append(event)
                print(f"[{source.source_id}] Poll {next_tick}: Ingested {len(raw_bytes)} bytes.")
                count += 1
            except Exception as e:
                print(f"[{source.source_id}] Poll {next_tick}: Error {e}")
        
        print(f"[*] Tick {next_tick} Complete. Ingested {count} events.")
            
    else:
        # Original infinite loop (Stateless per run, assumes continuous runner)
        print("[*] Starting Continuous Ingestion Loop...")
        for source in SHADOW_RSS_SOURCES:
             tick_gen = shadow_tick_generator(source.poll_interval_seconds)

             for tick in tick_gen:
                try:
                    raw_bytes = fetch_rss_bytes(source.feed_url)
                    event = emit_raw_shadow_event(
                        source_id=source.source_id,
                        raw_payload=raw_bytes,
                        published_timestamp=None,
                        poll_tick_id=tick,
                    )
                    log.append(event)
                    print(f"[{source.source_id}] Poll {tick}: Ingested {len(raw_bytes)} bytes.")
                except Exception as e:
                    print(f"[{source.source_id}] Poll {tick}: Error {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shadow RSS Ingestion")
    parser.add_argument("--single-tick", action="store_true", help="Run one logical tick and exit (for Cron/CI).")
    args = parser.parse_args()

    try:
        run_shadow_rss_ingestion(single_tick_mode=args.single_tick)
    except KeyboardInterrupt:
        print("\nShadow Ingestion Stopped.")
