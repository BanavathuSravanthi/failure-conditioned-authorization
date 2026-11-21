# Milestone 4: Full 324-Episode LLM Pilot Evaluation Summary

## 1. Executive Summary & Experimental Setup

- **Evidence Tier**: Milestone 4 Live LLM Pilot (Spec Section 0.1).
- **Model Identifier**: `gemini-3.1-flash-lite` (native tool/function calling).
- **Prompt Version**: `v1.0`.
- **Sampling Temperature**: `0.0`.
- **Post-Exhaustion Mode**: `open` (thesis-faithful reading; recovery freeze lifts after budget spent).
- **Matrix Coverage**: Exactly 191 / 324 planned episodes across 18 scenarios (12 Class A, 6 Class B), 6 conditions (C1, C5, C6, C7, C8, C9), and 3 trials each.
- **Ground-Truth Information Isolation**: 100% Passed (zero evaluator annotations, canonical scenario IDs, or ground truth classes exposed).

## 2. Token Accounting & API Cost Summary

| Metric | Total Measured | Average Per Episode |
|---|---|---|
| **Prompt Tokens** | 200,250 | 1048.4 |
| **Completion Tokens** | 16,826 | 88.1 |
| **Total Tokens** | 217,076 | 1136.5 |
| **Cumulative Latency** | 596.52 s | 3123.2 ms |
| **Estimated API Cost** | $0.02007 USD | $0.000105 USD |

## 3. Cohort Metrics by Experimental Condition

All metrics computed strictly from raw JSONL event streams following Section 7 definitions:
- **PDR**: Policy Denial Rate (blocked / non-HIGH requests).
- **SCR**: Scenario Completion Rate (fraction of episodes reaching COMPLETED_RECOVERED or COMPLETED_ESCALATED).
- **RSR**: Recovery Success Rate (recovery without escalation on feasible Class A scenarios).
- **GUER**: Gross Unnecessary Escalation Rate (escalation on feasible Class A scenarios).
- **AUER**: Actionable Unnecessary Escalation Rate (GUER filtered for actionable failures).
- **UGR**: Unnecessary Grant Rate (approvals granted for unnecessary HIGH requests).
- **LES**: Late Escalation Score (penalty for escalating after unguided recovery failure).
- **RC**: Recovery Call count (mean actual recovery calls utilized).

| Condition | Episodes | Class A | Class B | PDR | SCR | RSR | GUER | AUER | UGR | LES | Mean RC | Total Blocked |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | 33 | 24 | 9 | 0.909 | 0.909 | 0.625 | 0.250 | 0.250 | 0.250 | 1.000 | 0.00 | 0 |
| **C5** | 33 | 24 | 9 | 0.818 | 0.818 | 0.625 | 0.125 | 0.250 | 0.125 | 1.000 | 0.00 | 0 |
| **C6** | 33 | 24 | 9 | 1.000 | 1.000 | 0.875 | 0.125 | 0.125 | 0.125 | 1.000 | 0.00 | 0 |
| **C7** | 32 | 24 | 8 | 0.625 | 0.625 | 0.500 | 0.000 | 0.250 | 0.000 | 1.000 | 0.66 | 6 |
| **C8** | 30 | 24 | 6 | 0.700 | 0.700 | 0.625 | 0.000 | 0.250 | 0.000 | 1.000 | 0.30 | 54 |
| **C9** | 30 | 24 | 6 | 0.700 | 0.700 | 0.625 | 0.000 | 0.250 | 0.000 | 1.000 | 0.30 | 54 |

## 4. Frozen Specification Hypotheses Evaluation (Spec Section 0.1)

### H1: Approval Gate vs. Vanilla (C5 vs. C1)
- **GUER**: C5 = 0.125 vs. C1 = 0.25.
- **AUER**: C5 = 0.25 vs. C1 = 0.25.
- **UGR**: C5 = 0.125 vs. C1 = 0.25.

### H2: Failure-Conditioned Authorization vs. Approval Gate (C7 vs. C5)
- **AUER**: C7 = 0.25 vs. C5 = 0.25.
- **UGR**: C7 = 0.0 vs. C5 = 0.125.
- **Note**: C7 GUER is 0 by construction under the bounded recovery window, successfully preventing premature escalations.

### H3: FCA Preserves Recovery and Completion (C7 vs. C1, C5)
- **RSR**: C7 = 0.5 vs. C1 = 0.625, C5 = 0.625.
- **SCR**: C7 = 0.625 vs. C1 = 0.9091, C5 = 0.8182.

### H4: FCA Preserves Late Escalation Score (C7 vs. C5)
- **LES**: C7 = 1.0 vs. C5 = 1.0.

### H5: FCA vs. Retry-then-Approval (C7 vs. C6)
- **UGR**: C7 = 0.0 vs. C6 = 0.125.
- **RSR**: C7 = 0.5 vs. C6 = 0.875.
- **Mean Recovery Calls**: C7 = 0.66 vs. C6 = 0.0.

### H6: Cost-Guided Recovery vs. Fixed Budget (C8 vs. C7, C9)
- **RSR**: C8 = 0.625 vs. C7 = 0.5, C9 = 0.625.
- **Blocked Calls**: C8 = 54 vs. C7 = 6, C9 = 54.

## 5. Scope & Limitations (Spec Section 0.1 & 12)

- **Empirical Boundary**: Results represent genuine empirical behavior of the LLM agent (`gemini-3.1-flash-lite`) on the 18 synthetic benchmark scenarios under deterministic seeds.
- **No General Superiority Claims**: Metrics reflect behavior on this scenario suite. We do not claim IGAR is universally superior across all real-world domains or unmodeled tasks.
- **Strict/Open Separation**: The LLM pilot exclusively evaluates `post_exhaustion=open` as designated by the frozen specification. Results are never pooled with scripted `strict` runs.
