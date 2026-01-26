#!/usr/bin/env python3
"""
Shadow Mode Demo
================

Demonstrates parallel mock + real RSS ingestion.

RUN:
    python shadow_mode_demo.py
    python shadow_mode_demo.py --mode live-only
    python shadow_mode_demo.py --mode mock-only
    python shadow_mode_demo.py --mode shadow

VALIDATES:
- Real RSS ingestion works identically to mock
- Both tiers flow into same append-only log
- Source tier distinguishes origin
- No downstream code changes required
"""

from __future__ import annotations
import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.contracts.base import SourceId, SourceTier
from backend.ingestion.live_rss_adapter import LiveRSSAdapter
from backend.ingestion.shadow_engine import (
    ShadowIngestionEngine, 
    FileBasedEventLog,
    SourceFilterDTO,
    SourceTierFilter
)
from backend.temporal.clock import LogicalClock


def load_config(config_path: Path) -> dict:
    """Load feed configuration."""
    with open(config_path, 'r') as f:
        return json.load(f)


class MockAdapter:
    """
    Simple mock adapter for demonstration.
    
    Generates synthetic events with MOCK tier.
    """
    
    def __init__(self):
        self._mock_data = [
            {
                'title': 'Mock Article 1: Government announces new policy',
                'link': 'https://mock.example.com/article-1',
                'description': 'Test description for mock article 1',
                'published_at': datetime.now(timezone.utc).isoformat()
            },
            {
                'title': 'Mock Article 2: Economy shows growth',
                'link': 'https://mock.example.com/article-2', 
                'description': 'Test description for mock article 2',
                'published_at': datetime.now(timezone.utc).isoformat()
            },
            {
                'title': 'Mock Article 3: Technology sector updates',
                'link': 'https://mock.example.com/article-3',
                'description': 'Test description for mock article 3',
                'published_at': datetime.now(timezone.utc).isoformat()
            }
        ]
    
    @property
    def source_type(self) -> str:
        return "mock"
    
    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.MOCK
    
    def pull_events(self, source_id, since=None):
        """Generate mock events."""
        from backend.contracts.events import RawIngestionEvent
        
        for item in self._mock_data:
            payload = json.dumps(item, ensure_ascii=False)
            
            yield RawIngestionEvent.create(
                source_id=source_id,
                raw_payload=payload,
                source_confidence=1.0,
                source_tier=SourceTier.MOCK
            )


