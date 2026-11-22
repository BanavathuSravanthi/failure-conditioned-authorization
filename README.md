# Failure-Conditioned Authorization (FCA) with ILP-Guided Authorization Recovery (IGAR)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-156%20passed%2C%201%20skipped-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An academic research implementation and experimental testbed evaluating **Failure-Conditioned Authorization (FCA)** and **ILP-Guided Authorization Recovery (IGAR)** in autonomous LLM and scripted agent workflows.

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

### ILP-Guided Authorization Recovery (IGAR)
Rather than using a fixed recovery budget, IGAR sizes the recovery budget ($B$) dynamically based on the ILP-derived permission-cost gap between the failed tool's scope and the lowest-cost alternative candidate tool:
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

| Condition | Name | Architecture | Recovery Target | Matrix Coverage |
|---|---|---|---|---|
| **C1** | Vanilla | Baseline; no authorization gate; immediate execution of HIGH | None | Scripted & LLM |
| **C2** | Static least privilege | Static enforcement; HIGH always blocked | None | Optional (Scripted tier) |
| **C3** | Prompt-only | Natural-language prompt recovery instructions | Agent-chosen | Skipped in Scripted; requires LLM |
| **C4** | Harness Retry | Silent harness retry ($K=2$), then vanilla access | Same tool | Scripted tier |
| **C5** | Approval Gate | Progent-style approval gate; all HIGH requests reach approver | None | Scripted & LLM |
| **C6** | Retry + Approval | Harness retry ($K=2$), then C5 approval gate | Same tool | Scripted & LLM |
| **C7** | FCA Fixed-$K$ | Failure-conditioned freeze; $K=2$ attempts to failed tool | Failed tool | Scripted & LLM |
| **C8** | IGAR Cost-Gap | Candidate-directed recovery with budget $B \in \{0, 1, 2\}$ sized by cost gap | Candidate tool | Scripted & LLM |
| **C9** | Directed Recovery Ablation | Fixed budget $K=2$ directed to candidate (fallback to failed tool) | Candidate tool | Scripted & LLM |

> **Note on $K=0$ Calibration**: A configuration of C7 with recovery budget $K=0$ represents an immediate freeze-lift where non-HIGH calls are never blocked and HIGH requests pass directly to the approver. By mathematical specification, $K=0$ reproduces C5 behavior and serves as a calibration check (Test 27), rather than an independent condition.

### Post-Exhaustion Modes (Spec Section 3.2)
- **`strict`**: Harness-forced worst case. Once recovery budget reaches 0, all non-HIGH calls are blocked; only HIGH escalation requests may proceed to the Approver.
- **`open`**: Freeze lifts when budget reaches 0. Ordinary non-HIGH calls may execute without consuming budget; HIGH requests proceed to the Approver as in C5.
- **Evaluation Rule**: Strict and open modes are evaluated side-by-side and never pooled.

### Experimental Matrices
- **Scripted Experiment Matrix**: Evaluates conditions **C1, C4, C5, C6, C7, C8, C9** across all 18 scenarios in both `strict` and `open` modes ($18 \times 7 \times 2 = \mathbf{252}$ completed episodes). C2 is designated optional; C3 is skipped as natural-language prompt adherence requires an LLM.
- **Live LLM Pilot Matrix**: Evaluates conditions **C1, C5, C6, C7, C8, C9** exclusively under `open` post-exhaustion mode across all 18 scenarios and 3 independent trials ($18 \times 6 \times 3 = \mathbf{324}$ completed episodes). 100% matrix execution complete on `gemini-3.1-flash-lite` with zero mock fallback.

---

## 4. System Architecture & Five-File Scenario Isolation

To ensure scientific validity and eliminate data leakage, each scenario strictly adheres to a **five-file separation**:

```
scenarios/scenario_XXX/
├── scenario.yaml      # Agent-visible: task text, 3-tool inventory, generic error codes.
├── controller.yaml    # Controller-only: opaque ID, candidate_order, feasibility, costs.
├── approver.yaml      # Approver-only: approvable_high_tools allowlist, max scope.
├── environment.yaml   # Mock Executor-only: failure depth D, success attempts.
└── ground_truth.yaml  # Evaluator-only: scenario class (A/B), completing tools.
```

### Label-Blindness & Isolation Guarantees
- The **Agent** sees only `scenario.yaml` (task instructions and tool schemas). It never sees condition names, ground truth labels, scenario IDs, or policy configurations.
- The **Approver** loads strictly `approver.yaml` and is completely blind to `class`, `feasible`, `ground_truth`, failure depth, and scenario IDs. Verified via canary attribute interceptions.
- The **Controller** operates using opaque scenario IDs (`scenario_001` through `scenario_018`). Canonical IDs (e.g., `gmail_A_3`) exist solely in evaluator-side logs.

---

## 5. Repository Directory Structure

