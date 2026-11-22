/**
 * FCA-IGAR Research Console & Demonstration Frontend (Vanilla JS)
 * Zero external libraries or npm dependencies.
 */

// Global State Cache
let state = {
  scenarios: [],
  conditions: {},
  latestInteractiveRun: null,
  liveStatus: null,
};

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initSubTabs();
  loadSystemStatus();
  loadConditions();
  loadScenarios();
  loadResultsLLM();
  loadResultsScripted();
  loadHypotheses();
  setupEventListeners();
  loadLiveStatus();
  initLiveControls();
});

// ============================================================================
// Navigation & Tab Switching
// ============================================================================
function initTabs() {
  const tabButtons = document.querySelectorAll(".console-tabs .tab-btn");
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add("active");
      }
    });
  });
}

function initSubTabs() {
  const btnLLM = document.getElementById("btn-view-llm");
  const btnScripted = document.getElementById("btn-view-scripted");
  const btnHypotheses = document.getElementById("btn-view-hypotheses");

  const secLLM = document.getElementById("section-results-llm");
  const secScripted = document.getElementById("section-results-scripted");
  const secHypotheses = document.getElementById("section-results-hypotheses");

  function resetSubTabs() {
    [btnLLM, btnScripted, btnHypotheses].forEach(b => b.classList.remove("active"));
    [secLLM, secScripted, secHypotheses].forEach(s => (s.style.display = "none"));
  }

  btnLLM.addEventListener("click", () => {
    resetSubTabs();
    btnLLM.classList.add("active");
    secLLM.style.display = "block";
  });

  btnScripted.addEventListener("click", () => {
    resetSubTabs();
    btnScripted.classList.add("active");
    secScripted.style.display = "block";
  });

  btnHypotheses.addEventListener("click", () => {
    resetSubTabs();
    btnHypotheses.classList.add("active");
    secHypotheses.style.display = "block";
  });
}

// ============================================================================
// API Loaders
// ============================================================================
async function loadSystemStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("Failed to fetch system status");
    const data = await res.json();

    const indicator = document.getElementById("system-status-indicator");
    const statusText = document.getElementById("status-text");

    if (data.status === "PASS") {
      indicator.innerHTML = `<span class="status-dot" style="background-color: #2da44e;"></span><span>Invariants Verified (v0.3.9)</span>`;
    } else {
      indicator.innerHTML = `<span class="status-dot" style="background-color: #d9381e;"></span><span>Integrity Warning</span>`;
    }

    document.getElementById("stat-spec-hash").textContent = data.freeze_spec_hash ? `${data.freeze_spec_hash.substring(0, 16)}...` : "Missing";
    document.getElementById("stat-spec-status").textContent = data.freeze_spec_valid ? "✓ Hash Invariant Matched" : "✗ Hash Mismatch";

    document.getElementById("stat-defence-hash").textContent = data.defence_notes_hash ? `${data.defence_notes_hash.substring(0, 16)}...` : "Missing";
    document.getElementById("stat-defence-status").textContent = data.defence_notes_valid ? "✓ Hash Invariant Matched" : "✗ Hash Mismatch";

    document.getElementById("stat-dataset-count").textContent = `${data.llm_pilot_episodes} Episodes`;
    document.getElementById("stat-dataset-status").textContent = data.dataset_checksums_valid ? "✓ 324 SHA-256 Hashes Verified" : "✗ Checksum Mismatch";
  } catch (err) {
    console.error("Status load error:", err);
  }
}

async function loadConditions() {
  try {
    const res = await fetch("/api/conditions");
    if (!res.ok) throw new Error("Failed to load conditions");
    state.conditions = await res.json();

    const tbody = document.getElementById("conditions-tbody");
    tbody.innerHTML = "";

    Object.entries(state.conditions).forEach(([condKey, cond]) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono"><strong>${condKey}</strong></td>
        <td><strong>${cond.name}</strong><br><span style="font-size: 11.5px; color: var(--text-secondary);">${cond.description}</span></td>
        <td class="mono">${cond.recovery_target}</td>
        <td class="mono">${cond.budget}</td>
        <td>${cond.evaluated_scripted ? '<span class="badge badge-supported">Evaluated</span>' : '<span class="badge">N/A</span>'}</td>
        <td>${cond.evaluated_llm ? '<span class="badge badge-supported">Evaluated</span>' : '<span class="badge">N/A</span>'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Conditions load error:", err);
  }
}

async function loadScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    if (!res.ok) throw new Error("Failed to load scenarios");
    state.scenarios = await res.json();

    filterScenariosByApp();
    populateHistoricalScenarios();
    filterLiveScenariosByApp();
  } catch (err) {
    console.error("Scenarios load error:", err);
  }
}

