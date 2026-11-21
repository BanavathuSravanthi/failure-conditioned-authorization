"""Tests for Budget, IGAR Math, and Candidate Selection (Tests 1, 2, 3, 6, 24(a,b,c), 25).
Authority: Spec Section 3.1, Section 4, Section 10.
"""
import random
import pytest
from src.igar_budget import (
    calculate_igar_budget,
    calculate_budget_from_cost_gap,
    compute_integer_rhu,
    select_candidate_tool,
    CandidateSelectionResult
)
from src.controller import Controller

# Exact per-application cost tables from Spec Section 4
GMAIL_COSTS = {"LOW": 1, "MEDIUM": 3, "HIGH": 6}   # Crange=5, dC=2 -> B=1
SLACK_COSTS = {"LOW": 1, "MEDIUM": 5, "HIGH": 6}   # Crange=5, dC=4 -> B=2
DRIVE_COSTS = {"LOW": 1, "MEDIUM": 4, "HIGH": 6}   # Crange=5, dC=3 -> B=2

# Synthetic cost tables for clipping tests (Spec Sec 4 & Test 25)
GMAIL_COSTS_EXCEED = {"LOW": 1, "MEDIUM": 11, "HIGH": 6}  # Crange=5, dC=10
DRIVE_COSTS_EXCEED = {"LOW": 1, "MEDIUM": 17, "HIGH": 9}  # Crange=8, dC=16


# ============================================================================
# Test 1: Initial failed call does not consume budget (Spec Sec 3.1, Sec 10 #1)
# ============================================================================
def test_initial_failed_call_does_not_consume_budget():
    """Spec Section 3.1 and Section 10 Test 1:
    Initial failed call below HIGH opens recovery window but does NOT consume budget.
    """
    ctrl = Controller(
        scenario_id="scenario_001",
        condition="C7",
        post_exhaustion="strict",
        k_value=2,
        failed_tool={"name": "gmail.send_draft", "scope": "MEDIUM"},
        cost_table=GMAIL_COSTS
    )
    assert ctrl.recovery_budget_remaining is None
    assert not ctrl.recovery_window_open

    ctrl.record_first_failure(tool_name="gmail.send_draft", scope="MEDIUM")

    assert ctrl.recovery_window_open is True
    assert ctrl.recovery_budget_permitted == 2
    assert ctrl.recovery_budget_remaining == 2
    assert ctrl.recovery_calls_actual == 0


