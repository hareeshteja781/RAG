const API_BASE = window.API_BASE || 'http://127.0.0.1:8000/';

const state = {
  documents: [],
  conversations: [],
  questionCount: Number(localStorage.getItem('rag_question_count') || '0'),
  currentUser: null,
};

function token() {
  return localStorage.getItem('token');
}

function authHeaders(extra = {}) {
  const jwt = token();
  return jwt ? { ...extra, Authorization: `Bearer ${jwt}` } : extra;
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with status ${response.status}`);
  }
  return data;
}

function showToast(title, message = '', type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3400);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function setButtonLoading(button, loading, text = null) {
  if (!button) return;
  if (loading) {
    button.dataset.originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Working...';
  } else {
    button.disabled = false;
    button.innerHTML = text || button.dataset.originalText || 'Continue';
  }
}

function updateStats() {
  document.getElementById('stat-documents').textContent = state.documents.length;
  document.getElementById('stat-questions').textContent = state.questionCount;
  document.getElementById('stat-conversations').textContent = state.conversations.length;
  document.getElementById('document-count-chip').textContent = state.documents.length;
}

function updateAuthView() {
  const authScreen = document.getElementById('auth-screen');
  const appShell = document.getElementById('app-shell');

  if (token()) {
    authScreen.classList.add('hidden');
    appShell.classList.remove('hidden');
    const email = state.currentUser?.email || 'User';
    document.getElementById('sidebar-user').textContent = email;
    document.getElementById('avatar-initial').textContent = email.charAt(0).toUpperCase();
  } else {
    authScreen.classList.remove('hidden');
    appShell.classList.add('hidden');
  }
}

function switchAuthTab(tab) {
  const loginTab = document.getElementById('tab-login');
  const registerTab = document.getElementById('tab-register');
  const loginPanel = document.getElementById('login-panel');
  const registerPanel = document.getElementById('register-panel');

  const loginActive = tab === 'login';
  loginTab.classList.toggle('active', loginActive);
  registerTab.classList.toggle('active', !loginActive);
  loginPanel.classList.toggle('hidden', !loginActive);
  registerPanel.classList.toggle('hidden', loginActive);
}

async function loadCurrentUser() {
  if (!token()) {
    updateAuthView();
    return;
  }

  try {
    const response = await fetch(`${API_BASE}auth/me`, { headers: authHeaders() });
    state.currentUser = await parseResponse(response);
    updateAuthView();
  } catch (error) {
    localStorage.removeItem('token');
    state.currentUser = null;
    updateAuthView();
    showToast('Session expired', 'Please sign in again.', 'error');
  }
}

async function login() {
  const email = document.getElementById('log-email').value.trim();
  const password = document.getElementById('log-pass').value;
  const button = document.getElementById('btn-login');

  if (!email || !password) {
    showToast('Missing details', 'Enter your email and password.', 'error');
    return;
  }

  setButtonLoading(button, true);
  try {
    const response = await fetch(`${API_BASE}auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await parseResponse(response);
    localStorage.setItem('token', data.access_token);
    document.getElementById('log-email').value = '';
    document.getElementById('log-pass').value = '';
    await loadCurrentUser();
    await Promise.all([loadDocuments(), loadConversations()]);
    showToast('Welcome back', 'Your knowledge workspace is ready.');
  } catch (error) {
    showToast('Login failed', error.message, 'error');
  } finally {
    setButtonLoading(button, false, '<span>Sign in</span><span class="btn-arrow">→</span>');
  }
}

