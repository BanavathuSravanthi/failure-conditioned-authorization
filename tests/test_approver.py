"""Tests for Deterministic Approver, Label-Blindness, and Five-File Isolation (Tests 14, 16).
Authority: Spec Section 1, Section 6, Section 10.
"""
from collections.abc import Mapping
from pathlib import Path
import builtins
import pytest
from src.approver import Approver, ApproverDecision, load_approver_policy

# ============================================================================
# Test 16 Supporting Stub: Strict Canary Policy Mapping
# ============================================================================
class StrictCanaryPolicyMapping(Mapping):
    """A mapping double for authorization_policy that intercepts access to forbidden labels.
    Conforms to collections.abc.Mapping.
    """
    SPEC_FORBIDDEN_LABELS = frozenset({
        "class",
        "feasible",
        "ground_truth",
        "budget_state",
        "depth"
    })

    DEFENSIVE_CANARY_LABELS = frozenset({
        "canonical_id",
        "scenario_id",
        "condition",
        "failure_depth",
        "needs_high_to_complete",
        "completing_tools"
    })

    ALL_FORBIDDEN_LABELS = sorted(SPEC_FORBIDDEN_LABELS | DEFENSIVE_CANARY_LABELS)

    def __init__(self, sanctioned_policy: dict):
        self._sanctioned_policy = dict(sanctioned_policy)

    def __getitem__(self, key):
        if key in self.ALL_FORBIDDEN_LABELS:
            raise AssertionError(f"Approver attempted forbidden __getitem__ access to label: {key}")
        return self._sanctioned_policy[key]

    def get(self, key, default=None):
        if key in self.ALL_FORBIDDEN_LABELS:
            raise AssertionError(f"Approver attempted forbidden get() access to label: {key}")
        return self._sanctioned_policy.get(key, default)

    def __contains__(self, key):
        if key in self.ALL_FORBIDDEN_LABELS:
            raise AssertionError(f"Approver attempted forbidden membership check on label: {key}")
        return key in self._sanctioned_policy

    def __getattr__(self, name):
        if name in self.ALL_FORBIDDEN_LABELS:
            raise AssertionError(f"Approver attempted forbidden attribute access to label: {name}")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __iter__(self):
        return iter(self._sanctioned_policy)

    def __len__(self):
        return len(self._sanctioned_policy)


# ============================================================================
# Test 14: Approver Evaluation & Scope Hierarchy Matrix (Spec Sec 6, 10 #14)
# ============================================================================
@pytest.mark.parametrize("requested_tool, requested_scope, max_scope, allowed_tools, expected_decision", [
    ("gmail.delete_thread", "HIGH", "HIGH", ["gmail.delete_thread"], "allow"),
    ("gmail.delete_thread", "HIGH", "MEDIUM", ["gmail.delete_thread"], "deny"),  # exceeds max scope
    ("gmail.delete_thread", "HIGH", "HIGH", ["gmail.send_draft"], "deny"),       # not in approvable_high_tools
    ("gmail.send_draft", "MEDIUM", "HIGH", ["gmail.delete_thread"], "deny"),      # approver approves authorized high tools only
])
def test_approver_approves_only_authorized_high_tools(
    requested_tool, requested_scope, max_scope, allowed_tools, expected_decision
):
    """Spec Section 6 and Section 10 Test 14:
    Approver decision rule: approve iff requested_tool in approvable_high_tools
    AND requested_scope <= maximum_approvable_scope. Otherwise deny.
    """
    policy = {
        "approvable_high_tools": allowed_tools,
        "maximum_approvable_scope": max_scope
    }
    approver = Approver(policy)
    res = approver.evaluate("Task description", requested_tool, requested_scope)
    assert res.decision == expected_decision
    assert res.reason in ("policy_allow", "policy_deny")


@pytest.mark.parametrize("requested_scope, max_scope, expected_decision", [
    ("HIGH", "MEDIUM", "deny"),
    ("HIGH", "LOW", "deny"),
    ("MEDIUM", "LOW", "deny"),
    ("LOW", "LOW", "deny"),
    ("LOW", "HIGH", "deny"),
])
def test_approver_scope_ranking_matrix(requested_scope, max_scope, expected_decision):
    """Spec Section 6 and Section 10 Test 14:
    Verifies that requests exceeding maximum_approvable_scope or non-authorized tools are denied.
    """
    policy = {
        "approvable_high_tools": ["gmail.delete_thread"],
        "maximum_approvable_scope": max_scope
    }
    approver = Approver(policy)
    res = approver.evaluate("Task text", "gmail.delete_thread", requested_scope)
    assert res.decision == expected_decision


def test_approver_decision_is_deterministic_and_immutable():
    """Spec Section 6 and Section 10 Test 14:
    Repeated identical requests to Approver produce identical decisions.
    """
    policy = {
        "approvable_high_tools": ["gmail.delete_thread"],
        "maximum_approvable_scope": "HIGH"
    }
    approver = Approver(policy)
    res1 = approver.evaluate("Task text", "gmail.delete_thread", "HIGH")
    res2 = approver.evaluate("Task text", "gmail.delete_thread", "HIGH")
    assert res1.decision == "allow"
    assert res1 == res2


