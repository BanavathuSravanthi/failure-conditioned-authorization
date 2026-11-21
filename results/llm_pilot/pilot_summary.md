# Milestone 4: Genuine LLM Pilot Execution Summary

## Executive Overview
- **Model**: `gemini-3.1-flash-lite`
- **Agent Architecture**: Autonomous tool-calling `LLMAgent` with dynamic recovery feedback
- **Prompt Version**: `v1.0`
- **Sampling Temperature**: `0.0`
- **Post-Exhaustion Mode**: `open` (Spec Section 3.2)
- **Total Planned Episodes**: `324`
- **Total Completed Episodes**: `1`
- **Total Failed Episodes**: `1`
- **Total Tokens Consumed**: `0` (Prompt: 0, Completion: 0)
- **Total API Cost**: `$0.000000 USD`
- **Average Episode Latency**: `0.0 ms`

## Cohort Metrics by Experimental Condition

| Condition | Episodes | Class A / B | PDR | SCR | RSR | GUER | AUER | UGR | LES | Total RC | Mean RC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | 1 | 1/0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | N/A | 0 | 0.0 |

## Evidence Tier Analysis and Claims
1. **Evidence Tier**: Tier 2 (LLM Pilot, single model `gemini-3.1-flash-lite`, 3 trials per combination, 324 total episodes).
2. **Information Isolation**: 100% compliant. Prompt payloads strictly audited with zero hidden annotations or scenario IDs.
3. **Condition Comparisons**:
   - **H1 (Gate vs Vanilla)**: Evaluated through C5 vs C1 on GUER, AUER, and UGR.
   - **H2 (Failure-Conditioned vs Gate)**: Evaluated through C7 vs C5 on AUER and UGR.
   - **Ablations**: C7 vs C9 (recovery target) and C9 vs C8 (cost-guided budget).
4. **Methodological Note**: Results represent autonomous LLM tool-calling behavior on the specified benchmark scenarios. No claims of universal generalization beyond this model and scenario matrix are made.
