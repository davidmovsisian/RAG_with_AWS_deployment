/**
 * script.js
 * Frontend logic for the RAG Chat Assistant.
 * Uses vanilla JavaScript (no frameworks) to call the Flask API.
 *
 * API endpoints used:
 *   POST   /ask         - send a question, get an AI answer + context chunks
 *   POST   /upload      - upload one or more .txt files
 *   GET    /list-files  - retrieve list of uploaded files
 *   DELETE /delete-file - delete an uploaded file by name
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
            // Wait 1 second for S3/SQS processing before refreshing the file list
            setTimeout(() => {
                loadFiles();
            }, 1000);
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

    el.classList.remove('hidden');

     // 2. Set a timer to hide it after 1 seconds
    setTimeout(() => {
        el.classList.add('hidden');
        
        // Optional: Clear text after fade out finishes (e.g., after 200ms transition)
        setTimeout(() => { el.textContent = ''; }, 200);
    }, 1000);

}

/* =============================================
   File Management  (/list-files, /delete-file)
   ============================================= */

/**
 * Fetches the list of uploaded files from the backend and renders them as tabs.
 */
async function loadFiles() {
    try {
        const response = await fetch('/list-files');
        const data = await response.json();

        if (response.ok) {
            displayFileTabs(data.files || []);
        } else {
            console.error('Error loading files:', data.error);
        }
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

/**
 * Renders the given list of filenames as horizontal pill tabs inside #fileTabs.
 * When the list is empty the CSS ::before pseudo-element shows a placeholder.
 * @param {string[]} files - array of filenames
 */
function displayFileTabs(files) {
    const container = document.getElementById('fileTabs');
    container.innerHTML = '';

    files.forEach(filename => {
        const tab = document.createElement('div');
        tab.className = 'file-tab';

        // File icon removed - no longer needed

        const name = document.createElement('span');
        name.className = 'file-name';
        name.textContent = filename;

        const btn = document.createElement('button');
        btn.className = 'delete-btn';
        btn.textContent = '✕';
        btn.addEventListener('click', () => deleteFile(filename));

        // Only append name and button (no icon)
        tab.appendChild(name);
        tab.appendChild(btn);
        container.appendChild(tab);
    });
}

/**
 * Sends a DELETE request to remove a file, then refreshes the file list.
 * No confirmation dialog is shown (by design).
 * @param {string} filename
 */
async function deleteFile(filename) {
    const statusEl = document.getElementById('uploadStatus');
    // Visually mark the tab as being deleted
    const tabs = document.querySelectorAll('.file-tab');
    tabs.forEach(tab => {
        if (tab.querySelector('.file-name').textContent === filename) {
            tab.classList.add('deleting');
        }
    });

    try {
        const response = await fetch('/delete-file', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });

        const data = await response.json();

        if (response.ok) {
            console.log(`Deleted: ${filename}`);
            setStatus(statusEl, `File deleted successfully: ${filename}`, 'success');
        } else {
            setStatus(statusEl, `Error deleting file: ${data.error || 'An unexpected error occurred.'}`, 'error');
        }
    } catch (error) {
        console.error('Delete error:', error);
        setStatus(statusEl, 'Network error. Please try again.', 'error');
    } finally {
        loadFiles();
    }
}

/**
 * Escapes special HTML characters to prevent XSS when inserting filenames into the DOM.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/* =============================================
   Initialization
   ============================================= */

document.addEventListener('DOMContentLoaded', () => {
    loadFiles();
});
