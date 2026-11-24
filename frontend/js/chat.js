/**
 * AI Healthcare Chat Controller
 * Manages conversation history, message rendering, RAG source citations, and emergency UI.
 */

let activeConversationId = null;
let isGenerating = false;
let lastSentMessage = "";

document.addEventListener("DOMContentLoaded", async () => {
  const user = Storage.getUser();
  if (!user) {
    window.location.href = "/login";
    return;
  }

  setupChatEvents();
  await loadRAGStatus();
  await loadConversationList();

  // Check URL query parameters for active conversation
  const urlParams = new URLSearchParams(window.location.search);
  const convId = urlParams.get("conv");
  if (convId) {
    await switchConversation(convId);
  }
});

function setupChatEvents() {
  const chatInput = document.getElementById("chatInput");
  const btnSend = document.getElementById("btnSendMessage");
  const btnNewChat = document.getElementById("btnNewChat");
  const btnClearChat = document.getElementById("btnClearChat");

  // Auto-resize textarea
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
  });

  // Enter to send
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  btnSend.addEventListener("click", handleSendMessage);
  btnNewChat.addEventListener("click", startNewConversation);
  btnClearChat.addEventListener("click", clearChatWindow);
}

async function loadRAGStatus() {
  try {
    const status = await API.knowledge.getStatus();
    const badge = document.getElementById("ragStatusBadge");
    if (badge && status.is_ready) {
      badge.innerText = `● RAG Active (${status.total_chunks} Chunks Index)`;
      badge.className = "badge badge-selfcare";
    }
  } catch (err) {
    console.warn("Could not query RAG status", err);
  }
}

async function loadConversationList() {
  const listEl = document.getElementById("conversationList");
  if (!listEl) return;

  try {
    const convs = await API.chat.getHistory();
    if (!convs || convs.length === 0) {
      listEl.innerHTML = `
        <li style="text-align: center; padding: 1.5rem; color: var(--text-light); font-size: 0.85rem;">
          No conversations yet.<br>Ask a health question to begin!
        </li>
      `;
      return;
    }

    listEl.innerHTML = convs.map(c => `
      <li class="chat-history-item ${c.id === activeConversationId ? 'active' : ''}" 
          onclick="switchConversation('${c.id}')" id="convItem_${c.id}">
        <span class="chat-history-title" title="${escapeHtml(c.title)}">
          💬 ${escapeHtml(c.title)}
        </span>
        <button class="chat-delete-btn" onclick="handleDeleteConversation(event, '${c.id}')" title="Delete conversation">
          ✕
        </button>
      </li>
    `).join("");
  } catch (err) {
    console.error("Failed to load conversations", err);
  }
}

async function switchConversation(conversationId) {
  if (isGenerating) return;

  activeConversationId = conversationId;
  const newUrl = `${window.location.pathname}?conv=${conversationId}`;
  window.history.replaceState({ path: newUrl }, '', newUrl);

  // Update sidebar active class
  document.querySelectorAll(".chat-history-item").forEach(el => el.classList.remove("active"));
  const currentItem = document.getElementById(`convItem_${conversationId}`);
  if (currentItem) currentItem.classList.add("active");

  const chatContainer = document.getElementById("chatMessages");
  const typingIndicator = document.getElementById("typingIndicator");

  chatContainer.querySelectorAll(".message-row:not(:first-child)").forEach(el => el.remove());

  try {
    const details = await API.chat.getConversation(conversationId);
    document.getElementById("currentChatTitle").innerText = details.title;

    details.messages.forEach(msg => {
      appendMessageToUI(msg.role, msg.content, msg.citations, msg.safety_flags, msg.created_at);
    });

    scrollToBottom();
  } catch (err) {
    alert("Could not load conversation: " + err.message);
  }
}

function startNewConversation() {
  if (isGenerating) return;
  activeConversationId = null;
  window.history.replaceState({}, '', window.location.pathname);
  document.querySelectorAll(".chat-history-item").forEach(el => el.classList.remove("active"));
  document.getElementById("currentChatTitle").innerText = "New Healthcare Consultation";
  clearChatWindow();
}

function clearChatWindow() {
  const chatContainer = document.getElementById("chatMessages");
  chatContainer.querySelectorAll(".message-row:not(:first-child)").forEach(el => el.remove());
  scrollToBottom();
}

async function handleDeleteConversation(event, conversationId) {
  event.stopPropagation();
  if (!confirm("Are you sure you want to permanently delete this consultation history?")) {
    return;
  }

  try {
    await API.chat.deleteConversation(conversationId);
    if (activeConversationId === conversationId) {
      startNewConversation();
    }
    await loadConversationList();
  } catch (err) {
    alert("Failed to delete conversation: " + err.message);
  }
}

