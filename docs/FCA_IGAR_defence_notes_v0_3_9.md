# FCA + IGAR: defence notes for v0.3.9

Sources checked: thesis PDF, mid-sem report PDF, mid-sem deck (the three files agree with each other on metrics, conditions, K, budget formula, 10-scenario grid and limitations). Section numbers below are thesis sections.

**Say this first in the viva:** the scripted tier checks that the controller follows the rules; in `open` mode every Class A episode recovers there, so UGR is 0. Only the LLM pilot measures escalation behaviour.

## 1. The final idea in six lines

1. Question: after a call below HIGH fails, can bounded recovery stop unnecessary HIGH escalation and still allow it when HIGH is really needed?
2. FCA (C7, core): freeze HIGH after the failure, allow K=2 more calls to the same tool, then a HIGH request may reach the approver.
3. IGAR (C8, extension): if an oracle-annotated cheaper alternative exists, recover through it with budget B from the cost gap; if none exists, B=0: no recovery attempts and no HIGH freeze, so a HIGH request is eligible at once (the agent still decides whether to ask).
4. C9 (planned in thesis 3.3): fixed K=2 aimed at the candidate. C7 vs C9 isolates the target. C9 vs C8 isolates budget sizing only in Class A with a feasible candidate; Class B is reported separately because C9 retries and C8 gives no recovery attempts and no HIGH freeze, so HIGH is eligible at once.
5. Evidence: scripted agent for controller correctness, LLM pilot for real escalation behaviour, both labelled as pilot-level.
6. Metrics are exactly the thesis ones (GUER, PDR, RSR, LES, AUER); UGR is our supplement.

## 2. Every change from the thesis, with a defence

