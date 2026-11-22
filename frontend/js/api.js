/**
 * ArogyaAI API Client
 * Centralized Fetch API client with automatic JWT token management and error handling.
 * Project ID: 26P_3CSE294
 */

const API_BASE = "";

const Storage = {
  getToken: () => localStorage.getItem("arogya_token"),
  setToken: (token) => localStorage.setItem("arogya_token", token),
  removeToken: () => localStorage.removeItem("arogya_token"),
  getUser: () => {
    try {
      return JSON.parse(localStorage.getItem("arogya_user"));
    } catch {
      return null;
    }
  },
  setUser: (user) => localStorage.setItem("arogya_user", JSON.stringify(user)),
  removeUser: () => localStorage.removeItem("arogya_user"),
  clear: () => {
    localStorage.removeItem("arogya_token");
    localStorage.removeItem("arogya_user");
  }
};

async function apiRequest(endpoint, options = {}) {
  const {
    method = "GET",
    body = null,
    requiresAuth = true,
    headers = {}
  } = options;

  const requestHeaders = {
    "Content-Type": "application/json",
    ...headers
  };

  if (requiresAuth) {
    const token = Storage.getToken();
    if (!token) {
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register" && window.location.pathname !== "/") {
        window.location.href = "/login";
      }
      throw new Error("Authentication required");
    }
    requestHeaders["Authorization"] = `Bearer ${token}`;
  }

  const fetchOptions = {
    method,
    headers: requestHeaders
  };

  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    if (response.status === 401 && requiresAuth) {
      Storage.clear();
      window.location.href = "/login?expired=1";
      throw new Error("Session expired. Please log in again.");
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data.detail || data.message || `Request failed (${response.status})`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (error) {
    console.error(`[API Error] ${method} ${endpoint}:`, error.message);
    throw error;
  }
}

// API Service Modules
const API = {
  auth: {
    register: (userData) => apiRequest("/auth/register", { method: "POST", body: userData, requiresAuth: false }),
    login: (credentials) => apiRequest("/auth/login", { method: "POST", body: credentials, requiresAuth: false }),
    me: () => apiRequest("/auth/me"),
    logout: () => apiRequest("/auth/logout", { method: "POST" })
  },
  patients: {
    getDashboard: () => apiRequest("/patients/dashboard"),
    getProfile: () => apiRequest("/patients/profile"),
    updateProfile: (profileData) => apiRequest("/patients/profile", { method: "PUT", body: profileData }),
    
    // Conditions
    getConditions: () => apiRequest("/patients/medical-history"),
    createCondition: (condData) => apiRequest("/patients/medical-history", { method: "POST", body: condData }),
    updateCondition: (id, condData) => apiRequest(`/patients/medical-history/${id}`, { method: "PUT", body: condData }),
    deleteCondition: (id) => apiRequest(`/patients/medical-history/${id}`, { method: "DELETE" }),

    // Allergies
    getAllergies: () => apiRequest("/patients/allergies"),
    createAllergy: (allergyData) => apiRequest("/patients/allergies", { method: "POST", body: allergyData }),
    updateAllergy: (id, allergyData) => apiRequest(`/patients/allergies/${id}`, { method: "PUT", body: allergyData }),
    deleteAllergy: (id) => apiRequest(`/patients/allergies/${id}`, { method: "DELETE" }),

    // Medications
    getMedications: () => apiRequest("/patients/medications"),
    createMedication: (medData) => apiRequest("/patients/medications", { method: "POST", body: medData }),
    updateMedication: (id, medData) => apiRequest(`/patients/medications/${id}`, { method: "PUT", body: medData }),
    deleteMedication: (id) => apiRequest(`/patients/medications/${id}`, { method: "DELETE" })
  },
  chat: {
    sendMessage: (content, conversationId = null) => apiRequest("/chat/message", {
      method: "POST",
      body: { content, conversation_id: conversationId }
    }),
    getHistory: () => apiRequest("/chat/history"),
    getConversation: (id) => apiRequest(`/chat/history/${id}`),
    deleteConversation: (id) => apiRequest(`/chat/history/${id}`, { method: "DELETE" })
  },
  triage: {
    assessSymptoms: (assessmentData) => apiRequest("/triage/assess", { method: "POST", body: assessmentData }),
    getHistory: () => apiRequest("/triage/history"),
    getDetail: (id) => apiRequest(`/triage/history/${id}`)
  },
  medications: {
    search: (query = "") => apiRequest(`/medications/search?q=${encodeURIComponent(query)}`),
    getById: (id) => apiRequest(`/medications/${id}`)
  },
  knowledge: {
    getStatus: () => apiRequest("/knowledge/status"),
    ingest: () => apiRequest("/knowledge/ingest", { method: "POST" })
  }
};