function handleSuggestion(buttonEl) {
  const query = buttonEl.innerText.trim();
  const chatInput = document.getElementById("chatInput");
  chatInput.value = query;
  handleSendMessage();
}

function renderCitationsHtml(citations) {
  if (!citations || citations.length === 0) return "";
  return `
    <div class="citation-container">
      <div class="citation-header">
        <span>📚 Verified Medical Sources Grounding:</span>
      </div>
      ${citations.map((c, i) => `
        <div class="citation-item">
          [${i+1}] <strong>${escapeHtml(c.title)}</strong> 
          ${c.section ? `• <em>${escapeHtml(c.section)}</em>` : ''} 
          ${c.url ? `• <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">Official Link</a>` : ''}
          ${c.relevance_score ? `<span style="opacity: 0.8; font-size: 0.75rem;">(${Math.round(c.relevance_score * 100)}% Match)</span>` : ''}
        </div>
      `).join("")}
    </div>
  `;
}

function renderEmergencyCardHtml(safetyFlags) {
  if (!safetyFlags || !safetyFlags.emergency_detected) return "";
  return `
    <div class="chat-emergency-card">
      <div class="chat-emergency-header">
        <span>🚨 Critical Warning Sign Detected:</span>
        <span>${escapeHtml(safetyFlags.category || "Emergency Escalation")}</span>
      </div>
      <div>Please seek in-person emergency care without delay.</div>
      <div class="emergency-btn-group">
        <a href="tel:112" class="btn btn-danger btn-sm">📞 Call National Emergency 112</a>
        <a href="tel:102" class="btn btn-outline btn-sm" style="color: #991b1b; border-color: #991b1b;">
          🚑 Call Ambulance 102/108
        </a>
      </div>
    </div>
  `;
}

async function handleSendMessage(customText = null) {
  const chatInput = document.getElementById("chatInput");
  const text = customText !== null ? customText.trim() : chatInput.value.trim();

  if (!text || isGenerating) return;

  lastSentMessage = text;

  // Clear input
  if (customText === null) {
    chatInput.value = "";
    chatInput.style.height = "48px";
  }

  // Append user bubble if not a retry
  if (customText === null) {
    appendMessageToUI("user", text, null, null, new Date().toISOString());
    scrollToBottom();
  }

  // Show typing indicator
  setGenerating(true);

  let streamMessageRow = null;
  let bubbleContentEl = null;
  let accumulatedText = "";
  let citationsData = [];
  let safetyFlagsData = null;

  try {
    // Attempt progressive SSE streaming first
    await API.chat.sendMessageStream(text, activeConversationId, {
      onStart: (payload) => {
        citationsData = payload.citations || [];
        safetyFlagsData = payload.safety_flags || null;
        if (payload.conversation_id && !activeConversationId) {
          activeConversationId = payload.conversation_id;
          const newUrl = `${window.location.pathname}?conv=${activeConversationId}`;
          window.history.replaceState({ path: newUrl }, '', newUrl);
          loadConversationList();
        }
      },
      onToken: (token) => {
        if (!streamMessageRow) {
          const indicator = document.getElementById("typingIndicator");
          if (indicator) indicator.style.display = "none";

          streamMessageRow = document.createElement("div");
          streamMessageRow.className = "message-row assistant";
          const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

          streamMessageRow.innerHTML = `
            <div class="message-avatar">AI</div>
            <div class="message-content">
              <div class="message-bubble" id="streamingBubble"></div>
              <span class="message-time">${timeStr}</span>
            </div>
          `;
          const chatContainer = document.getElementById("chatMessages");
          chatContainer.insertBefore(streamMessageRow, indicator);
          bubbleContentEl = streamMessageRow.querySelector("#streamingBubble");
        }
        accumulatedText += token;
        if (bubbleContentEl) {
          bubbleContentEl.innerHTML = formatMarkdown(accumulatedText) +
            renderEmergencyCardHtml(safetyFlagsData) +
            renderCitationsHtml(citationsData);
        }
        scrollToBottom();
      },
      onEmergency: (payload) => {
        const indicator = document.getElementById("typingIndicator");
        if (indicator) indicator.style.display = "none";
        appendMessageToUI("assistant", payload.content, payload.citations, payload.safety_flags, new Date().toISOString());
        scrollToBottom();
      },
      onError: (errMessage) => {
        throw new Error(errMessage);
      },
      onDone: (payload) => {
        if (bubbleContentEl && payload.full_content) {
          bubbleContentEl.innerHTML = formatMarkdown(payload.full_content) +
            renderEmergencyCardHtml(safetyFlagsData) +
            renderCitationsHtml(citationsData);
        }
        scrollToBottom();
      }
    });

  } catch (streamErr) {
    console.warn("Streaming fallback to standard HTTP POST:", streamErr);
    if (!streamMessageRow) {
      try {
        const response = await API.chat.sendMessage(text, activeConversationId);

        // If new conversation, set active ID and reload sidebar
        if (!activeConversationId && response.conversation_id) {
          activeConversationId = response.conversation_id;
          const newUrl = `${window.location.pathname}?conv=${activeConversationId}`;
          window.history.replaceState({ path: newUrl }, '', newUrl);
          await loadConversationList();
        }

        appendMessageToUI(
          "assistant",
          response.content,
          response.citations,
          response.safety_flags,
          response.created_at
        );
        scrollToBottom();
      } catch (err) {
        appendMessageToUI(
          "assistant",
          `⚠️ **Connection Notice:** ${err.message || "Could not reach the healthcare service. Please check your network and retry."}`,
          null,
          { is_error: true, can_retry: true },
          new Date().toISOString()
        );
        scrollToBottom();
      }
    }
  } finally {
    setGenerating(false);
  }
}

