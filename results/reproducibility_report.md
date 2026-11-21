# Reproducibility Report

## Execution Environment
- **Python Version**: 3.11+
- **Deterministic Seeds**: Assigned per scenario (1001-1006 for Gmail, 2001-2006 for Slack, 3001-3006 for Drive).
- **Raw Log Storage**: `results/raw_logs/strict/` and `results/raw_logs/open/`.
- **Verification**: Every reported metric is derived strictly from raw JSONL event streams via `src/analysis.py`.

## Reproduction Commands
```bash
# 1. Run the entire experimental matrix and generate metrics
python scripts/run_experiments.py

# 2. Run the complete pytest test suite (110+ tests)
pytest -v
```
