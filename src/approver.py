"""Interface scaffolding for Deterministic Approver (Spec Section 6).
Contains only shape-correct placeholder returns for TDD red-phase collection.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Union

@dataclass(frozen=True)
class ApproverDecision:
    decision: str
    reason: str

class Approver:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy

    def evaluate(self, task_text: str, requested_tool: str, requested_scope: str) -> ApproverDecision:
        return ApproverDecision(decision="deny", reason="stub_placeholder")

def load_approver_policy(policy_path: Union[str, Path]) -> Dict[str, Any]:
    with open(policy_path, "r", encoding="utf-8") as f:
        pass
    return {}
