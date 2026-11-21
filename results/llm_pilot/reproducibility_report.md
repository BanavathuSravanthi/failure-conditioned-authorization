# LLM Pilot Reproducibility Report

## 1. Execution Setup & Protocol
- **Agent Architecture**: Genuine LLM tool-calling agent ([src/llm_agent.py](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/src/llm_agent.py)).
- **Providers Supported**: Google Gemini API ([src/llm_provider.py](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/src/llm_provider.py)), OpenAI Chat Completions API, and Canary-auditing Mock provider.
- **Strict Data Isolation**: Verified by unit test suite and canary token interception ([tests/test_llm_agent.py](file:///c:/Users/Sravanthi/OneDrive/Desktop/RM_Project/tests/test_llm_agent.py)).
- **Post-Exhaustion Mode**: Strictly `open` mode for all LLM pilot runs (Spec Section 3.2).
- **Matrix Composition**: 18 scenarios $\times$ 6 conditions (`C1`, `C5`, `C6`, `C7`, `C8`, `C9`) $\times$ 3 independent trials = **324 planned episodes**.
- **Deterministic Seeding**: `seed = base_seed + trial * 1000` (Scenario base seeds: Gmail 1001–1006, Slack 2001–2006, Drive 3001–3006).

---

## 2. Reproduction Instructions

### Step A: Connect LLM Provider
Set your provider API key in your environment (without committing or sharing):
```bash
# For Google Gemini API:
export GEMINI_API_KEY="your-gemini-api-key"

# OR for OpenAI API:
export OPENAI_API_KEY="your-openai-api-key"
```

### Step B: Execute the Full 324-Episode Pilot
```bash
# Execute with auto-detected live provider:
python scripts/run_llm_pilot.py --temperature 0.0

# Or execute with explicit model:
python scripts/run_llm_pilot.py --provider gemini --model gemini-1.5-pro --temperature 0.0
```

### Step C: Execute Dry-Run Verification (Mock Provider)
```bash
python scripts/run_llm_pilot.py --mock --max-episodes 6
```

### Step D: Run Test Suite
```bash
pytest tests/test_llm_agent.py -v
```