async function register() {
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-pass').value;
  const button = document.getElementById('btn-register');

  if (!email || !password) {
    showToast('Missing details', 'Enter an email and password.', 'error');
    return;
  }

  setButtonLoading(button, true);
  try {
    const response = await fetch(`${API_BASE}users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    await parseResponse(response);
    document.getElementById('reg-email').value = '';
    document.getElementById('reg-pass').value = '';
    switchAuthTab('login');
    document.getElementById('log-email').value = email;
    showToast('Account created', 'You can now sign in to your workspace.');
  } catch (error) {
    showToast('Registration failed', error.message, 'error');
  } finally {
    setButtonLoading(button, false, '<span>Create account</span><span class="btn-arrow">→</span>');
  }
}

function logout() {
  localStorage.removeItem('token');
  state.currentUser = null;
  state.documents = [];
  state.conversations = [];
  document.getElementById('answer-card').classList.add('hidden');
  document.getElementById('answer').textContent = '';
  document.getElementById('question').value = '';
  updateStats();
  updateAuthView();
  switchAuthTab('login');
  showToast('Signed out', 'Your session has been cleared.');
}

function renderDocuments() {
  const list = document.getElementById('doc-list');
  list.innerHTML = '';

  if (!state.documents.length) {
    list.className = 'document-list empty-state';

    list.innerHTML = `
      <div class="empty-icon">✦</div>
      <strong>No documents yet</strong>
      <span>
        Upload a document to start building your knowledge base.
      </span>
    `;

    updateStats();
    return;
  }

  list.className = 'document-list';

  state.documents.forEach((doc) => {
    const item = document.createElement('div');
    item.className = 'document-item';

    const status =
      (doc.processing_status || 'uploaded').toLowerCase();

    const statusClass =
      `status-${status}`;

    const canProcess =
      status !== 'processed' &&
      status !== 'processing';

    item.innerHTML = `
      <div class="doc-icon">DOC</div>

      <div class="doc-copy">
        <strong title="${escapeHtml(doc.filename)}">
          ${escapeHtml(doc.filename)}
        </strong>

        <span>
          ${escapeHtml(formatBytes(doc.file_size))}
          · ID ${escapeHtml(doc.id)}
        </span>

        <span class="status-chip ${statusClass}">
          ${escapeHtml(status)}
        </span>
      </div>

      <div class="doc-actions">

        <button
          class="process-btn"
          type="button"
          data-doc-id="${doc.id}"
          ${canProcess ? '' : 'disabled'}
        >
          ${
            status === 'processed'
              ? 'Ready'
              : status === 'processing'
                ? 'Processing…'
                : 'Process'
          }
        </button>

        <button
          class="delete-btn"
          type="button"
          data-delete-id="${doc.id}"
        >
          Delete
        </button>

      </div>
    `;

    const processButton =
      item.querySelector('.process-btn');

    if (canProcess) {
      processButton.addEventListener(
        'click',
        () => processDocument(doc.id, processButton)
      );
    }

    const deleteButton =
      item.querySelector('.delete-btn');

    deleteButton.addEventListener(
      'click',
      () => deleteDocument(doc.id, doc.filename, deleteButton)
    );

    list.appendChild(item);
  });

  updateStats();
}

async function loadDocuments() {
  if (!token()) return;

  try {
    const response = await fetch(`${API_BASE}documents`, {
      headers: authHeaders()
    });

    state.documents = await parseResponse(response);
    renderDocuments();
  } catch (error) {
    showToast('Could not load documents', error.message, 'error');
  }
}

async function processDocument(id, button) {
  setButtonLoading(button, true);

  try {
    const response = await fetch(`${API_BASE}documents/${id}/process`, {
      method: 'POST',
      headers: authHeaders(),
    });

    const data = await parseResponse(response);

    showToast(
      'Document processed',
      data.detail || 'Embeddings are ready for RAG search.'
    );

    await loadDocuments();
  } catch (error) {
    showToast('Processing failed', error.message, 'error');
    await loadDocuments();
  }
}


/* =========================
   DELETE DOCUMENT
========================= */

async function deleteDocument(id, filename, button) {
  const confirmed = window.confirm(
    `Are you sure you want to delete "${filename}"?\n\n` +
    'This will remove the document from your workspace.'
  );

  if (!confirmed) {
    return;
  }

  setButtonLoading(button, true);

  try {
    const response = await fetch(
      `${API_BASE}documents/${id}`,
      {
        method: 'DELETE',
        headers: authHeaders(),
      }
    );

    const data = await parseResponse(response);

    showToast(
      'Document deleted',
      data.detail || `${filename} was deleted successfully.`
    );

    await loadDocuments();

  } catch (error) {
    showToast(
      'Delete failed',
      error.message,
      'error'
    );

    if (button) {
      button.disabled = false;
      button.innerHTML = 'Delete';
    }
  }
}


async function uploadDocument() {
  if (!token()) {
    showToast('Sign in required', 'Please log in before uploading.', 'error');
    return;
  }

  const input = document.getElementById('file-input');
  const file = input.files[0];
  const button = document.getElementById('btn-upload');

  if (!file) {
    showToast('No file selected', 'Choose a TXT, PDF, or DOCX file.', 'error');
    return;
  }

  const form = new FormData();
  form.append('file', file);
  setButtonLoading(button, true);

  try {
    const response = await fetch(`${API_BASE}documents/upload`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });

    await parseResponse(response);
    input.value = '';
    updateSelectedFile(null);
    await loadDocuments();
    showToast('Upload complete', `${file.name} is now in your document library.`);
  } catch (error) {
    showToast('Upload failed', error.message, 'error');
  } finally {
    setButtonLoading(button, false, 'Upload document <span>→</span>');
  }
}

async function askQuestion() {
  if (!token()) {
    showToast('Sign in required', 'Please log in before asking questions.', 'error');
    return;
  }

  const question = document.getElementById('question').value.trim();
  const button = document.getElementById('btn-query');

  if (!question) {
    showToast('Add a question', 'Type a question about your documents.', 'error');
    return;
  }

  setButtonLoading(button, true);

  try {
    const response = await fetch(`${API_BASE}query`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ question }),
    });

    const data = await parseResponse(response);
    renderAnswer(data);

    state.questionCount += 1;
    localStorage.setItem(
      'rag_question_count',
      String(state.questionCount)
    );

    updateStats();

    showToast(
      'Answer ready',
      'The response was generated from your processed documents.'
    );
  } catch (error) {
    showToast('Question failed', error.message, 'error');
  } finally {
    setButtonLoading(button, false, 'Ask RAG <span>↗</span>');
  }
}

function renderAnswer(data) {
  const card = document.getElementById('answer-card');
  const answer = document.getElementById('answer');
  const sourceList = document.getElementById('source-list');

  answer.textContent = data.answer || 'No answer returned.';
  sourceList.innerHTML = '';

  (data.sources || []).forEach((source) => {
    const chip = document.createElement('div');
    chip.className = 'source-chip';
    chip.innerHTML = `<strong>${escapeHtml(source.filename || 'Document')}</strong> · score ${escapeHtml(source.score ?? '—')}`;
    sourceList.appendChild(chip);
  });

  card.classList.remove('hidden');
  card.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest'
  });
}

async function createConversation() {
  if (!token()) {
    showToast(
      'Sign in required',
      'Please log in before creating a conversation.',
      'error'
    );
    return;
  }

  const button = document.getElementById('btn-new-conv');
  setButtonLoading(button, true);

  try {
    await parseResponse(
      await fetch(`${API_BASE}conversations`, {
        method: 'POST',
        headers: authHeaders(),
      })
    );

    await loadConversations();
    showToast('Conversation created', 'A new conversation is ready.');
  } catch (error) {
    showToast(
      'Could not create conversation',
      error.message,
      'error'
    );
  } finally {
    setButtonLoading(
      button,
      false,
      '+ New conversation'
    );
  }
}

async function loadConversations() {
  if (!token()) return;

  try {
    const response = await fetch(
      `${API_BASE}conversations`,
      {
        headers: authHeaders()
      }
    );

    state.conversations =
      await parseResponse(response);

    renderConversations();
  } catch (error) {
    showToast(
      'Could not load conversations',
      error.message,
      'error'
    );
  }
}

function renderConversations() {
  const list =
    document.getElementById('conv-list');

  list.innerHTML = '';

  if (!state.conversations.length) {
    list.className =
      'conversation-list empty-state';

    list.innerHTML =
      '<div class="empty-icon">◌</div><strong>No conversations yet</strong><span>Start a conversation to keep your Q&A history organized.</span>';

    updateStats();
    return;
  }

  list.className =
    'conversation-list';

  state.conversations.forEach(
    (conversation) => {
      const item =
        document.createElement('div');

      item.className =
        'conversation-item';

      item.innerHTML = `
        <div class="conversation-number">
          ${escapeHtml(conversation.id)}
        </div>
        <div>
          <strong>
            ${escapeHtml(
              conversation.title ||
              'New conversation'
            )}
          </strong>
          <span>
            ${formatDate(
              conversation.updated_at ||
              conversation.created_at
            )}
          </span>
        </div>
      `;

      list.appendChild(item);
    }
  );

  updateStats();
}

function updateSelectedFile(file) {
  const name =
    document.getElementById('file-name');

  const meta =
    document.getElementById('file-meta');

  if (!file) {
    name.textContent =
      'Drop a file here';

    meta.textContent =
      'TXT · PDF · DOCX';

    return;
  }

  name.textContent =
    file.name;

  meta.textContent =
    `${formatBytes(file.size)} · ${file.type || 'document'}`;
}

function formatBytes(bytes) {
  if (bytes == null) return 'Unknown size';

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return 'No date';

  const date =
    new Date(value);

  if (Number.isNaN(date.getTime())) {
    return 'No date';
  }

  return date.toLocaleString(
    [],
    {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }
  );
}

function setupInteractions() {
  document
    .getElementById('tab-login')
    .addEventListener(
      'click',
      () => switchAuthTab('login')
    );

  document
    .getElementById('tab-register')
    .addEventListener(
      'click',
      () => switchAuthTab('register')
    );

  document
    .getElementById('btn-login')
    .addEventListener(
      'click',
      login
    );

  document
    .getElementById('btn-register')
    .addEventListener(
      'click',
      register
    );

  document
    .getElementById('btn-logout')
    .addEventListener(
      'click',
      logout
    );

  document
    .getElementById('btn-upload')
    .addEventListener(
      'click',
      uploadDocument
    );

  document
    .getElementById('btn-query')
    .addEventListener(
      'click',
      askQuestion
    );

  document
    .getElementById('btn-new-conv')
    .addEventListener(
      'click',
      createConversation
    );

  document
    .querySelectorAll('.password-toggle')
    .forEach((toggle) => {
      toggle.addEventListener(
        'click',
        () => {
          const input =
            document.getElementById(
              toggle.dataset.target
            );

          const showing =
            input.type === 'text';

          input.type =
            showing
              ? 'password'
              : 'text';

          toggle.textContent =
            showing
              ? 'Show'
              : 'Hide';
        }
      );
    });

  [
    'log-pass',
    'reg-pass'
  ].forEach((id) => {
    document
      .getElementById(id)
      .addEventListener(
        'keydown',
        (event) => {
          if (event.key === 'Enter') {
            id === 'log-pass'
              ? login()
              : register();
          }
        }
      );
  });

  document
    .getElementById('question')
    .addEventListener(
      'keydown',
      (event) => {
        if (
          event.key === 'Enter' &&
          (event.ctrlKey || event.metaKey)
        ) {
          askQuestion();
        }
      }
    );

  const input =
    document.getElementById('file-input');

  const dropZone =
    document.getElementById('drop-zone');

  input.addEventListener(
    'change',
    () =>
      updateSelectedFile(
        input.files[0] || null
      )
  );

  [
    'dragenter',
    'dragover'
  ].forEach((eventName) => {
    dropZone.addEventListener(
      eventName,
      (event) => {
        event.preventDefault();
        dropZone.classList.add('dragover');
      }
    );
  });

  [
    'dragleave',
    'drop'
  ].forEach((eventName) => {
    dropZone.addEventListener(
      eventName,
      (event) => {
        event.preventDefault();
        dropZone.classList.remove('dragover');
      }
    );
  });

  dropZone.addEventListener(
    'drop',
    (event) => {
      const file =
        event.dataTransfer.files[0];

      if (!file) return;

      const transfer =
        new DataTransfer();

      transfer.items.add(file);
      input.files = transfer.files;

      updateSelectedFile(file);
    }
  );
}

async function initialize() {
  setupInteractions();
  updateStats();

  await loadCurrentUser();

  if (token()) {
    await Promise.all([
      loadDocuments(),
      loadConversations()
    ]);
  }

  updateStats();
}

initialize();