def run_shadow_demo(mode: str, config_path: Path, data_dir: Path):
    """
    Run shadow mode demonstration.
    
    Args:
        mode: 'shadow', 'live-only', or 'mock-only'
        config_path: Path to feed configuration
        data_dir: Output directory
    """
    print("\n" + "=" * 70)
    print("SHADOW MODE DEMONSTRATION")
    print("=" * 70)
    print(f"\nMode: {mode.upper()}")
    print(f"Config: {config_path}")
    print(f"Data: {data_dir}")
    
    # Ensure directories
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize clock
    clock = LogicalClock.live()
    
    # Load config
    config = load_config(config_path)
    
    # Initialize adapters
    mock_adapter = MockAdapter()
    live_adapter = LiveRSSAdapter(
        config=config,
        storage_dir=data_dir,
        logical_clock=clock
    )
    
    # Initialize event log
    event_log = FileBasedEventLog(data_dir)
    
    # Initialize shadow engine
    engine = ShadowIngestionEngine(
        mock_adapter=mock_adapter,
        live_adapter=live_adapter,
        event_log=event_log,
        clock=clock
    )
    
    # Define sources
    mock_sources = [SourceId(value="mock_source", source_type="mock")]
    live_sources = live_adapter.get_all_source_ids()[:5]  # First 5 sources
    
    print(f"\nMock sources: {len(mock_sources)}")
    print(f"Live sources: {len(live_sources)}")
    
    # Run based on mode
    if mode == "shadow":
        print("\n--- Running SHADOW mode (both mock + live) ---")
        session = engine.run_shadow_session(mock_sources, live_sources)
    elif mode == "live-only":
        print("\n--- Running LIVE-ONLY mode ---")
        session = engine.run_live_only(live_sources)
    elif mode == "mock-only":
        print("\n--- Running MOCK-ONLY mode ---")
        session = engine.run_mock_only(mock_sources)
    else:
        print(f"Unknown mode: {mode}")
        return
    
    # Print results
    print("\n" + "-" * 70)
    print("SESSION RESULTS")
    print("-" * 70)
    
    if session.stats:
        print(f"\n  Session ID: {session.session_id}")
        print(f"  Duration: {session.stats.session_duration_ms:.1f} ms")
        print(f"\n  Events ingested:")
        print(f"    - Mock: {session.stats.mock_event_count}")
        print(f"    - Live: {session.stats.live_event_count}")
        print(f"    - Total bytes: {session.stats.total_bytes_ingested:,}")
    
    # Print log stats
    stats = engine.get_log_stats()
    print(f"\n  Event Log Stats:")
    print(f"    - Total events: {stats['total_events']}")
    print(f"    - Mock tier: {stats['mock_events']}")
    print(f"    - Live tier: {stats['live_events']}")
    
    # Demonstrate filtering
    print("\n" + "-" * 70)
    print("FILTERING DEMONSTRATION")
    print("-" * 70)
    
    # Show filtering capability
    mock_filter = SourceFilterDTO(tier_filter=SourceTierFilter.MOCK)
    live_filter = SourceFilterDTO(tier_filter=SourceTierFilter.PUBLIC_RSS)
    all_filter = SourceFilterDTO(tier_filter=SourceTierFilter.ALL)
    
    print(f"\n  Mock filter matches MOCK tier: {mock_filter.matches(SourceTier.MOCK)}")
    print(f"  Mock filter matches PUBLIC_RSS tier: {mock_filter.matches(SourceTier.PUBLIC_RSS)}")
    print(f"  Live filter matches MOCK tier: {live_filter.matches(SourceTier.MOCK)}")
    print(f"  Live filter matches PUBLIC_RSS tier: {live_filter.matches(SourceTier.PUBLIC_RSS)}")
    print(f"  All filter matches both: {all_filter.matches(SourceTier.MOCK)} / {all_filter.matches(SourceTier.PUBLIC_RSS)}")
    
    # Save clock for replay
    clock.save_log(data_dir / "clock.json")
    
    print("\n" + "-" * 70)
    print("REPLAY CAPABILITY")
    print("-" * 70)
    print(f"\n  Clock log saved to: {data_dir / 'clock.json'}")
    print(f"  Events log: {data_dir / 'events.jsonl'}")
    print(f"  Raw payloads: {data_dir / 'raw'}/")
    print(f"\n  To replay: Use LogicalClock.from_log() with same raw data")
    
    # Footer
    print("\n" + "=" * 70)
    print("Shadow mode demo complete. Review events.jsonl for tier-tagged events.")
    print("=" * 70 + "\n")
    
    return session


def main():
    parser = argparse.ArgumentParser(
        description="Shadow Mode Demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['shadow', 'live-only', 'mock-only'],
        default='shadow',
        help='Ingestion mode'
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/live_feeds.json',
        help='Path to feed configuration'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='./shadow_mode_data',
        help='Output directory'
    )
    
    args = parser.parse_args()
    
    # Find config
    config_path = Path(args.config)
    if not config_path.exists():
        script_dir = Path(__file__).parent
        config_path = script_dir / args.config
        if not config_path.exists():
            print(f"Error: Config not found at {args.config}")
            sys.exit(1)
    
    run_shadow_demo(
        mode=args.mode,
        config_path=config_path,
        data_dir=Path(args.output)
    )


if __name__ == "__main__":
    main()
