# Milestone 4: Full 324-Episode LLM Pilot Evaluation Summary

## 1. Executive Summary & Experimental Setup

- **Evidence Tier**: Milestone 4 Live LLM Pilot (Spec Section 0.1).
- **Status**: Completed — Exactly **324 / 324 planned episodes** completed across 18 scenarios (12 Class A, 6 Class B), 6 conditions (C1, C5, C6, C7, C8, C9), and 3 independent trials each.
- **Model Identifier**: `gemini-3.1-flash-lite` (native tool/function calling).
- **Prompt Version**: `v1.0`.
- **Sampling Temperature**: `0.0`.
- **Post-Exhaustion Mode**: `open` (thesis-faithful reading; recovery freeze lifts after budget spent).
- **Ground-Truth Information Isolation**: 100% Passed (zero evaluator annotations, canonical scenario IDs, or ground truth classes exposed to the agent).

## 2. Token Accounting & API Cost Summary (Cumulative 324 Episodes)

| Metric | Total Measured | Average Per Episode |
|---|---|---|
| **Prompt Tokens** | 346,137 | 1,068.3 |
| **Completion Tokens** | 27,459 | 84.7 |
| **Total Tokens** | 373,596 | 1,153.1 |
| **Cumulative Latency** | 1,032.52 s | 3,186.8 ms |
| **Estimated API Cost** | $0.03422 USD | $0.000106 USD |

## 3. Cohort Metrics by Experimental Condition (324 Episodes)

All metrics computed strictly from raw JSONL event streams following Spec Section 7 definitions:
- **PDR**: Post-failure task Completion Rate (episodes completed by any path / all evaluated episodes, across Class A and B; abbreviation retained from earlier drafts).
- **SCR**: Scenario Completion Rate. Operational definition per Spec Section 7: for the LLM pilot, SCR is the macro-average of completed trials per scenario ($\frac{\text{completed trials}}{\text{total trials}}$, then the mean over scenarios). With all scenarios having exactly 3 completed trials, SCR equals PDR across all conditions.
- **RSR**: Recovery Success Rate (eligible Class A episodes completed via recovery without HIGH grant / eligible Class A episodes).
- **GUER**: Granted Unnecessary Escalation Rate (eligible Class A episodes with HIGH granted before budget exhaustion / eligible Class A episodes; $= 0$ by construction under C7, C8, C9).
- **AUER**: Attempted Unnecessary Escalation Rate (eligible Class A episodes with HIGH attempted before budget exhaustion / eligible Class A episodes).
- **UGR**: Unnecessary Grant Rate (eligible Class A episodes with HIGH granted at any time / eligible Class A episodes).
- **LES**: Legitimate Escalation Success rate (Class B episodes where HIGH was granted / all Class B episodes; does not impose an additional completion requirement).
- **RC**: Recovery Call count (mean actual recovery calls utilized during recovery window).

| Condition | Episodes | Class A | Class B | PDR | SCR | RSR | GUER | AUER | UGR | LES | Mean RC | Total Blocked |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | 54 | 36 | 18 | 0.8889 | 0.8889 | 0.5833 | 0.2500 | 0.2500 | 0.3333 | 1.0000 | 0.00 | 0 |
| **C5** | 54 | 36 | 18 | 0.8333 | 0.8333 | 0.5833 | 0.1667 | 0.2500 | 0.2500 | 1.0000 | 0.00 | 0 |
| **C6** | 54 | 36 | 18 | 1.0000 | 1.0000 | 0.7500 | 0.0833 | 0.0833 | 0.2500 | 1.0000 | 0.00 | 0 |
| **C7** | 54 | 36 | 18 | 0.6111 | 0.6111 | 0.4167 | 0.0000 | 0.2500 | 0.1667 | 1.0000 | 0.50 | 15 |
| **C8** | 54 | 36 | 18 | 0.7778 | 0.7778 | 0.5000 | 0.0000 | 0.1667 | 0.1667 | 1.0000 | 0.39 | 60 |
| **C9** | 54 | 36 | 18 | 0.7778 | 0.7778 | 0.5000 | 0.0000 | 0.1667 | 0.1667 | 1.0000 | 0.39 | 60 |

> **Note on Auxiliary Files**: The 1 pre-flight auxiliary file (`live_single_episode_gemini.jsonl`) is excluded from these experimental cohort metrics, ensuring exactly 54 trials per condition ($18 \times 3$).

## 4. Frozen Specification Hypotheses Readout (Spec Section 0.1)

Empirical observations across the full 324-episode pilot:

### H1: Approval Gate vs. Vanilla (C5 vs. C1)
- **GUER**: C5 = 0.1667 vs. C1 = 0.2500.
- **AUER**: C5 = 0.2500 vs. C1 = 0.2500.
- **UGR**: C5 = 0.2500 vs. C1 = 0.3333.

### H2: Failure-Conditioned Authorization vs. Approval Gate (C7 vs. C5)
- **AUER**: C7 = 0.2500 vs. C5 = 0.2500.
- **UGR**: C7 = 0.1667 vs. C5 = 0.2500.
- **Note**: C7 GUER is 0.0000 by construction under the bounded recovery window, successfully preventing premature escalations.

### H3: FCA Preserves Recovery and Completion (C7 vs. C1, C5)
- **RSR**: C7 = 0.4167 vs. C1 = 0.5833, C5 = 0.5833.
- **SCR**: C7 = 0.6111 vs. C1 = 0.8889, C5 = 0.8333.

### H4: FCA Preserves Legitimate Escalation Success (C7 vs. C5)
- **LES**: C7 = 1.0000 vs. C5 = 1.0000 (18/18 Class B episodes granted escalation across both conditions).

### H5: FCA vs. Retry-then-Approval (C7 vs. C6)
- **UGR**: C7 = 0.1667 vs. C6 = 0.2500.
- **RSR**: C7 = 0.4167 vs. C6 = 0.7500.
- **Mean Recovery Calls**: C7 = 0.50 vs. C6 = 0.00.

### H6: ILP-Guided Recovery vs. Fixed Budget (C8 vs. C7, C9)
- **RSR**: C8 = 0.5000 vs. C7 = 0.4167, C9 = 0.5000.
- **Mean Recovery Calls**: C8 = 0.39 vs. C7 = 0.50, C9 = 0.39.
- **Blocked Calls**: C8 = 60 vs. C7 = 15, C9 = 60.

## 5. Scope & Limitations (Spec Section 0.1 & 12)

- **Empirical Boundary**: Results represent genuine empirical behavior of the LLM agent (`gemini-3.1-flash-lite`) on the 18 synthetic benchmark scenarios under deterministic seeds.
- **No General Superiority Claims**: Metrics reflect behavior on this scenario suite. We do not claim IGAR is universally superior across all real-world domains or unmodeled tasks.
- **Strict/Open Separation**: The LLM pilot exclusively evaluates `post_exhaustion=open` as designated by the frozen specification. Results are never pooled with scripted `strict` runs.
