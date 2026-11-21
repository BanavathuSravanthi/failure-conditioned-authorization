"""IGAR budget calculations and candidate selection (Spec Section 4).
Authority: Spec Section 4, Section 10 (Tests 6, 24, 25).
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any


@dataclass(frozen=True)
class CandidateSelectionResult:
    selected_tool: Optional[str]
    tie_break_applied: bool
    candidate_order: Optional[List[str]]


def compute_integer_rhu(numerator: int, denominator: int) -> int:
    """Computes round-half-up division using integer-only math per Spec Section 4.
    Formula: floor((2 * numerator + denominator) // (2 * denominator)) using Python's
    floor division '//' which rounds toward negative infinity for negative numbers.
    """
    if denominator <= 0:
        raise ValueError("denominator must be strictly positive")
    return (2 * numerator + denominator) // (2 * denominator)


def calculate_budget_from_cost_gap(
    dc: int,
    crange: int,
    k_max: int = 2,
    feasible: bool = True
) -> int:
    """Computes IGAR recovery budget B from cost gap dC and Crange per Spec Section 4.
    if not feasible: B = 0
    if crange == 0:  B = 1
    if dc <= 0:      B = 1 (clipped at 1 for dC <= 0)
    else:            B = clip(1 + RHU((Kmax - 1) * dC / Crange), 1, Kmax)
    """
    if not feasible:
        return 0
    if k_max <= 0:
        raise ValueError("k_max must be strictly positive")
    if crange < 0:
        raise ValueError("crange must be non-negative (cost(HIGH) >= cost(LOW))")
    if crange == 0:
        return 1
    if dc <= 0:
        return 1

    rhu = compute_integer_rhu((k_max - 1) * dc, crange)
    raw_b = 1 + rhu
    return max(1, min(k_max, raw_b))


def calculate_igar_budget(
    failed_scope: str,
    candidate_scope: Optional[str],
    cost_table: Dict[str, int],
    feasible: bool,
    k_max: int = 2
) -> Tuple[int, bool]:
    """Calculates IGAR budget B and uninformative flag for a scenario per Spec Section 4.
    Returns (budget, uninformative).
    """
    if not feasible:
        return 0, False

    if candidate_scope is None:
        raise ValueError("candidate_scope is required when feasible is True")

    for required_key in ("LOW", "HIGH", failed_scope, candidate_scope):
        if required_key not in cost_table:
            raise ValueError(f"cost_table missing required scope: {required_key}")

    crange = cost_table["HIGH"] - cost_table["LOW"]
    uninformative = (crange == 0)
    dc = cost_table[failed_scope] - cost_table[candidate_scope]

    budget = calculate_budget_from_cost_gap(
        dc=dc,
        crange=crange,
        k_max=k_max,
        feasible=feasible
    )
    return budget, uninformative


def select_candidate_tool(
    feasible_candidates: List[Dict[str, Any]],
    candidate_order: Optional[List[str]] = None
) -> CandidateSelectionResult:
    """Selects candidate tool using cost minimization first, broken by candidate_order.
    Spec Section 4:
    - Lowest-cost feasible alternative.
    - Ties broken by fixed candidate_order set in controller.yaml.
    - If a tie exists, candidate_order must be provided and must contain all tied candidates;
      otherwise raises ValueError.
    """
    if not feasible_candidates:
        return CandidateSelectionResult(
            selected_tool=None,
            tie_break_applied=False,
            candidate_order=candidate_order
        )

    min_cost = min(c["cost"] for c in feasible_candidates)
    min_candidates = [c for c in feasible_candidates if c["cost"] == min_cost]

    # Case 1: Strictly cheaper candidate exists (no tie)
    if len(min_candidates) == 1:
        return CandidateSelectionResult(
            selected_tool=min_candidates[0]["name"],
            tie_break_applied=False,
            candidate_order=candidate_order
        )

    # Case 2: Tie exists among multiple minimum-cost candidates
    if candidate_order is None or len(candidate_order) == 0:
        raise ValueError("candidate_order is required when a tie exists")

    min_names = {c["name"] for c in min_candidates}
    missing_candidates = [name for name in min_names if name not in candidate_order]
    if missing_candidates:
        raise ValueError(
            f"Tied candidates missing from candidate_order: {missing_candidates}"
        )

    # Deterministic tie-breaking: candidate appearing earliest in candidate_order wins
    selected = min(min_candidates, key=lambda c: candidate_order.index(c["name"]))["name"]
    return CandidateSelectionResult(
        selected_tool=selected,
        tie_break_applied=True,
        candidate_order=candidate_order
    )
