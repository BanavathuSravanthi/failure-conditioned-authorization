"""Interface scaffolding for FCA/IGAR Controller (Spec Section 2, 3.1, 3.2, 8.2).
Contains only shape-correct placeholder returns for TDD red-phase collection.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

GENERIC_DENIAL_MESSAGE = "Action not permitted at this time."

@dataclass(frozen=True)
class ControllerEvaluation:
    allowed: bool
    is_blocked: bool
    requires_approval: bool
    denial_message: Optional[str]
    events_to_log: List[Dict[str, Any]]

class Controller:
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

        self.recovery_window_open: bool = False
        self.recovery_budget_permitted: Optional[int] = None
        self.recovery_budget_remaining: Optional[int] = None
        self.recovery_calls_actual: int = 0
        self.executed_calls_after_first_failure: int = 0
        self.failed_executed_calls_after_first_failure: int = 0

    def record_first_failure(self, tool_name: str, scope: str):
        pass

    def evaluate_call(self, tool_name: str, scope: str) -> ControllerEvaluation:
        return ControllerEvaluation(
            allowed=True,
            is_blocked=False,
            requires_approval=False,
            denial_message=None,
            events_to_log=[]
        )

    def record_call_executed(self, tool_name: str, scope: str, success: bool):
        pass
