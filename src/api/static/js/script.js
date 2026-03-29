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

async function uploadFiles() {
    const fileInput   = document.getElementById('fileInput');
    const uploadBtn   = document.getElementById('uploadBtn');
    const statusEl    = document.getElementById('uploadStatus');
    const files       = fileInput.files;

    if (!files || files.length === 0) {
        setStatus(statusEl, 'Please select at least one .txt or .pdf file.', 'error');
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
        const response = await fetch('/upload-files', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            const msg = data.error || 'Upload failed. Please try again.';
            setStatus(statusEl, msg, 'error');
            uploadBtn.disabled = false;
        } else {
            fileInput.value = ''; // Clear the file input after success            
            // Start polling for file readiness
            if (data.job_id) {
                setStatus(statusEl, 'Files uploaded. Syncing Knowledge Base...', '');
                res = await pollSyncStatus(data.job_id, statusEl);
                if (res)
                    loadFiles();
                    uploadBtn.disabled = false;    
            } else {
                setStatus(statusEl, 'Failed to start sync.', 'error');
                uploadBtn.disabled = false;
                // loadFiles();
            }
        }
    } catch (err) {
        setStatus(statusEl, 'Network error during upload.', 'error');
        uploadBtn.disabled = false;
    }
}

/**
 * @param {string} jobId - Job ID for the sync operation
 * @param {HTMLElement} statusEl - Status element to update
 */
async function pollSyncStatus(jobId, statusEl) {
    const maxAttempts = 60; // 60 attempts * 2 seconds = 2 minutes max
    let attempts = 0;
        
    const checkStatus = async () => {
        attempts++;
        
        try {
            const response = await fetch('/check_sync_completion', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ job_id: jobId })
            });
            
            const data = await response.json();
            
            if (data.is_failed) {
                setStatus(statusEl, `Sync failed (Status: ${data.status}).`, 'error');
                return false;
            }
            
            if (data.is_ready) {
                setStatus(statusEl, `Sync complete!`, 'success');
                loadFiles();
                return true;
            }

            if (attempts >= maxAttempts) {
                setStatus(statusEl, 'Sync is taking a long time. Check back later.', 'error');
                return false;
            }
            
            // Poll again after delay
            setTimeout(checkStatus, 2000); // Check every 2 seconds
            
        } catch (error) {
            console.error('Error checking sync:', error);
            setStatus(statusEl, 'Network error while checking sync status.', 'error');}
            return false;
    };
    
    // Start polling immediately
    checkStatus();
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
 * Ensures the chat box is scrolled to show the most recent message.
 * @param {HTMLElement} chatBox
 */
function scrollToBottom(chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
}

/* =============================================
   Helper: set status message
   ============================================= */

/**
 * Updates the text and class of a status element.
 * @param {HTMLElement} el   - the status element
 * @param {string} text       - text to display
 * @param {string} className  - 'success' | 'error' | ''
 */
function setStatus(el, text, className) {
    el.textContent = text;
    el.className = 'status-message';
    if (className) el.classList.add(className);
}

/* =============================================
   List Files  (/list-files)
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
 * Renders file tabs with delete buttons.
 * @param {Array<string>} files - list of filenames
 */
function displayFileTabs(files) {
    const container = document.getElementById('fileTabs');
    container.innerHTML = ''; // Clear existing tabs

    if (!files || files.length === 0) {
        container.innerHTML = '<p class="no-files">No files uploaded yet.</p>';
        return;
    }

    files.forEach(filename => {
        const tab = document.createElement('div');
        tab.classList.add('file-tab');

        // File name
        const nameSpan = document.createElement('span');
        nameSpan.classList.add('file-name');
        nameSpan.textContent = filename;
        tab.appendChild(nameSpan);

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.classList.add('delete-btn');
        deleteBtn.textContent = '×';
        deleteBtn.title = `Delete ${filename}`;
        deleteBtn.onclick = () => deleteFileHandler(filename);
        tab.appendChild(deleteBtn);

        container.appendChild(tab);
    });
}

/* =============================================
   Delete File  (/delete-file)
   ============================================= */

/**
 * Sends a DELETE request to remove a file, then refreshes the list.
 * @param {string} filename
 */
async function deleteFileHandler(filename) {
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
            if (data.job_id) {
                setStatus(statusEl, `Deleting ${filename} and syncing...`, '');
                await pollSyncStatus(data.job_id, statusEl);
            }
        } else {
            setStatus(statusEl, `Error deleting file: ${data.error || 'An unexpected error occurred.'}`, 'error');
        }
    } catch (error) {
        setStatus(statusEl, `Network error while deleting file: ${error.message}`, 'error');
    }

    // Refresh the file list after a short delay
    setTimeout(() => {
        loadFiles();
        // Clear success/error message after displaying files
        setTimeout(() => setStatus(statusEl, '', ''), 3000);
    }, 500);
}

/* =============================================
   Page Load
   ============================================= */

// Load the file list when the page loads
window.addEventListener('DOMContentLoaded', () => {
    loadFiles();
});