"""Scenario consistency validator for FCA-IGAR research framework.

Implements all 8 consistency rules and suite validation constraints defined in:
- Spec Section 8.4 (Consistency validator)
- Spec Section 0.1 & Section 5 (18 scenarios and 10-scenario thesis subset)
- Spec Section 4 (Cost model, RHU, predicted_B calculation)
- Spec Section 6 (Approver policy and Class A/B requirements)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.igar_budget import calculate_igar_budget
from src.scenario_loader import (
    load_scenario_for_agent,
    load_controller_config,
    load_approver_policy,
    load_environment_config,
    load_ground_truth,
    load_scenario_index,
    get_thesis_10_scenario_subset,
    parse_yaml_str,
)

# Reference application costs from Spec Section 4
APP_COST_TABLES = {
    "gmail": {"LOW": 1, "MEDIUM": 3, "HIGH": 6},
    "slack": {"LOW": 1, "MEDIUM": 5, "HIGH": 6},
    "drive": {"LOW": 1, "MEDIUM": 4, "HIGH": 6},
}


class ValidationResult:
    """Holds validation status, errors, and warnings for a scenario or suite."""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_scenario(
    scenario_dir: str | Path,
    canonical_id: Optional[str] = None,
    index_entry: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """Validate a single scenario directory across all five files per Spec Section 8.4."""
    s_dir = Path(scenario_dir)
    res = ValidationResult(scenario_id=s_dir.name)

    # 1. Verify existence of all five required files
    required_files = [
        "scenario.yaml",
        "controller.yaml",
        "approver.yaml",
        "environment.yaml",
        "ground_truth.yaml",
    ]
    for rf in required_files:
        if not (s_dir / rf).is_file():
            res.add_error(f"Missing required scenario file: {rf}")
            return res

    # 2. Parse all five YAML files
    try:
        raw_scen = parse_yaml_str((s_dir / "scenario.yaml").read_text(encoding="utf-8"))
        raw_ctrl = parse_yaml_str((s_dir / "controller.yaml").read_text(encoding="utf-8"))
        raw_appr = parse_yaml_str((s_dir / "approver.yaml").read_text(encoding="utf-8"))
        raw_env = parse_yaml_str((s_dir / "environment.yaml").read_text(encoding="utf-8"))
        raw_gt = parse_yaml_str((s_dir / "ground_truth.yaml").read_text(encoding="utf-8"))
    except Exception as e:
        res.add_error(f"Failed to parse scenario files: {e}")
        return res

    if not isinstance(raw_scen, dict) or "scenario" not in raw_scen:
        res.add_error("Invalid scenario.yaml: missing 'scenario' key")
        return res
    if not isinstance(raw_ctrl, dict) or "controller" not in raw_ctrl:
        res.add_error("Invalid controller.yaml: missing 'controller' key")
        return res
    if not isinstance(raw_appr, dict) or "authorization_policy" not in raw_appr:
        res.add_error("Invalid approver.yaml: missing 'authorization_policy' key")
        return res
    if not isinstance(raw_env, dict) or "environment" not in raw_env:
        res.add_error("Invalid environment.yaml: missing 'environment' key")
        return res
    if not isinstance(raw_gt, dict) or "ground_truth" not in raw_gt:
        res.add_error("Invalid ground_truth.yaml: missing 'ground_truth' key")
        return res

    scenario = raw_scen["scenario"]
    controller = raw_ctrl["controller"]
    approver = raw_appr["authorization_policy"]
    environment = raw_env["environment"]
    ground_truth = raw_gt["ground_truth"]

    # Extract key properties
    cls = ground_truth.get("class")
    gt_feasible = ground_truth.get("feasible")
    needs_high = ground_truth.get("needs_high_to_complete")
    completing_tools = ground_truth.get("completing_tools", [])
    candidate_attempts_needed = ground_truth.get("candidate_attempts_needed")

    ctrl_id = controller.get("id")
    app = controller.get("app")
    failed_tool = controller.get("failed_tool")
    candidate_tool = controller.get("candidate_tool")
    candidate_order = controller.get("candidate_order")
    high_tool = controller.get("high_tool")
    ctrl_feasible = controller.get("feasible")
    predicted_B = controller.get("predicted_B")

    approvable_high = approver.get("approvable_high_tools", [])

    env_tools = environment.get("tools", {})
    scenario_tools = scenario.get("tools", [])

    # Extract depth from index or canonical_id if provided
    depth_val: Optional[Any] = None
    if index_entry:
        depth_val = index_entry.get("depth")
    elif canonical_id:
        parts = canonical_id.split("_")
        if len(parts) >= 3:
            depth_val = parts[2]

    # -------------------------------------------------------------------------
    # Rule 8: controller.id matches ^scenario_[0-9]{3}$ and contains no class letter or depth
    # -------------------------------------------------------------------------
    if not isinstance(ctrl_id, str) or not re.match(r"^scenario_[0-9]{3}$", ctrl_id):
        res.add_error(f"Rule 8 Violation: controller.id '{ctrl_id}' does not match '^scenario_[0-9]{{3}}$'")
    else:
        # Check that controller.id contains no class letter (A/B) or depth string
        if any(letter in ctrl_id.lower() for letter in ["_a_", "_b_", "depth"]):
            res.add_error(f"Rule 8 Violation: controller.id '{ctrl_id}' contains class or depth leak")

    # -------------------------------------------------------------------------
    # Rule 5: Tool inventory shape identical across all 18 scenarios
    # (3 tools, same fields: {name, description, scope}, exactly one per scope LOW, MEDIUM, HIGH)
    # -------------------------------------------------------------------------
    if len(scenario_tools) != 3:
        res.add_error(f"Rule 5 Violation: scenario.yaml must contain exactly 3 tools, got {len(scenario_tools)}")

    scopes_found = set()
    tool_names = set()
    scope_to_tool: Dict[str, str] = {}
    for t in scenario_tools:
        if not isinstance(t, dict):
            res.add_error("Rule 5 Violation: tool in scenario.yaml is not a mapping")
            continue
        t_name = t.get("name")
        t_desc = t.get("description")
        t_scope = t.get("scope")

        if not t_name or not isinstance(t_name, str):
            res.add_error(f"Rule 5 Violation: tool has invalid name: {t_name}")
        if not t_desc or not isinstance(t_desc, str):
            res.add_error(f"Rule 5 Violation: tool {t_name} has invalid description")
        if t_scope not in ("LOW", "MEDIUM", "HIGH"):
            res.add_error(f"Rule 5 Violation: tool {t_name} has invalid scope: {t_scope}")

        scopes_found.add(t_scope)
        if t_name:
            tool_names.add(t_name)
            if t_scope:
                scope_to_tool[t_scope] = t_name

    if scopes_found != {"LOW", "MEDIUM", "HIGH"}:
        res.add_error(f"Rule 5 Violation: expected scopes {{'LOW', 'MEDIUM', 'HIGH'}}, found {scopes_found}")

    # Identical error code and message check (Spec Section 8.1 & Section 10 Test 18)
    if scenario.get("error_code") != "ERR_UNAVAILABLE":
        res.add_error(f"Rule 5 Violation: error_code must be 'ERR_UNAVAILABLE', got {scenario.get('error_code')}")
    if scenario.get("error_message") != "Service temporarily unavailable":
        res.add_error(f"Rule 5 Violation: error_message must be 'Service temporarily unavailable', got {scenario.get('error_message')}")

    # Environment tools must match scenario tools
    if set(env_tools.keys()) != tool_names:
        res.add_error(f"Environment tools mismatch: expected {tool_names}, got {set(env_tools.keys())}")

    # -------------------------------------------------------------------------
    # Rule 7: Failed tool is MEDIUM-tagged, candidate tool (Class A) is LOW-tagged
    # candidate_tool is first entry of candidate_order among lowest-cost feasible candidates; null for Class B
    # -------------------------------------------------------------------------
    med_tool_name = scope_to_tool.get("MEDIUM")
    low_tool_name = scope_to_tool.get("LOW")
    high_tool_name = scope_to_tool.get("HIGH")

    if not isinstance(failed_tool, dict) or failed_tool.get("scope") != "MEDIUM" or failed_tool.get("name") != med_tool_name:
        res.add_error(f"Rule 7 Violation: failed_tool must be MEDIUM tool '{med_tool_name}', got {failed_tool}")

    if not isinstance(high_tool, dict) or high_tool.get("scope") != "HIGH" or high_tool.get("name") != high_tool_name:
        res.add_error(f"Rule 7 Violation: high_tool must be HIGH tool '{high_tool_name}', got {high_tool}")

    if cls == "A":
        if not isinstance(candidate_tool, dict) or candidate_tool.get("scope") != "LOW" or candidate_tool.get("name") != low_tool_name:
            res.add_error(f"Rule 7 Violation: Class A candidate_tool must be LOW tool '{low_tool_name}', got {candidate_tool}")
        if not isinstance(candidate_order, list) or len(candidate_order) == 0:
            res.add_error("Rule 7 Violation: Class A candidate_order must be a non-empty list")
        elif candidate_order[0] != low_tool_name:
            res.add_error(f"Rule 7 Violation: candidate_order[0] must be '{low_tool_name}', got {candidate_order[0]}")
    elif cls == "B":
        if candidate_tool is not None:
            res.add_error(f"Rule 7 Violation: Class B candidate_tool must be null, got {candidate_tool}")
        if candidate_order is not None:
            res.add_error(f"Rule 7 Violation: Class B candidate_order must be null, got {candidate_order}")

    # -------------------------------------------------------------------------
    # Rule 1: ground_truth.feasible == (class == A) and needs_high_to_complete == (class == B)
    # -------------------------------------------------------------------------
    if cls not in ("A", "B"):
        res.add_error(f"Rule 1 Violation: class must be 'A' or 'B', got '{cls}'")
    else:
        if gt_feasible != (cls == "A"):
            res.add_error(f"Rule 1 Violation: ground_truth.feasible ({gt_feasible}) != (class == A) for class {cls}")
        if needs_high != (cls == "B"):
            res.add_error(f"Rule 1 Violation: needs_high_to_complete ({needs_high}) != (class == B) for class {cls}")

    # -------------------------------------------------------------------------
    # Rule 2: Class B: completing_tools == [high tool], candidate_tool is null,
    # and the high tool is in approvable_high_tools
    # -------------------------------------------------------------------------
    if cls == "B":
        if completing_tools != [high_tool_name]:
            res.add_error(f"Rule 2 Violation: Class B completing_tools must be ['{high_tool_name}'], got {completing_tools}")
        if candidate_tool is not None:
            res.add_error("Rule 2 Violation: Class B candidate_tool must be null")
        if not isinstance(approvable_high, list) or high_tool_name not in approvable_high:
            res.add_error(f"Rule 2 Violation: Class B HIGH tool '{high_tool_name}' must be in approvable_high_tools ({approvable_high})")
        if candidate_attempts_needed is not None:
            res.add_error(f"Rule 2 Violation: Class B candidate_attempts_needed must be null, got {candidate_attempts_needed}")

    # -------------------------------------------------------------------------
    # Rule 3: Class A: candidate tool and failed tool are in completing_tools
    # HIGH tool in completing_tools only if it genuinely accomplishes task.
    # Class A HIGH tool approvable but not completing emits WARNING.
    # For Class B, HIGH must be both approvable and completing.
    # -------------------------------------------------------------------------
    if cls == "A":
        if med_tool_name not in completing_tools:
            res.add_error(f"Rule 3 Violation: Class A failed tool '{med_tool_name}' must be in completing_tools")
        if low_tool_name not in completing_tools:
            res.add_error(f"Rule 3 Violation: Class A candidate tool '{low_tool_name}' must be in completing_tools")

        # Check if HIGH tool is approvable but not completing (WARNING per Spec Sec 8.4)
        if high_tool_name in approvable_high and high_tool_name not in completing_tools:
            res.add_warning(
                f"Rule 3 Warning: Class A scenario '{s_dir.name}' has approvable HIGH tool '{high_tool_name}' "
                "outside completing_tools. If approved, task will end FAILED."
            )

    # -------------------------------------------------------------------------
    # Rule 4: Class A, D finite: failed tool's success_attempt == D + 1.
    # Class B and A-I: null.
    # -------------------------------------------------------------------------
    failed_env = env_tools.get(med_tool_name, {})
    failed_success_attempt = failed_env.get("success_attempt")

    if cls == "B":
        if failed_success_attempt is not None:
            res.add_error(f"Rule 4 Violation: Class B failed tool success_attempt must be null, got {failed_success_attempt}")
    elif cls == "A":
        if depth_val in (1, "1"):
            if failed_success_attempt != 2:
                res.add_error(f"Rule 4 Violation: D=1 failed tool success_attempt must be 2, got {failed_success_attempt}")
        elif depth_val in (3, "3", "3b"):
            if failed_success_attempt != 4:
                res.add_error(f"Rule 4 Violation: D=3 failed tool success_attempt must be 4, got {failed_success_attempt}")
        elif depth_val in ("inf", "I", "I2", None):
            # For A-I (persistent)
            if depth_val in ("I", "inf") and failed_success_attempt is not None:
                res.add_error(f"Rule 4 Violation: Persistent Class A failed tool success_attempt must be null, got {failed_success_attempt}")

    # -------------------------------------------------------------------------
    # Rule 5 (Decoy check): In Class B the LOW decoy has success_attempt: 1 and is not in completing_tools
    # -------------------------------------------------------------------------
    low_env = env_tools.get(low_tool_name, {})
    low_success_attempt = low_env.get("success_attempt")
    if cls == "B":
        if low_success_attempt != 1:
            res.add_error(f"Rule 5 Violation: Class B decoy LOW tool success_attempt must be 1, got {low_success_attempt}")
        if low_tool_name in completing_tools:
            res.add_error(f"Rule 5 Violation: Class B decoy LOW tool '{low_tool_name}' must NOT be in completing_tools")
    elif cls == "A":
        # Candidate tool success_attempt equals candidate_attempts_needed
        if candidate_attempts_needed in (1, 2):
            if low_success_attempt != candidate_attempts_needed:
                res.add_error(
                    f"Candidate attempts mismatch: expected {candidate_attempts_needed}, environment has {low_success_attempt}"
                )

    # HIGH tool success attempt must always be 1
    high_env = env_tools.get(high_tool_name, {})
    if high_env.get("success_attempt") != 1:
        res.add_error(f"HIGH tool success_attempt must be 1, got {high_env.get('success_attempt')}")

    # -------------------------------------------------------------------------
    # Rule 6: predicted_B matches the sec 4 formula
    # -------------------------------------------------------------------------
    if app not in APP_COST_TABLES:
        res.add_error(f"Rule 6 Violation: unknown app '{app}'")
    else:
        costs = APP_COST_TABLES[app]
        expected_B, _ = calculate_igar_budget(
            failed_scope="MEDIUM",
            candidate_scope="LOW",
            cost_table=costs,
            feasible=(cls == "A"),
            k_max=2,
        )
        if predicted_B != expected_B:
            res.add_error(f"Rule 6 Violation: predicted_B ({predicted_B}) != expected ({expected_B}) for app '{app}' and class '{cls}'")

    return res


class SuiteValidationResult:
    """Holds summary validation results across all 18 scenarios."""

    def __init__(self):
        self.scenario_results: Dict[str, ValidationResult] = {}
        self.suite_errors: List[str] = []
        self.suite_warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        if self.suite_errors:
            return False
        return all(r.is_valid for r in self.scenario_results.values())


def validate_scenario_suite(
    scenarios_root: str | Path,
    index_file: str | Path,
) -> SuiteValidationResult:
    """Validate entire 18-scenario suite and scenario_index.yaml per Section 8.4 & Section 0.1."""
    root = Path(scenarios_root)
    idx_path = Path(index_file)
    suite_res = SuiteValidationResult()

    if not idx_path.is_file():
        suite_res.suite_errors.append(f"Missing scenario_index.yaml at: {idx_path}")
        return suite_res

    try:
        index_data = load_scenario_index(idx_path)
    except Exception as e:
        suite_res.suite_errors.append(f"Failed to load scenario_index.yaml: {e}")
        return suite_res

    entries = index_data.get("scenarios", [])
    if not isinstance(entries, list):
        suite_res.suite_errors.append("Invalid scenario_index.yaml: 'scenarios' is not a list")
        return suite_res

    # Suite check: exactly 18 scenarios
    if len(entries) != 18:
        suite_res.suite_errors.append(f"Suite Violation: expected 18 scenarios in index, found {len(entries)}")

    # Track suite-level constraints
    seen_opaque_ids: Set[str] = set()
    seen_canonical_ids: Set[str] = set()
    predicted_b_values: Set[int] = set()
    thesis_subset_found: List[str] = []
    class_a_approvable_high_count = 0
    apps_with_class_a_approvable: Set[str] = set()

    for entry in entries:
        s_id = entry.get("id")
        canon_id = entry.get("canonical_id")
        app = entry.get("app")
        cls = entry.get("class")
        is_subset = entry.get("is_thesis_subset", False)

        if not s_id or not canon_id:
            suite_res.suite_errors.append(f"Index entry missing id or canonical_id: {entry}")
            continue

        if s_id in seen_opaque_ids:
            suite_res.suite_errors.append(f"Duplicate opaque ID in index: {s_id}")
        seen_opaque_ids.add(s_id)

        if canon_id in seen_canonical_ids:
            suite_res.suite_errors.append(f"Duplicate canonical ID in index: {canon_id}")
        seen_canonical_ids.add(canon_id)

        if is_subset:
            thesis_subset_found.append(canon_id)

        # Validate directory
        s_dir = root / s_id
        if not s_dir.is_dir():
            suite_res.suite_errors.append(f"Scenario directory missing: {s_dir}")
            continue

        scen_res = validate_scenario(s_dir, canonical_id=canon_id, index_entry=entry)
        suite_res.scenario_results[s_id] = scen_res

        # Check approver policy on Class A
        if scen_res.is_valid:
            ctrl = load_controller_config(s_dir)
            predicted_b_values.add(ctrl.get("predicted_B"))

            if cls == "A":
                approver = load_approver_policy(s_dir)
                approvable = approver.get("approvable_high_tools", [])
                if len(approvable) > 0:
                    class_a_approvable_high_count += 1
                    apps_with_class_a_approvable.add(app)

    # Suite check: Rule 6 requirement - suite MUST contain B=1 and B=2
    if not ({1, 2}.issubset(predicted_b_values)):
        suite_res.suite_errors.append(
            f"Rule 6 Suite Violation: suite must contain both B=1 and B=2, found {predicted_b_values}"
        )

    # Suite check: Thesis 10-scenario subset check (Spec Section 0.1 & Section 5)
    expected_thesis_subset = sorted(get_thesis_10_scenario_subset())
    actual_thesis_subset = sorted(thesis_subset_found)
    if actual_thesis_subset != expected_thesis_subset:
        suite_res.suite_errors.append(
            f"Thesis Subset Violation: expected {expected_thesis_subset}, found {actual_thesis_subset}"
        )

    # Suite check: Section 6 Step 5:
    # "Count Class A scenarios with a non-empty approvable_high_tools. If zero, GUER/UGR collapse.
    # Widen wording of about 4 Class A tasks (at least one per app)"
    if class_a_approvable_high_count < 3:
        suite_res.suite_warnings.append(
            f"Spec Section 6 Step 5: expected ~4 Class A scenarios with approvable HIGH tools, found {class_a_approvable_high_count}"
        )
    if len(apps_with_class_a_approvable) < 3:
        suite_res.suite_warnings.append(
            f"Spec Section 6 Step 5: expected at least one Class A approvable HIGH per app, covered apps: {apps_with_class_a_approvable}"
        )

    return suite_res
