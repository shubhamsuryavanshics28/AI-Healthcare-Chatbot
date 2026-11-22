/**
 * Allergies & Current Medications Controller
 * Handles tab toggling and full CRUD operations for both allergies and medications.
 */

let allergiesCache = [];
let medsCache = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  await loadAllergies();
  await loadMedications();
  setupAllergyForm();
  setupMedForm();
});

function switchTab(tabName) {
  const secAllergies = document.getElementById("sectionAllergies");
  const secMeds = document.getElementById("sectionMeds");
  const btnAllergies = document.getElementById("tabBtnAllergies");
  const btnMeds = document.getElementById("tabBtnMeds");

  if (tabName === "allergies") {
    secAllergies.style.display = "block";
    secMeds.style.display = "none";
    btnAllergies.classList.add("active");
    btnMeds.classList.remove("active");
  } else {
    secAllergies.style.display = "none";
    secMeds.style.display = "block";
    btnAllergies.classList.remove("active");
    btnMeds.classList.add("active");
  }
}

// --- ALLERGIES ---
async function loadAllergies() {
  const container = document.getElementById("allergiesListContainer");
  const countEl = document.getElementById("allergyCount");

  try {
    const list = await API.patients.getAllergies();
    allergiesCache = list || [];
    countEl.innerText = allergiesCache.length;

    if (allergiesCache.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          No allergies currently documented.<br>
          Click <strong>Add Allergy</strong> above to record known drug, food, or environmental sensitivities.
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
          <thead>
            <tr style="text-align: left; border-bottom: 2px solid var(--border); color: var(--text-muted);">
              <th style="padding: 0.75rem;">Allergen</th>
              <th style="padding: 0.75rem;">Reaction</th>
              <th style="padding: 0.75rem;">Severity</th>
              <th style="padding: 0.75rem;">Notes</th>
              <th style="padding: 0.75rem; text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${allergiesCache.map(a => {
              const sevClass = a.severity === 'severe' ? 'badge-emergency' : (a.severity === 'moderate' ? 'badge-urgent' : 'badge-selfcare');
              return `
                <tr style="border-bottom: 1px solid var(--border);">
                  <td style="padding: 0.85rem; font-weight: 700; color: var(--text-main);">
                    ${escapeHtml(a.allergen)}
                  </td>
                  <td style="padding: 0.85rem; color: var(--text-main);">${escapeHtml(a.reaction)}</td>
                  <td style="padding: 0.85rem;">
                    <span class="badge ${sevClass}" style="text-transform: capitalize;">
                      ${escapeHtml(a.severity)}
                    </span>
                  </td>
                  <td style="padding: 0.85rem; color: var(--text-muted); max-width: 250px;">
                    ${escapeHtml(a.notes || '—')}
                  </td>
                  <td style="padding: 0.85rem; text-align: right;">
                    <button class="btn btn-outline btn-sm" onclick="openEditAllergyModal(${a.id})">Edit</button>
                    <button class="btn btn-outline btn-sm" style="color: var(--emergency);" onclick="handleDeleteAllergy(${a.id})">Delete</button>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">Error: ${escapeHtml(err.message)}</div>`;
  }
}

function openAddAllergyModal() {
  document.getElementById("allergyEditId").value = "";
  document.getElementById("allergyModalTitle").innerText = "Add Allergy Record";
  document.getElementById("allergen").value = "";
  document.getElementById("allergyReaction").value = "";
  document.getElementById("allergySeverity").value = "mild";
  document.getElementById("allergyNotes").value = "";
  document.getElementById("allergyModal").classList.add("active");
}

function openEditAllergyModal(id) {
  const a = allergiesCache.find(x => x.id === id);
  if (!a) return;

  document.getElementById("allergyEditId").value = a.id;
  document.getElementById("allergyModalTitle").innerText = "Edit Allergy Record";
  document.getElementById("allergen").value = a.allergen;
  document.getElementById("allergyReaction").value = a.reaction;
  document.getElementById("allergySeverity").value = a.severity;
  document.getElementById("allergyNotes").value = a.notes || "";
  document.getElementById("allergyModal").classList.add("active");
}

function closeAllergyModal() {
  document.getElementById("allergyModal").classList.remove("active");
}

function setupAllergyForm() {
  const form = document.getElementById("allergyForm");
  const saveBtn = document.getElementById("btnSaveAllergy");
  const alertEl = document.getElementById("recordsAlert");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    saveBtn.disabled = true;
    saveBtn.innerText = "Saving...";

    const editId = document.getElementById("allergyEditId").value;
    const payload = {
      allergen: document.getElementById("allergen").value.trim(),
      reaction: document.getElementById("allergyReaction").value.trim(),
      severity: document.getElementById("allergySeverity").value,
      notes: document.getElementById("allergyNotes").value.trim() || null
    };

    try {
      if (editId) {
        await API.patients.updateAllergy(parseInt(editId), payload);
      } else {
        await API.patients.createAllergy(payload);
      }
      closeAllergyModal();
      await loadAllergies();
      alertEl.className = "alert alert-success";
      alertEl.innerText = "✓ Allergy record updated successfully.";
      alertEl.style.display = "block";
    } catch (err) {
      alert("Failed to save allergy: " + err.message);
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save Allergy";
    }
  });
}