function filterScenariosByApp() {
  const appFilter = document.getElementById("select-app").value;
  const selectScenario = document.getElementById("select-scenario");
  selectScenario.innerHTML = "";

  const filtered = state.scenarios.filter(s => (appFilter === "all" || s.app === appFilter));

  filtered.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.canonical_id;
    const subsetBadge = s.is_thesis_subset ? " [Thesis 10]" : "";
    opt.textContent = `${s.canonical_id} (Class ${s.class}, Depth ${s.depth})${subsetBadge}`;
    selectScenario.appendChild(opt);
  });

  if (filtered.length > 0) {
    updateScenarioDetails(filtered[0].canonical_id);
  }
}

function populateHistoricalScenarios() {
  const histScenario = document.getElementById("hist-scenario");
  histScenario.innerHTML = "";

  state.scenarios.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.canonical_id;
    opt.textContent = `${s.canonical_id} (${s.app.toUpperCase()}, Class ${s.class})`;
    histScenario.appendChild(opt);
  });
}

function updateScenarioDetails(canonicalId) {
  const scen = state.scenarios.find(s => s.canonical_id === canonicalId);
  if (!scen) return;

  document.getElementById("scenario-card-title").textContent = `Scenario: ${scen.canonical_id} (${scen.app.toUpperCase()})`;
  document.getElementById("scenario-card-task").textContent = `Task: "${scen.task}"`;

  const badgesDiv = document.getElementById("scenario-card-badges");
  const failedToolName = scen.failed_tool ? scen.failed_tool.name : "None";
  const failedScope = scen.failed_tool ? scen.failed_tool.scope : "N/A";
  const candidateToolName = scen.candidate_tool ? scen.candidate_tool.name : (scen.feasible ? "N/A" : "None (Class B)");
  const candidateScope = scen.candidate_tool ? scen.candidate_tool.scope : "N/A";

  badgesDiv.innerHTML = `
    <span class="badge ${scen.class === 'A' ? 'badge-supported' : 'badge-failure'}">Class ${scen.class}</span>
    <span class="badge badge-tool">Depth: ${scen.depth}</span>
    <span class="badge badge-failure">Injected Failure: ${failedToolName} [${failedScope}]</span>
    <span class="badge badge-recovery">Candidate: ${candidateToolName} [${candidateScope}]</span>
    <span class="badge badge-tool">ΔC = ${scen.cost_gap} (C_range = ${scen.cost_range})</span>
    <span class="badge badge-decision">IGAR Predicted B = ${scen.predicted_B}</span>
    ${scen.is_thesis_subset ? '<span class="badge badge-terminal">Thesis 10 Subset</span>' : ''}
  `;
}

// ============================================================================
// Interactive Demo Execution
// ============================================================================
function setupEventListeners() {
  const selectApp = document.getElementById("select-app");
  const selectScenario = document.getElementById("select-scenario");
  const btnRunDemo = document.getElementById("btn-run-demo");
  const btnViewTraceTab = document.getElementById("btn-view-trace-tab");

  selectApp.addEventListener("change", filterScenariosByApp);
  selectScenario.addEventListener("change", (e) => updateScenarioDetails(e.target.value));

  btnRunDemo.addEventListener("click", runInteractiveDemo);

  btnViewTraceTab.addEventListener("click", () => {
    const traceTabBtn = document.querySelector(`.tab-btn[data-tab="tab-trace"]`);
    if (traceTabBtn) traceTabBtn.click();
  });

  // Trace Source Switching
  const btnSourceInteractive = document.getElementById("btn-source-interactive");
  const btnSourceHistorical = document.getElementById("btn-source-historical");
  const histPanel = document.getElementById("historical-selector-panel");
  const histTier = document.getElementById("hist-tier");
  const histTrialGroup = document.getElementById("hist-trial-group");
  const histModeGroup = document.getElementById("hist-mode-group");
  const btnLoadHistorical = document.getElementById("btn-load-historical");

  btnSourceInteractive.addEventListener("click", () => {
    btnSourceInteractive.classList.add("active");
    btnSourceHistorical.classList.remove("active");
    histPanel.style.display = "none";
    if (state.latestInteractiveRun) {
      renderTimeline(state.latestInteractiveRun.timeline, `Interactive Run: ${state.latestInteractiveRun.scenario.canonical_id} (${state.latestInteractiveRun.condition})`);
    } else {
      document.getElementById("timeline-container").innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">No interactive demo has been run yet. Execute one in the "Run Experiment" tab.</p>`;
    }
  });

  btnSourceHistorical.addEventListener("click", () => {
    btnSourceHistorical.classList.add("active");
    btnSourceInteractive.classList.remove("active");
    histPanel.style.display = "block";
  });

  histTier.addEventListener("change", (e) => {
    if (e.target.value === "llm") {
      histTrialGroup.style.display = "block";
      histModeGroup.style.display = "none";
    } else {
      histTrialGroup.style.display = "none";
      histModeGroup.style.display = "block";
    }
  });

  btnLoadHistorical.addEventListener("click", loadHistoricalTrace);
}

