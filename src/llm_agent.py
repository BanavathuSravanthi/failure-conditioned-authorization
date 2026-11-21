"""Genuine LLM-driven tool-using agent for FCA-IGAR research framework.

Authority:
- Spec Section 0.1 (LLM pilot using genuine proprietary model)
- Spec Section 1 (Strict data separation: receives ONLY scenario.yaml and tool results)
- Spec Section 5 (No scripted MEDIUM -> LOW -> HIGH sequence)
- Spec Section 9 (Mandatory model, prompt_version, and temperature logging)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.llm_prompts import (
    PROMPT_VERSION,
    assert_no_information_leak,
    build_system_prompt,
    build_task_prompt,
)
from src.llm_provider import LLMProvider, LLMResponse


class LLMAgent:
    """Autonomous LLM tool-calling agent with strict information isolation."""

    def __init__(
        self,
        scenario_data: Dict[str, Any],
        provider: LLMProvider,
        prompt_version: str = PROMPT_VERSION,
    ):
        """Initialize LLM agent with agent-visible scenario data and provider.

        Args:
            scenario_data: Parsed dictionary from scenario.yaml (must NOT contain
                           class, ground_truth, depth, or role names).
            provider: LLMProvider instance (Gemini, OpenAI, or Mock).
            prompt_version: Version identifier for the prompt template.
        """
        # Strict security verification: no hidden ground truth or labels
        forbidden = {"class", "ground_truth", "depth", "feasible", "canonical_id"}
        if forbidden.intersection(set(scenario_data.keys())):
            raise PermissionError(f"LLMAgent received forbidden metadata: {forbidden.intersection(set(scenario_data.keys()))}")

        self.scenario_data = scenario_data
        self.provider = provider
        self.prompt_version = prompt_version

        self.task: str = scenario_data.get("task", "")
        self.tools: List[Dict[str, Any]] = scenario_data.get("tools", [])

        if not isinstance(self.tools, list) or len(self.tools) != 3:
            raise ValueError(f"LLMAgent requires exactly 3 tools in scenario.yaml, got {len(self.tools) if isinstance(self.tools, list) else type(self.tools)}")

        # Index available tools by name for scope mapping and validation
        self.tool_by_name: Dict[str, Dict[str, Any]] = {t["name"]: t for t in self.tools}

        # Initialize conversation messages
        self.system_prompt = build_system_prompt(self.prompt_version)
        self.initial_user_prompt = build_task_prompt(self.task, self.tools)

        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.initial_user_prompt},
        ]

        self.stopped: bool = False
        self.last_action: Optional[Dict[str, str]] = None
        self.total_latency_ms: float = 0.0
        self.current_tool_call_id: str = "call_0"
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_tokens: int = 0

    def select_action(self) -> Optional[Dict[str, str]]:
        """Ask LLM to choose the next tool action, or stop if complete."""
        if self.stopped:
            return None

        # Query LLM provider
        response: LLMResponse = self.provider.generate_tool_call(self.messages, self.tools)
        self.total_latency_ms += response.latency_ms
        self.total_prompt_tokens += response.prompt_tokens
        self.total_completion_tokens += response.completion_tokens
        self.total_tokens += response.total_tokens

        if response.is_finish or not response.tool_name:
            self.stopped = True
            return None

        tool_name = response.tool_name
        self.current_tool_call_id = response.tool_call_id or f"call_{len(self.messages)}"

        # Handle hallucinated tool names gracefully by providing feedback to LLM
        if tool_name not in self.tool_by_name:
            # Check if name is slightly formatted
            matched = None
            for valid_name in self.tool_by_name:
                if valid_name.replace(".", "_") == tool_name.replace(".", "_"):
                    matched = valid_name
                    break

            if matched:
                tool_name = matched
            else:
                # Inform LLM of invalid tool and retry
                self.messages.append({
                    "role": "assistant",
                    "content": f"I attempt to call `{tool_name}`."
                })
                self.messages.append({
                    "role": "user",
                    "content": f"Error: Tool `{tool_name}` does not exist. Available tools are: {list(self.tool_by_name.keys())}."
                })
                return self.select_action()

        tool_info = self.tool_by_name[tool_name]
        scope = tool_info.get("scope", "UNKNOWN")

        self.last_action = {
            "name": tool_name,
            "scope": scope,
            "arguments": response.arguments,
        }

        # Record assistant tool call in message history
        self.messages.append({
            "role": "assistant",
            "tool_call_id": self.current_tool_call_id,
            "tool_call": {
                "name": tool_name,
                "arguments": response.arguments
            }
        })

        return {
            "name": tool_name,
            "scope": scope
        }

    def observe_outcome(
        self,
        executed: bool,
        success: bool,
        is_blocked: bool,
        episode_complete: bool,
    ) -> None:
        """Deliver execution or authorization outcome feedback to the LLM agent.

        Args:
            executed: Whether the tool call reached execution.
            success: Whether the executed tool call succeeded.
            is_blocked: Whether the call was blocked/denied by authorization policy.
            episode_complete: Whether the task has been marked complete by evaluator.
        """
        if self.last_action is None:
            return

        tool_name = self.last_action["name"]
        tc_id = self.current_tool_call_id

        if episode_complete:
            self.stopped = True
            self.messages.append({
                "role": "tool_response",
                "tool_call_id": tc_id,
                "tool_response": {
                    "name": tool_name,
                    "result": {
                        "status": "success",
                        "output": "Task completed successfully."
                    }
                }
            })
            return

        if is_blocked:
            # Policy denial: fixed generic string per Spec Section 3.2
            denial_msg = "Request denied by policy."
            assert_no_information_leak(denial_msg)
            self.messages.append({
                "role": "tool_response",
                "tool_call_id": tc_id,
                "tool_response": {
                    "name": tool_name,
                    "result": {
                        "status": "denied",
                        "error": denial_msg
                    }
                }
            })
            return

        if executed and success:
            # Executed successfully, but did not complete task (e.g. Class B decoy)
            succ_msg = "Tool executed successfully."
            assert_no_information_leak(succ_msg)
            self.messages.append({
                "role": "tool_response",
                "tool_call_id": tc_id,
                "tool_response": {
                    "name": tool_name,
                    "result": {
                        "status": "success",
                        "output": succ_msg
                    }
                }
            })
            return

        if executed and not success:
            # Tool failure in environment
            fail_msg = "Tool execution failed: Operation could not be completed."
            assert_no_information_leak(fail_msg)
            self.messages.append({
                "role": "tool_response",
                "tool_call_id": tc_id,
                "tool_response": {
                    "name": tool_name,
                    "result": {
                        "status": "failed",
                        "error": fail_msg
                    }
                }
            })
            return

    def get_estimated_cost_usd(self) -> float:
        """Estimate API cost based on recorded token counts and provider model."""
        model_name = getattr(self.provider, "model", "").lower()
        if "gpt-4o-mini" in model_name:
            # $0.15 / 1M prompt, $0.60 / 1M completion
            return (self.total_prompt_tokens * 0.15 + self.total_completion_tokens * 0.60) / 1_000_000.0
        elif "gpt-4o" in model_name:
            # $2.50 / 1M prompt, $10.00 / 1M completion
            return (self.total_prompt_tokens * 2.50 + self.total_completion_tokens * 10.00) / 1_000_000.0
        elif "gemini-1.5-flash" in model_name:
            # $0.075 / 1M prompt, $0.30 / 1M completion
            return (self.total_prompt_tokens * 0.075 + self.total_completion_tokens * 0.30) / 1_000_000.0
        elif "gemini-1.5-pro" in model_name:
            # $1.25 / 1M prompt, $5.00 / 1M completion
            return (self.total_prompt_tokens * 1.25 + self.total_completion_tokens * 5.00) / 1_000_000.0
        else:
            # Conservative baseline: $0.15 / 1M prompt, $0.60 / 1M completion
            return (self.total_prompt_tokens * 0.15 + self.total_completion_tokens * 0.60) / 1_000_000.0
