# LLM Pilot Reproducibility Report

## 1. Execution Setup & Protocol
- **Agent Architecture**: Genuine LLM tool-calling agent ([src/llm_agent.py](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/src/llm_agent.py)).
- **Providers Supported**: Google Gemini API ([src/llm_provider.py](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/src/llm_provider.py)), OpenAI Chat Completions API, and Canary-auditing Mock provider.
- **Active Evaluated Model**: `gemini-3.1-flash-lite` (native tool/function calling).
- **Strict Data Isolation**: Verified by unit test suite and canary token interception ([tests/test_llm_agent.py](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/tests/test_llm_agent.py)).
- **Post-Exhaustion Mode**: Strictly `open` mode for all LLM pilot runs (Spec Section 3.2).
- **Matrix Composition**: 18 scenarios $\times$ 6 conditions (`C1`, `C5`, `C6`, `C7`, `C8`, `C9`) $\times$ 3 independent trials = **324 planned episodes**.
- **Current Progress**: 191 episodes completed; 133 remaining paused due to daily API rate limits.
- **Deterministic Seeding**: `seed = base_seed + trial * 1000` (Scenario base seeds: Gmail 1001–1006, Slack 2001–2006, Drive 3001–3006).

---

## 2. Reproduction Instructions

### Step A: Connect LLM Provider
Set your provider API key in your environment (without committing or sharing):
```bash
# For Google Gemini API (PowerShell):
$env:GEMINI_API_KEY="your-gemini-api-key"

# Linux / macOS:
export GEMINI_API_KEY="your-gemini-api-key"
```

### Step B: Execute / Resume the 324-Episode Pilot
The runner automatically checks `results/llm_pilot/raw_logs/` and skips already completed episodes without duplicating them:
```bash
# Execute with verified model:
python scripts/run_llm_pilot.py --provider gemini --model gemini-3.1-flash-lite --temperature 0.0
```

### Step C: Execute Single Episode Diagnostic
To test a single scenario-condition pair with full console reporting:
```bash
python scripts/run_single_live_episode.py --provider gemini --scenario gmail_A_1 --condition C7 --model gemini-3.1-flash-lite
```

### Step D: Execute Dry-Run Verification (Mock Provider)
```bash
python scripts/run_llm_pilot.py --mock --max-episodes 6
```

### Step E: Run Test Suite
```bash
pytest tests/test_llm_agent.py -v
```
