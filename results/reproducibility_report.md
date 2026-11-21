# FCA-IGAR Reproducibility Report

## 1. Execution Environment
- **Platform**: Windows / Python 3.11+ (Evaluated on Python 3.13.1)
- **Deterministic Seeding**: Assigned per scenario (1001-1006 for Gmail, 2001-2006 for Slack, 3001-3006 for Drive).
- **Five-File Architecture Isolation**: Verified across all 18 scenarios and loaders (`scenario.yaml`, `controller.yaml`, `approver.yaml`, `environment.yaml`, `ground_truth.yaml`).
- **Raw Event Logs**: Preserved in `results/raw_logs/strict/` (126 files) and `results/raw_logs/open/` (126 files).
- **Frozen Specifications**:
  - `docs/FCA_IGAR_freeze_spec_v0_3_9_CANDIDATE.md`: `7472FD5EF6AE769A29C3668AE09A4F887B63FBC5EB3A537938D54C3CE128831D`
  - `docs/FCA_IGAR_defence_notes_v0_3_9.md`: `143225AAA882480A656EBE690E45453FC7BBB3DA8EEBB28DD5B356CC2B1DFBAE`

---

## 2. Reproduction Commands

### Step A: Execute Complete Experimental Matrix
To rerun all 252 experimental episodes across both post-exhaustion modes (`strict` and `open`) and generate all metric tables:
```bash
python scripts/run_experiments.py
```
This script:
1. Executes 126 strict-mode runs and 126 open-mode runs across all 18 scenarios and 7 conditions (`C1`, `C4`, `C5`, `C6`, `C7`, `C8`, `C9`).
2. Validates every stream with `src/jsonl_validator.py` (0 errors).
3. Directly writes raw JSONL logs to `results/raw_logs/strict/` and `results/raw_logs/open/`.
4. Computes all Spec Section 7 metrics and exports `results/metrics_strict.csv`, `results/metrics_open.csv`, `results/metrics_summary_strict.json`, and `results/metrics_summary_open.json`.

### Step B: Run Complete Test Suite
To execute all 147 unit and integration tests (including all 29 mandatory specification tests):
```bash
pytest -v
```

### Step C: Verify Stream Validity
To independently validate all generated JSONL streams against the Spec Section 9 event schema:
```bash
python -c "
import glob
from src.jsonl_validator import validate_jsonl_stream

for f in glob.glob('results/raw_logs/*/*.jsonl'):
    with open(f, 'r', encoding='utf-8') as fp:
        validate_jsonl_stream(fp.read())
print('All 252 JSONL streams successfully validated against Section 9 schema.')
"
```

### Step D: Independently Recompute Metrics from Raw Logs
To independently recompute all metrics directly from the raw event streams:
```bash
python -c "
import glob
from src.analysis import parse_episode_events, EpisodeMetrics, MetricAggregator

def analyze_cohort(directory):
    files = glob.glob(directory + '/*.jsonl')
    episodes = [EpisodeMetrics(parse_episode_events(open(f, encoding='utf-8').read())) for f in files]
    by_cond = {}
    for ep in episodes:
        by_cond.setdefault(ep.condition, []).append(ep)
    for cond in sorted(by_cond.keys()):
        m = MetricAggregator(cond, by_cond[cond]).compute_metrics()
        print(f'{cond:4s} | PDR: {m[\"PDR\"]} | RSR: {m[\"RSR\"]} | GUER: {m[\"GUER\"]} | LES: {m[\"LES\"]} | RC: {m[\"total_recovery_calls\"]} | Blocked: {m[\"blocked_calls\"]}')

print('--- STRICT RECOMPUTATION ---')
analyze_cohort('results/raw_logs/strict')
print('\n--- OPEN RECOMPUTATION ---')
analyze_cohort('results/raw_logs/open')
"
```

---

## 3. Metric Calculations and Formulas
- **PDR (Primary Defect Resolution)**: $\frac{\text{Completed Episodes}}{\text{Total Episodes}}$
- **SCR (Sub-task Completion Rate)**: Evaluated identical to PDR for scripted tier ($SCR = PDR$).
- **RSR (Recovery Success Rate)**: $\frac{\text{Class A Completed without HIGH}}{\text{Class A Eligible Episodes}}$
- **GUER (Granted Unnecessary Escalation Ratio)**: $\frac{\text{Class A with HIGH Granted before Exhaustion}}{\text{Class A Eligible Episodes}}$
- **AUER (Attempted Unnecessary Escalation Ratio)**: $\frac{\text{Class A with HIGH Attempted before Exhaustion}}{\text{Class A Eligible Episodes}}$
- **UGR (Unguided Grant Ratio)**: $\frac{\text{Class A with HIGH Granted at Any Time}}{\text{Class A Eligible Episodes}}$
- **LES (Legitimate Escalation Success Rate)**: $\frac{\text{Class B Completed via HIGH}}{\text{Class B Eligible Episodes}}$ (Reported as `N/A` if denominator is 0).
- **RC (Total Recovery Calls)**: Sum of all executed recovery calls during the recovery window.
