/**
 * Dashboard Controller
 * Fetches patient dashboard statistics, recent triage evaluations, and conversations.
 */

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  const welcomeGreeting = document.getElementById("welcomeGreeting");
  if (welcomeGreeting) {
    welcomeGreeting.innerText = `Welcome back, ${user.full_name}`;
  }

  await loadDashboardData();
  await loadRecentAssessments();
  await loadRecentChats();
});

async function loadDashboardData() {
  try {
    const summary = await API.patients.getDashboard();
    document.getElementById("condCount").innerText = summary.conditions_count;
    document.getElementById("allCount").innerText = summary.allergies_count;
    document.getElementById("medCount").innerText = summary.medications_count;
    document.getElementById("assessCount").innerText = summary.recent_assessments_count;
  } catch (err) {
    console.error("Failed to load dashboard metrics", err);
  }
}

async function loadRecentAssessments() {
  const container = document.getElementById("recentAssessmentsList");
  if (!container) return;

  try {
    const history = await API.triage.getHistory();
    if (!history || history.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.9rem;">
          No previous symptom assessments recorded.<br>
          <a href="/triage" class="btn btn-outline btn-sm" style="margin-top: 0.75rem;">Run First Assessment</a>
        </div>
      `;
      return;
    }

    const items = history.slice(0, 4).map(a => {
      const urgency = a.triage_result ? a.triage_result.urgency_level : "ROUTINE";
      const badgeClass = `badge-${urgency.toLowerCase().replace('_', '')}`;
      const dateStr = new Date(a.created_at).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });

      return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid var(--border);">
          <div>
            <div style="font-weight: 700; font-size: 0.925rem; color: var(--text-main);">
              ${escapeHtml(a.primary_symptom)}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              Duration: ${escapeHtml(a.duration)} • Severity: ${a.severity}/10 • ${dateStr}
            </div>
          </div>
          <div>
            <span class="badge ${badgeClass}">${urgency}</span>
          </div>
        </div>
      `;
    }).join("");

    container.innerHTML = items;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">Failed to load assessments: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadRecentChats() {
  const container = document.getElementById("recentChatsList");
  if (!container) return;

  try {
    const chats = await API.chat.getHistory();
    if (!chats || chats.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.9rem;">
          No past AI consultations.<br>
          <a href="/chat" class="btn btn-primary btn-sm" style="margin-top: 0.75rem;">Start First Consultation</a>
        </div>
      `;
      return;
    }

    const items = chats.slice(0, 4).map(c => {
      const dateStr = new Date(c.updated_at).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });

      return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid var(--border);">
          <div style="max-width: 75%;">
            <a href="/chat?conv=${c.id}" style="font-weight: 700; font-size: 0.925rem; color: var(--primary-dark); text-decoration: none;">
              ${escapeHtml(c.title)}
            </a>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              ${c.message_count} messages • Last updated: ${dateStr}
            </div>
          </div>
          <a href="/chat?conv=${c.id}" class="btn btn-outline btn-sm">Resume &rarr;</a>
        </div>
      `;
    }).join("");

    container.innerHTML = items;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">Failed to load consultations: ${escapeHtml(err.message)}</div>`;
  }
}
