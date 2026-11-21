"""Deterministic mock environment for tool execution per Spec Section 8.3.

Authority:
- Spec Section 8.3 (environment.yaml tool success schedules)
- Spec Section 3.4 (Tool execution counting and return formats)
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class MockEnvironment:
    """Simulates tool execution according to environment.yaml schedule.

    Tracks execution attempt counts per tool. Blocked calls do not reach
    execution and do not increment attempt counters.
    """

    def __init__(self, env_config: Dict[str, Any]):
        """Initialize environment with parsed environment.yaml dict.

        Args:
            env_config: Parsed dict from environment.yaml (contains 'tools' dict).
        """
        tools_dict = env_config.get("tools", {})
        if not isinstance(tools_dict, dict):
            raise ValueError(f"Invalid environment configuration: expected 'tools' mapping, got {type(tools_dict)}")

        self.tool_configs: Dict[str, Dict[str, Any]] = tools_dict
        self.tool_attempts: Dict[str, int] = {tool: 0 for tool in self.tool_configs}

    def execute_tool(self, tool_name: str) -> Dict[str, Any]:
        """Execute a tool call against the deterministic schedule.

        Args:
            tool_name: Fully qualified tool name (e.g. 'gmail.send_draft').

        Returns:
            Dict containing execution outcome:
            - status: "success" or "error"
            - attempt: attempt number for this tool
            - error_code: "ERR_UNAVAILABLE" or None
            - error_message: "Service temporarily unavailable" or None
        """
        if tool_name not in self.tool_configs:
            raise ValueError(f"Tool '{tool_name}' not defined in environment schedule: {list(self.tool_configs.keys())}")

        self.tool_attempts[tool_name] += 1
        attempt_num = self.tool_attempts[tool_name]

        success_attempt = self.tool_configs[tool_name].get("success_attempt")
        if success_attempt is not None and attempt_num >= success_attempt:
            return {
                "status": "success",
                "attempt": attempt_num,
                "error_code": None,
                "error_message": None,
                "payload": {"result": "Operation completed successfully"}
            }
        else:
            return {
                "status": "error",
                "attempt": attempt_num,
                "error_code": "ERR_UNAVAILABLE",
                "error_message": "Service temporarily unavailable",
                "payload": None
            }
