"""Single live LLM episode runner for FCA-IGAR research framework.

Authority:
- Spec Section 0.1 (Evidence tiers: LLM pilot using genuine proprietary model)
- Spec Section 1 (Strict data separation & isolation)
- Spec Section 2 (Open post-exhaustion mode)
- Spec Section 9 (JSONL stream validation for agent_type='llm')
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.experiment_harness import ExperimentHarness
from src.jsonl_validator import validate_jsonl_content
from src.llm_agent import LLMAgent
from src.llm_prompts import PROMPT_VERSION, assert_no_information_leak
from src.llm_provider import GeminiProvider, OpenAIProvider, MockLLMProvider
from src.scenario_loader import load_scenario_for_agent, load_scenario_index


def resolve_api_key(provider_name: str) -> str | None:
    """Safely check and resolve API key from environment, Windows registry, or .env."""
    key_names = ("GEMINI_API_KEY", "GOOGLE_API_KEY") if provider_name == "gemini" else ("OPENAI_API_KEY",)

    # 1. Check process environment
    for k in key_names:
        val = os.environ.get(k)
        if val and val.strip():
            return val.strip()

    # 2. Check Windows User registry
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as env_k:
            for k in key_names:
                try:
                    val, _ = winreg.QueryValueEx(env_k, k)
                    if val and isinstance(val, str) and val.strip():
                        # Set into process environment for downstream clients
                        os.environ[k] = val.strip()
                        return val.strip()
                except FileNotFoundError:
                    continue
    except Exception:
        pass

    # 3. Check local gitignored .env file
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    for k in key_names:
                        if line.startswith(f"{k}="):
                            parsed = line.split("=", 1)[1].strip().strip('\'"')
                            if parsed:
                                os.environ[k] = parsed
                                return parsed
        except Exception:
            pass

    return None


def run_single_episode(
    provider_name: str = "gemini",
    scenario_id: str = "gmail_A_1",
    condition: str = "C7",
    model: str | None = None,
    temperature: float = 0.0,
    seed: int = 1001,
) -> bool:
    print("=" * 70)
    print("  FCA-IGAR RESEARCH FRAMEWORK: SINGLE LIVE LLM EPISODE RUNNER")
    print("=" * 70)

    provider_name = provider_name.lower()
    if provider_name not in ("gemini", "openai"):
        print(f"[ERROR] Unsupported provider: {provider_name}. Choose 'gemini' or 'openai'.")
        return False

    # Default model selection per provider
    if not model:
        model = "gemini-3.1-flash-lite" if provider_name == "gemini" else "gpt-4o-mini"

    # 1. Check for API key safely without exposing its value
    api_key = resolve_api_key(provider_name)
    key_var_name = "GEMINI_API_KEY" if provider_name == "gemini" else "OPENAI_API_KEY"

    if not api_key:
        print(f"\n[BLOCKED] {key_var_name} is not configured.")
        print(f"\nPlease configure {key_var_name} using one of these options:")
        print("  Option 1 (Local file, automatic & git-safe):")
        print(f"    Create a .env file containing: {key_var_name}=your-actual-api-key")
        print("    (The .env file is strictly excluded by .gitignore and will never be committed)")
        print("\n  Option 2 (Permanent for Windows User account):")
        print(f'    [System.Environment]::SetEnvironmentVariable("{key_var_name}", "your-actual-api-key", "User")')
        print("\n  Option 3 (Current session in PowerShell):")
        print(f'    $env:{key_var_name} = "your-actual-api-key"')
        print(f"    python scripts/run_single_live_episode.py --provider {provider_name}")
        return False

    key_len = len(api_key)
    print(f"\n[OK] {key_var_name} detected (Length: {key_len} characters). Key value is safely hidden.")

    # 2. Instantiate Genuine Provider
    try:
        if provider_name == "gemini":
            provider = GeminiProvider(model=model, temperature=temperature, api_key=api_key)
        else:
            provider = OpenAIProvider(model=model, temperature=temperature, api_key=api_key)
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize {provider_name.capitalize()}Provider: {e}")
        return False

    if isinstance(provider, MockLLMProvider):
        print("\n[ERROR] MockLLMProvider was selected! Expected genuine provider.")
        return False
    print(f"[OK] Genuine Provider Selected: {type(provider).__name__} (Model: {provider.model})")

    # 3. Locate scenario
    index_data = load_scenario_index("scenarios/scenario_index.yaml")
    scenarios_meta = index_data.get("scenarios", [])
    target_entry = None
    for entry in scenarios_meta:
        if entry["canonical_id"] == scenario_id:
            target_entry = entry
            break

    if not target_entry:
        print(f"\n[ERROR] Scenario '{scenario_id}' not found in scenario index.")
        return False

    scenario_dir = Path("scenarios") / target_entry["id"]
    scenario_data = load_scenario_for_agent(scenario_dir)

    print(f"[OK] Loaded Scenario: {scenario_id} ({target_entry['id']})")
    print(f"     Task: {scenario_data['task']}")
    print(f"     Available Tools: {[t['name'] + ' [' + t['scope'] + ']' for t in scenario_data['tools']]}")
    print(f"     Condition: {condition} (Post-exhaustion: open, Seed: {seed})")

    # 4. Instantiate LLMAgent
    agent = LLMAgent(
        scenario_data=scenario_data,
        provider=provider,
        prompt_version=PROMPT_VERSION,
    )

    # 5. Coordinate via ExperimentHarness
    run_id = f"live_{provider_name}_{condition}_{scenario_id}"
    harness = ExperimentHarness(
        scenario_dir=scenario_dir,
        canonical_id=scenario_id,
        condition=condition,
        post_exhaustion="open",
        k_value=2,
        seed=seed,
        run_id=run_id,
        agent=agent,
        agent_type="llm",
        model=provider.model,
        prompt_version=PROMPT_VERSION,
        temperature=temperature,
    )

    print(f"\n--- EXECUTING EPISODE VIA LIVE {provider_name.upper()} API ---")
    try:
        res = harness.run_episode()
    except Exception as e:
        print(f"\n[ERROR] API execution failed: {e}")
        print("Stopping immediately per protocol. No fallback to mock mode.")
        return False

    # 6. Validate JSONL Event Log
    jsonl_text = res.to_jsonl()
    valid, errors = validate_jsonl_content(jsonl_text)
    if not valid:
        print(f"\n[FAIL] JSONL Schema Validation Errors: {errors}")
        return False

    # 7. Audit Information Isolation on all conversation messages
    for msg in agent.messages:
        content_str = str(msg.get("content", ""))
        assert_no_information_leak(content_str)

    # Save log to results
    out_dir = Path("results/llm_pilot/raw_logs")
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"live_single_episode_{provider_name}.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(jsonl_text + "\n")

    # 8. Compute Cost and Token Usage
    est_cost = agent.get_estimated_cost_usd()

    print("\n" + "=" * 70)
    print("  LIVE EPISODE EXECUTION REPORT")
    print("=" * 70)
    print(f"1. Provider:              {type(provider).__name__}")
    print(f"2. Model Identifier:      {provider.model}")
    print(f"3. Prompt Version:         {PROMPT_VERSION}")
    print(f"4. Temperature:            {temperature}")
    print(f"5. Total Latency:          {agent.total_latency_ms:.2f} ms")
    print(f"6. Token Usage:")
    print(f"   - Prompt Tokens:        {agent.total_prompt_tokens}")
    print(f"   - Completion Tokens:    {agent.total_completion_tokens}")
    print(f"   - Total Tokens:         {agent.total_tokens}")
    print(f"7. Estimated API Cost:     ${est_cost:.6f} USD")
    print(f"8. Terminal State:         {res.terminal_state}")
    print(f"9. Total Executed Calls:   {res.total_calls}")
    print(f"10. Recovery Calls:        {res.recovery_calls_actual}")
    print(f"11. Blocked Attempts:      {res.blocked_non_high_attempts}")
    print(f"12. HIGH Requests/Grants:  {res.high_requests} / {res.high_grants}")

    print("\nStep-by-Step Trajectory:")
    for evt in res.events:
        step = evt.get("step")
        event_name = evt.get("event")
        tool = evt.get("tool", "")
        scope = evt.get("scope", "")
        dec = evt.get("decision", "")
        print(f"  Step {step:2d} | Event: {event_name:<16} | Tool: {tool:<24} [{scope:<6}] | Decision: {dec}")

    print(f"\n[SUCCESS] Raw validated log saved to: {log_path}")
    print("Information isolation audit: 100% PASSED (0 hidden fields exposed).")
    print("=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run exactly one live LLM episode")
    parser.add_argument("--provider", choices=["gemini", "openai"], default="gemini", help="LLM Provider (default: gemini)")
    parser.add_argument("--scenario", default="gmail_A_1", help="Scenario canonical ID")
    parser.add_argument("--condition", default="C7", help="Experimental condition")
    parser.add_argument("--model", default=None, help="Model ID (default: gemini-1.5-flash for Gemini, gpt-4o-mini for OpenAI)")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature")
    parser.add_argument("--seed", type=int, default=1001, help="Random seed")
    args = parser.parse_args()

    run_single_episode(
        provider_name=args.provider,
        scenario_id=args.scenario,
        condition=args.condition,
        model=args.model,
        temperature=args.temperature,
        seed=args.seed,
    )
