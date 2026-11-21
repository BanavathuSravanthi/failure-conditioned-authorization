"""Experiment Harness orchestrating FCA-IGAR research evaluations.

Authority:
- Spec Section 1 (Data separation and five-file layout)
- Spec Section 2 (Conditions C1-C9 and K=0 calibration)
- Spec Section 3 (Episode rules, recovery window, strict vs open post-exhaustion modes)
- Spec Section 5a (Scripted agent option order and thresholds)
- Spec Section 9 (JSONL log schema and event contracts)
- Spec Section 10 (Mandatory verification tests)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.approver import Approver
from src.controller import Controller
from src.evaluator import Evaluator
from src.mock_environment import MockEnvironment
from src.scenario_loader import (
    load_scenario_for_agent,
    load_controller_config,
    load_approver_policy,
    load_environment_config,
    load_ground_truth,
)
from src.scripted_agent import ScriptedAgent
from src.scenario_validator import APP_COST_TABLES


@dataclass
class EpisodeResult:
    """Outcome and event trajectory of an executed scenario episode."""
    run_id: str
    scenario_id: str
    condition: str
    post_exhaustion: str
    terminal_state: str
    recovery_calls_actual: int
    blocked_non_high_attempts: int
    total_calls: int
    high_requests: int
    high_grants: int
    events: List[Dict[str, Any]]

    def to_jsonl(self) -> str:
        """Serialize trajectory into newline-delimited JSON events."""
        return "\n".join(json.dumps(e, sort_keys=False) for e in self.events)


class ExperimentHarness:
    """Coordinates agent, controller, approver, environment, and evaluator per episode."""

    def __init__(
        self,
        scenario_dir: str | Path,
        canonical_id: str,
        condition: str,
        post_exhaustion: str = "strict",
        k_value: int = 2,
        k_max: int = 2,
        seed: int = 42,
        run_id: str = "run_001",
        max_steps: int = 12,
        fail_threshold: int = 3,
    ):
        self.scenario_dir = Path(scenario_dir)
        self.canonical_id = canonical_id
        self.condition = condition
        self.post_exhaustion = post_exhaustion
        self.k_value = k_value
        self.k_max = k_max
        self.seed = seed
        self.run_id = run_id
        self.max_steps = max_steps
        self.fail_threshold = fail_threshold

        # 1. Independent component loading preserving strict file boundaries (Spec Sec 1)
        self.scenario_data = load_scenario_for_agent(self.scenario_dir)
        self.controller_data = load_controller_config(self.scenario_dir)
        self.approver_policy = load_approver_policy(self.scenario_dir)
        self.environment_data = load_environment_config(self.scenario_dir)
        self.ground_truth = load_ground_truth(self.scenario_dir)

        app_name = self.controller_data["app"]
        cost_table = APP_COST_TABLES.get(app_name, {})

        # 2. Component instantiation
        self.agent = ScriptedAgent(self.scenario_data, fail_threshold=self.fail_threshold)
        self.controller = Controller(
            scenario_id=self.controller_data["id"],
            condition=self.condition,
            post_exhaustion=self.post_exhaustion,
            k_value=self.k_value,
            failed_tool=self.controller_data.get("failed_tool"),
            candidate_tool=self.controller_data.get("candidate_tool"),
            feasible=self.controller_data.get("feasible", True),
            cost_table=cost_table,
            k_max=self.k_max,
        )
        self.approver = Approver(policy=self.approver_policy)
        self.environment = MockEnvironment(self.environment_data)
        self.evaluator = Evaluator(self.ground_truth)

        # 3. Execution metrics and event log
        self.events: List[Dict[str, Any]] = []
        self.total_calls: int = 0
        self.blocked_non_high_calls: int = 0
        self.high_attempts: int = 0
        self.high_grants: int = 0
        self.current_step: int = 0

    def _create_base_event(self, event_type: str, step: int) -> Dict[str, Any]:
        """Create base event payload with mandatory fields per Spec Section 9."""
        return {
            "run_id": self.run_id,
            "scenario_id": self.canonical_id,
            "condition": self.condition,
            "agent_type": "scripted",
            "model": None,
            "prompt_version": None,
            "temperature": None,
            "seed": self.seed,
            "scripted_fail_threshold": self.fail_threshold,
            "step": step,
            "event": event_type,
            "recovery_call": False,
            "recovery_budget_permitted": self.controller.recovery_budget_permitted,
            "recovery_budget_remaining": self.controller.recovery_budget_remaining,
            "high_request": False,
            "high_granted": False,
            "terminal_state": None,
        }

    def _log_event(self, event_type: str, step: int, **kwargs) -> Dict[str, Any]:
        evt = self._create_base_event(event_type, step)
        evt.update(kwargs)
        self.events.append(evt)
        return evt

    def run_episode(self) -> EpisodeResult:
        """Execute a complete single-scenario episode conforming to Spec Section 3 & 5a."""
        while (
            self.current_step < self.max_steps
            and not self.evaluator.task_completed
            and not self.agent.stopped
        ):
            action = self.agent.select_action()
            if action is None:
                # Agent has exhausted options
                break

            self.current_step += 1
            tool_name = action["name"]
            scope = action["scope"]
            is_high = (scope == "HIGH")

            if is_high:
                self.high_attempts += 1
                self.evaluator.record_high_request()

            # Step 1: Controller evaluates call
            ctrl_eval = self.controller.evaluate_call(tool_name, scope)

            # Emit events generated by controller (e.g. blocked_attempt, freeze_block)
            for raw_evt in ctrl_eval.events_to_log:
                evt_type = raw_evt.get("event", "blocked_attempt")
                is_high_block = raw_evt.get("high_request", is_high)
                if evt_type == "blocked_attempt" and not is_high_block:
                    self.blocked_non_high_calls += 1

                self._log_event(
                    event_type=evt_type,
                    step=self.current_step,
                    tool=tool_name,
                    scope=scope,
                    decision=raw_evt.get("decision"),
                    reason=raw_evt.get("reason"),
                    high_request=is_high_block,
                    high_granted=False,
                    recovery_call=False,
                )

            if ctrl_eval.is_blocked:
                # Call was blocked before execution: consumes 0 budget
                self.agent.observe_outcome(
                    executed=False,
                    success=False,
                    is_blocked=True,
                    episode_complete=False,
                )
                continue

            # Step 2: Authorization gate for HIGH requests
            if is_high:
                if self.condition in ("C1", "C4"):
                    # Vanilla: no approver gate (Spec Section 3.3)
                    auth_decision = "allow"
                    auth_reason = "no_gate"
                elif self.condition == "C2":
                    # Static least privilege: HIGH unavailable
                    auth_decision = "deny"
                    auth_reason = "policy_deny"
                else:
                    # Gated conditions: consult label-blind Approver
                    appr_res = self.approver.evaluate(
                        task_text=self.scenario_data["task"],
                        requested_tool=tool_name,
                        requested_scope=scope,
                    )
                    auth_decision = appr_res.decision
                    auth_reason = appr_res.reason

                is_granted = (auth_decision == "allow")
                self.evaluator.record_auth_decision(auth_decision)
                self._log_event(
                    event_type="auth_decision",
                    step=self.current_step,
                    tool=tool_name,
                    scope=scope,
                    decision=auth_decision,
                    reason=auth_reason,
                    high_request=True,
                    high_granted=is_granted,
                    recovery_call=False,
                )

                if not is_granted:
                    # Approver denied HIGH: agent observes block, episode terminates per Spec Sec 3.4
                    self.agent.observe_outcome(
                        executed=False,
                        success=False,
                        is_blocked=True,
                        episode_complete=False,
                    )
                    break

                self.high_grants += 1

            # Step 3: Tool Call Execution
            is_recovery_call = False
            if self.controller.recovery_window_open:
                permitted = self.controller._get_permitted_recovery_tool_name()
                if tool_name == permitted:
                    is_recovery_call = True

            self._log_event(
                event_type="tool_call",
                step=self.current_step,
                tool=tool_name,
                scope=scope,
                attempt_number=self.environment.tool_attempts.get(tool_name, 0) + 1,
                recovery_call=is_recovery_call,
                high_request=is_high,
                high_granted=is_high,
            )

            exec_res = self.environment.execute_tool(tool_name)
            self.total_calls += 1
            call_success = (exec_res["status"] == "success")

            # Step 4: Record execution in Controller state machine
            if not self.controller.first_failure_occurred and not call_success and scope != "HIGH":
                # Initial failure below HIGH: opens recovery window
                self.controller.record_first_failure(tool_name, scope)
                self._log_event(
                    event_type="tool_failure",
                    step=self.current_step,
                    tool=tool_name,
                    scope=scope,
                    attempt_number=exec_res["attempt"],
                    recovery_call=False,
                    high_request=False,
                    high_granted=False,
                )

                # Special handling for C4/C6: silent harness retries (Spec Section 3.3)
                if self.condition in ("C4", "C6"):
                    for _ in range(self.k_value):
                        retry_res = self.environment.execute_tool(tool_name)
                        self.total_calls += 1
                        if retry_res["status"] == "success":
                            call_success = True
                            break
            else:
                self.controller.record_call_executed(tool_name, scope, call_success)
                if not call_success:
                    self._log_event(
                        event_type="tool_failure",
                        step=self.current_step,
                        tool=tool_name,
                        scope=scope,
                        attempt_number=exec_res["attempt"],
                        recovery_call=is_recovery_call,
                        high_request=is_high,
                        high_granted=is_high,
                    )

            # Step 5: Evaluator checks task completion
            task_complete = self.evaluator.evaluate_tool_execution(tool_name, call_success)
            self.agent.observe_outcome(
                executed=True,
                success=call_success,
                is_blocked=False,
                episode_complete=task_complete,
            )

            if task_complete:
                break

        # Episode termination
        terminal_state = self.evaluator.determine_terminal_state(self.current_step, self.max_steps)

        # Step 6: Log episode_end event per Spec Section 9
        predicted_b = self.controller_data.get("predicted_B", 0)
        self._log_event(
            event_type="episode_end",
            step=self.current_step,
            terminal_state=terminal_state,
            recovery_calls_permitted=self.controller.recovery_budget_permitted,
            recovery_calls_actual=self.controller.recovery_calls_actual,
            executed_calls_after_first_failure=self.controller.executed_calls_after_first_failure,
            failed_executed_calls_after_first_failure=self.controller.failed_executed_calls_after_first_failure,
            predicted_B=predicted_b,
            candidate_tool=self.controller_data.get("candidate_tool", {}).get("name") if self.controller_data.get("candidate_tool") else None,
            total_calls=self.total_calls,
            blocked_calls=self.blocked_non_high_calls,
            high_attempts=self.high_attempts,
            high_grants=self.high_grants,
            post_exhaustion=self.post_exhaustion,
            recovery_call=False,
            high_request=False,
            high_granted=False,
        )

        return EpisodeResult(
            run_id=self.run_id,
            scenario_id=self.canonical_id,
            condition=self.condition,
            post_exhaustion=self.post_exhaustion,
            terminal_state=terminal_state,
            recovery_calls_actual=self.controller.recovery_calls_actual,
            blocked_non_high_attempts=self.blocked_non_high_calls,
            total_calls=self.total_calls,
            high_requests=self.high_attempts,
            high_grants=self.high_grants,
            events=self.events,
        )
