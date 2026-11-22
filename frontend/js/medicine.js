/**
 * Medicine Search & Information Controller
 * Connects to curated pharmaceutical repository and renders comprehensive drug monographs.
 */

let allMedsCache = [];

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  setupSearch();
  await executeSearch("");
});

function setupSearch() {
  const searchInput = document.getElementById("medSearchInput");
  const btnSearch = document.getElementById("btnSearch");

  btnSearch.addEventListener("click", () => {
    executeSearch(searchInput.value.trim());
  });

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      executeSearch(searchInput.value.trim());
    }
  });
}

function quickSearch(term) {
  document.getElementById("medSearchInput").value = term;
  executeSearch(term);
}

async function executeSearch(query) {
  const container = document.getElementById("medicinesContainer");
  const countBadge = document.getElementById("resultsCountBadge");
  const statusEl = document.getElementById("searchStatus");

  container.innerHTML = `
    <div style="text-align: center; padding: 3rem; color: var(--text-muted); grid-column: 1 / -1;">
      Searching verified pharmacological reference...
    </div>
  `;

  try {
    const result = await API.medications.search(query);
    allMedsCache = result.results || [];
    countBadge.innerText = `${result.total_found} Found`;
    statusEl.innerText = query ? `Results for "${escapeHtml(query)}"` : "Verified Medications";

    if (allMedsCache.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3rem; color: var(--text-muted); grid-column: 1 / -1;">
          No matching medications found in the verified reference database.<br>
          <em>Please verify the spelling or consult a licensed pharmacist.</em>
        </div>
      `;
      return;
    }

    container.innerHTML = allMedsCache.map(m => `
      <div class="med-card">
        <div class="med-generic">${escapeHtml(m.generic_name)}</div>
        <div class="med-brands">Common Brands: ${escapeHtml(m.brand_names || 'Generic formulation')}</div>
        <div>
          <span class="med-class">${escapeHtml(m.drug_class || 'Pharmaceutical')}</span>
        </div>

        <div style="margin-top: 0.5rem; flex: 1;">
          <div class="med-section-title">Common Uses:</div>
          <div style="font-size: 0.85rem; color: var(--text-main); line-height: 1.4; margin-top: 0.2rem;">
            ${escapeHtml(m.common_uses)}
          </div>
        </div>

        ${m.serious_warnings ? `
          <div class="med-warning-callout">
            <strong>⚠️ Warning:</strong> ${escapeHtml(m.serious_warnings.substring(0, 110))}...
          </div>
        ` : ''}

        <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.725rem; color: var(--text-light);">
            Source: ${escapeHtml(m.source_reference.split('&')[0])}
          </span>
          <button class="btn btn-outline btn-sm" onclick="openMedicineDetail(${m.id})">
            Clinical Details &rarr;
          </button>
        </div>
      </div>
    `).join("");

  } catch (err) {
    container.innerHTML = `
      <div class="alert alert-danger" style="grid-column: 1 / -1;">
        Failed to search medicine database: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function openMedicineDetail(id) {
  const med = allMedsCache.find(m => m.id === id);
  if (!med) return;

  const modalBody = document.getElementById("medModalBody");
  modalBody.innerHTML = `
    <div style="margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.75rem;">
      <h2 style="font-size: 1.4rem; font-weight: 800; color: var(--primary-dark);">
        ${escapeHtml(med.generic_name)}
      </h2>
      <div style="font-size: 0.9rem; color: var(--text-muted); margin-top: 0.2rem;">
        <strong>Common Brands:</strong> ${escapeHtml(med.brand_names || 'Generic')}
      </div>
      <div style="margin-top: 0.4rem;">
        <span class="med-class">${escapeHtml(med.drug_class || 'Pharmaceutical')}</span>
      </div>
    </div>

    <div style="display: flex; flex-direction: column; gap: 1rem; font-size: 0.9rem;">
      <div>
        <h4 style="font-weight: 700; color: var(--text-main);">Clinical Indications & Uses:</h4>
        <p style="color: var(--text-main); margin-top: 0.25rem;">${escapeHtml(med.common_uses)}</p>
      </div>

      ${med.mechanism_of_action ? `
        <div>
          <h4 style="font-weight: 700; color: var(--text-main);">Mechanism of Action:</h4>
          <p style="color: var(--text-main); margin-top: 0.25rem;">${escapeHtml(med.mechanism_of_action)}</p>
        </div>
      ` : ''}

      ${med.serious_warnings ? `
        <div style="background: #fff1f2; border: 1px solid #fecdd3; border-radius: var(--radius-md); padding: 0.85rem;">
          <h4 style="font-weight: 700; color: #9f1239;">🚨 Boxed Warning & Serious Safety Advisory:</h4>
          <p style="color: #881337; margin-top: 0.25rem; font-size: 0.875rem;">${escapeHtml(med.serious_warnings)}</p>
        </div>
      ` : ''}

      ${med.common_side_effects ? `
        <div>
          <h4 style="font-weight: 700; color: var(--text-main);">Common Adverse Effects:</h4>
          <p style="color: var(--text-main); margin-top: 0.25rem;">${escapeHtml(med.common_side_effects)}</p>
        </div>
      ` : ''}

      ${med.precautions ? `
        <div>
          <h4 style="font-weight: 700; color: var(--text-main);">Precautions:</h4>
          <p style="color: var(--text-main); margin-top: 0.25rem;">${escapeHtml(med.precautions)}</p>
        </div>
      ` : ''}

      ${med.contraindications ? `
        <div>
          <h4 style="font-weight: 700; color: var(--emergency);">Contraindications (Do NOT take if):</h4>
          <p style="color: var(--text-main); margin-top: 0.25rem;">${escapeHtml(med.contraindications)}</p>
        </div>
      ` : ''}

      ${med.drug_interactions ? `
        <div>
          <h4 style="font-weight: 700; color: var(--text-main);">Significant Drug Interactions:</h4>
          <p style="color: var(--text-main); margin-top: 0.25rem;">${escapeHtml(med.drug_interactions)}</p>
        </div>
      ` : ''}

      <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.85rem; margin-top: 0.5rem; font-size: 0.825rem;">
        <div><strong>Official Source Reference:</strong> ${escapeHtml(med.source_reference)}</div>
        ${med.source_url ? `
          <div style="margin-top: 0.2rem;">
            <strong>Link:</strong> <a href="${escapeHtml(med.source_url)}" target="_blank" rel="noopener" style="color: var(--primary); text-decoration: underline;">${escapeHtml(med.source_url)}</a>
          </div>
        ` : ''}
        ${med.last_reviewed_date ? `<div style="margin-top: 0.2rem; color: var(--text-muted);">Last Authority Review: ${escapeHtml(med.last_reviewed_date)}</div>` : ''}
      </div>

      <div style="font-size: 0.775rem; color: var(--text-light); line-height: 1.4; border-top: 1px solid var(--border); padding-top: 0.5rem;">
        ⚠️ <em>Disclaimer: Medicine information is strictly educational. Never initiate, stop, or modify prescription drug regimens without formal consultation and direct evaluation from your licensed medical physician.</em>
      </div>
    </div>
  `;

  document.getElementById("medicineDetailModal").classList.add("active");
}

function closeMedicineDetailModal() {
  document.getElementById("medicineDetailModal").classList.remove("active");
}
