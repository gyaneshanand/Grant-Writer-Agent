const API_URL = 'http://localhost:8000/api/v1/chatbot/chat';

// State
let state = {
    session_id: crypto.randomUUID(), // Generate a UUID if not provided by backend initially
    conversation_history: [],
    mode: 'stateless', // 'stateless' or 'stateful'
    isWaiting: false
};

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');

// Initialize
function init() {
    userInput.focus();
    setupEventListeners();
}

function setupEventListeners() {
    // Send message on click
    sendBtn.addEventListener('click', sendMessage);

    // Send message on Enter (Shift+Enter for new line)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    userInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        toggleSendButton();
    });

    // New Chat
    newChatBtn.addEventListener('click', () => {
        location.reload(); // Simple reload to clear state for now
    });
}

function toggleSendButton() {
    if (userInput.value.trim().length > 0) {
        sendBtn.removeAttribute('disabled');
    } else {
        sendBtn.setAttribute('disabled', 'true');
    }
}

function setInput(text) {
    userInput.value = text;
    toggleSendButton();
    userInput.focus();
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || state.isWaiting) return;

    // UI Updates
    addMessageToUI('user', message);
    userInput.value = '';
    userInput.style.height = 'auto';
    toggleSendButton();
    state.isWaiting = true;

    // Add loading indicator
    const loadingId = addLoadingIndicator();

    // Prepare Request Payload
    const payload = {
        message: message,
        session_id: state.session_id,
        conversation_mode: state.mode,
        conversation_history: state.conversation_history
    };

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }

        const data = await response.json();

        // Update State
        state.session_id = data.session_id;
        state.conversation_history = data.conversation_history;

        // Remove loading and show response
        removeLoadingIndicator(loadingId);
        addMessageToUI('assistant', data.response);

        // Render Search Results if any
        if (data.search_results && data.search_results.length > 0) {
            addSearchResults(data.search_results);
        }

    } catch (error) {
        console.error('Error:', error);
        removeLoadingIndicator(loadingId);
        addMessageToUI('assistant', 'Sorry, something went wrong. Please ensure the backend server is running.');
    } finally {
        state.isWaiting = false;
        userInput.focus();
    }
}

function addMessageToUI(role, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;

    // Parse Markdown
    const formattedText = marked.parse(text);

    messageDiv.innerHTML = `
        <div class="avatar">
            <i class="fa-solid ${role === 'user' ? 'fa-user' : 'fa-robot'}"></i>
        </div>
        <div class="message-content">
            <p>${formattedText}</p>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addLoadingIndicator() {
    const id = 'loading-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message assistant-message`;
    messageDiv.id = id;

    messageDiv.innerHTML = `
        <div class="avatar">
            <i class="fa-solid fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeLoadingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function addSearchResults(results) {
    const container = document.createElement('div');
    container.className = 'message assistant-message';

    // Start building cards HTML
    let cardsHtml = '<div class="grant-results">';

    results.forEach(grant => {
        const amount = grant.amount_high
            ? `$${grant.amount_low?.toLocaleString()} - $${grant.amount_high?.toLocaleString()}`
            : 'Amount varies';

        // Use a simpler concatenation approach
        const card = `
            <div class="grant-card">
                <div>
                    <h3>${grant.opportunity_title}</h3>
                    <p>${grant.description || 'No description available.'}</p>
                </div>
                <div class="grant-meta">
                    <span class="grant-amount">${amount}</span>
                    <span>Deadline: ${grant.deadline_at || 'Open'}</span>
                </div>
            </div>
        `;
        cardsHtml += card;
    });

    cardsHtml += '</div>';

    container.innerHTML = `
        <div class="avatar" style="visibility: hidden"><i class="fa-solid fa-robot"></i></div>
        <div style="flex-grow: 1">${cardsHtml}</div>
    `;

    chatMessages.appendChild(container); // Fix: Append to chatMessages, not container itself
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Start
init();