# ============================================================================
# Test 2: Blocked alternate-tool attempt does not reset budget (Spec Sec 3.1, 3.2, 10 #2)
# ============================================================================
def test_blocked_alternate_tool_does_not_reset_budget_c7():
    """Spec Section 3.1, 3.2, and Section 10 Test 2 (C7):
    In C7 (same-tool recovery), an executed recovery call consumes budget.
    A subsequent attempt to a non-permitted tool is blocked and does NOT reset budget.
    Returning to the permitted tool decrements from the persisted remaining budget.
    """
    ctrl = Controller(
        scenario_id="scenario_001",
        condition="C7",
        post_exhaustion="strict",
        k_value=2,
        failed_tool={"name": "gmail.send_draft", "scope": "MEDIUM"},
        cost_table=GMAIL_COSTS
    )
    ctrl.record_first_failure(tool_name="gmail.send_draft", scope="MEDIUM")
    assert ctrl.recovery_budget_remaining == 2

    # Permitted recovery call 1 executes and consumes 1 budget unit
    ctrl.record_call_executed(tool_name="gmail.send_draft", scope="MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 1
    assert ctrl.recovery_calls_actual == 1

    # Agent attempts alternate non-permitted tool -> blocked
    eval_res = ctrl.evaluate_call(tool_name="gmail.create_draft", scope="LOW")
    assert eval_res.is_blocked is True
    # Crucial assertion: switching does NOT reset budget back to 2
    assert ctrl.recovery_budget_remaining == 1
    assert ctrl.recovery_calls_actual == 1

    # Permitted recovery call 2 executes
    ctrl.record_call_executed(tool_name="gmail.send_draft", scope="MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 0
    assert ctrl.recovery_calls_actual == 2


def test_blocked_alternate_tool_does_not_reset_budget_c8():
    """Spec Section 3.1, 3.2, and Section 10 Test 2 (C8):
    In C8, recovery is directed at the candidate tool. Using Slack costs (B=2):
    Permitted call to candidate consumes budget; blocked attempt to failed tool
    does NOT reset budget.
    """
    ctrl = Controller(
        scenario_id="scenario_003",
        condition="C8",
        post_exhaustion="strict",
        k_value=2,
        failed_tool={"name": "slack.post_message", "scope": "MEDIUM"},
        candidate_tool={"name": "slack.add_reaction", "scope": "LOW"},
        feasible=True,
        cost_table=SLACK_COSTS
    )
    ctrl.record_first_failure(tool_name="slack.post_message", scope="MEDIUM")
    assert ctrl.recovery_budget_remaining == 2

    # Permitted call to candidate tool consumes 1 budget unit
    ctrl.record_call_executed(tool_name="slack.add_reaction", scope="LOW", success=False)
    assert ctrl.recovery_budget_remaining == 1
    assert ctrl.recovery_calls_actual == 1

    # Blocked attempt to failed tool does not reset budget
    eval_res = ctrl.evaluate_call(tool_name="slack.post_message", scope="MEDIUM")
    assert eval_res.is_blocked is True
    assert ctrl.recovery_budget_remaining == 1
    assert ctrl.recovery_calls_actual == 1

    # Second permitted call consumes remaining budget
    ctrl.record_call_executed(tool_name="slack.add_reaction", scope="LOW", success=False)
    assert ctrl.recovery_budget_remaining == 0
    assert ctrl.recovery_calls_actual == 2


def test_blocked_alternate_tool_does_not_reset_budget_c9_class_a():
    """Spec Section 2, 3.1, 3.2, and Section 10 Test 2 (C9 Class A):
    C9 has fixed K=2 directed at candidate tool.
    Blocked attempt to failed tool does NOT reset budget.
    """
    ctrl = Controller(
        scenario_id="scenario_001",
        condition="C9",
        post_exhaustion="strict",
        k_value=2,
        failed_tool={"name": "gmail.send_draft", "scope": "MEDIUM"},
        candidate_tool={"name": "gmail.create_draft", "scope": "LOW"},
        feasible=True,
        cost_table=GMAIL_COSTS
    )
    ctrl.record_first_failure(tool_name="gmail.send_draft", scope="MEDIUM")
    assert ctrl.recovery_budget_remaining == 2

    ctrl.record_call_executed(tool_name="gmail.create_draft", scope="LOW", success=False)
    assert ctrl.recovery_budget_remaining == 1

    eval_res = ctrl.evaluate_call(tool_name="gmail.send_draft", scope="MEDIUM")
    assert eval_res.is_blocked is True
    assert ctrl.recovery_budget_remaining == 1

    ctrl.record_call_executed(tool_name="gmail.create_draft", scope="LOW", success=False)
    assert ctrl.recovery_budget_remaining == 0
    assert ctrl.recovery_calls_actual == 2


def test_blocked_alternate_tool_does_not_reset_budget_c9_class_b_fallback():
    """Spec Section 2, 3.1, 3.2, and Section 10 Test 2 (C9 Class B Fallback):
    When no candidate exists in C9 (Class B), recovery falls back to failed tool with fixed K=2.
    Blocked attempt to LOW decoy does NOT reset budget.
    """
    ctrl = Controller(
        scenario_id="scenario_002",
        condition="C9",
        post_exhaustion="strict",
        k_value=2,
        failed_tool={"name": "gmail.send_draft", "scope": "MEDIUM"},
        candidate_tool=None,
        feasible=False,
        cost_table=GMAIL_COSTS
    )
    ctrl.record_first_failure(tool_name="gmail.send_draft", scope="MEDIUM")
    assert ctrl.recovery_budget_remaining == 2

    ctrl.record_call_executed(tool_name="gmail.send_draft", scope="MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 1

    eval_res = ctrl.evaluate_call(tool_name="gmail.create_draft", scope="LOW")
    assert eval_res.is_blocked is True
    assert ctrl.recovery_budget_remaining == 1

    ctrl.record_call_executed(tool_name="gmail.send_draft", scope="MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 0
    assert ctrl.recovery_calls_actual == 2


# ============================================================================
# Test 3: Budget never goes below 0 (Spec Sec 3.1, Sec 10 #3)
# ============================================================================
def test_budget_never_goes_below_zero():
    """Spec Section 3.1 and Section 10 Test 3:
    Recovery budget never goes below 0 regardless of subsequent calls.
    """
    ctrl = Controller(
        scenario_id="scenario_001",
        condition="C7",
        post_exhaustion="strict",
        k_value=2,
        failed_tool={"name": "gmail.send_draft", "scope": "MEDIUM"},
        cost_table=GMAIL_COSTS
    )
    ctrl.record_first_failure("gmail.send_draft", "MEDIUM")
    ctrl.record_call_executed("gmail.send_draft", "MEDIUM", success=False)
    ctrl.record_call_executed("gmail.send_draft", "MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 0
    assert ctrl.recovery_window_open is False

    # Attempting to record further executions does not make budget negative
    ctrl.record_call_executed("gmail.send_draft", "MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 0


# ============================================================================
# Test 6: IGAR Budget Formula, Monotonicity, and Infeasible B=0 (Spec Sec 4, 10 #6)
# ============================================================================
def test_test6_igar_budget_cost_gap_formula_and_rhu_tie():
    """Spec Section 4 and Section 10 Test 6:
    Verifies:
    1. Exact halfway tie example: Kmax=3, Crange=4, dC=1 gives (2*1)/4 = 0.5 -> RHU 1 -> B=2.
    2. Monotonicity in dC.
    3. Both B=1 and B=2 occur in the suite across Gmail, Slack, and Drive.
    """
    # 1. Exact halfway tie example from spec
    b_tie = calculate_budget_from_cost_gap(dc=1, crange=4, k_max=3, feasible=True)
    assert b_tie == 2

    # 2. Monotonicity in dC for fixed Crange=5, Kmax=2
    b_dc1 = calculate_budget_from_cost_gap(dc=1, crange=5, k_max=2, feasible=True)
    b_dc2 = calculate_budget_from_cost_gap(dc=2, crange=5, k_max=2, feasible=True)
    b_dc3 = calculate_budget_from_cost_gap(dc=3, crange=5, k_max=2, feasible=True)
    b_dc4 = calculate_budget_from_cost_gap(dc=4, crange=5, k_max=2, feasible=True)
    assert b_dc1 <= b_dc2 <= b_dc3 <= b_dc4

    # 3. Both B=1 and B=2 occur in the suite
    b_gmail, _ = calculate_igar_budget("MEDIUM", "LOW", GMAIL_COSTS, feasible=True, k_max=2)
    b_slack, _ = calculate_igar_budget("MEDIUM", "LOW", SLACK_COSTS, feasible=True, k_max=2)
    b_drive, _ = calculate_igar_budget("MEDIUM", "LOW", DRIVE_COSTS, feasible=True, k_max=2)
    assert b_gmail == 1
    assert b_slack == 2
    assert b_drive == 2
    assert {b_gmail, b_slack} == {1, 2}


def test_test6_igar_budget_infeasible_gives_zero():
    """Spec Section 4 and Section 10 Test 6:
    When feasible=False, B is strictly 0.
    """
    b = calculate_budget_from_cost_gap(dc=2, crange=5, k_max=2, feasible=False)
    assert b == 0

    budget, uninformative = calculate_igar_budget(
        failed_scope="MEDIUM",
        candidate_scope=None,
        cost_table=GMAIL_COSTS,
        feasible=False,
        k_max=2
    )
    assert budget == 0
    assert uninformative is False


# ============================================================================
# Test 24(a,b,c): Candidate Selection Algorithm & Tie-Breaking (Spec Sec 4, 10 #24)
# (Note: Test 24(d) writing to frozen scenario table is pending Milestone 2)
# ============================================================================
def test_candidate_selection_strictly_cheaper():
    """Spec Section 4 and Section 10 Test 24(c):
    Cost minimization strictly precedes tie-breaking: a cheaper candidate later
    in candidate_order beats a costlier candidate earlier in candidate_order.
    """
    candidates = [
        {"name": "tool_expensive", "cost": 3, "scope": "MEDIUM"},
        {"name": "tool_cheap", "cost": 1, "scope": "LOW"}
    ]
    # tool_expensive is FIRST in candidate_order
    candidate_order = ["tool_expensive", "tool_cheap"]

    res = select_candidate_tool(candidates, candidate_order)

    assert res.selected_tool == "tool_cheap"
    assert res.tie_break_applied is False
    assert res.candidate_order == candidate_order


def test_candidate_tie_break_algorithm_selection():
    """Spec Section 4 and Section 10 Test 24(a):
    Equal-cost candidates: candidate appearing first in candidate_order is selected.
    The result object records selected_tool, tie_break_applied=True, and candidate_order.
    """
    candidates = [
        {"name": "tool_beta", "cost": 1, "scope": "LOW"},
        {"name": "tool_alpha", "cost": 1, "scope": "LOW"}
    ]
    candidate_order = ["tool_alpha", "tool_beta"]

    res = select_candidate_tool(candidates, candidate_order)

    assert res.selected_tool == "tool_alpha"
    assert res.tie_break_applied is True
    assert res.candidate_order == ["tool_alpha", "tool_beta"]


@pytest.mark.parametrize("order_case", ["order_alpha_first", "order_beta_first"])
def test_candidate_selection_scenario_tool_order_invariance(order_case):
    """Spec Section 4 and Section 10 Test 24(b):
    Reversing the tool order in scenario.yaml does not change the selected candidate.
    """
    order_a = [
        {"name": "tool_alpha", "cost": 1, "scope": "LOW"},
        {"name": "tool_beta", "cost": 1, "scope": "LOW"}
    ]
    order_b = [
        {"name": "tool_beta", "cost": 1, "scope": "LOW"},
        {"name": "tool_alpha", "cost": 1, "scope": "LOW"}
    ]
    selected_input = order_a if order_case == "order_alpha_first" else order_b
    candidate_order = ["tool_alpha", "tool_beta"]

    res = select_candidate_tool(selected_input, candidate_order)

    assert res.selected_tool == "tool_alpha"
    assert res.tie_break_applied is True


@pytest.mark.parametrize("seed", [42, 123, 999])
def test_candidate_selection_seed_invariance(seed):
    """Spec Section 4 and Section 10 Test 24(b):
    Changing the seed (which shuffles candidate inventory) does not change choice.
    """
    candidates = [
        {"name": "tool_alpha", "cost": 1, "scope": "LOW"},
        {"name": "tool_beta", "cost": 1, "scope": "LOW"},
        {"name": "tool_gamma", "cost": 1, "scope": "LOW"}
    ]
    rng = random.Random(seed)
    shuffled = list(candidates)
    rng.shuffle(shuffled)

    candidate_order = ["tool_gamma", "tool_alpha", "tool_beta"]

    res = select_candidate_tool(shuffled, candidate_order)
    assert res.selected_tool == "tool_gamma"
    assert res.tie_break_applied is True


@pytest.mark.parametrize("candidate_order", [None, [], ["tool_alpha"]])
def test_candidate_selection_requires_complete_candidate_order(candidate_order):
    """Spec Section 4: If a tie exists, candidate_order is strictly required and
    must contain all tied candidates. Missing or incomplete order raises ValueError.
    """
    candidates = [
        {"name": "tool_alpha", "cost": 1, "scope": "LOW"},
        {"name": "tool_beta", "cost": 1, "scope": "LOW"}
    ]
    with pytest.raises(ValueError):
        select_candidate_tool(candidates, candidate_order)


# ============================================================================
# Test 25: Budget Clipping (Spec Sec 4, Sec 10 #25)
# ============================================================================
@pytest.mark.parametrize("cost_table, k_max, expected_b", [
    (GMAIL_COSTS_EXCEED, 2, 2),  # Crange=5, dC=10 -> clips to Kmax=2
    (DRIVE_COSTS_EXCEED, 3, 3),  # Crange=8, dC=16 -> clips to Kmax=3
])
def test_budget_clipping_when_dc_exceeds_crange(cost_table, k_max, expected_b):
    """Spec Section 4 and Section 10 Test 25:
    With synthetic costs where dC exceeds Crange, B is clipped to Kmax.
    """
    budget, uninformative = calculate_igar_budget(
        failed_scope="MEDIUM",
        candidate_scope="LOW",
        cost_table=cost_table,
        feasible=True,
        k_max=k_max
    )
    assert budget == expected_b
    assert uninformative is False


@pytest.mark.parametrize("failed_scope, candidate_scope", [
    ("LOW", "LOW"),
    ("LOW", "MEDIUM"),
])
def test_budget_clipping_when_dc_less_equal_zero(failed_scope, candidate_scope):
    """Spec Section 4 and Section 10 Test 25: for dC <= 0, B is clipped to 1."""
    budget, uninformative = calculate_igar_budget(
        failed_scope=failed_scope,
        candidate_scope=candidate_scope,
        cost_table=GMAIL_COSTS,
        feasible=True,
        k_max=2
    )
    assert budget == 1
    assert uninformative is False
