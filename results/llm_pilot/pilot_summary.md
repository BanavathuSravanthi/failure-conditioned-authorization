# Milestone 4: Interim LLM Pilot Execution Summary

## Executive Overview
- **Model**: `gemini-3.1-flash-lite` (native tool/function calling)
- **Agent Architecture**: Autonomous tool-calling `LLMAgent` with dynamic recovery feedback
- **Prompt Version**: `v1.0`
- **Sampling Temperature**: `0.0`
- **Post-Exhaustion Mode**: `open` (Spec Section 3.2)
- **Total Planned Episodes**: `324` (18 scenarios $\times$ 6 conditions $\times$ 3 trials)
- **Total Completed Episodes**: `191`
- **Remaining Episodes**: `133` (paused at provider free-tier daily rate limit)
- **Total Tokens Consumed**: `217,076` (Prompt: 200,250, Completion: 16,826)
- **Total Estimated API Cost**: `$0.02007 USD`
- **Average Episode Latency**: `3123.2 ms`

## Condition Matrix Coverage
- **Evaluated Conditions**: `C1`, `C5`, `C6`, `C7`, `C8`, `C9`
- **Scenarios**: 18 total (12 Class A, 6 Class B)
- **Trials**: 3 independent trials per scenario-condition pair

## Interim Cohort Metrics Summary (191 Episodes)

| Condition | Completed / Planned | PDR | SCR | RSR | GUER | AUER | UGR | LES | Mean RC | Total Blocked |
|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | 33 / 54 | 0.909 | 0.909 | 0.625 | 0.250 | 0.250 | 0.250 | 1.000 | 0.00 | 0 |
| **C5** | 33 / 54 | 0.818 | 0.818 | 0.625 | 0.125 | 0.250 | 0.125 | 1.000 | 0.00 | 0 |
| **C6** | 33 / 54 | 1.000 | 1.000 | 0.875 | 0.125 | 0.125 | 0.125 | 1.000 | 0.00 | 0 |
| **C7** | 32 / 54 | 0.625 | 0.625 | 0.500 | 0.000 | 0.250 | 0.000 | 1.000 | 0.66 | 6 |
| **C8** | 30 / 54 | 0.700 | 0.700 | 0.625 | 0.000 | 0.250 | 0.000 | 1.000 | 0.30 | 54 |
| **C9** | 30 / 54 | 0.700 | 0.700 | 0.625 | 0.000 | 0.250 | 0.000 | 1.000 | 0.30 | 54 |

For detailed breakdown, token accounting, and hypothesis evaluations, see [llm_pilot_summary.md](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/results/llm_pilot/llm_pilot_summary.md).

## Evidence Tier Analysis and Claims
1. **Evidence Tier**: Tier 2 (LLM Pilot, single model `gemini-3.1-flash-lite`, 3 trials per combination, 324 planned episodes, 191 currently completed).
2. **Information Isolation**: 100% compliant. Prompt payloads strictly audited with zero hidden annotations, scenario IDs, or ground truth labels.
3. **Condition Comparisons**:
   - **H1 (Gate vs Vanilla)**: Evaluated through C5 vs C1 on GUER, AUER, and UGR.
   - **H2 (Failure-Conditioned vs Gate)**: Evaluated through C7 vs C5 on AUER and UGR.
   - **Ablations**: C7 vs C9 (recovery target) and C9 vs C8 (ILP-guided cost-gap budget).
4. **Methodological Note**: Results represent autonomous LLM tool-calling behavior on the specified benchmark scenarios. No claims of universal generalization beyond this model and scenario matrix are made.
