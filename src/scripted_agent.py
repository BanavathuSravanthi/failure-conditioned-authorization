"""Scripted agent implementation for FCA-IGAR research framework.

Authority:
- Spec Section 1 (Data separation: sees ONLY scenario.yaml and tool results)
- Spec Section 5a (Scripted agent policy, option order, retry threshold)
- Spec Section 10 (Mandatory tests 7a, 11, 15, 21)

Option order is determined ONLY by agent-visible scope tags:
1. MEDIUM-tagged tool first
2. LOW-tagged tool second
3. HIGH-tagged tool third

Advancement criteria:
(a) Current call is blocked / denied
(b) Agent sees 3 consecutive failures of the same tool (scripted_fail_threshold = 3)
(c) Call executes successfully but task does not complete (e.g., Class B decoy)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class ScriptedAgent:
    """Deterministic, label-blind scripted agent conforming to Spec Section 5a."""

    def __init__(self, scenario_data: Dict[str, Any], fail_threshold: int = 3):
        """Initialize scripted agent with agent-visible scenario data only.

        Args:
            scenario_data: Parsed dictionary from scenario.yaml (must NOT contain
                           class, ground_truth, depth, or role names).
            fail_threshold: Consecutive failure limit before switching options (default 3).
        """
        # Security invariant: verify no label leakage in agent inputs
        forbidden = {"class", "ground_truth", "depth", "feasible", "canonical_id"}
        if forbidden.intersection(set(scenario_data.keys())):
            raise PermissionError(f"ScriptedAgent received forbidden metadata: {forbidden.intersection(set(scenario_data.keys()))}")

        self.task = scenario_data.get("task", "")
        self.fail_threshold = fail_threshold

        tools = scenario_data.get("tools", [])
        if not isinstance(tools, list) or len(tools) != 3:
            raise ValueError(f"ScriptedAgent requires exactly 3 tools in scenario, got {len(tools) if isinstance(tools, list) else type(tools)}")

        # Extract tools by scope tag ONLY (MEDIUM -> LOW -> HIGH per Spec Sec 5a)
        med_tool = None
        low_tool = None
        high_tool = None

        for t in tools:
            scope = t.get("scope")
            if scope == "MEDIUM":
                med_tool = t
            elif scope == "LOW":
                low_tool = t
            elif scope == "HIGH":
                high_tool = t

        if not (med_tool and low_tool and high_tool):
            raise ValueError(f"ScriptedAgent requires one tool of each scope {{LOW, MEDIUM, HIGH}}, found: {[t.get('scope') for t in tools]}")

        # Frozen option order: MEDIUM -> LOW -> HIGH
        self.options: List[Dict[str, str]] = [
            {"name": med_tool["name"], "scope": "MEDIUM"},
            {"name": low_tool["name"], "scope": "LOW"},
            {"name": high_tool["name"], "scope": "HIGH"}
        ]

        self.current_option_idx: int = 0
        self.consecutive_failures: int = 0
        self.stopped: bool = False

    def select_action(self) -> Optional[Dict[str, str]]:
        """Return the next proposed tool call, or None if the agent has stopped."""
        if self.stopped or self.current_option_idx >= len(self.options):
            self.stopped = True
            return None

        current = self.options[self.current_option_idx]
        return {
            "name": current["name"],
            "scope": current["scope"]
        }

    def observe_outcome(self, executed: bool, success: bool, is_blocked: bool, episode_complete: bool):
        """Update internal state after observing a tool call outcome per Spec Section 5a.

        Args:
            executed: Whether the tool call reached execution.
            success: Whether the executed tool call succeeded.
            is_blocked: Whether the call was blocked/denied by Controller or Approver.
            episode_complete: Whether the evaluator signaled task completion.
        """
        if episode_complete:
            self.stopped = True
            return

        if is_blocked:
            # Rule (a): call is blocked/denied -> advance to next option
            self._advance_option()
        elif executed and success:
            # Rule (c): call executes successfully but episode did not end (non-completing decoy)
            # -> advance to next option
            self._advance_option()
        elif executed and not success:
            # Executed call failed
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.fail_threshold:
                # Rule (b): 3 consecutive failures -> advance to next option
                self._advance_option()

    def _advance_option(self):
        """Advance to the next option in sequence and reset consecutive failure counter."""
        self.current_option_idx += 1
        self.consecutive_failures = 0
        if self.current_option_idx >= len(self.options):
            self.stopped = True
