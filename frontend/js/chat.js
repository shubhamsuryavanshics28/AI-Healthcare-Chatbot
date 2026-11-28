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
      badge.innerText = `â— RAG Active (${status.total_chunks} Chunks Index)`;
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
          ðŸ’¬ ${escapeHtml(c.title)}
        </span>
        <button class="chat-delete-btn" onclick="handleDeleteConversation(event, '${c.id}')" title="Delete conversation">
          âœ•
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
  // Deduplicate citations by title
  const uniqueCitations = [];
  const seen = new Set();
  for (const c of citations) {
    const key = (c.title || "").trim().toLowerCase();
    if (key && !seen.has(key)) {
      seen.add(key);
      uniqueCitations.push(c);
    }
  }
  if (uniqueCitations.length === 0) return "";

  return `
    <div class="citation-container">
      <div class="citation-header">
        <span>ðŸ“š Verified Clinical Guidelines Referenced:</span>
      </div>
      ${uniqueCitations.map((c, i) => `
        <div class="citation-item">
          [${i+1}] <strong>${escapeHtml(c.title)}</strong>
          ${c.source && c.source !== 'Official Medical Reference' ? `(${escapeHtml(c.source)})` : ''}
          ${c.section && c.section !== 'General Overview' ? `â€¢ <em>${escapeHtml(c.section)}</em>` : ''}
          ${c.url ? `â€¢ <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener">Official Guideline Link</a>` : ''}
        </div>
      `).join("")}
    </div>
  `;
}

function renderEmergencyCardHtml(safetyFlags, rawContent = "") {
  if (!safetyFlags || !safetyFlags.emergency_detected) return "";
  const triggersList = Array.isArray(safetyFlags.triggers) && safetyFlags.triggers.length > 0
    ? `<div style="margin: 0.5rem 0; font-size: 0.88rem; color: #7f1d1d;">
         <strong>Detected Warning Symptoms:</strong><br/>
         ${safetyFlags.triggers.map(t => `<span class="badge badge-emergency" style="display:inline-block; margin: 0.2rem 0.3rem 0.2rem 0; font-size: 0.82rem; padding: 0.25rem 0.5rem;">âš ï¸ ${escapeHtml(t)}</span>`).join(" ")}
       </div>`
    : "";

  // Extract clean clinical guidance text if present in raw content
  let guidanceText = "";
  if (rawContent) {
    const paragraphs = rawContent.split("\n\n");
    for (const p of paragraphs) {
      const cleanP = p.trim();
      if (cleanP && !cleanP.startsWith("ðŸš¨") && !cleanP.startsWith("**Detected") && !cleanP.startsWith("ðŸ“ž") && !cleanP.startsWith("âš ï¸")) {
        guidanceText = cleanP;
        break;
      }
    }
  }
  if (!guidanceText) {
    guidanceText = "These symptoms indicate a critical medical situation requiring immediate professional assessment.";
  }

  return `
    <div class="chat-emergency-card" style="border: 2px solid #dc2626; background: #fef2f2; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
      <div class="chat-emergency-header" style="font-weight: 700; color: #991b1b; font-size: 1.05rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
        <span>ðŸš¨ Critical Warning Signs Detected â€” Possible Medical Emergency</span>
      </div>
      <div style="color: #1f2937; line-height: 1.5; margin-bottom: 0.5rem;">
        ${escapeHtml(guidanceText)}
      </div>
      ${triggersList}
      <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 0.6rem 0.75rem; margin: 0.75rem 0; font-size: 0.88rem; color: #7f1d1d; border-radius: 4px;">
        <strong>âš ï¸ Immediate Safety Actions:</strong>
        <ul style="margin: 0.25rem 0 0 1.2rem; padding: 0;">
          <li>Seek emergency hospital care immediately. <strong>DO NOT drive yourself.</strong></li>
          <li>Cease physical exertion and sit or lie in a comfortable resting position.</li>
          <li>If someone is nearby, have them stay with you while awaiting responders.</li>
        </ul>
      </div>
      <div class="emergency-btn-group" style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem;">
        <a href="tel:112" class="btn btn-danger btn-sm" style="font-weight: 600; padding: 0.45rem 0.85rem;">ðŸ“ž Call National Emergency 112</a>
        <a href="tel:102" class="btn btn-outline btn-sm" style="color: #991b1b; border: 1px solid #991b1b; font-weight: 600; padding: 0.45rem 0.85rem;">
          ðŸš‘ Call Ambulance 102 / 108
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
          `âš ï¸ **Connection Notice:** ${err.message || "Could not reach the healthcare service. Please check your network and retry."}`,
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

  let bubbleInnerHtml = "";
  if (safetyFlags && safetyFlags.emergency_detected) {
    // Single consolidated emergency alert: no duplicate markdown text or duplicated contact blocks
    bubbleInnerHtml = renderEmergencyCardHtml(safetyFlags, content);
  } else {
    const formattedHtml = formatMarkdown(content);
    const citationsHtml = renderCitationsHtml(citations);
    let retryButtonHtml = "";
    if (safetyFlags && safetyFlags.can_retry) {
      retryButtonHtml = `
        <div>
          <button class="chat-retry-btn" onclick="retryLastMessage()">
            ðŸ”„ Retry Sending Message
          </button>
        </div>
      `;
    }
    bubbleInnerHtml = formattedHtml + citationsHtml + retryButtonHtml;
  }

  row.innerHTML = `
    <div class="message-avatar">${role === 'user' ? 'ðŸ‘¤' : 'AI'}</div>
    <div class="message-content">
      <div class="message-bubble">
        ${bubbleInnerHtml}
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
  formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gm, '<div class="chat-list-item">â€¢ $1</div>');

  // Linebreaks (convert \n to <br> if not already preceded by a block element)
  formatted = formatted.replace(/([^>])\n/g, '$1<br>');

  return formatted;
}
