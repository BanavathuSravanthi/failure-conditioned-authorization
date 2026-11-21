# Failure-Conditioned Authorization (FCA) with Information-Guided Authorization Recovery (IGAR)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-77%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An academic research implementation and experimental testbed evaluating **Failure-Conditioned Authorization (FCA)** and **Information-Guided Authorization Recovery (IGAR)** in autonomous LLM and scripted agent workflows.

---

## 1. Project Overview & Research Objective

Modern autonomous tool-use agents frequently request high-privilege permissions (`HIGH`) prematurely when encountering transient or non-fatal task execution failures at lower privilege levels (`LOW` or `MEDIUM`).

This project implements and evaluates the **FCA-IGAR** framework to address privilege escalation:
- **Core Hypothesis**: By conditioning escalation authorization on explicit failure at lower scopes and enforcing a bounded recovery window before escalation requests are permitted to reach the human/policy approver, unnecessary privilege escalations can be prevented while legitimate escalations are preserved.
- **Key Safety Invariant**: FCA and IGAR act as filters/delays on escalation requests; they never grant permissions themselves. Every `HIGH` grant under FCA/IGAR would also have been granted under an unconditioned approval gate (C5).

---

## 2. Core Concepts: FCA & IGAR

### Failure-Conditioned Authorization (FCA)
When a tool call fails below `HIGH` privilege:
1. Escalation to `HIGH` tools is immediately frozen.
2. An active **recovery window** opens with an allotted recovery budget ($K$).
3. Any `HIGH` request attempted during this window is blocked at the Controller level without invoking the Approver, emitting a `blocked_attempt` event and an `auth_decision` denial with reason `freeze_block`.
4. Only designated recovery calls execute and decrement the budget.
5. Once the recovery budget reaches 0, the window closes.

### Information-Guided Authorization Recovery (IGAR)
Rather than using a fixed recovery budget, IGAR sizes the recovery budget ($B$) dynamically based on the information-theoretic cost gap between the failed tool's scope and the lowest-cost alternative candidate tool:
- **Cost Range**: $C_{\text{range}} = \text{cost}(\text{HIGH}) - \text{cost}(\text{LOW})$
- **Cost Gap**: $dC = \text{cost}(\text{failed\_scope}) - \text{cost}(\text{candidate\_scope})$
- **Budget Allocation Formula** (Spec Section 4):
  $$\text{If not feasible: } B = 0$$
  $$\text{Else: } B = \text{clip}\left(1 + \text{RHU}\left(\frac{(K_{\max} - 1) \cdot dC}{C_{\text{range}}}\right), 1, K_{\max}\right)$$
  where $\text{RHU}$ is integer-only Round-Half-Up division:
  $$\text{RHU}\left(\frac{\text{num}}{\text{den}}\right) = \left\lfloor \frac{2 \cdot \text{num} + \text{den}}{2 \cdot \text{den}} \right\rfloor$$
- **Candidate Selection**: Minimizes alternative execution cost. Ties are broken deterministically via `candidate_order`.

---

## 3. Experimental Conditions (C1–C9)

| Condition | Name | Architecture | Recovery Target |
|---|---|---|---|
| **C1** | Vanilla | No authorization gate; immediate execution of HIGH | None |
| **C2** | Re-prompt | Prompt retry upon failure | Same tool |
| **C3** | Self-reflection | Structured reflection step prior to escalation | Agent-chosen |
| **C4** | Harness Retry | Silent harness retry ($K=2$), then vanilla access | Same tool |
| **C5** | Approval Gate | Progent-style gate; all HIGH requests reach approver | None |
| **C6** | Retry + Approval | Harness retry ($K=2$), then C5 approval gate | Same tool |
| **C7** | FCA Fixed-$K$ | Failure-conditioned freeze; $K=2$ attempts to failed tool | Failed tool |
| **C8** | IGAR Cost-Gap | Candidate-directed recovery with budget $B \in \{0, 1, 2\}$ | Candidate tool |
| **C9** | Directed Recovery Ablation | Fixed budget $K=2$ directed to candidate (fallback to failed) | Candidate tool |

### Post-Exhaustion Modes (Spec Section 3.2)
- **`strict`**: Harness-forced worst case. Once recovery budget reaches 0, all non-HIGH calls are blocked; only HIGH escalation requests may proceed to the Approver.
- **`open`**: Freeze lifts when budget reaches 0. Ordinary non-HIGH calls may execute without consuming budget; HIGH requests proceed to the Approver as in C5.

---

## 4. System Architecture & Five-File Scenario Isolation

To ensure rigorous scientific validity and eliminate data leakage, each scenario strictly adheres to a **five-file separation**:

```
scenarios/scenario_XXX/
├── scenario.yaml      # Agent-visible: task text, 3-tool inventory, generic error codes.
├── controller.yaml    # Controller-only: opaque ID, candidate_order, feasibility, costs.
├── approver.yaml      # Approver-only: approvable_high_tools allowlist, max scope.
├── environment.yaml   # Mock Executor-only: failure depth D, success attempts.
└── ground_truth.yaml  # Evaluator-only: scenario class (A/B), completing tools.
```