async function runInteractiveDemo() {
  const btn = document.getElementById("btn-run-demo");
  const canonicalId = document.getElementById("select-scenario").value;
  const condition = document.getElementById("select-condition").value;
  const postExhaustion = document.getElementById("select-mode").value;

  btn.disabled = true;
  btn.innerHTML = `<span>⏳ Executing Episode in Memory...</span>`;

  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        canonical_id: canonicalId,
        condition: condition,
        post_exhaustion: postExhaustion,
        seed: 1234
      })
    });

    if (!res.ok) throw new Error("Interactive demo execution failed");
    const data = await res.json();
    state.latestInteractiveRun = data;

    // Show summary card
    const summaryCard = document.getElementById("demo-summary-card");
    summaryCard.style.display = "block";

    document.getElementById("demo-stat-terminal").textContent = data.summary.terminal_state;
    document.getElementById("demo-stat-rc").textContent = `${data.summary.recovery_calls_actual} calls`;
    document.getElementById("demo-stat-blocked").textContent = `${data.summary.blocked_calls} blocked`;
    document.getElementById("demo-stat-total").textContent = `${data.summary.total_calls} calls`;
    document.getElementById("demo-stat-grants").textContent = `${data.summary.high_grants} grants`;

    const badge = document.getElementById("demo-terminal-badge");
    badge.textContent = data.summary.terminal_state;
    if (data.summary.terminal_state.startsWith("COMPLETED")) {
      badge.className = "badge badge-terminal";
    } else {
      badge.className = "badge badge-failure";
    }

    // Render timeline in Tab 3
    renderTimeline(data.timeline, `Interactive Mock: ${data.scenario.canonical_id} (${data.condition}, mode=${data.post_exhaustion})`);
  } catch (err) {
    alert("Error executing demonstration: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>▶ Execute Interactive Episode</span>`;
  }
}

