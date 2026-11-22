/**
 * ArogyaAI Authentication & Nav Controller
 * Handles authentication state, dynamic navigation rendering, login, register, and logout.
 */

document.addEventListener("DOMContentLoaded", () => {
  renderNavbar();
  setupAuthForms();
});

function renderNavbar() {
  const token = Storage.getToken();
  const user = Storage.getUser();
  const currentPath = window.location.pathname;

  const navLinksContainer = document.getElementById("navLinks");
  const navAuthContainer = document.getElementById("navAuth");

  if (!navLinksContainer || !navAuthContainer) return;

  if (token && user) {
    // Authenticated Navigation
    navLinksContainer.innerHTML = `
      <li><a href="/dashboard" class="${currentPath === '/dashboard' ? 'active' : ''}">Dashboard</a></li>
      <li><a href="/chat" class="${currentPath === '/chat' ? 'active' : ''}">AI Chat</a></li>
      <li><a href="/triage" class="${currentPath === '/triage' ? 'active' : ''}">Symptom Triage</a></li>
      <li><a href="/medicine" class="${currentPath === '/medicine' ? 'active' : ''}">Medicines</a></li>
      <li><a href="/history" class="${currentPath === '/history' ? 'active' : ''}">Medical History</a></li>
      <li><a href="/medications-page" class="${currentPath === '/medications-page' ? 'active' : ''}">Allergies & Meds</a></li>
    `;

    navAuthContainer.innerHTML = `
      <a href="/profile" class="btn btn-outline btn-sm" title="View Profile">
        👤 ${escapeHtml(user.full_name.split(' ')[0])}
      </a>
      <button onclick="handleLogout()" class="btn btn-outline btn-sm" style="color: var(--emergency);">
        Logout
      </button>
    `;
  } else {
    // Public Navigation
    navLinksContainer.innerHTML = `
      <li><a href="/" class="${currentPath === '/' ? 'active' : ''}">Home</a></li>
      <li><a href="/login" class="${currentPath === '/login' ? 'active' : ''}">Consult Assistant</a></li>
    `;

    navAuthContainer.innerHTML = `
      <a href="/login" class="btn btn-outline btn-sm">Login</a>
      <a href="/register" class="btn btn-primary btn-sm">Register</a>
    `;
  }
}

function setupAuthForms() {
  // Login Form
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const errorBanner = document.getElementById("authError");
      const submitBtn = loginForm.querySelector("button[type='submit']");

      errorBanner.style.display = "none";
      submitBtn.disabled = true;
      submitBtn.innerText = "Signing in...";

      try {
        const response = await API.auth.login({ email, password });
        Storage.setToken(response.access_token);
        Storage.setUser(response.user);
        window.location.href = "/dashboard";
      } catch (err) {
        errorBanner.innerText = err.message || "Failed to log in. Please verify your credentials.";
        errorBanner.style.display = "block";
        submitBtn.disabled = false;
        submitBtn.innerText = "Login";
      }
    });
  }

  // Register Form
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fullName = document.getElementById("fullName").value.trim();
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const confirmPassword = document.getElementById("confirmPassword").value;
      const agreeDisclaimer = document.getElementById("agreeDisclaimer").checked;
      const agreePrivacy = document.getElementById("agreePrivacy").checked;
      const errorBanner = document.getElementById("authError");
      const submitBtn = registerForm.querySelector("button[type='submit']");

      errorBanner.style.display = "none";

      if (password !== confirmPassword) {
        errorBanner.innerText = "Passwords do not match.";
        errorBanner.style.display = "block";
        return;
      }

      if (!agreeDisclaimer || !agreePrivacy) {
        errorBanner.innerText = "You must accept the medical safety disclaimer and privacy terms.";
        errorBanner.style.display = "block";
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerText = "Creating Account...";

      try {
        const response = await API.auth.register({
          full_name: fullName,
          email,
          password,
          agree_medical_disclaimer: agreeDisclaimer,
          agree_privacy_policy: agreePrivacy
        });

        Storage.setToken(response.access_token);
        Storage.setUser(response.user);
        window.location.href = "/dashboard";
      } catch (err) {
        errorBanner.innerText = err.message || "Registration failed. Please check inputs.";
        errorBanner.style.display = "block";
        submitBtn.disabled = false;
        submitBtn.innerText = "Create Patient Account";
      }
    });
  }
}

async function handleLogout() {
  try {
    await API.auth.logout();
  } catch (err) {
    console.warn("Logout API notification failed", err);
  } finally {
    Storage.clear();
    window.location.href = "/";
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, (m) => map[m]);
}
