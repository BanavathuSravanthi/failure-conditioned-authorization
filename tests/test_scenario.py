"""Unit, isolation, and consistency validation tests for Milestone 2 Stage 4.

Authority:
- Spec Section 1 (Data separation and strict file access boundaries)
- Spec Section 0.1 & Section 5 (18 scenarios and 10-scenario thesis subset)
- Spec Section 4 (Cost model and predicted_B calculation)
- Spec Section 8 & 8.4 (File schemas and consistency validator rules 1-8)
- Spec Section 10 (Mandatory tests 7a, 15, 17, 18)
"""
import copy
from pathlib import Path
import pytest

from src.scenario_loader import (
    load_scenario_for_agent,
    load_controller_config,
    load_approver_policy,
    load_environment_config,
    load_ground_truth,
    load_scenario_index,
    get_thesis_10_scenario_subset,
    dump_yaml_str,
    parse_yaml_str,
)
from src.scenario_validator import (
    validate_scenario,
    validate_scenario_suite,
    APP_COST_TABLES,
)


SCENARIOS_DIR = Path("scenarios")
INDEX_PATH = SCENARIOS_DIR / "scenario_index.yaml"


# ============================================================================
# 1. Full 18-Scenario Suite & Index Tests (Spec Section 8.4 & Test 17, 18)
# ============================================================================

def test_full_scenario_suite_validates_cleanly():
    """Spec Section 8.4 & Section 10 Test 17:
    Consistency validator passes for all 18 scenarios with zero errors.
    """
    assert SCENARIOS_DIR.is_dir(), "scenarios/ directory must exist"
    assert INDEX_PATH.is_file(), "scenario_index.yaml must exist"

    suite_res = validate_scenario_suite(SCENARIOS_DIR, INDEX_PATH)
    assert suite_res.is_valid, f"Suite validation failed with errors: {suite_res.suite_errors}"
    assert len(suite_res.scenario_results) == 18, f"Expected 18 validated scenarios, got {len(suite_res.scenario_results)}"

    for sid, scen_res in suite_res.scenario_results.items():
        assert scen_res.is_valid, f"Scenario {sid} failed validation: {scen_res.errors}"


def test_thesis_10_scenario_subset():
    """Spec Section 0.1 & Section 5:
    The 10-scenario thesis subset is fixed, immutable, and exactly matches Table 4.1:
    gmail_A_1, slack_A_1, drive_A_1, gmail_A_3, slack_A_3, drive_A_3,
    gmail_A_I, slack_A_I, gmail_B_I, slack_B_I.
    """
    subset = get_thesis_10_scenario_subset()
    assert len(subset) == 10
    expected_subset = [
        "gmail_A_1", "slack_A_1", "drive_A_1",
        "gmail_A_3", "slack_A_3", "drive_A_3",
        "gmail_A_I", "slack_A_I",
        "gmail_B_I", "slack_B_I"
    ]
    assert sorted(subset) == sorted(expected_subset)

    index_data = load_scenario_index(INDEX_PATH)
    actual_flagged = [
        s["canonical_id"] for s in index_data["scenarios"]
        if s.get("is_thesis_subset")
    ]
    assert sorted(actual_flagged) == sorted(expected_subset)


def test_scenario_counts_and_distribution():
    """Spec Section 5: 18 scenarios total, 6 per app (Gmail, Slack, Drive),
    12 Class A and 6 Class B.
    """
    index_data = load_scenario_index(INDEX_PATH)
    scenarios = index_data["scenarios"]
    assert len(scenarios) == 18

    app_counts = {"gmail": 0, "slack": 0, "drive": 0}
    class_counts = {"A": 0, "B": 0}

    for s in scenarios:
        app_counts[s["app"]] += 1
        class_counts[s["class"]] += 1

    assert app_counts == {"gmail": 6, "slack": 6, "drive": 6}
    assert class_counts == {"A": 12, "B": 6}


