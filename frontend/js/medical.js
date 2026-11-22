/**
 * Medical Conditions Management Controller
 * Handles CRUD operations for patient medical conditions.
 */

let conditionsCache = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  await loadConditions();
  setupConditionForm();
});

async function loadConditions() {
  const container = document.getElementById("conditionsListContainer");
  const countBadge = document.getElementById("conditionCountBadge");
  const alertEl = document.getElementById("historyAlert");

  try {
    const list = await API.patients.getConditions();
    conditionsCache = list || [];
    countBadge.innerText = `${conditionsCache.length} Records`;

    if (conditionsCache.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          No medical conditions currently recorded.<br>
          Click <strong>Add Condition</strong> above to log any diagnosed illnesses.
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
          <thead>
            <tr style="text-align: left; border-bottom: 2px solid var(--border); color: var(--text-muted);">
              <th style="padding: 0.75rem;">Condition Name</th>
              <th style="padding: 0.75rem;">Diagnosed Date</th>
              <th style="padding: 0.75rem;">Status</th>
              <th style="padding: 0.75rem;">Notes</th>
              <th style="padding: 0.75rem; text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${conditionsCache.map(c => {
              const statusClass = c.status === 'active' ? 'badge-routine' : (c.status === 'managed' ? 'badge-selfcare' : 'badge-routine');
              const dateDisplay = c.diagnosed_date ? new Date(c.diagnosed_date).toLocaleDateString() : 'Not recorded';

              return `
                <tr style="border-bottom: 1px solid var(--border);">
                  <td style="padding: 0.85rem; font-weight: 700; color: var(--text-main);">
                    ${escapeHtml(c.condition_name)}
                  </td>
                  <td style="padding: 0.85rem; color: var(--text-muted);">${dateDisplay}</td>
                  <td style="padding: 0.85rem;">
                    <span class="badge ${statusClass}" style="text-transform: capitalize;">
                      ${escapeHtml(c.status)}
                    </span>
                  </td>
                  <td style="padding: 0.85rem; color: var(--text-muted); max-width: 280px;">
                    ${escapeHtml(c.notes || '—')}
                  </td>
                  <td style="padding: 0.85rem; text-align: right;">
                    <button class="btn btn-outline btn-sm" onclick="openEditConditionModal(${c.id})">Edit</button>
                    <button class="btn btn-outline btn-sm" style="color: var(--emergency);" onclick="handleDeleteCondition(${c.id})">Delete</button>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    alertEl.className = "alert alert-danger";
    alertEl.innerText = "Error loading conditions: " + err.message;
    alertEl.style.display = "block";
  }
}

function openAddConditionModal() {
  document.getElementById("condEditId").value = "";
  document.getElementById("modalTitle").innerText = "Add Medical Condition";
  document.getElementById("condName").value = "";
  document.getElementById("condDate").value = "";
  document.getElementById("condStatus").value = "active";
  document.getElementById("condNotes").value = "";
  document.getElementById("conditionModal").classList.add("active");
}

function openEditConditionModal(id) {
  const cond = conditionsCache.find(c => c.id === id);
  if (!cond) return;

  document.getElementById("condEditId").value = cond.id;
  document.getElementById("modalTitle").innerText = "Edit Medical Condition";
  document.getElementById("condName").value = cond.condition_name;
  document.getElementById("condDate").value = cond.diagnosed_date || "";
  document.getElementById("condStatus").value = cond.status;
  document.getElementById("condNotes").value = cond.notes || "";
  document.getElementById("conditionModal").classList.add("active");
}

function closeConditionModal() {
  document.getElementById("conditionModal").classList.remove("active");
}

function setupConditionForm() {
  const form = document.getElementById("conditionForm");
  const saveBtn = document.getElementById("btnSaveCondition");
  const alertEl = document.getElementById("historyAlert");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    saveBtn.disabled = true;
    saveBtn.innerText = "Saving...";

    const editId = document.getElementById("condEditId").value;
    const payload = {
      condition_name: document.getElementById("condName").value.trim(),
      diagnosed_date: document.getElementById("condDate").value || null,
      status: document.getElementById("condStatus").value,
      notes: document.getElementById("condNotes").value.trim() || null
    };

    try {
      if (editId) {
        await API.patients.updateCondition(parseInt(editId), payload);
      } else {
        await API.patients.createCondition(payload);
      }
      closeConditionModal();
      await loadConditions();
      alertEl.className = "alert alert-success";
      alertEl.innerText = "✓ Medical condition saved successfully.";
      alertEl.style.display = "block";
    } catch (err) {
      alert("Failed to save condition: " + err.message);
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save Condition";
    }
  });
}

async function handleDeleteCondition(id) {
  if (!confirm("Are you sure you want to remove this condition record?")) {
    return;
  }

  const alertEl = document.getElementById("historyAlert");
  try {
    await API.patients.deleteCondition(id);
    await loadConditions();
    alertEl.className = "alert alert-success";
    alertEl.innerText = "✓ Medical condition removed.";
    alertEl.style.display = "block";
  } catch (err) {
    alertEl.className = "alert alert-danger";
    alertEl.innerText = "Failed to remove condition: " + err.message;
    alertEl.style.display = "block";
  }
}