```text
failure-conditioned-authorization/
├── docs/
│   ├── FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md  # Immutable specification v0.3.9
│   └── FCA_IGAR_defence_notes_v0_3_9.md         # Immutable defence notes & thesis alignment
├── scenarios/
│   ├── scenario_001/ ... scenario_018/          # 18 five-file scenario directories
│   └── scenario_index.yaml                      # Scenario registry and metadata
├── src/
│   ├── __init__.py
│   ├── igar_budget.py         # Integer RHU, cost-gap formula, candidate selection
│   ├── approver.py            # Deterministic label-blind approver & policy loader
│   ├── controller.py          # FCA/IGAR controller state machine, routing, generic denial
│   ├── mock_environment.py    # Simulated tool environments (Gmail, Slack, Drive)
│   ├── scripted_agent.py      # Spec-compliant scripted agent (MEDIUM -> LOW -> HIGH)
│   ├── experiment_harness.py  # Automated experiment orchestration and event emission
│   ├── jsonl_validator.py     # Section 9 event stream validator
│   ├── analysis.py            # Authoritative metric aggregator (GUER, AUER, UGR, etc.)
│   ├── scenario_validator.py  # Five-file scenario consistency auditor & validator
│   ├── scenario_loader.py     # Scenario YAML loader with label isolation
│   ├── llm_provider.py        # LLM providers: Gemini, OpenAI, and MockLLMProvider
│   └── llm_agent.py           # Autonomous tool-calling LLM agent with prompt versioning
├── scripts/
│   ├── run_experiments.py          # Executes 252-episode scripted benchmark
│   ├── run_llm_pilot.py            # Orchestrates 324-episode live LLM pilot
│   ├── run_single_live_episode.py  # Single live LLM episode diagnostic runner
│   ├── generate_scenarios.py       # Scaffolds 18 five-file scenario folders
│   └── run_web_ui.py               # Research demonstration web interface runner
├── web/
│   ├── app.py                      # FastAPI demonstration backend
│   └── static/                     # Vanilla HTML/CSS/JS frontend dashboard
├── tests/
│   ├── __init__.py
│   ├── test_budget.py         # Budget math & integer RHU tests (24 tests)
│   ├── test_approver.py       # Approver policy & label blindness canary tests (40 tests)
│   ├── test_controller.py     # Controller routing & freeze lifecycle tests (13 tests)
│   ├── test_mandatory_29.py   # Mandatory 29 specification tests (M3 verification)
│   ├── test_harness.py        # Harness execution & validator tests
│   └── test_llm_agent.py      # Live provider, isolation canary, & tool-call tests
├── results/
│   ├── raw_logs/              # Raw JSONL logs from scripted runs (126 strict, 126 open)
│   ├── metrics_strict.csv     # Scripted metrics under strict post-exhaustion
│   ├── metrics_open.csv       # Scripted metrics under open post-exhaustion
│   ├── final_experiment_summary.md # Comprehensive Milestone 3 report
│   ├── reproducibility_report.md   # Scripted reproduction guidelines
│   └── llm_pilot/             # Milestone 4 Live LLM Pilot artifacts
│       ├── raw_logs/          # 324 validated LLM pilot episodes
│       ├── metrics.csv        # Interim LLM metrics
│       ├── llm_pilot_summary.md # Interim evaluation summary
│       ├── pilot_summary.md   # Execution overview
│       ├── comparison_scripted_vs_llm.md # Scripted vs. LLM analysis
│       └── reproducibility_report.md     # LLM pilot reproduction guidelines
├── .gitignore
└── README.md
```

---

## 6. Installation & Setup

### Prerequisites
- Python 3.11+ (tested on Python 3.13)
- Git

### Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/BanavathuSravanthi/failure-conditioned-authorization.git
cd failure-conditioned-authorization

# Create and activate virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install required dependencies
pip install pytest pandas pyyaml requests
```

---

## 7. Running the Test Suite & Experiments

### Run Unit and Integration Tests
Execute the full test suite (156 passing, 1 skipped):
```bash
pytest -v
```

### Run Scripted Experiments (Milestone 3)
Execute all 252 scripted episodes across `strict` and `open` modes:
```bash
python scripts/run_experiments.py
```

### Run Live LLM Pilot (Milestone 4)
Configure your provider API key as an environment variable (e.g. `GEMINI_API_KEY`) and run:
```bash
# Execute live LLM pilot on Gemini 3.1 Flash Lite:
python scripts/run_llm_pilot.py --provider gemini --model gemini-3.1-flash-lite --temperature 0.0

