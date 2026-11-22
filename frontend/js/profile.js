/**
 * Patient Profile Controller
 * Manages loading and updating patient demographic and emergency contact records.
 */

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  await loadProfile();
  setupProfileForm();
});

async function loadProfile() {
  const alertEl = document.getElementById("profileAlert");
  try {
    const profile = await API.patients.getProfile();
    if (profile) {
      if (profile.date_of_birth) document.getElementById("dob").value = profile.date_of_birth;
      if (profile.gender) document.getElementById("gender").value = profile.gender;
      if (profile.blood_group) document.getElementById("bloodGroup").value = profile.blood_group;
      if (profile.height_cm) document.getElementById("heightCm").value = profile.height_cm;
      if (profile.weight_kg) document.getElementById("weightKg").value = profile.weight_kg;
      if (profile.emergency_contact_name) document.getElementById("emergName").value = profile.emergency_contact_name;
      if (profile.emergency_contact_phone) document.getElementById("emergPhone").value = profile.emergency_contact_phone;
      if (profile.emergency_contact_relation) document.getElementById("emergRelation").value = profile.emergency_contact_relation;
      if (profile.general_notes) document.getElementById("generalNotes").value = profile.general_notes;
    }
  } catch (err) {
    alertEl.className = "alert alert-danger";
    alertEl.innerText = "Failed to load profile: " + err.message;
    alertEl.style.display = "block";
  }
}

function setupProfileForm() {
  const form = document.getElementById("profileForm");
  const alertEl = document.getElementById("profileAlert");
  const saveBtn = document.getElementById("btnSaveProfile");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    alertEl.style.display = "none";
    saveBtn.disabled = true;
    saveBtn.innerText = "Saving Updates...";

    const payload = {
      date_of_birth: document.getElementById("dob").value || null,
      gender: document.getElementById("gender").value || null,
      blood_group: document.getElementById("bloodGroup").value || null,
      height_cm: parseFloat(document.getElementById("heightCm").value) || null,
      weight_kg: parseFloat(document.getElementById("weightKg").value) || null,
      emergency_contact_name: document.getElementById("emergName").value.trim() || null,
      emergency_contact_phone: document.getElementById("emergPhone").value.trim() || null,
      emergency_contact_relation: document.getElementById("emergRelation").value.trim() || null,
      general_notes: document.getElementById("generalNotes").value.trim() || null
    };

    try {
      await API.patients.updateProfile(payload);
      alertEl.className = "alert alert-success";
      alertEl.innerText = "✓ Patient profile updated successfully.";
      alertEl.style.display = "block";
    } catch (err) {
      alertEl.className = "alert alert-danger";
      alertEl.innerText = "Failed to update profile: " + err.message;
      alertEl.style.display = "block";
    } finally {
      saveBtn.disabled = false;
      saveBtn.innerText = "Save Profile Updates";
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });
}
