"""
Recovery node — Phase 3 requirement.

Handles selector breaks and portal changes:
1. Detect when a selector doesn't match
2. Try fallback selectors
3. Ask user to click-to-teach if all else fails
4. Persist learned mappings for future use
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import hashlib
import json

from ..state import AgentState


class RecoveryStrategy(str, Enum):
    FUZZY_MATCH = "fuzzy_match"           # Try similar selectors
    LABEL_SEARCH = "label_search"         # Find by label text
    POSITION_BASED = "position_based"     # Use relative position
    USER_CLICK = "user_click"             # Ask user to click
    SKIP = "skip"                         # Skip this field
    ABORT = "abort"                       # Abort the fill operation


class RecoveryStatus(str, Enum):
    PENDING = "pending"
    ATTEMPTING = "attempting"
    RESOLVED = "resolved"
    USER_HELP_NEEDED = "user_help_needed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class SelectorFailure:
    """Record of a failed selector."""
    failure_id: str
    original_selector: str
    field_id: str
    field_label: str
    page_type: str
    error_type: str  # not_found, multiple_matches, wrong_type, etc.
    timestamp: str
    dom_snapshot_hash: Optional[str] = None
    

@dataclass
class RecoveryAttempt:
    """A single recovery attempt."""
    strategy: RecoveryStrategy
    selector_tried: str
    success: bool
    element_found: bool
    element_matches: int
    timestamp: str


@dataclass
class LearnedMapping:
    """A user-taught selector mapping."""
    mapping_id: str
    field_id: str
    field_label: str
    page_type: str
    original_selector: str
    learned_selector: str
    learned_from: str  # 'user_click', 'fuzzy_match', etc.
    confidence: float
    created_at: str
    last_used: str
    use_count: int = 1


@dataclass
class RecoveryResult:
    """Result of recovery operation."""
    failure: SelectorFailure
    status: RecoveryStatus
    attempts: list[RecoveryAttempt] = field(default_factory=list)
    resolved_selector: Optional[str] = None
    learned_mapping: Optional[LearnedMapping] = None
    user_action_required: bool = False
    user_instructions: Optional[str] = None


# Fallback selector patterns
FALLBACK_PATTERNS = {
    # Pattern: (attribute, template)
    "id": [("id", "#{value}")],
    "name": [("name", "[name='{value}']")],
    "data-field": [("data-field", "[data-field='{value}']")],
    "aria-label": [("aria-label", "[aria-label*='{label}']")],
    "placeholder": [("placeholder", "[placeholder*='{label}']")],
    "label-for": [("label", "label:contains('{label}') + input, label:contains('{label}') ~ input")],
}


def generate_failure_id() -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return hashlib.sha256(ts.encode()).hexdigest()[:12]


def generate_mapping_id(field_id: str, page_type: str) -> str:
    data = f"{field_id}-{page_type}"
    return hashlib.sha256(data.encode()).hexdigest()[:12]


def generate_fallback_selectors(field_id: str, field_label: str) -> list[str]:
    """Generate fallback selectors to try."""
    fallbacks = []
    
    # Try ID variations
    id_variations = [
        field_id,
        field_id.replace("_", "-"),
        field_id.replace("-", "_"),
        field_id.lower(),
        f"txt{field_id}",
        f"input{field_id}",
    ]
    for var in id_variations:
        fallbacks.append(f"#{var}")
        fallbacks.append(f"[id*='{var}']")
    
    # Try name attribute
    fallbacks.append(f"[name='{field_id}']")
    fallbacks.append(f"[name*='{field_id}']")
    
    # Try data attributes
    fallbacks.append(f"[data-field='{field_id}']")
    fallbacks.append(f"[data-name='{field_id}']")
    
    # Try label-based (case insensitive approximation)
    label_words = field_label.lower().split()
    if label_words:
        fallbacks.append(f"input[aria-label*='{label_words[0]}']")
        fallbacks.append(f"input[placeholder*='{label_words[0]}']")
    
    return fallbacks


def create_user_click_instructions(field_label: str, field_id: str) -> str:
    """Create instructions for user to click-to-teach."""
    return (
        f"I couldn't find the field '{field_label}' on this page.\n\n"
        f"**Please help me learn:**\n"
        f"1. Click on the input field for '{field_label}'\n"
        f"2. I'll remember this for next time\n\n"
        f"Or click 'Skip' to skip this field, or 'Abort' to stop filling."
    )


async def recovery(state: AgentState) -> dict[str, Any]:
    """
    Recovery node — handles selector failures.
    
    Phase 3 requirement:
    1. Try fallback selectors
    2. Ask user for help if needed
    3. Learn and persist new mappings
    """
    # Get failure context
    selector_failure = state.get("selector_failure")
    learned_mappings = state.get("learned_mappings", {})
    user_click_response = state.get("user_click_response")
    
    if not selector_failure:
        # No failure to recover from
        return {
            "messages": state.get("messages", []),
            "recovery_status": "no_failure"
        }
    
    field_id = selector_failure.get("field_id", "")
    field_label = selector_failure.get("field_label", "")
    page_type = selector_failure.get("page_type", "")
    original_selector = selector_failure.get("selector", "")
    
    failure = SelectorFailure(
        failure_id=generate_failure_id(),
        original_selector=original_selector,
        field_id=field_id,
        field_label=field_label,
        page_type=page_type,
        error_type=selector_failure.get("error_type", "not_found"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    result = RecoveryResult(
        failure=failure,
        status=RecoveryStatus.ATTEMPTING,
    )
    
    # Check if we have a learned mapping for this field
    mapping_key = f"{page_type}:{field_id}"
    if mapping_key in learned_mappings:
        learned = learned_mappings[mapping_key]
        result.resolved_selector = learned.get("selector")
        result.status = RecoveryStatus.RESOLVED
        
        messages = state.get("messages", [])
        messages.append({
            "role": "assistant",
            "content": f"✅ Using learned selector for '{field_label}'",
            "metadata": {"node": "recovery", "used_learned": True}
        })
        
        return {
            "messages": messages,
            "recovery_result": {
                "status": "resolved",
                "selector": result.resolved_selector,
                "method": "learned_mapping"
            },
            "selector_failure": None  # Clear the failure
        }
    
    # Check if user provided a click response
    if user_click_response:
        clicked_selector = user_click_response.get("selector")
        if clicked_selector:
            # Learn the new mapping
            new_mapping = LearnedMapping(
                mapping_id=generate_mapping_id(field_id, page_type),
                field_id=field_id,
                field_label=field_label,
                page_type=page_type,
                original_selector=original_selector,
                learned_selector=clicked_selector,
                learned_from="user_click",
                confidence=1.0,  # User-taught is highest confidence
                created_at=datetime.now(timezone.utc).isoformat(),
                last_used=datetime.now(timezone.utc).isoformat(),
            )
            
            result.resolved_selector = clicked_selector
            result.learned_mapping = new_mapping
            result.status = RecoveryStatus.RESOLVED
            
            # Update learned mappings
            updated_mappings = dict(learned_mappings)
            updated_mappings[mapping_key] = {
                "selector": clicked_selector,
                "learned_from": "user_click",
                "created_at": new_mapping.created_at,
            }
            
            messages = state.get("messages", [])
            messages.append({
                "role": "assistant",
                "content": f"✅ Learned new selector for '{field_label}'. I'll remember this!",
                "metadata": {"node": "recovery", "learned_new": True}
            })
            
            return {
                "messages": messages,
                "recovery_result": {
                    "status": "resolved",
                    "selector": clicked_selector,
                    "method": "user_click"
                },
                "learned_mappings": updated_mappings,
                "selector_failure": None,
                "user_click_response": None
            }
        elif user_click_response.get("action") == "skip":
            result.status = RecoveryStatus.SKIPPED
            messages = state.get("messages", [])
            messages.append({
                "role": "assistant",
                "content": f"⏭️ Skipping field '{field_label}'",
                "metadata": {"node": "recovery", "skipped": True}
            })
            return {
                "messages": messages,
                "recovery_result": {"status": "skipped"},
                "selector_failure": None,
                "user_click_response": None
            }
        elif user_click_response.get("action") == "abort":
            result.status = RecoveryStatus.FAILED
            messages = state.get("messages", [])
            messages.append({
                "role": "assistant",
                "content": f"🛑 Fill operation aborted",
                "metadata": {"node": "recovery", "aborted": True}
            })
            return {
                "messages": messages,
                "recovery_result": {"status": "aborted"},
                "selector_failure": None,
                "user_click_response": None,
                "fill_aborted": True
            }
    
    # Try fallback selectors
    fallbacks = generate_fallback_selectors(field_id, field_label)
    
    # We'll emit these as candidates to try
    # The actual testing happens in the extension
    result.status = RecoveryStatus.USER_HELP_NEEDED
    result.user_action_required = True
    result.user_instructions = create_user_click_instructions(field_label, field_id)
    
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": (
            f"## ⚠️ Field Not Found\n\n"
            f"{result.user_instructions}\n\n"
            f"**Field ID:** `{field_id}`\n"
            f"**Original selector:** `{original_selector}`"
        ),
        "metadata": {
            "node": "recovery",
            "awaiting_user_click": True,
            "field_id": field_id,
            "fallback_selectors": fallbacks[:5]  # Send top 5 to try
        }
    })
    
    return {
        "messages": messages,
        "recovery_result": {
            "status": "awaiting_user_help",
            "field_id": field_id,
            "field_label": field_label,
            "fallback_selectors": fallbacks,
        },
        "awaiting_user_click": True,
        "click_target_field": field_id,
    }


# Legacy interface
def run(state: AgentState) -> AgentState:
    import asyncio
    result = asyncio.run(recovery(state))
    state.apply_update(result)
    return state