| # | Thesis says | We do | Why | One-line defence |
|---|---|---|---|---|
| 1 | 10 scenarios (Table 4.1) | 18 scenarios; the thesis 10 are a fixed subset reported alongside | A_3b is the only case where the candidate needs 2 attempts, so it is the only case that separates B=1 from B=2. A second Class B task and third-app coverage give LES more than 2 episodes. | "The thesis grid is a subset of ours; we report both." |
| 2 | Costs 1/3/6; B=1 in every case; B=2 needs per-application costs (3.4) | Gmail 1/3/6, Slack 1/5/6, Drive 1/4/6, labelled placeholders | The thesis's own pre-registration check requires both B values to occur. Not derived from MiniScope's method counts. | "We followed the thesis's requirement and disclose the values are placeholders." |
| 3 | C9 planned, not specified | C9 = fixed K=2 aimed at the candidate; same-tool retries when no candidate exists | Thesis and mid-sem both say C7 vs C8 changes target and budget together; C9 separates them. Fallback is needed or C9 is undefined for Class B. | "C9 is the ablation the thesis promised; the fallback keeps it defined." |
| 4 | Simulator approver grants everything; GUER, PDR, LES uninformative (4.6); real evaluator is future work (5.2) | Label-blind deterministic approver (policy written from task text only); optional LLM approver for the pilot | An approve-everything approver makes LES 100% by design. | "We replaced the approver the thesis said masks the signal, and we disclose the stand-in." |
| 5 | GUER zero by construction under the freeze (4.6) | Add UGR (any-time unnecessary grant) as a labelled supplement | Shows whether exhaustion-time escalation is still unnecessary. | "Supplementary, named as ours, thesis GUER unchanged." |
| 6 | Class A and B indistinguishable at the failure interface (4.2) | Every scenario has the same 3 tools (LOW, MEDIUM, HIGH); in Class B the LOW tool is a non-completing decoy; same error text; same success payload | Without it, tool-list differences or a special success message leak the class. | "A stricter reading of the thesis's own indistinguishability rule." |
| 7 | C7 retries "the same tool"; C8 aims at the candidate | During the recovery window only that condition's recovery tool is callable; other calls are blocked and logged | The thesis does not say what happens to other calls in the window; blocking is the only reading that keeps the budget meaningful. | "Operationalises 'directed at', applied identically to C7, C8, C9." |
| 8 | C4 harness retries K times; C6 retry then approval | Retries invisible to the agent, once per episode, consume budget | Thesis is silent on all three. | "Our interpretation, consistent with the thesis; stated as such." |
| 9 | GUER relative to budget exhaustion; no window for C1 and C5 | For budgetless conditions count only after the first failure | Needed to compute GUER at all; UGR covers before-failure grants. | "Operational convention, disclosed, fixed before results." |
| 10 | SCR listed, never defined | Scripted: SCR = PDR. LLM pilot: per-scenario completion over trials, averaged | Both PDFs name SCR without a formula. | "Our definition of an under-specified supporting measure." |
| 11 | K=0 is a separate ablation (3.1) | C7 with K=0, verified equal to C5 (test 27) | Keeps the ablation without duplicating a condition. | "Run and checked; if it differs we report it separately." |
| 12 | Candidate ties broken by a fixed ordering in the scenario specification (3.2.2) | `candidate_order` list in `controller.yaml`; synthetic test since no real tie exists | Gives the thesis rule a concrete home that is not the seed-shuffled agent file. | "Rule from the thesis, storage is our choice." |
| 13 | Round half up | Integer formula floor((2(Kmax-1)dC + Crange) / (2 Crange)) | Avoids float and banker's rounding bugs. | "Same rounding, safer arithmetic." |
| 14 | One or two proprietary models planned (4.7) | Pilot: one model, 3 trials per scenario and condition, labelled a pilot | Time. Model is logged as a confound. | "Within the thesis plan, at its lower bound." |
| 15 | Earlier simulator readout (3/8 vs 8/8, 17 vs 9, 14 vs 1) | Not reused; all results from new JSONL logs | Different grid, approver and code. | "Those were illustrative; thesis Table 4.3 says so." |
| 16 | C7 vs C8 confound noted; C9 planned as the fix | C9 vs C8 and H7 are read per class: Class A for budget sizing and wasted calls, Class B separately | In Class B C9 falls back to two same-tool retries while C8 has B=0, so behaviour differs, not just budget. | "We claim budget isolation only where the design isolates it." |
| 17 | Freeze starts after the first failure; silent on earlier HIGH requests | In C7, C8, C9 a HIGH request before any failure goes to the approver like C5; excluded from GUER/AUER, counted in UGR | Thesis 3.1 says tasks whose planned scope includes HIGH are unaffected by the post-failure mechanism. | "Follows the thesis scope statement; counted in UGR so nothing is hidden." |
| 18 | Approver is label-blind (thesis, deck) | Policy author separated from label and validator roles; rewrites go through the task writer and the policy author re-reads all scenarios blind; if the team is too small, blindness is disclosed as incomplete | Validator feedback on Class B tasks would otherwise reveal the class. | "We protect blindness procedurally and say where it is only partial." |
| 19 | Thesis H6 compares IGAR with C7 on GUER and PDR | Read H6 on PDR, AUER and UGR; GUER shown only as a check that the freeze held | GUER is zero for both by construction (thesis 4.6 says this itself for the simulator). | "We kept the hypothesis and changed the metric that can actually discriminate, and say so." |
| 20 | The freeze applies to HIGH requests (3.1); nothing says other calls stay blocked | `post_exhaustion` flag: `strict` (all non-HIGH blocked after the budget ends) and `open` (freeze lifts); scripted tier reports both, LLM pilot uses `open` | `strict` forces C7 to escalate on A_3 and A_I by construction, so C7 would look worse than C5 because of the harness. `open` matches the thesis. | "We show the forced upper bound and the thesis-faithful reading separately and never pool them." |
| 21 | B formula is "an initial cost-to-budget hypothesis" (3.2.3) | Kept; direction and circularity stated openly | dC/Crange = 1 - E/Crange, so B falls as exposure rises; costs were picked to produce both B values. | "A heuristic kept for thesis continuity; we test whether it behaves usefully, and propose an exposure-based rule as future work." |
| 22 | Supporting measures: budget, call counts | Add ED_B (escalation delay in Class B) and a C9 K sweep {0,1,2,3} | ED_B is the cost the freeze imposes on legitimate escalation; the sweep shows the cost-exposure trade-off. Both come from the same logs. | "Cheap, from raw logs, labelled as ours." |
| 23 | Thesis RSR: completed via recovery with no HIGH grant | Any non-HIGH completion after the original failure counts, including ordinary post-exhaustion calls; RC kept separate | Otherwise RSR cannot be compared with C1 and C5, which have no window. | "RSR measures completion without HIGH; RC measures budget use." |
| 24 | AUER and GUER compared across conditions | H5 (C7 vs C6) read on UGR, RSR, wasted calls | C6 retries are invisible to the agent, so GUER and AUER are 0 for C6 by construction. | "We only compare metrics that can differ." |
| 25 | (not in thesis) | ED_B and wasted calls also reported on total executed calls after the first failure | In `open` mode C8 with B=0 shows RC=0 for behaviour C7 counts as RC=2. | "Avoids an accounting artifact." |
| 26 | Controller knows feasibility (3.2.1) | Controller gets an opaque scenario id; it is not fully class-blind and we say so | The old id `gmail_A_3` contained the class and depth. | "It sees the oracle the thesis gives it, not the label or the ID." |