async function loadHistoricalTrace() {
  const btn = document.getElementById("btn-load-historical");
  const tier = document.getElementById("hist-tier").value;
  const condition = document.getElementById("hist-condition").value;
  const scenarioId = document.getElementById("hist-scenario").value;
  const trial = document.getElementById("hist-trial").value;
  const mode = document.getElementById("hist-mode").value;

  btn.disabled = true;
  btn.textContent = "Loading...";

  try {
    const url = `/api/historical_trace?tier=${tier}&condition=${condition}&scenario_id=${scenarioId}&trial=${trial}&mode=${mode}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load historical log file");
    const data = await res.json();

    const formattedEvents = data.events.map((evt, idx) => {
      const eventType = evt.event;
      const step = evt.step;
      const tool = evt.tool || "";
      const scope = evt.scope || "";

      let description = "";
      let badgeType = "info";

      if (eventType === "tool_call") {
        badgeType = evt.recovery_call ? "recovery" : "tool";
        description = evt.recovery_call ? `Recovery call on ${tool} (${scope}).` : `Initial call: ${tool} (${scope}).`;
      } else if (eventType === "tool_failure") {
        badgeType = "failure";
        description = `Tool failure on ${tool}. Recovery window activated.`;
      } else if (eventType === "blocked_attempt") {
        badgeType = "blocked";
        if (scope === "HIGH") {
          description = `Controller intercepted premature HIGH privilege request (${tool}). Approver NOT invoked.`;
        } else if (condition === "C8" || condition === "C9") {
          description = `Controller blocked same-tool retry (${tool} [${scope}]); IGAR restricts recovery to the designated candidate tool.`;
        } else {
          description = `Controller blocked non-permitted tool call (${tool} [${scope}]) during active recovery window.`;
        }
      } else if (eventType === "auth_decision") {
        badgeType = "decision";
        description = `Decision: ${evt.decision} (Reason: ${evt.reason || 'N/A'}).`;
      } else if (eventType === "episode_end") {
        badgeType = "terminal";
        description = `Episode terminal state: ${evt.terminal_state}.`;
      } else {
        description = `Event: ${eventType} on ${tool || 'controller'}.`;
      }

      return {
        seq: idx + 1,
        step: step,
        event: eventType,
        tool: tool,
        scope: scope,
        recovery_call: evt.recovery_call || false,
        recovery_budget_permitted: evt.recovery_budget_permitted,
        recovery_budget_remaining: evt.recovery_budget_remaining,
        high_request: evt.high_request || false,
        high_granted: evt.high_granted || false,
        terminal_state: evt.terminal_state,
        badge_type: badgeType,
        description: description,
      };
    });

    renderTimeline(formattedEvents, `Historical File: ${data.filename} (${tier.toUpperCase()})`);
  } catch (err) {
    alert("Historical log error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Load Historical Log";
  }
}

function renderTimeline(events, title) {
  const container = document.getElementById("timeline-container");
  document.getElementById("timeline-title").textContent = title;
  document.getElementById("timeline-subtitle").textContent = `${events.length} Events Recorded`;

  if (!events || events.length === 0) {
    container.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">No events recorded in this episode.</p>`;
    return;
  }

  container.innerHTML = "";

  events.forEach(evt => {
    const item = document.createElement("div");
    item.className = "timeline-item";

    let badgeClass = "badge-tool";
    if (evt.badge_type === "failure") badgeClass = "badge-failure";
    else if (evt.badge_type === "blocked") badgeClass = "badge-blocked";
    else if (evt.badge_type === "recovery") badgeClass = "badge-recovery";
    else if (evt.badge_type === "decision") badgeClass = "badge-decision";
    else if (evt.badge_type === "terminal") badgeClass = "badge-terminal";

    const budgetRemaining = evt.recovery_budget_remaining !== null && evt.recovery_budget_remaining !== undefined ? evt.recovery_budget_remaining : "N/A";
    const budgetPermitted = evt.recovery_budget_permitted !== null && evt.recovery_budget_permitted !== undefined ? evt.recovery_budget_permitted : "N/A";

    let budgetDisplay = `Budget: ${budgetRemaining} / ${budgetPermitted} remaining`;
    if (budgetRemaining !== "N/A" && budgetPermitted !== "N/A") {
      if (evt.event === "tool_call" && evt.recovery_call) {
        budgetDisplay = `Budget at entry: ${budgetRemaining} / ${budgetPermitted} (consumed by call)`;
      } else if (evt.event === "episode_end") {
        budgetDisplay = `Final Budget: ${budgetRemaining} / ${budgetPermitted} remaining`;
      }
    }

    item.innerHTML = `
      <div class="timeline-marker ${evt.badge_type === 'blocked' || evt.badge_type === 'failure' ? 'active' : ''}"></div>
      <div class="timeline-card">
        <div class="timeline-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="timeline-step">Step ${evt.step}</span>
            <span class="badge ${badgeClass}">${evt.event}</span>
            ${evt.tool ? `<span class="badge badge-tool mono">${evt.tool} [${evt.scope || 'N/A'}]</span>` : ''}
          </div>
          ${evt.terminal_state ? `<span class="badge badge-terminal">${evt.terminal_state}</span>` : ''}
        </div>
        <div class="timeline-body">${evt.description}</div>
        <div class="timeline-meta">
          <span>${budgetDisplay}</span>
          <span>HIGH Request: ${evt.high_request ? 'YES' : 'NO'}</span>
          <span>HIGH Granted: ${evt.high_granted ? 'YES' : 'NO'}</span>
        </div>
      </div>
    `;
    container.appendChild(item);
  });
}

// ============================================================================
// Results & Hypotheses Renderers
// ============================================================================
async function loadResultsLLM() {
  try {
    const res = await fetch("/api/results/llm");
    if (!res.ok) throw new Error("Failed to load LLM results");
    const data = await res.json();

    const tbody = document.getElementById("tbody-llm-metrics");
    tbody.innerHTML = "";

    const conditionOrder = ["C1", "C5", "C6", "C7", "C8", "C9"];
    conditionOrder.forEach(c => {
      const m = data.by_condition[c];
      if (!m) return;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono"><strong>${c}</strong></td>
        <td class="mono">${m.total_episodes}</td>
        <td class="mono">${m.n_class_a}</td>
        <td class="mono">${m.n_class_b}</td>
        <td class="mono">${formatRate(m.PDR)}</td>
        <td class="mono">${formatRate(m.SCR)}</td>
        <td class="mono">${formatRate(m.RSR)}</td>
        <td class="mono" style="${m.GUER === 0 ? 'font-weight:700; color:#137333;' : ''}">${formatRate(m.GUER)}</td>
        <td class="mono">${formatRate(m.AUER)}</td>
        <td class="mono">${formatRate(m.UGR)}</td>
        <td class="mono" style="font-weight:700;">${formatRate(m.LES)}</td>
        <td class="mono">${typeof m.mean_recovery_calls === 'number' ? m.mean_recovery_calls.toFixed(2) : m.mean_recovery_calls}</td>
        <td class="mono">${m.blocked_calls}</td>
      `;
      tbody.appendChild(tr);
    });

    // Populate Per-Scenario Table
    const perScenTbody = document.getElementById("tbody-llm-per-scenario");
    perScenTbody.innerHTML = "";

    data.per_scenario.slice(0, 18).forEach(row => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono"><strong>${row.scenario_id}</strong></td>
        <td class="mono">${row.app}</td>
        <td><span class="badge ${row.class === 'A' ? 'badge-supported' : 'badge-failure'}">Class ${row.class}</span></td>
        <td class="mono">${row.depth}</td>
        <td class="mono"><strong>${row.condition}</strong></td>
        <td class="mono">${row.completed_trials}</td>
        <td class="mono">${row.total_trials}</td>
        <td class="mono">${row.RSR}</td>
        <td class="mono">${row.SCR}</td>
        <td class="mono">${row.mean_recovery_calls}</td>
        <td class="mono">${row.blocked_calls}</td>
      `;
      perScenTbody.appendChild(tr);
    });
  } catch (err) {
    console.error("LLM results error:", err);
  }
}

