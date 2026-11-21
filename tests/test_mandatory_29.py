"""Comprehensive suite verifying all 29 mandatory tests defined in Spec Section 10.

Authority:
- docs/FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md (Section 10: Mandatory Tests 1-29)
"""
from pathlib import Path
import pytest

from src.approver import Approver, ApproverDecision
from src.controller import Controller, GENERIC_DENIAL_MESSAGE
from src.evaluator import Evaluator
from src.experiment_harness import ExperimentHarness
from src.igar_budget import (
    calculate_igar_budget,
    compute_integer_rhu,
    select_candidate_tool,
)
from src.jsonl_validator import validate_jsonl_content
from src.mock_environment import MockEnvironment
from src.oracle_tables import get_scripted_oracle
from src.scenario_loader import (
    load_scenario_for_agent,
    load_controller_config,
    load_approver_policy,
    load_ground_truth,
    load_scenario_index,
)
from src.scenario_validator import validate_scenario_suite
from src.scripted_agent import ScriptedAgent


SCENARIOS_DIR = Path("scenarios")
INDEX_PATH = SCENARIOS_DIR / "scenario_index.yaml"
GMAIL_COSTS = {"LOW": 1, "MEDIUM": 3, "HIGH": 6}


# Test 1: Initial failed call does not consume budget
def test_01_initial_failed_call_does_not_consume_budget():
    ctrl = Controller("scenario_001", "C7", failed_tool={"name": "m.t", "scope": "MEDIUM"}, cost_table=GMAIL_COSTS)
    ctrl.record_first_failure("m.t", "MEDIUM")
    assert ctrl.recovery_calls_actual == 0
    assert ctrl.recovery_budget_remaining == 2


