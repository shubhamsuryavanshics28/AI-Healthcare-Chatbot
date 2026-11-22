/**
 * Symptom Assessment & Clinical Triage Controller
 * Handles interactive severity updates, submission to triage safety engine,
 * and rendering urgency tier results.
 */

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  setupSeveritySlider();
  setupTriageForm();
  await loadTriageHistory();
});

function setupSeveritySlider() {
  const slider = document.getElementById("severitySlider");
  const display = document.getElementById("severityDisplay");

  slider.addEventListener("input", (e) => {
    const val = parseInt(e.target.value);
    let label = "Mild";
    let badgeClass = "badge-selfcare";

    if (val <= 3) {
      label = "Mild Discomfort";
      badgeClass = "badge-selfcare";
    } else if (val <= 6) {
      label = "Moderate Pain / Discomfort";
      badgeClass = "badge-routine";
    } else if (val <= 8) {
      label = "Severe / Intense Symptoms";
      badgeClass = "badge-urgent";
    } else {
      label = "CRITICAL / Extremely Unbearable";
      badgeClass = "badge-emergency";
    }

    display.className = `severity-badge-indicator ${badgeClass}`;
    display.innerText = `Severity: ${val}/10 (${label})`;
  });
}

function setupTriageForm() {
  const form = document.getElementById("triageForm");
  const runBtn = document.getElementById("btnRunTriage");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    runBtn.disabled = true;
    runBtn.innerText = "Evaluating Clinical Urgency Rules...";

    const payload = {
      primary_symptom: document.getElementById("primarySymptom").value.trim(),
      duration: document.getElementById("duration").value.trim(),
      severity: parseInt(document.getElementById("severitySlider").value),
      frequency: document.getElementById("frequency").value,
      body_location: document.getElementById("bodyLocation").value.trim() || null,
      associated_symptoms: document.getElementById("associatedSymptoms").value.trim() || null,
      relevant_history: document.getElementById("relevantHistory").value.trim() || null
    };

    try {
      const assessment = await API.triage.assessSymptoms(payload);
      renderTriageResult(assessment);
      await loadTriageHistory();
    } catch (err) {
      alert("Failed to evaluate symptoms: " + err.message);
    } finally {
      runBtn.disabled = false;
      runBtn.innerText = "Run Triage Assessment →";
    }
  });
}

function renderTriageResult(assessment) {
  const placeholder = document.getElementById("triageResultPlaceholder");
  const activeResult = document.getElementById("triageActiveResult");
  const res = assessment.triage_result;

  if (!res) return;

  placeholder.style.display = "none";
  activeResult.style.display = "block";

  const urgencyClass = res.urgency_level; // EMERGENCY | URGENT | ROUTINE | SELF_CARE

  let urgencyIcon = "🌿";
  let urgencyTitle = "Level 4: Self-Care & Supportive Monitoring";
  if (urgencyClass === "EMERGENCY") {
    urgencyIcon = "🚨";
    urgencyTitle = "Level 1: EMERGENCY MEDICAL CARE";
  } else if (urgencyClass === "URGENT") {
    urgencyIcon = "⚠️";
    urgencyTitle = "Level 2: Urgent Medical Attention Required";
  } else if (urgencyClass === "ROUTINE") {
    urgencyIcon = "🩺";
    urgencyTitle = "Level 3: Routine Medical Consultation Recommended";
  }

  let emergencyActionsHtml = "";
  if (res.emergency_flag || urgencyClass === "EMERGENCY") {
    emergencyActionsHtml = `
      <div style="background: #fee2e2; border: 1px solid #f87171; border-radius: var(--radius-md); padding: 1rem; margin-top: 1rem;">
        <div style="font-weight: 800; color: #991b1b; margin-bottom: 0.5rem;">
          🚨 IMMEDIATE ACTION REQUIRED
        </div>
        <div style="color: #7f1d1d; font-size: 0.9rem; margin-bottom: 0.75rem;">
          Do not wait or drive yourself. Immediately contact emergency dispatch services:
        </div>
        <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
          <a href="tel:112" class="btn btn-danger btn-sm">📞 Call National Emergency 112</a>
          <a href="tel:102" class="btn btn-outline btn-sm" style="color: #991b1b; border-color: #991b1b;">
            🚑 Call Ambulance 102 / 108
          </a>
        </div>
      </div>
    `;
  }

  activeResult.innerHTML = `
    <div class="triage-card ${urgencyClass}">
      <div class="triage-header-badge">
        ${urgencyIcon} ${urgencyTitle}
      </div>

      <div style="margin-bottom: 1rem;">
        <strong style="color: var(--text-main); font-size: 0.95rem;">Recommended Timeframe:</strong>
        <div style="font-size: 1.05rem; font-weight: 700; color: var(--text-main); margin-top: 0.2rem;">
          ⏱️ ${escapeHtml(res.recommended_timeframe)}
        </div>
      </div>

      <div style="margin-bottom: 1rem;">
        <strong style="color: var(--text-main); font-size: 0.95rem;">Actionable Clinical Guidance:</strong>
        <p style="font-size: 0.925rem; line-height: 1.5; color: var(--text-main); margin-top: 0.25rem;">
          ${escapeHtml(res.guidance)}
        </p>
      </div>

      <div style="background: rgba(255, 255, 255, 0.7); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.85rem; margin-bottom: 1rem;">
        <strong style="font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase;">Clinical Rationale:</strong>
        <p style="font-size: 0.875rem; color: var(--text-main); margin-top: 0.2rem;">
          ${escapeHtml(res.rationale)}
        </p>
      </div>

      ${emergencyActionsHtml}

      <div style="margin-top: 1.25rem; padding-top: 0.75rem; border-top: 1px solid rgba(0,0,0,0.1); font-size: 0.78rem; color: var(--text-muted); line-height: 1.4;">
        ⚠️ <em>${escapeHtml(res.disclaimer)}</em>
      </div>
    </div>
  `;
}