# Or execute a single diagnostic episode:
python scripts/run_single_live_episode.py --provider gemini --scenario gmail_A_1 --condition C7 --model gemini-3.1-flash-lite
```

---

## 8. Metrics & Evaluation Methodology

All reported metrics are computed directly from raw structured JSONL episode logs via `src/analysis.py` adhering to Spec Section 7:

- **PDR (Post-failure task Completion Rate)**: Fraction of evaluated episodes completed by any path ($\frac{\text{Completed Episodes}}{\text{Total Episodes}}$, across Class A and B; abbreviation retained from earlier drafts).
- **SCR (Scenario Completion Rate)**: Operational metric per Spec Section 7. In the scripted tier (one episode per scenario), SCR is reported identical to PDR. In the LLM pilot, SCR is defined as the macro-average of completed trials per scenario ($\frac{\text{completed trials}}{\text{total trials}}$, then the mean over scenarios). SCR equals PDR only when every scenario has completed an equal number of trials; in interim unbalanced pilot datasets, SCR and PDR can produce different values.
- **RSR (Recovery Success Rate)**: Fraction of eligible Class A episodes completed via recovery without any `HIGH` grant ($\frac{\text{Class A Completed without HIGH}}{\text{Class A Eligible Episodes}}$).
- **GUER (Granted Unnecessary Escalation Rate)**: Percentage of Class A episodes where a `HIGH` request was granted *before* recovery budget exhaustion ($= 0$ by construction under C7, C8, C9).
- **AUER (Attempted Unnecessary Escalation Rate)**: Percentage of Class A episodes where a `HIGH` request was attempted *before* budget exhaustion (measures agent escalation pressure).
- **UGR (Unnecessary Grant Rate)**: Percentage of Class A episodes where `HIGH` was granted at *any* time (measures whether exhaustion-time escalation was still unneeded).
- **LES (Legitimate Escalation Success rate)**: Percentage of Class B episodes where `HIGH` was granted ($\frac{\text{Class B Episodes with HIGH Granted}}{\text{All Class B Episodes}}$). Measures whether legitimate escalation was granted under infeasibility, without imposing an additional completion requirement.
- **RC (Recovery Calls)**: Total and mean count of executed recovery calls during the recovery window.

---

## 9. Current Implementation Status & Declared Research Limitations

### Implementation Status
- [x] **Milestone 1**: Red-phase test contracts (61 base tests established).
- [x] **Milestone 2 Stage 1**: IGAR budget math, integer RHU division, candidate selection algorithms (`src/igar_budget.py`).
- [x] **Milestone 2 Stage 2**: Deterministic label-blind Approver with fail-closed defaults and strict policy isolation (`src/approver.py`).
- [x] **Milestone 2 Stage 3**: FCA/IGAR Controller state machine, routing, and post-exhaustion modes (`src/controller.py`).
- [x] **Milestone 2 Stage 4**: Five-file scenario architecture across all 18 scenarios and consistency validator (`src/scenario_validator.py`).
- [x] **Milestone 2 Stage 5**: Mock tools (Gmail, Slack, Drive), scripted agent (`src/scripted_agent.py`), and experiment harness (`src/experiment_harness.py`).
- [x] **Milestone 3**: Full 29 mandatory specification verification tests passing; complete 252-episode scripted benchmark executed across `strict` and `open` modes.
- [x] **Milestone 4**: Full live LLM pilot completed on `gemini-3.1-flash-lite` (`post_exhaustion=open`). Exactly 324 / 324 planned episodes executed and validated; 100% ground-truth isolation verified.
- [x] **Test Suite**: 156 passed, 0 failed, 1 skipped (157 total).

### Declared Research Limitations
In accordance with academic rigor, the following 9 explicit limitations are declared:
1. **Oracle Feasibility Annotation**: Candidate tool feasibility in `controller.yaml` is provided as an oracle annotation; the controller does not dynamically infer runtime tool feasibility from tool outputs.
2. **Placeholder Cost Models**: Application permission costs (Gmail: 1/3/6, Slack: 1/5/6, Drive: 1/4/6) are calibrated experimental placeholders to isolate $B=1$ vs $B=2$ recovery dynamics, not empirical security risk measurements.
3. **Proposed Budget Hypothesis**: The linear cost-gap budget formula ($B \in \{0, 1, 2\}$) is a proposed heuristic; non-linear, multi-candidate, or learned sizing models are unmodeled.
4. **Simulated Mock Tools**: Tool execution is simulated in deterministic mock environments with injected failure depth $D$; real third-party service latency, network partitions, and asynchronous webhooks are not tested.
5. **Single LLM Evaluation**: Live LLM evaluation is conducted using Google Gemini (`gemini-3.1-flash-lite`); cross-model variance across OpenAI, Anthropic, or open-weights models remains future work.
6. **Non-Adversarial Failures**: Injected tool failures represent transient API or authentication defects; active adversarial prompt injections, malicious tool tampering, or jailbreaks are out of scope.
7. **LOW-Tool Failures Not Injected**: Failures are injected exclusively at MEDIUM-scope tools; failures of LOW-scoped tools during recovery are not injected in the benchmark suite.
8. **Deterministic Approver Stand-in**: The policy-based approver acts as a procedural stand-in for human security review, granting or denying based strictly on static allowlists under label-blind isolation.
9. **Direct Tool-Calling Loop**: The LLM agent interacts via a direct provider tool-calling loop rather than multi-agent orchestration frameworks (e.g., LangGraph, MCP, AutoGen), isolating authorization effects from framework-specific routing.

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