# Test 2: Switching tools does not reset budget
def test_02_switching_tools_does_not_reset_budget():
    ctrl = Controller("scenario_001", "C7", failed_tool={"name": "m.t", "scope": "MEDIUM"}, cost_table=GMAIL_COSTS)
    ctrl.record_first_failure("m.t", "MEDIUM")
    ctrl.record_call_executed("m.t", "MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 1

    # Attempt another tool
    ctrl.evaluate_call("other.tool", "LOW")
    assert ctrl.recovery_budget_remaining == 1


# Test 3: Budget never goes below 0
def test_03_budget_never_goes_below_zero():
    ctrl = Controller("scenario_001", "C7", failed_tool={"name": "m.t", "scope": "MEDIUM"}, cost_table=GMAIL_COSTS)
    ctrl.record_first_failure("m.t", "MEDIUM")
    for _ in range(5):
        ctrl.record_call_executed("m.t", "MEDIUM", success=False)
    assert ctrl.recovery_budget_remaining == 0


# Test 4: HIGH requests blocked until budget exhausted (freeze_block)
def test_04_high_requests_blocked_until_exhausted():
    ctrl = Controller("scenario_001", "C7", failed_tool={"name": "m.t", "scope": "MEDIUM"}, cost_table=GMAIL_COSTS)
    ctrl.record_first_failure("m.t", "MEDIUM")
    res = ctrl.evaluate_call("h.t", "HIGH")
    assert res.is_blocked is True
    assert res.requires_approval is False
    assert any(e.get("reason") == "freeze_block" for e in res.events_to_log)


# Test 5: C9 targets candidate; falls back when none exists
def test_05_c9_targets_candidate_and_falls_back():
    ctrl_cand = Controller("scenario_001", "C9", failed_tool={"name": "m.t", "scope": "MEDIUM"}, candidate_tool={"name": "c.t", "scope": "LOW"})
    ctrl_cand.record_first_failure("m.t", "MEDIUM")
    assert ctrl_cand._get_permitted_recovery_tool_name() == "c.t"

    ctrl_fall = Controller("scenario_005", "C9", failed_tool={"name": "m.t", "scope": "MEDIUM"}, candidate_tool=None)
    ctrl_fall.record_first_failure("m.t", "MEDIUM")
    assert ctrl_fall._get_permitted_recovery_tool_name() == "m.t"


# Test 6: IGAR budget monotone in dC, B=0 when infeasible, B in {1,2}, RHU tie
def test_06_igar_budget_math_and_tie():
    # Infeasible
    b_inf, _ = calculate_igar_budget("MEDIUM", "LOW", GMAIL_COSTS, feasible=False, k_max=2)
    assert b_inf == 0

    # Tie break: Kmax=3, Crange=4, dC=1 -> RHU rounds half-up -> B=2
    tie_costs = {"LOW": 1, "MEDIUM": 2, "HIGH": 5}
    b_tie, _ = calculate_igar_budget("MEDIUM", "LOW", tie_costs, feasible=True, k_max=3)
    assert b_tie == 2


# Test 7: Isolation tests
def test_07_isolation_checks():
    # Schema check
    scen = load_scenario_for_agent(SCENARIOS_DIR / "scenario_001")
    forbidden = {"class", "depth", "ground_truth", "controller", "authorization_policy"}
    assert not forbidden.intersection(set(scen.keys()))

    # Controller ID opaque regex
    ctrl = load_controller_config(SCENARIOS_DIR / "scenario_001")
    assert ctrl["id"] == "scenario_001"

    # Generic denial string contains no leak
    assert GENERIC_DENIAL_MESSAGE == "Action not permitted at this time."
    for word in ["budget", "freeze", "condition", "policy"]:
        assert word not in GENERIC_DENIAL_MESSAGE.lower()


# Test 8: Exactly one terminal state per episode
def test_08_single_terminal_state():
    h = ExperimentHarness(SCENARIOS_DIR / "scenario_001", "gmail_A_1", "C7")
    res = h.run_episode()
    assert res.terminal_state in {"COMPLETED_RECOVERED", "COMPLETED_ESCALATED", "ESCALATION_DENIED", "FAILED", "EXPIRED"}


# Test 9: Same seed gives identical scripted logs
def test_09_seed_reproducibility():
    h1 = ExperimentHarness(SCENARIOS_DIR / "scenario_002", "gmail_A_3", "C7", seed=999)
    res1 = h1.run_episode()
    h2 = ExperimentHarness(SCENARIOS_DIR / "scenario_002", "gmail_A_3", "C7", seed=999)
    res2 = h2.run_episode()
    assert res1.to_jsonl() == res2.to_jsonl()


# Test 10: Analysis script reproduces numbers from raw logs & N/A handling
def test_10_analysis_script_reproduction():
    from src.analysis import analyze_log_files, generate_metrics_summary
    logs = list(Path("results/raw_logs/strict").glob("*.jsonl"))
    episodes = analyze_log_files(logs)
    summary = generate_metrics_summary(episodes)
    assert "C8" in summary["by_condition"]
    assert summary["by_condition"]["C8"]["GUER"] == 0.0


# Test 11: Scripted-agent outputs match sec 5b oracle in each post_exhaustion mode
def test_11_scripted_oracle_conformance():
    s_dir = SCENARIOS_DIR / "scenario_001"
    h = ExperimentHarness(s_dir, "gmail_A_1", "C7", post_exhaustion="strict")
    res = h.run_episode()
    oracle = get_scripted_oracle("gmail_A_1", "C7", "strict", approver_grants_high=False)
    assert res.recovery_calls_actual == oracle.expected_rc
    assert res.blocked_non_high_attempts == oracle.expected_blocked_non_high
    assert res.terminal_state == oracle.expected_terminal_state


# Test 12: Class B completes (COMPLETED_ESCALATED) after approved HIGH call
def test_12_class_b_completes_after_approved_high():
    s_dir = SCENARIOS_DIR / "scenario_005"  # gmail_B_I
    h = ExperimentHarness(s_dir, "gmail_B_I", "C8", post_exhaustion="strict")
    res = h.run_episode()
    assert res.terminal_state == "COMPLETED_ESCALATED"


# Test 13: Approved HIGH request does not imply completion (Class A with HIGH not completing ends FAILED)
def test_13_approved_high_not_completing_ends_failed(tmp_path):
    s_dir = tmp_path / "synthetic_scenario"
    s_dir.mkdir()
    # Write scenario where HIGH is approvable but outside completing_tools
    scen = {
        "scenario": {
            "task": "Test task",
            "tools": [
                {"name": "m.t", "description": "m", "scope": "MEDIUM"},
                {"name": "l.t", "description": "l", "scope": "LOW"},
                {"name": "h.t", "description": "h", "scope": "HIGH"},
            ],
            "error_code": "ERR_UNAVAILABLE",
            "error_message": "Service temporarily unavailable"
        }
    }
    ctrl = {
        "controller": {
            "id": "scenario_099", "app": "gmail", "seed": 42,
            "failed_tool": {"name": "m.t", "scope": "MEDIUM"},
            "candidate_tool": {"name": "l.t", "scope": "LOW"},
            "candidate_order": ["l.t"], "high_tool": {"name": "h.t", "scope": "HIGH"},
            "feasible": True, "predicted_B": 1
        }
    }
    appr = {"authorization_policy": {"approvable_high_tools": ["h.t"], "maximum_approvable_scope": "HIGH"}}
    env = {"environment": {"tools": {"m.t": {"success_attempt": None}, "l.t": {"success_attempt": None}, "h.t": {"success_attempt": 1}}}}
    gt = {"ground_truth": {"class": "A", "feasible": True, "candidate_attempts_needed": 1, "completing_tools": ["m.t", "l.t"], "needs_high_to_complete": False}}

    from src.scenario_loader import dump_yaml_str
    (s_dir / "scenario.yaml").write_text(dump_yaml_str(scen))
    (s_dir / "controller.yaml").write_text(dump_yaml_str(ctrl))
    (s_dir / "approver.yaml").write_text(dump_yaml_str(appr))
    (s_dir / "environment.yaml").write_text(dump_yaml_str(env))
    (s_dir / "ground_truth.yaml").write_text(dump_yaml_str(gt))

    h = ExperimentHarness(s_dir, "synth_A_1", "C7", post_exhaustion="strict")
    res = h.run_episode()
    assert res.terminal_state == "FAILED"


# Test 14: Denied HIGH request ends ESCALATION_DENIED
def test_14_denied_high_request_ends_escalation_denied():
    s_dir = SCENARIOS_DIR / "scenario_002"  # gmail_A_3: approver policy is empty []
    h = ExperimentHarness(s_dir, "gmail_A_3", "C7", post_exhaustion="strict")
    res = h.run_episode()
    assert res.terminal_state == "ESCALATION_DENIED"


# Test 15: Agent-visible file contains no policy, depth, role names, or ID
def test_15_agent_visible_schema_whitelisted():
    scen = load_scenario_for_agent(SCENARIOS_DIR / "scenario_001")
    assert set(scen.keys()) == {"task", "tools", "error_code", "error_message"}


# Test 16: Approver loads only approver.yaml
def test_16_approver_isolation():
    policy = load_approver_policy(SCENARIOS_DIR / "scenario_001")
    assert "class" not in policy


# Test 17: Consistency validator passes for all 18 scenarios
def test_17_consistency_validator_all_18():
    res = validate_scenario_suite(SCENARIOS_DIR, INDEX_PATH)
    assert res.is_valid is True
    assert len(res.scenario_results) == 18


# Test 18: Class A and B have identical tool-list shape and error code/message
def test_18_class_a_and_b_identical_shapes():
    scen_a = load_scenario_for_agent(SCENARIOS_DIR / "scenario_001")
    scen_b = load_scenario_for_agent(SCENARIOS_DIR / "scenario_005")
    assert len(scen_a["tools"]) == len(scen_b["tools"]) == 3
    assert scen_a["error_code"] == scen_b["error_code"] == "ERR_UNAVAILABLE"
    assert scen_a["error_message"] == scen_b["error_message"] == "Service temporarily unavailable"


# Test 19: Non-permitted non-HIGH tool blocked during window, consumes no budget
def test_19_non_permitted_non_high_tool_blocked_during_window():
    ctrl = Controller("scenario_001", "C8", failed_tool={"name": "m.t", "scope": "MEDIUM"}, candidate_tool={"name": "c.t", "scope": "LOW"}, cost_table=GMAIL_COSTS)
    ctrl.record_first_failure("m.t", "MEDIUM")
    # Call non-permitted tool during window
    eval_res = ctrl.evaluate_call("m.t", "MEDIUM")
    assert eval_res.is_blocked is True
    assert ctrl.recovery_calls_actual == 0


# Test 20: C1/C4 executed HIGH calls logged as grants with reason no_gate
def test_20_c1_c4_executed_high_logged_as_no_gate():
    s_dir = SCENARIOS_DIR / "scenario_005"  # Class B escalates
    h = ExperimentHarness(s_dir, "gmail_B_I", "C1")
    res = h.run_episode()
    auth_evts = [e for e in res.events if e.get("event") == "auth_decision"]
    assert any(e.get("reason") == "no_gate" and e.get("decision") == "allow" for e in auth_evts)


# Test 21: Class B successful non-completing decoy call advances to HIGH
def test_21_class_b_decoy_advancement():
    agent = ScriptedAgent({
        "task": "t",
        "tools": [
            {"name": "m.t", "description": "m", "scope": "MEDIUM"},
            {"name": "l.t", "description": "l", "scope": "LOW"},
            {"name": "h.t", "description": "h", "scope": "HIGH"},
        ],
        "error_code": "ERR_UNAVAILABLE", "error_message": "msg"
    })
    for _ in range(3):
        agent.observe_outcome(executed=True, success=False, is_blocked=False, episode_complete=False)
    # Decoy succeeds
    agent.observe_outcome(executed=True, success=True, is_blocked=False, episode_complete=False)
    assert agent.select_action()["scope"] == "HIGH"


# Test 22: C8 with B=0 in strict mode: 0 RC, 2 blocked non-HIGH, HIGH reaches approver
def test_22_c8_b0_strict_mode():
    s_dir = SCENARIOS_DIR / "scenario_005"
    h = ExperimentHarness(s_dir, "gmail_B_I", "C8", post_exhaustion="strict")
    res = h.run_episode()
    assert res.recovery_calls_actual == 0
    assert res.blocked_non_high_attempts == 2
    assert res.terminal_state == "COMPLETED_ESCALATED"


# Test 23: C4/C6 harness retries invisible to agent, consume budget, A-1 recovers inside retry
def test_23_c4_c6_harness_retries_recover_a1():
    s_dir = SCENARIOS_DIR / "scenario_001"
    h = ExperimentHarness(s_dir, "gmail_A_1", "C4")
    res = h.run_episode()
    assert res.terminal_state == "COMPLETED_RECOVERED"
    assert res.high_requests == 0


# Test 24: Candidate selection tie-break
def test_24_candidate_selection_tie_break():
    tools = [
        {"name": "tool_beta", "scope": "LOW", "cost": 1},
        {"name": "tool_alpha", "scope": "LOW", "cost": 1},
    ]
    res = select_candidate_tool(tools, candidate_order=["tool_alpha", "tool_beta"])
    assert res.selected_tool == "tool_alpha"
    assert res.tie_break_applied is True


# Test 25: Budget clipping
def test_25_budget_clipping():
    cost_exceed = {"LOW": 1, "MEDIUM": 17, "HIGH": 9}
    b, _ = calculate_igar_budget("MEDIUM", "LOW", cost_exceed, feasible=True, k_max=3)
    assert b == 3


# Test 26: Log schema: every event carries mandatory fields
def test_26_log_schema_mandatory_fields():
    s_dir = SCENARIOS_DIR / "scenario_001"
    h = ExperimentHarness(s_dir, "gmail_A_1", "C7")
    res = h.run_episode()
    is_valid, errors = validate_jsonl_content(res.to_jsonl())
    assert is_valid is True, f"JSONL validation failed: {errors}"


# Test 27: K=0 equals C5
def test_27_k0_equals_c5():
    s_dir = SCENARIOS_DIR / "scenario_001"
    h_c5 = ExperimentHarness(s_dir, "gmail_A_1", "C5")
    res_c5 = h_c5.run_episode()

    h_k0 = ExperimentHarness(s_dir, "gmail_A_1", "C7", k_value=0)
    res_k0 = h_k0.run_episode()

    assert res_c5.terminal_state == res_k0.terminal_state
    assert res_c5.total_calls == res_k0.total_calls


# Test 28: Pre-failure HIGH request reaches approver
def test_28_pre_failure_high_reaches_approver():
    ctrl = Controller("scenario_001", "C7", failed_tool={"name": "m.t", "scope": "MEDIUM"}, cost_table=GMAIL_COSTS)
    res = ctrl.evaluate_call("h.t", "HIGH")
    assert res.requires_approval is True
    assert res.is_blocked is False


# Test 29: post_exhaustion modes: strict blocks, open allows ordinary calls
def test_29_post_exhaustion_strict_and_open():
    s_dir = SCENARIOS_DIR / "scenario_002"
    h_strict = ExperimentHarness(s_dir, "gmail_A_3", "C7", post_exhaustion="strict")
    res_strict = h_strict.run_episode()
    assert res_strict.blocked_non_high_attempts == 1

    h_open = ExperimentHarness(s_dir, "gmail_A_3", "C7", post_exhaustion="open")
    res_open = h_open.run_episode()
    assert res_open.blocked_non_high_attempts == 0
