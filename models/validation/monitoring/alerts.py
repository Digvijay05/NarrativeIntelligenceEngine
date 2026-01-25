"""Alert management."""

from __future__ import annotations
from typing import List, Dict
from datetime import datetime

from ...contracts.validation_contracts import DriftAlert, AlertSeverity


class AlertManager:
    """Manage alerts from monitoring."""
    
    def __init__(self):
        self._alerts: List[DriftAlert] = []
        self._acknowledged: set = set()
    
    def add_alert(self, alert: DriftAlert):
        """Add an alert."""
        if alert:
            self._alerts.append(alert)
    
    def get_active_alerts(self) -> List[DriftAlert]:
        """Get all unacknowledged alerts."""
        return [a for a in self._alerts if a.alert_id not in self._acknowledged]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[DriftAlert]:
        """Get alerts by severity level."""
        return [a for a in self._alerts if a.severity == severity]
    
    def acknowledge(self, alert_id: str):
        """Acknowledge an alert."""
        self._acknowledged.add(alert_id)
    
    def get_summary(self) -> Dict[str, int]:
        """Get alert summary by severity."""
        active = self.get_active_alerts()
        return {
            'critical': sum(1 for a in active if a.severity == AlertSeverity.CRITICAL),
            'error': sum(1 for a in active if a.severity == AlertSeverity.ERROR),
            'warning': sum(1 for a in active if a.severity == AlertSeverity.WARNING),
            'info': sum(1 for a in active if a.severity == AlertSeverity.INFO),
        }
