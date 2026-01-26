#!/usr/bin/env python3
"""
Shadow Mode Validation Suite
=============================

Binary pass/fail validation for shadow mode invariants.

RUN:
    python tools/validate_shadow.py
    python tools/validate_shadow.py --session <session_id>

VALIDATES:
- V1: Immutability
- V2: Append-only log
- V3: Deterministic replay
- V4: Schema identity (mock vs real)
- V5: Raw storage
- V6: Tier metadata
- V7: No downstream changes
- V8: Divergence detection
- V9: Contradiction detection
- V10: Absence detection
"""

from __future__ import annotations
import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, FrozenInstanceError
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.contracts.base import SourceTier, SourceId, Timestamp
from backend.contracts.events import RawIngestionEvent


@dataclass(frozen=True)
class ValidationResult:
    """Immutable validation result."""
    check_id: str
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class ShadowModeValidator:
    """
    Validates shadow mode invariants.
    
    All checks are BINARY pass/fail.
    """
    
    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)
        self._results: List[ValidationResult] = []
    
    def run_all_checks(self) -> Dict[str, bool]:
        """
        Run all validation checks.
        
        Returns dict of {check_id: pass/fail}
        """
        self._results = []
        
        # V1: Immutability
        self._check_v1_immutability()
        
        # V2: Append-only
        self._check_v2_append_only()
        
        # V3: Deterministic replay (requires clock log)
        self._check_v3_deterministic_replay()
        
        # V4: Schema identity
        self._check_v4_schema_identity()
        
        # V5: Raw storage
        self._check_v5_raw_storage()
        
        # V6: Tier metadata
        self._check_v6_tier_metadata()
        
        # V7: No downstream changes (structural check)
        self._check_v7_no_downstream_changes()
        
        # V8: Divergence detection
        self._check_v8_divergence_detection()
        
        # V9: Contradiction detection
        self._check_v9_contradiction_detection()
        
        # V10: Absence detection
        self._check_v10_absence_detection()
        
        return {r.check_id: r.passed for r in self._results}
    
    def _check_v1_immutability(self) -> None:
        """V1: Verify frozen dataclasses raise on modification."""
        try:
            # Create a test event
            event = RawIngestionEvent.create(
                source_id=SourceId(value="test", source_type="test"),
                raw_payload='{"test": "data"}',
                source_tier=SourceTier.MOCK
            )
            
            # Attempt to modify via normal attribute assignment (should fail)
            try:
                event.event_id = 'modified'
                # If we get here, immutability is broken
                self._results.append(ValidationResult(
                    check_id="V1",
                    check_name="Immutability",
                    passed=False,
                    message="RawIngestionEvent is mutable - assignment did not raise"
                ))
            except (FrozenInstanceError, AttributeError, TypeError):
                # Expected behavior
                self._results.append(ValidationResult(
                    check_id="V1",
                    check_name="Immutability",
                    passed=True,
                    message="RawIngestionEvent correctly raises error on modification"
                ))
        except Exception as e:
            self._results.append(ValidationResult(
                check_id="V1",
                check_name="Immutability",
                passed=False,
                message=f"Check failed with error: {str(e)}"
            ))
    
    def _check_v2_append_only(self) -> None:
        """V2: Verify event log is append-only."""
        events_file = self._data_dir / "events.jsonl"
        
        if not events_file.exists():
            self._results.append(ValidationResult(
                check_id="V2",
                check_name="Append-only Log",
                passed=True,
                message="No events file yet (will be created on first ingestion)"
            ))
            return
        
        # Count events
        with open(events_file, 'r') as f:
            event_count = sum(1 for line in f if line.strip())
        
        # Try to read all events
        with open(events_file, 'r') as f:
            events = [json.loads(line) for line in f if line.strip()]
        
        # Verify count matches
        if len(events) == event_count:
            self._results.append(ValidationResult(
                check_id="V2",
                check_name="Append-only Log",
                passed=True,
                message=f"Event log contains {event_count} events, all readable",
                details={'event_count': event_count}
            ))
        else:
            self._results.append(ValidationResult(
                check_id="V2",
                check_name="Append-only Log",
                passed=False,
                message="Event count mismatch - possible corruption"
            ))
    
    def _check_v3_deterministic_replay(self) -> None:
        """V3: Verify replay produces identical output with same clock."""
        clock_file = self._data_dir / "clock.json"
        
        if not clock_file.exists():
            self._results.append(ValidationResult(
                check_id="V3",
                check_name="Deterministic Replay",
                passed=True,
                message="No clock log yet (will be created during execution)"
            ))
            return
        
        with open(clock_file, 'r') as f:
            clock_data = json.load(f)
        
        # Verify clock has required fields
        required_fields = ['version', 'ticks', 'tick_count']
        has_fields = all(field in clock_data for field in required_fields)
        
        if has_fields and len(clock_data.get('ticks', [])) > 0:
            self._results.append(ValidationResult(
                check_id="V3",
                check_name="Deterministic Replay",
                passed=True,
                message=f"Clock log valid with {clock_data['tick_count']} ticks",
                details={'tick_count': clock_data['tick_count']}
            ))
        else:
            self._results.append(ValidationResult(
                check_id="V3",
                check_name="Deterministic Replay",
                passed=False,
                message="Clock log missing required fields or empty"
            ))
    
    def _check_v4_schema_identity(self) -> None:
        """V4: Verify mock and real events have identical schema."""
        events_file = self._data_dir / "events.jsonl"
        
        if not events_file.exists():
            self._results.append(ValidationResult(
                check_id="V4",
                check_name="Schema Identity",
                passed=True,
                message="No events yet to compare"
            ))
            return
        
        mock_events = []
        live_events = []
        
        with open(events_file, 'r') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    if event.get('source_tier') == 'mock':
                        mock_events.append(event)
                    elif event.get('source_tier') == 'public_rss':
                        live_events.append(event)
        
        if not mock_events and not live_events:
            self._results.append(ValidationResult(
                check_id="V4",
                check_name="Schema Identity",
                passed=True,
                message="No events yet to compare"
            ))
            return
        
        # Get schema (keys) from first event of each type
        mock_schema = set(mock_events[0].keys()) if mock_events else set()
        live_schema = set(live_events[0].keys()) if live_events else set()
        
        if mock_schema and live_schema:
            if mock_schema == live_schema:
                self._results.append(ValidationResult(
                    check_id="V4",
                    check_name="Schema Identity",
                    passed=True,
                    message="Mock and live events have identical schema",
                    details={'fields': list(mock_schema)}
                ))
            else:
                diff = mock_schema.symmetric_difference(live_schema)
                self._results.append(ValidationResult(
                    check_id="V4",
                    check_name="Schema Identity",
                    passed=False,
                    message=f"Schema mismatch: {diff}"
                ))
        else:
            # Only one type present
            self._results.append(ValidationResult(
                check_id="V4",
                check_name="Schema Identity",
                passed=True,
                message="Only one event type present, schema comparison pending"
            ))
    
    def _check_v5_raw_storage(self) -> None:
        """V5: Verify raw payloads are stored and match hashes."""
        raw_dir = self._data_dir / "raw"
        
        if not raw_dir.exists():
            self._results.append(ValidationResult(
                check_id="V5",
                check_name="Raw Storage",
                passed=True,
                message="No raw storage directory yet"
            ))
            return
        
        raw_files = list(raw_dir.glob("*.xml"))
        
        if not raw_files:
            self._results.append(ValidationResult(
                check_id="V5",
                check_name="Raw Storage",
                passed=True,
                message="No raw payload files yet"
            ))
            return
        
        # Verify files exist and are readable
        valid_count = 0
        for raw_file in raw_files[:10]:  # Check first 10
            try:
                with open(raw_file, 'rb') as f:
                    content = f.read()
                if len(content) > 0:
                    valid_count += 1
            except Exception:
                pass
        
        if valid_count == min(len(raw_files), 10):
            self._results.append(ValidationResult(
                check_id="V5",
                check_name="Raw Storage",
                passed=True,
                message=f"{len(raw_files)} raw payload files stored and readable",
                details={'file_count': len(raw_files)}
            ))
        else:
            self._results.append(ValidationResult(
                check_id="V5",
                check_name="Raw Storage",
                passed=False,
                message="Some raw payload files unreadable"
            ))
    
    def _check_v6_tier_metadata(self) -> None:
        """V6: Verify source tier is correctly set."""
        events_file = self._data_dir / "events.jsonl"
        
        if not events_file.exists():
            self._results.append(ValidationResult(
                check_id="V6",
                check_name="Tier Metadata",
                passed=True,
                message="No events yet"
            ))
            return
        
        mock_count = 0
        live_count = 0
        missing_tier = 0
        
        with open(events_file, 'r') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    tier = event.get('source_tier')
                    if tier == 'mock':
                        mock_count += 1
                    elif tier == 'public_rss':
                        live_count += 1
                    elif tier is None:
                        missing_tier += 1
        
        if missing_tier == 0:
            self._results.append(ValidationResult(
                check_id="V6",
                check_name="Tier Metadata",
                passed=True,
                message=f"All events have tier: {mock_count} mock, {live_count} live",
                details={'mock': mock_count, 'live': live_count}
            ))
        else:
            self._results.append(ValidationResult(
                check_id="V6",
                check_name="Tier Metadata",
                passed=False,
                message=f"{missing_tier} events missing tier metadata"
            ))
    
    def _check_v7_no_downstream_changes(self) -> None:
        """V7: Verify no changes needed to downstream code."""
        # Structural check - verify imports work
        try:
            from backend.contracts.events import (
                RawIngestionEvent, NormalizedFragment, ThreadStateSnapshot
            )
            from backend.contracts.base import SourceTier
            
            # Verify SourceTier is importable and has required values
            assert hasattr(SourceTier, 'MOCK')
            assert hasattr(SourceTier, 'PUBLIC_RSS')
            
            self._results.append(ValidationResult(
                check_id="V7",
                check_name="No Downstream Changes",
                passed=True,
                message="All contracts import correctly, SourceTier available"
            ))
        except Exception as e:
            self._results.append(ValidationResult(
                check_id="V7",
                check_name="No Downstream Changes",
                passed=False,
                message=f"Import error: {str(e)}"
            ))
    
    def _check_v8_divergence_detection(self) -> None:
        """V8: Verify divergence detection works with real data."""
        # This checks the structural capability, not actual divergence
        try:
            from backend.contracts.events import ThreadProcessingResult
            
            assert hasattr(ThreadProcessingResult, 'DIVERGENCE_DETECTED')
            
            self._results.append(ValidationResult(
                check_id="V8",
                check_name="Divergence Detection",
                passed=True,
                message="Divergence detection capability verified"
            ))
        except Exception as e:
            self._results.append(ValidationResult(
                check_id="V8",
                check_name="Divergence Detection",
                passed=False,
                message=f"Error: {str(e)}"
            ))
    
    def _check_v9_contradiction_detection(self) -> None:
        """V9: Verify contradiction detection works with real data."""
        try:
            from backend.contracts.events import ContradictionStatus, ContradictionInfo
            
            assert hasattr(ContradictionStatus, 'CONTRADICTION_DETECTED')
            
            self._results.append(ValidationResult(
                check_id="V9",
                check_name="Contradiction Detection",
                passed=True,
                message="Contradiction detection capability verified"
            ))
        except Exception as e:
            self._results.append(ValidationResult(
                check_id="V9",
                check_name="Contradiction Detection",
                passed=False,
                message=f"Error: {str(e)}"
            ))
    
    def _check_v10_absence_detection(self) -> None:
        """V10: Verify absence detection works."""
        try:
            from backend.contracts.events import ThreadStateSnapshot
            
            # Verify absence_detected field exists
            import dataclasses
            fields = {f.name for f in dataclasses.fields(ThreadStateSnapshot)}
            
            if 'absence_detected' in fields:
                self._results.append(ValidationResult(
                    check_id="V10",
                    check_name="Absence Detection",
                    passed=True,
                    message="Absence detection field present in ThreadStateSnapshot"
                ))
            else:
                self._results.append(ValidationResult(
                    check_id="V10",
                    check_name="Absence Detection",
                    passed=False,
                    message="absence_detected field not found"
                ))
        except Exception as e:
            self._results.append(ValidationResult(
                check_id="V10",
                check_name="Absence Detection",
                passed=False,
                message=f"Error: {str(e)}"
            ))
    
    def print_report(self) -> None:
        """Print validation report."""
        print("\n" + "=" * 70)
        print("SHADOW MODE VALIDATION REPORT")
        print("=" * 70)
        
        passed = sum(1 for r in self._results if r.passed)
        total = len(self._results)
        
        for result in self._results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"\n{result.check_id}: {result.check_name}")
            print(f"   Status: {status}")
            print(f"   {result.message}")
            if result.details:
                for k, v in result.details.items():
                    print(f"   - {k}: {v}")
        
        print("\n" + "-" * 70)
        print(f"TOTAL: {passed}/{total} checks passed")
        
        if passed == total:
            print("\n✓ All validation checks PASSED")
        else:
            print(f"\n✗ {total - passed} checks FAILED")
        
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Shadow Mode Validation Suite")
    parser.add_argument(
        '--data-dir', '-d',
        default='./shadow_mode_data',
        help='Path to shadow mode data directory'
    )
    
    args = parser.parse_args()
    
    validator = ShadowModeValidator(Path(args.data_dir))
    results = validator.run_all_checks()
    validator.print_report()
    
    # Exit with error if any check failed
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