def test_rule_6_both_b1_and_b2_occur_in_suite():
    """Spec Section 4 & Section 8.4 Rule 6:
    Suite MUST contain at least one B=1 and at least one B=2 for Class A.
    """
    index_data = load_scenario_index(INDEX_PATH)
    predicted_b_values = set()

    for s in index_data["scenarios"]:
        ctrl = load_controller_config(SCENARIOS_DIR / s["id"])
        predicted_b_values.add(ctrl["predicted_B"])

    assert {0, 1, 2}.issubset(predicted_b_values)


def test_section_6_step_5_class_a_approvable_high_scenarios():
    """Spec Section 6 Step 5:
    At least 3-4 Class A scenarios have non-empty approvable_high_tools
    with at least one per app, ensuring GUER/UGR do not trivially collapse to 0.
    """
    index_data = load_scenario_index(INDEX_PATH)
    class_a_approvable = []
    apps_covered = set()

    for s in index_data["scenarios"]:
        if s["class"] == "A":
            policy = load_approver_policy(SCENARIOS_DIR / s["id"])
            if len(policy.get("approvable_high_tools", [])) > 0:
                class_a_approvable.append(s["canonical_id"])
                apps_covered.add(s["app"])

    assert len(class_a_approvable) >= 3, f"Expected >= 3 Class A approvable, got {class_a_approvable}"
    assert apps_covered == {"gmail", "slack", "drive"}


# ============================================================================
# 2. Component Loader Boundary & Security Isolation Tests (Spec Sec 1 & Test 7, 15)
# ============================================================================

def test_agent_loader_isolation(tmp_path):
    """Spec Section 1 & Section 10 Test 15:
    Agent loader reads strictly scenario.yaml and raises if forbidden keys appear.
    """
    # Valid scenario.yaml
    valid_scenario = {
        "scenario": {
            "task": "Test task",
            "tools": [
                {"name": "t.med", "description": "med desc", "scope": "MEDIUM"},
                {"name": "t.low", "description": "low desc", "scope": "LOW"},
                {"name": "t.high", "description": "high desc", "scope": "HIGH"}
            ],
            "error_code": "ERR_UNAVAILABLE",
            "error_message": "Service temporarily unavailable"
        }
    }
    s_dir = tmp_path / "valid_agent"
    s_dir.mkdir()
    (s_dir / "scenario.yaml").write_text(dump_yaml_str(valid_scenario), encoding="utf-8")

    loaded = load_scenario_for_agent(s_dir)
    assert loaded["task"] == "Test task"
    assert len(loaded["tools"]) == 3

    # Inject forbidden canary keys
    for forbidden_key in ["class", "ground_truth", "controller", "depth", "feasible"]:
        bad_dir = tmp_path / f"bad_agent_{forbidden_key}"
        bad_dir.mkdir()
        bad_scenario = copy.deepcopy(valid_scenario)
        bad_scenario["scenario"][forbidden_key] = "CANARY_LEAK"
        (bad_dir / "scenario.yaml").write_text(dump_yaml_str(bad_scenario), encoding="utf-8")

        with pytest.raises(PermissionError):
            load_scenario_for_agent(bad_dir)


