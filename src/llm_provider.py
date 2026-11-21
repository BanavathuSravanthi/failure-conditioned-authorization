"""LLM Provider abstraction and API clients for FCA-IGAR research framework.

Authority:
- Spec Section 0.1 (Evidence tier: LLM pilot using real proprietary model)
- Spec Section 1 (Strict data separation & isolation)
- Spec Section 9 (Mandatory model and temperature logging)
"""
from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import urllib.request
import urllib.error

from src.llm_prompts import (
    assert_no_information_leak,
    convert_tools_to_gemini_schema,
    convert_tools_to_openai_schema,
)


@dataclass
class LLMResponse:
    """Standardized tool-call response from any LLM provider."""
    tool_name: Optional[str]
    arguments: Dict[str, Any] = field(default_factory=dict)
    is_finish: bool = False
    raw_text: Optional[str] = None
    latency_ms: float = 0.0
    tool_call_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    thought_signature: Optional[str] = None


class LLMProvider(ABC):
    """Abstract interface for LLM model providers."""

    def __init__(self, model: str, temperature: float = 0.0, max_retries: int = 3):
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    @abstractmethod
    def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        """Given conversation history and available tools, return next tool action."""
        pass


class GeminiProvider(LLMProvider):
    """Real proprietary Gemini API client using native function declarations."""

    def __init__(
        self,
        model: str = "gemini-3.1-flash-lite",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_retries: int = 5,
    ):
        super().__init__(model=model, temperature=temperature, max_retries=max_retries)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        # Fallback 1: check Windows user registry
        if not self.api_key:
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as env_k:
                    for k_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                        try:
                            val, _ = winreg.QueryValueEx(env_k, k_name)
                            if val and isinstance(val, str) and val.strip():
                                self.api_key = val.strip()
                                break
                        except FileNotFoundError:
                            continue
            except Exception:
                pass

        # Fallback 2: check local gitignored .env file
        if not self.api_key and os.path.exists(".env"):
            try:
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                            self.api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass

        if not self.api_key:
            raise ValueError("GeminiProvider requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable or explicit api_key argument")

        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        )

    def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        # Build tool mapping between dotted scenario names and underscore Gemini names
        name_map = {t["name"].replace(".", "_"): t["name"] for t in tools}
        gemini_tools = [{"functionDeclarations": convert_tools_to_gemini_schema(tools)}]

        # Format conversation messages for Gemini
        contents = []
        for m in messages:
            role = m["role"]
            if role == "system":
                # Gemini handles system in systemInstruction
                continue
            gemini_role = "user" if role in ("user", "tool", "tool_response") else "model"
            parts = []
            if "content" in m and m["content"]:
                parts.append({"text": m["content"]})
            if "tool_call" in m:
                tc = m["tool_call"]
                g_name = tc["name"].replace(".", "_")
                fc_dict: Dict[str, Any] = {"name": g_name, "args": tc.get("arguments", {})}
                if "tool_call_id" in m and m["tool_call_id"]:
                    fc_dict["id"] = m["tool_call_id"]
                part_entry: Dict[str, Any] = {"functionCall": fc_dict}
                if "thought_signature" in m and m["thought_signature"]:
                    part_entry["thoughtSignature"] = m["thought_signature"]
                parts.append(part_entry)
            if "tool_response" in m:
                tr = m["tool_response"]
                g_name = tr["name"].replace(".", "_")
                fr_dict: Dict[str, Any] = {
                    "name": g_name,
                    "response": {"result": tr.get("result", {})}
                }
                if "tool_call_id" in m and m["tool_call_id"]:
                    fr_dict["id"] = m["tool_call_id"]
                parts.append({"functionResponse": fr_dict})
            if parts:
                contents.append({"role": gemini_role, "parts": parts})

        # Ensure alternating user/model turns for Gemini multi-turn format
        merged_contents = []
        for c in contents:
            if not c["parts"]:
                continue
            if merged_contents and merged_contents[-1]["role"] == c["role"]:
                merged_contents[-1]["parts"].extend(c["parts"])
            else:
                merged_contents.append(c)

        system_instruction = None
        for m in messages:
            if m["role"] == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
                break

        payload: Dict[str, Any] = {
            "contents": merged_contents,
            "tools": gemini_tools,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 1024,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            }
        )

        # Bounded exponential backoff retry loop
        last_err = None
        for attempt in range(self.max_retries):
            start_t = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    latency = (time.perf_counter() - start_t) * 1000.0

                    usage = resp_data.get("usageMetadata", {})
                    p_tokens = usage.get("promptTokenCount", 0)
                    c_tokens = usage.get("candidatesTokenCount", 0)
                    t_tokens = usage.get("totalTokenCount", 0)

                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        return LLMResponse(
                            tool_name=None,
                            is_finish=True,
                            latency_ms=latency,
                            prompt_tokens=p_tokens,
                            completion_tokens=c_tokens,
                            total_tokens=t_tokens,
                        )

                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    for p in content_parts:
                        if "functionCall" in p:
                            fc = p["functionCall"]
                            raw_name = fc.get("name", "")
                            orig_name = name_map.get(raw_name, raw_name.replace("_", "."))
                            args = fc.get("args", {})
                            sig = p.get("thoughtSignature")
                            tc_id = fc.get("id")
                            return LLMResponse(
                                tool_name=orig_name,
                                arguments=args,
                                is_finish=False,
                                latency_ms=latency,
                                prompt_tokens=p_tokens,
                                completion_tokens=c_tokens,
                                total_tokens=t_tokens,
                                tool_call_id=tc_id,
                                thought_signature=sig,
                            )
                        if "text" in p:
                            raw_txt = p["text"]
                            if "finish" in raw_txt.lower() or "complete" in raw_txt.lower():
                                return LLMResponse(
                                    tool_name=None,
                                    is_finish=True,
                                    raw_text=raw_txt,
                                    latency_ms=latency,
                                    prompt_tokens=p_tokens,
                                    completion_tokens=c_tokens,
                                    total_tokens=t_tokens,
                                )

                    return LLMResponse(
                        tool_name=None,
                        is_finish=True,
                        latency_ms=latency,
                        prompt_tokens=p_tokens,
                        completion_tokens=c_tokens,
                        total_tokens=t_tokens,
                    )

            except urllib.error.HTTPError as e:
                last_err = e
                # 429 Rate Limit or 5xx Server Error -> retry
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    sleep_time = (2 ** attempt) * 1.5
                    time.sleep(sleep_time)
                    continue
                raise RuntimeError(f"Gemini API HTTP Error {e.code}: {e.read().decode('utf-8')}") from e
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"Gemini API request failed: {e}") from e

        raise RuntimeError(f"Gemini API failed after {self.max_retries} attempts: {last_err}")