async function loadResultsScripted() {
  try {
    const res = await fetch("/api/results/scripted");
    if (!res.ok) throw new Error("Failed to load scripted results");
    const data = await res.json();

    const tbody = document.getElementById("tbody-scripted-metrics");
    tbody.innerHTML = "";

    const conditions = ["C1", "C4", "C5", "C6", "C7", "C8", "C9"];
    conditions.forEach(cond => {
      ["open", "strict"].forEach(mode => {
        const m = mode === "open" ? data.open_mode[cond] : data.strict_mode[cond];
        if (!m) return;

        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="mono"><strong>${cond}</strong></td>
          <td><span class="badge ${mode === 'open' ? 'badge-supported' : 'badge-blocked'}">${mode}</span></td>
          <td class="mono">${m.total_episodes}</td>
          <td class="mono">${formatRate(m.PDR)}</td>
          <td class="mono">${formatRate(m.SCR)}</td>
          <td class="mono">${formatRate(m.RSR)}</td>
          <td class="mono">${formatRate(m.GUER)}</td>
          <td class="mono">${formatRate(m.AUER)}</td>
          <td class="mono">${formatRate(m.UGR)}</td>
          <td class="mono">${formatRate(m.LES)}</td>
          <td class="mono">${m.total_recovery_calls}</td>
          <td class="mono">${typeof m.mean_recovery_calls === 'number' ? m.mean_recovery_calls.toFixed(2) : m.mean_recovery_calls}</td>
          <td class="mono">${m.blocked_calls}</td>
        `;
        tbody.appendChild(tr);
      });
    });
  } catch (err) {
    console.error("Scripted results error:", err);
  }
}

async function loadHypotheses() {
  try {
    const res = await fetch("/api/results/hypotheses");
    if (!res.ok) throw new Error("Failed to load hypotheses");
    const list = await res.json();

    const container = document.getElementById("hypotheses-container");
    container.innerHTML = "";

    list.forEach(h => {
      const card = document.createElement("div");
      card.className = "hypo-card";
      card.innerHTML = `
        <div class="hypo-header">
          <div>
            <div class="hypo-title">${h.id}: ${h.title}</div>
            <div class="hypo-meta">Comparison: ${h.comparison} • Required Metrics: ${h.metrics}</div>
          </div>
          <span class="badge ${h.badge_class}">${h.verdict}</span>
        </div>
        <div class="hypo-findings">
          <strong>Live LLM Pilot:</strong> ${h.llm_findings}
        </div>
        <div style="font-size: 11.5px; color: var(--text-secondary);">
          <strong>Scripted Tier Context:</strong> ${h.scripted_findings}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Hypotheses load error:", err);
  }
}

function formatRate(val) {
  if (val === null || val === undefined) return "N/A";
  if (typeof val === "number") return val.toFixed(4);
  return String(val);
}

// ============================================================================
// TAB 5: Live Agent Demonstration Logic (Supplementary)
// ============================================================================

const LIVE_MODELS = {
  gemini: [
    { id: "gemini-3.1-flash-lite", label: "gemini-3.1-flash-lite (Pilot Benchmark Model)" },
    { id: "gemini-2.5-flash", label: "gemini-2.5-flash" },
    { id: "gemini-1.5-flash", label: "gemini-1.5-flash" },
    { id: "gemini-1.5-pro", label: "gemini-1.5-pro" },
  ],
  openai: [
    { id: "gpt-4o-mini", label: "gpt-4o-mini (Default)" },
    { id: "gpt-4o", label: "gpt-4o" },
  ],
};

async function loadLiveStatus() {
  try {
    const res = await fetch("/api/live/status");
    if (!res.ok) throw new Error("Failed to load live status");
    const data = await res.json();
    state.liveStatus = data;

    const pillGemini = document.getElementById("status-pill-gemini");
    const pillOpenAI = document.getElementById("status-pill-openai");

    if (pillGemini) {
      if (data.gemini && data.gemini.available) {
        pillGemini.className = "status-pill status-pill-ok";
        pillGemini.textContent = "✓ Configured in Environment";
      } else {
        pillGemini.className = "status-pill status-pill-missing";
        pillGemini.textContent = "✗ Not Configured";
      }
    }

    if (pillOpenAI) {
      if (data.openai && data.openai.available) {
        pillOpenAI.className = "status-pill status-pill-ok";
        pillOpenAI.textContent = "✓ Configured in Environment";
      } else {
        pillOpenAI.className = "status-pill status-pill-missing";
        pillOpenAI.textContent = "✗ Not Configured";
      }
    }

    updateLiveModelOptions("gemini");
  } catch (err) {
    console.error("Live status load error:", err);
  }
}

function updateLiveModelOptions(provider) {
  const modelSelect = document.getElementById("live-select-model");
  if (!modelSelect) return;
  modelSelect.innerHTML = "";

  const list = LIVE_MODELS[provider] || [];
  list.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = m.label;
    modelSelect.appendChild(opt);
  });
}

function filterLiveScenariosByApp() {
  const appFilterEl = document.getElementById("live-select-app");
  const scenarioSelect = document.getElementById("live-select-scenario");
  if (!appFilterEl || !scenarioSelect) return;

  const appFilter = appFilterEl.value;
  scenarioSelect.innerHTML = "";

  const filtered = state.scenarios.filter(s => (appFilter === "all" || s.app === appFilter));

  filtered.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.canonical_id;
    const subsetBadge = s.is_thesis_subset ? " [Thesis 10]" : "";
    opt.textContent = `${s.canonical_id} (Class ${s.class}, Depth ${s.depth})${subsetBadge}`;
    scenarioSelect.appendChild(opt);
  });

  if (filtered.length > 0) {
    updateLiveScenarioPreview(filtered[0].canonical_id);
  }
}