async function handleDeleteAllergy(id) {
  if (!confirm("Are you sure you want to remove this allergy record?")) return;
  try {
    await API.patients.deleteAllergy(id);
    await loadAllergies();
  } catch (err) {
    alert("Delete failed: " + err.message);
  }
}

// --- MEDICATIONS ---
async function loadMedications() {
  const container = document.getElementById("medicationsListContainer");
  const countEl = document.getElementById("medsCount");

  try {
    const list = await API.patients.getMedications();
    medsCache = list || [];
    countEl.innerText = medsCache.length;

    if (medsCache.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          No medications currently logged.<br>
          Click <strong>Add Medication</strong> above to record your current prescriptions.
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
          <thead>
            <tr style="text-align: left; border-bottom: 2px solid var(--border); color: var(--text-muted);">
              <th style="padding: 0.75rem;">Medicine Name</th>
              <th style="padding: 0.75rem;">Dosage & Frequency</th>
              <th style="padding: 0.75rem;">Status</th>
              <th style="padding: 0.75rem;">Notes</th>
              <th style="padding: 0.75rem; text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${medsCache.map(m => {
              const statusBadge = m.is_current ? '<span class="badge badge-selfcare">Current</span>' : '<span class="badge badge-routine">Completed</span>';
              return `
                <tr style="border-bottom: 1px solid var(--border);">
                  <td style="padding: 0.85rem; font-weight: 700; color: var(--primary-dark);">
                    ${escapeHtml(m.medication_name)}
                  </td>
                  <td style="padding: 0.85rem; color: var(--text-main);">
                    <strong>${escapeHtml(m.dosage)}</strong> • ${escapeHtml(m.frequency)}
                  </td>
                  <td style="padding: 0.85rem;">${statusBadge}</td>
                  <td style="padding: 0.85rem; color: var(--text-muted); max-width: 250px;">
                    ${escapeHtml(m.notes || '—')}
                  </td>
                  <td style="padding: 0.85rem; text-align: right;">
                    <button class="btn btn-outline btn-sm" onclick="openEditMedModal(${m.id})">Edit</button>
                    <button class="btn btn-outline btn-sm" style="color: var(--emergency);" onclick="handleDeleteMed(${m.id})">Delete</button>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">Error: ${escapeHtml(err.message)}</div>`;
  }
}

function openAddMedModal() {
  document.getElementById("medEditId").value = "";
  document.getElementById("medModalTitle").innerText = "Record Patient Medication";
  document.getElementById("medName").value = "";
  document.getElementById("medDosage").value = "";
  document.getElementById("medFrequency").value = "";
  document.getElementById("medStart").value = "";
  document.getElementById("medIsCurrent").value = "true";
  document.getElementById("medNotes").value = "";
  document.getElementById("medModal").classList.add("active");
}

function openEditMedModal(id) {
  const m = medsCache.find(x => x.id === id);
  if (!m) return;

  document.getElementById("medEditId").value = m.id;
  document.getElementById("medModalTitle").innerText = "Edit Medication Record";
  document.getElementById("medName").value = m.medication_name;
  document.getElementById("medDosage").value = m.dosage;
  document.getElementById("medFrequency").value = m.frequency;
  document.getElementById("medStart").value = m.start_date || "";
  document.getElementById("medIsCurrent").value = m.is_current ? "true" : "false";
  document.getElementById("medNotes").value = m.notes || "";
  document.getElementById("medModal").classList.add("active");
}

function closeMedModal() {
  document.getElementById("medModal").classList.remove("active");
}

function setupMedForm() {
  const form = document.getElementById("medForm");
  const saveBtn = document.getElementById("btnSaveMed");
  const alertEl = document.getElementById("recordsAlert");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    saveBtn.disabled = true;
    saveBtn.innerText = "Saving...";

    const editId = document.getElementById("medEditId").value;
    const payload = {
      medication_name: document.getElementById("medName").value.trim(),
      dosage: document.getElementById("medDosage").value.trim(),
      frequency: document.getElementById("medFrequency").value.trim(),
      start_date: document.getElementById("medStart").value || null,
      is_current: document.getElementById("medIsCurrent").value === "true",
      notes: document.getElementById("medNotes").value.trim() || null
    };

    try {
      if (editId) {
        await API.patients.updateMedication(parseInt(editId), payload);
      } else {
        await API.patients.createMedication(payload);
      }
      closeMedModal();
      await loadMedications();
      alertEl.className = "alert alert-success";
      alertEl.innerText = "✓ Medication record updated successfully.";
      alertEl.style.display = "block";
    } catch (err) {
      alert("Failed to save medication: " + err.message);
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save Medication";
    }
  });
}

async function handleDeleteMed(id) {
  if (!confirm("Are you sure you want to remove this medication record?")) return;
  try {
    await API.patients.deleteMedication(id);
    await loadMedications();
  } catch (err) {
    alert("Delete failed: " + err.message);
  }
}
