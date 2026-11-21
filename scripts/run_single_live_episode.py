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
from src.llm_provider import OpenAIProvider, MockLLMProvider
from src.scenario_loader import load_scenario_for_agent, load_scenario_index


def run_single_episode(
    scenario_id: str = "gmail_A_1",
    condition: str = "C7",
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    seed: int = 1001,
) -> bool:
    print("=" * 70)
    print("  FCA-IGAR RESEARCH FRAMEWORK: SINGLE LIVE LLM EPISODE RUNNER")
    print("=" * 70)

    # 1. Check for API key safely without exposing its value
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # Fallback check Windows registry
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as env_k:
                val, _ = winreg.QueryValueEx(env_k, "OPENAI_API_KEY")
                if val and isinstance(val, str) and val.strip():
                    api_key = val.strip()
                    os.environ["OPENAI_API_KEY"] = api_key
        except Exception:
            pass

    if not api_key and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ["OPENAI_API_KEY"] = api_key
                        break
        except Exception:
            pass

    if not api_key:
        print("\n[BLOCKED] OPENAI_API_KEY is not configured.")
        print("\nPlease follow these exact instructions in Windows PowerShell:")
        print("  Option A (Recommended for current session):")
        print('    $env:OPENAI_API_KEY = "sk-proj-your-actual-key"')
        print("    python scripts/run_single_live_episode.py")
        print("\n  Option B (Permanent for User account):")
        print('    [System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-proj-your-actual-key", "User")')
        print("    (Then restart terminal or re-run)")
        print("\n  Option C (Local file):")
        print('    Create a .env file containing: OPENAI_API_KEY=sk-proj-your-actual-key')
        print("    (The .env file is strictly excluded by .gitignore and will never be committed)")
        return False

    key_len = len(api_key)
    print(f"\n[OK] OPENAI_API_KEY detected (Length: {key_len} characters, Format: {'Valid sk- prefix' if api_key.startswith('sk-') else 'Custom prefix'}). Key value is safely hidden.")

    # 2. Instantiate OpenAIProvider and verify it is genuine (not Mock)
    try:
        provider = OpenAIProvider(model=model, temperature=temperature)
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize OpenAIProvider: {e}")
        return False

    if isinstance(provider, MockLLMProvider):
        print("\n[ERROR] MockLLMProvider was selected! Expected genuine OpenAIProvider.")
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
    run_id = f"live_llm_{condition}_{scenario_id}"
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

    print("\n--- EXECUTING EPISODE VIA LIVE OPENAI API ---")
    res = harness.run_episode()

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
    log_path = out_dir / "live_single_episode.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(jsonl_text + "\n")

    # 8. Compute Cost and Token Usage
    est_cost = agent.get_estimated_cost_usd()

    print("\n" + "=" * 70)
    print("  LIVE EPISODE EXECUTION REPORT")
    print("=" * 70)
    print(f"1. Model Identifier:     {provider.model}")
    print(f"2. Prompt Version:        {PROMPT_VERSION}")
    print(f"3. Temperature:           {temperature}")
    print(f"4. Total Latency:         {agent.total_latency_ms:.2f} ms")
    print(f"5. Token Usage:")
    print(f"   - Prompt Tokens:       {agent.total_prompt_tokens}")
    print(f"   - Completion Tokens:   {agent.total_completion_tokens}")
    print(f"   - Total Tokens:        {agent.total_tokens}")
    print(f"6. Estimated API Cost:    ${est_cost:.6f} USD")
    print(f"7. Terminal State:        {res.terminal_state}")
    print(f"8. Total Executed Calls:  {res.total_calls}")
    print(f"9. Recovery Calls:        {res.recovery_calls_actual}")
    print(f"10. Blocked Attempts:     {res.blocked_non_high_attempts}")
    print(f"11. HIGH Requests/Grants: {res.high_requests} / {res.high_grants}")

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
    parser.add_argument("--scenario", default="gmail_A_1", help="Scenario canonical ID")
    parser.add_argument("--condition", default="C7", help="Experimental condition")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI Model ID")
    parser.add_argument("--temperature", type=float, default=0.0, help="Temperature")
    parser.add_argument("--seed", type=int, default=1001, help="Random seed")
    args = parser.parse_args()

    run_single_episode(
        scenario_id=args.scenario,
        condition=args.condition,
        model=args.model,
        temperature=args.temperature,
        seed=args.seed,
    )