function updateLiveScenarioPreview(canonicalId) {
  const previewBox = document.getElementById("live-scenario-preview");
  if (!previewBox) return;

  const scen = state.scenarios.find(s => s.canonical_id === canonicalId);
  if (!scen) {
    previewBox.innerHTML = "<em>Select a scenario to view parameters.</em>";
    return;
  }

  const failedToolName = scen.failed_tool ? scen.failed_tool.name : "N/A";
  const failedScope = scen.failed_tool ? scen.failed_tool.scope : "N/A";
  const candidateToolName = scen.candidate_tool ? scen.candidate_tool.name : (scen.feasible ? "N/A" : "None (Class B)");
  const candidateScope = scen.candidate_tool ? scen.candidate_tool.scope : "N/A";

  previewBox.innerHTML = `
    <div style="font-weight: 600; margin-bottom: 6px;">Task: ${scen.task}</div>
    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
      <span class="badge ${scen.class === 'A' ? 'badge-supported' : 'badge-failure'}">Class ${scen.class}</span>
      <span class="badge badge-tool">Depth: ${scen.depth}</span>
      <span class="badge badge-failure">Injected Failure: ${failedToolName} [${failedScope}]</span>
      <span class="badge badge-recovery">Candidate: ${candidateToolName} [${candidateScope}]</span>
      <span class="badge badge-tool">ΔC = ${scen.cost_gap} (C_range = ${scen.cost_range})</span>
      <span class="badge badge-decision">IGAR Predicted B = ${scen.predicted_B}</span>
      ${scen.is_thesis_subset ? '<span class="badge badge-terminal">Thesis 10 Subset</span>' : ''}
    </div>
  `;
}

function initLiveControls() {
  const providerSelect = document.getElementById("live-select-provider");
  const appSelect = document.getElementById("live-select-app");
  const scenarioSelect = document.getElementById("live-select-scenario");
  const confirmChk = document.getElementById("live-confirm-chk");
  const btnRunLive = document.getElementById("btn-run-live");

  if (providerSelect) {
    providerSelect.addEventListener("change", (e) => {
      updateLiveModelOptions(e.target.value);
    });
  }

  if (appSelect) {
    appSelect.addEventListener("change", filterLiveScenariosByApp);
  }

  if (scenarioSelect) {
    scenarioSelect.addEventListener("change", (e) => {
      updateLiveScenarioPreview(e.target.value);
    });
  }

  if (confirmChk && btnRunLive) {
    confirmChk.addEventListener("change", () => {
      btnRunLive.disabled = !confirmChk.checked;
    });

    btnRunLive.addEventListener("click", runLiveEpisode);
  }
}

