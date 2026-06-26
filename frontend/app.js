const API_BASE = (() => {
  // Production: Railway (Flask serves frontend + API from same domain)
  if (window.location.host.includes("railway.app")) {
    return `${window.location.origin}/api`;
  }
  // Local development
  return "http://127.0.0.1:5000/api";
})();

const SUGGESTED_QUERIES = [
  "What alerts should I review first?",
  "Which zones are critical today?",
  "Lata Bai ki report kaisi hai?",
  "What is your work?",
  "Show me workers with no visits today.",
  "Which worker has flagged visits?",
  "Which zone needs urgent follow-up?",
  "Summarize active fake visit alerts.",
];

const state = {
  dashboard: null,
  zones: [],
  workers: [],
  expandedWorkerId: null,
  userMessageCount: 0,
};

const RAISE_QUERY_PROMPT = "Raise Query: I need a specific worker, alert, or zone review.";

function formatDate(value) {
  if (!value) {
    return "N/A";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function showErrorBanner(show) {
  document.getElementById("error-banner").classList.toggle("hidden", !show);
}

async function apiFetch(path, options = {}) {
  const config = {
    mode: "cors",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  };

  try {
    const response = await fetch(`${API_BASE}${path}`, config);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || `Request failed with ${response.status}`);
    }
    showErrorBanner(false);
    return response.json();
  } catch (error) {
    showErrorBanner(true);
    throw error;
  }
}

function renderDashboard(data) {
  state.dashboard = data;
  document.getElementById("kpi-workers").textContent = data.total_workers ?? 0;
  document.getElementById("kpi-visits").textContent = data.visits_today ?? 0;
  document.getElementById("kpi-flagged").textContent = data.flagged_visits ?? 0;
  document.getElementById("kpi-alerts").textContent = data.active_alerts ?? 0;
  document.getElementById("critical-zones").textContent = `${data.critical_zones ?? 0} critical zones`;
  document.getElementById("critical-zones-top").textContent = `${data.critical_zones ?? 0} critical zones`;
  renderAlertFeed(data.recent_alerts || []);
}

function renderAlertFeed(alerts) {
  const container = document.getElementById("alert-feed");
  container.innerHTML = "";

  if (!alerts.length) {
    container.innerHTML = "<p class='zone-empty'>No alerts available.</p>";
    return;
  }

  alerts.forEach((alert) => {
    const card = document.createElement("article");
    card.className = `alert-card ${alert.severity}`;
    card.innerHTML = `
      <div class="alert-card-header">
        <div>
          <strong>${alert.alert_type.replaceAll("_", " ")}</strong>
          <div>${alert.zone}</div>
        </div>
        <span class="alert-badge severity-${alert.severity}">${alert.severity}</span>
      </div>
      <p>${alert.message}</p>
      <div class="alert-meta">
        <span>${formatDate(alert.created_at)}</span>
        ${alert.is_resolved ? "<span>Resolved</span>" : `<button class="resolve-button" data-alert-id="${alert.id}">Resolve</button>`}
      </div>
    `;
    container.appendChild(card);
  });

  container.querySelectorAll(".resolve-button").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await apiFetch(`/alerts/${button.dataset.alertId}/resolve`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        await refreshAll();
      } catch (error) {
        button.disabled = false;
      }
    });
  });
}

function getZoneFilters() {
  return {
    risk: document.getElementById("zone-risk-filter").value,
    search: document.getElementById("zone-search").value.trim().toLowerCase(),
  };
}

function applyZoneFilters() {
  const { risk, search } = getZoneFilters();
  const filtered = state.zones.filter((zone) => {
    const matchesRisk = risk === "all" || (zone.risk_level || "normal") === risk;
    const matchesSearch = !search || zone.zone.toLowerCase().includes(search);
    return matchesRisk && matchesSearch;
  });
  renderZoneMap(filtered, risk, search);
}

