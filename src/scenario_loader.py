"""Scenario loader module for FCA-IGAR research framework.

Enforces strict five-file separation and data isolation per Spec Section 1 and Section 8:
- scenario.yaml (agent-visible only)
- controller.yaml (controller-only)
- approver.yaml (approver-only)
- environment.yaml (executor-only)
- ground_truth.yaml (evaluator-only)
- scenario_index.yaml (evaluator-only offline mapping)

Zero external dependencies: uses built-in YAML parser fallback when PyYAML is unavailable.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
    _HAS_PYYAML = True
except ImportError:
    yaml = None  # type: ignore
    _HAS_PYYAML = False


# ============================================================================
# Pure-Python Robust YAML Parser & Serializer Fallback
# ============================================================================

def parse_yaml_str(content: str) -> Any:
    """Parse YAML content using PyYAML if present, or deterministic pure-Python parser."""
    if _HAS_PYYAML:
        return yaml.safe_load(content)
    return _pure_python_yaml_parse(content)


def dump_yaml_str(data: Any, indent: int = 0) -> str:
    """Deterministic, clean YAML dumper for scenario structures."""
    if _HAS_PYYAML:
        return yaml.dump(data, sort_keys=False, default_flow_style=False)
    return _pure_python_yaml_dump(data, indent=indent)


def _pure_python_yaml_dump(obj: Any, indent: int = 0) -> str:
    """Recursively dump Python primitives into valid, clean YAML format."""
    sp = " " * indent
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, str):
        if "\n" in obj or ":" in obj or "#" in obj or obj.strip() in ("true", "false", "null", ""):
            # Quote special strings
            escaped = obj.replace('"', '\\"')
            return f'"{escaped}"'
        return obj
    elif isinstance(obj, list):
        if len(obj) == 0:
            return "[]"
        # Check if list contains only primitives (small inline list)
        if all(isinstance(x, (str, int, float, bool)) for x in obj) and len(obj) <= 2:
            items_str = ", ".join(_pure_python_yaml_dump(x, 0) for x in obj)
            return f"[{items_str}]"
        lines = []
        for item in obj:
            if isinstance(item, dict):
                # block dict inside list
                item_dump = _pure_python_yaml_dump(item, indent + 2)
                item_lines = item_dump.splitlines()
                lines.append(f"{sp}- {item_lines[0].lstrip()}")
                for l in item_lines[1:]:
                    lines.append(l)
            else:
                lines.append(f"{sp}- {_pure_python_yaml_dump(item, indent + 2)}")
        return "\n".join(lines)
    elif isinstance(obj, dict):
        if len(obj) == 0:
            return "{}"
        lines = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and (isinstance(v, dict) and len(v) > 0 or isinstance(v, list) and len(v) > 0 and not (all(isinstance(x, (str, int, float, bool)) for x in v) and len(v) <= 2)):
                lines.append(f"{sp}{k}:")
                lines.append(_pure_python_yaml_dump(v, indent + 2))
            else:
                lines.append(f"{sp}{k}: {_pure_python_yaml_dump(v, indent + 2)}")
        return "\n".join(lines)
    return str(obj)


def _parse_scalar(val: str) -> Any:
    """Parse scalar token into Python typed value."""
    val = val.strip()
    if not val:
        return None
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    if val.lower() in ("null", "none", "~"):
        return None
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        items = [x.strip() for x in inner.split(",") if x.strip()]
        return [_parse_scalar(x) for x in items]
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _pure_python_yaml_parse(content: str) -> Any:
    """Robust fallback YAML parser supporting dictionaries, lists, and primitives."""
    raw_lines = content.splitlines()
    clean_lines: List[tuple[int, str]] = []
    for line in raw_lines:
        # Strip comments
        no_comm = re.sub(r'#.*$', '', line)
        if not no_comm.strip():
            continue
        indent = len(no_comm) - len(no_comm.lstrip())
        clean_lines.append((indent, no_comm.strip()))

    if not clean_lines:
        return None

    def parse_block(idx: int, current_indent: int) -> tuple[Any, int]:
        if idx >= len(clean_lines):
            return None, idx

        first_indent, first_text = clean_lines[idx]
        if first_text.startswith("- "):
            # It is a list
            items = []
            while idx < len(clean_lines):
                ind, text = clean_lines[idx]
                if ind < current_indent:
                    break
                if ind == current_indent and text.startswith("- "):
                    item_text = text[2:].strip()
                    idx += 1
                    if not item_text:
                        # Sub-block item
                        sub_val, idx = parse_block(idx, ind + 2)
                        items.append(sub_val)
                    elif ":" in item_text:
                        # Inline dict key in list item: e.g. - name: val
                        # Collect all subsequent lines belonging to this dict
                        dict_data = {}
                        k, v = item_text.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if v:
                            dict_data[k] = _parse_scalar(v)
                        else:
                            sub_v, idx = parse_block(idx, ind + 2)
                            dict_data[k] = sub_v
                        # Read further dict fields with indent > ind
                        while idx < len(clean_lines):
                            sub_ind, sub_text = clean_lines[idx]
                            if sub_ind <= ind or sub_text.startswith("- "):
                                break
                            if ":" in sub_text:
                                sk, sv = sub_text.split(":", 1)
                                sk, sv = sk.strip(), sv.strip()
                                idx += 1
                                if sv:
                                    dict_data[sk] = _parse_scalar(sv)
                                else:
                                    sval, idx = parse_block(idx, sub_ind + 2)
                                    dict_data[sk] = sval
                            else:
                                idx += 1
                        items.append(dict_data)
                    else:
                        items.append(_parse_scalar(item_text))
                else:
                    break
            return items, idx
        else:
            # It is a mapping
            mapping: Dict[str, Any] = {}
            while idx < len(clean_lines):
                ind, text = clean_lines[idx]
                if ind < current_indent:
                    break
                if ind == current_indent and ":" in text:
                    k, v = text.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    idx += 1
                    if not v:
                        # Nested structure
                        if idx < len(clean_lines) and clean_lines[idx][0] > ind:
                            sub_val, idx = parse_block(idx, clean_lines[idx][0])
                            mapping[k] = sub_val
                        else:
                            mapping[k] = None
                    else:
                        mapping[k] = _parse_scalar(v)
                else:
                    break
            return mapping, idx

    res, _ = parse_block(0, clean_lines[0][0])
    return res


# ============================================================================
# Strict Component Loaders & Boundary Verification
# ============================================================================

FORBIDDEN_AGENT_KEYS = {
    "class", "depth", "failure_depth", "feasible", "ground_truth",
    "authorization_policy", "controller", "environment", "budget",
    "canonical_id", "scenario_id", "failed", "candidate", "high"
}

FORBIDDEN_CONTROLLER_KEYS = {
    "class", "needs_high_to_complete", "authorization_policy",
    "ground_truth", "environment"
}

FORBIDDEN_APPROVER_KEYS = {
    "class", "feasible", "ground_truth", "budget_state", "failure_depth",
    "scenario_id", "canonical_id", "candidate_tool", "failed_tool"
}


def load_scenario_for_agent(scenario_dir: str | Path) -> Dict[str, Any]:
    """Load scenario.yaml for the agent.

    Authority: Spec Section 1 & Section 8.1.
    Must contain ONLY task, tools list, error_code, error_message.
    Strictly verifies no forbidden label keys or hidden architecture data is present.
    """
    path = Path(scenario_dir) / "scenario.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required agent scenario file: {path}")

    content = path.read_text(encoding="utf-8")
    data = parse_yaml_str(content)
    if not isinstance(data, dict) or "scenario" not in data:
        raise ValueError(f"Invalid scenario.yaml: missing top-level 'scenario' key in {path}")

    scenario_data = data["scenario"]
    if not isinstance(scenario_data, dict):
        raise ValueError(f"Invalid 'scenario' section in {path}: expected mapping")

    # Structural security & leakage check
    found_forbidden = FORBIDDEN_AGENT_KEYS.intersection(set(scenario_data.keys()))
    if found_forbidden:
        raise PermissionError(f"Security isolation violation in scenario.yaml: forbidden keys {found_forbidden}")

    # Validate tools whitelist
    tools = scenario_data.get("tools", [])
    if not isinstance(tools, list) or len(tools) != 3:
        raise ValueError(f"scenario.yaml must contain exactly 3 tools, got {len(tools) if isinstance(tools, list) else type(tools)}")

    for t in tools:
        if not isinstance(t, dict):
            raise ValueError("Tool entry must be a dictionary")
        tool_keys = set(t.keys())
        if tool_keys != {"name", "description", "scope"}:
            raise ValueError(f"Tool entry has invalid keys: {tool_keys}; allowed only {{name, description, scope}}")

    return scenario_data


def load_controller_config(scenario_dir: str | Path) -> Dict[str, Any]:
    """Load controller.yaml for the controller.

    Authority: Spec Section 1 & Section 8.2.
    Controller sees opaque scenario id, app, seed, failed_tool, candidate_tool,
    candidate_order, high_tool, feasible (oracle annotation), and predicted_B.
    Must NOT contain class, needs_high_to_complete, authorization_policy, or canonical ID.
    """
    path = Path(scenario_dir) / "controller.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required controller file: {path}")

    content = path.read_text(encoding="utf-8")
    data = parse_yaml_str(content)
    if not isinstance(data, dict) or "controller" not in data:
        raise ValueError(f"Invalid controller.yaml: missing top-level 'controller' key in {path}")

    ctrl_data = data["controller"]
    if not isinstance(ctrl_data, dict):
        raise ValueError(f"Invalid 'controller' section in {path}: expected mapping")

    # Canary & label-leakage check
    found_forbidden = FORBIDDEN_CONTROLLER_KEYS.intersection(set(ctrl_data.keys()))
    if found_forbidden:
        raise PermissionError(f"Security isolation violation in controller.yaml: forbidden keys {found_forbidden}")

    # Canonical ID regex check: opaque ID must match ^scenario_[0-9]{3}$
    scenario_id = ctrl_data.get("id")
    if not isinstance(scenario_id, str) or not re.match(r"^scenario_[0-9]{3}$", scenario_id):
        raise ValueError(f"controller.id must match '^scenario_[0-9]{{3}}$', got: '{scenario_id}'")

    return ctrl_data


def load_approver_policy(scenario_dir: str | Path) -> Dict[str, Any]:
    """Load approver.yaml for the approver.

    Authority: Spec Section 1 & Section 6 & Section 8.
    Must contain ONLY authorization_policy (approvable_high_tools, maximum_approvable_scope).
    """
    path = Path(scenario_dir) / "approver.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required approver file: {path}")

    content = path.read_text(encoding="utf-8")
    data = parse_yaml_str(content)
    if not isinstance(data, dict) or "authorization_policy" not in data:
        raise ValueError(f"Invalid approver.yaml: missing top-level 'authorization_policy' key in {path}")

    policy = data["authorization_policy"]
    if not isinstance(policy, dict):
        raise ValueError(f"Invalid 'authorization_policy' in {path}: expected mapping")

    found_forbidden = FORBIDDEN_APPROVER_KEYS.intersection(set(policy.keys()))
    if found_forbidden:
        raise PermissionError(f"Security isolation violation in approver.yaml: forbidden keys {found_forbidden}")

    return policy


def load_environment_config(scenario_dir: str | Path) -> Dict[str, Any]:
    """Load environment.yaml for the execution environment.

    Authority: Spec Section 1 & Section 8.3.
    """
    path = Path(scenario_dir) / "environment.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required environment file: {path}")

    content = path.read_text(encoding="utf-8")
    data = parse_yaml_str(content)
    if not isinstance(data, dict) or "environment" not in data:
        raise ValueError(f"Invalid environment.yaml: missing top-level 'environment' key in {path}")

    env_data = data["environment"]
    if not isinstance(env_data, dict):
        raise ValueError(f"Invalid 'environment' in {path}: expected mapping")

    return env_data


def load_ground_truth(scenario_dir: str | Path) -> Dict[str, Any]:
    """Load ground_truth.yaml for the evaluator only.

    Authority: Spec Section 1 & Section 8.3.
    Only offline evaluator or consistency validator may load this file.
    """
    path = Path(scenario_dir) / "ground_truth.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required ground_truth file: {path}")

    content = path.read_text(encoding="utf-8")
    data = parse_yaml_str(content)
    if not isinstance(data, dict) or "ground_truth" not in data:
        raise ValueError(f"Invalid ground_truth.yaml: missing top-level 'ground_truth' key in {path}")

    gt = data["ground_truth"]
    if not isinstance(gt, dict):
        raise ValueError(f"Invalid 'ground_truth' in {path}: expected mapping")

    return gt


def load_scenario_index(index_path: str | Path) -> Dict[str, Any]:
    """Load scenario_index.yaml mapping opaque IDs to canonical IDs (evaluator-side only)."""
    path = Path(index_path)
    if not path.is_file():
        raise FileNotFoundError(f"Missing scenario_index file: {path}")

    content = path.read_text(encoding="utf-8")
    data = parse_yaml_str(content)
    if not isinstance(data, dict) or "scenarios" not in data:
        raise ValueError(f"Invalid scenario_index.yaml: missing 'scenarios' key in {path}")

    return data


def get_thesis_10_scenario_subset() -> List[str]:
    """Return the immutable thesis 10-scenario subset defined in Spec Section 0.1 & Section 5.

    Subset: gmail_A_1, slack_A_1, drive_A_1, gmail_A_3, slack_A_3, drive_A_3,
            gmail_A_I, slack_A_I, gmail_B_I, slack_B_I
    """
    return [
        "gmail_A_1",
        "slack_A_1",
        "drive_A_1",
        "gmail_A_3",
        "slack_A_3",
        "drive_A_3",
        "gmail_A_I",
        "slack_A_I",
        "gmail_B_I",
        "slack_B_I"
    ]