async function runLiveEpisode() {
  const btn = document.getElementById("btn-run-live");
  const confirmChk = document.getElementById("live-confirm-chk");
  const errorBox = document.getElementById("live-error-box");
  const resultsContainer = document.getElementById("live-results-container");

  if (!confirmChk || !confirmChk.checked) {
    alert("Please check the confirmation box before executing a paid live API call.");
    return;
  }

  const provider = document.getElementById("live-select-provider").value;
  const model = document.getElementById("live-select-model").value;
  const canonicalId = document.getElementById("live-select-scenario").value;
  const condition = document.getElementById("live-select-condition").value;
  const postExhaustion = document.getElementById("live-select-mode").value;
  const temperature = parseFloat(document.getElementById("live-input-temp").value) || 0.0;
  const seed = parseInt(document.getElementById("live-input-seed").value) || 2001;

  btn.disabled = true;
  btn.innerHTML = `<span>⏳ Executing Live Episode via ${provider.toUpperCase()} API...</span>`;
  errorBox.style.display = "none";
  errorBox.innerHTML = "";
  resultsContainer.style.display = "none";

  try {
    const res = await fetch("/api/live/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: provider,
        model: model,
        canonical_id: canonicalId,
        condition: condition,
        post_exhaustion: postExhaustion,
        temperature: temperature,
        seed: seed,
        user_confirmed: true
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const detail = errData.detail || `HTTP Error ${res.status}: ${res.statusText}`;
      throw new Error(detail);
    }

    const data = await res.json();
    displayLiveResults(data);
  } catch (err) {
    errorBox.style.display = "block";
    errorBox.innerHTML = `
      <strong>Live Execution Blocked / Failed:</strong> ${err.message}<br>
      <span style="font-size: 11.5px; margin-top: 4px; display: inline-block;">
        Safety Note: Live runs fail closed per research safety protocol. Live runs are NEVER silently replaced with mock data.
      </span>
    `;
  } finally {
    btn.disabled = !confirmChk.checked;
    btn.innerHTML = `<span>⚡ Execute Live LLM Episode</span>`;
  }
}

function displayLiveResults(data) {
  const resultsContainer = document.getElementById("live-results-container");
  resultsContainer.style.display = "block";

  // Telemetry
  document.getElementById("live-metric-model").textContent = `${data.provider.toUpperCase()} (${data.model})`;
  document.getElementById("live-metric-latency").textContent = `${data.latency_ms} ms`;
  document.getElementById("live-metric-prompt-tokens").textContent = data.tokens.prompt;
  document.getElementById("live-metric-completion-tokens").textContent = data.tokens.completion;
  document.getElementById("live-metric-total-tokens").textContent = data.tokens.total;
  document.getElementById("live-metric-cost").textContent = `$${data.estimated_cost_usd.toFixed(6)} USD`;

  // Summary counts
  const terminalVal = document.getElementById("live-stat-terminal");
  terminalVal.textContent = data.summary.terminal_state;
  if (data.summary.terminal_state.startsWith("COMPLETED")) {
    terminalVal.className = "stat-value badge badge-terminal";
  } else {
    terminalVal.className = "stat-value badge badge-failure";
  }

  document.getElementById("live-stat-rc").textContent = `${data.summary.recovery_calls_actual} calls`;
  document.getElementById("live-stat-blocked").textContent = `${data.summary.blocked_calls} blocked`;
  document.getElementById("live-stat-total").textContent = `${data.summary.total_calls} calls`;
  document.getElementById("live-stat-grants").textContent = `${data.summary.high_requests} / ${data.summary.high_grants}`;

  // IGAR parameters callout
  const igarDetails = document.getElementById("live-igar-details");
  const failedName = data.scenario.failed_tool ? `${data.scenario.failed_tool.name} [${data.scenario.failed_tool.scope}]` : "N/A";
  const candName = data.scenario.candidate_tool ? `${data.scenario.candidate_tool.name} [${data.scenario.candidate_tool.scope}]` : "None (Class B)";

  igarDetails.innerHTML = `
    <strong>IGAR Controller Parameters & Budget Allocation:</strong><br>
    • Scenario: <span class="mono">${data.scenario.canonical_id}</span> (App: ${data.scenario.app.toUpperCase()}, Class: ${data.scenario.class})<br>
    • Injected Failure: <span class="mono">${failedName}</span> &nbsp;→&nbsp; Designated Candidate: <span class="mono">${candName}</span><br>
    • Cost Hierarchy: C_range = ${data.scenario.cost_range}, ΔC = ${data.scenario.cost_gap} &nbsp;→&nbsp; <strong>Allocated Budget B = ${data.scenario.predicted_B}</strong><br>
    • Feasible Recovery Path: <strong>${data.scenario.feasible ? 'YES (Class A)' : 'NO (Class B: B=0 bypasses wasted calls)'}</strong>
  `;

  // Visual Timeline
  renderLiveTimeline(data.timeline, data.scenario.canonical_id, data.condition);

  // Conversation history
  renderLiveConversation(data.conversation);
}