class OpenAIProvider(LLMProvider):
    """Real proprietary OpenAI API client using native tools parameter."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1/chat/completions",
        temperature: float = 0.0,
        max_retries: int = 5,
    ):
        super().__init__(model=model, temperature=temperature, max_retries=max_retries)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        # Fallback 1: check Windows user registry
        if not self.api_key:
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as env_k:
                    val, _ = winreg.QueryValueEx(env_k, "OPENAI_API_KEY")
                    if val and isinstance(val, str) and val.strip():
                        self.api_key = val.strip()
            except Exception:
                pass

        # Fallback 2: check local gitignored .env file
        if not self.api_key and os.path.exists(".env"):
            try:
                with open(".env", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENAI_API_KEY="):
                            self.api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass

        if not self.api_key:
            raise ValueError("OpenAIProvider requires OPENAI_API_KEY environment variable or explicit api_key argument")
        self.endpoint = base_url

    def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        openai_tools = convert_tools_to_openai_schema(tools)

        # Format conversation messages for OpenAI
        formatted_messages = []
        for m in messages:
            role = m["role"]
            if role == "tool_response":
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id") or "call_0",
                    "content": json.dumps(m.get("tool_response", {}))
                })
            elif role == "assistant" and "tool_call" in m:
                formatted_messages.append({
                    "role": "assistant",
                    "content": m.get("content"),
                    "tool_calls": [{
                        "id": m.get("tool_call_id") or "call_0",
                        "type": "function",
                        "function": {
                            "name": m["tool_call"]["name"],
                            "arguments": json.dumps(m["tool_call"].get("arguments", {}))
                        }
                    }]
                })
            else:
                formatted_messages.append({
                    "role": role,
                    "content": m.get("content", "")
                })

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "tools": openai_tools,
            "temperature": self.temperature,
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )

        last_err = None
        for attempt in range(self.max_retries):
            start_t = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    latency = (time.perf_counter() - start_t) * 1000.0

                    usage = resp_data.get("usage", {})
                    p_tokens = usage.get("prompt_tokens", 0)
                    c_tokens = usage.get("completion_tokens", 0)
                    t_tokens = usage.get("total_tokens", 0)

                    choices = resp_data.get("choices", [])
                    if not choices:
                        return LLMResponse(
                            tool_name=None,
                            is_finish=True,
                            latency_ms=latency,
                            prompt_tokens=p_tokens,
                            completion_tokens=c_tokens,
                            total_tokens=t_tokens,
                        )

                    msg = choices[0].get("message", {})
                    tool_calls = msg.get("tool_calls", [])
                    if tool_calls:
                        tc = tool_calls[0]
                        tc_id = tc.get("id")
                        fn = tc.get("function", {})
                        fn_name = fn.get("name")
                        try:
                            fn_args = json.loads(fn.get("arguments", "{}"))
                        except Exception:
                            fn_args = {}
                        return LLMResponse(
                            tool_name=fn_name,
                            arguments=fn_args,
                            is_finish=False,
                            latency_ms=latency,
                            tool_call_id=tc_id,
                            prompt_tokens=p_tokens,
                            completion_tokens=c_tokens,
                            total_tokens=t_tokens,
                        )

                    content = msg.get("content", "")
                    return LLMResponse(
                        tool_name=None,
                        is_finish=True,
                        raw_text=content,
                        latency_ms=latency,
                        prompt_tokens=p_tokens,
                        completion_tokens=c_tokens,
                        total_tokens=t_tokens,
                    )

            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    time.sleep((2 ** attempt) * 1.5)
                    continue
                raise RuntimeError(f"OpenAI API HTTP Error {e.code}: {e.read().decode('utf-8')}") from e
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"OpenAI API request failed: {e}") from e

        raise RuntimeError(f"OpenAI API failed after {self.max_retries} attempts: {last_err}")


class MockLLMProvider(LLMProvider):
    """Deterministic, canary-auditing Mock provider for tests and CI."""

    def __init__(
        self,
        model: str = "mock-model-v1",
        temperature: float = 0.0,
        decision_sequence: Optional[List[Dict[str, Any]]] = None,
        dynamic_policy: Optional[Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], LLMResponse]] = None,
        canary_tokens: Optional[Set[str]] = None,
    ):
        super().__init__(model=model, temperature=temperature)
        self.decision_sequence = list(decision_sequence) if decision_sequence else []
        self.dynamic_policy = dynamic_policy
        self.canary_tokens = canary_tokens or set()
        self.call_count = 0
        self.received_messages: List[List[Dict[str, Any]]] = []

    def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> LLMResponse:
        self.call_count += 1
        self.received_messages.append(messages)

        # Audit prompt messages for information leaks or canary tokens
        for m in messages:
            content = str(m.get("content", ""))
            assert_no_information_leak(content, extra_forbidden=self.canary_tokens)

        # Dynamic policy takes precedence
        if self.dynamic_policy:
            return self.dynamic_policy(messages, tools)

        # Next in pre-programmed sequence
        if self.decision_sequence:
            action = self.decision_sequence.pop(0)
            return LLMResponse(
                tool_name=action.get("name"),
                arguments=action.get("arguments", {}),
                is_finish=action.get("finish", False),
                latency_ms=10.0
            )

        # Default fallback: stop
        return LLMResponse(tool_name=None, is_finish=True, latency_ms=5.0)


def create_llm_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> LLMProvider:
    """Factory to instantiate the appropriate LLM provider."""
    # 1. Explicit provider
    if provider_name == "gemini":
        return GeminiProvider(model=model or "gemini-1.5-pro", temperature=temperature)
    if provider_name == "openai":
        return OpenAIProvider(model=model or "gpt-4o", temperature=temperature)
    if provider_name == "mock":
        return MockLLMProvider(model=model or "mock-model-v1", temperature=temperature)

    # 2. Auto-detect from environment
    if os.environ.get("GEMINI_API_KEY"):
        return GeminiProvider(model=model or "gemini-1.5-pro", temperature=temperature)
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIProvider(model=model or "gpt-4o", temperature=temperature)

    raise ValueError(
        "No LLM provider credentials configured. Please set GEMINI_API_KEY or OPENAI_API_KEY, "
        "or pass provider_name='mock' for testing."
    )
