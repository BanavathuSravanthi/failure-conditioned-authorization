"""Deterministic Approver and policy loader (Spec Section 6, Section 10 Tests 14, 16).
Authority: Spec Section 1, Section 6, Section 10.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Union, Mapping, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

SCOPE_RANKS = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


@dataclass(frozen=True)
class ApproverDecision:
    decision: str
    reason: str


def _parse_val(val: str) -> Any:
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]
    return val.strip("\"'")


def _parse_yaml_policy(text: str) -> Dict[str, Any]:
    """Lightweight fallback YAML parser for approver.yaml schema when PyYAML is unavailable.
    Handles the frozen approver.yaml schema:
    - 2-level nesting (authorization_policy -> child keys)
    - Block lists (- tool_name)
    - Inline lists ([tool_name] and [])
    - Empty block lists (approvable_high_tools: followed by next key)
    - Quoted values ("HIGH", 'gmail.delete_thread')
    - Full-line and inline comments (# comment)
    """
    lines = text.splitlines()
    result: Dict[str, Any] = {}
    current_section: Dict[str, Any] = result
    current_list_key: Optional[str] = None

    for raw_line in lines:
        line = raw_line
        if "#" in line:
            parts = line.split("#")
            clean_parts = []
            quote_count = 0
            for p in parts:
                quote_count += p.count('"') + p.count("'")
                clean_parts.append(p)
                if quote_count % 2 == 0:
                    break
            line = "#".join(clean_parts)

        line = line.rstrip()
        if not line or line.strip() == "":
            continue

        stripped = line.strip()

        # Handle block list item: "- item"
        if stripped.startswith("- "):
            item = stripped[2:].strip().strip("\"'")
            if current_list_key is not None and isinstance(current_section.get(current_list_key), list):
                current_section[current_list_key].append(item)
            continue

        # If not a block list item, clear active list key
        current_list_key = None

        if ":" in stripped:
            indent = len(raw_line) - len(raw_line.lstrip())
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()

            if indent == 0:
                if val == "":
                    result[key] = {}
                    current_section = result[key]
                else:
                    result[key] = _parse_val(val)
                    current_section = result
            else:
                if val == "":
                    current_section[key] = []
                    current_list_key = key
                else:
                    current_section[key] = _parse_val(val)

    return result


def load_approver_policy(policy_path: Union[str, Path]) -> Dict[str, Any]:
    """Loads approver policy from approver.yaml in strict isolation.
    Opens strictly policy_path and does not access any sibling scenario files.
    """
    with open(policy_path, "r", encoding="utf-8") as f:
        if yaml is not None:
            data = yaml.safe_load(f)
            return data if data is not None else {}
        content = f.read()
        return _parse_yaml_policy(content)


class Approver:
    """Deterministic, label-blind approver evaluating escalation requests (Spec Section 6).
    Enforces authorization_policy strictly:
    - Approves iff requested_tool in approvable_high_tools AND scope <= maximum_approvable_scope.
    - Approver approves authorized HIGH tools only.
    - Fails closed on missing, malformed, or unhashable policy fields (never assumes permissive defaults).
    - Operates with strict isolation: never accesses ground truth, scenario IDs, condition, or labels.
    """

    def __init__(self, policy: Optional[Mapping[str, Any]]):
        if isinstance(policy, Mapping) and "authorization_policy" in policy:
            self.policy = policy["authorization_policy"]
        else:
            self.policy = policy

    def evaluate(self, task_text: str, requested_tool: str, requested_scope: str) -> ApproverDecision:
        """Evaluates an authorization request according to Spec Section 6.
        Returns ApproverDecision with decision ('allow' or 'deny') and reason
        ('policy_allow' or 'policy_deny').
        All evaluations fail closed if policy or scope attributes are missing, invalid, or unhashable.
        """
        # Fail-closed: policy must be a valid mapping
        if not isinstance(self.policy, Mapping):
            return ApproverDecision(decision="deny", reason="policy_deny")

        # Fail-closed: approver evaluates and approves authorized HIGH tools only
        if not isinstance(requested_scope, str) or requested_scope != "HIGH":
            return ApproverDecision(decision="deny", reason="policy_deny")

        if not isinstance(requested_tool, str):
            return ApproverDecision(decision="deny", reason="policy_deny")

        # Fail-closed: approvable_high_tools must be present and a sequence
        allowed_tools = self.policy.get("approvable_high_tools")
        if not isinstance(allowed_tools, (list, tuple, set)):
            return ApproverDecision(decision="deny", reason="policy_deny")

        # Fail-closed: maximum_approvable_scope must be a valid string scope in SCOPE_RANKS
        max_scope = self.policy.get("maximum_approvable_scope")
        if not isinstance(max_scope, str) or max_scope not in SCOPE_RANKS:
            return ApproverDecision(decision="deny", reason="policy_deny")

        try:
            tool_allowed = requested_tool in allowed_tools
        except Exception:
            return ApproverDecision(decision="deny", reason="policy_deny")

        scope_allowed = SCOPE_RANKS[requested_scope] <= SCOPE_RANKS[max_scope]

        if tool_allowed and scope_allowed:
            return ApproverDecision(decision="allow", reason="policy_allow")
        return ApproverDecision(decision="deny", reason="policy_deny")