function renderLiveTimeline(events, canonicalId, condition) {
  const container = document.getElementById("live-timeline-container");
  const subtitle = document.getElementById("live-timeline-subtitle");
  subtitle.textContent = `${events.length} Sequential Events Recorded for ${canonicalId} (${condition})`;
  container.innerHTML = "";

  events.forEach(evt => {
    const item = document.createElement("div");
    item.className = "timeline-item";

    let badgeClass = "badge-tool";
    if (evt.badge_type === "failure") badgeClass = "badge-failure";
    else if (evt.badge_type === "blocked") badgeClass = "badge-blocked";
    else if (evt.badge_type === "recovery") badgeClass = "badge-recovery";
    else if (evt.badge_type === "decision") badgeClass = "badge-decision";
    else if (evt.badge_type === "terminal") badgeClass = "badge-terminal";

    const budgetRemaining = evt.recovery_budget_remaining !== null && evt.recovery_budget_remaining !== undefined ? evt.recovery_budget_remaining : "N/A";
    const budgetPermitted = evt.recovery_budget_permitted !== null && evt.recovery_budget_permitted !== undefined ? evt.recovery_budget_permitted : "N/A";

    let budgetDisplay = `Budget: ${budgetRemaining} / ${budgetPermitted} remaining`;
    if (budgetRemaining !== "N/A" && budgetPermitted !== "N/A") {
      if (evt.event === "tool_call" && evt.recovery_call) {
        budgetDisplay = `Budget at entry: ${budgetRemaining} / ${budgetPermitted} (consumed by call)`;
      } else if (evt.event === "episode_end") {
        budgetDisplay = `Final Budget: ${budgetRemaining} / ${budgetPermitted} remaining`;
      }
    }

    item.innerHTML = `
      <div class="timeline-marker ${evt.badge_type === 'blocked' || evt.badge_type === 'failure' ? 'active' : ''}"></div>
      <div class="timeline-card">
        <div class="timeline-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="timeline-step">Step ${evt.step}</span>
            <span class="badge ${badgeClass}">${evt.event}</span>
            ${evt.tool ? `<span class="badge badge-tool mono">${evt.tool} [${evt.scope || 'N/A'}]</span>` : ''}
          </div>
          ${evt.terminal_state ? `<span class="badge badge-terminal">${evt.terminal_state}</span>` : ''}
        </div>
        <div class="timeline-body">${evt.description}</div>
        <div class="timeline-meta">
          <span>${budgetDisplay}</span>
          <span>HIGH Request: ${evt.high_request ? 'YES' : 'NO'}</span>
          <span>HIGH Granted: ${evt.high_granted ? 'YES' : 'NO'}</span>
        </div>
      </div>
    `;
    container.appendChild(item);
  });
}

function renderLiveConversation(conversation) {
  const container = document.getElementById("live-conversation-container");
  container.innerHTML = "";

  if (!conversation || conversation.length === 0) {
    container.innerHTML = "<p style='color: var(--text-muted); font-size: 13px;'>No conversation turns recorded.</p>";
    return;
  }

  conversation.forEach((msg, idx) => {
    const box = document.createElement("div");
    box.className = "conversation-msg";

    let roleLabel = msg.role.toUpperCase();
    let bodyContent = "";

    if (msg.role === "user") {
      roleLabel = "USER (Task Prompt)";
      bodyContent = `<div>${msg.content}</div>`;
    } else if (msg.role === "assistant") {
      roleLabel = "ASSISTANT (LLM Action)";
      if (msg.tool_call) {
        bodyContent = `
          <div><strong>Requested Tool:</strong> <code class="mono">${msg.tool_call.name}</code></div>
          <div style="margin-top: 4px;"><strong>Arguments:</strong> <pre class="mono" style="font-size: 11px; background: #fff; padding: 6px; border: 1px solid var(--border-color); border-radius: 4px;">${JSON.stringify(msg.tool_call.arguments, null, 2)}</pre></div>
        `;
      } else {
        bodyContent = `<div>${msg.content || '<em>Model did not specify action</em>'}</div>`;
      }
    } else if (msg.role === "tool_response") {
      roleLabel = "ENVIRONMENT (Tool Result / Controller Feedback)";
      bodyContent = `<pre class="mono" style="font-size: 11px; background: #fff; padding: 6px; border: 1px solid var(--border-color); border-radius: 4px;">${JSON.stringify(msg.tool_response, null, 2)}</pre>`;
    }

    box.innerHTML = `
      <div class="conversation-role">${roleLabel}</div>
      ${bodyContent}
    `;
    container.appendChild(box);
  });
}
