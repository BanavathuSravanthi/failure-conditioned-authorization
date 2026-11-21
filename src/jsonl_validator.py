"""Validator for raw experiment JSONL event streams per Spec Section 9.

Authority:
- Spec Section 9 (JSONL log contract)
- Spec Section 10 (Mandatory test 26)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

MANDATORY_BASE_FIELDS = {
    "run_id",
    "scenario_id",
    "condition",
    "agent_type",
    "model",
    "prompt_version",
    "temperature",
    "seed",
    "scripted_fail_threshold",
    "step",
    "event",
    "recovery_call",
    "recovery_budget_permitted",
    "recovery_budget_remaining",
    "high_request",
    "high_granted",
    "terminal_state",
}

VALID_EVENTS = {
    "tool_call",
    "tool_failure",
    "auth_decision",
    "recovery_decision",
    "blocked_attempt",
    "episode_end",
}

VALID_TERMINAL_STATES = {
    "COMPLETED_RECOVERED",
    "COMPLETED_ESCALATED",
    "ESCALATION_DENIED",
    "FAILED",
    "EXPIRED",
}


class JSONLValidationError(Exception):
    pass


def validate_event_dict(event: Dict[str, Any], line_num: int = 1) -> List[str]:
    """Validate a single parsed event against the Spec Section 9 contract."""
    errors = []

    # 1. Check mandatory base fields
    missing_fields = MANDATORY_BASE_FIELDS - set(event.keys())
    if missing_fields:
        errors.append(f"Line {line_num}: Missing mandatory base fields: {sorted(missing_fields)}")

    # 2. Check base field types
    event_type = event.get("event")
    if event_type not in VALID_EVENTS:
        errors.append(f"Line {line_num}: Invalid event type '{event_type}', must be one of {VALID_EVENTS}")

    if not isinstance(event.get("step"), int):
        errors.append(f"Line {line_num}: 'step' must be int, got {type(event.get('step'))}")

    if not isinstance(event.get("recovery_call"), bool):
        errors.append(f"Line {line_num}: 'recovery_call' must be bool, got {type(event.get('recovery_call'))}")

    if not isinstance(event.get("high_request"), bool):
        errors.append(f"Line {line_num}: 'high_request' must be bool, got {type(event.get('high_request'))}")

    if not isinstance(event.get("high_granted"), bool):
        errors.append(f"Line {line_num}: 'high_granted' must be bool, got {type(event.get('high_granted'))}")

    if event.get("agent_type") == "scripted":
        if event.get("scripted_fail_threshold") != 3:
            errors.append(f"Line {line_num}: 'scripted_fail_threshold' must be 3 for scripted agent, got {event.get('scripted_fail_threshold')}")

    # 3. Check event-specific contracts
    if event_type == "tool_call":
        if "tool" not in event or not isinstance(event["tool"], str):
            errors.append(f"Line {line_num}: 'tool_call' must specify 'tool' string")
        if "scope" not in event or event["scope"] not in ("LOW", "MEDIUM", "HIGH"):
            errors.append(f"Line {line_num}: 'tool_call' must specify valid scope")

    elif event_type == "tool_failure":
        if "tool" not in event or not isinstance(event["tool"], str):
            errors.append(f"Line {line_num}: 'tool_failure' must specify 'tool'")
        if "attempt_number" not in event or not isinstance(event["attempt_number"], int):
            errors.append(f"Line {line_num}: 'tool_failure' must specify int 'attempt_number'")

    elif event_type == "auth_decision":
        if event.get("decision") not in ("allow", "deny"):
            errors.append(f"Line {line_num}: 'auth_decision' decision must be 'allow' or 'deny'")
        valid_reasons = ("policy_allow", "policy_deny", "no_gate", "freeze_block")
        if event.get("reason") not in valid_reasons:
            errors.append(f"Line {line_num}: 'auth_decision' reason must be one of {valid_reasons}")

    elif event_type == "blocked_attempt":
        if "tool" not in event or "scope" not in event:
            errors.append(f"Line {line_num}: 'blocked_attempt' must specify tool and scope")

    elif event_type == "episode_end":
        term = event.get("terminal_state")
        if term not in VALID_TERMINAL_STATES:
            errors.append(f"Line {line_num}: 'episode_end' has invalid terminal_state '{term}'")
        req_end_fields = [
            "recovery_calls_permitted", "recovery_calls_actual",
            "executed_calls_after_first_failure", "failed_executed_calls_after_first_failure",
            "total_calls", "blocked_calls", "high_attempts", "high_grants"
        ]
        for f in req_end_fields:
            if f not in event:
                errors.append(f"Line {line_num}: 'episode_end' missing required summary field '{f}'")

    return errors


def validate_jsonl_content(content: str) -> Tuple[bool, List[str]]:
    """Validate full JSONL text content for schema, ordering, and transitions."""
    lines = content.strip().splitlines()
    if not lines:
        return False, ["Empty JSONL stream"]

    all_errors = []
    seen_end = False
    last_step = -1

    for idx, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError as e:
            all_errors.append(f"Line {idx}: JSON parse error: {e}")
            continue

        errors = validate_event_dict(evt, line_num=idx)
        all_errors.extend(errors)

        step = evt.get("step", 0)
        if step < last_step:
            all_errors.append(f"Line {idx}: Step decreased from {last_step} to {step}")
        last_step = step

        if evt.get("event") == "episode_end":
            if seen_end:
                all_errors.append(f"Line {idx}: Multiple episode_end events in single stream")
            seen_end = True

    if not seen_end:
        all_errors.append("Stream missing episode_end event")

    return (len(all_errors) == 0, all_errors)


def validate_jsonl_file(file_path: str | Path) -> Tuple[bool, List[str]]:
    """Validate a JSONL file on disk."""
    path = Path(file_path)
    if not path.is_file():
        return False, [f"File not found: {path}"]
    content = path.read_text(encoding="utf-8")
    return validate_jsonl_content(content)