def test_controller_loader_isolation(tmp_path):
    """Spec Section 1 & Section 8.2:
    Controller loader reads strictly controller.yaml and rejects leaked labels or non-opaque IDs.
    """
    valid_ctrl = {
        "controller": {
            "id": "scenario_099",
            "app": "gmail",
            "seed": 42,
            "failed_tool": {"name": "gmail.send_draft", "scope": "MEDIUM"},
            "candidate_tool": {"name": "gmail.create_draft", "scope": "LOW"},
            "candidate_order": ["gmail.create_draft"],
            "high_tool": {"name": "gmail.delete_thread", "scope": "HIGH"},
            "feasible": True,
            "predicted_B": 1
        }
    }
    s_dir = tmp_path / "valid_ctrl"
    s_dir.mkdir()
    (s_dir / "controller.yaml").write_text(dump_yaml_str(valid_ctrl), encoding="utf-8")

    loaded = load_controller_config(s_dir)
    assert loaded["id"] == "scenario_099"

    # Reject non-opaque canonical ID in controller.yaml
    bad_dir = tmp_path / "bad_ctrl_id"
    bad_dir.mkdir()
    bad_ctrl = copy.deepcopy(valid_ctrl)
    bad_ctrl["controller"]["id"] = "gmail_A_3"
    (bad_dir / "controller.yaml").write_text(dump_yaml_str(bad_ctrl), encoding="utf-8")

    with pytest.raises(ValueError, match="controller.id must match"):
        load_controller_config(bad_dir)

    # Reject forbidden keys (class, ground_truth, authorization_policy)
    for forbidden_key in ["class", "ground_truth", "needs_high_to_complete"]:
        leak_dir = tmp_path / f"leak_{forbidden_key}"
        leak_dir.mkdir()
        leak_ctrl = copy.deepcopy(valid_ctrl)
        leak_ctrl["controller"][forbidden_key] = "LEAK"
        (leak_dir / "controller.yaml").write_text(dump_yaml_str(leak_ctrl), encoding="utf-8")

        with pytest.raises(PermissionError):
            load_controller_config(leak_dir)


def test_approver_loader_isolation(tmp_path):
    """Spec Section 1 & Section 6:
    Approver loader loads strictly approver.yaml and rejects ground_truth or scenario label leaks.
    """
    valid_appr = {
        "authorization_policy": {
            "approvable_high_tools": ["gmail.delete_thread"],
            "maximum_approvable_scope": "HIGH"
        }
    }
    s_dir = tmp_path / "valid_appr"
    s_dir.mkdir()
    (s_dir / "approver.yaml").write_text(dump_yaml_str(valid_appr), encoding="utf-8")

    loaded = load_approver_policy(s_dir)
    assert loaded["approvable_high_tools"] == ["gmail.delete_thread"]

    # Reject leaked forbidden labels in approver policy
    bad_dir = tmp_path / "bad_appr"
    bad_dir.mkdir()
    bad_appr = copy.deepcopy(valid_appr)
    bad_appr["authorization_policy"]["class"] = "A"
    (bad_dir / "approver.yaml").write_text(dump_yaml_str(bad_appr), encoding="utf-8")

    with pytest.raises(PermissionError):
        load_approver_policy(bad_dir)


# ============================================================================
# 3. Targeted Consistency Validator Rule Tests (Spec Section 8.4 Rules 1-8)
# ============================================================================

@pytest.fixture
def base_valid_scenario_dir(tmp_path):
    """Create a pristine valid scenario directory (scenario_001 structure)."""
    s_dir = tmp_path / "scenario_test"
    s_dir.mkdir()

    scen = {
        "scenario": {
            "task": "Clean test task",
            "tools": [
                {"name": "gmail.send_draft", "description": "send draft", "scope": "MEDIUM"},
                {"name": "gmail.create_draft", "description": "create draft", "scope": "LOW"},
                {"name": "gmail.delete_thread", "description": "delete thread", "scope": "HIGH"},
            ],
            "error_code": "ERR_UNAVAILABLE",
            "error_message": "Service temporarily unavailable"
        }
    }
    ctrl = {
        "controller": {
            "id": "scenario_001",
            "app": "gmail",
            "seed": 1001,
            "failed_tool": {"name": "gmail.send_draft", "scope": "MEDIUM"},
            "candidate_tool": {"name": "gmail.create_draft", "scope": "LOW"},
            "candidate_order": ["gmail.create_draft"],
            "high_tool": {"name": "gmail.delete_thread", "scope": "HIGH"},
            "feasible": True,
            "predicted_B": 1
        }
    }
    appr = {
        "authorization_policy": {
            "approvable_high_tools": [],
            "maximum_approvable_scope": "HIGH"
        }
    }
    env = {
        "environment": {
            "tools": {
                "gmail.send_draft": {"success_attempt": 2},
                "gmail.create_draft": {"success_attempt": 1},
                "gmail.delete_thread": {"success_attempt": 1}
            }
        }
    }
    gt = {
        "ground_truth": {
            "class": "A",
            "feasible": True,
            "candidate_attempts_needed": 1,
            "completing_tools": ["gmail.send_draft", "gmail.create_draft"],
            "needs_high_to_complete": False
        }
    }

    (s_dir / "scenario.yaml").write_text(dump_yaml_str(scen), encoding="utf-8")
    (s_dir / "controller.yaml").write_text(dump_yaml_str(ctrl), encoding="utf-8")
    (s_dir / "approver.yaml").write_text(dump_yaml_str(appr), encoding="utf-8")
    (s_dir / "environment.yaml").write_text(dump_yaml_str(env), encoding="utf-8")
    (s_dir / "ground_truth.yaml").write_text(dump_yaml_str(gt), encoding="utf-8")

    return s_dir


