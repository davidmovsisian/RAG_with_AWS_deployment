/**
 * script.js
 * Frontend logic for the RAG Chat Assistant.
 * Uses vanilla JavaScript (no frameworks) to call the Flask API.
 *
 * API endpoints used:
 *   POST /ask    - send a question, get an AI answer + context chunks
 *   POST /upload - upload one or more .txt files
 */

/* =============================================
   Send Question  (/ask)
   ============================================= */

/**
 * Reads the question input and top_k selector, then:
 *  1. Displays the user message immediately.
 *  2. Shows a loading indicator.
 *  3. POSTs to /ask.
 *  4. Replaces the loading indicator with the AI answer (+ sources).
 */
async function sendQuestion() {
    const input   = document.getElementById('questionInput');
    const topK    = parseInt(document.getElementById('topKSelect').value, 10);
    const sendBtn = document.getElementById('sendBtn');
    const question = input.value.trim();

    if (!question) return;

    // Show the user's message in the chat
    appendMessage(question, 'user');
    input.value = '';

    // Disable the button and show a loading placeholder
    sendBtn.disabled = true;
    const loadingEl = appendMessage('Thinking…', 'loading');

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, top_k: topK })
        });

        const data = await response.json();

        // Remove the loading placeholder
        loadingEl.remove();

        if (!response.ok) {
            // API returned an error status
            const msg = data.error || 'An error occurred. Please try again.';
            appendMessage(msg, 'error');
        } else {
            // Build the AI answer element (with optional source chunks)
            appendAIMessage(data);
        }
    } catch (err) {
        // Network or unexpected error
        loadingEl.remove();
        appendMessage('Network error. Please check your connection.', 'error');
    } finally {
        sendBtn.disabled = false;
    }
}

/**
 * Allows the user to press Enter (without Shift) to send the question.
 * @param {KeyboardEvent} event
 */
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendQuestion();
    }
}

/* =============================================
   Upload Files  (/upload)
   ============================================= */

/**
 * Reads the file input and POSTs all selected .txt files to /upload.
 * Displays a status message with the result.
 */
async function uploadFiles() {
    const fileInput   = document.getElementById('fileInput');
    const uploadBtn   = document.getElementById('uploadBtn');
    const statusEl    = document.getElementById('uploadStatus');
    const files       = fileInput.files;

    if (!files || files.length === 0) {
        setStatus(statusEl, 'Please select at least one .txt file.', 'error');
        return;
    }

    // Build multipart form data
    const formData = new FormData();
    for (const file of files) {
        formData.append('files', file);
    }

    // Disable the button while uploading
    uploadBtn.disabled = true;
    setStatus(statusEl, 'Uploading…', '');

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            const msg = data.error || 'Upload failed. Please try again.';
            setStatus(statusEl, msg, 'error');
        } else {
            setStatus(statusEl, data.message || 'Files uploaded successfully.', 'success');
            fileInput.value = ''; // Clear the file input after success
        }
    } catch (err) {
        setStatus(statusEl, 'Network error during upload.', 'error');
    } finally {
        uploadBtn.disabled = false;
    }
}

/* =============================================
   Helper: append messages to the chat box
   ============================================= */

/**
 * Creates and appends a simple text message bubble to the chat box.
 * @param {string} text    - message text
 * @param {string} type    - 'user' | 'ai' | 'error' | 'loading'
 * @returns {HTMLElement}  - the created element (so it can be removed later)
 */
function appendMessage(text, type) {
    const chatBox = document.getElementById('chatBox');
    const el = document.createElement('div');
    el.classList.add('message', type);
    el.textContent = text;
    chatBox.appendChild(el);
    scrollToBottom(chatBox);
    return el;
}

/**
 * Appends an AI response bubble that includes the answer text and,
 * if context chunks are present, a collapsible sources section.
 * @param {Object} data - response from /ask
 */
function appendAIMessage(data) {
    const chatBox = document.getElementById('chatBox');

    const el = document.createElement('div');
    el.classList.add('message', 'ai');

    // Answer text
    const answerEl = document.createElement('p');
    answerEl.textContent = data.answer || '(No answer returned)';
    el.appendChild(answerEl);

    // Source chunks (collapsible) — only shown when context is available
    if (data.context && data.context.length > 0) {
        const details = document.createElement('details');
        details.classList.add('sources');

        const summary = document.createElement('summary');
        summary.textContent = `Sources (${data.context.length} chunk${data.context.length > 1 ? 's' : ''})`;
        details.appendChild(summary);

        data.context.forEach((chunk, idx) => {
            const chunkEl = document.createElement('div');
            chunkEl.classList.add('source-chunk');

            const label = document.createElement('span');
            label.classList.add('chunk-label');
            // Show filename and chunk id if available
            const filename = chunk.filename || 'unknown';
            label.textContent = `[${idx + 1}] ${filename} — chunk ${chunk.chunk_id ?? idx}`;
            chunkEl.appendChild(label);

            const content = document.createElement('span');
            content.textContent = chunk.content || '';
            chunkEl.appendChild(content);

            details.appendChild(chunkEl);
        });

        el.appendChild(details);
    }

    chatBox.appendChild(el);
    scrollToBottom(chatBox);
}

/* =============================================
   Helper: scroll chat to the bottom
   ============================================= */

/**
 * Scrolls the chat box to its bottom so the latest message is visible.
 * @param {HTMLElement} chatBox
 */
function scrollToBottom(chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
}

/* =============================================
   Helper: set upload status message
   ============================================= */

/**
 * Updates the upload status paragraph with text and an optional CSS class.
 * @param {HTMLElement} el     - the status <p> element
 * @param {string}      text   - status text to display
 * @param {string}      type   - '' | 'success' | 'error'
 */
function setStatus(el, text, type) {
    el.textContent = text;
    el.className = 'status-message'; // reset classes
    if (type) el.classList.add(type);
}