function retryLastMessage() {
  if (lastSentMessage && !isGenerating) {
    // Remove last error message bubble if present
    const chatContainer = document.getElementById("chatMessages");
    const lastMsg = chatContainer.querySelector(".message-row:last-of-type");
    if (lastMsg && lastMsg.classList.contains("assistant")) {
      lastMsg.remove();
    }
    handleSendMessage(lastSentMessage);
  }
}

function setGenerating(status) {
  isGenerating = status;
  const indicator = document.getElementById("typingIndicator");
  const btnSend = document.getElementById("btnSendMessage");
  const chatInput = document.getElementById("chatInput");

  if (status) {
    indicator.style.display = "flex";
    btnSend.disabled = true;
    chatInput.disabled = true;
  } else {
    indicator.style.display = "none";
    btnSend.disabled = false;
    chatInput.disabled = false;
    chatInput.focus();
  }
}

function appendMessageToUI(role, content, citations, safetyFlags, timestamp) {
  const chatContainer = document.getElementById("chatMessages");
  const typingIndicator = document.getElementById("typingIndicator");

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
  const formattedHtml = formatMarkdown(content);
  const citationsHtml = renderCitationsHtml(citations);
  const emergencyCardHtml = renderEmergencyCardHtml(safetyFlags);

  let retryButtonHtml = "";
  if (safetyFlags && safetyFlags.can_retry) {
    retryButtonHtml = `
      <div>
        <button class="chat-retry-btn" onclick="retryLastMessage()">
          🔄 Retry Sending Message
        </button>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="message-avatar">${role === 'user' ? '👤' : 'AI'}</div>
    <div class="message-content">
      <div class="message-bubble">
        ${formattedHtml}
        ${emergencyCardHtml}
        ${citationsHtml}
        ${retryButtonHtml}
      </div>
      <span class="message-time">${timeStr}</span>
    </div>
  `;

  // Insert before typing indicator
  chatContainer.insertBefore(row, typingIndicator);
}

function scrollToBottom() {
  const container = document.getElementById("chatMessages");
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

function formatMarkdown(text) {
  if (!text) return "";
  let formatted = escapeHtml(text);

  // Headers: ### Header 3
  formatted = formatted.replace(/^###\s+(.*)$/gm, '<h4 class="chat-heading">$1</h4>');
  
  // Headers: ## Header 2
  formatted = formatted.replace(/^##\s+(.*)$/gm, '<h3 class="chat-heading">$1</h3>');

  // Bold **text**
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Italic *text*
  formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

  // Inline code `code`
  formatted = formatted.replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.06);padding:0.1rem 0.3rem;border-radius:3px;">$1</code>');

  // Blockquotes > text
  formatted = formatted.replace(/^>\s+(.*)$/gm, '<div class="chat-callout">$1</div>');

  // Numbered list items: 1. item
  formatted = formatted.replace(/^\s*(\d+)\.\s+(.*)$/gm, '<div class="chat-list-item"><strong>$1.</strong> $2</div>');

  // Bullet list items: - item or * item
  formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gm, '<div class="chat-list-item">• $1</div>');
  
  // Linebreaks (convert \n to <br> if not already preceded by a block element)
  formatted = formatted.replace(/([^>])\n/g, '$1<br>');

  return formatted;
}