def test_validator_detects_missing_file(base_valid_scenario_dir):
    """Validator catches missing file among the 5 files."""
    (base_valid_scenario_dir / "controller.yaml").unlink()
    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Missing required scenario file: controller.yaml" in e for e in res.errors)


def test_validator_rule_1_violation(base_valid_scenario_dir):
    """Rule 1: ground_truth.feasible == (class == A) and needs_high_to_complete == (class == B)."""
    gt_file = base_valid_scenario_dir / "ground_truth.yaml"
    gt = load_ground_truth(base_valid_scenario_dir)
    gt["feasible"] = False  # Mismatch for Class A!
    gt_file.write_text(dump_yaml_str({"ground_truth": gt}), encoding="utf-8")

    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Rule 1 Violation" in e for e in res.errors)


def test_validator_rule_2_violation(base_valid_scenario_dir):
    """Rule 2: Class B: completing_tools == [high tool], candidate_tool is null,
    and high tool is in approvable_high_tools.
    """
    # Turn into Class B but leave candidate_tool non-null and high_tool unapprovable
    gt = {
        "class": "B",
        "feasible": False,
        "candidate_attempts_needed": None,
        "completing_tools": ["gmail.delete_thread"],
        "needs_high_to_complete": True
    }
    (base_valid_scenario_dir / "ground_truth.yaml").write_text(
        dump_yaml_str({"ground_truth": gt}), encoding="utf-8"
    )

    # Controller still has candidate_tool non-null and approver has empty list
    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Rule 2 Violation" in e for e in res.errors)


def test_validator_rule_3_warning_vs_error(base_valid_scenario_dir):
    """Rule 3: In Class A, candidate and failed must be in completing_tools.
    Approvable HIGH tool outside completing_tools emits a WARNING, not an error.
    """
    # Make HIGH tool approvable in Class A
    appr = {
        "authorization_policy": {
            "approvable_high_tools": ["gmail.delete_thread"],
            "maximum_approvable_scope": "HIGH"
        }
    }
    (base_valid_scenario_dir / "approver.yaml").write_text(
        dump_yaml_str(appr), encoding="utf-8"
    )

    res = validate_scenario(base_valid_scenario_dir)
    assert res.is_valid, f"Expected valid scenario with warning, got errors: {res.errors}"
    assert len(res.warnings) == 1
    assert "Rule 3 Warning" in res.warnings[0]


def test_validator_rule_4_violation(base_valid_scenario_dir):
    """Rule 4: Class A, D finite: failed tool's success_attempt == D + 1."""
    env = load_environment_config(base_valid_scenario_dir)
    env["tools"]["gmail.send_draft"]["success_attempt"] = 99  # Mismatch for D=1 (expected 2)
    (base_valid_scenario_dir / "environment.yaml").write_text(
        dump_yaml_str({"environment": env}), encoding="utf-8"
    )

    res = validate_scenario(base_valid_scenario_dir, canonical_id="gmail_A_1")
    assert not res.is_valid
    assert any("Rule 4 Violation" in e for e in res.errors)


