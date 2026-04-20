"""
Selector-drift telemetry — Phase 1 requirement.

Logs every page-adapter mismatch for tuning.
Tracks selector failures, DOM structure changes, and adaptation needs.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from .tracing import get_tracer


class DriftType(str, Enum):
    """Types of selector drift detected."""
    SELECTOR_NOT_FOUND = "selector_not_found"
    MULTIPLE_MATCHES = "multiple_matches"
    WRONG_ELEMENT_TYPE = "wrong_element_type"
    ATTRIBUTE_CHANGED = "attribute_changed"
    STRUCTURE_CHANGED = "structure_changed"
    PAGE_NOT_RECOGNIZED = "page_not_recognized"
    FIELD_MOVED = "field_moved"
    NEW_FIELD_DETECTED = "new_field_detected"
    FIELD_REMOVED = "field_removed"


class DriftSeverity(str, Enum):
    """Severity levels for drift events."""
    LOW = "low"           # Cosmetic, doesn't affect functionality
    MEDIUM = "medium"     # May cause issues, needs attention
    HIGH = "high"         # Breaks functionality, immediate fix needed
    CRITICAL = "critical" # Blocks entire page/flow


@dataclass
class DriftEvent:
    """A single selector drift event."""
    event_id: str
    timestamp: str
    drift_type: DriftType
    severity: DriftSeverity
    page_type: str
    selector: str
    expected: Optional[str]
    actual: Optional[str]
    dom_snapshot_hash: Optional[str]
    url: str
    user_agent: str
    recovery_attempted: bool
    recovery_successful: bool
    metadata: dict


class DriftTelemetry:
    """
    Collects and reports selector drift events.
    
    Used to:
    1. Track adapter failures in real-time
    2. Generate alerts for high-severity drift
    3. Build training data for adapter regeneration
    4. Measure adapter reliability over time
    """
    
    def __init__(self, storage_backend: Optional[Any] = None):
        self.tracer = get_tracer("drift_telemetry")
        self._events: list[DriftEvent] = []
        self._storage = storage_backend
        self._session_id: Optional[str] = None
    
    def set_session(self, session_id: str) -> None:
        """Set the current session ID for grouping events."""
        self._session_id = session_id
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        ts = datetime.now(timezone.utc).isoformat()
        return hashlib.sha256(f"{ts}-{len(self._events)}".encode()).hexdigest()[:16]
    
    def _hash_dom_snapshot(self, snapshot: Optional[str]) -> Optional[str]:
        """Create a hash of DOM snapshot for comparison."""
        if not snapshot:
            return None
        return hashlib.sha256(snapshot.encode()).hexdigest()[:32]
    
    def log_drift(
        self,
        drift_type: DriftType,
        severity: DriftSeverity,
        page_type: str,
        selector: str,
        url: str,
        user_agent: str = "",
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        dom_snapshot: Optional[str] = None,
        recovery_attempted: bool = False,
        recovery_successful: bool = False,
        metadata: Optional[dict] = None
    ) -> DriftEvent:
        """
        Log a selector drift event.
        
        Args:
            drift_type: Category of drift
            severity: Impact level
            page_type: Which portal page (e.g., "salary-schedule")
            selector: The CSS/XPath selector that failed
            url: Current page URL
            user_agent: Browser user agent
            expected: What we expected to find
            actual: What we actually found
            dom_snapshot: Optional HTML snapshot for debugging
            recovery_attempted: Whether fallback was tried
            recovery_successful: Whether fallback worked
            metadata: Additional context
        """
        with self.tracer.start_as_current_span("log_drift") as span:
            event = DriftEvent(
                event_id=self._generate_event_id(),
                timestamp=datetime.now(timezone.utc).isoformat(),
                drift_type=drift_type,
                severity=severity,
                page_type=page_type,
                selector=selector,
                expected=expected,
                actual=actual,
                dom_snapshot_hash=self._hash_dom_snapshot(dom_snapshot),
                url=url,
                user_agent=user_agent,
                recovery_attempted=recovery_attempted,
                recovery_successful=recovery_successful,
                metadata=metadata or {}
            )
            
            # Add session context
            if self._session_id:
                event.metadata["session_id"] = self._session_id
            
            self._events.append(event)
            
            # Set span attributes
            span.set_attribute("drift.type", drift_type.value)
            span.set_attribute("drift.severity", severity.value)
            span.set_attribute("drift.page", page_type)
            span.set_attribute("drift.selector", selector)
            span.set_attribute("drift.recovery_success", recovery_successful)
            
            # Log based on severity
            if severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL):
                span.set_attribute("alert", True)
                self._send_alert(event)
            
            # Persist if storage backend available
            if self._storage:
                self._persist_event(event)
            
            return event
    
    def log_selector_not_found(
        self,
        page_type: str,
        selector: str,
        url: str,
        field_name: Optional[str] = None,
        fallback_tried: bool = False,
        fallback_selector: Optional[str] = None,
        fallback_success: bool = False
    ) -> DriftEvent:
        """Convenience method for selector not found errors."""
        severity = DriftSeverity.MEDIUM
        if not fallback_tried or not fallback_success:
            severity = DriftSeverity.HIGH
        
        return self.log_drift(
            drift_type=DriftType.SELECTOR_NOT_FOUND,
            severity=severity,
            page_type=page_type,
            selector=selector,
            url=url,
            expected=f"Element matching {selector}",
            actual="No element found",
            recovery_attempted=fallback_tried,
            recovery_successful=fallback_success,
            metadata={
                "field_name": field_name,
                "fallback_selector": fallback_selector
            }
        )
    
    def log_page_not_recognized(
        self,
        url: str,
        detected_signals: dict,
        dom_snippet: Optional[str] = None
    ) -> DriftEvent:
        """Log when page detection fails."""
        return self.log_drift(
            drift_type=DriftType.PAGE_NOT_RECOGNIZED,
            severity=DriftSeverity.HIGH,
            page_type="unknown",
            selector="page-detection",
            url=url,
            dom_snapshot=dom_snippet,
            metadata={"detected_signals": detected_signals}
        )
    
    def log_structure_change(
        self,
        page_type: str,
        url: str,
        old_structure_hash: str,
        new_structure_hash: str,
        changed_regions: list[str]
    ) -> DriftEvent:
        """Log when page DOM structure changes significantly."""
        return self.log_drift(
            drift_type=DriftType.STRUCTURE_CHANGED,
            severity=DriftSeverity.MEDIUM,
            page_type=page_type,
            selector="page-structure",
            url=url,
            expected=f"Structure hash: {old_structure_hash}",
            actual=f"Structure hash: {new_structure_hash}",
            metadata={"changed_regions": changed_regions}
        )
    
    def _send_alert(self, event: DriftEvent) -> None:
        """Send alert for high-severity drift events."""
        # TODO: Integrate with alerting system (Slack, PagerDuty, etc.)
        print(f"🚨 DRIFT ALERT: {event.drift_type.value} on {event.page_type}")
        print(f"   Selector: {event.selector}")
        print(f"   Severity: {event.severity.value}")
    
    def _persist_event(self, event: DriftEvent) -> None:
        """Persist event to storage backend."""
        if self._storage:
            self._storage.write(asdict(event))
    
    def get_session_events(self) -> list[DriftEvent]:
        """Get all drift events for current session."""
        return self._events.copy()
    
    def get_statistics(self) -> dict:
        """Get drift statistics for monitoring."""
        if not self._events:
            return {
                "total_events": 0,
                "by_type": {},
                "by_severity": {},
                "by_page": {},
                "recovery_rate": 0.0
            }
        
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_page: dict[str, int] = {}
        recovery_attempts = 0
        recovery_successes = 0
        
        for event in self._events:
            by_type[event.drift_type.value] = by_type.get(event.drift_type.value, 0) + 1
            by_severity[event.severity.value] = by_severity.get(event.severity.value, 0) + 1
            by_page[event.page_type] = by_page.get(event.page_type, 0) + 1
            
            if event.recovery_attempted:
                recovery_attempts += 1
                if event.recovery_successful:
                    recovery_successes += 1
        
        return {
            "total_events": len(self._events),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_page": by_page,
            "recovery_rate": recovery_successes / recovery_attempts if recovery_attempts > 0 else 0.0,
            "session_id": self._session_id
        }
    
    def export_for_training(self) -> list[dict]:
        """
        Export drift events in format suitable for adapter retraining.
        Used by portal-drift autopilot.
        """
        return [
            {
                "page_type": e.page_type,
                "selector": e.selector,
                "drift_type": e.drift_type.value,
                "url": e.url,
                "dom_hash": e.dom_snapshot_hash,
                "timestamp": e.timestamp
            }
            for e in self._events
            if e.drift_type in (
                DriftType.SELECTOR_NOT_FOUND,
                DriftType.STRUCTURE_CHANGED,
                DriftType.FIELD_MOVED
            )
        ]


# Global instance
_drift_telemetry: Optional[DriftTelemetry] = None


def get_drift_telemetry() -> DriftTelemetry:
    """Get or create the global drift telemetry instance."""
    global _drift_telemetry
    if _drift_telemetry is None:
        _drift_telemetry = DriftTelemetry()
    return _drift_telemetry


def log_selector_drift(
    page_type: str,
    selector: str,
    url: str,
    **kwargs
) -> DriftEvent:
    """Convenience function to log selector drift."""
    return get_drift_telemetry().log_selector_not_found(
        page_type=page_type,
        selector=selector,
        url=url,
        **kwargs
    )
