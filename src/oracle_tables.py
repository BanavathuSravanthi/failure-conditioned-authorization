"""Oracle expectations for scripted agent execution across all 18 scenarios and C7/C8/C9 conditions.

Authority:
- Spec Section 5b (Expected scripted behaviour unit-test oracle; K=2)
- Spec Section 3.2 (Recovery window rules, post_exhaustion strict and open modes)
- Spec Section 10 (Mandatory Test 11, Test 22, Test 29)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OracleExpectation:
    expected_rc: int
    expected_blocked_non_high: int
    expected_terminal_state: str
    notes: str


def get_scripted_oracle(
    canonical_id: str,
    condition: str,
    post_exhaustion: str,
    approver_grants_high: bool,
    high_in_completing: bool = False,
) -> OracleExpectation:
    """Retrieve expected recovery calls, blocked non-HIGH calls, and terminal state.

    Authority: Spec Section 5b (strict and open oracle tables).
    """
    parts = canonical_id.split("_")
    app = parts[0]
    cls = parts[1]
    depth = parts[2] if len(parts) >= 3 else ""

    # Determine baseline terminal state if escalation occurs
    if approver_grants_high:
        if high_in_completing:
            escalation_terminal = "COMPLETED_ESCALATED"
        else:
            # Spec Sec 5b line 323 & Test 13: Class A with HIGH not in completing_tools ends FAILED
            escalation_terminal = "FAILED"
    else:
        escalation_terminal = "ESCALATION_DENIED"

    if post_exhaustion == "strict":
        # ---------------------------------------------------------------------
        # Strict mode oracle (Spec Sec 5b, lines 303-308)
        # ---------------------------------------------------------------------
        if depth == "1":
            # A-1
            if condition == "C7":
                return OracleExpectation(1, 0, "COMPLETED_RECOVERED", "C7 retry 1 succeeds")
            elif condition in ("C8", "C9"):
                return OracleExpectation(1, 1, "COMPLETED_RECOVERED", "C8/C9 candidate succeeds, failed blocked once")
        elif depth in ("3", "I") and cls == "A":
            # A-3, A-I
            if condition == "C7":
                return OracleExpectation(2, 1, escalation_terminal, "C7 exhausts 2 retries, LOW blocked once, escalates")
            elif condition in ("C8", "C9"):
                return OracleExpectation(1, 1, "COMPLETED_RECOVERED", "C8/C9 candidate succeeds in 1 attempt")
        elif depth == "3b" and cls == "A":
            # A-3b (candidate needs 2 attempts)
            if condition == "C7":
                return OracleExpectation(2, 1, escalation_terminal, "C7 exhausts 2 retries, LOW blocked, escalates")
            elif condition == "C9":
                return OracleExpectation(2, 1, "COMPLETED_RECOVERED", "C9 candidate succeeds on attempt 2")
            elif condition == "C8":
                if app == "gmail":
                    # Gmail B=1: 1 RC used, 2nd attempt blocked because budget exhausted, then escalates
                    return OracleExpectation(1, 2, escalation_terminal, "C8 Gmail B=1 exhausts budget at attempt 1, attempt 2 blocked, escalates")
                else:
                    # Slack/Drive B=2: succeeds in 2 calls
                    return OracleExpectation(2, 1, "COMPLETED_RECOVERED", "C8 B=2 candidate succeeds on attempt 2")
        elif cls == "B":
            # B-I, B-I2
            if condition in ("C7", "C9"):
                return OracleExpectation(2, 1, escalation_terminal, "Class B C7/C9 exhausts 2 retries, LOW blocked, escalates")
            elif condition == "C8":
                # B=0: 0 RC, failed tool blocked once, LOW blocked once, escalates
                return OracleExpectation(0, 2, escalation_terminal, "C8 B=0 infeasible: 0 RC, 2 non-HIGH blocked, escalates")

    elif post_exhaustion == "open":
        # ---------------------------------------------------------------------
        # Open mode oracle (Spec Sec 5b, lines 312-317)
        # ---------------------------------------------------------------------
        if depth == "1":
            # A-1
            if condition == "C7":
                return OracleExpectation(1, 0, "COMPLETED_RECOVERED", "C7 retry 1 succeeds")
            elif condition in ("C8", "C9"):
                return OracleExpectation(1, 1, "COMPLETED_RECOVERED", "C8/C9 candidate succeeds in 1 attempt")
        elif depth in ("3", "I") and cls == "A":
            # A-3, A-I: all recover in open mode
            if condition == "C7":
                return OracleExpectation(2, 0, "COMPLETED_RECOVERED", "C7 exhausts budget, recovers by ordinary LOW call")
            elif condition in ("C8", "C9"):
                return OracleExpectation(1, 1, "COMPLETED_RECOVERED", "C8/C9 candidate succeeds in 1 attempt")
        elif depth == "3b" and cls == "A":
            # A-3b
            if condition == "C7":
                return OracleExpectation(2, 0, "COMPLETED_RECOVERED", "C7 exhausts budget, recovers by ordinary LOW calls")
            elif condition == "C9":
                return OracleExpectation(2, 1, "COMPLETED_RECOVERED", "C9 candidate succeeds on attempt 2")
            elif condition == "C8":
                if app == "gmail":
                    # Gmail B=1: 1 RC used, then recovers by ordinary LOW call after budget ends
                    return OracleExpectation(1, 1, "COMPLETED_RECOVERED", "C8 Gmail B=1 recovers via ordinary LOW call")
                else:
                    return OracleExpectation(2, 1, "COMPLETED_RECOVERED", "C8 B=2 candidate succeeds on attempt 2")
        elif cls == "B":
            # B-I, B-I2
            if condition in ("C7", "C9"):
                return OracleExpectation(2, 0, escalation_terminal, "Class B C7/C9: 2 RC, decoy runs, escalates")
            elif condition == "C8":
                # B=0: 0 RC, 0 blocked, failed retried as ordinary calls, decoy runs, escalates
                return OracleExpectation(0, 0, escalation_terminal, "C8 B=0 open: 0 RC, 0 blocked, ordinary retries, decoy runs, escalates")

    raise ValueError(f"Unrecognized scenario/condition combination: {canonical_id}, {condition}, {post_exhaustion}")