function renderZoneMap(zones, risk = "all", search = "") {
  const container = document.getElementById("zone-map");
  const summary = document.getElementById("zone-filter-summary");
  container.innerHTML = "";

  const summaryParts = [];
  summaryParts.push(risk === "all" ? "all risks" : `${risk} risk`);
  if (search) {
    summaryParts.push(`matching "${search}"`);
  }
  summary.textContent = `Showing ${zones.length} zone${zones.length === 1 ? "" : "s"} for ${summaryParts.join(" ")}`;

  if (!zones.length) {
    container.innerHTML = "<div class='zone-empty'>No zones match this filter. Try a different risk level or search term.</div>";
    return;
  }

  zones.forEach((zone) => {
    const riskLevel = zone.risk_level || "normal";
    const card = document.createElement("article");
    card.className = "zone-card";
    card.innerHTML = `
      <div class="zone-card-top">
        <h3>${zone.zone}</h3>
        <div class="zone-status">
          <span class="zone-dot dot-${riskLevel}"></span>
          <span>${riskLevel.toUpperCase()}</span>
        </div>
      </div>
      <div class="zone-metrics">
        <div class="zone-metric">
          <span>Visits last 7d</span>
          <strong>${zone.visits_7d ?? zone.visits_last_7d ?? 0}</strong>
        </div>
        <div class="zone-metric">
          <span>Unvisited households</span>
          <strong>${zone.unvisited_households ?? 0}</strong>
        </div>
        <div class="zone-metric">
          <span>Visits last 14d</span>
          <strong>${zone.visits_14d ?? 0}</strong>
        </div>
        <div class="zone-metric">
          <span>Visits last 30d</span>
          <strong>${zone.visits_30d ?? 0}</strong>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderWorkers(workers) {
  state.workers = workers;
  const tbody = document.getElementById("worker-table-body");
  tbody.innerHTML = "";

  workers.forEach((worker) => {
    const row = document.createElement("tr");
    row.dataset.workerId = worker.id;
    row.innerHTML = `
      <td>${worker.name}</td>
      <td>${worker.zone}</td>
      <td>${worker.visits_today}</td>
      <td><span class="status-pill status-${worker.status}">${worker.status}</span></td>
      <td>${formatDate(worker.last_visit)}</td>
    `;
    row.addEventListener("click", () => toggleWorkerDetail(worker.id, row));
    tbody.appendChild(row);
  });
}

async function toggleWorkerDetail(workerId, row) {
  const nextSibling = row.nextElementSibling;
  if (nextSibling && nextSibling.classList.contains("visit-detail-row")) {
    nextSibling.remove();
    state.expandedWorkerId = null;
    return;
  }

  document.querySelectorAll(".visit-detail-row").forEach((item) => item.remove());
  const detail = await apiFetch(`/workers/${workerId}`);
  const template = document.getElementById("visit-row-template");
  const detailRow = template.content.firstElementChild.cloneNode(true);
  const content = detailRow.querySelector(".visit-detail-content");

  if (!detail.last_10_visits.length) {
    content.innerHTML = "<div class='visit-chip'>No recent visits found.</div>";
  } else {
    content.innerHTML = detail.last_10_visits.map((visit) => `
      <div class="visit-chip">
        <strong>${formatDate(visit.visit_date)}</strong><br>
        Status: ${visit.status} | GPS: ${visit.gps_lat}, ${visit.gps_lng}<br>
        ${visit.verification_reason || "No verification note."}
      </div>
    `).join("");
  }

  row.insertAdjacentElement("afterend", detailRow);
  state.expandedWorkerId = workerId;
}

async function loadDashboard() {
  const data = await apiFetch("/dashboard");
  renderDashboard(data);
}

async function loadAlerts() {
  const alerts = await apiFetch("/alerts?resolved=false");
  renderAlertFeed(alerts);
}

async function loadWorkers() {
  const workers = await apiFetch("/workers");
  renderWorkers(workers);
}

async function loadZones() {
  state.zones = await apiFetch("/zones");
  applyZoneFilters();
}

function addMessage(role, text) {
  const box = document.getElementById("chat-messages");
  const message = document.createElement("div");
  message.className = `message ${role}`;
  const label = role === "user" ? "You" : role === "system" ? "Guide" : "Supervisor Agent";
  message.innerHTML = `
    <span class="message-label">${label}</span>
    <span>${text}</span>
  `;
  box.appendChild(message);
  box.scrollTop = box.scrollHeight;
}

function renderSuggestionChips() {
  const chipList = document.getElementById("chat-chip-list");
  chipList.innerHTML = "";

  SUGGESTED_QUERIES.forEach((query) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chat-chip";
    chip.textContent = query;
    chip.addEventListener("click", () => {
      document.getElementById("chat-input").value = query;
      document.getElementById("chat-form").requestSubmit();
    });
    chipList.appendChild(chip);
  });

  const raiseChip = document.createElement("button");
  raiseChip.type = "button";
  raiseChip.className = "chat-chip chat-chip-strong";
  raiseChip.textContent = "Raise Query";
  raiseChip.addEventListener("click", () => {
    document.getElementById("chat-input").value = RAISE_QUERY_PROMPT;
    document.getElementById("chat-input").focus();
  });
  chipList.appendChild(raiseChip);
}

function maybePromptStructuredQuery() {
  if (state.userMessageCount === 5) {
    addMessage("system", "Need a structured query? Use the built-in prompts below, or tap Raise Query for a specific worker, alert, or zone request.");
  }
}

async function submitChatQuery(query, language) {
  addMessage("user", query);
  addMessage("ai", "Agent is thinking...");
  state.userMessageCount += 1;
  maybePromptStructuredQuery();

  try {
    const response = await apiFetch("/chat", {
      method: "POST",
      body: JSON.stringify({ query, language }),
    });
    const messages = document.getElementById("chat-messages");
    messages.lastElementChild.remove();
    addMessage("ai", response.response || "No response available.");
  } catch (error) {
    const messages = document.getElementById("chat-messages");
    messages.lastElementChild.remove();
    addMessage("ai", error.message);
  }
}

function initChat() {
  const panel = document.getElementById("chat-panel");
  document.getElementById("chat-toggle").addEventListener("click", () => {
    panel.classList.toggle("hidden");
  });
  document.getElementById("chat-close").addEventListener("click", () => {
    panel.classList.add("hidden");
  });

  renderSuggestionChips();
  addMessage("system", "Ask directly, or use the suggested questions for worker, alert, and zone insights.");

  document.getElementById("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("chat-input");
    const language = document.getElementById("chat-language").value;
    const query = input.value.trim();
    if (!query) {
      return;
    }

    input.value = "";
    await submitChatQuery(query, language);
  });
}

function initZoneFilters() {
  document.getElementById("zone-risk-filter").addEventListener("change", applyZoneFilters);
  document.getElementById("zone-search").addEventListener("input", applyZoneFilters);
}

async function refreshAll() {
  await Promise.all([loadDashboard(), loadAlerts(), loadWorkers(), loadZones()]);
}

function init() {
  document.getElementById("refresh-button").addEventListener("click", refreshAll);
  initChat();
  initZoneFilters();
  refreshAll().catch(() => {});
  setInterval(() => {
    refreshAll().catch(() => {});
  }, 30000);
}

document.addEventListener("DOMContentLoaded", init);
