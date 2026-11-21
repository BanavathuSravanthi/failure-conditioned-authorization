"""Interface scaffolding for IGAR budget math and candidate selection (Spec Section 4).
Contains only shape-correct placeholder returns for TDD red-phase collection.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

@dataclass(frozen=True)
class CandidateSelectionResult:
    selected_tool: Optional[str]
    tie_break_applied: bool
    candidate_order: Optional[List[str]]

def compute_integer_rhu(numerator: int, denominator: int) -> int:
    return 0

def calculate_budget_from_cost_gap(
    dc: int,
    crange: int,
    k_max: int = 2,
    feasible: bool = True
) -> int:
    return 0

def calculate_igar_budget(
    failed_scope: str,
    candidate_scope: Optional[str],
    cost_table: Dict[str, int],
    feasible: bool,
    k_max: int = 2
) -> Tuple[int, bool]:
    return 0, False

def select_candidate_tool(
    feasible_candidates: List[Dict[str, Any]],
    candidate_order: Optional[List[str]] = None
) -> CandidateSelectionResult:
    return CandidateSelectionResult(
        selected_tool=None,
        tie_break_applied=False,
        candidate_order=candidate_order
    )