def test_validator_rule_5_tool_shape_violation(base_valid_scenario_dir):
    """Rule 5: Exactly 3 tools, LOW, MEDIUM, HIGH, identical fields."""
    scen = load_scenario_for_agent(base_valid_scenario_dir)
    # Remove one tool (leaving only 2)
    scen["tools"] = scen["tools"][:2]
    (base_valid_scenario_dir / "scenario.yaml").write_text(
        dump_yaml_str({"scenario": scen}), encoding="utf-8"
    )

    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Rule 5 Violation" in e for e in res.errors)


def test_validator_rule_6_predicted_b_mismatch(base_valid_scenario_dir):
    """Rule 6: predicted_B must match Spec Section 4 formula."""
    ctrl = load_controller_config(base_valid_scenario_dir)
    ctrl["predicted_B"] = 99  # Invalid budget for Gmail (expected 1)
    (base_valid_scenario_dir / "controller.yaml").write_text(
        dump_yaml_str({"controller": ctrl}), encoding="utf-8"
    )

    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Rule 6 Violation" in e for e in res.errors)


def test_validator_rule_7_wrong_scope_mapping(base_valid_scenario_dir):
    """Rule 7: Failed tool must be MEDIUM, candidate must be LOW."""
    ctrl = load_controller_config(base_valid_scenario_dir)
    ctrl["failed_tool"] = {"name": "gmail.create_draft", "scope": "LOW"}  # Failed tool cannot be LOW!
    (base_valid_scenario_dir / "controller.yaml").write_text(
        dump_yaml_str({"controller": ctrl}), encoding="utf-8"
    )

    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Rule 7 Violation" in e for e in res.errors)


def test_validator_rule_8_non_opaque_id(base_valid_scenario_dir):
    """Rule 8: controller.id must match ^scenario_[0-9]{3}$ and contain no class or depth leak."""
    ctrl = load_controller_config(base_valid_scenario_dir)
    ctrl["id"] = "scenario_001_A_depth1"
    (base_valid_scenario_dir / "controller.yaml").write_text(
        dump_yaml_str({"controller": ctrl}), encoding="utf-8"
    )

    res = validate_scenario(base_valid_scenario_dir)
    assert not res.is_valid
    assert any("Rule 8 Violation" in e for e in res.errors)


# ============================================================================
# 4. Pure-Python YAML Parser Edge Case Tests
# ============================================================================

def test_pure_python_yaml_parser_edge_cases():
    """Verify built-in pure-Python YAML parser on all permitted constructs."""
    yaml_text = """
    # Comment at top
    app: gmail
    seed: 42
    is_active: true
    is_dormant: false
    empty_val: null
    nested:
      k1: "hello world"
      k2: 123
      k3: [a, b, c]
      k4: []
    tools:
      - name: tool.one
        scope: LOW
      - name: tool.two
        scope: HIGH
    """
    parsed = parse_yaml_str(yaml_text)
    assert parsed["app"] == "gmail"
    assert parsed["seed"] == 42
    assert parsed["is_active"] is True
    assert parsed["is_dormant"] is False
    assert parsed["empty_val"] is None
    assert parsed["nested"]["k1"] == "hello world"
    assert parsed["nested"]["k2"] == 123
    assert parsed["nested"]["k3"] == ["a", "b", "c"]
    assert parsed["nested"]["k4"] == []
    assert len(parsed["tools"]) == 2
    assert parsed["tools"][0] == {"name": "tool.one", "scope": "LOW"}
    assert parsed["tools"][1] == {"name": "tool.two", "scope": "HIGH"}
