"""FCA/IGAR Controller, Routing, Generic Denial, and State Machine (Spec Section 2, 3.1, 3.2, 8.2).
Authority: Spec Section 2, Section 3.1, Section 3.2, Section 8.2, Section 10.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from src.igar_budget import calculate_igar_budget

GENERIC_DENIAL_MESSAGE = "Action not permitted at this time."


@dataclass(frozen=True)
class ControllerEvaluation:
    allowed: bool
    is_blocked: bool
    requires_approval: bool
    denial_message: Optional[str]
    events_to_log: List[Dict[str, Any]]


class Controller:
    """FCA/IGAR Controller managing recovery window, budget, freeze, and routing.
    Enforces Spec Section 2, 3.1, 3.2:
    - C7: same-tool retries with K budget.
    - C8: candidate-directed recovery with cost-gap budget B.
    - C9: candidate-directed recovery (Class A) or same-tool fallback (Class B) with fixed K=2.
    - Freeze on HIGH requests during recovery window (denied without approver invocation).
    - Post-exhaustion modes: strict (blocks non-HIGH) and open (lifts freeze for ordinary calls).
    """

    def __init__(
        self,
        scenario_id: str,
        condition: str,
        post_exhaustion: str = "strict",
        k_value: int = 2,
        failed_tool: Optional[Dict[str, Any]] = None,
        candidate_tool: Optional[Dict[str, Any]] = None,
        feasible: bool = True,
        cost_table: Optional[Dict[str, int]] = None,
        k_max: int = 2
    ):
        self.scenario_id = scenario_id
        self.condition = condition
        self.post_exhaustion = post_exhaustion
        self.k_value = k_value
        self.failed_tool = failed_tool
        self.candidate_tool = candidate_tool
        self.feasible = feasible
        self.cost_table = cost_table or {}
        self.k_max = k_max

        self.first_failure_occurred: bool = False
        self.recovery_window_open: bool = False
        self.recovery_budget_permitted: Optional[int] = None
        self.recovery_budget_remaining: Optional[int] = None
        self.recovery_calls_actual: int = 0
        self.executed_calls_after_first_failure: int = 0
        self.failed_executed_calls_after_first_failure: int = 0

    def _get_permitted_recovery_tool_name(self) -> Optional[str]:
        """Returns the permitted recovery tool name during the recovery window per Spec Section 3.2."""
        if self.condition == "C7":
            return self.failed_tool["name"] if self.failed_tool else None
        elif self.condition == "C8":
            return self.candidate_tool["name"] if self.candidate_tool else None
        elif self.condition == "C9":
            if self.candidate_tool and self.candidate_tool.get("name"):
                return self.candidate_tool["name"]
            elif self.failed_tool:
                return self.failed_tool["name"]
        return None

    def record_first_failure(self, tool_name: str, scope: str):
        """Records initial tool failure below HIGH, opening the recovery window per Spec Section 3.1 & 4."""
        self.first_failure_occurred = True

        if self.condition in ("C7", "C9"):
            b = self.k_value
            self.recovery_budget_permitted = b
            self.recovery_budget_remaining = b
            self.recovery_window_open = (b > 0)
        elif self.condition == "C8":
            if not self.feasible or self.candidate_tool is None:
                b = 0
            else:
                candidate_scope = self.candidate_tool.get("scope")
                b, _ = calculate_igar_budget(
                    failed_scope=scope,
                    candidate_scope=candidate_scope,
                    cost_table=self.cost_table,
                    feasible=self.feasible,
                    k_max=self.k_max
                )
            self.recovery_budget_permitted = b
            self.recovery_budget_remaining = b
            self.recovery_window_open = (b > 0)
        else:
            self.recovery_budget_permitted = None
            self.recovery_budget_remaining = None
            self.recovery_window_open = False

    def evaluate_call(self, tool_name: str, scope: str) -> ControllerEvaluation:
        """Evaluates a proposed tool call per Spec Section 3.2:
        - Before first failure: non-HIGH allowed, HIGH forwarded to approver (Test 28).
        - During window: permitted tool allowed; non-permitted non-HIGH blocked (Test 19);
          HIGH blocked and never forwarded to approver (Test 4).
        - Post-exhaustion: strict blocks non-HIGH, open allows ordinary non-HIGH; HIGH to approver (Test 22, 29).
        """
        # 1. Before first failure: no freeze exists yet (Spec Sec 3.3, Test 28)
        if not self.first_failure_occurred:
            if scope == "HIGH":
                if self.condition == "C2":
                    # Static least privilege: HIGH always blocked
                    blocked_event = {
                        "event": "blocked_attempt",
                        "tool": tool_name,
                        "scope": "HIGH",
                        "high_request": True,
                        "high_granted": False,
                        "recovery_call": False
                    }
                    return ControllerEvaluation(
                        allowed=False,
                        is_blocked=True,
                        requires_approval=False,
                        denial_message=GENERIC_DENIAL_MESSAGE,
                        events_to_log=[blocked_event]
                    )
                return ControllerEvaluation(
                    allowed=False,
                    is_blocked=False,
                    requires_approval=True,
                    denial_message=None,
                    events_to_log=[]
                )
            return ControllerEvaluation(
                allowed=True,
                is_blocked=False,
                requires_approval=False,
                denial_message=None,
                events_to_log=[]
            )

        # 2. During recovery window (Spec Sec 3.2, Test 4, 19)
        if self.recovery_window_open:
            if scope == "HIGH":
                # HIGH request during recovery window is frozen and never reaches approver
                blocked_event = {
                    "event": "blocked_attempt",
                    "tool": tool_name,
                    "scope": "HIGH",
                    "high_request": True,
                    "high_granted": False,
                    "recovery_call": False
                }
                auth_event = {
                    "event": "auth_decision",
                    "decision": "deny",
                    "reason": "freeze_block",
                    "high_request": True,
                    "high_granted": False,
                    "recovery_call": False
                }
                return ControllerEvaluation(
                    allowed=False,
                    is_blocked=True,
                    requires_approval=False,
                    denial_message=GENERIC_DENIAL_MESSAGE,
                    events_to_log=[blocked_event, auth_event]
                )

            # Non-HIGH call during recovery window
            permitted_tool = self._get_permitted_recovery_tool_name()
            if tool_name == permitted_tool:
                return ControllerEvaluation(
                    allowed=True,
                    is_blocked=False,
                    requires_approval=False,
                    denial_message=None,
                    events_to_log=[]
                )
            else:
                # Non-permitted non-HIGH call during window is blocked
                blocked_event = {
                    "event": "blocked_attempt",
                    "tool": tool_name,
                    "scope": scope,
                    "high_request": False,
                    "high_granted": False,
                    "recovery_call": False
                }
                return ControllerEvaluation(
                    allowed=False,
                    is_blocked=True,
                    requires_approval=False,
                    denial_message=GENERIC_DENIAL_MESSAGE,
                    events_to_log=[blocked_event]
                )

        # 3. Post-exhaustion / Conditions without budget (C1, C4, C5, C6)
        if scope == "HIGH":
            if self.condition == "C2":
                blocked_event = {
                    "event": "blocked_attempt",
                    "tool": tool_name,
                    "scope": "HIGH",
                    "high_request": True,
                    "high_granted": False,
                    "recovery_call": False
                }
                return ControllerEvaluation(
                    allowed=False,
                    is_blocked=True,
                    requires_approval=False,
                    denial_message=GENERIC_DENIAL_MESSAGE,
                    events_to_log=[blocked_event]
                )
            # HIGH request reaches the approver (or gate)
            return ControllerEvaluation(
                allowed=False,
                is_blocked=False,
                requires_approval=True,
                denial_message=None,
                events_to_log=[]
            )

        # For budgetless / retry conditions or K=0, non-HIGH calls are never blocked
        if self.condition in ("C1", "C4", "C5", "C6") or (self.condition in ("C7", "C9") and self.k_value == 0):
            return ControllerEvaluation(
                allowed=True,
                is_blocked=False,
                requires_approval=False,
                denial_message=None,
                events_to_log=[]
            )

        if self.post_exhaustion == "strict":
            # In strict mode, every non-HIGH call is blocked
            blocked_event = {
                "event": "blocked_attempt",
                "tool": tool_name,
                "scope": scope,
                "high_request": False,
                "high_granted": False,
                "recovery_call": False
            }
            return ControllerEvaluation(
                allowed=False,
                is_blocked=True,
                requires_approval=False,
                denial_message=GENERIC_DENIAL_MESSAGE,
                events_to_log=[blocked_event]
            )
        else:
            # In open mode, freeze is lifted; ordinary call executes
            return ControllerEvaluation(
                allowed=True,
                is_blocked=False,
                requires_approval=False,
                denial_message=None,
                events_to_log=[]
            )

    def record_call_executed(self, tool_name: str, scope: str, success: bool):
        """Records an executed call, consuming recovery budget if inside recovery window."""
        if self.first_failure_occurred:
            self.executed_calls_after_first_failure += 1
            if not success:
                self.failed_executed_calls_after_first_failure += 1

        if self.recovery_window_open:
            permitted_tool = self._get_permitted_recovery_tool_name()
            if tool_name == permitted_tool:
                self.recovery_calls_actual += 1
                if self.recovery_budget_remaining is not None and self.recovery_budget_remaining > 0:
                    self.recovery_budget_remaining -= 1
                if self.recovery_budget_remaining == 0:
                    self.recovery_window_open = False
