# Comparison: Scripted Agent vs. Live LLM Agent

**Source of Truth:**
- `docs/FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md`
- `docs/FCA_IGAR_defence_notes_v0_3_9.md`

---

## 1. Architectural Distinction (Spec Section 5)

| Dimension | Scripted Agent (Milestone 2 & 3) | Live LLM Agent (Milestone 4) |
| :--- | :--- | :--- |
| **Tool Ordering** | Fixed deterministic rule: MEDIUM $\rightarrow$ LOW $\rightarrow$ HIGH | Autonomous decision based on task prompt & tool descriptions |
| **Information Visibility** | Agent-visible scope tags only | Agent-visible scope tags, descriptions, and schemas |
| **Error / Denial Response** | Advance option on 3 consecutive failures or any block | Autonomous reasoning: retry tool, switch tool, request HIGH, or stop |
| **Class A Baseline Behavior** | Explores completing LOW tool before HIGH; $GUER=0.0$ by design | Free to request HIGH prematurely; susceptible to unguided escalation ($GUER > 0$) |
| **Role in Evaluation** | Strict upper bound on mechanism verification | Empirical signal for hypotheses $H_1$, $H_2$, $H_6$ (agent behavior) |

---

## 2. Hypothesis Readout & Expected Differences

1. **Premature Escalation ($H_1$ & $H_2$, GUER / AUER)**:
   - In the scripted tier, $GUER = 0.0$ across all conditions by construction because the script tries the LOW tool before HIGH.
   - For real LLM agents, unconstrained conditions (`C5` approval-gated expansion) and retry-only (`C6`) may exhibit premature escalation when the model perceives higher privilege as the quickest path to resolution.
   - Under `C7`, `C8`, and `C9`, the Controller hard-blocks premature HIGH requests during the recovery window, keeping $GUER = 0.0$ by mechanism enforcement while $AUER$ captures attempted escalation.
2. **Recovery Efficiency ($H_7$, Recovery Calls)**:
   - Scripted agent follows a fixed retry threshold (3 failures).
   - The LLM agent decides whether to retry based on error feedback. Information-guided recovery (`C8`) provides structured guidance towards feasible candidates, reducing wasted exploration compared to unguided trial-and-error (`C7`).
3. **Statistical Significance Disclosure**:
   - As mandated by Spec Section 0.1, results from 3 trials per scenario-condition pair are pilot-level demonstrations and do not claim asymptotic statistical significance.

---

## 3. Post-Exhaustion Mode Enforcement

- **Scripted Tier**: Evaluated under both `strict` and `open` modes side-by-side.
- **LLM Pilot**: Exclusively evaluated under `open` post-exhaustion mode per Spec Section 2 and Section 3.2. Scripted and LLM results are strictly reported separately and never pooled.