async function loadTriageHistory() {
  const container = document.getElementById("triageHistoryContainer");
  const countBadge = document.getElementById("historyCountBadge");

  try {
    const list = await API.triage.getHistory();
    countBadge.innerText = `${list ? list.length : 0} Records`;

    if (!list || list.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
          No past triage assessments recorded. Run an assessment above to log results.
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
          <thead>
            <tr style="text-align: left; border-bottom: 2px solid var(--border); color: var(--text-muted);">
              <th style="padding: 0.75rem;">Date & Time</th>
              <th style="padding: 0.75rem;">Primary Concern</th>
              <th style="padding: 0.75rem;">Duration</th>
              <th style="padding: 0.75rem;">Severity</th>
              <th style="padding: 0.75rem;">Urgency Tier</th>
              <th style="padding: 0.75rem; text-align: right;">View Guidance</th>
            </tr>
          </thead>
          <tbody>
            ${list.map(a => {
              const res = a.triage_result;
              const urgency = res ? res.urgency_level : "ROUTINE";
              const badgeClass = `badge-${urgency.toLowerCase().replace('_', '')}`;
              const dateStr = new Date(a.created_at).toLocaleString();

              return `
                <tr style="border-bottom: 1px solid var(--border);">
                  <td style="padding: 0.85rem; color: var(--text-muted); font-size: 0.85rem;">${dateStr}</td>
                  <td style="padding: 0.85rem; font-weight: 700; color: var(--text-main);">
                    ${escapeHtml(a.primary_symptom)}
                  </td>
                  <td style="padding: 0.85rem; color: var(--text-main);">${escapeHtml(a.duration)}</td>
                  <td style="padding: 0.85rem; font-weight: 600;">${a.severity}/10</td>
                  <td style="padding: 0.85rem;">
                    <span class="badge ${badgeClass}">${urgency}</span>
                  </td>
                  <td style="padding: 0.85rem; text-align: right;">
                    <button class="btn btn-outline btn-sm" onclick='showHistoricalAssessment(${JSON.stringify(a).replace(/'/g, "&apos;")})'>
                      Review Details
                    </button>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">Failed to load history: ${escapeHtml(err.message)}</div>`;
  }
}

function showHistoricalAssessment(assessmentObj) {
  renderTriageResult(assessmentObj);
  window.scrollTo({ top: 350, behavior: 'smooth' });
}