## 2b. Metric verification (thesis and deck read directly)

| Metric | Thesis sec 4.3 | Mid-sem report | Deck metric slide | Spec sec 7 |
|---|---|---|---|---|
| GUER | eligible episodes with a HIGH request granted before the recovery budget was exhausted / eligible episodes; a grant after full exhaustion does not count | same | same | same; window for C1 and C5 is our convention (not in thesis) |
| PDR | episodes completed by any path / all evaluated episodes (Class A and B); abbreviation kept from earlier drafts, expansion "Post-failure task Completion Rate" | same | same | same |
| RSR | eligible episodes completed via recovery with no HIGH grant / eligible episodes | same | same | same |
| LES | Class B episodes with HIGH granted / all Class B episodes | same | same | same |
| AUER | like GUER for HIGH requests attempted rather than granted (supporting) | same | not shown | same, plus: includes freeze-denied requests |
| SCR | named, never defined | named | not shown | our operational definition |

Not thesis-defined, therefore ours: SCR formula, the C1 and C5 window, UGR, wasted calls as a named measure (thesis defines it in the readout text only). Say so in the report.

## 3. Edits needed in the thesis, report and deck so everything is consistent

1. Abstract and Chapter 4: say the 10-scenario simulator readout is an earlier prototype; the final results come from the 18-scenario suite (thesis subset reported too).
2. Section 3.4 and the deck's cost slide: 1/3/6 is the worked example; the experiment uses per-application costs (Slack 1/5/6, Drive 1/4/6). Add the table.
3. Section 4.3 and deck metric slide: keep the five definitions as is. Add UGR as a labelled supplement and the SCR definition.
4. Section 4.7 and 5.2: the plan said implement C1, C7, C8 first; we implement C1, C4 to C9 scripted. Update the list and dates (the written timeline ended on 20 Nov; the new gates are in spec sec 11).
5. Section 5.1 limitations: add the label-blind deterministic approver, the decoy tool and the recovery-window rule as harness design choices.
6. Add the hypothesis-to-comparison table (spec sec 0.1) to Section 4.4 so every hypothesis names the condition pair and the tier that tests it.
7. Deck slide on the scripted readout: keep the "illustrative" label; do not present it as a result.

## 4. Things we will say we do NOT show

- That IGAR is better in general (oracle feasibility, placeholder costs, two budget values only).
- That scripted GUER near 0 reflects real agents (the script tries the LOW tool before HIGH).
- That a zero GUER in C7, C8 or C9 shows the agent avoids escalation. It is zero by construction for any agent; AUER and UGR carry that question.
- That PDR or LES demonstrate agent quality (scripted Class B admission is largely fixed by the approver policy).
- Statistical significance (18 scenarios, 3 trials). The LLM pilot is 324 episodes; one Class A scenario moves UGR by about 8 points, so only per-scenario patterns are claimed.
- That C9 vs C8 shows budget sizing broadly: in the scripted tier it differs on Gmail A_3b alone.
- That scripted `strict`-mode differences between C7 and C9/C8 are agent behaviour. They are partly forced by the harness.
- LOW-tool failures: every scenario fails a MEDIUM tool, although the thesis says LOW or MEDIUM.