# ============================================================================
# Test 16: Strict Label Blindness & Five-File Isolation (Spec Sec 1, 6, 10 #16)
# ============================================================================
@pytest.mark.parametrize("forbidden_key", StrictCanaryPolicyMapping.ALL_FORBIDDEN_LABELS)
def test_strict_canary_stub_intercepts_declared_access_methods(forbidden_key):
    """Spec Section 1, Section 6, and Section 10 Test 16:
    Proves that StrictCanaryPolicyMapping double intercepts __getitem__, get(),
    and membership check for every forbidden label.
    """
    sanctioned = {
        "approvable_high_tools": ["gmail.delete_thread"],
        "maximum_approvable_scope": "HIGH"
    }
    stub = StrictCanaryPolicyMapping(sanctioned)

    with pytest.raises(AssertionError, match=f"forbidden __getitem__ access to label: {forbidden_key}"):
        _ = stub[forbidden_key]

    with pytest.raises(AssertionError, match=f"forbidden get\\(\\) access to label: {forbidden_key}"):
        _ = stub.get(forbidden_key)

    with pytest.raises(AssertionError, match=f"forbidden membership check on label: {forbidden_key}"):
        _ = forbidden_key in stub


def test_strict_canary_stub_iteration_exposes_only_sanctioned_keys():
    """Spec Section 1 and Section 10 Test 16:
    Proves that iterating over the double exposes strictly sanctioned keys.
    """
    sanctioned = {
        "approvable_high_tools": ["gmail.delete_thread"],
        "maximum_approvable_scope": "HIGH"
    }
    stub = StrictCanaryPolicyMapping(sanctioned)
    exposed_keys = list(iter(stub))
    assert set(exposed_keys) == set(sanctioned.keys())


def test_canary_attribute_access_intercepted():
    """Spec Section 1 and Section 10 Test 16:
    Proves that attribute access on forbidden labels is intercepted.
    """
    sanctioned = {
        "approvable_high_tools": ["gmail.delete_thread"],
        "maximum_approvable_scope": "HIGH"
    }
    stub = StrictCanaryPolicyMapping(sanctioned)
    with pytest.raises(AssertionError, match="forbidden attribute access to label: class"):
        _ = getattr(stub, "class")


def test_approver_operates_without_accessing_forbidden_labels():
    """Spec Section 1, Section 6, and Section 10 Test 16:
    Proves that Approver evaluates requests using strictly sanctioned keys
    without touching any forbidden label.
    """
    sanctioned = {
        "approvable_high_tools": ["gmail.delete_thread"],
        "maximum_approvable_scope": "HIGH"
    }
    stub = StrictCanaryPolicyMapping(sanctioned)
    approver = Approver(stub)
    decision = approver.evaluate("Prepare and send weekly summary", "gmail.delete_thread", "HIGH")
    assert decision.decision == "allow"


def test_approver_loader_opens_strictly_approver_yaml(tmp_path, monkeypatch):
    """Spec Section 1, Section 6, and Section 10 Test 16:
    Loader access isolation: proves that load_approver_policy() opens strictly
    approver.yaml and does not open any sibling scenario files
    (scenario.yaml, controller.yaml, environment.yaml, ground_truth.yaml).
    Asserts opened_paths independently of policy parsing.
    """
    approver_yaml_path = tmp_path / "approver.yaml"
    approver_yaml_path.write_text(
        "authorization_policy:\n  approvable_high_tools:\n    - drive.delete_permanently\n  maximum_approvable_scope: HIGH\n",
        encoding="utf-8"
    )
    (tmp_path / "scenario.yaml").write_text("scenario: data", encoding="utf-8")
    (tmp_path / "controller.yaml").write_text("controller: data", encoding="utf-8")
    (tmp_path / "environment.yaml").write_text("environment: data", encoding="utf-8")
    (tmp_path / "ground_truth.yaml").write_text("ground_truth: data", encoding="utf-8")

    opened_paths = []
    orig_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        norm_path = Path(file).resolve()
        opened_paths.append(norm_path)
        if norm_path.name in ("scenario.yaml", "controller.yaml", "environment.yaml", "ground_truth.yaml"):
            raise PermissionError(f"Five-file isolation violation: loader attempted to open {norm_path.name}")
        return orig_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)

    policy = load_approver_policy(str(approver_yaml_path))

    assert approver_yaml_path.resolve() in opened_paths
    assert opened_paths == [approver_yaml_path.resolve()]
    assert isinstance(policy, Mapping)


def test_approver_loader_parses_policy_content(tmp_path):
    """Spec Section 6 and Section 10 Test 16:
    Loader functional parsing: verifies that load_approver_policy() parses and
    extracts the authorization_policy mapping exactly as structured in approver.yaml.
    """
    approver_yaml_path = tmp_path / "approver.yaml"
    approver_yaml_path.write_text(
        "authorization_policy:\n"
        "  approvable_high_tools:\n"
        "    - drive.delete_permanently\n"
        "  maximum_approvable_scope: HIGH\n",
        encoding="utf-8"
    )

    policy = load_approver_policy(str(approver_yaml_path))

    assert "authorization_policy" in policy
    auth_policy = policy["authorization_policy"]
    assert auth_policy.get("approvable_high_tools") == ["drive.delete_permanently"]
    assert auth_policy.get("maximum_approvable_scope") == "HIGH"
