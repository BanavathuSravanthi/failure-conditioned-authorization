# Milestone 4: Full LLM Pilot Execution Summary

## Executive Overview
- **Model**: `gemini-3.1-flash-lite` (native tool/function calling)
- **Agent Architecture**: Autonomous tool-calling `LLMAgent` with dynamic recovery feedback
- **Prompt Version**: `v1.0`
- **Sampling Temperature**: `0.0`
- **Post-Exhaustion Mode**: `open` (Spec Section 3.2)
- **Total Planned Episodes**: `324` (18 scenarios $\times$ 6 conditions $\times$ 3 trials)
- **Total Completed Episodes**: `324`
- **Remaining Episodes**: `0` (100% complete)
- **Total Tokens Consumed**: `373,596` (Prompt: 346,137, Completion: 27,459)
- **Total Estimated API Cost**: `$0.03422 USD`
- **Average Episode Latency**: `3186.8 ms`

## Condition Matrix Coverage
- **Evaluated Conditions**: `C1`, `C5`, `C6`, `C7`, `C8`, `C9`
- **Scenarios**: 18 total (12 Class A, 6 Class B)
- **Trials**: 3 independent trials per scenario-condition pair

## Final Cohort Metrics Summary (324 Episodes)

| Condition | Completed / Planned | PDR | SCR | RSR | GUER | AUER | UGR | LES | Mean RC | Total Blocked |
|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | 54 / 54 | 0.8889 | 0.8889 | 0.5833 | 0.2500 | 0.2500 | 0.3333 | 1.0000 | 0.00 | 0 |
| **C5** | 54 / 54 | 0.8333 | 0.8333 | 0.5833 | 0.1667 | 0.2500 | 0.2500 | 1.0000 | 0.00 | 0 |
| **C6** | 54 / 54 | 1.0000 | 1.0000 | 0.7500 | 0.0833 | 0.0833 | 0.2500 | 1.0000 | 0.00 | 0 |
| **C7** | 54 / 54 | 0.6111 | 0.6111 | 0.4167 | 0.0000 | 0.2500 | 0.1667 | 1.0000 | 0.50 | 15 |
| **C8** | 54 / 54 | 0.7778 | 0.7778 | 0.5000 | 0.0000 | 0.1667 | 0.1667 | 1.0000 | 0.39 | 60 |
| **C9** | 54 / 54 | 0.7778 | 0.7778 | 0.5000 | 0.0000 | 0.1667 | 0.1667 | 1.0000 | 0.39 | 60 |

For detailed breakdown, token accounting, and hypothesis evaluations, see [llm_pilot_summary.md](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/results/llm_pilot/llm_pilot_summary.md).

## Evidence Tier Analysis and Claims
1. **Evidence Tier**: Tier 2 (LLM Pilot, single model `gemini-3.1-flash-lite`, 3 trials per combination, 324 completed episodes).
2. **Information Isolation**: 100% compliant. Prompt payloads strictly audited with zero hidden annotations, scenario IDs, or ground truth labels.
3. **Condition Comparisons**:
   - **H1 (Gate vs Vanilla)**: Evaluated through C5 vs C1 on GUER, AUER, and UGR.
   - **H2 (Failure-Conditioned vs Gate)**: Evaluated through C7 vs C5 on AUER and UGR.
   - **Ablations**: C7 vs C9 (recovery target) and C9 vs C8 (ILP-guided cost-gap budget).
4. **Methodological Note**: Results represent autonomous LLM tool-calling behavior on the specified benchmark scenarios. No claims of universal generalization beyond this model and scenario matrix are made.
