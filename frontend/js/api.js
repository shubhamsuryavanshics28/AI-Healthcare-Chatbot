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
    sendMessageStream: async (content, conversationId = null, handlers = {}) => {
      const { onToken, onStart, onEmergency, onError, onDone } = handlers;
      const token = Storage.getToken();
      const response = await fetch(`${API_BASE}/chat/message/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ content, conversation_id: conversationId })
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Request failed with status ${response.status}`);
      }

      if (!response.body) {
        throw new Error("ReadableStream not supported by browser environment.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop(); // Keep unfinished chunk in buffer

        for (const block of parts) {
          const trimmed = block.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const payload = JSON.parse(trimmed.replace(/^data:\s*/, ""));
              const pType = payload.type;
              if (pType === "start" && onStart) onStart(payload);
              else if (pType === "token" && onToken) onToken(payload.content);
              else if (pType === "emergency" && onEmergency) onEmergency(payload);
              else if (pType === "error" && onError) onError(payload.message);
              else if (pType === "done" && onDone) onDone(payload);
            } catch (err) {
              console.warn("SSE JSON parse error:", err, block);
            }
          }
        }
      }
    },
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
