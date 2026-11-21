# FCA-IGAR Milestone 3 Final Experiment Summary

**Source of Truth:** `docs/FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md`

## 1. Experimental Matrix Overview

- **Scenarios**: 18 total (12 Class A, 6 Class B; 6 Gmail, 6 Slack, 6 Drive).
- **Thesis 10-Scenario Subset**: `gmail_A_1, slack_A_1, drive_A_1, gmail_A_3, slack_A_3, drive_A_3, gmail_A_I, slack_A_I, gmail_B_I, slack_B_I`.
- **Conditions**: C1 (Vanilla), C4 (Retry-only), C5 (Approval-gated), C6 (Retry+Approval), C7 (FCA fixed-K), C8 (IGAR), C9 (Candidate ablation).
- **Post-exhaustion Modes**: `strict` (harness blocks non-HIGH) and `open` (freeze lifted for ordinary calls). Evaluated side-by-side without pooling.

## 2. Metric Results Table: Strict Mode

| Condition | PDR | SCR | RSR | GUER | AUER | UGR | LES | Total RC | Mean RC | Blocked Calls |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C4 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C5 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C6 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C7 | 0.5 | 0.5 | 0.25 | 0.0 | 0.0 | 0.3333 | 1.0 | 33 | 1.83 | 15 |
| C8 | 0.9444 | 0.9444 | 0.9167 | 0.0 | 0.0 | 0.0 | 1.0 | 14 | 0.78 | 25 |
| C9 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 27 | 1.5 | 18 |

## 3. Metric Results Table: Open Mode

| Condition | PDR | SCR | RSR | GUER | AUER | UGR | LES | Total RC | Mean RC | Blocked Calls |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C4 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C5 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C6 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0 | 0.0 | 0 |
| C7 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 33 | 1.83 | 0 |
| C8 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 14 | 0.78 | 12 |
| C9 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 27 | 1.5 | 12 |

## 4. Key Comparative Findings

1. **GUER Freeze Enforcement**: Under C7, C8, and C9, `GUER = 0.0` in all modes by construction, confirming that the Controller rigorously blocks premature HIGH requests during the recovery window.
2. **Recovery Call Efficiency (H7)**: In Class A scenarios under `strict` mode, C8 uses fewer total recovery calls than C7 (e.g. Gmail B=1 uses 1 RC; Slack/Drive B=2 uses 2 RC).
3. **Legitimate Escalation Preservation (LES / H8)**: In Class B scenarios, C8 ($B=0$) achieves `LES = 1.0` (6/6 Class B granted and completed), preserving legitimate escalation without wasting unnecessary recovery attempts.
4. **Strict vs Open Separation**: In `open` mode, Class A tasks recover without escalation (`RSR = 1.0`), whereas in `strict` mode, post-exhaustion blocking forces escalation where lower-scope paths remain unpermitted.