### Label-Blindness Guarantees
- The **Agent** never sees condition names, ground truth labels, scenario IDs, or policy configurations.
- The **Approver** loads strictly `approver.yaml` and is completely blind to `class`, `feasible`, `ground_truth`, failure depth, and scenario IDs. Verified via canary attribute interceptions.
- The **Controller** operates using opaque scenario IDs (`scenario_001` through `scenario_018`). Canonical IDs (e.g., `gmail_A_3`) exist solely in evaluator-side logs.

---

## 5. Directory Structure

```text
failure-conditioned-authorization/
├── docs/
│   ├── FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md  # Immutable specification v0.3.9
│   └── FCA_IGAR_defence_notes_v0_3_9.md         # Immutable defence notes & thesis alignment
├── src/
│   ├── __init__.py
│   ├── igar_budget.py    # Integer RHU, cost-gap formula, candidate selection
│   ├── approver.py       # Deterministic label-blind approver & isolated policy loader
│   └── controller.py     # FCA/IGAR controller state machine, routing, and generic denial
├── tests/
│   ├── __init__.py
│   ├── test_budget.py     # Unit & property tests for budget calculations (24 tests)
│   ├── test_approver.py   # Unit & isolation canary tests for approver (40 tests)
│   └── test_controller.py # Routing, freeze, and lifecycle tests (13 tests)
├── .gitignore
└── README.md
```

---

## 6. Installation & Setup

### Prerequisites
- Python 3.11+
- Git

### Installation
Clone the repository and install test dependencies:
```bash
git clone https://github.com/Sravanthi/failure-conditioned-authorization.git
cd failure-conditioned-authorization

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install required testing libraries
pip install pytest pandas pyyaml
```

---

## 7. Running the Test Suite

Execute the full test suite with verbose output:
```bash
pytest -v
```

Run specific test modules:
```bash
# Budget math, integer RHU, and candidate selection tests:
pytest -v tests/test_budget.py

# Approver policy, label blindness, and fail-closed tests:
pytest -v tests/test_approver.py

# Controller routing, recovery window, and post-exhaustion tests:
pytest -v tests/test_controller.py
```

---

## 8. Metrics & Evaluation Methodology

All reported metrics are computed directly from raw structured JSONL episode logs:

- **GUER (Granted Unnecessary Escalation Rate)**: Percentage of Class A (feasible) episodes where a `HIGH` request was granted *before* recovery budget exhaustion ($= 0$ by construction in C7, C8, C9).
- **AUER (Attempted Unnecessary Escalation Rate)**: Percentage of Class A episodes where a `HIGH` request was attempted before exhaustion (signals agent escalation pressure).
- **UGR (Unnecessary Grant Rate)**: Class A episodes where `HIGH` was granted at *any* time (measures whether exhaustion-time escalation was still unneeded).
- **LES (Legitimate Escalation Success)**: Percentage of Class B (infeasible) episodes where `HIGH` was granted and the task completed.
- **RSR (Recovery Success Rate)**: Percentage of Class A episodes completed via recovery without any `HIGH` grant.
- **PDR (Post-failure Completion Rate)**: Total episodes completed across all paths.

---

## 9. Current Implementation Status & Declared Limitations

### Implementation Status
- [x] **Milestone 1**: Red-phase test contracts (61 base tests established).
- [x] **Milestone 2 Stage 1**: IGAR budget math, integer RHU division, candidate selection algorithms (`src/igar_budget.py`).
- [x] **Milestone 2 Stage 2**: Deterministic label-blind Approver with fail-closed defaults and strict policy isolation (`src/approver.py`).
- [x] **Milestone 2 Stage 3**: FCA/IGAR Controller state machine, routing, and post-exhaustion modes (`src/controller.py`).
- [ ] **Milestone 2 Stage 4**: Five-file scenario generation (18 scenarios) and consistency validator.
- [ ] **Milestone 2 Stage 5**: Mock tools (Gmail, Slack, Drive) and scripted agent.
- [ ] **Milestone 3**: Full 29 mandatory specification verification tests.

### Declared Research Limitations
1. **Mock Integrations Only**: Tools use deterministic mocks with simulated failure depth $D$; no real network or external services are accessed.
2. **Cost Model Approximations**: Application permission costs (Gmail: 1/3/6, Slack: 1/5/6, Drive: 1/4/6) are calibrated experimental placeholders to isolate $B=1$ vs $B=2$ recovery dynamics.
3. **Approver Stand-in**: The deterministic approver acts as a procedural stand-in for human security review under label-blind isolation.

---

## 10. Immutable Specification Hashes

To guarantee integrity across all development milestones, the specification documents in `docs/` are strictly immutable:

| Document | SHA-256 Hash |
|---|---|
| `docs/FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md` | `7472FD5EF6AE769A29C3668AE09A4F887B63FBC5EB3A537938D54C3CE128831D` |
| `docs/FCA_IGAR_defence_notes_v0_3_9.md` | `143225AAA882480A656EBE690E45453FC7BBB3DA8EEBB28DD5B356CC2B1DFBAE` |

---

## 11. License

This research codebase is licensed under the [MIT License](LICENSE).
