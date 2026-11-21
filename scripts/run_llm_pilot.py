"""Batch runner and evaluator for Milestone 4 LLM Pilot.

Authority:
- Spec Section 0.1 (Evidence tiers: LLM pilot, one model, 3 trials per scenario and condition)
- Spec Section 2 (Conditions C1, C5, C6, C7, C8, C9; post_exhaustion='open')
- Spec Section 3.2 (LLM pilot uses open mode)
- Spec Section 7 (Metrics: PDR, RSR, GUER, AUER, UGR, LES, SCR, RC)
- Spec Section 9 (JSONL stream validation for agent_type='llm')
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, ".")

from src.analysis import parse_episode_events, EpisodeMetrics, MetricAggregator, export_metrics_to_csv
from src.experiment_harness import ExperimentHarness
from src.jsonl_validator import validate_jsonl_content
from src.llm_agent import LLMAgent
from src.llm_prompts import PROMPT_VERSION
from src.llm_provider import LLMProvider, create_llm_provider, MockLLMProvider
from src.scenario_loader import load_scenario_index, load_scenario_for_agent

SCENARIO_SEEDS = {
    "gmail_A_1": 1001,
    "gmail_A_3": 1002,
    "gmail_A_3b": 1003,
    "gmail_A_I": 1004,
    "gmail_B_I": 1005,
    "gmail_B_I2": 1006,
    "slack_A_1": 2001,
    "slack_A_3": 2002,
    "slack_A_3b": 2003,
    "slack_A_I": 2004,
    "slack_B_I": 2005,
    "slack_B_I2": 2006,
    "drive_A_1": 3001,
    "drive_A_3": 3002,
    "drive_A_3b": 3003,
    "drive_A_I": 3004,
    "drive_B_I": 3005,
    "drive_B_I2": 3006,
}

LLM_CONDITIONS = ["C1", "C5", "C6", "C7", "C8", "C9"]
NUM_TRIALS = 3


def run_llm_pilot(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    output_dir: str = "results/llm_pilot",
    use_mock: bool = False,
    max_episodes: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute the full 324-episode LLM pilot matrix."""
    out_path = Path(output_dir)
    logs_dir = out_path / "raw_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize LLM provider
    if use_mock:
        print("[LLM Pilot] Running in MOCK mode for dry-run verification.")
        # Program a realistic decision sequence: try MEDIUM, then LOW
        decisions = [
            {"name": "gmail.send_draft", "arguments": {}},
            {"name": "gmail.archive_thread", "arguments": {}},
            {"name": "gmail.get_threads", "arguments": {}},
            {"finish": True}
        ]
        provider: LLMProvider = MockLLMProvider(
            model=model_name or "mock-gpt4",
            temperature=temperature,
            decision_sequence=decisions
        )
    else:
        try:
            provider = create_llm_provider(
                provider_name=provider_name,
                model=model_name,
                temperature=temperature,
            )
            print(f"[LLM Pilot] Connected to live provider: {type(provider).__name__} (Model: {provider.model})")
        except ValueError as e:
            print(f"\n[ERROR] Unable to initialize LLM provider: {e}")
            print("Please ensure GEMINI_API_KEY or OPENAI_API_KEY is exported, or pass --mock for verification.")
            return {"status": "FAILED_MISSING_CREDENTIALS", "error": str(e)}

    # 2. Load scenario index
    index_data = load_scenario_index("scenarios/scenario_index.yaml")
    scenarios_meta = index_data.get("scenarios", [])

    total_runs = len(scenarios_meta) * len(LLM_CONDITIONS) * NUM_TRIALS
    print(f"[LLM Pilot] Planning {total_runs} episodes across 18 scenarios, {len(LLM_CONDITIONS)} conditions, {NUM_TRIALS} trials.")

    completed_episodes = 0
    failed_episodes = 0
    results_records = []

    for sc_entry in scenarios_meta:
        canon_id = sc_entry["canonical_id"]
        dir_name = sc_entry["id"]
        scenario_dir = Path("scenarios") / dir_name
        base_seed = SCENARIO_SEEDS.get(canon_id, 42)

        for cond in LLM_CONDITIONS:
            for trial in range(1, NUM_TRIALS + 1):
                if max_episodes and completed_episodes >= max_episodes:
                    break

                seed = base_seed + (trial * 1000)
                run_id = f"llm_{cond}_{canon_id}_t{trial}"
                log_file = logs_dir / f"C{cond}_{canon_id}_trial_{trial}.jsonl"

                # If mock provider, refresh decisions per episode
                if use_mock:
                    provider = MockLLMProvider(
                        model=model_name or "mock-gpt4",
                        temperature=temperature,
                        decision_sequence=[
                            {"name": "gmail.send_draft", "arguments": {}},
                            {"name": "gmail.archive_thread", "arguments": {}},
                            {"name": "gmail.get_threads", "arguments": {}},
                            {"finish": True}
                        ]
                    )

                scenario_data = load_scenario_for_agent(scenario_dir)
                agent = LLMAgent(
                    scenario_data=scenario_data,
                    provider=provider,
                    prompt_version=PROMPT_VERSION,
                )

                harness = ExperimentHarness(
                    scenario_dir=scenario_dir,
                    canonical_id=canon_id,
                    condition=cond,
                    post_exhaustion="open",  # Spec Section 3.2: LLM pilot strictly uses open mode
                    k_value=2,
                    seed=seed,
                    run_id=run_id,
                    agent=agent,
                    agent_type="llm",
                    model=provider.model,
                    prompt_version=PROMPT_VERSION,
                    temperature=temperature,
                )

                try:
                    res = harness.run_episode()
                    jsonl_text = res.to_jsonl()

                    # Stream schema validation
                    valid, errs = validate_jsonl_content(jsonl_text)
                    if not valid:
                        raise ValueError(f"JSONL schema validation failed for {run_id}: {errs}")

                    with open(log_file, "w", encoding="utf-8") as f:
                        f.write(jsonl_text + "\n")

                    completed_episodes += 1
                    results_records.append({
                        "run_id": run_id,
                        "canonical_id": canon_id,
                        "condition": cond,
                        "trial": trial,
                        "terminal_state": res.terminal_state,
                        "total_calls": res.total_calls,
                        "recovery_calls": res.recovery_calls_actual,
                        "blocked_calls": res.blocked_non_high_attempts,
                        "high_requests": res.high_requests,
                        "high_grants": res.high_grants,
                    })

                    print(f"[{completed_episodes}/{total_runs}] {run_id} -> {res.terminal_state} (Calls: {res.total_calls}, RC: {res.recovery_calls_actual})")

                except Exception as e:
                    failed_episodes += 1
                    print(f"[FAIL] Error in {run_id}: {e}")

    # 3. Export Per-Scenario Results CSV
    per_scenario_csv = out_path / "per_scenario.csv"
    if results_records:
        with open(per_scenario_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results_records[0].keys()))
            writer.writeheader()
            writer.writerows(results_records)

    # 4. Compute Cohort Metrics from Raw Logs
    raw_files = glob.glob(str(logs_dir / "*.jsonl"))
    episodes = []
    for rf in raw_files:
        with open(rf, "r", encoding="utf-8") as f:
            episodes.append(EpisodeMetrics(parse_episode_events(f.read())))

    by_condition = {}
    for ep in episodes:
        by_condition.setdefault(ep.condition, []).append(ep)

    condition_metrics = {}
    for cond in LLM_CONDITIONS:
        cohort = by_condition.get(cond, [])
        if cohort:
            agg = MetricAggregator(cond, cohort)
            condition_metrics[cond] = agg.compute_metrics()

    summary_data = {
        "agent_type": "llm",
        "model": provider.model,
        "prompt_version": PROMPT_VERSION,
        "temperature": temperature,
        "post_exhaustion": "open",
        "total_planned": total_runs,
        "total_completed": completed_episodes,
        "total_failed": failed_episodes,
        "by_condition": condition_metrics,
    }

    # Save metrics JSON & CSV
    with open(out_path / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    export_metrics_to_csv(condition_metrics, str(out_path / "metrics.csv"))

    print(f"\n[LLM Pilot Complete] Generated metrics in {out_path}/")
    return summary_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Milestone 4 LLM Pilot")
    parser.add_argument("--provider", choices=["gemini", "openai", "mock"], default=None, help="LLM Provider")
    parser.add_argument("--model", type=str, default=None, help="Model identifier")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    parser.add_argument("--mock", action="store_true", help="Run with mock provider for verification")
    parser.add_argument("--max-episodes", type=int, default=None, help="Limit episodes (e.g. for testing)")
    args = parser.parse_args()

    run_llm_pilot(
        provider_name=args.provider,
        model_name=args.model,
        temperature=args.temperature,
        use_mock=args.mock,
        max_episodes=args.max_episodes,
    )
